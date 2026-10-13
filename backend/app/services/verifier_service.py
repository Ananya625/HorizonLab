from .workflow_service import observed, workflow
"""Evidence-based verification; unsupported natural-language checks stay unverified."""
from typing import List, Optional, Any, Dict
import ast
import uuid
import time
from ..models.schema import VerificationReport, CriterionVerification, ConstraintCompliance, EvaluationMetrics
from .db import db_service
from .ollama_service import ollama_service
from .telemetry_service import telemetry_manager
from .drift_controller_service import drift_controller_service
from .goal_tracker_service import goal_tracker_service
from .workspace_service import workspace_service


def compute_evaluation_scores(
    criteria_evaluations: List[CriterionVerification],
    latest_test: Optional[Any] = None,
    code_changes: Optional[List[Any]] = None,
    audit_summary: Optional[Dict[str, Any]] = None,
    semantic_alignment: Optional[str] = None  # None = infer deterministically; "aligned", "misaligned", "unknown"
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
    
    if total_crit == 0:
        # Missing criteria handled explicitly - does not assume perfect score
        criteria_completion_rate = 0.0
        criteria_gap_penalty = 100.0
        criteria_missing = True
        criteria_evidence = "Zero acceptance criteria defined for task; criteria gap cannot be evaluated as successful."
    else:
        criteria_missing = False
        criteria_completion_rate = round((passed_crit_count / total_crit) * 100.0, 2)
        criteria_gap_penalty = round(100.0 * (1.0 - (passed_crit_count / total_crit)), 2)
        criteria_evidence = f"{passed_crit_count}/{total_crit} required acceptance criteria verified ({criteria_completion_rate}%)."

    # 2. Execution Failure Penalty & Test Pass Rate (Weight: 0.25)
    if latest_test is None:
        # Unavailable test results handled explicitly - does not assume test success
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

    # 3. Goal Misalignment Penalty (Weight: 0.40)
    # Measured deviation of executed actions and output from active goal.
    # Security violations and harmless duplicate skips do NOT increase misalignment.
    if semantic_alignment == "unknown":
        goal_misalignment_penalty = 50.0
        semantic_status = "unknown"
        misalignment_evidence = "Semantic goal alignment cannot be determined reliably without explicit ground-truth specification; recorded as unknown."
    elif semantic_alignment == "misaligned":
        goal_misalignment_penalty = 100.0
        semantic_status = "misaligned"
        misalignment_evidence = "Output actions demonstrably deviate from the active user-approved goal."
    elif semantic_alignment == "aligned":
        if unrelated_count > 0:
            goal_misalignment_penalty = min(100.0, float(unrelated_count * 50.0))
            semantic_status = "unrelated_actions"
            misalignment_evidence = f"Output is aligned, but {unrelated_count} unrelated action(s) attempted."
        else:
            goal_misalignment_penalty = 0.0
            semantic_status = "aligned"
            misalignment_evidence = "Executed actions and generated code fully align with the active user-approved goal."
    else:
        # Deterministic inference based on actions and code changes
        if unrelated_count > 0:
            goal_misalignment_penalty = min(100.0, float(unrelated_count * 50.0))
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
    async def verify_run(self, run_id, model_name=None, temperature=0.1, execution_started=None):
        record = db_service.get_run_record(run_id)
        goal = db_service.get_goal_model(run_id)
        if not record or not goal:
            raise ValueError('A run and goal model are required')
        repo = record.plan.target_repo_path if record.plan else record.repo_path
        criteria = []
        from .criterion_checks import evaluate
        before_verification = workflow.state(run_id)
        for criterion in goal.success_criteria:
            verdict, evidence = evaluate(criterion, repo)
            criteria.append(CriterionVerification(criterion_id=criterion.id,
                criterion_description=criterion.description, verdict=verdict, evidence=evidence))
        if before_verification is None or before_verification != workflow.state(run_id):
            criteria = [c.model_copy(update={'verdict':'UNVERIFIED',
                'evidence':'Workspace changed during verification or its state could not be established; retry with a stable workspace.'}) for c in criteria]
        constraints = [ConstraintCompliance(constraint_id=c.id, constraint_text=c.text,
            is_hard=hard, compliant=None, notes='No independent constraint checker registered')
            for hard, values in [(True, goal.hard_constraints), (False, goal.soft_constraints)] for c in values]
        failed = any(c.verdict == 'FAIL' for c in criteria)
        complete = bool(criteria) and all(c.verdict == 'PASS' for c in criteria) and all(c.compliant is True for c in constraints if c.is_hard)
        complete = complete and goal.is_confirmed and not any(a.severity == 'blocking' and not a.resolved for a in goal.ambiguities)
        verified = False if failed else True if complete else None
        coverage = 100 * sum(c.verdict == 'PASS' for c in criteria)/len(criteria) if criteria else None
        verdict = 'FAILED_VERIFICATION' if failed else 'VERIFIED_PASSED' if complete else 'UNVERIFIED'
        report = VerificationReport(id=f'ver_{uuid.uuid4().hex}', run_id=run_id,
            overall_verdict=verdict, pass_rate_percent=coverage, criteria_evaluations=criteria,
            constraint_compliances=constraints, verifier_version='2', verified_success=verified,
            goal_model_version=goal.goal_model_version,
            review_summary=f'{sum(c.verdict == "PASS" for c in criteria)}/{len(criteria)} criteria independently verified; {sum(c.verdict == "UNVERIFIED" for c in criteria)} lack supported evidence.',
            recommendations=list(dict.fromkeys(c.evidence for c in criteria if c.verdict=='UNVERIFIED')) + (['Hard constraints still require independent checks.'] if any(c.compliant is None and c.is_hard for c in constraints) else []))
        latest = record.test_results[-1] if record.test_results else None
        fresh = bool(latest and latest.evidence_version == 'junit-v1' and latest.workspace_digest == workspace_service.digest(repo))
        logs = db_service.get_execution_logs(run_id)
        model_results = [e.details for e in logs if e.event_type == 'model_result' and e.details]
        def tokens(key):
            return sum(r[key] for r in model_results) if model_results and all(r.get(key) is not None for r in model_results) else None
        metrics = EvaluationMetrics(run_id=run_id, task_id=record.task_id,
            metric_version='2', verified_success=verified, outcome='failed' if failed else 'success' if complete else 'unverified',
            success_rate=coverage, termination_reason=verdict,
            execution_time_seconds=time.perf_counter()-execution_started if execution_started is not None else None,
            execution_mode=record.metadata.get('execution_mode', 'unknown'),
            total_tool_calls=sum(e.event_type == 'tool_call' for e in logs),
            total_model_calls=sum(e.event_type == 'model_call' for e in logs),
            input_tokens=tokens('input_tokens'), output_tokens=tokens('output_tokens'),
            recovery_attempts_count=len(record.recovery_attempts),
            lines_added=sum(c.lines_added for c in record.code_changes),
            lines_removed=sum(c.lines_removed for c in record.code_changes),
            tests_passed=latest.passed_tests if fresh else 0, tests_total=latest.total_tests if fresh else 0)
        state = goal_tracker_service.get_state(run_id)
        if state:
            for criterion in criteria:
                if criterion.verdict == 'UNVERIFIED':
                    for tracked in state.acceptance_criteria:
                        if tracked.id == criterion.criterion_id:
                            tracked.status, tracked.evidence, tracked.verified_at = 'pending', criterion.evidence, None
                else:
                    goal_tracker_service.verify_criterion(run_id, criterion.criterion_id,
                        criterion.verdict == 'PASS', criterion.evidence)
            goal_tracker_service._persist_state(state)
        audit = drift_controller_service.get_audit_summary(run_id)
        tracker = telemetry_manager.get(run_id)
        # Composite heuristic scores are auxiliary diagnostics, not independent verdicts.
        scoring = compute_evaluation_scores(criteria, latest if fresh else None,
            record.code_changes, audit, semantic_alignment='unknown')
        extras = dict(criteria_completion_rate=coverage,
            test_pass_rate=scoring['test_pass_rate'], component_penalties=scoring['component_penalties'],
            score_status='partial_evidence', score_version=scoring['score_version'],
            evidence_breakdown={'diagnostic_scores':scoring,'audit_summary':audit,
                'limitation':'Heuristic composite is not independently verified goal alignment.'},
            repeated_action_count=audit.get('repeated_action_count',0),
            harmless_duplicate_skip_count=audit.get('harmless_duplicate_skip_count',0),
            security_violation_count=audit.get('security_violation_count',0))
        report = report.model_copy(update=extras)
        metrics = metrics.model_copy(update={**extras, 'telemetry':tracker.finalize() if tracker else None})
        db_service.finalize_run(metrics, report)
        db_service.add_log(run_id, 'verifier', 'Independent Verifier', 'verification', verdict,
                          {'goal_version': goal.goal_model_version, 'verified_success': verified})
        workflow.verification(run_id, report, checked_state=before_verification)
        return report


verifier_service = VerifierService()
