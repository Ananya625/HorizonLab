import React from 'react';
import { 
  ShieldCheck, 
  CheckCircle2, 
  XCircle, 
  AlertTriangle, 
  ArrowRight, 
  FileCheck2, 
  Lock, 
  Sparkles, 
  BarChart3,
  Check
} from 'lucide-react';

export default function VerificationView({
  verification,
  onNavigateToEvaluations
}) {
  if (!verification) {
    return (
      <div className="card-panel" style={{ padding: '40px', textAlign: 'center' }}>
        <ShieldCheck size={36} color="#64748b" style={{ margin: '0 auto 12px' }} />
        <h3 style={{ fontSize: '1.1rem', color: '#f1f5f9', marginBottom: '8px' }}>No Verification Report Available</h3>
        <p style={{ fontSize: '0.85rem', color: '#94a3b8', maxWidth: '500px', margin: '0 auto 16px' }}>
          Execute the test and verification stages to capture test outcomes. Acceptance criteria are reported as unverified until linked test evidence is available.
        </p>
      </div>
    );
  }

  const isVerifiedPass = ['TESTS_PASSED', 'VERIFIED_PASSED'].includes(
    verification.overall_verdict
  );
  const verdictBadge = verification.overall_verdict === 'TESTS_PASSED'
    ? 'badge-emerald'
    : 'badge-amber';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Top Verdict Hero Banner */}
      <div className="card-panel" style={{
        padding: '24px',
        background: isVerifiedPass 
          ? 'linear-gradient(135deg, rgba(16, 185, 129, 0.15) 0%, #101626 100%)'
          : 'linear-gradient(135deg, rgba(245, 158, 11, 0.15) 0%, #101626 100%)',
        border: `1px solid ${isVerifiedPass ? 'rgba(52, 211, 153, 0.4)' : 'rgba(251, 191, 36, 0.4)'}`,
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        flexWrap: 'wrap',
        gap: '16px'
      }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
            <span className="badge badge-cyan">Stage 6: Independent Verifier</span>
            <span className={`badge ${verdictBadge}`} style={{ fontSize: '0.75rem', padding: '3px 10px' }}>
              {verification.overall_verdict.replaceAll('_', ' ')}
            </span>
          </div>
          <h2 style={{ fontSize: '1.35rem', fontWeight: 700, color: '#f8fafc', marginBottom: '6px' }}>
            Captured Test Results & Verification Evidence
          </h2>
          <p style={{ fontSize: '0.85rem', color: '#cbd5e1', maxWidth: '850px', lineHeight: '1.5' }}>
            {verification.review_summary}
          </p>
        </div>

        {/* Action Button */}
        <button
          className="btn btn-emerald"
          onClick={onNavigateToEvaluations}
          style={{
            padding: '10px 20px',
            fontWeight: 600,
            background: 'linear-gradient(135deg, #059669 0%, #047857 100%)'
          }}
        >
          <BarChart3 size={16} />
          <span>View Evaluation Dashboard (Stage 7)</span>
          <ArrowRight size={15} />
        </button>
      </div>

      {/* Verification KPI Matrix */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '12px' }}>
        <div className="card-panel" style={{ padding: '14px 16px' }}>
          <span style={{ fontSize: '0.675rem', color: '#64748b', textTransform: 'uppercase', display: 'block', marginBottom: '2px' }}>
            Automated Test Pass Rate
          </span>
          <span style={{ fontSize: '1.2rem', fontWeight: 700, color: '#34d399' }}>
            {verification.pass_rate_percent == null ? '—' : `${verification.pass_rate_percent}%`}
          </span>
          <span style={{ display: 'block', fontSize: '0.7rem', color: '#64748b' }}>
            {verification.tests_total > 0
              ? `${verification.tests_passed}/${verification.tests_total} captured tests passed`
              : 'No test results captured'}
          </span>
        </div>

        <div className="card-panel" style={{ padding: '14px 16px' }}>
          <span style={{ fontSize: '0.675rem', color: '#64748b', textTransform: 'uppercase', display: 'block', marginBottom: '2px' }}>
            Acceptance Criteria
          </span>
          <span style={{ fontSize: '1.2rem', fontWeight: 700, color: '#a78bfa' }}>
            {verification.criteria_evaluations?.length
              ? `${verification.criteria_evaluations.filter((criterion) => criterion.verdict === 'PASS').length}/${verification.criteria_evaluations.length} verified`
              : '—'}
          </span>
          <span style={{ display: 'block', fontSize: '0.7rem', color: '#64748b' }}>
            {verification.criteria_evaluations?.some((criterion) => criterion.verdict === 'NOT_VERIFIED')
              ? 'No criterion-to-test mapping captured'
              : 'Based on recorded criterion evidence'}
          </span>
        </div>

        <div className="card-panel" style={{ padding: '14px 16px' }}>
          <span style={{ fontSize: '0.675rem', color: '#64748b', textTransform: 'uppercase', display: 'block', marginBottom: '2px' }}>
            Security Audit
          </span>
          <span style={{ fontSize: '0.85rem', fontWeight: 700, color: '#34d399' }}>
            {verification.security_verdict.split('(')[0]}
          </span>
        </div>
      </div>

      {/* Acceptance Criteria Evaluation Matrix */}
      <div className="card-panel" style={{ padding: '20px' }}>
        <h3 style={{ fontSize: '0.95rem', fontWeight: 600, color: '#f1f5f9', display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '14px' }}>
          <FileCheck2 size={16} color="#38bdf8" />
          <span>Acceptance Criteria Verification Ledger ({verification.criteria_evaluations?.length || 0})</span>
        </h3>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          {(verification.criteria_evaluations || []).map((crit, idx) => (
            <div
              key={idx}
              style={{
                backgroundColor: '#0c121d',
                border: '1px solid #1e293b',
                borderRadius: '8px',
                padding: '12px 16px',
                display: 'flex',
                flexDirection: 'column',
                gap: '6px'
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span className="badge badge-purple" style={{ fontSize: '0.65rem' }}>
                    {crit.criterion_id}
                  </span>
                  <span style={{ fontSize: '0.85rem', fontWeight: 600, color: '#f8fafc' }}>
                    {crit.criterion_description}
                  </span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span className={`badge ${
                    crit.verdict === 'PASS' ? 'badge-emerald'
                      : crit.verdict === 'NOT_VERIFIED' ? 'badge-amber'
                        : 'badge-rose'
                  }`} style={{ fontSize: '0.65rem' }}>
                    {crit.verdict}
                  </span>
                </div>
              </div>

              <div style={{
                fontSize: '0.775rem',
                color: '#94a3b8',
                backgroundColor: '#070a10',
                padding: '8px 12px',
                borderRadius: '4px',
                borderLeft: `3px solid ${crit.verdict === 'PASS' ? '#10b981' : '#f59e0b'}`
              }}>
                <strong style={{ color: crit.verdict === 'PASS' ? '#34d399' : '#fbbf24' }}>Evidence:</strong> {crit.evidence}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Constraints Compliance & Recommendations Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: '16px' }}>
        
        {/* Constraints Compliance Audit */}
        <div className="card-panel" style={{ padding: '18px' }}>
          <h4 style={{ fontSize: '0.9rem', fontWeight: 600, color: '#f1f5f9', display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '12px' }}>
            <Lock size={15} color="#38bdf8" />
            <span>Constraints Compliance Audit</span>
          </h4>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {(verification.constraint_compliances || []).map((cc, idx) => (
              <div
                key={idx}
                style={{
                  backgroundColor: '#0c121d',
                  border: '1px solid #1e293b',
                  borderRadius: '6px',
                  padding: '10px 12px'
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span className={`badge ${cc.is_hard ? 'badge-rose' : 'badge-amber'}`} style={{ fontSize: '0.6rem' }}>
                      {cc.is_hard ? 'Hard Constraint' : 'Soft Constraint'}
                    </span>
                    <span style={{ fontSize: '0.775rem', fontWeight: 600, color: '#cbd5e1' }}>
                      {cc.constraint_text}
                    </span>
                  </div>
                  {cc.compliant === true || cc.status === 'compliant' ? (
                    <span style={{ display: 'flex', alignItems: 'center', gap: '4px', color: '#10b981', fontSize: '0.7rem' }}>
                      <CheckCircle2 size={15} color="#10b981" /> Compliant
                    </span>
                  ) : cc.compliant === false || cc.status === 'violated' ? (
                    <span style={{ display: 'flex', alignItems: 'center', gap: '4px', color: '#ef4444', fontSize: '0.7rem' }}>
                      <XCircle size={15} color="#ef4444" /> Violated
                    </span>
                  ) : (
                    <span style={{ display: 'flex', alignItems: 'center', gap: '4px', color: '#f59e0b', fontSize: '0.7rem' }}>
                      <AlertTriangle size={15} color="#f59e0b" /> Unknown / Unverified
                    </span>
                  )}
                </div>
                <p style={{ fontSize: '0.725rem', color: '#64748b' }}>
                  {cc.notes}
                </p>
              </div>
            ))}
          </div>
        </div>

        {/* Verifier Recommendations */}
        <div className="card-panel" style={{ padding: '18px' }}>
          <h4 style={{ fontSize: '0.9rem', fontWeight: 600, color: '#f1f5f9', display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '12px' }}>
            <Sparkles size={15} color="#fbbf24" />
            <span>Reviewer Recommendations</span>
          </h4>

          <ul style={{ display: 'flex', flexDirection: 'column', gap: '8px', paddingLeft: '18px', fontSize: '0.8rem', color: '#94a3b8' }}>
            {(verification.recommendations || []).map((rec, idx) => (
              <li key={idx} style={{ lineHeight: '1.4' }}>
                {rec}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}
