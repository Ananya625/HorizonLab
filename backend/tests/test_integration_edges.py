import asyncio
from pathlib import Path
import pytest
from app.models.schema import RecoveryAttempt
from app.services.goal_parser_service import goal_parser_service
from app.services.verifier_service import verifier_service
from app.services.benchmark_service import benchmark_service, SoftwareEnvironment
from app.models.benchmark import ExperimentManifest
from app.services.benchmark_analysis import validate_split_isolation, memory_metrics


@pytest.mark.asyncio
async def test_initial_pipeline_stops_at_confirmation(database, tmp_path, monkeypatch):
    from app.services.orchestrator_service import orchestrator_service
    from app.services.ollama_service import ollama_service
    async def model(**kwargs):
        return {'message':{'content':'{"main_goal":"Test","summary":"Test","success_criteria":[]}'}}
    monkeypatch.setattr(ollama_service, 'chat_completion', model)
    record = await orchestrator_service.run_full_pipeline('Test', repo_path=str(tmp_path), temperature=0, max_recovery_retries=0)
    assert record.goal_model.task_id == record.task_id
    assert not record.goal_model.is_confirmed
    assert record.plan is None and record.evaluation is None
    assert record.metadata['config']['max_recovery_retries'] == 0


def test_recovery_episode_roundtrip(database, run):
    episode = RecoveryAttempt(id='episode', run_id='r1', attempt_number=1, failure_reason='x', diagnosis='unknown', root_cause_analysis='unknown', proposed_fix='retry', started_at='start')
    database.save_recovery_attempt(episode)
    episode.local_tests_passed = True
    episode.duration_seconds = .04
    database.save_recovery_attempt(episode)
    records = database.get_recovery_attempts('r1')
    assert len(records) == 1 and records[0].duration_seconds == .04
    assert not records[0].resolved and records[0].verified_recovered is None


def test_interrupted_experiment_retains_failed_run(database, monkeypatch):
    def fail(*args, **kwargs):
        raise OSError('workspace unavailable')
    monkeypatch.setattr(SoftwareEnvironment, '__init__', fail)
    with pytest.raises(OSError):
        benchmark_service.run(ExperimentManifest(task_ids=['sum_fix'], task_lengths=[5], conditions=['baseline'], repetitions=1))
    experiment = database.get_experiments()[0]
    assert experiment['status'] == 'interrupted' and experiment['active_trial']
    assert database.get_evaluation(experiment['active_trial']).outcome == 'error'


def test_memory_labels_and_split_isolation():
    metrics = memory_metrics([
        dict(relevant_available=True, relevant_retrieved=False, incorrect_retrieved=False, used_correctly=False),
        dict(relevant_available=False, relevant_retrieved=False, incorrect_retrieved=True, used_correctly=False),
    ])
    assert metrics['missing_memory_rate'] == .5
    assert metrics['available_but_not_retrieved_rate'] == 1
    with pytest.raises(ValueError):
        validate_split_isolation([{'run_id':'train', 'task_template_id':'same'}], [{'run_id':'eval','task_template_id':'same'}])


def test_budgets_count_retries(database):
    manifest = ExperimentManifest(task_ids=['sum_fix'], task_lengths=[5], repetitions=1,
        conditions=['idempotent_retry'], max_steps=5, fault={'kind':'transient'})
    row = benchmark_service.run(manifest)['trials'][0]
    assert row['termination_reason'] == 'budget_exceeded'
    assert row['tool_calls'] == 5 and not row['verified_success']


def test_trace_export_complete(database, run):
    from fastapi.testclient import TestClient
    from app.main import app
    for i in range(210):
        database.add_log('r1','test','agent','info',str(i))
    client = TestClient(app)
    assert len(client.get('/api/runs/r1/export').json()['logs']) == 210
    page = client.get('/api/runs/r1/logs?limit=10&offset=200').json()['logs']
    assert len(page)==10 and page[0]['step']==1
    latest = client.get('/api/runs/r1/logs?limit=10').json()['logs']
    assert len(latest) == 10 and latest[0]['step'] == 201


def test_stale_verdict_masked_on_direct_api(database, run):
    from app.models.schema import EvaluationMetrics, VerificationReport, CriterionVerification
    from fastapi.testclient import TestClient
    from app.main import app
    database.finalize_run(EvaluationMetrics(run_id='r1', task_id='t1', metric_version='2',
        verified_success=True, outcome='success'), VerificationReport(id='v', run_id='r1',
        verifier_version='2', overall_verdict='VERIFIED_PASSED', verified_success=True,
        review_summary='passed', criteria_evaluations=[CriterionVerification(criterion_id='c',
        criterion_description='c', verdict='PASS', evidence='old')]))
    database.invalidate_evaluation('r1', 'goal edited')
    report = TestClient(app).get('/api/verifier/r1').json()
    assert report['overall_verdict'] == 'UNVERIFIED' and report['verified_success'] is None
    assert report['criteria_evaluations'][0]['verdict'] == 'UNVERIFIED'


def test_manual_stage_error_persisted(database, run, monkeypatch):
    from app.api.routes import planner_service
    from fastapi.testclient import TestClient
    from app.main import app
    async def fail(**kwargs):
        raise RuntimeError('unavailable')
    monkeypatch.setattr(planner_service, 'generate_plan', fail)
    response = TestClient(app).post('/api/planner/generate', json={'run_id':'r1'})
    assert response.status_code == 500
    assert database.get_evaluation('r1').termination_reason == 'planner:RuntimeError'
    assert database.get_run_record('r1').status == 'failed'


def test_invalid_stage_request_is_not_failed_trial(database, run):
    from fastapi.testclient import TestClient
    from app.main import app
    response = TestClient(app).post('/api/verifier/verify', json={'run_id':'r1'})
    assert response.status_code == 400 and database.get_evaluation('r1') is None


def test_simulation_and_workflow_stats_separated(database, run):
    from app.models.schema import EvaluationMetrics
    database.finalize_run(EvaluationMetrics(run_id='r1', task_id='t1', metric_version='2',
        execution_mode='mixed_demo', verified_success=False, outcome='failed', total_tool_calls=0))
    benchmark_service.run(ExperimentManifest(task_ids=['sum_fix'], task_lengths=[5], conditions=['baseline'], repetitions=1))
    stats = database.get_aggregate_evaluations()
    groups = {g['execution_mode']:g for g in stats['by_execution_mode']}
    assert groups['mixed_demo']['verified_success_rate'] == 0
    assert groups['trusted_simulation']['verified_success_rate'] == 1
    assert stats['aggregate_stats']['total_tool_calls'] == 5


def test_final_verification_respects_time_budget(database, monkeypatch):
    import time
    original = SoftwareEnvironment.verify
    def delayed(self):
        result = original(self)
        self.started = time.perf_counter()-2
        return result
    monkeypatch.setattr(SoftwareEnvironment, 'verify', delayed)
    row = benchmark_service.run(ExperimentManifest(task_ids=['sum_fix'], task_lengths=[5],
        conditions=['baseline'], repetitions=1, timeout_seconds=1))['trials'][0]
    assert all(row['verification']['criteria'].values())
    assert row['termination_reason'] == 'budget_exceeded' and not row['verified_success']
    assert database.get_evaluation(row['run_id']).outcome == 'budget_exceeded'


@pytest.mark.asyncio
async def test_merged_tracking_does_not_approve_unsupported_goal(database, run):
    from app.models.goal_model import GoalModel, SuccessCriterion
    from app.services.goal_tracker_service import goal_tracker_service
    from app.services.drift_controller_service import drift_controller_service
    goal = GoalModel(run_id='r1', task_id='t1', original_request='Test', normalized_request='Test',
        main_goal='Test', summary='Test', is_confirmed=True,
        success_criteria=[SuccessCriterion(id='c', description='Must satisfy performance requirements', metric='latency')])
    database.save_goal_model(goal)
    goal_tracker_service.initialize_task('r1', 't1', 'Test', acceptance_criteria=[c.model_dump() for c in goal.success_criteria])
    drift_controller_service.validate_result('r1', 'test_run', 'pytest', True,
        {'exit_code':0, 'passed_tests':1, 'failed_tests':0, 'total_tests':1})
    report = await verifier_service.verify_run('r1')
    assert report.verified_success is None
    assert goal_tracker_service.get_state('r1').acceptance_criteria[0].status == 'pending'
    assert not drift_controller_service.check_completion('r1').allowed


def test_merged_revision_invalidates_goal_and_evidence(database, run):
    from app.models.goal_model import GoalModel
    from app.models.schema import EvaluationMetrics
    from app.services.goal_tracker_service import goal_tracker_service
    from fastapi.testclient import TestClient
    from app.main import app
    database.save_goal_model(GoalModel(run_id='r1', task_id='t1', original_request='Test',
        normalized_request='Test', main_goal='Test', summary='Test', is_confirmed=True))
    database.finalize_run(EvaluationMetrics(run_id='r1',task_id='t1',verified_success=True,outcome='success'))
    goal_tracker_service.initialize_task('r1','t1','Test')
    goal_tracker_service.verify_criterion('r1','all',True,'Old evidence')
    response = TestClient(app).post('/api/goals/revise',json={'run_id':'r1','new_goal':'Revised task'})
    assert response.status_code == 200, response.text
    goal = database.get_goal_model('r1')
    assert goal.main_goal == 'Revised task' and goal.original_request == 'Test'
    assert not goal.is_confirmed and goal.goal_model_version != '1.0'
    assert database.get_evaluation('r1').evidence_stale
    state = goal_tracker_service.get_state('r1')
    assert state.current_goal == goal.main_goal and len(state.revision_history) == 1
    assert not goal_tracker_service.can_complete('r1')


def test_merged_recovery_persists_both_versions_fields(database, run):
    first = RecoveryAttempt(id='old', run_id='r1', attempt_number=1, failure_reason='failure',
        diagnosis='unknown', root_cause_analysis='unknown', proposed_fix='retry')
    database.save_recovery_attempt(first)
    updated = first.model_copy(update={'id':'new', 'duration_seconds':0.2, 'local_tests_passed':True,
        'subsequent_test_run_id':'after', 'test_result_status':'PASSED', 'error_summary':'traceback'})
    database.save_recovery_attempt(updated)
    rows = database.get_recovery_attempts('r1')
    assert len(rows) == 1 and rows[0].id == 'old'
    assert rows[0].duration_seconds == 0.2 and rows[0].local_tests_passed
    assert rows[0].subsequent_test_run_id == 'after' and rows[0].test_result_status == 'PASSED'
    assert rows[0].error_summary == 'traceback' and not rows[0].resolved
