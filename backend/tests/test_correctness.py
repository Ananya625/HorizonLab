import asyncio
import json
import subprocess
from pathlib import Path
import pytest
from pydantic import ValidationError
from app.models.schema import GoalModel, SuccessCriterion, Constraint, EvaluationMetrics, RunPipelineRequest
from app.services.workspace_service import workspace_service
from app.services.test_runner_service import test_runner_service
from app.services.verifier_service import verifier_service


def test_zero_and_request_validation():
    request = RunPipelineRequest(request_text='test', temperature=0, max_recovery_retries=0)
    assert request.temperature == request.max_recovery_retries == 0
    with pytest.raises(ValidationError):
        RunPipelineRequest(request_text='test', max_recovery_retries=-1)


@pytest.mark.parametrize('path', ['../outside', '/etc/passwd', 'C:/outside', '.git/config', 'a/../../x', 'test.py:stream', '.GiT/config', '.EVALUATOR/answer', '.git /config', 'CON', 'COM1.txt'])
def test_path_escape_rejected(tmp_path, path):
    with pytest.raises(ValueError):
        workspace_service.resolve_path(str(tmp_path), path)


def test_symlink_escape_rejected(tmp_path):
    outside = tmp_path / 'outside'
    outside.mkdir()
    root = tmp_path / 'root'
    root.mkdir()
    try:
        (root / 'link').symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip('Host does not permit creating symbolic links')
    with pytest.raises(ValueError):
        workspace_service.resolve_path(str(root), 'link/file')


def test_unchanged_diff():
    result = workspace_service.compute_diff('x=1\n', 'x=1\n', 'a.py')
    assert result['diff_patch'] == ''
    assert result['lines_added'] == result['lines_removed'] == 0


def test_no_invented_tests():
    assert test_runner_service._parse_pytest_output('', 0) == ([], 0, 0, 0)


def test_junit_mixed_parameterized(tmp_path):
    path = tmp_path / 'report.xml'
    path.write_text('<testsuite><testcase classname="tests.test_x" name="test_x[ok]" time="0.01"/><testcase classname="tests.test_x" name="test_x[bad]" time="0.02"><failure message="wrong">trace</failure></testcase><testcase name="skip"><skipped/></testcase></testsuite>')
    items = test_runner_service.parse_junit(path)
    assert [i.status for i in items] == ['PASSED', 'FAILED', 'SKIPPED']
    assert items[1].duration_ms == 20


def test_process_exception_is_not_success(database, run, monkeypatch):
    def fail(*args, **kwargs):
        raise OSError('not found')
    monkeypatch.setattr(subprocess, 'run', fail)
    result = test_runner_service.run_tests(run.run_id)
    assert result.status == 'ERROR'
    assert result.total_tests == result.passed_tests == 0
    assert result.exit_code == -1


def test_real_recursive_pytest(database, run):
    nested = Path(run.repo_path) / 'tests' / 'nested'
    nested.mkdir(parents=True)
    (nested / 'test_sample.py').write_text('import pytest\n@pytest.mark.parametrize("x", [1,2])\ndef test_x(x):\n    assert x == 1\n')
    result = test_runner_service.run_tests(run.run_id)
    assert result.status == 'FAILED'
    assert (result.total_tests, result.passed_tests, result.failed_tests) == (2, 1, 1)


@pytest.mark.asyncio
async def test_unrelated_checks_do_not_verify_constraints(database, run):
    database.save_goal_model(GoalModel(task_id='t1', run_id='r1', original_request='Test', normalized_request='Test', main_goal='Test', summary='', is_confirmed=True,
        success_criteria=[SuccessCriterion(id='c1', description='Fast', metric='latency < 1ms')],
        hard_constraints=[Constraint(id='h1', text='No secrets')]))
    report = await verifier_service.verify_run('r1')
    assert report.overall_verdict == 'UNVERIFIED'
    assert report.constraint_compliances[0].compliant is None
    assert report.goal_drift_score is report.code_quality_score is None
    assert database.get_evaluation('r1').verified_success is None


def test_more_than_200_events(database, run):
    for i in range(205):
        database.add_log('r1', 'test', 'test', 'info', str(i))
    assert len(database.get_execution_logs('r1')) == 205
    assert len(database.get_execution_logs('r1', limit=200)) == 200


def test_legacy_and_unknown_denominators(database, run):
    database.save_evaluation(EvaluationMetrics(run_id='r1', task_id='t1', success_rate=100))
    stats = database.get_aggregate_evaluations()['aggregate_stats']
    assert stats['legacy_runs'] == 1 and stats['avg_success_rate'] is None
    database.finalize_run(EvaluationMetrics(run_id='r1', task_id='t1', metric_version='2', outcome='unverified'))
    assert database.get_aggregate_evaluations()['aggregate_stats']['avg_success_rate'] == 0


def test_finalization_rollback(database, run, monkeypatch):
    from app.models.schema import VerificationReport
    def fail(*args, **kwargs):
        raise RuntimeError('simulated write failure')
    monkeypatch.setattr(database, 'save_evaluation', fail)
    with pytest.raises(RuntimeError):
        database.finalize_run(EvaluationMetrics(run_id='r1', task_id='t1'), VerificationReport(id='v1', run_id='r1', overall_verdict='UNVERIFIED', review_summary=''))
    assert database.get_verification('r1') is None


@pytest.mark.asyncio
async def test_confirmed_goal_preserved_and_zero_retries(database, run, monkeypatch):
    from app.services.orchestrator_service import orchestrator_service, planner_service, coder_service, debugger_service, goal_parser_service
    goal = GoalModel(task_id='t1', run_id='r1', original_request='Test', normalized_request='Test', main_goal='Edited objective', summary='', is_confirmed=True)
    database.save_goal_model(goal)
    calls = []
    async def stage(**kwargs):
        calls.append(kwargs)
    async def forbidden(*args, **kwargs):
        raise AssertionError('Confirmed goal must not be reparsed')
    monkeypatch.setattr(goal_parser_service, 'parse_request', forbidden)
    monkeypatch.setattr(planner_service, 'generate_plan', stage)
    monkeypatch.setattr(coder_service, 'execute_plan', stage)
    monkeypatch.setattr(debugger_service, 'run_testing_and_recovery_loop', stage)
    record = await orchestrator_service.run_full_pipeline('Test', existing_run_id='r1', temperature=0, max_recovery_retries=0)
    assert record.goal_model.main_goal == 'Edited objective'
    assert record.goal_model.task_id == record.task_id == 't1'
    assert calls[-1]['max_recovery_retries'] == 0
    assert calls[0]['temperature'] == calls[1]['temperature'] == 0


@pytest.mark.asyncio
async def test_pipeline_failure_retains_outcome(database, run, monkeypatch):
    from app.services.orchestrator_service import orchestrator_service, planner_service
    database.save_goal_model(GoalModel(task_id='t1', run_id='r1', original_request='Test', normalized_request='Test', main_goal='Test', summary='', is_confirmed=True))
    async def fail(**kwargs):
        raise RuntimeError('failed stage')
    monkeypatch.setattr(planner_service, 'generate_plan', fail)
    with pytest.raises(RuntimeError):
        await orchestrator_service.run_full_pipeline('Test', existing_run_id='r1')
    evaluation = database.get_evaluation('r1')
    assert evaluation.outcome == 'error' and evaluation.verified_success is False


def test_edit_goal_invalidates_and_preserves_history(database, run):
    from app.services.goal_parser_service import goal_parser_service
    database.save_goal_model(GoalModel(task_id='t1', run_id='r1', original_request='Test', normalized_request='Test', main_goal='Test', summary='', is_confirmed=True))
    database.save_evaluation(EvaluationMetrics(run_id='r1', task_id='t1', metric_version='2', verified_success=True, outcome='success'))
    edited = goal_parser_service.patch_goal_model('r1', {'main_goal':'Updated'})
    assert edited.is_confirmed is False
    assert database.get_evaluation('r1').evidence_stale
    assert database.get_evaluation('r1').verified_success is None
    with database._get_connection() as conn:
        assert conn.execute('SELECT COUNT(*) FROM evaluation_history').fetchone()[0] == 1


def test_stage_api_respects_zero(database, run, monkeypatch):
    from app.api.routes import debugger_service
    from fastapi.testclient import TestClient
    from app.main import app
    seen = []
    async def execute(**kwargs):
        seen.append(kwargs)
        return {}
    monkeypatch.setattr(debugger_service, 'run_testing_and_recovery_loop', execute)
    response = TestClient(app).post('/api/tester/execute', json={'run_id':'r1','max_recovery_retries':0})
    assert response.status_code == 200
    assert seen[0]['max_recovery_retries'] == 0


def test_trace_identity(database, run):
    database.add_log('r1','test','agent','info','test')
    event = database.get_execution_logs('r1')[0]
    assert event.task_id == 't1' and event.step == 1 and event.agent_id == 'agent'
