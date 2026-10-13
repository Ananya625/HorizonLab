from datetime import datetime
from types import SimpleNamespace

import pytest


def make_goal():
    return SimpleNamespace(
        success_criteria=[
            SimpleNamespace(
                id="criterion-1",
                description="Requested behavior is implemented",
                metric="behavior",
            )
        ],
        hard_constraints=[],
        soft_constraints=[],
    )


@pytest.mark.asyncio
async def test_verifier_pass_percentage_uses_captured_test_counts(monkeypatch):
    from app.services import verifier_service as module

    run = SimpleNamespace(
        task_id="task-test",
        created_at="2000-01-01T00:00:00",
        logs=[],
    )
    test_result = SimpleNamespace(
        passed_tests=3,
        total_tests=4,
        status="FAILED",
        id="test-run-1",
    )
    saved = {}
    monkeypatch.setattr(module.db_service, "get_goal_model", lambda _: make_goal())
    monkeypatch.setattr(module.db_service, "get_plan", lambda _: None)
    monkeypatch.setattr(module.db_service, "get_code_changes", lambda _: [])
    monkeypatch.setattr(module.db_service, "get_test_results", lambda _: [test_result])
    monkeypatch.setattr(module.db_service, "get_recovery_attempts", lambda _: [])
    monkeypatch.setattr(module.db_service, "get_run_record", lambda _: run)
    monkeypatch.setattr(module.db_service, "save_verification", lambda report: report)
    monkeypatch.setattr(
        module.db_service,
        "save_evaluation",
        lambda metrics: saved.setdefault("evaluation", metrics),
    )
    monkeypatch.setattr(module.db_service, "add_log", lambda **_: None)
    monkeypatch.setattr(module.time, "perf_counter", lambda: 112.345)

    report = await module.verifier_service.verify_run(
        "run-test",
        execution_started_at=50.0,
    )

    assert report.pass_rate_percent == 75.0
    assert report.tests_passed == 3
    assert report.tests_total == 4
    assert report.goal_drift_score is None
    assert report.criteria_evaluations[0].verdict == "NOT_VERIFIED"
    assert report.criteria_evaluations[0].confidence_score is None
    assert saved["evaluation"].success_rate == 75.0
    assert saved["evaluation"].goal_drift_score is None
    assert saved["evaluation"].execution_time_seconds == 62.34


@pytest.mark.asyncio
async def test_verifier_does_not_create_a_percentage_without_test_counts(monkeypatch):
    from app.services import verifier_service as module

    run = SimpleNamespace(
        task_id="task-test",
        created_at=datetime.now().isoformat(),
        logs=[],
    )
    saved = {}
    monkeypatch.setattr(module.db_service, "get_goal_model", lambda _: make_goal())
    monkeypatch.setattr(module.db_service, "get_plan", lambda _: None)
    monkeypatch.setattr(module.db_service, "get_code_changes", lambda _: [])
    monkeypatch.setattr(module.db_service, "get_test_results", lambda _: [])
    monkeypatch.setattr(module.db_service, "get_recovery_attempts", lambda _: [])
    monkeypatch.setattr(module.db_service, "get_run_record", lambda _: run)
    monkeypatch.setattr(module.db_service, "save_verification", lambda report: report)
    monkeypatch.setattr(
        module.db_service,
        "save_evaluation",
        lambda metrics: saved.setdefault("evaluation", metrics),
    )
    monkeypatch.setattr(module.db_service, "add_log", lambda **_: None)

    report = await module.verifier_service.verify_run("run-no-tests")

    assert report.pass_rate_percent is None
    assert report.overall_verdict == "TESTS_NOT_RUN"
    assert saved["evaluation"].success_rate is None
