import React from 'react';
import { 
  Cpu, 
  Layers, 
  FileCode2, 
  CheckCircle2, 
  ArrowRight, 
  AlertTriangle, 
  FlaskConical, 
  Workflow, 
  ShieldCheck 
} from 'lucide-react';

export default function PlannerView({
  plan,
  onExecuteCoding,
  isExecutingCode,
  onNavigateToStage
}) {
  if (!plan) {
    return (
      <div className="card-panel" style={{ padding: '48px 24px', textAlign: 'center', backgroundColor: '#FFFFFF' }}>
        <Cpu size={36} color="var(--text-muted, #98A2B3)" style={{ margin: '0 auto 12px' }} />
        <h3 style={{ fontSize: '1.15rem', color: 'var(--text-primary, #172033)', marginBottom: '8px' }}>
          No Implementation Plan Generated Yet
        </h3>
        <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary, #667085)', maxWidth: '520px', margin: '0 auto 16px' }}>
          Confirm the Requirement Analysis in Stage 2 to trigger codebase inspection and generate the architecture plan.
        </p>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Top Banner */}
      <section className="card-panel" style={{
        padding: '20px 24px',
        backgroundColor: '#FFFFFF',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        flexWrap: 'wrap',
        gap: '16px'
      }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
            <span className="badge badge-purple">Stage 3: Planner</span>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary, #667085)' }}>
              Target: <code style={{ color: 'var(--accent-primary, #6257D9)' }}>{plan.target_repo_path}</code>
            </span>
          </div>
          <h2 style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--text-primary, #172033)', marginBottom: '4px' }}>
            Architectural Blueprint & Implementation Strategy
          </h2>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary, #667085)', maxWidth: '850px', lineHeight: '1.5', margin: 0 }}>
            {plan.architecture_overview}
          </p>
        </div>

        {/* Action Button */}
        <button
          type="button"
          className="btn btn-primary"
          onClick={onExecuteCoding}
          disabled={isExecutingCode}
          style={{
            padding: '10px 20px',
            fontWeight: 600
          }}
        >
          <FileCode2 size={16} />
          <span>{isExecutingCode ? 'Writing Source Files...' : 'Execute Coding Agent (Stage 4)'}</span>
          <ArrowRight size={15} />
        </button>
      </section>

      {/* Tech Stack & Modules */}
      {plan.tech_stack && Object.keys(plan.tech_stack).length > 0 && (
        <section style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '12px' }}>
          {Object.entries(plan.tech_stack).map(([key, val]) => (
            <div key={key} className="card-panel" style={{ padding: '12px 16px', backgroundColor: '#FFFFFF' }}>
              <span style={{ fontSize: '0.675rem', color: 'var(--text-secondary, #667085)', textTransform: 'uppercase', display: 'block', marginBottom: '2px' }}>
                {key.replace(/_/g, ' ')}
              </span>
              <span style={{ fontSize: '0.9rem', fontWeight: 700, color: 'var(--accent-primary, #6257D9)' }}>
                {String(val)}
              </span>
            </div>
          ))}
        </section>
      )}

      {/* Planned Files Table */}
      <section className="card-panel" style={{ padding: '20px', backgroundColor: '#FFFFFF' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
          <h3 style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--text-primary, #172033)', display: 'flex', alignItems: 'center', gap: '8px', margin: 0 }}>
            <FileCode2 size={16} color="var(--accent-primary, #6257D9)" />
            <span>Planned Target Files ({plan.planned_files?.length || 0})</span>
          </h3>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {(plan.planned_files || []).map((file, idx) => {
            const actionBadge = file.action === 'create' ? 'badge-emerald' : (file.action === 'test' ? 'badge-purple' : 'badge-slate');
            return (
              <div 
                key={idx}
                style={{
                  backgroundColor: 'var(--bg-page, #F6F7FB)',
                  border: '1px solid var(--border-subtle, #E5E7EF)',
                  borderRadius: '6px',
                  padding: '10px 14px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: '12px',
                  flexWrap: 'wrap'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <span className={`badge ${actionBadge}`} style={{ fontSize: '0.65rem' }}>
                    {file.action}
                  </span>
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary, #172033)' }}>
                    {file.path}
                  </span>
                </div>
                <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary, #667085)', flex: 1, minWidth: '200px' }}>
                  {file.description}
                </span>
                <span style={{ fontSize: '0.725rem', color: 'var(--text-secondary, #667085)', fontFamily: 'var(--font-mono)' }}>
                  ~{file.estimated_loc} loc
                </span>
              </div>
            );
          })}
        </div>
      </section>

      {/* Sequential Execution Steps Roadmap */}
      <section className="card-panel planner-roadmap" style={{ padding: '20px', backgroundColor: '#FFFFFF' }}>
        <h3 style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--text-primary, #172033)', display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '14px' }}>
          <Workflow size={16} color="var(--accent-primary, #6257D9)" />
          <span>Planned Execution Flow ({plan.steps?.length || 0} Steps)</span>
        </h3>

        <div className="planner-roadmap-track" aria-label="Sequential planned execution flow">
          {(plan.steps || []).map((step, idx) => (
            <React.Fragment key={`${step.step_number}-${idx}`}>
              <article className="planner-roadmap-step">
                <div className="planner-roadmap-step-marker" aria-hidden="true">
                  <span>{step.step_number}</span>
                </div>
                <div className="planner-roadmap-step-content">
                  <div className="planner-roadmap-step-heading">
                    <span className="planner-roadmap-step-label">Step {step.step_number}</span>
                    <span className="badge badge-slate" style={{ fontSize: '0.65rem' }}>
                      {step.assigned_agent}
                    </span>
                  </div>
                  <h4>{step.title}</h4>
                  <p>{step.description}</p>
                  <div className="planner-roadmap-step-targets">
                    <span className="planner-roadmap-target-label">Targets</span>
                    {(step.target_files || []).map((tf, i) => (
                      <span key={i} className="planner-roadmap-file">
                        {tf}
                      </span>
                    ))}
                    {step.expected_outcome && (
                      <span className="planner-roadmap-outcome">
                        <CheckCircle2 size={13} />
                        <span>{step.expected_outcome}</span>
                      </span>
                    )}
                  </div>
                </div>
              </article>
              {idx < (plan.steps || []).length - 1 && (
                <div className="planner-roadmap-connector" aria-hidden="true">
                  <ArrowRight size={17} />
                </div>
              )}
            </React.Fragment>
          ))}
        </div>
      </section>

      {/* Testing Strategy & Risk Assessment */}
      <section style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '16px' }}>
        <div className="card-panel" style={{ padding: '16px 20px', backgroundColor: '#FFFFFF' }}>
          <h4 style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--accent-primary, #6257D9)', display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '8px' }}>
            <FlaskConical size={15} />
            <span>Testing & Verification Strategy</span>
          </h4>
          <p style={{ fontSize: '0.825rem', color: 'var(--text-secondary, #667085)', lineHeight: '1.5', margin: 0 }}>
            {plan.testing_strategy}
          </p>
        </div>

        <div className="card-panel" style={{ padding: '16px 20px', backgroundColor: '#FFFFFF' }}>
          <h4 style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--warning-color, #B7791F)', display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '8px' }}>
            <AlertTriangle size={15} />
            <span>Risk Assessment & Guardrails</span>
          </h4>
          <p style={{ fontSize: '0.825rem', color: 'var(--text-secondary, #667085)', lineHeight: '1.5', margin: 0 }}>
            {plan.risk_assessment}
          </p>
        </div>
      </section>
    </div>
  );
}
