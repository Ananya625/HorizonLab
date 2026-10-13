"""Hierarchical Agent Proficiency Profiling Service.

Provides micro-level (7 individual agents) and macro-level (end-to-end system)
evidence-grounded profiling from persisted execution outcomes.
"""
from __future__ import annotations

import json
import logging
import math
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .db import db_service
from .capability_estimator import ContinuousSummary
from .feature_analytics_service import validate_model_name

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# The 7 Actual Agents Registry
# ---------------------------------------------------------------------------

AGENT_REGISTRY: Dict[str, Dict[str, str]] = {
    "orchestrator": {
        "id": "orchestrator",
        "name": "System Orchestrator",
        "stage": "workspace / pipeline",
        "primary_metric": "workflow_completion_rate",
        "primary_metric_label": "Workflow Completion Rate",
        "description": "Lifecycle orchestration, stage gating, and pipeline fault tolerance.",
        "measurement_basis": "Completed runs divided by analyzed runs, from the persisted run status.",
    },
    "requirement_analyst": {
        "id": "requirement_analyst",
        "name": "Requirement Analyst Agent",
        "stage": "requirement",
        "primary_metric": "goal_extraction_success_rate",
        "primary_metric_label": "Structured Goal Output Rate",
        "description": "Whether the requirement stage persisted a structured GoalModel; this does not score semantic correctness.",
        "measurement_basis": "Persisted, parseable GoalModel outputs divided by requirement-stage attempts.",
    },
    "planner": {
        "id": "planner",
        "name": "Codebase Analyst & Planner Agent",
        "stage": "planner",
        "primary_metric": "plan_feasibility_rate",
        "primary_metric_label": "Plan Feasibility Rate",
        "description": "Repository AST inspection, target file mapping, and execution roadmap generation.",
        "measurement_basis": "Planned and changed file paths that match divided by the union of planned and changed paths.",
    },
    "coder": {
        "id": "coder",
        "name": "Coding Agent",
        "stage": "coder",
        "primary_metric": "ast_validity_rate",
        "primary_metric_label": "AST Syntax Validity Rate",
        "description": "Multi-file source code generation, unified Git diffs, and AST syntax validation.",
        "measurement_basis": "AST-valid changed files divided by all changed files with recorded AST results.",
    },
    "test_runner": {
        "id": "test_runner",
        "name": "Test Runner Agent",
        "stage": "testing",
        "primary_metric": "execution_integrity_rate",
        "primary_metric_label": "Test Pass Rate",
        "description": "Real pytest sandbox execution, zero-fabrication parsing, and exit code classification.",
        "measurement_basis": "Passed test cases divided by all passed and failed test cases recorded across attempts.",
    },
    "debugger": {
        "id": "debugger",
        "name": "Debugging & Recovery Agent",
        "stage": "debugger",
        "primary_metric": "recovery_success_rate",
        "primary_metric_label": "Recovery Success Rate",
        "description": "Root-cause diagnosis, self-healing patch generation, and regression containment.",
        "measurement_basis": "Verified resolved recovery attempts divided by measured recovery attempts; runs needing no recovery are excluded.",
    },
    "verifier": {
        "id": "verifier",
        "name": "Independent Code Reviewer & Verifier Agent",
        "stage": "verifier",
        "primary_metric": "verification_pass_rate",
        "primary_metric_label": "Verified Audit Rate",
        "description": "Independent criteria verification, deterministic constraint audit, and goal drift scoring.",
        "measurement_basis": "Compliant constraints divided by constraints with a recorded compliance result.",
    },
}

ALL_AGENT_IDS = list(AGENT_REGISTRY.keys())
_PROFICIENCY_DATA_VERSION = "3"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Hierarchical Proficiency Service
# ---------------------------------------------------------------------------

class HierarchicalProficiencyService:
    """Computes, persists, and aggregates hierarchical agent proficiencies."""

    def __init__(self):
        self.db_path = getattr(db_service, "db_path", None)
        if not self.db_path:
            raise RuntimeError("DatabaseService db_path is not configured")
        self._apply_migrations()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _apply_migrations(self) -> None:
        ddl = """
        CREATE TABLE IF NOT EXISTS agent_proficiency_observations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            obs_id TEXT NOT NULL UNIQUE,
            run_id TEXT NOT NULL,
            agent_id TEXT NOT NULL,
            model_name TEXT NOT NULL,
            metric_name TEXT NOT NULL,
            successes INTEGER NOT NULL DEFAULT 0,
            failures INTEGER NOT NULL DEFAULT 0,
            continuous_value REAL,
            attribution TEXT,
            details_json TEXT NOT NULL DEFAULT '{}',
            provenance TEXT NOT NULL DEFAULT 'llm',
            is_valid INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        )
        """
        with self._connect() as conn:
            conn.execute(ddl)
            conn.execute(
                """CREATE TABLE IF NOT EXISTS agent_proficiency_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )"""
            )
            conn.execute(
                "INSERT OR IGNORE INTO agent_proficiency_metadata (key, value) VALUES ('data_version', '0')"
            )
            # Index for fast aggregation by model_name and agent_id
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_agent_prof_model_agent "
                "ON agent_proficiency_observations (model_name, agent_id, metric_name)"
            )
            conn.commit()

    # ------------------------------------------------------------------
    # Analysis & Extraction of a Single Run
    # ------------------------------------------------------------------

    def record_run_proficiencies(
        self,
        run_id: str,
        model_name: Optional[str] = None,
        provenance: str = "llm"
    ) -> Dict[str, Any]:
        """Analyze run artifacts and persist proficiency observations for all 7 agents and system."""
        with self._connect() as conn:
            # 1. Fetch run header
            run_row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
            if not run_row:
                logger.warning("record_run_proficiencies: run %s not found", run_id)
                return {}

            # Determine model_name
            actual_model = model_name
            if not actual_model or actual_model.lower() in ("none", "", "unknown", "null"):
                # Try finding model_name in feature_events or execution_logs
                fe_row = conn.execute(
                    "SELECT model_name FROM feature_events WHERE run_id = ? AND model_name NOT IN ('none', '', 'unknown', 'null') LIMIT 1",
                    (run_id,)
                ).fetchone()
                if fe_row:
                    actual_model = fe_row[0]
                else:
                    actual_model = None

            if not actual_model:
                logger.warning("No model identity recorded for run %s; profile observation skipped", run_id)
                return {}

            try:
                actual_model = validate_model_name(actual_model)
            except ValueError:
                logger.warning("Invalid model identity for run %s; profile observation skipped", run_id)
                return {}

            # 2. Fetch all stage artifacts for run
            gm_row = conn.execute("SELECT data_json FROM goal_models WHERE run_id = ?", (run_id,)).fetchone()
            plan_row = conn.execute("SELECT data_json FROM plans WHERE run_id = ?", (run_id,)).fetchone()
            changes_rows = conn.execute("SELECT * FROM code_changes WHERE run_id = ?", (run_id,)).fetchall()
            test_rows = conn.execute(
                "SELECT * FROM test_results WHERE run_id = ? ORDER BY attempt_number ASC",
                (run_id,)
            ).fetchall()
            recovery_rows = conn.execute(
                "SELECT * FROM recovery_attempts WHERE run_id = ? ORDER BY attempt_number ASC",
                (run_id,)
            ).fetchall()
            verif_row = conn.execute("SELECT * FROM verifications WHERE run_id = ?", (run_id,)).fetchone()
            log_rows = conn.execute(
                "SELECT * FROM execution_logs WHERE run_id = ? ORDER BY timestamp ASC",
                (run_id,)
            ).fetchall()

            # Parse JSON structures
            try:
                goal_model = json.loads(gm_row["data_json"]) if gm_row else {}
            except json.JSONDecodeError as exc:
                logger.warning("Ignoring malformed GoalModel for run %s: %s", run_id, exc)
                goal_model = {}
            try:
                plan = json.loads(plan_row["data_json"]) if plan_row else {}
            except json.JSONDecodeError as exc:
                logger.warning("Ignoring malformed plan for run %s: %s", run_id, exc)
                plan = {}
            try:
                verif = json.loads(verif_row["data_json"]) if verif_row else {}
            except json.JSONDecodeError as exc:
                logger.warning("Ignoring malformed verification report for run %s: %s", run_id, exc)
                verif = {}
            if not isinstance(goal_model, dict):
                logger.warning("Ignoring non-object GoalModel for run %s", run_id)
                goal_model = {}
            if not isinstance(plan, dict):
                logger.warning("Ignoring non-object plan for run %s", run_id)
                plan = {}
            if not isinstance(verif, dict):
                logger.warning("Ignoring non-object verification report for run %s", run_id)
                verif = {}

            now_str = _now()
            observations_to_insert = []

            observed_failure_events = [
                {"stage": str(row["stage"] or "unknown"), "event_type": str(row["event_type"] or "unknown")}
                for row in log_rows
                if str(row["event_type"] or "").lower() in {
                    "error", "failure", "tool_error", "test_failure", "recovery_incomplete", "policy_stop"
                }
            ]

            # --- Agent 1: System Orchestrator ---
            is_completed = (run_row["status"] == "completed")
            orchestrator_success = 1 if is_completed else 0
            orch_attribution = "completed" if is_completed else str(run_row["current_stage"] or "incomplete")
            observations_to_insert.append((
                f"{run_id}_orchestrator_workflow_completion_rate",
                run_id, "orchestrator", actual_model, "workflow_completion_rate",
                orchestrator_success, 1 - orchestrator_success, None, orch_attribution,
                json.dumps({
                    "status": run_row["status"],
                    "stage": run_row["current_stage"],
                    "measurement_basis": AGENT_REGISTRY["orchestrator"]["measurement_basis"],
                }),
                provenance, 1, now_str
            ))

            # --- Agent 2: Requirement Analyst Agent ---
            subgoals = goal_model.get("sub_goals", [])
            criteria = goal_model.get("success_criteria", [])
            stage_attempted = bool(gm_row) or str(run_row["current_stage"] or "").lower() in {
                "requirement", "planner", "planning", "coder", "coding", "testing",
                "debugger", "verification", "verifier", "completed",
            }
            req_measured = stage_attempted
            has_structured_shape = (
                isinstance(goal_model.get("main_goal"), str) and bool(goal_model["main_goal"].strip())
            ) or (
                isinstance(goal_model.get("sub_goals"), list)
                and isinstance(goal_model.get("success_criteria"), list)
            )
            req_success = int(bool(gm_row and has_structured_shape))
            req_attribution = "structured_goal_output_recorded" if req_success else "structured_goal_output_missing"
            observations_to_insert.append((
                f"{run_id}_requirement_analyst_goal_extraction_success_rate",
                run_id, "requirement_analyst", actual_model, "goal_extraction_success_rate",
                req_success if req_measured else 0,
                (1 - req_success) if req_measured else 0,
                float(len(criteria)) if isinstance(criteria, list) else None,
                req_attribution,
                json.dumps({
                    "subgoals_count": len(subgoals) if isinstance(subgoals, list) else 0,
                    "criteria_count": len(criteria) if isinstance(criteria, list) else 0,
                    "measurement_basis": AGENT_REGISTRY["requirement_analyst"]["measurement_basis"],
                }),
                provenance, int(req_measured), now_str
            ))

            # --- Agent 3: Codebase Analyst & Planner Agent ---
            steps = plan.get("steps", [])
            planned_files = plan.get("planned_files", [])
            # Calculate plan fidelity vs actual files changed
            actual_file_paths = {r["file_path"] for r in changes_rows}
            planned_file_paths = {f.get("path") or f.get("file_path") for f in planned_files if f.get("path") or f.get("file_path")}
            matched_files = len(actual_file_paths & planned_file_paths)
            unmatched_files = len(actual_file_paths ^ planned_file_paths)
            plan_measured = bool(actual_file_paths | planned_file_paths)
            plan_fidelity = round(matched_files / len(actual_file_paths | planned_file_paths), 4) if actual_file_paths | planned_file_paths else None
            plan_attribution = "measured" if plan_measured else "insufficient_evidence"

            observations_to_insert.append((
                f"{run_id}_planner_plan_feasibility_rate",
                run_id, "planner", actual_model, "plan_feasibility_rate",
                matched_files, unmatched_files, plan_fidelity, plan_attribution,
                json.dumps({"steps_count": len(steps), "planned_files_count": len(planned_files), "actual_files_count": len(actual_file_paths), "matched_files": matched_files, "unmatched_files": unmatched_files, "fidelity": plan_fidelity, "measurement_basis": AGENT_REGISTRY["planner"]["measurement_basis"]}),
                provenance, int(plan_measured), now_str
            ))

            # --- Agent 4: Coding Agent ---
            ast_valid_count = sum(1 for c in changes_rows if int(c["ast_valid"]) == 1)
            total_changes = len(changes_rows)
            invalid_ast_count = total_changes - ast_valid_count
            coder_attribution = "measured" if total_changes else "no_code_changes_recorded"
            total_lines_diff = sum(int(c["lines_added"]) + int(c["lines_removed"]) for c in changes_rows)

            observations_to_insert.append((
                f"{run_id}_coder_ast_validity_rate",
                run_id, "coder", actual_model, "ast_validity_rate",
                ast_valid_count, invalid_ast_count, float(total_lines_diff), coder_attribution,
                json.dumps({"ast_valid": ast_valid_count, "total_files": total_changes, "lines_diff": total_lines_diff, "measurement_basis": AGENT_REGISTRY["coder"]["measurement_basis"]}),
                provenance, int(total_changes > 0), now_str
            ))

            # --- Agent 5: Test Runner Agent ---
            test_durations = []
            total_tests_count = 0
            passed_tests_count = 0
            failed_tests_count = 0
            if test_rows:
                for tr in test_rows:
                    test_durations.append(float(tr["duration_seconds"] or 0.0))
                    passed_tests_count += int(tr["passed_tests"] or 0)
                    failed_tests_count += int(tr["failed_tests"] or 0)
                    total_tests_count += int(tr["total_tests"] or 0)

            test_attribution = "measured" if test_rows else "insufficient_evidence"
            avg_test_duration = sum(test_durations) / max(1, len(test_durations))

            observations_to_insert.append((
                f"{run_id}_test_runner_execution_integrity_rate",
                run_id, "test_runner", actual_model, "execution_integrity_rate",
                passed_tests_count, failed_tests_count, avg_test_duration, test_attribution,
                json.dumps({"total_tests": total_tests_count, "test_runs": len(test_rows), "measurement_basis": AGENT_REGISTRY["test_runner"]["measurement_basis"]}),
                provenance, int(total_tests_count > 0), now_str
            ))

            # --- Agent 6: Debugging & Recovery Agent ---
            # Recovery is only active when test failures occurred and recovery was needed
            had_initial_failure = any(tr["status"] != "PASSED" or int(tr["failed_tests"] or 0) > 0 for tr in test_rows[:1])
            recovery_needed = 1 if (had_initial_failure or len(recovery_rows) > 0) else 0

            if recovery_needed and recovery_rows:
                final_test_row = test_rows[-1] if test_rows else None
                recovery_measured = bool(final_test_row and int(final_test_row["total_tests"] or 0) > 0)
                final_passed = bool(recovery_measured and final_test_row["status"] == "PASSED" and int(final_test_row["failed_tests"] or 0) == 0)
                recovery_success = sum(bool(r["resolved"]) for r in recovery_rows) if final_passed else 0
                recovery_failures = len(recovery_rows) - recovery_success
                deb_attribution = "debugger_recovered" if recovery_success else "debugger_exhaustion"
            else:
                recovery_measured = False
                recovery_success = 0
                recovery_failures = 0
                deb_attribution = "no_recovery_needed_unmeasured"

            observations_to_insert.append((
                f"{run_id}_debugger_recovery_success_rate",
                run_id, "debugger", actual_model, "recovery_success_rate",
                recovery_success, recovery_failures,
                float(len(recovery_rows)), deb_attribution,
                json.dumps({"recovery_attempts": len(recovery_rows), "recovery_needed": recovery_needed, "measurement_basis": AGENT_REGISTRY["debugger"]["measurement_basis"]}),
                provenance, int(bool(recovery_needed and recovery_rows and recovery_measured)), now_str
            ))

            # --- Agent 7: Independent Code Reviewer & Verifier ---
            verdict_str = str(verif.get("overall_verdict") or "")
            final_test = test_rows[-1] if test_rows else None
            constraints = verif.get("constraint_compliances") or []
            measured_constraints = [c for c in constraints if c.get("compliant") is not None]
            verif_success = sum(bool(c.get("compliant")) for c in measured_constraints)
            verif_failures = len(measured_constraints) - verif_success
            verif_attribution = "measured" if measured_constraints else "no_independent_evidence"

            observations_to_insert.append((
                f"{run_id}_verifier_verification_pass_rate",
                run_id, "verifier", actual_model, "verification_pass_rate",
                verif_success, verif_failures, None, verif_attribution,
                json.dumps({
                    "verdict": verdict_str,
                    "constraints_measured": len(measured_constraints),
                    "constraints_compliant": verif_success,
                    "criteria_statuses": [c.get("verdict") for c in (verif.get("criteria_evaluations") or [])],
                    "measurement_basis": AGENT_REGISTRY["verifier"]["measurement_basis"],
                }),
                provenance, int(bool(measured_constraints)), now_str
            ))

            # --- System Profile: End-to-End ---
            final_tests_passed = bool(
                test_rows
                and test_rows[-1]["status"] == "PASSED"
                and int(test_rows[-1]["total_tests"] or 0) > 0
                and int(test_rows[-1]["passed_tests"] or 0) == int(test_rows[-1]["total_tests"] or 0)
            )
            e2e_verified = int(is_completed and final_tests_passed)
            system_measured = bool(test_rows and int(test_rows[-1]["total_tests"] or 0) > 0)
            system_attribution = json.dumps(observed_failure_events)

            observations_to_insert.append((
                f"{run_id}_system_e2e_verified_success_rate",
                run_id, "system", actual_model, "e2e_verified_success_rate",
                e2e_verified, 1 - e2e_verified, None, system_attribution,
                json.dumps({
                    "e2e_verified": e2e_verified,
                    "observed_failure_events": observed_failure_events,
                    "recovery_outcome": deb_attribution,
                }),
                provenance, int(system_measured), now_str
            ))

            execution_duration = db_service.get_verified_execution_duration(conn, run_id)
            observations_to_insert.append((
                f"{run_id}_system_e2e_duration_seconds",
                run_id, "system", actual_model, "e2e_duration_seconds",
                0, 0, execution_duration,
                "verified_execution_duration" if execution_duration is not None else "unverified_duration",
                json.dumps({"execution_time_seconds": execution_duration}),
                provenance, int(execution_duration is not None), now_str,
            ))

            # Idempotently insert observations
            conn.executemany(
                """INSERT INTO agent_proficiency_observations
                (obs_id, run_id, agent_id, model_name, metric_name, successes, failures,
                 continuous_value, attribution, details_json, provenance, is_valid, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(obs_id) DO UPDATE SET
                    successes = excluded.successes,
                    failures = excluded.failures,
                    continuous_value = excluded.continuous_value,
                    attribution = excluded.attribution,
                    details_json = excluded.details_json,
                    is_valid = excluded.is_valid,
                    created_at = excluded.created_at
                """,
                observations_to_insert
            )
            conn.commit()

            attribution_info = self._classify_run_attribution(
                run_row,
                goal_model,
                plan,
                changes_rows,
                test_rows,
                recovery_rows,
                verif,
            )
            return {
                "run_id": run_id,
                "model_name": actual_model,
                "observations_recorded": len(observations_to_insert),
                "attribution": attribution_info,
            }

    # ------------------------------------------------------------------
    # Failure & Recovery Attribution Engine
    # ------------------------------------------------------------------

    def _classify_run_attribution(
        self,
        run_row: sqlite3.Row,
        goal_model: dict,
        plan: dict,
        code_changes: list,
        test_results: list,
        recovery_attempts: list,
        verification: dict,
    ) -> Dict[str, str]:
        """Accurately attributes root causes and recovery outcomes based on concrete execution artifacts."""
        root_causes: List[str] = []

        # 1. Requirement & Planner
        if not goal_model.get("sub_goals") or not goal_model.get("success_criteria"):
            root_causes.append("requirement_failure")

        if not plan.get("steps") or not plan.get("planned_files"):
            root_causes.append("planner_failure")

        # 2. Coder
        has_ast_error = any(int(c["ast_valid"]) == 0 for c in code_changes)
        if has_ast_error:
            root_causes.append("coder_syntax_failure")
            coder_attribution = "root_cause_syntax"
        elif test_results and (test_results[0]["status"] != "PASSED" or int(test_results[0]["failed_tests"] or 0) > 0):
            root_causes.append("coder_logic_failure")
            coder_attribution = "root_cause_logic"
        else:
            coder_attribution = "clean"

        # 3. Test Runner
        has_harness_error = any(tr["status"] == "ERROR" or tr["exit_code"] in (2, 3, 4) for tr in test_results)
        if has_harness_error:
            root_causes.append("test_harness_failure")

        # 4. Debugger & Recovery
        final_test = test_results[-1] if test_results else None
        final_test_failed = bool(final_test and (final_test["status"] != "PASSED" or int(final_test["failed_tests"] or 0) > 0))

        if len(recovery_attempts) > 0 or (test_results and test_results[0]["status"] != "PASSED"):
            if final_test_failed:
                root_causes.append("debugger_exhaustion")
                recovery_outcome = "unresolved_failure"
            else:
                recovery_outcome = "debugger_recovered"
        else:
            recovery_outcome = "clean_no_recovery_needed"

        # 5. Verifier
        verdict = str(verification.get("overall_verdict") or "").upper()
        if "FAIL" in verdict or "REJECT" in verdict:
            root_causes.append("verifier_rejection")

        # 6. Orchestrator
        if run_row["status"] != "completed":
            root_causes.append("orchestrator_abort")
            orch_attribution = "orchestrator_abort"
        else:
            orch_attribution = "clean"

        # Select primary root cause
        if not root_causes:
            primary_root_cause = "clean_execution"
        else:
            # Deterministic precedence: syntax error > logic error > harness error > planner failure > verifier rejection > orchestrator abort
            precedence = [
                "coder_syntax_failure",
                "coder_logic_failure",
                "test_harness_failure",
                "planner_failure",
                "requirement_failure",
                "debugger_exhaustion",
                "verifier_rejection",
                "orchestrator_abort",
            ]
            primary_root_cause = next((c for c in precedence if c in root_causes), root_causes[0])

        return {
            "primary_root_cause": primary_root_cause,
            "all_causes": root_causes,
            "recovery_outcome": recovery_outcome,
            "coder_attribution": coder_attribution,
            "orchestrator_attribution": orch_attribution,
        }

    # ------------------------------------------------------------------
    # Batch Synchronization of Historical Database Runs
    # ------------------------------------------------------------------

    def sync_all_historical_runs(self) -> int:
        """Scan all completed/in-progress runs in SQLite and populate proficiency observations."""
        with self._connect() as conn:
            runs = conn.execute("SELECT run_id FROM runs").fetchall()

        count = 0
        for r in runs:
            try:
                res = self.record_run_proficiencies(r["run_id"])
                if res:
                    count += 1
            except Exception as exc:
                logger.warning("Error syncing run %s: %s", r["run_id"], exc)
        return count

    # ------------------------------------------------------------------
    # Hierarchical Profiles Aggregator
    # ------------------------------------------------------------------

    @staticmethod
    def _observed_binary_metric(
        metric: str,
        successes: int,
        failures: int,
        evidence_status: str,
    ) -> Dict[str, Any]:
        sample_size = successes + failures
        return {
            "capability": metric,
            "successes": successes,
            "failures": failures,
            "sample_size": sample_size,
            "observed_rate": successes / sample_size if sample_size else None,
            "evidence_status": "measured" if sample_size else evidence_status,
        }

    def get_hierarchical_profiles(
        self,
        model_name: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Aggregate only recorded execution outcomes for agents and the system."""
        # Re-read the selected run idempotently so the view always reflects its latest artifacts.
        if run_id:
            self.record_run_proficiencies(run_id, model_name=model_name)
        else:
            with self._connect() as conn:
                version = conn.execute(
                    "SELECT value FROM agent_proficiency_metadata WHERE key='data_version'"
                ).fetchone()
                needs_refresh = not version or version["value"] != _PROFICIENCY_DATA_VERSION
            if needs_refresh:
                self.sync_all_historical_runs()
                with self._connect() as conn:
                    conn.execute(
                        "UPDATE agent_proficiency_metadata SET value=? WHERE key='data_version'",
                        (_PROFICIENCY_DATA_VERSION,),
                    )

        with self._connect() as conn:
            # Query valid observations
            query = """
                SELECT run_id, agent_id, metric_name, successes, failures,
                       continuous_value, attribution, model_name
                FROM agent_proficiency_observations
                WHERE is_valid = 1
            """
            params: List[Any] = []
            if model_name:
                try:
                    norm_model = validate_model_name(model_name)
                    query += " AND model_name = ?"
                    params.append(norm_model)
                except ValueError:
                    # Return insufficient evidence for invalid model name
                    return self._empty_hierarchical_response(model_name or "unknown")

            if run_id:
                query += " AND run_id = ?"
                params.append(run_id)

            rows = conn.execute(query, params).fetchall()

            # Query unique runs count
            run_query = "SELECT COUNT(DISTINCT run_id) FROM agent_proficiency_observations WHERE is_valid = 1"
            run_params: List[Any] = []
            if model_name:
                run_query += " AND model_name = ?"
                run_params.append(norm_model)
            if run_id:
                run_query += " AND run_id = ?"
                run_params.append(run_id)
            total_runs = conn.execute(run_query, run_params).fetchone()[0]

        # Group observations by (agent_id, metric_name)
        grouped_binary: Dict[str, Dict[str, Dict[str, int]]] = {}
        grouped_continuous: Dict[str, Dict[str, List[float]]] = {}
        failure_attributions: Dict[str, int] = {}
        recovery_attributions: Dict[str, int] = {}

        for r in rows:
            agent = r["agent_id"]
            metric = r["metric_name"]
            s = int(r["successes"])
            f = int(r["failures"])
            val = r["continuous_value"]
            attr = r["attribution"]

            if agent not in grouped_binary:
                grouped_binary[agent] = {}
                grouped_continuous[agent] = {}

            if metric not in grouped_binary[agent]:
                grouped_binary[agent][metric] = {"successes": 0, "failures": 0}

            grouped_binary[agent][metric]["successes"] += s
            grouped_binary[agent][metric]["failures"] += f

            if val is not None:
                if agent == "system" and metric == "e2e_duration_seconds":
                    val = db_service.get_verified_execution_duration(
                        conn, r["run_id"]
                    )
                    if val is None:
                        continue
                if metric not in grouped_continuous[agent]:
                    grouped_continuous[agent][metric] = []
                grouped_continuous[agent][metric].append(float(val))

            # Track attributions at system level
            if agent == "system" and attr:
                try:
                    events = json.loads(attr)
                except (TypeError, json.JSONDecodeError):
                    events = []
                for event in events if isinstance(events, list) else []:
                    label = f"{event.get('stage', 'unknown')}: {event.get('event_type', 'unknown')}"
                    failure_attributions[label] = failure_attributions.get(label, 0) + 1
            if agent == "debugger" and attr:
                recovery_attributions[attr] = recovery_attributions.get(attr, 0) + 1

        # --------------------------------------------------------------
        # 1. Build Micro Profiles for All 7 Agents
        # --------------------------------------------------------------
        agent_profiles: Dict[str, Any] = {}

        for agent_id, meta in AGENT_REGISTRY.items():
            primary_metric = meta["primary_metric"]
            bin_data = grouped_binary.get(agent_id, {}).get(primary_metric, {"successes": 0, "failures": 0})
            s = bin_data["successes"]
            f = bin_data["failures"]
            n = s + f

            observed_metric = self._observed_binary_metric(
                primary_metric, s, f, "insufficient_evidence"
            )

            # Continuous measurements for agent
            cont_measurements: Dict[str, Any] = {}
            for c_metric, vals in grouped_continuous.get(agent_id, {}).items():
                if vals:
                    c_summary = ContinuousSummary(measurement=c_metric, unit="value", values=vals)
                    cont_measurements[c_metric] = c_summary.to_dict()

            agent_profiles[agent_id] = {
                "agent_id": agent_id,
                "agent_name": meta["name"],
                "stage": meta["stage"],
                "description": meta["description"],
                "measurement_basis": meta["measurement_basis"],
                "primary_metric_label": meta["primary_metric_label"],
                "primary_metric": observed_metric,
                "secondary_metrics": cont_measurements,
                "sample_size": n,
                "evidence_status": observed_metric["evidence_status"],
            }

        # --------------------------------------------------------------
        # 2. Build Macro Profile for End-to-End System
        # --------------------------------------------------------------
        sys_bin = grouped_binary.get("system", {}).get("e2e_verified_success_rate", {"successes": 0, "failures": 0})
        sys_s = sys_bin["successes"]
        sys_f = sys_bin["failures"]
        sys_n = sys_s + sys_f

        sys_metric = self._observed_binary_metric(
            "e2e_verified_success_rate", sys_s, sys_f, "insufficient_evidence"
        )

        sys_durations = grouped_continuous.get("system", {}).get("e2e_duration_seconds", [])
        duration_summary = ContinuousSummary(measurement="pipeline_duration", unit="seconds", values=sys_durations).to_dict()

        system_profile = {
            "name": "End-to-End System Profile",
            "description": "Synthesized full-pipeline capability across all multi-agent stages.",
            "measurement_basis": "Completed runs with recorded final test outcomes divided into fully passing or not-fully-passing outcomes.",
            "verified_success_rate": sys_metric,
            "duration_summary": duration_summary,
            "total_runs_analyzed": total_runs,
            "evidence_status": sys_metric["evidence_status"],
        }

        # --------------------------------------------------------------
        # 3. Attribution Matrix
        # --------------------------------------------------------------
        attribution_matrix = {
            "total_runs_analyzed": total_runs,
            "total_failures_observed": sum(failure_attributions.values()),
            "failure_attributions": failure_attributions,
            "recovery_attributions": recovery_attributions,
        }

        return {
            "model_name": model_name or "all_models",
            "total_runs_analyzed": total_runs,
            "system_profile": system_profile,
            "agent_profiles": agent_profiles,
            "attribution_matrix": attribution_matrix,
            "generated_at": _now(),
        }

    def _empty_hierarchical_response(self, model_name: str) -> Dict[str, Any]:
        """Return structured response with insufficient_evidence when data is absent."""
        agent_profiles = {}
        for agent_id, meta in AGENT_REGISTRY.items():
            observed_metric = self._observed_binary_metric(
                meta["primary_metric"], 0, 0, "insufficient_evidence"
            )
            agent_profiles[agent_id] = {
                "agent_id": agent_id,
                "agent_name": meta["name"],
                "stage": meta["stage"],
                "description": meta["description"],
                "measurement_basis": meta["measurement_basis"],
                "primary_metric_label": meta["primary_metric_label"],
                "primary_metric": observed_metric,
                "secondary_metrics": {},
                "sample_size": 0,
                "evidence_status": "insufficient_evidence",
            }

        sys_metric = self._observed_binary_metric(
            "e2e_verified_success_rate", 0, 0, "insufficient_evidence"
        )
        return {
            "model_name": model_name,
            "total_runs_analyzed": 0,
            "system_profile": {
                "name": "End-to-End System Profile",
                "description": "Synthesized full-pipeline capability across all multi-agent stages.",
                "verified_success_rate": sys_metric,
                "measurement_basis": "Completed runs with recorded final test outcomes divided into fully passing or not-fully-passing outcomes.",
                "duration_summary": ContinuousSummary(measurement="duration", unit="seconds", values=[]).to_dict(),
                "total_runs_analyzed": 0,
                "evidence_status": "insufficient_evidence",
            },
            "agent_profiles": agent_profiles,
            "attribution_matrix": {
                "total_runs_analyzed": 0,
                "total_failures_observed": 0,
                "failure_attributions": {},
                "recovery_attributions": {},
            },
            "generated_at": _now(),
        }


hierarchical_proficiency_service = HierarchicalProficiencyService()
