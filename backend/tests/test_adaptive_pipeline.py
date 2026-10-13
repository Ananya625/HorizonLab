import os
import sys
import pytest

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.task_router_service import task_router_service
from app.services.workspace_service import workspace_service
from app.services.telemetry_service import telemetry_manager
from app.services.orchestrator_service import orchestrator_service

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
    assert decision.model_name == "qwen3:1.7b"

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

@pytest.fixture
def deterministic_model(monkeypatch):
    from app.services.ollama_service import ollama_service

    async def completion(messages, **kwargs):
        # Tests exercise the generated implementation, not a duplicate function.
        code = ('from app.service import add\ndef test_add(): assert add(2, 3) == 5\n'
                if 'File to write: tests/' in messages[-1]['content'] else 'def add(a, b): return a + b\n')
        return {"message": {"content": code}}

    monkeypatch.setattr(ollama_service, "chat_completion", completion)


@pytest.mark.asyncio
async def test_fast_path_execution_and_verification(deterministic_model):
    from app.services.goal_parser_service import goal_parser_service
    prompt = "Implement a helper function add(a: int, b: int) -> int in app/service.py and test in tests/test_service.py"
    prepared = await orchestrator_service.run_full_pipeline(request_text=prompt, repo_path=None)
    assert prepared.goal_model.is_confirmed is False
    goal_parser_service.patch_goal_model(prepared.run_id, {'ambiguities': []}, 'Fixture defines arithmetic behavior')
    goal_parser_service.confirm_goal_model(prepared.run_id)
    run_record = await orchestrator_service.run_full_pipeline(
        request_text=prompt, existing_run_id=prepared.run_id, max_recovery_retries=0)
    assert run_record.verification is not None
    assert run_record.evaluation is not None
    assert run_record.evaluation.telemetry is not None
    assert run_record.evaluation.verified_success is not True
    telemetry = run_record.evaluation.telemetry
    assert telemetry["total_wall_clock_seconds"] > 0
    assert "workspace" in telemetry["stage_durations"]


@pytest.mark.asyncio
async def test_dynamic_isolated_workspace_creation(deterministic_model):
    prompt = "Implement a simple utility square(n: int) -> int in app/service.py and test in tests/test_service.py"
    run_record = await orchestrator_service.run_full_pipeline(request_text=prompt, repo_path=None)
    assert run_record.goal_model.is_confirmed is False
    assert "workspace_" in run_record.repo_path
    for path in ("app", "tests", "pytest.ini", "requirements.txt"):
        assert os.path.exists(os.path.join(run_record.repo_path, path))


@pytest.mark.asyncio
async def test_existing_repo_used_when_explicitly_provided(deterministic_model):
    existing_repo = workspace_service.get_default_repo_path()
    prompt = "Add health route check in app/service.py and tests/test_service.py"
    run_record = await orchestrator_service.run_full_pipeline(request_text=prompt, repo_path=existing_repo)
    assert run_record.goal_model.is_confirmed is False
    assert os.path.abspath(run_record.repo_path) == os.path.abspath(existing_repo)
