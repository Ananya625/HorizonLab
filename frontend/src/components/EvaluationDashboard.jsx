import React, { useState, useEffect, useRef } from 'react';
import {
  BarChart3,
  RefreshCw,
  Download,
  Activity,
} from 'lucide-react';
import {
  fetchEvaluationDashboard,
  exportRun,
  fetchRunRecovery,
} from '../services/api';
import BenchmarkPanel from './BenchmarkPanel';
import BenchmarkStudies from './BenchmarkStudies';
import WorkflowAnalysis from './WorkflowAnalysis';

function StatusPill({ status }) {
  const colors = {
    measured: { bg: 'rgba(16, 185, 129, 0.15)', text: '#34D399', border: 'rgba(16, 185, 129, 0.35)' },
    insufficient_evidence: { bg: 'rgba(148, 163, 184, 0.12)', text: '#94A3B8', border: 'rgba(148, 163, 184, 0.25)' },
  };
  const c = colors[status] || colors.insufficient_evidence;
  return (
    <span style={{
      fontSize: '0.65rem', padding: '2px 8px', borderRadius: '9999px',
      background: c.bg, color: c.text, border: `1px solid ${c.border}`,
      fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em'
    }}>
      {status === 'insufficient_evidence' ? 'no data yet' : status}
    </span>
  );
}

function PercentageMeter({ label, value, color = '#6257D9' }) {
  if (!Number.isFinite(value)) return null;
  const percentage = Math.max(0, Math.min(100, value));
  return (
    <div
      className="evaluation-meter"
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={percentage}
    >
      <span className="evaluation-meter-fill" style={{ width: `${percentage}%`, backgroundColor: color }} />
    </div>
  );
}

function MetricCell({ label, value, color = '#F1F5F9', sub, badge, visual }) {
  return (
    <div style={{ background: '#0D1526', padding: '14px 16px', borderRadius: '8px', border: '1px solid rgba(255, 255, 255, 0.08)' }}>
      <div style={{ color: '#94A3B8', fontSize: '0.68rem', textTransform: 'uppercase', marginBottom: '4px', fontWeight: 500 }}>{label}</div>
      <div style={{ color, fontSize: '1.25rem', fontWeight: 700 }}>{value}</div>
      {sub && <div style={{ color: '#94A3B8', fontSize: '0.7rem', marginTop: '4px' }}>{sub}</div>}
      {visual && <div style={{ marginTop: '10px' }}>{visual}</div>}
      {badge && <div style={{ marginTop: '6px' }}>{badge}</div>}
    </div>
  );
}

function TestDoughnutChart({ passed = 0, failed = 0, skipped = 0, total = 0 }) {
  const totalCount = total > 0 ? total : (passed + failed + skipped);
  const r = 38;
  const c = 2 * Math.PI * r;
  const pFraction = totalCount > 0 ? (passed / totalCount) : 0;
  const fFraction = totalCount > 0 ? (failed / totalCount) : 0;
  const sFraction = totalCount > 0 ? (skipped / totalCount) : 0;

  const pStroke = pFraction * c;
  const fStroke = fFraction * c;
  const sStroke = sFraction * c;

  const fOffset = -pStroke;
  const sOffset = -(pStroke + fStroke);

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '20px', flexWrap: 'wrap' }}>
      <div style={{ position: 'relative', width: '96px', height: '96px', flexShrink: 0 }}>
        <svg width="96" height="96" viewBox="0 0 100 100" style={{ transform: 'rotate(-90deg)' }}>
          <circle cx="50" cy="50" r={r} fill="none" stroke="#E5E7EF" strokeWidth="12" />
          {totalCount > 0 && pStroke > 0 && (
            <circle cx="50" cy="50" r={r} fill="none" stroke="#16845B" strokeWidth="12"
              strokeDasharray={`${pStroke} ${c}`} strokeDashoffset={0} />
          )}
          {totalCount > 0 && fStroke > 0 && (
            <circle cx="50" cy="50" r={r} fill="none" stroke="#D14343" strokeWidth="12"
              strokeDasharray={`${fStroke} ${c}`} strokeDashoffset={fOffset} />
          )}
          {totalCount > 0 && sStroke > 0 && (
            <circle cx="50" cy="50" r={r} fill="none" stroke="#98A2B3" strokeWidth="12"
              strokeDasharray={`${sStroke} ${c}`} strokeDashoffset={sOffset} />
          )}
        </svg>
        <div style={{
          position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center', pointerEvents: 'none'
        }}>
          <span style={{ fontSize: '1.15rem', fontWeight: 700, color: '#172033', lineHeight: 1.1 }}>
            {totalCount}
          </span>
          <span style={{ fontSize: '0.625rem', color: '#667085', textTransform: 'uppercase', fontWeight: 500 }}>
            Tests
          </span>
        </div>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', fontSize: '0.775rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#16845B' }} />
          <span>Passed: <strong style={{ color: '#16845B' }}>{passed}</strong></span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#D14343' }} />
          <span>Failed: <strong style={{ color: '#D14343' }}>{failed}</strong></span>
        </div>
        {skipped > 0 && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#98A2B3' }} />
            <span>Skipped: <strong>{skipped}</strong></span>
          </div>
        )}
        <span style={{ fontSize: '0.72rem', color: '#667085', marginTop: '2px' }}>
          {totalCount === 0 ? 'No test executions recorded' : `${passed} of ${totalCount} tests passed`}
        </span>
      </div>
    </div>
  );
}

function CriteriaProgressBar({ successRate }) {
  const hasRate = Number.isFinite(successRate);
  const pct = hasRate ? Math.max(0, Math.min(100, successRate)) : null;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', width: '100%' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.8rem' }}>
        <span style={{ fontWeight: 600, color: '#172033' }}>
          Acceptance Criteria Progress
        </span>
        <span style={{ fontWeight: 700, color: hasRate ? '#16845B' : '#667085' }}>
          {hasRate ? `${pct}%` : 'Unavailable'}
        </span>
      </div>
      <div style={{
        height: '10px',
        width: '100%',
        backgroundColor: '#E5E7EF',
        borderRadius: '9999px',
        overflow: 'hidden'
      }}>
        {hasRate && pct > 0 && (
          <div style={{
            height: '100%',
            width: `${pct}%`,
            backgroundColor: pct === 100 ? '#16845B' : '#6257D9',
            borderRadius: '9999px',
            transition: 'width 0.4s ease'
          }} />
        )}
      </div>
      <div style={{ fontSize: '0.725rem', color: '#667085' }}>
        {hasRate
          ? `${pct}% of requirement criteria verified with empirical evidence.`
          : 'Criteria completion percentage is unavailable for this run.'}
      </div>
    </div>
  );
}

function GoalDriftGauge({ driftScore }) {
  const hasScore = Number.isFinite(driftScore);
  const scoreVal = hasScore ? Math.max(0, Math.min(100, driftScore)) : null;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', width: '100%' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.8rem' }}>
        <span style={{ fontWeight: 600, color: '#172033' }}>
          Goal Drift Gauge
        </span>
        <span style={{ fontWeight: 700, color: hasScore ? (scoreVal > 25 ? '#B7791F' : '#16845B') : '#667085' }}>
          {hasScore ? `${scoreVal}%` : 'Unavailable'}
        </span>
      </div>
      <div style={{
        height: '10px',
        width: '100%',
        backgroundColor: '#E5E7EF',
        borderRadius: '9999px',
        overflow: 'hidden'
      }}>
        {hasScore && (
          <div style={{
            height: '100%',
            width: `${scoreVal}%`,
            backgroundColor: scoreVal > 30 ? '#D14343' : scoreVal > 15 ? '#B7791F' : '#16845B',
            borderRadius: '9999px',
            transition: 'width 0.4s ease'
          }} />
        )}
      </div>
      <div style={{ fontSize: '0.725rem', color: '#667085' }}>
        {hasScore
          ? 'Measures semantic divergence between original user prompt and generated code.'
          : 'Unavailable — no validated semantic alignment measurement recorded.'}
      </div>
    </div>
  );
}

function formatDuration(seconds) {
  if (!Number.isFinite(seconds) || seconds < 0) return '—';
  if (seconds === 0) return '0s';
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  if (seconds < 3600) return `${(seconds / 60).toFixed(1)}m`;
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  return minutes > 0 ? `${hours}h ${minutes}m` : `${hours}h`;
}

export function RecentRunCoverageChart({ runs = [] }) {
  const measuredRuns = runs
    .filter(run => run.metric_version === '2' && Number.isFinite(run.success_rate))
    .slice(0, 8);

  return (
    <section className="card-panel evaluation-run-chart" aria-label="Recent validated run coverage">
      <div className="evaluation-run-chart-header">
        <div>
          <h3><BarChart3 size={16} /> Bar chart · criteria coverage by recent run</h3>
          <p>Latest validated measurements, shown on a 0–100% scale. Runs may differ in task and execution mode.</p>
        </div>
        <span className="evaluation-run-chart-scale">0–100%</span>
      </div>
      {measuredRuns.length === 0 ? (
        <p className="evaluation-run-chart-empty">No validated criteria-coverage measurements are available in recent runs.</p>
      ) : (
        <div
          className="evaluation-run-chart-graph"
          role="img"
          aria-label={`Vertical bar chart of criteria coverage for ${measuredRuns.length} recent runs`}
        >
          <div className="evaluation-run-chart-axis" aria-hidden="true">
            {[100, 75, 50, 25, 0].map(value => <span key={value}>{value}%</span>)}
          </div>
          <div className="evaluation-run-chart-columns">
            {measuredRuns.map((run, index) => {
              const coverage = Math.max(0, Math.min(100, run.success_rate));
              const title = run.title || 'Coding task';
              return (
                <div
                  className="evaluation-run-chart-column"
                  key={run.run_id}
                  title={`${title} · ${run.run_id} · ${coverage}% criteria coverage`}
                >
                  <strong className="evaluation-run-chart-value">{coverage}%</strong>
                  <div className="evaluation-run-chart-bar-area">
                    <span className="evaluation-run-chart-bar" style={{ height: `${coverage}%` }} />
                  </div>
                  <span className="evaluation-run-chart-run-label">Run {index + 1}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </section>
  );
}

function RecoveryPanel({ recovery }) {
  if (!recovery || recovery.evidence_status === 'insufficient_evidence'
    || (recovery.evidence_status === 'no_recovery_needed' && !recovery.total_episodes)) {
    return (
      <div style={{ color: '#64748b', fontSize: '0.8rem', fontStyle: 'italic', padding: '12px 0' }}>
        {recovery?.note || 'No recovery episodes recorded for this run.'}
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '12px' }}>
        <MetricCell
          label={recovery.data_source === 'legacy_recovery_run_stats' || recovery.data_source === 'legacy_recovery_attempts'
            ? 'Recovery Attempts'
            : 'Total Episodes'}
          value={recovery.total_episodes}
          color="#172033"
          sub={`data source: ${recovery.data_source}`}
        />
        <MetricCell
          label="Resolved"
          value={recovery.resolved_episodes}
          color="#16845B"
          sub={recovery.data_source === 'legacy_recovery_attempts'
            ? 'attempts marked resolved by recorded re-tests; not independently verified'
            : 'original failure fixed + regressions passed'}
        />
        <MetricCell
          label="Recovery Rate"
          value={recovery.recovery_rate_percent != null ? `${recovery.recovery_rate_percent}%` : '—'}
          color="#16845B"
          badge={<StatusPill status="measured" />}
        />
        <MetricCell
          label={recovery.data_source === 'legacy_recovery_run_stats' ? 'Recovery Time' : 'Mean Duration'}
          value={recovery.mean_recovery_duration_seconds != null
            ? formatDuration(recovery.mean_recovery_duration_seconds)
            : '—'}
          color="#0284C7"
          sub={recovery.data_source === 'legacy_recovery_run_stats' ? 'total run recovery time' : 'per episode'}
        />
        <MetricCell
          label="Total Extra Steps"
          value={recovery.total_extra_steps ?? '—'}
          color="#6257D9"
          sub="recovery overhead"
        />
      </div>

      {recovery.failure_type_breakdown && Object.keys(recovery.failure_type_breakdown).length > 0 && (
        <div style={{ background: 'rgba(255, 255, 255, 0.03)', padding: '12px 14px', borderRadius: '8px', border: '1px solid rgba(255, 255, 255, 0.08)' }}>
          <div style={{ color: '#94A3B8', fontSize: '0.7rem', textTransform: 'uppercase', marginBottom: '8px' }}>
            Failure type breakdown
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px' }}>
            {Object.entries(recovery.failure_type_breakdown).map(([ft, data]) => (
              <div key={ft} style={{
                background: '#0D1526', border: '1px solid rgba(255, 255, 255, 0.08)',
                borderRadius: '6px', padding: '8px 12px', minWidth: '140px'
              }}>
                <div style={{ color: '#94A3B8', fontWeight: 600, fontSize: '0.78rem' }}>{ft}</div>
                <div style={{ color: '#F1F5F9', fontSize: '0.85rem', marginTop: '2px', fontWeight: 600 }}>
                  {data.resolved}/{data.attempts} resolved
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {recovery.episodes && recovery.episodes.length > 0 && (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.78rem' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid #E5E7EF', color: '#667085' }}>
                {(recovery.data_source === 'legacy_recovery_attempts'
                  ? ['Attempt', 'Failure', 'Duration', 'Extra Steps', 'Outcome', 'Human?']
                  : ['Episode', 'Failure Type', 'Duration', 'Extra Steps', 'Outcome', 'Human?']).map(h => (
                  <th key={h} style={{ padding: '8px 10px', textAlign: 'left' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {recovery.episodes.map((ep) => (
                <tr key={ep.episode_id} style={{ borderBottom: '1px solid #E5E7EF' }}>
                  <td style={{ padding: '8px 10px', color: '#667085', fontFamily: 'monospace', fontSize: '0.7rem' }}>
                    {recovery.data_source === 'legacy_recovery_attempts'
                      ? `#${ep.attempt_number} ${ep.episode_id}`
                      : ep.episode_id}
                  </td>
                  <td style={{ padding: '8px 10px', color: '#172033' }}>{ep.failure_type}</td>
                  <td style={{ padding: '8px 10px', color: '#6257D9' }}>
                    {ep.recovery_duration_seconds != null ? `${ep.recovery_duration_seconds.toFixed(1)}s` : '—'}
                  </td>
                  <td style={{ padding: '8px 10px', color: '#6257D9' }}>{ep.extra_steps}</td>
                  <td style={{ padding: '8px 10px' }}>
                    <span style={{
                      color: ep.verified_success === true
                        ? '#16845B'
                        : ep.verified_success === false ? '#D14343' : '#9A6700',
                      fontWeight: 700, fontSize: '0.72rem'
                    }}>
                      {ep.final_verified_outcome}
                    </span>
                  </td>
                  <td style={{ padding: '8px 10px', color: '#64748b' }}>
                    {ep.human_intervention ? '✓' : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {recovery.note && (
        <div style={{ color: '#64748b', fontSize: '0.72rem' }}>{recovery.note}</div>
      )}
    </div>
  );
}

export default function EvaluationDashboard({
  currentRunRecord,
  onSelectRun,
  onReset: _onReset
}) {
  const [dashboardData, setDashboardData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [section, setSection] = useState('run');
  const [benchmarksOpened, setBenchmarksOpened] = useState(false);
  const [workflowRefresh, setWorkflowRefresh] = useState(0);
  const requestId = useRef(0);

  const [recoveryData, setRecoveryData] = useState(null);

  const loadDashboard = () => {
    const id = ++requestId.current;
    setLoading(true);
    setError(null);
    setDashboardData(null);
    fetchEvaluationDashboard()
      .then((data) => { if (id === requestId.current) setDashboardData(data); })
      .catch((err) => { if (id === requestId.current) setError(err.message); })
      .finally(() => { if (id === requestId.current) setLoading(false); });
  };

  useEffect(() => {
    loadDashboard();
    return () => { requestId.current += 1; };
  }, [currentRunRecord?.run_id, currentRunRecord?.evaluation?.created_at]);

  useEffect(() => {
    if (!currentRunRecord?.run_id) {
      setRecoveryData(null);
      return;
    }
    setRecoveryData(null);
    let cancelled = false;
    fetchRunRecovery(currentRunRecord.run_id)
      .then((data) => { if (!cancelled) setRecoveryData(data); })
      .catch((e) => { if (!cancelled) { console.warn('Recovery data error:', e); setRecoveryData(null); } });
    return () => { cancelled = true; };
  }, [currentRunRecord?.run_id]);

  const currentEval = currentRunRecord?.evaluation;
  const aggregate = dashboardData?.aggregate_stats ?? {};
  const recentEvals = dashboardData?.recent_evaluations ?? [];
  const maxRecentDuration = Math.max(0, ...recentEvals
    .filter(run => run.duration_status !== 'unverified_legacy')
    .map(run => run.execution_time_seconds)
    .filter(value => Number.isFinite(value) && value >= 0));

  const handleExportJSON = async () => {
    let payload = {
      dashboard: dashboardData,
      run: currentRunRecord,
      recovery: recoveryData,
    };
    try {
      if (currentRunRecord?.run_id) {
        payload.run_export = await exportRun(currentRunRecord.run_id);
      }
    } catch (err) {
      console.warn('Export run error:', err);
    }
    const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(payload, null, 2));
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute('href', dataStr);
    downloadAnchor.setAttribute('download', `horizonlab_run_${currentRunRecord?.run_id ?? 'export'}.json`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  };

  const sections = [
    ['run', 'This run'],
    ['recovery', 'Recovery Episodes'],
    ['benchmarks', 'Benchmarks'],
    ['history', 'Run history'],
  ];

  return (
    <div className="evaluation-dashboard" style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <div className="card-panel" style={{
        padding: '20px 24px',
        backgroundColor: '#0D1526',
        border: '1px solid rgba(255, 255, 255, 0.08)',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        flexWrap: 'wrap',
        gap: '16px'
      }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
            <span className="badge badge-purple">Stage 7: Evaluation Dashboard</span>
            <span style={{ fontSize: '0.75rem', color: '#94A3B8' }}>Persistent Run Analytics & Benchmarks</span>
          </div>
          <h2 style={{ fontSize: '1.25rem', fontWeight: 700, color: '#F8FAFC', marginBottom: '4px' }}>
            Evaluation
          </h2>
          <p style={{ fontSize: '0.85rem', color: '#94A3B8', margin: 0 }}>
            Understand this run, inspect repeated work, or compare controlled benchmark trials.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '10px' }}>
          <button
            className="btn btn-secondary"
            onClick={() => {
              loadDashboard();
              setWorkflowRefresh(value => value + 1);
            }}
            style={{ padding: '8px 14px', fontSize: '0.8rem' }}
          >
            <RefreshCw size={14} />
            <span>Refresh measurements</span>
          </button>

          <button
            className="btn btn-primary"
            onClick={handleExportJSON}
            disabled={!currentRunRecord?.run_id && !dashboardData}
            style={{ padding: '8px 16px', fontWeight: 600 }}
          >
            <Download size={14} />
            <span>{currentRunRecord?.run_id ? 'Export this run' : 'Export history'}</span>
          </button>
        </div>
      </div>

      <nav aria-label="Evaluation sections" style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        {sections.map(([id, label]) => (
          <button
            key={id}
            type="button"
            aria-pressed={section === id}
            className={`btn ${section === id ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => {
              setSection(id);
              if (id === 'benchmarks') setBenchmarksOpened(true);
            }}
          >
            {label}
          </button>
        ))}
      </nav>

      {error && <p role="alert">Unable to load saved measurements: {error}</p>}

      {benchmarksOpened && (
        <section
          hidden={section !== 'benchmarks'}
          aria-label="Controlled benchmarks"
          style={{ display: section === 'benchmarks' ? 'grid' : 'none', gap: 16 }}
        >
          <p>Compare matched trials. Simulated results test the evaluation system; they do not measure model ability.</p>
          <details className="card-panel" style={{ padding: 20 }} open>
            <summary>Run a benchmark</summary>
            <BenchmarkPanel onComplete={loadDashboard} />
          </details>
          <details className="card-panel" style={{ padding: 20 }}>
            <summary>Experiment studies and model pilots</summary>
            <BenchmarkStudies onComplete={loadDashboard} />
          </details>
        </section>
      )}

      {section === 'run' && (
        <section aria-label="Selected run" style={{ display: 'grid', gap: 16 }}>
          {!currentRunRecord?.run_id && <p>Select a saved run from Run history to see its measurements.</p>}
          <WorkflowAnalysis runId={currentRunRecord?.run_id} refreshKey={`${currentRunRecord?.evaluation?.created_at || ''}:${workflowRefresh}`} />

          {currentEval && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              {/* Visual Evaluation Graphs Card */}
              <div className="card-panel" style={{ padding: '20px 24px', backgroundColor: '#0D1526', border: '1px solid rgba(255, 255, 255, 0.08)' }}>
                <h3 style={{ fontSize: '1rem', fontWeight: 700, color: '#F1F5F9', marginBottom: '16px' }}>
                  Execution Visualizations & Metrics
                </h3>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '24px', alignItems: 'center' }}>
                  {/* Test Outcomes Doughnut Chart */}
                  <div style={{ background: 'rgba(255, 255, 255, 0.03)', padding: '16px', borderRadius: '8px', border: '1px solid rgba(255, 255, 255, 0.07)' }}>
                    <div style={{ fontSize: '0.75rem', fontWeight: 600, color: '#F1F5F9', marginBottom: '10px' }}>
                      Test Execution Breakdown
                    </div>
                    <TestDoughnutChart
                      passed={currentEval.tests_passed ?? 0}
                      failed={currentEval.tests_failed ?? (currentEval.tests_total != null && currentEval.tests_passed != null ? Math.max(0, currentEval.tests_total - currentEval.tests_passed) : 0)}
                      skipped={currentEval.tests_skipped ?? 0}
                      total={currentEval.tests_total ?? 0}
                    />
                  </div>

                  {/* Criteria Progress Bar */}
                  <div style={{ background: 'rgba(255, 255, 255, 0.03)', padding: '16px', borderRadius: '8px', border: '1px solid rgba(255, 255, 255, 0.07)' }}>
                    <CriteriaProgressBar successRate={currentEval.success_rate} />
                  </div>

                  {/* Goal Drift Gauge */}
                  <div style={{ background: 'rgba(255, 255, 255, 0.03)', padding: '16px', borderRadius: '8px', border: '1px solid rgba(255, 255, 255, 0.07)' }}>
                    <GoalDriftGauge driftScore={currentEval.goal_drift_score ?? currentEval.evidence_breakdown?.diagnostic_scores?.goal_drift_score} />
                  </div>
                </div>
              </div>

              {/* Saved Test and Timing Telemetry (Exact spans for assertions) */}
              <details open className="card-panel" style={{ padding: '20px 24px', backgroundColor: '#0D1526', border: '1px solid rgba(255, 255, 255, 0.08)' }}>
                <summary>Saved test and timing summary</summary>
                {currentEval.metric_version !== '2' && <p>Historical measurements are unvalidated.</p>}
                <div style={{ fontSize: '0.8rem', fontWeight: 600, color: '#94A3B8', textTransform: 'uppercase', margin: '12px 0 8px 0' }}>
                  Current Run Telemetry ({currentRunRecord?.run_id})
                </div>

                <div className="evaluation-telemetry-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '12px' }}>
                  <div className="card-panel evaluation-telemetry-stat" style={{ padding: '14px 16px', backgroundColor: 'rgba(255, 255, 255, 0.03)', border: '1px solid rgba(255, 255, 255, 0.07)' }}>
                    <span style={{ fontSize: '0.675rem', color: '#94A3B8', textTransform: 'uppercase', display: 'block', marginBottom: '2px', fontWeight: 500 }}>
                      Criteria Coverage
                    </span>
                    <span style={{ fontSize: '1.25rem', fontWeight: 700, color: '#16845B' }}>
                      {currentEval.success_rate == null ? 'Unavailable' : `${currentEval.success_rate}%`}
                    </span>
                    <PercentageMeter label="Criteria coverage" value={currentEval.success_rate} color="#16845B" />
                  </div>

                  <div className="card-panel evaluation-telemetry-stat evaluation-telemetry-duration" style={{ padding: '14px 16px', backgroundColor: '#F8F9FD' }}>
                    <span style={{ fontSize: '0.675rem', color: '#667085', textTransform: 'uppercase', display: 'block', marginBottom: '2px', fontWeight: 500 }}>
                      Execution Time
                    </span>
                    <span style={{ fontSize: '1.25rem', fontWeight: 700, color: '#6257D9' }}>
                      {formatDuration(currentEval.execution_time_seconds) === '—'
                        ? 'Unavailable'
                        : formatDuration(currentEval.execution_time_seconds)}
                    </span>
                  </div>

                  <div className="card-panel evaluation-telemetry-stat evaluation-telemetry-tools" style={{ padding: '14px 16px', backgroundColor: '#F8F9FD' }}>
                    <span style={{ fontSize: '0.675rem', color: '#667085', textTransform: 'uppercase', display: 'block', marginBottom: '2px', fontWeight: 500 }}>
                      Total Tool Calls
                    </span>
                    <span style={{ fontSize: '1.25rem', fontWeight: 700, color: '#172033' }}>
                      {currentEval.total_tool_calls ?? 'Unavailable'}
                    </span>
                  </div>

                  <div className="card-panel evaluation-telemetry-stat evaluation-telemetry-recovery" style={{ padding: '14px 16px', backgroundColor: '#F8F9FD' }}>
                    <span style={{ fontSize: '0.675rem', color: '#667085', textTransform: 'uppercase', display: 'block', marginBottom: '2px', fontWeight: 500 }}>
                      Recovery Attempts
                    </span>
                    <span style={{ fontSize: '1.25rem', fontWeight: 700, color: '#B7791F' }}>
                      {currentEval.recovery_attempts_count ?? 'Unavailable'}
                    </span>
                  </div>

                  <div className="card-panel evaluation-telemetry-stat evaluation-telemetry-tests" style={{ padding: '14px 16px', backgroundColor: '#F8F9FD' }}>
                    <span style={{ fontSize: '0.675rem', color: '#667085', textTransform: 'uppercase', display: 'block', marginBottom: '2px', fontWeight: 500 }}>
                      Tests Passing
                    </span>
                    <span style={{ fontSize: '1.25rem', fontWeight: 700, color: '#16845B' }}>
                      {currentEval.tests_passed ?? '—'} / {currentEval.tests_total ?? '—'}
                    </span>
                    <PercentageMeter
                      label="Tests passing"
                      value={Number.isFinite(currentEval.tests_passed)
                        && Number.isFinite(currentEval.tests_total)
                        && currentEval.tests_total > 0
                        ? (currentEval.tests_passed / currentEval.tests_total) * 100
                        : null}
                      color="#16845B"
                    />
                  </div>

                  <div className="card-panel evaluation-telemetry-stat evaluation-telemetry-drift" style={{ padding: '14px 16px', backgroundColor: '#F8F9FD' }}>
                    <span style={{ fontSize: '0.675rem', color: '#667085', textTransform: 'uppercase', display: 'block', marginBottom: '2px', fontWeight: 500 }}>
                      Goal Drift Score
                    </span>
                    <span style={{ fontSize: '1.25rem', fontWeight: 700, color: '#6257D9' }}>
                      {(() => {
                        const score = currentEval.goal_drift_score ?? currentEval.evidence_breakdown?.diagnostic_scores?.goal_drift_score;
                        if (score == null) return 'Unavailable';
                        const isDiag = currentEval.goal_drift_score == null && currentEval.evidence_breakdown?.diagnostic_scores?.goal_drift_score != null;
                        return isDiag ? `${score}% (Diagnostic)` : `${score}%`;
                      })()}
                    </span>
                    <PercentageMeter
                      label="Goal drift score"
                      value={currentEval.goal_drift_score ?? currentEval.evidence_breakdown?.diagnostic_scores?.goal_drift_score}
                      color="#6257D9"
                    />
                  </div>
                </div>
              </details>
            </div>
          )}
          <p style={{ color: '#667085', fontSize: '0.85rem' }}>Unavailable means a measurement was not recorded. Unverified means the available evidence does not establish the result.</p>
        </section>
      )}


      {section === 'recovery' && (
        <div className="card-panel" style={{ padding: '20px' }}>
          <div style={{ marginBottom: '14px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
              <span className="badge badge-cyan">Feature 2</span>
              <h3 style={{ fontSize: '1rem', fontWeight: 700, color: '#172033', margin: 0 }}>
                Trace-Based Recovery Analysis
              </h3>
            </div>
            <p style={{ fontSize: '0.78rem', color: '#667085', margin: 0 }}>
              Each failure/recovery pair is a distinct episode. A recovery is marked successful only
              when the re-test actually passes — never inferred from debugging stage completion.
            </p>
          </div>

          {!currentRunRecord?.run_id ? (
            <div style={{ color: '#64748b', fontSize: '0.8rem', fontStyle: 'italic' }}>
              Select a completed run to inspect its recovery episodes.
            </div>
          ) : (
            <RecoveryPanel recovery={recoveryData} />
          )}
        </div>
      )}

      {section === 'history' && (
        <section aria-label="Run history" style={{ display: 'grid', gap: 16 }}>
          <RecentRunCoverageChart runs={recentEvals} />
          {loading && <p role="status">Loading measurements…</p>}
          <p>History includes different tasks. Use Benchmarks for controlled comparisons.</p>
          <details>
            <summary>How historical results are counted</summary>
            <p>Legacy scores are unvalidated. Unknown outcomes remain in the current-version success denominator; pending and legacy runs are reported separately.</p>
            <p>Legacy: {aggregate.legacy_runs ?? '—'} · Unevaluated: {aggregate.unevaluated_runs ?? '—'} · Unverified: {aggregate.unverified_runs ?? '—'}</p>
            {(dashboardData?.by_execution_mode || []).map(group => (
              <p key={group.execution_mode}>{group.execution_mode}: {group.verified_successes}/{group.sample_count} verified successes</p>
            ))}
          </details>

          <div className="card-panel" style={{ padding: '20px' }}>
            <h3 style={{ fontSize: '0.95rem', fontWeight: 600, color: '#172033', display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '14px' }}>
              <Activity size={16} color="#38bdf8" />
              <span>Recorded Run Summary (Across Different Tasks and Execution Modes)</span>
            </h3>

            <div className="evaluation-history-summary" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '14px' }}>
              <div className="evaluation-summary-stat">
                <span style={{ fontSize: '0.7rem', color: '#667085', display: 'block' }}>Total Recorded Runs</span>
                <span style={{ fontSize: '1.2rem', fontWeight: 700, color: '#172033' }}>{aggregate.total_runs ?? 'Unavailable'}</span>
              </div>

              <div className="evaluation-summary-stat evaluation-summary-success">
                <span style={{ fontSize: '0.7rem', color: '#667085', display: 'block' }}>Verified Task Success Rate</span>
                <span style={{ fontSize: '1.2rem', fontWeight: 700, color: '#16845B' }}>
                  {aggregate.avg_success_rate == null ? 'Unavailable' : `${Math.round(aggregate.avg_success_rate)}%`}
                </span>
                <PercentageMeter label="Verified task success rate" value={aggregate.avg_success_rate} color="#16845B" />
              </div>

              <div className="evaluation-summary-stat">
                <span style={{ fontSize: '0.7rem', color: '#667085', display: 'block' }}>Average Execution Duration</span>
                <span style={{ fontSize: '1.2rem', fontWeight: 700, color: '#6257D9' }}>
                  {aggregate.avg_duration == null ? 'Unavailable' : `${Math.round(aggregate.avg_duration * 10) / 10}s`}
                </span>
              </div>

              <div className="evaluation-summary-stat">
                <span style={{ fontSize: '0.7rem', color: '#667085', display: 'block' }}>Recovery Attempts</span>
                <span style={{ fontSize: '1.2rem', fontWeight: 700, color: '#B7791F' }}>
                  {aggregate.total_recoveries ?? 'Unavailable'}
                </span>
              </div>
            </div>
          </div>

          <div className="card-panel" style={{ padding: '20px' }}>
            <h3 style={{ fontSize: '0.95rem', fontWeight: 600, color: '#172033', display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '14px' }}>
              <BarChart3 size={16} color="#6257D9" />
              <span>Saved runs</span>
            </h3>
            <p className="evaluation-history-note">Bars compare each run to the displayed range; use Benchmarks for controlled comparisons.</p>

            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem', textAlign: 'left' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid #E5E7EF', color: '#667085' }}>
                    <th style={{ padding: '10px 12px' }}>Run ID & Task</th>
                    <th style={{ padding: '10px 12px' }}>Criteria / Outcome</th>
                    <th style={{ padding: '10px 12px' }}>Duration · relative</th>
                    <th style={{ padding: '10px 12px' }}>Tool Calls</th>
                    <th style={{ padding: '10px 12px' }}>Recoveries</th>
                    <th style={{ padding: '10px 12px' }}>Tests</th>
                    <th style={{ padding: '10px 12px' }}>Drift</th>
                    <th style={{ padding: '10px 12px' }}>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {recentEvals.length > 0 ? (
                    recentEvals.map((r, idx) => (
                      <tr
                        key={r.run_id ?? idx}
                        style={{
                          borderBottom: '1px solid #E5E7EF',
                          backgroundColor: currentRunRecord?.run_id === r.run_id ? '#F0EEFF' : 'transparent'
                        }}
                      >
                        <td style={{ padding: '10px 12px' }}>
                          <div style={{ fontWeight: 600, color: '#172033' }}>
                            {r.title ? r.title.slice(0, 40) : 'Coding Task'}
                          </div>
                          <span style={{ fontSize: '0.675rem', fontFamily: 'var(--font-mono)', color: '#64748b' }}>
                            {r.run_id}
                          </span>
                        </td>
                        <td style={{ padding: '10px 12px' }}>
                          <span className={`badge ${r.metric_version === '2' && r.outcome === 'success' ? 'badge-emerald' : r.outcome === 'failed' || r.outcome === 'error' ? 'badge-rose' : 'badge-amber'}`} style={{ fontSize: '0.65rem' }}>
                            {r.metric_version !== '2' ? 'Legacy / unvalidated' : `${r.success_rate ?? '—'}% / ${r.outcome}`}
                          </span>
                          {r.metric_version === '2' && Number.isFinite(r.success_rate) && (
                            <PercentageMeter label={`${r.title || r.run_id} criteria coverage`} value={r.success_rate} color="#16845B" />
                          )}
                        </td>
                        <td
                          title={r.duration_status === 'reconstructed'
                            ? 'Duration reconstructed from this run’s recorded start and verification timestamps.'
                            : r.duration_status === 'unverified_legacy'
                              ? 'No matching execution start and completion timestamps were recorded for this legacy duration.'
                              : undefined}
                          style={{ padding: '10px 12px', color: '#0284C7', fontFamily: 'var(--font-mono)' }}
                        >
                          {r.duration_status === 'unverified_legacy'
                            ? 'Unverified'
                            : formatDuration(r.execution_time_seconds)}
                          {r.duration_status !== 'unverified_legacy'
                            && maxRecentDuration > 0
                            && Number.isFinite(r.execution_time_seconds)
                            && r.execution_time_seconds >= 0 && (
                              <div
                                className="evaluation-history-bar"
                                role="img"
                                aria-label={`${formatDuration(r.execution_time_seconds)} relative to longest displayed run`}
                              >
                                <span style={{ width: `${Math.max(0, Math.min(100, (r.execution_time_seconds / maxRecentDuration) * 100))}%`, background: '#6257D9' }} />
                              </div>
                            )}
                        </td>
                        <td style={{ padding: '10px 12px', color: '#6257D9' }}>
                          {r.total_tool_calls ?? '—'}
                        </td>
                        <td style={{ padding: '10px 12px', color: '#9A6700' }}>
                          {r.recovery_attempts_count ?? '—'}
                        </td>
                        <td style={{ padding: '10px 12px', color: '#16845B' }}>
                          {r.tests_passed ?? '—'} / {r.tests_total ?? '—'}
                          <PercentageMeter
                            label={`${r.title || r.run_id} tests passing`}
                            value={Number.isFinite(r.tests_passed) && Number.isFinite(r.tests_total) && r.tests_total > 0
                              ? (r.tests_passed / r.tests_total) * 100
                              : null}
                            color="#16845B"
                          />
                        </td>
                        <td style={{ padding: '10px 12px', color: '#0284C7' }}>
                          {(() => {
                            const score = r.goal_drift_score ?? r.evidence_breakdown?.diagnostic_scores?.goal_drift_score;
                            if (score == null) return 'Unavailable';
                            const isDiag = r.goal_drift_score == null && r.evidence_breakdown?.diagnostic_scores?.goal_drift_score != null;
                            return isDiag ? `${score}% (Diag)` : `${score}%`;
                          })()}
                          <PercentageMeter
                            label={`${r.title || r.run_id} goal drift score`}
                            value={r.goal_drift_score ?? r.evidence_breakdown?.diagnostic_scores?.goal_drift_score}
                            color="#D9A441"
                          />
                        </td>
                        <td style={{ padding: '10px 12px' }}>
                          <button
                            onClick={() => { onSelectRun?.(r.run_id); setSection('run'); }}
                            className="btn btn-secondary btn-sm"
                            style={{ fontSize: '0.7rem', padding: '3px 8px' }}
                          >
                            Load Run
                          </button>
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={8} style={{ padding: '24px', textAlign: 'center', color: '#64748b' }}>
                        No evaluations recorded yet. Run a workflow to populate benchmarks.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </section>
      )}
    </div>
  );
}
