import os
import json
import sqlite3
import uuid
from contextlib import nullcontext, contextmanager
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
DB_PATH = os.environ.get('AGENTEVAL_DB_PATH', os.path.join(DB_DIR, "agent_eval.db"))

class DatabaseService:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_db()

    @contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            from .workflow_store import initialize
            initialize(conn)
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
                    error_summary TEXT,
                    subsequent_test_run_id TEXT,
                    test_result_status TEXT,
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

            columns = {r[1] for r in cursor.execute('PRAGMA table_info(recovery_attempts)')}
            for name in ('error_summary', 'subsequent_test_run_id', 'test_result_status', 'data_json'):
                if name not in columns:
                    cursor.execute(f'ALTER TABLE recovery_attempts ADD COLUMN {name} TEXT')
            cursor.execute('CREATE TABLE IF NOT EXISTS experiment_runs (experiment_id TEXT PRIMARY KEY, manifest_json TEXT NOT NULL, data_json TEXT NOT NULL, created_at TEXT NOT NULL)')
            cursor.execute('CREATE TABLE IF NOT EXISTS evaluation_history (id INTEGER PRIMARY KEY, run_id TEXT NOT NULL, data_json TEXT NOT NULL, reason TEXT NOT NULL, created_at TEXT NOT NULL)')
            cursor.execute('CREATE TABLE IF NOT EXISTS benchmark_checkpoints (run_id TEXT PRIMARY KEY, data_json TEXT NOT NULL, updated_at TEXT NOT NULL)')
            cursor.execute('CREATE TABLE IF NOT EXISTS benchmark_events (run_id TEXT NOT NULL, event_id TEXT NOT NULL, data_json TEXT NOT NULL, PRIMARY KEY(run_id, event_id))')
            cursor.execute('CREATE TABLE IF NOT EXISTS benchmark_pilot_budgets (pilot_id TEXT PRIMARY KEY, data_json TEXT NOT NULL)')
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
                metadata=json.loads(row['metadata_json'] or '{}'),
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
    def save_goal_model(self, model: GoalModel, expected_version=None, expected_revision=None) -> GoalModel:
        now = datetime.now().isoformat()
        model.updated_at = now
        model_json = model.model_dump_json()
        
        with self._get_connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            if expected_version is not None:
                row = conn.execute('SELECT data_json FROM goal_models WHERE run_id=?', (model.run_id,)).fetchone()
                if not row or json.loads(row[0])['goal_model_version'] != expected_version:
                    raise ValueError('Goal changed concurrently; reload before editing')
            if expected_revision is not None:
                from .workflow_service import goal_revision
                row = conn.execute('SELECT data_json FROM goal_models WHERE run_id=?', (model.run_id,)).fetchone()
                if not row or goal_revision(GoalModel.model_validate_json(row[0])) != expected_revision:
                    raise ValueError('Goal changed concurrently; reload before editing')
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

        from .workflow_service import workflow
        try:
            gr, pr = workflow.snapshots(model.run_id)
            workflow.emit(model.run_id, 'notice', goal_revision=gr, plan_revision=pr,
                reason='requirements_changed', data={'goal_version':model.goal_model_version, 'reported_status':{g.id:g.status for g in model.sub_goals}})
        except Exception:
            pass
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
        from .workflow_service import goal_revision
        goal = self.get_goal_model(plan.run_id)
        if plan.goal_revision is None and goal and plan.goal_model_version == goal.goal_model_version:
            plan.goal_revision = goal_revision(goal)
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
            cursor.execute("SELECT data_json FROM test_results WHERE run_id = ? ORDER BY created_at ASC, rowid ASC", (run_id,))
            rows = cursor.fetchall()
            return [TestRunResult.model_validate_json(r["data_json"]) for r in rows]

    def save_recovery_attempt(self, attempt: RecoveryAttempt) -> RecoveryAttempt:
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Check if this attempt outcome already exists to avoid duplicates
            cursor.execute("""
                SELECT id FROM recovery_attempts 
                WHERE id = ? OR (run_id = ? AND attempt_number = ?)
            """, (attempt.id, attempt.run_id, attempt.attempt_number))
            existing = cursor.fetchone()

            files_modified_json = json.dumps(attempt.files_modified)
            resolved_int = 1 if attempt.resolved else 0
            err_summary = attempt.error_summary or attempt.failure_reason

            if existing:
                existing_id = existing["id"]
                cursor.execute("""
                    UPDATE recovery_attempts SET
                        attempt_number = ?,
                        failure_reason = ?,
                        diagnosis = ?,
                        root_cause_analysis = ?,
                        proposed_fix = ?,
                        files_modified_json = ?,
                        resolved = ?,
                        test_run_id = ?,
                        error_summary = ?,
                        subsequent_test_run_id = ?,
                        test_result_status = ?,
                        created_at = ?
                    WHERE id = ?
                """, (
                    attempt.attempt_number, attempt.failure_reason, attempt.diagnosis,
                    attempt.root_cause_analysis or "", attempt.proposed_fix, files_modified_json,
                    resolved_int, attempt.test_run_id, err_summary,
                    attempt.subsequent_test_run_id, attempt.test_result_status,
                    attempt.created_at, existing_id
                ))
            else:
                cursor.execute("""
                    INSERT INTO recovery_attempts (
                        id, run_id, attempt_number, failure_reason, diagnosis,
                        root_cause_analysis, proposed_fix, files_modified_json,
                        resolved, test_run_id, error_summary, subsequent_test_run_id,
                        test_result_status, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    attempt.id, attempt.run_id, attempt.attempt_number, attempt.failure_reason,
                    attempt.diagnosis, attempt.root_cause_analysis or "", attempt.proposed_fix,
                    files_modified_json, resolved_int, attempt.test_run_id,
                    err_summary, attempt.subsequent_test_run_id, attempt.test_result_status,
                    attempt.created_at
                ))
            stored_id = existing['id'] if existing else attempt.id
            attempt = attempt.model_copy(update={'id':stored_id})
            cursor.execute('UPDATE recovery_attempts SET data_json=? WHERE id=?', (attempt.model_dump_json(), stored_id))
            conn.commit()
        return attempt

    def get_recovery_attempts(self, run_id: str) -> List[RecoveryAttempt]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM recovery_attempts WHERE run_id = ? ORDER BY attempt_number ASC", (run_id,))
            rows = cursor.fetchall()
            if not rows:
                return []

            col_names = set(rows[0].keys()) if rows else set()
            attempts = []
            for r in rows:
                if r['data_json']:
                    attempts.append(RecoveryAttempt.model_validate_json(r['data_json']))
                    continue
                err_summary = r["error_summary"] if "error_summary" in col_names and r["error_summary"] else r["failure_reason"]
                sub_test_id = r["subsequent_test_run_id"] if "subsequent_test_run_id" in col_names else None
                test_status = r["test_result_status"] if "test_result_status" in col_names else None
                resolved_bool = bool(r["resolved"])

                if not test_status:
                    if resolved_bool:
                        test_status = "PASSED"
                    elif sub_test_id is not None:
                        test_status = "FAILED"
                    else:
                        test_status = None

                attempts.append(
                    RecoveryAttempt(
                        id=r["id"],
                        run_id=r["run_id"],
                        attempt_number=r["attempt_number"],
                        failure_reason=r["failure_reason"],
                        diagnosis=r["diagnosis"],
                        root_cause_analysis=r["root_cause_analysis"] or "",
                        proposed_fix=r["proposed_fix"],
                        files_modified=json.loads(r["files_modified_json"] or "[]"),
                        resolved=resolved_bool,
                        test_run_id=r["test_run_id"],
                        error_summary=err_summary,
                        subsequent_test_run_id=sub_test_id,
                        test_result_status=test_status,
                        created_at=r["created_at"]
                    )
                )
            return attempts

    # --- Verification Methods ---
    def save_verification(self, report: VerificationReport, connection=None) -> VerificationReport:
        report_json = report.model_dump_json()
        with (nullcontext(connection) if connection is not None else self._get_connection()) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO verifications (id, run_id, overall_verdict, pass_rate_percent, goal_drift_score, code_quality_score, security_verdict, data_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    id=excluded.id,
                    created_at=excluded.created_at,
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
                UPDATE runs SET current_stage = 'verifier', updated_at = ? WHERE run_id = ?
            """, (datetime.now().isoformat(), report.run_id))
            if connection is None:
                conn.commit()
        return report

    def get_verification(self, run_id: str) -> Optional[VerificationReport]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT data_json FROM verifications WHERE run_id = ?", (run_id,))
            row = cursor.fetchone()
            if not row:
                return None
            report = VerificationReport.model_validate_json(row["data_json"])
            evaluation = conn.execute('SELECT data_json FROM evaluations WHERE run_id=?', (run_id,)).fetchone()
            evidence = json.loads(evaluation[0]) if evaluation else {}
            if evidence.get('evidence_stale') or evidence.get('outcome') in ('error', 'budget_exceeded'):
                report = report.model_copy(update={
                    'overall_verdict':'UNVERIFIED', 'verified_success':None,
                    'pass_rate_percent':None, 'goal_drift_score':None,
                    'code_quality_score':None, 'security_verdict':'UNVERIFIED',
                    'criteria_evaluations':[c.model_copy(update={'verdict':'UNVERIFIED', 'confidence_score':None, 'evidence':'Previous evidence is stale'}) for c in report.criteria_evaluations],
                    'constraint_compliances':[c.model_copy(update={'compliant':None, 'notes':'Previous evidence is stale'}) for c in report.constraint_compliances],
                    'review_summary':'Previous evidence is stale or a later stage failed. Reverify the current state.'})
            return report

    # --- Evaluation Methods ---
    def save_evaluation(self, eval_metrics: EvaluationMetrics, connection=None) -> EvaluationMetrics:
        eval_json = eval_metrics.model_dump_json()
        with (nullcontext(connection) if connection is not None else self._get_connection()) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO evaluations (run_id, task_id, success_rate, execution_time_seconds, total_tool_calls, recovery_attempts_count, goal_drift_score, lines_added, lines_removed, tests_passed, tests_total, data_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    created_at=excluded.created_at,
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
            if connection is None:
                conn.commit()
        return eval_metrics

    def update_metadata(self, run_id: str, **updates):
        with self._get_connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            row = conn.execute('SELECT metadata_json FROM runs WHERE run_id=?', (run_id,)).fetchone()
            if not row:
                raise ValueError('Unknown run')
            metadata = json.loads(row[0] or '{}')
            metadata.update(updates)
            conn.execute('UPDATE runs SET metadata_json=?, updated_at=? WHERE run_id=?',
                         (json.dumps(metadata), datetime.now().isoformat(), run_id))

    def invalidate_evaluation(self, run_id, reason):
        previous = self.get_evaluation(run_id)
        if previous is None or previous.evidence_stale:
            return
        with self._get_connection() as conn:
            conn.execute('INSERT INTO evaluation_history (run_id, data_json, reason, created_at) VALUES (?, ?, ?, ?)',
                         (run_id, previous.model_dump_json(), reason, datetime.now().isoformat()))
            revised = previous.model_copy(update={'evidence_stale':True, 'verified_success':None,
                'outcome':'unverified', 'success_rate':None, 'termination_reason':reason})
            self.save_evaluation(revised, connection=conn)

    def finalize_run(self, metrics: EvaluationMetrics, report: Optional[VerificationReport] = None):
        if report and report.run_id != metrics.run_id:
            raise ValueError('Report/evaluation run mismatch')
        with self._get_connection() as conn:
            row = conn.execute('SELECT task_id FROM runs WHERE run_id=?', (metrics.run_id,)).fetchone()
            if not row or row[0] != metrics.task_id:
                raise ValueError('Unknown or mismatched task')
            if report:
                self.save_verification(report, connection=conn)
            self.save_evaluation(metrics, connection=conn)
            status = 'failed' if metrics.outcome in ('failed', 'error', 'budget_exceeded') else 'completed'
            conn.execute('UPDATE runs SET current_stage=?, status=?, updated_at=? WHERE run_id=?',
                ('completed', status, datetime.now().isoformat(), metrics.run_id))

    def save_experiment(self, experiment_id, manifest, report, connection=None):
        with (nullcontext(connection) if connection is not None else self._get_connection()) as conn:
            conn.execute('INSERT INTO experiment_runs VALUES (?, ?, ?, ?) ON CONFLICT(experiment_id) DO UPDATE SET data_json=excluded.data_json',
                (experiment_id, json.dumps(manifest), json.dumps(report), datetime.now().isoformat()))

    def get_experiments(self):
        with self._get_connection() as conn:
            return [json.loads(r[0]) for r in conn.execute('SELECT data_json FROM experiment_runs ORDER BY created_at DESC')]

    def save_benchmark_checkpoint(self, run_id, state, events=(), connection=None):
        """Checkpoint and append-only evidence commit together; event IDs are idempotent."""
        with (nullcontext(connection) if connection is not None else self._get_connection()) as conn:
            if connection is None:
                conn.execute('BEGIN IMMEDIATE')
            for event in events:
                encoded = json.dumps(event, sort_keys=True, allow_nan=False)
                old = conn.execute('SELECT data_json FROM benchmark_events WHERE run_id=? AND event_id=?', (run_id, event['event_id'])).fetchone()
                if old and old[0] != encoded:
                    raise ValueError('Existing benchmark evidence cannot be rewritten')
                conn.execute('INSERT OR IGNORE INTO benchmark_events VALUES (?, ?, ?)', (run_id, event['event_id'], encoded))
                if event['kind'] == 'tool':
                    details = dict(event['data'], trace_step=event['step'], task_id=event['task_id'], agent_id=event.get('agent_id', 'benchmark-agent'))
                    conn.execute('INSERT OR IGNORE INTO execution_logs VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                        (f"benchlog_{run_id}_{event['event_id']}", run_id, 'benchmark', 'Benchmark Agent', 'tool_call', details['tool'], json.dumps(details), event['timestamp']))
            if state is not None:
                conn.execute('INSERT INTO benchmark_checkpoints VALUES (?, ?, ?) ON CONFLICT(run_id) DO UPDATE SET data_json=excluded.data_json, updated_at=excluded.updated_at',
                    (run_id, json.dumps(state, allow_nan=False), datetime.now().isoformat()))

    def get_benchmark_checkpoint(self, run_id):
        with self._get_connection() as conn:
            row = conn.execute('SELECT data_json FROM benchmark_checkpoints WHERE run_id=?', (run_id,)).fetchone()
            return json.loads(row[0]) if row else None

    def get_benchmark_events(self, run_id):
        with self._get_connection() as conn:
            return [json.loads(row[0]) for row in conn.execute('SELECT data_json FROM benchmark_events WHERE run_id=? ORDER BY rowid', (run_id,))]

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
            cursor.execute('BEGIN IMMEDIATE')
            run = cursor.execute('SELECT task_id FROM runs WHERE run_id=?', (run_id,)).fetchone()
            if not run:
                raise ValueError('Cannot log an unknown run')
            step = cursor.execute('SELECT COUNT(*) FROM execution_logs WHERE run_id=?', (run_id,)).fetchone()[0] + 1
            log_entry.details = dict(details or {}, trace_step=step, task_id=run['task_id'], agent_id=(details or {}).get('agent_id', agent_role))
            log_entry.task_id, log_entry.step, log_entry.agent_id = run['task_id'], step, log_entry.details['agent_id']
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

    def get_execution_logs(self, run_id: str, limit: Optional[int] = None, offset: int = 0) -> List[ExecutionLogEntry]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM execution_logs 
                WHERE run_id = ? 
                ORDER BY timestamp DESC, rowid DESC
                LIMIT ? OFFSET ?
            """, (run_id, limit if limit is not None else -1, offset))
            rows = list(reversed(cursor.fetchall()))
            return [
                ExecutionLogEntry(
                    id=r["id"],
                    run_id=r["run_id"],
                    timestamp=r["timestamp"],
                    stage=r["stage"],
                    agent_role=r["agent_role"],
                    event_type=r["event_type"],
                    message=r["message"],
                    details=json.loads(r["details_json"]) if r["details_json"] else None,
                    task_id=json.loads(r['details_json'] or '{}').get('task_id'),
                    step=json.loads(r['details_json'] or '{}').get('trace_step'),
                    agent_id=json.loads(r['details_json'] or '{}').get('agent_id'),
                    sub_goal_id=json.loads(r['details_json'] or '{}').get('sub_goal_id'),
                )
                for r in rows
            ]

    def get_aggregate_evaluations(self) -> Dict[str, Any]:
        with self._get_connection() as conn:
            rows = conn.execute('SELECT r.run_id, r.title, r.status, e.data_json FROM runs r LEFT JOIN evaluations e ON e.run_id=r.run_id ORDER BY r.created_at DESC').fetchall()
        evaluations = [dict(json.loads(r['data_json']), title=r['title']) for r in rows if r['data_json']]
        current = [e for e in evaluations if e.get('metric_version') == '2']
        successes = sum(e.get('verified_success') is True for e in current)
        durations = [e['execution_time_seconds'] for e in current if e.get('execution_time_seconds') is not None]
        drift = [e['goal_drift_score'] for e in current if e.get('goal_drift_score') is not None and not e.get('evidence_stale')]
        calls = [e['total_tool_calls'] for e in current if e.get('total_tool_calls') is not None]
        modes = []
        for mode in sorted({e.get('execution_mode', 'unknown') for e in current}):
            population = [e for e in current if e.get('execution_mode', 'unknown') == mode]
            verified = sum(e.get('verified_success') is True for e in population)
            modes.append({'execution_mode':mode, 'sample_count':len(population),
                          'verified_successes':verified, 'verified_success_rate':verified/len(population)})
        return {'aggregate_stats': {
            'total_runs': len(rows), 'evaluated_runs': len(current),
            'legacy_runs': len(evaluations)-len(current), 'unevaluated_runs': len(rows)-len(evaluations),
            'verified_successes': successes,
            'unverified_runs': sum(e.get('verified_success') is None for e in current),
            'avg_success_rate': successes / len(current) * 100 if current else None,
            'avg_duration': sum(durations)/len(durations) if durations else None,
            'total_tool_calls': sum(calls) if calls else None,
            'avg_drift': sum(drift)/len(drift) if drift else None,
            'total_recoveries': sum(e.get('recovery_attempts_count', 0) for e in current),
            'population': 'Current metric-version evaluations; unknown outcomes remain in denominator. Legacy and pending runs reported separately.'
        }, 'by_execution_mode': modes, 'recent_evaluations': evaluations[:15]}

db_service = DatabaseService()
