import React, { useEffect, useMemo, useState } from 'react';
import { fetchWorkflowReport, fetchWorkflowEvents, fetchWorkflowEvent, exportWorkflow } from '../services/api';
import { createWorkflowController } from '../services/workflowController';

const show = value => value == null ? 'Unavailable' : typeof value === 'number' ? Number(value.toFixed(3)).toString() : String(value);

const percent = value => value == null ? 'Unavailable' : `${(value * 100).toFixed(1)}%`;

const api = { report: fetchWorkflowReport, events: fetchWorkflowEvents, event: fetchWorkflowEvent };

/* Clean inline SVG icons for zero external dependencies and fast static test bundling */
const ActivityIcon = ({ size = 16, className = "" }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}><polyline points="22 12 18 12 15 21 9 3 6 12 2 12" /></svg>
);
const RefreshIcon = ({ size = 14, className = "" }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}><path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67" /></svg>
);
const DownloadIcon = ({ size = 14, className = "" }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="7 10 12 15 17 10" /><line x1="12" y1="15" x2="12" y2="3" /></svg>
);
const ChevronDownIcon = ({ size = 16, className = "" }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}><polyline points="6 9 12 15 18 9" /></svg>
);
const CheckCircleIcon = ({ size = 16, className = "" }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" /><polyline points="22 4 12 14.01 9 11.01" /></svg>
);
const LayersIcon = ({ size = 16, className = "" }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}><polygon points="12 2 2 7 12 12 22 7 12 2" /><polyline points="2 17 12 22 22 17" /><polyline points="2 12 12 17 22 12" /></svg>
);
const TargetIcon = ({ size = 16, className = "" }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}><circle cx="12" cy="12" r="10" /><circle cx="12" cy="12" r="6" /><circle cx="12" cy="12" r="2" /></svg>
);
const DatabaseIcon = ({ size = 16, className = "" }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}><ellipse cx="12" cy="5" rx="9" ry="3" /><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3" /><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" /></svg>
);
const CpuIcon = ({ size = 16, className = "" }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}><rect x="4" y="4" width="16" height="16" rx="2" ry="2" /><rect x="9" y="9" width="6" height="6" /><line x1="9" y1="1" x2="9" y2="4" /><line x1="15" y1="1" x2="15" y2="4" /><line x1="9" y1="20" x2="9" y2="23" /><line x1="15" y1="20" x2="15" y2="23" /><line x1="20" y1="9" x2="23" y2="9" /><line x1="20" y1="14" x2="23" y2="14" /><line x1="1" y1="9" x2="4" y2="9" /><line x1="1" y1="14" x2="4" y2="14" /></svg>
);
const ClockIcon = ({ size = 16, className = "" }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}><circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" /></svg>
);
const AlertCircleIcon = ({ size = 16, className = "" }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}><circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" /></svg>
);
const RepeatIcon = ({ size = 16, className = "" }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}><polyline points="17 1 21 5 17 9" /><path d="M3 11V9a4 4 0 0 1 4-4h14" /><polyline points="7 23 3 19 7 15" /><path d="M21 13v2a4 4 0 0 1-4 4H3" /></svg>
);
const ZapIcon = ({ size = 16, className = "" }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" /></svg>
);

function WorkflowMeter({ label, value }) {
  if (!Number.isFinite(value)) return <span className="workflow-meter-unavailable">Unavailable</span>;
  const ratio = Math.max(0, Math.min(1, value));
  const percentage = ratio * 100;
  return (
    <div className="workflow-meter" role="progressbar" aria-label={label} aria-valuemin={0} aria-valuemax={100} aria-valuenow={percentage}>
      <span style={{ width: `${percentage}%` }} />
    </div>
  );
}

function WorkflowProgressRing({ value, verified, required }) {
  const hasProgress = Number.isFinite(value);
  const ratio = hasProgress ? Math.max(0, Math.min(1, value)) : 0;
  const radius = 30;
  const circumference = 2 * Math.PI * radius;
  return (
    <div className="workflow-progress-ring" role={hasProgress ? 'img' : undefined}
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
    </div>
  );
}

function SubGoalStatus({ status }) {
  const label = status || 'unverified';
  const knownStatuses = ['verified', 'failed', 'stale', 'unverified'];
  return <span className={`workflow-status-chip ${knownStatuses.includes(label) ? `is-${label}` : ''}`}>{label}</span>;
}

export function WorkflowView({ state, onRefresh, onPage, onInspect, onExport }) {
  const [findingPage, setFindingPage] = useState(0);
  const [copiedRun, setCopiedRun] = useState(false);

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

  const taskVerification = report?.task_verification_status || (
    summary?.verified_outcome === true ? 'verified_passed' :
    summary?.verified_outcome === false ? 'verified_failed' :
    (summary?.verified_sub_goals && summary?.required_sub_goals && summary.verified_sub_goals === summary.required_sub_goals) ? 'verified_passed' :
    'unverified'
  );

  const evidenceCompleteness = report?.workflow_evidence_completeness || (
    report?.evidence_status === 'observed' ? 'complete' :
    report?.evidence_status === 'partial' ? 'partial' :
    'unavailable'
  );

  const mappingCoverage = report?.sub_goal_mapping_coverage || {
    mapped_percentage: report?.coverage?.sub_goal_mapping != null ? +(report.coverage.sub_goal_mapping * 100).toFixed(1) : 0,
    unmapped_percentage: report?.coverage?.sub_goal_mapping != null ? +(100 - (report.coverage.sub_goal_mapping * 100)).toFixed(1) : 0,
    mapped_actions: report?.coverage?.mapped_actions,
    unmapped_actions: report?.coverage?.unmapped_actions ?? summary?.unmapped_actions,
    total_actions: (report?.coverage?.mapped_actions != null && report?.coverage?.unmapped_actions != null) ? (report.coverage.mapped_actions + report.coverage.unmapped_actions) : null
  };

  const partialReasons = report?.partial_evidence_reasons || [];

  useEffect(() => setFindingPage(0), [report]);

  const copyRunId = () => {
    if (state.runId) {
      navigator.clipboard?.writeText(state.runId);
      setCopiedRun(true);
      setTimeout(() => setCopiedRun(false), 2000);
    }
  };

  return (
    <section className="card-panel evaluation-workflow" aria-label="Actual Workflow Analysis">
      {/* Sleek Hero Header */}
      <div className="wf-hero-header">
        <div className="wf-hero-title-group">
          <span className="wf-eyebrow">
            <ActivityIcon size={12} /> Live Workflow Telemetry & Audit
          </span>
          <h2>
            Actual Workflow Analysis
          </h2>
          <p>See how much work the agent performed, where it repeated work, and which sub-goals have verified evidence.</p>
        </div>

        <div className="wf-toolbar">
          {!state.runId && <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>Select a run to inspect its workflow.</p>}

          {state.runId && (
            <>
              <div className="wf-run-pill" title="Click to copy Run ID" onClick={copyRunId} style={{ cursor: 'pointer' }}>
                <span style={{ color: 'var(--text-secondary)' }}>Run:</span>
                <span>{state.runId}</span>
                <span style={{ fontSize: '0.65rem', color: copiedRun ? 'var(--success-color)' : 'var(--text-muted)' }}>
                  {copiedRun ? '✓ Copied' : '📋'}
                </span>
              </div>
              <button
                type="button"
                className="wf-btn wf-btn-primary"
                disabled={state.loading}
                onClick={onRefresh}
              >
                <RefreshIcon size={14} className={state.loading ? 'rotating-spin' : ''} />
                Refresh workflow
              </button>
              <button
                type="button"
                className="wf-btn"
                disabled={!report}
                onClick={onExport}
              >
                <DownloadIcon size={14} />
                Export workflow evidence
              </button>
            </>
          )}
        </div>
      </div>

      {state.loading && (
        <div className="wf-alert-banner" role="status" style={{ background: 'var(--accent-primary-subtle)', borderColor: 'var(--accent-primary-border)', color: 'var(--accent-primary)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <RefreshIcon size={16} className="rotating-spin" />
            <span>Loading workflow evidence…</span>
          </div>
        </div>
      )}

      {state.error && (
        <div className="wf-alert-banner" role="alert" style={{ background: 'var(--danger-subtle)', borderColor: 'var(--danger-border)', color: 'var(--danger-color)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <AlertCircleIcon size={16} />
            <span>{state.error}</span>
          </div>
        </div>
      )}

      {report && (
        <>
          {/* Tri-Status Strip (Task Verification, Evidence Completeness, Sub-Goal Mapping) */}
          <div className="wf-status-group" style={{ marginBottom: 14 }} aria-label="Workflow execution and evidence statuses">
            <span className={`wf-status-badge is-${taskVerification}`} title="Task verification: verified passed, verified failed, or unverified.">
              <TargetIcon size={14} />
              Task: {taskVerification === 'verified_passed' ? 'Verified Passed' : taskVerification === 'verified_failed' ? 'Verified Failed' : 'Unverified'}
            </span>
            <span className={`wf-status-badge is-${evidenceCompleteness}`} title="Workflow evidence completeness: complete, partial, or unavailable.">
              <ActivityIcon size={14} />
              Evidence: {evidenceCompleteness === 'complete' ? 'Complete Evidence' : evidenceCompleteness === 'partial' ? 'Partial Evidence' : 'Unavailable'}
            </span>
            <span className="wf-status-badge" title="Sub-goal mapping coverage: mapped versus unmapped recorded activity.">
              <LayersIcon size={14} />
              Mapping: {percent(report.coverage?.sub_goal_mapping)} ({mappingCoverage.mapped_percentage}% mapped{mappingCoverage.unmapped_percentage > 0 ? ` / ${mappingCoverage.unmapped_percentage}% unmapped` : ''})
            </span>
          </div>

          {/* Evidence Notice Banner */}
          <div className={`wf-alert-banner is-${report.evidence_status || 'unavailable'}`}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
              <span className={`wf-pill-badge is-${report.evidence_status || 'unavailable'}`} style={{ fontWeight: 700 }}>
                Evidence: {report.evidence_status}
              </span>
              <span title="Detailed event data is available in the timeline below." style={{ fontWeight: 500 }}>
                Only recorded actions are counted.
              </span>
            </div>
            <span style={{ fontSize: '0.75rem', opacity: 0.9 }}>
              {report.evidence_status === 'unavailable'
                ? 'This historical run has no structured action evidence. Missing actions and completion are not reconstructed from logs.'
                : 'Refresh to observe new activity. Unfinished actions remain incomplete.'}
            </span>
          </div>

          {/* Partial Evidence Explanation Box */}
          {(evidenceCompleteness === 'partial' || report.evidence_status === 'partial') && (
            <div className="wf-partial-explanation" role="region" aria-label="Partial evidence explanation">
              <div className="wf-partial-explanation-header">
                <AlertCircleIcon size={15} />
                <span>Why is workflow evidence partial?</span>
              </div>
              <ul className="wf-partial-explanation-list">
                {partialReasons.length > 0 ? (
                  partialReasons.map((r, i) => <li key={i}>{r}</li>)
                ) : (
                  <>
                    {mappingCoverage.unmapped_actions > 0 && (
                      <li>
                        {mappingCoverage.unmapped_actions} of {mappingCoverage.total_actions || 'all'} recorded action(s) ({mappingCoverage.unmapped_percentage}%) were executed outside sub-goal scopes (e.g. preliminary inspection, planning, or independent verification).
                      </li>
                    )}
                    <li>All required sub-goals may be verified, but non-scoped telemetry remains unmapped.</li>
                  </>
                )}
              </ul>
            </div>
          )}

          {/* Visual Overview: Run at a glance */}
          <section className="workflow-visual-overview" aria-label="Workflow visual summary">
            <div className="workflow-overview-header">
              <div>
                <h3>Run at a glance</h3>
                <p>Verified progress and observed execution activity for this workflow.</p>
              </div>
              <div className="wf-status-group">
                <span className={`workflow-evidence-badge is-${taskVerification}`}>
                  {taskVerification === 'verified_passed' ? 'Verified passed' : taskVerification === 'verified_failed' ? 'Verified failed' : 'Unverified task'}
                </span>
                <span className={`workflow-evidence-badge is-${report.evidence_status || 'unavailable'}`}>
                  {String(report.evidence_status || 'unavailable').replaceAll('_', ' ')} evidence
                </span>
              </div>
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
                {subGoals.length === 0 ? (
                  <p className="workflow-chart-empty">No explicit sub-goal evidence is available.</p>
                ) : (
                  <>
                    <div className="workflow-status-stack" role="img" aria-label={`${statusCounts.verified} verified, ${statusCounts.failed} failed, ${statusCounts.stale} stale, ${statusCounts.unverified} unverified sub-goals`}>
                      {[
                        ['verified', '#10B981'],
                        ['failed', '#EF4444'],
                        ['stale', '#F59E0B'],
                        ['unverified', '#475569'],
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
                        <span key={status}>
                          <i className={`workflow-legend-dot is-${status}`} />
                          {label} <strong>{statusCounts[status]}</strong>
                        </span>
                      ))}
                    </div>
                  </>
                )}
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

          {/* Core Telemetry KPI Deck (The 7 Pillars) */}
          <dl className="wf-kpi-deck" aria-label="Core workflow telemetry metrics">
            {[
              ['Verified outcome', summary.verified_outcome === true ? 'Verified success' : summary.verified_outcome === false ? 'Verified failure' : 'Unverified'],
              ['Action attempts', show(summary.action_attempts)],
              ['Model calls', show(summary.model_calls)],
              ['Workflow stages', show(summary.stages)],
              ['Verified sub-goal progress', percent(summary.progress_rate)],
              ['Repeated actions', show(summary.repeated_actions)],
              ['Observed wall time (s)', show(summary.wall_seconds)],
            ].map(([label, value]) => {
              const iconMap = {
                'Verified outcome': <TargetIcon size={14} />,
                'Action attempts': <ZapIcon size={14} />,
                'Model calls': <CpuIcon size={14} />,
                'Workflow stages': <LayersIcon size={14} />,
                'Verified sub-goal progress': <CheckCircleIcon size={14} />,
                'Repeated actions': <RepeatIcon size={14} />,
                'Observed wall time (s)': <ClockIcon size={14} />,
              };
              return (
                <div key={label} className="wf-kpi-tile">
                  <div className="wf-kpi-header">
                    <dt>{label}</dt>
                    <span style={{ color: 'var(--accent-primary)', opacity: 0.8 }}>{iconMap[label] || <ActivityIcon size={14} />}</span>
                  </div>
                  <dd>
                    {label === 'Verified outcome' && value === 'Verified success' ? (
                      <span style={{ color: 'var(--success-color)' }}>✓ {value}</span>
                    ) : label === 'Verified outcome' && value === 'Verified failure' ? (
                      <span style={{ color: 'var(--danger-color)' }}>✗ {value}</span>
                    ) : (
                      value
                    )}
                  </dd>
                </div>
              );
            })}
          </dl>

          {/* Section: Available Saved Measurements */}
          {report.saved_measurements && (
            <details className="wf-accordion" open>
              <summary className="wf-accordion-summary">
                <div className="wf-accordion-title">
                  <span className="wf-accordion-icon"><DatabaseIcon size={15} /></span>
                  <span>Available saved measurements</span>
                </div>
                <ChevronDownIcon size={16} className="wf-chevron" />
              </summary>
              <div className="wf-accordion-body">
                <p style={{ fontWeight: 600, color: 'var(--text-primary)', marginBottom: 8 }}>{report.saved_measurements.source}</p>
                <div className="wf-badge-strip">
                  <span className="wf-pill-badge">
                    <span className="wf-dot wf-dot-success" /> Recorded tool log entries: <strong>{show(report.saved_measurements.recorded_tool_log_entries)}</strong>
                  </span>
                  <span className="wf-pill-badge">
                    <span className="wf-dot wf-dot-warning" /> Recorded model requests: <strong>{show(report.saved_measurements.recorded_model_requests)}</strong>
                  </span>
                  <span className="wf-pill-badge">
                    <span className="wf-dot wf-dot-muted" /> Saved recovery episodes: <strong>{show(report.saved_measurements.recorded_recovery_episodes)}</strong>
                  </span>
                </div>
                {report.saved_measurements.latest_test && (
                  <div className="wf-alert-banner is-observed" style={{ margin: '10px 0' }}>
                    <span>
                      Last stored test report: <strong>{report.saved_measurements.latest_test.reported_status}</strong> · {report.saved_measurements.latest_test.passed}/{report.saved_measurements.latest_test.total} passed · {report.saved_measurements.latest_test.evidence_version} · {report.saved_measurements.latest_test.freshness}
                    </span>
                  </div>
                )}
                <p style={{ color: 'var(--text-muted)', fontSize: '0.74rem', marginTop: 8 }}>{report.saved_measurements.limitations}</p>
              </div>
            </details>
          )}

          {/* Section: Which requirements can be checked? */}
          {!!report.verification_support?.length && (
            <details className="wf-accordion">
              <summary className="wf-accordion-summary">
                <div className="wf-accordion-title">
                  <span className="wf-accordion-icon"><CheckCircleIcon size={15} /></span>
                  <span>Which requirements can be checked?</span>
                </div>
                <ChevronDownIcon size={16} className="wf-chevron" />
              </summary>
              <div className="wf-accordion-body">
                <div style={{ display: 'grid', gap: 10 }}>
                  {report.verification_support.map(c => (
                    <div key={c.criterion_id} style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', padding: '10px 14px', background: 'var(--bg-card-subtle)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)', gap: 12 }}>
                      <div>
                        <strong>{c.criterion_id}: {c.description}</strong> — {c.available ? `Checker available: ${c.checker}. Run verification to obtain a result.` : `Unverified until evidence is supplied. ${c.next_step}`}
                      </div>
                      <span className={`wf-pill-badge ${c.available ? 'is-observed' : ''}`} style={{ flexShrink: 0 }}>
                        {c.available ? 'Ready to check' : 'Evidence required'}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </details>
          )}

          {/* Section: Resource Usage & Evidence Coverage */}
          <details className="wf-accordion">
            <summary className="wf-accordion-summary">
              <div className="wf-accordion-title">
                <span className="wf-accordion-icon"><LayersIcon size={15} /></span>
                <span>Resource usage and evidence coverage</span>
              </div>
              <ChevronDownIcon size={16} className="wf-chevron" />
            </summary>
            <div className="wf-accordion-body">
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 14 }}>
                <div style={{ padding: 12, background: 'var(--bg-card-subtle)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
                  <strong style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', textTransform: 'uppercase' }}>Action Tracking</strong>
                  <p style={{ marginTop: 6 }}>Incomplete actions: <strong>{show(summary.incomplete_actions)}</strong> · Duplicate effects: <strong>{show(summary.duplicate_effects)}</strong></p>
                  <p>Dependency checks: <strong>{show(summary.dependency_checks)}</strong> · Unmapped work: <strong>{show(summary.unmapped_actions)}</strong></p>
                </div>
                <div style={{ padding: 12, background: 'var(--bg-card-subtle)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
                  <strong style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', textTransform: 'uppercase' }}>Token & Model Usage</strong>
                  <p style={{ marginTop: 6 }}>Generated tokens: <strong>{show(summary.resources?.output_tokens)}</strong> · Input tokens: <strong>{show(summary.resources?.input_tokens)}</strong></p>
                  <p>Calls with unknown usage: <strong>{show(summary.resources?.unknown_usage_calls)}</strong></p>
                  <p style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Known token subtotal: {show(summary.resources?.known_input_tokens)} input / {show(summary.resources?.known_output_tokens)} generated. Unknown requests are excluded from these subtotals.</p>
                </div>
                <div style={{ padding: 12, background: 'var(--bg-card-subtle)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
                  <strong style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', textTransform: 'uppercase' }}>Coverage & Velocity</strong>
                  <p style={{ marginTop: 6 }}>Paired outcomes: <strong>{percent(report.coverage?.paired_outcomes)}</strong> · State evidence: <strong>{percent(report.coverage?.state_references)}</strong></p>
                  <p>Sub-goal mapping: <strong>{percent(report.coverage?.sub_goal_mapping)}</strong></p>
                  <p style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Stagnation since {report.stagnation?.baseline ? report.stagnation.baseline.replaceAll('_', ' ') : 'baseline'}: {show(report.stagnation?.actions)} actions / {show(report.stagnation?.seconds)} seconds. Preparation can be legitimate.</p>
                </div>
              </div>
            </div>
          </details>

          {/* Section: Sub-goals, attempts and revisits */}
          <details className="wf-accordion" open>
            <summary className="wf-accordion-summary">
              <div className="wf-accordion-title">
                <span className="wf-accordion-icon"><TargetIcon size={15} /></span>
                <span>Sub-goals, attempts and revisits ({subGoals.length})</span>
              </div>
              <ChevronDownIcon size={16} className="wf-chevron" />
            </summary>
            <div className="wf-accordion-body">
              {!subGoals.length ? (
                <p className="workflow-chart-empty">No explicit sub-goal evidence is available.</p>
              ) : (
                <div className="wf-table-wrapper">
                  <table className="wf-table">
                    <thead>
                      <tr>
                        {['Sub-goal', 'Reported status', 'Verification', 'Attempts', 'Revisits', 'Regressions', 'Calls (tool/model)', 'Seconds', 'Generated tokens'].map(x => <th key={x}>{x}</th>)}
                      </tr>
                    </thead>
                    <tbody>
                      {subGoals.map(g => (
                        <tr key={g.id}>
                          <td><strong>{g.id}</strong>: {g.title}</td>
                          <td><span className="wf-pill-badge">{g.reported_status || 'Unavailable'}</span></td>
                          <td><SubGoalStatus status={g.status} /></td>
                          <td className="wf-mono">{g.attempts} ({g.incomplete_attempts} incomplete)</td>
                          <td className="wf-mono">{g.revisits}</td>
                          <td className="wf-mono">{g.regressions > 0 ? <span style={{ color: 'var(--danger-color)', fontWeight: 700 }}>{g.regressions}</span> : g.regressions}</td>
                          <td className="wf-mono">{g.resources.tool_calls}/{g.resources.model_calls}</td>
                          <td className="wf-mono">{show(g.resources.duration_seconds)}</td>
                          <td className="wf-mono">{show(g.resources.output_tokens)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              <div style={{ marginTop: 14 }}>
                <strong style={{ fontSize: '0.72rem', textTransform: 'uppercase', color: 'var(--text-secondary)' }}>Tool Outcomes:</strong>
                <div className="wf-badge-strip">
                  {Object.keys(summary.tool_outcomes || {}).length ? (
                    Object.entries(summary.tool_outcomes).map(([key, value]) => {
                      const dotClass = key === 'success' ? 'wf-dot-success' : key === 'failed' || key === 'error' ? 'wf-dot-danger' : 'wf-dot-warning';
                      return (
                        <span key={key} className="wf-pill-badge">
                          <span className={`wf-dot ${dotClass}`} />
                          {key}: <strong>{value}</strong>
                        </span>
                      );
                    })
                  ) : (
                    <span className="wf-pill-badge">Tool outcomes: Unavailable</span>
                  )}
                </div>
              </div>

              <details className="wf-nested-accordion">
                <summary>Resources by explicit attempt ({report.attempts?.length || 0})</summary>
                <div style={{ padding: 12, display: 'grid', gap: 8 }}>
                  {(report.attempts || []).map(a => (
                    <div key={a.attempt_id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 12px', background: 'var(--bg-card)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)', flexWrap: 'wrap', gap: 8 }}>
                      <span className="wf-mono" style={{ fontWeight: 600 }}>{a.attempt_id}</span>
                      <span className="wf-pill-badge">{a.sub_goal_id || 'Unmapped'}</span>
                      <span className="wf-pill-badge">{a.outcome}</span>
                      <span className="wf-mono" style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Tool/model calls: {a.resources.tool_calls}/{a.resources.model_calls} · Seconds: {show(a.resources.duration_seconds)} · Generated tokens: {show(a.resources.output_tokens)}</span>
                    </div>
                  ))}
                </div>
              </details>
            </div>
          </details>

          {/* Section: Recovery and repeated-work costs */}
          <details className="wf-accordion">
            <summary className="wf-accordion-summary">
              <div className="wf-accordion-title">
                <span className="wf-accordion-icon"><RepeatIcon size={15} /></span>
                <span>Recovery and repeated-work costs</span>
              </div>
              <ChevronDownIcon size={16} className="wf-chevron" />
            </summary>
            <div className="wf-accordion-body">
              <p style={{ color: 'var(--text-secondary)', marginBottom: 12 }}>{report.overhead.note}</p>
              <div className="wf-table-wrapper">
                <table className="wf-table">
                  <thead>
                    <tr>
                      <th>Group</th>
                      <th>Tool calls</th>
                      <th>Model calls</th>
                      <th>Seconds</th>
                      <th>Generated tokens</th>
                    </tr>
                  </thead>
                  <tbody>
                    {['recovery', 'rework', 'union'].map(k => (
                      <tr key={k}>
                        <td><span className="wf-pill-badge" style={{ textTransform: 'capitalize' }}>{k}</span></td>
                        <td className="wf-mono">{show(report.overhead[k].tool_calls)}</td>
                        <td className="wf-mono">{show(report.overhead[k].model_calls)}</td>
                        <td className="wf-mono">{show(report.overhead[k].duration_seconds)}</td>
                        <td className="wf-mono">{show(report.overhead[k].output_tokens)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {report.recovery?.length > 0 && (
                <div style={{ marginTop: 12, display: 'grid', gap: 8 }}>
                  {report.recovery.map(r => (
                    <div key={r.recovery_id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 12px', background: 'var(--bg-card-subtle)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
                      <strong>{r.recovery_id}</strong>
                      <span>{r.verified_recovery ? 'Independently verified recovery' : 'Recovery not independently verified'}</span>
                      <span className="wf-pill-badge">Later recurrence: {r.recurrence ? 'Yes' : 'Not observed'}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </details>

          {/* Section: Plan versus observed work */}
          <details className="wf-accordion">
            <summary className="wf-accordion-summary">
              <div className="wf-accordion-title">
                <span className="wf-accordion-icon"><LayersIcon size={15} /></span>
                <span>Plan versus observed work</span>
              </div>
              <ChevronDownIcon size={16} className="wf-chevron" />
            </summary>
            <div className="wf-accordion-body">
              {(report.plan_observations || []).map(p => (
                <div key={p.plan_revision} style={{ padding: 12, background: 'var(--bg-card-subtle)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)', marginBottom: 10 }}>
                  <p style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{p.note}</p>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 8, marginTop: 8 }}>
                    <div className="wf-pill-badge">Planned targets: {p.planned_targets.join(', ') || 'Unavailable'}</div>
                    <div className="wf-pill-badge">Observed writes: {p.observed_writes.join(', ') || 'None observed'}</div>
                    <div className="wf-pill-badge">Unobserved targets: {p.unobserved_targets.join(', ') || 'None'}</div>
                    <div className="wf-pill-badge">Other targets: {p.unplanned_targets.join(', ') || 'None'}</div>
                  </div>
                </div>
              ))}
            </div>
          </details>

          {/* Section: Behavior findings */}
          <div style={{ marginTop: 20 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12, flexWrap: 'wrap', gap: 8 }}>
              <h3 style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--text-primary)', margin: 0, display: 'flex', alignItems: 'center', gap: 8 }}>
                <AlertCircleIcon size={16} style={{ color: 'var(--warning-color)' }} />
                Behavior findings ({findings.length})
              </h3>
              {findings.length > 0 && (
                <span style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                  {findings.reduce((sum, f) => sum + (f.occurrence_count || 1), 0)} total recorded occurrence(s)
                </span>
              )}
            </div>

            {findings.length === 0 ? (
              <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>No findings in the available evidence. This does not prove optimal behavior.</p>
            ) : (
              <div className="wf-findings-container">
                {findings.slice(findingPage * 20, findingPage * 20 + 20).map(f => {
                  const title = f.title || (f.kind ? f.kind.replaceAll('_', ' ') : 'Behavior finding');
                  const status = f.status || f.confidence || 'observed';
                  const hasMultiple = (f.occurrence_count || 1) > 1;
                  const prereqStep = f.prerequisite_step ?? f.details?.prerequisite_step;
                  const depStep = f.dependent_step ?? f.details?.dependent_step;
                  const prereqSg = f.prerequisite ?? f.prerequisite_sub_goals?.join(', ') ?? f.details?.prerequisite;
                  const depSg = f.dependent_sub_goal ?? f.details?.dependent_sub_goal;

                  return (
                    <details key={f.id} className="wf-finding-card">
                      <summary className="wf-finding-summary-btn" role="button" tabIndex={0} aria-label={`Finding: ${title}, Status: ${status}`}>
                        <div className="wf-finding-summary-left">
                          <span className={`wf-finding-chip is-${status}`}>
                            {status}
                          </span>
                          <span className="wf-finding-title">{title}</span>
                          {f.confidence && (
                            <span className="wf-pill-badge" style={{ fontWeight: 600, fontSize: '0.7rem' }}>
                              [{f.confidence}]
                            </span>
                          )}
                          {(prereqStep != null || depStep != null) && (
                            <span className="wf-finding-step-pill" title="Plan step dependency">
                              Step {prereqStep ?? '?'} → Step {depStep ?? '?'}
                            </span>
                          )}
                          {(prereqSg || depSg) && (
                            <span className="wf-finding-step-pill" title="Sub-goal dependency">
                              {prereqSg ? `Prereq: ${prereqSg}` : ''} {depSg ? `→ SG: ${depSg}` : ''}
                            </span>
                          )}
                          {hasMultiple && (
                            <span className="wf-finding-count-badge" title={`${f.occurrence_count} occurrences detected across tool actions`}>
                              {f.occurrence_count}× occurrences
                            </span>
                          )}
                        </div>
                        <ChevronDownIcon size={16} className="wf-chevron" />
                      </summary>

                      <div className="wf-finding-body">
                        {f.reason && (
                          <div className="wf-finding-reason">
                            <strong>Reason:</strong> {f.reason}
                          </div>
                        )}
                        {f.message && f.message !== f.reason && (
                          <div style={{ color: 'var(--text-secondary)', fontSize: '0.78rem' }}>
                            {f.message}
                          </div>
                        )}
                        {f.recommended_action && (
                          <div className="wf-finding-action">
                            <ZapIcon size={14} style={{ flexShrink: 0, marginTop: 2 }} />
                            <div>
                              <strong>Recommended Action:</strong> {f.recommended_action}
                            </div>
                          </div>
                        )}

                        <div className="wf-finding-tech-details">
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
                            <div>
                              <span style={{ color: 'var(--text-secondary)' }}>Detector:</span> {f.detector_version || 'v1'} ·{' '}
                              <span style={{ color: 'var(--text-secondary)' }}>Referenced events:</span> {f.event_ids?.length || 1}
                              {f.first_seen && (
                                <> · <span style={{ color: 'var(--text-secondary)' }}>First seen:</span> {f.first_seen}</>
                              )}
                            </div>
                            <button
                              type="button"
                              className="wf-btn"
                              style={{ fontSize: '0.72rem', padding: '4px 10px' }}
                              onClick={(e) => {
                                e.preventDefault();
                                onInspect(f);
                              }}
                            >
                              <ActivityIcon size={12} /> Inspect Event Evidence
                            </button>
                          </div>
                        </div>
                      </div>
                    </details>
                  );
                })}
              </div>
            )}

            {findings.length > 20 && (
              <div style={{ display: 'flex', gap: 10, marginTop: 10 }}>
                <button type="button" className="wf-btn" disabled={!findingPage} onClick={() => setFindingPage(p => p - 1)}>
                  Previous findings
                </button>
                <button type="button" className="wf-btn" disabled={(findingPage + 1) * 20 >= findings.length} onClick={() => setFindingPage(p => p + 1)}>
                  Next findings
                </button>
              </div>
            )}

            {state.finding && (
              <aside aria-label="Finding evidence" style={{ marginTop: 14, padding: 14, background: 'var(--bg-card-subtle)', border: '1px solid var(--border-strong)', borderRadius: 'var(--radius-md)' }}>
                <h4 style={{ fontSize: '0.9rem', fontWeight: 700 }}>{state.finding.kind} — evidence</h4>
                <p style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>{state.finding.message} · {state.finding.detector_version}</p>

                {state.evidence.length === 0 && <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Loading selected evidence…</p>}

                <div style={{ display: 'grid', gap: 8, marginTop: 10 }}>
                  {state.evidence.map(e => (
                    <details key={e.event_id} className="wf-nested-accordion">
                      <summary>Event {e.sequence}: {e.operation || e.kind}</summary>
                      <pre style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere', padding: 10, background: 'var(--bg-card)', borderRadius: 'var(--radius-sm)', fontSize: '0.75rem', fontFamily: 'var(--font-mono)' }}>
                        {JSON.stringify(e, null, 2)}
                      </pre>
                    </details>
                  ))}
                </div>
              </aside>
            )}
          </div>

          {/* Section: Action and progress timeline */}
          <details className="wf-accordion" style={{ marginTop: 20 }}>
            <summary className="wf-accordion-summary">
              <div className="wf-accordion-title">
                <span className="wf-accordion-icon"><ClockIcon size={15} /></span>
                <span>Action and progress timeline</span>
              </div>
              <ChevronDownIcon size={16} className="wf-chevron" />
            </summary>
            <div className="wf-accordion-body">
              <div className="wf-table-wrapper">
                <table className="wf-table">
                  <thead>
                    <tr>
                      <th>Sequence</th>
                      <th>Time</th>
                      <th>Event</th>
                      <th>Operation / sub-goal</th>
                      <th>Outcome / progress</th>
                      <th>Evidence</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(state.page?.events || []).map(e => {
                      const progress = (report.progress || []).find(p => p.event_id === e.event_id);
                      return (
                        <tr key={e.event_id}>
                          <td className="wf-mono"><strong>#{e.sequence}</strong></td>
                          <td className="wf-mono" style={{ color: 'var(--text-muted)' }}>{e.timestamp}</td>
                          <td><span className="wf-pill-badge">{e.kind}</span></td>
                          <td>{e.operation || e.sub_goal_id || '—'}</td>
                          <td>
                            {e.outcome || e.data?.verdict || '—'}
                            {progress && ` · ${progress.verified}/${progress.required} verified`}
                          </td>
                          <td>
                            <button
                              type="button"
                              className="wf-btn"
                              style={{ padding: '3px 8px', fontSize: '0.72rem' }}
                              onClick={() => onInspect({ kind: e.kind, message: 'Recorded event', event_ids: [e.event_id], detector_version: report.version })}
                            >
                              Inspect event {e.sequence}
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              <div style={{ display: 'flex', gap: 10, marginTop: 12 }}>
                <button
                  type="button"
                  className="wf-btn"
                  disabled={state.loading || state.history.length <= 1}
                  onClick={() => onPage('previous')}
                >
                  Previous events
                </button>
                <button
                  type="button"
                  className="wf-btn"
                  disabled={state.loading || state.page?.next_after == null}
                  onClick={() => onPage('next')}
                >
                  Next events
                </button>
              </div>
            </div>
          </details>

          {/* Section: Definitions and limitations */}
          <details className="wf-accordion">
            <summary className="wf-accordion-summary">
              <div className="wf-accordion-title">
                <span className="wf-accordion-icon"><AlertCircleIcon size={15} /></span>
                <span>Definitions and limitations</span>
              </div>
              <ChevronDownIcon size={16} className="wf-chevron" />
            </summary>
            <div className="wf-accordion-body">
              {(report.limitations || []).map(text => <p key={text} style={{ marginBottom: 6 }}>• {text}</p>)}
              <div className="wf-badge-strip" style={{ marginTop: 10 }}>
                <span className="wf-pill-badge">Mode: <strong>{report.execution_mode}</strong></span>
                <span className="wf-pill-badge">Evaluator: <strong>{report.version}</strong></span>
                <span className="wf-pill-badge">Snapshot: <strong>{report.snapshot_sequence}</strong></span>
              </div>
              <pre style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere', padding: 12, background: 'var(--bg-card-subtle)', borderRadius: 'var(--radius-sm)', fontSize: '0.72rem', fontFamily: 'var(--font-mono)', marginTop: 10 }}>
                {JSON.stringify(report.calculation, null, 2)}
              </pre>
            </div>
          </details>
        </>
      )}
    </section>
  );
}

export default function WorkflowAnalysis({ runId, refreshKey }) {
  const [state, setState] = useState({ runId: null, report: null, history: [0], evidence: [] });
  const controller = useMemo(() => createWorkflowController(api, setState), []);

  useEffect(() => {
    controller.select(runId);
    return () => controller.dispose();
  }, [controller, runId, refreshKey]);

  const visible = state.runId === runId ? state : { runId, report: null, loading: !!runId, history: [0], evidence: [] };

  const download = async () => {
    try {
      const payload = await exportWorkflow(runId);
      const url = URL.createObjectURL(new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' }));
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = `workflow_${runId}.json`;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      setState(old => old.runId === runId ? { ...old, error: error.message } : old);
    }
  };

  return (
    <WorkflowView
      state={visible}
      onRefresh={() => controller.select(runId)}
      onPage={controller.page}
      onInspect={controller.inspect}
      onExport={download}
    />
  );
}
