import uuid
import json
import ast
from typing import List, Optional
from datetime import datetime
from ..models.schema import (
    CodeChange,
    ImplementationPlan,
    GoalModel
)
from .ollama_service import ollama_service
from .workspace_service import workspace_service
from .db import db_service

CODER_SYSTEM_PROMPT = """You are the Senior Coding Agent in an autonomous software engineering system.

Implement the requested file in the language indicated by its path and existing content. Follow the task, implementation plan, constraints, and project conventions. Preserve existing behavior unless the task requires a change.

Return only the complete file contents. Do not include conversational markdown or prose."""

class CoderService:
    async def execute_plan(
        self,
        run_id: str,
        model_name: Optional[str] = "qwen2.5-coder:7b",
        temperature: float = 0.2
    ) -> List[CodeChange]:
        plan = db_service.get_plan(run_id)
        if not plan:
            raise ValueError(f"Plan for run_id '{run_id}' not found")
        goal_model = db_service.get_goal_model(run_id)
        if not goal_model:
            raise ValueError(f"Goal model for run_id '{run_id}' not found")

        repo_path = plan.target_repo_path
        code_changes: List[CodeChange] = []

        db_service.add_log(
            run_id=run_id,
            stage="coder",
            agent_role="Coding Agent",
            event_type="info",
            message=f"Starting implementation for {len(plan.planned_files)} planned files across {len(plan.steps)} steps.",
            details={"repo_path": repo_path}
        )

        if not plan.planned_files:
            raise ValueError(f"Plan for run_id '{run_id}' contains no planned files")

        # Generate and validate every file before writing any of them. This prevents
        # a model timeout or malformed response from leaving a half-applied plan.
        staged_files = []
        for planned_file in plan.planned_files:
            file_rel_path = planned_file.path
            action = planned_file.action
            description = planned_file.description

            original_content = workspace_service.read_file(repo_path, file_rel_path)

            db_service.add_log(
                run_id=run_id,
                stage="coder",
                agent_role="Coding Agent",
                event_type="tool_call",
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
                temperature=temperature
            )

            # Validate before any write.
            diff_res = workspace_service.compute_diff(original_content, new_content, file_rel_path)
            if not diff_res["ast_valid"]:
                raise RuntimeError(f"Generated invalid Python syntax for '{file_rel_path}'. No planned files were written.")
            staged_files.append((planned_file, original_content, new_content, diff_res))

        for planned_file, original_content, new_content, diff_res in staged_files:
            file_rel_path = planned_file.path
            workspace_service.write_file(repo_path, file_rel_path, new_content)

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
            message=f"Coding completed successfully. Created/updated {len(code_changes)} planned files.",
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
        temperature: float
    ) -> str:
        active_model = model_name or ollama_service.default_model
        constraints = [item.text for item in (goal_model.hard_constraints or [])]
        plan_data = plan.model_dump() if hasattr(plan, "model_dump") else str(plan)
        plan_context = (
            json.dumps(plan_data, ensure_ascii=False, default=str, indent=2)
            if isinstance(plan_data, dict) else plan_data
        )
        user_msg = f"""Task: {goal_model.main_goal}
Implementation plan:
{plan_context}

File to write: {file_rel_path}
Action: {action}
Description: {description}
Hard constraints:
{json.dumps(constraints, ensure_ascii=False, indent=2)}
Existing content:
{original_content if original_content is not None else '(new file)'}

Return the complete contents of this file only. Match the file's language and conventions. Do not return placeholders, sample implementations, tests for unrelated behavior, or explanatory prose."""
        try:
            response = await ollama_service.chat_completion(
                messages=[
                    {"role": "system", "content": CODER_SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                model=active_model,
                temperature=temperature,
                format_json=False,
            )
        except Exception as exc:
            raise RuntimeError(
                f"Code generation failed for '{file_rel_path}' with model '{active_model}' "
                f"at {ollama_service.host}: {exc}"
            ) from exc

        raw = response.get("message", {}).get("content", "")
        if not isinstance(raw, str) or not raw.strip():
            raise RuntimeError(f"Model '{active_model}' returned an empty result for '{file_rel_path}'.")

        cleaned = raw.strip()
        if "<think>" in cleaned and "</think>" in cleaned:
            import re
            cleaned = re.sub(r"<think>.*?</think>", "", cleaned, flags=re.DOTALL).strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()
        if not cleaned:
            raise RuntimeError(f"Model '{active_model}' returned no usable file content for '{file_rel_path}'.")
        if file_rel_path.lower().endswith(".py"):
            try:
                ast.parse(cleaned, filename=file_rel_path)
            except SyntaxError as exc:
                raise RuntimeError(
                    f"Model returned invalid Python for '{file_rel_path}' at line {exc.lineno}: {exc.msg}. "
                    "No generated files were written."
                ) from exc
        return cleaned

coder_service = CoderService()
