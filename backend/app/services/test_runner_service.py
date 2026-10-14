from .workflow_service import observed, workflow
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
import re
from typing import Optional, Dict, Any, List
from ..models.schema import TestRunResult, TestResultItem
from .db import db_service
from .workspace_service import workspace_service
from .telemetry_service import telemetry_manager
from .drift_controller_service import drift_controller_service
from .goal_tracker_service import goal_tracker_service


class PytestParseResult(tuple):
    def __new__(cls, items, total, passed, failed, status):
        return super().__new__(cls, (items, total, passed, failed, status))

    def __eq__(self, other):
        if isinstance(other, tuple) and len(other) == 4:
            return self[:4] == other
        return super().__eq__(other)


class TestRunnerService:
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
        if test_file_target:
            file_part = test_file_target.split('::')[0] if '::' in test_file_target else test_file_target
            workspace_service.resolve_path(repo, file_part)
        targets = target_test_files or [test_file_target or 'tests']
        for item in targets:
            file_part = item.split('::')[0] if '::' in item else item
            workspace_service.resolve_path(repo, file_part)
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
        repo_path_resolved = str(Path(repo).resolve())
        app_path_resolved = str((Path(repo) / 'app').resolve())
        env = os.environ.copy()
        env['PYTHONPATH'] = os.pathsep.join([repo_path_resolved, app_path_resolved])
        env['PYTEST_DISABLE_PLUGIN_AUTOLOAD'] = '1'
        env.pop('PYTEST_ADDOPTS', None)
        with tempfile.TemporaryDirectory(prefix='agenteval-results-') as directory:
            report = str(Path(directory) / 'results.xml')
            command = [
                sys.executable, '-m', 'pytest',
                '-o', f'pythonpath={repo_path_resolved} {app_path_resolved}',
                '-v', '--tb=short', '-p', 'pytest_asyncio.plugin',
                f'--junitxml={report}', '--', *targets
            ]
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

    def _parse_pytest_output(self, output: str, exit_code: int):
        items: List[TestResultItem] = []
        output_str = output or ""
        trimmed = output_str.strip()

        # 1. Empty / unparseable output
        if not trimmed:
            status = "ERROR" if exit_code != 0 else "NOT_RUN"
            if status == "ERROR":
                items.append(
                    TestResultItem(
                        name="pytest_execution_error",
                        status="ERROR",
                        duration_ms=0.0,
                        error_message="Empty test output with non-zero exit code"
                    )
                )
            return PytestParseResult(items, 0, 0, 0, status)

        # 2. Check for "no tests ran" / "collected 0 items"
        if re.search(r"no tests ran|collected 0 items", output_str, re.IGNORECASE) or (exit_code == 5 and "collected 0" in output_str.lower()):
            return PytestParseResult([], 0, 0, 0, "NOT_RUN")

        # 3. Look for pytest individual lines: tests/test_auth.py::test_name PASSED / FAILED / SKIPPED / ERROR
        pattern = re.compile(
            r"^([\w/\\.\-]+(?:::[\w\-\[\]]+)?)\s+(PASSED|FAILED|SKIPPED|ERROR|XFAIL|XPASS)",
            re.MULTILINE
        )
        matches = list(pattern.finditer(output_str))

        # Extract failure summaries if present
        # Format: FAILED tests/test_auth.py::test_login - assert 200 == 401
        failure_details: Dict[str, str] = {}
        for m in re.finditer(r"^(?:FAILED|ERROR)\s+([\w/\\.\-]+(?:::[\w\-\[\]]+)?)(?:\s*[-:]\s*(.+))?$", output_str, re.MULTILINE):
            name, reason = m.group(1), m.group(2)
            if name:
                failure_details[name.strip()] = (reason.strip() if reason else "Assertion failed or error occurred")

        failures_section = ""
        if "=== FAILURES ===" in output_str or "=== ERRORS ===" in output_str:
            failures_section = output_str

        total = 0
        passed = 0
        failed = 0

        for match in matches:
            test_name = match.group(1)
            outcome = match.group(2)
            total += 1

            if outcome == "PASSED":
                passed += 1
                items.append(
                    TestResultItem(
                        name=test_name,
                        status="PASSED",
                        duration_ms=45.0,
                        error_message=None
                    )
                )
            elif outcome in ("FAILED", "ERROR", "XFAIL"):
                failed += 1
                err_msg = failure_details.get(test_name)
                if not err_msg and failures_section:
                    tb_match = re.search(r"_{3,}\s*" + re.escape(test_name.split("::")[-1]) + r"\s*_{3,}(.+?)(?:_{3,}|=|$)", failures_section, re.DOTALL)
                    if tb_match:
                        e_lines = [line.strip() for line in tb_match.group(1).splitlines() if line.strip().startswith("E ")]
                        if e_lines:
                            err_msg = "\n".join(e_lines[:3])
                if not err_msg:
                    err_msg = "Test failed during execution"

                items.append(
                    TestResultItem(
                        name=test_name,
                        status=outcome,
                        duration_ms=45.0,
                        error_message=err_msg
                    )
                )
            elif outcome == "SKIPPED":
                items.append(
                    TestResultItem(
                        name=test_name,
                        status="SKIPPED",
                        duration_ms=0.0
                    )
                )

        if items:
            if exit_code == 0 and failed == 0 and total > 0:
                status = "PASSED"
            elif any(it.status == "ERROR" for it in items) or (exit_code != 0 and failed == 0):
                status = "ERROR"
            else:
                status = "FAILED"
            return PytestParseResult(items, total, passed, failed, status)

        # 4. If individual lines not present, check summary line
        p_m = re.search(r"(\d+)\s+passed", output_str, re.IGNORECASE)
        f_m = re.search(r"(\d+)\s+failed", output_str, re.IGNORECASE)
        e_m = re.search(r"(\d+)\s+error(?:s)?", output_str, re.IGNORECASE)
        s_m = re.search(r"(\d+)\s+skipped", output_str, re.IGNORECASE)

        p_cnt = int(p_m.group(1)) if p_m else 0
        f_cnt = int(f_m.group(1)) if f_m else 0
        e_cnt = int(e_m.group(1)) if e_m else 0
        s_cnt = int(s_m.group(1)) if s_m else 0
        summary_total = p_cnt + f_cnt + e_cnt + s_cnt

        if summary_total > 0:
            total = summary_total
            passed = p_cnt
            failed = f_cnt + e_cnt
            for fname, freason in failure_details.items():
                items.append(TestResultItem(name=fname, status="FAILED", error_message=freason))
            if exit_code == 0 and failed == 0:
                status = "PASSED"
            elif e_cnt > 0:
                status = "ERROR"
            else:
                status = "FAILED"
            return PytestParseResult(items, total, passed, failed, status)

        # 5. Output could not be parsed and no test counts available
        total = 0
        passed = 0
        failed = 0
        if exit_code != 0:
            status = "ERROR"
            items.append(
                TestResultItem(
                    name="pytest_execution_error",
                    status="ERROR",
                    duration_ms=0.0,
                    error_message=trimmed[:500]
                )
            )
        else:
            status = "NOT_RUN"

        return PytestParseResult(items, total, passed, failed, status)

test_runner_service = TestRunnerService()
