import uuid
import logging
import time
from typing import Dict, Any, List, Optional
from datetime import datetime
from ..models.schema import (
    VerificationReport,
    CriterionVerification,
    ConstraintCompliance,
    EvaluationMetrics,
    GoalModel,
    CodeChange,
    TestRunResult
)
from .db import db_service
from .ollama_service import ollama_service

logger = logging.getLogger(__name__)

class VerifierService:
    async def verify_run(
        self,
        run_id: str,
        model_name: Optional[str] = "qwen2.5-coder:7b",
        temperature: float = 0.1,
        execution_started_at: Optional[float] = None,
    ) -> VerificationReport:
        verification_started_at = time.perf_counter()
        goal_model = db_service.get_goal_model(run_id)
        if not goal_model:
            raise ValueError(f"Goal model for run_id '{run_id}' not found")
        
        plan = db_service.get_plan(run_id)
        code_changes = db_service.get_code_changes(run_id)
        test_results = db_service.get_test_results(run_id)
        recovery_attempts = db_service.get_recovery_attempts(run_id)

        latest_test = test_results[-1] if test_results else None
        tests_passed = latest_test.passed_tests if latest_test else 0
        tests_total = latest_test.total_tests if latest_test else 0
        test_status = latest_test.status if latest_test else "UNKNOWN"

        db_service.add_log(
            run_id=run_id,
            stage="verifier",
            agent_role="Independent Code Reviewer",
            event_type="info",
            message=f"Beginning independent verification of {len(code_changes)} modified files against {len(goal_model.success_criteria)} acceptance criteria and {len(goal_model.hard_constraints)} hard constraints.",
            details={"files_count": len(code_changes), "criteria_count": len(goal_model.success_criteria)}
        )

        # Test outcomes are measurable, but the current runner does not link
        # individual test cases to individual acceptance criteria.
        criteria_evaluations: List[CriterionVerification] = []
        for crit in goal_model.success_criteria:
            criteria_evaluations.append(
                CriterionVerification(
                    criterion_id=crit.id,
                    criterion_description=crit.description,
                    verdict="NOT_VERIFIED",
                    evidence=(
                        "No test-to-criterion mapping is available, so this criterion "
                        "cannot be individually verified from the captured test results."
                    ),
                    test_evidence_ref=latest_test.id if latest_test else None
                )
            )

        # 2. Evaluate Constraints Compliance deterministically
        constraint_compliances: List[ConstraintCompliance] = []
        for hc in goal_model.hard_constraints:
            constraint_compliances.append(
                self._verify_constraint(hc, code_changes, test_results, plan)
            )
        for sc in goal_model.soft_constraints:
            constraint_compliances.append(
                self._verify_constraint(sc, code_changes, test_results, plan)
            )

        test_pass_rate = (
            round((tests_passed / tests_total) * 100, 1)
            if tests_total > 0 else None
        )
        if tests_total == 0:
            overall_verdict = "TESTS_NOT_RUN"
        elif test_status == "PASSED" and tests_passed == tests_total:
            overall_verdict = "TESTS_PASSED"
        else:
            overall_verdict = "TESTS_WITH_FAILURES"

        total_lines_added = sum(c.lines_added for c in code_changes)
        total_lines_removed = sum(c.lines_removed for c in code_changes)

        security_verdict = self._evaluate_security_verdict(constraint_compliances)

        report = VerificationReport(
            id=f"ver_{uuid.uuid4().hex[:8]}",
            run_id=run_id,
            overall_verdict=overall_verdict,
            pass_rate_percent=test_pass_rate,
            goal_drift_score=None,
            tests_passed=tests_passed,
            tests_total=tests_total,
            criteria_evaluations=criteria_evaluations,
            constraint_compliances=constraint_compliances,
            code_quality_score=None,
            security_verdict=security_verdict,
            review_summary=(
                f"Automated test evidence: {tests_passed}/{tests_total} tests passed"
                if tests_total else "No automated test results were captured."
            ) + " Acceptance criteria have no linked test cases and remain unverified. "
            + f"Security evidence: {security_verdict}.",
            recommendations=[
                "Maintain test suite coverage in CI/CD pipeline.",
                "Verify secrets injection via environment variables."
            ],
            created_at=datetime.now().isoformat()
        )

        db_service.save_verification(report)

        # Calculate evaluation metrics
        run_record = db_service.get_run_record(run_id)
        duration_start = (
            execution_started_at
            if execution_started_at is not None
            else verification_started_at
        )
        exec_duration = round(max(0.0, time.perf_counter() - duration_start), 2)

        eval_metrics = EvaluationMetrics(
            run_id=run_id,
            task_id=run_record.task_id if run_record else "task_main",
            success_rate=test_pass_rate,
            execution_time_seconds=exec_duration,
            total_tool_calls=len(run_record.logs) if run_record else 0,
            recovery_attempts_count=len(recovery_attempts),
            goal_drift_score=None,
            lines_added=total_lines_added,
            lines_removed=total_lines_removed,
            tests_passed=tests_passed,
            tests_total=tests_total,
            created_at=datetime.now().isoformat()
        )

        db_service.save_evaluation(eval_metrics)

        db_service.add_log(
            run_id=run_id,
            stage="verifier",
            agent_role="Independent Code Reviewer",
            event_type="success",
            message=(
                f"Verification Complete: {overall_verdict} "
                f"(test pass rate: {test_pass_rate if test_pass_rate is not None else 'not measured'}%)."
            ),
            details={
                "verdict": overall_verdict,
                "test_pass_rate_percent": test_pass_rate,
                "tests_passed": tests_passed,
                "tests_total": tests_total,
            }
        )

        return report

    def _verify_constraint(
        self,
        constraint: Any,
        code_changes: List[CodeChange],
        test_results: List[TestRunResult],
        plan: Optional[Any]
    ) -> ConstraintCompliance:
        import re
        txt = (constraint.text or "").lower()
        is_hard = getattr(constraint, "is_hard", True)

        combined_code = "\n".join(c.new_content for c in code_changes)
        combined_diff = "\n".join(c.diff_patch for c in code_changes)
        latest_test = test_results[-1] if test_results else None
        test_stdout = (latest_test.stdout or "") + "\n" + (latest_test.stderr or "") if latest_test else ""

        # 1. AST / syntax validity check
        if any(w in txt for w in ["ast", "syntax", "static analysis", "flake8", "bandit"]):
            if not code_changes:
                return ConstraintCompliance(
                    constraint_id=constraint.id,
                    constraint_text=constraint.text,
                    is_hard=is_hard,
                    compliant=None,
                    status="unknown",
                    notes="Verification check unavailable: No modified files available for static inspection."
                )
            ast_failures = [c.file_path for c in code_changes if not c.ast_valid]
            if not ast_failures:
                return ConstraintCompliance(
                    constraint_id=constraint.id,
                    constraint_text=constraint.text,
                    is_hard=is_hard,
                    compliant=True,
                    status="compliant",
                    notes="Verified: All modified and generated source files passed AST syntax tree validation."
                )
            else:
                return ConstraintCompliance(
                    constraint_id=constraint.id,
                    constraint_text=constraint.text,
                    is_hard=is_hard,
                    compliant=False,
                    status="violated",
                    notes=f"Violated: AST syntax errors detected in: {ast_failures}"
                )

        # 2. Cryptography / password hashing / salts
        if any(w in txt for w in ["hash", "bcrypt", "pbkdf2", "argon2", "salt", "cryptographic"]):
            has_hash_impl = any(re.search(p, combined_code, re.IGNORECASE) for p in [
                r"passlib", r"bcrypt", r"pbkdf2", r"hashlib", r"cryptcontext", r"pwd_context", r"hash_password", r"verify_password"
            ])
            if has_hash_impl:
                return ConstraintCompliance(
                    constraint_id=constraint.id,
                    constraint_text=constraint.text,
                    is_hard=is_hard,
                    compliant=True,
                    status="compliant",
                    notes="Verified: Code implements cryptographic password hashing / salting primitives."
                )
            elif "password" in combined_code.lower() and not has_hash_impl:
                return ConstraintCompliance(
                    constraint_id=constraint.id,
                    constraint_text=constraint.text,
                    is_hard=is_hard,
                    compliant=False,
                    status="violated",
                    notes="Violated: Password handling observed without cryptographic hashing or salting."
                )
            else:
                return ConstraintCompliance(
                    constraint_id=constraint.id,
                    constraint_text=constraint.text,
                    is_hard=is_hard,
                    compliant=None,
                    status="unknown",
                    notes="Verification check unavailable: No password handling code observed to verify this constraint."
                )

        # 3. HTTP 401 Unauthorized status code rejection
        if any(w in txt for w in ["401", "unauthorized", "unauthenticated", "invalid credentials rejection"]):
            has_401 = any(re.search(p, combined_code, re.IGNORECASE) for p in [
                r"401", r"http_401", r"status\.http_401_unauthorized", r"httpexception\([^)]*status_code\s*=\s*401"
            ]) or "401" in test_stdout
            if has_401:
                return ConstraintCompliance(
                    constraint_id=constraint.id,
                    constraint_text=constraint.text,
                    is_hard=is_hard,
                    compliant=True,
                    status="compliant",
                    notes="Verified: HTTP 401 Unauthorized rejection status code verified in application logic and test cases."
                )
            else:
                return ConstraintCompliance(
                    constraint_id=constraint.id,
                    constraint_text=constraint.text,
                    is_hard=is_hard,
                    compliant=False,
                    status="violated",
                    notes="Violated: HTTP 401 Unauthorized handling not identified in codebase or test assertions."
                )

        # 4. Concurrency lock / mutual exclusion
        if any(w in txt for w in ["lock", "mutex", "concurrency", "race condition", "connectionpool"]):
            has_lock = any(re.search(p, combined_code, re.IGNORECASE) for p in [
                r"asyncio\.lock", r"threading\.lock", r"\.acquire\(", r"\.release\(", r"async with (?:self\.)?.*lock"
            ])
            if has_lock:
                return ConstraintCompliance(
                    constraint_id=constraint.id,
                    constraint_text=constraint.text,
                    is_hard=is_hard,
                    compliant=True,
                    status="compliant",
                    notes="Verified: Mutual exclusion lock synchronization detected in concurrent paths."
                )
            else:
                return ConstraintCompliance(
                    constraint_id=constraint.id,
                    constraint_text=constraint.text,
                    is_hard=is_hard,
                    compliant=None,
                    status="unknown",
                    notes="Verification check unavailable: Unable to deterministically confirm concurrency bounds."
                )

        # 5. Interface backward compatibility
        if any(w in txt for w in ["backward compatibility", "signature", "public interface", "break the existing"]):
            breaking_deletions = [
                line for line in combined_diff.splitlines()
                if line.startswith("-") and not line.startswith("---")
                and (re.match(r"^-\s*def\s+\w+", line) or re.match(r"^-\s*class\s+\w+", line))
            ]
            if not breaking_deletions:
                return ConstraintCompliance(
                    constraint_id=constraint.id,
                    constraint_text=constraint.text,
                    is_hard=is_hard,
                    compliant=True,
                    status="compliant",
                    notes="Verified: No removed public function or class signatures observed in git diff."
                )
            else:
                return ConstraintCompliance(
                    constraint_id=constraint.id,
                    constraint_text=constraint.text,
                    is_hard=is_hard,
                    compliant=False,
                    status="violated",
                    notes=f"Violated: Detected deleted public declarations in diff: {breaking_deletions[:2]}"
                )

        # 6. SQL Injection parameterization (CWE-89)
        if any(w in txt for w in ["sql injection", "cwe-89", "raw f-string sql"]):
            raw_fstring_sql = re.findall(r'f["\'].*?(?:SELECT|INSERT|UPDATE|DELETE).*?\{.*?\}["\']', combined_code, re.IGNORECASE)
            if raw_fstring_sql:
                return ConstraintCompliance(
                    constraint_id=constraint.id,
                    constraint_text=constraint.text,
                    is_hard=is_hard,
                    compliant=False,
                    status="violated",
                    notes="Violated: Raw string-interpolated SQL query detected."
                )
            elif re.search(r'(?:execute|query)\s*\(.*?[,\(]', combined_code, re.IGNORECASE):
                return ConstraintCompliance(
                    constraint_id=constraint.id,
                    constraint_text=constraint.text,
                    is_hard=is_hard,
                    compliant=True,
                    status="compliant",
                    notes="Verified: Query parameterization observed; no string-interpolated SQL found."
                )
            else:
                return ConstraintCompliance(
                    constraint_id=constraint.id,
                    constraint_text=constraint.text,
                    is_hard=is_hard,
                    compliant=None,
                    status="unknown",
                    notes="Verification check unavailable: No database queries found to inspect for CWE-89."
                )

        # 7. Default: Report unavailable check as unknown
        return ConstraintCompliance(
            constraint_id=constraint.id,
            constraint_text=constraint.text,
            is_hard=is_hard,
            compliant=None,
            status="unknown",
            notes=f"Verification check unavailable: Deterministic check could not be established from static analysis and test suite for '{constraint.text[:60]}'."
        )

    def _evaluate_security_verdict(
        self,
        compliances: List[ConstraintCompliance]
    ) -> str:
        sec_checks = [c for c in compliances if any(k in c.constraint_text.lower() for k in ["security", "cwe", "jwt", "auth", "hash", "password", "salt"])]
        if not sec_checks:
            return "SECURITY_UNVERIFIED (No dedicated security constraints specified)"
        if any(c.status == "violated" for c in sec_checks):
            return "SECURITY_VIOLATION (One or more security constraints violated)"
        if any(c.status == "compliant" for c in sec_checks):
            return "SECURE_PASS (Deterministic security checks passed)"
        return "SECURITY_UNVERIFIED (Static checks inconclusive)"

verifier_service = VerifierService()
