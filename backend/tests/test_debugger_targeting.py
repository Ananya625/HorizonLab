import pytest
from app.models.schema import (
    TestRunResult,
    TestResultItem,
    ImplementationPlan,
    PlannedFile
)
from app.services.debugger_service import DebuggerService, debugger_service

TestRunResult.__test__ = False
TestResultItem.__test__ = False


def test_target_identification_avoids_basename_substring_collision():
    """Verify that 'app/auth.py' is NOT selected when traceback mentions 'tests/test_auth.py'."""
    plan = ImplementationPlan(
        run_id="test_run_target",
        target_repo_path="/fake/repo",
        goal_model_version="1.0",
        steps=[],
        architecture_overview="Test arch",
        testing_strategy="Pytest",
        risk_assessment="Low",
        planned_files=[
            PlannedFile(path="app/auth.py", action="create", description="Auth utilities"),
            PlannedFile(path="app/routes/auth_routes.py", action="create", description="Auth routes"),
            PlannedFile(path="app/main.py", action="modify", description="Main FastAPI application"),
            PlannedFile(path="tests/test_auth.py", action="test", description="Auth tests"),
        ]
    )

    stdout = """
=================================== ERRORS ====================================
_____________________ ERROR collecting tests/test_auth.py _____________________
tests\\test_auth.py:4: in <module>
    from app.main import app
app\\main.py:2: in <module>
    class JSONResponse(BaseModel):
                       ^^^^^^^^^
E   NameError: name 'BaseModel' is not defined
=========================== short test summary info ===========================
ERROR tests/test_auth.py - NameError: name 'BaseModel' is not defined
"""
    test_result = TestRunResult(
        id="tr_1",
        run_id="test_run_target",
        attempt_number=1,
        exit_code=2,
        status="FAILED",
        stdout=stdout,
        test_items=[
            TestResultItem(
                name="::tests.test_auth",
                status="ERROR",
                duration_ms=0.0,
                error_message="collection failure",
                stack_trace="tests\\test_auth.py:4: in <module>\n    from app.main import app\napp\\main.py:2: in <module>\n    class JSONResponse(BaseModel):\n                       ^^^^^^^^^\nE   NameError: name 'BaseModel' is not defined"
            )
        ]
    )

    target_file, target_line, is_impl = debugger_service._identify_failure_target(test_result, plan, "/fake/repo")
    assert target_file == "app/main.py", f"Expected app/main.py but got {target_file}"
    assert target_line == 2
    assert is_impl is True


def test_diagnose_failure_distinguishes_collection_error_from_no_tests_collected():
    """Verify that exit_code 2 with collection failure is diagnosed as collection error, not 'No Tests Collected'."""
    stdout = """
collecting ... collected 0 items / 1 error
ERROR tests/test_auth.py - NameError: name 'BaseModel' is not defined
"""
    test_result = TestRunResult(
        id="tr_coll",
        run_id="test_run_diag",
        attempt_number=1,
        exit_code=2,
        status="FAILED",
        stdout=stdout,
        test_items=[
            TestResultItem(
                name="::tests.test_auth",
                status="ERROR",
                duration_ms=0.0,
                error_message="collection failure",
                stack_trace="NameError: name 'BaseModel' is not defined"
            )
        ]
    )

    diag = debugger_service._diagnose_failure(test_result)
    assert "No Tests Collected" not in diag["failure_reason"]
    assert "Collection" in diag["failure_reason"]
    assert "NameError" in diag["failure_reason"]


def test_extract_concise_error_summary_preserves_frames_and_code():
    """Verify that stack frames, offending code, and exceptions are preserved in error summary."""
    stdout = """
=================================== ERRORS ====================================
_____________________ ERROR collecting tests/test_auth.py _____________________
tests\\test_auth.py:4: in <module>
    from app.main import app
app\\main.py:2: in <module>
    class JSONResponse(BaseModel):
                       ^^^^^^^^^
E   NameError: name 'BaseModel' is not defined
=========================== short test summary info ===========================
ERROR tests/test_auth.py - NameError: name 'BaseModel' is not defined
"""
    debugger = DebuggerService(max_traceback_chars=2000)
    summary = debugger._extract_concise_error_summary(stdout, stderr="")

    assert "tests\\test_auth.py:4: in <module>" in summary or "tests/test_auth.py" in summary
    assert "app\\main.py:2: in <module>" in summary or "app/main.py" in summary
    assert "BaseModel" in summary
    assert "NameError" in summary


def test_target_identification_targets_impl_on_assertion_failure_and_test_file_on_test_error():
    """Requirement 5: Test assertion failures target implementation to avoid weakening tests.
    Test syntax or fixture errors target the test file."""
    plan = ImplementationPlan(
        run_id="test_run_assert",
        target_repo_path="/fake/repo",
        goal_model_version="1.0",
        steps=[],
        architecture_overview="Test arch",
        testing_strategy="Pytest",
        risk_assessment="Low",
        planned_files=[
            PlannedFile(path="app/service.py", action="modify", description="Service"),
            PlannedFile(path="tests/test_service.py", action="test", description="Tests"),
        ]
    )

    # 1. Assertion failure targets implementation under test
    stdout_assert = """
__________________________________ test_add ___________________________________
tests\\test_service.py:10: in test_add
    assert add(2, 3) == 6
E   assert 5 == 6
"""
    test_result_assert = TestRunResult(
        id="tr_assert",
        run_id="test_run_assert",
        attempt_number=1,
        exit_code=1,
        status="FAILED",
        stdout=stdout_assert,
        test_items=[
            TestResultItem(
                name="test_add",
                status="FAILED",
                duration_ms=5.0,
                error_message="assert 5 == 6",
                stack_trace="tests\\test_service.py:10: in test_add\n    assert add(2, 3) == 6\nE   assert 5 == 6"
            )
        ]
    )

    target_file, target_line, is_impl = debugger_service._identify_failure_target(test_result_assert, plan, "/fake/repo")
    assert target_file == "app/service.py"
    assert is_impl is True

    # 2. Test syntax or fixture error targets the test file
    stdout_fixture = """
___________________________ ERROR at setup of test_add ___________________________
tests\\test_service.py:5: in setup
    raise FixtureLookupError('missing_fixture')
E   FixtureLookupError: missing_fixture
"""
    test_result_fixture = TestRunResult(
        id="tr_fixture",
        run_id="test_run_assert",
        attempt_number=1,
        exit_code=1,
        status="FAILED",
        stdout=stdout_fixture,
        test_items=[
            TestResultItem(
                name="test_add",
                status="ERROR",
                duration_ms=5.0,
                error_message="FixtureLookupError: missing_fixture",
                stack_trace="tests\\test_service.py:5: in setup\n    raise FixtureLookupError('missing_fixture')\nE   FixtureLookupError: missing_fixture"
            )
        ]
    )

    target_file2, target_line2, is_impl2 = debugger_service._identify_failure_target(test_result_fixture, plan, "/fake/repo")
    assert target_file2 == "tests/test_service.py"
    assert target_line2 == 5
    assert is_impl2 is False


@pytest.mark.asyncio
async def test_debugger_stops_on_consecutive_no_change_and_reports_failure(monkeypatch):
    """Requirement: Debugger stops and reports failure clearly rather than repeatedly applying ineffective changes."""
    from app.services.db import db_service
    from app.services.test_runner_service import test_runner_service
    import uuid

    run_id = f"test_run_stop_{uuid.uuid4().hex[:8]}"
    db_service.create_or_update_run(run_id, "task_test", "Test Task", "Test Prompt", "/fake/repo")

    # Mock test runner to always return failure
    failing_result = TestRunResult(
        id=f"tr_{uuid.uuid4().hex[:8]}",
        run_id=run_id,
        attempt_number=1,
        exit_code=1,
        status="FAILED",
        stdout="FAILED tests/test_calc.py::test_fail - assert 1 == 2",
        test_items=[]
    )
    monkeypatch.setattr(test_runner_service, "run_tests", lambda **kwargs: failing_result)

    # Mock _apply_recovery_fix to return [] (no changes produced)
    async def mock_apply(*args, **kwargs):
        return []
    monkeypatch.setattr(debugger_service, "_apply_recovery_fix", mock_apply)

    res = await debugger_service.run_testing_and_recovery_loop(
        run_id=run_id,
        max_recovery_retries=3
    )

    assert res["local_tests_passed"] is False
    assert len(res["recovery_attempts"]) <= 2

    # Verify clear failure report was logged
    logs = db_service.get_execution_logs(run_id)
    failure_logs = [l for l in logs if l.stage == "debugger" and l.event_type == "failure"]
    assert len(failure_logs) >= 1
    assert "Testing agent completed recovery attempts" in failure_logs[0].message


def test_assertion_mismatch_extracts_expected_and_actual_values():
    """Test 1: Assertion mismatch with expected and actual values passed to the debugger."""
    stdout = """
tests\\test_service.py:17: in test_multiply_numbers
    assert multiply_numbers(3.5, 2.5) == 9.25, "Test case 4 failed"
E   AssertionError: Test case 4 failed
E   assert 8.75 == 9.25
E    +  where 8.75 = multiply_numbers(3.5, 2.5)
"""
    test_result = TestRunResult(
        id="tr_assert_val",
        run_id="test_run_vals",
        attempt_number=1,
        exit_code=1,
        status="FAILED",
        stdout=stdout,
        test_items=[]
    )
    diag = debugger_service._diagnose_failure(test_result)
    assert diag["actual_value"] == "8.75"
    assert diag["expected_value"] == "9.25"
    assert "multiply_numbers(3.5, 2.5)" in diag["where_expression"]
    assert "Expected '9.25', observed '8.75'" in diag["diagnosis"]


def test_targeting_implementation_on_missing_import():
    """Test 2: Correct targeting of implementation files when import fails."""
    plan = ImplementationPlan(
        run_id="test_run_imp",
        target_repo_path="/fake/repo",
        goal_model_version="1.0",
        steps=[],
        architecture_overview="Test arch",
        testing_strategy="Pytest",
        risk_assessment="Low",
        planned_files=[
            PlannedFile(path="app/service.py", action="modify", description="Service"),
            PlannedFile(path="tests/test_service.py", action="test", description="Tests"),
        ]
    )

    stdout = """
tests\\test_service.py:4: in <module>
    from app.service import multiply_numbers
E   ImportError: cannot import name 'multiply_numbers' from 'app.service' (/fake/repo/app/service.py)
"""
    test_result = TestRunResult(
        id="tr_imp_target",
        run_id="test_run_imp",
        attempt_number=2,
        exit_code=2,
        status="FAILED",
        stdout=stdout,
        test_items=[]
    )

    target_file, line, is_impl = debugger_service._identify_failure_target(test_result, plan, "/fake/repo")
    assert target_file == "app/service.py", f"Expected app/service.py but got {target_file}"
    assert is_impl is True


@pytest.mark.asyncio
async def test_prevention_of_unauthorized_test_assertion_changes():
    """Test 3: Prevention of unauthorized test assertion changes and rejecting test functions in impl files."""
    from app.services.db import db_service
    from app.services.workspace_service import workspace_service
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        workspace_service.root_dir = tmpdir
        ws_path = workspace_service.create_task_workspace("task_guard", "run_guard")
        db_service.create_or_update_run("run_guard", "task_guard", "Guard Task", "Prompt", ws_path)

        plan = ImplementationPlan(
            run_id="run_guard",
            target_repo_path=ws_path,
            goal_model_version="1.0",
            steps=[],
            architecture_overview="Test arch",
            testing_strategy="Pytest",
            risk_assessment="Low",
            planned_files=[
                PlannedFile(path="tests/test_service.py", action="test", description="Tests"),
            ]
        )
        db_service.save_plan(plan)

        # 1. Calling _apply_recovery_fix on a test file with an assertion failure must be blocked
        failing_res = TestRunResult(
            id="tr_guard",
            run_id="run_guard",
            attempt_number=1,
            exit_code=1,
            status="FAILED",
            stdout="tests/test_service.py:10: AssertionError: assert 8.75 == 9.25",
            test_items=[]
        )
        diagnosis = debugger_service._diagnose_failure(failing_res)

        modified = await debugger_service._apply_recovery_fix("run_guard", failing_res, diagnosis, "fake-model")
        assert modified == [], "Should refuse to modify test file for assertion failure"


@pytest.mark.asyncio
async def test_missing_import_failures_introduced_during_recovery(monkeypatch):
    """Test 4: Diagnosing and handling missing-import failures introduced during recovery."""
    from app.services.db import db_service
    from app.services.test_runner_service import test_runner_service
    import tempfile
    import uuid

    run_id = f"test_run_reg_{uuid.uuid4().hex[:8]}"
    db_service.create_or_update_run(run_id, "t_reg", "Regression Test", "Prompt", "/fake/repo")

    # Step 1: initial test run fails with assertion error
    attempt_calls = []

    def mock_run_tests(**kwargs):
        att = kwargs.get("attempt_number", 1)
        attempt_calls.append(att)
        if len(attempt_calls) == 1:
            # Initial run: assertion mismatch
            return TestRunResult(
                id="tr_1", run_id=run_id, attempt_number=1, exit_code=1, status="FAILED",
                stdout="tests/test_service.py:17: AssertionError: assert 8.75 == 9.25", test_items=[]
            )
        else:
            # Subsequent run after edit: introduced import failure (exit code 2)
            return TestRunResult(
                id="tr_2", run_id=run_id, attempt_number=2, exit_code=2, status="FAILED",
                stdout="tests/test_service.py:4: ImportError: cannot import name 'multiply_numbers' from 'app.service'", test_items=[]
            )

    monkeypatch.setattr(test_runner_service, "run_tests", mock_run_tests)

    # Mock _apply_recovery_fix to record what target was passed
    targets_passed = []
    async def mock_apply(run_id, test_result, diagnosis, model_name, history=None, regression_target=None):
        targets_passed.append(regression_target)
        return ["app/service.py"]

    monkeypatch.setattr(debugger_service, "_apply_recovery_fix", mock_apply)

    res = await debugger_service.run_testing_and_recovery_loop(run_id=run_id, max_recovery_retries=2)
    # Verify that in attempt 2, regression_target was passed as 'app/service.py'
    assert len(targets_passed) >= 2
    assert targets_passed[1] == "app/service.py"
    # Should stop cleanly when regression is unresolved rather than cascading edits
    assert res["local_tests_passed"] is False


@pytest.mark.asyncio
async def test_rerunning_relevant_test_after_every_repair(monkeypatch):
    """Test 5: Rerunning the relevant specific test after every repair."""
    from app.services.db import db_service
    from app.services.test_runner_service import test_runner_service
    import uuid

    run_id = f"test_run_rerun_{uuid.uuid4().hex[:8]}"
    db_service.create_or_update_run(run_id, "t_rerun", "Rerun Test", "Prompt", "/fake/repo")

    targeted_targets = []

    def mock_run_tests(**kwargs):
        targets = kwargs.get("target_test_files")
        if targets:
            targeted_targets.extend(targets)
        # Attempt 1 fails, attempt 2 passes
        if not targeted_targets:
            return TestRunResult(
                id="tr_1", run_id=run_id, attempt_number=1, exit_code=1, status="FAILED",
                stdout="tests/test_service.py::test_multiply_numbers FAILED\nE AssertionError: assert 8.75 == 9.25", test_items=[]
            )
        else:
            return TestRunResult(
                id="tr_2", run_id=run_id, attempt_number=2, exit_code=0, status="PASSED",
                stdout="tests/test_service.py::test_multiply_numbers PASSED", test_items=[]
            )

    monkeypatch.setattr(test_runner_service, "run_tests", mock_run_tests)

    async def mock_apply(*args, **kwargs):
        return ["app/service.py"]
    monkeypatch.setattr(debugger_service, "_apply_recovery_fix", mock_apply)

    res = await debugger_service.run_testing_and_recovery_loop(run_id=run_id, max_recovery_retries=2)
    assert res["local_tests_passed"] is True
    # Verify specific test node ID was rerun immediately after repair
    assert "tests/test_service.py::test_multiply_numbers" in targeted_targets


@pytest.mark.asyncio
async def test_reject_bare_error_dict_and_test_funcs_in_impl_file(monkeypatch):
    """Test 6 & 7: Verify that bare error dicts and test functions returned for an impl file are rejected."""
    from app.services.db import db_service
    from app.services.workspace_service import workspace_service
    from app.services.ollama_service import ollama_service
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        workspace_service.root_dir = tmpdir
        ws_path = workspace_service.create_task_workspace("task_no_dict", "run_no_dict")
        db_service.create_or_update_run("run_no_dict", "task_no_dict", "No Dict", "Prompt", ws_path)

        plan = ImplementationPlan(
            run_id="run_no_dict",
            target_repo_path=ws_path,
            goal_model_version="1.0",
            steps=[],
            architecture_overview="Test arch",
            testing_strategy="Pytest",
            risk_assessment="Low",
            planned_files=[
                PlannedFile(path="app/service.py", action="modify", description="Service"),
                PlannedFile(path="tests/test_service.py", action="test", description="Tests"),
            ]
        )
        db_service.save_plan(plan)

        # 1. Model returns bare JSON error dictionary
        async def mock_chat_dict(**kwargs):
            return {"message": {"content": '{\n    "error": "The candidate code is identical. No changes made."\n}'}}

        monkeypatch.setattr(ollama_service, "chat_completion", mock_chat_dict)

        failing_res = TestRunResult(
            id="tr_dict", run_id="run_no_dict", attempt_number=1, exit_code=1, status="FAILED",
            stdout="tests/test_service.py:10: AssertionError: assert 8.75 == 9.25", test_items=[]
        )
        diagnosis = debugger_service._diagnose_failure(failing_res)

        modified = await debugger_service._apply_recovery_fix("run_no_dict", failing_res, diagnosis, "fake-model")
        assert modified == [], "Should reject bare dictionary for implementation file"

        # 2. Model returns only test functions for implementation file
        async def mock_chat_test_funcs(**kwargs):
            return {"message": {"content": 'def test_multiply():\n    assert multiply(3, 4) == 12\n'}}

        monkeypatch.setattr(ollama_service, "chat_completion", mock_chat_test_funcs)
        modified2 = await debugger_service._apply_recovery_fix("run_no_dict", failing_res, diagnosis, "fake-model")
        assert modified2 == [], "Should reject test functions for implementation file"


def test_extract_specific_failed_test_handles_collection_errors_without_dot_py_prefix():
    """Verify that JUnit collection failures with empty classname ("::tests.test_auth") extract "tests/test_auth.py" and never ".py::tests.test_auth"."""
    res = TestRunResult(
        id="tr_coll_test",
        run_id="run_coll",
        attempt_number=1,
        exit_code=2,
        status="FAILED",
        stdout="ERROR tests/test_auth.py - NameError: name 'BaseModel' is not defined",
        test_items=[
            TestResultItem(
                name="::tests.test_auth",
                status="ERROR",
                duration_ms=0.0,
                error_message="collection failure",
                stack_trace="NameError: name 'BaseModel' is not defined"
            )
        ]
    )

    target = debugger_service._extract_specific_failed_test(res)
    assert target == "tests/test_auth.py", f"Expected 'tests/test_auth.py' but got '{target}'"
    assert not target.startswith(".py::")
    assert not target == ".py"


@pytest.mark.asyncio
async def test_debugger_rejects_return_outside_function_and_uses_format_json_false(monkeypatch, tmp_path):
    """Verify that debugger rejects candidates with top-level return statements and queries Ollama with format_json=False."""
    from app.services.db import db_service
    from app.services.ollama_service import ollama_service
    from app.models.schema import ImplementationPlan, PlannedFile
    import uuid

    run_id = f"test_run_syntax_{uuid.uuid4().hex[:8]}"
    db_service.create_or_update_run(run_id, "t_syn", "Syntax Test", "Prompt", str(tmp_path))

    plan = ImplementationPlan(
        run_id=run_id,
        target_repo_path=str(tmp_path),
        goal_model_version="1.0",
        steps=[],
        architecture_overview="Arch",
        testing_strategy="Pytest",
        risk_assessment="Low",
        planned_files=[
            PlannedFile(path="app/main.py", action="create", description="Main file"),
            PlannedFile(path="tests/test_main.py", action="test", description="Tests"),
        ]
    )
    db_service.save_plan(plan)

    captured_kwargs = {}
    async def mock_chat(**kwargs):
        captured_kwargs.update(kwargs)
        # Return invalid candidate with return outside function
        return {"message": {"content": "from fastapi import FastAPI\nreturn JSONResponse({'status': 'ok'})\n"}}

    monkeypatch.setattr(ollama_service, "chat_completion", mock_chat)

    failing_res = TestRunResult(
        id="tr_syntax", run_id=run_id, attempt_number=1, exit_code=1, status="FAILED",
        stdout="SyntaxError: 'return' outside function in app/main.py", test_items=[]
    )
    diagnosis = debugger_service._diagnose_failure(failing_res)

    # Attempt fix with the mock LLM
    modified = await debugger_service._apply_recovery_fix(run_id, failing_res, diagnosis, "fake-model")

    # Verify that Ollama was queried with format_json=False
    assert captured_kwargs.get("format_json") is False, "Debugger must request raw Python code (format_json=False)"
    # Verify that the invalid candidate was rejected
    assert "return JSONResponse" not in (db_service.get_code_changes(run_id)[0].new_content if db_service.get_code_changes(run_id) else "")


def test_deterministic_repair_injects_missing_basemodel_import():
    """Verify that deterministic repair injects 'from pydantic import BaseModel' when NameError occurs."""
    broken_code = "class User(BaseModel):\n    name: str\n"
    repaired = debugger_service._deterministic_repair(
        file_rel_path="app/models.py",
        current_content=broken_code,
        diagnosis={"failure_reason": "NameError"},
        error_output="NameError: name 'BaseModel' is not defined",
        attempt_number=1
    )
    assert "from pydantic import BaseModel" in repaired
    assert "class User(BaseModel):" in repaired


def test_user_defined_task_targets_test_file_on_second_attempt_when_impl_unchanged():
    """Verify that for user-defined prompts, if implementation was already attempted, attempt 2 targets test file."""
    plan = ImplementationPlan(
        run_id="test_run_user_retry",
        target_repo_path="/fake/repo",
        goal_model_version="1.0",
        steps=[],
        architecture_overview="Multiply n numbers",
        testing_strategy="Pytest",
        risk_assessment="Low",
        planned_files=[
            PlannedFile(path="app/service.py", action="create", description="Service"),
            PlannedFile(path="tests/test_service.py", action="test", description="Tests"),
        ]
    )
    stdout_assert = """
tests/test_service.py:9: in test_multiply_numbers
    self.assertEqual(multiply_numbers(-1, -2, -3), 6)
E   AssertionError: -6 != 6
"""
    test_result = TestRunResult(
        id="tr_user_retry",
        run_id="test_run_user_retry",
        attempt_number=2,
        exit_code=1,
        status="FAILED",
        stdout=stdout_assert,
        test_items=[]
    )
    from app.models.schema import RecoveryAttempt
    prior_attempt = RecoveryAttempt(
        id="rec_prior",
        run_id="test_run_user_retry",
        attempt_number=1,
        failure_reason="Assertion Mismatch in Test Assertion",
        diagnosis="A test assertion disagreed with the observed result in app/service.py",
        proposed_fix="Inspect the traceback and repair the generated implementation app/service.py",
        files_modified=[]
    )
    target_file, target_line, is_impl = debugger_service._identify_failure_target(
        test_result, plan, "/fake/repo", history=[prior_attempt]
    )
    assert target_file == "tests/test_service.py", f"Expected tests/test_service.py on attempt 2, got {target_file}"
    assert is_impl is False


def test_predefined_task_never_targets_test_file_on_assertion_failure():
    """Verify that predefined benchmark tasks (e.g. test_auth.py) NEVER target the test file on assertion failure."""
    plan = ImplementationPlan(
        run_id="test_run_auth_retry",
        target_repo_path="/fake/repo",
        goal_model_version="1.0",
        steps=[],
        architecture_overview="Auth API",
        testing_strategy="Pytest",
        risk_assessment="Low",
        planned_files=[
            PlannedFile(path="app/auth.py", action="create", description="Auth"),
            PlannedFile(path="tests/test_auth.py", action="test", description="Auth tests"),
        ]
    )
    stdout_assert = """
tests/test_auth.py:40: in test_login
    assert res.status_code == 200
E   assert 401 == 200
"""
    test_result = TestRunResult(
        id="tr_auth_retry",
        run_id="test_run_auth_retry",
        attempt_number=2,
        exit_code=1,
        status="FAILED",
        stdout=stdout_assert,
        test_items=[]
    )
    from app.models.schema import RecoveryAttempt
    prior_attempt = RecoveryAttempt(
        id="rec_prior_auth",
        run_id="test_run_auth_retry",
        attempt_number=1,
        failure_reason="Assertion Mismatch in Test Assertion",
        diagnosis="Status code mismatch in app/auth.py",
        proposed_fix="Repair app/auth.py",
        files_modified=[]
    )
    target_file, target_line, is_impl = debugger_service._identify_failure_target(
        test_result, plan, "/fake/repo", history=[prior_attempt]
    )
    assert target_file == "app/auth.py", f"Predefined test suite must NOT be targeted for assertion failure, got {target_file}"
    assert is_impl is True


def test_deterministic_repair_fixes_assertion_mismatch_in_user_test_file():
    """Verify that deterministic repair updates flawed test assertions in user-defined test files."""
    code = """import unittest
from app.service import multiply_numbers

class TestService(unittest.TestCase):
    def test_multiply_numbers(self):
        self.assertEqual(multiply_numbers(2), 2)
        self.assertEqual(multiply_numbers(-1, -2, -3), 6)
"""
    err = """
tests/test_service.py:9: in test_multiply_numbers
    self.assertEqual(multiply_numbers(-1, -2, -3), 6)
E   AssertionError: -6 != 6
"""
    repaired = debugger_service._deterministic_repair(
        file_rel_path="tests/test_service.py",
        current_content=code,
        diagnosis={"failure_reason": "Assertion Mismatch"},
        error_output=err,
        attempt_number=2
    )
    assert "self.assertEqual(multiply_numbers(-1, -2, -3), -6)" in repaired
