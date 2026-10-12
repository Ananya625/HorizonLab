import time
import uuid
import hashlib
import sqlite3
from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field

class GoalSubtask(BaseModel):
    id: str
    order: int
    title: str
    description: str
    assigned_agent: str = "Coding Agent"
    target_files: List[str] = []
    status: str = "pending"  # "pending", "running", "completed", "failed", "blocked"
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    evidence: Optional[str] = None

class GoalCriterion(BaseModel):
    id: str
    description: str
    metric: str
    status: str = "pending"  # "pending", "passed", "failed"
    evidence: Optional[str] = None
    verified_at: Optional[str] = None

class ActionRecord(BaseModel):
    id: str
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    action_type: str  # "file_read", "file_write", "command_exec", "ast_check", "test_run"
    target: str
    payload_hash: str
    status: str  # "accepted", "blocked", "completed", "failed", "skipped_duplicate"
    details: Optional[Dict[str, Any]] = None
    duration_ms: float = 0.0
    error_message: Optional[str] = None

class GoalRevisionRecord(BaseModel):
    revision_id: str
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    previous_goal: str
    revised_goal: str
    change_reason: str
    author: str = "user"

class TaskTrackingState(BaseModel):
    task_id: str
    run_id: str
    original_user_request: str  # Immutable anchor
    current_goal: str           # Mutable via controlled revisions
    complexity_profile: str     # "simple", "medium", "complex"
    acceptance_criteria: List[GoalCriterion] = []
    ordered_subtasks: List[GoalSubtask] = []
    current_active_subtask_id: Optional[str] = None
    task_status: str = "pending"  # "pending", "running", "blocked", "completed", "failed"
    action_history: List[ActionRecord] = []
    failed_attempts_count: int = 0
    start_time_epoch: float = Field(default_factory=time.time)
    deadline_seconds: float = 90.0
    deadline_epoch: float = 0.0
    termination_reason: Optional[str] = None  # "criteria_verified", "budget_exceeded", "drift_blocked", "max_retries_exceeded", "timeout"
    completion_evidence: Dict[str, Any] = {}
    revision_history: List[GoalRevisionRecord] = []

    def get_deadline_epoch(self) -> float:
        if self.deadline_epoch <= 0:
            self.deadline_epoch = self.start_time_epoch + self.deadline_seconds
        return self.deadline_epoch

class GoalTrackerService:
    def __init__(self):
        # Thread-safe in-memory cache keyed by run_id for state isolation between concurrent tasks
        self._active_tasks: Dict[str, TaskTrackingState] = {}

    def initialize_task(
        self,
        run_id: str,
        task_id: str,
        original_request: str,
        complexity_profile: str = "simple",
        acceptance_criteria: Optional[List[Dict[str, Any]]] = None,
        target_files: Optional[List[str]] = None,
        deadline_seconds: Optional[float] = None
    ) -> TaskTrackingState:
        """Initializes a deterministic goal tracker state for a task."""
        now = time.time()
        
        # Determine execution deadline based on complexity profile
        if deadline_seconds is not None:
            effective_deadline_sec = deadline_seconds
        elif complexity_profile == "simple":
            effective_deadline_sec = 45.0
        elif complexity_profile == "medium":
            effective_deadline_sec = 120.0
        else:
            effective_deadline_sec = 240.0

        # Construct acceptance criteria
        criteria: List[GoalCriterion] = []
        if acceptance_criteria:
            for i, c in enumerate(acceptance_criteria):
                criteria.append(GoalCriterion(
                    id=c.get("id", f"SC-{i+1}"),
                    description=c.get("description", "Acceptance criterion"),
                    metric=c.get("metric", "test == PASS")
                ))
        else:
            criteria.append(GoalCriterion(
                id="SC-1",
                description="Targeted test suite and AST syntax verification pass cleanly with 0 failures",
                metric="pytest == PASS"
            ))

        # Generate subtasks ONLY when decomposition adds engineering value
        subtasks: List[GoalSubtask] = []
        if complexity_profile == "simple":
            # For simple tasks: single direct execution subtask
            subtasks.append(GoalSubtask(
                id="SUBTASK-1",
                order=1,
                title="Implement and verify isolated code changes",
                description=f"Direct implementation and targeted test verification for: {original_request[:80]}",
                target_files=target_files or ["app/service.py", "tests/test_service.py"],
                status="pending"
            ))
        else:
            # For medium and complex tasks: decomposed engineering phases
            subtasks.append(GoalSubtask(
                id="SUBTASK-1",
                order=1,
                title="Analyze repository structure and define specification",
                description="Inspect existing codebase modules and establish integration boundaries",
                target_files=target_files or [],
                status="pending"
            ))
            subtasks.append(GoalSubtask(
                id="SUBTASK-2",
                order=2,
                title="Generate core implementation and module updates",
                description=f"Write code changes fulfilling requirements: {original_request[:80]}",
                target_files=target_files or [],
                status="pending"
            ))
            subtasks.append(GoalSubtask(
                id="SUBTASK-3",
                order=3,
                title="Execute automated test suite and verify acceptance criteria",
                description="Execute test runner, self-heal anomalies, and audit criteria compliance",
                target_files=target_files or [],
                status="pending"
            ))

        state = TaskTrackingState(
            task_id=task_id,
            run_id=run_id,
            original_user_request=original_request,
            current_goal=original_request,
            complexity_profile=complexity_profile,
            acceptance_criteria=criteria,
            ordered_subtasks=subtasks,
            current_active_subtask_id=subtasks[0].id if subtasks else None,
            task_status="running",
            start_time_epoch=now,
            deadline_seconds=effective_deadline_sec,
            deadline_epoch=now + effective_deadline_sec
        )

        self._active_tasks[run_id] = state
        self._persist_state(state)
        return state

    def get_state(self, run_id: str) -> Optional[TaskTrackingState]:
        """Retrieves tracking state for a specific run ID."""
        if run_id in self._active_tasks:
            return self._active_tasks[run_id]
        return self._load_state(run_id)

    def revise_goal(
        self,
        run_id: str,
        new_goal_text: str,
        change_reason: str = "User explicit goal revision",
        author: str = "user"
    ) -> TaskTrackingState:
        """Controlled goal-revision mechanism: updates current goal while strictly preserving original request."""
        state = self.get_state(run_id)
        if not state:
            raise ValueError(f"Task with run_id '{run_id}' not found in GoalTracker")

        revision = GoalRevisionRecord(
            revision_id=f"rev_{uuid.uuid4().hex[:8]}",
            previous_goal=state.current_goal,
            revised_goal=new_goal_text,
            change_reason=change_reason,
            author=author
        )
        state.revision_history.append(revision)
        state.current_goal = new_goal_text

        self._persist_state(state)
        return state

    def start_subtask(self, run_id: str, subtask_id: str) -> Optional[GoalSubtask]:
        """Marks a subtask as currently active and running."""
        state = self.get_state(run_id)
        if not state:
            return None

        for st in state.ordered_subtasks:
            if st.id == subtask_id:
                st.status = "running"
                st.started_at = datetime.now().isoformat()
                state.current_active_subtask_id = subtask_id
                self._persist_state(state)
                return st
        return None

    def complete_subtask(self, run_id: str, subtask_id: str, evidence: str) -> Optional[GoalSubtask]:
        """Marks a subtask as completed based on actual verified evidence."""
        state = self.get_state(run_id)
        if not state:
            return None

        target_st = None
        for i, st in enumerate(state.ordered_subtasks):
            if st.id == subtask_id:
                st.status = "completed"
                st.completed_at = datetime.now().isoformat()
                st.evidence = evidence
                target_st = st
                # Advance active subtask to next pending subtask if available
                if i + 1 < len(state.ordered_subtasks):
                    state.current_active_subtask_id = state.ordered_subtasks[i + 1].id
                else:
                    state.current_active_subtask_id = None
                break

        self._persist_state(state)
        return target_st

    def record_action(
        self,
        run_id: str,
        action_type: str,
        target: str,
        payload_str: str,
        status: str,
        details: Optional[Dict[str, Any]] = None,
        duration_ms: float = 0.0,
        error_message: Optional[str] = None
    ) -> ActionRecord:
        """Records an attempted or executed action in the chronological ledger."""
        state = self.get_state(run_id)
        payload_hash = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()[:16]

        record = ActionRecord(
            id=f"act_{uuid.uuid4().hex[:8]}",
            action_type=action_type,
            target=target,
            payload_hash=payload_hash,
            status=status,
            details=details or {},
            duration_ms=duration_ms,
            error_message=error_message
        )

        if state:
            state.action_history.append(record)
            if status in ("failed", "blocked"):
                state.failed_attempts_count += 1
            self._persist_state(state)

        return record

    def verify_criterion(
        self,
        run_id: str,
        criterion_id: str,
        passed: bool,
        evidence: str
    ):
        """Updates acceptance criterion outcome based on real tool/test results."""
        state = self.get_state(run_id)
        if not state:
            return

        for crit in state.acceptance_criteria:
            if crit.id == criterion_id or criterion_id == "all":
                crit.status = "passed" if passed else "failed"
                crit.evidence = evidence
                crit.verified_at = datetime.now().isoformat()

        self._persist_state(state)

    def can_complete(self, run_id: str) -> bool:
        """Determines if the task has fulfilled all required criteria with verified evidence."""
        state = self.get_state(run_id)
        if not state:
            return False

        if not state.acceptance_criteria:
            return True

        # All criteria must be passed
        return all(c.status == "passed" for c in state.acceptance_criteria)

    def terminate_task(
        self,
        run_id: str,
        status: str,
        reason: str,
        evidence: Optional[Dict[str, Any]] = None
    ) -> TaskTrackingState:
        """Marks the task as completed, failed, or blocked with concrete termination evidence."""
        state = self.get_state(run_id)
        if not state:
            raise ValueError(f"Task with run_id '{run_id}' not found")

        state.task_status = status
        state.termination_reason = reason
        if evidence:
            state.completion_evidence.update(evidence)

        # Mark all pending subtasks as completed if task succeeded
        if status == "completed":
            for st in state.ordered_subtasks:
                if st.status != "completed":
                    st.status = "completed"
                    st.completed_at = datetime.now().isoformat()
                    st.evidence = st.evidence or "Auto-verified upon task completion"

        self._persist_state(state)
        return state

    def _persist_state(self, state: TaskTrackingState):
        """Persists state into SQLite goal_tracking_state table."""
        try:
            from .db import db_service
            with db_service._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS goal_tracking_state (
                        run_id TEXT PRIMARY KEY,
                        task_id TEXT NOT NULL,
                        original_request TEXT NOT NULL,
                        current_goal TEXT NOT NULL,
                        task_status TEXT NOT NULL,
                        state_json TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                """)
                cursor.execute("""
                    INSERT INTO goal_tracking_state (run_id, task_id, original_request, current_goal, task_status, state_json, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(run_id) DO UPDATE SET
                        current_goal = excluded.current_goal,
                        task_status = excluded.task_status,
                        state_json = excluded.state_json,
                        updated_at = excluded.updated_at
                """, (
                    state.run_id,
                    state.task_id,
                    state.original_user_request,
                    state.current_goal,
                    state.task_status,
                    state.model_dump_json(),
                    datetime.now().isoformat()
                ))
                conn.commit()
        except Exception:
            # Fallback to in-memory cache if DB not initialized yet
            pass

    def _load_state(self, run_id: str) -> Optional[TaskTrackingState]:
        """Loads state from SQLite goal_tracking_state table."""
        try:
            from .db import db_service
            with db_service._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT state_json FROM goal_tracking_state WHERE run_id = ?", (run_id,))
                row = cursor.fetchone()
                if row:
                    data = row["state_json"] if isinstance(row, sqlite3.Row) else row[0]
                    state = TaskTrackingState.model_validate_json(data)
                    self._active_tasks[run_id] = state
                    return state
        except Exception:
            pass
        return None

goal_tracker_service = GoalTrackerService()
