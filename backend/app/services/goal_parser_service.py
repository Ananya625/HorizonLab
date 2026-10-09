import json
import logging
import re
from datetime import datetime
from typing import Dict, Any, Optional, List
from ..models.goal_model import (
    GoalModel, SubGoal, SuccessCriterion, Constraint, ExpectedOutput, Ambiguity, AuditEntry
)
from .ollama_service import ollama_service
from .storage_service import storage_service

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are the Goal Model & Requirement Interpreter for AgentEval-X, an advanced evaluation, goal governance, and closed-loop recovery platform specifically for CODING AGENTS and Software Engineering tasks.

Your mission is to translate an unstructured natural language software engineering / coding task (e.g. bug fixing, codebase refactoring, feature implementation, security vulnerability patching, API modernization) into an explicit, structured, reviewable, and verifiable Goal Model before code execution begins.

You must respond ONLY with a valid JSON object matching the following structure:
{
  "summary": "Concise 1-2 sentence engineering summary of the required code modification and verification",
  "main_goal": "Single explicit, human-readable primary engineering objective",
  "detected_language": "en / es / fr / de / hi / zh / etc.",
  "normalized_request": "Cleaned, standardized technical English version of the request",
  "sub_goals": [
    {
      "id": "SG-1",
      "title": "Clear actionable engineering title e.g. 'Isolate Failure and Write Reproduction Test'",
      "description": "Detailed explanation of code changes, files to touch, and required logic",
      "order": 1,
      "priority": "high",  // "high", "medium", or "low"
      "assigned_agent_role": "Code Architect Agent / Implementation Agent / Test & Verification Agent / Security Auditor Agent",
      "dependencies": []   // e.g. ["SG-1"] for SG-2
    }
  ],
  "success_criteria": [
    {
      "id": "SC-1",
      "sub_goal_id": "SG-1",
      "description": "Concrete measurable code condition or test execution result",
      "metric": "pytest tests/test_concurrency.py == PASS / 0 unclosed sockets / Bandit score == 0 alerts",
      "verification_method": "automated_test", // "automated_test", "diff_inspection", "schema_validation", "state_ledger_check", "ast_check"
      "expected_output": "Description of code patch, test file, or benchmark report"
    }
  ],
  "hard_constraints": [
    {
      "id": "HC-1",
      "text": "Strict rule that MUST NEVER be violated (e.g. 'Do not break existing public API signatures', 'Never delete production tests', 'No plain-text credentials in code')",
      "category": "safety" // "safety", "budget", "security", "resource", "temporal"
    }
  ],
  "soft_constraints": [
    {
      "id": "SC-1",
      "text": "Code quality preference or architectural guideline (e.g. 'Follow PEP 8 formatting', 'Ensure memory usage under 256MB')",
      "category": "performance" // "performance", "style", "cost", "preference"
    }
  ],
  "expected_output": {
    "format": "Unified Git Diff & Test Execution Report",
    "schema_summary": "Modified files list, line diffs, passing test logs, AST validity status",
    "delivery_target": "Repository Worktree & Execution Ledger"
  },
  "ambiguities": [
    {
      "id": "AMB-1",
      "question": "Specific clarification question regarding missing engineering requirements, edge cases, test frameworks, or backward compatibility",
      "context": "Why this ambiguity needs clarification before coding starts",
      "severity": "blocking", // "blocking" if execution cannot safely proceed without human answer, or "non_blocking"
      "suggested_options": ["Option A description", "Option B description", "Option C description"],
      "default_assumption": "What assumption will be used if user does not specify"
    }
  ]
}

CRITICAL RULES FOR CODING AGENTS:
1. Always partition sub-goals into logical engineering phases (e.g. 1. Analysis/Reproduction, 2. Core Implementation/Refactoring, 3. Regression Testing & Static Verification).
2. Hard constraints must protect against code regression, unauthorized file deletion, security leaks (CWE), and broken public interfaces.
3. Every sub-goal must have at least one measurable success criterion verifiable via automated test runner, diff check, or static analysis.
4. Ambiguities: If target runtime version, minimum test coverage threshold, or backward compatibility policies are unspecified, generate 1-3 clarification questions with 'blocking' or 'non_blocking' severity.
5. Return RAW JSON ONLY. No conversational commentary.
"""

class GoalParserService:
    async def parse_request(
        self,
        request_text: str,
        model_name: Optional[str] = "qwen2.5-coder:7b",
        run_id: Optional[str] = None,
        language: Optional[str] = "auto",
        temperature: float = 0.2
    ) -> GoalModel:
        if not run_id:
            run_id = storage_service.generate_run_id()
        task_id = storage_service.generate_task_id()

        user_message = f"""Software Engineering Task for Coding Agent:
\"\"\"{request_text}\"\"\"

Analyze this coding request and generate the complete structured AgentEval-X Goal Model JSON."""

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message}
        ]

        parsed_data = None
        used_fallback = False

        # Attempt to call Ollama
        try:
            resp = await ollama_service.chat_completion(
                messages=messages,
                model=model_name,
                temperature=temperature,
                format_json=True
            )
            raw_content = resp.get("message", {}).get("content", "")
            if raw_content:
                parsed_data = ollama_service.extract_json_object(raw_content)
        except Exception as e:
            logger.warning(f"Ollama parsing failed or unavailable ({e}), using intelligent coding agent heuristic parser")
            used_fallback = True

        if not parsed_data:
            parsed_data = self._generate_heuristic_goal_model(request_text)

        # Build GoalModel object
        sub_goals = [SubGoal(**sg) for sg in parsed_data.get("sub_goals", [])]
        success_criteria = [SuccessCriterion(**sc) for sc in parsed_data.get("success_criteria", [])]
        
        hard_constraints = [
            Constraint(id=hc.get("id", f"HC-{i+1}"), text=hc.get("text", ""), category=hc.get("category", "safety"), is_hard=True)
            for i, hc in enumerate(parsed_data.get("hard_constraints", []))
        ]
        
        soft_constraints = [
            Constraint(id=sc.get("id", f"SC-{i+1}"), text=sc.get("text", ""), category=sc.get("category", "preference"), is_hard=False)
            for i, sc in enumerate(parsed_data.get("soft_constraints", []))
        ]

        expected_output = ExpectedOutput(**parsed_data.get("expected_output", {}))
        
        ambiguities = [
            Ambiguity(
                id=amb.get("id", f"AMB-{i+1}"),
                question=amb.get("question", ""),
                context=amb.get("context", ""),
                severity=amb.get("severity", "blocking"),
                suggested_options=amb.get("suggested_options", []),
                default_assumption=amb.get("default_assumption", "")
            )
            for i, amb in enumerate(parsed_data.get("ambiguities", []))
        ]

        now = datetime.now().isoformat()
        audit_history = [
            AuditEntry(
                version="1.0",
                timestamp=now,
                change_summary=f"Initial Goal Model parsed for Coding Agent via {'Ollama (' + str(model_name) + ')' if not used_fallback else 'Coding Heuristic Engine'}",
                modified_fields=["main_goal", "sub_goals", "success_criteria", "hard_constraints", "soft_constraints", "ambiguities"],
                author="system"
            )
        ]

        goal_model = GoalModel(
            task_id=task_id,
            run_id=run_id,
            original_request=request_text,
            normalized_request=parsed_data.get("normalized_request", request_text),
            detected_language=parsed_data.get("detected_language", "en"),
            goal_model_version="1.0",
            main_goal=parsed_data.get("main_goal", "Execute coding task with verified correctness and zero regressions"),
            summary=parsed_data.get("summary", "Automated code modification, regression testing, and static analysis verification plan."),
            sub_goals=sub_goals,
            success_criteria=success_criteria,
            hard_constraints=hard_constraints,
            soft_constraints=soft_constraints,
            expected_output=expected_output,
            ambiguities=ambiguities,
            is_confirmed=False,
            created_at=now,
            updated_at=now,
            audit_history=audit_history
        )

        from .db import db_service
        from .workspace_service import workspace_service

        db_service.create_or_update_run(
            run_id=run_id,
            task_id=task_id,
            title=request_text[:80],
            prompt=request_text,
            repo_path=workspace_service.get_default_repo_path(),
            current_stage="requirement",
            status="in_progress"
        )

        storage_service.save_goal_model(goal_model)

        db_service.add_log(
            run_id=run_id,
            stage="requirement",
            agent_role="Requirement Analyst",
            event_type="success",
            message=f"Parsed Goal Model v1.0 with {len(sub_goals)} sub-goals, {len(success_criteria)} acceptance criteria, and {len(hard_constraints)} hard constraints.",
            details={"model": model_name, "fallback": used_fallback}
        )
        return goal_model

    def patch_goal_model(
        self,
        run_id: str,
        patch_data: Dict[str, Any],
        change_summary: str = "User edited goal model"
    ) -> GoalModel:
        model = storage_service.get_goal_model(run_id)
        if not model:
            raise ValueError(f"Run ID {run_id} not found")

        modified_fields = []
        for key, value in patch_data.items():
            if value is not None and hasattr(model, key):
                setattr(model, key, value)
                modified_fields.append(key)

        # Bump version number (e.g. 1.0 -> 1.1 or 1.1 -> 1.2)
        try:
            major, minor = model.goal_model_version.split(".")
            new_version = f"{major}.{int(minor) + 1}"
        except Exception:
            new_version = f"{model.goal_model_version}.1"

        model.goal_model_version = new_version
        now = datetime.now().isoformat()
        model.updated_at = now

        model.audit_history.append(
            AuditEntry(
                version=new_version,
                timestamp=now,
                change_summary=change_summary,
                modified_fields=modified_fields,
                author="user"
            )
        )

        storage_service.save_goal_model(model)
        return model

    def resolve_ambiguity(
        self,
        run_id: str,
        ambiguity_id: str,
        user_answer: str,
        apply_as_constraint: bool = True,
        constraint_type: str = "hard"
    ) -> GoalModel:
        model = storage_service.get_goal_model(run_id)
        if not model:
            raise ValueError(f"Run ID {run_id} not found")

        target_amb = None
        for amb in model.ambiguities:
            if amb.id == ambiguity_id:
                amb.resolved = True
                amb.user_answer = user_answer
                amb.resolved_at = datetime.now().isoformat()
                target_amb = amb
                break

        if not target_amb:
            raise ValueError(f"Ambiguity {ambiguity_id} not found")

        # Append answer into constraints to keep Goal Model mathematically sound
        if apply_as_constraint:
            constraint_id = f"HC-RESOLVED-{ambiguity_id}" if constraint_type == "hard" else f"SC-RESOLVED-{ambiguity_id}"
            new_constraint = Constraint(
                id=constraint_id,
                text=f"[Engineering Decision on {target_amb.question}]: {user_answer}",
                category="clarification_policy",
                is_hard=(constraint_type == "hard")
            )
            if constraint_type == "hard":
                model.hard_constraints.append(new_constraint)
            else:
                model.soft_constraints.append(new_constraint)

        return self.patch_goal_model(
            run_id=run_id,
            patch_data={
                "ambiguities": model.ambiguities,
                "hard_constraints": model.hard_constraints,
                "soft_constraints": model.soft_constraints
            },
            change_summary=f"Resolved clarification {ambiguity_id}: '{user_answer}'"
        )

    def confirm_goal_model(self, run_id: str) -> GoalModel:
        model = storage_service.get_goal_model(run_id)
        if not model:
            raise ValueError(f"Run ID {run_id} not found")

        # Check for unresolved blocking ambiguities
        unresolved_blocking = [a for a in model.ambiguities if a.severity == "blocking" and not a.resolved]
        if unresolved_blocking:
            raise ValueError(f"Cannot confirm Goal Model: {len(unresolved_blocking)} blocking clarification questions must be answered first.")

        model.is_confirmed = True
        model.confirmed_at = datetime.now().isoformat()
        
        try:
            major, minor = model.goal_model_version.split(".")
            new_version = f"{int(major) + 1}.0-locked"
        except Exception:
            new_version = "2.0-locked"

        model.goal_model_version = new_version
        now = datetime.now().isoformat()
        model.updated_at = now
        model.audit_history.append(
            AuditEntry(
                version=new_version,
                timestamp=now,
                change_summary="Goal Model confirmed and locked by human operator for Coding Agent execution",
                modified_fields=["is_confirmed", "confirmed_at"],
                author="user"
            )
        )

        storage_service.save_goal_model(model)
        return model

    def _generate_heuristic_goal_model(self, text: str) -> Dict[str, Any]:
        """Intelligent semantic fallback generator specialized for Coding Agent tasks."""
        lower = text.lower()
        
        # Scenario 1: Bug Fix & Concurrency Race Condition
        if any(w in lower for w in ["race condition", "concurrency", "lock", "deadlock", "socket", "pool", "asyncio", "thread"]):
            return {
                "summary": "Reproduce intermittent socket race condition in ConnectionPool, implement thread-safe mutual exclusion with asyncio.Lock, and verify 0 socket leaks.",
                "main_goal": "Resolve concurrent socket acquisition race condition in ConnectionPool while preserving zero-allocation fast path and public API compatibility.",
                "detected_language": "en",
                "normalized_request": text.strip(),
                "sub_goals": [
                    {
                        "id": "SG-1",
                        "title": "Author Deterministic Reproduction Test Case",
                        "description": "Create 'tests/test_pool_concurrency.py' with 50 concurrent worker coroutines to deterministically trigger double-acquisition under load.",
                        "order": 1,
                        "priority": "high",
                        "assigned_agent_role": "Test & Verification Agent",
                        "dependencies": []
                    },
                    {
                        "id": "SG-2",
                        "title": "Implement Thread-Safe Mutex in Connection Acquisition",
                        "description": "Modify 'src/core/connection_pool.py' to guard socket checkout with asyncio.Lock and atomic state transitions.",
                        "order": 2,
                        "priority": "high",
                        "assigned_agent_role": "Implementation Agent",
                        "dependencies": ["SG-1"]
                    },
                    {
                        "id": "SG-3",
                        "title": "Run Full Regression Suite and Leak Detector",
                        "description": "Execute pytest test suite with asyncio debug mode enabled and verify 0 resource warnings or unclosed sockets.",
                        "order": 3,
                        "priority": "high",
                        "assigned_agent_role": "Verification Agent",
                        "dependencies": ["SG-2"]
                    }
                ],
                "success_criteria": [
                    {
                        "id": "SC-1",
                        "sub_goal_id": "SG-1",
                        "description": "Reproduction test fails reliably against unpatched code (Exit code != 0)",
                        "metric": "pytest tests/test_pool_concurrency.py == FAIL (Pre-fix)",
                        "verification_method": "automated_test",
                        "expected_output": "Reproduction test trace showing Assertion or SocketConflict error"
                    },
                    {
                        "id": "SC-2",
                        "sub_goal_id": "SG-2",
                        "description": "Reproduction test passes cleanly with patch applied (100% pass over 50 iterations)",
                        "metric": "pytest tests/test_pool_concurrency.py == PASS (Post-fix)",
                        "verification_method": "automated_test",
                        "expected_output": "Passing test execution output with 0 socket collision errors"
                    },
                    {
                        "id": "SC-3",
                        "sub_goal_id": "SG-3",
                        "description": "Full unit test suite passes with 0 regressions and 0 unclosed socket warnings",
                        "metric": "pytest tests/ == 100% PASS, ResourceWarning count == 0",
                        "verification_method": "automated_test",
                        "expected_output": "Complete test suite report"
                    }
                ],
                "hard_constraints": [
                    {
                        "id": "HC-1",
                        "text": "Must not modify or remove existing public method signatures on ConnectionPool (acquire, release, close)",
                        "category": "safety"
                    },
                    {
                        "id": "HC-2",
                        "text": "Never delete or weaken existing unit test assertions in 'tests/'",
                        "category": "safety"
                    },
                    {
                        "id": "HC-3",
                        "text": "Acquisition latency overhead for idle cached connections must not exceed 0.5ms",
                        "category": "temporal"
                    }
                ],
                "soft_constraints": [
                    {
                        "id": "SC-1",
                        "text": "Maintain type annotations compatible with mypy --strict",
                        "category": "style"
                    },
                    {
                        "id": "SC-2",
                        "text": "Add docstring explaining lock acquisition order to prevent future deadlocks",
                        "category": "preference"
                    }
                ],
                "expected_output": {
                    "format": "Unified Git Diff & Pytest Execution Log",
                    "schema_summary": "Diff of src/core/connection_pool.py and tests/test_pool_concurrency.py with test execution timestamps",
                    "delivery_target": "Repository Worktree"
                },
                "ambiguities": [
                    {
                        "id": "AMB-1",
                        "question": "Should connection acquisition timeout raise a custom ConnectionTimeoutError or standard asyncio.TimeoutError?",
                        "context": "Exception type determines whether downstream consumer exception handlers catch the error properly.",
                        "severity": "blocking",
                        "suggested_options": ["Raise custom ConnectionTimeoutError (inherits from PoolError)", "Raise built-in asyncio.TimeoutError", "Support both with custom subclass"],
                        "default_assumption": "Raise custom ConnectionTimeoutError inheriting from PoolError"
                    },
                    {
                        "id": "AMB-2",
                        "question": "What is the maximum allowed pool connection capacity before queued coroutines are rejected?",
                        "context": "Pool capacity limits impact memory footprint under high concurrency bursts.",
                        "severity": "non_blocking",
                        "suggested_options": ["Max 20 connections", "Max 50 connections", "Max 100 connections (configurable via env var)"],
                        "default_assumption": "Max 50 connections (configurable via POOL_MAX_SIZE)"
                    }
                ]
            }

        # Scenario 2: Refactoring & Architecture / Async Migration
        if any(w in lower for w in ["refactor", "async", "sqlalchemy", "orm", "repository", "sqlite", "migration"]):
            return {
                "summary": "Refactor legacy synchronous database layer into asynchronous SQLAlchemy 2.0 repositories with connection pooling.",
                "main_goal": "Migrate database operations to async SQLAlchemy 2.0 preserving repository interfaces, type safety, and <= 256MB memory.",
                "detected_language": "en",
                "normalized_request": text.strip(),
                "sub_goals": [
                    {
                        "id": "SG-1",
                        "title": "Define Async SQLAlchemy Models and Engine Configuration",
                        "description": "Create async engine using create_async_engine, async_sessionmaker, and modern DeclarativeBase.",
                        "order": 1,
                        "priority": "high",
                        "assigned_agent_role": "Code Architect Agent",
                        "dependencies": []
                    },
                    {
                        "id": "SG-2",
                        "title": "Implement Async Repository Classes",
                        "description": "Refactor 'src/storage/repositories/' methods (find_by_id, insert, update, batch_query) with async/await coroutines.",
                        "order": 2,
                        "priority": "high",
                        "assigned_agent_role": "Implementation Agent",
                        "dependencies": ["SG-1"]
                    },
                    {
                        "id": "SG-3",
                        "title": "Migrate Test Suite to pytest-asyncio and Validate Coverage",
                        "description": "Update existing test fixtures to async fixtures, verify 100% test pass rate and branch coverage >= 90%.",
                        "order": 3,
                        "priority": "high",
                        "assigned_agent_role": "Test & Verification Agent",
                        "dependencies": ["SG-2"]
                    }
                ],
                "success_criteria": [
                    {
                        "id": "SC-1",
                        "sub_goal_id": "SG-1",
                        "description": "Async database session initializes and passes connection ping test",
                        "metric": "SELECT 1 executed via async engine == 1",
                        "verification_method": "automated_test",
                        "expected_output": "Async engine test report"
                    },
                    {
                        "id": "SC-2",
                        "sub_goal_id": "SG-2",
                        "description": "All CRUD repository operations complete without blocking event loop",
                        "metric": "pytest tests/storage/ == 100% PASS",
                        "verification_method": "automated_test",
                        "expected_output": "Repository test suite report"
                    },
                    {
                        "id": "SC-3",
                        "sub_goal_id": "SG-3",
                        "description": "Branch coverage meets or exceeds 90% threshold",
                        "metric": "pytest-cov branch coverage >= 90%",
                        "verification_method": "automated_test",
                        "expected_output": "Coverage HTML/XML artifact"
                    }
                ],
                "hard_constraints": [
                    {
                        "id": "HC-1",
                        "text": "Never introduce synchronous blocking I/O calls inside async coroutines",
                        "category": "performance"
                    },
                    {
                        "id": "HC-2",
                        "text": "Total process memory usage during 10,000 record batch migration must remain below 256MB",
                        "category": "resource"
                    },
                    {
                        "id": "HC-3",
                        "text": "Do not break existing domain entity return types or field names",
                        "category": "safety"
                    }
                ],
                "soft_constraints": [
                    {
                        "id": "SC-1",
                        "text": "Use yield statement within async context managers for automatic session rollback on error",
                        "category": "preference"
                    },
                    {
                        "id": "SC-2",
                        "text": "Format all modified files using Ruff or Black with line length 100",
                        "category": "style"
                    }
                ],
                "expected_output": {
                    "format": "Unified Git Diff & Async Coverage Report",
                    "schema_summary": "Updated repository files, async model definitions, and pytest-cov summary",
                    "delivery_target": "Repository Worktree"
                },
                "ambiguities": [
                    {
                        "id": "AMB-1",
                        "question": "Which database async driver should be used as the default engine (asyncpg for PostgreSQL or aiosqlite for SQLite)?",
                        "context": "Determines driver dependencies in pyproject.toml / requirements.txt.",
                        "severity": "blocking",
                        "suggested_options": ["aiosqlite (for local dev & SQLite tests)", "asyncpg (for production PostgreSQL)", "Dual configuration via environment variable"],
                        "default_assumption": "Dual configuration: aiosqlite for local tests, asyncpg for PostgreSQL"
                    }
                ]
            }

        # Scenario 3: Security Remediation & Vulnerability Patching
        if any(w in lower for w in ["security", "vulnerability", "cwe", "sqli", "injection", "sanitize", "bandit", "traversal"]):
            return {
                "summary": "Remediate CWE-89 SQL Injection and CWE-22 Path Traversal vulnerabilities in API routes and utility modules.",
                "main_goal": "Patch security vulnerabilities using parameterized queries and strict path resolution with clean static analysis.",
                "detected_language": "en",
                "normalized_request": text.strip(),
                "sub_goals": [
                    {
                        "id": "SG-1",
                        "title": "Audit and Replace Raw String Query Interpolations",
                        "description": "Locate dynamic SQL in 'src/api/routes/reports.py' and replace with parameterized queries to eliminate CWE-89.",
                        "order": 1,
                        "priority": "high",
                        "assigned_agent_role": "Security Auditor Agent",
                        "dependencies": []
                    },
                    {
                        "id": "SG-2",
                        "title": "Sanitize and Jail File Path Operations",
                        "description": "Update 'src/utils/file_manager.py' using os.path.realpath and base directory boundary checks to eliminate CWE-22.",
                        "order": 2,
                        "priority": "high",
                        "assigned_agent_role": "Implementation Agent",
                        "dependencies": ["SG-1"]
                    },
                    {
                        "id": "SG-3",
                        "title": "Add Exploit Regression Tests and Run Bandit AST Scanner",
                        "description": "Write security test suite attempting payload injection and verify Bandit scanner outputs 0 High/Medium alerts.",
                        "order": 3,
                        "priority": "high",
                        "assigned_agent_role": "Test & Verification Agent",
                        "dependencies": ["SG-2"]
                    }
                ],
                "success_criteria": [
                    {
                        "id": "SC-1",
                        "sub_goal_id": "SG-1",
                        "description": "Zero raw SQL string concatenations or format strings detected in repository",
                        "metric": "Bandit B608 (SQL Injection) == 0 alerts",
                        "verification_method": "ast_check",
                        "expected_output": "Bandit AST scan report"
                    },
                    {
                        "id": "SC-2",
                        "sub_goal_id": "SG-2",
                        "description": "Attempted path traversal attacks (e.g. '../../etc/passwd') strictly raise PermissionError",
                        "metric": "pytest tests/test_security_traversal.py == 100% PASS",
                        "verification_method": "automated_test",
                        "expected_output": "Security exploit regression test log"
                    },
                    {
                        "id": "SC-3",
                        "sub_goal_id": "SG-3",
                        "description": "All standard business logic routes continue passing without functional regressions",
                        "metric": "pytest tests/api/ == 100% PASS",
                        "verification_method": "automated_test",
                        "expected_output": "API test suite pass confirmation"
                    }
                ],
                "hard_constraints": [
                    {
                        "id": "HC-1",
                        "text": "Never expose raw database stack traces or internal server error messages in API JSON responses",
                        "category": "security"
                    },
                    {
                        "id": "HC-2",
                        "text": "Never use shell=True or unescaped subprocess executions",
                        "category": "security"
                    },
                    {
                        "id": "HC-3",
                        "text": "Do not delete or weaken any existing functional test assertions",
                        "category": "safety"
                    }
                ],
                "soft_constraints": [
                    {
                        "id": "SC-1",
                        "text": "Log all blocked path traversal attempts with masked IP to security audit log",
                        "category": "preference"
                    }
                ],
                "expected_output": {
                    "format": "Unified Git Diff & Security Audit Verdict",
                    "schema_summary": "Sanitized source files, Bandit AST scan JSON, and security regression test results",
                    "delivery_target": "Repository Worktree"
                },
                "ambiguities": [
                    {
                        "id": "AMB-1",
                        "question": "When a malicious path traversal attempt is detected, should the API return HTTP 400 Bad Request or HTTP 403 Forbidden?",
                        "context": "HTTP status code must adhere to API design standards for security violations.",
                        "severity": "blocking",
                        "suggested_options": ["HTTP 400 Bad Request (generic error)", "HTTP 403 Forbidden (explicit security rejection)", "HTTP 404 Not Found (stealth mode)"],
                        "default_assumption": "HTTP 400 Bad Request with standardized error JSON"
                    }
                ]
            }

        # Generic Coding Agent Fallback
        return {
            "summary": f"Execute software engineering task: '{text[:80]}...' with test-driven implementation, static validation, and zero regression.",
            "main_goal": f"Complete coding task: '{text.strip()}' ensuring test suite compliance, clean static analysis, and interface stability.",
            "detected_language": "en",
            "normalized_request": text.strip(),
            "sub_goals": [
                {
                    "id": "SG-1",
                    "title": "Analyze Codebase Context & Establish Baseline Test Suite",
                    "description": "Inspect existing modules, understand AST dependencies, and verify existing test baselines pass.",
                    "order": 1,
                    "priority": "high",
                    "assigned_agent_role": "Code Architect Agent",
                    "dependencies": []
                },
                {
                    "id": "SG-2",
                    "title": "Implement Code Modifications and Unit Tests",
                    "description": "Perform clean modular changes in target files and create comprehensive unit tests covering edge cases.",
                    "order": 2,
                    "priority": "high",
                    "assigned_agent_role": "Implementation Agent",
                    "dependencies": ["SG-1"]
                },
                {
                    "id": "SG-3",
                    "title": "Execute Regression Verification & Linter Audit",
                    "description": "Run test suite, verify 100% test pass rate, check for type errors, and inspect diff cleanliness.",
                    "order": 3,
                    "priority": "medium",
                    "assigned_agent_role": "Test & Verification Agent",
                    "dependencies": ["SG-2"]
                }
            ],
            "success_criteria": [
                {
                    "id": "SC-1",
                    "sub_goal_id": "SG-1",
                    "description": "Baseline codebase passes initial static syntax and import checks",
                    "metric": "Syntax errors == 0",
                    "verification_method": "ast_check",
                    "expected_output": "Initial syntax verification report"
                },
                {
                    "id": "SC-2",
                    "sub_goal_id": "SG-2",
                    "description": "All newly implemented feature and bugfix unit tests pass",
                    "metric": "pytest new_tests == 100% PASS",
                    "verification_method": "automated_test",
                    "expected_output": "Unit test execution output"
                },
                {
                    "id": "SC-3",
                    "sub_goal_id": "SG-3",
                    "description": "Full regression test suite passes with 0 test failures or broken imports",
                    "metric": "Regression failures == 0",
                    "verification_method": "automated_test",
                    "expected_output": "Full test suite execution report"
                }
            ],
            "hard_constraints": [
                {
                    "id": "HC-1",
                    "text": "Never delete, comment out, or skip existing test assertions to force a pass",
                    "category": "safety"
                },
                {
                    "id": "HC-2",
                    "text": "Do not break public function signatures or exported module interfaces",
                    "category": "safety"
                },
                {
                    "id": "HC-3",
                    "text": "Never commit plaintext API secrets, credentials, or private keys to source code",
                    "category": "security"
                }
            ],
            "soft_constraints": [
                {
                    "id": "SC-1",
                    "text": "Maintain clean modular code adhering to standard PEP 8 / Clean Code conventions",
                    "category": "style"
                },
                {
                    "id": "SC-2",
                    "text": "Include clear docstrings and typing annotations on newly created functions",
                    "category": "preference"
                }
            ],
            "expected_output": {
                "format": "Unified Git Diff & Verification Trace",
                "schema_summary": "Unified patch diff, modified file list, test results, and execution metrics",
                "delivery_target": "Repository Worktree"
            },
            "ambiguities": [
                {
                    "id": "AMB-1",
                    "question": "What is the minimum required test coverage percentage for the newly created or modified functions?",
                    "context": "Coverage requirement guides the depth of test cases authored.",
                    "severity": "blocking",
                    "suggested_options": ["Minimum 80% coverage", "Minimum 90% coverage", "100% branch coverage"],
                    "default_assumption": "Minimum 85% test coverage"
                },
                {
                    "id": "AMB-2",
                    "question": "Which Python version should be targeted for syntax and standard library compatibility?",
                    "context": "Affects usage of modern typing features (e.g. match statements, Self type).",
                    "severity": "non_blocking",
                    "suggested_options": ["Python 3.10+", "Python 3.11+", "Python 3.12+"],
                    "default_assumption": "Python 3.11+"
                }
            ]
        }

goal_parser_service = GoalParserService()
