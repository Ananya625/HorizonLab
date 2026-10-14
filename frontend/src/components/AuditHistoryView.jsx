import React, { useState, useEffect } from 'react';
import { History, GitCommit, Clock, User, Cpu, FileDiff, CheckCircle2, ChevronRight } from 'lucide-react';
import { fetchRunHistory } from '../services/api';

export default function AuditHistoryView({ runId, currentModel }) {
  const [historyList, setHistoryList] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedSnapshot, setSelectedSnapshot] = useState(null);

  useEffect(() => {
    if (runId) {
      setLoading(true);
      fetchRunHistory(runId)
        .then((data) => {
          setHistoryList(data.versions || []);
          if (data.versions && data.versions.length > 0) {
            setSelectedSnapshot(data.versions[data.versions.length - 1]);
          }
        })
        .catch((err) => console.error('Failed to load history:', err))
        .finally(() => setLoading(false));
    }
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
            background: '#F0EEFF',
            border: '1px solid #E5E7EF',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}>
            <History size={20} color="#6257D9" />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span className="badge badge-purple">State 2.E: Audit Trail</span>
              <span className="font-mono" style={{ fontSize: '0.75rem', color: '#667085' }}>Run ID: {runId}</span>
            </div>
            <h2 style={{ fontSize: '1.25rem', fontWeight: 700, color: '#172033', marginTop: '2px' }}>
              Goal Model Provenance & Version Timeline
            </h2>
          </div>
        </div>
        <p style={{ fontSize: '0.85rem', color: '#667085' }}>
          HorizonLab maintains strict provenance. Every user patch, constraint addition, and ambiguity answer creates an auditable version snapshot without erasing the original user requirement.
        </p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
        {/* Timeline Log */}
        <div className="card-panel" style={{ padding: '20px', backgroundColor: '#FFFFFF' }}>
          <h3 style={{ fontSize: '1rem', fontWeight: 600, color: '#172033', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <GitCommit size={16} color="#6257D9" /> Version Change Log ({auditEntries.length} Revisions)
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
                  backgroundColor: '#F6F7FB',
                  border: '1px solid #E5E7EF',
                  borderRadius: '8px'
                }}
              >
                <div style={{
                  minWidth: '28px',
                  height: '28px',
                  borderRadius: '50%',
                  backgroundColor: entry.author === 'system' ? '#F0EEFF' : 'rgba(22, 132, 91, 0.1)',
                  border: `1px solid ${entry.author === 'system' ? '#6257D9' : '#16845B'}`,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center'
                }}>
                  {entry.author === 'system' ? <Cpu size={13} color="#6257D9" /> : <User size={13} color="#16845B" />}
                </div>

                <div style={{ flex: 1 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <span className="badge badge-purple" style={{ fontSize: '0.65rem' }}>v{entry.version}</span>
                      <span className="badge badge-slate" style={{ fontSize: '0.6rem' }}>{entry.author}</span>
                    </div>
                    <span style={{ fontSize: '0.7rem', color: '#667085' }}>
                      {new Date(entry.timestamp).toLocaleTimeString()}
                    </span>
                  </div>

                  <p style={{ fontSize: '0.825rem', color: '#172033', fontWeight: 500, marginBottom: '6px' }}>
                    {entry.change_summary}
                  </p>

                  {entry.modified_fields && entry.modified_fields.length > 0 && (
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                      {entry.modified_fields.map((f) => (
                        <span key={f} className="font-mono" style={{ fontSize: '0.65rem', backgroundColor: '#F0EEFF', color: '#6257D9', padding: '1px 5px', borderRadius: '3px' }}>
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
        <div className="card-panel" style={{ padding: '20px', backgroundColor: '#FFFFFF' }}>
          <h3 style={{ fontSize: '1rem', fontWeight: 600, color: '#172033', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <FileDiff size={16} color="#6257D9" /> Immutable Original Request
          </h3>

          <div style={{ backgroundColor: '#F6F7FB', border: '1px solid #E5E7EF', borderRadius: '8px', padding: '14px', marginBottom: '16px' }}>
            <div style={{ fontSize: '0.7rem', color: '#667085', textTransform: 'uppercase', marginBottom: '4px' }}>
              Original Unaltered User Prompt
            </div>
            <p style={{ fontSize: '0.85rem', color: '#172033', lineHeight: '1.5' }}>
              "{currentModel?.original_request}"
            </p>
          </div>

          <div style={{ backgroundColor: '#F6F7FB', border: '1px solid #E5E7EF', borderRadius: '8px', padding: '14px' }}>
            <div style={{ fontSize: '0.7rem', color: '#667085', textTransform: 'uppercase', marginBottom: '4px' }}>
              Normalized Canonical Specification
            </div>
            <p style={{ fontSize: '0.85rem', color: '#6257D9', lineHeight: '1.5', fontWeight: 500 }}>
              "{currentModel?.normalized_request}"
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
