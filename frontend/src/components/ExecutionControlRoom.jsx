import React, { useState, useEffect, useRef } from 'react';
import { 
  Terminal, 
  ChevronUp, 
  ChevronDown, 
  Search, 
  Filter, 
  Cpu, 
  Copy,
  Check,
  XCircle
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
  const [isOpen, setIsOpen] = useState(true);
  const [filterRole, setFilterRole] = useState('ALL');
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

  const agentActivity = [...filteredLogs.reduce((activity, log) => {
    const name = log.agent_role || log.stage || 'Unattributed';
    const current = activity.get(name) || { name, eventCount: 0, attentionCount: 0, latestEvent: null };
    current.eventCount += 1;
    if (log.event_type === 'error' || log.event_type === 'warning') current.attentionCount += 1;
    current.latestEvent = log;
    activity.set(name, current);
    return activity;
  }, new Map()).values()];

  return (
    <div style={{
      position: 'fixed',
      bottom: 0,
      left: 0,
      right: 0,
      backgroundColor: 'var(--bg-card, #FFFFFF)',
      borderTop: '1px solid var(--border-subtle, #E5E7EF)',
      boxShadow: '0 -6px 20px rgba(16, 24, 40, 0.1)',
      zIndex: 40,
      transition: 'all 0.25s cubic-bezier(0.4, 0, 0.2, 1)'
    }}>
      {/* Control Room Bar Header */}
      <div 
        style={{
          padding: '10px 20px',
          backgroundColor: 'var(--bg-card, #FFFFFF)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          borderBottom: isOpen ? '1px solid var(--border-subtle, #E5E7EF)' : 'none',
          cursor: 'pointer',
          userSelect: 'none',
          gap: '12px',
          flexWrap: 'wrap'
        }}
        onClick={() => setIsOpen(!isOpen)}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
          <span className="live-pulse-dot" title="Live stream active" />
          <Terminal size={16} color="var(--accent-primary, #315B40)" />
          <span style={{ fontSize: '0.85rem', fontFamily: 'var(--font-heading, "Plus Jakarta Sans")', fontWeight: 700, color: 'var(--text-primary, #172033)' }}>
            Execution Console & Live Telemetry
          </span>
          {runId && (
            <span className="wf-pill-badge wf-mono" style={{ fontSize: '0.7rem', background: 'var(--accent-primary-subtle)', color: 'var(--accent-primary)', borderColor: 'var(--accent-primary-border)' }}>
              {runId}
            </span>
          )}
          {pendingApproval && (
            <span className="badge badge-amber" style={{ fontSize: '0.68rem', animation: 'live-pulse-anim 1.5s infinite' }}>
              ⚠ Human Approval Required
            </span>
          )}
          <span className="wf-pill-badge" style={{ fontSize: '0.68rem' }}>
            {logs.length} Events Logged
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }} onClick={(e) => e.stopPropagation()}>
          {isOpen && (
            <>
              {/* Agent Filter */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                <Filter size={13} color="var(--text-secondary, #667085)" />
                <select
                  aria-label="Filter by agent"
                  value={filterRole}
                  onChange={(e) => setFilterRole(e.target.value)}
                  style={{
                    backgroundColor: 'var(--bg-card-subtle, #F8F9FC)',
                    color: 'var(--text-primary, #172033)',
                    border: '1px solid var(--border-subtle, #E5E7EF)',
                    borderRadius: '6px',
                    padding: '3px 8px',
                    fontSize: '0.74rem',
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

              {/* Search Filter */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '4px', backgroundColor: 'var(--bg-card-subtle, #F8F9FC)', border: '1px solid var(--border-subtle, #E5E7EF)', borderRadius: '6px', padding: '3px 8px' }}>
                <Search size={13} color="var(--text-secondary, #667085)" />
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
                    fontSize: '0.74rem',
                    outline: 'none',
                    width: '120px',
                    fontFamily: 'var(--font-sans)'
                  }}
                />
                {searchQuery && (
                  <button
                    type="button"
                    onClick={() => setSearchQuery('')}
                    style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', padding: 0 }}
                  >
                    <XCircle size={12} />
                  </button>
                )}
              </div>

              {/* Auto Scroll Toggle */}
              <button
                type="button"
                onClick={() => setAutoScroll(!autoScroll)}
                title={autoScroll ? 'Auto-scroll is ON' : 'Auto-scroll is PAUSED'}
                style={{
                  background: autoScroll ? 'var(--accent-primary-subtle)' : 'var(--bg-card-subtle)',
                  border: `1px solid ${autoScroll ? 'var(--accent-primary-border)' : 'var(--border-subtle)'}`,
                  color: autoScroll ? 'var(--accent-primary)' : 'var(--text-secondary)',
                  borderRadius: '6px',
                  padding: '3px 8px',
                  fontSize: '0.7rem',
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
                  background: 'var(--bg-card-subtle)',
                  border: '1px solid var(--border-subtle)',
                  color: 'var(--text-secondary)',
                  borderRadius: '6px',
                  padding: '3px 8px',
                  fontSize: '0.7rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 4
                }}
              >
                {copiedLogs ? <Check size={12} color="var(--success-color)" /> : <Copy size={12} />}
                <span>{copiedLogs ? 'Copied' : 'Copy'}</span>
              </button>
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
              fontSize: '0.75rem',
              fontWeight: 600
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
          maxHeight: '320px',
          overflowY: 'auto',
          padding: '12px 20px',
          backgroundColor: '#0B0F19',
          color: '#E2E8F0',
          fontFamily: 'var(--font-mono, "JetBrains Mono", monospace)',
          fontSize: '0.75rem',
          display: 'flex',
          flexDirection: 'column',
          gap: '4px',
          borderTop: '1px solid #1E293B'
        }}>
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

          {agentActivity.length > 0 && (
            <section className="observed-agent-activity" aria-label="Observed agent activity from execution logs" style={{ background: '#111827', borderColor: '#1F2937', color: '#E5E7EB' }}>
              <div className="observed-agent-heading">
                <div>
                  <strong style={{ color: '#F9FAFB' }}>Observed agent activity</strong>
                  <span style={{ color: '#9CA3AF' }}>From {filteredLogs.length} matching recorded event{filteredLogs.length === 1 ? '' : 's'}</span>
                </div>
                <span className="observed-agent-count" style={{ background: '#1F2937', color: '#D1D5DB', borderColor: '#374151' }}>
                  {agentActivity.length} observed
                </span>
              </div>
              <div className="observed-agent-track">
                {agentActivity.map((agent) => {
                  const latestType = agent.latestEvent?.event_type || 'event';
                  const tone = agent.attentionCount > 0
                    ? 'attention'
                    : latestType === 'success'
                      ? 'success'
                      : 'neutral';
                  return (
                    <article className={`observed-agent-card is-${tone}`} key={agent.name} style={{ background: '#1F2937', borderColor: '#374151' }}>
                      <div className="observed-agent-card-top">
                        <span className="observed-agent-icon" style={{ background: '#111827', borderColor: '#374151', color: '#60A5FA' }}><Cpu size={14} /></span>
                        <span className={`observed-agent-status is-${tone}`}>
                          {agent.attentionCount > 0 ? `${agent.attentionCount} attention` : latestType}
                        </span>
                      </div>
                      <strong className="observed-agent-name" style={{ color: '#F9FAFB' }}>{agent.name}</strong>
                      <span className="observed-agent-events" style={{ color: '#9CA3AF' }}>{agent.eventCount} recorded event{agent.eventCount === 1 ? '' : 's'}</span>
                      {agent.latestEvent?.message && (
                        <span className="observed-agent-latest" title={agent.latestEvent.message} style={{ color: '#CBD5E1' }}>
                          {agent.latestEvent.message}
                        </span>
                      )}
                    </article>
                  );
                })}
              </div>
            </section>
          )}

          {filteredLogs.length > 0 ? (
            filteredLogs.map((log) => {
              let tagColor = '#38BDF8';
              let badgeColor = '#1E293B';
              let badgeBorder = '#334155';
              let badgeTextColor = '#94A3B8';

              if (log.event_type === 'success') {
                tagColor = '#34D399';
                badgeTextColor = '#34D399';
              } else if (log.event_type === 'error' || log.event_type === 'warning') {
                tagColor = '#F87171';
                badgeTextColor = '#F87171';
              } else if (log.event_type === 'recovery') {
                tagColor = '#FBBF24';
                badgeTextColor = '#FBBF24';
              } else if (log.event_type === 'command') {
                tagColor = '#A78BFA';
                badgeTextColor = '#A78BFA';
              }

              const timeStr = log.timestamp ? log.timestamp.split('T')[1]?.slice(0, 8) : '';

              return (
                <div 
                  key={log.id} 
                  style={{ 
                    display: 'flex', 
                    alignItems: 'flex-start', 
                    gap: '10px', 
                    padding: '3px 6px',
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
                        <pre style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere', backgroundColor: '#1E293B', padding: '8px', border: '1px solid #334155', borderRadius: '4px', marginTop: '4px', color: '#F1F5F9' }}>
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
      )}
    </div>
  );
}
