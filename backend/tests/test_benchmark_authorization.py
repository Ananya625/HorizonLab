from pathlib import Path
import pytest
from app.services.orchestrator_service import orchestrator_service
from app.services.goal_parser_service import goal_parser_service
from app.services.ollama_service import ollama_service
from app.models.schema import GoalModel, SubGoal, SuccessCriterion, Constraint, Ambiguity, PlanStep

PROMPT = "Implement a helper function add(a: int, b: int) -> int in app/service.py and test in tests/test_service.py"


@pytest.mark.asyncio
async def test_ordinary_interactive_run_requires_confirmation_and_does_not_execute_code_generation(database, monkeypatch):
    """
    Demonstrates:
    1. Ordinary interactive runs (authorized_benchmark=False) still require confirmation.
    2. Unconfirmed interactive runs do not execute code generation (plan is None, code files uncreated).
    """
    async def fake_model(**kwargs):
        return {'message': {'content': '{"main_goal":"Add two numbers","summary":"Arithmetic","success_criteria":[]}'}}
    monkeypatch.setattr(ollama_service, 'chat_completion', fake_model)

    # Initial ordinary interactive call:
    record = await orchestrator_service.run_full_pipeline(
        PROMPT, repo_path=None, temperature=0, max_recovery_retries=0
    )

    # Asserts that the run stopped at confirmation gate
    assert record.goal_model is not None
    assert record.goal_model.is_confirmed is False
    assert record.current_stage == "requirement"
    assert record.status == "in_progress"
    assert record.plan is None
    assert record.evaluation is None

    # Asserts that no code generation took place in the workspace
    service_file = Path(record.repo_path) / "app" / "service.py"
    assert not service_file.exists()


@pytest.mark.asyncio
async def test_unconfirmed_interactive_run_cannot_execute_code_generation(database, monkeypatch):
    """
    Demonstrates:
    Calling run_full_pipeline with an existing unconfirmed run_id without authorization
    is strictly rejected by the confirmation gate.
    """
    async def fake_model(**kwargs):
        return {'message': {'content': '{"main_goal":"Add two numbers","summary":"Arithmetic","success_criteria":[]}'}}
    monkeypatch.setattr(ollama_service, 'chat_completion', fake_model)

    # Step 1: Initial submission creates unconfirmed goal
    record = await orchestrator_service.run_full_pipeline(
        PROMPT, repo_path=None, temperature=0, max_recovery_retries=0
    )
    assert not record.goal_model.is_confirmed

    # Step 2: Attempting to execute unconfirmed run without authorization raises ValueError
    with pytest.raises(ValueError, match="Confirm the goal and resolve blocking ambiguities before execution"):
        await orchestrator_service.run_full_pipeline(
            PROMPT, existing_run_id=record.run_id, authorized_benchmark=False
        )

    # Workspace remains unwritten
    service_file = Path(record.repo_path) / "app" / "service.py"
    assert not service_file.exists()


@pytest.mark.asyncio
async def test_authorized_benchmark_can_complete_workflow_with_verification(database, monkeypatch):
    """
    Demonstrates:
    1. An explicitly authorized benchmark (authorized_benchmark=True) completes the full workflow.
    2. Code generation, testing, and final verification occur.
    """
    async def fake_model(**kwargs):
        prompt = kwargs['messages'][-1]['content']
        code = (
            'from app.service import add\n'
            'def test_add():\n'
            '    assert add(2, 3) == 5\n'
            '    assert add(-4, 2) == -2\n'
            '    assert add(0, 0) == 0\n'
            if 'File to write: tests/' in prompt else
            'def add(a, b):\n    return a + b\n'
        )
        return {'message': {'content': code}}
    monkeypatch.setattr(ollama_service, 'chat_completion', fake_model)

    record = await orchestrator_service.run_full_pipeline(
        PROMPT, repo_path=None, temperature=0, max_recovery_retries=0, authorized_benchmark=True
    )

    # Goal is confirmed automatically with benchmark authorization
    assert record.goal_model.is_confirmed is True
    assert record.status == "completed"
    assert record.current_stage == "completed"

    # Plan was generated
    assert record.plan is not None
    assert len(record.code_changes) > 0

    # Code files were created
    service_file = Path(record.repo_path) / "app" / "service.py"
    test_file = Path(record.repo_path) / "tests" / "test_service.py"
    assert service_file.exists()
    assert test_file.exists()

    # Tests ran and verified
    assert len(record.test_results) > 0
    latest_test = record.test_results[-1]
    assert latest_test.passed_tests > 0

    # Verification report was generated
    assert record.verification is not None
    assert record.verification.overall_verdict in ("VERIFIED_PASSED", "VERIFIED_WITH_WARNINGS", "UNVERIFIED")

    # Evaluation metrics recorded authorized_benchmark execution mode
    assert record.evaluation is not None
    assert record.metadata.get("execution_mode") == "authorized_benchmark"


@pytest.mark.asyncio
async def test_authorized_benchmark_resolves_blocking_ambiguities_with_defaults(database, monkeypatch):
    """
    Demonstrates:
    Authorized benchmark auto-resolves any blocking ambiguities using default assumptions
    and confirms the goal model without getting stuck.
    """
    async def fake_model(**kwargs):
        prompt = kwargs['messages'][-1]['content']
        code = (
            'from app.service import add\n'
            'def test_add():\n'
            '    assert add(2, 3) == 5\n'
            if 'File to write: tests/' in prompt else
            'def add(a, b):\n    return a + b\n'
        )
        return {'message': {'content': code}}
    monkeypatch.setattr(ollama_service, 'chat_completion', fake_model)

    # Initial run creates goal
    initial_record = await orchestrator_service.run_full_pipeline(
        PROMPT, repo_path=None, temperature=0, max_recovery_retries=0
    )
    goal = database.get_goal_model(initial_record.run_id)
    goal.ambiguities.append(Ambiguity(
        id="AMB-1",
        question="What should negative inputs do?",
        severity="blocking",
        resolved=False,
        default_assumption="Support standard negative integer addition"
    ))
    database.save_goal_model(goal)

    # Calling with authorized_benchmark=True resolves the blocking ambiguity and executes
    completed_record = await orchestrator_service.run_full_pipeline(
        PROMPT, existing_run_id=initial_record.run_id, authorized_benchmark=True
    )

    assert completed_record.goal_model.is_confirmed is True
    assert completed_record.status == "completed"
    stored_goal = database.get_goal_model(initial_record.run_id)
    resolved_amb = [a for a in stored_goal.ambiguities if a.id == "AMB-1"][0]
    assert resolved_amb.resolved is True
    assert resolved_amb.user_answer == "Support standard negative integer addition"


def test_plan_step_accepts_string_and_integer_dependencies():
    """
    Verifies that PlanStep accepts both integer step IDs and string references
    (such as file paths returned by Ollama) without Pydantic validation errors.
    """
    step = PlanStep(
        step_number=2,
        title="Create test suite",
        description="Verify addition module",
        target_files=["tests/test_addition.py"],
        dependencies=["app/addition.py", 1],
        expected_outcome="Passing test suite"
    )
    assert "app/addition.py" in step.dependencies
    assert 1 in step.dependencies


@pytest.mark.asyncio
async def test_coder_accepts_test_importing_module_by_basename(database, monkeypatch):
    """
    Verifies that coder accepts tests importing either 'from app.addition import add'
    or 'from addition import add' without raising ValueError.
    """
    from app.services.coder_service import coder_service
    goal = await goal_parser_service.parse_request(PROMPT)
    raw = "from addition import add\n\ndef test_add():\n    assert add(1, 2) == 3\n"
    async def completion(**kwargs):
        return {"message": {"content": raw}, "done": True, "done_reason": "stop"}
    monkeypatch.setattr(ollama_service, "chat_completion", completion)

    code = await coder_service._generate_code_for_file(
        "tests/test_addition.py", "test", "add test", None,
        goal, None, None, 0, goal.run_id, {"app/addition.py": "def add(a, b): return a + b"}
    )
    assert "def test_add()" in code


@pytest.mark.asyncio
async def test_coder_refines_test_when_model_initially_redefines_symbol(database, monkeypatch):
    """
    Verifies that when a model initially redefines an implementation symbol instead
    of importing it, the coder sends a refinement prompt and accepts the corrected test.
    """
    from app.services.coder_service import coder_service
    goal = await goal_parser_service.parse_request(PROMPT)
    call_count = 0

    async def completion(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # First attempt: mistakenly redefines symbol locally
            return {"message": {"content": "def add(a, b): return a + b\ndef test_add(): assert add(1, 2) == 3"}}
        else:
            # Refinement attempt: corrects to import from app.service
            return {"message": {"content": "from app.service import add\ndef test_add(): assert add(1, 2) == 3"}}

    monkeypatch.setattr(ollama_service, "chat_completion", completion)

    code = await coder_service._generate_code_for_file(
        "tests/test_service.py", "test", "test addition", None,
        goal, None, None, 0, goal.run_id, {"app/service.py": "def add(a, b): return a + b"}
    )
    assert call_count == 2
    assert "from app.service import add" in code
    assert "def test_add():" in code
