import os
import uuid
import pytest
from types import SimpleNamespace
from pathlib import Path

from app.models.schema import (
    GoalModel,
    SubGoal,
    SuccessCriterion,
    TestRunResult,
    CriterionVerification,
    ConstraintCompliance,
    CodeChange,
)
from app.services.verifier_service import verifier_service, compute_evaluation_scores
from app.services.workspace_service import workspace_service
from app.services.test_runner_service import test_runner_service
from app.services.workflow_service import workflow


# ==============================================================================
# TASK 2: ACCEPTANCE-CRITERIA ACCOUNTING TESTS
# ==============================================================================

def test_criteria_accounting_all_passing():
    """All criteria passing must report 100% completion, 100% coverage, and 0 gap penalty."""
    criteria = [
        CriterionVerification(criterion_id=f"c{i}", criterion_description=f"Criterion {i}", verdict="PASS")
        for i in range(4)
    ]
    latest_test = SimpleNamespace(total_tests=5, passed_tests=5, failed_tests=0, status="PASSED", exit_code=0)

    scores = compute_evaluation_scores(
        criteria_evaluations=criteria,
        latest_test=latest_test,
        semantic_alignment="aligned",
    )

    assert scores["criteria_passed"] == 4
    assert scores["criteria_failed"] == 0
    assert scores["criteria_unverified"] == 0
    assert scores["criteria_total"] == 4
    assert scores["criteria_completion_rate"] == 100.0
    assert scores["evidence_coverage_percent"] == 100.0
    assert scores["component_penalties"]["criteria_gap_penalty"] == 0.0
    assert scores["goal_drift_score"] == 0.0
    assert scores["goal_alignment_score"] == 100.0
    assert scores["score_status"] == "computed"


def test_criteria_accounting_all_failing():
    """All criteria failing must report 0% completion, 100% coverage, and 100.0 gap penalty."""
    criteria = [
        CriterionVerification(criterion_id=f"c{i}", criterion_description=f"Criterion {i}", verdict="FAIL")
        for i in range(4)
    ]
    latest_test = SimpleNamespace(total_tests=5, passed_tests=5, failed_tests=0, status="PASSED", exit_code=0)

    scores = compute_evaluation_scores(
        criteria_evaluations=criteria,
        latest_test=latest_test,
        semantic_alignment="aligned",
    )

    assert scores["criteria_passed"] == 0
    assert scores["criteria_failed"] == 4
    assert scores["criteria_unverified"] == 0
    assert scores["criteria_total"] == 4
    assert scores["criteria_completion_rate"] == 0.0
    assert scores["evidence_coverage_percent"] == 100.0
    assert scores["component_penalties"]["criteria_gap_penalty"] == 100.0
    # Drift = 0.40*(0) + 0.35*(100) + 0.25*(0) = 35.0
    assert scores["goal_drift_score"] == 35.0
    assert scores["goal_alignment_score"] == 65.0
    assert scores["score_status"] == "computed"


def test_criteria_accounting_mixed_pass_and_fail():
    """Mixed pass and fail criteria must report exact split counts and proportional gap penalty."""
    criteria = [
        CriterionVerification(criterion_id="c1", criterion_description="Criterion 1", verdict="PASS"),
        CriterionVerification(criterion_id="c2", criterion_description="Criterion 2", verdict="PASS"),
        CriterionVerification(criterion_id="c3", criterion_description="Criterion 3", verdict="FAIL"),
        CriterionVerification(criterion_id="c4", criterion_description="Criterion 4", verdict="FAIL"),
    ]
    latest_test = SimpleNamespace(total_tests=5, passed_tests=5, failed_tests=0, status="PASSED", exit_code=0)

    scores = compute_evaluation_scores(
        criteria_evaluations=criteria,
        latest_test=latest_test,
        semantic_alignment="aligned",
    )

    assert scores["criteria_passed"] == 2
    assert scores["criteria_failed"] == 2
    assert scores["criteria_unverified"] == 0
    assert scores["criteria_total"] == 4
    assert scores["criteria_completion_rate"] == 50.0
    assert scores["evidence_coverage_percent"] == 100.0
    assert scores["component_penalties"]["criteria_gap_penalty"] == 50.0
    # Drift = 0.40*(0) + 0.35*(50) + 0.25*(0) = 17.5
    assert scores["goal_drift_score"] == 17.5
    assert scores["goal_alignment_score"] == 82.5
    assert scores["score_status"] == "computed"


def test_criteria_accounting_one_pass_three_unverified():
    """One pass and three unverified criteria must report partial evidence, 25% coverage, and uncertified alignment."""
    criteria = [
        CriterionVerification(criterion_id="c1", criterion_description="Criterion 1", verdict="PASS"),
        CriterionVerification(criterion_id="c2", criterion_description="Criterion 2", verdict="UNVERIFIED"),
        CriterionVerification(criterion_id="c3", criterion_description="Criterion 3", verdict="NOT_VERIFIED"),
        CriterionVerification(criterion_id="c4", criterion_description="Criterion 4", verdict="UNVERIFIED"),
    ]
    latest_test = SimpleNamespace(total_tests=5, passed_tests=5, failed_tests=0, status="PASSED", exit_code=0)

    scores = compute_evaluation_scores(
        criteria_evaluations=criteria,
        latest_test=latest_test,
        semantic_alignment="aligned",
    )

    assert scores["criteria_passed"] == 1
    assert scores["criteria_failed"] == 0
    assert scores["criteria_unverified"] == 3
    assert scores["criteria_total"] == 4
    assert scores["criteria_completion_rate"] == 25.0
    assert scores["evidence_coverage_percent"] == 25.0
    # Unverified criteria must NOT generate criteria_gap_penalty
    assert scores["component_penalties"]["criteria_gap_penalty"] == 0.0
    assert scores["goal_drift_score"] == 0.0
    # Unverified criteria must NOT produce a certified 100% or 80% alignment score
    assert scores["goal_alignment_score"] is None
    assert scores["score_status"] == "partial_evidence"


def test_criteria_accounting_all_criteria_unverified():
    """All criteria unverified must report 0% completion, 0% coverage, and uncertified alignment."""
    criteria = [
        CriterionVerification(criterion_id=f"c{i}", criterion_description=f"Criterion {i}", verdict="UNVERIFIED")
        for i in range(4)
    ]
    latest_test = SimpleNamespace(total_tests=5, passed_tests=5, failed_tests=0, status="PASSED", exit_code=0)

    scores = compute_evaluation_scores(
        criteria_evaluations=criteria,
        latest_test=latest_test,
        semantic_alignment="aligned",
    )

    assert scores["criteria_passed"] == 0
    assert scores["criteria_failed"] == 0
    assert scores["criteria_unverified"] == 4
    assert scores["criteria_total"] == 4
    assert scores["criteria_completion_rate"] == 0.0
    assert scores["evidence_coverage_percent"] == 0.0
    assert scores["component_penalties"]["criteria_gap_penalty"] == 0.0
    assert scores["goal_drift_score"] == 0.0
    assert scores["goal_alignment_score"] is None
    assert scores["score_status"] == "partial_evidence"


def test_criteria_accounting_empty_criteria_list():
    """Empty criteria list must incur full criteria gap penalty and status 'missing_criteria'."""
    scores = compute_evaluation_scores(
        criteria_evaluations=[],
        latest_test=SimpleNamespace(total_tests=5, passed_tests=5, failed_tests=0, status="PASSED", exit_code=0),
        semantic_alignment="aligned",
    )

    assert scores["criteria_passed"] == 0
    assert scores["criteria_failed"] == 0
    assert scores["criteria_unverified"] == 0
    assert scores["criteria_total"] == 0
    assert scores["criteria_completion_rate"] == 0.0
    assert scores["evidence_coverage_percent"] == 0.0
    assert scores["component_penalties"]["criteria_gap_penalty"] == 100.0
    assert scores["score_status"] == "missing_criteria"
    # Drift = 0.40*(0) + 0.35*(100) + 0.25*(0) = 35.0
    assert scores["goal_drift_score"] == 35.0
    assert scores["goal_alignment_score"] == 65.0


def test_criteria_accounting_unexpected_criterion_verdict():
    """Invalid or unexpected verdicts (e.g., 'MAYBE', 'INCONCLUSIVE', '', 'UNKNOWN_STATE') must count as unverified."""
    criteria = [
        CriterionVerification(criterion_id="c1", criterion_description="C1", verdict="PASS"),
        CriterionVerification(criterion_id="c2", criterion_description="C2", verdict="UNKNOWN_STATE"),
        CriterionVerification(criterion_id="c3", criterion_description="C3", verdict=""),
        CriterionVerification(criterion_id="c4", criterion_description="C4", verdict="inconclusive"),
    ]
    latest_test = SimpleNamespace(total_tests=5, passed_tests=5, failed_tests=0, status="PASSED", exit_code=0)

    scores = compute_evaluation_scores(
        criteria_evaluations=criteria,
        latest_test=latest_test,
        semantic_alignment="aligned",
    )

    assert scores["criteria_passed"] == 1
    assert scores["criteria_failed"] == 0
    assert scores["criteria_unverified"] == 3
    assert scores["criteria_total"] == 4
    assert scores["criteria_completion_rate"] == 25.0
    assert scores["evidence_coverage_percent"] == 25.0
    assert scores["goal_alignment_score"] is None
    assert scores["score_status"] == "partial_evidence"


def test_criteria_accounting_missing_test_evidence():
    """Missing test results when tests are required must set score_status to unavailable_tests and penalize execution."""
    criteria = [
        CriterionVerification(criterion_id="c1", criterion_description="C1", verdict="PASS")
    ]
    scores = compute_evaluation_scores(
        criteria_evaluations=criteria,
        latest_test=None,
        semantic_alignment="aligned",
    )

    assert scores["component_penalties"]["execution_failure_penalty"] == 100.0
    assert scores["score_status"] == "unavailable_tests"
    assert scores["goal_drift_score"] == 25.0  # 0.25 * 100
    assert scores["goal_alignment_score"] == 75.0


@pytest.mark.asyncio
async def test_criteria_accounting_stale_test_evidence(database, run):
    """Stale test evidence must cause verify_run to return UNVERIFIED, not false VERIFIED_PASSED."""
    repo = Path(run.repo_path)
    (repo / "app.py").write_text("def run(): return 42\n", encoding="utf-8")

    goal = GoalModel(
        task_id="t1",
        run_id="r1",
        original_request="Test stale evidence",
        normalized_request="Test stale evidence",
        main_goal="Test stale evidence",
        summary="Test stale evidence",
        is_confirmed=True,
        success_criteria=[
            SuccessCriterion(
                id="c1",
                description="Syntax valid",
                metric="python_syntax",
                verification_method="ast_check",
                expected_output="app.py",
            )
        ],
    )
    database.save_goal_model(goal)

    # Save a test run with a mismatched/stale digest
    old_test = TestRunResult(
        id=f"test_{uuid.uuid4().hex[:8]}",
        run_id="r1",
        attempt_number=1,
        total_tests=3,
        passed_tests=3,
        failed_tests=0,
        status="PASSED",
        exit_code=0,
        evidence_version="junit-v1",
        workspace_digest="stale_digest_value_that_does_not_match",
    )
    database.save_test_result(old_test)

    report = await verifier_service.verify_run("r1")

    assert report.overall_verdict == "UNVERIFIED"
    assert report.verified_success is None
    assert "test evidence stale" in report.review_summary


# ==============================================================================
# TASK 3: EVIDENCE-FRESHNESS VERIFICATION TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_freshness_source_file_modified_after_testing(database, run):
    """Running tests successfully then modifying a source file before verification must invalidate freshness."""
    repo = Path(run.repo_path)
    src_file = repo / "app.py"
    src_file.write_text("x = 10\n", encoding="utf-8")

    # Record digest when tests ran
    pre_test_digest = workspace_service.digest(str(repo))

    goal = GoalModel(
        task_id="t1",
        run_id="r1",
        original_request="Freshness test",
        normalized_request="Freshness test",
        main_goal="Freshness test",
        summary="Freshness test",
        is_confirmed=True,
        goal_model_version="v1",
        success_criteria=[
            SuccessCriterion(
                id="c1",
                description="Syntax valid",
                metric="python_syntax",
                verification_method="ast_check",
                expected_output="app.py",
            )
        ],
    )
    database.save_goal_model(goal)

    # Test result records the pre_test_digest
    test_result = TestRunResult(
        id=f"test_{uuid.uuid4().hex[:8]}",
        run_id="r1",
        attempt_number=1,
        total_tests=4,
        passed_tests=4,
        failed_tests=0,
        status="PASSED",
        exit_code=0,
        evidence_version="junit-v1",
        workspace_digest=pre_test_digest,
        goal_model_version="v1",
    )
    database.save_test_result(test_result)

    # Modify source file AFTER testing
    src_file.write_text("x = 20  # Modified after testing!\n", encoding="utf-8")
    post_edit_digest = workspace_service.digest(str(repo))
    assert pre_test_digest != post_edit_digest

    report = await verifier_service.verify_run("r1")

    # Overall verdict must be UNVERIFIED due to stale test evidence
    assert report.overall_verdict == "UNVERIFIED"
    assert report.verified_success is None
    assert "workspace changed since testing" in report.review_summary


@pytest.mark.asyncio
async def test_freshness_test_file_modified_after_testing(database, run):
    """Running tests successfully then modifying a test file before verification must invalidate freshness."""
    repo = Path(run.repo_path)
    (repo / "app.py").write_text("def add(a, b): return a + b\n", encoding="utf-8")
    test_file = repo / "test_app.py"
    test_file.write_text("def test_add(): assert True\n", encoding="utf-8")

    pre_test_digest = workspace_service.digest(str(repo))

    goal = GoalModel(
        task_id="t1",
        run_id="r1",
        original_request="Test file freshness",
        normalized_request="Test file freshness",
        main_goal="Test file freshness",
        summary="Test file freshness",
        is_confirmed=True,
        goal_model_version="v1",
        success_criteria=[
            SuccessCriterion(
                id="c1",
                description="Syntax valid",
                metric="python_syntax",
                verification_method="ast_check",
                expected_output="app.py",
            )
        ],
    )
    database.save_goal_model(goal)

    test_result = TestRunResult(
        id=f"test_{uuid.uuid4().hex[:8]}",
        run_id="r1",
        attempt_number=1,
        total_tests=1,
        passed_tests=1,
        failed_tests=0,
        status="PASSED",
        exit_code=0,
        evidence_version="junit-v1",
        workspace_digest=pre_test_digest,
        goal_model_version="v1",
    )
    database.save_test_result(test_result)

    # Modify test file AFTER testing
    test_file.write_text("def test_add(): assert 1 + 1 == 2\n", encoding="utf-8")
    assert pre_test_digest != workspace_service.digest(str(repo))

    report = await verifier_service.verify_run("r1")

    assert report.overall_verdict == "UNVERIFIED"
    assert report.verified_success is None
    assert "workspace changed since testing" in report.review_summary


@pytest.mark.asyncio
async def test_freshness_file_modified_while_tests_are_running(database, run, monkeypatch):
    """Modifying a workspace file while tests are running must produce execution_error and reject verification."""
    repo = Path(run.repo_path)
    (repo / "app.py").write_text("x = 1\n", encoding="utf-8")
    (repo / "test_app.py").write_text("def test_pass(): assert True\n", encoding="utf-8")

    goal = GoalModel(
        task_id="t1",
        run_id="r1",
        original_request="In-flight modification",
        normalized_request="In-flight modification",
        main_goal="In-flight modification",
        summary="In-flight modification",
        is_confirmed=True,
        goal_model_version="v1",
        success_criteria=[
            SuccessCriterion(
                id="c1",
                description="Syntax valid",
                metric="python_syntax",
                verification_method="ast_check",
                expected_output="app.py",
            )
        ],
    )
    database.save_goal_model(goal)

    # Simulate in-flight file modification during subprocess run
    import subprocess
    original_run = subprocess.run

    def mock_subprocess_run(*args, **kwargs):
        # Mutate the file while tests are executing
        (repo / "app.py").write_text("x = 999  # In-flight edit!\n", encoding="utf-8")
        return original_run(*args, **kwargs)

    monkeypatch.setattr("app.services.test_runner_service.subprocess.run", mock_subprocess_run)

    # Run tests via test_runner_service (it retrieves repo_path from run record)
    result = test_runner_service.run_tests("r1", attempt_number=1, target_test_files=["test_app.py"])

    assert result.status == "ERROR"
    assert "Workspace changed during test execution" in (result.execution_error or "")

    # Now verify run - must NOT produce VERIFIED_PASSED
    report = await verifier_service.verify_run("r1")
    assert report.overall_verdict == "UNVERIFIED"
    assert report.verified_success is None


@pytest.mark.asyncio
async def test_freshness_goal_model_changed_after_test_execution(database, run):
    """Changing the goal model version after test execution must invalidate test evidence freshness."""
    repo = Path(run.repo_path)
    (repo / "app.py").write_text("x = 1\n", encoding="utf-8")
    current_digest = workspace_service.digest(str(repo))

    # Tests ran under goal model version v1
    test_result = TestRunResult(
        id=f"test_{uuid.uuid4().hex[:8]}",
        run_id="r1",
        attempt_number=1,
        total_tests=3,
        passed_tests=3,
        failed_tests=0,
        status="PASSED",
        exit_code=0,
        evidence_version="junit-v1",
        workspace_digest=current_digest,
        goal_model_version="v1",
    )
    database.save_test_result(test_result)

    # Goal model is updated to version v2
    goal_v2 = GoalModel(
        task_id="t1",
        run_id="r1",
        original_request="Revised requirements",
        normalized_request="Revised requirements",
        main_goal="Revised requirements",
        summary="Revised requirements",
        is_confirmed=True,
        goal_model_version="v2",  # Updated!
        success_criteria=[
            SuccessCriterion(
                id="c1",
                description="Syntax valid",
                metric="python_syntax",
                verification_method="ast_check",
                expected_output="app.py",
            )
        ],
    )
    database.save_goal_model(goal_v2)

    report = await verifier_service.verify_run("r1")

    # Mismatch between test_goal_version and current goal_version invalidates freshness
    assert report.overall_verdict == "UNVERIFIED"
    assert report.verified_success is None
    assert "goal model updated since testing" in report.review_summary


@pytest.mark.asyncio
async def test_freshness_missing_or_malformed_digest_evidence(database, run):
    """Test result with missing or empty workspace_digest must never produce VERIFIED_PASSED."""
    repo = Path(run.repo_path)
    (repo / "app.py").write_text("x = 1\n", encoding="utf-8")

    goal = GoalModel(
        task_id="t1",
        run_id="r1",
        original_request="Malformed digest test",
        normalized_request="Malformed digest test",
        main_goal="Malformed digest test",
        summary="Malformed digest test",
        is_confirmed=True,
        goal_model_version="v1",
        success_criteria=[
            SuccessCriterion(
                id="c1",
                description="Syntax valid",
                metric="python_syntax",
                verification_method="ast_check",
                expected_output="app.py",
            )
        ],
    )
    database.save_goal_model(goal)

    # Missing workspace_digest
    bad_test = TestRunResult(
        id=f"test_{uuid.uuid4().hex[:8]}",
        run_id="r1",
        attempt_number=1,
        total_tests=2,
        passed_tests=2,
        failed_tests=0,
        status="PASSED",
        exit_code=0,
        evidence_version="junit-v1",
        workspace_digest=None,
        goal_model_version="v1",
    )
    database.save_test_result(bad_test)

    report = await verifier_service.verify_run("r1")
    assert report.overall_verdict == "UNVERIFIED"
    assert report.verified_success is None


@pytest.mark.asyncio
async def test_freshness_stale_test_result_from_previous_attempt(database, run):
    """Attempt 2 with modifications must not be validated by attempt 1's passing test."""
    repo = Path(run.repo_path)
    src_file = repo / "app.py"
    src_file.write_text("version = 1\n", encoding="utf-8")

    attempt1_digest = workspace_service.digest(str(repo))

    goal = GoalModel(
        task_id="t1",
        run_id="r1",
        original_request="Multi-attempt test",
        normalized_request="Multi-attempt test",
        main_goal="Multi-attempt test",
        summary="Multi-attempt test",
        is_confirmed=True,
        goal_model_version="v1",
        success_criteria=[
            SuccessCriterion(
                id="c1",
                description="Syntax valid",
                metric="python_syntax",
                verification_method="ast_check",
                expected_output="app.py",
            )
        ],
    )
    database.save_goal_model(goal)

    # Attempt 1 passing test
    test_att1 = TestRunResult(
        id=f"test_att1_{uuid.uuid4().hex[:8]}",
        run_id="r1",
        attempt_number=1,
        total_tests=3,
        passed_tests=3,
        failed_tests=0,
        status="PASSED",
        exit_code=0,
        evidence_version="junit-v1",
        workspace_digest=attempt1_digest,
        goal_model_version="v1",
    )
    database.save_test_result(test_att1)

    # Attempt 2 code change
    src_file.write_text("version = 2\n", encoding="utf-8")
    assert attempt1_digest != workspace_service.digest(str(repo))

    # Verification run without a fresh test run
    report = await verifier_service.verify_run("r1")

    assert report.overall_verdict == "UNVERIFIED"
    assert report.verified_success is None
    # Historical test record is preserved intact in database
    history = database.get_test_results("r1")
    assert len(history) == 1
    assert history[0].id == test_att1.id


@pytest.mark.asyncio
async def test_freshness_current_passing_test_result_verifies_valid_run(database, run):
    """A fresh passing test result matching workspace digest and goal version verifies a valid run."""
    repo = Path(run.repo_path)
    (repo / "app.py").write_text("def solve(): return True\n", encoding="utf-8")
    current_digest = workspace_service.digest(str(repo))

    goal = GoalModel(
        task_id="t1",
        run_id="r1",
        original_request="Valid run verification",
        normalized_request="Valid run verification",
        main_goal="Valid run verification",
        summary="Valid run verification",
        is_confirmed=True,
        goal_model_version="v1",
        success_criteria=[
            SuccessCriterion(
                id="c1",
                description="Syntax valid",
                metric="python_syntax",
                verification_method="ast_check",
                expected_output="app.py",
            )
        ],
    )
    database.save_goal_model(goal)

    fresh_test = TestRunResult(
        id=f"test_fresh_{uuid.uuid4().hex[:8]}",
        run_id="r1",
        attempt_number=1,
        total_tests=5,
        passed_tests=5,
        failed_tests=0,
        status="PASSED",
        exit_code=0,
        evidence_version="junit-v1",
        workspace_digest=current_digest,
        goal_model_version="v1",
    )
    database.save_test_result(fresh_test)

    report = await verifier_service.verify_run("r1")

    assert report.overall_verdict == "VERIFIED_PASSED"
    assert report.verified_success is True
    assert report.criteria_passed == 1
    assert report.criteria_failed == 0
    assert report.criteria_unverified == 0
    assert report.evidence_coverage_percent == 100.0
