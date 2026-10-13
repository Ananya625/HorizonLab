# Proposed merge review

Status: proposal only. No project source files replaced. Original workspace files and all four attachments preserved byte-for-byte; workspace hashes recorded in original-sha256.json. Person attribution assumes attachment order A dashboard, B dashboard, A settings, B settings, because the message placeholders were empty. With only two snapshots, this identifies differences, not who originally authored shared lines.

## Dashboard: complete meaningful comparison

| Area | Person A | Person B | Proposed resolution |
|---|---|---|---|
| Shared interface/layout | Current run, selection callback, banner, refresh/export controls, six telemetry cards, four aggregate cards, historical table and Load Run action | Retains these | Preserve |
| Imports | Extra unused icons and unused fetchRunEvaluation | Removes unused imports; adds useRef, exportRun and two benchmark panels | Keep B's used imports; removed imports had no invoked behavior |
| onReset | Declared, never invoked | Not destructured | Restore A's declaration; caller still passes it; no new reset control |
| Request sequencing | Every response updates state | Latest request only; effect cleanup invalidates old requests | Keep B's race protection |
| Loading/errors | Loading state not rendered; errors only console warning | Visible loading and error; clears prior data/error on refresh | Keep B's visible feedback; console-only behavior superseded |
| Refresh dependency | Run ID | Run ID and evaluation creation time | Keep B's same-run refresh fix |
| Null fallback operators | Null-only defaults for aggregate, recent rows, filename, row key and recovery count | Uses falsy defaults for these | Restore A's null-only semantics |
| Export | Downloads current in-memory run or dashboard | Fetches complete selected-run export through existing API; aborts on error | Keep B's complete export; no partial fallback that could misrepresent completeness |
| Controlled benchmarks | None | BenchmarkPanel and BenchmarkStudies; refresh on completion | Keep both existing integration points |
| Evidence interpretation | No caveats | Legacy/pending/unverified counts; mixed-task caveat; execution-mode counts | Keep B |
| Current score | Success Rate label; percent directly appended | Criteria Coverage label; missing score unavailable | Keep B; matches backend per-run coverage meaning |
| Current duration/tool/drift | Direct values, including empty output on missing fields | Explicit unavailable states; preserves actual zero | Keep B |
| Current tests/recovery | Existing counts | Unchanged | Preserve |
| Aggregate title/count | Platform Benchmark Aggregates; Total Evaluated Runs; falls back to recent list length | Recorded Run Summary; Total Recorded Runs; unknown count unavailable | Keep B; recent list is truncated and is not the total |
| Aggregate success | Falsy value becomes 100 percent | Null unavailable, actual zero remains zero; verified success label | Keep B; backend measures current-version verified successes |
| Aggregate duration | Falsy value becomes 3.5 seconds | Null unavailable, actual zero remains zero | Keep B |
| Aggregate recovery | Calls attempts recoveries, missing becomes zero | Labels attempts; unknown unavailable | Keep B |
| Historical coverage/outcome | Missing score becomes 100 percent | Legacy label or current criteria/outcome | Keep B |
| Historical duration/tool/tests/drift | Defaults 3.2 seconds, 12 calls, 6/6 tests, zero drift | Unknown placeholders rather than fabricated values | Keep B |
| Historical recovery | Null-only zero fallback | Falsy zero fallback | Keep A operator; numeric zero unchanged |
| Styling/navigation | Existing styling, highlighted selected row, title truncation, empty-table text | Unchanged | Preserve |
| Final newline | Missing | Present | Normalize final newline |

No unique executed feature in A was removed by B. The meaningful behavioral conflicts are fabricated metric defaults versus unknown measurements, and snapshot export versus full export. The proposal uses B's corrections because the current backend and the agreed benchmarking requirements support them. A's original structural UI and navigation remain intact.

## Settings modal

Both attachments are identical after final-newline normalization. Both already use configureOllama({ host, default_model: selectedModel }); there is no positional-argument conflict in the provided pair. Preserve the entire shared implementation, props, model/host controls, zero-capable temperature slider, close/cancel, busy state and feedback. The proposed file equals the current workspace version. Cpu and fetchOllamaStatus are unused in both originals and are retained rather than changing unrelated shared code.

## Integration and residual issues

Reviewed App.jsx callers, services/api.js, backend configuration/export routes and dashboard aggregate schema. All required imports and endpoints exist. No duplicated functions or conflicting declarations were introduced. onReset remains intentionally unused, as in A. No API or data model changes are proposed.

Existing issues documented, not silently repaired:
- Both modal versions initialize local host/model state only on mount; later currentStatus updates do not reset it. Choosing when to overwrite unsaved edits requires a separate UI decision.
- B's mode label maps local_ollama and registered_adapter to unspecified despite backend support.
- Historical missing recovery count still displays zero in both versions; current missing recovery/test counts can render blank. B's missing historical duration/coverage use dash-with-unit placeholders.
- B uses a load-error label even for export errors, and permits a null dashboard export while data is unavailable. These are existing behaviors, not merge conflicts.

## Verification

Six automated checks passed: zero setting serialization, proposed dashboard zero/unknown rendering, verification unknown handling, pilot unknown-token rendering, proposed modal hidden/open/zero-temperature rendering, and mocked settings API payload. A production Vite build with both proposed components injected into the real app also passed (7 total checks, 0 failures). No provider requests or model calls were made. Tests do not establish real-browser interaction correctness or explicitly exercise out-of-order requests/export clicks. The current project source hashes still match their backups.

Review proposed/*.jsx for complete code, *.workspace-to-proposed.diff for the small application diff, and *.person-a-to-proposed.diff for all integrated differences from A. These artifacts are under the existing ignored output directory and have not been staged or committed.

Approval needed: confirm the attachment attribution if the assumed ordering is wrong, and approve applying the proposed dashboard diff. The settings file needs no source change. Shared residual issues are separate from this merge.
