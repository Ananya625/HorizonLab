import React, { useState, useEffect } from 'react';
import { History, GitCommit, User, Cpu, FileDiff } from 'lucide-react';
import { fetchRunHistory } from '../services/api';

export default function AuditHistoryView({ runId, currentModel }) {
  const [historyList, setHistoryList] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedSnapshot, setSelectedSnapshot] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setHistoryList([]);
    setSelectedSnapshot(null);
    setError(null);
    if (runId) {
      setLoading(true);
      fetchRunHistory(runId)
        .then(data => {
          if (cancelled) return;
          setHistoryList(data.versions || []);
          setSelectedSnapshot(data.versions?.at(-1) || null);
        })
        .catch(err => { if (!cancelled) setError(err.message); })
        .finally(() => { if (!cancelled) setLoading(false); });
    }
    return () => { cancelled = true; };
  }, [runId, currentModel?.goal_model_version]);

  const auditEntries = currentModel?.audit_history || [];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <div className="card-panel" style={{ padding: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
          <div style={{
            width: '36px',
            height: '36px',
            borderRadius: '8px',
            background: 'rgba(139, 92, 246, 0.1)',
            border: '1px solid rgba(139, 92, 246, 0.3)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}>
            <History size={20} color="#a78bfa" />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span className="badge badge-purple">State 2.E: Audit Trail</span>
              <span className="font-mono" style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Run ID: {runId}</span>
            </div>
            <h2 style={{ fontSize: '1.25rem', fontWeight: 700, color: '#f8fafc', marginTop: '2px' }}>
              Goal Model Provenance & Version Timeline
            </h2>
          </div>
        </div>
        <p style={{ fontSize: '0.85rem', color: '#94a3b8' }}>
          AgentEval-X maintains strict provenance. Every user patch, constraint addition, and ambiguity answer creates an auditable version snapshot without erasing the original user requirement.
        </p>
      </div>

      <section className="card-panel" style={{padding:20}} aria-label="Goal version snapshots">
        {loading && <p>Loading goal history...</p>}
        {error && <p role="alert">{error}</p>}
        {!loading && !error && historyList.length === 0 && <p>No saved versions.</p>}
        {historyList.map((snapshot, index) => <button key={index} type="button"
          aria-pressed={selectedSnapshot === snapshot} onClick={() => setSelectedSnapshot(snapshot)}>
          v{snapshot.version}: {snapshot.change_summary}
        </button>)}
        {selectedSnapshot && <pre style={{whiteSpace:'pre-wrap'}}>{JSON.stringify(selectedSnapshot.model, null, 2)}</pre>}
      </section>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
        {/* Timeline Log */}
        <div className="card-panel" style={{ padding: '20px', backgroundColor: '#0e1522' }}>
          <h3 style={{ fontSize: '1rem', fontWeight: 600, color: '#f8fafc', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <GitCommit size={16} color="#38bdf8" /> Version Change Log ({auditEntries.length} Revisions)
          </h3>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px', position: 'relative' }}>
            {auditEntries.map((entry, idx) => (
              <div 
                key={idx}
                style={{
                  display: 'flex',
                  gap: '14px',
                  alignItems: 'flex-start',
                  padding: '12px',
                  backgroundColor: '#070b12',
                  border: '1px solid #1e293b',
                  borderRadius: '8px'
                }}
              >
                <div style={{
                  minWidth: '28px',
                  height: '28px',
                  borderRadius: '50%',
                  backgroundColor: entry.author === 'system' ? 'rgba(56, 189, 248, 0.15)' : 'rgba(16, 185, 129, 0.15)',
                  border: `1px solid ${entry.author === 'system' ? '#38bdf8' : '#10b981'}`,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center'
                }}>
                  {entry.author === 'system' ? <Cpu size={13} color="#38bdf8" /> : <User size={13} color="#10b981" />}
                </div>

                <div style={{ flex: 1 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <span className="badge badge-purple" style={{ fontSize: '0.65rem' }}>v{entry.version}</span>
                      <span className="badge badge-slate" style={{ fontSize: '0.6rem' }}>{entry.author}</span>
                    </div>
                    <span style={{ fontSize: '0.7rem', color: '#64748b' }}>
                      {new Date(entry.timestamp).toLocaleTimeString()}
                    </span>
                  </div>

                  <p style={{ fontSize: '0.825rem', color: '#f1f5f9', fontWeight: 500, marginBottom: '6px' }}>
                    {entry.change_summary}
                  </p>

                  {entry.modified_fields && entry.modified_fields.length > 0 && (
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                      {entry.modified_fields.map((f) => (
                        <span key={f} className="font-mono" style={{ fontSize: '0.65rem', backgroundColor: '#131e30', color: '#38bdf8', padding: '1px 5px', borderRadius: '3px' }}>
                          {f}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Snapshot / Original Request Comparison */}
        <div className="card-panel" style={{ padding: '20px', backgroundColor: '#0e1522' }}>
          <h3 style={{ fontSize: '1rem', fontWeight: 600, color: '#f8fafc', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <FileDiff size={16} color="#a78bfa" /> Immutable Original Request
          </h3>

          <div style={{ backgroundColor: '#070b12', border: '1px solid #1e293b', borderRadius: '8px', padding: '14px', marginBottom: '16px' }}>
            <div style={{ fontSize: '0.7rem', color: '#64748b', textTransform: 'uppercase', marginBottom: '4px' }}>
              Original Unaltered User Prompt
            </div>
            <p style={{ fontSize: '0.85rem', color: '#cbd5e1', lineHeight: '1.5' }}>
              "{currentModel?.original_request}"
            </p>
          </div>

          <div style={{ backgroundColor: '#070b12', border: '1px solid #1e293b', borderRadius: '8px', padding: '14px' }}>
            <div style={{ fontSize: '0.7rem', color: '#64748b', textTransform: 'uppercase', marginBottom: '4px' }}>
              Normalized Canonical Specification
            </div>
            <p style={{ fontSize: '0.85rem', color: '#38bdf8', lineHeight: '1.5' }}>
              "{currentModel?.normalized_request}"
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
