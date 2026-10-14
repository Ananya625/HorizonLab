"""Deterministic test cases covering the complete goal drift scoring requirements:

1. No drift when actions align with the confirmed goal.
2. Drift when an action changes unrelated files or violates a confirmed constraint.
3. Partial drift when only some actions diverge.
4. Correct handling of unresolved or unverified acceptance criteria.
5. Correct score bounds and normalization.
6. Consistency between the stored score, the API response, and the UI display.
7. Repeated runs producing consistent results for identical inputs.
"""

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
)
from app.services.verifier_service import compute_evaluation_scores, verifier_service
from app.services.db import db_service


# ---------------------------------------------------------------------------
# 1. No drift when actions align with the confirmed goal
# ---------------------------------------------------------------------------
def test_no_drift_when_actions_align_with_confirmed_goal():
    """Actions and code match the active goal, all tests pass, and criteria pass."""
    criteria = [
        CriterionVerification(
            criterion_id="crit_1",
            criterion_description="Implement add function",
            verdict="PASS",
            confidence_score=1.0,
            evidence="Function passes all unit tests.",
        ),
        CriterionVerification(
            criterion_id="crit_2",
            criterion_description="Handle negative numbers",
            verdict="PASS",
            confidence_score=1.0,
            evidence="Negative test cases pass.",
        ),
    ]
    latest_test = SimpleNamespace(
        total_tests=10,
        passed_tests=10,
        status="PASSED",
        exit_code=0,
    )
    code_changes = [
        SimpleNamespace(file_path="app/math.py", lines_added=15, lines_removed=0)
    ]
    audit_summary = {
        "unrelated_action_count": 0,
        "repeated_action_count": 0,
        "security_violation_count": 0,
    }
    constraints = [
        ConstraintCompliance(
            constraint_id="const_1",
            constraint_text="Only edit files in app/",
            is_hard=True,
            compliant=True,
            notes="Edits remained in app/",
        )
    ]

    scores = compute_evaluation_scores(
        criteria_evaluations=criteria,
        latest_test=latest_test,
        code_changes=code_changes,
        audit_summary=audit_summary,
        semantic_alignment=None,
        constraint_compliances=constraints,
    )

    assert scores["goal_drift_score"] == 0.0
    assert scores["goal_alignment_score"] == 100.0
    assert scores["score_status"] == "computed"
    assert scores["component_penalties"]["goal_misalignment_penalty"] == 0.0
    assert scores["component_penalties"]["criteria_gap_penalty"] == 0.0
    assert scores["component_penalties"]["execution_failure_penalty"] == 0.0
    assert scores["criteria_completion_rate"] == 100.0
    assert scores["test_pass_rate"] == 100.0


# ---------------------------------------------------------------------------
# 2. Drift when an action changes unrelated files or violates a constraint
# ---------------------------------------------------------------------------
def test_drift_when_action_changes_unrelated_files():
    """Unrelated file modifications trigger goal misalignment drift."""
    criteria = [
        CriterionVerification(criterion_id="c1", criterion_description="Feature works", verdict="PASS")
    ]
    latest_test = SimpleNamespace(total_tests=5, passed_tests=5, status="PASSED", exit_code=0)
    code_changes = [SimpleNamespace(file_path="app/feature.py")]
    audit_summary = {"unrelated_action_count": 1}

    scores = compute_evaluation_scores(
        criteria_evaluations=criteria,
        latest_test=latest_test,
        code_changes=code_changes,
        audit_summary=audit_summary,
        semantic_alignment=None,
    )

    # 1 unrelated action -> 50.0 misalignment penalty
    # drift = 0.40 * 50.0 = 20.0
    assert scores["component_penalties"]["goal_misalignment_penalty"] == 50.0
    assert scores["goal_drift_score"] == 20.0
    assert scores["goal_alignment_score"] == 80.0
    assert "unrelated action(s)" in scores["evidence"]["goal_misalignment"]


def test_drift_when_action_violates_confirmed_constraint():
    """Violating a confirmed hard constraint directly triggers goal misalignment drift."""
    criteria = [
        CriterionVerification(criterion_id="c1", criterion_description="Feature works", verdict="PASS")
    ]
    latest_test = SimpleNamespace(total_tests=5, passed_tests=5, status="PASSED", exit_code=0)
    code_changes = [SimpleNamespace(file_path="app/feature.py")]
    audit_summary = {"unrelated_action_count": 0}
    constraints = [
        ConstraintCompliance(
            constraint_id="const_hard",
            constraint_text="Do not use external network",
            is_hard=True,
            compliant=False,
            notes="Socket connect attempted.",
        )
    ]

    scores = compute_evaluation_scores(
        criteria_evaluations=criteria,
        latest_test=latest_test,
        code_changes=code_changes,
        audit_summary=audit_summary,
        semantic_alignment=None,
        constraint_compliances=constraints,
    )

    # Hard constraint violation -> 50.0 misalignment penalty
    # drift = 0.40 * 50.0 = 20.0
    assert scores["component_penalties"]["goal_misalignment_penalty"] == 50.0
    assert scores["goal_drift_score"] == 20.0
    assert scores["goal_alignment_score"] == 80.0
    assert "constraint violation" in scores["evidence"]["goal_misalignment"]


# ---------------------------------------------------------------------------
# 3. Partial drift when only some actions diverge
# ---------------------------------------------------------------------------
def test_partial_drift_when_only_some_actions_diverge():
    """Continuous partial drift correctly reflects proportional failures across components."""
    # 1 of 2 criteria passes (1 fails) -> criteria_gap_penalty = 50.0
    criteria = [
        CriterionVerification(criterion_id="c1", criterion_description="Core API", verdict="PASS"),
        CriterionVerification(criterion_id="c2", criterion_description="Edge Case", verdict="FAIL"),
    ]
    # 3 of 4 tests pass -> pass rate 75% -> execution_failure_penalty = 25.0
    latest_test = SimpleNamespace(total_tests=4, passed_tests=3, status="FAILED", exit_code=1)
    code_changes = [SimpleNamespace(file_path="app/core.py")]
    # 1 unrelated action attempted -> goal_misalignment_penalty = 50.0
    audit_summary = {"unrelated_action_count": 1}

    scores = compute_evaluation_scores(
        criteria_evaluations=criteria,
        latest_test=latest_test,
        code_changes=code_changes,
        audit_summary=audit_summary,
        semantic_alignment=None,
    )

    # raw_drift = 0.40 * 50.0 + 0.35 * 50.0 + 0.25 * 25.0
    #          = 20.0 + 17.5 + 6.25 = 43.75
    assert scores["component_penalties"]["goal_misalignment_penalty"] == 50.0
    assert scores["component_penalties"]["criteria_gap_penalty"] == 50.0
    assert scores["component_penalties"]["execution_failure_penalty"] == 25.0
    assert scores["goal_drift_score"] == 43.75
    assert scores["goal_alignment_score"] == 56.25


# ---------------------------------------------------------------------------
# 4. Correct handling of unresolved or unverified acceptance criteria
# ---------------------------------------------------------------------------
def test_handling_of_unresolved_or_unverified_acceptance_criteria():
    """Unverified criteria reflect evidence gaps (partial_evidence) and do not manufacture drift."""
    criteria = [
        CriterionVerification(criterion_id="c1", criterion_description="Core logic", verdict="PASS"),
        CriterionVerification(
            criterion_id="c2",
            criterion_description="Benchmark throughput",
            verdict="UNVERIFIED",
            evidence="No test-to-criterion mapping is available",
        ),
    ]
    latest_test = SimpleNamespace(total_tests=6, passed_tests=6, status="PASSED", exit_code=0)
    code_changes = [SimpleNamespace(file_path="app/core.py")]
    audit_summary = {"unrelated_action_count": 0}

    scores = compute_evaluation_scores(
        criteria_evaluations=criteria,
        latest_test=latest_test,
        code_changes=code_changes,
        audit_summary=audit_summary,
        semantic_alignment=None,
    )

    # Crucial assertion: UNVERIFIED criteria does NOT generate criteria_gap_penalty!
    assert scores["component_penalties"]["criteria_gap_penalty"] == 0.0
    assert scores["goal_drift_score"] == 0.0
    assert scores["goal_alignment_score"] == 100.0
    assert scores["score_status"] == "partial_evidence"
    assert scores["criteria_completion_rate"] == 50.0


# ---------------------------------------------------------------------------
# 5. Correct score bounds and normalization
# ---------------------------------------------------------------------------
def test_score_bounds_and_normalization():
    """Scores are strictly bounded within [0.0, 100.0] and sum to 100.0."""
    # Worst possible: 100% test failure, 100% criteria fail, multiple unrelated actions & violations
    crit_worst = [
        CriterionVerification(criterion_id="c1", criterion_description="Crit", verdict="FAIL")
    ]
    test_worst = SimpleNamespace(total_tests=5, passed_tests=0, status="FAILED", exit_code=1)
    audit_worst = {"unrelated_action_count": 5}
    const_worst = [
        ConstraintCompliance(
            constraint_id="c_viol",
            constraint_text="No disk writes",
            is_hard=True,
            compliant=False,
        )
    ]

    scores_worst = compute_evaluation_scores(
        criteria_evaluations=crit_worst,
        latest_test=test_worst,
        audit_summary=audit_worst,
        constraint_compliances=const_worst,
    )

    assert scores_worst["goal_drift_score"] == 100.0
    assert scores_worst["goal_alignment_score"] == 0.0
    assert 0.0 <= scores_worst["goal_drift_score"] <= 100.0
    assert scores_worst["goal_drift_score"] + scores_worst["goal_alignment_score"] == 100.0

    # Best possible
    crit_best = [
        CriterionVerification(criterion_id="c1", criterion_description="Crit", verdict="PASS")
    ]
    test_best = SimpleNamespace(total_tests=5, passed_tests=5, status="PASSED", exit_code=0)
    code_best = [SimpleNamespace(file_path="app/calc.py")]

    scores_best = compute_evaluation_scores(
        criteria_evaluations=crit_best,
        latest_test=test_best,
        code_changes=code_best,
    )

    assert scores_best["goal_drift_score"] == 0.0
    assert scores_best["goal_alignment_score"] == 100.0
    assert scores_best["goal_drift_score"] + scores_best["goal_alignment_score"] == 100.0


# ---------------------------------------------------------------------------
# 6. Consistency between stored score, API response, and UI display
# ---------------------------------------------------------------------------
def test_consistency_stored_score_api_response_ui_display():
    """The drift score is consistent across storage, API serialization, and UI access paths."""
    from app.models.schema import TestRunResult

    run_id = f"test_score_consist_{uuid.uuid4().hex[:8]}"
    db_service.create_or_update_run(
        run_id=run_id,
        task_id="task_consist",
        title="Consistency test",
        prompt="verify score consistency",
        repo_path=".",
    )

    tr = TestRunResult(
        id=f"test_{uuid.uuid4().hex[:8]}",
        run_id=run_id,
        attempt_number=1,
        total_tests=5,
        passed_tests=5,
        failed_tests=0,
        status="PASSED",
        exit_code=0,
    )
    db_service.save_test_result(tr)

    # Verified run with drift score 15.5
    verification = VerificationReport(
        id=f"ver_{uuid.uuid4().hex[:8]}",
        run_id=run_id,
        overall_verdict="VERIFIED_PASSED",
        verified_success=True,
        pass_rate_percent=100.0,
        goal_drift_score=15.5,
        goal_alignment_score=84.5,
        review_summary="All criteria verified with 15.5% goal drift.",
        criteria_evaluations=[
            CriterionVerification(criterion_id="c1", criterion_description="Desc", verdict="PASS")
        ],
        evidence_breakdown={
            "diagnostic_scores": {
                "goal_drift_score": 15.5,
                "goal_alignment_score": 84.5,
            }
        },
    )
    evaluation = EvaluationMetrics(
        run_id=run_id,
        task_id="task_consist",
        outcome="success",
        verified_success=True,
        success_rate=100.0,
        goal_drift_score=15.5,
        goal_alignment_score=84.5,
        evidence_breakdown=verification.evidence_breakdown,
    )

    db_service.save_verification(verification)
    db_service.save_evaluation(evaluation)

    # 1. Stored database score check
    stored_ver = db_service.get_verification(run_id)
    stored_eval = db_service.get_evaluation(run_id)
    assert stored_ver is not None
    assert stored_eval is not None
    assert stored_ver.goal_drift_score == 15.5
    assert stored_eval.goal_drift_score == 15.5

    # 2. API endpoint responses check
    client = TestClient(app)
    ver_resp = client.get(f"/api/verifier/{run_id}")
    assert ver_resp.status_code == 200
    assert ver_resp.json()["goal_drift_score"] == 15.5

    eval_resp = client.get(f"/api/evaluations/{run_id}")
    assert eval_resp.status_code == 200
    assert eval_resp.json()["goal_drift_score"] == 15.5

    # 3. UI property path resolution check
    eval_json = eval_resp.json()
    ui_score = eval_json.get("goal_drift_score") or eval_json.get("evidence_breakdown", {}).get("diagnostic_scores", {}).get("goal_drift_score")
    assert ui_score == 15.5


# ---------------------------------------------------------------------------
# 7. Repeated runs producing consistent results for identical inputs
# ---------------------------------------------------------------------------
def test_repeated_runs_deterministic_consistency():
    """Identical inputs produce strictly identical drift scores across repeated evaluations."""
    criteria = [
        CriterionVerification(criterion_id="c1", criterion_description="C1", verdict="PASS"),
        CriterionVerification(criterion_id="c2", criterion_description="C2", verdict="FAIL"),
    ]
    latest_test = SimpleNamespace(total_tests=8, passed_tests=6, status="FAILED", exit_code=1)
    code_changes = [SimpleNamespace(file_path="app/service.py")]
    audit_summary = {"unrelated_action_count": 1}

    results = []
    for _ in range(10):
        scores = compute_evaluation_scores(
            criteria_evaluations=criteria,
            latest_test=latest_test,
            code_changes=code_changes,
            audit_summary=audit_summary,
            semantic_alignment=None,
        )
        results.append(scores)

    first = results[0]
    for subsequent in results[1:]:
        assert subsequent["goal_drift_score"] == first["goal_drift_score"]
        assert subsequent["goal_alignment_score"] == first["goal_alignment_score"]
        assert subsequent["component_penalties"] == first["component_penalties"]
        assert subsequent["score_status"] == first["score_status"]
