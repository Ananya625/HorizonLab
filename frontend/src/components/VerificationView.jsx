import React from 'react';
import { ArrowRight, ShieldCheck } from 'lucide-react';

const card = { padding: 20 };
const badge = verdict => verdict === 'PASS' ? 'badge-emerald' : verdict === 'FAIL' ? 'badge-rose' : 'badge-amber';

export default function VerificationView({ verification, onNavigateToEvaluations }) {
  if (!verification) return <section className="card-panel" style={card}>
    <ShieldCheck size={28} /><h2>No code review yet</h2>
    <p>Run verification after code generation and testing to see which requirements have supporting evidence.</p>
  </section>;

  const current = verification.verifier_version === '2';
  const criteria = verification.criteria_evaluations || [];
  const passed = criteria.filter(c => c.verdict === 'PASS').length;
  const failed = criteria.filter(c => c.verdict === 'FAIL').length;
  const unknown = criteria.length - passed - failed;
  const complete = current && verification.overall_verdict === 'VERIFIED_PASSED';
  const title = !current ? 'Historical review' : complete ? 'Requirements verified' : failed ? 'Changes needed' : 'More evidence needed';

  return <div className="verification-review" style={{ display: 'grid', gap: 16 }}>
    <section className="card-panel" style={card}>
      <span className={`badge ${complete ? 'badge-emerald' : failed && current ? 'badge-rose' : 'badge-amber'}`}>
        {current ? (verification.overall_verdict || 'UNVERIFIED').replaceAll('_', ' ') : 'Legacy / unvalidated'}
      </span>
      <h2>{title}</h2>
      <p>{verification.review_summary || 'A passing test suite alone does not verify every task requirement.'}</p>
      {!current && <p>These saved results have not been independently revalidated.</p>}
      <p>{passed} passed · {failed} failed · {unknown} unverified {current ? 'requirements' : 'in the historical report'}</p>
      <button className="btn btn-primary" onClick={onNavigateToEvaluations}>View workflow evaluation <ArrowRight size={16} /></button>
    </section>

    <section className="card-panel" style={card}>
      <h3>Requirement checks</h3>
      {!criteria.length && <p>No acceptance criteria were checked. Define criteria before evaluating task completion.</p>}
      {criteria.map((criterion, index) => <article key={criterion.criterion_id || index} style={{ borderTop: '1px solid #334155', padding: '14px 0' }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 10 }}>
          <span className={`badge ${current ? badge(criterion.verdict) : 'badge-amber'}`}>{criterion.verdict || 'UNVERIFIED'}</span>
          <strong>{criterion.criterion_description || criterion.criterion_id}</strong>
        </div>
        <p style={{ overflowWrap: 'anywhere' }}><strong>{criterion.verdict === 'UNVERIFIED' ? 'Missing evidence: ' : 'Evidence: '}</strong>{criterion.evidence || 'No evidence supplied.'}</p>
      </article>)}
    </section>

    {!!verification.recommendations?.length && <section className="card-panel" style={card}>
      <h3>What to do next</h3>
      <ul>{verification.recommendations.map((text, index) => <li key={index} style={{ marginBottom: 8 }}>{text}</li>)}</ul>
    </section>}

    {!!verification.constraint_compliances?.length && <details className="card-panel" style={card}>
      <summary>Constraints ({verification.constraint_compliances.length})</summary>
      {verification.constraint_compliances.map((constraint, index) => <p key={constraint.constraint_id || index}>
        <span className={`badge ${current ? badge(constraint.compliant === true ? 'PASS' : constraint.compliant === false ? 'FAIL' : 'UNVERIFIED') : 'badge-amber'}`}>
          {constraint.compliant === true ? 'PASS' : constraint.compliant === false ? 'FAIL' : 'UNVERIFIED'}
        </span> {constraint.constraint_text}{constraint.is_hard ? ' (required)' : ' (preference)'}<br />{constraint.notes}
      </p>)}
    </details>}

    <details className="card-panel" style={card}>
      <summary>Additional ratings and their limitations</summary>
      <p>Goal drift: {current && verification.goal_drift_score != null ? `${verification.goal_drift_score}%` : 'Unavailable — no validated semantic alignment measurement.'}</p>
      <p>Code quality: {current && verification.code_quality_score != null ? `${verification.code_quality_score} / 10` : 'Unverified — no calibrated quality checker is connected.'}</p>
      <p>Security: {current ? verification.security_verdict || 'UNVERIFIED' : 'UNVERIFIED'}.</p>
      <p>Syntax and passing tests do not constitute a security audit. These ratings are excluded from task approval when supporting evidence is absent.</p>
    </details>
  </div>;
}
