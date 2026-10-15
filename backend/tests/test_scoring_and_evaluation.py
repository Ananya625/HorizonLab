import os
import sys
import time
import uuid
import pytest
from types import SimpleNamespace

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models.schema import (
    CriterionVerification,
    ConstraintCompliance,
    VerificationReport,
    EvaluationMetrics,
    GoalModel,
    SuccessCriterion,
    CodeChange,
    TestRunResult
)

TestRunResult.__test__ = False
from app.services.verifier_service import compute_evaluation_scores, verifier_service
from app.services.drift_controller_service import drift_controller_service
from app.services.goal_tracker_service import goal_tracker_service
from app.services.db import db_service


# ==============================================================================
# INDIVIDUAL COMPONENT UNIT TESTS
# ==============================================================================

def test_component_criteria_gap_penalty():
    """Unit test for Criteria Gap Penalty component isolation."""
    # 2/2 passed => 0 penalty, 100% completion
    crit_all_pass = [
        CriterionVerification(criterion_id="C1", criterion_description="Desc1", verdict="PASS"),
        CriterionVerification(criterion_id="C2", criterion_description="Desc2", verdict="PASS")
    ]
    res_pass = compute_evaluation_scores(crit_all_pass, latest_test=SimpleNamespace(total_tests=2, passed_tests=2, status="PASSED", exit_code=0), semantic_alignment="aligned")
    assert res_pass["component_penalties"]["criteria_gap_penalty"] == 0.0
    assert res_pass["criteria_completion_rate"] == 100.0

    # 1/2 passed => 50 penalty, 50% completion
    crit_half_pass = [
        CriterionVerification(criterion_id="C1", criterion_description="Desc1", verdict="PASS"),
        CriterionVerification(criterion_id="C2", criterion_description="Desc2", verdict="FAIL")
    ]
    res_half = compute_evaluation_scores(crit_half_pass, latest_test=SimpleNamespace(total_tests=2, passed_tests=2, status="PASSED", exit_code=0), semantic_alignment="aligned")
    assert res_half["component_penalties"]["criteria_gap_penalty"] == 50.0
    assert res_half["criteria_completion_rate"] == 50.0

    # 0 criteria => 100 penalty, 0% completion, status="missing_criteria"
    res_none = compute_evaluation_scores([], latest_test=SimpleNamespace(total_tests=2, passed_tests=2, status="PASSED", exit_code=0), semantic_alignment="aligned")
    assert res_none["component_penalties"]["criteria_gap_penalty"] == 100.0
    assert res_none["criteria_completion_rate"] == 0.0
    assert res_none["score_status"] == "missing_criteria"


def test_component_execution_failure_penalty():
    """Unit test for Execution Failure Penalty component isolation."""
    crit = [CriterionVerification(criterion_id="C1", criterion_description="Desc", verdict="PASS")]

    # 4/4 passed => 0 penalty, 100% pass rate
    t_pass = SimpleNamespace(total_tests=4, passed_tests=4, status="PASSED", exit_code=0)
    res_pass = compute_evaluation_scores(crit, latest_test=t_pass, semantic_alignment="aligned")
    assert res_pass["component_penalties"]["execution_failure_penalty"] == 0.0
    assert res_pass["test_pass_rate"] == 100.0

    # 2/4 passed => 50 penalty, 50% pass rate
    t_half = SimpleNamespace(total_tests=4, passed_tests=2, status="FAILED", exit_code=1)
    res_half = compute_evaluation_scores(crit, latest_test=t_half, semantic_alignment="aligned")
    assert res_half["component_penalties"]["execution_failure_penalty"] == 50.0
    assert res_half["test_pass_rate"] == 50.0

    # Unavailable test => 100 penalty, test_pass_rate is None, status="unavailable_tests"
    res_unavail = compute_evaluation_scores(crit, latest_test=None, semantic_alignment="aligned")
    assert res_unavail["component_penalties"]["execution_failure_penalty"] == 100.0
    assert res_unavail["test_pass_rate"] is None
    assert res_unavail["score_status"] == "unavailable_tests"


def test_component_goal_misalignment_penalty():
    """Unit test for Goal Misalignment Penalty component isolation."""
    crit = [CriterionVerification(criterion_id="C1", criterion_description="Desc", verdict="PASS")]
    t_pass = SimpleNamespace(total_tests=2, passed_tests=2, status="PASSED", exit_code=0)

    # Fully aligned, 0 unrelated actions => 0 penalty
    res_align = compute_evaluation_scores(crit, latest_test=t_pass, audit_summary={"unrelated_action_count": 0}, semantic_alignment="aligned")
    assert res_align["component_penalties"]["goal_misalignment_penalty"] == 0.0

    # 1 unrelated action => 50 penalty
    res_unrel = compute_evaluation_scores(crit, latest_test=t_pass, audit_summary={"unrelated_action_count": 1}, semantic_alignment="aligned")
    assert res_unrel["component_penalties"]["goal_misalignment_penalty"] == 50.0

    # Explicit unknown semantic alignment => 0 penalty (no manufactured drift), status="unknown_semantic", alignment=None
    res_unk = compute_evaluation_scores(crit, latest_test=t_pass, semantic_alignment="unknown")
    assert res_unk["component_penalties"]["goal_misalignment_penalty"] == 0.0
    assert res_unk["score_status"] == "unknown_semantic"
    assert res_unk["goal_drift_score"] == 0.0
    assert res_unk["goal_alignment_score"] is None


# ==============================================================================
# 14 SPECIFIC REGRESSION SCENARIOS
# ==============================================================================

def test_scenario_01_clean_successful_execution():
    """Scenario 1: Clean successful execution."""
    crit = [
        CriterionVerification(criterion_id="C1", criterion_description="Functional requirements met", verdict="PASS"),
        CriterionVerification(criterion_id="C2", criterion_description="Clean unit test execution", verdict="PASS")
    ]
    latest_test = SimpleNamespace(total_tests=10, passed_tests=10, status="PASSED", exit_code=0)
    code_changes = [SimpleNamespace(file_path="app/math.py", lines_added=20, lines_removed=0)]
    audit_summary = {"unrelated_action_count": 0, "security_violation_count": 0, "harmless_duplicate_skip_count": 0}

    scores = compute_evaluation_scores(
        criteria_evaluations=crit,
        latest_test=latest_test,
        code_changes=code_changes,
        audit_summary=audit_summary,
        semantic_alignment="aligned"
    )

    assert scores["goal_drift_score"] == 0.0
    assert scores["goal_alignment_score"] == 100.0
    assert scores["criteria_completion_rate"] == 100.0
    assert scores["test_pass_rate"] == 100.0
    assert scores["score_status"] == "computed"
    assert scores["component_penalties"]["goal_misalignment_penalty"] == 0.0
    assert scores["component_penalties"]["criteria_gap_penalty"] == 0.0
    assert scores["component_penalties"]["execution_failure_penalty"] == 0.0


def test_scenario_02_failed_tests_criteria_satisfied():
    """Scenario 2: Failed tests with all criteria otherwise satisfied."""
    crit = [
        CriterionVerification(criterion_id="C1", criterion_description="All business criteria satisfied", verdict="PASS")
    ]
    # 3 out of 6 tests passed => 50% pass rate
    latest_test = SimpleNamespace(total_tests=6, passed_tests=3, status="FAILED", exit_code=1)
    code_changes = [SimpleNamespace(file_path="app/service.py", lines_added=15, lines_removed=0)]
    audit_summary = {"unrelated_action_count": 0}

    scores = compute_evaluation_scores(
        criteria_evaluations=crit,
        latest_test=latest_test,
        code_changes=code_changes,
        audit_summary=audit_summary,
        semantic_alignment="aligned"
    )

    assert scores["criteria_completion_rate"] == 100.0
    assert scores["test_pass_rate"] == 50.0
    assert scores["component_penalties"]["criteria_gap_penalty"] == 0.0
    assert scores["component_penalties"]["execution_failure_penalty"] == 50.0
    assert scores["component_penalties"]["goal_misalignment_penalty"] == 0.0

    # goal_drift_score = 0.40*(0) + 0.35*(0) + 0.25*(50) = 12.5
    assert scores["goal_drift_score"] == 12.5
    assert scores["goal_alignment_score"] == 87.5
    assert scores["score_status"] == "computed"


def test_scenario_03_missing_acceptance_criteria():
    """Scenario 3: Missing acceptance criteria."""
    latest_test = SimpleNamespace(total_tests=5, passed_tests=5, status="PASSED", exit_code=0)
    code_changes = [SimpleNamespace(file_path="app/service.py", lines_added=10, lines_removed=0)]

    # Zero criteria defined
    scores = compute_evaluation_scores(
        criteria_evaluations=[],
        latest_test=latest_test,
        code_changes=code_changes,
        semantic_alignment="aligned"
    )

    assert scores["criteria_completion_rate"] == 0.0
    assert scores["component_penalties"]["criteria_gap_penalty"] == 100.0
    assert scores["score_status"] == "missing_criteria"
    # goal_drift_score = 0.40*(0) + 0.35*(100) + 0.25*(0) = 35.0
    assert scores["goal_drift_score"] == 35.0
    assert scores["goal_alignment_score"] == 65.0
    assert "Zero acceptance criteria" in scores["evidence"]["criteria_gap"]


def test_scenario_04_unavailable_test_results():
    """Scenario 4: Unavailable test results."""
    crit = [CriterionVerification(criterion_id="C1", criterion_description="Code written", verdict="PASS")]
    code_changes = [SimpleNamespace(file_path="app/service.py", lines_added=10, lines_removed=0)]

    # Test runner results unavailable (None)
    scores = compute_evaluation_scores(
        criteria_evaluations=crit,
        latest_test=None,
        code_changes=code_changes,
        semantic_alignment="aligned"
    )

    assert scores["test_pass_rate"] is None
    assert scores["component_penalties"]["execution_failure_penalty"] == 100.0
    assert scores["score_status"] == "unavailable_tests"
    # goal_drift_score = 0.40*(0) + 0.35*(0) + 0.25*(100) = 25.0
    assert scores["goal_drift_score"] == 25.0
    assert scores["goal_alignment_score"] == 75.0
    assert "unavailable" in scores["evidence"]["execution_failure"].lower()


def test_scenario_05_harmless_duplicate_edit_skipped_with_recovery():
    """Scenario 5: Harmless duplicate edit skipped, followed by successful recovery."""
    run_id = f"test_run_dup_{uuid.uuid4().hex[:8]}"
    goal_tracker_service.initialize_task(
        run_id=run_id,
        task_id="task_dup",
        original_request="Implement function",
        complexity_profile="simple"
    )

    # 1. First file write: allowed
    d1 = drift_controller_service.check_action(
        run_id=run_id,
        action_type="file_write",
        target="app/calc.py",
        payload_str="def add(a, b): return a + b\n"
    )
    assert d1.allowed is True

    # 2. Duplicate file write with identical content: skipped harmlessly
    d2 = drift_controller_service.check_action(
        run_id=run_id,
        action_type="file_write",
        target="app/calc.py",
        payload_str="def add(a, b): return a + b\n"
    )
    assert d2.allowed is False
    assert d2.event_category == "harmless_duplicate_skip"
    assert d2.action_category == "duplicate_skipped"

    # 3. Targeted recovery edit with updated content: allowed
    d3 = drift_controller_service.check_action(
        run_id=run_id,
        action_type="file_write",
        target="app/calc.py",
        payload_str="def add(a, b): return a + b # recovered\n"
    )
    assert d3.allowed is True

    audit = drift_controller_service.get_audit_summary(run_id)
    assert audit["harmless_duplicate_skip_count"] == 1
    assert audit["unrelated_action_count"] == 0
    assert audit["security_violation_count"] == 0

    # Ensure harmless duplicate skips do NOT increase drift score
    crit = [CriterionVerification(criterion_id="C1", criterion_description="Criteria", verdict="PASS")]
    latest_test = SimpleNamespace(total_tests=2, passed_tests=2, status="PASSED", exit_code=0)
    scores = compute_evaluation_scores(
        criteria_evaluations=crit,
        latest_test=latest_test,
        code_changes=[SimpleNamespace(file_path="app/calc.py")],
        audit_summary=audit,
        semantic_alignment="aligned"
    )
    assert scores["goal_drift_score"] == 0.0
    assert scores["goal_alignment_score"] == 100.0


def test_scenario_06_repeated_actions_without_progress():
    """Scenario 6: Repeated actions without progress."""
    run_id = f"test_run_rep_{uuid.uuid4().hex[:8]}"
    goal_tracker_service.initialize_task(
        run_id=run_id,
        task_id="task_rep",
        original_request="Run tests",
        complexity_profile="simple"
    )

    cmd = "pytest tests/test_calc.py"
    # Action 1: allowed
    d1 = drift_controller_service.check_action(run_id=run_id, action_type="command_exec", target=cmd)
    assert d1.allowed is True

    # Action 2: allowed (simple profile allows up to 2 identical actions)
    d2 = drift_controller_service.check_action(run_id=run_id, action_type="command_exec", target=cmd)
    assert d2.allowed is True

    # Action 3: repeated action limit exceeded without workspace changes -> blocked
    d3 = drift_controller_service.check_action(run_id=run_id, action_type="command_exec", target=cmd)
    assert d3.allowed is False
    assert d3.event_category == "repeated_action"

    audit = drift_controller_service.get_audit_summary(run_id)
    assert audit["repeated_action_count"] >= 1


def test_scenario_07_unrelated_action_blocked():
    """Scenario 7: Unrelated action blocked."""
    run_id = f"test_run_unrel_{uuid.uuid4().hex[:8]}"
    goal_tracker_service.initialize_task(
        run_id=run_id,
        task_id="task_unrel",
        original_request="Create user service",
        complexity_profile="simple"
    )

    # Attempt to write invalid binary/script unrelated to task
    decision = drift_controller_service.check_action(
        run_id=run_id,
        action_type="file_write",
        target="malicious_miner.exe",
        payload_str="binary data"
    )
    assert decision.allowed is False
    assert decision.event_category == "unrelated_action"

    audit = drift_controller_service.get_audit_summary(run_id)
    assert audit["unrelated_action_count"] == 1

    crit = [CriterionVerification(criterion_id="C1", criterion_description="Criterion", verdict="PASS")]
    latest_test = SimpleNamespace(total_tests=2, passed_tests=2, status="PASSED", exit_code=0)
    scores = compute_evaluation_scores(
        criteria_evaluations=crit,
        latest_test=latest_test,
        code_changes=[SimpleNamespace(file_path="app/user.py")],
        audit_summary=audit,
        semantic_alignment=None
    )
    # 1 unrelated action => 50 misalignment penalty
    assert scores["component_penalties"]["goal_misalignment_penalty"] == 50.0
    # drift = 0.40 * 50 + 0 + 0 = 20.0
    assert scores["goal_drift_score"] == 20.0
    assert scores["goal_alignment_score"] == 80.0


def test_scenario_08_security_violation_blocked():
    """Scenario 8: Security violation blocked, policy enforced without polluting drift score."""
    run_id = f"test_run_sec_{uuid.uuid4().hex[:8]}"
    sandbox_dir = "d:/SicProject/backend"

    goal_tracker_service.initialize_task(
        run_id=run_id,
        task_id="task_sec",
        original_request="Implement secure token helper",
        complexity_profile="simple"
    )

    # Attempt path traversal escaping repository
    decision = drift_controller_service.check_action(
        run_id=run_id,
        action_type="file_write",
        target="../../Windows/System32/config.sys",
        payload_str="corrupt",
        repo_path=sandbox_dir
    )
    assert decision.allowed is False
    assert decision.event_category == "security_violation"

    audit = drift_controller_service.get_audit_summary(run_id)
    assert audit["security_violation_count"] == 1
    assert audit["unrelated_action_count"] == 0

    # The agent adheres to security policy inside sandbox; code satisfies all criteria
    crit = [CriterionVerification(criterion_id="C1", criterion_description="Pass criteria", verdict="PASS")]
    latest_test = SimpleNamespace(total_tests=4, passed_tests=4, status="PASSED", exit_code=0)
    scores = compute_evaluation_scores(
        criteria_evaluations=crit,
        latest_test=latest_test,
        code_changes=[SimpleNamespace(file_path="app/token.py")],
        audit_summary=audit,
        semantic_alignment="aligned"
    )
    # Security violation does NOT falsely inflate goal drift score
    assert scores["goal_drift_score"] == 0.0
    assert scores["goal_alignment_score"] == 100.0


def test_scenario_09_deduplication_of_repeated_failure_logs():
    """Scenario 9: Same underlying failure appearing in multiple logs is deduplicated."""
    run_id = f"test_run_dedup_{uuid.uuid4().hex[:8]}"

    # Simulate 3 repeated log occurrences of identical security violation across retries
    drift_controller_service._log_drift_event(
        run_id=run_id,
        violation_type="path_traversal",
        reason="Path escapes sandbox",
        action_type="file_write",
        target="../../etc/shadow",
        event_category="security_violation"
    )
    drift_controller_service._log_drift_event(
        run_id=run_id,
        violation_type="path_traversal",
        reason="Retry 1: Path escapes sandbox",
        action_type="file_write",
        target="../../etc/shadow",
        event_category="security_violation"
    )
    drift_controller_service._log_drift_event(
        run_id=run_id,
        violation_type="path_traversal",
        reason="Retry 2: Path escapes sandbox",
        action_type="file_write",
        target="../../etc/shadow",
        event_category="security_violation"
    )

    audit = drift_controller_service.get_audit_summary(run_id)
    # Total raw events is 3, but deduplicated security violation count must be 1
    assert audit["total_events"] == 3
    assert audit["security_violation_count"] == 1


def test_scenario_10_explicit_user_approved_goal_revision():
    """Scenario 10: Explicit user-approved goal revision preserves history and does not increase drift."""
    run_id = f"test_run_rev_{uuid.uuid4().hex[:8]}"
    initial_goal = "Implement bubble_sort(items)"

    state = goal_tracker_service.initialize_task(
        run_id=run_id,
        task_id="task_rev",
        original_request=initial_goal,
        complexity_profile="simple"
    )
    assert state.original_user_request == initial_goal
    assert state.current_goal == initial_goal
    assert len(state.revision_history) == 0

    # User explicitly changes the goal to quicksort
    revised_goal = "Change requirement: Implement quick_sort(items)"
    updated_state = goal_tracker_service.revise_goal(
        run_id=run_id,
        new_goal_text=revised_goal,
        change_reason="User requested O(n log n) sorting algorithm"
    )
    assert updated_state.original_user_request == initial_goal
    assert updated_state.current_goal == revised_goal
    assert len(updated_state.revision_history) == 1
    assert updated_state.revision_history[0].previous_goal == initial_goal
    assert updated_state.revision_history[0].revised_goal == revised_goal

    # Code aligned with the revised goal produces 0 drift
    crit = [CriterionVerification(criterion_id="C1", criterion_description="quicksort working", verdict="PASS")]
    latest_test = SimpleNamespace(total_tests=5, passed_tests=5, status="PASSED", exit_code=0)
    scores = compute_evaluation_scores(
        criteria_evaluations=crit,
        latest_test=latest_test,
        code_changes=[SimpleNamespace(file_path="app/sort.py")],
        audit_summary={"unrelated_action_count": 0},
        semantic_alignment="aligned"
    )
    assert scores["goal_drift_score"] == 0.0
    assert scores["goal_alignment_score"] == 100.0


def test_scenario_11_concurrent_runs_isolated_scores():
    """Scenario 11: Two concurrent runs with separate isolated scores."""
    run_a = f"run_concurrent_A_{uuid.uuid4().hex[:8]}"
    run_b = f"run_concurrent_B_{uuid.uuid4().hex[:8]}"

    goal_tracker_service.initialize_task(run_id=run_a, task_id="task_a", original_request="Task A")
    goal_tracker_service.initialize_task(run_id=run_b, task_id="task_b", original_request="Task B")

    # Run A has clean success
    crit_a = [CriterionVerification(criterion_id="CA", criterion_description="Crit A", verdict="PASS")]
    test_a = SimpleNamespace(total_tests=4, passed_tests=4, status="PASSED", exit_code=0)
    scores_a = compute_evaluation_scores(crit_a, latest_test=test_a, semantic_alignment="aligned")

    # Run B has test failure (2 of 4 passed)
    crit_b = [CriterionVerification(criterion_id="CB", criterion_description="Crit B", verdict="PASS")]
    test_b = SimpleNamespace(total_tests=4, passed_tests=2, status="FAILED", exit_code=1)
    scores_b = compute_evaluation_scores(crit_b, latest_test=test_b, semantic_alignment="aligned")

    assert scores_a["goal_drift_score"] == 0.0
    assert scores_a["goal_alignment_score"] == 100.0

    assert scores_b["goal_drift_score"] == 12.5  # 0.25 * 50.0
    assert scores_b["goal_alignment_score"] == 87.5

    # State isolation check
    state_a = goal_tracker_service.get_state(run_a)
    state_b = goal_tracker_service.get_state(run_b)
    assert state_a.task_id == "task_a"
    assert state_b.task_id == "task_b"


def test_scenario_12_passing_tests_unmet_criterion():
    """Scenario 12: A passing test suite that does not satisfy a required criterion."""
    # Automated pytest passed 100%, but 1 of 2 criteria is unmet (e.g., benchmark or documentation)
    crit = [
        CriterionVerification(criterion_id="C1", criterion_description="Tests pass", verdict="PASS"),
        CriterionVerification(criterion_id="C2", criterion_description="Latency under 5ms", verdict="FAIL")
    ]
    latest_test = SimpleNamespace(total_tests=10, passed_tests=10, status="PASSED", exit_code=0)

    scores = compute_evaluation_scores(
        criteria_evaluations=crit,
        latest_test=latest_test,
        code_changes=[SimpleNamespace(file_path="app/perf.py")],
        semantic_alignment="aligned"
    )

    assert scores["test_pass_rate"] == 100.0
    assert scores["criteria_completion_rate"] == 50.0
    assert scores["component_penalties"]["execution_failure_penalty"] == 0.0
    assert scores["component_penalties"]["criteria_gap_penalty"] == 50.0

    # goal_drift_score = 0.40*(0) + 0.35*(50.0) + 0.25*(0) = 17.5
    assert scores["goal_drift_score"] == 17.5
    assert scores["goal_alignment_score"] == 82.5
    assert scores["score_status"] == "computed"


def test_scenario_13_unknown_semantic_alignment():
    """Scenario 13: Unknown semantic alignment without manufacturing precision."""
    crit = [CriterionVerification(criterion_id="C1", criterion_description="Crit", verdict="PASS")]
    latest_test = SimpleNamespace(total_tests=2, passed_tests=2, status="PASSED", exit_code=0)

    # Neither code changes nor audit summary provided, semantic_alignment="unknown"
    scores = compute_evaluation_scores(
        criteria_evaluations=crit,
        latest_test=latest_test,
        code_changes=[],
        audit_summary={},
        semantic_alignment="unknown"
    )

    assert scores["score_status"] == "unknown_semantic"
    assert scores["component_penalties"]["goal_misalignment_penalty"] == 0.0
    assert "unavailable" in scores["evidence"]["goal_misalignment"] or "cannot be determined reliably" in scores["evidence"]["goal_misalignment"]
    # goal_drift_score = 0.40*(0.0) + 0.35*(0) + 0.25*(0) = 0.0 (no false drift)
    assert scores["goal_drift_score"] == 0.0
    # goal_alignment_score cannot be certified 100 or 80 when semantic evidence is missing
    assert scores["goal_alignment_score"] is None


def test_scenario_14_score_boundaries_and_normalization():
    """Scenario 14: Score boundaries and normalization."""
    # Case A: Worst-case failure across all components
    crit_worst = [CriterionVerification(criterion_id="C1", criterion_description="Crit", verdict="FAIL")]
    test_worst = SimpleNamespace(total_tests=5, passed_tests=0, status="FAILED", exit_code=1)
    scores_worst = compute_evaluation_scores(
        criteria_evaluations=crit_worst,
        latest_test=test_worst,
        semantic_alignment="misaligned"
    )
    assert scores_worst["component_penalties"]["goal_misalignment_penalty"] == 100.0
    assert scores_worst["component_penalties"]["criteria_gap_penalty"] == 100.0
    assert scores_worst["component_penalties"]["execution_failure_penalty"] == 100.0
    # 0.40*100 + 0.35*100 + 0.25*100 = 100.0
    assert scores_worst["goal_drift_score"] == 100.0
    assert scores_worst["goal_alignment_score"] == 0.0

    # Case B: Best-case across all components
    crit_best = [CriterionVerification(criterion_id="C1", criterion_description="Crit", verdict="PASS")]
    test_best = SimpleNamespace(total_tests=5, passed_tests=5, status="PASSED", exit_code=0)
    scores_best = compute_evaluation_scores(
        criteria_evaluations=crit_best,
        latest_test=test_best,
        code_changes=[SimpleNamespace(file_path="app.py")],
        semantic_alignment="aligned"
    )
    assert scores_best["goal_drift_score"] == 0.0
    assert scores_best["goal_alignment_score"] == 100.0

    # Case C: Boundary clamping verification
    assert 0.0 <= scores_worst["goal_drift_score"] <= 100.0
    assert 0.0 <= scores_best["goal_drift_score"] <= 100.0
    assert 0.0 <= scores_worst["goal_alignment_score"] <= 100.0
    assert 0.0 <= scores_best["goal_alignment_score"] <= 100.0


@pytest.mark.asyncio
async def test_verifier_service_and_db_persistence_e2e():
    """Verify end-to-end verifier run execution and SQLite persistence."""
    run_id = f"test_e2e_ver_{uuid.uuid4().hex[:8]}"
    task_id = "task_e2e"

    db_service.create_or_update_run(
        run_id=run_id,
        task_id=task_id,
        title="Test E2E Verification",
        prompt="Implement robust helper",
        repo_path="d:/SicProject/backend"
    )

    gm = GoalModel(
        task_id=task_id,
        run_id=run_id,
        original_request="Implement robust helper",
        normalized_request="Implement robust helper",
        main_goal="Implement robust helper",
        summary="Implement robust helper",
        success_criteria=[
            SuccessCriterion(id="SC-1", description="Criterion 1", metric="PASS")
        ]
    )
    db_service.save_goal_model(gm)

    # Save a passing test result
    tr = TestRunResult(
        id=f"test_{uuid.uuid4().hex[:8]}",
        run_id=run_id,
        attempt_number=1,
        total_tests=5,
        passed_tests=5,
        failed_tests=0,
        status="PASSED",
        exit_code=0
    )
    db_service.save_test_result(tr)

    # Save code change
    cc = CodeChange(
        id=f"cc_{uuid.uuid4().hex[:8]}",
        run_id=run_id,
        file_path="app/helper.py",
        action="created",
        new_content="def helper(): pass\n",
        diff_patch="+def helper(): pass\n",
        lines_added=10,
        lines_removed=0
    )
    db_service.save_code_change(cc)

    # Execute verify_run
    report = await verifier_service.verify_run(run_id=run_id)

    # Legacy passing counts cannot independently verify arbitrary requirements.
    assert report.goal_drift_score is None
    assert report.goal_alignment_score is None
    assert report.verified_success is None
    assert report.overall_verdict == "UNVERIFIED"
    assert report.criteria_completion_rate == 0.0
    assert report.score_status == "partial_evidence"
    assert report.score_version == "v2.0"
    assert "diagnostic_scores" in report.evidence_breakdown

    saved_report = db_service.get_verification(run_id)
    assert saved_report.model_dump() == report.model_dump()
    saved_eval = db_service.get_evaluation(run_id)
    assert saved_eval.goal_drift_score is None
    assert saved_eval.verified_success is None
    assert saved_eval.score_status == "partial_evidence"
    assert saved_eval.evidence_breakdown == report.evidence_breakdown
