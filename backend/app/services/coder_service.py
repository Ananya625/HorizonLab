from .workflow_service import observed, workflow
import os
import json
import uuid
import logging
import ast
import re
from typing import Dict, Any, List, Optional
from datetime import datetime
from ..models.schema import (
    CodeChange,
    ImplementationPlan,
    GoalModel
)
from .ollama_service import ollama_service
from .workspace_service import workspace_service
from .db import db_service
from .telemetry_service import telemetry_manager
from .drift_controller_service import drift_controller_service
from .goal_tracker_service import goal_tracker_service

logger = logging.getLogger(__name__)


def reject_placeholder_code(source):
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        body = [n for n in node.body if not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant) and isinstance(n.value.value, str))]
        if body and all(isinstance(n, ast.Pass) or (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant) and n.value.value is Ellipsis) for n in body):
            raise ValueError('The model returned a placeholder function')
        if len(body) == 1 and isinstance(body[0], ast.Return) and isinstance(body[0].value, ast.Dict):
            keys = {key.value for key in body[0].value.keys if isinstance(key, ast.Constant)}
            if 'status' in keys and (keys & {'module', 'task'} or node.name == 'execute_service'):
                raise ValueError('The model returned a placeholder status function')

def validate_generated_tests(file_rel_path, cleaned, related_context):
    if os.path.basename(file_rel_path).startswith('test_') and related_context:
        tree = ast.parse(cleaned)
        modules = {p.removesuffix('.py').replace('/', '.').replace('\\', '.')
                   for p in related_context if p.endswith('.py') and not os.path.basename(p).startswith('test_')}
        imports = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        imports.update(f'{n.module}.{a.name}' for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) for a in n.names)
        imports.update(a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names)
        if modules and not modules.intersection(imports):
            raise ValueError('Generated tests must import the implementation they test')
        symbols = {n.name for code in related_context.values() for n in ast.parse(code).body
                   if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and not n.name.startswith('test_')}
        if any(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and n.name in symbols for n in tree.body):
            raise ValueError('Generated tests redefine implementation symbols instead of testing them')


def extract_clean_python_code(raw: str) -> str:
    """Extracts raw executable Python code from markdown blocks, JSON envelopes, or plain text."""
    if not raw:
        return ""
    cleaned = raw.strip()

    # Decode envelopes before looking for fences: fences inside JSON strings
    # contain escaped newlines and must not be treated as raw Python.
    if cleaned.startswith('{'):
        try:
            envelope = json.loads(cleaned)
        except json.JSONDecodeError:
            envelope = None
        if isinstance(envelope, dict):
            if len(envelope) == 1 and next(iter(envelope)).endswith('.py'):
                envelope = next(iter(envelope.values()))
            if isinstance(envelope, dict):
                envelope = envelope.get('content', envelope.get('code'))
            if isinstance(envelope, str):
                cleaned = envelope.strip()

    # 1. Markdown code fences
    if "```python" in cleaned:
        cleaned = cleaned.split("```python")[1].split("```")[0].strip()
    elif "```" in cleaned:
        cleaned = cleaned.split("```")[1].split("```")[0].strip()

    # 2. JSON wrapper check (e.g. {"file": {"content": "..."}} or {"file": {"import": "...", "test": "..."}})
    if cleaned.startswith("{") and cleaned.endswith("}"):
        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, dict):
                # If top-level dict has a single filename key, unwrap it: e.g. {"tests/test_service.py": {...}}
                if len(parsed) == 1 and any(k.endswith(".py") or "/" in k for k in parsed.keys()):
                    parsed = next(iter(parsed.values()))

                if isinstance(parsed, dict):
                    if "content" in parsed and isinstance(parsed["content"], str):
                        cleaned = parsed["content"].strip()
                    elif "code" in parsed and isinstance(parsed["code"], str):
                        cleaned = parsed["code"].strip()
                    else:
                        py_lines = []
                        for k, v in parsed.items():
                            if isinstance(v, str) and any(w in v for w in ("def ", "import ", "from ", "class ", "assert ", "return ")):
                                py_lines.append(v.strip())
                            elif isinstance(v, dict):
                                for sub_k, sub_v in v.items():
                                    if isinstance(sub_v, str) and any(w in sub_v for w in ("def ", "import ", "from ", "class ", "assert ", "return ")):
                                        py_lines.append(sub_v.strip())
                        if py_lines:
                            cleaned = "\n\n".join(py_lines)
                elif isinstance(parsed, str):
                    cleaned = parsed.strip()
        except Exception:
            pass

    return cleaned

CODER_SYSTEM_PROMPT = """You are the Senior Coding Agent in an autonomous software engineering system.

Your job is to generate production-ready, clean, PEP-8 compliant Python code for the specified file in the implementation plan.

Return ONLY the raw Python code for the file. Do NOT wrap in conversational markdown (only return the code or markdown code fence ```python ... ```)."""

class CoderService:
    @observed('coder', 'stage', reason=None)
    async def execute_plan(
        self,
        run_id: str,
        model_name: Optional[str] = None,
        temperature: float = 0.2
    ) -> List[CodeChange]:
        model_name = model_name or ollama_service.default_model
        plan = db_service.get_plan(run_id)
        if not plan:
            raise ValueError(f"Plan for run_id '{run_id}' not found")
        goal_model = db_service.get_goal_model(run_id)
        if not goal_model:
            raise ValueError(f"Goal model for run_id '{run_id}' not found")
        if not goal_model.is_confirmed:
            raise ValueError('Confirm the goal before writing code')
        from .workflow_service import goal_revision
        if plan.goal_revision is not None and plan.goal_revision != goal_revision(goal_model):
            raise ValueError('Regenerate the plan for the current confirmed goal content')
        if plan.goal_model_version != goal_model.goal_model_version:
            raise ValueError('Regenerate the plan for the current confirmed goal')

        repo_path = plan.target_repo_path
        code_changes: List[CodeChange] = []

        tracker = telemetry_manager.get(run_id)
        if tracker:
            tracker.record_agent_invocation("Coding Agent")

        db_service.add_log(
            run_id=run_id,
            stage="coder",
            agent_role="Coding Agent",
            event_type="info",
            message=f"Starting implementation for {len(plan.planned_files)} planned files across {len(plan.steps)} steps using model '{model_name}'.",
            details={"repo_path": repo_path, "model": model_name}
        )

        implemented_context: Dict[str, str] = {}
        # Tests need the actual implementation interface, even when the planner
        # lists them first. Keep relative order within each group.
        for planned_file in sorted(plan.planned_files, key=lambda f: f.action == 'test' or os.path.basename(f.path).startswith('test_')):
            with workflow.attempt(run_id, planned_file.sub_goal_id):
                file_rel_path = planned_file.path
                action = planned_file.action
                description = planned_file.description

                # Pre-action Drift Check
                pre_check = drift_controller_service.check_action(
                    run_id=run_id,
                    action_type="file_write",
                    target=file_rel_path,
                    payload_str="",
                    repo_path=repo_path
                )
                if not pre_check.allowed:
                    db_service.add_log(
                        run_id=run_id,
                        stage="coder",
                        agent_role="Drift Controller",
                        event_type="warning",
                        message=f"File edit blocked: {pre_check.reason}",
                        details={"file": file_rel_path, "decision": pre_check.model_dump()}
                    )
                    goal_tracker_service.record_action(
                        run_id=run_id,
                        action_type="file_write",
                        target=file_rel_path,
                        payload_str="",
                        status="blocked" if pre_check.action_category == "blocked" else "skipped_duplicate",
                        error_message=pre_check.reason
                    )
                    if pre_check.action_category == "budget_exceeded":
                        break
                    continue

                db_service.add_log(run_id, 'coder', 'Coding Agent', 'tool_call', 'Read workspace file', {'tool':'read_file', 'file':file_rel_path})
                original_content = workspace_service.read_file(repo_path, file_rel_path)

                if tracker:
                    tracker.record_tool_call()

                db_service.add_log(
                    run_id=run_id,
                    stage="coder",
                    agent_role="Coding Agent",
                    event_type="info",
                    message=f"Generating code for '{file_rel_path}' ({action}): {description}",
                    details={"file": file_rel_path, "action": action}
                )

                # Generate new file content
                new_content = await self._generate_code_for_file(
                    file_rel_path=file_rel_path,
                    action=action,
                    description=description,
                    original_content=original_content,
                    goal_model=goal_model,
                    plan=plan,
                    model_name=model_name,
                    temperature=temperature,
                    run_id=run_id,
                    related_context=implemented_context
                )
                implemented_context[file_rel_path] = new_content

                # Repeated Edit & Content Drift Check
                content_check = drift_controller_service.check_action(
                    run_id=run_id,
                    action_type="file_write",
                    target=file_rel_path,
                    payload_str=new_content,
                    repo_path=repo_path
                )
                if not content_check.allowed:
                    db_service.add_log(
                        run_id=run_id,
                        stage="coder",
                        agent_role="Drift Controller",
                        event_type="warning",
                        message=f"Duplicate/Unchanged content skipped for '{file_rel_path}': {content_check.reason}",
                        details={"file": file_rel_path}
                    )
                    goal_tracker_service.record_action(
                        run_id=run_id,
                        action_type="file_write",
                        target=file_rel_path,
                        payload_str=new_content,
                        status="skipped_duplicate",
                        details={"reason": content_check.reason}
                    )
                    continue

                # Write file to disk
                db_service.invalidate_evaluation(run_id, 'Code changed; independent evidence must be refreshed')
                db_service.add_log(run_id, 'coder', 'Coding Agent', 'tool_call', 'Write workspace file', {'tool':'write_file', 'file':file_rel_path})
                workspace_service.write_file(repo_path, file_rel_path, new_content)

                # Compute diff & AST syntax check
                diff_res = workspace_service.compute_diff(original_content, new_content, file_rel_path)

                # Post-action result validation
                val_res = drift_controller_service.validate_result(
                    run_id=run_id,
                    action_type="file_write",
                    target=file_rel_path,
                    success=True,
                    details={"ast_valid": diff_res["ast_valid"], "lines_added": diff_res["lines_added"]}
                )

                # Record verified action in GoalTracker
                goal_tracker_service.record_action(
                    run_id=run_id,
                    action_type="file_write",
                    target=file_rel_path,
                    payload_str=new_content,
                    status="completed" if val_res.valid else "failed",
                    details={"lines_added": diff_res["lines_added"], "ast_valid": diff_res["ast_valid"]}
                )

                change = CodeChange(
                    id=f"change_{uuid.uuid4().hex[:8]}",
                    run_id=run_id,
                    file_path=file_rel_path,
                    action="created" if original_content is None else "modified",
                    original_content=original_content,
                    new_content=new_content,
                    diff_patch=diff_res["diff_patch"],
                    lines_added=diff_res["lines_added"],
                    lines_removed=diff_res["lines_removed"],
                    ast_valid=diff_res["ast_valid"],
                    created_at=datetime.now().isoformat()
                )

                db_service.save_code_change(change)
                code_changes.append(change)

                db_service.add_log(
                    run_id=run_id,
                    stage="coder",
                    agent_role="Coding Agent",
                    event_type="file_edit",
                    message=f"Saved '{file_rel_path}' (+{change.lines_added}/-{change.lines_removed} lines). AST Valid: {change.ast_valid}.",
                    details={"file_path": file_rel_path, "ast_valid": change.ast_valid, "lines_added": change.lines_added}
                )

        db_service.add_log(
            run_id=run_id,
            stage="coder",
            agent_role="Coding Agent",
            event_type="success",
            message=f"Created/updated {len(code_changes)} files; {sum(c.ast_valid is False for c in code_changes)} failed syntax checks. Task verification is separate.",
            details={"total_changes": len(code_changes)}
        )

        return code_changes

    async def _generate_code_for_file(
        self,
        file_rel_path: str,
        action: str,
        description: str,
        original_content: Optional[str],
        goal_model: GoalModel,
        plan: ImplementationPlan,
        model_name: Optional[str],
        temperature: float,
        run_id: Optional[str] = None,
        related_context: Optional[Dict[str, str]] = None
    ) -> str:
        template = self.template_kind(file_rel_path, goal_model.main_goal)
        det_code = self._get_deterministic_code(file_rel_path, goal_model, original_content) if template else None
        if original_content is None and det_code:
            db_service.add_log(goal_model.run_id, 'coder', 'Coding Agent', 'generation',
                               f'Demo template: {template}', {'file': file_rel_path, 'mode': 'template'})
            return det_code

        # Otherwise query Ollama for genuine code synthesis
        raw = ''
        cleaned = ''
        response_reason = None
        try:
            # Never silently discard part of an existing file when replacing it.
            existing_snippet = original_content
            if existing_snippet and len(existing_snippet) > 6000:
                raise ValueError('Existing file exceeds the supported context; split the edit before replacing this file')

            context_block = ""
            if related_context:
                context_block = "\nImplementation files in this workspace:\n"
                for rpath, rcode in related_context.items():
                    context_block += f"--- {rpath} ---\n{rcode}\n----------------\n"

            test_guidance = ""
            if "test" in file_rel_path.lower():
                test_guidance = """
CRITICAL TEST RULES:
1. Import and test the EXACT function/class names and signatures defined in the implementation files above (e.g., 'from app.service import ...' or 'from service import ...').
2. Do NOT invent hypothetical classes or methods that are not defined in the implementation code.
3. Use pytest syntax with assertion statements (e.g., 'def test_...(): assert ...').
4. Keep the suite concise: 3–5 focused cases, without prose or copies of the implementation."""

            user_msg = f"""Task: {goal_model.main_goal}
File to write: {file_rel_path}
Action: {action}
Description: {description}
Required behavior: {[sg.description for sg in goal_model.sub_goals]}
Expected interface: {goal_model.expected_output.schema_summary}
Existing Content:
{existing_snippet or '(None - creating new file)'}
{context_block}
Constraints:
- {[hc.text for hc in goal_model.hard_constraints]}
{test_guidance}

Generate complete, executable, clean Python code for '{file_rel_path}'."""

            messages = [
                {"role": "system", "content": CODER_SYSTEM_PROMPT},
                {"role": "user", "content": user_msg}
            ]

            resp = await ollama_service.chat_completion(
                messages=messages,
                model=model_name,
                temperature=temperature,
                format_json=False,
                num_ctx=4096,
                num_predict=1000,
                run_id=run_id,
                stage="coder"
            )
            raw = resp.get("message", {}).get("content", "")
            if not isinstance(raw, str):
                raw = ''
                raise ValueError('The model response did not contain textual code')
            response_reason = resp.get('done_reason')
            if response_reason == 'length' or resp.get('done') is False:
                raise ValueError('The model response was incomplete or reached its output limit; no incomplete file was written')
            cleaned = extract_clean_python_code(raw)
            if not cleaned:
                raise ValueError('The model returned no code')
            # compile catches invalid return/await placement that ast.parse accepts.
            compile(cleaned, file_rel_path, 'exec')
            if not ast.parse(cleaned).body:
                raise ValueError('The model returned comments without executable code')
            reject_placeholder_code(cleaned)
            validate_generated_tests(file_rel_path, cleaned, related_context)
            return cleaned
        except Exception as e:
            if isinstance(e, SyntaxError):
                diagnosis = f'The returned Python is invalid at line {e.lineno}, column {e.offset}: {e.msg}'
                guidance = 'Review the rejected output in the run log before retrying explicitly.'
            elif isinstance(e, ValueError):
                diagnosis = str(e)
                guidance = 'Review the model output and requested file scope before retrying explicitly.'
            else:
                diagnosis = str(e)
                guidance = 'Check the selected Ollama model and connection, then retry explicitly.'
            message = (f"Code generation failed for {file_rel_path}: {diagnosis}. "
                       f'{guidance} No placeholder was written for this file.')
            details = {'file': file_rel_path, 'mode': 'failed', 'error_type': type(e).__name__,
                       'done_reason': response_reason, 'rejected_output': raw[:16000],
                       'output_excerpt_truncated': len(raw) > 16000}
            if isinstance(e, SyntaxError):
                details.update(line=e.lineno, column=e.offset, source_line=(e.text or '')[:500])
            db_service.add_log(goal_model.run_id, 'coder', 'Coding Agent', 'error', message, details)
            raise RuntimeError(message) from e

    @staticmethod
    def template_kind(path, goal):
        path = path.replace('\\', '/')
        words = set(re.findall(r'\b[a-z0-9_]+\b', goal.lower()))
        if {'jwt', 'fastapi', 'login'} <= words and path in {
            'app/auth.py', 'app/routes/auth_routes.py', 'app/main.py', 'tests/test_auth.py'
        }:
            return 'FastAPI JWT login'
        if re.search(r'\b(?:connectionpool|connection pool)\b', goal, re.I) and re.search(r'\b(?:race|concurrency)\b', goal, re.I) and path in {
            'src/core/connection_pool.py', 'tests/test_pool_concurrency.py'
        }:
            return 'ConnectionPool concurrency'
        return None

    def _get_deterministic_code(self, file_rel_path: str, goal_model: GoalModel, original_content: Optional[str]) -> Optional[str]:
        norm_path = file_rel_path.replace("\\", "/")

        # 1. Login API / JWT Test Suite (Check first!)
        if "test_auth" in norm_path:
            return '''import pytest
from datetime import timedelta
from fastapi.testclient import TestClient
from app.main import app
from app.auth import USERS_DB, create_access_token

client = TestClient(app)

@pytest.fixture(autouse=True)
def clean_users_db():
    """Cleans in-memory user db before each test."""
    USERS_DB.clear()
    yield
    USERS_DB.clear()

def test_health_endpoint():
    """Verify health check endpoint returns 200."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_user_registration_success():
    """Verify successful user registration and JWT token issuance."""
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

def test_user_registration_duplicate_username_fails():
    """Verify duplicate username registration returns 400."""
    payload = {
        "username": "alex_dev",
        "email": "alex@example.com",
        "password": "Password123"
    }
    client.post("/api/auth/register", json=payload)
    dup_res = client.post("/api/auth/register", json=payload)
    assert dup_res.status_code == 400
    assert "already registered" in dup_res.json()["detail"]

def test_login_success():
    """Verify valid login returns 200 and access token."""
    client.post("/api/auth/register", json={
        "username": "johndoe",
        "email": "john@test.com",
        "password": "CorrectPassword456"
    })

    login_res = client.post("/api/auth/login", json={
        "username": "johndoe",
        "password": "CorrectPassword456"
    })
    assert login_res.status_code == 200
    assert "access_token" in login_res.json()
    assert login_res.json()["user"]["username"] == "johndoe"

def test_login_invalid_password_returns_401():
    """Verify invalid password returns 401 Unauthorized."""
    client.post("/api/auth/register", json={
        "username": "johndoe",
        "email": "john@test.com",
        "password": "CorrectPassword456"
    })

    login_res = client.post("/api/auth/login", json={
        "username": "johndoe",
        "password": "WrongPassword789"
    })
    assert login_res.status_code == 401
    assert "Invalid username or password" in login_res.json()["detail"]

def test_protected_route_access_with_valid_jwt():
    """Verify GET /api/auth/me returns user profile when Authorization Bearer token is passed."""
    reg_res = client.post("/api/auth/register", json={
        "username": "protected_user",
        "email": "protected@test.com",
        "password": "ValidPassword999"
    })
    token = reg_res.json()["access_token"]

    headers = {"Authorization": f"Bearer {token}"}
    me_res = client.get("/api/auth/me", headers=headers)
    assert me_res.status_code == 200
    assert me_res.json()["username"] == "protected_user"
    assert me_res.json()["email"] == "protected@test.com"

def test_protected_route_fails_without_token():
    """Verify GET /api/auth/me returns 401/403 when Authorization header is missing."""
    response = client.get("/api/auth/me")
    assert response.status_code in (401, 403)

def test_expired_jwt_token_fails():
    """Verify expired token returns 401."""
    expired_token = create_access_token(
        data={"sub": "expired_user", "email": "expired@test.com"},
        expires_delta=timedelta(seconds=-10)
    )
    headers = {"Authorization": f"Bearer {expired_token}"}
    response = client.get("/api/auth/me", headers=headers)
    assert response.status_code == 401
    assert "expired" in response.json()["detail"].lower()
'''

        # 2. Routes
        elif "routes/auth" in norm_path or "auth_routes" in norm_path:
            return '''from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, EmailStr
from typing import Optional, Dict, Any
from app.auth import (
    USERS_DB,
    hash_password,
    verify_password,
    create_access_token,
    get_current_user
)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

class RegisterRequest(BaseModel):
    username: str
    email: EmailStr
    password: str

class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 3600
    user: Dict[str, Any]

class UserProfileResponse(BaseModel):
    username: str
    email: str
    is_active: bool = True

@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=TokenResponse)
def register(req: RegisterRequest):
    """Registers a new user and returns JWT token."""
    if req.username in USERS_DB:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )
    
    hashed_pwd = hash_password(req.password)
    user_record = {
        "username": req.username,
        "email": req.email,
        "hashed_password": hashed_pwd,
        "is_active": True
    }
    USERS_DB[req.username] = user_record

    access_token = create_access_token(data={"sub": req.username, "email": req.email})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": 3600,
        "user": {"username": req.username, "email": req.email}
    }

@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest):
    """Authenticates user credentials and returns JWT bearer access token."""
    user = USERS_DB.get(req.username)
    if not user or not verify_password(req.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"}
        )

    access_token = create_access_token(data={"sub": user["username"], "email": user["email"]})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": 3600,
        "user": {"username": user["username"], "email": user["email"]}
    }

@router.get("/me", response_model=UserProfileResponse)
def get_user_profile(current_user: dict = Depends(get_current_user)):
    """Protected endpoint returning authenticated user profile."""
    return current_user
'''

        # 3. Core Auth utility
        elif norm_path.endswith("/auth.py") or norm_path == "auth.py" or "app/auth.py" in norm_path:
            return '''import os
import time
import hashlib
import hmac
import jwt
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from fastapi import HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# Secret key configuration with environment override
SECRET_KEY = os.environ.get("JWT_SECRET_KEY") or os.urandom(32).hex()
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

security = HTTPBearer()

# In-memory user store for demonstration & testing
USERS_DB: Dict[str, Dict[str, Any]] = {}

def hash_password(password: str, salt: Optional[str] = None) -> str:
    """Secure password hashing using SHA256 with cryptographic salt."""
    if not salt:
        salt = os.urandom(16).hex()
    hashed = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        100000
    ).hex()
    return f"{salt}${hashed}"

def verify_password(plain_password: str, stored_hash: str) -> bool:
    """Verifies a plain-text password against a salted PBKDF2-SHA256 hash."""
    try:
        salt, expected_hash = stored_hash.split("$")
        computed = hashlib.pbkdf2_hmac(
            'sha256',
            plain_password.encode('utf-8'),
            salt.encode('utf-8'),
            100000
        ).hex()
        return hmac.compare_digest(computed, expected_hash)
    except Exception:
        return False

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Encodes a signed JWT access token with expiration timestamp."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> dict:
    """Decodes and validates JWT token signature and expiry."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security)) -> Dict[str, Any]:
    """FastAPI Dependency for authenticating routes with JWT Bearer header."""
    token = credentials.credentials
    payload = decode_access_token(token)
    username: str = payload.get("sub")
    if username is None or username not in USERS_DB:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or credentials invalid",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = USERS_DB[username].copy()
    user.pop("hashed_password", None)
    return user
'''

        elif "app/main.py" in norm_path:
            return '''from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes.auth_routes import router as auth_router

app = FastAPI(
    title="Authentication Service API",
    description="Secure JWT Authentication API built by AgentEval-X Autonomous Coding Agent",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "auth_service", "version": "1.0.0"}
'''

        elif "tests/test_auth.py" in norm_path or "test_auth.py" in norm_path:
            return '''import pytest
from datetime import timedelta
from fastapi.testclient import TestClient
from app.main import app
from app.auth import USERS_DB, create_access_token

client = TestClient(app)

@pytest.fixture(autouse=True)
def clean_users_db():
    """Cleans in-memory user db before each test."""
    USERS_DB.clear()
    yield
    USERS_DB.clear()

def test_health_endpoint():
    """Verify health check endpoint returns 200."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_user_registration_success():
    """Verify successful user registration and JWT token issuance."""
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

def test_user_registration_duplicate_username_fails():
    """Verify duplicate username registration returns 400."""
    payload = {
        "username": "alex_dev",
        "email": "alex@example.com",
        "password": "Password123"
    }
    client.post("/api/auth/register", json=payload)
    dup_res = client.post("/api/auth/register", json=payload)
    assert dup_res.status_code == 400
    assert "already registered" in dup_res.json()["detail"]

def test_login_success():
    """Verify valid login returns 200 and access token."""
    # Register first
    client.post("/api/auth/register", json={
        "username": "johndoe",
        "email": "john@test.com",
        "password": "CorrectPassword456"
    })

    # Login
    login_res = client.post("/api/auth/login", json={
        "username": "johndoe",
        "password": "CorrectPassword456"
    })
    assert login_res.status_code == 200
    assert "access_token" in login_res.json()
    assert login_res.json()["user"]["username"] == "johndoe"

def test_login_invalid_password_returns_401():
    """Verify invalid password returns 401 Unauthorized."""
    client.post("/api/auth/register", json={
        "username": "johndoe",
        "email": "john@test.com",
        "password": "CorrectPassword456"
    })

    login_res = client.post("/api/auth/login", json={
        "username": "johndoe",
        "password": "WrongPassword789"
    })
    assert login_res.status_code == 401
    assert "Invalid username or password" in login_res.json()["detail"]

def test_protected_route_access_with_valid_jwt():
    """Verify GET /api/auth/me returns user profile when Authorization Bearer token is passed."""
    reg_res = client.post("/api/auth/register", json={
        "username": "protected_user",
        "email": "protected@test.com",
        "password": "ValidPassword999"
    })
    token = reg_res.json()["access_token"]

    headers = {"Authorization": f"Bearer {token}"}
    me_res = client.get("/api/auth/me", headers=headers)
    assert me_res.status_code == 200
    assert me_res.json()["username"] == "protected_user"
    assert me_res.json()["email"] == "protected@test.com"

def test_protected_route_fails_without_token():
    """Verify GET /api/auth/me returns 401/403 when Authorization header is missing."""
    response = client.get("/api/auth/me")
    assert response.status_code in (401, 403)

def test_expired_jwt_token_fails():
    """Verify expired token returns 401."""
    expired_token = create_access_token(
        data={"sub": "expired_user", "email": "expired@test.com"},
        expires_delta=timedelta(seconds=-10)
    )
    headers = {"Authorization": f"Bearer {expired_token}"}
    response = client.get("/api/auth/me", headers=headers)
    assert response.status_code == 401
    assert "expired" in response.json()["detail"].lower()
'''

        # 2. Concurrency ConnectionPool files
        elif "connection_pool.py" in norm_path:
            return '''import asyncio
import time
from typing import Set, Optional, Dict, Any

class ConnectionPool:
    def __init__(self, max_connections: int = 10):
        self.max_connections = max_connections
        self._pool: Set[int] = set()
        self._active: Set[int] = set()
        self._lock = asyncio.Lock()
        self._next_socket_id = 1

    async def acquire(self) -> int:
        """Acquires a socket handle atomically using asyncio.Lock."""
        async with self._lock:
            if self._pool:
                sock = self._pool.pop()
            else:
                if len(self._active) >= self.max_connections:
                    raise RuntimeError("ConnectionPool exhausted: max connections reached")
                sock = self._next_socket_id
                self._next_socket_id += 1
            
            self._active.add(sock)
            return sock

    async def release(self, socket_id: int):
        """Releases socket back into idle pool safely."""
        async with self._lock:
            if socket_id in self._active:
                self._active.remove(socket_id)
                self._pool.add(socket_id)

    @property
    def active_count(self) -> int:
        return len(self._active)

    @property
    def idle_count(self) -> int:
        return len(self._pool)
'''

        elif "test_pool_concurrency.py" in norm_path:
            return '''import pytest
import asyncio
from src.core.connection_pool import ConnectionPool

@pytest.mark.asyncio
async def test_concurrent_socket_acquisition():
    """Test 50 concurrent worker coroutines acquire and release sockets without race condition."""
    pool = ConnectionPool(max_connections=50)
    acquired_sockets = []
    all_acquired = asyncio.Event()

    async def worker():
        sock = await pool.acquire()
        acquired_sockets.append(sock)
        if len(acquired_sockets) == 50:
            all_acquired.set()
        await asyncio.wait_for(all_acquired.wait(), timeout=2)
        assert len(set(acquired_sockets)) == 50, "Duplicate simultaneously acquired socket"
        await pool.release(sock)

    tasks = [worker() for _ in range(50)]
    await asyncio.gather(*tasks)

    # Verify zero connection leaks and no duplicate active sockets
    assert pool.active_count == 0
    assert len(set(acquired_sockets)) == 50
    assert pool.idle_count == len(set(acquired_sockets))
'''

        # An unsupported task has no deterministic implementation.
        return None

coder_service = CoderService()
