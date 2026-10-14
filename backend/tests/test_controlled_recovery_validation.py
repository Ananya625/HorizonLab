import pytest
from pathlib import Path
from app.models.schema import ImplementationPlan, PlannedFile, PlanStep, TestRunResult
TestRunResult.__test__ = False
from app.services.db import db_service
from app.services.workspace_service import workspace_service
from app.services.debugger_service import debugger_service
from app.services.test_runner_service import test_runner_service
from app.services.ollama_service import ollama_service
import tempfile
import uuid


@pytest.mark.asyncio
async def test_controlled_recovery_with_deliberately_broken_impl(monkeypatch):
    """Step 4 Validation: Execute a controlled task with a deliberately incorrect implementation.
    Confirm testing agent diagnoses failure, repairs implementation, reruns pytest, and verifies success."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_dir = Path(tmpdir) / "disposable_repo"
        repo_dir.mkdir()
        app_dir = repo_dir / "app"
        app_dir.mkdir()
        tests_dir = repo_dir / "tests"
        tests_dir.mkdir()

        # pytest.ini in workspace for isolated pythonpath
        (repo_dir / "pytest.ini").write_text("[pytest]\npythonpath = . app\n", encoding="utf-8")

        # 1. Deliberately broken implementation (returns a + b instead of a * b)
        impl_path = app_dir / "service.py"
        impl_path.write_text("def multiply_numbers(a: int, b: int) -> int:\n    return a + b\n", encoding="utf-8")

        # 2. Genuine acceptance criteria tests (must never be modified)
        test_content = (
            "import pytest\n"
            "from app.service import multiply_numbers\n\n"
            "def test_multiply_positive():\n"
            "    assert multiply_numbers(4, 5) == 20\n\n"
            "def test_multiply_negative():\n"
            "    assert multiply_numbers(-3, 2) == -6\n"
        )
        test_path = tests_dir / "test_service.py"
        test_path.write_text(test_content, encoding="utf-8")

        run_id = f"run_ctrl_{uuid.uuid4().hex[:8]}"
        db_service.create_or_update_run(run_id, "t_ctrl", "Multiply Numbers", "Implement multiply_numbers", str(repo_dir))

        plan = ImplementationPlan(
            id=f"plan_{uuid.uuid4().hex[:6]}",
            run_id=run_id,
            goal_model_version="1.0",
            architecture_overview="Arithmetic service",
            target_repo_path=str(repo_dir),
            tech_stack={"framework": "FastAPI", "test_runner": "pytest"},
            key_modules=["app/service.py"],
            planned_files=[
                PlannedFile(path="app/service.py", action="modify", description="Arithmetic multiplication logic"),
                PlannedFile(path="tests/test_service.py", action="test", description="Acceptance tests"),
            ],
            steps=[PlanStep(step_number=1, title="Multiply", description="Code", assigned_agent="Coding Agent", target_files=["app/service.py"], expected_outcome="Passes tests")],
            testing_strategy="pytest tests/test_service.py",
            risk_assessment="Low",
            created_at="2026-10-13T12:00:00"
        )
        db_service.save_plan(plan)

        # Mock debugger LLM to propose corrected implementation
        async def mock_repair(**kwargs):
            corrected_code = (
                "def multiply_numbers(a: int, b: int) -> int:\n"
                "    \"\"\"Multiply two numbers.\"\"\"\n"
                "    return a * b\n"
            )
            return {"message": {"content": f"```python\n{corrected_code}\n```"}, "done": True}

        monkeypatch.setattr(ollama_service, "chat_completion", mock_repair)

        # Execute testing and recovery loop
        result = await debugger_service.run_testing_and_recovery_loop(
            run_id=run_id,
            max_recovery_retries=2,
            target_test_files=["tests/test_service.py"]
        )

        # 3. Assert that testing agent verified success
        assert result["local_tests_passed"] is True
        assert result["resolved"] is False  # Preserved: independent verification remains required
        assert "app/service.py" in result["recovery_attempts"][0].files_modified

        # 4. Confirm implementation was corrected on disk
        updated_impl = impl_path.read_text(encoding="utf-8")
        assert "return a * b" in updated_impl

        # 5. Confirm existing tests were NOT modified or weakened
        assert test_path.read_text(encoding="utf-8") == test_content


@pytest.mark.asyncio
async def test_controlled_unresolvable_failure_never_fakes_success(monkeypatch):
    """Step 4 Validation: When an implementation cannot resolve the test failure within retries,
    it must report the exact root cause and remain FAILED or UNVERIFIED. Never fake a passing result."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_dir = Path(tmpdir) / "disposable_repo_unres"
        repo_dir.mkdir()
        app_dir = repo_dir / "app"
        app_dir.mkdir()
        tests_dir = repo_dir / "tests"
        tests_dir.mkdir()

        (repo_dir / "pytest.ini").write_text("[pytest]\npythonpath = . app\n", encoding="utf-8")

        # Broken implementation
        impl_path = app_dir / "service.py"
        impl_path.write_text("def solve_impossible():\n    return False\n", encoding="utf-8")

        # Test expecting True
        test_path = tests_dir / "test_service.py"
        test_path.write_text("from app.service import solve_impossible\ndef test_solve():\n    assert solve_impossible() is True\n", encoding="utf-8")

        run_id = f"run_unres_{uuid.uuid4().hex[:8]}"
        db_service.create_or_update_run(run_id, "t_unres", "Impossible Task", "Prompt", str(repo_dir))

        plan = ImplementationPlan(
            id=f"plan_{uuid.uuid4().hex[:6]}",
            run_id=run_id,
            goal_model_version="1.0",
            architecture_overview="Service",
            target_repo_path=str(repo_dir),
            tech_stack={"framework": "FastAPI", "test_runner": "pytest"},
            key_modules=["app/service.py"],
            planned_files=[
                PlannedFile(path="app/service.py", action="modify", description="Logic"),
                PlannedFile(path="tests/test_service.py", action="test", description="Tests"),
            ],
            steps=[],
            testing_strategy="pytest",
            risk_assessment="Low",
            created_at="2026-10-13T12:00:00"
        )
        db_service.save_plan(plan)

        # Mock debugger fix returning unchanged code (ineffective fix)
        async def mock_ineffective(**kwargs):
            return {"message": {"content": "def solve_impossible():\n    return False\n"}, "done": True}

        monkeypatch.setattr(ollama_service, "chat_completion", mock_ineffective)

        result = await debugger_service.run_testing_and_recovery_loop(
            run_id=run_id,
            max_recovery_retries=2,
            target_test_files=["tests/test_service.py"]
        )

        # Must NOT fake success
        assert result["local_tests_passed"] is False
        assert result["resolved"] is False
        assert result["final_test_result"].status == "FAILED"

        # Verify failure was reported in execution logs
        logs = db_service.get_execution_logs(run_id)
        failure_logs = [l for l in logs if l.stage == "debugger" and l.event_type == "failure"]
        assert len(failure_logs) >= 1
        assert "without resolving test failures" in failure_logs[0].message
