import json
import sqlite3

from app.models.schema import (
    CriterionVerification,
    EvaluationMetrics,
    VerificationReport,
)
from app.services.db import DatabaseService


def create_run(database, run_id):
    return database.create_or_update_run(
        run_id=run_id,
        task_id=f"task_{run_id}",
        title="Evaluation metric test",
        prompt="test metrics",
        repo_path=".",
    )


def test_old_saved_percentages_are_recomputed_from_captured_test_counts(tmp_path):
    database = DatabaseService(str(tmp_path / "evaluation.db"))
    create_run(database, "run-with-tests")
    create_run(database, "run-without-tests")
    database.save_evaluation(
        EvaluationMetrics(
            run_id="run-with-tests",
            task_id="task-run-with-tests",
            success_rate=100.0,
            goal_drift_score=15.5,
            tests_passed=1,
            tests_total=4,
        )
    )
    database.save_evaluation(
        EvaluationMetrics(
            run_id="run-without-tests",
            task_id="task-run-without-tests",
            success_rate=100.0,
            goal_drift_score=0.0,
            tests_passed=0,
            tests_total=0,
        )
    )
    with sqlite3.connect(database.db_path) as connection:
        connection.execute(
            "UPDATE evaluations SET data_json = ? WHERE run_id = ?",
            (
                '{"run_id":"run-with-tests","task_id":"task-run-with-tests"}',
                "run-with-tests",
            ),
        )

    assert database.get_evaluation("run-with-tests").success_rate == 25.0
    assert database.get_evaluation("run-with-tests").goal_drift_score is None
    assert database.get_evaluation("run-without-tests").success_rate is None

    aggregate = database.get_aggregate_evaluations()["aggregate_stats"]
    assert aggregate["avg_test_pass_rate"] == 25.0


def test_old_verification_claims_are_not_returned_as_measured_criteria(tmp_path):
    database = DatabaseService(str(tmp_path / "verification.db"))
    create_run(database, "run-legacy-verifier")
    database.save_verification(
        VerificationReport(
            id="verification-legacy",
            run_id="run-legacy-verifier",
            overall_verdict="VERIFIED_PASSED",
            pass_rate_percent=100.0,
            goal_drift_score=0.0,
            code_quality_score=9.0,
            security_verdict="SECURE_PASS",
            review_summary="Legacy values",
            criteria_evaluations=[
                CriterionVerification(
                    criterion_id="criterion-1",
                    criterion_description="Criterion",
                    verdict="PASS",
                    confidence_score=0.98,
                    evidence="Legacy global test status",
                )
            ],
        )
    )

    report = database.get_verification("run-legacy-verifier")

    assert report.overall_verdict == "TESTS_NOT_RUN"
    assert report.pass_rate_percent is None
    assert report.goal_drift_score is None
    assert report.code_quality_score is None
    assert report.criteria_evaluations[0].verdict == "NOT_VERIFIED"
    assert report.criteria_evaluations[0].confidence_score is None


def test_resaving_evaluation_updates_timestamp_with_current_execution(tmp_path):
    database = DatabaseService(str(tmp_path / "evaluation-rerun.db"))
    create_run(database, "run-rerun")
    first = EvaluationMetrics(
        run_id="run-rerun",
        task_id="task-run-rerun",
        execution_time_seconds=47000.0,
        created_at="2026-10-12T20:51:09",
    )
    database.save_evaluation(first)

    second = EvaluationMetrics(
        run_id="run-rerun",
        task_id="task-run-rerun",
        execution_time_seconds=63.4,
        created_at="2026-10-13T09:58:02",
    )
    database.save_evaluation(second)

    with sqlite3.connect(database.db_path) as connection:
        row = connection.execute(
            "SELECT execution_time_seconds, created_at FROM evaluations WHERE run_id = ?",
            ("run-rerun",),
        ).fetchone()

    assert row == (63.4, "2026-10-13T09:58:02")
    benchmark = database.get_aggregate_evaluations()["recent_evaluations"][0]
    assert benchmark["duration_status"] == "measured"
    assert benchmark["execution_time_seconds"] == 63.4


def test_legacy_rerun_duration_is_reconstructed_from_latest_execution_logs(tmp_path):
    database = DatabaseService(str(tmp_path / "evaluation-legacy-rerun.db"))
    create_run(database, "run-valid")
    create_run(database, "run-stale")
    database.save_evaluation(
        EvaluationMetrics(
            run_id="run-valid",
            task_id="task-run-valid",
            execution_time_seconds=20.0,
            created_at="2026-10-13T09:00:00",
        )
    )
    database.save_evaluation(
        EvaluationMetrics(
            run_id="run-stale",
            task_id="task-run-stale",
            execution_time_seconds=47299.3,
            created_at="2026-10-12T20:51:09",
        )
    )
    with sqlite3.connect(database.db_path) as connection:
        row = connection.execute(
            "SELECT data_json FROM evaluations WHERE run_id = ?",
            ("run-stale",),
        ).fetchone()
        data = json.loads(row[0])
        data["created_at"] = "2026-10-13T09:58:02"
        connection.execute(
            "UPDATE evaluations SET data_json = ? WHERE run_id = ?",
            (json.dumps(data), "run-stale"),
        )
    with sqlite3.connect(database.db_path) as connection:
        connection.execute(
            """INSERT INTO execution_logs
               (id, run_id, timestamp, stage, agent_role, event_type, message)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                "legacy-start",
                "run-stale",
                "2026-10-13T09:00:00",
                "workspace",
                "System Orchestrator",
                "info",
                "Initialized autonomous coding workflow run 'run-stale'.",
            ),
        )
        connection.execute(
            """INSERT INTO execution_logs
               (id, run_id, timestamp, stage, agent_role, event_type, message)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                "legacy-finish",
                "run-stale",
                "2026-10-13T09:00:20",
                "verifier",
                "Independent Code Reviewer",
                "success",
                "Verification Complete: TESTS_PASSED",
            ),
        )

    dashboard = database.get_aggregate_evaluations()
    assert dashboard["aggregate_stats"]["avg_duration"] == 20.0
    stale = next(
        record
        for record in dashboard["recent_evaluations"]
        if record["run_id"] == "run-stale"
    )
    assert stale["execution_time_seconds"] == 20.0
    assert stale["duration_status"] == "reconstructed"
    with sqlite3.connect(database.db_path) as connection:
        connection.row_factory = sqlite3.Row
        assert database.get_verified_execution_duration(connection, "run-stale") == 20.0


def test_unverifiable_legacy_duration_is_not_reported(tmp_path):
    database = DatabaseService(str(tmp_path / "evaluation-unverified.db"))
    create_run(database, "run-unverified")
    database.save_evaluation(
        EvaluationMetrics(
            run_id="run-unverified",
            task_id="task-run-unverified",
            execution_time_seconds=47299.3,
            created_at="2026-10-12T20:51:09",
        )
    )
    with sqlite3.connect(database.db_path) as connection:
        row = connection.execute(
            "SELECT data_json FROM evaluations WHERE run_id = ?",
            ("run-unverified",),
        ).fetchone()
        data = json.loads(row[0])
        data["created_at"] = "2026-10-13T09:58:02"
        connection.execute(
            "UPDATE evaluations SET data_json = ? WHERE run_id = ?",
            (json.dumps(data), "run-unverified"),
        )

    with database._get_connection() as connection:
        assert database.get_verified_execution_duration(
            connection, "run-unverified"
        ) is None

    recent = database.get_aggregate_evaluations()["recent_evaluations"]
    unverified = next(row for row in recent if row["run_id"] == "run-unverified")
    assert unverified["execution_time_seconds"] is None
    assert unverified["duration_status"] == "unverified_legacy"
