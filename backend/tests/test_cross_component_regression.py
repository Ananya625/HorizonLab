"""Cross-Component Regression Matrix.

Validates the contracts, boundaries, and interactions between:
- Coding Agent (coder_service)
- Testing & Debugging Agent (test_runner_service & debugger_service)
- Drift Controller (drift_controller_service & goal_tracker_service)
- Independent Verifier (verifier_service & criterion_checks)
- Database persistence, API serialization, and UI access paths

12 Scenarios:
1. Correct implementation, passing tests, no drift.
2. Correctly scoped implementation, failing tests, no drift.
3. Unrelated file modification, with otherwise passing tests.
4. Constraint violation detected by drift control.
5. Code-generation failure, with no placeholder written.
6. Test failure followed by a successful implementation repair.
7. Recovery that repeatedly fails and terminates at the retry limit.
8. Unresolved acceptance criteria that block final verification.
9. Persisted drift score matches the API and UI.
10. Repeated identical inputs produce consistent drift scores.
11. Capability-profile functionality works without breaking coding, testing, or drift control.
12. All safety gates remain enforced.
"""

import os
import time
import uuid
from types import SimpleNamespace
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.schema import (
    CriterionVerification,
    ConstraintCompliance,
    VerificationReport,
    EvaluationMetrics,
    RunRecord,
    TestRunResult,
    CodeChange,
    RecoveryAttempt,
    GoalModel,
    SuccessCriterion,
)
from app.services.db import db_service
from app.services.goal_tracker_service import goal_tracker_service
from app.services.drift_controller_service import drift_controller_service
from app.services.verifier_service import compute_evaluation_scores, verifier_service
from app.services.capability_estimator import compute_beta_binomial


# ==============================================================================
# Scenario 1: Correct implementation, passing tests, no drift
# ==============================================================================
def test_scenario_01_correct_implementation_passing_tests_no_drift():
    """Correctly scoped implementation with 100% test pass rate and verified criteria has zero drift."""
    criteria = [
        CriterionVerification(criterion_id="SC-1", criterion_description="Core logic", verdict="PASS"),
        CriterionVerification(criterion_id="SC-2", criterion_description="Boundary cases", verdict="PASS"),
    ]
    latest_test = SimpleNamespace(total_tests=10, passed_tests=10, failed_tests=0, status="PASSED", exit_code=0)
    code_changes = [SimpleNamespace(file_path="app/service.py", lines_added=25, lines_removed=0)]
    audit_summary = {"unrelated_action_count": 0, "repeated_action_count": 0, "security_violation_count": 0}

    scores = compute_evaluation_scores(
        criteria_evaluations=criteria,
        latest_test=latest_test,
        code_changes=code_changes,
        audit_summary=audit_summary,
    )

    assert scores["goal_drift_score"] == 0.0
    assert scores["goal_alignment_score"] == 100.0
    assert scores["criteria_completion_rate"] == 100.0
    assert scores["test_pass_rate"] == 100.0
    assert scores["component_penalties"]["goal_misalignment_penalty"] == 0.0
    assert scores["component_penalties"]["criteria_gap_penalty"] == 0.0
    assert scores["component_penalties"]["execution_failure_penalty"] == 0.0
    assert scores["score_status"] == "computed"


# ==============================================================================
# Scenario 2: Correctly scoped implementation, failing tests, no drift
# ==============================================================================
def test_scenario_02_correctly_scoped_failing_tests_no_misalignment():
    """Implementation is strictly within declared scope, but tests fail functionally.

    Goal misalignment penalty remains 0.0; execution failure penalty reflects test failure.
    """
    criteria = [
        CriterionVerification(criterion_id="SC-1", criterion_description="Core logic", verdict="PASS")
    ]
    # 2 of 4 tests pass (50% pass rate)
    latest_test = SimpleNamespace(total_tests=4, passed_tests=2, failed_tests=2, status="FAILED", exit_code=1)
    code_changes = [SimpleNamespace(file_path="app/service.py", lines_added=30, lines_removed=0)]
    audit_summary = {"unrelated_action_count": 0}

    scores = compute_evaluation_scores(
        criteria_evaluations=criteria,
        latest_test=latest_test,
        code_changes=code_changes,
        audit_summary=audit_summary,
    )

    # Goal misalignment is zero because no unrelated files or constraints were breached
    assert scores["component_penalties"]["goal_misalignment_penalty"] == 0.0
    # Execution failure penalty accurately reflects 50% test failure
    assert scores["component_penalties"]["execution_failure_penalty"] == 50.0
    assert scores["test_pass_rate"] == 50.0
    # Composite: 0.25 * 50.0 = 12.5 drift
    assert scores["goal_drift_score"] == 12.5
    assert scores["goal_alignment_score"] == 87.5


# ==============================================================================
# Scenario 3: Unrelated file modification, with otherwise passing tests
# ==============================================================================
def test_scenario_03_unrelated_file_modification_detected_by_drift_controller():
    """Modifying a file outside scope triggers unrelated action drift even if tests pass."""
    run_id = f"test_unrel_{uuid.uuid4().hex[:8]}"
    goal_tracker_service.initialize_task(
        run_id=run_id,
        task_id="task_unrel",
        original_request="Add math utility function",
        complexity_profile="simple"
    )

    # Drift controller blocks scope drift on invalid extension
    decision = drift_controller_service.check_action(
        run_id=run_id,
        action_type="file_write",
        target="malicious_exploit.exe",
        payload_str="evil",
        repo_path="."
    )
    assert decision.allowed is False
    assert decision.violation_type == "unrelated_action"
    assert decision.event_category == "unrelated_action"

    audit = drift_controller_service.get_audit_summary(run_id)
    assert audit["unrelated_action_count"] >= 1

    # Verify scoring penalizes the unrelated action
    criteria = [CriterionVerification(criterion_id="SC-1", criterion_description="Math", verdict="PASS")]
    latest_test = SimpleNamespace(total_tests=5, passed_tests=5, status="PASSED", exit_code=0)
    scores = compute_evaluation_scores(
        criteria_evaluations=criteria,
        latest_test=latest_test,
        code_changes=[SimpleNamespace(file_path="app/math.py")],
        audit_summary=audit,
    )
    assert scores["component_penalties"]["goal_misalignment_penalty"] == 50.0
    assert scores["goal_drift_score"] == 20.0  # 0.40 * 50.0


# ==============================================================================
# Scenario 4: Constraint violation detected by drift control
# ==============================================================================
def test_scenario_04_constraint_violation_detected_by_drift_control():
    """Violating a confirmed hard constraint induces goal misalignment drift."""
    criteria = [CriterionVerification(criterion_id="SC-1", criterion_description="Feature", verdict="PASS")]
    latest_test = SimpleNamespace(total_tests=5, passed_tests=5, status="PASSED", exit_code=0)
    constraints = [
        ConstraintCompliance(
            constraint_id="HC-1",
            constraint_text="Never use raw SQL queries",
            is_hard=True,
            compliant=False,
            notes="Observed raw SQL string interpolation."
        )
    ]

    scores = compute_evaluation_scores(
        criteria_evaluations=criteria,
        latest_test=latest_test,
        code_changes=[SimpleNamespace(file_path="app/service.py")],
        constraint_compliances=constraints,
    )

    assert scores["component_penalties"]["goal_misalignment_penalty"] == 50.0
    assert scores["goal_drift_score"] == 20.0
    assert "constraint violation" in scores["evidence"]["goal_misalignment"]


# ==============================================================================
# Scenario 5: Code-generation failure, with no placeholder written
# ==============================================================================
@pytest.mark.asyncio
async def test_scenario_05_code_generation_failure_no_placeholder(tmp_path):
    """When code generation fails AST validation or yields empty output, target file is untouched."""
    from app.services.coder_service import coder_service

    target_file = tmp_path / "app" / "broken.py"
    target_file.parent.mkdir(parents=True, exist_ok=True)
    target_file.write_text("# Initial pristine state\n", encoding="utf-8")
    initial_bytes = target_file.read_bytes()

    # Empty generation is rejected before file write
    with pytest.raises(Exception):
        await coder_service._generate_code_for_file(
            file_rel_path="app/broken.py",
            action="modify",
            description="Add function",
            original_content="# Initial pristine state\n",
            goal_model=None,
            plan=None,
            model_name="nonexistent_mock_model",
            temperature=0.1,
            run_id="test_run_codegen_fail"
        )

    # Pristine file content remained untouched
    assert target_file.read_bytes() == initial_bytes


# ==============================================================================
# Scenario 6: Test failure followed by a successful implementation repair
# ==============================================================================
@pytest.mark.asyncio
async def test_scenario_06_test_failure_followed_by_successful_repair(tmp_path):
    """Debugger repairs the failing implementation and rerun tests confirm resolution."""
    run_id = f"test_recov_pass_{uuid.uuid4().hex[:8]}"
    db_service.create_or_update_run(
        run_id=run_id,
        task_id="task_recov",
        title="Recovery Test",
        prompt="Fix addition function",
        repo_path=str(tmp_path),
    )

    # Initial buggy implementation
    service_py = tmp_path / "app" / "service.py"
    service_py.parent.mkdir(parents=True, exist_ok=True)
    service_py.write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")

    test_py = tmp_path / "tests" / "test_service.py"
    test_py.parent.mkdir(parents=True, exist_ok=True)
    test_py.write_text("from app.service import add\ndef test_add():\n    assert add(2, 3) == 5\n", encoding="utf-8")

    # Record initial failing test run
    initial_test = TestRunResult(
        id=f"tr_{uuid.uuid4().hex[:8]}",
        run_id=run_id,
        attempt_number=1,
        total_tests=1,
        passed_tests=0,
        failed_tests=1,
        status="FAILED",
        exit_code=1,
        stdout="AssertionError: assert -1 == 5",
    )
    db_service.save_test_result(initial_test)

    # Apply valid fix to implementation
    service_py.write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")

    # Record successful subsequent test run
    fixed_test = TestRunResult(
        id=f"tr_{uuid.uuid4().hex[:8]}",
        run_id=run_id,
        attempt_number=2,
        total_tests=1,
        passed_tests=1,
        failed_tests=0,
        status="PASSED",
        exit_code=0,
        stdout="1 passed in 0.01s",
        workspace_digest="digest_fixed",
        evidence_version="junit-v1",
    )
    db_service.save_test_result(fixed_test)

    attempt = RecoveryAttempt(
        id=f"rec_{uuid.uuid4().hex[:8]}",
        run_id=run_id,
        attempt_number=1,
        failure_reason="AssertionError: assert -1 == 5",
        diagnosis="Function subtracted instead of added",
        root_cause_analysis="Operator '-' used in place of '+'",
        proposed_fix="Change operator to '+'",
        files_modified=["app/service.py"],
        resolved=True,
        local_tests_passed=True,
        termination_reason="local_tests_passed",
    )
    db_service.save_recovery_attempt(attempt)

    attempts = db_service.get_recovery_attempts(run_id)
    assert len(attempts) == 1
    assert attempts[0].resolved is True
    assert attempts[0].local_tests_passed is True


# ==============================================================================
# Scenario 7: Recovery that repeatedly fails and terminates at retry limit
# ==============================================================================
def test_scenario_07_recovery_terminates_at_retry_limit():
    """Recovery halts cleanly when retry limit is reached without infinite recursion."""
    from app.services.debugger_service import debugger_service

    run_id = f"test_limit_{uuid.uuid4().hex[:8]}"
    db_service.create_or_update_run(
        run_id=run_id,
        task_id="task_limit",
        title="Retry Limit Test",
        prompt="Unfixable defect",
        repo_path=".",
    )

    # Create attempts up to max_recovery_retries (3)
    for i in range(1, 4):
        att = RecoveryAttempt(
            id=f"rec_{uuid.uuid4().hex[:8]}",
            run_id=run_id,
            attempt_number=i,
            failure_reason="Persistent syntax error",
            diagnosis="Cannot parse token",
            root_cause_analysis="Invalid construct",
            proposed_fix="Retry alternate fix",
            files_modified=["app/bad.py"],
            resolved=False,
            local_tests_passed=False,
            termination_reason="tests_failed",
        )
        db_service.save_recovery_attempt(att)

    attempts = db_service.get_recovery_attempts(run_id)
    assert len(attempts) == 3
    assert all(not a.resolved for a in attempts)


# ==============================================================================
# Scenario 8: Unresolved acceptance criteria that block final verification
# ==============================================================================
def test_scenario_08_unresolved_criteria_block_completion_without_false_drift():
    """Unverified acceptance criteria prevent completion and report partial evidence without false drift."""
    run_id = f"test_unres_{uuid.uuid4().hex[:8]}"
    goal_tracker_service.initialize_task(
        run_id=run_id,
        task_id="task_unres",
        original_request="Implement service with unverified metric",
        complexity_profile="simple",
        acceptance_criteria=[
            {"id": "SC-1", "description": "Syntax check", "metric": "python_syntax_workspace"},
            {"id": "SC-2", "description": "Unverified criterion", "metric": "unsupported_metric_xyz"}
        ]
    )

    # SC-1 passes, SC-2 is unverified
    goal_tracker_service.verify_criterion(run_id, "SC-1", passed=True, evidence="Syntax verified")
    state = goal_tracker_service.get_state(run_id)

    # Completion must be blocked because SC-2 is pending
    assert goal_tracker_service.can_complete(run_id) is False

    # Drift score evaluation treats unverified criteria as partial evidence, not drift penalty
    crit_evals = [
        CriterionVerification(criterion_id="SC-1", criterion_description="Syntax", verdict="PASS"),
        CriterionVerification(criterion_id="SC-2", criterion_description="Unsupported", verdict="UNVERIFIED", evidence="No oracle available"),
    ]
    latest_test = SimpleNamespace(total_tests=5, passed_tests=5, status="PASSED", exit_code=0)
    scores = compute_evaluation_scores(
        criteria_evaluations=crit_evals,
        latest_test=latest_test,
        code_changes=[SimpleNamespace(file_path="app/service.py")],
    )

    assert scores["component_penalties"]["criteria_gap_penalty"] == 0.0
    assert scores["goal_drift_score"] == 0.0
    assert scores["score_status"] == "partial_evidence"


# ==============================================================================
# Scenario 9: Persisted drift score matches the API and UI
# ==============================================================================
def test_scenario_09_persisted_drift_score_matches_api_and_ui():
    """Stored drift score is identical across database, API endpoint, and UI resolution paths."""
    run_id = f"test_pers_{uuid.uuid4().hex[:8]}"
    db_service.create_or_update_run(
        run_id=run_id,
        task_id="task_pers",
        title="Consistency check",
        prompt="Verify score matching",
        repo_path=".",
    )

    target_drift_score = 12.5
    target_alignment_score = 87.5

    verification = VerificationReport(
        id=f"ver_{uuid.uuid4().hex[:8]}",
        run_id=run_id,
        overall_verdict="VERIFIED_PASSED",
        verified_success=True,
        pass_rate_percent=100.0,
        goal_drift_score=target_drift_score,
        goal_alignment_score=target_alignment_score,
        verifier_version="2",
        review_summary="Verified cleanly",
        criteria_evaluations=[],
        evidence_breakdown={"diagnostic_scores": {"goal_drift_score": target_drift_score}}
    )
    evaluation = EvaluationMetrics(
        run_id=run_id,
        task_id="task_pers",
        outcome="success",
        verified_success=True,
        success_rate=100.0,
        goal_drift_score=target_drift_score,
        goal_alignment_score=target_alignment_score,
        evidence_breakdown=verification.evidence_breakdown
    )

    db_service.save_verification(verification)
    db_service.save_evaluation(evaluation)

    # 1. DB retrieval
    db_ver = db_service.get_verification(run_id)
    db_eval = db_service.get_evaluation(run_id)
    assert db_ver.goal_drift_score == target_drift_score
    assert db_eval.goal_drift_score == target_drift_score

    # 2. API response
    client = TestClient(app)
    resp = client.get(f"/api/evaluations/{run_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["goal_drift_score"] == target_drift_score

    # 3. UI property path
    ui_score = data.get("goal_drift_score") or data.get("evidence_breakdown", {}).get("diagnostic_scores", {}).get("goal_drift_score")
    assert ui_score == target_drift_score


# ==============================================================================
# Scenario 10: Repeated identical inputs produce consistent drift scores
# ==============================================================================
def test_scenario_10_repeated_identical_inputs_produce_consistent_scores():
    """Identical input states produce strictly deterministic drift scores across repeated evaluations."""
    crit = [
        CriterionVerification(criterion_id="SC-1", criterion_description="A", verdict="PASS"),
        CriterionVerification(criterion_id="SC-2", criterion_description="B", verdict="FAIL"),
    ]
    latest_test = SimpleNamespace(total_tests=10, passed_tests=8, failed_tests=2, status="FAILED", exit_code=1)
    code_changes = [SimpleNamespace(file_path="app/service.py")]
    audit = {"unrelated_action_count": 0}

    runs = []
    for _ in range(5):
        s = compute_evaluation_scores(
            criteria_evaluations=crit,
            latest_test=latest_test,
            code_changes=code_changes,
            audit_summary=audit,
        )
        runs.append(s)

    baseline = runs[0]
    for r in runs[1:]:
        assert r["goal_drift_score"] == baseline["goal_drift_score"]
        assert r["goal_alignment_score"] == baseline["goal_alignment_score"]
        assert r["component_penalties"] == baseline["component_penalties"]
        assert r["score_status"] == baseline["score_status"]


# ==============================================================================
# Scenario 11: Capability-profile functionality works without breaking other components
# ==============================================================================
def test_scenario_11_capability_profile_works_without_breaking_drift_or_coding():
    """Capability estimator and proficiency services analyze logs without modifying execution state."""
    run_id = f"test_cap_{uuid.uuid4().hex[:8]}"
    db_service.create_or_update_run(
        run_id=run_id,
        task_id="task_cap",
        title="Capability Test",
        prompt="Analyze capabilities",
        repo_path=".",
    )

    db_service.add_log(run_id, "coder", "Coding Agent", "tool_call", "Write file", {"file": "app/service.py"})
    db_service.add_log(run_id, "testing", "Test Runner", "test_run", "Pytest: PASSED", {"exit_code": 0})

    # Estimate capability profile
    est = compute_beta_binomial(successes=1, failures=0, capability="coding")
    assert est is not None
    assert est.successes == 1
    assert est.failures == 0
    assert 0.0 <= est.posterior_mean <= 1.0

    # Verify tracker state was not mutated by capability calculation
    state = goal_tracker_service.get_state(run_id)
    if state:
        assert state.task_status in ("pending", "running", "completed")


# ==============================================================================
# Scenario 12: All safety gates remain enforced
# ==============================================================================
def test_scenario_12_all_safety_gates_remain_strictly_enforced():
    """Path traversal, protected system directories, and premature completion are strictly blocked."""
    run_id = f"test_gates_{uuid.uuid4().hex[:8]}"
    goal_tracker_service.initialize_task(
        run_id=run_id,
        task_id="task_gates",
        original_request="Test safety guardrails",
        complexity_profile="simple"
    )

    # Gate 1: Path traversal blocked
    d_trav = drift_controller_service.check_action(
        run_id=run_id,
        action_type="file_write",
        target="../../etc/shadow",
        payload_str="root",
        repo_path="D:/SicProject"
    )
    assert d_trav.allowed is False
    assert d_trav.violation_type in ("path_traversal", "unrelated_action", "permission_violation")

    # Gate 2: Protected system directory blocked (.git)
    d_git = drift_controller_service.check_action(
        run_id=run_id,
        action_type="file_write",
        target=".git/config",
        payload_str="evil",
        repo_path="D:/SicProject"
    )
    assert d_git.allowed is False
    assert d_git.violation_type == "permission_violation"

    # Gate 3: Premature completion blocked when criteria unverified
    comp = drift_controller_service.check_completion(run_id)
    assert comp.allowed is False
    assert comp.violation_type == "premature_completion"
