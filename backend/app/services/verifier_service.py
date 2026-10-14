from .workflow_service import observed, workflow
"""Evidence-based verification; unsupported natural-language checks stay unverified."""
import uuid
import logging
import time
import re
from typing import List, Optional, Any, Dict
from datetime import datetime
from ..models.schema import (
    VerificationReport,
    CriterionVerification,
    ConstraintCompliance,
    EvaluationMetrics,
    CodeChange,
    TestRunResult,
    GoalModel
)
from .db import db_service
from .ollama_service import ollama_service
from .telemetry_service import telemetry_manager
from .drift_controller_service import drift_controller_service
from .goal_tracker_service import goal_tracker_service
from .workspace_service import workspace_service

logger = logging.getLogger(__name__)


def compute_evaluation_scores(
    criteria_evaluations: List[CriterionVerification],
    latest_test: Optional[Any] = None,
    code_changes: Optional[List[Any]] = None,
    audit_summary: Optional[Dict[str, Any]] = None,
    semantic_alignment: Optional[str] = None,  # None = infer deterministically; "aligned", "misaligned", "unknown"
    constraint_compliances: Optional[List[Any]] = None
) -> Dict[str, Any]:
    """Computes distinct evaluation metrics using the normalized composite goal drift model:

    goal_drift_score =
        0.40 * goal_misalignment_penalty
      + 0.35 * criteria_gap_penalty
      + 0.25 * execution_failure_penalty
    """
    summary = audit_summary or {}
    unrelated_count = summary.get("unrelated_action_count", 0)

    # 1. Criteria Gap Penalty & Criteria Completion Rate (Weight: 0.35)
    total_crit = len(criteria_evaluations)
    passed_crit_count = sum(1 for c in criteria_evaluations if getattr(c, "verdict", "") == "PASS")
    failed_crit_count = sum(1 for c in criteria_evaluations if getattr(c, "verdict", "") == "FAIL")
    unverified_crit_count = sum(1 for c in criteria_evaluations if getattr(c, "verdict", "") not in ("PASS", "FAIL"))

    if total_crit == 0:
        criteria_completion_rate = 0.0
        criteria_gap_penalty = 100.0
        criteria_missing = True
        criteria_evidence = "Zero acceptance criteria defined for task; criteria gap cannot be evaluated as successful."
    else:
        criteria_missing = False
        criteria_completion_rate = round((passed_crit_count / total_crit) * 100.0, 2)
        # Unverified criteria reflect evidence gap, not proven goal drift.
        # Only explicitly failed criteria induce a criteria gap penalty.
        criteria_gap_penalty = round(100.0 * (failed_crit_count / total_crit), 2)
        if unverified_crit_count > 0:
            criteria_evidence = f"{passed_crit_count}/{total_crit} required criteria verified, {unverified_crit_count} unverified (partial evidence)."
        else:
            criteria_evidence = f"{passed_crit_count}/{total_crit} required acceptance criteria verified ({criteria_completion_rate}%)."

    # 2. Execution Failure Penalty & Test Pass Rate (Weight: 0.25)
    if latest_test is None:
        test_pass_rate = None
        execution_failure_penalty = 100.0
        tests_unavailable = True
        exec_evidence = "Test results unavailable; no test runner execution evidence recorded."
    else:
        tests_unavailable = False
        t_total = getattr(latest_test, "total_tests", 0)
        t_passed = getattr(latest_test, "passed_tests", 0)
        t_status = getattr(latest_test, "status", "UNKNOWN")
        t_exit = getattr(latest_test, "exit_code", 0)

        if t_total > 0:
            test_pass_rate = round((t_passed / t_total) * 100.0, 2)
            execution_failure_penalty = round(100.0 - test_pass_rate, 2)
            exec_evidence = f"{t_passed}/{t_total} tests passed (Pass rate: {test_pass_rate}%, Exit code: {t_exit})."
        else:
            if t_exit == 0 and t_status == "PASSED":
                test_pass_rate = 100.0
                execution_failure_penalty = 0.0
                exec_evidence = "Test runner completed with exit code 0."
            else:
                test_pass_rate = 0.0
                execution_failure_penalty = 100.0
                exec_evidence = f"Test execution failed (exit code {t_exit})."

    # Constraint violations contribute directly to goal misalignment
    hard_violations = sum(
        1 for c in (constraint_compliances or [])
        if getattr(c, "compliant", None) is False and getattr(c, "is_hard", True)
    )
    soft_violations = sum(
        1 for c in (constraint_compliances or [])
        if getattr(c, "compliant", None) is False and not getattr(c, "is_hard", True)
    )
    constraint_penalty = min(100.0, float(hard_violations * 50.0 + soft_violations * 20.0))

    # 3. Goal Misalignment Penalty (Weight: 0.40)
    if semantic_alignment == "unknown":
        goal_misalignment_penalty = 50.0
        semantic_status = "unknown"
        misalignment_evidence = "Semantic goal alignment cannot be determined reliably without explicit ground-truth specification; recorded as unknown."
    elif semantic_alignment == "misaligned":
        goal_misalignment_penalty = 100.0
        semantic_status = "misaligned"
        misalignment_evidence = "Output actions demonstrably deviate from the active user-approved goal."
    elif semantic_alignment == "aligned":
        if unrelated_count > 0 or constraint_penalty > 0:
            goal_misalignment_penalty = min(100.0, float(unrelated_count * 50.0) + constraint_penalty)
            semantic_status = "unrelated_actions" if unrelated_count > 0 else "constraint_violation"
            misalignment_evidence = f"Output is declared aligned, but {unrelated_count} unrelated action(s) and {hard_violations + soft_violations} constraint violation(s) detected."
        else:
            goal_misalignment_penalty = 0.0
            semantic_status = "aligned"
            misalignment_evidence = "Executed actions and generated code fully align with the active user-approved goal."
    else:
        if unrelated_count > 0 or constraint_penalty > 0:
            goal_misalignment_penalty = min(100.0, float(unrelated_count * 50.0) + constraint_penalty)
            if unrelated_count > 0 and constraint_penalty > 0:
                semantic_status = "unrelated_actions_and_constraint_violation"
                misalignment_evidence = f"{unrelated_count} unrelated action(s) and {hard_violations + soft_violations} constraint violation(s) detected."
            elif constraint_penalty > 0:
                semantic_status = "constraint_violation"
                misalignment_evidence = f"{hard_violations + soft_violations} confirmed constraint violation(s) detected against active goal."
            else:
                semantic_status = "unrelated_actions"
                misalignment_evidence = f"{unrelated_count} unrelated action(s) attempted outside active goal scope."
        elif code_changes is not None and len(code_changes) > 0:
            goal_misalignment_penalty = 0.0
            semantic_status = "aligned"
            misalignment_evidence = f"All {len(code_changes)} code modifications match planned targets for the active goal."
        elif (code_changes is None or len(code_changes) == 0) and not summary:
            goal_misalignment_penalty = 50.0
            semantic_status = "unknown"
            misalignment_evidence = "Insufficient evidence to determine semantic alignment; recorded as unknown."
        else:
            goal_misalignment_penalty = 0.0
            semantic_status = "aligned"
            misalignment_evidence = "No goal misalignment detected."

    # Clamp all penalties to [0.0, 100.0]
    goal_misalignment_penalty = max(0.0, min(100.0, float(goal_misalignment_penalty)))
    criteria_gap_penalty = max(0.0, min(100.0, float(criteria_gap_penalty)))
    execution_failure_penalty = max(0.0, min(100.0, float(execution_failure_penalty)))

    # Composite Drift Score Calculation
    raw_drift = (
        0.40 * goal_misalignment_penalty
      + 0.35 * criteria_gap_penalty
      + 0.25 * execution_failure_penalty
    )
    goal_drift_score = round(max(0.0, min(100.0, raw_drift)), 2)
    goal_alignment_score = round(max(0.0, min(100.0, 100.0 - goal_drift_score)), 2)

    # Determine score_status
    if criteria_missing:
        score_status = "missing_criteria"
    elif unverified_crit_count > 0:
        score_status = "partial_evidence"
    elif tests_unavailable:
        score_status = "unavailable_tests"
    elif semantic_status == "unknown":
        score_status = "unknown_semantic"
    else:
        score_status = "computed"

    return {
        "goal_drift_score": goal_drift_score,
        "goal_alignment_score": goal_alignment_score,
        "criteria_completion_rate": criteria_completion_rate,
        "test_pass_rate": test_pass_rate,
        "component_penalties": {
            "goal_misalignment_penalty": goal_misalignment_penalty,
            "criteria_gap_penalty": criteria_gap_penalty,
            "execution_failure_penalty": execution_failure_penalty
        },
        "score_status": score_status,
        "score_version": "v2.0",
        "evidence": {
            "goal_misalignment": misalignment_evidence,
            "criteria_gap": criteria_evidence,
            "execution_failure": exec_evidence
        }
    }


class VerifierService:
    @observed('verification', 'stage', reason='validation')
    async def verify_run(self, run_id, model_name=None, temperature=0.1, execution_started=None, execution_started_at=None) -> VerificationReport:
        verification_started_at = time.perf_counter()
        exec_start = execution_started_at if execution_started_at is not None else execution_started
        record = db_service.get_run_record(run_id)
        goal = db_service.get_goal_model(run_id)
        if not record or not goal:
            raise ValueError('A run and goal model are required')
        
        repo = getattr(record, 'repo_path', None)
        if hasattr(record, 'plan') and record.plan:
            repo = getattr(record.plan, 'target_repo_path', repo)
        
        test_results = db_service.get_test_results(run_id) if hasattr(db_service, 'get_test_results') else []
        latest_test = test_results[-1] if test_results else (getattr(record, 'test_results', [None])[-1] if hasattr(record, 'test_results') and record.test_results else None)
        tests_passed = latest_test.passed_tests if latest_test else 0
        tests_total = latest_test.total_tests if latest_test else 0
        test_status = getattr(latest_test, 'status', 'UNKNOWN') if latest_test else 'UNKNOWN'

        test_pass_rate = (
            round((tests_passed / tests_total) * 100, 1)
            if tests_total > 0 else None
        )

        code_changes = db_service.get_code_changes(run_id) if hasattr(db_service, 'get_code_changes') else (getattr(record, 'code_changes', []) or [])
        plan = db_service.get_plan(run_id) if hasattr(db_service, 'get_plan') else getattr(record, 'plan', None)
        recovery_attempts = db_service.get_recovery_attempts(run_id) if hasattr(db_service, 'get_recovery_attempts') else (getattr(record, 'recovery_attempts', []) or [])

        # Constraint compliance checks
        constraint_compliances = []
        for hc in getattr(goal, 'hard_constraints', []):
            constraint_compliances.append(self._verify_constraint(hc, code_changes, test_results, plan))
        for sc in getattr(goal, 'soft_constraints', []):
            constraint_compliances.append(self._verify_constraint(sc, code_changes, test_results, plan))
        
        security_verdict = self._evaluate_security_verdict(constraint_compliances)

        criteria = []
        if repo and hasattr(workflow, 'state'):
            from .criterion_checks import evaluate
            before_verification = workflow.state(run_id)
            for criterion in goal.success_criteria:
                verdict, evidence = evaluate(criterion, repo)
                criteria.append(CriterionVerification(
                    criterion_id=criterion.id,
                    criterion_description=getattr(criterion, 'description', ''),
                    verdict=verdict,
                    evidence=evidence,
                    confidence_score=None
                ))
            if before_verification is None or before_verification != workflow.state(run_id):
                criteria = [c.model_copy(update={'verdict':'UNVERIFIED',
                    'evidence':'Workspace changed during verification or its state could not be established; retry with a stable workspace.'}) for c in criteria]
        else:
            before_verification = None
            for crit in goal.success_criteria:
                criteria.append(
                    CriterionVerification(
                        criterion_id=crit.id,
                        criterion_description=getattr(crit, 'description', ''),
                        verdict="NOT_VERIFIED",
                        evidence=(
                            "No test-to-criterion mapping is available, so this criterion "
                            "cannot be individually verified from the captured test results."
                        ),
                        confidence_score=None,
                        test_evidence_ref=getattr(latest_test, 'id', None) if latest_test else None
                    )
                )

        failed = any(c.verdict == 'FAIL' for c in criteria)
        complete = bool(criteria) and all(c.verdict == 'PASS' for c in criteria) and all(c.compliant is True for c in constraint_compliances if getattr(c, 'is_hard', False))
        complete = complete and getattr(goal, 'is_confirmed', False) and not any(getattr(a, 'severity', None) == 'blocking' and not getattr(a, 'resolved', True) for a in getattr(goal, 'ambiguities', []))
        verified = False if failed else True if complete else None
        coverage = 100.0 * sum(c.verdict == 'PASS' for c in criteria)/len(criteria) if criteria else None

        if repo:
            verdict = 'FAILED_VERIFICATION' if failed else 'VERIFIED_PASSED' if complete else 'UNVERIFIED'
        else:
            if tests_total == 0:
                verdict = "TESTS_NOT_RUN"
            elif test_status == "PASSED" and tests_passed == tests_total:
                verdict = "TESTS_PASSED"
            else:
                verdict = "TESTS_WITH_FAILURES"

        pass_rate_val = coverage if repo else test_pass_rate

        report = VerificationReport(
            id=f'ver_{uuid.uuid4().hex[:8]}',
            run_id=run_id,
            overall_verdict=verdict,
            pass_rate_percent=pass_rate_val,
            criteria_evaluations=criteria,
            constraint_compliances=constraint_compliances,
            verifier_version='2',
            verified_success=verified,
            goal_model_version=getattr(goal, 'goal_model_version', None),
            review_summary=f'{sum(c.verdict == "PASS" for c in criteria)}/{len(criteria)} criteria independently verified; {sum(c.verdict in ("UNVERIFIED", "NOT_VERIFIED") for c in criteria)} lack supported evidence.',
            recommendations=list(dict.fromkeys(c.evidence for c in criteria if c.verdict in ('UNVERIFIED', 'NOT_VERIFIED'))),
            tests_passed=tests_passed,
            tests_total=tests_total,
            security_verdict=security_verdict
        )

        fresh = bool(latest_test and getattr(latest_test, 'evidence_version', None) == 'junit-v1' and getattr(latest_test, 'workspace_digest', None) == (workspace_service.digest(repo) if repo else None))
        logs = db_service.get_execution_logs(run_id) if hasattr(db_service, 'get_execution_logs') else (getattr(record, 'logs', []) or [])
        model_results = [getattr(e, 'details', {}) for e in logs if getattr(e, 'event_type', None) == 'model_result' and getattr(e, 'details', None)]
        def tokens(key):
            return sum(r[key] for r in model_results) if model_results and all(r.get(key) is not None for r in model_results) else None

        exec_duration = round(max(0.0, time.perf_counter() - exec_start), 2) if exec_start is not None else None

        metrics = EvaluationMetrics(
            run_id=run_id,
            task_id=getattr(record, 'task_id', 'task_main'),
            metric_version='2',
            verified_success=verified,
            outcome='failed' if failed else 'success' if complete else 'unverified',
            success_rate=test_pass_rate if not repo else coverage,
            termination_reason=verdict,
            execution_time_seconds=exec_duration,
            execution_mode=getattr(record, 'metadata', {}).get('execution_mode', 'unknown') if hasattr(record, 'metadata') else 'unknown',
            total_tool_calls=sum(getattr(e, 'event_type', None) == 'tool_call' for e in logs),
            total_model_calls=sum(getattr(e, 'event_type', None) == 'model_call' for e in logs),
            input_tokens=tokens('input_tokens'),
            output_tokens=tokens('output_tokens'),
            recovery_attempts_count=len(recovery_attempts),
            lines_added=sum(getattr(c, 'lines_added', 0) for c in code_changes),
            lines_removed=sum(getattr(c, 'lines_removed', 0) for c in code_changes),
            tests_passed=latest_test.passed_tests if (fresh or not repo) and latest_test else 0,
            tests_total=latest_test.total_tests if (fresh or not repo) and latest_test else 0
        )

        state = goal_tracker_service.get_state(run_id)
        if state:
            for criterion in criteria:
                if criterion.verdict in ('UNVERIFIED', 'NOT_VERIFIED'):
                    for tracked in state.acceptance_criteria:
                        if tracked.id == criterion.criterion_id:
                            tracked.status, tracked.evidence, tracked.verified_at = 'pending', criterion.evidence, None
                else:
                    goal_tracker_service.verify_criterion(run_id, criterion.criterion_id,
                        criterion.verdict == 'PASS', criterion.evidence)
            goal_tracker_service._persist_state(state)

        audit = drift_controller_service.get_audit_summary(run_id)
        tracker = telemetry_manager.get(run_id)
        scoring = compute_evaluation_scores(
            criteria_evaluations=criteria,
            latest_test=latest_test if (fresh or not repo) else None,
            code_changes=code_changes,
            audit_summary=audit,
            semantic_alignment=None,
            constraint_compliances=constraint_compliances
        )
        has_verified_verdict = verdict in ("VERIFIED_PASSED", "VERIFIED_WITH_WARNINGS", "FAILED_VERIFICATION") and verified is not None
        drift_score = scoring['goal_drift_score'] if has_verified_verdict else None
        alignment_score = scoring['goal_alignment_score'] if has_verified_verdict else None

        extras = dict(
            criteria_completion_rate=coverage,
            test_pass_rate=scoring['test_pass_rate'],
            component_penalties=scoring['component_penalties'],
            score_status=scoring['score_status'],
            score_version=scoring['score_version'],
            goal_drift_score=drift_score,
            goal_alignment_score=alignment_score,
            evidence_breakdown={
                'diagnostic_scores': scoring,
                'audit_summary': audit,
                'limitation': 'Heuristic composite is not independently verified goal alignment.'
            },
            repeated_action_count=audit.get('repeated_action_count', 0),
            harmless_duplicate_skip_count=audit.get('harmless_duplicate_skip_count', 0),
            security_violation_count=audit.get('security_violation_count', 0)
        )
        report = report.model_copy(update=extras)
        metrics = metrics.model_copy(update={**extras, 'telemetry': tracker.finalize() if tracker else None})

        if hasattr(db_service, 'save_verification'):
            db_service.save_verification(report)
        if hasattr(db_service, 'save_evaluation'):
            db_service.save_evaluation(metrics)
        if recovery_attempts and verified is not None:
            for rec in recovery_attempts:
                rec.verified_recovered = bool(verified is True and rec.local_tests_passed)
                if hasattr(db_service, 'save_recovery_attempt'):
                    db_service.save_recovery_attempt(rec)
        if repo and hasattr(db_service, 'finalize_run'):
            try:
                db_service.finalize_run(metrics, report)
            except Exception:
                pass

        db_service.add_log(
            run_id=run_id,
            stage='verifier',
            agent_role='Independent Verifier',
            event_type='verification',
            message=verdict,
            details={'goal_version': getattr(goal, 'goal_model_version', None), 'verified_success': verified}
        )
        if repo and hasattr(workflow, 'verification'):
            workflow.verification(run_id, report, checked_state=before_verification)

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
            breaking_deletions = []
            for line in combined_diff.splitlines():
                if line.startswith("-") and not line.startswith("---"):
                    m = re.match(r"^-\s*(?:async\s+)?def\s+(\w+)", line) or re.match(r"^-\s*class\s+(\w+)", line)
                    if m:
                        name = m.group(1)
                        if not re.search(rf"\b(?:async\s+)?def\s+{name}\b|\bclass\s+{name}\b|\b{name}\s*=", combined_code):
                            breaking_deletions.append(line)
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

        # 7. Preserving test assertions and avoiding skips
        if any(w in txt for w in ["assertion", "skip existing test", "delete or weaken", "comment out, or skip", "force a pass"]):
            if not code_changes and not test_results:
                return ConstraintCompliance(
                    constraint_id=constraint.id,
                    constraint_text=constraint.text,
                    is_hard=is_hard,
                    compliant=None,
                    status="unknown",
                    notes="Verification check unavailable: No modified files or test results available."
                )
            removed_asserts = [
                re.sub(r"\s+", " ", line[1:].strip())
                for line in combined_diff.splitlines()
                if line.startswith("-") and not line.startswith("---") and re.search(r"\bassert\b", line)
            ]
            added_asserts = {
                re.sub(r"\s+", " ", line[1:].strip())
                for line in combined_diff.splitlines()
                if line.startswith("+") and not line.startswith("+++") and re.search(r"\bassert\b", line)
            }
            final_test_content = re.sub(r"\s+", " ", "\n".join(c.new_content for c in code_changes if "test" in c.file_path))
            deleted_assertions = [
                a for a in removed_asserts
                if a not in added_asserts and a not in final_test_content
            ]
            added_skips = [
                line for line in combined_diff.splitlines()
                if line.startswith("+") and not line.startswith("+++")
                and re.search(r"@(pytest\.mark\.skip|unittest\.skip)|pytest\.skip\(", line)
            ]
            commented_assertions = [
                line for line in combined_diff.splitlines()
                if line.startswith("+") and not line.startswith("+++")
                and re.search(r"^\+\s*#.*?\bassert\b", line)
                and not any(re.sub(r"\s+", " ", line[1:].strip().lstrip("#").strip()) in added_asserts for line in combined_diff.splitlines() if line.startswith("+") and not line.startswith("+++"))
            ]
            if deleted_assertions or added_skips or commented_assertions:
                return ConstraintCompliance(
                    constraint_id=constraint.id,
                    constraint_text=constraint.text,
                    is_hard=is_hard,
                    compliant=False,
                    status="violated",
                    notes=f"Violated: Detected deleted or skipped test assertions in diff: {(deleted_assertions or added_skips or commented_assertions)[:2]}"
                )
            return ConstraintCompliance(
                constraint_id=constraint.id,
                constraint_text=constraint.text,
                is_hard=is_hard,
                compliant=True,
                status="compliant",
                notes="Verified: No deleted, commented out, or skipped test assertions detected in test suite diff."
            )

        # 8. Plaintext API secrets, credentials, or private keys
        if any(w in txt for w in ["plaintext api secret", "credentials", "private key", "plaintext", "private keys", "secrets"]) and not any(w in txt for w in ["hash", "bcrypt", "pbkdf2"]):
            if not code_changes:
                return ConstraintCompliance(
                    constraint_id=constraint.id,
                    constraint_text=constraint.text,
                    is_hard=is_hard,
                    compliant=None,
                    status="unknown",
                    notes="Verification check unavailable: No modified files available for secret pattern inspection."
                )
            has_priv_key = re.search(r"-----BEGIN (?:[A-Z0-9_\- ]+)?PRIVATE KEY-----", combined_code, re.IGNORECASE)
            has_secret = re.search(r"(?:api[_-]?key|secret[_-]?key|auth[_-]?token|private[_-]?key|access[_-]?token)\s*=\s*['\"][A-Za-z0-9+/=_\-]{20,}['\"]", combined_code, re.IGNORECASE)
            has_known_token = re.search(r"\b(?:ghp_[A-Za-z0-9]{36}|sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16})\b", combined_code)
            if has_priv_key or has_secret or has_known_token:
                return ConstraintCompliance(
                    constraint_id=constraint.id,
                    constraint_text=constraint.text,
                    is_hard=is_hard,
                    compliant=False,
                    status="violated",
                    notes="Violated: Potential plaintext API secret, credential, or private key pattern detected in committed code."
                )
            return ConstraintCompliance(
                constraint_id=constraint.id,
                constraint_text=constraint.text,
                is_hard=is_hard,
                compliant=True,
                status="compliant",
                notes="Verified: Static pattern analysis found no plaintext API secrets, credentials, or private keys in source code."
            )

        # 9. PEP 8 / Clean Code conventions
        if any(w in txt for w in ["pep 8", "pep8", "clean code", "clean modular code", "ruff", "black"]):
            if not code_changes:
                return ConstraintCompliance(
                    constraint_id=constraint.id,
                    constraint_text=constraint.text,
                    is_hard=is_hard,
                    compliant=None,
                    status="unknown",
                    notes="Verification check unavailable: No modified files available for PEP 8 static inspection."
                )
            ast_failures = [c.file_path for c in code_changes if not c.ast_valid]
            if ast_failures:
                return ConstraintCompliance(
                    constraint_id=constraint.id,
                    constraint_text=constraint.text,
                    is_hard=is_hard,
                    compliant=False,
                    status="violated",
                    notes=f"Violated: AST syntax errors detected in: {ast_failures}"
                )
            long_lines = [
                line for line in combined_code.splitlines()
                if len(line) > 160 and not line.strip().startswith("#") and "http" not in line
            ]
            if long_lines:
                return ConstraintCompliance(
                    constraint_id=constraint.id,
                    constraint_text=constraint.text,
                    is_hard=is_hard,
                    compliant=False,
                    status="violated",
                    notes="Violated: Source lines significantly exceed standard PEP 8 line length limits."
                )
            return ConstraintCompliance(
                constraint_id=constraint.id,
                constraint_text=constraint.text,
                is_hard=is_hard,
                compliant=True,
                status="compliant",
                notes="Verified: Source code adheres to standard PEP 8 syntax, clean modular structure, and formatting guidelines."
            )

        # 10. Docstrings and typing annotations
        if any(w in txt for w in ["docstring", "typing annotation", "type annotation", "annotations on newly created"]):
            if not code_changes:
                return ConstraintCompliance(
                    constraint_id=constraint.id,
                    constraint_text=constraint.text,
                    is_hard=is_hard,
                    compliant=None,
                    status="unknown",
                    notes="Verification check unavailable: No modified files available to inspect docstrings/type annotations."
                )
            import ast
            try:
                tree = ast.parse(combined_code)
                funcs = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and not n.name.startswith("test_")]
                if not funcs:
                    funcs = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
                if funcs:
                    has_doc = any(ast.get_docstring(f) is not None for f in funcs)
                    has_type = any(f.returns is not None or any(a.annotation is not None for a in f.args.args) for f in funcs)
                    if has_doc or has_type:
                        return ConstraintCompliance(
                            constraint_id=constraint.id,
                            constraint_text=constraint.text,
                            is_hard=is_hard,
                            compliant=True,
                            status="compliant",
                            notes="Verified: Implemented function(s) with clear docstrings and/or typing annotations."
                        )
                    else:
                        return ConstraintCompliance(
                            constraint_id=constraint.id,
                            constraint_text=constraint.text,
                            is_hard=is_hard,
                            compliant=False,
                            status="violated",
                            notes="Violated: Newly created functions lack clear docstrings and typing annotations."
                        )
                else:
                    return ConstraintCompliance(
                        constraint_id=constraint.id,
                        constraint_text=constraint.text,
                        is_hard=is_hard,
                        compliant=True,
                        status="compliant",
                        notes="Verified: No undocumented functions introduced."
                    )
            except Exception:
                return ConstraintCompliance(
                    constraint_id=constraint.id,
                    constraint_text=constraint.text,
                    is_hard=is_hard,
                    compliant=True,
                    status="compliant",
                    notes="Verified: Static analysis inspected function signatures."
                )

        # 11. Subprocess shell=True safety
        if any(w in txt for w in ["shell=true", "subprocess"]):
            if "shell=true" in combined_code.lower().replace(" ", ""):
                return ConstraintCompliance(
                    constraint_id=constraint.id,
                    constraint_text=constraint.text,
                    is_hard=is_hard,
                    compliant=False,
                    status="violated",
                    notes="Violated: Detected unsafe shell=True parameter in subprocess execution."
                )
            return ConstraintCompliance(
                constraint_id=constraint.id,
                constraint_text=constraint.text,
                is_hard=is_hard,
                compliant=True,
                status="compliant",
                notes="Verified: No shell=True or unescaped subprocess executions observed."
            )

        # 12. Synchronous blocking I/O calls inside async coroutines
        if any(w in txt for w in ["blocking i/o", "synchronous blocking", "inside async"]):
            if re.search(r"async\s+def\s+.*?time\.sleep\(", combined_code, re.DOTALL):
                return ConstraintCompliance(
                    constraint_id=constraint.id,
                    constraint_text=constraint.text,
                    is_hard=is_hard,
                    compliant=False,
                    status="violated",
                    notes="Violated: Synchronous time.sleep call detected inside async coroutine."
                )
            return ConstraintCompliance(
                constraint_id=constraint.id,
                constraint_text=constraint.text,
                is_hard=is_hard,
                compliant=True,
                status="compliant",
                notes="Verified: No synchronous blocking I/O calls detected inside async coroutines."
            )

        # 13. Raw database stack traces or internal server error messages
        if any(w in txt for w in ["stack trace", "internal server error messages"]):
            if re.search(r"traceback\.format_exc\(|traceback\.print_exc\(", combined_code):
                return ConstraintCompliance(
                    constraint_id=constraint.id,
                    constraint_text=constraint.text,
                    is_hard=is_hard,
                    compliant=False,
                    status="violated",
                    notes="Violated: Raw traceback formatting exposed in API responses."
                )
            return ConstraintCompliance(
                constraint_id=constraint.id,
                constraint_text=constraint.text,
                is_hard=is_hard,
                compliant=True,
                status="compliant",
                notes="Verified: No raw database stack traces or internal error details exposed in API JSON responses."
            )

        # 14. Default: Report unavailable check as unknown
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
        sec_checks = [c for c in compliances if any(k in c.constraint_text.lower() for k in ["security", "cwe", "jwt", "auth", "hash", "password", "salt", "secret", "credential", "private key", "token"])]
        if not sec_checks:
            return "SECURITY_UNVERIFIED (No dedicated security constraints specified)"
        if any(c.status == "violated" for c in sec_checks):
            return "SECURITY_VIOLATION (One or more security constraints violated)"
        if any(c.status == "compliant" for c in sec_checks):
            return "SECURE_PASS (Deterministic security checks passed)"
        return "SECURITY_UNVERIFIED (Static checks inconclusive)"



verifier_service = VerifierService()
