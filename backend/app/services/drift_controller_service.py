import os
import re
import time
import hashlib
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field

from .goal_tracker_service import goal_tracker_service, TaskTrackingState

logger = logging.getLogger(__name__)

class DriftDecision(BaseModel):
    allowed: bool
    violation_type: Optional[str] = None  # "unrelated_action", "path_traversal", "repeated_action", "budget_exceeded", "deadline_exceeded", "permission_violation", "premature_completion"
    event_category: str = "safe"  # "security_violation", "unrelated_action", "repeated_action", "harmless_duplicate_skip", "budget_exceeded", "deadline_exceeded", "verification_failure", "safe"
    reason: str
    action_category: str  # "safe", "blocked", "duplicate_skipped", "budget_exceeded"
    suggested_recovery: Optional[str] = None

class ResultValidation(BaseModel):
    valid: bool
    status: str  # "accepted", "failed", "syntax_error", "test_failure"
    feedback: str
    should_retry: bool = False
    evidence: Optional[Dict[str, Any]] = None

class DriftControllerService:
    def __init__(self):
        # In-memory action fingerprint cache per run: {run_id: set_of_action_fingerprints}
        self._action_fingerprints: Dict[str, Dict[str, int]] = {}
        # In-memory file hash history: {run_id: {file_path: [content_hashes]}}
        self._file_hash_history: Dict[str, Dict[str, List[str]]] = {}
        # In-memory structured audit events per run: {run_id: [event_dicts]}
        self._audit_events: Dict[str, List[Dict[str, Any]]] = {}
        # Execution limits
        self.default_limits = {
            "simple": {"max_tool_calls": 12, "max_retries": 2, "max_identical_actions": 2, "timeout_seconds": 60.0},
            "medium": {"max_tool_calls": 25, "max_retries": 3, "max_identical_actions": 3, "timeout_seconds": 180.0},
            "complex": {"max_tool_calls": 50, "max_retries": 5, "max_identical_actions": 3, "timeout_seconds": 360.0}
        }

    def check_action(
        self,
        run_id: str,
        action_type: str,  # "file_write", "file_read", "command_exec", "plan_generation"
        target: str,
        payload_str: str = "",
        repo_path: Optional[str] = None
    ) -> DriftDecision:
        """Deterministic-first pre-action drift validation executed BEFORE any tool call."""
        state = goal_tracker_service.get_state(run_id)
        if not state:
            return DriftDecision(allowed=True, reason="No tracking state registered; proceeding under standard policy.", action_category="safe")

        limits = self.default_limits.get(state.complexity_profile, self.default_limits["simple"])

        # 1. Deadline & Runtime Overrun Check
        current_time = time.time()
        if current_time > state.get_deadline_epoch():
            msg = f"Execution deadline exceeded ({state.deadline_seconds}s limit reached)."
            self._log_drift_event(run_id, "deadline_exceeded", msg, action_type, target, event_category="deadline_exceeded")
            goal_tracker_service.terminate_task(run_id, status="failed", reason="deadline_exceeded")
            return DriftDecision(
                allowed=False,
                violation_type="deadline_exceeded",
                event_category="deadline_exceeded",
                reason=msg,
                action_category="budget_exceeded",
                suggested_recovery="Terminate execution and report deadline timeout."
            )

        # 2. Total Tool Call Budget Check (Counts real tool executions)
        tool_call_count = len([
            a for a in state.action_history 
            if a.status in ("completed", "failed") and a.action_type in ("file_write", "command_exec", "test_run")
        ])
        if tool_call_count >= limits["max_tool_calls"]:
            msg = f"Action budget exhausted ({tool_call_count}/{limits['max_tool_calls']} calls used for {state.complexity_profile} profile)."
            self._log_drift_event(run_id, "budget_exceeded", msg, action_type, target, event_category="budget_exceeded")
            goal_tracker_service.terminate_task(run_id, status="failed", reason="budget_exceeded")
            return DriftDecision(
                allowed=False,
                violation_type="budget_exceeded",
                event_category="budget_exceeded",
                reason=msg,
                action_category="budget_exceeded",
                suggested_recovery="Halt execution; excessive tool actions indicate unconverged loop."
            )

        # 3. Path Traversal & Filesystem Permission Check (Security Violation)
        target_norm = target.replace("\\", "/")
        if ".." in target_norm or target_norm.startswith(("/", "\\", "C:", "D:")) and repo_path:
            # Check if attempting to write outside target repo
            if not os.path.abspath(target).startswith(os.path.abspath(repo_path)):
                msg = f"Security Violation: Proposed file path '{target}' escapes designated repository sandbox '{repo_path}'."
                self._log_drift_event(run_id, "path_traversal", msg, action_type, target, event_category="security_violation")
                return DriftDecision(
                    allowed=False,
                    violation_type="path_traversal",
                    event_category="security_violation",
                    reason=msg,
                    action_category="blocked",
                    suggested_recovery="Restrict path to relative paths inside the active sandbox directory."
                )

        forbidden_patterns = [r"\.git/", r"\.venv/", r"node_modules/", r"/etc/", r"C:[\\/]Windows"]
        for pat in forbidden_patterns:
            if re.search(pat, target_norm, re.IGNORECASE):
                msg = f"Permission Violation: Target '{target}' matches protected system directory pattern."
                self._log_drift_event(run_id, "permission_violation", msg, action_type, target, event_category="security_violation")
                return DriftDecision(
                    allowed=False,
                    violation_type="permission_violation",
                    event_category="security_violation",
                    reason=msg,
                    action_category="blocked",
                    suggested_recovery="Target only project application and test source files."
                )

        # 4. Scope & Relevance Check (Detect actions unrelated to goal)
        if action_type == "file_write":
            # Check if file has valid extension for coding task
            valid_exts = (".py", ".json", ".txt", ".md", ".yaml", ".yml", ".ini", ".cfg", ".toml", ".js", ".ts", ".html", ".css")
            if not target_norm.endswith(valid_exts):
                msg = f"Scope Drift: File '{target}' has invalid or unapproved file extension for coding agent."
                self._log_drift_event(run_id, "unrelated_action", msg, action_type, target, event_category="unrelated_action")
                return DriftDecision(
                    allowed=False,
                    violation_type="unrelated_action",
                    event_category="unrelated_action",
                    reason=msg,
                    action_category="blocked",
                    suggested_recovery="Target standard software source or test files."
                )

            # Check if file is completely alien to declared subtasks or request
            goal_lower = state.current_goal.lower()
            target_base = os.path.basename(target_norm).lower()
            # If target filename looks like system binaries or alien scripts
            if any(k in target_base for k in ["exploit", "hack", "bitcoin", "miner", "trojan", "passwords.txt"]):
                msg = f"Security Drift: File '{target}' appears unrelated or malicious relative to goal '{state.current_goal[:60]}'."
                self._log_drift_event(run_id, "unrelated_action", msg, action_type, target, event_category="unrelated_action")
                return DriftDecision(
                    allowed=False,
                    violation_type="unrelated_action",
                    event_category="unrelated_action",
                    reason=msg,
                    action_category="blocked",
                    suggested_recovery="Align file naming with software application components."
                )

        # 5. Repeated Action & Identical Edit Loop Check
        if action_type == "file_write" and payload_str:
            payload_hash = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()[:16]
            if run_id not in self._file_hash_history:
                self._file_hash_history[run_id] = {}
            history = self._file_hash_history[run_id].setdefault(target_norm, [])
            
            if payload_hash in history:
                # Same exact content already applied previously - Harmless duplicate skip to avoid redundant writes
                msg = f"Repeated Edit Loop: Proposed content for '{target}' is identical to previously applied content ({payload_hash}). No new evidence generated."
                self._log_drift_event(run_id, "repeated_action", msg, action_type, target, event_category="harmless_duplicate_skip")
                return DriftDecision(
                    allowed=False,
                    violation_type="repeated_action",
                    event_category="harmless_duplicate_skip",
                    reason=msg,
                    action_category="duplicate_skipped",
                    suggested_recovery="Introduce targeted corrections addressing test failure diagnosis."
                )
            
            # Register content hash and reset command repeat counters since workspace code has changed
            history.append(payload_hash)
            if run_id in self._action_fingerprints:
                self._action_fingerprints[run_id].clear()

        # If repeating identical command without state changes
        if action_type == "command_exec":
            payload_hash = hashlib.sha256((payload_str or "").encode("utf-8")).hexdigest()[:16]
            action_key = f"{action_type}:{target_norm}:{payload_hash}"

            if run_id not in self._action_fingerprints:
                self._action_fingerprints[run_id] = {}

            seen_count = self._action_fingerprints[run_id].get(action_key, 0)
            if seen_count >= limits["max_identical_actions"]:
                msg = f"Repeated Command: Command '{target}' executed {seen_count} times without intermediate workspace code changes."
                self._log_drift_event(run_id, "repeated_action", msg, action_type, target, event_category="repeated_action")
                return DriftDecision(
                    allowed=False,
                    violation_type="repeated_action",
                    event_category="repeated_action",
                    reason=msg,
                    action_category="duplicate_skipped",
                    suggested_recovery="Skip duplicate command execution; await code modification."
                )
            self._action_fingerprints[run_id][action_key] = seen_count + 1

        return DriftDecision(allowed=True, reason="Action passed all drift & security policies.", action_category="safe", event_category="safe")

    def reset_file_history(self, run_id: str, file_path: Optional[str] = None):
        """Clears file hash history for a run or file to allow genuine self-healing recovery fixes."""
        if run_id in self._file_hash_history:
            if file_path:
                target_norm = file_path.replace("\\", "/")
                if target_norm in self._file_hash_history[run_id]:
                    self._file_hash_history[run_id][target_norm].clear()
            else:
                self._file_hash_history[run_id].clear()
        if run_id in self._action_fingerprints:
            self._action_fingerprints[run_id].clear()

    def validate_result(
        self,
        run_id: str,
        action_type: str,
        target: str,
        success: bool,
        details: Optional[Dict[str, Any]] = None
    ) -> ResultValidation:
        """Validates tool results after execution and records real evidence."""
        det = details or {}
        
        # Validate file edit AST syntax
        if action_type == "file_write":
            ast_valid = det.get("ast_valid", True)
            if not ast_valid:
                return ResultValidation(
                    valid=False,
                    status="syntax_error",
                    feedback=f"File '{target}' contains Python syntax error. AST parse failed.",
                    should_retry=True
                )
            return ResultValidation(
                valid=True,
                status="accepted",
                feedback=f"File '{target}' successfully written and verified with valid AST syntax.",
                evidence={"file": target, "lines_added": det.get("lines_added", 0)}
            )

        # Validate test runner execution
        if action_type == "test_run":
            exit_code = det.get("exit_code", 0)
            passed = det.get("passed_tests", 0)
            total = det.get("total_tests", 0)
            
            if success and exit_code == 0 and passed > 0 and det.get("failed_tests", 0) == 0:
                # Mark criteria passed in GoalTracker
                from .db import db_service
                # Pipeline goals require the independent verifier; local test success
                # alone does not establish arbitrary acceptance criteria.
                if db_service.get_goal_model(run_id) is None:
                    goal_tracker_service.verify_criterion(
                        run_id=run_id, criterion_id="all", passed=True,
                        evidence=f"Automated pytest confirmed {passed}/{total} tests passed cleanly."
                    )
                return ResultValidation(
                    valid=True,
                    status="accepted",
                    feedback=f"Test suite passed completely ({passed}/{total} tests).",
                    evidence={"exit_code": 0, "passed": passed, "total": total}
                )
            else:
                return ResultValidation(
                    valid=False,
                    status="test_failure",
                    feedback=f"Tests failed ({det.get('failed_tests', 1)} failed, exit code {exit_code}).",
                    should_retry=True,
                    evidence={"exit_code": exit_code, "stdout": det.get("stdout", "")[:300]}
                )

        return ResultValidation(valid=True, status="accepted", feedback="Action completed successfully.")

    def check_completion(self, run_id: str) -> DriftDecision:
        """Enforces that completion cannot be claimed prematurely without verified evidence."""
        state = goal_tracker_service.get_state(run_id)
        if not state:
            return DriftDecision(allowed=True, reason="No tracker state.", action_category="safe", event_category="safe")

        # Must have verified acceptance criteria
        if not goal_tracker_service.can_complete(run_id):
            unverified = [c.id for c in state.acceptance_criteria if c.status != "passed"]
            msg = f"Premature Completion Blocked: Acceptance criteria {unverified} remain unverified without passing test evidence."
            self._log_drift_event(run_id, "premature_completion", msg, "completion_check", "verifier", event_category="verification_failure")
            return DriftDecision(
                allowed=False,
                violation_type="premature_completion",
                event_category="verification_failure",
                reason=msg,
                action_category="blocked",
                suggested_recovery="Run test suite and verify acceptance criteria assertions before marking complete."
            )

        return DriftDecision(allowed=True, reason="All required acceptance criteria verified with evidence.", action_category="safe", event_category="safe")

    def _categorize_event(self, violation_type: str, reason: str = "", action_type: str = "") -> str:
        """Maps violation to one of the 7 canonical policy event categories."""
        if violation_type in ("path_traversal", "permission_violation", "security_violation"):
            return "security_violation"
        if violation_type in ("unrelated_action", "scope_drift"):
            return "unrelated_action"
        if violation_type == "repeated_action":
            if "identical" in reason.lower() and "file" in action_type:
                return "harmless_duplicate_skip"
            return "repeated_action"
        if violation_type == "budget_exceeded":
            return "budget_exceeded"
        if violation_type == "deadline_exceeded":
            return "deadline_exceeded"
        if violation_type in ("verification_failure", "premature_completion", "test_failure", "syntax_error"):
            return "verification_failure"
        return "unrelated_action"

    def _log_drift_event(
        self,
        run_id: str,
        violation_type: str,
        reason: str,
        action_type: str,
        target: str,
        event_category: Optional[str] = None
    ):
        """Logs structured drift decision into memory cache and SQLite audit ledger."""
        cat = event_category or self._categorize_event(violation_type, reason, action_type)
        logger.warning(f"[{run_id}] DriftController: {cat.upper()} ({violation_type}) - {reason} (Target: {target})")

        event_dict = {
            "run_id": run_id,
            "violation_type": violation_type,
            "event_category": cat,
            "action_type": action_type,
            "target": target,
            "reason": reason,
            "timestamp": datetime.now().isoformat()
        }
        if run_id not in self._audit_events:
            self._audit_events[run_id] = []
        self._audit_events[run_id].append(event_dict)

        try:
            from .db import db_service
            db_service.add_log(
                run_id=run_id,
                stage="verifier",
                agent_role="Drift Controller",
                event_type="warning" if cat == "harmless_duplicate_skip" else "error",
                message=f"Drift Control [{cat.upper()}]: {reason}",
                details={"violation_type": violation_type, "event_category": cat, "action_type": action_type, "target": target}
            )
            with db_service._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS drift_audit_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        run_id TEXT NOT NULL,
                        violation_type TEXT NOT NULL,
                        event_category TEXT DEFAULT 'unrelated_action',
                        action_type TEXT NOT NULL,
                        target TEXT NOT NULL,
                        reason TEXT NOT NULL,
                        timestamp TEXT NOT NULL
                    )
                """)
                try:
                    cursor.execute("ALTER TABLE drift_audit_logs ADD COLUMN event_category TEXT DEFAULT 'unrelated_action'")
                except Exception:
                    pass

                cursor.execute("""
                    INSERT INTO drift_audit_logs (run_id, violation_type, event_category, action_type, target, reason, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (run_id, violation_type, cat, action_type, target, reason, event_dict["timestamp"]))
                conn.commit()
        except Exception:
            pass

    def get_audit_summary(self, run_id: str) -> Dict[str, Any]:
        """Returns structured audit summary categorized into 7 canonical event types with deduplication."""
        events = list(self._audit_events.get(run_id, []))
        if not events:
            try:
                from .db import db_service
                with db_service._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT violation_type, event_category, action_type, target, reason, timestamp
                        FROM drift_audit_logs WHERE run_id = ?
                    """, (run_id,))
                    rows = cursor.fetchall()
                    for r in rows:
                        events.append({
                            "run_id": run_id,
                            "violation_type": r[0],
                            "event_category": r[1] if (len(r) > 1 and r[1]) else self._categorize_event(r[0], r[4], r[2]),
                            "action_type": r[2],
                            "target": r[3],
                            "reason": r[4],
                            "timestamp": r[5]
                        })
            except Exception:
                pass

        # Deduplicate identical underlying failures across retry attempts or repeated logs
        seen_failure_keys = set()
        security_violation_count = 0
        unrelated_action_count = 0
        repeated_action_count = 0
        harmless_duplicate_skip_count = 0
        budget_exceeded_count = 0
        deadline_exceeded_count = 0
        verification_failure_count = 0

        for ev in events:
            cat = ev.get("event_category") or self._categorize_event(ev.get("violation_type", ""), ev.get("reason", ""), ev.get("action_type", ""))
            dedup_key = f"{cat}:{ev.get('action_type', '')}:{ev.get('target', '')}"

            if cat == "security_violation":
                if dedup_key not in seen_failure_keys:
                    seen_failure_keys.add(dedup_key)
                    security_violation_count += 1
            elif cat == "unrelated_action":
                if dedup_key not in seen_failure_keys:
                    seen_failure_keys.add(dedup_key)
                    unrelated_action_count += 1
            elif cat == "repeated_action":
                repeated_action_count += 1
            elif cat == "harmless_duplicate_skip":
                harmless_duplicate_skip_count += 1
            elif cat == "budget_exceeded":
                budget_exceeded_count += 1
            elif cat == "deadline_exceeded":
                deadline_exceeded_count += 1
            elif cat == "verification_failure":
                if dedup_key not in seen_failure_keys:
                    seen_failure_keys.add(dedup_key)
                    verification_failure_count += 1

        return {
            "security_violation_count": security_violation_count,
            "unrelated_action_count": unrelated_action_count,
            "repeated_action_count": repeated_action_count,
            "harmless_duplicate_skip_count": harmless_duplicate_skip_count,
            "budget_exceeded_count": budget_exceeded_count,
            "deadline_exceeded_count": deadline_exceeded_count,
            "verification_failure_count": verification_failure_count,
            "total_events": len(events),
            "events": events
        }

drift_controller_service = DriftControllerService()
