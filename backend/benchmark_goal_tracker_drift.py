import asyncio
import os
import sys
import time
import json
import statistics
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.orchestrator_service import orchestrator_service
from app.services.workspace_service import workspace_service
from app.services.goal_tracker_service import goal_tracker_service
from app.services.drift_controller_service import drift_controller_service

async def run_goal_tracker_benchmarks():
    print("=" * 70)
    print("AgentEval-X: Goal Tracker & Drift Control Latency Benchmark")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("=" * 70)

    # 1. Benchmark: Simple Task (Repeated 3 runs for median)
    simple_prompt = "Implement a helper function add(a: int, b: int) -> int in app/service.py and test in tests/test_service.py"
    simple_runs = []

    print("\n>>> Measuring Simple Task (3 repeated runs for median)...")
    for r in range(1, 4):
        t0 = time.time()
        record = await orchestrator_service.run_full_pipeline(
            request_text=simple_prompt,
            repo_path=workspace_service.get_default_repo_path()
        )
        wall_sec = round(time.time() - t0, 3)
        tracking = goal_tracker_service.get_state(record.run_id)
        
        telemetry = record.evaluation.telemetry if record.evaluation else {}
        counters = telemetry.get("counters", {})

        run_info = {
            "run": r,
            "run_id": record.run_id,
            "wall_sec": wall_sec,
            "status": record.status,
            "verdict": record.verification.overall_verdict if record.verification else "N/A",
            "model_calls": counters.get("model_calls", 0),
            "tool_calls": counters.get("tool_calls", 0),
            "retries": counters.get("retries", 0),
            "subtasks_count": len(tracking.ordered_subtasks) if tracking else 0,
            "action_history_len": len(tracking.action_history) if tracking else 0,
            "criteria_verified": all(c.status == "passed" for c in tracking.acceptance_criteria) if tracking else False
        }
        simple_runs.append(run_info)
        print(f"  Run #{r}: Latency = {wall_sec}s | Status = {record.status} | Verdict = {run_info['verdict']} | Model Calls = {run_info['model_calls']} | Tool Calls = {run_info['tool_calls']}")

    simple_latencies = [x["wall_sec"] for x in simple_runs]
    simple_median = round(statistics.median(simple_latencies), 3)
    print(f"\n--> Simple Task Median Latency: {simple_median}s (Runs: {simple_latencies})")

    # 2. Benchmark: Complex Multi-File Task (JWT Authentication)
    complex_prompt = "Implement complete JWT authentication with user registration, login, and token verification with password hashing and expiring tokens in app/auth.py, app/routes/auth_routes.py, app/main.py, and tests/test_auth.py."
    print("\n>>> Measuring Complex Multi-File Task...")
    t0 = time.time()
    complex_record = await orchestrator_service.run_full_pipeline(
        request_text=complex_prompt,
        repo_path=workspace_service.get_default_repo_path(),
        model_name="qwen2.5-coder:7b"
    )
    complex_wall_sec = round(time.time() - t0, 3)
    complex_tracking = goal_tracker_service.get_state(complex_record.run_id)
    complex_telemetry = complex_record.evaluation.telemetry if complex_record.evaluation else {}
    complex_counters = complex_telemetry.get("counters", {})

    complex_info = {
        "run_id": complex_record.run_id,
        "wall_sec": complex_wall_sec,
        "status": complex_record.status,
        "verdict": complex_record.verification.overall_verdict if complex_record.verification else "N/A",
        "model_calls": complex_counters.get("model_calls", 0),
        "tool_calls": complex_counters.get("tool_calls", 0),
        "retries": complex_counters.get("retries", 0),
        "subtasks_count": len(complex_tracking.ordered_subtasks) if complex_tracking else 0,
        "action_history_len": len(complex_tracking.action_history) if complex_tracking else 0,
        "criteria_verified": all(c.status == "passed" for c in complex_tracking.acceptance_criteria) if complex_tracking else False
    }
    print(f"--> Complex Task Latency: {complex_wall_sec}s | Status = {complex_record.status} | Verdict = {complex_info['verdict']} | Model Calls = {complex_info['model_calls']} | Tool Calls = {complex_info['tool_calls']}")

    # 3. Micro-benchmark: Deterministic Drift Check & Goal Tracker Overhead
    print("\n>>> Measuring Micro-Benchmark Overhead of Drift Check & Goal Tracker...")
    overhead_times = []
    dummy_run = "micro_overhead_test"
    goal_tracker_service.initialize_task(
        run_id=dummy_run,
        task_id="task_micro",
        original_request="Test micro-overhead",
        complexity_profile="simple"
    )
    for _ in range(100):
        t_micro = time.perf_counter()
        drift_controller_service.check_action(dummy_run, "file_write", "app/service.py", payload_str="x = 1")
        drift_controller_service.validate_result(dummy_run, "file_write", "app/service.py", True)
        overhead_times.append(time.perf_counter() - t_micro)

    median_micro_ms = round(statistics.median(overhead_times) * 1000, 3)
    p95_micro_ms = round(statistics.quantiles(overhead_times, n=20)[18] * 1000, 3)
    print(f"--> Deterministic Policy Overhead per Action: Median = {median_micro_ms}ms, P95 = {p95_micro_ms}ms")

    # Save summary
    benchmark_report = {
        "timestamp": datetime.now().isoformat(),
        "simple_task": {
            "median_runtime_seconds": simple_median,
            "individual_runs_seconds": simple_latencies,
            "details": simple_runs
        },
        "complex_task": complex_info,
        "drift_and_tracker_overhead_ms": {
            "median_ms": median_micro_ms,
            "p95_ms": p95_micro_ms
        }
    }

    out_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "goal_tracker_benchmark_results.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(benchmark_report, f, indent=2)

    print(f"\nBenchmark results successfully written to: {out_file}")

if __name__ == "__main__":
    asyncio.run(run_goal_tracker_benchmarks())
