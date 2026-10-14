from pathlib import Path
from types import SimpleNamespace
import pytest
from app.models.schema import GoalModel, SuccessCriterion, TestRunResult as RunResult
from app.services.criterion_checks import evaluate, support
from app.services.verifier_service import verifier_service
from app.services.workflow_reports import workflow_report


def criterion(method='ast_check',metric='Syntax errors == 0',target='Initial syntax verification report'):
    return SuccessCriterion(id='c',description='Check',verification_method=method,metric=metric,expected_output=target)


def test_actual_legacy_syntax_alias_and_compiler_semantics(tmp_path):
    (tmp_path/'app.py').write_text('x = 1\n')
    assert evaluate(criterion(),str(tmp_path))[0]=='PASS'
    (tmp_path/'app.py').write_text('return 1\n')  # ast.parse alone accepts this.
    assert evaluate(criterion(),str(tmp_path))[0]=='FAIL'


def test_empty_workspace_is_not_success_and_dependencies_excluded(tmp_path):
    tmp_path=tmp_path/'empty-repo'
    tmp_path.mkdir()
    assert evaluate(criterion(),str(tmp_path))[0]=='UNVERIFIED'
    (tmp_path/'app.py').write_text('x=1')
    (tmp_path/'.venv').mkdir()
    (tmp_path/'.venv'/'broken.py').write_text('x=(')
    assert evaluate(criterion(),str(tmp_path))[0]=='PASS'


@pytest.mark.parametrize('content,verdict',[('{"x":1}','PASS'),('{"x":NaN}','FAIL'),('not json','FAIL')])
def test_json_valid_is_only_json_syntax(tmp_path,content,verdict):
    (tmp_path/'config.json').write_text(content)
    assert evaluate(criterion('schema_validation','json_valid','config.json'),str(tmp_path))[0]==verdict


def test_missing_file_and_bad_configuration_are_distinct(tmp_path):
    assert evaluate(criterion('state_ledger_check','file_exists','missing.txt'),str(tmp_path))[0]=='FAIL'
    assert evaluate(criterion('state_ledger_check','file_exists','../outside'),str(tmp_path))[0]=='UNVERIFIED'
    assert support(criterion(target=''))['available']  # global alias does not need a filename
    assert not support(criterion(metric='python_syntax',target=''))['available']


def test_large_files_unreadable_encoding_and_broad_claims_stay_unknown(tmp_path):
    (tmp_path/'large.py').write_bytes(b'x'*(1024*1024+1))
    assert evaluate(criterion(metric='python_syntax',target='large.py'),str(tmp_path))[0]=='UNVERIFIED'
    (tmp_path/'bad.py').write_bytes(b'\xff')
    assert evaluate(criterion(metric='python_syntax',target='bad.py'),str(tmp_path))[0]=='UNVERIFIED'
    for metric in ('Bandit B608 (SQL Injection) == 0 alerts','Regression failures == 0','pytest new_tests == 100% PASS'):
        method='ast_check' if metric.startswith('Bandit') else 'automated_test'
        verdict,evidence=evaluate(criterion(method,metric),str(tmp_path))
        assert verdict=='UNVERIFIED' and evidence


@pytest.mark.parametrize(
    ('returncode', 'expected_verdict'),
    [(0, 'PASS'), (1, 'FAIL'), (2, 'UNVERIFIED'), (3, 'UNVERIFIED'), (5, 'UNVERIFIED')],
)
def test_workspace_test_suite_distinguishes_failures_from_incomplete_runs(
    tmp_path, monkeypatch, returncode, expected_verdict
):
    from app.services import criterion_checks

    (tmp_path / 'test_sample.py').write_text('def test_sample(): pass\n')
    monkeypatch.setattr(
        'subprocess.run',
        lambda *args, **kwargs: SimpleNamespace(
            returncode=returncode,
            stdout='1 passed\n' if returncode == 0 else '1 error\n',
            stderr='',
        ),
    )

    verdict, _evidence = criterion_checks.evaluate(
        criterion('automated_test', 'pytest new_tests == 100% PASS'), str(tmp_path)
    )

    assert verdict == expected_verdict


def test_workspace_test_suite_timeout_remains_unverified(tmp_path, monkeypatch):
    import subprocess

    from app.services import criterion_checks

    (tmp_path / 'test_sample.py').write_text('def test_sample(): pass\n')

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], timeout=20)

    monkeypatch.setattr('subprocess.run', timeout)

    verdict, evidence = criterion_checks.evaluate(
        criterion('automated_test', 'pytest new_tests == 100% PASS'), str(tmp_path)
    )

    assert verdict == 'UNVERIFIED'
    assert 'timed out' in evidence


@pytest.mark.asyncio
async def test_legacy_syntax_criterion_verifies_current_state(database,run):
    (Path(run.repo_path)/'app.py').write_text('x=1')
    database.save_goal_model(GoalModel(run_id='r1',task_id='t1',original_request='Check syntax',
        normalized_request='Check syntax',main_goal='Check syntax',summary='Syntax only',is_confirmed=True,
        success_criteria=[criterion()]))
    report=await verifier_service.verify_run('r1')
    assert report.verified_success is True
    assert 'Syntax only' in report.criteria_evaluations[0].evidence


def test_legacy_records_exposed_without_inventing_actions(database,run):
    database.add_log('r1','model','model','model_call','old request',{'operation_id':'old'})
    database.save_test_result(RunResult(id='old',run_id='r1',total_tests=3,passed_tests=3,status='PASSED'))
    report,events=workflow_report(database,'r1')
    assert events==[] and report['summary']['action_attempts'] is None
    assert report['saved_measurements']['recorded_model_requests']==1
    assert report['saved_measurements']['latest_test']['total']==3
    assert report['saved_measurements']['latest_test']['evidence_version']=='legacy'
    assert report['summary']['verified_outcome'] is None


@pytest.mark.asyncio
async def test_workspace_change_during_check_invalidates_result(database,run,monkeypatch):
    from app.services import criterion_checks
    path=Path(run.repo_path)/'app.py'
    path.write_text('x=1')
    database.save_goal_model(GoalModel(run_id='r1',task_id='t1',original_request='Syntax',
        normalized_request='Syntax',main_goal='Syntax',summary='Syntax',is_confirmed=True,
        success_criteria=[criterion()]))
    def changing_check(*args):
        path.write_text('x=(')
        return 'PASS','Earlier state passed'
    monkeypatch.setattr(criterion_checks,'evaluate',changing_check)
    report=await verifier_service.verify_run('r1')
    assert report.verified_success is None
    assert 'changed during verification' in report.criteria_evaluations[0].evidence
