import os
import json
import sqlite3
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime
from ..models.schema import (
    RunRecord,
    GoalModel,
    ImplementationPlan,
    CodeChange,
    TestRunResult,
    RecoveryAttempt,
    VerificationReport,
    EvaluationMetrics,
    ExecutionLogEntry,
    AuditEntry
)

DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
os.makedirs(DB_DIR, exist_ok=True)
DB_PATH = os.path.join(DB_DIR, "agent_eval.db")

class DatabaseService:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Runs table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    prompt TEXT NOT NULL,
                    repo_path TEXT NOT NULL,
                    current_stage TEXT NOT NULL DEFAULT 'workspace',
                    status TEXT NOT NULL DEFAULT 'initialized',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    metadata_json TEXT
                )
            """)

            # Goal Models table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS goal_models (
                    run_id TEXT PRIMARY KEY,
                    data_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (run_id) REFERENCES runs (run_id) ON DELETE CASCADE
                )
            """)

            # Goal Model Snapshots (Audit history)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS goal_model_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    version TEXT NOT NULL,
                    data_json TEXT NOT NULL,
                    change_summary TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (run_id) REFERENCES runs (run_id) ON DELETE CASCADE
                )
            """)

            # Implementation Plans table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS plans (
                    run_id TEXT PRIMARY KEY,
                    data_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (run_id) REFERENCES runs (run_id) ON DELETE CASCADE
                )
            """)

            # Code Changes table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS code_changes (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    action TEXT NOT NULL,
                    original_content TEXT,
                    new_content TEXT,
                    diff_patch TEXT,
                    lines_added INTEGER DEFAULT 0,
                    lines_removed INTEGER DEFAULT 0,
                    ast_valid INTEGER DEFAULT 1,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (run_id) REFERENCES runs (run_id) ON DELETE CASCADE
                )
            """)

            # Test Results table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS test_results (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    attempt_number INTEGER DEFAULT 1,
                    total_tests INTEGER DEFAULT 0,
                    passed_tests INTEGER DEFAULT 0,
                    failed_tests INTEGER DEFAULT 0,
                    duration_seconds REAL DEFAULT 0.0,
                    stdout TEXT,
                    stderr TEXT,
                    exit_code INTEGER DEFAULT 0,
                    status TEXT NOT NULL,
                    data_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (run_id) REFERENCES runs (run_id) ON DELETE CASCADE
                )
            """)

            # Recovery Attempts table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS recovery_attempts (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    attempt_number INTEGER NOT NULL,
                    failure_reason TEXT NOT NULL,
                    diagnosis TEXT NOT NULL,
                    root_cause_analysis TEXT,
                    proposed_fix TEXT NOT NULL,
                    files_modified_json TEXT,
                    resolved INTEGER DEFAULT 0,
                    test_run_id TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (run_id) REFERENCES runs (run_id) ON DELETE CASCADE
                )
            """)

            # Verification Reports table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS verifications (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL UNIQUE,
                    overall_verdict TEXT NOT NULL,
                    pass_rate_percent REAL DEFAULT 100.0,
                    goal_drift_score REAL DEFAULT 0.0,
                    code_quality_score REAL DEFAULT 9.0,
                    security_verdict TEXT NOT NULL,
                    data_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (run_id) REFERENCES runs (run_id) ON DELETE CASCADE
                )
            """)

            # Evaluation Metrics table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS evaluations (
                    run_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    success_rate REAL DEFAULT 100.0,
                    execution_time_seconds REAL DEFAULT 0.0,
                    total_tool_calls INTEGER DEFAULT 0,
                    recovery_attempts_count INTEGER DEFAULT 0,
                    goal_drift_score REAL DEFAULT 0.0,
                    lines_added INTEGER DEFAULT 0,
                    lines_removed INTEGER DEFAULT 0,
                    tests_passed INTEGER DEFAULT 0,
                    tests_total INTEGER DEFAULT 0,
                    data_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (run_id) REFERENCES runs (run_id) ON DELETE CASCADE
                )
            """)

            # Execution Logs table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS execution_logs (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    agent_role TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    message TEXT NOT NULL,
                    details_json TEXT,
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY (run_id) REFERENCES runs (run_id) ON DELETE CASCADE
                )
            """)

            conn.commit()

    # --- Run Methods ---
    def create_or_update_run(
        self,
        run_id: str,
        task_id: str,
        title: str,
        prompt: str,
        repo_path: str,
        current_stage: str = "workspace",
        status: str = "initialized",
        metadata: Optional[Dict[str, Any]] = None
    ) -> RunRecord:
        now = datetime.now().isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO runs (run_id, task_id, title, prompt, repo_path, current_stage, status, created_at, updated_at, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    title=excluded.title,
                    current_stage=excluded.current_stage,
                    status=excluded.status,
                    updated_at=excluded.updated_at,
                    metadata_json=coalesce(excluded.metadata_json, runs.metadata_json)
            """, (run_id, task_id, title, prompt, repo_path, current_stage, status, now, now, json.dumps(metadata) if metadata else None))
            conn.commit()
        return self.get_run_record(run_id)

    def get_run_record(self, run_id: str) -> Optional[RunRecord]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,))
            row = cursor.fetchone()
            if not row:
                return None
            
            # Fetch attached entities
            goal_model = self.get_goal_model(run_id)
            plan = self.get_plan(run_id)
            code_changes = self.get_code_changes(run_id)
            test_results = self.get_test_results(run_id)
            recovery_attempts = self.get_recovery_attempts(run_id)
            verification = self.get_verification(run_id)
            evaluation = self.get_evaluation(run_id)
            logs = self.get_execution_logs(run_id)

            return RunRecord(
                run_id=row["run_id"],
                task_id=row["task_id"],
                title=row["title"],
                prompt=row["prompt"],
                repo_path=row["repo_path"],
                current_stage=row["current_stage"],
                status=row["status"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                goal_model=goal_model,
                plan=plan,
                code_changes=code_changes,
                test_results=test_results,
                recovery_attempts=recovery_attempts,
                verification=verification,
                evaluation=evaluation,
                logs=logs
            )

    def list_all_runs(self) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT r.*, e.success_rate, e.execution_time_seconds, e.recovery_attempts_count, e.goal_drift_score
                FROM runs r
                LEFT JOIN evaluations e ON r.run_id = e.run_id
                ORDER BY r.created_at DESC
            """)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    # --- Goal Model Methods ---
    def save_goal_model(self, model: GoalModel) -> GoalModel:
        now = datetime.now().isoformat()
        model.updated_at = now
        model_json = model.model_dump_json()
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO goal_models (run_id, data_json, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    data_json=excluded.data_json,
                    updated_at=excluded.updated_at
            """, (model.run_id, model_json, model.created_at, now))

            # Record in snapshot history
            cursor.execute("""
                INSERT INTO goal_model_history (run_id, version, data_json, change_summary, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (model.run_id, model.goal_model_version, model_json, "Updated Goal Model", now))

            # Update run record
            cursor.execute("""
                UPDATE runs SET current_stage = 'requirement', updated_at = ? WHERE run_id = ?
            """, (now, model.run_id))
            conn.commit()

        return model

    def get_goal_model(self, run_id: str) -> Optional[GoalModel]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT data_json FROM goal_models WHERE run_id = ?", (run_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return GoalModel.model_validate_json(row["data_json"])

    def get_goal_model_history(self, run_id: str) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT version, change_summary, created_at, data_json 
                FROM goal_model_history 
                WHERE run_id = ? 
                ORDER BY id ASC
            """, (run_id,))
            rows = cursor.fetchall()
            return [
                {
                    "version": r["version"],
                    "change_summary": r["change_summary"],
                    "created_at": r["created_at"],
                    "model": json.loads(r["data_json"])
                }
                for r in rows
            ]

    # --- Plan Methods ---
    def save_plan(self, plan: ImplementationPlan) -> ImplementationPlan:
        now = datetime.now().isoformat()
        plan_json = plan.model_dump_json()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO plans (run_id, data_json, created_at)
                VALUES (?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    data_json=excluded.data_json
            """, (plan.run_id, plan_json, now))

            cursor.execute("""
                UPDATE runs SET current_stage = 'planner', updated_at = ? WHERE run_id = ?
            """, (now, plan.run_id))
            conn.commit()
        return plan

    def get_plan(self, run_id: str) -> Optional[ImplementationPlan]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT data_json FROM plans WHERE run_id = ?", (run_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return ImplementationPlan.model_validate_json(row["data_json"])

    # --- Code Changes Methods ---
    def save_code_change(self, change: CodeChange) -> CodeChange:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO code_changes (id, run_id, file_path, action, original_content, new_content, diff_patch, lines_added, lines_removed, ast_valid, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    new_content=excluded.new_content,
                    diff_patch=excluded.diff_patch,
                    lines_added=excluded.lines_added,
                    lines_removed=excluded.lines_removed,
                    ast_valid=excluded.ast_valid
            """, (
                change.id, change.run_id, change.file_path, change.action,
                change.original_content, change.new_content, change.diff_patch,
                change.lines_added, change.lines_removed, 1 if change.ast_valid else 0,
                change.created_at
            ))
            cursor.execute("""
                UPDATE runs SET current_stage = 'coder', updated_at = ? WHERE run_id = ?
            """, (datetime.now().isoformat(), change.run_id))
            conn.commit()
        return change

    def get_code_changes(self, run_id: str) -> List[CodeChange]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM code_changes WHERE run_id = ? ORDER BY created_at ASC", (run_id,))
            rows = cursor.fetchall()
            return [
                CodeChange(
                    id=r["id"],
                    run_id=r["run_id"],
                    file_path=r["file_path"],
                    action=r["action"],
                    original_content=r["original_content"],
                    new_content=r["new_content"],
                    diff_patch=r["diff_patch"],
                    lines_added=r["lines_added"],
                    lines_removed=r["lines_removed"],
                    ast_valid=bool(r["ast_valid"]),
                    created_at=r["created_at"]
                )
                for r in rows
            ]

    # --- Test Results & Recovery Methods ---
    def save_test_result(self, result: TestRunResult) -> TestRunResult:
        result_json = result.model_dump_json()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO test_results (id, run_id, attempt_number, total_tests, passed_tests, failed_tests, duration_seconds, stdout, stderr, exit_code, status, data_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                result.id, result.run_id, result.attempt_number, result.total_tests,
                result.passed_tests, result.failed_tests, result.duration_seconds,
                result.stdout, result.stderr, result.exit_code, result.status,
                result_json, result.created_at
            ))
            cursor.execute("""
                UPDATE runs SET current_stage = 'testing', updated_at = ? WHERE run_id = ?
            """, (datetime.now().isoformat(), result.run_id))
            conn.commit()
        return result

    def get_test_results(self, run_id: str) -> List[TestRunResult]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT data_json FROM test_results WHERE run_id = ? ORDER BY attempt_number ASC", (run_id,))
            rows = cursor.fetchall()
            return [TestRunResult.model_validate_json(r["data_json"]) for r in rows]

    def save_recovery_attempt(self, attempt: RecoveryAttempt) -> RecoveryAttempt:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO recovery_attempts (id, run_id, attempt_number, failure_reason, diagnosis, root_cause_analysis, proposed_fix, files_modified_json, resolved, test_run_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                attempt.id, attempt.run_id, attempt.attempt_number, attempt.failure_reason,
                attempt.diagnosis, attempt.root_cause_analysis, attempt.proposed_fix,
                json.dumps(attempt.files_modified), 1 if attempt.resolved else 0,
                attempt.test_run_id, attempt.created_at
            ))
            conn.commit()
        return attempt

    def get_recovery_attempts(self, run_id: str) -> List[RecoveryAttempt]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM recovery_attempts WHERE run_id = ? ORDER BY attempt_number ASC", (run_id,))
            rows = cursor.fetchall()
            return [
                RecoveryAttempt(
                    id=r["id"],
                    run_id=r["run_id"],
                    attempt_number=r["attempt_number"],
                    failure_reason=r["failure_reason"],
                    diagnosis=r["diagnosis"],
                    root_cause_analysis=r["root_cause_analysis"] or "",
                    proposed_fix=r["proposed_fix"],
                    files_modified=json.loads(r["files_modified_json"] or "[]"),
                    resolved=bool(r["resolved"]),
                    test_run_id=r["test_run_id"],
                    created_at=r["created_at"]
                )
                for r in rows
            ]

    # --- Verification Methods ---
    def save_verification(self, report: VerificationReport) -> VerificationReport:
        report_json = report.model_dump_json()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO verifications (id, run_id, overall_verdict, pass_rate_percent, goal_drift_score, code_quality_score, security_verdict, data_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    overall_verdict=excluded.overall_verdict,
                    pass_rate_percent=excluded.pass_rate_percent,
                    goal_drift_score=excluded.goal_drift_score,
                    code_quality_score=excluded.code_quality_score,
                    security_verdict=excluded.security_verdict,
                    data_json=excluded.data_json
            """, (
                report.id, report.run_id, report.overall_verdict, report.pass_rate_percent,
                report.goal_drift_score, report.code_quality_score, report.security_verdict,
                report_json, report.created_at
            ))
            cursor.execute("""
                UPDATE runs SET current_stage = 'verifier', status = 'completed', updated_at = ? WHERE run_id = ?
            """, (datetime.now().isoformat(), report.run_id))
            conn.commit()
        return report

    def get_verification(self, run_id: str) -> Optional[VerificationReport]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT data_json FROM verifications WHERE run_id = ?", (run_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return VerificationReport.model_validate_json(row["data_json"])

    # --- Evaluation Methods ---
    def save_evaluation(self, eval_metrics: EvaluationMetrics) -> EvaluationMetrics:
        eval_json = eval_metrics.model_dump_json()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO evaluations (run_id, task_id, success_rate, execution_time_seconds, total_tool_calls, recovery_attempts_count, goal_drift_score, lines_added, lines_removed, tests_passed, tests_total, data_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    success_rate=excluded.success_rate,
                    execution_time_seconds=excluded.execution_time_seconds,
                    total_tool_calls=excluded.total_tool_calls,
                    recovery_attempts_count=excluded.recovery_attempts_count,
                    goal_drift_score=excluded.goal_drift_score,
                    lines_added=excluded.lines_added,
                    lines_removed=excluded.lines_removed,
                    tests_passed=excluded.tests_passed,
                    tests_total=excluded.tests_total,
                    data_json=excluded.data_json
            """, (
                eval_metrics.run_id, eval_metrics.task_id, eval_metrics.success_rate,
                eval_metrics.execution_time_seconds, eval_metrics.total_tool_calls,
                eval_metrics.recovery_attempts_count, eval_metrics.goal_drift_score,
                eval_metrics.lines_added, eval_metrics.lines_removed,
                eval_metrics.tests_passed, eval_metrics.tests_total,
                eval_json, eval_metrics.created_at
            ))
            conn.commit()
        return eval_metrics

    def get_evaluation(self, run_id: str) -> Optional[EvaluationMetrics]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT data_json FROM evaluations WHERE run_id = ?", (run_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return EvaluationMetrics.model_validate_json(row["data_json"])

    # --- Execution Logs ---
    def add_log(
        self,
        run_id: str,
        stage: str,
        agent_role: str,
        event_type: str,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ) -> ExecutionLogEntry:
        log_entry = ExecutionLogEntry(
            id=f"log_{uuid.uuid4().hex[:8]}",
            run_id=run_id,
            stage=stage,
            agent_role=agent_role,
            event_type=event_type,
            message=message,
            details=details,
            timestamp=datetime.now().isoformat()
        )
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO execution_logs (id, run_id, stage, agent_role, event_type, message, details_json, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                log_entry.id, log_entry.run_id, log_entry.stage, log_entry.agent_role,
                log_entry.event_type, log_entry.message,
                json.dumps(log_entry.details) if log_entry.details else None,
                log_entry.timestamp
            ))
            conn.commit()
        return log_entry

    def get_execution_logs(self, run_id: str, limit: int = 200) -> List[ExecutionLogEntry]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM execution_logs 
                WHERE run_id = ? 
                ORDER BY timestamp ASC 
                LIMIT ?
            """, (run_id, limit))
            rows = cursor.fetchall()
            return [
                ExecutionLogEntry(
                    id=r["id"],
                    run_id=r["run_id"],
                    timestamp=r["timestamp"],
                    stage=r["stage"],
                    agent_role=r["agent_role"],
                    event_type=r["event_type"],
                    message=r["message"],
                    details=json.loads(r["details_json"]) if r["details_json"] else None
                )
                for r in rows
            ]

    def get_aggregate_evaluations(self) -> Dict[str, Any]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_runs,
                    AVG(success_rate) as avg_success_rate,
                    AVG(execution_time_seconds) as avg_duration,
                    SUM(total_tool_calls) as total_tool_calls,
                    SUM(recovery_attempts_count) as total_recoveries,
                    AVG(goal_drift_score) as avg_drift
                FROM evaluations
            """)
            stats = dict(cursor.fetchone())
            
            # Fetch recent 10 evaluations for benchmarking chart
            cursor.execute("""
                SELECT r.run_id, r.title, r.task_id, e.success_rate, e.execution_time_seconds, 
                       e.total_tool_calls, e.recovery_attempts_count, e.goal_drift_score, 
                       e.lines_added, e.lines_removed, e.tests_passed, e.tests_total, r.created_at
                FROM evaluations e
                JOIN runs r ON e.run_id = r.run_id
                ORDER BY r.created_at DESC
                LIMIT 15
            """)
            recent_evals = [dict(r) for r in cursor.fetchall()]

            return {
                "aggregate_stats": stats,
                "recent_evaluations": recent_evals
            }

db_service = DatabaseService()
