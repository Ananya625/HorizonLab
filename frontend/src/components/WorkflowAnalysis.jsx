import React, { useEffect, useMemo, useState } from 'react';

import { fetchWorkflowReport, fetchWorkflowEvents, fetchWorkflowEvent, exportWorkflow } from '../services/api';

import { createWorkflowController } from '../services/workflowController';



const show = value => value == null ? 'Unavailable' : typeof value === 'number' ? Number(value.toFixed(3)).toString() : String(value);

const percent = value => value == null ? 'Unavailable' : `${(value * 100).toFixed(1)}%`;

const box = { padding: 16, marginTop: 12, overflowX: 'auto', lineHeight: 1.6 };

const api = { report: fetchWorkflowReport, events: fetchWorkflowEvents, event: fetchWorkflowEvent };

function WorkflowMeter({ label, value }) {
  if (!Number.isFinite(value)) return <span className="workflow-meter-unavailable">Unavailable</span>;
  const ratio = Math.max(0, Math.min(1, value));
  const percentage = ratio * 100;
  return <div className="workflow-meter" role="progressbar" aria-label={label} aria-valuemin={0} aria-valuemax={100} aria-valuenow={percentage}>
    <span style={{ width: `${percentage}%` }} />
  </div>;
}

function WorkflowProgressRing({ value, verified, required }) {
  const hasProgress = Number.isFinite(value);
  const ratio = hasProgress ? Math.max(0, Math.min(1, value)) : 0;
  const radius = 30;
  const circumference = 2 * Math.PI * radius;
  return <div className="workflow-progress-ring" role={hasProgress ? 'img' : undefined}
    aria-label={hasProgress ? `${show(verified)} of ${show(required)} sub-goals verified` : 'Verified sub-goal progress unavailable'}>
    <svg viewBox="0 0 80 80" aria-hidden="true">
      <circle className="workflow-progress-ring-track" cx="40" cy="40" r={radius} />
      {hasProgress && <circle className="workflow-progress-ring-value" cx="40" cy="40" r={radius}
        strokeDasharray={`${ratio * circumference} ${circumference}`} />}
    </svg>
    <div className="workflow-progress-ring-label">
      <strong>{hasProgress ? `${Math.round(ratio * 100)}%` : '—'}</strong>
      <span>verified</span>
    </div>
  </div>;
}

function SubGoalStatus({ status }) {
  const label = status || 'unverified';
  const knownStatuses = ['verified', 'failed', 'stale', 'unverified'];
  return <span className={`workflow-status-chip ${knownStatuses.includes(label) ? `is-${label}` : ''}`}>{label}</span>;
}



export function WorkflowView({ state, onRefresh, onPage, onInspect, onExport }) {

  const [findingPage, setFindingPage] = useState(0);

  const report = state.report;

  const summary = report?.summary;

  const findings = report?.findings || [];
  const subGoals = report?.sub_goals || [];
  const statusCounts = subGoals.reduce((counts, goal) => {
    const status = ['verified', 'failed', 'stale'].includes(goal.status) ? goal.status : 'unverified';
    counts[status] += 1;
    return counts;
  }, { verified: 0, failed: 0, stale: 0, unverified: 0 });
  const maximumAttempts = Math.max(0, ...subGoals.map(goal => goal.attempts).filter(Number.isFinite));
  const maximumToolCalls = Math.max(0, ...subGoals.map(goal => goal.resources?.tool_calls).filter(Number.isFinite));
  const coverageMetrics = [
    ['Paired outcomes', report?.coverage?.paired_outcomes],
    ['State evidence', report?.coverage?.state_references],
    ['Sub-goal mapping', report?.coverage?.sub_goal_mapping],
  ];

  useEffect(() => setFindingPage(0), [report]);

  return <section className="card-panel evaluation-workflow" style={box} aria-label="Actual Workflow Analysis">

    <h2>Actual Workflow Analysis</h2>

    <p>See how much work the agent performed, where it repeated work, and which sub-goals have verified evidence.</p>

    {!state.runId && <p>Select a run to inspect its workflow.</p>}

    {state.runId && <p>Run: {state.runId} <button disabled={state.loading} onClick={onRefresh}>Refresh workflow</button> <button disabled={!report} onClick={onExport}>Export workflow evidence</button></p>}

    {state.loading && <p role="status">Loading workflow evidence…</p>}

    {state.error && <p role="alert">{state.error}</p>}

    {report && <>

      <p>Evidence: {report.evidence_status}. <span title="Detailed event data is available in the timeline below.">Only recorded actions are counted.</span></p>

      <p>{report.evidence_status === 'unavailable' ? 'This historical run has no structured action evidence. Missing actions and completion are not reconstructed from logs.' : 'Refresh to observe new activity. Unfinished actions remain incomplete.'}</p>

      <section className="workflow-visual-overview" aria-label="Workflow visual summary">
        <div className="workflow-overview-header">
          <div>
            <h3>Run at a glance</h3>
            <p>Verified progress and observed execution activity for this workflow.</p>
          </div>
          <span className={`workflow-evidence-badge is-${report.evidence_status || 'unavailable'}`}>
            {String(report.evidence_status || 'unavailable').replaceAll('_', ' ')} evidence
          </span>
        </div>

        <div className="workflow-overview-grid">
          <article className="workflow-progress-card">
            <WorkflowProgressRing
              value={summary.progress_rate}
              verified={summary.verified_sub_goals}
              required={summary.required_sub_goals}
            />
            <div>
              <span className="workflow-visual-label">Verified sub-goals</span>
              <strong className="workflow-progress-count">
                {show(summary.verified_sub_goals)} <span>/ {show(summary.required_sub_goals)}</span>
              </strong>
              <span className="workflow-visual-caption">Freshly supported by verification evidence</span>
            </div>
          </article>

          <article className="workflow-kpi-card">
            <span className="workflow-visual-label">Action attempts</span>
            <strong>{show(summary.action_attempts)}</strong>
            <span className="workflow-visual-caption">{show(summary.incomplete_actions)} incomplete actions recorded</span>
          </article>

          <article className="workflow-kpi-card">
            <span className="workflow-visual-label">Model calls</span>
            <strong>{show(summary.model_calls)}</strong>
            <span className="workflow-visual-caption">Observed wall time: {show(summary.wall_seconds)}s</span>
          </article>

          <article className="workflow-kpi-card workflow-kpi-rework">
            <span className="workflow-visual-label">Repeated actions</span>
            <strong>{show(summary.repeated_actions)}</strong>
            {Number.isFinite(summary.action_attempts) && summary.action_attempts > 0 && Number.isFinite(summary.repeated_actions)
              ? <WorkflowMeter label="Repeated actions as a share of action attempts" value={summary.repeated_actions / summary.action_attempts} />
              : <span className="workflow-visual-caption">Share unavailable</span>}
          </article>
        </div>

        <div className="workflow-chart-grid">
          <article className="workflow-chart-card">
            <div className="workflow-chart-heading">
              <div>
                <h4>Sub-goal verification</h4>
                <p>Current evidence status for each required sub-goal.</p>
              </div>
              {subGoals.length > 0 && <span>{subGoals.length} total</span>}
            </div>
            {subGoals.length === 0 ? <p className="workflow-chart-empty">No explicit sub-goal evidence is available.</p> : <>
              <div className="workflow-status-stack" role="img" aria-label={`${statusCounts.verified} verified, ${statusCounts.failed} failed, ${statusCounts.stale} stale, ${statusCounts.unverified} unverified sub-goals`}>
                {[
                  ['verified', '#16845B'],
                  ['failed', '#D14343'],
                  ['stale', '#D9A441'],
                  ['unverified', '#CBD2E0'],
                ].map(([status, color]) => statusCounts[status] > 0 && (
                  <span key={status} style={{ width: `${(statusCounts[status] / subGoals.length) * 100}%`, background: color }} />
                ))}
              </div>
              <div className="workflow-status-legend">
                {[
                  ['verified', 'Verified'],
                  ['failed', 'Failed'],
                  ['stale', 'Stale'],
                  ['unverified', 'Unverified'],
                ].filter(([status]) => statusCounts[status] > 0).map(([status, label]) => (
                  <span key={status}><i className={`workflow-legend-dot is-${status}`} />{label} <strong>{statusCounts[status]}</strong></span>
                ))}
              </div>
            </>}
          </article>

          <article className="workflow-chart-card">
            <div className="workflow-chart-heading">
              <div>
                <h4>Evidence coverage</h4>
                <p>How much of the observed work has supporting references.</p>
              </div>
            </div>
            <div className="workflow-coverage-list">
              {coverageMetrics.map(([label, value]) => (
                <div key={label} className="workflow-coverage-row">
                  <div><span>{label}</span><strong>{percent(value)}</strong></div>
                  <WorkflowMeter label={label} value={value} />
                </div>
              ))}
            </div>
          </article>
        </div>

        {subGoals.length > 0 && (
          <article className="workflow-chart-card workflow-effort-card">
            <div className="workflow-chart-heading">
              <div>
                <h4>Effort by sub-goal</h4>
                <p>Compare observed attempts and tool calls; each measure uses its own scale.</p>
              </div>
            </div>
            <div className="workflow-effort-list">
              {subGoals.map(goal => (
                <div className="workflow-effort-row" key={goal.id}>
                  <div className="workflow-effort-name">
                    <span title={goal.title}>{goal.title || goal.id}</span>
                    <SubGoalStatus status={goal.status} />
                  </div>
                  <div className="workflow-effort-metric">
                    <span>Attempts <strong>{show(goal.attempts)}</strong></span>
                    {maximumAttempts > 0 && Number.isFinite(goal.attempts) && (
                      <div className="workflow-meter" role="img" aria-label={`${goal.attempts} attempts for ${goal.title || goal.id}, relative to the highest sub-goal`}>
                        <span style={{ width: `${(goal.attempts / maximumAttempts) * 100}%` }} />
                      </div>
                    )}
                  </div>
                  <div className="workflow-effort-metric is-tools">
                    <span>Tool calls <strong>{show(goal.resources?.tool_calls)}</strong></span>
                    {maximumToolCalls > 0 && Number.isFinite(goal.resources?.tool_calls) && (
                      <div className="workflow-meter" role="img" aria-label={`${goal.resources.tool_calls} tool calls for ${goal.title || goal.id}, relative to the highest sub-goal`}>
                        <span style={{ width: `${(goal.resources.tool_calls / maximumToolCalls) * 100}%` }} />
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </article>
        )}
      </section>

      {report.saved_measurements && <details><summary>Available saved measurements</summary>
        <p>{report.saved_measurements.source}</p>
        <p>Recorded tool log entries: {show(report.saved_measurements.recorded_tool_log_entries)} · Recorded model requests: {show(report.saved_measurements.recorded_model_requests)} · Saved recovery episodes: {show(report.saved_measurements.recorded_recovery_episodes)}</p>
        {report.saved_measurements.latest_test && <p>Last stored test report: {report.saved_measurements.latest_test.reported_status} · {report.saved_measurements.latest_test.passed}/{report.saved_measurements.latest_test.total} passed · {report.saved_measurements.latest_test.evidence_version} · {report.saved_measurements.latest_test.freshness}</p>}
        <p>{report.saved_measurements.limitations}</p>
      </details>}
      {!!report.verification_support?.length && <details><summary>Which requirements can be checked?</summary>
        {report.verification_support.map(c => <p key={c.criterion_id}><strong>{c.criterion_id}: {c.description}</strong> — {c.available ? `Checker available: ${c.checker}. Run verification to obtain a result.` : `Unverified until evidence is supplied. ${c.next_step}`}</p>)}
      </details>}

      <dl style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(190px, 1fr))', gap: 10 }}>

        {[

          ['Verified outcome', summary.verified_outcome === true ? 'Verified success' : summary.verified_outcome === false ? 'Verified failure' : 'Unverified'],

          ['Action attempts', show(summary.action_attempts)], ['Model calls', show(summary.model_calls)], ['Workflow stages', show(summary.stages)],

          ['Verified sub-goal progress', percent(summary.progress_rate)],

          ['Repeated actions', show(summary.repeated_actions)],

          ['Observed wall time (s)', show(summary.wall_seconds)],

        ].map(([label, value]) => <div key={label}><dt>{label}</dt><dd style={{ margin: 0, fontWeight: 600 }}>{value}</dd></div>)}

      </dl>

      <details><summary>Resource usage and evidence coverage</summary>
      <p>Incomplete actions: {show(summary.incomplete_actions)} · Duplicate effects: {show(summary.duplicate_effects)} · Dependency checks: {show(summary.dependency_checks)} · Unmapped work: {show(summary.unmapped_actions)}</p>
      <p>Generated tokens: {show(summary.resources?.output_tokens)} · Input tokens: {show(summary.resources?.input_tokens)} · Calls with unknown usage: {show(summary.resources?.unknown_usage_calls)}</p>
      <p>Paired outcomes: {percent(report.coverage.paired_outcomes)} · State evidence: {percent(report.coverage.state_references)} · Sub-goal mapping: {percent(report.coverage.sub_goal_mapping)}</p>
      <p>Known token subtotal: {show(summary.resources?.known_input_tokens)} input / {show(summary.resources?.known_output_tokens)} generated. Unknown requests are excluded from these subtotals.</p>

      <p>Stagnation since {report.stagnation.baseline.replaceAll('_', ' ')}: {show(report.stagnation.actions)} actions / {show(report.stagnation.seconds)} seconds. Preparation can be legitimate.</p>

      </details>
      <details><summary>Sub-goals, attempts and revisits ({subGoals.length})</summary>

      {!subGoals.length ? <p>No explicit sub-goal evidence is available.</p> : <table><thead><tr>{['Sub-goal', 'Reported status', 'Verification', 'Attempts', 'Revisits', 'Regressions', 'Calls (tool/model)', 'Seconds', 'Generated tokens'].map(x => <th key={x}>{x}</th>)}</tr></thead><tbody>

        {subGoals.map(g => <tr key={g.id}><td>{g.id}: {g.title}</td><td>{g.reported_status || 'Unavailable'}</td><td><SubGoalStatus status={g.status} /></td><td>{g.attempts} ({g.incomplete_attempts} incomplete)</td><td>{g.revisits}</td><td>{g.regressions}</td><td>{g.resources.tool_calls}/{g.resources.model_calls}</td><td>{show(g.resources.duration_seconds)}</td><td>{show(g.resources.output_tokens)}</td></tr>)}

      </tbody></table>}

      <p>Tool outcomes: {Object.entries(summary.tool_outcomes || {}).map(([key, value]) => `${key}: ${value}`).join(' · ') || 'Unavailable'}</p>

      <details><summary>Resources by explicit attempt</summary>{(report.attempts || []).map(a => <p key={a.attempt_id}>{a.attempt_id} · {a.sub_goal_id || 'Unmapped'} · {a.outcome} · Tool/model calls: {a.resources.tool_calls}/{a.resources.model_calls} · Seconds: {show(a.resources.duration_seconds)} · Generated tokens: {show(a.resources.output_tokens)}</p>)}</details>

      </details>
      <details><summary>Recovery and repeated-work costs</summary>

      <p>{report.overhead.note}</p>

      <table><thead><tr><th>Group</th><th>Tool calls</th><th>Model calls</th><th>Seconds</th><th>Generated tokens</th></tr></thead><tbody>

        {['recovery','rework','union'].map(k => <tr key={k}><td>{k}</td><td>{show(report.overhead[k].tool_calls)}</td><td>{show(report.overhead[k].model_calls)}</td><td>{show(report.overhead[k].duration_seconds)}</td><td>{show(report.overhead[k].output_tokens)}</td></tr>)}

      </tbody></table>

      {report.recovery.map(r => <p key={r.recovery_id}>{r.recovery_id}: {r.verified_recovery ? 'Independently verified recovery' : 'Recovery not independently verified'} · Later recurrence: {r.recurrence ? 'Yes' : 'Not observed'}</p>)}

      </details>
      <details><summary>Plan versus observed work</summary>{(report.plan_observations || []).map(p => <div key={p.plan_revision}><p>{p.note}</p><p>Planned targets: {p.planned_targets.join(', ') || 'Unavailable'}</p><p>Observed writes: {p.observed_writes.join(', ') || 'None observed'}</p><p>Unobserved targets: {p.unobserved_targets.join(', ') || 'None'}</p><p>Other targets: {p.unplanned_targets.join(', ') || 'None'}</p></div>)}</details>

      <h3>Behavior findings ({findings.length})</h3>

      {findings.slice(findingPage * 20, findingPage * 20 + 20).map(f => <p key={f.id}><button onClick={() => onInspect(f)}>{f.kind.replaceAll('_', ' ')}</button> [{f.confidence}] {f.message}</p>)}

      {!findings.length && <p>No findings in the available evidence. This does not prove optimal behavior.</p>}

      {findings.length > 20 && <p><button disabled={!findingPage} onClick={() => setFindingPage(p => p - 1)}>Previous findings</button> <button disabled={(findingPage + 1) * 20 >= findings.length} onClick={() => setFindingPage(p => p + 1)}>Next findings</button></p>}

      {state.finding && <aside aria-label="Finding evidence"><h4>{state.finding.kind} — evidence</h4><p>{state.finding.message} · {state.finding.detector_version}</p>

        {state.evidence.length === 0 && <p>Loading selected evidence…</p>}

        {state.evidence.map(e => <details key={e.event_id}><summary>Event {e.sequence}: {e.operation || e.kind}</summary><pre style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{JSON.stringify(e, null, 2)}</pre></details>)}

      </aside>}

      <details><summary>Action and progress timeline</summary>

      <table><thead><tr><th>Sequence</th><th>Time</th><th>Event</th><th>Operation / sub-goal</th><th>Outcome / progress</th><th>Evidence</th></tr></thead><tbody>

        {(state.page?.events || []).map(e => {

          const progress = report.progress.find(p => p.event_id === e.event_id);

          return <tr key={e.event_id}><td>{e.sequence}</td><td>{e.timestamp}</td><td>{e.kind}</td><td>{e.operation || e.sub_goal_id || '—'}</td><td>{e.outcome || e.data?.verdict || '—'}{progress && ` · ${progress.verified}/${progress.required} verified`}</td><td><button onClick={() => onInspect({ kind: e.kind, message: 'Recorded event', event_ids: [e.event_id], detector_version: report.version })}>Inspect event {e.sequence}</button></td></tr>;

        })}

      </tbody></table>

      <button disabled={state.loading || state.history.length <= 1} onClick={() => onPage('previous')}>Previous events</button> <button disabled={state.loading || state.page?.next_after == null} onClick={() => onPage('next')}>Next events</button>

      </details>
      <details><summary>Definitions and limitations</summary>{report.limitations.map(text => <p key={text}>{text}</p>)}<p>Mode: {report.execution_mode} · Evaluator: {report.version} · Snapshot: {report.snapshot_sequence}</p><pre style={{ whiteSpace: 'pre-wrap' }}>{JSON.stringify(report.calculation, null, 2)}</pre></details>

    </>}

  </section>;

}



export default function WorkflowAnalysis({ runId, refreshKey }) {

  const [state, setState] = useState({ runId: null, report: null, history: [0], evidence: [] });

  const controller = useMemo(() => createWorkflowController(api, setState), []);

  useEffect(() => { controller.select(runId); return () => controller.dispose(); }, [controller, runId, refreshKey]);

  const visible = state.runId === runId ? state : { runId, report: null, loading: !!runId, history: [0], evidence: [] };

  const download = async () => {

    try {

      const payload = await exportWorkflow(runId);

      const url = URL.createObjectURL(new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' }));

      const anchor = document.createElement('a'); anchor.href = url; anchor.download = `workflow_${runId}.json`; anchor.click(); URL.revokeObjectURL(url);

    } catch (error) { setState(old => old.runId === runId ? { ...old, error: error.message } : old); }

  };

  return <WorkflowView state={visible} onRefresh={() => controller.select(runId)} onPage={controller.page} onInspect={controller.inspect} onExport={download} />;

}
