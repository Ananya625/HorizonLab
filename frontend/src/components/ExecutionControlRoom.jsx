import React, { useState, useEffect, useRef } from 'react';
import { 
  Terminal, 
  ChevronUp, 
  ChevronDown, 
  Search, 
  Filter, 
  Copy,
  Check,
  XCircle,
  AlertTriangle
} from 'lucide-react';
import {
  fetchPendingPolicyApproval,
  respondToPolicyApproval,
} from '../services/api';

export default function ExecutionControlRoom({
  runId,
  logs = [],
  onRefreshLogs
}) {
  // Default collapsed state as specified in requirements
  const [isOpen, setIsOpen] = useState(false);
  const [filterRole, setFilterRole] = useState('ALL');
  const [filterType, setFilterType] = useState('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const [autoScroll, setAutoScroll] = useState(true);
  const [copiedLogs, setCopiedLogs] = useState(false);
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
  }, [logs, isOpen, autoScroll]);

  const filteredLogs = logs.filter((log) => {
    if (filterRole !== 'ALL' && !log.agent_role?.toLowerCase().includes(filterRole.toLowerCase())) {
      return false;
    }
    if (filterType !== 'ALL') {
      if (filterType === 'error' && log.event_type !== 'error' && log.event_type !== 'warning') return false;
      if (filterType === 'success' && log.event_type !== 'success') return false;
      if (filterType === 'recovery' && log.event_type !== 'recovery') return false;
      if (filterType === 'command' && log.event_type !== 'command') return false;
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

  const copyAllLogs = () => {
    const text = filteredLogs.map(l => `[${l.timestamp || ''}] [${l.agent_role || l.stage}] [${l.event_type}] ${l.message}`).join('\n');
    navigator.clipboard?.writeText(text);
    setCopiedLogs(true);
    setTimeout(() => setCopiedLogs(false), 2000);
  };

  return (
    <div 
      className="execution-dock"
      style={{
        position: 'fixed',
        bottom: 0,
        left: 0,
        right: 0,
        backgroundColor: '#090E1A',
        borderTop: '1px solid rgba(255, 255, 255, 0.1)',
        boxShadow: '0 -8px 30px rgba(0, 0, 0, 0.6)',
        zIndex: 40,
        transition: 'all 0.25s cubic-bezier(0.16, 1, 0.3, 1)'
      }}
    >
      {/* Control Room Slim Bar Header */}
      <div 
        style={{
          padding: '8px 20px',
          backgroundColor: '#090E1A',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          borderBottom: isOpen ? '1px solid rgba(255, 255, 255, 0.08)' : 'none',
          cursor: 'pointer',
          userSelect: 'none',
          gap: '12px',
          flexWrap: 'wrap'
        }}
        onClick={() => setIsOpen(!isOpen)}
      >
        {/* Left identity & indicators */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
          <span 
            style={{
              width: '8px',
              height: '8px',
              borderRadius: '50%',
              backgroundColor: '#38BDF8',
              boxShadow: '0 0 8px #38BDF8',
              display: 'inline-block'
            }} 
            title="Live telemetry active" 
          />
          <Terminal size={15} color="#818CF8" />
          <span style={{ 
            fontSize: '0.825rem', 
            fontFamily: 'var(--font-heading, "Plus Jakarta Sans")', 
            fontWeight: 700, 
            color: '#F1F5F9' 
          }}>
            Execution Console
          </span>

          {runId && (
            <span style={{ 
              fontSize: '0.7rem', 
              fontFamily: 'var(--font-mono, monospace)',
              background: 'rgba(99, 102, 241, 0.15)', 
              color: '#A5B4FC', 
              border: '1px solid rgba(99, 102, 241, 0.3)',
              padding: '1px 8px',
              borderRadius: '9999px'
            }}>
              {runId}
            </span>
          )}

          {pendingApproval && (
            <span style={{ 
              fontSize: '0.7rem',
              fontWeight: 600,
              background: 'rgba(245, 158, 11, 0.15)',
              color: '#FCD34D',
              border: '1px solid rgba(245, 158, 11, 0.4)',
              padding: '2px 8px',
              borderRadius: '4px',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '4px'
            }}>
              <AlertTriangle size={12} />
              Human Approval Required
            </span>
          )}

          <span style={{ 
            fontSize: '0.7rem',
            color: '#94A3B8',
            background: 'rgba(255, 255, 255, 0.05)',
            border: '1px solid rgba(255, 255, 255, 0.08)',
            padding: '1px 8px',
            borderRadius: '9999px'
          }}>
            {logs.length} Recorded Events
          </span>
        </div>

        {/* Right controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }} onClick={(e) => e.stopPropagation()}>
          {/* Controls visible when expanded */}
          {isOpen && (
            <>
              {/* Agent Filter */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                <Filter size={12} color="#94A3B8" />
                <select
                  aria-label="Filter by agent"
                  value={filterRole}
                  onChange={(e) => setFilterRole(e.target.value)}
                  style={{
                    backgroundColor: '#111827',
                    color: '#F1F5F9',
                    border: '1px solid rgba(255, 255, 255, 0.12)',
                    borderRadius: '6px',
                    padding: '3px 8px',
                    fontSize: '0.72rem',
                    outline: 'none',
                    fontFamily: 'var(--font-sans)'
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

              {/* Event Type Filter */}
              <select
                aria-label="Filter by event type"
                value={filterType}
                onChange={(e) => setFilterType(e.target.value)}
                style={{
                  backgroundColor: '#111827',
                  color: '#F1F5F9',
                  border: '1px solid rgba(255, 255, 255, 0.12)',
                  borderRadius: '6px',
                  padding: '3px 8px',
                  fontSize: '0.72rem',
                  outline: 'none',
                  fontFamily: 'var(--font-sans)'
                }}
              >
                <option value="ALL">All Types</option>
                <option value="success">Success</option>
                <option value="error">Errors & Warnings</option>
                <option value="recovery">Recovery</option>
                <option value="command">Commands</option>
              </select>

              {/* Search Filter */}
              <div style={{ 
                display: 'flex', 
                alignItems: 'center', 
                gap: '4px', 
                backgroundColor: '#111827', 
                border: '1px solid rgba(255, 255, 255, 0.12)', 
                borderRadius: '6px', 
                padding: '3px 8px' 
              }}>
                <Search size={12} color="#94A3B8" />
                <input
                  aria-label="Search execution logs"
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search logs..."
                  style={{
                    background: 'transparent',
                    border: 'none',
                    color: '#F1F5F9',
                    fontSize: '0.72rem',
                    outline: 'none',
                    width: '110px',
                    fontFamily: 'var(--font-sans)'
                  }}
                />
                {searchQuery && (
                  <button
                    type="button"
                    onClick={() => setSearchQuery('')}
                    style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#94A3B8', padding: 0 }}
                  >
                    <XCircle size={11} />
                  </button>
                )}
              </div>

              {/* Auto Scroll Toggle */}
              <button
                type="button"
                onClick={() => setAutoScroll(!autoScroll)}
                title={autoScroll ? 'Auto-scroll is ON' : 'Auto-scroll is PAUSED'}
                style={{
                  background: autoScroll ? 'rgba(99, 102, 241, 0.15)' : 'rgba(255, 255, 255, 0.05)',
                  border: `1px solid ${autoScroll ? 'rgba(99, 102, 241, 0.35)' : 'rgba(255, 255, 255, 0.1)'}`,
                  color: autoScroll ? '#A5B4FC' : '#94A3B8',
                  borderRadius: '6px',
                  padding: '3px 8px',
                  fontSize: '0.68rem',
                  fontWeight: 600,
                  cursor: 'pointer'
                }}
              >
                Auto-scroll: {autoScroll ? 'ON' : 'OFF'}
              </button>

              {/* Copy Logs */}
              <button
                type="button"
                onClick={copyAllLogs}
                title="Copy all filtered logs to clipboard"
                style={{
                  background: 'rgba(255, 255, 255, 0.05)',
                  border: '1px solid rgba(255, 255, 255, 0.1)',
                  color: '#F1F5F9',
                  borderRadius: '6px',
                  padding: '3px 8px',
                  fontSize: '0.68rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 4
                }}
              >
                {copiedLogs ? <Check size={11} color="#34D399" /> : <Copy size={11} />}
                <span>{copiedLogs ? 'Copied' : 'Copy'}</span>
              </button>
            </>
          )}

          {/* Toggle Expand/Collapse */}
          <button
            type="button"
            onClick={() => setIsOpen(!isOpen)}
            style={{
              background: 'rgba(255, 255, 255, 0.06)',
              border: '1px solid rgba(255, 255, 255, 0.1)',
              borderRadius: '6px',
              padding: '3px 8px',
              color: '#F1F5F9',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              fontSize: '0.72rem',
              fontWeight: 600
            }}
          >
            <span>{isOpen ? 'Collapse' : 'Expand'}</span>
            {isOpen ? <ChevronDown size={14} /> : <ChevronUp size={14} />}
          </button>
        </div>
      </div>

      {/* Expanded Logs Body (Retained in DOM for tests with height control) */}
      <div 
        className={`execution-console-body ${isOpen ? 'is-open' : 'is-collapsed'}`}
        style={{
          maxHeight: isOpen ? 'min(36vh, 320px)' : '0px',
          height: isOpen ? 'min(36vh, 320px)' : '0px',
          overflowY: isOpen ? 'auto' : 'hidden',
          padding: isOpen ? '12px 20px' : '0 20px',
          opacity: isOpen ? 1 : 0,
          backgroundColor: '#070B14',
          color: '#E2E8F0',
          fontFamily: 'var(--font-mono, "JetBrains Mono", monospace)',
          fontSize: '0.74rem',
          display: 'flex',
          flexDirection: 'column',
          gap: '4px',
          borderTop: isOpen ? '1px solid #1E293B' : 'none',
          transition: 'all 0.22s ease-in-out'
        }}
      >
        {pendingApproval && (
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '10px 14px',
            marginBottom: '8px',
            backgroundColor: '#1E1B13',
            border: '1px solid #D97706',
            borderRadius: '6px',
            color: '#FCD34D',
            fontFamily: 'var(--font-sans, sans-serif)',
          }}>
            <span style={{ flex: 1, fontSize: '0.8rem', fontWeight: 600 }}>
              ⚠️ The agent paused at step {pendingApproval.step_index} and is waiting for approval.
            </span>
            {approvalError && (
              <span role="alert" style={{ color: '#F87171', fontWeight: 600 }}>{approvalError}</span>
            )}
            <input
              aria-label="Approval comment"
              value={approvalComment}
              onChange={(event) => setApprovalComment(event.target.value)}
              placeholder="Optional note"
              style={{
                background: '#0B0F19',
                border: '1px solid #4B5563',
                borderRadius: '4px',
                color: '#FFFFFF',
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
            let tagColor = '#38BDF8';
            let badgeColor = '#0F172A';
            let badgeBorder = 'rgba(255, 255, 255, 0.1)';
            let badgeTextColor = '#94A3B8';

            if (log.event_type === 'success') {
              tagColor = '#34D399';
              badgeTextColor = '#34D399';
              badgeColor = 'rgba(16, 185, 129, 0.1)';
              badgeBorder = 'rgba(16, 185, 129, 0.25)';
            } else if (log.event_type === 'error' || log.event_type === 'warning') {
              tagColor = '#F87171';
              badgeTextColor = '#F87171';
              badgeColor = 'rgba(239, 68, 68, 0.1)';
              badgeBorder = 'rgba(239, 68, 68, 0.25)';
            } else if (log.event_type === 'recovery') {
              tagColor = '#FBBF24';
              badgeTextColor = '#FBBF24';
              badgeColor = 'rgba(245, 158, 11, 0.1)';
              badgeBorder = 'rgba(245, 158, 11, 0.25)';
            } else if (log.event_type === 'command') {
              tagColor = '#A78BFA';
              badgeTextColor = '#A78BFA';
              badgeColor = 'rgba(139, 92, 246, 0.1)';
              badgeBorder = 'rgba(139, 92, 246, 0.25)';
            }

            const timeStr = log.timestamp ? log.timestamp.split('T')[1]?.slice(0, 8) : '';

            return (
              <div 
                key={log.id} 
                style={{ 
                  display: 'flex', 
                  alignItems: 'flex-start', 
                  gap: '10px', 
                  padding: '3px 8px',
                  borderRadius: '4px',
                  lineHeight: '1.45',
                  transition: 'background 0.15s ease'
                }}
                onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'rgba(255, 255, 255, 0.04)'}
                onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
              >
                <span style={{ color: '#64748B', fontSize: '0.7rem', flexShrink: 0, fontFamily: 'var(--font-mono)' }}>
                  {timeStr}
                </span>
                <span style={{
                  fontSize: '0.62rem',
                  padding: '1px 6px',
                  flexShrink: 0,
                  borderRadius: '3px',
                  background: badgeColor,
                  border: `1px solid ${badgeBorder}`,
                  color: badgeTextColor,
                  fontWeight: 600
                }}>
                  {log.agent_role || log.stage}
                </span>
                <span style={{ color: tagColor, flexShrink: 0, fontWeight: 700 }}>
                  [{log.event_type}]
                </span>
                <div style={{ color: '#E2E8F0', wordBreak: 'break-word', minWidth: 0, flex: 1 }}>
                  {log.message}
                  {typeof log.details?.rejected_output === 'string' && log.details.rejected_output && (
                    <details style={{ marginTop: 6 }}>
                      <summary style={{ color: '#F87171', cursor: 'pointer', fontWeight: 600 }}>
                        Show rejected model output (not written to the file)
                      </summary>
                      {log.details.output_excerpt_truncated && (
                        <p style={{ color: '#94A3B8', margin: '4px 0' }}>
                          Only the first 16,000 characters were retained.
                        </p>
                      )}
                      <pre style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere', backgroundColor: '#111827', padding: '8px', border: '1px solid #1F2937', borderRadius: '4px', marginTop: '4px', color: '#F1F5F9' }}>
                        {log.details.rejected_output}
                      </pre>
                    </details>
                  )}
                </div>
              </div>
            );
          })
        ) : (
          <div style={{ color: '#64748B', textAlign: 'center', padding: '24px 0', fontSize: '0.8rem' }}>
            {runId ? 'No matching logs found.' : 'Telemetry console ready. Start a task to stream live agent execution events.'}
          </div>
        )}
        <div ref={logEndRef} />
      </div>
    </div>
  );
}
