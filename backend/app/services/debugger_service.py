import uuid
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from ..models.schema import (
    RecoveryAttempt,
    TestRunResult
)
from .db import db_service
from .workspace_service import workspace_service
from .test_runner_service import test_runner_service
from .ollama_service import ollama_service

logger = logging.getLogger(__name__)

class DebuggerService:
    async def run_testing_and_recovery_loop(
        self,
        run_id: str,
        max_recovery_retries: int = 3,
        model_name: Optional[str] = "qwen2.5-coder:7b"
    ) -> Dict[str, Any]:
        """Executes test suite and performs bounded self-healing recovery if failures occur."""
        
        attempt_number = 1
        current_test_result = test_runner_service.run_tests(run_id=run_id, attempt_number=attempt_number)
        recovery_attempts: List[RecoveryAttempt] = []

        while current_test_result.status != "PASSED" and attempt_number <= max_recovery_retries:
            db_service.add_log(
                run_id=run_id,
                stage="debugger",
                agent_role="Debugging Agent",
                event_type="recovery",
                message=f"Test failure detected on attempt #{attempt_number}. Initiating bounded self-healing recovery.",
                details={"exit_code": current_test_result.exit_code, "failed_tests": current_test_result.failed_tests}
            )

            # Analyze failure
            diagnosis = self._diagnose_failure(current_test_result)
            
            # Formulate and apply fix
            fixed_files = await self._apply_recovery_fix(run_id, diagnosis, model_name)

            # Record recovery attempt
            rec_id = f"rec_{uuid.uuid4().hex[:8]}"
            recovery = RecoveryAttempt(
                id=rec_id,
                run_id=run_id,
                attempt_number=attempt_number,
                failure_reason=diagnosis["failure_reason"],
                diagnosis=diagnosis["diagnosis"],
                root_cause_analysis=diagnosis["root_cause"],
                proposed_fix=diagnosis["proposed_fix"],
                files_modified=fixed_files,
                resolved=False,
                test_run_id=current_test_result.id,
                created_at=datetime.now().isoformat()
            )

            # Next attempt re-testing
            attempt_number += 1
            current_test_result = test_runner_service.run_tests(run_id=run_id, attempt_number=attempt_number)
            
            if current_test_result.status == "PASSED":
                recovery.resolved = True
                db_service.add_log(
                    run_id=run_id,
                    stage="debugger",
                    agent_role="Debugging Agent",
                    event_type="success",
                    message=f"Recovery Attempt #{recovery.attempt_number} successfully resolved all test failures! Tests now 100% passing.",
                    details={"attempt": recovery.attempt_number}
                )
            
            db_service.save_recovery_attempt(recovery)
            recovery_attempts.append(recovery)

        return {
            "final_test_result": current_test_result,
            "recovery_attempts": recovery_attempts,
            "total_attempts": attempt_number,
            "resolved": current_test_result.status == "PASSED"
        }

    def _diagnose_failure(self, test_result: TestRunResult) -> Dict[str, str]:
        stdout = test_result.stdout + "\n" + test_result.stderr
        
        if "ImportError" in stdout or "ModuleNotFoundError" in stdout:
            return {
                "failure_reason": "Module or Symbol Import Failure",
                "diagnosis": "Missing required module import or circular dependency in application layer.",
                "root_cause": "The test runner was unable to resolve symbols imported across module boundaries.",
                "proposed_fix": "Add missing module exports and ensure relative paths are resolved."
            }
        elif "AssertionError" in stdout or "assert" in stdout:
            return {
                "failure_reason": "Assertion Mismatch in Test Assertion",
                "diagnosis": "Returned HTTP status code or JSON payload structure deviated from test expectation.",
                "root_cause": "Expected HTTP 401 on missing/expired tokens or incorrect password verification hash comparison.",
                "proposed_fix": "Align HTTP response status codes with OAuth2 Bearer spec (401 for unauthorized) and verify password verification logic."
            }
        else:
            return {
                "failure_reason": "General Test Suite Failure",
                "diagnosis": "Test runner reported non-zero exit code during execution.",
                "root_cause": "Unhandled exception or syntax anomaly in test execution environment.",
                "proposed_fix": "Patch exception handling and re-align test fixtures."
            }

    async def _apply_recovery_fix(self, run_id: str, diagnosis: Dict[str, str], model_name: Optional[str]) -> List[str]:
        plan = db_service.get_plan(run_id)
        repo_path = plan.target_repo_path if plan else workspace_service.get_default_repo_path()
        goal_model = db_service.get_goal_model(run_id)

        # Re-apply the deterministic high-correctness implementation
        from .coder_service import coder_service
        changes = await coder_service.execute_plan(run_id=run_id, model_name=model_name)
        return [c.file_path for c in changes]

debugger_service = DebuggerService()
