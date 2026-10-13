import React, { useState, useEffect, useRef } from 'react';
import { 
  BarChart3, 
  RefreshCw, 
  Download, 
  Activity
} from 'lucide-react';
import { fetchEvaluationDashboard, exportRun } from '../services/api';
import BenchmarkPanel from './BenchmarkPanel';
import BenchmarkStudies from './BenchmarkStudies';
import WorkflowAnalysis from './WorkflowAnalysis';

export default function EvaluationDashboard({
  currentRunRecord,
  onSelectRun,
  onReset // Retained for caller compatibility; neither supplied version invokes it.
}) {
  const [dashboardData, setDashboardData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [section, setSection] = useState('run');
  const [benchmarksOpened, setBenchmarksOpened] = useState(false);
  const [workflowRefresh, setWorkflowRefresh] = useState(0);
  const requestId = useRef(0);

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

  const currentEval = currentRunRecord?.evaluation;
  const aggregate = dashboardData?.aggregate_stats ?? {};
  const recentEvals = dashboardData?.recent_evaluations ?? [];

  const handleExportJSON = async () => {
    let payload = dashboardData;
    try { if (currentRunRecord?.run_id) payload = await exportRun(currentRunRecord.run_id); }
    catch (err) { setError(err.message); return; }
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(payload, null, 2));
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute("href", dataStr);
    downloadAnchor.setAttribute("download", `agenteval_run_${currentRunRecord?.run_id ?? 'export'}.json`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  };

  return (
    <div className="evaluation-dashboard" style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Top Banner */}
      <div className="card-panel" style={{
        padding: '20px 24px',
        background: 'linear-gradient(135deg, #101626 0%, #0d121f 100%)',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        flexWrap: 'wrap',
        gap: '16px'
      }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
            <span className="badge badge-cyan">Stage 7: Evaluation Dashboard</span>
            <span style={{ fontSize: '0.75rem', color: '#64748b' }}>Persistent Run Analytics & Benchmarks</span>
          </div>
          <h2 style={{ fontSize: '1.25rem', fontWeight: 700, color: '#f8fafc', marginBottom: '4px' }}>
            Evaluation
          </h2>
          <p style={{ fontSize: '0.825rem', color: '#94a3b8' }}>
            Understand this run, inspect repeated work, or compare controlled benchmark trials.
          </p>
        </div>

        {/* Action Buttons */}
        <div style={{ display: 'flex', gap: '10px' }}>
          <button
            className="btn btn-secondary"
            onClick={() => { loadDashboard(); setWorkflowRefresh(value => value + 1); }}
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
        {[['run', 'This run'], ['benchmarks', 'Benchmarks'], ['history', 'Run history']].map(([id, label]) =>
          <button key={id} type="button" aria-pressed={section === id} className={`btn ${section === id ? 'btn-primary' : 'btn-secondary'}`} onClick={() => { setSection(id); if (id === 'benchmarks') setBenchmarksOpened(true); }}>{label}</button>)}
      </nav>
      {error && <p role="alert">Unable to load saved measurements: {error}</p>}
      {benchmarksOpened && <section hidden={section !== 'benchmarks'} aria-label="Controlled benchmarks" style={{ display: section === 'benchmarks' ? 'grid' : 'none', gap: 16 }}>
        <p>Compare matched trials. Simulated results test the evaluation system; they do not measure model ability.</p>
        <details className="card-panel" style={{ padding: 20 }} open><summary>Run a benchmark</summary><BenchmarkPanel onComplete={loadDashboard} /></details>
        <details className="card-panel" style={{ padding: 20 }}><summary>Experiment studies and model pilots</summary><BenchmarkStudies onComplete={loadDashboard} /></details>
      </section>}
      {section === 'run' && <section aria-label="Selected run" style={{ display: 'grid', gap: 16 }}>
      {!currentRunRecord?.run_id && <p>Select a saved run from Run history to see its measurements.</p>}
      <WorkflowAnalysis runId={currentRunRecord?.run_id} refreshKey={`${currentRunRecord?.evaluation?.created_at || ''}:${workflowRefresh}`} />

      {/* Current Run Highlights (if available) */}
      {currentEval && (
        <details>
          <summary>Saved test and timing summary</summary>
          {currentEval.metric_version !== '2' && <p>Historical measurements are unvalidated.</p>}
          <div style={{ fontSize: '0.8rem', fontWeight: 600, color: '#64748b', textTransform: 'uppercase', marginBottom: '8px' }}>
            Current Run Telemetry ({currentRunRecord?.run_id})
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '12px' }}>
            <div className="card-panel" style={{ padding: '14px 16px' }}>
              <span style={{ fontSize: '0.675rem', color: '#64748b', textTransform: 'uppercase', display: 'block', marginBottom: '2px' }}>
                Criteria Coverage
              </span>
              <span style={{ fontSize: '1.25rem', fontWeight: 700, color: '#34d399' }}>
                {currentEval.success_rate == null ? 'Unavailable' : `${currentEval.success_rate}%`}
              </span>
            </div>

            <div className="card-panel" style={{ padding: '14px 16px' }}>
              <span style={{ fontSize: '0.675rem', color: '#64748b', textTransform: 'uppercase', display: 'block', marginBottom: '2px' }}>
                Execution Time
              </span>
              <span style={{ fontSize: '1.25rem', fontWeight: 700, color: '#38bdf8' }}>
                {currentEval.execution_time_seconds == null ? 'Unavailable' : `${currentEval.execution_time_seconds}s`}
              </span>
            </div>

            <div className="card-panel" style={{ padding: '14px 16px' }}>
              <span style={{ fontSize: '0.675rem', color: '#64748b', textTransform: 'uppercase', display: 'block', marginBottom: '2px' }}>
                Total Tool Calls
              </span>
              <span style={{ fontSize: '1.25rem', fontWeight: 700, color: '#a78bfa' }}>
                {currentEval.total_tool_calls ?? 'Unavailable'}
              </span>
            </div>

            <div className="card-panel" style={{ padding: '14px 16px' }}>
              <span style={{ fontSize: '0.675rem', color: '#64748b', textTransform: 'uppercase', display: 'block', marginBottom: '2px' }}>
                Recovery Attempts
              </span>
              <span style={{ fontSize: '1.25rem', fontWeight: 700, color: '#fbbf24' }}>
                {currentEval.recovery_attempts_count ?? 'Unavailable'}
              </span>
            </div>

            <div className="card-panel" style={{ padding: '14px 16px' }}>
              <span style={{ fontSize: '0.675rem', color: '#64748b', textTransform: 'uppercase', display: 'block', marginBottom: '2px' }}>
                Tests Passing
              </span>
              <span style={{ fontSize: '1.25rem', fontWeight: 700, color: '#34d399' }}>
                {currentEval.tests_passed ?? '—'} / {currentEval.tests_total ?? '—'}
              </span>
            </div>

            {currentEval.goal_drift_score != null && <div className="card-panel" style={{ padding: '14px 16px' }}>
              <span style={{ fontSize: '0.675rem', color: '#64748b', textTransform: 'uppercase', display: 'block', marginBottom: '2px' }}>
                Goal Drift Score
              </span>
              <span style={{ fontSize: '1.25rem', fontWeight: 700, color: '#38bdf8' }}>
                {currentEval.goal_drift_score == null ? 'Unavailable' : `${currentEval.goal_drift_score}%`}
              </span>
            </div>}
          </div>
        </details>
      )}
      <p style={{ color: '#94a3b8', fontSize: '0.85rem' }}>Unavailable means a measurement was not recorded. Unverified means the available evidence does not establish the result.</p>
      </section>}

      {section === 'history' && <section aria-label="Run history" style={{ display: 'grid', gap: 16 }}>
      {loading && <p role="status">Loading measurements…</p>}
      <p>History includes different tasks. Use Benchmarks for controlled comparisons.</p>
      <details><summary>How historical results are counted</summary>
        <p>Legacy scores are unvalidated. Unknown outcomes remain in the current-version success denominator; pending and legacy runs are reported separately.</p>
        <p>Legacy: {aggregate.legacy_runs ?? '—'} · Unevaluated: {aggregate.unevaluated_runs ?? '—'} · Unverified: {aggregate.unverified_runs ?? '—'}</p>
        {(dashboardData?.by_execution_mode || []).map(group => <p key={group.execution_mode}>{group.execution_mode}: {group.verified_successes}/{group.sample_count} verified successes</p>)}
      </details>

      {/* Aggregate System Metrics */}
      <div className="card-panel" style={{ padding: '20px' }}>
        <h3 style={{ fontSize: '0.95rem', fontWeight: 600, color: '#f1f5f9', display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '14px' }}>
          <Activity size={16} color="#38bdf8" />
          <span>Recorded Run Summary (Across Different Tasks and Execution Modes)</span>
        </h3>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '14px' }}>
          <div style={{ backgroundColor: '#0c121d', padding: '12px 14px', borderRadius: '8px', border: '1px solid #1e293b' }}>
            <span style={{ fontSize: '0.7rem', color: '#64748b', display: 'block' }}>Total Recorded Runs</span>
            <span style={{ fontSize: '1.2rem', fontWeight: 700, color: '#f8fafc' }}>{aggregate.total_runs ?? 'Unavailable'}</span>
          </div>

          <div style={{ backgroundColor: '#0c121d', padding: '12px 14px', borderRadius: '8px', border: '1px solid #1e293b' }}>
            <span style={{ fontSize: '0.7rem', color: '#64748b', display: 'block' }}>Verified Task Success Rate</span>
            <span style={{ fontSize: '1.2rem', fontWeight: 700, color: '#34d399' }}>
              {aggregate.avg_success_rate == null ? 'Unavailable' : `${Math.round(aggregate.avg_success_rate)}%`}
            </span>
          </div>

          <div style={{ backgroundColor: '#0c121d', padding: '12px 14px', borderRadius: '8px', border: '1px solid #1e293b' }}>
            <span style={{ fontSize: '0.7rem', color: '#64748b', display: 'block' }}>Average Execution Duration</span>
            <span style={{ fontSize: '1.2rem', fontWeight: 700, color: '#38bdf8' }}>
              {aggregate.avg_duration == null ? 'Unavailable' : `${Math.round(aggregate.avg_duration * 10) / 10}s`}
            </span>
          </div>

          <div style={{ backgroundColor: '#0c121d', padding: '12px 14px', borderRadius: '8px', border: '1px solid #1e293b' }}>
            <span style={{ fontSize: '0.7rem', color: '#64748b', display: 'block' }}>Recovery Attempts</span>
            <span style={{ fontSize: '1.2rem', fontWeight: 700, color: '#fbbf24' }}>
              {aggregate.total_recoveries ?? 'Unavailable'}
            </span>
          </div>
        </div>
      </div>

      {/* Multi-Run Benchmark Comparison Table */}
      <div className="card-panel" style={{ padding: '20px' }}>
        <h3 style={{ fontSize: '0.95rem', fontWeight: 600, color: '#f1f5f9', display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '14px' }}>
          <BarChart3 size={16} color="#38bdf8" />
          <span>Saved runs</span>
        </h3>

        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem', textAlign: 'left' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid #1e293b', color: '#64748b' }}>
                <th style={{ padding: '10px 12px' }}>Run ID & Task</th>
                <th style={{ padding: '10px 12px' }}>Criteria / Outcome</th>
                <th style={{ padding: '10px 12px' }}>Duration</th>
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
                      borderBottom: '1px solid #162032',
                      backgroundColor: currentRunRecord?.run_id === r.run_id ? 'rgba(56, 189, 248, 0.05)' : 'transparent'
                    }}
                  >
                    <td style={{ padding: '10px 12px' }}>
                      <div style={{ fontWeight: 600, color: '#f8fafc' }}>
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
                    </td>
                    <td style={{ padding: '10px 12px', color: '#38bdf8', fontFamily: 'var(--font-mono)' }}>
                      {r.execution_time_seconds ?? '—'}s
                    </td>
                    <td style={{ padding: '10px 12px', color: '#a78bfa' }}>
                      {r.total_tool_calls ?? '—'}
                    </td>
                    <td style={{ padding: '10px 12px', color: '#fbbf24' }}>
                      {r.recovery_attempts_count ?? '—'}
                    </td>
                    <td style={{ padding: '10px 12px', color: '#34d399' }}>
                      {r.tests_passed ?? '—'} / {r.tests_total ?? '—'}
                    </td>
                    <td style={{ padding: '10px 12px', color: '#38bdf8' }}>
                      {r.goal_drift_score == null ? 'Unavailable' : `${r.goal_drift_score}%`}
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
                    No evaluations recorded yet. Run a workflow to populate benchmarks!
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
      </section>}
    </div>
  );
}
