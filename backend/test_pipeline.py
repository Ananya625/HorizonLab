import sys
import asyncio
import json
from typing import Optional
from app.services.orchestrator_service import orchestrator_service
from app.services.db import db_service

async def test_full_pipeline(repo_path: Optional[str] = None):
    print("==================================================")
    print("STARTING FULL END-TO-END CODING AGENT WORKFLOW TEST")
    print("==================================================")

    request_text = "Build a login API with JWT authentication using FastAPI. Implement user registration with password hashing, login endpoint returning JWT bearer token, protected route GET /api/auth/me, invalid credentials rejection (HTTP 401), expired token rejection, and automated pytest suite."

    print(f"\n[1] Task Prompt: '{request_text}'")
    print(f"[2] Repo Input: {repo_path or '(None - Will dynamically create a new isolated workspace folder)'}\n")

    record = await orchestrator_service.run_full_pipeline(
        request_text=request_text,
        repo_path=repo_path,
        model_name="qwen2.5-coder:1.5b",
        temperature=0.2,
        max_recovery_retries=3
    )

    print("\n--- Pipeline Execution Summary ---")
    print(f"Run ID: {record.run_id}")
    print(f"Task ID: {record.task_id}")
    print(f"Target Workspace: {record.repo_path}")
    print(f"Current Stage: {record.current_stage}")
    print(f"Status: {record.status}")
    print(f"Goal Model Version: {record.goal_model.goal_model_version if record.goal_model else 'N/A'}")
    print(f"Sub-Goals: {len(record.goal_model.sub_goals) if record.goal_model else 0}")
    print(f"Criteria: {len(record.goal_model.success_criteria) if record.goal_model else 0}")
    print(f"Hard Constraints: {len(record.goal_model.hard_constraints) if record.goal_model else 0}")
    print(f"Planned Steps: {len(record.plan.steps) if record.plan else 0}")
    print(f"Planned Files: {len(record.plan.planned_files) if record.plan else 0}")
    print(f"Generated Code Files: {len(record.code_changes)}")
    for change in record.code_changes:
        print(f"  - {change.file_path} ({change.action}): +{change.lines_added}/-{change.lines_removed} lines (AST valid: {change.ast_valid})")

    print(f"\nTest Runs Count: {len(record.test_results)}")
    if record.test_results:
        latest = record.test_results[-1]
        print(f"Latest Test Status: {latest.status} ({latest.passed_tests}/{latest.total_tests} passed in {latest.duration_seconds}s, exit code: {latest.exit_code})")
        for item in latest.test_items:
            print(f"    * {item.name} -> {item.status}")

    print(f"Recovery Attempts: {len(record.recovery_attempts)}")

    if record.verification:
        print(f"\nIndependent Verification Verdict: {record.verification.overall_verdict}")
        print(f"Criteria Pass Rate: {record.verification.pass_rate_percent}%")
        print(f"Goal Drift Score: {record.verification.goal_drift_score}%")
        print(f"Code Quality Score: {record.verification.code_quality_score}/10")
        print(f"Security Verdict: {record.verification.security_verdict}")
        print(f"Review Summary: {record.verification.review_summary}")

    if record.evaluation:
        print(f"\nEvaluation KPIs:")
        print(f"  * Success Rate: {record.evaluation.success_rate}%")
        print(f"  * Execution Time: {record.evaluation.execution_time_seconds}s")
        print(f"  * Total Tool Calls: {record.evaluation.total_tool_calls}")
        print(f"  * Recovery Attempts: {record.evaluation.recovery_attempts_count}")
        print(f"  * Tests Passed: {record.evaluation.tests_passed}/{record.evaluation.tests_total}")

    # Verify SQLite persistence
    persisted_record = db_service.get_run_record(record.run_id)
    assert persisted_record is not None, "Failed to retrieve persisted run from SQLite!"
    assert persisted_record.run_id == record.run_id
    assert len(persisted_record.code_changes) == len(record.code_changes)
    print("\n[SUCCESS] SQLite persistence verified! All data stored & retrieved successfully.")

if __name__ == "__main__":
    cli_repo = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(test_full_pipeline(repo_path=cli_repo))
