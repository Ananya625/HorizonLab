import ast
import uuid
from pathlib import Path
import pytest

from app.services.coder_service import coder_service, extract_clean_python_code, redact_sensitive_text
from app.services.goal_parser_service import goal_parser_service
from app.services.ollama_service import ollama_service
from app.services.orchestrator_service import orchestrator_service
from app.services.debugger_service import debugger_service
from app.services.test_runner_service import test_runner_service
from app.services.workspace_service import workspace_service
from app.models.schema import ImplementationPlan, PlannedFile, PlanStep

PROMPT = "Build an authentication module in app/auth.py with JWT tokens and a test suite in tests/test_auth.py."


@pytest.fixture(autouse=True)
def disable_deterministic_templates(monkeypatch):
    """Ensure genuine model generation and safety paths are exercised, not hardcoded templates."""
    monkeypatch.setattr(coder_service, "_get_deterministic_code", lambda *args: None)


# ---------------------------------------------------------------------------
# 1. Truly empty model output
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@pytest.mark.parametrize("empty_raw", ["", "   ", "\n\t\n"])
async def test_truly_empty_model_output_rejected_safely(database, monkeypatch, empty_raw):
    goal = await goal_parser_service.parse_request(PROMPT)

    async def mock_empty(**kwargs):
        return {"message": {"content": empty_raw}, "done": True, "done_reason": "stop"}

    monkeypatch.setattr(ollama_service, "chat_completion", mock_empty)

    with pytest.raises(RuntimeError, match="The model returned no code") as exc_info:
        await coder_service._generate_code_for_file(
            file_rel_path="app/auth.py",
            action="create",
            description="Create auth module",
            original_content=None,
            goal_model=goal,
            plan=None,
            model_name="test-model",
            temperature=0.0,
            run_id=goal.run_id
        )

    assert "No placeholder was written for this file" in str(exc_info.value)

    # Verify diagnostic log in SQLite
    logs = database.get_execution_logs(goal.run_id)
    error_log = next(entry for entry in logs if entry.event_type == "error")
    assert error_log.details["response_length"] == len(empty_raw)
    assert error_log.details["validation_failure_reason"] == "The model returned no code"
    assert error_log.details["requested_file_path"] == "app/auth.py"


# ---------------------------------------------------------------------------
# 2. Valid Python code inside markdown fences
# ---------------------------------------------------------------------------
def test_valid_code_inside_markdown_fences():
    fenced_output = """Here is the implementation:
```python
from datetime import datetime

def hash_password(password: str) -> str:
    return "hashed_" + password

def verify_password(plain: str, hashed: str) -> bool:
    return hashed == "hashed_" + plain
```
I hope this meets all requirements!
"""
    cleaned = extract_clean_python_code(fenced_output, requested_file="app/auth.py")
    assert "Here is the implementation" not in cleaned
    assert "I hope this meets" not in cleaned
    assert "def hash_password" in cleaned
    assert "def verify_password" in cleaned

    # Must compile cleanly
    compile(cleaned, "app/auth.py", "exec")
    tree = ast.parse(cleaned)
    assert len(tree.body) >= 2


# ---------------------------------------------------------------------------
# 3. Valid code returned in expected Ollama response format (JSON envelopes)
# ---------------------------------------------------------------------------
def test_valid_code_returned_in_ollama_json_format():
    # Single-file envelope
    json_envelope = '{"code": "def create_token(user_id: str) -> str:\\n    return f\\"token_{user_id}\\""}'
    cleaned = extract_clean_python_code(json_envelope, requested_file="app/auth.py")
    assert "def create_token" in cleaned
    compile(cleaned, "app/auth.py", "exec")

    # Multi-file envelope keyed by file path
    multi_file_json = """{
        "app/auth.py": "def login():\\n    return True",
        "tests/test_auth.py": "def test_login():\\n    assert True"
    }"""
    auth_code = extract_clean_python_code(multi_file_json, requested_file="app/auth.py")
    assert "def login" in auth_code
    assert "def test_login" not in auth_code

    test_code = extract_clean_python_code(multi_file_json, requested_file="tests/test_auth.py")
    assert "def test_login" in test_code
    assert "def login" not in test_code


# ---------------------------------------------------------------------------
# 4. Malformed or truncated output
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
@pytest.mark.parametrize("metadata", [
    {"done_reason": "length", "done": True},
    {"done": False, "done_reason": "stop"}
])
async def test_truncated_output_rejected_without_partial_write(database, monkeypatch, metadata):
    goal = await goal_parser_service.parse_request(PROMPT)

    async def mock_truncated(**kwargs):
        return {"message": {"content": "def authenticate(user, password):\n    # unfinished logic"}, **metadata}

    monkeypatch.setattr(ollama_service, "chat_completion", mock_truncated)

    with pytest.raises(RuntimeError, match="incomplete or reached its output limit"):
        await coder_service._generate_code_for_file(
            file_rel_path="app/auth.py",
            action="create",
            description="Create auth module",
            original_content=None,
            goal_model=goal,
            plan=None,
            model_name="test-model",
            temperature=0.0,
            run_id=goal.run_id
        )


# ---------------------------------------------------------------------------
# 5. Wrong-file or wrong-scope output
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_wrong_scope_output_rejected(database, monkeypatch):
    goal = await goal_parser_service.parse_request(PROMPT)

    # Model returns only test functions for an implementation file
    async def mock_test_code_for_impl(**kwargs):
        return {"message": {"content": "import pytest\n\ndef test_auth_me():\n    assert True"}, "done": True}

    monkeypatch.setattr(ollama_service, "chat_completion", mock_test_code_for_impl)

    with pytest.raises(RuntimeError, match="model returned only test functions"):
        await coder_service._generate_code_for_file(
            file_rel_path="app/auth.py",
            action="create",
            description="Create auth module",
            original_content=None,
            goal_model=goal,
            plan=None,
            model_name="test-model",
            temperature=0.0,
            run_id=goal.run_id
        )

    # Model returns no test functions for a test file
    async def mock_non_test_code(**kwargs):
        return {"message": {"content": "def helper_calc(x):\n    return x + 1"}, "done": True}

    monkeypatch.setattr(ollama_service, "chat_completion", mock_non_test_code)

    with pytest.raises(RuntimeError, match="model returned no test functions"):
        await coder_service._generate_code_for_file(
            file_rel_path="tests/test_auth.py",
            action="create",
            description="Create test module",
            original_content=None,
            goal_model=goal,
            plan=None,
            model_name="test-model",
            temperature=0.0,
            run_id=goal.run_id
        )


# ---------------------------------------------------------------------------
# 6. Generation failure must NOT trigger tests against incomplete code
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_generation_failure_does_not_trigger_tests(database, monkeypatch):
    prepared = await orchestrator_service.run_full_pipeline(PROMPT, model_name="test-model")
    goal_parser_service.confirm_goal_model(prepared.run_id)

    # Mock coder failure
    async def mock_failing_completion(**kwargs):
        return {"message": {"content": ""}, "done": True}

    monkeypatch.setattr(ollama_service, "chat_completion", mock_failing_completion)

    test_runner_called = False
    def mock_run_tests(*args, **kwargs):
        nonlocal test_runner_called
        test_runner_called = True
        raise AssertionError("Test runner must never be called when code generation fails!")

    monkeypatch.setattr(test_runner_service, "run_tests", mock_run_tests)

    with pytest.raises(RuntimeError, match="No placeholder was written"):
        await orchestrator_service.run_full_pipeline(PROMPT, existing_run_id=prepared.run_id, max_recovery_retries=0)

    # Assert test runner was never called
    assert test_runner_called is False

    # Assert stage-specific termination reason recorded in SQLite
    run_record = database.get_run_record(prepared.run_id)
    assert run_record.evaluation.outcome == "error"
    assert run_record.evaluation.termination_reason == "coder:RuntimeError"


# ---------------------------------------------------------------------------
# 7. Test failure followed by successful repair and retest
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_test_failure_followed_by_successful_repair(database, monkeypatch, tmp_path):
    repo_dir = tmp_path / "repair_repo"
    repo_dir.mkdir()
    app_dir = repo_dir / "app"
    app_dir.mkdir()
    tests_dir = repo_dir / "tests"
    tests_dir.mkdir()

    # Initial broken implementation
    impl_path = app_dir / "auth.py"
    impl_path.write_text("def verify_token(token: str) -> bool:\n    return False\n", encoding="utf-8")

    test_path = tests_dir / "test_auth.py"
    test_path.write_text("from app.auth import verify_token\ndef test_token():\n    assert verify_token('good') is True\n", encoding="utf-8")

    run_id = "run_repair_test"
    database.create_or_update_run(run_id, "t_repair", "Repair Test", PROMPT, str(repo_dir))

    # Setup plan in database
    from datetime import datetime
    plan = ImplementationPlan(
        id="plan_rep",
        run_id=run_id,
        goal_model_version="v1",
        architecture_overview="Auth module",
        target_repo_path=str(repo_dir),
        tech_stack={"framework": "FastAPI", "test_runner": "pytest"},
        key_modules=["app/auth.py"],
        planned_files=[
            PlannedFile(path="app/auth.py", action="modify", description="Fix token verification"),
            PlannedFile(path="tests/test_auth.py", action="test", description="Test token verification")
        ],
        steps=[PlanStep(step_number=1, title="Repair", description="Fix", assigned_agent="Coding Agent", target_files=["app/auth.py"], expected_outcome="Passes tests")],
        testing_strategy="pytest tests/test_auth.py",
        risk_assessment="Low",
        created_at=datetime.now().isoformat()
    )
    database.save_plan(plan)

    # Mock debugger fix returning corrected implementation
    async def mock_debugger_fix(**kwargs):
        fixed_code = "def verify_token(token: str) -> bool:\n    return token == 'good'\n"
        return {"message": {"content": f"```python\n{fixed_code}\n```"}, "done": True}

    monkeypatch.setattr(ollama_service, "chat_completion", mock_debugger_fix)

    # Run testing and recovery loop
    result = await debugger_service.run_testing_and_recovery_loop(
        run_id=run_id,
        max_recovery_retries=2,
        model_name="test-model",
        target_test_files=["tests/test_auth.py"]
    )

    # Verify recovery loop succeeded on attempt 2
    assert result["local_tests_passed"] is True
    assert result["total_attempts"] == 2
    assert "app/auth.py" in result["recovery_attempts"][0].files_modified
    assert "token == 'good'" in impl_path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 8. Persistent failure terminates cleanly after retry limit
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_persistent_failure_terminates_cleanly_after_retry_limit(database, monkeypatch, tmp_path):
    repo_dir = tmp_path / "persistent_fail_repo"
    repo_dir.mkdir()
    app_dir = repo_dir / "app"
    app_dir.mkdir()
    tests_dir = repo_dir / "tests"
    tests_dir.mkdir()

    impl_path = app_dir / "auth.py"
    impl_path.write_text("def verify_token(token: str) -> bool:\n    return False\n", encoding="utf-8")

    test_path = tests_dir / "test_auth.py"
    test_path.write_text("from app.auth import verify_token\ndef test_token():\n    assert verify_token('good') is True\n", encoding="utf-8")

    run_id = "run_persistent_fail"
    database.create_or_update_run(run_id, "t_persist", "Persist Fail Test", PROMPT, str(repo_dir))

    from datetime import datetime
    plan = ImplementationPlan(
        id="plan_persist",
        run_id=run_id,
        goal_model_version="v1",
        architecture_overview="Auth module",
        target_repo_path=str(repo_dir),
        tech_stack={"framework": "FastAPI", "test_runner": "pytest"},
        key_modules=["app/auth.py"],
        planned_files=[
            PlannedFile(path="app/auth.py", action="modify", description="Fix token verification"),
            PlannedFile(path="tests/test_auth.py", action="test", description="Test token verification")
        ],
        steps=[PlanStep(step_number=1, title="Repair", description="Fix", assigned_agent="Coding Agent", target_files=["app/auth.py"], expected_outcome="Passes tests")],
        testing_strategy="pytest tests/test_auth.py",
        risk_assessment="Low",
        created_at=datetime.now().isoformat()
    )
    database.save_plan(plan)

    # Debugger returns repeated unhelpful code
    async def mock_failing_debugger(**kwargs):
        return {"message": {"content": "def verify_token(token: str) -> bool:\n    return False\n"}, "done": True}

    monkeypatch.setattr(ollama_service, "chat_completion", mock_failing_debugger)

    result = await debugger_service.run_testing_and_recovery_loop(
        run_id=run_id,
        max_recovery_retries=2,
        model_name="test-model",
        target_test_files=["tests/test_auth.py"]
    )

    # Verify bounded termination without looping
    assert result["local_tests_passed"] is False
    assert result["total_attempts"] <= 3  # Initial + max_retries


# ---------------------------------------------------------------------------
# 9. Preservation of previous valid file when generation is rejected
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_preservation_of_previous_valid_file_on_rejection(database, monkeypatch, tmp_path):
    repo_dir = tmp_path / "valid_repo"
    repo_dir.mkdir()
    app_dir = repo_dir / "app"
    app_dir.mkdir()

    original_code = "def get_active_user():\n    return {'username': 'original_valid_user'}\n"
    auth_file = app_dir / "auth.py"
    auth_file.write_text(original_code, encoding="utf-8")

    goal = await goal_parser_service.parse_request(PROMPT)

    # Model returns syntax error
    async def mock_syntax_error(**kwargs):
        return {"message": {"content": "def get_active_user(:\n    # broken"}, "done": True}

    monkeypatch.setattr(ollama_service, "chat_completion", mock_syntax_error)

    with pytest.raises(RuntimeError, match="No placeholder was written for this file"):
        await coder_service._generate_code_for_file(
            file_rel_path="app/auth.py",
            action="modify",
            description="Update auth module",
            original_content=original_code,
            goal_model=goal,
            plan=None,
            model_name="test-model",
            temperature=0.0,
            run_id=goal.run_id
        )

    # File on disk must be completely unchanged
    current_content = auth_file.read_text(encoding="utf-8")
    assert current_content == original_code

    # No leftover .tmp files
    tmp_files = list(app_dir.glob(".tmp_*"))
    assert len(tmp_files) == 0


# ---------------------------------------------------------------------------
# Secret & Credential Redaction Test
# ---------------------------------------------------------------------------
def test_sensitive_credentials_redacted():
    raw_output_with_secrets = 'password="supersecret123" and api_key = "abc-xyz-token" and bearer = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.doNotLeakSignature"'
    redacted = redact_sensitive_text(raw_output_with_secrets)

    assert "supersecret123" not in redacted
    assert "abc-xyz-token" not in redacted
    assert "doNotLeakSignature" not in redacted
    assert "[REDACTED]" in redacted


# ---------------------------------------------------------------------------
# Exact Sanitized Rejected app/main.py Responses Regression Tests
# ---------------------------------------------------------------------------
REJECTED_MAIN_7117 = """```python
from fastapi import FastAPI, HTTPException, Depends, status
from pydantic import BaseModel, EmailStr
from typing import Optional, Dict, Any
from app.auth import (
    USERS_DB,
    hash_password,
    verify_password,
    create_access_token,
    get_current_user
)

app = FastAPI(title="Task Service API", version="1.0.0")

@app.get("/health")
def health():
    return {"status": "healthy"}

# Auth router
from app.routes.auth_routes import router as auth_router
app.include_router(auth_router, prefix="/api/auth", tags=["Authentication"])

# Global error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return {"detail": exc.detail, "status_code": exc.status_code}

# Protected route
@app.get("/api/auth/me", response_model=UserProfileResponse)
def get_user_profile(current_user: dict = Depends(get_current_user)):
    return current_user

# Run test suite
import pytest
from app.main import app

@pytest.fixture
def client():
    return app.test_client()

def test_register(client):
    data = {
        "username": "testuser",
        "email": "testuser@example.com",
        "password": "testpassword"
    }
    response = client.post("/api/auth/register", json=data)
    assert response.status_code == 201
    assert "access_token" in response.json()

def test_login(client):
    data = {
        "username": "testuser",
        "password": "testpassword"
    }
    response = client.post("/api/auth/login", json=data)
    assert response.status_code == 200
    assert "access_token" in response.json()

def test_get_user_profile(client):
    response = client.get("/api/auth/me")
    assert response.status_code == 200
    assert "username" in response.json()
```"""

REJECTED_MAIN_9280 = """```python
from fastapi import FastAPI, HTTPException, Depends, status
from pydantic import BaseModel, EmailStr
from typing import Optional, Dict, Any
from app.auth import (
    USERS_DB,
    hash_password,
    verify_password,
    create_access_token,
    get_current_user
)

app = FastAPI(title="Task Service API", version="1.0.0")

@app.get("/health")
def health():
    return {"status": "healthy"}

# Import auth router
from app.routes.auth_routes import router

app.include_router(router)

# Register global error handlers
@app.exception_handler(HTTPException)
async def handle_http_exception(request, exc):
    return {"status": "error", "message": exc.detail}, exc.status_code

# Run test suite, verify 100% test pass rate, check for type errors, and inspect diff cleanliness
# This is a placeholder for running the test suite and checking the results
# You would typically use a testing framework like pytest to run the tests
# Example: pytest app/test_main.py
```"""


@pytest.mark.asyncio
async def test_exact_rejected_main_py_extracted_and_validated_safely(database, monkeypatch):
    goal = await goal_parser_service.parse_request(PROMPT)

    async def mock_resp_7117(**kwargs):
        return {"message": {"content": REJECTED_MAIN_7117}, "done": True, "done_reason": "stop"}

    monkeypatch.setattr(ollama_service, "chat_completion", mock_resp_7117)

    code = await coder_service._generate_code_for_file(
        file_rel_path="app/main.py",
        action="modify",
        description="Include auth router in main FastAPI application and register global error handlers.",
        original_content="from fastapi import FastAPI\napp = FastAPI()",
        goal_model=goal,
        plan=None,
        model_name="qwen2.5-coder:1.5b",
        temperature=0.2,
        run_id=goal.run_id
    )

    assert len(code) > 0
    assert "FastAPI" in code
    assert "auth_router" in code
    # Must compile cleanly
    compile(code, "app/main.py", "exec")


@pytest.mark.asyncio
async def test_exact_rejected_main_py_9280_extracted_and_validated_safely(database, monkeypatch):
    goal = await goal_parser_service.parse_request(PROMPT)

    async def mock_resp_9280(**kwargs):
        return {"message": {"content": REJECTED_MAIN_9280}, "done": True, "done_reason": "stop"}

    monkeypatch.setattr(ollama_service, "chat_completion", mock_resp_9280)

    code = await coder_service._generate_code_for_file(
        file_rel_path="app/main.py",
        action="modify",
        description="Include auth router in main FastAPI application and register global error handlers.",
        original_content="from fastapi import FastAPI\napp = FastAPI()",
        goal_model=goal,
        plan=None,
        model_name="qwen2.5-coder:1.5b",
        temperature=0.2,
        run_id=goal.run_id
    )

    assert len(code) > 0
    assert "FastAPI" in code
    assert "app.include_router(router)" in code
    compile(code, "app/main.py", "exec")

