import React, { useEffect, useState } from 'react';
import { fetchExperiments, runStudy, resumeExperiment } from '../services/api';

const studies = ['normal', 'goal_adherence', 'memory_retention', 'tool_recovery', 'sustained_correctness', 'task_length', 'efficiency'];
const title = value => value.replaceAll('_', ' ');

export function StudyResults({ report }) {
  if (!report) return null;
  const calls = report.model_budget?.calls || [];
  const unknown = calls.filter(c => c.status !== 'completed');
  const generated = calls.reduce((n,c) => n + (c.generated_tokens ?? 0), 0);
  const reserved = unknown.reduce((n,c) => n + c.reserved_tokens, 0);
  const download = () => {
    const url = URL.createObjectURL(new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' }));
    const anchor = document.createElement('a'); anchor.href = url; anchor.download = `${report.experiment_id}.json`;
    anchor.click(); URL.revokeObjectURL(url);
  };
  return <div>
    <p>{report.status} · {report.trials.length} recorded trials · {report.manifest.execution_mode === 'local_ollama' ? report.manifest.model : 'Deterministic fixture adapter'}</p>
    {report.model_budget && <p>Model calls: {calls.length}/{report.model_budget.limits.calls} · Known generated tokens: {generated}/{report.model_budget.limits.generated_tokens} · Unresolved reserved tokens: {reserved}. Input tokens are counted separately. No automatic model retries.</p>}
    <button className="btn btn-secondary" onClick={download}>Export study and evidence</button>
    <div style={{ overflowX: 'auto', marginTop: 16 }}><table style={{ width: '100%', textAlign: 'left' }}>
      <thead><tr><th>Task / condition</th><th>Verified outcome</th><th>Calls</th><th>Termination</th></tr></thead>
      <tbody>{report.trials.map(row => <tr key={row.run_id}>
        <td>{title(row.task_id)} / {title(row.condition)}</td><td>{row.verified_success ? 'Passed' : 'Failed'}</td>
        <td>{row.tool_calls} tool / {row.model_calls ?? 0} model</td><td>{title(row.termination_reason)}</td>
      </tr>)}</tbody></table></div>
    {report.analytics?.paired_comparisons.map((pair,i) => <p key={i}>{title(pair.baseline)} → {title(pair.condition)}: {pair.matched_pairs} matched pairs, {(100*pair.verified_success_difference).toFixed(1)} percentage-point success difference, {pair.mean_extra_calls.toFixed(1)} extra calls.</p>)}
    <details><summary>Memory, prediction, human effort and capability evidence</summary>
      <p>Unavailable evidence remains unknown. Fixture memory strategies and risk signals do not represent completed teammate modules. Capability scores describe these tasks only.</p>
      {(report.analytics?.capability_history || []).map(snapshot => <div key={snapshot.run_id} style={{ marginTop: 12 }}>
        <strong>{title(snapshot.task_id)} / {title(snapshot.condition)}</strong>
        <p>{Object.entries(snapshot.dimensions).map(([name,value]) => `${title(name)}: ${value.ewma == null ? 'unavailable' : value.ewma.toFixed(2)} (n=${value.sample_count})`).join(' · ')}</p>
      </div>)}
      <pre style={{ whiteSpace: 'pre-wrap', maxHeight: 360, overflowY: 'auto' }}>{JSON.stringify(report.analytics?.runs || {}, null, 2)}</pre>
    </details>
  </div>;
}

export default function BenchmarkStudies({ onComplete }) {
  const [scenario, setScenario] = useState('normal');
  const [fault, setFault] = useState('none');
  const [length, setLength] = useState(8);
  const [report, setReport] = useState(null);
  const [saved, setSaved] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const refresh = () => fetchExperiments().then(data => setSaved(data.experiments.filter(e => e.manifest.manifest_version === '2')));
  useEffect(() => { let active = true;
    fetchExperiments().then(data => { if (active) setSaved(data.experiments.filter(e => e.manifest.manifest_version === '2')); }).catch(e => { if (active) setError(e.message); });
    return () => { active = false; };
  }, []);
  const execute = async (resume = false) => {
    setBusy(true); setError('');
    try {
      const result = resume ? await resumeExperiment(report.experiment_id) : await runStudy({
        scenario, task_ids: ['sum_fix'], task_lengths: [Number(length)], repetitions: 1,
        conditions: scenario === 'memory_retention' ? ['memory_none', 'memory_full_history', 'memory_semantic', 'memory_goal_aware'] : ['baseline', 'generic_retry', 'idempotent_retry'],
        fault: { kind: fault, tool: fault === 'noisy_observation' ? 'read' : 'commit' },
      });
      setReport(result); await refresh(); onComplete?.();
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  };
  return <section className="card-panel" style={{ padding: 24 }}>
    <h3>Benchmark studies and pilot reports</h3>
    <p>Run deterministic studies across all seven blueprint categories. Real-model pilots require an explicitly budgeted manifest; this control makes no model calls.</p>
    {error && <p role="alert">{error}</p>}
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, margin: '16px 0' }}>
      <label>Study <select disabled={busy} value={scenario} onChange={e => setScenario(e.target.value)}>{studies.map(s => <option key={s} value={s}>{title(s)}</option>)}</select></label>
      <label>Fault <select disabled={busy} value={fault} onChange={e => setFault(e.target.value)}>{['none','transient','timeout_after_commit','delay','noisy_observation'].map(f => <option key={f} value={f}>{title(f)}</option>)}</select></label>
      <label>Planned actions <input disabled={busy} type="number" min="5" max="100" value={length} onChange={e => setLength(e.target.value)} style={{ width: 70 }}/></label>
      <button className="btn btn-primary" disabled={busy || !Number.isInteger(Number(length)) || Number(length)<5 || Number(length)>100} onClick={() => execute()}>{busy ? 'Running…' : 'Run deterministic study'}</button>
      <button className="btn btn-secondary" disabled={busy} onClick={() => refresh().catch(e => setError(e.message))}>Refresh saved reports</button>
    </div>
    <label>Saved study <select value={report?.experiment_id || ''} onChange={e => setReport(saved.find(s => s.experiment_id===e.target.value) || null)}>
      <option value="">Select a report</option>{saved.map(s => <option key={s.experiment_id} value={s.experiment_id}>{s.created_at} · {s.manifest.model || title(s.manifest.scenario)} · {s.status}</option>)}
    </select></label>
    {report?.status === 'interrupted' && report.manifest.execution_mode === 'trusted_simulation' && <button disabled={busy} onClick={() => execute(true)}>Resume saved simulation</button>}
    <StudyResults report={report}/>
  </section>;
}
