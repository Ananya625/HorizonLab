import React, { useState, useEffect, useRef } from 'react';
import { 
  Activity, 
  RefreshCw, 
  Download, 
  ShieldCheck, 
  Layers, 
  Cpu,
  BarChart2,
  TrendingUp
} from 'lucide-react';
import {
  fetchCapabilityProfiles,
  fetchHierarchicalProficiency,
  rebuildHierarchicalProficiency,
} from '../services/api';

const capColors = {
  coding: '#6257D9',
  verification: '#16845B',
  recovery: '#D97706',
  efficiency: '#0284C7',
  generalization: '#7C3AED',
  instruction_following: '#2563EB',
};

function formatDuration(sec) {
  if (sec == null || !Number.isFinite(sec)) return '—';
  if (sec < 60) return `${Math.round(sec)}s`;
  const m = Math.floor(sec / 60);
  const s = Math.round(sec % 60);
  return `${m}m ${s}s`;
}

function StatusPill({ status }) {
  const map = {
    sufficient_evidence: { cls: 'badge-emerald', label: 'Sufficient evidence' },
    insufficient_evidence: { cls: 'badge-slate', label: 'Insufficient evidence' },
    measured: { cls: 'badge-emerald', label: 'Measured' },
    unmeasured: { cls: 'badge-slate', label: 'Unmeasured' },
    estimated: { cls: 'badge-amber', label: 'Estimated' },
    optimal: { cls: 'badge-emerald', label: 'Optimal' },
  };
  const { cls, label } = map[status] || { cls: 'badge-slate', label: status };
  return <span className={`badge ${cls}`} style={{ fontSize: '0.65rem' }}>{label}</span>;
}

function PercentageMeter({ label, value, color = '#10B981' }) {
  if (value == null || !Number.isFinite(value)) {
    return (
      <div className="evaluation-meter is-unavailable" role="img" aria-label={`${label} unavailable`}>
        <span className="evaluation-meter-empty">Unavailable</span>
      </div>
    );
  }
  const percentage = Math.max(0, Math.min(100, Math.round(value)));
  return (
    <div
      className="evaluation-meter"
      role="img"
      aria-label={`${label}: ${percentage}%`}
      aria-valuenow={percentage}
      aria-valuemin={0}
      aria-valuemax={100}
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

function BinaryCapabilityCard({ profile }) {
  const color = capColors[profile.capability] || '#818CF8';
  const successes = profile.successes ?? profile.k;
  const sampleSize = profile.sample_size ?? profile.n;
  const outcomeLabel = (successes != null && sampleSize != null)
    ? (profile.capability === 'coding'
        ? `${successes} / ${sampleSize} tasks verified`
        : `${successes} / ${sampleSize} successes`)
    : (profile.sample_size ? `${profile.sample_size} outcomes` : 'Unavailable');

  const observedDisplay = Number.isFinite(profile.observed_rate)
    ? `${Math.round(profile.observed_rate * 100)}%`
    : 'Unavailable';

  return (
    <div style={{
      background: '#0D1526', padding: '16px 18px', borderRadius: '8px',
      border: '1px solid rgba(255, 255, 255, 0.08)', borderLeft: `3px solid ${color}`
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
        <div>
          <div style={{ color, fontWeight: 700, textTransform: 'capitalize', fontSize: '0.95rem' }}>
            {profile.display_name || profile.capability.replace(/_/g, ' ')}
          </div>
          <div style={{ color: '#94A3B8', fontSize: '0.7rem', marginTop: '1px' }}>
            {profile.model_name}
          </div>
        </div>
        <StatusPill status={profile.evidence_status} />
      </div>

      <div className="capability-resource-strip" aria-label={`${profile.display_name || profile.capability} resource and outcome summary`}>
        <div className="capability-resource-metric">
          <span className="capability-resource-label">Observed</span>
          <span className="capability-resource-value" style={{ color: '#F1F5F9' }}>
            {observedDisplay}
          </span>
        </div>
        <div className="capability-resource-metric">
          <span className="capability-resource-label">Outcome</span>
          <span className="capability-resource-value" style={{ color: '#F1F5F9' }}>
            {outcomeLabel}
          </span>
        </div>
        <div className="capability-resource-metric">
          <span className="capability-resource-label">Duration</span>
          <span className="capability-resource-value" style={{ color: '#F1F5F9' }}>
            {formatDuration(profile.mean_duration_seconds)}
          </span>
        </div>
      </div>

      <div style={{ marginTop: '10px' }}>
        <PercentageMeter
          value={Number.isFinite(profile.observed_rate) ? profile.observed_rate * 100 : null}
          color={color}
          label={`${profile.display_name || profile.capability} observed rate`}
        />
      </div>
    </div>
  );
}

function EfficiencyCard({ profile }) {
  const fmt = formatDuration;
  return (
    <div style={{
      background: '#0D1526', padding: '16px 18px', borderRadius: '8px',
      border: '1px solid rgba(255, 255, 255, 0.08)', borderLeft: '3px solid #818CF8'
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '10px' }}>
        <div>
          <div style={{ color: '#818CF8', fontWeight: 700, fontSize: '0.95rem' }}>efficiency</div>
          <div style={{ color: '#94A3B8', fontSize: '0.7rem' }}>Task duration (continuous)</div>
        </div>
        <StatusPill status={profile.evidence_status || (profile.n > 0 ? 'measured' : 'insufficient_evidence')} />
      </div>
      {profile.n === 0 ? (
        <div style={{ color: '#64748b', fontSize: '0.78rem', fontStyle: 'italic' }}>
          No verifiable task durations recorded yet.
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(100px, 1fr))', gap: '10px' }}>
          <div style={{ background: 'rgba(255, 255, 255, 0.03)', padding: '8px 10px', borderRadius: '6px', border: '1px solid rgba(255, 255, 255, 0.07)' }}>
            <div style={{ color: '#94A3B8', fontSize: '0.65rem' }}>Mean</div>
            <div style={{ fontWeight: 700, fontSize: '0.9rem', color: '#F1F5F9' }}>{fmt(profile.mean)}</div>
          </div>
          <div style={{ background: 'rgba(255, 255, 255, 0.03)', padding: '8px 10px', borderRadius: '6px', border: '1px solid rgba(255, 255, 255, 0.07)' }}>
            <div style={{ color: '#94A3B8', fontSize: '0.65rem' }}>Median</div>
            <div style={{ fontWeight: 700, fontSize: '0.9rem', color: '#F1F5F9' }}>{fmt(profile.median)}</div>
          </div>
          <div style={{ background: 'rgba(255, 255, 255, 0.03)', padding: '8px 10px', borderRadius: '6px', border: '1px solid rgba(255, 255, 255, 0.07)' }}>
            <div style={{ color: '#94A3B8', fontSize: '0.65rem' }}>Min</div>
            <div style={{ fontWeight: 700, fontSize: '0.9rem', color: '#F1F5F9' }}>{fmt(profile.min)}</div>
          </div>
          <div style={{ background: 'rgba(255, 255, 255, 0.03)', padding: '8px 10px', borderRadius: '6px', border: '1px solid rgba(255, 255, 255, 0.07)' }}>
            <div style={{ color: '#94A3B8', fontSize: '0.65rem' }}>Max</div>
            <div style={{ fontWeight: 700, fontSize: '0.9rem', color: '#F1F5F9' }}>{fmt(profile.max)}</div>
          </div>
        </div>
      )}
    </div>
  );
}

function HierarchicalProfilingPanel({ data, loading, onRebuild, error, selectedRunId }) {
  if (loading && !data) {
    return (
      <div style={{ color: '#94A3B8', fontSize: '0.85rem', padding: '32px', textAlign: 'center' }}>
        <RefreshCw size={20} className="animate-spin" style={{ margin: '0 auto 8px', display: 'block' }} />
        Loading observed agent outcome rates...
      </div>
    );
  }

  if (!data) {
    return (
      <div style={{ color: '#94A3B8', fontSize: '0.82rem', fontStyle: 'italic', padding: '16px 0' }}>
        {error || 'No observed profile data is available for this run yet.'}
      </div>
    );
  }

  const { system_profile, agent_profiles = {}, attribution_matrix = {}, total_runs_analyzed = 0 } = data;
  const pct = (v) => v != null ? `${Math.round(v * 100)}%` : '—';
  const failureAttributions = Object.entries(attribution_matrix.failure_attributions || {});
  const recoveryAttributions = Object.entries(attribution_matrix.recovery_attributions || {});
  const maxFailureCount = Math.max(0, ...failureAttributions.map(([, count]) => Number(count)).filter(Number.isFinite));
  const maxRecoveryCount = Math.max(0, ...recoveryAttributions.map(([, count]) => Number(count)).filter(Number.isFinite));

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <div className="card-panel" style={{
        padding: '20px 24px',
        backgroundColor: '#0D1526',
        border: '1px solid rgba(255, 255, 255, 0.08)',
        borderRadius: '12px'
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px', flexWrap: 'wrap', gap: '10px' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
              <span className="badge badge-emerald" style={{ fontSize: '0.65rem' }}>Level 2: Macro System Profile</span>
              <span style={{ fontSize: '0.72rem', color: '#94A3B8' }}>{selectedRunId ? `Selected run: ${selectedRunId}` : 'All observed runs'}</span>
            </div>
            <h3 style={{ fontSize: '1.15rem', fontWeight: 700, color: '#F8FAFC', margin: 0 }}>
              End-to-End Verified System Proficiency
            </h3>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <StatusPill status={system_profile?.evidence_status || 'insufficient_evidence'} />
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={onRebuild}
              style={{ fontSize: '0.72rem', padding: '5px 10px', display: 'flex', alignItems: 'center', gap: '6px' }}
            >
              <RefreshCw size={12} /><span>Re-sync DB Runs</span>
            </button>
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '14px' }}>
          <MetricCell
            label="Total Runs Analyzed"
            value={total_runs_analyzed}
            color="#F1F5F9"
            sub="empirical runs in SQLite"
          />
          <MetricCell
            label="Observed Verified Run Rate"
            value={pct(system_profile?.verified_success_rate?.observed_rate)}
            color="#34D399"
            sub={`${system_profile?.verified_success_rate?.successes ?? 0} passed / ${system_profile?.verified_success_rate?.failures ?? 0} failed (n=${system_profile?.verified_success_rate?.sample_size ?? 0})`}
            visual={<PercentageMeter
              label="Observed verified run rate"
              value={Number.isFinite(system_profile?.verified_success_rate?.observed_rate)
                ? system_profile.verified_success_rate.observed_rate * 100
                : null}
              color="#10B981"
            />}
          />
          <MetricCell
            label="Mean Pipeline Latency"
            value={formatDuration(system_profile?.duration_summary?.mean)}
            color="#38BDF8"
            sub={system_profile?.duration_summary?.n ? `across ${system_profile.duration_summary.n} completed executions` : 'no duration data'}
          />
          <MetricCell
            label="Failures Identified"
            value={attribution_matrix.total_failures_observed || 0}
            color={attribution_matrix.total_failures_observed > 0 ? '#FBBF24' : '#34D399'}
            sub="from captured execution events"
          />
        </div>
      </div>

      <div className="card-panel" style={{ padding: '20px', backgroundColor: '#0D1526', border: '1px solid rgba(255, 255, 255, 0.08)', borderRadius: '12px' }}>
        <h3 style={{ fontSize: '0.95rem', fontWeight: 600, color: '#F1F5F9', display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
          <ShieldCheck size={16} color="#38BDF8" />
          <span>Failure & Recovery Attribution Matrix</span>
        </h3>
        <p style={{ fontSize: '0.75rem', color: '#94A3B8', marginBottom: '14px' }}>
          Rates and counts are calculated from captured files, test outcomes, recovery attempts, and verification records. Missing evidence is shown as unavailable.
        </p>

        <div className="evaluation-attribution-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '16px' }}>
          <div style={{ background: '#060A14', padding: '14px', borderRadius: '8px', border: '1px solid rgba(255, 255, 255, 0.08)' }}>
            <div style={{ color: '#94A3B8', fontSize: '0.7rem', textTransform: 'uppercase', marginBottom: '10px', fontWeight: 600 }}>
              Root-Cause Failure Distribution
            </div>
            {Object.keys(attribution_matrix.failure_attributions || {}).length === 0 ? (
              <div style={{ color: '#34D399', fontSize: '0.78rem', padding: '8px 0' }}>
                No failure events were captured for this view.
              </div>
            ) : (
              <div className="evaluation-category-bars">
                {failureAttributions.map(([cause, cnt]) => (
                  <div key={cause} className="evaluation-category-row">
                    <div className="evaluation-category-heading">
                      <span style={{ color: '#F1F5F9' }}>{cause}</span>
                      <span className="badge badge-amber" style={{ fontSize: '0.65rem' }}>{cnt} run(s)</span>
                    </div>
                    <div className="evaluation-category-track" role="img" aria-label={`${cause}: ${cnt} runs, relative to most frequent cause`}>
                      <span style={{ width: `${maxFailureCount > 0 && Number.isFinite(Number(cnt)) ? Math.max(0, Math.min(100, (Number(cnt) / maxFailureCount) * 100)) : 0}%`, background: '#D9A441' }} />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div style={{ background: '#060A14', padding: '14px', borderRadius: '8px', border: '1px solid rgba(255, 255, 255, 0.08)' }}>
            <div style={{ color: '#94A3B8', fontSize: '0.7rem', textTransform: 'uppercase', marginBottom: '10px', fontWeight: 600 }}>
              Recovery Resolution Outcomes
            </div>
            {Object.keys(attribution_matrix.recovery_attributions || {}).length === 0 ? (
              <div style={{ color: '#94A3B8', fontSize: '0.78rem', fontStyle: 'italic', padding: '8px 0' }}>
                No recovery episodes recorded.
              </div>
            ) : (
              <div className="evaluation-category-bars">
                {recoveryAttributions.map(([outcome, cnt]) => (
                  <div key={outcome} className="evaluation-category-row">
                    <div className="evaluation-category-heading">
                      <span style={{ color: '#F1F5F9' }}>{outcome}</span>
                      <span className={`badge ${outcome.includes('recovered') ? 'badge-emerald' : outcome.includes('clean') || outcome.includes('no_recovery') ? 'badge-purple' : 'badge-rose'}`} style={{ fontSize: '0.65rem' }}>
                        {cnt} episode(s)
                      </span>
                    </div>
                    <div className="evaluation-category-track" role="img" aria-label={`${outcome}: ${cnt} episodes, relative to most frequent outcome`}>
                      <span style={{ width: `${maxRecoveryCount > 0 && Number.isFinite(Number(cnt)) ? Math.max(0, Math.min(100, (Number(cnt) / maxRecoveryCount) * 100)) : 0}%`, background: outcome.includes('recovered') ? '#10B981' : '#6366F1' }} />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      <div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
          <span className="badge badge-purple" style={{ fontSize: '0.65rem' }}>Level 1: Micro Component Profiles</span>
          <h3 style={{ fontSize: '1rem', fontWeight: 700, color: '#F1F5F9', margin: 0 }}>
            Individual Agent Proficiencies (All 7 Pipeline Agents)
          </h3>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '16px' }}>
          {Object.entries(agent_profiles).map(([agentId, prof]) => {
            const pm = prof.primary_metric || {};
            return (
              <div
                key={agentId}
                style={{
                  background: '#0D1526',
                  padding: '16px 18px',
                  borderRadius: '10px',
                  border: '1px solid rgba(255, 255, 255, 0.08)',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '12px'
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <div>
                    <span className="badge badge-purple" style={{ fontSize: '0.6rem', marginBottom: '4px' }}>
                      Stage: {prof.stage}
                    </span>
                    <h4 style={{ fontSize: '0.9rem', fontWeight: 700, color: '#F1F5F9', margin: '2px 0' }}>
                      {prof.agent_name}
                    </h4>
                    <p style={{ fontSize: '0.7rem', color: '#94A3B8', margin: 0, lineHeight: 1.3 }}>
                      {prof.description}
                    </p>
                  </div>
                  <StatusPill status={prof.evidence_status} />
                </div>

                <div style={{ background: 'rgba(255, 255, 255, 0.03)', padding: '12px', borderRadius: '8px', border: '1px solid rgba(255, 255, 255, 0.07)' }}>
                  <div style={{ color: '#94A3B8', fontSize: '0.65rem', textTransform: 'uppercase', marginBottom: '2px' }}>
                    Primary: {prof.primary_metric_label}
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                    <div style={{ fontSize: '1.25rem', fontWeight: 700, color: '#818CF8' }}>
                      {pct(pm.observed_rate)}
                    </div>
                    <div style={{ fontSize: '0.72rem', color: '#94A3B8' }}>
                      {pm.successes} successes / {pm.failures} failures (n={pm.sample_size})
                    </div>
                  </div>
                  <div style={{ fontSize: '0.68rem', color: '#94A3B8', marginTop: '5px', lineHeight: 1.4 }}>
                    Basis: {prof.measurement_basis}
                  </div>
                </div>

                {prof.secondary_metrics && Object.keys(prof.secondary_metrics).length > 0 && (
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                    {Object.entries(prof.secondary_metrics).map(([smKey, smVal]) => (
                      <div key={smKey} style={{ background: 'rgba(255, 255, 255, 0.03)', padding: '6px 10px', borderRadius: '6px', border: '1px solid rgba(255, 255, 255, 0.07)', flex: '1 1 120px' }}>
                        <div style={{ fontSize: '0.62rem', color: '#94A3B8', textTransform: 'uppercase' }}>
                          {smKey.replace(/_/g, ' ')}
                        </div>
                        <div style={{ fontSize: '0.85rem', fontWeight: 600, color: '#F1F5F9' }}>
                          {smVal.mean != null ? `${smVal.mean.toFixed(2)}${smVal.unit === 'seconds' ? 's' : ''}` : '—'}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

export default function AgentPerformanceView({
  currentRunRecord,
  onSelectRun
}) {
  const [section, setSection] = useState('hierarchical');
  const [hierarchicalData, setHierarchicalData] = useState(null);
  const [hierarchicalLoading, setHierarchicalLoading] = useState(false);
  const [hierarchicalError, setHierarchicalError] = useState(null);

  const [capabilityProfiles, setCapabilityProfiles] = useState(null);
  const [capabilityError, setCapabilityError] = useState(null);
  const [capabilityLoading, setCapabilityLoading] = useState(false);
  const [capabilityScope, setCapabilityScope] = useState('all');

  const hierarchicalRequestId = useRef(0);
  const capabilityRequestId = useRef(0);

  const loadHierarchical = () => {
    const id = ++hierarchicalRequestId.current;
    setHierarchicalLoading(true);
    setHierarchicalError(null);
    setHierarchicalData(null);
    return fetchHierarchicalProficiency(undefined, currentRunRecord?.run_id)
      .then((data) => {
        if (id === hierarchicalRequestId.current) setHierarchicalData(data);
      })
      .catch((e) => {
        if (id === hierarchicalRequestId.current) {
          setHierarchicalError(e.message);
          console.warn('Hierarchical proficiency error:', e);
        }
      })
      .finally(() => {
        if (id === hierarchicalRequestId.current) setHierarchicalLoading(false);
      });
  };

  const loadCapabilityProfiles = () => {
    const id = ++capabilityRequestId.current;
    setCapabilityLoading(true);
    setCapabilityError(null);
    setCapabilityProfiles(null);
    const runId = capabilityScope === 'selected' ? currentRunRecord?.run_id : undefined;
    if (capabilityScope === 'selected' && !runId) {
      setCapabilityProfiles({ profiles: [] });
      setCapabilityLoading(false);
      return;
    }
    fetchCapabilityProfiles({ runId })
      .then((data) => {
        if (id === capabilityRequestId.current) setCapabilityProfiles(data);
      })
      .catch((e) => {
        if (id === capabilityRequestId.current) {
          setCapabilityError(e.message);
          console.warn('Capability profiles error:', e);
        }
      })
      .finally(() => {
        if (id === capabilityRequestId.current) setCapabilityLoading(false);
      });
  };

  const handleRebuildHierarchical = async () => {
    setHierarchicalLoading(true);
    try {
      await rebuildHierarchicalProficiency();
      await loadHierarchical();
    } catch (e) {
      console.warn('Rebuild error:', e);
    } finally {
      setHierarchicalLoading(false);
    }
  };

  useEffect(() => {
    loadHierarchical();
    loadCapabilityProfiles();
  }, [currentRunRecord?.run_id, currentRunRecord?.evaluation?.created_at]);

  useEffect(() => {
    loadCapabilityProfiles();
  }, [capabilityScope]);

  const profilesByModel = (capabilityProfiles?.profiles || []).reduce((groups, profile) => {
    const model = profile.model_name || 'unknown_model';
    if (!groups.has(model)) groups.set(model, []);
    groups.get(model).push(profile);
    return groups;
  }, new Map());

  const handleExportJSON = () => {
    const payload = {
      run_id: currentRunRecord?.run_id || 'all_runs',
      exported_at: new Date().toISOString(),
      hierarchical_proficiency: hierarchicalData,
      capability_profiles: capabilityProfiles,
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `horizonlab-performance-${currentRunRecord?.run_id || 'all'}-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const sections = [
    ['hierarchical', 'Hierarchical Profiling'],
    ['capabilities', 'Capability Profiles'],
  ];

  return (
    <div className="agent-performance-view" style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Top Header Banner */}
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
            <span className="badge badge-purple">Agent Performance</span>
            {currentRunRecord?.run_id ? (
              <span className="badge badge-cyan" style={{ fontSize: '0.7rem' }}>
                Run: {currentRunRecord.run_id}
              </span>
            ) : (
              <span style={{ fontSize: '0.75rem', color: '#94A3B8' }}>All Observed Runs</span>
            )}
          </div>
          <h2 style={{ fontSize: '1.25rem', fontWeight: 700, color: '#F8FAFC', marginBottom: '4px' }}>
            Agent Performance
          </h2>
          <p style={{ fontSize: '0.85rem', color: '#94A3B8', margin: 0 }}>
            Analyze agent capabilities, execution proficiency, and performance across runs.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '10px' }}>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => {
              loadHierarchical();
              loadCapabilityProfiles();
            }}
            disabled={hierarchicalLoading || capabilityLoading}
            style={{ padding: '8px 14px', fontSize: '0.8rem' }}
          >
            <RefreshCw size={14} className={(hierarchicalLoading || capabilityLoading) ? 'animate-spin' : ''} />
            <span>Refresh measurements</span>
          </button>

          <button
            type="button"
            className="btn btn-primary"
            onClick={handleExportJSON}
            style={{ padding: '8px 16px', fontWeight: 600 }}
          >
            <Download size={14} />
            <span>Export performance JSON</span>
          </button>
        </div>
      </div>

      {/* Sub-tabs Navigation */}
      <nav aria-label="Agent Performance sections" style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        {sections.map(([id, label]) => (
          <button
            key={id}
            type="button"
            aria-pressed={section === id}
            className={`btn ${section === id ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setSection(id)}
          >
            {label}
          </button>
        ))}
      </nav>

      {/* Sub-tab 1: Hierarchical Profiling */}
      {section === 'hierarchical' && (
        <HierarchicalProfilingPanel
          data={hierarchicalData}
          loading={hierarchicalLoading}
          onRebuild={handleRebuildHierarchical}
          error={hierarchicalError}
          selectedRunId={currentRunRecord?.run_id}
        />
      )}

      {/* Sub-tab 2: Capability Profiles */}
      {section === 'capabilities' && (
        <div className="card-panel" style={{ padding: '20px', backgroundColor: '#0D1526', border: '1px solid rgba(255, 255, 255, 0.08)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
            <span style={{ color: capabilityError ? '#F87171' : '#94A3B8', fontSize: '0.78rem' }}>
              {capabilityLoading ? 'Loading observed capability data…' : capabilityError || ''}
            </span>
            <button type="button" className="btn btn-secondary btn-sm" onClick={loadCapabilityProfiles} disabled={capabilityLoading}>
              <RefreshCw size={12} className={capabilityLoading ? 'animate-spin' : ''} /><span>{capabilityError ? 'Retry' : 'Refresh data'}</span>
            </button>
          </div>
          <div style={{ marginBottom: '14px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
              <span className="badge badge-cyan">Feature 1</span>
              <h3 style={{ fontSize: '1rem', fontWeight: 700, color: '#F1F5F9', margin: 0 }}>
                Evidence-Grounded Capability Profiles
              </h3>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', margin: '8px 0' }}>
              {[
                { id: 'all', label: 'All recorded runs' },
                { id: 'selected', label: 'Selected run' },
              ].map(({ id, label }) => (
                <button
                  key={id}
                  type="button"
                  onClick={() => setCapabilityScope(id)}
                  style={{
                    background: capabilityScope === id ? 'var(--accent-primary, #6257D9)' : 'rgba(255, 255, 255, 0.05)',
                    color: capabilityScope === id ? '#FFFFFF' : '#94A3B8',
                    border: capabilityScope === id ? '1px solid #6366F1' : '1px solid rgba(255, 255, 255, 0.1)',
                    borderRadius: '6px',
                    padding: '4px 10px',
                    fontSize: '0.72rem',
                    fontWeight: 500,
                    cursor: 'pointer',
                  }}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          {!capabilityProfiles || capabilityProfiles.profiles?.length === 0 ? (
            <div style={{ color: '#94A3B8', fontSize: '0.8rem', fontStyle: 'italic', padding: '16px 0' }}>
              {capabilityScope === 'selected'
                ? currentRunRecord?.run_id
                  ? 'No capability observations have been recorded for this run yet.'
                  : 'Select a run to inspect its capability observations.'
                : 'No capability observations have been recorded for any run yet.'}
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              {[...profilesByModel.entries()].map(([modelName, profiles]) => (
                <div key={modelName} style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  <div style={{ color: '#cbd5e1', fontSize: '0.78rem', fontWeight: 700 }}>
                    Model: {modelName}
                  </div>
                  {profiles.filter(p => p.measurement_type === 'binary').map(p => (
                    <BinaryCapabilityCard key={`${p.model_name}-${p.capability}`} profile={p} />
                  ))}
                  {profiles.filter(p => p.measurement_type === 'continuous').map(p => (
                    <EfficiencyCard key={`${p.model_name}-${p.capability}`} profile={p} />
                  ))}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
