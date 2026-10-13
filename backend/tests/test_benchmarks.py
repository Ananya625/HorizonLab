from pathlib import Path
import pytest
from pydantic import ValidationError
from fastapi.testclient import TestClient
from app.main import app
from app.models.benchmark import ExperimentManifest
from app.services.benchmark_service import benchmark_service, SoftwareEnvironment
from app.services.benchmark_analysis import summarize, prediction_metrics


def small_manifest(**updates):
    return ExperimentManifest(task_ids=['sum_fix'], task_lengths=[5], repetitions=1, **updates)


@pytest.mark.parametrize('kind,expected', [
    ('none', {'baseline':True, 'generic_retry':True, 'idempotent_retry':True}),
    ('transient', {'baseline':False, 'generic_retry':True, 'idempotent_retry':True}),
    ('timeout_after_commit', {'baseline':False, 'generic_retry':False, 'idempotent_retry':True}),
])
def test_controlled_conditions(database, kind, expected):
    report = benchmark_service.run(small_manifest(fault={'kind':kind}))
    assert report['status'] == 'completed'
    assert {r['condition']:r['verified_success'] for r in report['trials']} == expected
    assert len({r['initial_state']['source_digest'] for r in report['trials']}) == 1
    assert len({r['run_id'] for r in report['trials']}) == 3
    for row in report['trials']:
        assert row['tool_calls'] == len(row['events'])
        assert database.get_evaluation(row['run_id']).verified_success == row['verified_success']
    if kind == 'timeout_after_commit':
        generic = next(r for r in report['trials'] if r['condition']=='generic_retry')
        assert generic['verification']['duplicate_effects'] == 1
        assert generic['recovery_episodes'][0]['local_action_succeeded'] is True
        assert generic['recovery_episodes'][0]['verified_recovered'] is False


def test_all_five_tasks(database):
    report = benchmark_service.run(ExperimentManifest(task_lengths=[5], repetitions=1, conditions=['baseline']))
    assert len(report['trials']) == 5
    assert all(r['verified_success'] for r in report['trials'])


def test_budget_and_untriggered_fault(database):
    report = benchmark_service.run(small_manifest(max_steps=2, fault={'kind':'transient'}))
    assert all(r['termination_reason']=='budget_exceeded' for r in report['trials'])
    assert all(not r['fault_occurred'] and not r['verified_success'] for r in report['trials'])
    assert all(r['fault_not_triggered_reason'] for r in report['trials'])


def test_zero_retry_baseline(database):
    report = benchmark_service.run(small_manifest(max_retries=0, fault={'kind':'transient'}))
    assert all(not r['verified_success'] for r in report['trials'])
    assert all(r['recovery_episodes'][0]['attempts']==0 for r in report['trials'])


def test_resume_does_not_repeat_completed_trials(database):
    manifest = small_manifest()
    first = benchmark_service.run(manifest)
    second = benchmark_service.run(manifest, first['experiment_id'])
    assert second == first
    assert len(database.list_all_runs()) == 3


def test_private_checks_and_workspace_isolation(database):
    report = benchmark_service.run(small_manifest())
    rows = [database.get_run_record(r['run_id']) for r in report['trials']]
    assert len({r.repo_path for r in rows}) == 3
    first = Path(rows[0].repo_path)/'solution.py'
    first.write_text('broken')
    assert (Path(rows[1].repo_path)/'solution.py').read_text() != 'broken'
    capabilities = benchmark_service.capabilities()
    assert all('solution' not in t and 'cases' not in t for t in capabilities['tasks'])


def test_final_verifier_rejects_changed_source(tmp_path):
    env = SoftwareEnvironment('sum_fix', tmp_path/'trial', small_manifest())
    for tool in ['apply_patch','run_checks','commit','notify']:
        env.call(tool, tool)
    assert env.verify()['verified_success']
    env.source_path.write_text('raise RuntimeError("must not execute")')
    assert not env.verify()['verified_success']


def test_ordering_and_idempotency(tmp_path):
    env = SoftwareEnvironment('sum_fix', tmp_path/'trial', small_manifest())
    with pytest.raises(ValueError):
        env.call('notify', 'bad')
    for tool in ['apply_patch','run_checks','commit','notify']:
        env.call(tool, tool)
    env.call('commit', 'commit')
    assert len(env.commits) == 1
    assert not env.verify()['verified_success']  # Earlier prohibited effect remains visible.


@pytest.mark.parametrize('updates', [
    {'conditions':['enhanced_agent']}, {'task_ids':['unknown']}, {'task_lengths':[0]},
    {'repetitions':21}, {'conditions':['baseline','baseline']},
    {'fault':{'kind':'timeout_after_commit','tool':'read'}}, {'execution_mode':'real_model'},
    {'timeout_seconds':float('nan')}, {'seed':-1}, {'task_lengths':[5,5]},
])
def test_manifest_rejects_unsupported(updates):
    with pytest.raises(ValidationError):
        ExperimentManifest(**updates)


def test_analysis_matches_trials(database):
    report = benchmark_service.run(small_manifest(fault={'kind':'timeout_after_commit'}))
    assert summarize(report['trials']) == report['comparisons']
    for group in report['comparisons']:
        assert group['sample_count'] == 1
        assert group['stdev_duration_seconds'] is None
        assert group['success_ci95'][0] <= group['verified_success_rate'] <= group['success_ci95'][1]


def test_prediction_adapter_rejects_future_evidence():
    event = dict(probability=.8, threshold=.5, step=2, feature_end_step=3,
                 eventual_failure=True, model_version='test', run_id='r', split='evaluation', failure_step=5)
    with pytest.raises(ValueError):
        prediction_metrics([event])
    event['feature_end_step'] = 2
    result = prediction_metrics([event])
    assert result['recall'] == 1 and result['mean_warning_lead_steps'] == 3
    assert result['brier_score'] == pytest.approx(.04)


def test_benchmark_api(database):
    client = TestClient(app)
    assert client.get('/api/benchmarks/capabilities').json()['execution_mode']=='trusted_simulation'
    invalid = client.post('/api/benchmarks/experiments', json={'conditions':['enhanced_agent']})
    assert invalid.status_code == 422
    result = client.post('/api/benchmarks/experiments', json=small_manifest().model_dump())
    assert result.status_code == 200
    report = result.json()
    assert client.get('/api/benchmarks/experiments/'+report['experiment_id']).json() == report
