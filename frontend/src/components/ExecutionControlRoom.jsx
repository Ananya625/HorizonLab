import React, { useState, useEffect, useRef } from 'react';
import { 
  Terminal, 
  ChevronUp, 
  ChevronDown, 
  Search, 
  Filter, 
  Cpu, 
  CheckCircle2, 
  AlertTriangle 
} from 'lucide-react';
import {
  fetchRunLogs,
  fetchPendingPolicyApproval,
  respondToPolicyApproval,
} from '../services/api';

export default function ExecutionControlRoom({
  runId,
  logs = [],
  onRefreshLogs
}) {
  const [isOpen, setIsOpen] = useState(true);
  const [filterRole, setFilterRole] = useState('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const [autoScroll, setAutoScroll] = useState(true);
  const [pendingApproval, setPendingApproval] = useState(null);
  const [approvalComment, setApprovalComment] = useState('');
  const [isSubmittingApproval, setIsSubmittingApproval] = useState(false);
  const [approvalError, setApprovalError] = useState('');
  const logEndRef = useRef(null);

  useEffect(() => {
    if (!runId) {
      setPendingApproval(null);
      return undefined;
    }
    let active = true;
    const refreshApproval = () => {
      fetchPendingPolicyApproval(runId)
        .then((approval) => {
          if (active) setPendingApproval(approval);
        })
        .catch((err) => console.warn('Policy approval status error:', err));
    };
    refreshApproval();
    const interval = setInterval(refreshApproval, 1000);
    return () => {
      active = false;
      clearInterval(interval);
    };
  }, [runId]);

  const submitApproval = async (approved) => {
    if (!pendingApproval || isSubmittingApproval) return;
    setIsSubmittingApproval(true);
    try {
      await respondToPolicyApproval(
        runId,
        pendingApproval.approval_id,
        approved,
        approvalComment
      );
      setPendingApproval(null);
      setApprovalComment('');
      setApprovalError('');
    } catch (err) {
      setApprovalError(err.message || 'Could not submit approval response.');
      console.error('Policy approval response failed:', err);
    } finally {
      setIsSubmittingApproval(false);
    }
  };

  useEffect(() => {
    if (autoScroll && logEndRef.current && isOpen) {
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
      backgroundColor: '#FFFFFF',
      borderTop: '1px solid var(--border-subtle, #E5E7EF)',
      boxShadow: '0 -4px 16px rgba(16, 24, 40, 0.08)',
      zIndex: 40,
      transition: 'all 0.25s ease'
    }}>
      {/* Control Room Bar Header (Collapsed Bar) */}
      <div 
        style={{
          padding: '8px 20px',
          backgroundColor: '#FFFFFF',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          borderBottom: isOpen ? '1px solid var(--border-subtle, #E5E7EF)' : 'none',
          cursor: 'pointer',
          userSelect: 'none'
        }}
        onClick={() => setIsOpen(!isOpen)}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <Terminal size={15} color="var(--accent-primary, #6257D9)" />
          <span style={{ fontSize: '0.825rem', fontFamily: 'var(--font-heading, "Plus Jakarta Sans")', fontWeight: 700, color: 'var(--text-primary, #172033)' }}>
            Execution Console & Live Telemetry
          </span>
          {runId && (
            <span className="badge badge-purple" style={{ fontSize: '0.65rem' }}>
              {runId}
            </span>
          )}
          {pendingApproval && (
            <span className="badge badge-amber" style={{ fontSize: '0.65rem' }}>
              Human Approval Required
            </span>
          )}
          <span className="badge badge-slate" style={{ fontSize: '0.65rem' }}>
            {logs.length} Events Logged
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }} onClick={(e) => e.stopPropagation()}>
          {isOpen && (
            <>
              {/* Agent Filter */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                <Filter size={12} color="var(--text-secondary, #667085)" />
                <select
                  aria-label="Filter by agent"
                  value={filterRole}
                  onChange={(e) => setFilterRole(e.target.value)}
                  style={{
                    backgroundColor: '#F8F9FC',
                    color: 'var(--text-primary, #172033)',
                    border: '1px solid var(--border-subtle, #E5E7EF)',
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
              <div style={{ display: 'flex', alignItems: 'center', gap: '4px', backgroundColor: '#F8F9FC', border: '1px solid var(--border-subtle, #E5E7EF)', borderRadius: '4px', padding: '2px 8px' }}>
                <Search size={12} color="var(--text-secondary, #667085)" />
                <input
                  aria-label="Search execution logs"
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Filter logs..."
                  style={{
                    background: 'transparent',
                    border: 'none',
                    color: 'var(--text-primary, #172033)',
                    fontSize: '0.725rem',
                    outline: 'none',
                    width: '110px'
                  }}
                />
              </div>
            </>
          )}

          {/* Toggle Expand/Collapse */}
          <button
            type="button"
            onClick={() => setIsOpen(!isOpen)}
            style={{
              background: 'transparent',
              border: 'none',
              color: 'var(--text-secondary, #667085)',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              fontSize: '0.725rem',
              fontWeight: 500
            }}
          >
            <span>{isOpen ? 'Collapse' : 'Expand'}</span>
            {isOpen ? <ChevronDown size={16} /> : <ChevronUp size={16} />}
          </button>
        </div>
      </div>

      {/* Expanded Logs Body */}
      {isOpen && (
        <div style={{
          maxHeight: '210px',
          overflowY: 'auto',
          padding: '10px 20px',
          backgroundColor: '#F8F9FC',
          fontFamily: 'var(--font-mono)',
          fontSize: '0.75rem',
          display: 'flex',
          flexDirection: 'column',
          gap: '4px',
          borderTop: '1px solid var(--border-subtle, #E5E7EF)'
        }}>
          {pendingApproval && (
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              padding: '10px',
              marginBottom: '8px',
              backgroundColor: '#FFFBEB',
              border: '1px solid #FDE68A',
              borderRadius: '6px',
              color: '#B7791F',
              fontFamily: 'var(--font-sans, sans-serif)',
            }}>
              <span style={{ flex: 1, fontSize: '0.8rem', fontWeight: 500 }}>
                The agent paused at step {pendingApproval.step_index} and is waiting for approval.
              </span>
              {approvalError && (
                <span role="alert" style={{ color: 'var(--danger-color, #D14343)' }}>{approvalError}</span>
              )}
              <input
                aria-label="Approval comment"
                value={approvalComment}
                onChange={(event) => setApprovalComment(event.target.value)}
                placeholder="Optional note"
                style={{
                  background: '#FFFFFF',
                  border: '1px solid #E5E7EF',
                  borderRadius: '4px',
                  color: '#172033',
                  padding: '5px 8px',
                  fontSize: '0.75rem'
                }}
              />
              <button
                type="button"
                disabled={isSubmittingApproval}
                onClick={() => submitApproval(true)}
                className="btn btn-emerald btn-sm"
              >
                Approve
              </button>
              <button
                type="button"
                disabled={isSubmittingApproval}
                onClick={() => submitApproval(false)}
                className="btn btn-danger btn-sm"
              >
                Reject
              </button>
            </div>
          )}

          {filteredLogs.length > 0 ? (
            filteredLogs.map((log) => {
              let tagColor = 'var(--accent-primary, #6257D9)';
              let badgeType = 'badge-purple';
              if (log.event_type === 'success') { tagColor = 'var(--success-color, #16845B)'; badgeType = 'badge-emerald'; }
              else if (log.event_type === 'error' || log.event_type === 'warning') { tagColor = 'var(--danger-color, #D14343)'; badgeType = 'badge-rose'; }
              else if (log.event_type === 'recovery') { tagColor = 'var(--warning-color, #B7791F)'; badgeType = 'badge-amber'; }
              else if (log.event_type === 'command') { tagColor = '#6257D9'; badgeType = 'badge-slate'; }

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
                  <span style={{ color: 'var(--text-secondary, #667085)', fontSize: '0.7rem', flexShrink: 0 }}>
                    {timeStr}
                  </span>
                  <span className={`badge ${badgeType}`} style={{ fontSize: '0.6rem', padding: '0 5px', flexShrink: 0 }}>
                    {log.agent_role || log.stage}
                  </span>
                  <span style={{ color: tagColor, flexShrink: 0, fontWeight: 700 }}>
                    [{log.event_type}]
                  </span>
                  <div style={{ color: 'var(--text-primary, #172033)', wordBreak: 'break-word', minWidth: 0 }}>
                    {log.message}
                    {typeof log.details?.rejected_output === 'string' && log.details.rejected_output && (
                      <details style={{ marginTop: 6 }}>
                        <summary>Show rejected model output (not written to the file)</summary>
                        {log.details.output_excerpt_truncated && <p style={{ color: 'var(--text-secondary, #667085)', margin: '4px 0' }}>Only the first 16,000 characters were retained.</p>}
                        <pre style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere', backgroundColor: '#FFFFFF', padding: '8px', border: '1px solid #E5E7EF', borderRadius: '4px', marginTop: '4px' }}>
                          {log.details.rejected_output}
                        </pre>
                      </details>
                    )}
                  </div>
                </div>
              );
            })
          ) : (
            <div style={{ color: 'var(--text-secondary, #667085)', textAlign: 'center', padding: '20px 0', fontSize: '0.8rem' }}>
              {runId ? 'No matching logs found.' : 'Telemetry console ready. Start a task to stream live agent execution events.'}
            </div>
          )}
          <div ref={logEndRef} />
        </div>
      )}
    </div>
  );
}
