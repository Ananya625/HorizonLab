"""Evidence-Grounded, Recovery-Aware Dynamic Capability Profiling Service.

Design principles
-----------------
* Every displayed metric must be traceable to real execution evidence or an
  explicitly identified statistical estimate.
* Binary outcomes are reported as raw observed successes divided by observed
  outcomes. Continuous measurements are stored as raw values and summarised
  descriptively.
* Where reliable evidence is unavailable the service returns
  ``evidence_status: "insufficient_evidence"`` instead of fabricating a score.
* ONE task-level success/failure observation is recorded per completed run, not
  one per pipeline stage. Stage events are stored for trajectory analysis but
  are NOT counted as independent capability observations.
* Recovery is tracked via explicit episode records, not inferred from stage
  completion.
* Live early-failure scores remain unavailable until a validated supervised
  model is deployed. Heuristic scores are never presented as predictions.
"""
from __future__ import annotations

import json
import logging
import math
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Optional, TypedDict


from .db import db_service
from .capability_estimator import (
    ContinuousSummary,
    CapabilityPolicyEngine,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Model name validation
# ---------------------------------------------------------------------------

_INVALID_MODEL_NAMES = {"none", "unknown", "null", "", "n/a", "undefined"}


def validate_model_name(model_name: Optional[str]) -> str:
    """Validate and normalise a model name.

    Raises ``ValueError`` for clearly invalid names like ``"none"`` or ``""``.
    Returns the stripped, non-empty model name.
    """
    if model_name is None:
        raise ValueError("model_name must not be None")
    clean = model_name.strip()
    if clean.lower() in _INVALID_MODEL_NAMES:
        raise ValueError(
            f"Invalid model_name '{model_name}'. "
            f"Must be a real model identifier, not one of {sorted(_INVALID_MODEL_NAMES)}."
        )
    return clean


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# LangGraph state (used for the observe → predict → profile pipeline)
# ---------------------------------------------------------------------------

class FeatureState(TypedDict, total=False):
    run_id: str
    model_name: str
    stage: str
    success: bool
    event_type: str
    details: dict[str, Any]
    elapsed_seconds: float
    risk_score: float
    risk_reasons: list[str]
    risk_action: str
    model_reliability: float
    risk_model_version: str
    provenance: str  # "llm" | "template" | "fallback" | "mock"
    # Consistent step index propagated across nodes
    _step_index: int
    # Task-level outcome — set only at run completion
    task_verified_success: Optional[bool]


# ---------------------------------------------------------------------------
# Risk action thresholds
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# DB migration helper
# ---------------------------------------------------------------------------

_MIGRATIONS = [
    # v1 → v2: add raw observation tables and recovery episode table
    """CREATE TABLE IF NOT EXISTS capability_observations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        obs_id TEXT NOT NULL UNIQUE,        -- stable dedup key (run_id+capability)
        model_name TEXT NOT NULL,
        capability TEXT NOT NULL,
        run_id TEXT NOT NULL,
        successes INTEGER NOT NULL DEFAULT 0,
        failures INTEGER NOT NULL DEFAULT 0,
        -- extra evidence fields stored as JSON
        evidence_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL
    )""",

    """CREATE TABLE IF NOT EXISTS capability_profiles_v2 (
        model_name TEXT NOT NULL,
        capability TEXT NOT NULL,
        -- raw aggregates (reproducible)
        total_successes INTEGER NOT NULL DEFAULT 0,
        total_failures INTEGER NOT NULL DEFAULT 0,
        -- continuous measurements stored as JSON list
        duration_values_json TEXT NOT NULL DEFAULT '[]',
        extra_json TEXT NOT NULL DEFAULT '{}',
        updated_at TEXT NOT NULL,
        alpha_prior REAL NOT NULL DEFAULT 1.0,
        beta_prior REAL NOT NULL DEFAULT 1.0,
        PRIMARY KEY (model_name, capability)
    )""",

    """CREATE TABLE IF NOT EXISTS recovery_episodes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        episode_id TEXT NOT NULL UNIQUE,
        run_id TEXT NOT NULL,
        model_name TEXT NOT NULL,
        failure_type TEXT NOT NULL,          -- tool_failure | test_failure | planning_failure | repeated_error | goal_deviation | unknown
        original_error TEXT NOT NULL DEFAULT '',
        failure_timestamp TEXT NOT NULL,
        recovery_start_timestamp TEXT,
        recovery_end_timestamp TEXT,
        recovery_actions_json TEXT NOT NULL DEFAULT '[]',
        extra_test_executions INTEGER NOT NULL DEFAULT 0,
        original_failure_resolved INTEGER NOT NULL DEFAULT 0,   -- 0/1
        regression_tests_passed INTEGER,                        -- NULL = not run, 0/1
        final_verified_outcome TEXT,         -- PASSED | FAILED | NOT_VERIFIED
        human_intervention INTEGER NOT NULL DEFAULT 0,
        recovery_duration_seconds REAL,
        extra_steps INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL
    )""",

    """CREATE TABLE IF NOT EXISTS trajectory_features (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT NOT NULL,
        step_index INTEGER NOT NULL,
        step_timestamp TEXT NOT NULL,
        stage TEXT NOT NULL,
        event_type TEXT NOT NULL,
        cumulative_errors INTEGER NOT NULL DEFAULT 0,
        cumulative_test_failures INTEGER NOT NULL DEFAULT 0,
        repeated_messages INTEGER NOT NULL DEFAULT 0,
        steps_without_progress INTEGER NOT NULL DEFAULT 0,
        constraint_violations INTEGER NOT NULL DEFAULT 0,
        elapsed_seconds REAL NOT NULL DEFAULT 0,
        -- pre-test feature columns
        ast_errors INTEGER NOT NULL DEFAULT 0,
        json_parse_errors INTEGER NOT NULL DEFAULT 0,
        plan_discrepancy INTEGER NOT NULL DEFAULT 0,
        retry_count INTEGER NOT NULL DEFAULT 0,
        tool_failures INTEGER NOT NULL DEFAULT 0,
        latency_anomaly INTEGER NOT NULL DEFAULT 0,
        llm_fallback_used INTEGER NOT NULL DEFAULT 0,
        template_used INTEGER NOT NULL DEFAULT 0,
        diff_size INTEGER NOT NULL DEFAULT 0,
        -- label: did this run eventually fail? (set at run completion)
        label_task_failed INTEGER,           -- NULL until run completes
        created_at TEXT NOT NULL,
        UNIQUE(run_id, step_index)
    )""",

    """CREATE TABLE IF NOT EXISTS prediction_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT NOT NULL,
        step_index INTEGER NOT NULL,
        risk_score REAL NOT NULL,
        risk_reasons_json TEXT NOT NULL DEFAULT '[]',
        risk_action TEXT NOT NULL DEFAULT 'continue',
        executed_action TEXT,
        execution_status TEXT NOT NULL DEFAULT 'recommended',
        execution_outcome_json TEXT,
        feature_snapshot_json TEXT NOT NULL DEFAULT '{}',
        model_version TEXT NOT NULL DEFAULT 'rule_baseline_v1',
        intervention_triggered INTEGER NOT NULL DEFAULT 0,
        final_outcome TEXT,                  -- filled at run completion
        created_at TEXT NOT NULL
    )""",

    """CREATE TABLE IF NOT EXISTS feature_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT NOT NULL,
        model_name TEXT NOT NULL,
        stage TEXT NOT NULL,
        event_type TEXT NOT NULL,
        success INTEGER NOT NULL,
        details_json TEXT NOT NULL DEFAULT '{}',
        elapsed_seconds REAL NOT NULL DEFAULT 0,
        risk_score REAL,
        risk_reasons_json TEXT,
        provenance TEXT DEFAULT 'llm',
        created_at TEXT NOT NULL
    )""",

    """CREATE TABLE IF NOT EXISTS recovery_run_stats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT NOT NULL UNIQUE,
        stats_json TEXT NOT NULL,
        created_at TEXT NOT NULL
    )""",

    """CREATE TABLE IF NOT EXISTS policy_approvals (
        approval_id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL,
        step_index INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        comment TEXT,
        created_at TEXT NOT NULL,
        resolved_at TEXT,
        UNIQUE(run_id, step_index)
    )""",
]

_LEGACY_TABLES_TO_KEEP = {
    "feature_events",        # kept for backward compatibility / older runs
    "capability_profiles",   # kept so old API queries don't crash
    "recovery_run_stats",    # kept for old runs
}

# Columns to ensure exist (idempotent ALTER TABLE ADD COLUMN)
_ENSURE_COLUMNS = [
    ("recovery_run_stats", "updated_at", "TEXT"),
    ("feature_events", "provenance", "TEXT DEFAULT 'llm'"),
    ("capability_observations", "is_valid", "INTEGER NOT NULL DEFAULT 1"),
    ("capability_observations", "provenance", "TEXT DEFAULT 'llm'"),
    ("capability_observations", "task_type", "TEXT"),
    ("capability_observations", "difficulty", "TEXT"),
    # Pre-test feature columns on trajectory_features
    ("trajectory_features", "ast_errors", "INTEGER NOT NULL DEFAULT 0"),
    ("trajectory_features", "json_parse_errors", "INTEGER NOT NULL DEFAULT 0"),
    ("trajectory_features", "plan_discrepancy", "INTEGER NOT NULL DEFAULT 0"),
    ("trajectory_features", "retry_count", "INTEGER NOT NULL DEFAULT 0"),
    ("trajectory_features", "tool_failures", "INTEGER NOT NULL DEFAULT 0"),
    ("trajectory_features", "latency_anomaly", "INTEGER NOT NULL DEFAULT 0"),
    ("trajectory_features", "llm_fallback_used", "INTEGER NOT NULL DEFAULT 0"),
    ("trajectory_features", "template_used", "INTEGER NOT NULL DEFAULT 0"),
    ("trajectory_features", "diff_size", "INTEGER NOT NULL DEFAULT 0"),
    # Prediction log extras
    ("prediction_log", "risk_action", "TEXT NOT NULL DEFAULT 'continue'"),
    ("prediction_log", "feature_snapshot_json", "TEXT NOT NULL DEFAULT '{}'"),
    ("prediction_log", "executed_action", "TEXT"),
    ("prediction_log", "execution_status", "TEXT NOT NULL DEFAULT 'recommended'"),
    ("prediction_log", "execution_outcome_json", "TEXT"),
]

# The six distinct capabilities
ALL_CAPABILITIES = ("planning", "coding", "debugging", "recovery", "reliability", "efficiency")


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class FeatureAnalyticsService:
    """Persists and computes evidence-grounded capability profiles."""

    # ------------------------------------------------------------------
    # Init & DB
    # ------------------------------------------------------------------

    def __init__(self):
        self.db_path = getattr(db_service, "db_path", None)
        if not self.db_path:
            raise RuntimeError("Could not locate AgentEval-X SQLite database path")
        self._apply_migrations()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _ensure_column(
        self, conn: sqlite3.Connection, table: str, column: str, col_type: str
    ) -> None:
        """Idempotently add a column to an existing table."""
        try:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
        except sqlite3.OperationalError as exc:
            if "duplicate column name" in str(exc).lower():
                pass  # Already exists — expected
            else:
                logger.warning("Failed to add column %s.%s: %s", table, column, exc)

    def _make_feature_event_risk_nullable(self, conn: sqlite3.Connection) -> None:
        """Allow legacy feature-event rows to represent unavailable predictions."""
        columns = conn.execute("PRAGMA table_info(feature_events)").fetchall()
        risk_column = next((column for column in columns if column["name"] == "risk_score"), None)
        if not risk_column or not risk_column["notnull"]:
            return

        preserved_sql = conn.execute(
            """SELECT sql FROM sqlite_master
               WHERE tbl_name='feature_events' AND type IN ('index', 'trigger')
                 AND sql IS NOT NULL"""
        ).fetchall()
        conn.execute(
            """CREATE TABLE feature_events_nullable_migration (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                model_name TEXT NOT NULL,
                stage TEXT NOT NULL,
                event_type TEXT NOT NULL,
                success INTEGER NOT NULL,
                details_json TEXT NOT NULL DEFAULT '{}',
                elapsed_seconds REAL NOT NULL DEFAULT 0,
                risk_score REAL,
                risk_reasons_json TEXT,
                provenance TEXT DEFAULT 'llm',
                created_at TEXT NOT NULL
            )"""
        )
        target_columns = {
            "id", "run_id", "model_name", "stage", "event_type", "success",
            "details_json", "elapsed_seconds", "risk_score", "risk_reasons_json",
            "provenance", "created_at",
        }
        copied_columns = [column["name"] for column in columns if column["name"] in target_columns]
        column_list = ", ".join(copied_columns)
        conn.execute(
            f"""INSERT INTO feature_events_nullable_migration ({column_list})
                SELECT {column_list} FROM feature_events"""
        )
        conn.execute("DROP TABLE feature_events")
        conn.execute(
            "ALTER TABLE feature_events_nullable_migration RENAME TO feature_events"
        )
        for statement in preserved_sql:
            conn.execute(statement["sql"])

    def _apply_migrations(self) -> None:
        with self._connect() as conn:
            for ddl in _MIGRATIONS:
                try:
                    conn.execute(ddl)
                except sqlite3.OperationalError as exc:
                    # Table already exists — expected
                    if "already exists" in str(exc).lower():
                        pass
                    else:
                        logger.error("Migration failed: %s — DDL: %s", exc, ddl[:80])
                        raise

            # Idempotent column additions
            for table, column, col_type in _ENSURE_COLUMNS:
                self._ensure_column(conn, table, column, col_type)

            self._make_feature_event_risk_nullable(conn)

            # Mark corrupted historical records as invalid
            try:
                conn.execute(
                    "UPDATE capability_observations SET is_valid = 0 "
                    "WHERE model_name IN ('none', '', 'unknown', 'null', 'n/a', 'undefined')"
                )
            except sqlite3.OperationalError:
                pass  # is_valid column may not have been added if table doesn't exist yet

            conn.commit()


    # ------------------------------------------------------------------
    # Public API: record a pipeline stage event
    # ------------------------------------------------------------------

    def record_stage(
        self,
        run_id: str,
        stage: str,
        success: bool,
        model_name: str = "qwen2.5-coder:7b",
        event_type: str = "stage_observed",
        details: dict[str, Any] | None = None,
        elapsed_seconds: float = 0.0,
        task_verified_success: Optional[bool] = None,
        provenance: str = "llm",
        task_type: Optional[str] = None,
        difficulty: Optional[str] = None,
    ) -> dict[str, Any]:
        """Record one pipeline stage observation.

        ``task_verified_success`` should only be passed for the final
        'completed' stage event, where independent verification has
        produced a verdict. This is the ONLY observation counted toward
        binary capability posteriors per run.
        """
        # Soft-validate model_name: warn but don't crash pipeline
        try:
            model_name = validate_model_name(model_name)
        except ValueError:
            logger.warning("record_stage called with invalid model_name '%s'; using 'unknown_model'", model_name)
            model_name = "unknown_model"

        state: FeatureState = {
            "run_id": run_id,
            "model_name": model_name,
            "stage": stage,
            "success": bool(success),
            "event_type": event_type,
            "details": details or {},
            "elapsed_seconds": max(0.0, float(elapsed_seconds)),
            "task_verified_success": task_verified_success,
            "provenance": provenance,
            "task_type": task_type or (details or {}).get("task_type"),
            "difficulty": difficulty or (details or {}).get("difficulty"),
        }
        state = self._observe_node(state)
        state = self._predict_node(state)
        state = self._profile_node(state)
        return state

    def get_policy_capability(self, model_name: str, capability: str) -> tuple[float, int]:
        """Return a Beta posterior mean and observed sample size for policy decisions."""
        with self._connect() as conn:
            row = conn.execute(
                """SELECT COALESCE(SUM(successes), 0) AS successes,
                          COALESCE(SUM(failures), 0) AS failures
                   FROM capability_observations
                   WHERE model_name=? AND capability=? AND is_valid=1
                     AND (provenance IS NULL OR provenance='llm')""",
                (model_name, capability),
            ).fetchone()
        successes = int(row["successes"])
        failures = int(row["failures"])
        return (
            (successes + 1.0) / (successes + failures + 2.0),
            successes + failures,
        )

    def record_policy_execution(
        self,
        run_id: str,
        step_index: int,
        executed_action: str,
        status: str,
        outcome: dict[str, Any],
    ) -> None:
        """Persist execution separately from the action recommended by prediction."""
        with self._connect() as conn:
            cursor = conn.execute(
                """UPDATE prediction_log
                   SET executed_action=?, execution_status=?,
                       execution_outcome_json=?,
                       intervention_triggered=CASE WHEN ?='executed'
                                                        AND ? NOT IN ('continue', 'none') THEN 1
                                                   ELSE intervention_triggered END
                   WHERE run_id=? AND step_index=?""",
                (
                    executed_action,
                    status,
                    json.dumps(outcome, default=str),
                    status,
                    executed_action,
                    run_id,
                    step_index,
                ),
            )
            if cursor.rowcount != 1:
                raise LookupError(
                    f"Policy prediction not found for run {run_id}, step {step_index}"
                )

    def create_policy_approval(self, run_id: str, step_index: int) -> dict[str, Any]:
        approval = {
            "approval_id": f"approval_{uuid.uuid4().hex}",
            "run_id": run_id,
            "step_index": step_index,
            "status": "pending",
            "comment": None,
            "created_at": _now(),
            "resolved_at": None,
        }
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO policy_approvals
                   (approval_id, run_id, step_index, status, created_at)
                   VALUES (?, ?, ?, 'pending', ?)""",
                (
                    approval["approval_id"],
                    run_id,
                    step_index,
                    approval["created_at"],
                ),
            )
        return approval

    def get_pending_policy_approval(self, run_id: str) -> Optional[dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                """SELECT approval_id, run_id, step_index, status, comment,
                          created_at, resolved_at
                   FROM policy_approvals
                   WHERE run_id=? AND status='pending'
                   ORDER BY created_at DESC LIMIT 1""",
                (run_id,),
            ).fetchone()
        return dict(row) if row else None

    def get_policy_approval(self, run_id: str, approval_id: str) -> Optional[dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                """SELECT approval_id, run_id, step_index, status, comment,
                          created_at, resolved_at
                   FROM policy_approvals WHERE run_id=? AND approval_id=?""",
                (run_id, approval_id),
            ).fetchone()
        return dict(row) if row else None

    def count_resolved_policy_approvals(self, run_id: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                """SELECT COUNT(*) FROM policy_approvals
                   WHERE run_id=? AND status IN ('approved', 'rejected')""",
                (run_id,),
            ).fetchone()
        return int(row[0])

    def resolve_policy_approval(
        self, run_id: str, approval_id: str, approved: bool, comment: Optional[str]
    ) -> Optional[dict[str, Any]]:
        status = "approved" if approved else "rejected"
        resolved_at = _now()
        with self._connect() as conn:
            cursor = conn.execute(
                """UPDATE policy_approvals SET status=?, comment=?, resolved_at=?
                   WHERE run_id=? AND approval_id=? AND status='pending'""",
                (status, comment, resolved_at, run_id, approval_id),
            )
            if cursor.rowcount != 1:
                return None
            row = conn.execute(
                """SELECT approval_id, run_id, step_index, status, comment,
                          created_at, resolved_at
                   FROM policy_approvals WHERE approval_id=? AND run_id=?""",
                (approval_id, run_id),
            ).fetchone()
        return dict(row) if row else None

    # ------------------------------------------------------------------
    # Observe node: persist the stage event
    # ------------------------------------------------------------------

    def _observe_node(self, state: FeatureState) -> FeatureState:
        run_id = state["run_id"]
        stage = state.get("stage", "unknown")
        details = state.get("details", {})
        provenance = state.get("provenance", "llm")

        with self._connect() as conn:
            # Count current step index for this run
            step_idx = conn.execute(
                "SELECT COUNT(*) FROM feature_events WHERE run_id=?", (run_id,)
            ).fetchone()[0]

            # Store in legacy feature_events for compatibility
            conn.execute(
                """INSERT INTO feature_events
                (run_id, model_name, stage, event_type, success, details_json,
                 elapsed_seconds, provenance, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    run_id,
                    state.get("model_name", "unknown"),
                    stage,
                    state.get("event_type", "observed"),
                    int(state.get("success", False)),
                    json.dumps(details, default=str),
                    float(state.get("elapsed_seconds", 0.0)),
                    provenance,
                    _now(),
                ),
            )

            # Extract pre-test features from details and event history
            pre_test = self._extract_pre_test_features(conn, run_id, details, step_idx)

            # Trajectory feature snapshot (used for failure prediction)
            cumulative = self._compute_cumulative_trajectory_features(
                conn, run_id, details, step_idx
            )

            try:
                conn.execute(
                    """INSERT INTO trajectory_features
                    (run_id, step_index, step_timestamp, stage, event_type,
                     cumulative_errors, cumulative_test_failures, repeated_messages,
                     steps_without_progress, constraint_violations, elapsed_seconds,
                     ast_errors, json_parse_errors, plan_discrepancy, retry_count,
                     tool_failures, latency_anomaly, llm_fallback_used, template_used,
                     diff_size, label_task_failed, created_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(run_id, step_index) DO NOTHING""",
                    (
                        run_id,
                        step_idx,
                        _now(),
                        stage,
                        state.get("event_type", "observed"),
                        cumulative["cumulative_errors"],
                        cumulative["cumulative_test_failures"],
                        cumulative["repeated_messages"],
                        cumulative.get("steps_without_progress", 0),
                        cumulative.get("constraint_violations", 0),
                        float(state.get("elapsed_seconds", 0.0)),
                        pre_test["ast_errors"],
                        pre_test["json_parse_errors"],
                        pre_test["plan_discrepancy"],
                        pre_test["retry_count"],
                        pre_test["tool_failures"],
                        pre_test["latency_anomaly"],
                        pre_test["llm_fallback_used"],
                        pre_test["template_used"],
                        pre_test["diff_size"],
                        None,  # label filled at run completion
                        _now(),
                    ),
                )
            except sqlite3.OperationalError:
                # Fallback if pre-test columns don't exist yet (old schema)
                conn.execute(
                    """INSERT INTO trajectory_features
                    (run_id, step_index, step_timestamp, stage, event_type,
                     cumulative_errors, cumulative_test_failures, repeated_messages,
                     steps_without_progress, constraint_violations, elapsed_seconds,
                     label_task_failed, created_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(run_id, step_index) DO NOTHING""",
                    (
                        run_id,
                        step_idx,
                        _now(),
                        stage,
                        state.get("event_type", "observed"),
                        cumulative["cumulative_errors"],
                        cumulative["cumulative_test_failures"],
                        cumulative["repeated_messages"],
                        cumulative.get("steps_without_progress", 0),
                        cumulative.get("constraint_violations", 0),
                        float(state.get("elapsed_seconds", 0.0)),
                        None,
                        _now(),
                    ),
                )
            conn.commit()

        return {**state, "_step_index": step_idx}

    def _extract_pre_test_features(
        self,
        conn: sqlite3.Connection,
        run_id: str,
        current_details: dict,
        current_step: int,
    ) -> dict:
        """Extract strictly pre-test features from current event details and history."""
        ast_errors = int(current_details.get("ast_errors", 0) or 0)
        json_parse_errors = int(current_details.get("json_parse_errors", 0) or 0)
        plan_discrepancy = int(current_details.get("plan_discrepancy", 0) or 0)
        retry_count = int(current_details.get("retry_count", 0) or current_details.get("attempt_number", 0) or 0)
        tool_failures = int(current_details.get("tool_failures", 0) or 0)
        diff_size = int(current_details.get("diff_size", 0) or current_details.get("changes_count", 0) or 0)

        # Latency anomaly: flag if elapsed is > 3x the running average
        elapsed = float(current_details.get("elapsed_seconds", 0) or 0)
        latency_anomaly = 0
        if elapsed > 0 and current_step > 0:
            try:
                avg_row = conn.execute(
                    "SELECT AVG(elapsed_seconds) FROM feature_events WHERE run_id=?",
                    (run_id,),
                ).fetchone()
                avg_elapsed = float(avg_row[0] or 0) if avg_row else 0
                if avg_elapsed > 0 and elapsed > 3 * avg_elapsed:
                    latency_anomaly = 1
            except Exception:
                pass

        # LLM fallback / template usage from provenance
        llm_fallback_used = int(current_details.get("llm_fallback_used", 0) or 0)
        template_used = int(current_details.get("template_used", 0) or 0)

        # Accumulate from history
        try:
            hist_rows = conn.execute(
                "SELECT details_json FROM feature_events WHERE run_id=? ORDER BY id",
                (run_id,),
            ).fetchall()
            for r in hist_rows:
                try:
                    d = json.loads(r["details_json"] or "{}")
                except json.JSONDecodeError:
                    continue
                ast_errors += int(d.get("ast_errors", 0) or 0)
                json_parse_errors += int(d.get("json_parse_errors", 0) or 0)
                tool_failures += int(d.get("tool_failures", 0) or 0)
        except Exception:
            pass

        return {
            "ast_errors": ast_errors,
            "json_parse_errors": json_parse_errors,
            "plan_discrepancy": plan_discrepancy,
            "retry_count": retry_count,
            "tool_failures": tool_failures,
            "latency_anomaly": latency_anomaly,
            "llm_fallback_used": llm_fallback_used,
            "template_used": template_used,
            "diff_size": diff_size,
        }

    def _compute_cumulative_trajectory_features(
        self,
        conn: sqlite3.Connection,
        run_id: str,
        current_details: dict,
        current_step: int,
    ) -> dict:
        rows = conn.execute(
            """SELECT event_type, success, details_json
               FROM feature_events WHERE run_id=? ORDER BY id""",
            (run_id,),
        ).fetchall()

        cum_errors = sum(
            1 for r in rows
            if r["event_type"].lower() in {"error", "test_failed", "tool_error", "failure"}
            or not bool(r["success"])
        )
        cum_test_failures = sum(
            int(json.loads(r["details_json"] or "{}").get("failed_tests", 0))
            for r in rows
        )

        messages = []
        for r in rows:
            try:
                payload = json.loads(r["details_json"] or "{}")
            except json.JSONDecodeError:
                payload = {}
            msg = str(payload.get("message") or payload.get("error") or "")
            if msg:
                messages.append(msg.strip().lower())
        repeated = len(messages) - len(set(messages))

        no_progress = int(current_details.get("steps_without_progress", 0) or 0)
        violations = int(current_details.get("constraint_violations", 0) or 0)

        return {
            "cumulative_errors": cum_errors,
            "cumulative_test_failures": cum_test_failures,
            "repeated_messages": repeated,
            "steps_without_progress": no_progress,
            "constraint_violations": violations,
        }

    # ------------------------------------------------------------------
    # Predict node: report that no validated prediction model is deployed.
    # ------------------------------------------------------------------

    def _predict_node(self, state: FeatureState) -> FeatureState:
        run_id = state["run_id"]
        step_idx = state.get("_step_index", 0)
        reasons: list[str] = []
        action = "continue"
        model_version = "unavailable_no_validated_model"
        feature_snapshot = {
            "status": "unavailable",
            "reason": "No validated live prediction model is deployed.",
        }

        with self._connect() as conn:
            conn.execute(
                """UPDATE feature_events SET risk_score=?, risk_reasons_json=?
                   WHERE id=(SELECT MAX(id) FROM feature_events WHERE run_id=?)""",
                (None, json.dumps(reasons), run_id),
            )
            # Log prediction with SAME step_index as observe node
            try:
                conn.execute(
                    """INSERT INTO prediction_log
                       (run_id, step_index, risk_score, risk_reasons_json,
                        risk_action, feature_snapshot_json,
                        model_version, intervention_triggered, created_at)
                       VALUES (?,?,?,?,?,?,?,?,?)""",
                    (
                        run_id,
                        step_idx,
                        0.0,
                        json.dumps(reasons),
                        action,
                        json.dumps(feature_snapshot),
                        model_version,
                        0,   # execution is recorded by the orchestrator after handling
                        _now(),
                    ),
                )
            except sqlite3.OperationalError:
                # Fallback for old schema without risk_action/feature_snapshot
                conn.execute(
                    """INSERT INTO prediction_log
                       (run_id, step_index, risk_score, risk_reasons_json,
                        model_version, intervention_triggered, created_at)
                       VALUES (?,?,?,?,?,?,?)""",
                    (
                        run_id,
                        step_idx,
                        0.0,
                        json.dumps(reasons),
                        model_version,
                        0,
                        _now(),
                    ),
                )
            conn.commit()

        return {**state, "risk_score": None, "risk_reasons": reasons,
                "risk_action": action, "risk_model_version": model_version}

    # ------------------------------------------------------------------
    # Profile node: update capability profiles
    # ------------------------------------------------------------------

    def _profile_node(self, state: FeatureState) -> FeatureState:
        """Update binary capability profiles with task-level verified evidence.

        Binary posteriors are updated ONLY when task_verified_success is
        explicitly set (i.e. at the 'completed' stage with verifier output).
        Task duration is sourced from timestamp-verified evaluations.

        Records SEPARATE capabilities:
        - planning: from planner stage success
        - coding: from test pass rates
        - debugging: from debugger recovery stage
        - recovery: from recovery episodes (handled separately)
        - reliability: from overall verified success
        """
        task_verified_success = state.get("task_verified_success")
        model = state.get("model_name", "unknown")
        run_id = state["run_id"]
        stage = state.get("stage", "unknown")
        provenance = state.get("provenance", "llm")

        # Exclude template/fallback/mock from model capability observations
        is_genuine_llm = provenance in ("llm",)

        with self._connect() as conn:
            # Record stage-level capability observations (non-binary tracking)
            if stage == "planner" and is_genuine_llm:
                obs_id_plan = f"{run_id}::planning"
                plan_success = state.get("success", False)
                self._upsert_observation(
                    conn, obs_id_plan, model, "planning", run_id,
                    1 if plan_success else 0, 0 if plan_success else 1,
                    {"stage": stage, "provenance": provenance},
                    provenance=provenance,
                    task_type=state.get("task_type"),
                    difficulty=state.get("difficulty"),
                )

            if stage == "debugger" and is_genuine_llm:
                obs_id_debug = f"{run_id}::debugging"
                debug_success = state.get("success", False)
                self._upsert_observation(
                    conn, obs_id_debug, model, "debugging", run_id,
                    1 if debug_success else 0, 0 if debug_success else 1,
                    {"stage": stage, "resolved": state.get("details", {}).get("resolved")},
                    provenance=provenance,
                    task_type=state.get("task_type"),
                    difficulty=state.get("difficulty"),
                )

            # Only record binary capability observations at run completion
            if stage == "completed" and task_verified_success is not None:
                success_int = 1 if task_verified_success else 0
                failure_int = 0 if task_verified_success else 1

                # Reliability: independently verified task success
                if is_genuine_llm:
                    obs_id_rel = f"{run_id}::reliability"
                    self._upsert_observation(
                        conn, obs_id_rel, model, "reliability", run_id,
                        success_int, failure_int,
                        {"verified": task_verified_success, "stage": stage},
                        provenance=provenance,
                        task_type=state.get("task_type"),
                        difficulty=state.get("difficulty"),
                    )

                # Coding: count completed test suites by whether all tests passed.
                details = state.get("details", {})
                passed_tests = int(details.get("passed_tests", 0) or 0)
                total_tests = int(details.get("tests_total", 0) or 0)
                if total_tests > 0 and is_genuine_llm:
                    coding_success = passed_tests == total_tests
                    obs_id_cod = f"{run_id}::coding"
                    self._upsert_observation(
                        conn, obs_id_cod, model, "coding", run_id,
                        1 if coding_success else 0,
                        0 if coding_success else 1,
                        {
                            "tests_passed": passed_tests,
                            "tests_total": total_tests,
                            "test_pass_rate": round(passed_tests / total_tests, 4),
                            "all_tests_passed": coding_success,
                        },
                        provenance=provenance,
                        task_type=state.get("task_type"),
                        difficulty=state.get("difficulty"),
                    )

            conn.commit()

        return state
    def _upsert_observation(
        self,
        conn: sqlite3.Connection,
        obs_id: str,
        model_name: str,
        capability: str,
        run_id: str,
        successes: int,
        failures: int,
        evidence: dict,
        provenance: str = "llm",
        task_type: Optional[str] = None,
        difficulty: Optional[str] = None,
    ) -> None:
        """Insert a task-level observation, ignoring duplicates (by obs_id)."""
        try:
            try:
                conn.execute(
                    """INSERT INTO capability_observations
                       (obs_id, model_name, capability, run_id,
                        successes, failures, evidence_json, provenance,
                        task_type, difficulty, created_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    (obs_id, model_name, capability, run_id,
                     successes, failures, json.dumps(evidence),
                     provenance, task_type, difficulty, _now()),
                )
            except sqlite3.OperationalError:
                # Fallback for old schema without provenance/task_type/difficulty
                conn.execute(
                    """INSERT INTO capability_observations
                       (obs_id, model_name, capability, run_id,
                        successes, failures, evidence_json, created_at)
                       VALUES (?,?,?,?,?,?,?,?)""",
                    (obs_id, model_name, capability, run_id,
                     successes, failures, json.dumps(evidence), _now()),
                )

            # Update aggregate profile
            conn.execute(
                """INSERT INTO capability_profiles_v2
                   (model_name, capability, total_successes, total_failures,
                    duration_values_json, extra_json, updated_at)
                   VALUES (?,?,?,?,?,?,?)
                   ON CONFLICT(model_name, capability) DO UPDATE SET
                     total_successes = total_successes + excluded.total_successes,
                     total_failures  = total_failures  + excluded.total_failures,
                     updated_at      = excluded.updated_at""",
                (model_name, capability, successes, failures,
                 json.dumps([]), json.dumps({}), _now()),
            )
        except sqlite3.IntegrityError:
            # obs_id already exists → already counted, skip
            pass

    # ------------------------------------------------------------------
    # Recovery episode management
    # ------------------------------------------------------------------

    def record_recovery_episode(
        self,
        episode_id: str,
        run_id: str,
        model_name: str,
        failure_type: str,
        original_error: str,
        failure_timestamp: str,
        recovery_start_timestamp: Optional[str] = None,
        recovery_end_timestamp: Optional[str] = None,
        recovery_actions: Optional[list[dict]] = None,
        extra_test_executions: int = 0,
        original_failure_resolved: bool = False,
        regression_tests_passed: Optional[bool] = None,
        final_verified_outcome: Optional[str] = None,
        human_intervention: bool = False,
        recovery_duration_seconds: Optional[float] = None,
        extra_steps: Optional[int] = None,
        attempts_count: int = 1,
        cost_units: float = 0.0,
    ) -> dict:
        """Record a structured recovery episode.

        A recovery is only marked successful when ``original_failure_resolved``
        is True AND ``regression_tests_passed`` is True (or None = not run).
        Never infer success from debugging stage completion alone.
        """
        if recovery_duration_seconds is None:
            if recovery_start_timestamp and recovery_end_timestamp:
                try:
                    t0 = datetime.fromisoformat(recovery_start_timestamp)
                    t1 = datetime.fromisoformat(recovery_end_timestamp)
                    recovery_duration_seconds = round((t1 - t0).total_seconds(), 3)
                except ValueError:
                    pass

        if extra_steps is None:
            extra_steps = extra_test_executions + len(recovery_actions or [])

        with self._connect() as conn:
            try:
                conn.execute(
                    """INSERT INTO recovery_episodes
                       (episode_id, run_id, model_name, failure_type, original_error,
                        failure_timestamp, recovery_start_timestamp, recovery_end_timestamp,
                        recovery_actions_json, extra_test_executions,
                        original_failure_resolved, regression_tests_passed,
                        final_verified_outcome, human_intervention,
                        recovery_duration_seconds, extra_steps, created_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        episode_id, run_id, model_name, failure_type, original_error,
                        failure_timestamp,
                        recovery_start_timestamp, recovery_end_timestamp,
                        json.dumps(recovery_actions or []),
                        extra_test_executions,
                        1 if original_failure_resolved else 0,
                        None if regression_tests_passed is None else (1 if regression_tests_passed else 0),
                        final_verified_outcome or "NOT_VERIFIED",
                        1 if human_intervention else 0,
                        recovery_duration_seconds,
                        extra_steps,
                        _now(),
                    ),
                )
                conn.commit()
            except sqlite3.IntegrityError:
                # Duplicate episode_id — update in place
                conn.execute(
                    """UPDATE recovery_episodes SET
                       original_failure_resolved=?, regression_tests_passed=?,
                       final_verified_outcome=?, recovery_end_timestamp=?,
                       recovery_duration_seconds=?, extra_steps=?
                       WHERE episode_id=?""",
                    (
                        1 if original_failure_resolved else 0,
                        None if regression_tests_passed is None else (1 if regression_tests_passed else 0),
                        final_verified_outcome or "NOT_VERIFIED",
                        recovery_end_timestamp,
                        recovery_duration_seconds,
                        extra_steps,
                        episode_id,
                    ),
                )
                conn.commit()

        # Update recovery capability profile after episode
        self._update_recovery_capability(model_name)

        return {"episode_id": episode_id, "run_id": run_id,
                "recovery_duration_seconds": recovery_duration_seconds,
                "extra_steps": extra_steps}

    def _update_recovery_capability(self, model_name: str) -> None:
        """Recompute recovery capability aggregates from all episodes."""
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT episode_id, run_id, original_failure_resolved,
                          regression_tests_passed, final_verified_outcome
                   FROM recovery_episodes
                   WHERE model_name=?""",
                (model_name,),
            ).fetchall()

        if not rows:
            return

        # Only explicit passing tests and a final PASSED verdict count as success.
        eligible = [
            r for r in rows
            if r["original_failure_resolved"] is not None
        ]
        successes = sum(
            1 for r in eligible
            if bool(r["original_failure_resolved"])
            and r["regression_tests_passed"] == 1
            and str(r["final_verified_outcome"] or "").upper() == "PASSED"
        )
        failures = len(eligible) - successes

        # Dedup by episode_id before aggregating
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO capability_profiles_v2
                   (model_name, capability, total_successes, total_failures,
                    duration_values_json, extra_json, updated_at)
                   VALUES (?,?,?,?,?,?,?)
                   ON CONFLICT(model_name, capability) DO UPDATE SET
                     total_successes = ?,
                     total_failures  = ?,
                     updated_at      = ?""",
                (model_name, "recovery", successes, failures,
                 json.dumps([]), json.dumps({}), _now(),
                 successes, failures, _now()),
            )
            conn.commit()

    # ------------------------------------------------------------------
    # Update trajectory labels at run completion
    # ------------------------------------------------------------------

    def finalize_run_labels(self, run_id: str, task_failed: bool) -> None:
        """Set task-failure label on all trajectory steps for a run.

        Called once at pipeline completion so that supervised predictors can
        use the data. Only sets the label; does not alter features.
        """
        with self._connect() as conn:
            conn.execute(
                "UPDATE trajectory_features SET label_task_failed=? WHERE run_id=?",
                (1 if task_failed else 0, run_id),
            )
            conn.execute(
                "UPDATE prediction_log SET final_outcome=? WHERE run_id=?",
                ("FAILED" if task_failed else "PASSED", run_id),
            )
            conn.commit()

    # ------------------------------------------------------------------
    # Read: evidence-backed capability profiles
    # ------------------------------------------------------------------

    def get_capability_profiles(
        self,
        model_name: Optional[str] = None,
        task_type: Optional[str] = None,
        difficulty: Optional[str] = None,
        run_id: Optional[str] = None,
        half_life_days: float = 14.0,
    ) -> dict:
        """Return directly observed capability outcomes.

        Each binary capability includes:
        - observed_rate      (raw successes / observed outcomes)
        - sample_size
        - evidence_status

        Efficiency returns a ContinuousSummary (descriptive stats only).
        No capability returns a single aggregated 0–100 score.
        """
        run_duration: Optional[float] = None
        with self._connect() as conn:
            # Get raw observations for recency weighting
            obs_query = "SELECT * FROM capability_observations WHERE is_valid = 1"
            params: list[Any] = []
            if model_name:
                obs_query += " AND model_name=?"
                params.append(model_name)
            if run_id:
                obs_query += " AND run_id=?"
                params.append(run_id)
            # Filter out template/fallback/mock from model profiles
            obs_query += " AND (provenance IS NULL OR provenance = 'llm')"
            if task_type:
                obs_query += " AND task_type=?"
                params.append(task_type)
            if difficulty:
                obs_query += " AND difficulty=?"
                params.append(difficulty)

            try:
                obs_rows = conn.execute(obs_query, params).fetchall()
            except sqlite3.OperationalError:
                # is_valid or provenance column may not exist
                fallback_query = "SELECT * FROM capability_observations"
                if model_name:
                    fallback_query += " WHERE model_name=?"
                    obs_rows = conn.execute(fallback_query, [model_name] if model_name else []).fetchall()
                else:
                    obs_rows = conn.execute(fallback_query).fetchall()

            # Fetch profile rows for efficiency/duration data
            if run_id:
                # A selected run must never inherit all-history aggregate counters.
                profile_rows = []
                run_duration = db_service.get_verified_execution_duration(conn, run_id)
            elif model_name:
                profile_rows = conn.execute(
                    "SELECT * FROM capability_profiles_v2 WHERE model_name=? ORDER BY capability",
                    (model_name,),
                ).fetchall()
            else:
                profile_rows = conn.execute(
                    "SELECT * FROM capability_profiles_v2 ORDER BY model_name, capability"
                ).fetchall()

        # Group observations by (model_name, capability)
        obs_groups: dict[tuple[str, str], list[dict]] = {}
        for r in obs_rows:
            observation = dict(r)
            try:
                validate_model_name(observation.get("model_name"))
            except ValueError:
                continue
            if not observation.get("is_valid", 1):
                continue
            if observation.get("provenance") not in (None, "llm"):
                continue
            key = (observation["model_name"], observation["capability"])
            if key[1] == "coding":
                evidence = json.loads(observation.get("evidence_json") or "{}")
                passed_tests = int(evidence.get("tests_passed", 0) or 0)
                total_tests = int(evidence.get("tests_total", 0) or 0)
                if total_tests > 0:
                    # Reinterpret older observations using their saved test evidence;
                    # older releases incorrectly copied the verifier outcome here.
                    coding_success = passed_tests == total_tests
                    observation["successes"] = 1 if coding_success else 0
                    observation["failures"] = 0 if coding_success else 1
            obs_groups.setdefault(key, []).append(observation)

        # Aggregate rows without eligible observations may contain stale
        # counters. Only use aggregate rows backed by valid observations.
        profile_lookup: dict[tuple[str, str], dict] = {}
        for r in profile_rows:
            key = (r["model_name"], r["capability"])
            if r["capability"] != "efficiency" and key in obs_groups:
                profile_lookup[key] = dict(r)

        # Collect all (model, capability) pairs
        all_keys = set(obs_groups.keys()) | set(profile_lookup.keys())

        if run_id and run_duration is not None:
            for model, _cap in obs_groups:
                all_keys.add((model, "efficiency"))

        profiles = []
        for model, cap in sorted(all_keys):
            prof = profile_lookup.get((model, cap), {})
            dur_vals = json.loads(prof.get("duration_values_json", "[]") or "[]")
            if cap == "efficiency":
                # Continuous measurement — no Bayesian posterior
                if run_id:
                    values = [run_duration] if run_duration is not None else []
                else:
                    values = dur_vals
                summary = ContinuousSummary(
                    measurement="task_duration",
                    unit="seconds",
                    values=values,
                )
                profiles.append({
                    "model_name": model,
                    "capability": cap,
                    "measurement_type": "continuous",
                    **summary.to_dict(),
                    "note": "Duration measured per run. Lower is generally better within same hardware/model config.",
                    "updated_at": prof.get("updated_at", ""),
                })
            else:
                obs_list = obs_groups.get((model, cap), [])
                successes = sum(int(o.get("successes", 0) or 0) for o in obs_list)
                failures = sum(int(o.get("failures", 0) or 0) for o in obs_list)
                sample_size = successes + failures
                profiles.append({
                    "model_name": model,
                    "capability": cap,
                    "measurement_type": "binary",
                    "successes": successes,
                    "failures": failures,
                    "sample_size": sample_size,
                    "observed_rate": successes / sample_size if sample_size else None,
                    "evidence_status": "measured" if sample_size else "insufficient_evidence",
                    "updated_at": prof.get("updated_at", ""),
                    "note": "Directly observed outcome counts; no prior-adjusted estimate.",
                })

        if not task_type and not difficulty:
            agent_metrics = {
                "orchestrator": ("workflow_completion_rate", "System Orchestrator", "Workflow Completion Rate"),
                "requirement_analyst": ("goal_extraction_success_rate", "Requirement Analyst Agent", "Structured Goal Output Rate"),
                "planner": ("plan_feasibility_rate", "Codebase Analyst & Planner Agent", "Plan Feasibility Rate"),
                "coder": ("ast_validity_rate", "Coding Agent", "AST Syntax Validity Rate"),
                "test_runner": ("execution_integrity_rate", "Test Runner Agent", "Test Pass Rate"),
                "debugger": ("recovery_success_rate", "Debugging & Recovery Agent", "Recovery Success Rate"),
                "verifier": ("verification_pass_rate", "Independent Code Reviewer & Verifier Agent", "Verified Audit Rate"),
            }
            hierarchy_rows = []
            hierarchy_durations: dict[str, list[float]] = {}
            try:
                hierarchy_query = """
                    SELECT run_id, model_name, agent_id, metric_name, successes, failures,
                           details_json, continuous_value
                    FROM agent_proficiency_observations
                    WHERE is_valid = 1
                """
                hierarchy_params: list[Any] = []
                if model_name:
                    hierarchy_query += " AND model_name=?"
                    hierarchy_params.append(model_name)
                if run_id:
                    hierarchy_query += " AND run_id=?"
                    hierarchy_params.append(run_id)
                with self._connect() as conn:
                    hierarchy_rows = conn.execute(hierarchy_query, hierarchy_params).fetchall()
                    for row in hierarchy_rows:
                        if row["agent_id"] != "system" or row["metric_name"] != "e2e_duration_seconds":
                            continue
                        duration = db_service.get_verified_execution_duration(
                            conn, row["run_id"]
                        )
                        if duration is not None:
                            hierarchy_durations.setdefault(row["model_name"], []).append(duration)
            except sqlite3.OperationalError as exc:
                if "no such table" not in str(exc).lower():
                    raise

            hierarchy_groups: dict[tuple[str, str], dict[str, Any]] = {}
            for row in hierarchy_rows:
                agent_id = row["agent_id"]
                model = row["model_name"]
                if agent_id == "system" and row["metric_name"] == "e2e_duration_seconds":
                    continue
                metric_info = agent_metrics.get(agent_id)
                if not metric_info or row["metric_name"] != metric_info[0]:
                    continue
                group = hierarchy_groups.setdefault(
                    (model, agent_id),
                    {"successes": 0, "failures": 0, "details_json": row["details_json"]},
                )
                group["successes"] += int(row["successes"] or 0)
                group["failures"] += int(row["failures"] or 0)

            hierarchy_models = {model for model, _agent in hierarchy_groups}
            for model in sorted(hierarchy_models):
                try:
                    validate_model_name(model)
                except ValueError:
                    continue
                if any(existing_model == model for existing_model, _capability in obs_groups):
                    continue

                for agent_id, (metric, display_name, metric_label) in agent_metrics.items():
                    group = hierarchy_groups.get((model, agent_id), {})
                    successes = int(group.get("successes", 0))
                    failures = int(group.get("failures", 0))
                    sample_size = successes + failures
                    try:
                        details = json.loads(group.get("details_json") or "{}")
                    except (TypeError, json.JSONDecodeError):
                        logger.warning(
                            "Invalid proficiency details for model %s agent %s",
                            model, agent_id,
                        )
                        details = {}
                    profiles.append({
                        "model_name": model,
                        "capability": agent_id,
                        "display_name": display_name,
                        "metric_label": metric_label,
                        "measurement_type": "binary",
                        "successes": successes,
                        "failures": failures,
                        "sample_size": sample_size,
                        "observed_rate": successes / sample_size if sample_size else None,
                        "evidence_status": "measured" if sample_size else "insufficient_evidence",
                        "measurement_basis": details.get("measurement_basis"),
                        "note": "Directly observed outcomes from persisted run artifacts; no prior or estimated score.",
                    })

                duration_values = hierarchy_durations.get(model, [])
                if run_id:
                    duration_values = []
                if duration_values:
                    summary = ContinuousSummary(
                        measurement="task_duration",
                        unit="seconds",
                        values=duration_values,
                    )
                    profiles.append({
                        "model_name": model,
                        "capability": "efficiency",
                        "measurement_type": "continuous",
                        **summary.to_dict(),
                        "evidence_status": "measured",
                        "note": "Recorded execution duration values from persisted runs.",
                    })

        return {
            "profiles": profiles,
            "note": (
                "Binary capabilities use directly observed outcome counts without prior-adjusted estimates. "
                "Agent fallback profiles use outcomes from persisted run artifacts; "
                "percentages are unavailable when no valid outcomes exist. "
                "Efficiency is a continuous measurement (recorded task duration). "
                "No weighted overall score is produced. "
                "Invalid and unidentified model observations are excluded."
            ),
        }

    # ------------------------------------------------------------------
    # Read: recovery summary for a run
    # ------------------------------------------------------------------

    def get_recovery_summary(self, run_id: str) -> dict:
        """Return recovery statistics derived from structured episodes."""
        with self._connect() as conn:
            episodes = conn.execute(
                """SELECT episode_id, failure_type, original_error,
                          original_failure_resolved, regression_tests_passed,
                          final_verified_outcome, recovery_duration_seconds,
                          extra_steps, human_intervention, failure_timestamp,
                          recovery_start_timestamp, recovery_end_timestamp,
                          recovery_actions_json
                   FROM recovery_episodes WHERE run_id=? ORDER BY id""",
                (run_id,),
            ).fetchall()

        if not episodes:
            legacy_attempts = []
            try:
                with self._connect() as conn:
                    legacy_attempts = conn.execute(
                        """SELECT id, attempt_number, failure_reason, resolved, created_at
                           FROM recovery_attempts WHERE run_id=?
                           ORDER BY attempt_number""",
                        (run_id,),
                    ).fetchall()
            except sqlite3.OperationalError as exc:
                if "no such table" not in str(exc).lower():
                    raise

            if legacy_attempts:
                total = len(legacy_attempts)
                resolved = sum(bool(attempt["resolved"]) for attempt in legacy_attempts)
                return {
                    "run_id": run_id,
                    "data_source": "legacy_recovery_attempts",
                    "total_episodes": total,
                    "resolved_episodes": resolved,
                    "recovery_rate": round(resolved / total, 4),
                    "recovery_rate_percent": round(100 * resolved / total, 2),
                    "mean_recovery_duration_seconds": None,
                    "total_extra_steps": None,
                    "failure_type_breakdown": {},
                    "episodes": [
                        {
                            "episode_id": attempt["id"],
                            "failure_type": "Legacy attempt",
                            "original_error_snippet": attempt["failure_reason"],
                            "recovery_duration_seconds": None,
                            "extra_steps": None,
                            "verified_success": None,
                            "final_verified_outcome": (
                                "RESOLVED" if attempt["resolved"] else "UNRESOLVED"
                            ),
                            "human_intervention": None,
                            "attempt_number": attempt["attempt_number"],
                        }
                        for attempt in legacy_attempts
                    ],
                    "evidence_status": "measured",
                    "note": (
                        "Legacy recovery attempts are shown from recorded test outcomes; "
                        "episode-level verification and duration were not stored."
                    ),
                }

            test_runs = []
            try:
                with self._connect() as conn:
                    test_runs = conn.execute(
                        """SELECT attempt_number, status, failed_tests
                           FROM test_results WHERE run_id=?
                           ORDER BY attempt_number""",
                        (run_id,),
                    ).fetchall()
            except sqlite3.OperationalError as exc:
                if "no such table" not in str(exc).lower():
                    raise

            if test_runs:
                initial_test_passed = (
                    test_runs[0]["status"] == "PASSED"
                    and int(test_runs[0]["failed_tests"] or 0) == 0
                )
                if initial_test_passed:
                    return {
                        "run_id": run_id,
                        "data_source": "test_results",
                        "total_episodes": 0,
                        "resolved_episodes": 0,
                        "recovery_rate": None,
                        "recovery_rate_percent": None,
                        "mean_recovery_duration_seconds": None,
                        "total_extra_steps": None,
                        "failure_type_breakdown": {},
                        "episodes": [],
                        "evidence_status": "no_recovery_needed",
                        "note": "Recorded tests passed on the initial run; no recovery was needed.",
                    }
                return {
                    "run_id": run_id,
                    "data_source": "test_results",
                    "total_episodes": 0,
                    "resolved_episodes": 0,
                    "recovery_rate": None,
                    "recovery_rate_percent": None,
                    "mean_recovery_duration_seconds": None,
                    "total_extra_steps": None,
                    "failure_type_breakdown": {},
                    "episodes": [],
                    "evidence_status": "insufficient_evidence",
                    "note": "Test results were recorded, but no recovery attempt was saved for this run.",
                }

            # Fall back to legacy run-level stats if available
            return self._get_legacy_recovery_stats(run_id)

        total = len(episodes)
        resolved = sum(
            1 for e in episodes
            if bool(e["original_failure_resolved"])
            and e["regression_tests_passed"] == 1
            and str(e["final_verified_outcome"] or "").upper() == "PASSED"
        )
        durations = [
            e["recovery_duration_seconds"]
            for e in episodes
            if e["recovery_duration_seconds"] is not None
        ]
        total_extra_steps = sum(e["extra_steps"] for e in episodes)

        failure_breakdown: dict[str, dict] = {}
        for e in episodes:
            ft = e["failure_type"] or "unknown"
            b = failure_breakdown.setdefault(ft, {"attempts": 0, "resolved": 0})
            b["attempts"] += 1
            if (bool(e["original_failure_resolved"])
                    and e["regression_tests_passed"] == 1
                    and str(e["final_verified_outcome"] or "").upper() == "PASSED") :
                b["resolved"] += 1

        episode_list = []
        for e in episodes:
            is_success = (
                bool(e["original_failure_resolved"])
                and e["regression_tests_passed"] == 1
                and str(e["final_verified_outcome"] or "").upper() == "PASSED"
            )
            episode_list.append({
                "episode_id": e["episode_id"],
                "failure_type": e["failure_type"],
                "original_error_snippet": (e["original_error"] or "")[:200],
                "recovery_duration_seconds": e["recovery_duration_seconds"],
                "extra_steps": e["extra_steps"],
                "verified_success": is_success,
                "final_verified_outcome": e["final_verified_outcome"],
                "human_intervention": bool(e["human_intervention"]),
            })

        return {
            "run_id": run_id,
            "data_source": "recovery_episodes",
            "total_episodes": total,
            "resolved_episodes": resolved,
            "recovery_rate": round(resolved / total, 4) if total else None,
            "recovery_rate_percent": round(100 * resolved / total, 2) if total else None,
            "mean_recovery_duration_seconds": round(sum(durations) / len(durations), 3) if durations else None,
            "total_extra_steps": total_extra_steps,
            "failure_type_breakdown": failure_breakdown,
            "episodes": episode_list,
            "unverified_episodes": sum(1 for e in episodes if e["regression_tests_passed"] is None or str(e["final_verified_outcome"] or "").upper() not in {"PASSED", "FAILED"}),
            "evidence_status": "measured" if total > 0 else "insufficient_evidence",
        }

    def _get_legacy_recovery_stats(self, run_id: str) -> dict:
        row = None
        try:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT stats_json FROM recovery_run_stats WHERE run_id=?",
                    (run_id,),
                ).fetchone()
        except sqlite3.OperationalError:
            row = None
        if not row:
            return {"run_id": run_id, "data_source": "none",
                    "evidence_status": "insufficient_evidence",
                    "note": "No recovery data recorded for this run."}
        stats = json.loads(row["stats_json"])
        stats["data_source"] = "legacy_recovery_run_stats"
        attempts = int(stats.get("recovery_attempts", 0) or 0)
        stats.update({
            "total_episodes": attempts,
            "resolved_episodes": int(stats.get("resolved_recoveries", 0) or 0),
            "mean_recovery_duration_seconds": stats.get("recovery_time_seconds"),
            "total_extra_steps": int(stats.get("extra_steps", 0) or 0),
            "episodes": [],
            "evidence_status": "measured" if attempts else "no_recovery_needed",
            "note": (
                "Legacy run-level recovery data; individual episode details are unavailable."
                if attempts else "No test failures triggered recovery for this run."
            ),
        })
        if stats.get("recovery_rate_percent") is None and attempts:
            stats["recovery_rate_percent"] = round(
                100 * stats["resolved_episodes"] / attempts, 2
            )
        if not attempts:
            stats["recovery_rate_percent"] = None
        return stats

    # ------------------------------------------------------------------
    # Read: run analytics (failure prediction + events)
    # ------------------------------------------------------------------

    def get_run_analytics(self, run_id: str) -> dict:
        with self._connect() as conn:
            events = conn.execute(
                """SELECT stage, event_type, success, details_json,
                          elapsed_seconds, risk_score, risk_reasons_json, created_at
                   FROM feature_events WHERE run_id=? ORDER BY id""",
                (run_id,),
            ).fetchall()
            preds = conn.execute(
                """SELECT step_index, risk_score, risk_reasons_json,
                          risk_action, executed_action, execution_status,
                          execution_outcome_json, model_version, intervention_triggered,
                          final_outcome, created_at
                   FROM prediction_log WHERE run_id=? ORDER BY id""",
                (run_id,),
            ).fetchall()
            traj = conn.execute(
                """SELECT step_index, stage, event_type,
                          cumulative_errors, cumulative_test_failures,
                          repeated_messages, steps_without_progress,
                          elapsed_seconds, label_task_failed
                   FROM trajectory_features WHERE run_id=? ORDER BY step_index""",
                (run_id,),
            ).fetchall()

        latest = events[-1] if events else None
        latest_pred = preds[-1] if preds else None

        prediction_available = bool(latest_pred and latest_pred["model_version"] != "unavailable_no_validated_model")
        latest_risk_score = None
        if prediction_available and latest and latest["risk_score"] is not None:
            latest_risk_score = float(latest["risk_score"])
        elif prediction_available and latest_pred and latest_pred["risk_score"] is not None:
            latest_risk_score = float(latest_pred["risk_score"])

        latest_risk_reasons = []
        if latest and latest["risk_reasons_json"]:
            try:
                latest_risk_reasons = json.loads(latest["risk_reasons_json"])
            except Exception:
                latest_risk_reasons = []
        elif latest_pred and latest_pred["risk_reasons_json"]:
            try:
                latest_risk_reasons = json.loads(latest_pred["risk_reasons_json"])
            except Exception:
                latest_risk_reasons = []

        return {
            "run_id": run_id,
            "event_count": len(events),
            # --- Early failure prediction ---
            "failure_prediction": {
                "latest_risk_score": latest_risk_score,
                "latest_risk_reasons": latest_risk_reasons,
                "recommended_action": latest_pred["risk_action"] if latest_pred else None,
                "executed_action": latest_pred["executed_action"] if latest_pred else None,
                "execution_status": latest_pred["execution_status"] if latest_pred else None,
                "execution_outcome": (
                    json.loads(latest_pred["execution_outcome_json"])
                    if latest_pred and latest_pred["execution_outcome_json"] else None
                ),
                "model_version": latest_pred["model_version"] if latest_pred else "unavailable_no_validated_model",
                "is_trained_model": False,
                "trained_model_status": "No validated model is deployed",
                "prediction_type": "unavailable",
                "note": "A risk score is withheld until a supervised model has been validated and deployed.",
            },
            # --- Recovery ---
            "recovery_stats": self.get_recovery_summary(run_id),
            # --- Events ---
            "events": [
                {
                    "stage": e["stage"],
                    "event_type": e["event_type"],
                    "success": bool(e["success"]),
                    "details": json.loads(e["details_json"] or "{}"),
                    "elapsed_seconds": e["elapsed_seconds"],
                    "risk_score": e["risk_score"],
                    "risk_reasons": json.loads(e["risk_reasons_json"] or "[]"),
                    "created_at": e["created_at"],
                }
                for e in events
            ],
            # --- Trajectory features (for prediction pipeline inspection) ---
            "trajectory": [
                {
                    "step_index": t["step_index"],
                    "stage": t["stage"],
                    "event_type": t["event_type"],
                    "cumulative_errors": t["cumulative_errors"],
                    "cumulative_test_failures": t["cumulative_test_failures"],
                    "repeated_messages": t["repeated_messages"],
                    "steps_without_progress": t["steps_without_progress"],
                    "elapsed_seconds": t["elapsed_seconds"],
                    "label_task_failed": t["label_task_failed"],
                }
                for t in traj
            ],
        }

    # ------------------------------------------------------------------
    # Read: failure predictor status
    # ------------------------------------------------------------------

    def get_predictor_status(self) -> dict:
        """Return status of the failure predictor and labelled trajectory counts."""
        with self._connect() as conn:
            total_traj = conn.execute(
                "SELECT COUNT(DISTINCT run_id) FROM trajectory_features"
            ).fetchone()[0]
            labelled = conn.execute(
                "SELECT COUNT(DISTINCT run_id) FROM trajectory_features "
                "WHERE label_task_failed IS NOT NULL"
            ).fetchone()[0]
            pos = conn.execute(
                "SELECT COUNT(DISTINCT run_id) FROM trajectory_features "
                "WHERE label_task_failed = 1"
            ).fetchone()[0]
            neg = conn.execute(
                "SELECT COUNT(DISTINCT run_id) FROM trajectory_features "
                "WHERE label_task_failed = 0"
            ).fetchone()[0]

        MIN_EACH = 5  # minimum per class for training
        can_train = pos >= MIN_EACH and neg >= MIN_EACH

        return {
            "live_prediction": "disabled_no_validated_model",
            "supervised_model": None,
            "supervised_mode": "offline_evaluation_only; no heuristic or unvalidated model is used for live predictions",
            "supervised_status": (
                "Insufficient labelled runs for offline evaluation"
                if not can_train
                else f"Ready for offline evaluation ({pos} failures, {neg} successes)"
            ),
            "can_train": can_train,
            "total_trajectories": total_traj,
            "labelled_trajectories": labelled,
            "positive_labels": pos,
            "negative_labels": neg,
            "min_samples_per_class_required": MIN_EACH,
            "training_split": "GroupShuffleSplit on run_id (no leakage)",
            "metrics_to_evaluate": [
                "precision", "recall", "f1", "pr_auc", "brier_score",
                "warning_lead_time_steps",
            ],
        }

    # ------------------------------------------------------------------
    # Supervised predictor training: leakage-free with GroupShuffleSplit
    # ------------------------------------------------------------------

    def train_and_evaluate_predictor(self) -> dict:
        """Train a logistic regression failure predictor using GroupShuffleSplit.

        Returns INSUFFICIENT_DATA when fewer than 5 samples per class exist.
        Uses run_id as group key so no data from the same run leaks between
        train and test folds.

        Features: cumulative_errors, cumulative_test_failures, repeated_messages,
        steps_without_progress, constraint_violations, elapsed_seconds,
        ast_errors, json_parse_errors, plan_discrepancy, retry_count,
        tool_failures, latency_anomaly, llm_fallback_used, template_used, diff_size
        """
        FEATURE_COLS = [
            "cumulative_errors", "cumulative_test_failures", "repeated_messages",
            "steps_without_progress", "constraint_violations", "elapsed_seconds",
            "ast_errors", "json_parse_errors", "plan_discrepancy", "retry_count",
            "tool_failures", "latency_anomaly", "llm_fallback_used", "template_used",
            "diff_size",
        ]

        with self._connect() as conn:
            rows = conn.execute(
                """SELECT run_id, step_index, label_task_failed,
                          cumulative_errors, cumulative_test_failures, repeated_messages,
                          steps_without_progress, constraint_violations, elapsed_seconds,
                          ast_errors, json_parse_errors, plan_discrepancy, retry_count,
                          tool_failures, latency_anomaly, llm_fallback_used, template_used,
                          diff_size
                   FROM trajectory_features
                   WHERE label_task_failed IS NOT NULL
                   ORDER BY run_id, step_index""",
            ).fetchall()

        if not rows:
            return {"status": "INSUFFICIENT_DATA", "reason": "No labelled trajectories available."}

        # Build arrays
        import numpy as np  # type: ignore
        run_ids = [r["run_id"] for r in rows]
        labels = np.array([r["label_task_failed"] for r in rows])
        features = np.array([
            [float(r[col] or 0) for col in FEATURE_COLS]
            for r in rows
        ])
        groups = np.array(run_ids)

        pos_count = int(labels.sum())
        neg_count = int(len(labels) - pos_count)
        unique_runs = len(set(run_ids))
        pos_runs = len(set(r["run_id"] for r in rows if r["label_task_failed"] == 1))
        neg_runs = unique_runs - pos_runs

        if pos_runs < 5 or neg_runs < 5:
            return {
                "status": "INSUFFICIENT_DATA",
                "reason": f"Need ≥5 runs per class. Have {pos_runs} failed, {neg_runs} passed.",
                "positive_runs": pos_runs,
                "negative_runs": neg_runs,
                "total_samples": len(rows),
            }

        try:
            from sklearn.linear_model import LogisticRegression  # type: ignore
            from sklearn.preprocessing import StandardScaler  # type: ignore
            from sklearn.metrics import (  # type: ignore
                precision_score, recall_score, f1_score,
                average_precision_score, brier_score_loss,
            )
            from sklearn.model_selection import GroupShuffleSplit  # type: ignore
        except ImportError:
            return {
                "status": "DEPENDENCY_MISSING",
                "reason": "scikit-learn is required for training. Install with: pip install scikit-learn",
            }

        gss = GroupShuffleSplit(n_splits=1, test_size=0.3, random_state=42)
        train_idx, test_idx = next(gss.split(features, labels, groups))

        X_train, X_test = features[train_idx], features[test_idx]
        y_train, y_test = labels[train_idx], labels[test_idx]

        # Check class balance in test set
        test_pos = int(y_test.sum())
        test_neg = int(len(y_test) - test_pos)
        if test_pos < 2 or test_neg < 2:
            return {
                "status": "INSUFFICIENT_DATA",
                "reason": f"Test split too imbalanced (pos={test_pos}, neg={test_neg}).",
                "total_samples": len(rows),
            }

        scaler = StandardScaler()
        X_train_sc = scaler.fit_transform(X_train)
        X_test_sc = scaler.transform(X_test)

        model = LogisticRegression(max_iter=500, random_state=42, class_weight="balanced")
        model.fit(X_train_sc, y_train)

        y_pred = model.predict(X_test_sc)
        y_prob = model.predict_proba(X_test_sc)[:, 1]

        precision = float(precision_score(y_test, y_pred, zero_division=0))
        recall = float(recall_score(y_test, y_pred, zero_division=0))
        f1 = float(f1_score(y_test, y_pred, zero_division=0))
        pr_auc = float(average_precision_score(y_test, y_prob))
        brier = float(brier_score_loss(y_test, y_prob))
        prevalence = float(y_test.mean())
        baseline_precision = prevalence  # random classifier precision

        # Warning lead time: avg step_index of first correct positive prediction per run
        test_run_ids = groups[test_idx]
        lead_times = []
        for rid in set(test_run_ids):
            mask = test_run_ids == rid
            if y_test[mask].sum() > 0:  # actually failed run
                pred_mask = mask & (y_pred == 1)
                if pred_mask.any():
                    first_warning_step = min(
                        rows[test_idx[i]]["step_index"]
                        for i in range(len(test_idx))
                        if pred_mask[i]
                    )
                    total_steps = max(
                        rows[test_idx[i]]["step_index"]
                        for i in range(len(test_idx))
                        if mask[i]
                    )
                    lead_times.append(total_steps - first_warning_step)

        avg_lead_time = round(sum(lead_times) / len(lead_times), 2) if lead_times else None

        return {
            "status": "EVALUATED_OFFLINE",
            "model_type": "LogisticRegression",
            "features": FEATURE_COLS,
            "training_samples": len(train_idx),
            "test_samples": len(test_idx),
            "unique_runs_train": len(set(groups[train_idx])),
            "unique_runs_test": len(set(groups[test_idx])),
            "metrics": {
                "precision": round(precision, 4),
                "recall": round(recall, 4),
                "f1": round(f1, 4),
                "pr_auc": round(pr_auc, 4),
                "brier_score": round(brier, 4),
                "prevalence": round(prevalence, 4),
                "baseline_precision": round(baseline_precision, 4),
                "avg_steps_before_terminal_outcome": avg_lead_time,
                "lead_time_definition": "steps from first positive warning to last observed step in each failed run",
            },
            "split_method": "GroupShuffleSplit on run_id (no leakage)",
            "note": (
                "Model trained on labelled trajectory features. "
                "PR-AUC and Brier score are the primary evaluation metrics. "
                "Prevalence and baseline precision are included for context."
            ),
        }

    # ------------------------------------------------------------------
    # Legacy shim: record_recovery_stats (called by orchestrator)
    # ------------------------------------------------------------------

    def record_recovery_stats(
        self,
        run_id: str,
        recovery_attempts: list[dict[str, Any]],
        test_results: list[dict[str, Any]],
        elapsed_seconds: float,
        human_intervention_count: int = 0,
    ) -> dict:
        """Kept for backward compatibility. Persists to legacy table only."""
        attempts = len(recovery_attempts)
        resolved = sum(1 for item in recovery_attempts if bool(item.get("resolved", False)))
        test_runs = len(test_results)
        failure_types: dict[str, dict] = {}
        for item in recovery_attempts:
            kind = str(item.get("failure_reason") or "unknown")
            bucket = failure_types.setdefault(kind, {"attempts": 0, "resolved": 0})
            bucket["attempts"] += 1
            bucket["resolved"] += int(bool(item.get("resolved", False)))

        stats = {
            "run_id": run_id,
            "data_source": "legacy_shim",
            "recovery_attempts": attempts,
            "resolved_recoveries": resolved,
            "recovery_rate_percent": round(100 * resolved / attempts, 2) if attempts else 0.0,
            "recovery_time_seconds": round(max(0.0, elapsed_seconds), 3),
            "extra_steps": attempts + max(0, test_runs - 1),
            "test_runs": test_runs,
            "human_intervention_count": int(human_intervention_count),
            "estimated_cost_units": attempts + max(0, test_runs - 1),
            "cost_note": (
                "Proxy count (recovery attempts + extra test runs). "
                "Not monetary or token cost."
            ),
            "failure_type_breakdown": failure_types,
            "updated_at": _now(),
        }
        with self._connect() as conn:
            try:
                conn.execute(
                    """INSERT INTO recovery_run_stats (run_id, stats_json, created_at, updated_at)
                       VALUES (?, ?, ?, ?)
                       ON CONFLICT(run_id) DO UPDATE SET
                         stats_json=excluded.stats_json, updated_at=excluded.updated_at""",
                    (run_id, json.dumps(stats), _now(), _now()),
                )
            except sqlite3.OperationalError:
                # Fallback if updated_at column doesn't exist yet
                conn.execute(
                    """INSERT INTO recovery_run_stats (run_id, stats_json, created_at)
                       VALUES (?, ?, ?)
                       ON CONFLICT(run_id) DO UPDATE SET
                         stats_json=excluded.stats_json""",
                    (run_id, json.dumps(stats), _now()),
                )
            conn.commit()
        return stats


feature_analytics_service = FeatureAnalyticsService()
