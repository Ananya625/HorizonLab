import React, { useState } from 'react';
import { X, CheckCircle2, ShieldAlert } from 'lucide-react';

export function EditCriterionModal({ isOpen, onClose, criterion, subGoals = [], onSave, existingIds = [] }) {
  if (!isOpen) return null;

  const isNew = !criterion?.id;
  const [id, setId] = useState(criterion?.id || `SC-${existingIds.length + 1}`);
  const [subGoalId, setSubGoalId] = useState(criterion?.sub_goal_id || (subGoals[0]?.id || ''));
  const [description, setDescription] = useState(criterion?.description || '');
  const [metric, setMetric] = useState(criterion?.metric || '');
  const [verificationMethod, setVerificationMethod] = useState(criterion?.verification_method || 'state_ledger_check');
  const [expectedOutput, setExpectedOutput] = useState(criterion?.expected_output || '');

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!description.trim() || !metric.trim()) return;

    onSave({
      id: id.trim() || `SC-${Date.now()}`,
      sub_goal_id: subGoalId,
      description: description.trim(),
      metric: metric.trim(),
      verification_method: verificationMethod,
      expected_output: expectedOutput.trim()
    });
    onClose();
  };

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      width: '100vw',
      height: '100vh',
      backgroundColor: 'rgba(0, 0, 0, 0.75)',
      backdropFilter: 'blur(6px)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 1100
    }}>
      <div className="card-panel" style={{
        width: '560px',
        maxWidth: '92vw',
        padding: '24px',
        backgroundColor: '#111827',
        border: '1px solid #1f293d',
        position: 'relative'
      }}>
        <button onClick={onClose} className="btn btn-ghost btn-sm" style={{ position: 'absolute', top: '16px', right: '16px', padding: '4px' }}>
          <X size={18} />
        </button>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '18px' }}>
          <div style={{
            width: '32px',
            height: '32px',
            borderRadius: '6px',
            background: 'rgba(16, 185, 129, 0.1)',
            border: '1px solid rgba(16, 185, 129, 0.3)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}>
            <CheckCircle2 size={18} color="#10b981" />
          </div>
          <div>
            <h3 style={{ fontSize: '1.1rem', fontWeight: 600, color: '#f8fafc' }}>
              {isNew ? 'Add Success Criterion' : `Edit Success Criterion (${id})`}
            </h3>
            <p style={{ fontSize: '0.775rem', color: '#94a3b8' }}>
              Define measurable checks to be independently verified during task execution
            </p>
          </div>
        </div>

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '12px' }}>
            <div>
              <label style={{ display: 'block', fontSize: '0.775rem', color: '#cbd5e1', marginBottom: '4px' }}>Criterion ID</label>
              <input 
                type="text" 
                value={id} 
                onChange={(e) => setId(e.target.value)}
                disabled={!isNew}
                className="font-mono"
                style={{
                  width: '100%',
                  padding: '8px 10px',
                  backgroundColor: '#0c121d',
                  border: '1px solid #24344d',
                  borderRadius: '6px',
                  color: '#f8fafc',
                  fontSize: '0.825rem',
                  outline: 'none'
                }}
              />
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '0.775rem', color: '#cbd5e1', marginBottom: '4px' }}>Mapped Sub-Goal</label>
              <select
                value={subGoalId}
                onChange={(e) => setSubGoalId(e.target.value)}
                style={{
                  width: '100%',
                  padding: '8px 10px',
                  backgroundColor: '#0c121d',
                  border: '1px solid #24344d',
                  borderRadius: '6px',
                  color: '#f8fafc',
                  fontSize: '0.825rem',
                  outline: 'none'
                }}
              >
                <option value="">(Global / Unmapped)</option>
                {subGoals.map((sg) => (
                  <option key={sg.id} value={sg.id}>
                    {sg.id} — {sg.title}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '0.775rem', color: '#cbd5e1', marginBottom: '4px' }}>Description</label>
            <input 
              type="text" 
              value={description} 
              onChange={(e) => setDescription(e.target.value)}
              placeholder="e.g. 100% of pending tickets classified with confidence >= 0.85"
              required
              style={{
                width: '100%',
                padding: '8px 12px',
                backgroundColor: '#0c121d',
                border: '1px solid #24344d',
                borderRadius: '6px',
                color: '#f8fafc',
                fontSize: '0.85rem',
                outline: 'none'
              }}
            />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
            <div>
              <label style={{ display: 'block', fontSize: '0.775rem', color: '#cbd5e1', marginBottom: '4px' }}>Measurable Metric / Expression</label>
              <input 
                type="text" 
                value={metric} 
                onChange={(e) => setMetric(e.target.value)}
                placeholder="e.g. Unclassified tickets == 0"
                required
                className="font-mono"
                style={{
                  width: '100%',
                  padding: '8px 10px',
                  backgroundColor: '#0c121d',
                  border: '1px solid #24344d',
                  borderRadius: '6px',
                  color: '#38bdf8',
                  fontSize: '0.825rem',
                  outline: 'none'
                }}
              />
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '0.775rem', color: '#cbd5e1', marginBottom: '4px' }}>Verification Method</label>
              <select
                value={verificationMethod}
                onChange={(e) => setVerificationMethod(e.target.value)}
                style={{
                  width: '100%',
                  padding: '8px 10px',
                  backgroundColor: '#0c121d',
                  border: '1px solid #24344d',
                  borderRadius: '6px',
                  color: '#f8fafc',
                  fontSize: '0.825rem',
                  outline: 'none'
                }}
              >
                <option value="state_ledger_check">state_ledger_check (State Audit)</option>
                <option value="automated_test">automated_test (Unit/E2E Run)</option>
                <option value="schema_validation">schema_validation (Payload Schema)</option>
                <option value="diff_inspection">diff_inspection (State Diff)</option>
              </select>
            </div>
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '0.775rem', color: '#cbd5e1', marginBottom: '4px' }}>Expected Output / Evidence Artifact</label>
            <input 
              type="text" 
              value={expectedOutput} 
              onChange={(e) => setExpectedOutput(e.target.value)}
              placeholder="e.g. Structured classification ledger with ticket IDs"
              style={{
                width: '100%',
                padding: '8px 12px',
                backgroundColor: '#0c121d',
                border: '1px solid #24344d',
                borderRadius: '6px',
                color: '#f8fafc',
                fontSize: '0.85rem',
                outline: 'none'
              }}
            />
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '12px' }}>
            <button type="button" onClick={onClose} className="btn btn-secondary">
              Cancel
            </button>
            <button type="submit" className="btn btn-emerald">
              <CheckCircle2 size={14} />
              <span>{isNew ? 'Add Criterion' : 'Save Criterion'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export function EditConstraintModal({ isOpen, onClose, constraint, isHardDefault = true, onSave, existingIds = [] }) {
  if (!isOpen) return null;

  const isNew = !constraint?.id;
  const [isHard, setIsHard] = useState(constraint ? constraint.is_hard : isHardDefault);
  const prefix = isHard ? 'HC' : 'SC';
  const [id, setId] = useState(constraint?.id || `${prefix}-${existingIds.length + 1}`);
  const [text, setText] = useState(constraint?.text || '');
  const [category, setCategory] = useState(constraint?.category || (isHard ? 'safety' : 'performance'));

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!text.trim()) return;

    onSave({
      id: id.trim() || `${prefix}-${Date.now()}`,
      text: text.trim(),
      category,
      is_hard: isHard
    });
    onClose();
  };

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      width: '100vw',
      height: '100vh',
      backgroundColor: 'rgba(0, 0, 0, 0.75)',
      backdropFilter: 'blur(6px)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 1100
    }}>
      <div className="card-panel" style={{
        width: '520px',
        maxWidth: '92vw',
        padding: '24px',
        backgroundColor: '#111827',
        border: '1px solid #1f293d',
        position: 'relative'
      }}>
        <button onClick={onClose} className="btn btn-ghost btn-sm" style={{ position: 'absolute', top: '16px', right: '16px', padding: '4px' }}>
          <X size={18} />
        </button>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '18px' }}>
          <div style={{
            width: '32px',
            height: '32px',
            borderRadius: '6px',
            background: isHard ? 'rgba(244, 63, 94, 0.1)' : 'rgba(245, 158, 11, 0.1)',
            border: `1px solid ${isHard ? 'rgba(244, 63, 94, 0.3)' : 'rgba(245, 158, 11, 0.3)'}`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}>
            <ShieldAlert size={18} color={isHard ? '#f43f5e' : '#f59e0b'} />
          </div>
          <div>
            <h3 style={{ fontSize: '1.1rem', fontWeight: 600, color: '#f8fafc' }}>
              {isNew ? (isHard ? 'Add Hard Constraint' : 'Add Soft Constraint') : `Edit Constraint (${id})`}
            </h3>
            <p style={{ fontSize: '0.775rem', color: '#94a3b8' }}>
              {isHard 
                ? 'Hard constraints are immutable invariant boundaries that must NEVER be violated' 
                : 'Soft constraints express heuristics, preferences, and style guidelines'}
            </p>
          </div>
        </div>

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
            <div>
              <label style={{ display: 'block', fontSize: '0.775rem', color: '#cbd5e1', marginBottom: '4px' }}>Constraint Type</label>
              <select
                value={isHard ? 'hard' : 'soft'}
                onChange={(e) => {
                  const hard = e.target.value === 'hard';
                  setIsHard(hard);
                  if (isNew) {
                    setId(`${hard ? 'HC' : 'SC'}-${existingIds.length + 1}`);
                  }
                }}
                style={{
                  width: '100%',
                  padding: '8px 10px',
                  backgroundColor: '#0c121d',
                  border: '1px solid #24344d',
                  borderRadius: '6px',
                  color: isHard ? '#fb7185' : '#fbbf24',
                  fontSize: '0.825rem',
                  fontWeight: 600,
                  outline: 'none'
                }}
              >
                <option value="hard">HARD (Strict Invariant)</option>
                <option value="soft">SOFT (Preference / Style)</option>
              </select>
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '0.775rem', color: '#cbd5e1', marginBottom: '4px' }}>Category</label>
              <select
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                style={{
                  width: '100%',
                  padding: '8px 10px',
                  backgroundColor: '#0c121d',
                  border: '1px solid #24344d',
                  borderRadius: '6px',
                  color: '#f8fafc',
                  fontSize: '0.825rem',
                  outline: 'none'
                }}
              >
                <option value="safety">Safety / Guardrails</option>
                <option value="budget">Budget / Cost Limits</option>
                <option value="security">Security & PII Protection</option>
                <option value="resource">Resource & Rate Limits</option>
                <option value="temporal">Temporal / Latency SLO</option>
                <option value="performance">Performance Optimization</option>
                <option value="style">Style & Formatting</option>
                <option value="preference">Operational Preference</option>
              </select>
            </div>
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '0.775rem', color: '#cbd5e1', marginBottom: '4px' }}>Constraint Rule Text</label>
            <textarea 
              value={text} 
              onChange={(e) => setText(e.target.value)}
              rows={3}
              placeholder={isHard ? "e.g. Never execute refund exceeding $100 without manager signature" : "e.g. Maintain polite tone in customer emails"}
              required
              style={{
                width: '100%',
                padding: '8px 12px',
                backgroundColor: '#0c121d',
                border: '1px solid #24344d',
                borderRadius: '6px',
                color: '#f8fafc',
                fontSize: '0.85rem',
                outline: 'none',
                resize: 'vertical'
              }}
            />
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '12px' }}>
            <button type="button" onClick={onClose} className="btn btn-secondary">
              Cancel
            </button>
            <button type="submit" className={isHard ? "btn btn-danger" : "btn btn-primary"}>
              <CheckCircle2 size={14} />
              <span>{isNew ? 'Add Constraint' : 'Save Constraint'}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
