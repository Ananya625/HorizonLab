from fastapi import APIRouter, HTTPException, Query
from typing import Optional
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
    ReviseGoalRequest,
    ImplementationPlan,
    VerificationReport,
    RunRecord,
    EvaluationMetrics
)
from ..services.ollama_service import ollama_service
from ..services.goal_parser_service import goal_parser_service
from ..services.storage_service import storage_service
from ..services.workspace_service import workspace_service
from ..services.planner_service import planner_service
from ..services.coder_service import coder_service
from ..services.debugger_service import debugger_service
from ..services.verifier_service import verifier_service
from ..services.orchestrator_service import orchestrator_service
from ..services.goal_tracker_service import goal_tracker_service
from ..services.db import db_service

router = APIRouter()


def record_stage_failure(run_id, stage, error):
    """Persist attempted-stage failures without inventing timing or test evidence."""
    record = db_service.get_run_record(run_id)
    if record is None:
        return
    db_service.invalidate_evaluation(run_id, f'{stage} failed; previous evidence superseded')
    db_service.add_log(run_id, stage, 'Stage Runner', 'error', type(error).__name__)
    db_service.finalize_run(EvaluationMetrics(run_id=run_id, task_id=record.task_id,
        metric_version='2', outcome='error', verified_success=False,
        execution_mode=record.metadata.get('execution_mode', 'mixed_demo'),
        termination_reason=f'{stage}:{type(error).__name__}'))

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
    try:
        ollama_service.update_config(host=req.host, default_model=req.default_model)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
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
    try:
        return workspace_service.inspect_directory(target_path)
    except ValueError as exc:
        raise HTTPException(400, str(exc))

# --- Stage 2: Requirement Analysis & Goal Model ---

@router.post("/goals/parse", response_model=GoalModel)
async def parse_task(req: ParseTaskRequest):
    if not req.request_text or not req.request_text.strip():
        raise HTTPException(status_code=400, detail="request_text cannot be empty")
    
    try:
        return await goal_parser_service.parse_request(
            request_text=req.request_text,
            model_name=req.model_name,
            run_id=req.run_id,
            language=req.language,
            temperature=req.temperature if req.temperature is not None else 0.2,
            repo_path=req.repo_path
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc))

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
        record = db_service.get_run_record(req.run_id)
        if not record:
            raise ValueError('Unknown run')
        config = record.metadata.get('config', {})
        plan = await planner_service.generate_plan(
            run_id=req.run_id,
            repo_path=record.repo_path,
            model_name=config.get('model_name'),
            temperature=config.get('temperature', 0.2)
        )
        return plan
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        record_stage_failure(req.run_id, 'planner', e)
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
        record = db_service.get_run_record(req.run_id)
        if not record:
            raise ValueError('Unknown run')
        config = record.metadata.get('config', {})
        changes = await coder_service.execute_plan(run_id=req.run_id,
            model_name=config.get('model_name'), temperature=config.get('temperature', 0.2))
        return {"run_id": req.run_id, "changes_count": len(changes), "changes": changes}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        record_stage_failure(req.run_id, 'coder', e)
        raise HTTPException(status_code=500, detail=f"Coding agent execution failed: {str(e)}")

@router.get("/coder/{run_id}/changes")
async def get_code_changes(run_id: str):
    changes = db_service.get_code_changes(run_id)
    return {"run_id": run_id, "changes": changes}

# --- Stage 5: Testing & Debugging Agents ---

@router.post("/tester/execute")
async def execute_testing(req: ExecuteTestsRequest):
    try:
        record = db_service.get_run_record(req.run_id)
        if not record:
            raise ValueError('Unknown run')
        result = await debugger_service.run_testing_and_recovery_loop(
            run_id=req.run_id,
            model_name=record.metadata.get('config', {}).get('model_name'),
            max_recovery_retries=req.max_recovery_retries if req.max_recovery_retries is not None else 3
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        record_stage_failure(req.run_id, 'testing', e)
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
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        record_stage_failure(req.run_id, 'verifier', e)
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
    try:
        record = await orchestrator_service.run_full_pipeline(
            request_text=req.request_text,
            repo_path=req.repo_path,
            model_name=req.model_name,
            temperature=req.temperature if req.temperature is not None else 0.2,
            max_recovery_retries=req.max_recovery_retries if req.max_recovery_retries is not None else 3,
            existing_run_id=req.run_id
        )
        return record
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Autonomous pipeline execution failed: {str(e)}")

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
async def get_run_logs(run_id: str, limit: int = Query(200, ge=1, le=1000), offset: int = Query(0, ge=0)):
    logs = db_service.get_execution_logs(run_id, limit=limit, offset=offset)
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

# --- Goal Tracking & Drift Control ---

@router.post("/goals/revise")
async def revise_goal(req: ReviseGoalRequest):
    try:
        if req.run_id in orchestrator_service.active:
            raise ValueError('Cannot revise a goal while its run is executing')
        if not req.new_goal.strip():
            raise ValueError('Revised goal must not be empty')
        if not goal_tracker_service.get_state(req.run_id):
            raise ValueError('No tracking state for this run')
        goal_parser_service.patch_goal_model(req.run_id, {'main_goal': req.new_goal.strip()},
            req.change_reason or 'User explicit goal revision')
        state = goal_tracker_service.revise_goal(
            run_id=req.run_id,
            new_goal_text=req.new_goal,
            change_reason=req.change_reason or "User explicit goal revision"
        )
        return {"status": "success", "state": state}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/goals/{run_id}/tracking")
async def get_goal_tracking(run_id: str):
    state = goal_tracker_service.get_state(run_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Tracking state for run {run_id} not found")
    return state


@router.get('/runs/{run_id}/export')
def export_run(run_id: str):
    record = db_service.get_run_record(run_id)
    if not record:
        raise HTTPException(404, 'Unknown run')
    return record


from ..models.benchmark import ExperimentManifest
from ..services.benchmark_service import benchmark_service
from ..models.benchmark_study import StudyManifest, EvidenceBatch
from ..services.benchmark_study_service import study_service
from ..services.benchmark_study_analysis import study_analytics, validate_evidence
from ..services.benchmark_lock import experiment_lock


@router.get('/benchmarks/capabilities')
def benchmark_capabilities():
    return benchmark_service.capabilities()


@router.get('/benchmarks/experiments')
def benchmark_experiments():
    return {'experiments': db_service.get_experiments()}


@router.post('/benchmarks/experiments')
def run_benchmark(manifest: ExperimentManifest):
    try:
        return benchmark_service.run(manifest)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@router.get('/benchmarks/experiments/{experiment_id}')
def benchmark_report(experiment_id: str):
    report = next((e for e in db_service.get_experiments() if e['experiment_id'] == experiment_id), None)
    if report is None:
        raise HTTPException(404, 'Unknown experiment')
    return report


@router.post('/benchmarks/experiments/{experiment_id}/resume')
def resume_benchmark(experiment_id: str):
    report = benchmark_report(experiment_id)
    try:
        if report['manifest'].get('manifest_version') == '2':
            return study_service.run(StudyManifest.model_validate(report['manifest']), experiment_id)
        return benchmark_service.run(ExperimentManifest.model_validate(report['manifest']), experiment_id)
    except ValueError as exc:
        raise HTTPException(409, str(exc))


@router.post('/benchmarks/studies')
def run_study(manifest: StudyManifest):
    try:
        return study_service.run(manifest)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@router.post('/benchmarks/experiments/{experiment_id}/evidence')
def append_benchmark_evidence(experiment_id: str, batch: EvidenceBatch):
    """Local evaluator/operator endpoint. It cannot change the independently verified outcome."""
    try:
        with experiment_lock(db_service.db_path):
            report = benchmark_report(experiment_id)
            if report['manifest'].get('manifest_version') != '2' or report['status'] not in ('completed','halted'):
                raise ValueError('Evidence ingestion requires a finished version-two study')
            rows = {r['run_id']:r for r in report['trials']}
            for event in batch.events:
                row = rows.get(event.run_id)
                if row is None or event.task_id != row['task_id'] or event.step > row['tool_calls']:
                    raise ValueError('Evidence is outside the recorded run/task/step')
                validate_evidence(event)
                if event.kind=='prediction' and event.source not in ('fixture','team_module'):
                    raise ValueError('Prediction source must identify its producer')
            # Validate the complete batch and all conflicts before any mutation.
            pending = {}
            for event in batch.events:
                value = event.model_dump()
                key = (event.run_id,event.event_id)
                prior = pending.get(key) or next((e for e in rows[event.run_id]['events'] if e['event_id']==event.event_id),None)
                if prior is not None and prior != value:
                    raise ValueError('Existing evidence cannot be rewritten')
                pending[key] = value
            additions_by_run = {}
            for run_id,row in rows.items():
                additions = [v for (r,e),v in pending.items() if r==run_id and not any(old['event_id']==e for old in row['events'])]
                additions_by_run[run_id] = additions
                row['events'].extend(additions)
            report['analytics'] = study_analytics(report['trials'])
            with db_service._get_connection() as conn:
                conn.execute('BEGIN IMMEDIATE')
                for run_id, additions in additions_by_run.items():
                    db_service.save_benchmark_checkpoint(run_id,None,additions,connection=conn)
                db_service.save_experiment(experiment_id,report['manifest'],report,connection=conn)
            return report
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@router.get('/benchmarks/capabilities/history')
def benchmark_capability_history():
    from ..services.benchmark_study_analysis import capability_history
    trials = [r for report in db_service.get_experiments() if report['manifest'].get('manifest_version')=='2' for r in report['trials']]
    return {'history':capability_history(trials)}


# Observational workflow analysis. Existing evaluation and run export contracts are unchanged.
from ..services.workflow_reports import workflow_report
from ..services import workflow_store


@router.get('/evaluations/{run_id}/workflow')
def get_workflow_analysis(run_id: str):
    report, _ = workflow_report(db_service, run_id)
    report.pop('timeline')  # Timeline evidence is paginated separately.
    return report


@router.get('/evaluations/{run_id}/workflow/events')
def get_workflow_events(run_id: str, after: int = Query(0, ge=0),
                        limit: int = Query(50, ge=1, le=200), through: Optional[int] = Query(None, ge=0)):
    if not db_service.get_run_record(run_id):
        raise HTTPException(404, 'Unknown run')
    return workflow_store.read(db_service, run_id, after, limit, through)


@router.get('/evaluations/{run_id}/workflow/events/{event_id}')
def get_workflow_event(run_id: str, event_id: str):
    with db_service._get_connection() as conn:
        row = conn.execute('SELECT sequence,data_json FROM workflow_events WHERE run_id=? AND event_id=?', (run_id,event_id)).fetchone()
    if not row:
        raise HTTPException(404, 'Unknown evidence for this run')
    import json
    return dict(json.loads(row['data_json']), sequence=row['sequence'])


@router.get('/evaluations/{run_id}/workflow/export')
def export_workflow_analysis(run_id: str):
    report, events = workflow_report(db_service, run_id)
    return {'report':report, 'events':events}
