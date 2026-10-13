import React, { useEffect, useState } from 'react';
import { fetchBenchmarkCapabilities, fetchExperiments, runExperiment } from '../services/api';

const percent = (value) => value == null ? 'Unavailable' : `${(value * 100).toFixed(1)}%`;

export default function BenchmarkPanel({ onComplete }) {
  const [capabilities, setCapabilities] = useState(null);
  const [experiments, setExperiments] = useState([]);
  const [report, setReport] = useState(null);
  const [fault, setFault] = useState('none');
  const [task, setTask] = useState('all');
  const [repetitions, setRepetitions] = useState(2);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => {
    let active = true;
    Promise.all([fetchBenchmarkCapabilities(), fetchExperiments()])
      .then(([c, e]) => { if (active) { setCapabilities(c); setExperiments(e.experiments); } })
      .catch(e => { if (active) setError(e.message); });
    return () => { active = false; };
  }, []);
  const run = async () => {
    setBusy(true); setError('');
    try {
      const result = await runExperiment({ task_ids: task === 'all' ? capabilities.tasks.map(t => t.task_id) : [task],
        repetitions: Number(repetitions), task_lengths: [5, 15], fault: { kind: fault, tool: 'commit', occurrence: 1 } });
      setReport(result); setExperiments(previous => [result, ...previous]); onComplete?.();
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  };
  const download = () => {
    const url = URL.createObjectURL(new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' }));
    const anchor = document.createElement('a'); anchor.href = url; anchor.download = `${report.experiment_id}.json`;
    anchor.click(); URL.revokeObjectURL(url);
  };
  return <section className="card-panel" style={{ padding: 24 }}>
    <h3>Controlled benchmarks</h3>
    <p>Trusted software-task simulation · Five fixed repair tasks · Fresh workspace for every trial</p>
    <p>{capabilities?.limitations}</p>
    {error && <p role="alert">{error}</p>}
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, margin: '16px 0' }}>
      <label>Task <select value={task} onChange={e => setTask(e.target.value)} disabled={busy}>
        <option value="all">All five tasks</option>{capabilities?.tasks.map(t => <option key={t.task_id} value={t.task_id}>{t.title}</option>)}
      </select></label>
      <label>Fault <select value={fault} onChange={e => setFault(e.target.value)} disabled={busy}>
        <option value="none">No fault</option><option value="transient">Transient failure</option><option value="timeout_after_commit">Timeout after commit</option>
      </select></label>
      <label>Repetitions <input type="number" min="1" max="10" value={repetitions} onChange={e => setRepetitions(e.target.value)} disabled={busy} style={{ width: 60 }}/></label>
      <button className="btn btn-primary" onClick={run} disabled={busy || !capabilities || !Number.isInteger(Number(repetitions)) || Number(repetitions) < 1 || Number(repetitions) > 10}>{busy ? 'Running trials…' : 'Run comparison'}</button>
    </div>
    <p>Compares baseline, generic retry, and retry with the same operation identity at 5 and 15 planned actions. These are scripted strategies, not completed adaptive-agent models.</p>
    <details><summary>Team integrations not yet available</summary><ul>{Object.entries(capabilities?.unavailable || {}).map(([k,v]) => <li key={k}>{k.replaceAll('_', ' ')}: {v}</li>)}</ul></details>
    <label>Saved experiment <select value={report?.experiment_id || ''} onChange={e => setReport(experiments.find(x => x.experiment_id === e.target.value) || null)}>
      <option value="">Select a report</option>{experiments.map(e => <option key={e.experiment_id} value={e.experiment_id}>{e.created_at} · {e.manifest.fault.kind} · {e.status}</option>)}
    </select></label>
    {report && <div style={{ overflowX: 'auto', marginTop: 16 }}>
      <p>{report.trials.length} trials · {report.status} <button onClick={download} className="btn btn-secondary">Export complete report</button></p>
      <p>95% Wilson intervals describe observed trials. Repeated deterministic trials do not establish general LLM performance.</p>
      <table style={{ width: '100%', textAlign: 'left' }}><thead><tr>{['Task / actions', 'Condition / fault occurred', 'n', 'Verified success', '95% interval', 'Mean calls', 'Recovery rate'].map(h => <th key={h}>{h}</th>)}</tr></thead>
        <tbody>{report.comparisons?.map((r,i) => <tr key={i}>
          <td>{r.task_id} / {r.task_length}</td><td>{r.condition} / {r.fault_occurred ? 'yes' : 'no'}</td><td>{r.sample_count}</td>
          <td>{percent(r.verified_success_rate)}</td><td>{r.success_ci95?.map(percent).join(' – ') || 'Unavailable'}</td>
          <td>{r.mean_tool_calls?.toFixed(1)}</td><td>{percent(r.recovery_rate)}</td>
        </tr>)}</tbody></table>
    </div>}
  </section>;
}
