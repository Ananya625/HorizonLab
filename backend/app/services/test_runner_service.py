from .workflow_service import observed
"""Real pytest execution. Console text alone is never evidence of success."""
import os
import sys
import uuid
import time
import math
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional
from ..models.schema import TestRunResult, TestResultItem
from .db import db_service
from .workspace_service import workspace_service
from .telemetry_service import telemetry_manager
from .drift_controller_service import drift_controller_service
from .goal_tracker_service import goal_tracker_service


class TestRunnerService:
    @staticmethod
    def subprocess_env(repo):
        env = {key: value for key, value in os.environ.items()
               if key.upper() in {'SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP', 'TMPDIR', 'LANG', 'LC_ALL'}}
        env['PYTHONPATH'] = os.pathsep.join([str(Path(repo).resolve()), str(Path(repo).resolve() / 'app')])
        env['PYTEST_DISABLE_PLUGIN_AUTOLOAD'] = '1'
        return env

    @staticmethod
    def parse_junit(path):
        root = ET.parse(path).getroot()
        if root.tag not in ('testsuite', 'testsuites'):
            raise ValueError('Invalid pytest report root')
        items = []
        for case in root.iter('testcase'):
            failure, error, skipped = case.find('failure'), case.find('error'), case.find('skipped')
            status = 'ERROR' if error is not None else 'FAILED' if failure is not None else 'SKIPPED' if skipped is not None else 'PASSED'
            detail = error if error is not None else failure if failure is not None else skipped
            duration = float(case.get('time', '0')) * 1000
            if duration < 0 or not math.isfinite(duration):
                raise ValueError('Invalid test duration')
            items.append(TestResultItem(name=f"{case.get('classname', '')}::{case.get('name', '')}",
                status=status, duration_ms=duration,
                error_message=detail.get('message') if detail is not None else None,
                stack_trace=detail.text if detail is not None else None))
        return items

    @observed('pytest', 'tool', reason='validation')
    def run_tests(self, run_id: str, attempt_number: int = 1,
                  test_file_target: Optional[str] = None, target_test_files: Optional[list[str]] = None) -> TestRunResult:
        record = db_service.get_run_record(run_id)
        if not record:
            raise ValueError('Unknown run')
        plan = db_service.get_plan(run_id)
        repo = plan.target_repo_path if plan else record.repo_path
        repo = workspace_service.validate_repo(repo)
        if test_file_target:
            workspace_service.resolve_path(repo, test_file_target)
        targets = target_test_files or [test_file_target or 'tests']
        for item in targets:
            workspace_service.resolve_path(repo, item)
        target = ' '.join(targets)
        cmd_target_str = 'pytest '+target
        decision = drift_controller_service.check_action(run_id=run_id, action_type='command_exec',
            target=cmd_target_str, payload_str=str(attempt_number), repo_path=repo)
        if not decision.allowed:
            result = TestRunResult(id=f'testrun_{uuid.uuid4().hex}',run_id=run_id,attempt_number=attempt_number,
                exit_code=1,status='ERROR',execution_error=decision.reason,evidence_version='junit-v1')
            db_service.save_test_result(result)
            goal_tracker_service.record_action(run_id=run_id,action_type='command_exec',target=cmd_target_str,
                payload_str=str(attempt_number),status='blocked',error_message=decision.reason)
            return result
        tracker = telemetry_manager.get(run_id)
        if tracker:
            tracker.record_agent_invocation('Test Runner Agent')
            tracker.record_tool_call()
        before = workspace_service.digest(repo)
        start = time.perf_counter()
        stdout, stderr, execution_error, exit_code, items = '', '', None, -1, []
        env = self.subprocess_env(repo)
        with tempfile.TemporaryDirectory(prefix='agenteval-results-') as directory:
            report = str(Path(directory) / 'results.xml')
            config = Path(repo) / 'pytest.ini'
            if not config.is_file():
                config = Path(directory) / 'pytest.ini'
                config.write_text('[pytest]\n', encoding='utf-8')
            command = [sys.executable, '-m', 'pytest', '-c', str(config), '--rootdir', repo, '-v', '--tb=short', '-p', 'pytest_asyncio.plugin', f'--junitxml={report}', '--', *targets]
            db_service.add_log(run_id, 'testing', 'Test Runner', 'tool_call', 'Executing pytest', {'operation_id': uuid.uuid4().hex, 'tool': 'pytest', 'target': target})
            try:
                process = subprocess.run(command, cwd=repo, env=env, capture_output=True, text=True, timeout=30)
                stdout, stderr, exit_code = process.stdout, process.stderr, process.returncode
                items = self.parse_junit(report)
            except subprocess.TimeoutExpired as exc:
                exit_code, execution_error = 124, 'Test execution exceeded 30 seconds'
                stdout = (exc.stdout or b'').decode(errors='replace') if isinstance(exc.stdout, bytes) else (exc.stdout or '')
                stderr = (exc.stderr or b'').decode(errors='replace') if isinstance(exc.stderr, bytes) else (exc.stderr or '')
            except (OSError, ValueError, ET.ParseError) as exc:
                execution_error = f'{type(exc).__name__}: {exc}'
        passed = sum(i.status == 'PASSED' for i in items)
        failed = sum(i.status in ('FAILED', 'ERROR') for i in items)
        skipped = sum(i.status == 'SKIPPED' for i in items)
        if before != workspace_service.digest(repo):
            execution_error = 'Workspace changed during test execution; evidence is not stable'
        status = 'ERROR' if execution_error else 'PASSED' if exit_code == 0 and passed > 0 and failed == 0 else 'FAILED'
        result = TestRunResult(id=f'testrun_{uuid.uuid4().hex}', run_id=run_id,
            attempt_number=attempt_number, total_tests=len(items), passed_tests=passed,
            failed_tests=failed, skipped_tests=skipped, duration_seconds=time.perf_counter()-start,
            stdout=stdout, stderr=stderr, exit_code=exit_code, status=status,
            test_items=items, execution_error=execution_error,
            evidence_version='junit-v1', workspace_digest=before)
        db_service.save_test_result(result)
        db_service.add_log(run_id, 'testing', 'Test Runner', 'test_run', f'Pytest: {status}', {'result_id': result.id, 'duration_seconds': result.duration_seconds})
        drift_controller_service.validate_result(run_id=run_id,action_type='test_run',target=cmd_target_str,
            success=status=='PASSED',details={'exit_code':exit_code,'passed_tests':passed,'failed_tests':failed,'total_tests':len(items),'stdout':stdout})
        goal_tracker_service.record_action(run_id=run_id,action_type='test_run',target=cmd_target_str,
            payload_str=str(attempt_number),status='completed' if status=='PASSED' else 'failed',
            details={'passed':passed,'failed':failed,'total':len(items),'duration_seconds':result.duration_seconds})
        return result



test_runner_service = TestRunnerService()
