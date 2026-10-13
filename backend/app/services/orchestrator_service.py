import asyncio
import uuid
import logging
import time
from typing import Dict, Any, Optional
from datetime import datetime
from ..models.schema import (
    RunRecord,
    RunPipelineRequest
)
from .db import db_service
from .workspace_service import workspace_service
from .goal_parser_service import goal_parser_service
from .planner_service import planner_service
from .coder_service import coder_service
from .test_runner_service import test_runner_service
from .debugger_service import debugger_service
from .verifier_service import verifier_service
from .feature_analytics_service import feature_analytics_service, validate_model_name
from .capability_estimator import CapabilityPolicyEngine

logger = logging.getLogger(__name__)


class OrchestratorService:
    async def _handle_policy_action(
        self,
        run_id: str,
        state: dict[str, Any],
        max_retry_budget: Optional[int] = None,
    ) -> dict[str, Any]:
        action = state.get("risk_action", "continue")
        step_index = int(state.get("_step_index", 0))
        stage = str(state.get("stage", "unknown"))
        risk_score = state.get("risk_score")
        risk_reasons = state.get("risk_reasons", [])

        db_service.add_log(
            run_id=run_id,
            stage=stage,
            agent_role="System Orchestrator",
            event_type="policy_recommendation",
            message=(
                f"Policy recommends '{action}' at risk score {risk_score:.3f}."
                if risk_score is not None
                else f"Policy recommends '{action}'; no validated risk score is available."
            ),
            details={
                "step_index": step_index,
                "recommended_action": action,
                "risk_score": risk_score,
                "risk_reasons": risk_reasons,
                "risk_model_version": state.get("risk_model_version"),
            },
        )

        if action == "continue":
            outcome = {"continued": True, "stage": stage}
            feature_analytics_service.record_policy_execution(
                run_id, step_index, "continue", "executed", outcome
            )
            db_service.add_log(
                run_id=run_id,
                stage=stage,
                agent_role="System Orchestrator",
                event_type="policy_action_executed",
                message="Policy allowed execution to continue.",
                details={"recommended_action": action, "executed_action": "continue", **outcome},
            )
            return {"stop": False}

        if action == "inspect":
            changes = db_service.get_code_changes(run_id)
            plan = db_service.get_plan(run_id)
            planned_files = {
                planned.path.replace("\\", "/")
                for planned in (plan.planned_files if plan else [])
            }
            invalid_files = [change.file_path for change in changes if not change.ast_valid]
            unplanned_files = [
                change.file_path for change in changes
                if planned_files and change.file_path.replace("\\", "/") not in planned_files
            ]
            outcome = {
                "inspected_change_count": len(changes),
                "invalid_ast_files": invalid_files,
                "unplanned_files": unplanned_files,
                "safe_to_continue": not invalid_files,
            }
            feature_analytics_service.record_policy_execution(
                run_id, step_index, "inspect", "executed", outcome
            )
            db_service.add_log(
                run_id=run_id,
                stage=stage,
                agent_role="System Orchestrator",
                event_type="policy_action_executed",
                message=(
                    "Policy inspection completed; invalid syntax found."
                    if invalid_files else "Policy inspection completed; no invalid syntax found."
                ),
                details={"recommended_action": action, "executed_action": "inspect", **outcome},
            )
            return {"stop": bool(invalid_files), "stop_reason": "inspection_found_invalid_ast"}

        if action == "switch_strategy":
            attempt_number = int(state.get("details", {}).get("attempt_number", 1) or 1)
            if stage == "testing" and max_retry_budget is not None and attempt_number > max_retry_budget:
                outcome = {
                    "strategy_override": None,
                    "verified": False,
                    "reason": "retry_budget_exhausted",
                }
                feature_analytics_service.record_policy_execution(
                    run_id, step_index, "switch_strategy", "skipped", outcome
                )
                db_service.add_log(
                    run_id=run_id,
                    stage=stage,
                    agent_role="System Orchestrator",
                    event_type="policy_action_skipped",
                    message="Strategy switch skipped because the recovery budget is exhausted.",
                    details={"recommended_action": action, **outcome},
                )
                return {"stop": False}
            strategy = "alternative_strategy"
            outcome = {
                "strategy_override": strategy,
                "applies_to": "next recovery attempt",
                "verified": False,
            }
            feature_analytics_service.record_policy_execution(
                run_id, step_index, "switch_strategy", "queued", outcome
            )
            db_service.add_log(
                run_id=run_id,
                stage=stage,
                agent_role="System Orchestrator",
                event_type="policy_action_queued",
                message=f"Recovery strategy '{strategy}' queued for the next repair attempt.",
                details={"recommended_action": action, **outcome},
            )
            return {
                "stop": False,
                "strategy_override": strategy,
                "strategy_step_index": step_index,
            }

        if action == "ask_human":
            approval = feature_analytics_service.create_policy_approval(run_id, step_index)
            feature_analytics_service.record_policy_execution(
                run_id,
                step_index,
                "ask_human",
                "pending_approval",
                {"approval_id": approval["approval_id"]},
            )
            db_service.update_run_status(run_id, f"{stage}_awaiting_approval", "awaiting_approval")
            db_service.add_log(
                run_id=run_id,
                stage=stage,
                agent_role="System Orchestrator",
                event_type="policy_approval_required",
                message="Execution paused for human approval before continuing.",
                details={
                    "approval_id": approval["approval_id"],
                    "step_index": step_index,
                    "recommended_action": action,
                    "risk_score": risk_score,
                },
            )
            while True:
                approval_state = feature_analytics_service.get_policy_approval(
                    run_id, approval["approval_id"]
                )
                if not approval_state:
                    raise LookupError(f"Approval {approval['approval_id']} disappeared")
                if approval_state["status"] != "pending":
                    break
                await asyncio.sleep(0.25)

            approved = approval_state["status"] == "approved"
            outcome = {
                "approval_id": approval["approval_id"],
                "decision": approval_state["status"],
                "comment": approval_state["comment"],
                "pipeline_continues": approved,
                "verified": True,
            }
            feature_analytics_service.record_policy_execution(
                run_id, step_index, "ask_human", "executed", outcome
            )
            db_service.update_run_status(run_id, stage, "in_progress")
            db_service.add_log(
                run_id=run_id,
                stage=stage,
                agent_role="System Orchestrator",
                event_type="policy_approval_resolved",
                message=(
                    "Human approved continuing the autonomous run."
                    if approved else "Human rejected continuation; stopping autonomous work."
                ),
                details={"executed_action": "ask_human", **outcome},
            )
            return {
                "stop": not approved,
                "stop_reason": "human_rejected",
                "human_intervention": True,
            }

        if action == "stop":
            outcome = {
                "pipeline_continues": False,
                "mutations_halted": True,
                "verified": True,
            }
            feature_analytics_service.record_policy_execution(
                run_id, step_index, "stop", "executed", outcome
            )
            db_service.add_log(
                run_id=run_id,
                stage=stage,
                agent_role="System Orchestrator",
                event_type="policy_action_executed",
                message="Policy stopped further autonomous execution.",
                details={"recommended_action": action, "executed_action": "stop", **outcome},
            )
            return {"stop": True, "stop_reason": "policy_stop"}

        raise ValueError(f"Unsupported policy action: {action}")

    def _stop_policy_run(
        self,
        run_id: str,
        stage: str,
        reason: str,
        pending_strategy_step_index: Optional[int] = None,
    ) -> RunRecord:
        if pending_strategy_step_index is not None:
            feature_analytics_service.record_policy_execution(
                run_id,
                pending_strategy_step_index,
                "switch_strategy",
                "skipped",
                {"verified": False, "reason": "pipeline_stopped_before_recovery"},
            )
        db_service.update_run_status(run_id, "stopped", "policy_stopped")
        db_service.add_log(
            run_id=run_id,
            stage="stopped",
            agent_role="System Orchestrator",
            event_type="warning",
            message="Autonomous pipeline stopped at a safe stage boundary.",
            details={"stage": stage, "reason": reason},
        )
        record = db_service.get_run_record(run_id)
        if not record:
            raise LookupError(f"Run {run_id} disappeared after policy stop")
        return record

    async def run_full_pipeline(
        self,
        request_text: str,
        repo_path: Optional[str] = None,
        model_name: Optional[str] = "qwen2.5-coder:7b",
        temperature: float = 0.2,
        max_recovery_retries: int = 3,
        existing_run_id: Optional[str] = None
    ) -> RunRecord:
        run_id = existing_run_id or f"run_{uuid.uuid4().hex[:8]}"
        task_id = f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        target_repo = repo_path or workspace_service.get_default_repo_path()
        pipeline_started = time.perf_counter()

        # Validate model_name at pipeline entry
        try:
            model_name = validate_model_name(model_name)
        except ValueError as exc:
            logger.error("Invalid model_name at pipeline entry: %s", exc)
            raise

        # Step 1: Initialize Run Record in SQLite
        run_record = db_service.create_or_update_run(
            run_id=run_id,
            task_id=task_id,
            title=request_text[:80] + ("..." if len(request_text) > 80 else ""),
            prompt=request_text,
            repo_path=target_repo,
            current_stage="workspace",
            status="in_progress"
        )
        recovery_mean, recovery_samples = feature_analytics_service.get_policy_capability(
            model_name, "recovery"
        )
        effective_retry_budget = (
            CapabilityPolicyEngine.get_retry_budget(
                recovery_mean, max_recovery_retries, recovery_samples
            )
            if max_recovery_retries > 0 else 0
        )
        queued_strategy_override: Optional[str] = None
        queued_strategy_step_index: Optional[int] = None

        db_service.add_log(
            run_id=run_id,
            stage="workspace",
            agent_role="System Orchestrator",
            event_type="info",
            message=f"Initialized autonomous coding workflow run '{run_id}' for workspace at '{target_repo}'.",
            details={"task_id": task_id, "prompt": request_text}
        )

        # Step 2: Requirement Analyst Agent (Ollama / Goal Model)
        db_service.add_log(
            run_id=run_id,
            stage="requirement",
            agent_role="Requirement Analyst Agent",
            event_type="info",
            message="Extracting requirements, constraints, and acceptance criteria.",
            details={"model": model_name}
        )
        db_service.add_log(
            run_id=run_id,
            stage="testing",
            agent_role="System Orchestrator",
            event_type="info",
            message=(
                f"Adaptive recovery budget set to {effective_retry_budget} "
                f"(requested {max_recovery_retries}; recovery evidence n={recovery_samples}, "
                f"posterior={recovery_mean:.3f})."
            ),
            details={
                "requested_retry_budget": max_recovery_retries,
                "effective_retry_budget": effective_retry_budget,
                "recovery_sample_size": recovery_samples,
                "recovery_posterior_mean": recovery_mean,
            },
        )
        stage_started = time.perf_counter()
        goal_model = await goal_parser_service.parse_request(
            request_text=request_text,
            model_name=model_name,
            run_id=run_id,
            temperature=temperature
        )
        # Trajectory observation only — no binary capability update
        policy_state = feature_analytics_service.record_stage(
            run_id, "requirement", True, model_name,
            details={
                "subgoals": len(goal_model.sub_goals),
                "criteria": len(goal_model.success_criteria),
            },
            elapsed_seconds=time.perf_counter() - stage_started,
            provenance="llm",
        )
        policy_result = await self._handle_policy_action(run_id, policy_state, effective_retry_budget)
        queued_strategy_override = policy_result.get("strategy_override", queued_strategy_override)
        queued_strategy_step_index = policy_result.get(
            "strategy_step_index", queued_strategy_step_index
        )
        if policy_result.get("stop"):
            return self._stop_policy_run(
                run_id, "requirement", policy_result["stop_reason"],
                queued_strategy_step_index,
            )

        # Step 3: Codebase Analyst + Planner Agent
        db_service.add_log(
            run_id=run_id,
            stage="planner",
            agent_role="Codebase Analyst & Planner Agent",
            event_type="info",
            message="Analyzing repository structure and creating step-by-step implementation plan.",
            details={"repo_path": target_repo}
        )
        stage_started = time.perf_counter()
        plan = await planner_service.generate_plan(
            run_id=run_id,
            repo_path=target_repo,
            model_name=model_name,
            temperature=temperature
        )
        policy_state = feature_analytics_service.record_stage(
            run_id, "planner", bool(plan.steps), model_name,
            details={
                "planned_steps": len(plan.steps),
                "planned_files": len(plan.planned_files),
            },
            elapsed_seconds=time.perf_counter() - stage_started,
            provenance="llm",
        )
        policy_result = await self._handle_policy_action(run_id, policy_state, effective_retry_budget)
        queued_strategy_override = policy_result.get("strategy_override", queued_strategy_override)
        queued_strategy_step_index = policy_result.get(
            "strategy_step_index", queued_strategy_step_index
        )
        if policy_result.get("stop"):
            return self._stop_policy_run(
                run_id, "planner", policy_result["stop_reason"],
                queued_strategy_step_index,
            )

        # Step 4: Coding Agent
        db_service.add_log(
            run_id=run_id,
            stage="coder",
            agent_role="Coding Agent",
            event_type="info",
            message=f"Writing code changes for {len(plan.planned_files)} planned files.",
            details={"files": [pf.path for pf in plan.planned_files]}
        )
        stage_started = time.perf_counter()
        code_changes = await coder_service.execute_plan(
            run_id=run_id,
            model_name=model_name,
            temperature=temperature
        )
        policy_state = feature_analytics_service.record_stage(
            run_id, "coder", bool(code_changes), model_name,
            details={
                "changes_count": len(code_changes),
                "plan_discrepancy": abs(len(code_changes) - len(plan.planned_files)),
                "diff_size": len(code_changes),
            },
            elapsed_seconds=time.perf_counter() - stage_started,
            provenance="llm",
        )
        policy_result = await self._handle_policy_action(run_id, policy_state, effective_retry_budget)
        queued_strategy_override = policy_result.get("strategy_override", queued_strategy_override)
        queued_strategy_step_index = policy_result.get(
            "strategy_step_index", queued_strategy_step_index
        )
        if policy_result.get("stop"):
            return self._stop_policy_run(
                run_id, "coder", policy_result["stop_reason"],
                queued_strategy_step_index,
            )

        # Step 5: Testing + Debugging Agent (Bounded Recovery Loop)
        # NOTE: record_stage for "testing" is done INSIDE debugger_service
        # to avoid duplicate testing events. The orchestrator records only
        # the debugger outcome.
        db_service.add_log(
            run_id=run_id,
            stage="testing",
            agent_role="Test & Debugging Agent",
            event_type="info",
            message="Executing automated test suite with bounded recovery self-healing.",
            details={
                "requested_max_retries": max_recovery_retries,
                "effective_max_retries": effective_retry_budget,
            }
        )
        stage_started = time.perf_counter()
        test_recovery_result = await debugger_service.run_testing_and_recovery_loop(
            run_id=run_id,
            max_recovery_retries=effective_retry_budget,
            model_name=model_name,
            policy_handler=lambda state: self._handle_policy_action(
                run_id, state, effective_retry_budget
            ),
            strategy_override=queued_strategy_override,
            strategy_override_step_index=queued_strategy_step_index,
        )
        final_test = test_recovery_result.get("final_test_result")
        test_passed = bool(final_test and final_test.status == "PASSED")
        debugger_elapsed = time.perf_counter() - stage_started

        # Record debugger outcome only (testing events are recorded by debugger_service)
        policy_state = feature_analytics_service.record_stage(
            run_id, "debugger", bool(test_recovery_result.get("resolved")),
            model_name,
            event_type="recovery_completed" if test_recovery_result.get("resolved") else "recovery_incomplete",
            details={"resolved": bool(test_recovery_result.get("resolved"))},
            elapsed_seconds=debugger_elapsed,
            provenance="llm",
        )
        if test_recovery_result.get("policy_stopped"):
            return self._stop_policy_run(
                run_id, "debugger", test_recovery_result.get("stop_reason", "policy_stop")
            )
        policy_result = await self._handle_policy_action(run_id, policy_state, effective_retry_budget)
        if policy_result.get("stop"):
            return self._stop_policy_run(run_id, "debugger", policy_result["stop_reason"])

        # Step 6: Independent Code Reviewer / Verifier
        db_service.add_log(
            run_id=run_id,
            stage="verifier",
            agent_role="Independent Code Reviewer",
            event_type="info",
            message="Performing independent code review and acceptance criteria verification.",
            details={}
        )
        stage_started = time.perf_counter()
        verification_report = await verifier_service.verify_run(
            run_id=run_id,
            model_name=model_name,
            temperature=0.1,
            execution_started_at=pipeline_started,
        )
        verdict = str(verification_report.overall_verdict)
        verifier_success = any(token in verdict.upper() for token in ("PASSED", "VERIFIED"))
        policy_state = feature_analytics_service.record_stage(
            run_id, "verifier", verifier_success, model_name,
            details={
                "verdict": verdict,
                "pass_rate_percent": verification_report.pass_rate_percent,
            },
            elapsed_seconds=time.perf_counter() - stage_started,
            provenance="llm",
        )
        policy_result = await self._handle_policy_action(run_id, policy_state, effective_retry_budget)
        if policy_result.get("stop"):
            return self._stop_policy_run(run_id, "verifier", policy_result["stop_reason"])

        # Step 7: Final Status Update
        db_service.create_or_update_run(
            run_id=run_id,
            task_id=task_id,
            title=request_text[:80],
            prompt=request_text,
            repo_path=target_repo,
            current_stage="completed",
            status="completed"
        )

        db_service.add_log(
            run_id=run_id,
            stage="completed",
            agent_role="System Orchestrator",
            event_type="success",
            message=(
                f"Autonomous workflow completed. Verdict: {verification_report.overall_verdict}, "
                f"Success Rate: {verification_report.pass_rate_percent}%."
            ),
            details={
                "verdict": verification_report.overall_verdict,
                "pass_rate": verification_report.pass_rate_percent,
            }
        )

        # Persist recovery stats (legacy shim for backward compatibility)
        final_record = db_service.get_run_record(run_id)
        recovery_items = [
            item.model_dump() if hasattr(item, "model_dump") else dict(item)
            for item in (final_record.recovery_attempts if final_record else [])
        ]
        test_items = [
            item.model_dump() if hasattr(item, "model_dump") else dict(item)
            for item in (final_record.test_results if final_record else [])
        ]
        feature_analytics_service.record_recovery_stats(
            run_id=run_id,
            recovery_attempts=recovery_items,
            test_results=test_items,
            elapsed_seconds=debugger_elapsed,
            human_intervention_count=(
                feature_analytics_service.count_resolved_policy_approvals(run_id)
            ),
        )

        # ---------------------------------------------------------------
        # Task-level capability observation (ONE per run).
        # This is the ONLY point where binary capability posteriors are
        # updated. Evidence: independent verifier verdict + test pass rate.
        # ---------------------------------------------------------------
        latest_test = final_test
        total_tests = getattr(latest_test, "total_tests", 0) or 0
        passed_tests_count = getattr(latest_test, "passed_tests", 0) or 0

        pipeline_elapsed = time.perf_counter() - pipeline_started

        completed_policy_state = feature_analytics_service.record_stage(
            run_id, "completed", verifier_success, model_name,
            event_type="run_completed",
            details={
                "verdict": verdict,
                "recovery_attempts": len(recovery_items),
                "passed_tests": passed_tests_count,
                "tests_total": total_tests,
            },
            elapsed_seconds=pipeline_elapsed,
            # Pass the verified success flag — drives binary posterior update
            task_verified_success=verifier_success,
            provenance="llm",
        )
        feature_analytics_service.record_policy_execution(
            run_id,
            int(completed_policy_state.get("_step_index", 0)),
            "none",
            "not_applicable",
            {"reason": "terminal_run_observation"},
        )

        # Label trajectory steps so supervised predictor can train later
        feature_analytics_service.finalize_run_labels(
            run_id=run_id,
            task_failed=not verifier_success,
        )

        # Record hierarchical proficiencies for the 7 agents and system profile
        try:
            from .hierarchical_proficiency_service import hierarchical_proficiency_service
            hierarchical_proficiency_service.record_run_proficiencies(run_id, model_name=model_name)
        except Exception as exc:
            logger.warning("Failed to record hierarchical proficiencies for run %s: %s", run_id, exc)

        return db_service.get_run_record(run_id)


orchestrator_service = OrchestratorService()
