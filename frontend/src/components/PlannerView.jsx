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
      <div className="card-panel" style={{ padding: '40px', textAlign: 'center' }}>
        <Cpu size={36} color="#64748b" style={{ margin: '0 auto 12px' }} />
        <h3 style={{ fontSize: '1.1rem', color: '#f1f5f9', marginBottom: '8px' }}>No Implementation Plan Generated Yet</h3>
        <p style={{ fontSize: '0.85rem', color: '#94a3b8', maxWidth: '500px', margin: '0 auto 16px' }}>
          Confirm the Requirement Analysis in Stage 2 to trigger codebase inspection and generate the architecture plan.
        </p>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Top Banner */}
      <div className="card-panel" style={{
        padding: '20px 24px',
        background: 'linear-gradient(135deg, #101626 0%, #0d121f 100%)',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        flexWrap: 'wrap',
        gap: '16px'
      }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
            <span className="badge badge-cyan">Stage 3: Codebase Analyst & Planner</span>
            <span style={{ fontSize: '0.75rem', color: '#64748b' }}>Target Repo: {plan.target_repo_path}</span>
          </div>
          <h2 style={{ fontSize: '1.25rem', fontWeight: 700, color: '#f8fafc', marginBottom: '4px' }}>
            Architectural Blueprint & Implementation Strategy
          </h2>
          <p style={{ fontSize: '0.825rem', color: '#94a3b8', maxWidth: '850px', lineHeight: '1.5' }}>
            {plan.architecture_overview}
          </p>
        </div>

        {/* Action Button */}
        <button
          className="btn btn-primary"
          onClick={onExecuteCoding}
          disabled={isExecutingCode}
          style={{
            padding: '10px 20px',
            fontWeight: 600,
            background: 'linear-gradient(135deg, #0284c7 0%, #0369a1 100%)'
          }}
        >
          <FileCode2 size={16} />
          <span>{isExecutingCode ? 'Coding Agent Writing Files...' : 'Execute Coding Agent (Stage 4)'}</span>
          <ArrowRight size={15} />
        </button>
      </div>

      {/* Tech Stack & Key Modules */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '12px' }}>
        {Object.entries(plan.tech_stack || {}).map(([key, val]) => (
          <div key={key} className="card-panel" style={{ padding: '12px 16px' }}>
            <span style={{ fontSize: '0.675rem', color: '#64748b', textTransform: 'uppercase', display: 'block', marginBottom: '2px' }}>
              {key.replace('_', ' ')}
            </span>
            <span style={{ fontSize: '0.85rem', fontWeight: 600, color: '#38bdf8' }}>
              {String(val)}
            </span>
          </div>
        ))}
      </div>

      {/* Planned Files Table */}
      <div className="card-panel" style={{ padding: '20px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
          <h3 style={{ fontSize: '0.95rem', fontWeight: 600, color: '#f1f5f9', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <FileCode2 size={16} color="#38bdf8" />
            <span>Target Files to Touch & Implement ({plan.planned_files?.length || 0})</span>
          </h3>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {(plan.planned_files || []).map((file, idx) => {
            const actionBadge = file.action === 'create' ? 'badge-emerald' : (file.action === 'test' ? 'badge-purple' : 'badge-cyan');
            return (
              <div 
                key={idx}
                style={{
                  backgroundColor: '#0c121d',
                  border: '1px solid #1e293b',
                  borderRadius: '6px',
                  padding: '10px 14px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: '12px'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <span className={`badge ${actionBadge}`} style={{ fontSize: '0.65rem' }}>
                    {file.action}
                  </span>
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.85rem', fontWeight: 600, color: '#f8fafc' }}>
                    {file.path}
                  </span>
                </div>
                <span style={{ fontSize: '0.775rem', color: '#94a3b8', flex: 1, marginLeft: '12px' }}>
                  {file.description}
                </span>
                <span style={{ fontSize: '0.7rem', color: '#64748b', fontFamily: 'var(--font-mono)' }}>
                  ~{file.estimated_loc} loc
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Sequential Execution Steps Roadmap */}
      <div className="card-panel" style={{ padding: '20px' }}>
        <h3 style={{ fontSize: '0.95rem', fontWeight: 600, color: '#f1f5f9', display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '14px' }}>
          <Workflow size={16} color="#38bdf8" />
          <span>Sequential Step-by-Step Execution Plan ({plan.steps?.length || 0} Steps)</span>
        </h3>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {(plan.steps || []).map((step, idx) => (
            <div 
              key={idx}
              style={{
                backgroundColor: '#0c121d',
                border: '1px solid #1e293b',
                borderRadius: '8px',
                padding: '14px 16px',
                display: 'flex',
                gap: '14px',
                alignItems: 'flex-start'
              }}
            >
              <div style={{
                width: '28px',
                height: '28px',
                borderRadius: '50%',
                backgroundColor: '#1e293b',
                color: '#38bdf8',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontWeight: 700,
                fontSize: '0.8rem',
                flexShrink: 0
              }}>
                {step.step_number}
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                  <h4 style={{ fontSize: '0.875rem', fontWeight: 600, color: '#f1f5f9' }}>
                    {step.title}
                  </h4>
                  <span className="badge badge-slate" style={{ fontSize: '0.65rem' }}>
                    {step.assigned_agent}
                  </span>
                </div>
                <p style={{ fontSize: '0.8rem', color: '#94a3b8', marginBottom: '6px', lineHeight: '1.4' }}>
                  {step.description}
                </p>
                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center' }}>
                  <span style={{ fontSize: '0.7rem', color: '#64748b' }}>Targets:</span>
                  {step.target_files.map((tf, i) => (
                    <span key={i} style={{ fontSize: '0.7rem', fontFamily: 'var(--font-mono)', color: '#38bdf8', background: '#151d2e', padding: '1px 6px', borderRadius: '4px' }}>
                      {tf}
                    </span>
                  ))}
                  <span style={{ fontSize: '0.7rem', color: '#10b981', marginLeft: 'auto' }}>
                    ✓ Expected: {step.expected_outcome}
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Testing Strategy & Risk Assessment */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
        <div className="card-panel" style={{ padding: '16px 20px' }}>
          <h4 style={{ fontSize: '0.85rem', fontWeight: 600, color: '#a78bfa', display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '8px' }}>
            <FlaskConical size={15} />
            <span>Testing & Verification Strategy</span>
          </h4>
          <p style={{ fontSize: '0.8rem', color: '#94a3b8', lineHeight: '1.5' }}>
            {plan.testing_strategy}
          </p>
        </div>

        <div className="card-panel" style={{ padding: '16px 20px' }}>
          <h4 style={{ fontSize: '0.85rem', fontWeight: 600, color: '#fbbf24', display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '8px' }}>
            <AlertTriangle size={15} />
            <span>Risk Assessment & Mitigation</span>
          </h4>
          <p style={{ fontSize: '0.8rem', color: '#94a3b8', lineHeight: '1.5' }}>
            {plan.risk_assessment}
          </p>
        </div>
      </div>
    </div>
  );
}
