import os
import sys
import pytest
import asyncio

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.task_router_service import task_router_service
from app.services.workspace_service import workspace_service
from app.services.test_runner_service import test_runner_service
from app.services.telemetry_service import telemetry_manager, TelemetryTracker
from app.services.verifier_service import verifier_service
from app.services.orchestrator_service import orchestrator_service
from app.services.db import db_service

def test_task_router_simple_isolated_function():
    prompt = "Implement a helper function multiply(a: float, b: float) -> float in app/service.py and test in tests/test_service.py"
    decision = task_router_service.route_task(prompt, workspace_service.get_default_repo_path())
    assert decision.task_tier == "simple"
    assert decision.use_fast_path is True
    assert decision.skip_separate_planner is True
    assert decision.single_coding_agent is True
    assert "app/service.py" in decision.target_files
    assert "tests/test_service.py" in decision.target_test_files

def test_task_router_complex_jwt_auth():
    prompt = "Implement complete JWT authentication with user registration, login, and token verification with password hashing in app/auth.py and tests/test_auth.py"
    decision = task_router_service.route_task(prompt, workspace_service.get_default_repo_path())
    assert decision.task_tier == "complex"
    assert decision.use_fast_path is False
    assert decision.security_sensitive is True
    assert decision.model_name == "qwen2.5-coder:7b"

def test_task_router_concurrency_sensitive():
    prompt = "Fix race condition and unclosed sockets in connection pool using asyncio.Lock in src/pool.py and tests/test_pool.py"
    decision = task_router_service.route_task(prompt, workspace_service.get_default_repo_path())
    assert decision.task_tier == "complex"
    assert decision.concurrency_sensitive is True
    assert decision.use_fast_path is False

def test_task_router_multi_file_medium_scope():
    prompt = "Add user account status field with UserStatus enum in app/models.py, update user response serializer in app/serializers.py, and verify in tests/test_models.py"
    decision = task_router_service.route_task(prompt, workspace_service.get_default_repo_path())
    assert decision.task_tier in ("medium", "complex")
    assert decision.use_fast_path is False

def test_targeted_inspection_vs_full_inspection():
    repo_path = workspace_service.get_default_repo_path()
    targeted = workspace_service.inspect_targeted(repo_path, ["app/main.py", "requirements.txt"])
    assert targeted["total_files"] == 2
    assert targeted["exists"] is True

    full = workspace_service.inspect_directory(repo_path)
    assert full["total_files"] >= targeted["total_files"]

def test_telemetry_tracker_lifecycle():
    run_id = "test_run_telemetry_123"
    task_id = "test_task_123"
    tracker = telemetry_manager.get_or_create(run_id, task_id)

    t0 = tracker.start_span("stage_test", "op_test")
    tracker.record_model_call(
        model_name="qwen2.5-coder:1.5b",
        duration_ms=450.0,
        tokens_in=120,
        tokens_out=45,
        tok_per_sec=100.0,
        stage="coder"
    )
    tracker.record_files_inspected(2)
    tracker.record_tool_call()
    tracker.end_span("stage_test", "op_test", t0)

    report = tracker.finalize()
    assert report["run_id"] == run_id
    assert report["counters"]["model_calls"] == 1
    assert report["counters"]["total_tokens_in"] == 120
    assert report["counters"]["total_tokens_out"] == 45
    assert report["counters"]["repository_files_inspected"] == 2
    assert report["counters"]["tool_calls"] == 1
    assert "stage_test" in report["stage_durations"]
    assert report["total_wall_clock_seconds"] >= 0.0

@pytest.mark.asyncio
async def test_fast_path_execution_and_verification():
    prompt = "Implement a helper function add(a: int, b: int) -> int in app/service.py and test in tests/test_service.py"
    run_record = await orchestrator_service.run_full_pipeline(
        request_text=prompt,
        repo_path=workspace_service.get_default_repo_path()
    )
    assert run_record.status == "completed"
    assert run_record.verification is not None
    assert run_record.evaluation is not None
    assert run_record.evaluation.telemetry is not None
    telemetry = run_record.evaluation.telemetry
    assert telemetry["total_wall_clock_seconds"] > 0
    assert "workspace" in telemetry["stage_durations"]

@pytest.mark.asyncio
async def test_dynamic_isolated_workspace_creation():
    prompt = "Implement a simple utility square(n: int) -> int in app/service.py and test in tests/test_service.py"
    # When repo_path is None or omitted, a brand-new folder must be created
    run_record = await orchestrator_service.run_full_pipeline(
        request_text=prompt,
        repo_path=None
    )
    assert run_record.status == "completed"
    assert "workspace_" in run_record.repo_path
    assert os.path.exists(run_record.repo_path)
    assert os.path.exists(os.path.join(run_record.repo_path, "app"))
    assert os.path.exists(os.path.join(run_record.repo_path, "tests"))
    assert os.path.exists(os.path.join(run_record.repo_path, "pytest.ini"))
    assert os.path.exists(os.path.join(run_record.repo_path, "requirements.txt"))

@pytest.mark.asyncio
async def test_existing_repo_used_when_explicitly_provided():
    existing_repo = workspace_service.get_default_repo_path()
    prompt = "Add health route check in app/service.py and tests/test_service.py"
    run_record = await orchestrator_service.run_full_pipeline(
        request_text=prompt,
        repo_path=existing_repo
    )
    assert run_record.status == "completed"
    assert os.path.abspath(run_record.repo_path) == os.path.abspath(existing_repo)
