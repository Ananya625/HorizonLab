import React, { useState, useEffect, useRef } from 'react';
import { 
  Terminal, 
  ChevronUp, 
  ChevronDown, 
  Search, 
  Filter, 
  Trash2, 
  Cpu, 
  FileCode2, 
  FlaskConical, 
  ShieldCheck,
  Layers,
  Activity
} from 'lucide-react';
import { fetchRunLogs } from '../services/api';

export default function ExecutionControlRoom({
  runId,
  logs = [],
  onRefreshLogs
}) {
  const [isOpen, setIsOpen] = useState(true);
  const [filterRole, setFilterRole] = useState('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const [autoScroll, setAutoScroll] = useState(true);
  const logEndRef = useRef(null);

  useEffect(() => {
    if (autoScroll && logEndRef.current) {
      logEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs, isOpen]);

  const filteredLogs = logs.filter((log) => {
    if (filterRole !== 'ALL' && !log.agent_role?.toLowerCase().includes(filterRole.toLowerCase())) {
      return false;
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      return (
        log.message?.toLowerCase().includes(q) ||
        log.agent_role?.toLowerCase().includes(q) ||
        log.stage?.toLowerCase().includes(q)
      );
    }
    return true;
  });

  return (
    <div style={{
      position: 'fixed',
      bottom: 0,
      left: 0,
      right: 0,
      backgroundColor: '#0a0d14',
      borderTop: '1px solid #1e293b',
      boxShadow: '0 -4px 20px rgba(0, 0, 0, 0.5)',
      zIndex: 40,
      transition: 'all 0.25s ease'
    }}>
      {/* Control Room Bar Header */}
      <div style={{
        padding: '8px 20px',
        backgroundColor: '#0c101a',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        borderBottom: isOpen ? '1px solid #1e293b' : 'none',
        cursor: 'pointer'
      }}
      onClick={() => setIsOpen(!isOpen)}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <Terminal size={16} color="#38bdf8" />
          <span style={{ fontSize: '0.825rem', fontWeight: 600, color: '#f8fafc' }}>
            Execution Control Room & Live Agent Telemetry
          </span>
          {runId && (
            <span className="badge badge-purple" style={{ fontSize: '0.65rem' }}>
              {runId}
            </span>
          )}
          <span className="badge badge-cyan" style={{ fontSize: '0.65rem' }}>
            {logs.length} Events Logged
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }} onClick={(e) => e.stopPropagation()}>
          {isOpen && (
            <>
              {/* Agent Filter */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                <Filter size={13} color="#64748b" />
                <select
                  value={filterRole}
                  onChange={(e) => setFilterRole(e.target.value)}
                  style={{
                    backgroundColor: '#151d2e',
                    color: '#cbd5e1',
                    border: '1px solid #1e293b',
                    borderRadius: '4px',
                    padding: '2px 8px',
                    fontSize: '0.725rem',
                    outline: 'none'
                  }}
                >
                  <option value="ALL">All Agents</option>
                  <option value="Orchestrator">Orchestrator</option>
                  <option value="Requirement">Requirement Analyst</option>
                  <option value="Planner">Planner Agent</option>
                  <option value="Coding">Coding Agent</option>
                  <option value="Test">Test Runner Agent</option>
                  <option value="Debugging">Debugging Agent</option>
                  <option value="Reviewer">Independent Verifier</option>
                </select>
              </div>

              {/* Search Filter */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '4px', backgroundColor: '#151d2e', border: '1px solid #1e293b', borderRadius: '4px', padding: '2px 8px' }}>
                <Search size={12} color="#64748b" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Filter logs..."
                  style={{
                    background: 'transparent',
                    border: 'none',
                    color: '#f8fafc',
                    fontSize: '0.725rem',
                    outline: 'none',
                    width: '100px'
                  }}
                />
              </div>
            </>
          )}

          {/* Toggle Expand/Collapse */}
          <button
            onClick={() => setIsOpen(!isOpen)}
            style={{
              background: 'transparent',
              border: 'none',
              color: '#94a3b8',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center'
            }}
          >
            {isOpen ? <ChevronDown size={18} /> : <ChevronUp size={18} />}
          </button>
        </div>
      </div>

      {/* Expanded Logs Body */}
      {isOpen && (
        <div style={{
          maxHeight: '220px',
          overflowY: 'auto',
          padding: '10px 20px',
          backgroundColor: '#070a10',
          fontFamily: 'var(--font-mono)',
          fontSize: '0.75rem',
          display: 'flex',
          flexDirection: 'column',
          gap: '4px'
        }}>
          {filteredLogs.length > 0 ? (
            filteredLogs.map((log) => {
              let tagColor = '#38bdf8';
              let badgeType = 'badge-cyan';
              if (log.event_type === 'success') { tagColor = '#34d399'; badgeType = 'badge-emerald'; }
              else if (log.event_type === 'error' || log.event_type === 'warning') { tagColor = '#fb7185'; badgeType = 'badge-rose'; }
              else if (log.event_type === 'recovery') { tagColor = '#fbbf24'; badgeType = 'badge-amber'; }
              else if (log.event_type === 'command') { tagColor = '#c084fc'; badgeType = 'badge-purple'; }

              const timeStr = log.timestamp ? log.timestamp.split('T')[1]?.slice(0, 8) : '';

              return (
                <div 
                  key={log.id} 
                  style={{ 
                    display: 'flex', 
                    alignItems: 'flex-start', 
                    gap: '10px', 
                    padding: '2px 0',
                    lineHeight: '1.4'
                  }}
                >
                  <span style={{ color: '#475569', fontSize: '0.7rem', flexShrink: 0 }}>
                    {timeStr}
                  </span>
                  <span className={`badge ${badgeType}`} style={{ fontSize: '0.6rem', padding: '0 4px', flexShrink: 0 }}>
                    {log.agent_role || log.stage}
                  </span>
                  <span style={{ color: tagColor, flexShrink: 0, fontWeight: 600 }}>
                    [{log.event_type}]
                  </span>
                  <div style={{ color: '#cbd5e1', wordBreak: 'break-word', minWidth: 0 }}>
                    {log.message}
                    {typeof log.details?.rejected_output === 'string' && log.details.rejected_output && (
                      <details style={{ marginTop: 6 }}>
                        <summary>Show rejected model output (not written to the file)</summary>
                        {log.details.output_excerpt_truncated && <p>Only the first 16,000 characters were retained.</p>}
                        <pre style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{log.details.rejected_output}</pre>
                      </details>
                    )}
                  </div>
                </div>
              );
            })
          ) : (
            <div style={{ color: '#64748b', textAlign: 'center', padding: '20px 0' }}>
              {runId ? 'No matching logs found.' : 'Control Room ready. Start a task to stream live agent execution events.'}
            </div>
          )}
          <div ref={logEndRef} />
        </div>
      )}
    </div>
  );
}
