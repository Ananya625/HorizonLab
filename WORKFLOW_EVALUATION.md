# Actual workflow evaluation (workflow-v1)

This observational evaluator implements E01–E13. It does not choose actions, retry,
stop, or repair an agent. Controlled benchmarks remain separate. No model calls or
new dependencies are needed to calculate these reports.

## Evidence contract

Events are append-only, ordered per run, and idempotent by event ID. An action is
one explicit operation attempt with paired start/result events. Stages and model
requests are separate from tool operations; nested stages do not inflate action
counts. An unfinished start is incomplete, never successful. Action, parent,
attempt, recovery, sub-goal, goal-revision, and plan-revision IDs bind evidence.
Arguments and observations are hashed; raw prompts, source, secrets and responses
are not duplicated in events. Targets are bounded workspace-relative summaries.

Goal revision identities use a content digest excluding confirmation, timestamps,
and audit history. This avoids numeric version collisions, including old data.
Goal edits use an atomic expected-version check; stale concurrent edits fail.
Plan identities use a content digest. Explicit file-to-sub-goal mappings are
optional and validated; absence means unmapped, never guessed from filenames.

Only registered independent criterion verification can complete a sub-goal. All
of its explicitly mapped required criteria must pass in the same goal revision
and workspace state. A changed state makes old evidence stale. A new independent
FAIL after a prior PASS on a changed state is a regression; staleness is not one.
Agent claims remain distinct. Workflow phase completion is not goal completion.

## Calculations and detector boundaries

* Action attempts = tool action starts; model calls and stages are reported
  separately. Completed + incomplete action counts reconcile to started actions.
* Verified progress = fresh verified sub-goals / required sub-goals. Empty
  denominator gives null. Historical runs without events have null action counts.
* Duration = recorded monotonic elapsed duration; total resource time is the union
  of leaf-operation intervals, not the sum of nested spans. Wall time is the
  event observation window. No arbitrary optimal path or quality score is used.
* Token totals require measured usage for every relevant model result. Known
  subtotals and unknown request counts are also shown; timeouts are not zero.
* Fingerprints use tool-specific argument identities, target, goal/plan revision,
  and relevant before-state. Reads compare exact content observations. Writes
  include intended content hash. Model requests are not repetition candidates.
* Repeated sequences of length 1–4 within the last 64 tool attempts are suspected
  loops only when state and observation evidence are complete and unchanged,
  there is no verified progress, and no retry, polling, or validation reason.
  Repetition alone is not an error. Stagnation counts actions/time since verified
  progress (or first event, with that baseline explicitly identified).
* Revisits after completion are classified as validation, repair, changed
  requirements, or unexplained rework. Operational work after independently
  verified run completion is flagged only without a documented allowed reason.
* Completion claims with unmet or unknown required criteria are premature claims,
  not proven task failure. Final reporting, cleanup and validation are allowed.
* Explicit dependencies are checked against fresh verified prerequisite evidence.
  Independent operations can occur in any order. Missing mappings are unknown.
* Duplicate effects require distinct committed effect IDs for one intended
  operation ID. Repeated calls or re-delivery of one event are not duplicate effects.
* Recovery/rework resource groups may overlap. Each group deduplicates action IDs;
  their union is shown separately and group totals must not be added together.
  Verified recovery requires later independent success; local test success alone
  is insufficient. Later failure is recurrence; PASS-to-FAIL is regression.
* Evidence coverage reports paired outcomes, state references, sub-goal mappings,
  and measured usage separately. It does not prove every external action was seen.

## APIs and UI

GET `/api/evaluations/{run_id}/workflow` computes a deterministic versioned report
from the stored event snapshot. GET `/api/evaluations/{run_id}/workflow/events`
supports bounded pagination and a snapshot upper sequence. GET
`/api/evaluations/{run_id}/workflow/events/{event_id}` returns scoped evidence.
GET `/api/evaluations/{run_id}/workflow/export` exports report and events; existing
run exports retain their original shape. There is no public untrusted evidence
injection endpoint. Internal modules can submit explicit evidence under this
contract; semantic drift, prediction and memory attribution are not fabricated.

The Evaluation page retains benchmark panels and adds an Actual Workflow Analysis
overview, sub-goal resources, timeline, finding details, and evidence drill-down.
Run changes cancel stale display results. Live refresh is explicit; reports show
the last observed sequence and cannot promise real-time activity between refreshes.

## Labeled examples (detector acceptance)

| Trace | Expected |
|---|---|
| Read A, Read A, Read A; unchanged state and observation | repetition and suspected loop |
| Read A, Read B, Read A, Read B; no new information | suspected sequence loop |
| Test, Edit, Test | validation cycle, no loop |
| Retry same operation after timeout with recovery reason | retry, no loop |
| Poll unchanged state within explicit polling policy | repetition, no loop |
| PASS, source edit | stale, no regression |
| PASS, source edit, independent FAIL | regression |
| Verified completion, final verification/report | allowed finalization |
| Verified completion, unexplained write | post-completion work |
| Repeated call with same committed effect ID | no duplicate effect |
| Same operation with two different committed effects | duplicate effect |

Tests replay labeled positive and negative traces, report detector confusion
counts, validate SQLite migration/idempotence/concurrency and API pagination, and
exercise UI request races, navigation and evidence selection without new packages.
Live-model validation and optional research extensions remain deferred.

## Implementation map

| Approved task | Implementation |
|---|---|
| E01 | This metric contract and hand-labeled replay fixtures in `tests/test_workflow.py`. |
| E02 | `models/workflow.py`, `services/workflow_store.py`, additive initialization in `db.py`. |
| E03 | `workflow_service.py` scopes/decorators on planner, coder, debugger, test runner, model client, orchestrator, verifier and workspace tools. |
| E04 | Explicit optional plan-to-sub-goal links, attempt scopes, independent criterion events, content revision identities and atomic goal edit checks. Newly saved plans bind to goal content; legacy plans remain readable. |
| E05–E09 | Pure `workflow_analysis.py` replay: counters, progress, evidence coverage, detectors, plan observations and resources by sub-goal, attempt and recovery. |
| E10 | `workflow_reports.py` and four read-only workflow report/evidence/export routes; existing APIs remain compatible. |
| E11–E12 | `WorkflowAnalysis.jsx`, request ownership/pagination controller and existing dashboard integration. |
| E13 | Backend storage/API/replay/instrumentation tests and frontend controller interaction/render tests. |

## Usage and measurement limits

After restarting the backend normally, its existing database initialization adds
the workflow event table. The extension records new workflow activity. Select a
run in Evaluation and use **Refresh workflow** to inspect its observation snapshot.
Run evidence is not backfilled by guessing from historical log messages. The
database was not migrated directly during development; tests use isolated copies.

No new independent semantic checker was invented. The existing supported Python
syntax checker supplies criterion evidence; other criteria remain unverified.
Explicit sub-goal links, intended-operation/effect identities, and completion
claims must come from the producer. Missing attribution is visible. Natural-
language completion claims are not inferred from model text. Plan writes indicate
observed work, not proof that a plan or task was satisfied.

Reports describe the recorded state. External workspace edits after the last
event are not silently rechecked by the read-only report endpoint. The next
observed operation/verification captures a new state. An attempt finishing without
an exception is still of unknown goal success until independently verified.

Resources are measured time/calls/tokens, not currency estimates. No provider
pricing or optimal action baseline is assumed. Detector thresholds are versioned
constants. The labeled sanity scorecard contains 11 examples: 5 true positives,
6 true negatives, 0 false positives and 0 false negatives across loop,
regression, stopping and duplicate-effect checks. This small constructed set is
not an estimate of accuracy on real-world agent trajectories.

## Validation recorded on 2026-10-12

- Complete backend regression run: 174 passed.
- After the final stale-failure/reopening refinements: all 81 affected workflow,
  correctness, adaptive-pipeline and integration tests passed (including two new
  cases). Unaffected benchmark tests were already included in the full run.
- Frontend: all 10 tests passed, including run-switch races, concurrent evidence
  selection/pagination, retry/disposal, API arguments, and rendered unknown values.
- Production frontend build passed; targeted lint for the new component,
  controller and API client reported no errors or warnings.
- Application Python compilation and Git diff whitespace checks passed.
- Existing Starlette/httpx TestClient deprecation warning remains. Dependencies
  were not changed to address it.
- No live model trials, browser walkthrough, installations, commits or pushes
  were performed. The earlier Qwen pilot and saved-run database are untouched.
- Source backup: `output/before-workflow-evaluation.zip`. The active database
  was verified byte-for-byte against the backup after testing.

## Evidence availability improvements

Inspection of the saved database found eight occurrences each of the fallback
criteria `Syntax errors == 0`, `pytest new_tests == 100% PASS`, and
`Regression failures == 0`. The syntax wording previously did not match the
implemented checker. It now maps to a repository Python compilation check that
does not execute code; new fallback goals use `python_syntax_workspace` explicitly.
An empty or unavailable workspace is unverified, not a vacuous pass. Dependency,
cache and linked directories are excluded; checks are bounded to 1,000 files and
1 MiB per file. State changes during verification invalidate the result.

The supported narrow contracts are:

| Method | Metric | Scope |
|---|---|---|
| ast_check | python_syntax | Compile the explicit expected_output file without executing it. |
| ast_check | python_syntax_workspace (legacy alias: Syntax errors == 0) | Compile current Python sources within the bounded workspace scope. |
| schema_validation | json_valid | Parse the explicit JSON file; this does not validate a business schema. |
| state_ledger_check | file_exists | Check that the explicit path is a regular file; this does not establish its behavior. |

`expected_output` is a workspace-relative path for file-specific contracts.
Paths escaping the workspace remain unverified. Missing required files fail;
unreadable/oversized files or invalid checker configuration remain unverified.
Unregistered functional/security/regression criteria now explain what evidence
is missing. No test baseline or functional oracle is inferred from generated tests.

The Actual Workflow Analysis panel exposes checker availability and next steps.
It also displays existing saved test reports, model-request records, tool log
entries, and recovery records separately. These are read-only historical facts,
not reconstructed actions or freshly verified outcomes. Original saved runs are
not rewritten; run verification explicitly to check the current workspace.
# Independent addition check (2026-10-13)

New basic addition goal drafts register `automated_test / python_addition_v1`
with `expected_output=app/service.py`. This evaluator-owned check reads current
source and interprets a small numeric AST language against eight fixed cases.
It does not import or execute workspace Python or trust generated tests. The
supported interface is standalone `add(a, b)`, optional int/float annotations,
local numeric assignments, a final return, and numeric + / - expressions.
Imports, decorators, calls, loops, conditionals, other interfaces and excessive
source/AST size remain UNVERIFIED. Incorrect supported behavior returns FAIL.
Evidence states the checker version and case count. Existing workspace/goal
freshness protections still apply. PASS is scoped to these numeric cases, not
a universal correctness theorem, security audit, or calibrated quality rating.
Old goals and historical files are not automatically rewritten.

