import time
from typing import Dict, Any, List, Optional
from datetime import datetime

class TelemetryTracker:
    def __init__(self, run_id: str, task_id: str):
        self.run_id = run_id
        self.task_id = task_id
        self.start_wall_time = time.time()
        self.end_wall_time: Optional[float] = None
        
        # Timing spans
        self.spans: List[Dict[str, Any]] = []
        
        # Telemetry counters
        self.model_calls_count = 0
        self.agent_invocations_count = 0
        self.repository_files_inspected = 0
        self.tool_calls_count = 0
        self.retries_count = 0
        self.duplicate_work_count = 0
        self.total_tokens_in = 0
        self.total_tokens_out = 0
        
        # Detailed model calls list
        self.model_calls: List[Dict[str, Any]] = []
        
        # Per-stage breakdown
        self.stage_durations: Dict[str, float] = {}

    def start_span(self, stage: str, operation: str) -> float:
        return time.time()

    def end_span(
        self,
        stage: str,
        operation: str,
        t_start: float,
        metadata: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None
    ) -> Dict[str, Any]:
        duration_ms = round((time.time() - t_start) * 1000, 2)
        duration_s = round(duration_ms / 1000.0, 3)
        
        self.stage_durations[stage] = round(self.stage_durations.get(stage, 0.0) + duration_s, 3)
        
        span_record = {
            "run_id": self.run_id,
            "stage": stage,
            "operation": operation,
            "duration_ms": duration_ms,
            "duration_seconds": duration_s,
            "metadata": metadata or {},
            "error": error,
            "timestamp": datetime.now().isoformat()
        }
        self.spans.append(span_record)
        return span_record

    def record_model_call(
        self,
        model_name: str,
        duration_ms: float,
        tokens_in: int,
        tokens_out: int,
        error_status: Optional[str] = None,
        tok_per_sec: float = 0.0,
        stage: str = "llm"
    ):
        self.model_calls_count += 1
        self.total_tokens_in += tokens_in
        self.total_tokens_out += tokens_out
        
        call_info = {
            "model_name": model_name,
            "stage": stage,
            "duration_ms": round(duration_ms, 2),
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "tok_per_sec": round(tok_per_sec, 1),
            "error_status": error_status,
            "timestamp": datetime.now().isoformat()
        }
        self.model_calls.append(call_info)

    def record_agent_invocation(self, agent_role: str):
        self.agent_invocations_count += 1

    def record_tool_call(self):
        self.tool_calls_count += 1

    def record_files_inspected(self, count: int):
        self.repository_files_inspected += count

    def record_retry(self):
        self.retries_count += 1

    def finalize(self) -> Dict[str, Any]:
        self.end_wall_time = time.time()
        total_duration_s = round(self.end_wall_time - self.start_wall_time, 3)
        
        return {
            "run_id": self.run_id,
            "task_id": self.task_id,
            "total_wall_clock_seconds": total_duration_s,
            "stage_durations": self.stage_durations,
            "counters": {
                "model_calls": self.model_calls_count,
                "agent_invocations": self.agent_invocations_count,
                "repository_files_inspected": self.repository_files_inspected,
                "tool_calls": self.tool_calls_count,
                "retries": self.retries_count,
                "duplicate_work": self.duplicate_work_count,
                "total_tokens_in": self.total_tokens_in,
                "total_tokens_out": self.total_tokens_out
            },
            "model_calls": self.model_calls,
            "spans": self.spans
        }

class TelemetryManager:
    def __init__(self):
        self._active_trackers: Dict[str, TelemetryTracker] = {}

    def get_or_create(self, run_id: str, task_id: str) -> TelemetryTracker:
        if run_id not in self._active_trackers:
            self._active_trackers[run_id] = TelemetryTracker(run_id, task_id)
        return self._active_trackers[run_id]

    def get(self, run_id: str) -> Optional[TelemetryTracker]:
        return self._active_trackers.get(run_id)

telemetry_manager = TelemetryManager()
