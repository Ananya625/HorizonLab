import os
import sys
import time
import pytest
from unittest.mock import patch

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.goal_tracker_service import (
    goal_tracker_service
)
from app.services.drift_controller_service import (
    drift_controller_service
)
from app.services.test_runner_service import test_runner_service
from app.services.workspace_service import workspace_service
from app.services.db import db_service


# ==============================================================================
# TEST 1: Simple Python addition task
# ==============================================================================
@pytest.mark.asyncio
async def test_01_simple_python_addition_task():
    """Test 1: Simple Python addition task with lightweight deterministic goal tracker."""
    run_id = f"test_run_add_{int(time.time()*1000)}"
    task_id = f"task_add_{int(time.time()*1000)}"
    request_text = "Implement a helper function add(a: int, b: int) -> int in app/service.py and test in tests/test_service.py"

    # Initialize tracker
    state = goal_tracker_service.initialize_task(
        run_id=run_id,
        task_id=task_id,
        original_request=request_text,
        complexity_profile="simple",
        target_files=["app/service.py", "tests/test_service.py"]
    )

    # 1. Verification of initial state
    assert state.run_id == run_id
    assert state.task_id == task_id
    assert state.original_user_request == request_text
    assert state.current_goal == request_text
    assert state.complexity_profile == "simple"
    assert state.task_status == "running"
    
    # Simple profile must NOT create redundant multi-phase planning subtasks
    assert len(state.ordered_subtasks) == 1
    assert state.ordered_subtasks[0].id == "SUBTASK-1"
    assert state.current_active_subtask_id == "SUBTASK-1"

    # Acceptance criteria initialized
    assert len(state.acceptance_criteria) >= 1
    assert state.acceptance_criteria[0].status == "pending"

    # Start subtask
    subtask = goal_tracker_service.start_subtask(run_id, "SUBTASK-1")
    assert subtask.status == "running"

    # Simulate tool action: writing code
    code_content = "def add(a: int, b: int) -> int:\n    return a + b\n"
    pre_check = drift_controller_service.check_action(
        run_id=run_id,
        action_type="file_write",
        target="app/service.py",
        payload_str=code_content
    )
    assert pre_check.allowed is True
    assert pre_check.action_category == "safe"

    act_record = goal_tracker_service.record_action(
        run_id=run_id,
        action_type="file_write",
        target="app/service.py",
        payload_str=code_content,
        status="completed",
        details={"lines_added": 2}
    )
    assert act_record.status == "completed"

    # Simulate test execution and criteria verification
    val_res = drift_controller_service.validate_result(
        run_id=run_id,
        action_type="test_run",
        target="pytest tests/test_service.py",
        success=True,
        details={"exit_code": 0, "passed_tests": 2, "failed_tests": 0, "total_tests": 2}
    )
    assert val_res.valid is True
    assert val_res.status == "accepted"

    # Verify criteria updated in tracker
    updated_state = goal_tracker_service.get_state(run_id)
    assert updated_state.acceptance_criteria[0].status == "passed"
    assert goal_tracker_service.can_complete(run_id) is True

    # Complete task
    goal_tracker_service.complete_subtask(run_id, "SUBTASK-1", evidence="2 tests passed cleanly")
    final_state = goal_tracker_service.terminate_task(
        run_id=run_id,
        status="completed",
        reason="criteria_verified",
        evidence={"tests_passed": 2, "exit_code": 0}
    )
    assert final_state.task_status == "completed"
    assert final_state.termination_reason == "criteria_verified"
    assert final_state.completion_evidence["tests_passed"] == 2


# ==============================================================================
# TEST 2: Coding task that requires multiple files
# ==============================================================================
def test_02_coding_task_multiple_files_decomposition():
    """Test 2: Coding task requiring multiple files triggers structured subtask decomposition."""
    run_id = f"test_run_multifile_{int(time.time()*1000)}"
    task_id = f"task_multifile_{int(time.time()*1000)}"
    request_text = "Implement account model in app/models.py, serializer in app/serializers.py, and test in tests/test_models.py"

    state = goal_tracker_service.initialize_task(
        run_id=run_id,
        task_id=task_id,
        original_request=request_text,
        complexity_profile="medium",
        target_files=["app/models.py", "app/serializers.py", "tests/test_models.py"]
    )

    # Decomposed into exactly 3 ordered engineering subtasks
    assert len(state.ordered_subtasks) == 3
    assert state.ordered_subtasks[0].id == "SUBTASK-1"
    assert state.ordered_subtasks[1].id == "SUBTASK-2"
    assert state.ordered_subtasks[2].id == "SUBTASK-3"

    # Step 1: Subtask 1 (Spec & Architecture)
    st1 = goal_tracker_service.start_subtask(run_id, "SUBTASK-1")
    assert st1.status == "running"
    goal_tracker_service.complete_subtask(run_id, "SUBTASK-1", evidence="Spec and interfaces defined")
    assert goal_tracker_service.get_state(run_id).current_active_subtask_id == "SUBTASK-2"

    # Step 2: Subtask 2 (Implementation across multiple files)
    st2 = goal_tracker_service.start_subtask(run_id, "SUBTASK-2")
    assert st2.status == "running"

    for fpath in ["app/models.py", "app/serializers.py"]:
        chk = drift_controller_service.check_action(run_id, "file_write", fpath, payload_str=f"# {fpath} code")
        assert chk.allowed is True
        goal_tracker_service.record_action(run_id, "file_write", fpath, f"# {fpath} code", "completed")

    goal_tracker_service.complete_subtask(run_id, "SUBTASK-2", evidence="All 2 files implemented")
    assert goal_tracker_service.get_state(run_id).current_active_subtask_id == "SUBTASK-3"

    # Step 3: Subtask 3 (Testing & Verification)
    goal_tracker_service.start_subtask(run_id, "SUBTASK-3")
    goal_tracker_service.verify_criterion(run_id, "all", passed=True, evidence="Suite passed 100%")
    goal_tracker_service.complete_subtask(run_id, "SUBTASK-3", evidence="Verified clean")

    final_state = goal_tracker_service.terminate_task(run_id, "completed", "criteria_verified")
    assert final_state.task_status == "completed"
    assert all(st.status == "completed" for st in final_state.ordered_subtasks)


# ==============================================================================
# TEST 3: Unrelated proposed action
# ==============================================================================
def test_03_unrelated_proposed_action_blocked():
    """Test 3: Drift controller detects and blocks unrelated/unsafe actions before execution."""
    run_id = f"test_run_drift_{int(time.time()*1000)}"
    task_id = f"task_drift_{int(time.time()*1000)}"
    repo_path = os.path.abspath("sandbox/test_workspace")

    goal_tracker_service.initialize_task(
        run_id=run_id,
        task_id=task_id,
        original_request="Implement simple string formatting in app/format.py",
        complexity_profile="simple"
    )

    db_service.create_or_update_run(run_id, task_id, 'Drift test', 'Drift test', repo_path)
    # 3a. Path Traversal escaping sandbox
    traversal_target = os.path.abspath(os.path.join(repo_path, "../../etc/passwd"))
    decision = drift_controller_service.check_action(
        run_id=run_id,
        action_type="file_write",
        target=traversal_target,
        payload_str="root:x:0:0",
        repo_path=repo_path
    )
    assert decision.allowed is False
    assert decision.violation_type == "path_traversal"
    assert decision.action_category == "blocked"

    # 3b. Protected system directory (.git)
    git_target = os.path.join(repo_path, ".git/hooks/pre-commit")
    decision2 = drift_controller_service.check_action(
        run_id=run_id,
        action_type="file_write",
        target=git_target,
        payload_str="#!/bin/sh\nexit 0",
        repo_path=repo_path
    )
    assert decision2.allowed is False
    assert decision2.violation_type == "permission_violation"

    # 3c. Unapproved file extension (.exe)
    exe_target = os.path.join(repo_path, "miner.exe")
    decision3 = drift_controller_service.check_action(
        run_id=run_id,
        action_type="file_write",
        target=exe_target,
        payload_str="binary data",
        repo_path=repo_path
    )
    assert decision3.allowed is False
    assert decision3.violation_type == "unrelated_action"

    # 3d. Check drift audit table was populated in SQLite
    with db_service._get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT violation_type FROM drift_audit_logs WHERE run_id = ?", (run_id,))
        violations = [row[0] for row in cursor.fetchall()]
        assert "path_traversal" in violations
        assert "permission_violation" in violations
        assert "unrelated_action" in violations


# ==============================================================================
# TEST 4: Repeated commands and repeated failed edits
# ==============================================================================
def test_04_repeated_commands_and_repeated_failed_edits():
    """Test 4: Drift controller blocks duplicate commands and identical content edit loops."""
    run_id = f"test_run_dup_{int(time.time()*1000)}"
    task_id = f"task_dup_{int(time.time()*1000)}"

    goal_tracker_service.initialize_task(
        run_id=run_id,
        task_id=task_id,
        original_request="Fix bug in calculation module",
        complexity_profile="simple"
    )

    content = "def calculate(x):\n    return x * 2\n"

    # First edit: permitted
    d1 = drift_controller_service.check_action(run_id, "file_write", "app/calc.py", payload_str=content)
    assert d1.allowed is True
    goal_tracker_service.record_action(run_id, "file_write", "app/calc.py", content, "completed")

    # Second edit with IDENTICAL content: blocked as duplicate
    d2 = drift_controller_service.check_action(run_id, "file_write", "app/calc.py", payload_str=content)
    assert d2.allowed is False
    assert d2.violation_type == "repeated_action"
    assert d2.action_category == "duplicate_skipped"
    assert "identical" in d2.reason.lower()

    # Repeated command execution check
    cmd = "pytest tests/test_calc.py"
    # First command: permitted
    cmd_d1 = drift_controller_service.check_action(run_id, "command_exec", cmd, payload_str="1")
    assert cmd_d1.allowed is True

    # Second command: permitted (max_identical_actions is 2)
    cmd_d2 = drift_controller_service.check_action(run_id, "command_exec", cmd, payload_str="1")
    assert cmd_d2.allowed is True

    # Third command without intermediate code changes: blocked as duplicate
    cmd_d3 = drift_controller_service.check_action(run_id, "command_exec", cmd, payload_str="1")
    assert cmd_d3.allowed is False
    assert cmd_d3.violation_type == "repeated_action"
    assert cmd_d3.action_category == "duplicate_skipped"


# ==============================================================================
# TEST 5: Legitimate retry after a test failure
# ==============================================================================
def test_05_legitimate_retry_after_test_failure():
    """Test 5: System permits legitimate retry with new code modification after a failure."""
    run_id = f"test_run_retry_{int(time.time()*1000)}"
    task_id = f"task_retry_{int(time.time()*1000)}"

    goal_tracker_service.initialize_task(
        run_id=run_id,
        task_id=task_id,
        original_request="Implement divider function with zero check",
        complexity_profile="medium"
    )

    # Attempt 1: Code with bug
    bad_code = "def divide(a, b):\n    return a / b\n"
    d1 = drift_controller_service.check_action(run_id, "file_write", "app/divide.py", bad_code)
    assert d1.allowed is True
    goal_tracker_service.record_action(run_id, "file_write", "app/divide.py", bad_code, "completed")

    # Test run 1: Fails
    val1 = drift_controller_service.validate_result(
        run_id=run_id,
        action_type="test_run",
        target="pytest tests/test_divide.py",
        success=False,
        details={"exit_code": 1, "passed_tests": 1, "failed_tests": 1, "total_tests": 2}
    )
    assert val1.valid is False
    assert val1.status == "test_failure"
    assert val1.should_retry is True

    goal_tracker_service.record_action(
        run_id=run_id,
        action_type="test_run",
        target="pytest tests/test_divide.py",
        payload_str="attempt_1",
        status="failed",
        error_message="ZeroDivisionError in test 2"
    )

    state = goal_tracker_service.get_state(run_id)
    assert state.failed_attempts_count == 1

    # Legitimate retry: NEW code with fix
    fixed_code = "def divide(a, b):\n    if b == 0:\n        raise ValueError('Division by zero')\n    return a / b\n"
    d2 = drift_controller_service.check_action(run_id, "file_write", "app/divide.py", fixed_code)
    assert d2.allowed is True  # Allowed because content hash is different!
    goal_tracker_service.record_action(run_id, "file_write", "app/divide.py", fixed_code, "completed")

    # Test run 2: Passes
    val2 = drift_controller_service.validate_result(
        run_id=run_id,
        action_type="test_run",
        target="pytest tests/test_divide.py",
        success=True,
        details={"exit_code": 0, "passed_tests": 2, "failed_tests": 0, "total_tests": 2}
    )
    assert val2.valid is True
    assert val2.status == "accepted"

    # Completion check succeeds
    comp = drift_controller_service.check_completion(run_id)
    assert comp.allowed is True


# ==============================================================================
# TEST 6: Task that exceeds its execution budget
# ==============================================================================
def test_06_task_exceeds_execution_budget():
    """Test 6: Drift controller blocks execution when tool action budget is exceeded."""
    run_id = f"test_run_budget_{int(time.time()*1000)}"
    task_id = f"task_budget_{int(time.time()*1000)}"

    goal_tracker_service.initialize_task(
        run_id=run_id,
        task_id=task_id,
        original_request="Simple task with strict budget",
        complexity_profile="simple"  # Max tool calls is 12
    )

    # Exhaust the budget with 12 recorded actions
    for i in range(12):
        goal_tracker_service.record_action(
            run_id=run_id,
            action_type="file_write",
            target=f"app/file_{i}.py",
            payload_str=f"# content {i}",
            status="completed"
        )

    # The 13th action should be blocked due to exhausted budget
    decision = drift_controller_service.check_action(
        run_id=run_id,
        action_type="file_write",
        target="app/file_overflow.py",
        payload_str="# overflow"
    )
    assert decision.allowed is False
    assert decision.violation_type == "budget_exceeded"
    assert decision.action_category == "budget_exceeded"

    # Task status should be terminated as failed
    updated_state = goal_tracker_service.get_state(run_id)
    assert updated_state.task_status == "failed"
    assert updated_state.termination_reason == "budget_exceeded"


# ==============================================================================
# TEST 7: Task that fails verification
# ==============================================================================
def test_07_task_fails_verification_and_blocks_premature_completion():
    """Test 7: check_completion blocks premature completion when acceptance criteria are unverified."""
    run_id = f"test_run_verif_fail_{int(time.time()*1000)}"
    task_id = f"task_verif_fail_{int(time.time()*1000)}"

    goal_tracker_service.initialize_task(
        run_id=run_id,
        task_id=task_id,
        original_request="Build microservice with full pytest suite",
        complexity_profile="simple"
    )

    # Agent attempts completion without passing test runner
    comp_check = drift_controller_service.check_completion(run_id)
    assert comp_check.allowed is False
    assert comp_check.violation_type == "premature_completion"
    assert "SC-1" in comp_check.reason

    # Mark criterion explicitly failed
    goal_tracker_service.verify_criterion(
        run_id=run_id,
        criterion_id="SC-1",
        passed=False,
        evidence="AssertionError in test_case_3"
    )

    state = goal_tracker_service.get_state(run_id)
    assert goal_tracker_service.can_complete(run_id) is False
    assert state.acceptance_criteria[0].status == "failed"

    # Terminate as failed
    final_state = goal_tracker_service.terminate_task(
        run_id=run_id,
        status="failed",
        reason="verification_failed",
        evidence={"failed_criterion": "SC-1"}
    )
    assert final_state.task_status == "failed"
    assert final_state.termination_reason == "verification_failed"


# ==============================================================================
# TEST 8: Explicit user-requested goal change
# ==============================================================================
def test_08_explicit_user_requested_goal_change():
    """Test 8: Controlled goal revision updates goal while strictly preserving original request."""
    run_id = f"test_run_revise_{int(time.time()*1000)}"
    task_id = f"task_revise_{int(time.time()*1000)}"
    original = "Implement basic username and password authentication in app/auth.py"

    goal_tracker_service.initialize_task(
        run_id=run_id,
        task_id=task_id,
        original_request=original,
        complexity_profile="medium"
    )

    # User modifies task goal
    revised_text = "Implement OAuth2 Bearer token authentication with Google provider"
    revised_state = goal_tracker_service.revise_goal(
        run_id=run_id,
        new_goal_text=revised_text,
        change_reason="User switched from local password to OAuth2 provider",
        author="user"
    )

    # Invariant: Original user request MUST remain unchanged
    assert revised_state.original_user_request == original
    assert revised_state.current_goal == revised_text
    
    # Invariant: Revision history tracked
    assert len(revised_state.revision_history) == 1
    rev = revised_state.revision_history[0]
    assert rev.previous_goal == original
    assert rev.revised_goal == revised_text
    assert rev.change_reason == "User switched from local password to OAuth2 provider"
    assert rev.author == "user"

    # Verify persisted in SQLite
    persisted_state = goal_tracker_service._load_state(run_id)
    assert persisted_state.original_user_request == original
    assert persisted_state.current_goal == revised_text
    assert len(persisted_state.revision_history) == 1


# ==============================================================================
# TEST 9: Two concurrent tasks with isolated state
# ==============================================================================
def test_09_two_concurrent_tasks_isolated_state():
    """Test 9: Multiple tasks running concurrently maintain strictly isolated tracking state."""
    run_id_a = f"test_run_conc_A_{int(time.time()*1000)}"
    run_id_b = f"test_run_conc_B_{int(time.time()*1000)}"

    # Task A: Simple addition
    goal_tracker_service.initialize_task(
        run_id=run_id_a,
        task_id="task_A",
        original_request="Task A: Addition helper",
        complexity_profile="simple"
    )

    # Task B: Complex encryption
    goal_tracker_service.initialize_task(
        run_id=run_id_b,
        task_id="task_B",
        original_request="Task B: AES-GCM encryption",
        complexity_profile="complex"
    )

    # Actions performed on Task A
    goal_tracker_service.record_action(run_id_a, "file_write", "app/add.py", "def add(): pass", "completed")
    goal_tracker_service.verify_criterion(run_id_a, "all", passed=True, evidence="A passed")

    # Revisions performed on Task B
    goal_tracker_service.revise_goal(run_id_b, "Task B: Revised to ChaCha20", "Changed cipher")

    # Read states back
    read_a = goal_tracker_service.get_state(run_id_a)
    read_b = goal_tracker_service.get_state(run_id_b)

    # Assert Task A isolation
    assert read_a.original_user_request == "Task A: Addition helper"
    assert read_a.current_goal == "Task A: Addition helper"
    assert len(read_a.action_history) == 1
    assert len(read_a.revision_history) == 0
    assert read_a.complexity_profile == "simple"
    assert read_a.acceptance_criteria[0].status == "passed"

    # Assert Task B isolation
    assert read_b.original_user_request == "Task B: AES-GCM encryption"
    assert read_b.current_goal == "Task B: Revised to ChaCha20"
    assert len(read_b.action_history) == 0
    assert len(read_b.revision_history) == 1
    assert read_b.complexity_profile == "complex"
    assert read_b.acceptance_criteria[0].status == "pending"


# ==============================================================================
# TEST 10: Tool timeout and recovery
# ==============================================================================
def test_10_tool_timeout_and_recovery():
    """Test 10: Subprocess timeout or deadline expiration is detected and handled with structured recovery."""
    run_id = f"test_run_timeout_{int(time.time()*1000)}"
    task_id = f"task_timeout_{int(time.time()*1000)}"

    # 10a. Deadline expiration in DriftController
    goal_tracker_service.initialize_task(
        run_id=run_id,
        task_id=task_id,
        original_request="Task with expired deadline",
        complexity_profile="simple",
        deadline_seconds=-1.0  # Already expired
    )

    decision = drift_controller_service.check_action(
        run_id=run_id,
        action_type="command_exec",
        target="pytest tests"
    )
    assert decision.allowed is False
    assert decision.violation_type == "deadline_exceeded"
    assert decision.action_category == "budget_exceeded"
    assert "deadline" in decision.reason.lower()

    # 10b. Subprocess timeout simulation in test runner
    run_id_sub = f"test_run_sub_{int(time.time()*1000)}"
    goal_tracker_service.initialize_task(
        run_id=run_id_sub,
        task_id="task_sub",
        original_request="Test runner subprocess timeout handling",
        complexity_profile="medium"
    )

    db_service.create_or_update_run(run_id_sub, 'task_sub', 'Timeout test', 'Timeout test', workspace_service.get_default_repo_path())
    # Mock subprocess.run to raise subprocess.TimeoutExpired
    with patch("subprocess.run", side_effect=__import__("subprocess").TimeoutExpired(cmd="pytest", timeout=25)):
        res = test_runner_service.run_tests(run_id=run_id_sub, attempt_number=1, test_file_target="tests/test_mock.py")
        assert res.exit_code == 124
        assert res.status == "ERROR"
        assert "exceeded" in res.execution_error.lower()

        # Result validation detects failure and signals bounded recovery
        val = drift_controller_service.validate_result(
            run_id=run_id_sub,
            action_type="test_run",
            target="pytest tests/test_mock.py",
            success=False,
            details={"exit_code": 1, "failed_tests": 1}
        )
        assert val.valid is False
        assert val.should_retry is True
        assert val.status == "test_failure"
