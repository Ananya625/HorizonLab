import asyncio
from .workflow_service import observed
import os
import time
import uuid
import logging
from typing import Optional
from datetime import datetime
from ..models.schema import (
    RunRecord,
    ImplementationPlan,
    PlannedFile,
    PlanStep
)
from .db import db_service
from .workspace_service import workspace_service
from .goal_parser_service import goal_parser_service
from .planner_service import planner_service
from .coder_service import coder_service
from .test_runner_service import test_runner_service
from .debugger_service import debugger_service
from .verifier_service import verifier_service
from .task_router_service import task_router_service
from .telemetry_service import telemetry_manager
from .goal_tracker_service import goal_tracker_service
from .drift_controller_service import drift_controller_service
from .ollama_service import ollama_service

logger = logging.getLogger(__name__)

from ..models.schema import EvaluationMetrics

class OrchestratorService:
    def __init__(self):
        self.active = set()

    async def run_full_pipeline(self, request_text, repo_path=None, model_name=None,
                                temperature=0.2, max_recovery_retries=3, existing_run_id=None):
        run_id = existing_run_id or f'run_{uuid.uuid4().hex}'
        if run_id in self.active:
            raise ValueError('This run is already executing')
        self.active.add(run_id)
        start = time.perf_counter()
        try:
            record = db_service.get_run_record(run_id)
            if existing_run_id and not record:
                raise ValueError('Unknown existing run')
            goal = db_service.get_goal_model(run_id)
            if goal and request_text.strip() != goal.original_request.strip():
                raise ValueError('Existing run has a different request; edit its goal or start a new run')
            if not record:
                task_id = f'task_{uuid.uuid4().hex}'
                target = repo_path or workspace_service.create_task_workspace(task_id=task_id, run_id=run_id)
                target = workspace_service.validate_repo(target)
                sample = next((r['path'] for r in workspace_service.list_sample_repositories() if r['id']==target),None)
                target = sample or target
                record = db_service.create_or_update_run(run_id, task_id, request_text[:80], request_text, target)
            model_name = model_name or record.metadata.get('config', {}).get('model_name') or ollama_service.default_model
            config = {'model_name': model_name, 'temperature': temperature,
                'max_recovery_retries': max_recovery_retries}
            db_service.update_metadata(run_id, config=config, execution_mode='mixed_demo')
            if not goal:
                try:
                    await goal_parser_service.parse_request(request_text, run_id=run_id,
                        model_name=config['model_name'], temperature=config['temperature'], repo_path=record.repo_path)
                except Exception as exc:
                    db_service.finalize_run(EvaluationMetrics(run_id=run_id, task_id=record.task_id,
                        metric_version='2', outcome='error', verified_success=False,
                        termination_reason=f'goal_parse:{type(exc).__name__}', execution_time_seconds=time.perf_counter()-start))
                    raise
                return db_service.get_run_record(run_id)
            if not goal.is_confirmed or any(a.severity == 'blocking' and not a.resolved for a in goal.ambiguities):
                raise ValueError('Confirm the goal and resolve blocking ambiguities before execution')
            try:
                return await self._execute_confirmed(request_text, repo_path=record.repo_path,
                    model_name=model_name, temperature=temperature, max_recovery_retries=max_recovery_retries,
                    existing_run_id=run_id, execution_started=start)
            except Exception as exc:
                db_service.finalize_run(EvaluationMetrics(run_id=run_id, task_id=record.task_id,
                    metric_version='2', outcome='error', verified_success=False,
                    termination_reason=type(exc).__name__, execution_time_seconds=time.perf_counter()-start))
                raise
        finally:
            self.active.discard(run_id)

    @observed('pipeline', 'stage', reason=None)
    async def _execute_confirmed(
        self,
        request_text: str,
        repo_path: Optional[str] = None,
        model_name: Optional[str] = None,
        temperature: float = 0.2,
        max_recovery_retries: int = 3,
        existing_run_id: Optional[str] = None,
        execution_started: Optional[float] = None
    ) -> RunRecord:
        run_id = existing_run_id
        record = db_service.get_run_record(run_id)
        task_id, target_repo = record.task_id, record.repo_path
        goal_model = db_service.get_goal_model(run_id)
        tracker = telemetry_manager.get_or_create(run_id, task_id)
        # Step 2: Lightweight Adaptive Task Router (Executed BEFORE expensive LLM calls)
        t_route_start = tracker.start_span("routing", "task_classification")
        routing = task_router_service.route_task(
            request_text=goal_model.main_goal,
            repo_path=target_repo
        )
        # Allow caller override of model if explicitly provided
        effective_model = model_name or record.metadata.get('config', {}).get('model_name') or ollama_service.default_model
        tracker.end_span("routing", "task_classification", t_route_start, metadata=routing.model_dump())

        db_service.add_log(
            run_id=run_id,
            stage="workspace",
            agent_role="Adaptive Task Router",
            event_type="routing",
            message=f"Task classified as tier '{routing.task_tier.upper()}' (Fast Path: {routing.use_fast_path}, Model: {effective_model}). {routing.reasoning}",
            details=routing.model_dump()
        )

        # Step 2.5: Initialize Deterministic Goal Tracker State
        previous_tracking = goal_tracker_service.get_state(run_id)
        tracking_state = goal_tracker_service.initialize_task(
            run_id=run_id,
            task_id=task_id,
            original_request=request_text,
            complexity_profile=routing.task_tier,
            target_files=routing.target_files,
            acceptance_criteria=[c.model_dump() for c in goal_model.success_criteria]
        )
        tracking_state.current_goal = goal_model.main_goal
        if previous_tracking:
            tracking_state.revision_history = previous_tracking.revision_history
            tracking_state.action_history = previous_tracking.action_history
            tracking_state.failed_attempts_count = previous_tracking.failed_attempts_count
        goal_tracker_service._persist_state(tracking_state)

        # =====================================================================
        # FAST PATH FOR SIMPLE ISOLATED TASKS
        # =====================================================================
        if routing.use_fast_path:
            logger.info(f"[{run_id}] Executing Adaptive Fast Path for {routing.task_tier} task.")
            goal_tracker_service.start_subtask(run_id, "SUBTASK-1")
            
            # Fast Path Step 1: Targeted Workspace Inspection
            t_span = tracker.start_span("workspace", "targeted_inspection")
            inspection = workspace_service.inspect_targeted(
                target_path=target_repo,
                file_list=routing.relevant_inspection_files,
                run_id=run_id
            )
            tracker.end_span("workspace", "targeted_inspection", t_span)

            db_service.add_log(
                run_id=run_id,
                stage="workspace",
                agent_role="Codebase Analyst Agent",
                event_type="tool_call",
                message=f"Targeted inspection complete for {len(inspection['files'])} relevant files ({inspection['total_lines_of_code']} LoC). Bypassed full repo walk.",
                details={"files": [f["path"] for f in inspection["files"]]}
            )

            # Fast Path Step 2: Concise Specification & Implementation Plan
            t_span = tracker.start_span("requirement", "concise_plan_synthesis")
            planned_files = []
            for tf in routing.target_files:
                tf_norm = tf.replace("\\", "/")
                exists = os.path.exists(os.path.join(target_repo, tf_norm))
                action = "modify" if exists else "create"
                desc = f"{'Update' if exists else 'Create'} {tf_norm} according to isolated specification."
                planned_files.append(
                    PlannedFile(path=tf_norm, action=action, description=desc, estimated_loc=30,
                                sub_goal_id=goal_model.sub_goals[0].id if len(goal_model.sub_goals) == 1 else None)
                )

            plan = ImplementationPlan(
                id=f"plan_{uuid.uuid4().hex[:8]}",
                run_id=run_id,
                goal_model_version=goal_model.goal_model_version,
                architecture_overview=f"Targeted isolated modification: {request_text[:80]}",
                target_repo_path=target_repo,
                tech_stack={"framework": "Python", "language": "Python 3.11+", "test_runner": "pytest"},
                key_modules=routing.target_files,
                planned_files=planned_files,
                steps=[
                    PlanStep(
                        step_number=1,
                        title="Generate and apply isolated code changes",
                        description=request_text,
                        assigned_agent="Coding Agent",
                        target_files=routing.target_files,
                        dependencies=[],
                        expected_outcome="Functional implementation meeting acceptance criteria."
                    )
                ],
                testing_strategy=f"Targeted pytest execution on {routing.target_test_files}",
                risk_assessment="Low risk: isolated change scoped to target module and test file.",
                created_at=datetime.now().isoformat()
            )
            db_service.save_plan(plan)
            tracker.end_span("requirement", "concise_plan_synthesis", t_span)

            db_service.add_log(
                run_id=run_id,
                stage="planner",
                agent_role="Codebase Analyst & Planner Agent",
                event_type="info",
                message=f"Concise implementation plan synthesized for {len(planned_files)} target files. Bypassed redundant multi-minute LLM planning roundtrip.",
                details={"target_files": routing.target_files}
            )

            # Fast Path Step 3: Single Coding Agent (with 1.5B high-speed model)
            t_span = tracker.start_span("coder", "code_generation")
            code_changes = await coder_service.execute_plan(
                run_id=run_id,
                model_name=effective_model,
                temperature=temperature
            )
            tracker.end_span("coder", "code_generation", t_span)

            # Fast Path Step 4: Targeted Test Execution
            t_span = tracker.start_span("testing", "targeted_pytest")
            test_run = await asyncio.to_thread(test_runner_service.run_tests, 
                run_id=run_id,
                attempt_number=1,
                target_test_files=routing.target_test_files
            )
            tracker.end_span("testing", "targeted_pytest", t_span)

            # Escalation Check: If targeted tests fail or AST syntax is invalid, escalate to full recovery loop
            any_syntax_invalid = any(not c.ast_valid for c in code_changes)
            if test_run.status != "PASSED" or any_syntax_invalid:
                db_service.add_log(
                    run_id=run_id,
                    stage="debugger",
                    agent_role="System Orchestrator",
                    event_type="escalation",
                    message=f"Targeted verification failed (Status: {test_run.status}, Syntax Valid: {not any_syntax_invalid}). Escalating to Bounded Recovery Debugger Loop.",
                    details={"exit_code": test_run.exit_code, "failed_tests": test_run.failed_tests}
                )
                await debugger_service.run_testing_and_recovery_loop(
                    run_id=run_id,
                    max_recovery_retries=max_recovery_retries,
                    model_name=effective_model,
                    target_test_files=routing.target_test_files
                )

            # Fast Path Step 5: Independent Verification
            t_span = tracker.start_span("verifier", "verification")
            verification_report = await verifier_service.verify_run(
                run_id=run_id,
                model_name=effective_model,
                temperature=0.1, execution_started=execution_started
            )
            tracker.end_span("verifier", "verification", t_span)

            # Fast Path Completion & Drift Verification Check
            comp_check = drift_controller_service.check_completion(run_id)
            if comp_check.allowed and verification_report.overall_verdict == "VERIFIED_PASSED":
                goal_tracker_service.complete_subtask(run_id, "SUBTASK-1", evidence=verification_report.review_summary)
                goal_tracker_service.terminate_task(run_id, status="completed", reason="criteria_verified", evidence={"verdict": verification_report.overall_verdict})
            else:
                reason = "verification_failed" if verification_report.overall_verdict != "VERIFIED_PASSED" else comp_check.reason
                goal_tracker_service.terminate_task(run_id, status="failed", reason=reason, evidence={"verdict": verification_report.overall_verdict})

        # =====================================================================
        # STANDARD MULTI-AGENT WORKFLOW FOR MEDIUM / COMPLEX TASKS
        # =====================================================================
        else:
            logger.info(f"[{run_id}] Executing Standard Multi-Agent Workflow for {routing.task_tier} task.")
            goal_tracker_service.start_subtask(run_id, "SUBTASK-1")
            
            # Step 2: Full Directory Inspection
            t_span = tracker.start_span("workspace", "full_inspection")
            inspection = workspace_service.inspect_directory(target_repo, run_id=run_id)
            tracker.end_span("workspace", "full_inspection", t_span)

            # Step 3: Requirement Analyst Agent (Ollama / Goal Model)
            db_service.add_log(
                run_id=run_id,
                stage="requirement",
                agent_role="Requirement Analyst Agent",
                event_type="info",
                message="Extracting requirements, constraints, and acceptance criteria.",
                details={"model": effective_model}
            )
            t_span = tracker.start_span("requirement", "goal_parsing")
            # The already-confirmed goal remains authoritative; never reparse it here.
            tracker.end_span("requirement", "goal_parsing", t_span)

            # Step 4: Codebase Analyst + Planner Agent
            db_service.add_log(
                run_id=run_id,
                stage="planner",
                agent_role="Codebase Analyst & Planner Agent",
                event_type="info",
                message="Analyzing repository structure and creating step-by-step implementation plan.",
                details={"repo_path": target_repo}
            )
            t_span = tracker.start_span("planner", "plan_generation")
            plan = await planner_service.generate_plan(
                run_id=run_id,
                repo_path=target_repo,
                model_name=effective_model,
                temperature=temperature
            )
            tracker.end_span("planner", "plan_generation", t_span)

            goal_tracker_service.complete_subtask(run_id, "SUBTASK-1", evidence="Architecture plan generated")
            goal_tracker_service.start_subtask(run_id, "SUBTASK-2")

            # Step 5: Coding Agent
            db_service.add_log(
                run_id=run_id,
                stage="coder",
                agent_role="Coding Agent",
                event_type="info",
                message=f"Writing code changes for {len(plan.planned_files) if plan else 0} planned files.",
                details={"files": [pf.path for pf in plan.planned_files] if plan else []}
            )
            t_span = tracker.start_span("coder", "code_generation")
            code_changes = await coder_service.execute_plan(
                run_id=run_id,
                model_name=effective_model,
                temperature=temperature
            )
            tracker.end_span("coder", "code_generation", t_span)

            goal_tracker_service.complete_subtask(run_id, "SUBTASK-2", evidence=f"{len(code_changes or [])} files modified")
            goal_tracker_service.start_subtask(run_id, "SUBTASK-3")

            # Step 6: Testing + Debugging Agent (Bounded Recovery Loop)
            db_service.add_log(
                run_id=run_id,
                stage="testing",
                agent_role="Test & Debugging Agent",
                event_type="info",
                message="Executing automated test suite with bounded recovery self-healing.",
                details={"max_retries": max_recovery_retries}
            )
            t_span = tracker.start_span("testing", "recovery_loop")
            await debugger_service.run_testing_and_recovery_loop(
                run_id=run_id,
                max_recovery_retries=max_recovery_retries,
                model_name=effective_model
            )
            tracker.end_span("testing", "recovery_loop", t_span)

            # Step 7: Independent Code Reviewer / Verifier
            db_service.add_log(
                run_id=run_id,
                stage="verifier",
                agent_role="Independent Code Reviewer",
                event_type="info",
                message="Performing independent code review and acceptance criteria verification.",
                details={}
            )
            t_span = tracker.start_span("verifier", "verification")
            verification_report = await verifier_service.verify_run(
                run_id=run_id,
                model_name=effective_model,
                temperature=0.1, execution_started=execution_started
            )
            tracker.end_span("verifier", "verification", t_span)

            # Standard Path Completion & Drift Verification Check
            comp_check = drift_controller_service.check_completion(run_id)
            if comp_check.allowed and verification_report.overall_verdict in ("VERIFIED_PASSED", "VERIFIED_WITH_WARNINGS"):
                goal_tracker_service.complete_subtask(run_id, "SUBTASK-3", evidence=verification_report.review_summary)
                goal_tracker_service.terminate_task(run_id, status="completed", reason="criteria_verified", evidence={"verdict": verification_report.overall_verdict})
            else:
                reason = "verification_failed" if verification_report.overall_verdict not in ("VERIFIED_PASSED", "VERIFIED_WITH_WARNINGS") else comp_check.reason
                goal_tracker_service.terminate_task(run_id, status="failed", reason=reason, evidence={"verdict": verification_report.overall_verdict})

        return db_service.get_run_record(run_id)

orchestrator_service = OrchestratorService()
