from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from ..services.feature_analytics_service import validate_model_name
from typing import Dict, Any, List, Optional
from ..models.schema import (
    GoalModel,
    ParseTaskRequest,
    PatchGoalModelRequest,
    ResolveAmbiguityRequest,
    OllamaConfigRequest,
    StartPlanRequest,
    ExecuteCodeRequest,
    ExecuteTestsRequest,
    ExecuteVerificationRequest,
    RunPipelineRequest,
    PolicyApprovalRequest,
    ImplementationPlan,
    VerificationReport,
    RunRecord
)
from ..services.ollama_service import ollama_service
from ..services.goal_parser_service import goal_parser_service
from ..services.storage_service import storage_service
from ..services.workspace_service import workspace_service
from ..services.planner_service import planner_service
from ..services.coder_service import coder_service
from ..services.test_runner_service import test_runner_service
from ..services.debugger_service import debugger_service
from ..services.verifier_service import verifier_service
from ..services.orchestrator_service import orchestrator_service
from ..services.db import db_service
from ..services.feature_analytics_service import feature_analytics_service

router = APIRouter()

PRESETS = [
    {
        "id": "preset_login_api_jwt",
        "title": "Build a login API with JWT authentication",
        "category": "Authentication & Security",
        "description": "Implement user registration, secure password hashing (PBKDF2/bcrypt), JWT token issuance (HS256), OAuth2 Bearer protected routes, and automated pytest suite.",
        "prompt": "Build a login API with JWT authentication using FastAPI. Requirements: 1) Implement user registration with password hashing. 2) Implement login endpoint that returns a signed JWT access token. 3) Implement protected route GET /api/auth/me requiring valid Bearer token. 4) Reject invalid passwords with HTTP 401 Unauthorized. 5) Reject expired or forged tokens with HTTP 401. 6) Write automated pytest test suite in 'tests/test_auth.py' achieving 100% test pass rate."
    },
    {
        "id": "preset_bug_fix_concurrency",
        "title": "Bug Fix: Concurrency Race Condition in ConnectionPool",
        "category": "Debugging & Concurrency",
        "description": "Reproduce race condition under high thread load, write isolated reproduction test, implement asyncio.Lock fix, and verify zero connection leaks.",
        "prompt": "Investigate and fix an intermittent race condition in 'src/core/connection_pool.py' where multiple concurrent worker coroutines acquire the same socket handle under peak load. Requirements: 1) Write a deterministic pytest reproduction test in 'tests/test_pool_concurrency.py' that reproduces the failure. 2) Implement proper mutual exclusion using asyncio.Lock while preserving zero-allocation fast path for idle connections. 3) Hard constraint: Do not break the existing Public ConnectionPool interface methods. 4) Ensure 100% of existing unit tests pass and connection leak check reports 0 unclosed sockets."
    },
    {
        "id": "preset_code_refactor_async",
        "title": "Codebase Refactoring: Sync DB Handler to Async SQLAlchemy",
        "category": "Refactoring & Architecture",
        "description": "Refactor monolithic blocking SQLite database queries into async SQLAlchemy 2.0 with connection pooling and typed repositories.",
        "prompt": "Refactor the legacy synchronous database module in 'src/storage/db_handler.py' to use asynchronous SQLAlchemy 2.0 with asyncpg/aiosqlite drivers. Separate queries into repository patterns under 'src/storage/repositories/'. Hard constraints: Maintain strict backward compatibility for all public repository function signatures. Ensure zero unhandled coroutine warnings. Memory footprint must not exceed 256MB during batch queries. Add full pytest-asyncio test coverage with >= 90% branch coverage."
    },
    {
        "id": "preset_security_patch_cwe",
        "title": "Security Remediation: AST Sanitization for SQLi & Path Traversal",
        "category": "Security & Static Analysis",
        "description": "Scan AST, patch CWE-89 SQL Injection and CWE-22 Path Traversal vulnerabilities, and verify static analysis clean pass.",
        "prompt": "Perform security vulnerability remediation on 'src/api/routes/reports.py' and 'src/utils/file_manager.py'. Replace all raw f-string SQL queries with parameterized query builders to eliminate CWE-89. Sanitize user-supplied file paths using os.path.realpath and base-directory boundary checks to prevent CWE-22 directory traversal. Hard constraints: Never expose internal system error stack traces to API clients. Never delete or weaken existing security test assertions. Ensure Bandit and flake8 linters pass with 0 security warnings."
    },
    {
        "id": "preset_api_modernization",
        "title": "API Modernization: REST to GraphQL with Schema Verification",
        "category": "API & Fullstack Engineering",
        "description": "Generate Strawberry GraphQL schema and resolvers for REST endpoints with DataLoader N+1 query batching and type invariants.",
        "prompt": "Modernize the REST endpoints in 'src/api/v1/projects.py' into a unified GraphQL schema using Strawberry GraphQL. Implement DataLoader batching to eliminate N+1 database queries on project members and issue lists. Hard constraints: Graph schema must pass strict type-checking with mypy. GraphQL response latency must stay below 120ms for nested queries up to 3 levels deep. Verify all integration tests pass with 0 regression."
    }
]

@router.get("/health")
async def health_check():
    return {"status": "ok", "service": "AgentEval-X Backend", "version": "1.0.0"}

# --- Ollama Telemetry & Configuration ---

@router.get("/ollama/status")
async def get_ollama_status():
    return await ollama_service.check_connection()

@router.post("/ollama/configure")
async def configure_ollama(req: OllamaConfigRequest):
    ollama_service.update_config(host=req.host, default_model=req.default_model)
    status = await ollama_service.check_connection()
    return {"message": "Ollama configuration updated", "status": status}

# --- Workspace & Presets ---

@router.get("/presets")
async def get_task_presets():
    return {"presets": PRESETS}

@router.get("/workspace/sample-repos")
async def get_sample_repos():
    return {"repositories": workspace_service.list_sample_repositories()}

@router.get("/workspace/inspect")
async def inspect_workspace(path: Optional[str] = Query(None)):
    target_path = path or workspace_service.get_default_repo_path()
    return workspace_service.inspect_directory(target_path)

# --- Stage 2: Requirement Analysis & Goal Model ---

@router.post("/goals/parse", response_model=GoalModel)
async def parse_task(req: ParseTaskRequest):
    if not req.request_text or not req.request_text.strip():
        raise HTTPException(status_code=400, detail="request_text cannot be empty")
    
    goal_model = await goal_parser_service.parse_request(
        request_text=req.request_text,
        model_name=req.model_name,
        run_id=req.run_id,
        language=req.language,
        temperature=req.temperature or 0.2
    )
    return goal_model

@router.post("/goals/patch", response_model=GoalModel)
async def patch_goal_model(req: PatchGoalModelRequest):
    try:
        patch_dict = req.model_dump(exclude_unset=True)
        run_id = patch_dict.pop("run_id")
        change_summary = patch_dict.pop("change_summary", "Manual user edit")
        
        updated_model = goal_parser_service.patch_goal_model(
            run_id=run_id,
            patch_data=patch_dict,
            change_summary=change_summary
        )
        return updated_model
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to patch goal model: {str(e)}")

@router.post("/goals/resolve-ambiguity", response_model=GoalModel)
async def resolve_ambiguity(req: ResolveAmbiguityRequest):
    try:
        updated_model = goal_parser_service.resolve_ambiguity(
            run_id=req.run_id,
            ambiguity_id=req.ambiguity_id,
            user_answer=req.user_answer,
            apply_as_constraint=req.apply_as_constraint if req.apply_as_constraint is not None else True,
            constraint_type=req.constraint_type or "hard"
        )
        return updated_model
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to resolve ambiguity: {str(e)}")

@router.post("/goals/confirm/{run_id}", response_model=GoalModel)
async def confirm_goal_model(run_id: str):
    try:
        confirmed_model = goal_parser_service.confirm_goal_model(run_id=run_id)
        return confirmed_model
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to confirm goal model: {str(e)}")

@router.get("/goals/{run_id}", response_model=GoalModel)
async def get_goal_model(run_id: str):
    model = storage_service.get_goal_model(run_id)
    if not model:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return model

@router.get("/goals/{run_id}/history")
async def get_goal_history(run_id: str):
    history = storage_service.get_run_history(run_id)
    return {"run_id": run_id, "versions": history}

# --- Stage 3: Codebase Analyst & Planner ---

@router.post("/planner/generate", response_model=ImplementationPlan)
async def generate_plan(req: StartPlanRequest):
    try:
        plan = await planner_service.generate_plan(
            run_id=req.run_id,
            repo_path=req.repo_path
        )
        return plan
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Planning failed: {str(e)}")

@router.get("/planner/{run_id}", response_model=ImplementationPlan)
async def get_plan(run_id: str):
    plan = db_service.get_plan(run_id)
    if not plan:
        raise HTTPException(status_code=404, detail=f"Plan for run {run_id} not found")
    return plan

# --- Stage 4: Coding Agent ---

@router.post("/coder/execute")
async def execute_coding(req: ExecuteCodeRequest):
    try:
        changes = await coder_service.execute_plan(
            run_id=req.run_id,
            model_name=req.model_name,
            temperature=req.temperature if req.temperature is not None else 0.2,
        )
        return {"run_id": req.run_id, "changes_count": len(changes), "changes": changes}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Coding agent execution failed: {str(e)}")

@router.get("/coder/{run_id}/changes")
async def get_code_changes(run_id: str):
    changes = db_service.get_code_changes(run_id)
    return {"run_id": run_id, "changes": changes}

# --- Stage 5: Testing & Debugging Agents ---

@router.post("/tester/execute")
async def execute_testing(req: ExecuteTestsRequest):
    try:
        result = await debugger_service.run_testing_and_recovery_loop(
            run_id=req.run_id,
            max_recovery_retries=req.max_recovery_retries or 3
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Testing and debugging loop failed: {str(e)}")

@router.get("/tester/{run_id}/results")
async def get_test_results(run_id: str):
    test_runs = db_service.get_test_results(run_id)
    recoveries = db_service.get_recovery_attempts(run_id)
    return {"run_id": run_id, "test_runs": test_runs, "recovery_attempts": recoveries}

# --- Stage 6: Independent Code Reviewer / Verifier ---

@router.post("/verifier/verify", response_model=VerificationReport)
async def verify_code(req: ExecuteVerificationRequest):
    try:
        report = await verifier_service.verify_run(run_id=req.run_id)
        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Verification failed: {str(e)}")

@router.get("/verifier/{run_id}", response_model=VerificationReport)
async def get_verification(run_id: str):
    report = db_service.get_verification(run_id)
    if not report:
        raise HTTPException(status_code=404, detail=f"Verification for run {run_id} not found")
    return report

# --- Stage 7: End-to-End Orchestrator Pipeline ---

@router.post("/pipeline/run-all", response_model=RunRecord)
async def run_pipeline(req: RunPipelineRequest):
    # Validate model_name before entering the pipeline
    try:
        validate_model_name(req.model_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    try:
        record = await orchestrator_service.run_full_pipeline(
            request_text=req.request_text,
            repo_path=req.repo_path,
            model_name=req.model_name,
            temperature=req.temperature or 0.2,
            max_recovery_retries=(
                req.max_recovery_retries
                if req.max_recovery_retries is not None else 3
            ),
            existing_run_id=req.run_id
        )
        return record
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Autonomous pipeline execution failed: {str(e)}")


@router.get("/runs/{run_id}/policy-approval")
async def get_pending_policy_approval(run_id: str):
    return feature_analytics_service.get_pending_policy_approval(run_id)


@router.post("/runs/{run_id}/policy-approval")
async def resolve_policy_approval(run_id: str, req: PolicyApprovalRequest):
    existing = feature_analytics_service.get_policy_approval(run_id, req.approval_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Approval request not found")
    approval = feature_analytics_service.resolve_policy_approval(
        run_id=run_id,
        approval_id=req.approval_id,
        approved=req.approved,
        comment=req.comment,
    )
    if approval:
        return approval
    raise HTTPException(status_code=409, detail="Approval request is no longer pending")

# --- Runs, Telemetry & Evaluations ---

@router.get("/runs")
async def list_runs():
    return {"runs": db_service.list_all_runs()}

@router.get("/runs/{run_id}", response_model=RunRecord)
async def get_run_details(run_id: str):
    record = db_service.get_run_record(run_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return record

@router.get("/runs/{run_id}/logs")
async def get_run_logs(run_id: str, limit: int = Query(200)):
    logs = db_service.get_execution_logs(run_id, limit=limit)
    return {"run_id": run_id, "logs": logs}

@router.get("/evaluations/dashboard")
async def get_evaluations_dashboard():
    return db_service.get_aggregate_evaluations()

@router.get("/evaluations/{run_id}")
async def get_run_evaluation(run_id: str):
    ev = db_service.get_evaluation(run_id)
    if not ev:
        raise HTTPException(status_code=404, detail=f"Evaluation for run {run_id} not found")
    return ev


# --- AgentEval-X research features: prediction, recovery stats, capability profile ---

@router.get("/features/capabilities")
async def get_capability_profiles(
    model_name: Optional[str] = Query(None),
    task_type: Optional[str] = Query(None),
    difficulty: Optional[str] = Query(None),
    run_id: Optional[str] = Query(None),
):
    """Return directly observed capabilities, falling back to agent artifact outcomes."""
    from ..services.hierarchical_proficiency_service import hierarchical_proficiency_service
    hierarchical_proficiency_service.get_hierarchical_profiles(
        model_name=model_name, run_id=run_id,
    )
    return feature_analytics_service.get_capability_profiles(
        model_name=model_name, task_type=task_type, difficulty=difficulty, run_id=run_id,
    )


@router.get("/features/predictor/status")
async def get_predictor_status():
    """Return failure predictor status and labelled trajectory counts.

    Includes whether a supervised model can be trained and what evaluation
    metrics will be computed (precision, recall, F1, PR-AUC, Brier score,
    warning lead time).
    """
    return feature_analytics_service.get_predictor_status()


@router.post("/features/predictor/train")
async def train_predictor():
    """Train the supervised failure predictor using accumulated trajectory data.

    Uses GroupShuffleSplit on run_id to prevent data leakage.
    Returns INSUFFICIENT_DATA when fewer than 5 runs per class exist.
    Reports PR-AUC, Brier score, precision, recall, prevalence, baseline,
    and warning lead time.
    """
    return feature_analytics_service.train_and_evaluate_predictor()


# ---------------------------------------------------------------------------
# Hierarchical Agent Proficiency Profiling Endpoints
# ---------------------------------------------------------------------------

@router.get("/features/hierarchical-proficiency")
async def get_hierarchical_proficiency(
    model_name: Optional[str] = Query(None),
    run_id: Optional[str] = Query(None),
):
    """Return hierarchical agent proficiency profiling.

    Tracks directly observed outcomes for all 7 actual agents and a macro-level
    end-to-end system profile using persisted execution data and root-cause
    failure and recovery attribution.
    """
    from ..services.hierarchical_proficiency_service import hierarchical_proficiency_service
    return hierarchical_proficiency_service.get_hierarchical_profiles(
        model_name=model_name, run_id=run_id,
    )


@router.post("/features/hierarchical-proficiency/rebuild")
async def rebuild_hierarchical_proficiency():
    """Scan all historical runs in SQLite and re-populate agent proficiency observations."""
    from ..services.hierarchical_proficiency_service import hierarchical_proficiency_service
    synced_count = hierarchical_proficiency_service.sync_all_historical_runs()
    return {"status": "success", "runs_synced": synced_count}


@router.get("/features/{run_id}/recovery")
async def get_run_recovery(run_id: str):
    """Return structured recovery episode data for a specific run.

    Each episode includes failure type, timestamps, corrective actions,
    extra test executions, and verified outcome — never inferred from
    stage completion alone.
    """
    return feature_analytics_service.get_recovery_summary(run_id)


@router.get("/features/{run_id}")
async def get_feature_analytics(run_id: str):
    """Return failure prediction signals and trajectory for a specific run.

    Prediction remains unavailable until a supervised model is validated and deployed.
    Trajectory features are retained for offline model evaluation.
    """
    return feature_analytics_service.get_run_analytics(run_id)
