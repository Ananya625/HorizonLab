import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from ..models.schema import (
    ImplementationPlan,
    PlannedFile,
    PlanStep,
    GoalModel
)
from .ollama_service import ollama_service
from .workspace_service import workspace_service
from .db import db_service

logger = logging.getLogger(__name__)

PLANNER_SYSTEM_PROMPT = """You are the Codebase Analyst + Principal Software Architect Agent for an autonomous software engineering system.

Your job is to inspect the existing codebase structure and the confirmed Goal Model / Requirements, and generate a precise, actionable, step-by-step Implementation Plan.

You must respond ONLY with a valid JSON object matching this schema:
{
  "architecture_overview": "Comprehensive technical summary of the architectural design, patterns, and component interactions",
  "tech_stack": {
    "framework": "e.g. FastAPI / Express / Flask",
    "language": "e.g. Python 3.11+ / TypeScript",
    "test_runner": "e.g. pytest / jest",
    "security_crypto": "e.g. PyJWT + passlib (bcrypt)"
  },
  "key_modules": ["module1", "module2"],
  "planned_files": [
    {
      "path": "app/auth.py",
      "action": "create", // "create", "modify", "delete", "test"
      "description": "JWT creation, token validation, password hashing and verification with bcrypt",
      "estimated_loc": 65
    }
  ],
  "steps": [
    {
      "step_number": 1,
      "title": "Clear action title",
      "description": "Exact implementation instructions, functions, and logic",
      "assigned_agent": "Coding Agent",
      "target_files": ["app/auth.py"],
      "dependencies": [],
      "expected_outcome": "Working utility with password hashing and JWT encoding/decoding"
    }
  ],
  "testing_strategy": "Concrete explanation of test suites, edge cases, and assertion checkpoints",
  "risk_assessment": "Key architectural risks (e.g. token expiration edge cases, secret exposure) and mitigation strategies"
}
"""

class PlannerService:
    async def generate_plan(
        self,
        run_id: str,
        repo_path: Optional[str] = None,
        model_name: Optional[str] = "qwen2.5-coder:7b",
        temperature: float = 0.2
    ) -> ImplementationPlan:
        goal_model = db_service.get_goal_model(run_id)
        if not goal_model:
            raise ValueError(f"Goal model for run_id '{run_id}' not found")

        target_repo = repo_path or workspace_service.get_default_repo_path()
        inspection = workspace_service.inspect_directory(target_repo)

        db_service.add_log(
            run_id=run_id,
            stage="planner",
            agent_role="Codebase Analyst Agent",
            event_type="tool_call",
            message=f"Scanned repository tree at '{target_repo}': found {inspection['total_files']} files, {inspection['total_lines_of_code']} LoC.",
            details={"inspection": inspection}
        )

        user_prompt = f"""Target Repository Inspection:
- Path: {target_repo}
- Detected Languages: {', '.join(inspection['detected_languages'])}
- Test Framework: {inspection['test_framework']}
- Total Existing Files: {inspection['total_files']}
- Existing Files List: {[f['path'] for f in inspection['files']]}

Goal Model Requirements:
- Main Goal: {goal_model.main_goal}
- Summary: {goal_model.summary}
- Sub-Goals: {[sg.title for sg in goal_model.sub_goals]}
- Hard Constraints: {[hc.text for hc in goal_model.hard_constraints]}
- Soft Constraints: {[sc.text for sc in goal_model.soft_constraints]}
- Acceptance Criteria: {[sc.metric for sc in goal_model.success_criteria]}

Generate the detailed Implementation Plan JSON for the Coding Agent."""

        messages = [
            {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ]

        parsed_plan = None
        try:
            resp = await ollama_service.chat_completion(
                messages=messages,
                model=model_name,
                temperature=temperature,
                format_json=True
            )
            raw_content = resp.get("message", {}).get("content", "")
            if raw_content:
                parsed_plan = ollama_service.extract_json_object(raw_content)
        except Exception as e:
            logger.warning(f"Ollama planning failed ({e}), generating deterministic high-precision plan")

        if not parsed_plan or "planned_files" not in parsed_plan:
            parsed_plan = self._generate_heuristic_plan(goal_model, target_repo, inspection)

        planned_files = [PlannedFile(**pf) for pf in parsed_plan.get("planned_files", [])]
        steps = [PlanStep(**s) for s in parsed_plan.get("steps", [])]

        plan = ImplementationPlan(
            run_id=run_id,
            architecture_overview=parsed_plan.get("architecture_overview", "Modular architecture with isolated authentication service, secure token issuance, and dedicated test suite."),
            target_repo_path=target_repo,
            tech_stack=parsed_plan.get("tech_stack", {"framework": "FastAPI", "language": "Python 3.11+", "auth": "PyJWT", "crypto": "passlib[bcrypt]", "test_runner": "pytest"}),
            key_modules=parsed_plan.get("key_modules", ["app.auth", "app.routes.auth", "tests.test_auth"]),
            planned_files=planned_files,
            steps=steps,
            testing_strategy=parsed_plan.get("testing_strategy", "Automated pytest suite validating user registration, successful token generation, invalid password rejection (401), expired token rejection, and protected endpoint access."),
            risk_assessment=parsed_plan.get("risk_assessment", "Potential risks: Hardcoded secrets (mitigated by environment variable fallback), weak password hashing (mitigated by bcrypt work factor 12)."),
            created_at=datetime.now().isoformat()
        )

        db_service.save_plan(plan)

        db_service.add_log(
            run_id=run_id,
            stage="planner",
            agent_role="Planner Agent",
            event_type="success",
            message=f"Generated Implementation Plan with {len(planned_files)} target files and {len(steps)} sequential execution steps.",
            details={"steps_count": len(steps), "files_count": len(planned_files)}
        )

        return plan

    def _generate_heuristic_plan(self, goal_model: GoalModel, repo_path: str, inspection: Dict[str, Any]) -> Dict[str, Any]:
        prompt_lower = (goal_model.original_request + " " + goal_model.main_goal).lower()
        
        if "login" in prompt_lower or "jwt" in prompt_lower or "auth" in prompt_lower:
            return {
                "architecture_overview": "FastAPI JWT Authentication Subsystem: Implements secure password hashing via bcrypt, JWT access token generation & verification using HS256, user database storage abstraction, and OAuth2 bearer token route protection.",
                "tech_stack": {
                    "framework": "FastAPI",
                    "language": "Python 3.11+",
                    "crypto": "passlib[bcrypt] / hashlib",
                    "tokens": "PyJWT (HS256)",
                    "test_runner": "pytest + httpx"
                },
                "key_modules": ["app.auth", "app.routes.auth_routes", "app.main", "tests.test_auth"],
                "planned_files": [
                    {
                        "path": "app/auth.py",
                        "action": "create",
                        "description": "Password hashing, password verification, JWT creation with expiration, and token decoding helper functions.",
                        "estimated_loc": 75
                    },
                    {
                        "path": "app/routes/auth_routes.py",
                        "action": "create",
                        "description": "API endpoints: POST /api/auth/register, POST /api/auth/login, and GET /api/auth/me (protected route).",
                        "estimated_loc": 90
                    },
                    {
                        "path": "app/main.py",
                        "action": "modify",
                        "description": "Include auth router in main FastAPI application and register global error handlers.",
                        "estimated_loc": 35
                    },
                    {
                        "path": "tests/test_auth.py",
                        "action": "test",
                        "description": "Comprehensive pytest suite testing registration, login success, invalid credentials (401), expired tokens, and protected route access.",
                        "estimated_loc": 110
                    }
                ],
                "steps": [
                    {
                        "step_number": 1,
                        "title": "Implement Core Cryptography & JWT Token Utilities",
                        "description": "Create 'app/auth.py' with bcrypt password hashing, secure token generation with configurable SECRET_KEY, and token payload validation.",
                        "assigned_agent": "Coding Agent",
                        "target_files": ["app/auth.py"],
                        "dependencies": [],
                        "expected_outcome": "Cryptographic functions pass unit verification"
                    },
                    {
                        "step_number": 2,
                        "title": "Implement Authentication REST Endpoints",
                        "description": "Create 'app/routes/auth_routes.py' with login and registration endpoints returning JWT bearer tokens.",
                        "assigned_agent": "Coding Agent",
                        "target_files": ["app/routes/auth_routes.py"],
                        "dependencies": [1],
                        "expected_outcome": "FastAPI APIRouter with typed request/response schemas"
                    },
                    {
                        "step_number": 3,
                        "title": "Wire Auth Router into FastAPI Main Application",
                        "description": "Update 'app/main.py' to attach router and configure CORS and exception handlers.",
                        "assigned_agent": "Coding Agent",
                        "target_files": ["app/main.py"],
                        "dependencies": [2],
                        "expected_outcome": "Main app exposes /api/auth endpoints"
                    },
                    {
                        "step_number": 4,
                        "title": "Author Deterministic Automated Pytest Suite",
                        "description": "Create 'tests/test_auth.py' using FastAPI TestClient to verify registration, login with valid/invalid credentials, and token bearer authentication.",
                        "assigned_agent": "Coding Agent",
                        "target_files": ["tests/test_auth.py"],
                        "dependencies": [3],
                        "expected_outcome": "Automated test suite ready for execution by Test Runner Agent"
                    }
                ],
                "testing_strategy": "Run pytest tests/test_auth.py verifying HTTP 200 on valid credentials, HTTP 401 on incorrect password, HTTP 401 on missing bearer token, and HTTP 200 on /me with valid token.",
                "risk_assessment": "Ensure SECRET_KEY fallback is provided for test environment and password hashing handles salting properly."
            }
        elif "concurrency" in prompt_lower or "race" in prompt_lower or "pool" in prompt_lower:
            return {
                "architecture_overview": "Thread-safe and Asyncio-safe Connection Pool: Implements mutual exclusion lock around socket acquisition, connection state tracking, and leak-free resource release.",
                "tech_stack": {"language": "Python", "concurrency": "asyncio.Lock", "test_runner": "pytest-asyncio"},
                "key_modules": ["src.core.connection_pool", "tests.test_pool_concurrency"],
                "planned_files": [
                    {
                        "path": "src/core/connection_pool.py",
                        "action": "modify",
                        "description": "Implement asyncio.Lock around socket acquisition while maintaining zero-allocation fast-path for idle connections.",
                        "estimated_loc": 95
                    },
                    {
                        "path": "tests/test_pool_concurrency.py",
                        "action": "test",
                        "description": "Deterministic pytest reproduction test spawning 50 concurrent worker coroutines under peak contention.",
                        "estimated_loc": 85
                    }
                ],
                "steps": [
                    {
                        "step_number": 1,
                        "title": "Write Concurrency Reproduction Test",
                        "description": "Create 'tests/test_pool_concurrency.py' reproducing race condition under 50 simultaneous worker coroutines.",
                        "assigned_agent": "Coding Agent",
                        "target_files": ["tests/test_pool_concurrency.py"],
                        "dependencies": [],
                        "expected_outcome": "Deterministic test reproduces race condition"
                    },
                    {
                        "step_number": 2,
                        "title": "Implement Async Mutual Exclusion in ConnectionPool",
                        "description": "Protect socket pool allocation with asyncio.Lock, ensuring atomicity and zero unclosed socket leaks.",
                        "assigned_agent": "Coding Agent",
                        "target_files": ["src/core/connection_pool.py"],
                        "dependencies": [1],
                        "expected_outcome": "Thread-safe connection pool"
                    }
                ],
                "testing_strategy": "Execute pytest tests/test_pool_concurrency.py to ensure 0 duplicate socket allocations and 0 socket leaks.",
                "risk_assessment": "Ensure lock contention does not cause throughput bottlenecks."
            }
        else:
            return {
                "architecture_overview": f"Modular Architecture for '{goal_model.main_goal}': Implements required domain logic, service layer, and comprehensive test suite.",
                "tech_stack": {"language": "Python 3.11+", "test_runner": "pytest"},
                "key_modules": ["app.service", "tests.test_service"],
                "planned_files": [
                    {
                        "path": "app/service.py",
                        "action": "create",
                        "description": "Core business logic and service methods fulfilling the task requirements.",
                        "estimated_loc": 80
                    },
                    {
                        "path": "tests/test_service.py",
                        "action": "test",
                        "description": "Unit and integration tests validating all acceptance criteria.",
                        "estimated_loc": 90
                    }
                ],
                "steps": [
                    {
                        "step_number": 1,
                        "title": "Implement Core Service Logic",
                        "description": "Create service implementation matching all functional requirements.",
                        "assigned_agent": "Coding Agent",
                        "target_files": ["app/service.py"],
                        "dependencies": [],
                        "expected_outcome": "Implemented service module"
                    },
                    {
                        "step_number": 2,
                        "title": "Create Automated Test Suite",
                        "description": "Author pytest test suite covering nominal and edge cases.",
                        "assigned_agent": "Coding Agent",
                        "target_files": ["tests/test_service.py"],
                        "dependencies": [1],
                        "expected_outcome": "100% test pass verification"
                    }
                ],
                "testing_strategy": "Run pytest on the test suite to verify all acceptance criteria.",
                "risk_assessment": "Ensure edge cases and error conditions are handled cleanly."
            }

planner_service = PlannerService()
