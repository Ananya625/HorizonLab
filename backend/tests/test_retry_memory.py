import uuid
import pytest
from app.models.schema import (
    RecoveryAttempt,
    TestRunResult,
    TestResultItem,
    CodeChange,
    GoalModel,
    ImplementationPlan,
    PlannedFile
)
from app.services.db import DatabaseService, db_service
from app.services.debugger_service import DebuggerService, debugger_service

TestRunResult.__test__ = False
TestResultItem.__test__ = False


# ==============================================================================
# TEST 1: First retry with no history
# ==============================================================================
def test_01_first_retry_with_no_history():
    """Requirement 8: First retry has no previous history; history context is empty."""
    run_id = f"test_run_first_retry_{uuid.uuid4().hex[:8]}"
    
    # Query database for brand new run_id
    history = db_service.get_recovery_attempts(run_id)
    assert len(history) == 0

    # Format context
    context = debugger_service.format_recovery_history_context(history)
    assert context == ""
    assert "PREVIOUS RECOVERY ATTEMPTS" not in context


# ==============================================================================
# TEST 2: Second retry receives the first failed attempt
# ==============================================================================
def test_02_second_retry_receives_first_failed_attempt():
    """Requirement 8: Second retry receives the first failed attempt with approach, outcome, and evidence."""
    run_id = f"test_run_second_retry_{uuid.uuid4().hex[:8]}"
    
    # Record attempt #1 which failed
    attempt_1 = RecoveryAttempt(
        id=f"rec_{uuid.uuid4().hex[:8]}",
        run_id=run_id,
        attempt_number=1,
        failure_reason="Assertion Mismatch in Test Assertion",
        diagnosis="Function returned 4 but test asserted 5",
        root_cause_analysis="Expected value was incorrectly hardcoded as 5",
        proposed_fix="Patched tests/test_calc.py: assert add(2, 2) == 5",
        files_modified=["tests/test_calc.py"],
        resolved=False,
        test_run_id=f"testrun_{uuid.uuid4().hex[:8]}",
        subsequent_test_run_id=f"testrun_sub_{uuid.uuid4().hex[:8]}",
        test_result_status="FAILED",
        error_summary="FAILED tests/test_calc.py::test_add - assert 4 == 5"
    )
    db_service.create_or_update_run(attempt_1.run_id, "fixture", "Fixture", "Fixture", str(__file__))
    db_service.save_recovery_attempt(attempt_1)

    # In retry #2, retrieve history
    history = db_service.get_recovery_attempts(run_id)
    assert len(history) == 1
    assert history[0].attempt_number == 1
    assert history[0].test_result_status == "FAILED"

    # Format context for Ollama prompt
    context = debugger_service.format_recovery_history_context(history)
    assert "Attempt #1" in context
    assert "Patched tests/test_calc.py" in context
    assert "Outcome: FAILED" in context
    assert "FAILED tests/test_calc.py::test_add - assert 4 == 5" in context
    assert "FAILED STRATEGY: Do NOT repeat this patch" in context


# ==============================================================================
# TEST 3: Previously successful recovery being marked correctly
# ==============================================================================
def test_03_previously_successful_recovery_marked_correctly():
    """Requirement 8: Succeeded recovery attempt is identified as SUCCEEDED without negative directives."""
    run_id = f"test_run_success_{uuid.uuid4().hex[:8]}"
    
    attempt = RecoveryAttempt(
        id=f"rec_{uuid.uuid4().hex[:8]}",
        run_id=run_id,
        attempt_number=1,
        failure_reason="ZeroDivisionError",
        diagnosis="Added check for zero divisor",
        root_cause_analysis="Denominator zero check missing",
        proposed_fix="Added if b == 0: raise ValueError()",
        files_modified=["app/calc.py"],
        resolved=True,
        test_run_id=f"testrun_{uuid.uuid4().hex[:8]}",
        subsequent_test_run_id=f"testrun_sub_{uuid.uuid4().hex[:8]}",
        test_result_status="PASSED",
        error_summary=""
    )
    db_service.create_or_update_run(attempt.run_id, "fixture", "Fixture", "Fixture", str(__file__))
    db_service.save_recovery_attempt(attempt)

    history = db_service.get_recovery_attempts(run_id)
    assert len(history) == 1
    assert history[0].resolved is True
    assert history[0].test_result_status == "PASSED"

    context = debugger_service.format_recovery_history_context(history)
    assert "Outcome: SUCCEEDED" in context
    assert "Test suite passed cleanly" in context
    assert "FAILED STRATEGY" not in context


# ==============================================================================
# TEST 4: No repetition of an unchanged failed approach
# ==============================================================================
def test_04_no_repetition_of_unchanged_failed_approach():
    """Requirement 8: Detect when candidate patch repeats unchanged file or a previous failed patch."""
    run_id = f"test_run_loop_{uuid.uuid4().hex[:8]}"
    current_failing_code = "def add(a, b):\n    return a - b\n"
    file_to_fix = "app/service.py"

    attempt_1 = RecoveryAttempt(
        id=f"rec_{uuid.uuid4().hex[:8]}",
        run_id=run_id,
        attempt_number=1,
        failure_reason="AssertionError",
        diagnosis="Calculation error",
        root_cause_analysis="",
        proposed_fix="Changed subtraction logic",
        files_modified=[file_to_fix],
        resolved=False,
        test_result_status="FAILED"
    )
    db_service.create_or_update_run(attempt_1.run_id, "fixture", "Fixture", "Fixture", str(__file__))
    db_service.save_recovery_attempt(attempt_1)

    failed_code_change = CodeChange(
        id=f"change_{uuid.uuid4().hex[:8]}",
        run_id=run_id,
        file_path=file_to_fix,
        action="modified",
        original_content="def add(a, b): pass",
        new_content="def add(a, b):\n    return a * b\n",
        diff_patch=""
    )
    db_service.save_code_change(failed_code_change)

    history = db_service.get_recovery_attempts(run_id)
    past_changes = db_service.get_code_changes(run_id)

    # 1. Unchanged code check: candidate is identical to current failing file
    rep1 = debugger_service._detect_repeated_approach(
        candidate_code=current_failing_code,
        current_content=current_failing_code,
        history=history,
        file_to_fix=file_to_fix,
        past_code_changes=past_changes
    )
    assert rep1 is not None
    assert "identical to the currently failing file" in rep1

    # 2. Repeated failed patch: candidate matches previously failed change
    rep2 = debugger_service._detect_repeated_approach(
        candidate_code="def add(a, b):\n    return a * b\n",
        current_content=current_failing_code,
        history=history,
        file_to_fix=file_to_fix,
        past_code_changes=past_changes
    )
    assert rep2 is not None
    assert "identical to a patch previously applied that failed" in rep2

    # 3. Valid, materially different fix: NOT blocked
    valid_fix = "def add(a, b):\n    return a + b\n"
    rep3 = debugger_service._detect_repeated_approach(
        candidate_code=valid_fix,
        current_content=current_failing_code,
        history=history,
        file_to_fix=file_to_fix,
        past_code_changes=past_changes
    )
    assert rep3 is None


# ==============================================================================
# TEST 5: Unknown test outcomes not being treated as failures
# ==============================================================================
def test_05_unknown_test_outcomes_not_treated_as_failures():
    """Requirement 8: Unknown/unverified test outcomes must never be reported as failures."""
    run_id = f"test_run_unknown_{uuid.uuid4().hex[:8]}"

    attempt = RecoveryAttempt(
        id=f"rec_{uuid.uuid4().hex[:8]}",
        run_id=run_id,
        attempt_number=1,
        failure_reason="Timeout pending",
        diagnosis="Proposed async socket timeout handler",
        root_cause_analysis="",
        proposed_fix="Added timeout=5 to socket connect",
        files_modified=["app/connection.py"],
        resolved=False,
        test_run_id=None,
        subsequent_test_run_id=None,
        test_result_status="UNKNOWN",
        error_summary=""
    )
    db_service.create_or_update_run(attempt.run_id, "fixture", "Fixture", "Fixture", str(__file__))
    db_service.save_recovery_attempt(attempt)

    history = db_service.get_recovery_attempts(run_id)
    assert len(history) == 1
    assert history[0].test_result_status == "UNKNOWN"

    context = debugger_service.format_recovery_history_context(history)
    assert "Outcome: UNKNOWN (Test outcome not verified)" in context
    assert "Outcome: FAILED" not in context
    assert "FAILED STRATEGY" not in context
    assert "do not assume this fix failed" in context


# ==============================================================================
# TEST 6: History limited to the configured number of attempts
# ==============================================================================
def test_06_history_limited_to_configured_number_of_attempts():
    """Requirement 8: History context is bounded to max_history_attempts."""
    run_id = f"test_run_limit_{uuid.uuid4().hex[:8]}"

    # Insert 5 attempts
    for i in range(1, 6):
        att = RecoveryAttempt(
            id=f"rec_{i}_{uuid.uuid4().hex[:8]}",
            run_id=run_id,
            attempt_number=i,
            failure_reason=f"Failure reason {i}",
            diagnosis=f"Diagnosis attempt {i}",
            root_cause_analysis="",
            proposed_fix=f"Patch attempt #{i}",
            files_modified=[f"file_{i}.py"],
            resolved=False,
            test_result_status="FAILED",
            error_summary=f"AssertionError in step {i}"
        )
        db_service.create_or_update_run(att.run_id, "fixture", "Fixture", "Fixture", str(__file__))
        db_service.save_recovery_attempt(att)

    history = db_service.get_recovery_attempts(run_id)
    assert len(history) == 5

    # With max_attempts = 2, only attempt #4 and #5 should appear
    custom_debugger = DebuggerService(max_history_attempts=2)
    context = custom_debugger.format_recovery_history_context(history)
    
    assert "Attempt #4" in context
    assert "Attempt #5" in context
    assert "Attempt #1" not in context
    assert "Attempt #2" not in context
    assert "Attempt #3" not in context


# ==============================================================================
# TEST 7: Large tracebacks producing bounded context
# ==============================================================================
def test_07_large_tracebacks_producing_bounded_context():
    """Requirement 8: Huge terminal logs/tracebacks are extracted and strictly bounded."""
    # Create massive 20,000 char log
    noisy_lines = ["collecting ... collected 100 items\n"] * 300
    noisy_lines.append("tests/test_auth.py::test_token FAILED\n")
    noisy_lines.append("E   AssertionError: assert 401 == 200\n")
    noisy_lines.append("E   + where 401 = response.status_code\n")
    noisy_lines.extend(["extra warning line\n"] * 300)
    huge_stdout = "".join(noisy_lines)
    assert len(huge_stdout) > 15000

    debugger = DebuggerService(max_traceback_chars=500)
    summary = debugger._extract_concise_error_summary(huge_stdout, stderr="")

    assert len(summary) <= 600  # 500 chars + truncation marker
    assert "AssertionError: assert 401 == 200" in summary
    assert "FAILED" in summary


# ==============================================================================
# TEST 8: Strict run_id isolation
# ==============================================================================
def test_08_strict_run_id_isolation():
    """Requirement 8: History from Run A is never exposed to Run B."""
    run_a = f"test_run_a_{uuid.uuid4().hex[:8]}"
    run_b = f"test_run_b_{uuid.uuid4().hex[:8]}"

    # Add attempt to Run A
    attempt_a = RecoveryAttempt(
        id=f"rec_a_{uuid.uuid4().hex[:8]}",
        run_id=run_a,
        attempt_number=1,
        failure_reason="Secret Key Missing in Run A",
        diagnosis="Run A private diagnosis",
        root_cause_analysis="",
        proposed_fix="Run A private patch",
        files_modified=["app/run_a.py"],
        resolved=False,
        test_result_status="FAILED"
    )
    db_service.create_or_update_run(attempt_a.run_id, "fixture", "Fixture", "Fixture", str(__file__))
    db_service.save_recovery_attempt(attempt_a)

    # Query for Run B
    history_b = db_service.get_recovery_attempts(run_b)
    assert len(history_b) == 0

    context_b = debugger_service.format_recovery_history_context(history_b)
    assert context_b == ""
    assert "Run A" not in context_b


# ==============================================================================
# TEST 9: Database persistence across application restart
# ==============================================================================
def test_09_database_persistence_across_application_restart():
    """Requirement 8: Stored attempts persist and reload in a fresh DatabaseService instance."""
    run_id = f"test_run_restart_{uuid.uuid4().hex[:8]}"

    attempt = RecoveryAttempt(
        id=f"rec_restart_{uuid.uuid4().hex[:8]}",
        run_id=run_id,
        attempt_number=1,
        failure_reason="ImportError: cannot import name 'auth_handler'",
        diagnosis="Missing export symbol in auth module",
        root_cause_analysis="Public function was not included in __all__",
        proposed_fix="Exported auth_handler in app/auth/__init__.py",
        files_modified=["app/auth/__init__.py"],
        resolved=True,
        test_run_id=f"testrun_init_{uuid.uuid4().hex[:8]}",
        subsequent_test_run_id=f"testrun_pass_{uuid.uuid4().hex[:8]}",
        test_result_status="PASSED",
        error_summary="ImportError: cannot import name 'auth_handler'"
    )
    db_service.create_or_update_run(attempt.run_id, "fixture", "Fixture", "Fixture", str(__file__))
    db_service.save_recovery_attempt(attempt)

    # Instantiate brand-new DatabaseService instance to simulate restart
    fresh_db = DatabaseService(db_path=db_service.db_path)
    loaded = fresh_db.get_recovery_attempts(run_id)

    assert len(loaded) == 1
    assert loaded[0].id == attempt.id
    assert loaded[0].run_id == run_id
    assert loaded[0].attempt_number == 1
    assert loaded[0].proposed_fix == "Exported auth_handler in app/auth/__init__.py"
    assert loaded[0].resolved is True
    assert loaded[0].test_result_status == "PASSED"
    assert loaded[0].error_summary == "ImportError: cannot import name 'auth_handler'"


# ==============================================================================
# TEST 10: Duplicate outcome handling
# ==============================================================================
def test_10_duplicate_outcome_handling():
    """Requirement 8: Saving same attempt outcome repeatedly updates existing row without duplicates."""
    run_id = f"test_run_dedup_{uuid.uuid4().hex[:8]}"
    attempt_id = f"rec_dedup_{uuid.uuid4().hex[:8]}"

    attempt_v1 = RecoveryAttempt(
        id=attempt_id,
        run_id=run_id,
        attempt_number=1,
        failure_reason="Initial error",
        diagnosis="Initial diagnosis",
        root_cause_analysis="",
        proposed_fix="Initial fix draft",
        files_modified=["tests/test_dup.py"],
        resolved=False,
        test_result_status="UNKNOWN"
    )
    db_service.create_or_update_run(attempt_v1.run_id, "fixture", "Fixture", "Fixture", str(__file__))
    db_service.save_recovery_attempt(attempt_v1)
    assert len(db_service.get_recovery_attempts(run_id)) == 1

    # Second save: updated with verified test results
    attempt_v2 = RecoveryAttempt(
        id=attempt_id,
        run_id=run_id,
        attempt_number=1,
        failure_reason="Verified error",
        diagnosis="Verified diagnosis",
        root_cause_analysis="Updated root cause",
        proposed_fix="Verified patch description",
        files_modified=["tests/test_dup.py"],
        resolved=True,
        test_result_status="PASSED",
        error_summary="Tests clean pass"
    )
    db_service.create_or_update_run(attempt_v2.run_id, "fixture", "Fixture", "Fixture", str(__file__))
    db_service.save_recovery_attempt(attempt_v2)

    # Must still have exactly 1 record, updated in place
    attempts = db_service.get_recovery_attempts(run_id)
    assert len(attempts) == 1
    assert attempts[0].id == attempt_id
    assert attempts[0].resolved is True
    assert attempts[0].test_result_status == "PASSED"
    assert attempts[0].proposed_fix == "Verified patch description"


# ==============================================================================
# TEST 11: Debugger prompt includes cumulative retry memory e2e
# ==============================================================================
@pytest.mark.asyncio
@pytest.mark.parametrize('valid_repair', [True, False])
async def test_11_debugger_retrieval_and_prompt_injection_e2e(monkeypatch, tmp_path, valid_repair):
    """End-to-End: Debugger retrieves previous attempts and passes them to Ollama prompt."""
    run_id = f"test_run_e2e_{uuid.uuid4().hex[:8]}"

    (tmp_path / "tests").mkdir()
    (tmp_path / "app").mkdir()
    (tmp_path / "app/service.py").write_text("def health(): return 404\n")
    (tmp_path / "tests/test_auth.py").write_text("from app.service import health\ndef test_health(): assert health() == 200\n")
    # Setup run and goal in DB
    db_service.create_or_update_run(
        run_id=run_id,
        task_id="task_e2e",
        title="Test E2E Recovery Memory",
        prompt="Fix calculation bug",
        repo_path=str(tmp_path)
    )
    goal = GoalModel(
        run_id=run_id,
        task_id="task_e2e",
        original_request="Fix calculation bug",
        normalized_request="Fix calculation bug",
        main_goal="Fix calculation bug",
        summary="Test summary"
    )
    db_service.save_goal_model(goal)

    plan = ImplementationPlan(
        run_id=run_id,
        architecture_overview="Test arch",
        target_repo_path=str(tmp_path),
        planned_files=[PlannedFile(path="app/service.py", action="modify", description="Health implementation"), PlannedFile(path="tests/test_auth.py", action="test", description="Auth test")],
        steps=[],
        testing_strategy="pytest",
        risk_assessment="low"
    )
    db_service.save_plan(plan)

    # Insert previous failed attempt #1
    attempt_1 = RecoveryAttempt(
        id=f"rec_e2e_{uuid.uuid4().hex[:8]}",
        run_id=run_id,
        attempt_number=1,
        failure_reason="Assertion Mismatch",
        diagnosis="Failed assertion in nominal case",
        root_cause_analysis="",
        proposed_fix="Tried asserting status == 404",
        files_modified=["tests/test_auth.py"],
        resolved=False,
        test_result_status="FAILED",
        error_summary="AssertionError: assert 404 == 200"
    )
    db_service.create_or_update_run(attempt_1.run_id, "fixture", "Fixture", "Fixture", str(__file__))
    db_service.save_recovery_attempt(attempt_1)

    captured_messages = []

    async def fake_chat_completion(messages, **kwargs):
        captured_messages.extend(messages)
        return {
            "message": {
                "content": "def health(): return 200\n" if valid_repair else ""
            }
        }

    from app.services.ollama_service import ollama_service
    monkeypatch.setattr(ollama_service, "chat_completion", fake_chat_completion)

    test_result = TestRunResult(
        id=f"tr_{uuid.uuid4().hex[:8]}",
        run_id=run_id,
        attempt_number=2,
        stdout="FAILED tests/test_auth.py::test_health - assert 404 == 200",
        exit_code=1,
        status="FAILED"
    )

    # Execute _apply_recovery_fix for Attempt #2
    from contextlib import nullcontext
    with nullcontext() if valid_repair else pytest.raises(RuntimeError, match='no valid'):
        await debugger_service._apply_recovery_fix(
            run_id=run_id,
            test_result=test_result,
            diagnosis={"failure_reason": "Assertion Mismatch", "diagnosis": "Assertion failed", "root_cause": "", "proposed_fix": "Fix assertion"},
            model_name="qwen2.5-coder:1.5b"
        )

    # Verify that captured prompt sent to Ollama contains Attempt #1 history
    assert len(captured_messages) > 0
    user_prompt = next(m["content"] for m in captured_messages if m["role"] == "user")
    
    assert "PREVIOUS RECOVERY ATTEMPTS IN THIS RUN (CUMULATIVE RETRY MEMORY)" in user_prompt
    assert "Attempt #1" in user_prompt
    assert "Tried asserting status == 404" in user_prompt
    assert "Outcome: FAILED" in user_prompt
    assert "FAILED STRATEGY: Do NOT repeat this patch" in user_prompt

    assert (tmp_path / 'app/service.py').read_text().strip() == ('def health(): return 200' if valid_repair else 'def health(): return 404')
    assert (tmp_path / 'tests/test_auth.py').read_text() == 'from app.service import health\ndef test_health(): assert health() == 200\n'
