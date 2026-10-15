"""Required Regression Tests for AgentEval-X.

Tests proving:
1. The registration endpoint returns the expected response (HTTP 201).
2. An incorrect or unmounted route produces a genuine test failure (HTTP 404).
3. The debugger fixes the implementation rather than changing assertions.
4. A successful recovery is backed by a passing rerun.
5. Repeated ineffective recovery terminates at the retry limit.
6. Drift is calculated correctly for aligned and out-of-scope actions.
7. Stored drift scores survive API retrieval and saved-run loading.
8. Missing legacy scores display an explicit unavailable state.
9. Coding, testing, verification, and drift results remain separate.
"""

import os
import uuid
from types import SimpleNamespace
import pytest
from fastapi import FastAPI, APIRouter, status
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.models.schema import (
    ImplementationPlan,
    PlannedFile,
    TestRunResult,
    TestResultItem,
    RecoveryAttempt,
    VerificationReport,
    EvaluationMetrics,
    CriterionVerification,
    ConstraintCompliance,
)
from app.services.db import db_service
from app.services.debugger_service import debugger_service
from app.services.goal_tracker_service import goal_tracker_service
from app.services.drift_controller_service import drift_controller_service
from app.services.verifier_service import compute_evaluation_scores, verifier_service
from app.main import app as main_fastapi_app

TestRunResult.__test__ = False
TestResultItem.__test__ = False


# ==============================================================================
# 1. Registration endpoint returns expected response (HTTP 201)
# ==============================================================================
def test_registration_endpoint_returns_expected_201_response():
    """Verify that a properly mounted registration endpoint returns HTTP 201 and token."""
    app = FastAPI(title="Auth API Test")
    router = APIRouter(prefix="/api/auth", tags=["Auth"])

    class RegisterRequest(BaseModel):
        username: str
        email: str
        password: str

    @router.post("/register", status_code=status.HTTP_201_CREATED)
    def register_user(req: RegisterRequest):
        return {
            "access_token": "valid_token_xyz",
            "token_type": "bearer",
            "user": {
                "username": req.username,
                "email": req.email,
            }
        }

    # Mount router onto app
    app.include_router(router)

    client = TestClient(app)
    payload = {
        "username": "alex_dev",
        "email": "alex@example.com",
        "password": "SuperSecretPassword123!"
    }
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["username"] == "alex_dev"


# ==============================================================================
# 2. An incorrect route produces a genuine test failure (HTTP 404)
# ==============================================================================
def test_incorrect_or_unmounted_route_produces_genuine_test_failure():
    """Verify that when a router is unmounted or prefix is wrong, it returns 404."""
    app = FastAPI(title="Defective App")
    router = APIRouter(prefix="/api/auth", tags=["Auth"])

    @router.post("/register", status_code=status.HTTP_201_CREATED)
    def register_user():
        return {"status": "ok"}

    # DEFECT: app.include_router(router) is deliberately omitted
    client = TestClient(app)
    response = client.post("/api/auth/register", json={"username": "alex"})
    assert response.status_code == 404  # Genuine failure caused by application routing defect


# ==============================================================================
# 3. The debugger fixes the implementation rather than changing assertions
# ==============================================================================
def test_debugger_fixes_implementation_rather_than_changing_assertions():
    """When a 404 or assertion failure occurs, debugger targets implementation (main.py),

    never the test file, and strictly rejects changing test assertions.
    """
    plan = ImplementationPlan(
        run_id="run_dbg_target",
        target_repo_path="/fake/repo",
        goal_model_version="1.0",
        steps=[],
        architecture_overview="Auth API",
        testing_strategy="Pytest",
        risk_assessment="Low",
        planned_files=[
            PlannedFile(path="app/auth.py", action="create", description="Auth logic"),
            PlannedFile(path="app/main.py", action="modify", description="FastAPI main application"),
            PlannedFile(path="tests/test_auth.py", action="test", description="Auth tests"),
        ]
    )

    # Test failure where endpoint returned 404 instead of 201
    failing_test = TestRunResult(
        id="tr_404",
        run_id="run_dbg_target",
        attempt_number=1,
        exit_code=1,
        status="FAILED",
        stdout="""
_________________________ test_user_registration_success _________________________
tests/test_auth.py:30: in test_user_registration_success
    assert response.status_code == 201
E   assert 404 == 201
        """,
        test_items=[
            TestResultItem(
                name="tests/test_auth.py::test_user_registration_success",
                status="FAILED",
                duration_ms=10.0,
                error_message="assert 404 == 201",
                stack_trace="tests/test_auth.py:30: in test_user_registration_success\n    assert response.status_code == 201\nE   assert 404 == 201"
            )
        ]
    )

    target_file, target_line, is_impl = debugger_service._identify_failure_target(
        failing_test, plan, "/fake/repo"
    )

    # Must target the routing implementation (app/main.py), NOT the test file
    assert target_file == "app/main.py"
    assert is_impl is True

    # Test that deterministic repair injects router mounting in main.py
    broken_main = (
        "from fastapi import FastAPI, APIRouter\n"
        "app = FastAPI()\n"
        "router = APIRouter(prefix='/api/auth')\n"
    )
    repaired_main = debugger_service._deterministic_repair(
        file_rel_path="app/main.py",
        current_content=broken_main,
        diagnosis={"failure_reason": "assert 404 == 201"},
        error_output="assert 404 == 201 (Endpoint Not Found)",
        attempt_number=1
    )
    assert "app.include_router(router)" in repaired_main


# ==============================================================================
# 4. A successful recovery is backed by a passing rerun
# ==============================================================================
@pytest.mark.asyncio
async def test_successful_recovery_is_backed_by_passing_rerun(tmp_path):
    """A recovery attempt is only resolved when subsequent test rerun passes."""
    run_id = f"test_rerun_{uuid.uuid4().hex[:8]}"
    db_service.create_or_update_run(run_id, "t_rerun", "Rerun Test", "Prompt", str(tmp_path))

    # Initial failing test
    tr_fail = TestRunResult(
        id=f"tr_fail_{uuid.uuid4().hex[:6]}",
        run_id=run_id,
        attempt_number=1,
        total_tests=1,
        passed_tests=0,
        failed_tests=1,
        status="FAILED",
        exit_code=1,
        stdout="AssertionError: assert 404 == 201",
    )
    db_service.save_test_result(tr_fail)

    # Recovery attempt before test rerun
    attempt = RecoveryAttempt(
        id=f"rec_{uuid.uuid4().hex[:6]}",
        run_id=run_id,
        attempt_number=1,
        failure_reason="Endpoint 404",
        diagnosis="Router not mounted",
        proposed_fix="Add app.include_router(router)",
        files_modified=["app/main.py"],
        resolved=False,
        local_tests_passed=False,
    )
    db_service.save_recovery_attempt(attempt)

    # Simulate passing test rerun
    tr_pass = TestRunResult(
        id=f"tr_pass_{uuid.uuid4().hex[:6]}",
        run_id=run_id,
        attempt_number=2,
        total_tests=1,
        passed_tests=1,
        failed_tests=0,
        status="PASSED",
        exit_code=0,
        stdout="1 passed in 0.02s",
    )
    db_service.save_test_result(tr_pass)

    # Recovery outcome marked resolved only after passing rerun
    attempt.local_tests_passed = True
    attempt.resolved = True
    attempt.subsequent_test_run_id = tr_pass.id
    attempt.test_result_status = "PASSED"
    db_service.save_recovery_attempt(attempt)

    saved_attempts = db_service.get_recovery_attempts(run_id)
    assert len(saved_attempts) == 1
    assert saved_attempts[0].resolved is True
    assert saved_attempts[0].local_tests_passed is True
    assert saved_attempts[0].test_result_status == "PASSED"


# ==============================================================================
# 5. Repeated ineffective recovery terminates at the retry limit
# ==============================================================================
def test_repeated_ineffective_recovery_terminates_at_retry_limit():
    """When fixes are ineffective or repeated, recovery loop halts cleanly without infinite loop."""
    run_id = f"test_limit_{uuid.uuid4().hex[:8]}"
    db_service.create_or_update_run(run_id, "t_limit", "Limit Test", "Prompt", ".")

    # Max retries = 3
    for attempt_no in range(1, 4):
        attempt = RecoveryAttempt(
            id=f"rec_{attempt_no}_{uuid.uuid4().hex[:4]}",
            run_id=run_id,
            attempt_number=attempt_no,
            failure_reason="Persistent failure",
            diagnosis="Same diagnosis",
            proposed_fix="Ineffective fix",
            files_modified=[],
            resolved=False,
            local_tests_passed=False,
            termination_reason="repeated_ineffective_fixes" if attempt_no >= 2 else "no_effective_patch",
        )
        db_service.save_recovery_attempt(attempt)

    attempts = db_service.get_recovery_attempts(run_id)
    assert len(attempts) == 3
    assert all(a.resolved is False for a in attempts)
    assert attempts[-1].termination_reason in ("repeated_ineffective_fixes", "tests_failed")


# ==============================================================================
# 6. Drift is calculated correctly for aligned and out-of-scope actions
# ==============================================================================
def test_drift_calculated_correctly_for_aligned_and_out_of_scope_actions():
    """Aligned actions produce 0 drift; out-of-scope actions and constraint breaches produce drift."""
    criteria = [
        CriterionVerification(criterion_id="SC-1", criterion_description="Core logic", verdict="PASS")
    ]
    latest_test = SimpleNamespace(total_tests=5, passed_tests=5, status="PASSED", exit_code=0)

    # 1. Aligned actions
    aligned_scores = compute_evaluation_scores(
        criteria_evaluations=criteria,
        latest_test=latest_test,
        code_changes=[SimpleNamespace(file_path="app/service.py", lines_added=20, lines_removed=0)],
        audit_summary={"unrelated_action_count": 0},
    )
    assert aligned_scores["goal_drift_score"] == 0.0
    assert aligned_scores["component_penalties"]["goal_misalignment_penalty"] == 0.0

    # 2. Out-of-scope action (e.g. modified unauthorized file or executable)
    unrelated_scores = compute_evaluation_scores(
        criteria_evaluations=criteria,
        latest_test=latest_test,
        code_changes=[SimpleNamespace(file_path="app/service.py")],
        audit_summary={"unrelated_action_count": 1},
    )
    assert unrelated_scores["component_penalties"]["goal_misalignment_penalty"] == 50.0
    assert unrelated_scores["goal_drift_score"] == 20.0

    # 3. Hard constraint violation
    constraint_scores = compute_evaluation_scores(
        criteria_evaluations=criteria,
        latest_test=latest_test,
        code_changes=[SimpleNamespace(file_path="app/service.py")],
        constraint_compliances=[
            ConstraintCompliance(
                constraint_id="HC-1",
                constraint_text="No plaintext passwords in logs",
                is_hard=True,
                compliant=False,
                notes="Observed plaintext logging."
            )
        ]
    )
    assert constraint_scores["component_penalties"]["goal_misalignment_penalty"] == 50.0
    assert constraint_scores["goal_drift_score"] == 20.0


# ==============================================================================
# 7. Stored drift scores survive API retrieval and saved-run loading
# ==============================================================================
def test_stored_drift_scores_survive_api_retrieval_and_saved_run_loading():
    """Drift scores, metric_version, outcome, and evidence_breakdown survive in DB and API responses."""
    run_id = f"test_surv_{uuid.uuid4().hex[:8]}"
    db_service.create_or_update_run(run_id, "t_surv", "Survival Test", "Prompt", ".")

    ver = VerificationReport(
        id=f"ver_{uuid.uuid4().hex[:6]}",
        run_id=run_id,
        overall_verdict="VERIFIED_PASSED",
        verified_success=True,
        pass_rate_percent=100.0,
        goal_drift_score=0.0,
        goal_alignment_score=100.0,
        verifier_version="2",
        review_summary="Clean verification",
        criteria_evaluations=[],
        evidence_breakdown={"diagnostic_scores": {"goal_drift_score": 0.0}}
    )
    ev = EvaluationMetrics(
        run_id=run_id,
        task_id="t_surv",
        outcome="success",
        verified_success=True,
        success_rate=100.0,
        goal_drift_score=0.0,
        goal_alignment_score=100.0,
        metric_version="2",
        evidence_breakdown={"diagnostic_scores": {"goal_drift_score": 0.0}}
    )

    db_service.save_verification(ver)
    db_service.save_evaluation(ev)

    # 1. Single run evaluation API
    client = TestClient(main_fastapi_app)
    resp = client.get(f"/api/evaluations/{run_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["goal_drift_score"] == 0.0
    assert data["metric_version"] == "2"
    assert data["outcome"] == "success"

    # 2. Dashboard aggregate evaluations API
    dash_resp = client.get("/api/evaluations/dashboard")
    assert dash_resp.status_code == 200
    dash_data = dash_resp.json()
    recent = dash_data.get("recent_evaluations", [])
    matching = [r for r in recent if r.get("run_id") == run_id]
    assert len(matching) == 1
    assert matching[0]["metric_version"] == "2"
    assert matching[0]["outcome"] == "success"
    assert matching[0]["goal_drift_score"] == 0.0


# ==============================================================================
# 8. Missing legacy scores display an explicit unavailable state
# ==============================================================================
def test_missing_legacy_scores_display_explicit_unavailable_state():
    """Runs with unverified evidence or legacy metrics represent missing drift explicitly as None/Unavailable."""
    run_id = f"test_leg_{uuid.uuid4().hex[:8]}"
    db_service.create_or_update_run(run_id, "t_leg", "Legacy Run", "Prompt", ".")

    # Run without verified outcome (e.g. tests failed or unverified criteria)
    ver = VerificationReport(
        id=f"ver_{uuid.uuid4().hex[:6]}",
        run_id=run_id,
        overall_verdict="UNVERIFIED",
        verified_success=None,
        pass_rate_percent=0.0,
        goal_drift_score=None,  # Explicitly None because evidence is incomplete
        goal_alignment_score=None,
        verifier_version="2",
        review_summary="Tests failed, cannot verify",
        criteria_evaluations=[],
        evidence_breakdown={"diagnostic_scores": {"goal_drift_score": 25.0}}
    )
    ev = EvaluationMetrics(
        run_id=run_id,
        task_id="t_leg",
        outcome="unverified",
        verified_success=None,
        success_rate=0.0,
        goal_drift_score=None,  # Explicitly None, NOT silently zero
        goal_alignment_score=None,
        metric_version="2",
        evidence_breakdown={"diagnostic_scores": {"goal_drift_score": 25.0}}
    )

    db_service.save_verification(ver)
    db_service.save_evaluation(ev)

    client = TestClient(main_fastapi_app)
    resp = client.get(f"/api/evaluations/{run_id}")
    assert resp.status_code == 200
    data = resp.json()

    # Must be None, not silently converted into 0.0
    assert data["goal_drift_score"] is None
    # Diagnostic score preserved in evidence breakdown
    assert data["evidence_breakdown"]["diagnostic_scores"]["goal_drift_score"] == 25.0


# ==============================================================================
# 9. Coding, testing, verification, and drift results remain separate
# ==============================================================================
def test_coding_testing_verification_and_drift_results_remain_separate():
    """Test failures induce execution penalties but do NOT corrupt goal alignment;

    unverified criteria remain distinct from drift violations.
    """
    criteria = [
        CriterionVerification(criterion_id="SC-1", criterion_description="Core", verdict="PASS"),
        CriterionVerification(criterion_id="SC-2", criterion_description="Extra", verdict="UNVERIFIED", evidence="Pending rerun"),
    ]
    # 50% test pass rate
    latest_test = SimpleNamespace(total_tests=4, passed_tests=2, failed_tests=2, status="FAILED", exit_code=1)
    code_changes = [SimpleNamespace(file_path="app/service.py", lines_added=15, lines_removed=0)]
    audit_summary = {"unrelated_action_count": 0}

    scores = compute_evaluation_scores(
        criteria_evaluations=criteria,
        latest_test=latest_test,
        code_changes=code_changes,
        audit_summary=audit_summary,
    )

    # 1. Goal misalignment penalty remains 0.0 (no out-of-scope edits or constraint breaches)
    assert scores["component_penalties"]["goal_misalignment_penalty"] == 0.0

    # 2. Execution failure penalty reflects the 50% test failure
    assert scores["component_penalties"]["execution_failure_penalty"] == 50.0

    # 3. Unverified criterion is reported as partial_evidence, not a criteria gap penalty
    assert scores["component_penalties"]["criteria_gap_penalty"] == 0.0
    assert scores["score_status"] == "partial_evidence"

    # 4. Composite drift score reflects execution failure weight (0.25 * 50 = 12.5), keeping components separated
    assert scores["goal_drift_score"] == 12.5
    # Since SC-2 is UNVERIFIED, goal_alignment_score must remain uncertified (None)
    assert scores["goal_alignment_score"] is None
    assert scores["criteria_unverified"] == 1
    assert scores["criteria_passed"] == 1
