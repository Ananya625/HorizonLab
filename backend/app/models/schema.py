from pydantic import BaseModel, Field
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
    summary: str
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
    path: str
    action: str = "modify"  # "create", "modify", "delete", "test"
    description: str
    estimated_loc: int = 50

class PlanStep(BaseModel):
    step_number: int
    title: str
    description: str
    assigned_agent: str = "Coding Agent"
    target_files: List[str] = []
    dependencies: List[int] = []
    expected_outcome: str

class ImplementationPlan(BaseModel):
    run_id: str
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
    status: str = "PASSED"  # "PASSED", "FAILED"
    test_items: List[TestResultItem] = []
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())

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
    confidence_score: float = 1.0
    evidence: str = ""
    test_evidence_ref: Optional[str] = None

class ConstraintCompliance(BaseModel):
    constraint_id: str
    constraint_text: str
    is_hard: bool = True
    compliant: bool = True
    notes: str = ""

class VerificationReport(BaseModel):
    id: str
    run_id: str
    overall_verdict: str  # "VERIFIED_PASSED", "VERIFIED_WITH_WARNINGS", "FAILED_VERIFICATION"
    pass_rate_percent: float = 100.0
    goal_drift_score: float = 0.0  # 0.0 = perfect alignment, 100.0 = total drift
    goal_alignment_score: float = 100.0  # 100.0 = fully aligned, 0.0 = completely misaligned
    criteria_completion_rate: float = 100.0  # 0.0 - 100.0%
    test_pass_rate: Optional[float] = 100.0  # 0.0 - 100.0%, None if tests unavailable
    component_penalties: Dict[str, float] = Field(default_factory=dict)  # goal_misalignment, criteria_gap, execution_failure
    security_violation_count: int = 0
    repeated_action_count: int = 0
    harmless_duplicate_skip_count: int = 0
    score_status: str = "computed"  # "computed", "partial_evidence", "missing_criteria", "unavailable_tests", "unknown_semantic"
    score_version: str = "v2.0"
    evidence_breakdown: Dict[str, Any] = Field(default_factory=dict)
    criteria_evaluations: List[CriterionVerification] = []
    constraint_compliances: List[ConstraintCompliance] = []
    code_quality_score: float = 9.5
    security_verdict: str = "SECURE_PASS"
    review_summary: str
    recommendations: List[str] = []
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())

# --- Evaluation & Overall Run Models ---

class EvaluationMetrics(BaseModel):
    run_id: str
    task_id: str
    success_rate: float = 100.0
    execution_time_seconds: float = 0.0
    total_tool_calls: int = 0
    recovery_attempts_count: int = 0
    goal_drift_score: float = 0.0
    goal_alignment_score: float = 100.0
    criteria_completion_rate: float = 100.0
    test_pass_rate: Optional[float] = 100.0
    component_penalties: Dict[str, float] = Field(default_factory=dict)
    security_violation_count: int = 0
    repeated_action_count: int = 0
    harmless_duplicate_skip_count: int = 0
    score_status: str = "computed"
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
    model_name: Optional[str] = "qwen2.5-coder:7b"
    run_id: Optional[str] = None
    language: Optional[str] = "auto"
    temperature: Optional[float] = 0.2

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
    default_model: Optional[str] = "qwen2.5-coder:7b"

class StartPlanRequest(BaseModel):
    run_id: str
    repo_path: Optional[str] = None

class ExecuteCodeRequest(BaseModel):
    run_id: str

class ExecuteTestsRequest(BaseModel):
    run_id: str
    max_recovery_retries: Optional[int] = 3

class ExecuteVerificationRequest(BaseModel):
    run_id: str

class RunPipelineRequest(BaseModel):
    run_id: Optional[str] = None
    request_text: str
    repo_path: Optional[str] = None
    model_name: Optional[str] = "qwen2.5-coder:7b"
    temperature: Optional[float] = 0.2
    max_recovery_retries: Optional[int] = 3

class ReviseGoalRequest(BaseModel):
    run_id: str
    new_goal: str
    change_reason: Optional[str] = "User revised task goal"
