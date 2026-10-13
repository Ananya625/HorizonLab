import asyncio
from .workflow_service import observed, workflow
import ast
import re
import uuid
import logging
import time
from typing import Dict, Any, List, Optional
from datetime import datetime
from ..models.schema import (
    RecoveryAttempt,
    TestRunResult,
    CodeChange
)
from .db import db_service
from .workspace_service import workspace_service
from .test_runner_service import test_runner_service
from .ollama_service import ollama_service
from .telemetry_service import telemetry_manager
from .drift_controller_service import drift_controller_service
from .goal_tracker_service import goal_tracker_service
from .coder_service import extract_clean_python_code, validate_generated_tests

logger = logging.getLogger(__name__)

class DebuggerService:
    def __init__(
        self,
        max_history_attempts: int = 3,
        max_summary_chars: int = 350,
        max_traceback_chars: int = 800,
        max_code_chars: int = 1200
    ):
        self.max_history_attempts = max_history_attempts
        self.max_summary_chars = max_summary_chars
        self.max_traceback_chars = max_traceback_chars
        self.max_code_chars = max_code_chars

    def _extract_concise_error_summary(
        self,
        stdout: Optional[str],
        stderr: Optional[str],
        max_chars: Optional[int] = None
    ) -> str:
        """Deterministically extracts assertion errors, tracebacks, and failure lines capped to max_chars."""
        limit = max_chars if max_chars is not None else self.max_traceback_chars
        combined = ((stdout or "") + "\n" + (stderr or "")).strip()
        if not combined:
            return "No test failure output recorded."

        # Strip ANSI escape sequences
        clean_text = re.sub(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])", "", combined)
        lines = [line.strip() for line in clean_text.splitlines() if line.strip()]

        error_lines = []
        for line in lines:
            if (
                line.startswith("E   ") or
                line.startswith("FAILED ") or
                " FAILED" in line or
                line.startswith("ERROR ") or
                "assert " in line or
                any(err in line for err in (
                    "AssertionError", "TypeError", "ImportError", "ModuleNotFoundError",
                    "SyntaxError", "NameError", "AttributeError", "ZeroDivisionError",
                    "ValueError", "KeyError", "IndexError"
                ))
            ):
                error_lines.append(line)

        if error_lines:
            summary = "\n".join(error_lines)
        else:
            summary = "\n".join(lines[-8:])

        if len(summary) > limit:
            summary = summary[:limit].rstrip() + "\n... (traceback truncated for context)"
        return summary

    def format_recovery_history_context(
        self,
        history: List[RecoveryAttempt],
        max_attempts: Optional[int] = None,
        max_summary_chars: Optional[int] = None
    ) -> str:
        """Constructs bounded, structured cumulative retry memory for previous attempts in this run."""
        if not history:
            return ""

        limit = max_attempts if max_attempts is not None else self.max_history_attempts
        char_limit = max_summary_chars if max_summary_chars is not None else self.max_summary_chars

        # Take only the most recent 'limit' attempts
        relevant = history[-limit:]
        if not relevant:
            return ""

        sections = [
            "=== PREVIOUS RECOVERY ATTEMPTS IN THIS RUN (CUMULATIVE RETRY MEMORY) ===",
            "Analyze this historical execution evidence. Do NOT repeat strategies that already failed:\n"
        ]

        for att in relevant:
            # Determine outcome strictly: do not treat unknown test outcomes as failures
            if att.resolved or att.test_result_status == "PASSED":
                outcome = "SUCCEEDED"
                evidence = "Test suite passed cleanly."
                directive = "Fix resolved tests."
            elif att.test_result_status == "UNKNOWN" or (att.test_result_status is None and att.subsequent_test_run_id is None and not att.resolved):
                outcome = "UNKNOWN (Test outcome not verified)"
                evidence = "Subsequent test execution was not recorded or is pending."
                directive = "Test outcome unverified; do not assume this fix failed."
            elif att.test_result_status == "FAILED" or (att.subsequent_test_run_id is not None and not att.resolved) or (not att.resolved):
                outcome = "FAILED"
                err_text = (att.error_summary or att.failure_reason or "Subsequent test assertion failed.")
                evidence = err_text[:char_limit].strip()
                directive = "FAILED STRATEGY: Do NOT repeat this patch or assertion strategy without new evidence."
            else:
                outcome = "UNKNOWN"
                evidence = "Test outcome unverified."
                directive = "Outcome unverified."

            approach = (att.proposed_fix or att.diagnosis or "Unspecified fix approach")[:char_limit].strip()
            files_str = ", ".join(att.files_modified) if att.files_modified else "None"

            block = (
                f"--- Attempt #{att.attempt_number} ---\n"
                f"Approach Attempted: {approach}\n"
                f"Files Changed: {files_str}\n"
                f"Outcome: {outcome}\n"
                f"Test Evidence: {evidence}\n"
                f"Directive: {directive}"
            )
            sections.append(block)

        sections.append("==========================================================================")
        return "\n\n".join(sections)

    def _detect_repeated_approach(
        self,
        candidate_code: str,
        current_content: str,
        history: List[RecoveryAttempt],
        file_to_fix: str,
        past_code_changes: Optional[List[CodeChange]] = None
    ) -> Optional[str]:
        """Detects if candidate code repeats an unchanged file or an identical previously failed patch."""
        candidate_clean = candidate_code.strip()
        if not candidate_clean:
            return None

        # 1. Unchanged code: Candidate is identical to the file that just failed
        if current_content and candidate_clean == current_content.strip():
            return f"Candidate code for '{file_to_fix}' is identical to the currently failing file (no changes made)."

        # 2. Repeated failed patch from prior attempt in this run
        if past_code_changes and history:
            failed_attempt_numbers = {
                att.attempt_number for att in history
                if (not att.resolved and att.test_result_status != "PASSED")
            }
            if failed_attempt_numbers:
                for change in past_code_changes:
                    if change.file_path == file_to_fix and change.new_content:
                        if candidate_clean == change.new_content.strip():
                            return f"Candidate code for '{file_to_fix}' is identical to a patch previously applied that failed tests."

        return None

    @observed('debugger', 'stage', reason=None)
    async def run_testing_and_recovery_loop(
        self,
        run_id: str,
        max_recovery_retries: int = 3,
        model_name: Optional[str] = None,
        target_test_files: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Executes test suite and performs bounded self-healing recovery if failures occur."""
        
        attempt_number = 1
        current_test_result = await asyncio.to_thread(test_runner_service.run_tests, 
            run_id=run_id,
            attempt_number=attempt_number,
            target_test_files=target_test_files
        )
        recovery_attempts: List[RecoveryAttempt] = []

        while current_test_result.status != "PASSED" and attempt_number <= max_recovery_retries:
            tracker = telemetry_manager.get(run_id)
            if tracker:
                tracker.record_retry()

            # Retrieve prior recovery attempts from SQLite for this run
            prior_history = db_service.get_recovery_attempts(run_id)

            db_service.add_log(
                run_id=run_id,
                stage="debugger",
                agent_role="Debugging Agent",
                event_type="recovery",
                message=f"Test failure detected on attempt #{attempt_number}. Initiating bounded self-healing recovery.",
                details={
                    "exit_code": current_test_result.exit_code,
                    "failed_tests": current_test_result.failed_tests,
                    "prior_attempts_count": len(prior_history)
                }
            )

            # Analyze failure
            diagnosis = self._diagnose_failure(current_test_result)
            
            fixed_files = []
            started = time.perf_counter()
            proposed_fix_summary = diagnosis['proposed_fix']
            initial_error_summary = self._extract_concise_error_summary(current_test_result.stdout, current_test_result.stderr)

            # Record recovery attempt
            rec_id = f"rec_{uuid.uuid4().hex[:8]}"
            recovery = RecoveryAttempt(
                id=rec_id,
                run_id=run_id,
                attempt_number=attempt_number,
                failure_reason=diagnosis["failure_reason"],
                diagnosis=diagnosis["diagnosis"],
                root_cause_analysis=diagnosis["root_cause"],
                proposed_fix=proposed_fix_summary,
                files_modified=fixed_files,
                resolved=False,
                started_at=datetime.now().isoformat(),
                test_run_id=current_test_result.id,
                error_summary=initial_error_summary,
                created_at=datetime.now().isoformat()
            )

            db_service.save_recovery_attempt(recovery)
            with workflow.attempt(run_id, recovery_id=rec_id, reason="recovery"):
                try:
                    recovery.files_modified = await self._apply_recovery_fix(run_id, current_test_result, diagnosis, model_name, history=prior_history)
                    attempt_number += 1
                    current_test_result = await asyncio.to_thread(test_runner_service.run_tests, run_id=run_id, attempt_number=attempt_number, target_test_files=target_test_files)
                    recovery.local_tests_passed = current_test_result.status == 'PASSED'
                    recovery.termination_reason = 'local_tests_passed' if recovery.local_tests_passed else 'tests_failed'
                except Exception:
                    recovery.termination_reason = 'repair_error'
                    raise
                finally:
                    recovery.ended_at = datetime.now().isoformat()
                    recovery.duration_seconds = time.perf_counter()-started
                    db_service.save_recovery_attempt(recovery)
            
            # Record subsequent test result outcome
            recovery.subsequent_test_run_id = current_test_result.id
            recovery.test_result_status = current_test_result.status

            if current_test_result.status == "PASSED":
                recovery.resolved = False  # Only an independent evaluator can establish recovery.
                db_service.add_log(
                    run_id=run_id,
                    stage="debugger",
                    agent_role="Debugging Agent",
                    event_type="success",
                    message=f"Recovery Attempt #{recovery.attempt_number}: local tests pass; independent recovery verification is pending.",
                    details={"attempt": recovery.attempt_number}
                )
            else:
                recovery.resolved = False
                recovery.error_summary = self._extract_concise_error_summary(
                    current_test_result.stdout, current_test_result.stderr
                )
            
            # Persist complete attempt outcome in SQLite
            db_service.save_recovery_attempt(recovery)
            recovery_attempts.append(recovery)

        return {
            "final_test_result": current_test_result,
            "recovery_attempts": recovery_attempts,
            "total_attempts": attempt_number,
            "resolved": False,
            "local_tests_passed": current_test_result.status == "PASSED"
        }

    def _diagnose_failure(self, test_result: TestRunResult) -> Dict[str, str]:
        stdout = (test_result.stdout or "") + "\n" + (test_result.stderr or "")
        
        if test_result.exit_code == 5 or "collected 0 items" in stdout or "no tests were collected" in stdout.lower():
            return {
                "failure_reason": "No Tests Collected",
                "diagnosis": "Test runner collected 0 test functions. The test file is empty or lacks 'def test_' functions.",
                "root_cause": "The test file does not define test functions starting with 'test_' or was wrapped in JSON syntax.",
                "proposed_fix": "Generate valid test functions ('def test_...(): assert ...') importing and asserting functions from the implementation module."
            }
        elif "ImportError" in stdout or "ModuleNotFoundError" in stdout:
            return {
                "failure_reason": "Module or Symbol Import Failure",
                "diagnosis": "Missing required module import or circular dependency in application layer.",
                "root_cause": "The test runner was unable to resolve symbols imported across module boundaries.",
                "proposed_fix": "Add missing module exports and ensure relative paths are resolved."
            }
        elif "AssertionError" in stdout or "assert" in stdout:
            return {
                "failure_reason": "Assertion Mismatch in Test Assertion",
                "diagnosis": "A test assertion disagreed with the observed result.",
                "root_cause": "Unknown; assertion evidence does not establish a specific root cause.",
                "proposed_fix": "Inspect the traceback and cumulative retry history; repair the generated test or implementation without claiming independent recovery."
            }
        else:
            return {
                "failure_reason": "General Test Suite Failure",
                "diagnosis": "Test runner reported non-zero exit code during execution.",
                "root_cause": "Unhandled exception or syntax anomaly in test execution environment.",
                "proposed_fix": "Patch exception handling and re-align test fixtures."
            }

    async def _apply_recovery_fix(
        self,
        run_id: str,
        test_result: TestRunResult,
        diagnosis: Dict[str, str],
        model_name: Optional[str],
        history: Optional[List[RecoveryAttempt]] = None
    ) -> List[str]:
        plan = db_service.get_plan(run_id)
        repo_path = plan.target_repo_path if plan else workspace_service.get_default_repo_path()
        goal_model = db_service.get_goal_model(run_id)

        # 1. Retrieve prior recovery attempts and past code changes for this run
        prior_history = history if history is not None else db_service.get_recovery_attempts(run_id)
        past_code_changes = db_service.get_code_changes(run_id)

        # 2. Extract structured concise error summary
        concise_error = self._extract_concise_error_summary(test_result.stdout, test_result.stderr)

        # 3. Build bounded cumulative retry memory context
        history_context = self.format_recovery_history_context(prior_history)
        history_block = f"\n{history_context}\n" if history_context else ""

        # Find target files
        impl_files = [pf.path for pf in plan.planned_files if pf.action != "test" and "test" not in pf.path] if plan else ["app/service.py"]
        test_files = [pf.path for pf in plan.planned_files if pf.action == "test" or "test" in pf.path] if plan else ["tests/test_service.py"]

        impl_file = impl_files[0] if impl_files else "app/service.py"
        test_file = test_files[0] if test_files else "tests/test_service.py"

        impl_content = workspace_service.read_file(repo_path, impl_file) or ""
        test_content = workspace_service.read_file(repo_path, test_file) or ""

        # Extract real functions/classes from impl_file via AST
        exported_funcs = []
        exported_classes = []
        if impl_content:
            try:
                tree = ast.parse(impl_content)
                exported_funcs = [
                    node.name for node in ast.walk(tree) 
                    if isinstance(node, ast.FunctionDef) and not node.name.startswith("_") and not node.name.startswith("test_")
                ]
                exported_classes = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
            except Exception:
                pass

        # Decide which file to fix:
        if not impl_files:
            raise ValueError('Recovery requires a planned implementation file; tests are immutable')
        file_to_fix = impl_file
        current_content = impl_content
        validate_generated_tests(test_file, test_content, {impl_file: impl_content})

        prompt = f"""Task: {goal_model.main_goal if goal_model else 'Fix test failure'}
The automated test runner failed with this error:
{concise_error}
{history_block}
Implementation module '{impl_file}':
{impl_content[:self.max_code_chars]}

Exported symbols in '{impl_file}':
Functions: {exported_funcs}
Classes: {exported_classes}

Existing tests '{test_file}' (immutable):
{test_content[:self.max_code_chars]}

Generate the complete, corrected Python code for '{file_to_fix}' so that:
1. Repair the implementation while preserving its public interface.
2. Do not edit, redefine, weaken or bypass tests; do not add test functions to implementation files.
3. It directly addresses the test failure evidence above and does NOT repeat previously failed approaches.
4. It passes cleanly. Return ONLY valid Python code."""

        messages = [
            {"role": "system", "content": "You are an Expert Debugging Agent. Output ONLY raw executable Python code for the file. Do NOT output JSON, dictionaries, or markdown wrappers. Return pure Python code starting with imports or def."},
            {"role": "user", "content": prompt}
        ]

        fixed_code = None
        try:
            resp = await ollama_service.chat_completion(
                messages=messages,
                model=model_name or ollama_service.default_model,
                temperature=0.1,
                num_predict=512,
                run_id=run_id,
                stage="debugger"
            )
            raw = resp.get("message", {}).get("content", "").strip()
            candidate = extract_clean_python_code(raw)
            if candidate and len(candidate) > 15:
                try:
                    ast.parse(candidate)

                    # Check for repeated failed approach / unchanged file
                    repeated_reason = self._detect_repeated_approach(
                        candidate, current_content, prior_history, file_to_fix, past_code_changes
                    )
                    if repeated_reason:
                        logger.warning(f"[{run_id}] Retry loop detected: {repeated_reason}. Re-prompting with directive.")
                        refine_msgs = list(messages) + [
                            {"role": "assistant", "content": candidate},
                            {
                                "role": "user",
                                "content": (
                                    f"CRITICAL: {repeated_reason}\n"
                                    f"Do NOT return identical or unchanged code. You must implement a materially different implementation fix based on the evidence."
                                )
                            }
                        ]
                        try:
                            refine_resp = await ollama_service.chat_completion(
                                messages=refine_msgs,
                                model=model_name or ollama_service.default_model,
                                temperature=0.3,
                                num_predict=512,
                                run_id=run_id,
                                stage="debugger"
                            )
                            refine_raw = refine_resp.get("message", {}).get("content", "").strip()
                            refine_candidate = extract_clean_python_code(refine_raw)
                            if refine_candidate and len(refine_candidate) > 15:
                                ast.parse(refine_candidate)
                                if not self._detect_repeated_approach(refine_candidate, current_content, prior_history, file_to_fix, past_code_changes):
                                    candidate = refine_candidate
                        except Exception as ref_err:
                            logger.warning(f"Refinement prompt error: {ref_err}")

                    fixed_code = candidate
                except SyntaxError:
                    pass
        except Exception as e:
            logger.warning(f"Debugger LLM chat error: {e}")

        if not fixed_code or self._detect_repeated_approach(fixed_code, current_content, prior_history, file_to_fix, past_code_changes):
            raise RuntimeError('Recovery failed: no valid, non-repeated implementation repair')
        compile(fixed_code, file_to_fix, 'exec')
        if any(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith('test_')
               for node in ast.walk(ast.parse(fixed_code))):
            raise ValueError('Recovery must repair implementation, not redefine tests')

        if fixed_code and fixed_code != current_content:
            drift_controller_service.reset_file_history(run_id, file_to_fix)
            db_service.invalidate_evaluation(run_id, 'Recovery changed code; verification must be refreshed')
            db_service.add_log(run_id, 'debugger', 'Debugging Agent', 'tool_call', 'Write recovery file', {'tool':'write_file','file':file_to_fix})
            workspace_service.write_file(repo_path, file_to_fix, fixed_code)
            diff_res = workspace_service.compute_diff(current_content, fixed_code, file_to_fix)

            change = CodeChange(
                id=f"change_rec_{uuid.uuid4().hex[:8]}",
                run_id=run_id,
                file_path=file_to_fix,
                action="modified",
                original_content=current_content,
                new_content=fixed_code,
                diff_patch=diff_res["diff_patch"],
                lines_added=diff_res["lines_added"],
                lines_removed=diff_res["lines_removed"],
                ast_valid=diff_res["ast_valid"]
            )
            db_service.save_code_change(change)
            goal_tracker_service.record_action(
                run_id=run_id,
                action_type="file_write",
                target=file_to_fix,
                payload_str=fixed_code,
                status="completed",
                details={"recovery": True, "lines_added": diff_res["lines_added"]}
            )
            return [file_to_fix]

        return []

debugger_service = DebuggerService()
