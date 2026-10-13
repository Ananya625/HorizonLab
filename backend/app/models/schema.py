from pydantic import BaseModel, Field, model_validator
from typing import List, Optional, Dict, Any
from datetime import datetime

# --- Goal & Requirement Models ---

class SubGoal(BaseModel):
    id: str = Field(description="Unique identifier e.g. SG-1")
    title: str
    description: str
    order: int = 1
    priority: str = "high"  # "high", "medium", "low"
    assigned_agent_role: str = "General Agent"
    dependencies: List[str] = []
    status: str = "pending"  # "pending", "in_progress", "completed", "failed"

class SuccessCriterion(BaseModel):
    id: str = Field(description="Unique identifier e.g. SC-1")
    sub_goal_id: Optional[str] = None
    description: str
    metric: str
    target_value: Optional[str] = ""
    verification_method: str = "automated_test"  # "automated_test", "diff_inspection", "schema_validation", "state_ledger_check", "ast_check"
    expected_output: Optional[str] = ""

class Constraint(BaseModel):
    id: str
    text: str
    category: str = "general"  # safety, budget, security, performance, temporal, general
    is_hard: bool = True  # True = Hard constraint, False = Soft constraint

class ExpectedOutput(BaseModel):
    format: str = "Unified Git Diff & Test Execution Report"
    schema_summary: str = "Modified files list, line diffs, passing test logs, AST validity status"
    delivery_target: str = "Repository Worktree & Execution Ledger"

class Ambiguity(BaseModel):
    id: str
    question: str
    context: str = ""
    severity: str = "blocking"  # "blocking" or "non_blocking"
    suggested_options: List[str] = []
    default_assumption: str = ""
    resolved: bool = False
    user_answer: Optional[str] = None
    resolved_at: Optional[str] = None

class AuditEntry(BaseModel):
    version: str
    timestamp: str
    change_summary: str
    modified_fields: List[str] = []
    author: str = "system"

class GoalModel(BaseModel):
    task_id: str
    run_id: str
    original_request: str
    normalized_request: str
    detected_language: str = "en"
    goal_model_version: str = "1.0"
    main_goal: str
    summary: str = ""
    hierarchical_layer: Optional[str] = "Task"
    sub_goals: List[SubGoal] = []
    success_criteria: List[SuccessCriterion] = []
    hard_constraints: List[Constraint] = []
    soft_constraints: List[Constraint] = []
    expected_output: ExpectedOutput = Field(default_factory=ExpectedOutput)
    ambiguities: List[Ambiguity] = []
    is_confirmed: bool = False
    confirmed_at: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    audit_history: List[AuditEntry] = []

# --- Codebase Analysis & Planner Models ---

class PlannedFile(BaseModel):
    sub_goal_id: Optional[str] = None
    path: str
    action: str = "modify"  # "create", "modify", "delete", "test"
    description: str
    estimated_loc: int = 50

class PlanStep(BaseModel):
    sub_goal_ids: List[str] = []
    step_number: int
    title: str
    description: str
    assigned_agent: str = "Coding Agent"
    target_files: List[str] = []
    dependencies: List[int] = []
    expected_outcome: str

class ImplementationPlan(BaseModel):
    goal_revision: Optional[str] = None
    run_id: str
    goal_model_version: Optional[str] = None
    architecture_overview: str
    target_repo_path: str
    tech_stack: Dict[str, str] = {}
    key_modules: List[str] = []
    planned_files: List[PlannedFile] = []
    steps: List[PlanStep] = []
    testing_strategy: str
    risk_assessment: str
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())

# --- Coding & Diff Models ---

class CodeChange(BaseModel):
    id: str
    run_id: str
    file_path: str
    action: str = "modified"  # "created", "modified", "deleted"
    original_content: Optional[str] = ""
    new_content: str
    diff_patch: str
    lines_added: int = 0
    lines_removed: int = 0
    ast_valid: bool = True
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())

# --- Testing & Debugging Models ---

class TestResultItem(BaseModel):
    name: str
    status: str  # "PASSED", "FAILED", "SKIPPED", "ERROR"
    duration_ms: float = 0.0
    error_message: Optional[str] = None
    stack_trace: Optional[str] = None

class TestRunResult(BaseModel):
    id: str
    run_id: str
    attempt_number: int = 1
    total_tests: int = 0
    passed_tests: int = 0
    failed_tests: int = 0
    duration_seconds: float = 0.0
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    status: str = "UNVERIFIED"
    evidence_version: str = "legacy"
    workspace_digest: Optional[str] = None
    skipped_tests: int = 0
    execution_error: Optional[str] = None
    test_items: List[TestResultItem] = []
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())

    @model_validator(mode='after')
    def validate_evidence_counts(self):
        if self.evidence_version != 'legacy':
            if min(self.total_tests, self.passed_tests, self.failed_tests, self.skipped_tests) < 0:
                raise ValueError('Negative test count')
            if self.total_tests != self.passed_tests + self.failed_tests + self.skipped_tests:
                raise ValueError('Test counts do not reconcile')
            if self.status == 'PASSED' and (self.exit_code != 0 or self.execution_error or self.passed_tests == 0 or self.failed_tests):
                raise ValueError('Passing tests require successful execution and evidence')
        return self

class RecoveryAttempt(BaseModel):
    id: str
    run_id: str
    attempt_number: int
    failure_reason: str
    diagnosis: str
    root_cause_analysis: str = ""
    proposed_fix: str
    files_modified: List[str] = []
    resolved: bool = False
    local_tests_passed: bool = False
    verified_recovered: Optional[bool] = None
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    duration_seconds: Optional[float] = None
    termination_reason: Optional[str] = None
    test_run_id: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    error_summary: Optional[str] = None
    subsequent_test_run_id: Optional[str] = None
    test_result_status: Optional[str] = None

# --- Code Review & Verification Models ---

class CriterionVerification(BaseModel):
    criterion_id: str
    criterion_description: str
    verdict: str  # "PASS", "FAIL", "PARTIAL"
    confidence_score: Optional[float] = None
    evidence: str = ""
    test_evidence_ref: Optional[str] = None

class ConstraintCompliance(BaseModel):
    constraint_id: str
    constraint_text: str = ""
    constraint: Optional[str] = None
    is_hard: bool = True
    compliant: Optional[bool] = None
    status: Optional[str] = "unknown"
    evidence: Optional[str] = None
    notes: str = ""

class VerificationReport(BaseModel):
    id: str
    run_id: str
    overall_verdict: str  # "VERIFIED_PASSED", "VERIFIED_WITH_WARNINGS", "FAILED_VERIFICATION"
    pass_rate_percent: Optional[float] = None
    goal_drift_score: Optional[float] = None  # 0.0 = perfect alignment, 100.0 = total drift
    goal_alignment_score: Optional[float] = None  # 100.0 = fully aligned, 0.0 = completely misaligned
    criteria_completion_rate: Optional[float] = None  # 0.0 - 100.0%
    test_pass_rate: Optional[float] = None  # 0.0 - 100.0%, None if tests unavailable
    component_penalties: Dict[str, float] = Field(default_factory=dict)  # goal_misalignment, criteria_gap, execution_failure
    security_violation_count: int = 0
    repeated_action_count: int = 0
    harmless_duplicate_skip_count: int = 0
    score_status: str = "partial_evidence"  # "computed", "partial_evidence", "missing_criteria", "unavailable_tests", "unknown_semantic"
    score_version: str = "v2.0"
    evidence_breakdown: Dict[str, Any] = Field(default_factory=dict)
    tests_passed: Optional[int] = 0
    tests_total: Optional[int] = 0
    criteria_evaluations: List[CriterionVerification] = []
    constraint_compliances: List[ConstraintCompliance] = []
    code_quality_score: Optional[float] = None
    security_verdict: str = "UNVERIFIED"
    verifier_version: str = "legacy"
    verified_success: Optional[bool] = None
    goal_model_version: Optional[str] = None
    review_summary: str
    recommendations: List[str] = []
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())

# --- Evaluation & Overall Run Models ---

class EvaluationMetrics(BaseModel):
    run_id: str
    task_id: str
    # Compatibility field: criterion coverage, NOT population task success.
    success_rate: Optional[float] = Field(default=None, ge=0, le=100, allow_inf_nan=False)
    metric_version: str = "legacy"
    verified_success: Optional[bool] = None
    outcome: str = "unverified"
    termination_reason: Optional[str] = None
    execution_mode: str = "unknown"
    evidence_stale: bool = False
    measurement_scope: str = 'Recorded service-boundary calls; pipeline duration includes verification up to metric computation, excludes final persistence; manual stage duration unavailable'
    execution_time_seconds: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    total_tool_calls: Optional[int] = Field(default=None, ge=0)
    total_model_calls: Optional[int] = Field(default=None, ge=0)
    input_tokens: Optional[int] = Field(default=None, ge=0)
    output_tokens: Optional[int] = Field(default=None, ge=0)
    recovery_attempts_count: int = 0
    goal_drift_score: Optional[float] = None
    goal_alignment_score: Optional[float] = None
    criteria_completion_rate: Optional[float] = None
    test_pass_rate: Optional[float] = None
    component_penalties: Dict[str, float] = Field(default_factory=dict)
    security_violation_count: int = 0
    repeated_action_count: int = 0
    harmless_duplicate_skip_count: int = 0
    score_status: str = "partial_evidence"
    score_version: str = "v2.0"
    evidence_breakdown: Dict[str, Any] = Field(default_factory=dict)
    lines_added: int = 0
    lines_removed: int = 0
    tests_passed: int = 0
    tests_total: int = 0
    telemetry: Optional[Dict[str, Any]] = None
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())

class ExecutionLogEntry(BaseModel):
    id: str
    run_id: str
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    stage: str  # "workspace", "requirement", "planner", "coder", "testing", "debugger", "verifier"
    agent_role: str
    event_type: str  # "info", "tool_call", "command", "file_edit", "test_run", "recovery", "warning", "error", "success"
    message: str
    details: Optional[Dict[str, Any]] = None
    task_id: Optional[str] = None
    step: Optional[int] = None
    agent_id: Optional[str] = None
    sub_goal_id: Optional[str] = None

class RunRecord(BaseModel):
    run_id: str
    task_id: str
    title: str
    prompt: str
    repo_path: str
    current_stage: str = "workspace"  # "workspace", "requirement", "planner", "coder", "testing", "verifier", "completed", "failed"
    status: str = "initialized"  # "initialized", "in_progress", "completed", "failed"
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = Field(default_factory=dict)
    goal_model: Optional[GoalModel] = None
    plan: Optional[ImplementationPlan] = None
    code_changes: List[CodeChange] = []
    test_results: List[TestRunResult] = []
    recovery_attempts: List[RecoveryAttempt] = []
    verification: Optional[VerificationReport] = None
    evaluation: Optional[EvaluationMetrics] = None
    logs: List[ExecutionLogEntry] = []

# --- Request DTOs ---

class ParseTaskRequest(BaseModel):
    request_text: str
    repo_path: Optional[str] = None
    model_name: Optional[str] = None
    run_id: Optional[str] = None
    language: Optional[str] = "auto"
    temperature: Optional[float] = Field(default=0.2, ge=0, le=2, allow_inf_nan=False)

class PatchGoalModelRequest(BaseModel):
    run_id: str
    main_goal: Optional[str] = None
    summary: Optional[str] = None
    sub_goals: Optional[List[SubGoal]] = None
    success_criteria: Optional[List[SuccessCriterion]] = None
    hard_constraints: Optional[List[Constraint]] = None
    soft_constraints: Optional[List[Constraint]] = None
    expected_output: Optional[ExpectedOutput] = None
    change_summary: Optional[str] = "Manual user edit"

class ResolveAmbiguityRequest(BaseModel):
    run_id: str
    ambiguity_id: str
    user_answer: str
    apply_as_constraint: Optional[bool] = True
    constraint_type: Optional[str] = "hard"

class OllamaConfigRequest(BaseModel):
    host: str = "http://localhost:11434"
    default_model: Optional[str] = None

class StartPlanRequest(BaseModel):
    run_id: str
    repo_path: Optional[str] = None

class ExecuteCodeRequest(BaseModel):
    run_id: str
    temperature: Optional[float] = 0.2
    model_name: Optional[str] = None

class ExecuteTestsRequest(BaseModel):
    run_id: str
    max_recovery_retries: Optional[int] = Field(default=3, ge=0, le=20)

class ExecuteVerificationRequest(BaseModel):
    run_id: str

class RunPipelineRequest(BaseModel):
    run_id: Optional[str] = None
    request_text: str
    repo_path: Optional[str] = None
    model_name: Optional[str] = None
    temperature: Optional[float] = Field(default=0.2, ge=0, le=2, allow_inf_nan=False)
    max_recovery_retries: Optional[int] = Field(default=3, ge=0, le=20)

class ReviseGoalRequest(BaseModel):
    run_id: str
    new_goal: str
    change_reason: Optional[str] = "User revised task goal"


class PolicyApprovalRequest(BaseModel):
    approval_id: str
    approved: bool
    comment: Optional[str] = None

class HardConstraint(BaseModel):
    id: str
    description: str
    category: str = "security"

class SoftConstraint(BaseModel):
    id: str
    description: str
    preference_weight: float = 0.5

AmbiguityQuestion = Ambiguity
