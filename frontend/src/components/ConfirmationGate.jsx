import React, { useState } from 'react';
import { 
  ShieldCheck, 
  Lock, 
  CheckCircle2, 
  XCircle, 
  Download, 
  Copy, 
  Check, 
  ArrowRight, 
  AlertTriangle
} from 'lucide-react';
import confetti from 'canvas-confetti';

export default function ConfirmationGate({ 
  goalModel, 
  onConfirm, 
  isConfirming, 
  onNavigateToClarifications,
  onProceedToPlanner,
  continueFullWorkflow = false
}) {
  const [copied, setCopied] = useState(false);

  const subGoalsCount = (goalModel?.sub_goals || []).length;
  const criteriaCount = (goalModel?.success_criteria || []).length;
  const hardConstraintsCount = (goalModel?.hard_constraints || []).length;
  const blockingAmbiguities = (goalModel?.ambiguities || []).filter((a) => a.severity === 'blocking');
  const unresolvedBlocking = blockingAmbiguities.filter((a) => !a.resolved);
  
  const isReadyToLock = 
    goalModel?.main_goal?.trim() &&
    subGoalsCount > 0 &&
    criteriaCount > 0 &&
    unresolvedBlocking.length === 0;

  const handleTriggerConfirm = async () => {
    if (!isReadyToLock || isConfirming) return;
    try {
      await onConfirm();
      try {
        confetti({
          particleCount: 70,
          spread: 60,
          origin: { y: 0.6 }
        });
      } catch (e) {
        // Confetti fallback
      }
    } catch (err) {
      alert(`Confirmation failed: ${err.message}`);
    }
  };

  const handleDownloadJSON = () => {
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(goalModel, null, 2));
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute("href", dataStr);
    downloadAnchor.setAttribute("download", `goal_manifest_${goalModel?.run_id || 'run'}.json`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  };

  const handleCopyJSON = () => {
    navigator.clipboard.writeText(JSON.stringify(goalModel, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Top Banner */}
      <section className="card-panel" style={{ padding: '24px', backgroundColor: '#FFFFFF' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
          <div style={{
            width: '38px',
            height: '38px',
            borderRadius: '8px',
            background: goalModel?.is_confirmed ? 'var(--success-subtle, #ECFDF5)' : 'var(--accent-primary-subtle, #F0EEFF)',
            border: `1px solid ${goalModel?.is_confirmed ? 'var(--success-border, #A7F3D0)' : 'var(--accent-primary-border, #D8D2FB)'}`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}>
            {goalModel?.is_confirmed ? <Lock size={20} color="var(--success-color, #16845B)" /> : <ShieldCheck size={20} color="var(--accent-primary, #6257D9)" />}
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span className={`badge ${goalModel?.is_confirmed ? 'badge-emerald' : 'badge-purple'}`}>
                {goalModel?.is_confirmed ? 'Goal Model Confirmed' : 'Confirmation Gate'}
              </span>
              <span className="font-mono" style={{ fontSize: '0.75rem', color: 'var(--text-secondary, #667085)' }}>
                v{goalModel?.goal_model_version || goalModel?.version || '1.0'}
              </span>
            </div>
            <h2 style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--text-primary, #172033)', marginTop: '2px', margin: 0 }}>
              {goalModel?.is_confirmed 
                ? 'Goal Model Confirmed & Locked — Ready for Codebase Planner' 
                : 'Review & Confirm Requirements Before Execution'}
            </h2>
          </div>
        </div>
        <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary, #667085)', margin: 0 }}>
          Confirming locks the requirement specification as the reference benchmark for code generation, test assertions, and independent verification.
        </p>
      </section>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '20px' }}>
        {/* Verification Readiness Checklist */}
        <section className="card-panel" style={{ padding: '20px', backgroundColor: '#FFFFFF' }}>
          <h3 style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--text-primary, #172033)', marginBottom: '14px' }}>
            Pre-Execution Verification Checklist
          </h3>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {/* Check 1: Main Goal */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 14px', backgroundColor: 'var(--bg-page, #F6F7FB)', border: '1px solid var(--border-subtle, #E5E7EF)', borderRadius: '6px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <CheckCircle2 size={16} color="var(--success-color, #16845B)" />
                <span style={{ fontSize: '0.825rem', color: 'var(--text-primary, #172033)', fontWeight: 500 }}>Main Objective Defined</span>
              </div>
              <span className="badge badge-emerald" style={{ fontSize: '0.65rem' }}>Ready</span>
            </div>

            {/* Check 2: Sub-Goals */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 14px', backgroundColor: 'var(--bg-page, #F6F7FB)', border: '1px solid var(--border-subtle, #E5E7EF)', borderRadius: '6px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                {subGoalsCount > 0 ? <CheckCircle2 size={16} color="var(--success-color, #16845B)" /> : <XCircle size={16} color="var(--danger-color, #D14343)" />}
                <span style={{ fontSize: '0.825rem', color: 'var(--text-primary, #172033)', fontWeight: 500 }}>Hierarchical Sub-Goals</span>
              </div>
              <span className={`badge ${subGoalsCount > 0 ? 'badge-emerald' : 'badge-rose'}`} style={{ fontSize: '0.65rem' }}>
                {subGoalsCount} Sub-Goals
              </span>
            </div>

            {/* Check 3: Success Criteria */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 14px', backgroundColor: 'var(--bg-page, #F6F7FB)', border: '1px solid var(--border-subtle, #E5E7EF)', borderRadius: '6px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                {criteriaCount > 0 ? <CheckCircle2 size={16} color="var(--success-color, #16845B)" /> : <XCircle size={16} color="var(--danger-color, #D14343)" />}
                <span style={{ fontSize: '0.825rem', color: 'var(--text-primary, #172033)', fontWeight: 500 }}>Measurable Success Criteria</span>
              </div>
              <span className={`badge ${criteriaCount > 0 ? 'badge-emerald' : 'badge-rose'}`} style={{ fontSize: '0.65rem' }}>
                {criteriaCount} Criteria
              </span>
            </div>

            {/* Check 4: Hard Constraints */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 14px', backgroundColor: 'var(--bg-page, #F6F7FB)', border: '1px solid var(--border-subtle, #E5E7EF)', borderRadius: '6px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <CheckCircle2 size={16} color="var(--success-color, #16845B)" />
                <span style={{ fontSize: '0.825rem', color: 'var(--text-primary, #172033)', fontWeight: 500 }}>Hard Constraint Guardrails</span>
              </div>
              <span className="badge badge-rose" style={{ fontSize: '0.65rem' }}>
                {hardConstraintsCount} Invariants
              </span>
            </div>

            {/* Check 5: Blocking Ambiguities */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 14px', backgroundColor: 'var(--bg-page, #F6F7FB)', border: `1px solid ${unresolvedBlocking.length === 0 ? 'var(--border-subtle, #E5E7EF)' : '#FECACA'}`, borderRadius: '6px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                {unresolvedBlocking.length === 0 ? <CheckCircle2 size={16} color="var(--success-color, #16845B)" /> : <AlertTriangle size={16} color="var(--danger-color, #D14343)" />}
                <span style={{ fontSize: '0.825rem', color: 'var(--text-primary, #172033)', fontWeight: 500 }}>Blocking Clarifications Resolved</span>
              </div>
              {unresolvedBlocking.length === 0 ? (
                <span className="badge badge-emerald" style={{ fontSize: '0.65rem' }}>100% Cleared</span>
              ) : (
                <button 
                  type="button"
                  onClick={onNavigateToClarifications} 
                  className="btn btn-sm btn-danger"
                  style={{ fontSize: '0.7rem', padding: '2px 8px' }}
                >
                  {unresolvedBlocking.length} Unresolved &rarr;
                </button>
              )}
            </div>
          </div>
        </section>

        {/* Action Panel & Next Stage Advance */}
        <section className="card-panel" style={{ padding: '20px', backgroundColor: '#FFFFFF', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
          <div>
            <h3 style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--text-primary, #172033)', marginBottom: '10px' }}>
              {goalModel?.is_confirmed ? 'Requirements Status' : 'Execute Requirement Confirmation'}
            </h3>

            {goalModel?.is_confirmed ? (
              <div style={{
                backgroundColor: 'var(--success-subtle, #ECFDF5)',
                border: '1px solid var(--success-border, #A7F3D0)',
                borderRadius: '8px',
                padding: '16px',
                marginBottom: '16px'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--success-color, #16845B)', fontWeight: 600, marginBottom: '6px' }}>
                  <ShieldCheck size={18} />
                  <span>Requirements Confirmed & Immutable</span>
                </div>
                <p style={{ fontSize: '0.825rem', color: 'var(--text-primary, #172033)', lineHeight: '1.4', margin: 0 }}>
                  Confirmed on {new Date(goalModel.confirmed_at || Date.now()).toLocaleString()}. Run ID: <span className="font-mono" style={{ color: 'var(--accent-primary, #6257D9)' }}>{goalModel.run_id}</span>.
                </p>
              </div>
            ) : (
              <p style={{ fontSize: '0.825rem', color: 'var(--text-secondary, #667085)', lineHeight: '1.5', marginBottom: '16px' }}>
                Confirmation records the requirements into the run ledger and allows the autonomous multi-agent pipeline to advance to architecture planning.
              </p>
            )}

            {/* Export buttons */}
            <div style={{ display: 'flex', gap: '8px', marginBottom: '16px' }}>
              <button type="button" onClick={handleDownloadJSON} className="btn btn-secondary btn-sm" style={{ flex: 1 }}>
                <Download size={14} /> Download Manifest
              </button>
              <button type="button" onClick={handleCopyJSON} className="btn btn-secondary btn-sm" style={{ flex: 1 }}>
                {copied ? <Check size={14} color="var(--success-color, #16845B)" /> : <Copy size={14} />}
                <span>{copied ? 'Copied' : 'Copy JSON'}</span>
              </button>
            </div>
          </div>

          {/* Bottom Confirmation Action / Next Stage Button */}
          <div>
            {!goalModel?.is_confirmed ? (
              <button 
                type="button"
                onClick={handleTriggerConfirm}
                disabled={!isReadyToLock || isConfirming}
                className="btn btn-emerald"
                style={{ width: '100%', padding: '11px', fontSize: '0.9rem', fontWeight: 600 }}
              >
                <Lock size={15} />
                <span>{isConfirming ? 'Confirming...' : continueFullWorkflow ? 'Confirm & continue workflow (3–7)' : 'Lock & Confirm Goal Model'}</span>
              </button>
            ) : (
              <button
                type="button"
                onClick={onProceedToPlanner}
                className="btn btn-primary"
                style={{ width: '100%', padding: '11px', fontSize: '0.9rem', fontWeight: 600 }}
              >
                <span>Proceed to Codebase Planner (Stage 3)</span>
                <ArrowRight size={15} />
              </button>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
