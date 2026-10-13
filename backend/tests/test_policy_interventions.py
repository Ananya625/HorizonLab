import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest


@pytest.fixture
def policy_services(tmp_path, monkeypatch):
    from app.services import orchestrator_service as orchestrator_module
    from app.services.db import DatabaseService
    from app.services.feature_analytics_service import FeatureAnalyticsService

    db_path = str(tmp_path / "policy_interventions.db")
    database = DatabaseService(db_path)
    analytics = FeatureAnalyticsService()
    analytics.db_path = db_path
    analytics._apply_migrations()
    monkeypatch.setattr(orchestrator_module, "db_service", database)
    monkeypatch.setattr(orchestrator_module, "feature_analytics_service", analytics)

    run_id = "run_policy_test"
    database.create_or_update_run(
        run_id=run_id,
        task_id="task_policy_test",
        title="Policy test",
        prompt="Exercise runtime policy",
        repo_path=str(tmp_path),
        current_stage="testing",
        status="in_progress",
    )
    return orchestrator_module.OrchestratorService(), database, analytics, run_id


def make_policy_state(analytics, run_id, action, stage="testing", details=None):
    state = analytics.record_stage(
        run_id=run_id,
        stage=stage,
        success=False,
        model_name="policy-test-model",
        event_type="test_failed",
        details=details or {"attempt_number": 1},
    )
    state["risk_action"] = action
    with analytics._connect() as conn:
        conn.execute(
            "UPDATE prediction_log SET risk_action=? WHERE run_id=? AND step_index=?",
            (action, run_id, state["_step_index"]),
        )
    return state


@pytest.mark.asyncio
async def test_continue_is_recorded_without_marking_an_intervention(policy_services):
    orchestrator, _, analytics, run_id = policy_services
    state = make_policy_state(analytics, run_id, "continue")

    result = await orchestrator._handle_policy_action(run_id, state)
    with analytics._connect() as conn:
        prediction = conn.execute(
            """SELECT executed_action, execution_status, intervention_triggered
               FROM prediction_log WHERE run_id=? AND step_index=?""",
            (run_id, state["_step_index"]),
        ).fetchone()

    assert result["stop"] is False
    assert prediction["executed_action"] == "continue"
    assert prediction["execution_status"] == "executed"
    assert prediction["intervention_triggered"] == 0


@pytest.mark.asyncio
async def test_stop_action_is_persisted_and_stops_run(policy_services):
    orchestrator, database, analytics, run_id = policy_services
    state = make_policy_state(analytics, run_id, "stop")

    result = await orchestrator._handle_policy_action(run_id, state)
    record = orchestrator._stop_policy_run(run_id, "testing", "policy_stop")
    analytics_result = analytics.get_run_analytics(run_id)["failure_prediction"]

    assert result["stop"] is True
    assert record.status == "policy_stopped"
    assert analytics_result["recommended_action"] == "stop"
    assert analytics_result["executed_action"] == "stop"
    assert analytics_result["execution_outcome"]["mutations_halted"] is True
    assert database.get_execution_logs(run_id)[-1].stage == "stopped"


@pytest.mark.asyncio
async def test_switch_strategy_queues_alternate_recovery(policy_services):
    orchestrator, _, analytics, run_id = policy_services
    state = make_policy_state(analytics, run_id, "switch_strategy")

    result = await orchestrator._handle_policy_action(run_id, state, max_retry_budget=2)
    prediction = analytics.get_run_analytics(run_id)["failure_prediction"]

    assert result["strategy_override"] == "alternative_strategy"
    assert result["strategy_step_index"] == state["_step_index"]
    assert prediction["recommended_action"] == "switch_strategy"
    assert prediction["executed_action"] == "switch_strategy"
    assert prediction["execution_status"] == "queued"
    assert prediction["execution_outcome"]["verified"] is False


@pytest.mark.asyncio
async def test_inspection_blocks_invalid_ast_changes(policy_services, monkeypatch):
    orchestrator, database, analytics, run_id = policy_services
    state = make_policy_state(analytics, run_id, "inspect")
    monkeypatch.setattr(
        database,
        "get_code_changes",
        lambda _: [SimpleNamespace(file_path="broken.py", ast_valid=False)],
    )

    result = await orchestrator._handle_policy_action(run_id, state)

    assert result["stop"] is True
    prediction = analytics.get_run_analytics(run_id)["failure_prediction"]
    assert prediction["executed_action"] == "inspect"
    assert prediction["execution_outcome"]["invalid_ast_files"] == ["broken.py"]


@pytest.mark.asyncio
@pytest.mark.parametrize(("approved", "expected_stop"), [(True, False), (False, True)])
async def test_human_approval_pauses_and_resolves_run(
    policy_services, approved, expected_stop
):
    orchestrator, database, analytics, run_id = policy_services
    state = make_policy_state(analytics, run_id, "ask_human")
    task = asyncio.create_task(orchestrator._handle_policy_action(run_id, state))

    approval = None
    for _ in range(100):
        approval = analytics.get_pending_policy_approval(run_id)
        if approval:
            break
        await asyncio.sleep(0.01)

    assert approval is not None
    assert database.get_run_record(run_id).status == "awaiting_approval"
    resolved = analytics.resolve_policy_approval(
        run_id, approval["approval_id"], approved, "test approval"
    )
    assert resolved["status"] == ("approved" if approved else "rejected")

    result = await asyncio.wait_for(task, timeout=1)
    assert result["stop"] is expected_stop
    assert database.get_run_record(run_id).status == "in_progress"
    prediction = analytics.get_run_analytics(run_id)["failure_prediction"]
    assert prediction["recommended_action"] == "ask_human"
    assert prediction["executed_action"] == "ask_human"
    assert prediction["execution_outcome"]["pipeline_continues"] is approved


@pytest.mark.asyncio
async def test_debugger_policy_stop_prevents_recovery_mutation(monkeypatch):
    from app.services import debugger_service as debugger_module

    failure = SimpleNamespace(
        id="test-failure",
        status="FAILED",
        failed_tests=1,
        passed_tests=0,
        duration_seconds=0.1,
        stderr="AssertionError",
        stdout="",
        exit_code=1,
        test_items=[],
    )
    analytics = SimpleNamespace(
        record_stage=lambda **_: {"risk_action": "stop", "_step_index": 0},
        record_recovery_episode=Mock(),
    )
    database = SimpleNamespace(
        get_plan=lambda _: None,
        add_log=Mock(),
        save_recovery_attempt=Mock(),
    )
    monkeypatch.setattr(debugger_module, "feature_analytics_service", analytics)
    monkeypatch.setattr(debugger_module, "db_service", database)
    monkeypatch.setattr(
        debugger_module.test_runner_service, "run_tests", Mock(return_value=failure)
    )
    monkeypatch.setattr(
        debugger_module.workspace_service, "get_default_repo_path", lambda: "."
    )
    repair = AsyncMock()
    monkeypatch.setattr(debugger_module.debugger_service, "_apply_recovery_fix", repair)

    async def stop_after_first_prediction(_):
        return {"stop": True, "stop_reason": "policy_stop"}

    result = await debugger_module.debugger_service.run_testing_and_recovery_loop(
        run_id="stop-before-repair",
        max_recovery_retries=3,
        model_name="policy-test-model",
        policy_handler=stop_after_first_prediction,
    )

    assert result["policy_stopped"] is True
    assert result["stop_reason"] == "policy_stop"
    assert repair.await_count == 0
    assert debugger_module.test_runner_service.run_tests.call_count == 1


@pytest.mark.asyncio
async def test_debugger_applies_queued_strategy_on_next_repair(monkeypatch):
    from app.services import debugger_service as debugger_module

    def test_result(test_id, status, stderr="", exit_code=0):
        return SimpleNamespace(
            id=test_id,
            status=status,
            failed_tests=1 if status == "FAILED" else 0,
            passed_tests=0 if status == "FAILED" else 1,
            duration_seconds=0.1,
            stderr=stderr,
            stdout="",
            exit_code=exit_code,
            test_items=[],
        )

    results = [test_result("initial", "FAILED", "AssertionError", 1),
               test_result("after-repair", "PASSED")]
    analytics = SimpleNamespace(
        record_stage=lambda **kwargs: {
            "risk_action": "continue",
            "details": kwargs.get("details", {}),
            "_step_index": 0 if kwargs.get("event_type") == "test_failed" else 1,
        },
        record_recovery_episode=Mock(),
        record_policy_execution=Mock(),
    )
    database = SimpleNamespace(
        get_plan=lambda _: None,
        add_log=Mock(),
        save_recovery_attempt=Mock(),
    )
    monkeypatch.setattr(debugger_module, "feature_analytics_service", analytics)
    monkeypatch.setattr(debugger_module, "db_service", database)
    monkeypatch.setattr(
        debugger_module.test_runner_service,
        "run_tests",
        Mock(side_effect=lambda **_: results.pop(0)),
    )
    monkeypatch.setattr(
        debugger_module.workspace_service, "get_default_repo_path", lambda: "."
    )
    monkeypatch.setattr(
        debugger_module.debugger_service, "_apply_recovery_fix",
        AsyncMock(return_value=["module.py"]),
    )
    monkeypatch.setattr(
        debugger_module.debugger_service, "_check_regression_tests", Mock(return_value=True)
    )
    callbacks = 0

    async def switch_once(_):
        nonlocal callbacks
        callbacks += 1
        if callbacks == 1:
            return {"strategy_override": "alternative_strategy", "strategy_step_index": 0}
        return {}

    result = await debugger_module.debugger_service.run_testing_and_recovery_loop(
        run_id="strategy-switch",
        max_recovery_retries=1,
        model_name="policy-test-model",
        policy_handler=switch_once,
    )

    assert result["resolved"] is True
    debugger_module.debugger_service._apply_recovery_fix.assert_awaited_once()
    assert (
        debugger_module.debugger_service._apply_recovery_fix.await_args.kwargs[
            "strategy_override"
        ] == "alternative_strategy"
    )
    analytics.record_policy_execution.assert_any_call(
        "strategy-switch",
        0,
        "switch_strategy",
        "executed",
        {
            "strategy": "alternative_strategy",
            "attempt": 1,
            "files_modified": ["module.py"],
            "verified": True,
        },
    )
