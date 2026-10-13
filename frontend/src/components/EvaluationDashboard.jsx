import React, { useState, useEffect, useRef } from 'react';
import {
  BarChart3,
  RefreshCw,
  Download,
  Layers,
  ShieldCheck,
  Activity,
  Info,
  Target,
} from 'lucide-react';
import {
  fetchEvaluationDashboard,
  fetchCapabilityProfiles,
  fetchRunRecovery,
  fetchHierarchicalProficiency,
  rebuildHierarchicalProficiency
} from '../services/api';

/* ──────────────────────────────────────────────────────────────────────────
   Small helpers
────────────────────────────────────────────────────────────────────────── */

function StatusPill({ status }) {
  const colors = {
    measured: { bg: 'rgba(52,211,153,0.12)', text: '#34d399', border: '#1a4a3a' },
    insufficient_evidence: { bg: 'rgba(251,191,36,0.12)', text: '#fbbf24', border: '#5a4200' },
  };
  const c = colors[status] || colors.insufficient_evidence;
  return (
    <span style={{
      fontSize: '0.65rem', padding: '2px 7px', borderRadius: '6px',
      background: c.bg, color: c.text, border: `1px solid ${c.border}`,
      fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em'
    }}>
      {status === 'insufficient_evidence' ? 'no data yet' : status}
    </span>
  );
}

function MetricCell({ label, value, color = '#f8fafc', sub, badge }) {
  return (
    <div style={{ background: '#0c121d', padding: '14px 16px', borderRadius: '10px', border: '1px solid #1e293b' }}>
      <div style={{ color: '#64748b', fontSize: '0.68rem', textTransform: 'uppercase', marginBottom: '4px' }}>{label}</div>
      <div style={{ color, fontSize: '1.3rem', fontWeight: 700 }}>{value}</div>
      {sub && <div style={{ color: '#64748b', fontSize: '0.7rem', marginTop: '4px' }}>{sub}</div>}
      {badge && <div style={{ marginTop: '6px' }}>{badge}</div>}
    </div>
  );
}

function formatTestPassRate(passed, total) {
  if (!Number.isFinite(total) || total <= 0 || !Number.isFinite(passed)) return '—';
  return `${((passed / total) * 100).toFixed(1)}%`;
}

function formatDuration(seconds) {
  if (!Number.isFinite(seconds) || seconds < 0) return '—';
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  if (seconds < 3600) return `${(seconds / 60).toFixed(1)}m`;
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  return minutes > 0 ? `${hours}h ${minutes}m` : `${hours}h`;
}

/* ──────────────────────────────────────────────────────────────────────────
   Binary capability card
────────────────────────────────────────────────────────────────────────── */
function BinaryCapabilityCard({ profile }) {
  const capColors = {
    reliability: '#34d399',
    coding: '#38bdf8',
    recovery: '#a78bfa',
    planning: '#fbbf24',
    debugging: '#fb923c',
    orchestrator: '#34d399',
    requirement_analyst: '#f472b6',
    planner: '#fbbf24',
    coder: '#38bdf8',
    test_runner: '#22d3ee',
    debugger: '#fb923c',
    verifier: '#a78bfa',
  };
  const color = capColors[profile.capability] || '#94a3b8';
  const pct = (v) => v != null ? `${Math.round(v * 100)}%` : '—';
  const outcomeLabel = profile.capability === 'coding'
    ? 'Completed test suites (all passed / at least one failed)'
    : 'Observed outcomes (successful / unsuccessful)';

  return (
    <div style={{
      background: '#0c121d', padding: '16px 18px', borderRadius: '10px',
      border: `1px solid #1e293b`, borderLeft: `3px solid ${color}`
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
        <div>
          <div style={{ color, fontWeight: 700, textTransform: 'capitalize', fontSize: '0.95rem' }}>
            {profile.display_name || profile.capability.replace(/_/g, ' ')}
          </div>
          <div style={{ color: '#475569', fontSize: '0.7rem', marginTop: '1px' }}>
            {profile.model_name}
          </div>
        </div>
        <StatusPill status={profile.evidence_status} />
      </div>

      {profile.evidence_status === 'insufficient_evidence' ? (
        <div style={{ color: '#64748b', fontSize: '0.78rem', marginTop: '8px', fontStyle: 'italic' }}>
          No valid recorded outcomes are available for this metric.
        </div>
      ) : (
        <>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', marginTop: '8px' }}>
            <div>
              <div style={{ color: '#64748b', fontSize: '0.65rem', textTransform: 'uppercase' }}>Observed rate</div>
              <div style={{ color: '#fbbf24', fontWeight: 700, fontSize: '1.1rem' }}>
                {pct(profile.observed_rate)}
              </div>
              <div style={{ color: '#475569', fontSize: '0.65rem' }}>
                {profile.successes}S / {profile.failures}F (n={profile.sample_size})
              </div>
            </div>
            <div>
              <div style={{ color: '#64748b', fontSize: '0.65rem', textTransform: 'uppercase' }}>
                {profile.metric_label || outcomeLabel}
              </div>
              <div style={{ color, fontWeight: 700, fontSize: '1.1rem' }}>
                {profile.successes} / {profile.failures}
              </div>
              <div style={{ color: '#475569', fontSize: '0.65rem' }}>n = {profile.sample_size} measured outcomes</div>
            </div>
          </div>
        </>
      )}
      {profile.measurement_basis && (
        <div style={{ color: '#64748b', fontSize: '0.67rem', marginTop: '8px' }}>
          Basis: {profile.measurement_basis}
        </div>
      )}
      {profile.note && (
        <div style={{ color: '#475569', fontSize: '0.67rem', marginTop: '8px', borderTop: '1px solid #1e293b', paddingTop: '6px' }}>
          {profile.note}
        </div>
      )}
    </div>
  );
}

/* ──────────────────────────────────────────────────────────────────────────
   Efficiency (continuous) card
────────────────────────────────────────────────────────────────────────── */
function EfficiencyCard({ profile }) {
  const fmt = formatDuration;
  return (
    <div style={{
      background: '#0c121d', padding: '16px 18px', borderRadius: '10px',
      border: '1px solid #1e293b', borderLeft: '3px solid #a78bfa'
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '10px' }}>
        <div>
          <div style={{ color: '#a78bfa', fontWeight: 700, fontSize: '0.95rem' }}>efficiency</div>
          <div style={{ color: '#475569', fontSize: '0.7rem' }}>Task duration (continuous)</div>
        </div>
        <StatusPill status={profile.evidence_status || (profile.n > 0 ? 'measured' : 'insufficient_evidence')} />
      </div>
      {profile.n === 0 ? (
        <div style={{ color: '#64748b', fontSize: '0.78rem', fontStyle: 'italic' }}>
          No verifiable task durations recorded yet.
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '10px' }}>
          {[
            { label: 'Mean', value: fmt(profile.mean) },
            { label: 'Min', value: fmt(profile.min) },
            { label: 'Max', value: fmt(profile.max) },
            { label: 'Std Dev', value: fmt(profile.stdev) },
          ].map(({ label, value }) => (
            <div key={label}>
              <div style={{ color: '#64748b', fontSize: '0.65rem', textTransform: 'uppercase' }}>{label}</div>
              <div style={{ color: '#a78bfa', fontWeight: 700, fontSize: '1.1rem' }}>{value}</div>
            </div>
          ))}
        </div>
      )}
      <div style={{ color: '#475569', fontSize: '0.67rem', marginTop: '8px', borderTop: '1px solid #1e293b', paddingTop: '6px' }}>
        {profile.n > 0
          ? `Based on ${profile.n} timestamp-verified run duration(s). ${profile.note || ''}`
          : profile.note || 'Unverifiable legacy durations are omitted.'}
      </div>
    </div>
  );
}

/* ──────────────────────────────────────────────────────────────────────────
   Recovery panel
────────────────────────────────────────────────────────────────────────── */
function RecoveryPanel({ recovery }) {
  if (!recovery || recovery.evidence_status === 'insufficient_evidence'
    || (recovery.evidence_status === 'no_recovery_needed' && !recovery.total_episodes)) {
    return (
      <div style={{ color: '#64748b', fontSize: '0.8rem', fontStyle: 'italic', padding: '12px 0' }}>
        {recovery?.note || 'No recovery episodes recorded for this run.'}
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '12px' }}>
        <MetricCell
          label={recovery.data_source === 'legacy_recovery_run_stats' || recovery.data_source === 'legacy_recovery_attempts'
            ? 'Recovery Attempts'
            : 'Total Episodes'}
          value={recovery.total_episodes}
          color="#f8fafc"
          sub={`data source: ${recovery.data_source}`}
        />
        <MetricCell
          label="Resolved"
          value={recovery.resolved_episodes}
          color="#34d399"
          sub={recovery.data_source === 'legacy_recovery_attempts'
            ? 'attempts marked resolved by recorded re-tests; not independently verified'
            : 'original failure fixed + regressions passed'}
        />
        <MetricCell
          label="Recovery Rate"
          value={recovery.recovery_rate_percent != null ? `${recovery.recovery_rate_percent}%` : '—'}
          color="#34d399"
          badge={<StatusPill status="measured" />}
        />
        <MetricCell
          label={recovery.data_source === 'legacy_recovery_run_stats' ? 'Recovery Time' : 'Mean Duration'}
          value={recovery.mean_recovery_duration_seconds != null
            ? formatDuration(recovery.mean_recovery_duration_seconds)
            : '—'}
          color="#38bdf8"
          sub={recovery.data_source === 'legacy_recovery_run_stats' ? 'total run recovery time' : 'per episode'}
        />
        <MetricCell
          label="Total Extra Steps"
          value={recovery.total_extra_steps ?? '—'}
          color="#a78bfa"
          sub="recovery overhead"
        />
      </div>

      {/* Failure breakdown */}
      {recovery.failure_type_breakdown && Object.keys(recovery.failure_type_breakdown).length > 0 && (
        <div style={{ background: '#0c121d', padding: '12px 14px', borderRadius: '8px', border: '1px solid #1e293b' }}>
          <div style={{ color: '#64748b', fontSize: '0.7rem', textTransform: 'uppercase', marginBottom: '8px' }}>
            Failure type breakdown
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px' }}>
            {Object.entries(recovery.failure_type_breakdown).map(([ft, data]) => (
              <div key={ft} style={{
                background: '#0f1928', border: '1px solid #1e293b',
                borderRadius: '6px', padding: '8px 12px', minWidth: '140px'
              }}>
                <div style={{ color: '#94a3b8', fontWeight: 600, fontSize: '0.78rem' }}>{ft}</div>
                <div style={{ color: '#f8fafc', fontSize: '0.85rem', marginTop: '2px' }}>
                  {data.resolved}/{data.attempts} resolved
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Individual episodes */}
      {recovery.episodes && recovery.episodes.length > 0 && (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.78rem' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid #1e293b', color: '#64748b' }}>
                {(recovery.data_source === 'legacy_recovery_attempts'
                  ? ['Attempt', 'Failure', 'Duration', 'Extra Steps', 'Outcome', 'Human?']
                  : ['Episode', 'Failure Type', 'Duration', 'Extra Steps', 'Outcome', 'Human?']).map(h => (
                  <th key={h} style={{ padding: '8px 10px', textAlign: 'left' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {recovery.episodes.map((ep) => (
                <tr key={ep.episode_id} style={{ borderBottom: '1px solid #0f1928' }}>
                  <td style={{ padding: '8px 10px', color: '#64748b', fontFamily: 'monospace', fontSize: '0.7rem' }}>
                    {recovery.data_source === 'legacy_recovery_attempts'
                      ? `#${ep.attempt_number} ${ep.episode_id}`
                      : ep.episode_id}
                  </td>
                  <td style={{ padding: '8px 10px', color: '#94a3b8' }}>{ep.failure_type}</td>
                  <td style={{ padding: '8px 10px', color: '#38bdf8' }}>
                    {ep.recovery_duration_seconds != null ? `${ep.recovery_duration_seconds.toFixed(1)}s` : '—'}
                  </td>
                  <td style={{ padding: '8px 10px', color: '#a78bfa' }}>{ep.extra_steps}</td>
                  <td style={{ padding: '8px 10px' }}>
                    <span style={{
                      color: ep.verified_success === true
                        ? '#34d399'
                        : ep.verified_success === false ? '#f87171' : '#fbbf24',
                      fontWeight: 700, fontSize: '0.72rem'
                    }}>
                      {ep.final_verified_outcome}
                    </span>
                  </td>
                  <td style={{ padding: '8px 10px', color: '#64748b' }}>
                    {ep.human_intervention ? '✓' : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {recovery.note && (
        <div style={{ color: '#64748b', fontSize: '0.72rem' }}>{recovery.note}</div>
      )}
    </div>
  );
}

/* ──────────────────────────────────────────────────────────────────────────
   Hierarchical Profiling Panel (7 Agents + System Macro Profile)
────────────────────────────────────────────────────────────────────────── */
function HierarchicalProfilingPanel({ data, loading, onRebuild, error, selectedRunId }) {
  if (loading && !data) {
    return (
      <div style={{ color: '#64748b', fontSize: '0.85rem', padding: '32px', textAlign: 'center' }}>
        <RefreshCw size={20} className="animate-spin" style={{ margin: '0 auto 8px', display: 'block' }} />
        Loading observed agent outcome rates...
      </div>
    );
  }

  if (!data) {
    return (
      <div style={{ color: '#64748b', fontSize: '0.82rem', fontStyle: 'italic', padding: '16px 0' }}>
        {error || 'No observed profile data is available for this run yet.'}
      </div>
    );
  }

  const { system_profile, agent_profiles = {}, attribution_matrix = {}, total_runs_analyzed = 0 } = data;
  const pct = (v) => v != null ? `${Math.round(v * 100)}%` : '—';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Level 2: Macro End-to-End System Profile */}
      <div className="card-panel" style={{
        padding: '20px 24px',
        background: 'linear-gradient(135deg, #0e1726 0%, #0a0f1d 100%)',
        border: '1px solid #1e3a5f',
        borderRadius: '12px'
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px', flexWrap: 'wrap', gap: '10px' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
              <span className="badge badge-purple" style={{ fontSize: '0.65rem' }}>Level 2: Macro System Profile</span>
              <span style={{ fontSize: '0.72rem', color: '#64748b' }}>{selectedRunId ? `Selected run: ${selectedRunId}` : 'All observed runs'}</span>
            </div>
            <h3 style={{ fontSize: '1.15rem', fontWeight: 700, color: '#f8fafc', margin: 0 }}>
              End-to-End Verified System Proficiency
            </h3>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <StatusPill status={system_profile?.evidence_status || 'insufficient_evidence'} />
            <button
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
            color="#f8fafc"
            sub="empirical runs in SQLite"
          />
          <MetricCell
            label="Observed Verified Run Rate"
            value={pct(system_profile?.verified_success_rate?.observed_rate)}
            color="#34d399"
            sub={`${system_profile?.verified_success_rate?.successes ?? 0} passed / ${system_profile?.verified_success_rate?.failures ?? 0} failed (n=${system_profile?.verified_success_rate?.sample_size ?? 0})`}
          />
          <MetricCell
            label="Mean Pipeline Latency"
            value={system_profile?.duration_summary?.mean != null ? `${system_profile.duration_summary.mean.toFixed(1)}s` : '—'}
            color="#38bdf8"
            sub={system_profile?.duration_summary?.n ? `across ${system_profile.duration_summary.n} completed executions` : 'no duration data'}
          />
          <MetricCell
            label="Failures Identified"
            value={attribution_matrix.total_failures_observed || 0}
            color={attribution_matrix.total_failures_observed > 0 ? '#fbbf24' : '#34d399'}
            sub="from captured execution events"
          />
        </div>

      </div>

      {/* Failure & Recovery Attribution Matrix */}
      <div className="card-panel" style={{ padding: '20px', borderRadius: '12px' }}>
        <h3 style={{ fontSize: '0.95rem', fontWeight: 600, color: '#f1f5f9', display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
          <ShieldCheck size={16} color="#38bdf8" />
          <span>Failure & Recovery Attribution Matrix</span>
        </h3>
        <p style={{ fontSize: '0.75rem', color: '#94a3b8', marginBottom: '14px' }}>
          Rates and counts are calculated from captured files, test outcomes, recovery attempts, and verification records. Missing evidence is shown as unavailable.
        </p>

        <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: '16px' }}>
          {/* Root causes */}
          <div style={{ background: '#0c121d', padding: '14px', borderRadius: '8px', border: '1px solid #1e293b' }}>
            <div style={{ color: '#64748b', fontSize: '0.7rem', textTransform: 'uppercase', marginBottom: '10px', fontWeight: 600 }}>
              Root-Cause Failure Distribution
            </div>
            {Object.keys(attribution_matrix.failure_attributions || {}).length === 0 ? (
              <div style={{ color: '#34d399', fontSize: '0.78rem', padding: '8px 0' }}>
                No failure events were captured for this view.
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {Object.entries(attribution_matrix.failure_attributions).map(([cause, cnt]) => (
                  <div key={cause} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.78rem' }}>
                    <span style={{ color: '#cbd5e1', fontFamily: 'monospace' }}>{cause}</span>
                    <span className="badge badge-amber" style={{ fontSize: '0.65rem' }}>{cnt} run(s)</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Recovery outcomes */}
          <div style={{ background: '#0c121d', padding: '14px', borderRadius: '8px', border: '1px solid #1e293b' }}>
            <div style={{ color: '#64748b', fontSize: '0.7rem', textTransform: 'uppercase', marginBottom: '10px', fontWeight: 600 }}>
              Recovery Resolution Outcomes
            </div>
            {Object.keys(attribution_matrix.recovery_attributions || {}).length === 0 ? (
              <div style={{ color: '#64748b', fontSize: '0.78rem', fontStyle: 'italic', padding: '8px 0' }}>
                No recovery episodes recorded.
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {Object.entries(attribution_matrix.recovery_attributions).map(([outcome, cnt]) => (
                  <div key={outcome} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.78rem' }}>
                    <span style={{ color: '#cbd5e1', fontFamily: 'monospace' }}>{outcome}</span>
                    <span className={`badge ${outcome.includes('recovered') ? 'badge-emerald' : outcome.includes('clean') || outcome.includes('no_recovery') ? 'badge-purple' : 'badge-rose'}`} style={{ fontSize: '0.65rem' }}>
                      {cnt} episode(s)
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Level 1: Micro Profiles for All 7 Actual Agents */}
      <div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
          <span className="badge badge-cyan" style={{ fontSize: '0.65rem' }}>Level 1: Micro Component Profiles</span>
          <h3 style={{ fontSize: '1rem', fontWeight: 700, color: '#f8fafc', margin: 0 }}>
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
                  background: '#0c121d',
                  padding: '16px 18px',
                  borderRadius: '10px',
                  border: '1px solid #1e293b',
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
                    <h4 style={{ fontSize: '0.9rem', fontWeight: 700, color: '#f1f5f9', margin: '2px 0' }}>
                      {prof.agent_name}
                    </h4>
                    <p style={{ fontSize: '0.7rem', color: '#64748b', margin: 0, lineHeight: 1.3 }}>
                      {prof.description}
                    </p>
                  </div>
                  <StatusPill status={prof.evidence_status} />
                </div>

                {/* Primary Metric */}
                <div style={{ background: '#080d16', padding: '12px', borderRadius: '8px', border: '1px solid #162032' }}>
                  <div style={{ color: '#64748b', fontSize: '0.65rem', textTransform: 'uppercase', marginBottom: '2px' }}>
                    Primary: {prof.primary_metric_label}
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                    <div style={{ fontSize: '1.25rem', fontWeight: 700, color: '#38bdf8' }}>
                      {pct(pm.observed_rate)}
                    </div>
                    <div style={{ fontSize: '0.72rem', color: '#94a3b8' }}>
                        {pm.successes} successes / {pm.failures} failures (n={pm.sample_size})
                    </div>
                  </div>
                    <div style={{ fontSize: '0.68rem', color: '#64748b', marginTop: '5px', lineHeight: 1.4 }}>
                      Basis: {prof.measurement_basis}
                    </div>
                </div>

                {/* Secondary Operational Metrics */}
                {prof.secondary_metrics && Object.keys(prof.secondary_metrics).length > 0 && (
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                    {Object.entries(prof.secondary_metrics).map(([smKey, smVal]) => (
                      <div key={smKey} style={{ background: '#101626', padding: '6px 10px', borderRadius: '6px', border: '1px solid #1e293b', flex: '1 1 120px' }}>
                        <div style={{ fontSize: '0.62rem', color: '#64748b', textTransform: 'uppercase' }}>
                          {smKey.replace(/_/g, ' ')}
                        </div>
                        <div style={{ fontSize: '0.85rem', fontWeight: 600, color: '#cbd5e1' }}>
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

/* ──────────────────────────────────────────────────────────────────────────
   Main dashboard
────────────────────────────────────────────────────────────────────────── */
export default function EvaluationDashboard({ currentRunRecord, onSelectRun }) {
  const [dashboardData, setDashboardData] = useState(null);
  const [capabilityProfiles, setCapabilityProfiles] = useState(null);
  const [capabilityError, setCapabilityError] = useState(null);
  const [capabilityLoading, setCapabilityLoading] = useState(false);
  const [recoveryData, setRecoveryData] = useState(null);
  const [hierarchicalData, setHierarchicalData] = useState(null);
  const [hierarchicalLoading, setHierarchicalLoading] = useState(false);
  const [hierarchicalError, setHierarchicalError] = useState(null);
  const [activeSection, setActiveSection] = useState('hierarchical');
  const [capabilityScope, setCapabilityScope] = useState('all');
  const hierarchicalRequestId = useRef(0);
  const capabilityRequestId = useRef(0);

  const loadDashboard = () => {
    fetchEvaluationDashboard()
      .then(setDashboardData)
      .catch((e) => console.warn('Dashboard fetch error:', e))
  };

  const loadHierarchical = () => {
    const requestId = ++hierarchicalRequestId.current;
    setHierarchicalLoading(true);
    setHierarchicalError(null);
    setHierarchicalData(null);
    return fetchHierarchicalProficiency(undefined, currentRunRecord?.run_id)
      .then((data) => {
        if (requestId === hierarchicalRequestId.current) setHierarchicalData(data);
      })
      .catch((e) => {
        if (requestId === hierarchicalRequestId.current) {
          setHierarchicalError(e.message);
          console.warn('Hierarchical proficiency error:', e);
        }
      })
      .finally(() => {
        if (requestId === hierarchicalRequestId.current) setHierarchicalLoading(false);
      });
  };

  const loadCapabilityProfiles = () => {
    const requestId = ++capabilityRequestId.current;
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
        if (requestId === capabilityRequestId.current) setCapabilityProfiles(data);
      })
      .catch((e) => {
        if (requestId === capabilityRequestId.current) {
          setCapabilityError(e.message);
          console.warn('Capability profiles error:', e);
        }
      })
      .finally(() => {
        if (requestId === capabilityRequestId.current) setCapabilityLoading(false);
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

  const refreshDashboardData = () => {
    loadDashboard();
    loadHierarchical();
    loadCapabilityProfiles();
  };

  useEffect(() => {
    loadDashboard();
  }, []);

  useEffect(() => {
    loadHierarchical();
    loadCapabilityProfiles();
  }, [currentRunRecord?.run_id, capabilityScope]);

  useEffect(() => {
    if (!currentRunRecord?.run_id) {
      setRecoveryData(null);
      return;
    }
    setRecoveryData(null);
    let cancelled = false;
    fetchRunRecovery(currentRunRecord.run_id)
      .then((data) => { if (!cancelled) setRecoveryData(data); })
      .catch((e) => { if (!cancelled) { console.warn('Recovery data error:', e); setRecoveryData(null); } });
    return () => { cancelled = true; };
  }, [currentRunRecord?.run_id]);

  const currentEval = currentRunRecord?.evaluation;
  const aggregate = dashboardData?.aggregate_stats || {};
  const recentEvals = dashboardData?.recent_evaluations || [];

  const profilesByModel = (capabilityProfiles?.profiles || []).reduce((groups, profile) => {
    const modelProfiles = groups.get(profile.model_name) || [];
    modelProfiles.push(profile);
    groups.set(profile.model_name, modelProfiles);
    return groups;
  }, new Map());

  const handleExportJSON = () => {
    const payload = {
      run: currentRunRecord,
      hierarchical_proficiency: hierarchicalData,
      capability_profiles: capabilityProfiles,
      recovery: recoveryData,
    };
    const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(payload, null, 2));
    const a = document.createElement('a');
    a.setAttribute('href', dataStr);
    a.setAttribute('download', `agenteval_run_${currentRunRecord?.run_id || 'export'}.json`);
    document.body.appendChild(a);
    a.click();
    a.remove();
  };

  const sections = [
    { id: 'hierarchical', label: 'Hierarchical Profiling', icon: <Layers size={14} /> },
    { id: 'capabilities', label: 'Capability Profiles', icon: <Target size={14} /> },
    { id: 'recovery', label: 'Recovery Episodes', icon: <RefreshCw size={14} /> },
    { id: 'benchmarks', label: 'Run Benchmarks', icon: <BarChart3 size={14} /> },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Top banner */}
      <div className="card-panel" style={{
        padding: '20px 24px',
        background: 'linear-gradient(135deg, #101626 0%, #0d121f 100%)',
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        flexWrap: 'wrap', gap: '16px'
      }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
            <span className="badge badge-cyan">Stage 7: Evaluation Dashboard</span>
            <span style={{ fontSize: '0.75rem', color: '#64748b' }}>Evidence-Grounded Analytics</span>
          </div>
          <h2 style={{ fontSize: '1.25rem', fontWeight: 700, color: '#f8fafc', marginBottom: '4px' }}>
            Evidence-Grounded Capability Profiling System
          </h2>
          <p style={{ fontSize: '0.82rem', color: '#94a3b8' }}>
            Percentages use captured outcomes. Values are unavailable when there is no measurable evidence.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '10px' }}>
          <button className="btn btn-secondary" onClick={refreshDashboardData} style={{ padding: '8px 14px', fontSize: '0.8rem' }}>
            <RefreshCw size={14} /><span>Refresh</span>
          </button>
          <button className="btn btn-primary" onClick={handleExportJSON} style={{ padding: '8px 16px', fontWeight: 600 }}>
            <Download size={14} /><span>Export JSON</span>
          </button>
        </div>
      </div>

      {/* Current run telemetry */}
      {currentEval && (
        <div>
          <div style={{ fontSize: '0.78rem', fontWeight: 600, color: '#64748b', textTransform: 'uppercase', marginBottom: '8px' }}>
            Current Run: {currentRunRecord?.run_id}
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '12px' }}>
            <MetricCell
              label="Automated Test Pass Rate"
              value={formatTestPassRate(currentEval.tests_passed, currentEval.tests_total)}
              color="#34d399"
              sub={`${currentEval.tests_passed}/${currentEval.tests_total} captured tests`}
            />
            <MetricCell label="Execution Time" value={formatDuration(currentEval.execution_time_seconds)} color="#38bdf8" />
            <MetricCell label="Total Log Events" value={currentEval.total_tool_calls} color="#a78bfa" />
            <MetricCell label="Recovery Attempts" value={currentEval.recovery_attempts_count} color="#fbbf24" />
            <MetricCell label="Tests Passing" value={`${currentEval.tests_passed}/${currentEval.tests_total}`} color="#34d399" />
            <MetricCell
              label="AST-Valid Changed Files"
              value={`${(currentRunRecord.code_changes || []).filter((change) => change.ast_valid).length}/${(currentRunRecord.code_changes || []).length}`}
              color="#38bdf8"
              sub="captured syntax checks"
            />
          </div>
        </div>
      )}

      {/* Section nav */}
      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
        {sections.map(s => (
          <button
            key={s.id}
            type="button"
            role="tab"
            aria-selected={activeSection === s.id}
            onClick={() => setActiveSection(s.id)}
            style={{
              display: 'flex', alignItems: 'center', gap: '6px',
              padding: '7px 14px', borderRadius: '8px', fontSize: '0.8rem',
              fontWeight: 600, cursor: 'pointer', border: 'none',
              background: activeSection === s.id ? '#38bdf8' : '#0f1928',
              color: activeSection === s.id ? '#0f172a' : '#94a3b8',
              transition: 'all 0.15s ease',
            }}
          >
            {s.icon}{s.label}
          </button>
        ))}
      </div>

      {/* === HIERARCHICAL PROFILING === */}
      {activeSection === 'hierarchical' && (
        <HierarchicalProfilingPanel
          data={hierarchicalData}
          loading={hierarchicalLoading}
          onRebuild={handleRebuildHierarchical}
          error={hierarchicalError}
          selectedRunId={currentRunRecord?.run_id}
        />
      )}

      {/* === CAPABILITIES === */}
      {activeSection === 'capabilities' && (
        <div className="card-panel" style={{ padding: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
            <span style={{ color: capabilityError ? '#fb7185' : '#94a3b8', fontSize: '0.78rem' }}>{capabilityLoading ? 'Loading observed capability data…' : capabilityError || ''}</span>
            <button type="button" className="btn btn-secondary btn-sm" onClick={loadCapabilityProfiles} disabled={capabilityLoading}>
              <RefreshCw size={12} /><span>{capabilityError ? 'Retry' : 'Refresh data'}</span>
            </button>
          </div>
          <div style={{ marginBottom: '14px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
              <span className="badge badge-cyan">Feature 1</span>
              <h3 style={{ fontSize: '1rem', fontWeight: 700, color: '#f8fafc', margin: 0 }}>
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
                  className={`btn ${capabilityScope === id ? 'btn-primary' : 'btn-secondary'} btn-sm`}
                  disabled={id === 'selected' && !currentRunRecord?.run_id}
                  aria-pressed={capabilityScope === id}
                  onClick={() => setCapabilityScope(id)}
                >
                  {label}
                </button>
              ))}
              <span style={{ color: '#64748b', fontSize: '0.7rem' }}>
                {capabilityScope === 'selected'
                  ? `Run: ${currentRunRecord?.run_id || 'none selected'}`
                  : 'Aggregated from persisted run evidence'}
              </span>
            </div>
            <p style={{ fontSize: '0.78rem', color: '#94a3b8', margin: 0 }}>
              Percentages are raw observed successes divided by the measured denominator shown on each card; different agents use their recorded output units (runs, files, tests, recovery attempts, or constraints). No outcome is inferred when evidence is missing. Efficiency uses recorded task durations.
              <strong style={{ color: '#fbbf24' }}> No weighted aggregate score is produced.</strong>
            </p>
            {capabilityProfiles?.note && (
              <div style={{ marginTop: '8px', padding: '8px 12px', background: '#0c121d', borderRadius: '6px', border: '1px solid #1e293b', color: '#64748b', fontSize: '0.7rem' }}>
                <Info size={12} style={{ display: 'inline', marginRight: '5px' }} />
                {capabilityProfiles.note}
              </div>
            )}
          </div>

          {capabilityLoading ? (
            <div style={{ color: '#64748b', fontSize: '0.82rem', fontStyle: 'italic', padding: '16px 0' }}>
              Loading capability observations…
            </div>
          ) : profilesByModel.size === 0 ? (
            <div style={{ color: '#64748b', fontSize: '0.82rem', fontStyle: 'italic', padding: '16px 0' }}>
              {currentRunRecord?.run_id
                ? capabilityScope === 'selected'
                  ? 'No capability observations were recorded for this run. Switch to all recorded runs to inspect available evidence.'
                  : 'No capability observations have been recorded for any run yet.'
                : capabilityScope === 'selected'
                  ? 'Select a run to inspect its capability observations.'
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

      {/* === RECOVERY === */}
      {activeSection === 'recovery' && (
        <div className="card-panel" style={{ padding: '20px' }}>
          <div style={{ marginBottom: '14px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
              <span className="badge badge-cyan">Feature 2</span>
              <h3 style={{ fontSize: '1rem', fontWeight: 700, color: '#f8fafc', margin: 0 }}>
                Trace-Based Recovery Analysis
              </h3>
            </div>
            <p style={{ fontSize: '0.78rem', color: '#94a3b8', margin: 0 }}>
              Each failure/recovery pair is a distinct episode. A recovery is marked successful only
              when the re-test actually passes — never inferred from debugging stage completion.
            </p>
          </div>

          {!currentRunRecord?.run_id ? (
            <div style={{ color: '#64748b', fontSize: '0.8rem', fontStyle: 'italic' }}>
              Select a completed run to inspect its recovery episodes.
            </div>
          ) : (
            <RecoveryPanel recovery={recoveryData} />
          )}
        </div>
      )}

      {/* === BENCHMARKS === */}
      {activeSection === 'benchmarks' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {/* Aggregates */}
          <div className="card-panel" style={{ padding: '20px' }}>
            <h3 style={{ fontSize: '0.95rem', fontWeight: 600, color: '#f1f5f9', display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '14px' }}>
              <Activity size={16} color="#38bdf8" />
              Platform Aggregates (Across All Persistent Runs)
            </h3>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '12px' }}>
              <MetricCell label="Total Evaluated Runs" value={aggregate.total_runs || recentEvals.length} color="#f8fafc" />
              <MetricCell
                label="Avg Test Pass Rate"
                value={aggregate.avg_test_pass_rate == null ? '—' : `${aggregate.avg_test_pass_rate.toFixed(1)}%`}
                color="#34d399"
                sub="mean of runs with captured test counts"
              />
              <MetricCell label="Avg Execution Time" value={formatDuration(aggregate.avg_duration)} color="#38bdf8" />
              <MetricCell label="Total Recoveries" value={aggregate.total_recoveries || 0} color="#fbbf24" />
            </div>
          </div>

          {/* Historical table */}
          <div className="card-panel" style={{ padding: '20px' }}>
            <h3 style={{ fontSize: '0.95rem', fontWeight: 600, color: '#f1f5f9', display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '14px' }}>
              <BarChart3 size={16} color="#38bdf8" />
              Historical Run Benchmark Table
            </h3>
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.78rem', textAlign: 'left' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid #1e293b', color: '#64748b' }}>
                    {['Run & Task', 'Test Pass Rate', 'Duration', 'Log Events', 'Recoveries', 'Tests', 'Action'].map(h => (
                      <th key={h} style={{ padding: '10px 12px' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {recentEvals.length > 0 ? recentEvals.map((r, idx) => (
                    <tr key={r.run_id || idx} style={{
                      borderBottom: '1px solid #162032',
                      background: currentRunRecord?.run_id === r.run_id ? 'rgba(56,189,248,0.05)' : 'transparent'
                    }}>
                      <td style={{ padding: '10px 12px' }}>
                        <div style={{ fontWeight: 600, color: '#f8fafc' }}>{(r.title || 'Coding Task').slice(0, 38)}</div>
                        <span style={{ fontSize: '0.67rem', fontFamily: 'monospace', color: '#64748b' }}>{r.run_id}</span>
                      </td>
                      <td style={{ padding: '10px 12px' }}>
                        <span className="badge badge-emerald" style={{ fontSize: '0.65rem' }}>
                          {formatTestPassRate(r.tests_passed, r.tests_total)}
                        </span>
                      </td>
                      <td
                        title={r.duration_status === 'reconstructed'
                          ? 'Duration reconstructed from this run’s recorded start and verification timestamps.'
                          : r.duration_status === 'unverified_legacy'
                            ? 'No matching execution start and completion timestamps were recorded for this legacy duration.'
                            : undefined}
                        style={{ padding: '10px 12px', color: '#38bdf8', fontFamily: 'monospace' }}
                      >
                        {r.duration_status === 'unverified_legacy'
                          ? 'Unverified'
                          : formatDuration(r.execution_time_seconds)}
                      </td>
                      <td style={{ padding: '10px 12px', color: '#a78bfa' }}>{r.total_tool_calls || '—'}</td>
                      <td style={{ padding: '10px 12px', color: '#fbbf24' }}>{r.recovery_attempts_count || 0}</td>
                      <td style={{ padding: '10px 12px', color: '#34d399' }}>
                        {r.tests_total > 0 ? `${r.tests_passed}/${r.tests_total}` : '—'}
                      </td>
                      <td style={{ padding: '10px 12px' }}>
                        <button onClick={() => onSelectRun && onSelectRun(r.run_id)}
                          className="btn btn-secondary btn-sm"
                          style={{ fontSize: '0.7rem', padding: '3px 8px' }}>
                          Load Run
                        </button>
                      </td>
                    </tr>
                  )) : (
                    <tr>
                      <td colSpan={7} style={{ padding: '24px', textAlign: 'center', color: '#64748b' }}>
                        No evaluations recorded yet. Run a workflow to populate benchmarks.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
