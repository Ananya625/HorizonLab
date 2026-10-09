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
  AlertTriangle,
  Bot,
  Zap,
  Sparkles
} from 'lucide-react';
import confetti from 'canvas-confetti';

export default function ConfirmationGate({ 
  goalModel, 
  onConfirm, 
  isConfirming, 
  onNavigateToClarifications,
  onProceedToPlanner
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
          particleCount: 80,
          spread: 70,
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
      <div className="card-panel" style={{ padding: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
          <div style={{
            width: '36px',
            height: '36px',
            borderRadius: '8px',
            background: goalModel?.is_confirmed ? 'rgba(16, 185, 129, 0.15)' : 'rgba(56, 189, 248, 0.15)',
            border: `1px solid ${goalModel?.is_confirmed ? '#10b981' : '#38bdf8'}`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}>
            {goalModel?.is_confirmed ? <Lock size={20} color="#10b981" /> : <ShieldCheck size={20} color="#38bdf8" />}
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span className={`badge ${goalModel?.is_confirmed ? 'badge-emerald' : 'badge-cyan'}`}>
                {goalModel?.is_confirmed ? 'Goal Model Locked' : 'Confirmation Gate'}
              </span>
              <span className="font-mono" style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Version: {goalModel?.goal_model_version}</span>
            </div>
            <h2 style={{ fontSize: '1.25rem', fontWeight: 700, color: '#f8fafc', marginTop: '2px' }}>
              {goalModel?.is_confirmed 
                ? 'Goal Model Confirmed & Locked — Ready for Codebase Planner' 
                : 'Lock & Confirm Immutable Goal Model'}
            </h2>
          </div>
        </div>
        <p style={{ fontSize: '0.85rem', color: '#94a3b8' }}>
          The Goal Model is locked into the execution ledger and serves as the immutable reference benchmark for multi-agent execution and independent verification.
        </p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
        {/* Verification Readiness Checklist */}
        <div className="card-panel" style={{ padding: '20px', backgroundColor: '#0e1522' }}>
          <h3 style={{ fontSize: '1rem', fontWeight: 600, color: '#f8fafc', marginBottom: '16px' }}>
            Pre-Execution Verification Checklist
          </h3>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {/* Check 1: Main Goal */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 12px', backgroundColor: '#070b12', border: '1px solid #1e293b', borderRadius: '6px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <CheckCircle2 size={16} color="#10b981" />
                <span style={{ fontSize: '0.825rem', color: '#f1f5f9' }}>Main Objective Defined</span>
              </div>
              <span className="badge badge-emerald" style={{ fontSize: '0.65rem' }}>Pass</span>
            </div>

            {/* Check 2: Sub-Goals */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 12px', backgroundColor: '#070b12', border: '1px solid #1e293b', borderRadius: '6px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                {subGoalsCount > 0 ? <CheckCircle2 size={16} color="#10b981" /> : <XCircle size={16} color="#f43f5e" />}
                <span style={{ fontSize: '0.825rem', color: '#f1f5f9' }}>Hierarchical Sub-Goals Partitioned</span>
              </div>
              <span className={`badge ${subGoalsCount > 0 ? 'badge-emerald' : 'badge-rose'}`} style={{ fontSize: '0.65rem' }}>
                {subGoalsCount} Sub-Goals
              </span>
            </div>

            {/* Check 3: Success Criteria */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 12px', backgroundColor: '#070b12', border: '1px solid #1e293b', borderRadius: '6px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                {criteriaCount > 0 ? <CheckCircle2 size={16} color="#10b981" /> : <XCircle size={16} color="#f43f5e" />}
                <span style={{ fontSize: '0.825rem', color: '#f1f5f9' }}>Measurable Verification Criteria</span>
              </div>
              <span className={`badge ${criteriaCount > 0 ? 'badge-emerald' : 'badge-rose'}`} style={{ fontSize: '0.65rem' }}>
                {criteriaCount} Criteria
              </span>
            </div>

            {/* Check 4: Hard Constraints */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 12px', backgroundColor: '#070b12', border: '1px solid #1e293b', borderRadius: '6px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                {hardConstraintsCount > 0 ? <CheckCircle2 size={16} color="#10b981" /> : <CheckCircle2 size={16} color="#f59e0b" />}
                <span style={{ fontSize: '0.825rem', color: '#f1f5f9' }}>Hard Constraint Guardrails</span>
              </div>
              <span className="badge badge-rose" style={{ fontSize: '0.65rem' }}>
                {hardConstraintsCount} Invariants
              </span>
            </div>

            {/* Check 5: Blocking Ambiguities */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 12px', backgroundColor: '#070b12', border: `1px solid ${unresolvedBlocking.length === 0 ? '#1e293b' : 'rgba(244, 63, 94, 0.4)'}`, borderRadius: '6px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                {unresolvedBlocking.length === 0 ? <CheckCircle2 size={16} color="#10b981" /> : <AlertTriangle size={16} color="#f43f5e" />}
                <span style={{ fontSize: '0.825rem', color: '#f1f5f9' }}>Blocking Clarifications Resolved</span>
              </div>
              {unresolvedBlocking.length === 0 ? (
                <span className="badge badge-emerald" style={{ fontSize: '0.65rem' }}>100% Cleared</span>
              ) : (
                <button 
                  onClick={onNavigateToClarifications} 
                  className="btn btn-sm btn-danger"
                  style={{ fontSize: '0.675rem', padding: '2px 8px' }}
                >
                  {unresolvedBlocking.length} Unresolved &rarr;
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Action Panel & Next Stage Advance */}
        <div className="card-panel" style={{ padding: '20px', backgroundColor: '#0e1522', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
          <div>
            <h3 style={{ fontSize: '1rem', fontWeight: 600, color: '#f8fafc', marginBottom: '10px' }}>
              {goalModel?.is_confirmed ? 'Goal Model Locked' : 'Execute Goal Governance Lock'}
            </h3>

            {goalModel?.is_confirmed ? (
              <div style={{
                backgroundColor: 'rgba(16, 185, 129, 0.1)',
                border: '1px solid rgba(16, 185, 129, 0.3)',
                borderRadius: '8px',
                padding: '16px',
                marginBottom: '16px'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#34d399', fontWeight: 600, marginBottom: '6px' }}>
                  <ShieldCheck size={18} />
                  <span>Goal Model Immutable & Validated</span>
                </div>
                <p style={{ fontSize: '0.8rem', color: '#cbd5e1', lineHeight: '1.4' }}>
                  Confirmed on {new Date(goalModel.confirmed_at || Date.now()).toLocaleString()}. Run ID: <span className="font-mono" style={{ color: '#38bdf8' }}>{goalModel.run_id}</span>.
                </p>
              </div>
            ) : (
              <p style={{ fontSize: '0.825rem', color: '#94a3b8', lineHeight: '1.5', marginBottom: '16px' }}>
                Locking converts the Goal Model into the immutable reference benchmark for tracking action drift, early failure prediction, and state verification.
              </p>
            )}

            {/* Export buttons */}
            <div style={{ display: 'flex', gap: '8px', marginBottom: '16px' }}>
              <button onClick={handleDownloadJSON} className="btn btn-secondary btn-sm" style={{ flex: 1 }}>
                <Download size={14} /> Download Manifest
              </button>
              <button onClick={handleCopyJSON} className="btn btn-secondary btn-sm" style={{ flex: 1 }}>
                {copied ? <Check size={14} color="#10b981" /> : <Copy size={14} />}
                <span>{copied ? 'Copied' : 'Copy JSON'}</span>
              </button>
            </div>
          </div>

          {/* Bottom Confirmation Action / Next Stage Button */}
          <div>
            {!goalModel?.is_confirmed ? (
              <button 
                onClick={handleTriggerConfirm}
                disabled={!isReadyToLock || isConfirming}
                className="btn btn-emerald"
                style={{ width: '100%', padding: '12px', fontSize: '0.95rem', fontWeight: 600 }}
              >
                <Lock size={16} />
                <span>{isConfirming ? 'Locking Goal Model...' : 'Lock & Confirm Goal Model'}</span>
              </button>
            ) : (
              <button
                onClick={onProceedToPlanner}
                className="btn btn-primary"
                style={{
                  width: '100%',
                  padding: '12px',
                  fontSize: '0.95rem',
                  fontWeight: 600,
                  background: 'linear-gradient(135deg, #0284c7 0%, #0369a1 100%)'
                }}
              >
                <span>Proceed to Codebase Planner (Stage 3)</span>
                <ArrowRight size={16} />
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
