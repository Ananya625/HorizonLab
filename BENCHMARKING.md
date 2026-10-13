# Benchmarking implementation and handoff

The benchmark supports the original deterministic suite and version-two studies covering all seven benchmark categories. Version two adds semantic subtasks, memory probes, stress conditions, resumable execution, an agent adapter contract, labeled-event analysis, capability history, and a budgeted local Ollama pilot. Scripted fixtures validate the harness; they do not establish learned-agent performance or completion of teammate-owned modules.

## Run the suite

Start the backend and frontend using the README instructions, open **Evaluation**, and use **Controlled benchmarks → Run comparison**. Select a task, fault, and repetition count. The panel compares three scripted strategies at 5 and 15 planned actions. Saved experiments and complete JSON exports are available in the same panel.

For a separate database and reproducible report, run from `backend` with the project Python environment activated:

```powershell
python -m app.benchmark_cli --fault none --repetitions 2 --seed 42 --database ../output/benchmarks/validation.sqlite3 --output ../output/benchmarks/clean.json
python -m app.benchmark_cli --fault transient --repetitions 2 --seed 42 --database ../output/benchmarks/validation.sqlite3 --output ../output/benchmarks/transient.json
python -m app.benchmark_cli --fault timeout_after_commit --repetitions 2 --seed 42 --database ../output/benchmarks/validation.sqlite3 --output ../output/benchmarks/after-commit.json
```

Each command creates 60 independent trial workspaces: five tasks × two lengths × two repetitions × three strategies. The database, reports, and workspaces under `output/benchmarks` are ignored by Git. These commands were used for validation without changing the existing application database. The dashboard uses the backend's configured database; set `AGENTEVAL_DB_PATH` before starting it to use the validation database instead.

The fixtures cover addition, empty-list averaging, stable deduplication, clamping, and Unicode case folding. A trial reads the initial source, applies a fixed trusted patch, checks behavior, commits, and notifies. Longer tasks add read actions; they test longer action sequences, not greater programming difficulty. Seeds control operation identities; task semantics and faults are deterministic. Run IDs and timings vary between executions.

That length description applies to the original version-one suite. In **Benchmark studies and pilot reports**, version-two longer tasks require dependent arithmetic checkpoints using an instruction disclosed near the start. Sustained-correctness studies place additional checkpoints after the commit/recovery point. Memory probes check the early rule and publication tag after intervening actions. These are controlled reasoning/retention probes, not realistic large-repository programming tasks.

## Pilot status — updated 13 October 2026

The approved smaller model is `qwen3:1.7b`. Following two Qwen3 8B timeouts,
`backend/benchmarks/qwen3_1_7b_remaining_pilot.json` conservatively allowed only
one remaining trial, 13 calls, 4,000 generated tokens and 1,000 per call.
That trial passed in 21.50 seconds: 5 model calls, 148 generated tokens,
2,796 input tokens, 5 tool actions, all 3 protected behavior tests passed and
no duplicate effects. This verifies simulator operation, not Python synthesis.
Its report is `output/benchmarks/qwen3-small-results-2026-10-13.json`.

Across all three attempts, 7 calls were used. Token accounting retains 2,000
tokens for earlier unknown usage in addition to 148 known generated tokens.
The attempted-trial allowance is exhausted; do not start another trial without
new authorization, even though some call/token allowance remains.

At the user's request, old run histories were cleared with recovery backups in
`output/result-backups-2026-10-13/`; older JSON reports were moved there too.
The active pilot database retains all budget ledgers and the new successful run.
The application database is separate, so this CLI pilot does not automatically
appear in its dashboard. For readout, use the exported report or start a backend
with `AGENTEVAL_DB_PATH` pointing to the pilot database. Do not rerun the trial
merely to display its results.

Tests use real temporary SQLite databases under ignored `backend/.test-tmp/`.
If Windows sandboxing stalls asyncio's local socket setup, scoped permission
is needed for the test process; no database mock or global permission weakening
is required. See `PROJECT_REPAIR_PLAN.md` for verification and remaining limits.

## Original Qwen3 8B pilot configuration (historical)

The approved manifest is `backend/benchmarks/qwen3_8b_pilot.json`. It fixes `qwen3:8b`, three baseline tasks, one trial per task, five actions per trial, sequential execution, and no automatic retries. Maximums across the entire pilot are **3 trials, 15 model calls, 6,000 generated tokens, and 1,000 generated tokens per call**. Input tokens are measured separately and do not consume the generated-token budget. Thinking output is disabled explicitly for this action-selection pilot.

```powershell
# From backend, using the project Python environment:
python -m app.benchmark_cli --study-manifest benchmarks/qwen3_8b_pilot.json --database ../output/benchmarks/qwen3-pilot.sqlite3 --output ../output/benchmarks/qwen3-pilot.json
```

The model selects validated simulator tool actions; it does not provide executable Python. The fixed `apply_patch` tool installs a trusted fixture repair. Results therefore measure controlled workflow operation, not general coding ability. The model sees only public observations; protected test cases, correctness labels, and the private ledger are retained by the evaluator.

`benchmark_budget.py` records a reservation before each request and reconciles it using Ollama's generated-token count. A failed, incomplete, or interrupted response retains its reserved allowance and halts the pilot. Calls cannot overlap or be automatically retried. The final call's output allowance is reduced to the remaining overall budget. Changing limits under the same pilot identity is rejected. Preserve the pilot database and ID: creating a new database or new pilot ID is a new experiment requiring a new run authorization, not a way to retry this pilot.

Ollama host configuration is shared with the existing service, but this pilot accepts only the local endpoint. Metadata reads record the exact model digest and Ollama version without warm-up generation. Runtime dependencies, fixture hashes and harness hashes are recorded in each study. The settings dialog's configuration payload has also been corrected.

### Recorded pilot result — 11 October 2026

Ollama 0.40.3 and `qwen3:8b` were installed successfully. Model digest: `500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41` (5,225,388,164 bytes).

The approved pilot halted on its first request with `ReadTimeout` after approximately 120.8 seconds. **One trial started, zero completed, one model call attempted, and no retries occurred.** No complete usage response was received: actual generated tokens are unknown, and the full 1,000-token allowance remains reserved against the 6,000-token ceiling. A recorded zero in known-token subtotals must not be interpreted as zero actual generation when `token_usage_complete` is false.

The machine reported about 8 GB total RAM and 625 MiB free before execution. Server logs confirmed model loading took approximately 60 seconds, followed by request cancellation after the client timeout. This is a runtime/resource limitation observation, not a model-quality result or proof that memory alone caused the timeout. The remaining two trials were not started.

The original report is now archived at `output/result-backups-2026-10-13/qwen3-pilot.json`; its durable accounting remains in `output/benchmarks/qwen3-pilot.sqlite3`. Do not clear the accounting or automatically retry this historical pilot. Subsequent authorized trials are summarized above. Teammate integration and general coding capability remain unvalidated.

## What is implemented

| Area | Current behavior | Main files |
| --- | --- | --- |
| Real test evidence | Runs recursive pytest tests, records JUnit cases, counts failures/errors/skips, preserves process output, and fingerprints source state. Missing reports, launch errors, and timeouts cannot pass. | `backend/app/services/test_runner_service.py`, `models/schema.py` |
| Independent outcomes | Protected fixture checks verify behavior, a single current commit, ordered notification, and absence of prohibited effects. The general workflow supports an explicit Python syntax criterion; other criteria and constraints remain unverified. | `services/benchmark_service.py`, `services/verifier_service.py` |
| Experiment definitions | Versioned manifests, bounded settings, recorded seed, fresh workspace, identical initial state across conditions, scheduled versus actual faults. | `models/benchmark.py`, `services/benchmark_tasks.py` |
| Controlled faults | Failure before effects and timeout after a committed effect; baseline, generic retry, and idempotent retry conditions. Unsupported enhanced/ablation conditions are rejected. | `services/benchmark_service.py` |
| Recovery measurement | Detection-to-final-verification timing, eligible episodes including unrecovered failures, retry counts, duplicate effects, and post-recovery violations. Local test success is distinct from independently verified recovery. | `services/benchmark_service.py`, `services/debugger_service.py` |
| Persistence and trace | Atomic terminal report/metrics/status writes, failed-run records, complete trace exports, paginated log browsing, version labels, stale evaluation invalidation/history, and additive database migration. | `services/db.py`, `api/routes.py` |
| Summaries | Sample counts, Wilson intervals, duration variability, calls per verified success, recovery statistics, and budget outcomes; comparisons remain within task, condition, length, and actual fault exposure. | `services/benchmark_analysis.py` |
| Workflow safeguards | Confirmation gate, consistent task/run identity, goal-version-bound plans, zero retry/temperature settings, validated workspace-relative writes, accurate unchanged diffs. | Parser/planner/coder/orchestrator/workspace services |
| Dashboard | Preserves zero values, displays unavailable measurements, labels legacy evidence, separates execution-mode counts, refreshes verification results, and exports complete records. | `frontend/src/components/BenchmarkPanel.jsx`, `EvaluationDashboard.jsx`, `VerificationView.jsx`, `services/api.js` |

Existing FastAPI, React, Pydantic, SQLite, Ollama APIs, goal editing, staged execution, sample workspaces, and historical records are retained. Old scores are readable but excluded from current-version success statistics. Previously confirmed goals must be explicitly edited and reconfirmed to change them; plans for older goal versions must be regenerated.

## Metric definitions

- **Verified success:** all registered independent task criteria and hard constraints pass. An unsupported criterion is unknown, not a pass. The simulator additionally fails trials that exhaust a budget or terminate before completion.
- **Criteria coverage:** passed criteria divided by total criteria, expressed as a percentage. The compatibility field `success_rate` stores this coverage for a single run. It is not the population task-success rate.
- **Task-success rate:** independently successful trials divided by all trials in the comparison group. Unknown outcomes remain in the general dashboard denominator; pending and legacy records are listed separately. Mixed-task dashboard summaries are descriptive, not controlled comparisons.
- **Recovery rate:** independently recovered episodes divided by all eligible fault episodes, including baseline episodes with zero retries. A scheduled fault that never occurs creates no recovery episode. No eligible episodes produces an unavailable rate.
- **Recovery duration:** detection through final verification in the simulator. The ordinary coding workflow records repair/test duration only and leaves verified recovery unknown.
- **Efficiency:** actual gateway calls, calls across all trials per verified success, elapsed duration, tool execution time, and harness overhead. Version-two trial timing starts after workspace initialization and includes action checkpoints and final verification; final trace/report persistence is excluded. General workflow telemetry counts instrumented service boundaries, not an exhaustive operating-system trace.
- **Unknown costs:** model token totals require complete returned usage data. Simulator token and compute costs are unavailable. Missing drift, security, quality, and confidence measurements have no fabricated defaults.
- **Intervals:** 95% Wilson intervals describe the recorded binary outcomes. Repeating a deterministic fixture does not produce independent evidence of general model capability. Do not use these intervals to claim an LLM improvement.

## Benchmarking scope and team dependencies

| Requirement | Status and dependency |
| --- | --- |
| Normal completion | Executable deterministic suite and budgeted Ollama adapter. Actual model results must come from the saved pilot report, not fixture outcomes. |
| Goal adherence | Independent original-instruction and constraint checks, labeled drift ingestion, confusion matrix, onset/duration/type/severity analysis. A live general-purpose goal tracker remains teammate-owned. |
| Memory retention | Early-instruction probes with delayed dependent subtasks; no-memory/full-history/semantic/goal-aware scripted fixture conditions; retrieval/use and retention-by-delay metrics. These fixture policies are deliberately simplified and are not the team's memory manager. |
| Tool-failure recovery | Repeatable transient and post-commit faults, retry/idempotency comparisons, costs and final verification. Team policy/diagnosis adapters can register through the same boundary. |
| Sustained correctness and duplicates | Additional semantic checkpoints after a recovered commit, ordering checks, duplicate/prohibited effects, and later-violation analysis. |
| Task-length effects | Version two increases dependent subtasks while retaining comparable initial state and fault schedules. This does not claim general model scaling performance. |
| Efficiency | Measured tool/model calls, generated/input tokens, elapsed time, overhead and cost per verified success. Monetary/compute cost stays unavailable without measured pricing/resource data. |
| Prediction and ablations | Executable fixture conditions for enhanced/no-prediction/no-diagnosis and memory strategies; actual prediction-event classification/calibration/lead-time analysis; split-leakage checks. Predictor training and live intervention policy implementations remain teammate-owned. Fixture risk signals are synthetic test inputs, not a trained predictor. |
| Capability history and human effort | Persisted/recalculable per-run metrics, comparable-cohort EWMA history with sample counts, actual human intervention/time/workload ingestion. Simulated clarification events are counted separately and never presented as observed human effort. |

The team handoff uses `benchmark_adapters.py`: register a trusted server-side adapter with `version`, supported `conditions`, and `act(public_observation, state, condition)`. Return a validated action, JSON-serializable state, and telemetry. A fresh adapter instance is used for each trial; state needed for resume belongs in the returned state, not hidden instance fields. No runtime code-upload endpoint is provided. The fixture, registered-team-adapter, and local-Ollama modes remain explicitly distinguished in every report.

`POST /api/benchmarks/experiments/{id}/evidence` accepts batches described by `EvidenceEvent` in `models/benchmark_study.py`. Every event carries its ID, run/task/step, timestamp, source, version, kind, and data. Prediction events require a feature cutoff no later than the decision step; eventual outcomes come from independent trial results. Drift evaluation requires labeled actual/predicted drift. Memory events require complete retrieval/use labels. Human events require observed seconds, an optional 0–100 workload rating, and an explicit simulated flag. Attribution includes evidence and confidence and remains a plausible cause, not proof of causality.

Evidence is append-only; conflicting IDs are rejected and a batch's raw events/report changes commit together. Derived metrics can be recalculated from stored raw records. Imported events cannot change a trial's independent success verdict. This is an operator/evaluator endpoint in the existing local application, not an authenticated public labeling service. The team must review these contracts and supply their real event producers; benchmarking code cannot establish their accuracy in their absence.

Capability history is available in report exports and through `GET /api/benchmarks/capabilities/history`. Scores are normalized to 0–1 within task/adapter/condition/environment cohorts. Missing dimensions are not updated. The update uses `0.7 * previous + 0.3 * current`; counts and the normalization description accompany every snapshot. Planning here means observed prerequisite completion, tool use means successful gateway calls, and efficiency compares planned minimum actions with actual calls on verified successes. These are task-specific observations, not general intelligence scores.

## Reliability boundaries and remaining work

- An operating-system lock serializes experiment execution across local workers sharing the same database. The OS releases it when a worker exits. Multi-host distributed scheduling is outside this local runner.
- Version-two simulator studies persist agent/environment checkpoints and append-only evidence at each action boundary, preserving the same run ID and operation identities on resume. Completed trials are not repeated. Unmeasured time at a crash is marked incomplete and excluded from duration averages. Version-one interrupted runs remain historical evidence and retain their conservative no-overwrite behavior.
- A worker lost during a model request does not trigger another request: the durable allowance stays charged and the response is recorded as interrupted. A failed/incomplete model response halts the pilot. Resume is not permission to reset a model budget.
- Tool budgets and time limits are checked at action boundaries and after verification. This is cooperative control of trusted fixtures, not a preemptive process sandbox.
- Both simulator and Ollama benchmark modes execute only allowlisted immutable server fixtures. Arbitrary model-generated code cannot enter this benchmark executor. The separate general pytest/coding workflow still executes repository code locally and is not an isolation boundary for untrusted programs.
- General pipeline and manual execution errors are persisted. Invalid requests are rejected without becoming failed trials. A process crash or failure of persistence itself can still leave an incomplete record.
- Goal/code edits through the application invalidate prior evidence. Test evidence is checked against the workspace digest on verification. Edits made externally after verification are not monitored continuously; rerun verification before treating an old report as current.
- Full experiment JSON includes raw gateway events, initial/final state, scheduled faults, actual exposure, and evaluator outcomes. These exports are evaluator artifacts and must not be supplied to a future agent as its observations.
- Backend dependencies retain their existing compatible ranges; version-two reports archive exact environment versions and hashes alongside results. No Python framework or model-provider SDK replacement is required.

## Verification and expected fixture outcomes

From `backend`, run `python -m pytest -q`. From `frontend`, run `npm test` and `npm run build`. The backend suite uses temporary databases, including for import-time initialization; it does not migrate the user's application database. Model tests mock all generation calls. Tests cover all seven scenarios, ablations, late correctness, cross-process locking, checkpoint resume, append-only evidence, atomic rollback, token and call limits, and halting after unknown responses. Frontend tests exercise zero-setting serialization, rendered unknown states, and known versus reserved model-token reporting. Full browser interaction is not part of the automated suite.

The three validation experiments produced:

| Fault condition | Baseline | Generic retry | Same-identity retry |
| --- | --- | --- | --- |
| None | 20/20 | 20/20 | 20/20 |
| Before commit | 0/20 | 20/20 | 20/20 |
| Timeout after commit | 0/20 | 0/20 | 20/20 |

The generic retry in the final row passes local behavior checks but creates a duplicate commit, so the independent task verdict correctly fails. Regression tests also cover goal preservation, stale verdicts, unavailable measurements, atomic rollback, failed stages, budget exhaustion, paths, split leakage, isolation, and complete exports.

The Qwen3 8B pilot and installation/download were explicitly approved with the limits above. Further real-model experiments require their own explicit budget authorization. Team integration validation still awaits the actual memory, drift, prediction, diagnosis, and policy implementations; they have not been replaced with invented production functionality.
