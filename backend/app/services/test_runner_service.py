import os
import sys
import uuid
import time
import subprocess
import re
from typing import Dict, Any, List, Optional
from datetime import datetime
from ..models.schema import (
    TestRunResult,
    TestResultItem,
    RecoveryAttempt
)
from .db import db_service
from .workspace_service import workspace_service

class TestRunnerService:
    def run_tests(
        self,
        run_id: str,
        attempt_number: int = 1,
        test_file_target: Optional[str] = None
    ) -> TestRunResult:
        plan = db_service.get_plan(run_id)
        repo_path = plan.target_repo_path if plan else workspace_service.get_default_repo_path()

        # Find test files
        test_files = []
        if test_file_target and os.path.exists(os.path.join(repo_path, test_file_target)):
            test_files.append(test_file_target)
        else:
            tests_dir = os.path.join(repo_path, "tests")
            if os.path.exists(tests_dir):
                for f in os.listdir(tests_dir):
                    if f.startswith("test_") and f.endswith(".py"):
                        test_files.append(os.path.join("tests", f))

        if not test_files:
            # Fallback to test files defined in plan
            if plan:
                for pf in plan.planned_files:
                    if pf.action == "test" or "test" in pf.path:
                        test_files.append(pf.path)

        db_service.add_log(
            run_id=run_id,
            stage="testing",
            agent_role="Test Runner Agent",
            event_type="command",
            message=f"Executing pytest suite in '{repo_path}' on target files: {test_files} (Attempt #{attempt_number}).",
            details={"repo_path": repo_path, "test_files": test_files, "attempt": attempt_number}
        )

        start_time = time.time()
        stdout_text = ""
        stderr_text = ""
        exit_code = 0
        test_items: List[TestResultItem] = []

        # Execute pytest in subprocess with repo_path in PYTHONPATH
        env = os.environ.copy()
        env["PYTHONPATH"] = f"{repo_path}{os.pathsep}{env.get('PYTHONPATH', '')}"

        cmd = [sys.executable, "-m", "pytest", "-v", "--tb=short"] + (test_files if test_files else ["tests"])

        try:
            process = subprocess.run(
                cmd,
                cwd=repo_path,
                env=env,
                capture_output=True,
                text=True,
                timeout=30
            )
            stdout_text = process.stdout
            stderr_text = process.stderr
            exit_code = process.returncode
        except subprocess.TimeoutExpired:
            stdout_text = "ERROR: Test execution timed out after 30 seconds."
            exit_code = 124
        except Exception as e:
            stdout_text = f"Subprocess invocation error: {str(e)}\n"
            exit_code = 1

        duration = round(time.time() - start_time, 2)

        # Parse test items from pytest output accurately
        parsed_items, total, passed, failed, status = self._parse_pytest_output(stdout_text, exit_code)

        result = TestRunResult(
            id=f"testrun_{uuid.uuid4().hex[:8]}",
            run_id=run_id,
            attempt_number=attempt_number,
            total_tests=total,
            passed_tests=passed,
            failed_tests=failed,
            duration_seconds=duration,
            stdout=stdout_text,
            stderr=stderr_text,
            exit_code=exit_code,
            status=status,
            test_items=parsed_items,
            created_at=datetime.now().isoformat()
        )

        db_service.save_test_result(result)

        event_type = "success" if status == "PASSED" else "warning"
        db_service.add_log(
            run_id=run_id,
            stage="testing",
            agent_role="Test Runner Agent",
            event_type=event_type,
            message=f"Test Suite Result: {status} ({passed}/{total} passed in {duration}s, exit code: {exit_code}).",
            details={"passed": passed, "total": total, "failed": failed, "status": status}
        )

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
            return items, 0, 0, 0, status

        # 2. Check for "no tests ran" / "collected 0 items"
        if re.search(r"no tests ran|collected 0 items", output_str, re.IGNORECASE) or (exit_code == 5 and "collected 0" in output_str.lower()):
            return [], 0, 0, 0, "NOT_RUN"

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
            return items, total, passed, failed, status

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
            return items, total, passed, failed, status

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

        return items, total, passed, failed, status

test_runner_service = TestRunnerService()
