# Coding and evaluation repairs

Original scope: preserve the existing architecture, confirmation gate, benchmark
controls, stored runs, and teammate changes. Later authorizations for bounded
live trials and clearing saved results are recorded below; they supersede the
original no-live-calls/preserve-history restrictions only for those actions.

1. **R1 — Generation correctness (critical).** Remove the generic success stub
   from `coder_service.py`. Stop with an actionable error on failed, empty, or
   invalid model output. Generate implementation before tests and reject tests
   that duplicate the implementation instead of importing it. Verify provider
   failure leaves the target untouched, invalid Python is rejected, and a mocked
   addition workflow exercises the actual implementation.
2. **R2 — Requirement latency and scope.** Recognize a narrowly defined simple
   addition request before model-based parsing; retain confirmation and use the
   existing fast execution path. Do not invent blocking coverage questions.
   Bound model-based requirement analysis and replace simulated progress stages
   with elapsed waiting status. Test simple/complex boundaries and timeout options.
3. **R3 — Honest review.** Make criterion results and actionable recommendations
   primary. Move unsupported aggregate ratings to clearly explained details;
   distinguish failed from unverified evidence and avoid green unknown results.
   Verify missing fields, historical reports, and unknown constraints.
4. **R4 — Evaluation usability.** Separate selected-run analysis, benchmark tools,
   and history. Keep exports and existing benchmark interfaces. Collapse detailed
   resource/evidence tables while retaining workflow findings. Check rendering,
   zero/missing values, controller regressions, and production compilation.
5. **R5 — Integration verification.** Run the backend suite, frontend tests and
   production build. Record limitations: generated tests alone cannot establish
   task correctness; security/semantic ratings require independent checkers.

Order: R1 then R2; R3/R4 can be reviewed independently; R5 follows all changes.
Risk: stricter generation validation intentionally rejects previously accepted
placeholder/self-testing output. Existing historical evidence is not rewritten.
This is a focused repair of confirmed faults, not a claim of exhaustive project
correctness. A real-model smoke test remains separate and requires an available
provider and the previously agreed call/token limits.

## Completed and verified — 2026-10-13

- R1: Removed the generic status stub. Failed/empty/invalid generation raises an
  explicit error before writing that file. Tests follow implementation files,
  receive their source, and must import rather than redefine the implementation.
  This is a structural guard, not proof of behavioral correctness. Oversized
  existing files now stop for a smaller edit instead of being silently truncated.
- R2: The exact basic Python addition exercise uses a small deterministic goal
  draft, then the normal confirmation gate and model coding path. Compound
  requests still use analysis. Model-based parsing uses a 15-second HTTP timeout;
  overall elapsed time can include other work. Generic coverage questions no
  longer block tasks. The selected/configured model is preserved across stages.
  Saved logs independently confirmed multiple model failures taking roughly
  45–50 seconds followed by fallback generation; the timer animation was not
  reporting real analysis stages.
- R3: Review leads with passed, failed and unverified requirements, evidence,
  and next steps. Missing ratings are explained in a collapsed section. Legacy
  results remain explicitly unvalidated.
- R4: Evaluation separates the current workflow, controlled benchmarks and
  history. Benchmark component state survives section switches. Sub-goal tables,
  resource detail, saved test summaries, raw evidence and definitions expand on
  demand. Findings still link to exact recorded events. Refresh also refreshes
  the workflow report. Generic routing/planning no longer invents auth modules.
- R5: 198 backend tests and 13 frontend tests passed. Production build passed.
  Targeted lint found no errors and six existing unused-code/redundant-catch
  warnings. Browser fixture checks covered overview, history, benchmark access,
  review, expandable sub-goals, and finding evidence. No live model trial ran.

## Remaining limitations and follow-up work

Update following approval: the addition-specific independent behavior checker
`python_addition_v1` is now implemented for new basic addition goal drafts.
It uses evaluator-owned cases and bounded AST interpretation, without running
workspace code. Unsupported code forms still need another independent checker.
Existing demo templates can no longer bypass synthesis when editing a file
that already exists. Historical artifacts remain unchanged.

Validation for this follow-up: 38 focused tests passed (addition checker,
generation repairs, existing criterion checks). A subsequent full-suite run was
declined before execution. The newly added end-to-end test proving that passing
generated tests cannot approve subtraction is therefore written but not yet
executed. The previous 198-test full-suite result predates this follow-up.

1. **Independent behavior checks (high):** Generated tests do not establish that
   arbitrary user requirements are satisfied. The ordinary workflow still needs
   trusted, task-specific acceptance checks and a regression baseline. Addition
   generated by a mocked model was executed in tests, but this does not establish
   real-model ability or make its generated tests an independent oracle.
2. **Security/quality/semantic ratings (medium):** No calibrated independent
   checker is connected for these broad claims. Choose scoped checker contracts
   before assigning scores; hiding missing evidence is not implementation.
3. **Provider readiness (high before live use):** A reachable selected model is
   needed for actual synthesis. No model installation/download/call occurred in
   this repair. Any benchmark pilot must retain the agreed limits and no retries.
4. **Existing artifacts:** Historical placeholder files and old records were not
   rewritten. New execution uses the repaired path. If generation fails on a
   later file, earlier successful file changes remain visible for review; this
   repair does not promise multi-file transactional editing.
5. **Preset scope:** Existing authentication/concurrency templates remain demo
   implementations, not evidence of general model competence. Broader template
   replacement and a full security audit were outside this focused repair.

Read-only browser fixture: `frontend/tests/repair-preview.html` (served by Vite).
It intercepts API calls and rejects execution requests. Preview screenshots use
synthetic data and are stored under `output/*-repair-preview.png`.

## Database and live-model follow-up — 2026-10-13

The user authorized live trials in this follow-up, superseding the earlier
no-live-calls scope for this bounded pilot only.

- Read-only SQLite integrity checks returned `ok` for the application database
  (146 saved runs) and the pilot database; both had zero foreign-key violations.
  Tests use real temporary SQLite databases to avoid altering saved user runs.
  The earlier temporary-database error was sandbox filesystem access, not
  detected database corruption. No database rebuild or record deletion was needed.
- The full regression suite passed all 215 tests, including the pending test
  where generated tests pass but incorrect addition independently fails.
- Corrected the coding client's default from an unavailable model to the
  user-selected installed `qwen3:8b`. Bounded Qwen3 code/JSON requests now disable
  thinking, matching the pilot settings. Two additional mocked HTTP tests passed.
- Ran a real, sequential Qwen3 continuation, preserving the older unknown
  1,000-token reservation. Its limits were 2 additional trials, 14 additional
  calls, 5,000 additional generated tokens and 1,000 per call, with no retries.
  It halted after its first request timed out at 120 seconds. No successful
  completion or zero-token usage is claimed.
- Across both pilot identities: 2 attempted trials, 2 model calls, and 2,000
  tokens conservatively reserved for unknown usage. Under the original ceilings,
  at most 1 further attempted trial, 13 calls and 4,000 generated tokens remain.
  Neither halted ledger was cleared or reset. No further retry was issued.
- Read-only model status showed Qwen3 loaded at approximately 5.94 GB,
  `size_vram=0`, context 4096, on a machine with about 8.2 GB physical RAM and
  only about 0.73 GB free after the attempt. Memory pressure/CPU inference is a
  plausible contributor, not a proven sole cause. Freeing memory or changing
  the approved model requires the user's direction; no other apps were closed.

Live report: `output/benchmarks/qwen3-continuation-results-2026-10-13.json`.
The live adapter tests model-selected simulator actions; it does not evaluate
arbitrary model-generated Python execution. Broad security, calibrated quality,
and semantic-drift scores still lack defined independent checker contracts.

## Smaller model, sandbox and history follow-up — 2026-10-13

- **Completed:** Installed `qwen3:1.7b` with user authorization and made it the
  backend/UI default. Settings now take the asynchronously loaded configured
  model until the user edits their selection. Existing explicit selections are
  retained. The backend was not running on port 8000 during this change; the
  new default applies when it next starts.
- **Memory:** Unloaded Qwen3 8B before the trial and Qwen3 1.7B afterwards.
  Ollama reported no loaded models afterwards; Windows reported about 1.50 GiB
  free physical memory. Other applications were not closed. Installed model
  files remain available on disk. Removing run records does not free model RAM.
- **Database cleanup:** Cleared 146 application runs, 2 old pilot runs and 180
  fixture runs, including their dependent result records. Recovery databases
  and five older report exports are in `output/result-backups-2026-10-13/`.
  `app/result_maintenance.py` backs up before deleting, rolls back failures and
  preserves model-budget ledgers. All three databases passed integrity and
  foreign-key checks after cleanup. The new successful pilot is retained.
- **Sandbox filesystem fix:** Tests now use ignored `backend/.test-tmp/` for
  real SQLite storage and subprocess scratch output. Maintenance/budget tests
  pass inside the sandbox. No ACLs, firewall settings or security policies changed.
- **Remaining host restriction:** Windows sandbox execution stalls in Python's
  asyncio loopback socket-pair setup. A captured stack identifies this separately
  from SQLite. Async regression tests and local Ollama access were completed with
  scoped execution approval. This host restriction is not claimed fixed by
  application code; use scoped approval if it recurs rather than disabling security.
- **Live result:** The single remaining trial used
  `benchmarks/qwen3_1_7b_remaining_pilot.json`, with limits 1 trial / 13 calls /
  4,000 generated tokens / 1,000 per call, sequentially and without retries.
  It completed in 21.50 seconds, with 5 tool calls, 5 model calls, 148 generated
  tokens and 2,796 input tokens. All 3 protected behavior tests and all fixture
  criteria passed; no duplicate effects were recorded. Report:
  `output/benchmarks/qwen3-small-results-2026-10-13.json`.
- **Aggregate accounting:** Three attempted trials, seven calls, 148 known
  generated tokens plus 2,000 reserved for earlier unknown responses. The trial
  allowance is exhausted conservatively; no additional generation was issued.
  Changing model did not erase old usage or reuse a halted pilot identity.
- **Verification:** Full backend suite: 219 passed, one dependency deprecation
  warning. The subsequently added smaller-model allowance test also passed
  (220 distinct backend tests verified). Frontend: 14 tests passed and production
  build passed. Lint now targets application/test source instead of dependencies;
  it reports existing unused-code/redundant-catch warnings, with no errors.

The successful live result covers model-selected trusted simulator actions,
not independently generated Python. General coding repairs are regression-tested
with controlled model responses; a real synthesis trial requires a new explicit
budget. Broad security/quality/semantic scoring and actual teammate-owned memory,
prediction and adaptive-policy integration remain separate outstanding work.

## Workflow navigation repair — 2026-10-13

Requirements now expose a confirmation action even when no clarification
questions exist. Full-workflow requests retain a run-specific pending intent:
execution pauses for review and resumes the same run after successful explicit
confirmation. Repeating the full-workflow click before confirmation navigates
to the gate (or unresolved blocking questions) without executing another request.
Manual analysis/confirmation remains stage-by-stage. Reset, selecting a different
run, and starting manual analysis clear the pending full-workflow intent.

Errors are visible on the current screen, and the waiting message distinguishes
requirement preparation from execution after confirmation. No backend gate was
removed, and no model calls were made to verify this repair. All 23 frontend tests
passed, including handler-level navigation tests with mocked HTTP and rendered
next-action checks. Production build and whitespace checks passed. These are
automated component/handler checks, not a live browser or model trial.

## Rejected test generation — 2026-10-13

The reported multiplication run saved syntactically valid `app/service.py` but
rejected `tests/test_service.py` at line 2. Its model response used exactly the
old 512-token ceiling; truncation is plausible, but the rejected source and stop
reason were not retained, so the original offending text cannot be reconstructed.
The model did respond; the connection advice on this syntax error was misleading.

Code generation now requests at most 1,000 output tokens, asks for concise tests,
and rejects explicit length-stop/incomplete responses even if their prefix
compiles. JSON code envelopes are decoded before extracting embedded code fences.
Failures retain up to 16,000 characters of rejected output in the local run log,
along with syntax position and stop reason; the UI displays that output as escaped
text in a collapsed disclosure. Invalid output is never substituted with a fake
success file or retried automatically. Existing generated files were not changed.
Nineteen focused backend generation tests passed using mocked model responses.
No live generation retry was made; actual new model output remains unverified.
