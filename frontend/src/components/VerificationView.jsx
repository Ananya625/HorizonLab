import React from 'react';
import { ArrowRight, ShieldCheck, CheckCircle2, XCircle, AlertTriangle } from 'lucide-react';

const cardStyle = { padding: '20px 24px', backgroundColor: '#FFFFFF' };
const badge = verdict => verdict === 'PASS' ? 'badge-emerald' : verdict === 'FAIL' ? 'badge-rose' : 'badge-amber';

export default function VerificationView({ verification, onNavigateToEvaluations }) {
  if (!verification) {
    return (
      <section className="card-panel" style={{ padding: '48px 24px', textAlign: 'center', backgroundColor: '#FFFFFF' }}>
        <ShieldCheck size={36} color="var(--text-muted, #98A2B3)" style={{ margin: '0 auto 12px' }} />
        <h2 style={{ fontSize: '1.25rem', color: 'var(--text-primary, #172033)', marginBottom: '8px' }}>
          No code review yet
        </h2>
        <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary, #667085)', maxWidth: '500px', margin: '0 auto' }}>
          Run verification after code generation and testing to see which requirements have supporting evidence.
        </p>
      </section>
    );
  }

  const current = verification.verifier_version === '2';
  const criteria = verification.criteria_evaluations || [];
  const passed = criteria.filter(c => c.verdict === 'PASS').length;
  const failed = criteria.filter(c => c.verdict === 'FAIL').length;
  const unknown = criteria.length - passed - failed;
  const complete = current && verification.overall_verdict === 'VERIFIED_PASSED';
  const title = !current ? 'Historical review' : complete ? 'Requirements verified' : failed ? 'Changes needed' : 'More evidence needed';

  return (
    <div className="verification-review" style={{ display: 'grid', gap: '16px' }}>
      {/* Overview & Verdict Banner */}
      <section className="card-panel" style={cardStyle}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '12px', marginBottom: '10px' }}>
          <div>
            <span className={`badge ${complete ? 'badge-emerald' : failed && current ? 'badge-rose' : 'badge-amber'}`} style={{ marginBottom: '6px' }}>
              {current ? (verification.overall_verdict || 'UNVERIFIED').replaceAll('_', ' ') : 'Legacy / unvalidated'}
            </span>
            <h2 style={{ fontSize: '1.35rem', fontWeight: 700, color: 'var(--text-primary, #172033)', marginTop: '2px', marginBottom: '6px' }}>
              {title}
            </h2>
          </div>

          <button 
            type="button"
            className="btn btn-primary" 
            onClick={onNavigateToEvaluations}
            style={{ fontWeight: 600 }}
          >
            <span>View workflow evaluation</span>
            <ArrowRight size={16} />
          </button>
        </div>

        <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary, #667085)', lineHeight: '1.5', margin: '0 0 10px 0' }}>
          {verification.review_summary || 'A passing test suite alone does not verify every task requirement.'}
        </p>

        {!current && (
          <p style={{ fontSize: '0.8rem', color: 'var(--warning-color, #B7791F)', margin: '0 0 10px 0' }}>
            These saved results have not been independently revalidated.
          </p>
        )}

        <div style={{ 
          fontSize: '0.85rem', 
          fontWeight: 600, 
          color: 'var(--text-primary, #172033)',
          background: 'var(--bg-page, #F6F7FB)',
          padding: '8px 12px',
          borderRadius: '6px',
          border: '1px solid var(--border-subtle, #E5E7EF)',
          display: 'inline-block'
        }}>
          {passed} passed · {failed} failed · {unknown} unverified {current ? 'requirements' : 'in the historical report'}
        </div>
      </section>

      {/* Requirement Checks */}
      <section className="card-panel" style={cardStyle}>
        <h3 style={{ fontSize: '1.05rem', fontWeight: 700, color: 'var(--text-primary, #172033)', marginBottom: '12px' }}>
          Requirement checks
        </h3>
        {!criteria.length && (
          <p style={{ color: 'var(--text-secondary, #667085)', fontSize: '0.85rem' }}>
            No acceptance criteria were checked. Define criteria before evaluating task completion.
          </p>
        )}
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          {criteria.map((criterion, index) => (
            <article 
              key={criterion.criterion_id || index} 
              style={{ 
                borderTop: index === 0 ? 'none' : '1px solid var(--border-subtle, #E5E7EF)', 
                padding: '14px 0' 
              }}
            >
              <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '10px', marginBottom: '6px' }}>
                <span className={`badge ${current ? badge(criterion.verdict) : 'badge-amber'}`}>
                  {criterion.verdict || 'UNVERIFIED'}
                </span>
                <strong style={{ color: 'var(--text-primary, #172033)', fontSize: '0.9rem' }}>
                  {criterion.criterion_description || criterion.criterion_id}
                </strong>
              </div>
              <p style={{ overflowWrap: 'anywhere', fontSize: '0.825rem', color: 'var(--text-secondary, #667085)', margin: 0, lineHeight: '1.5' }}>
                <strong style={{ color: 'var(--text-primary, #172033)' }}>
                  {criterion.verdict === 'UNVERIFIED' ? 'Missing evidence: ' : 'Evidence: '}
                </strong>
                {criterion.evidence || 'No evidence supplied.'}
              </p>
            </article>
          ))}
        </div>
      </section>

      {/* Recommendations */}
      {!!verification.recommendations?.length && (
        <section className="card-panel" style={cardStyle}>
          <h3 style={{ fontSize: '1.05rem', fontWeight: 700, color: 'var(--text-primary, #172033)', marginBottom: '12px' }}>
            What to do next
          </h3>
          <ul style={{ paddingLeft: '20px', fontSize: '0.85rem', color: 'var(--text-secondary, #667085)', lineHeight: '1.6' }}>
            {verification.recommendations.map((text, index) => (
              <li key={index} style={{ marginBottom: 6 }}>{text}</li>
            ))}
          </ul>
        </section>
      )}

      {/* Constraints Compliance */}
      {!!verification.constraint_compliances?.length && (
        <details className="card-panel" style={cardStyle}>
          <summary style={{ fontSize: '0.95rem', fontWeight: 600 }}>
            Constraints ({verification.constraint_compliances.length})
          </summary>
          <div style={{ marginTop: '12px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {verification.constraint_compliances.map((constraint, index) => (
              <p key={constraint.constraint_id || index} style={{ margin: 0, fontSize: '0.825rem', lineHeight: '1.5' }}>
                <span className={`badge ${current ? badge(constraint.compliant === true ? 'PASS' : constraint.compliant === false ? 'FAIL' : 'UNVERIFIED') : 'badge-amber'}`} style={{ marginRight: '6px' }}>
                  {constraint.compliant === true ? 'PASS' : constraint.compliant === false ? 'FAIL' : 'UNVERIFIED'}
                </span>
                <strong style={{ color: 'var(--text-primary, #172033)' }}>{constraint.constraint_text}</strong>
                {constraint.is_hard ? ' (required)' : ' (preference)'}
                {constraint.notes && (
                  <span style={{ display: 'block', color: 'var(--text-secondary, #667085)', marginLeft: '12px' }}>
                    {constraint.notes}
                  </span>
                )}
              </p>
            ))}
          </div>
        </details>
      )}

      {/* Additional ratings & limitations */}
      <details className="card-panel" style={cardStyle}>
        <summary>Additional ratings and their limitations</summary>
        <div style={{ marginTop: '10px', fontSize: '0.85rem', color: 'var(--text-secondary, #667085)', lineHeight: '1.6' }}>
          <p>Goal drift: {(() => {
            if (!current) return 'Unavailable — no validated semantic alignment measurement.';
            if (verification.goal_drift_score != null) return `${verification.goal_drift_score}%`;
            const diag = verification.evidence_breakdown?.diagnostic_scores?.goal_drift_score;
            if (diag != null) return `${diag}% (Diagnostic)`;
            return 'Unavailable — no validated semantic alignment measurement.';
          })()}</p>
          <p>Code quality: {current && verification.code_quality_score != null ? `${verification.code_quality_score} / 10` : 'Unverified — no calibrated quality checker is connected.'}</p>
          <p>Security: {current ? verification.security_verdict || 'UNVERIFIED' : 'UNVERIFIED'}.</p>
          <p style={{ fontSize: '0.775rem', color: 'var(--text-muted, #98A2B3)' }}>
            Syntax and passing tests do not constitute a security audit. These ratings are excluded from task approval when supporting evidence is absent.
          </p>
        </div>
      </details>
    </div>
  );
}
