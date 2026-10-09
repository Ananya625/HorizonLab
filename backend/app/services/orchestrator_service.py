import uuid
import logging
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

logger = logging.getLogger(__name__)

class OrchestratorService:
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
        goal_model = await goal_parser_service.parse_request(
            request_text=request_text,
            model_name=model_name,
            run_id=run_id,
            temperature=temperature
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
        plan = await planner_service.generate_plan(
            run_id=run_id,
            repo_path=target_repo,
            model_name=model_name,
            temperature=temperature
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
        code_changes = await coder_service.execute_plan(
            run_id=run_id,
            model_name=model_name,
            temperature=temperature
        )

        # Step 5: Testing + Debugging Agent (Bounded Recovery Loop)
        db_service.add_log(
            run_id=run_id,
            stage="testing",
            agent_role="Test & Debugging Agent",
            event_type="info",
            message="Executing automated test suite with bounded recovery self-healing.",
            details={"max_retries": max_recovery_retries}
        )
        test_recovery_result = await debugger_service.run_testing_and_recovery_loop(
            run_id=run_id,
            max_recovery_retries=max_recovery_retries,
            model_name=model_name
        )

        # Step 6: Independent Code Reviewer / Verifier
        db_service.add_log(
            run_id=run_id,
            stage="verifier",
            agent_role="Independent Code Reviewer",
            event_type="info",
            message="Performing independent code review and acceptance criteria verification.",
            details={}
        )
        verification_report = await verifier_service.verify_run(
            run_id=run_id,
            model_name=model_name,
            temperature=0.1
        )

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
            message=f"Autonomous workflow completed successfully! Verdict: {verification_report.overall_verdict}, Success Rate: {verification_report.pass_rate_percent}%.",
            details={"verdict": verification_report.overall_verdict, "pass_rate": verification_report.pass_rate_percent}
        )

        return db_service.get_run_record(run_id)

orchestrator_service = OrchestratorService()
