import asyncio
import os
import sys
import time
import json
from datetime import datetime

# Add backend directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.orchestrator_service import orchestrator_service
from app.services.workspace_service import workspace_service
from app.services.db import db_service
from app.services.telemetry_service import telemetry_manager

async def run_benchmark():
    sandbox_repo = workspace_service.get_default_repo_path()
    print(f"=== AgentEval-X Optimization Benchmark Suite ===")
    print(f"Target Sandbox Workspace: {sandbox_repo}")
    print(f"Timestamp: {datetime.now().isoformat()}\n")

    tasks = [
        {
            "id": "task_1_cold",
            "name": "Task 1 (Cold Start): Small isolated function",
            "prompt": "Implement a helper function multiply(a: float, b: float) -> float in app/service.py and test it in tests/test_service.py.",
            "type": "simple"
        },
        {
            "id": "task_1_warm",
            "name": "Task 1 (Warm Run): Small isolated function (repeat)",
            "prompt": "Implement a helper function power(base: float, exponent: int) -> float in app/service.py and test it in tests/test_service.py.",
            "type": "simple"
        },
        {
            "id": "task_2_bugfix",
            "name": "Task 2: Small bug fix",
            "prompt": "Fix bug in app/service.py where calculate_discount(price: float, discount_percent: float) returns negative price when discount is over 100%. Clamp discount between 0 and 100. Add tests in tests/test_service.py.",
            "type": "simple"
        },
        {
            "id": "task_3_multifile",
            "name": "Task 3: Multi-file change",
            "prompt": "Add user account status field with UserStatus enum in app/models.py, update user response serializer in app/serializers.py, and verify in tests/test_models.py.",
            "type": "medium"
        },
        {
            "id": "task_4_recovery",
            "name": "Task 4: Failing-test recovery task (Escalation)",
            "prompt": "Implement string sanitizer in app/service.py with strict validation for HTML tags and test in tests/test_service.py.",
            "type": "recovery"
        },
        {
            "id": "task_5_complex",
            "name": "Task 5: Complex feature (JWT Authentication Suite)",
            "prompt": "Implement complete JWT authentication with user registration, login, and token verification with password hashing and expiring tokens in app/auth.py, app/routes/auth_routes.py, app/main.py, and tests/test_auth.py.",
            "type": "complex"
        }
    ]

    results = []

    for idx, t in enumerate(tasks, 1):
        print(f"\n" + "="*70)
        print(f"RUNNING [{idx}/{len(tasks)}]: {t['name']}")
        print(f"Prompt: {t['prompt']}")
        print("="*70)

        t_start = time.time()
        run_record = await orchestrator_service.run_full_pipeline(
            request_text=t["prompt"],
            repo_path=sandbox_repo
        )
        total_wall_s = round(time.time() - t_start, 3)

        evaluation = run_record.evaluation
        telemetry = evaluation.telemetry if evaluation else {}
        counters = telemetry.get("counters", {})
        stage_durations = telemetry.get("stage_durations", {})
        model_calls = telemetry.get("model_calls", [])

        bench_item = {
            "task_id": t["id"],
            "name": t["name"],
            "total_wall_clock_seconds": total_wall_s,
            "status": run_record.status,
            "verdict": run_record.verification.overall_verdict if run_record.verification else "N/A",
            "success_rate": evaluation.success_rate if evaluation else 0,
            "stage_durations": stage_durations,
            "counters": {
                "model_calls": counters.get("model_calls", 0),
                "agent_invocations": counters.get("agent_invocations", 0),
                "repository_files_inspected": counters.get("repository_files_inspected", 0),
                "tool_calls": counters.get("tool_calls", 0),
                "retries": counters.get("retries", 0),
                "total_tokens_in": counters.get("total_tokens_in", 0),
                "total_tokens_out": counters.get("total_tokens_out", 0)
            },
            "model_calls_detail": model_calls,
            "tests_passed": evaluation.tests_passed if evaluation else 0,
            "tests_total": evaluation.tests_total if evaluation else 0
        }
        results.append(bench_item)

        print(f"\n--> Result for {t['name']}:")
        print(f"    Wall-Clock Latency: {total_wall_s}s")
        print(f"    Status: {run_record.status} | Verdict: {bench_item['verdict']}")
        print(f"    Model Calls: {counters.get('model_calls', 0)} | Files Inspected: {counters.get('repository_files_inspected', 0)} | Tool Calls: {counters.get('tool_calls', 0)}")
        print(f"    Tests Passed: {bench_item['tests_passed']}/{bench_item['tests_total']}")
        print(f"    Stage Durations: {json.dumps(stage_durations, indent=6)}")

    # Save benchmark results to disk
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "benchmark_results.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"\nAll benchmarks completed. Results written to: {out_path}")

if __name__ == "__main__":
    asyncio.run(run_benchmark())
