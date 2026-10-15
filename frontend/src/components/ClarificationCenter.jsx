import React, { useState } from 'react';
import { 
  HelpCircle, 
  AlertTriangle, 
  CheckCircle2, 
  ShieldCheck, 
  ArrowRight, 
  Send
} from 'lucide-react';

export default function ClarificationCenter({ 
  goalModel, 
  onResolveQuestion, 
  onProceedToConfirmation,
  resolvingId 
}) {
  const ambiguities = goalModel?.ambiguities || [];
  const [selectedAnswers, setSelectedAnswers] = useState({});
  const [customAnswers, setCustomAnswers] = useState({});
  const [constraintType, setConstraintType] = useState('hard');

  const blockingCount = ambiguities.filter((a) => a.severity === 'blocking').length;
  const resolvedBlockingCount = ambiguities.filter((a) => a.severity === 'blocking' && a.resolved).length;
  const isAllBlockingResolved = blockingCount === resolvedBlockingCount;

  const handleSelectOption = (ambId, option) => {
    setSelectedAnswers({ ...selectedAnswers, [ambId]: option });
    setCustomAnswers({ ...customAnswers, [ambId]: option });
  };

  const handleTriggerResolve = (amb) => {
    const answer = customAnswers[amb.id] || selectedAnswers[amb.id] || amb.default_assumption;
    if (!answer || !answer.trim()) return;

    onResolveQuestion({
      runId: goalModel.run_id,
      ambiguityId: amb.id,
      userAnswer: answer.trim(),
      applyAsConstraint: true,
      constraintType: constraintType
    });
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Overview Banner */}
      <section className="card-panel" style={{ padding: '24px', backgroundColor: '#0D1526', border: '1px solid rgba(255, 255, 255, 0.08)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '16px', flexWrap: 'wrap', gap: '12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{
              width: '38px',
              height: '38px',
              borderRadius: '8px',
              background: isAllBlockingResolved ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)',
              border: `1px solid ${isAllBlockingResolved ? 'rgba(16, 185, 129, 0.3)' : 'rgba(239, 68, 68, 0.3)'}`,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}>
              {isAllBlockingResolved ? <ShieldCheck size={20} color="#34D399" /> : <AlertTriangle size={20} color="#F87171" />}
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span className="badge badge-purple">State 2.1: Clarifications</span>
                <span className="badge badge-slate">Run {goalModel?.run_id}</span>
              </div>
              <h2 style={{ fontSize: '1.25rem', fontWeight: 700, color: '#F8FAFC', marginTop: '2px', margin: 0 }}>
                Ambiguity Detection & Human Clarifications
              </h2>
            </div>
          </div>

          {/* Proceed Button if all blocking resolved */}
          {isAllBlockingResolved && (
            <button 
              type="button"
              onClick={onProceedToConfirmation}
              className="btn btn-emerald"
              style={{ padding: '8px 18px', fontWeight: 600 }}
            >
              <span>Proceed to Confirmation Gate</span>
              <ArrowRight size={14} />
            </button>
          )}
        </div>

        <p style={{ fontSize: '0.85rem', color: '#94A3B8', lineHeight: '1.5', margin: '0 0 16px 0' }}>
          The requirement analyst identified ambiguous or underspecified constraints. Resolving questions injects explicit guardrails directly into the Goal Model before code generation.
        </p>

        {/* Progress Bar */}
        <div style={{
          backgroundColor: 'rgba(255, 255, 255, 0.03)',
          border: '1px solid rgba(255, 255, 255, 0.07)',
          borderRadius: '8px',
          padding: '12px 16px',
          display: 'flex',
          alignItems: 'center',
          gap: '16px'
        }}>
          <div style={{ flex: 1 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', marginBottom: '6px' }}>
              <span style={{ color: '#F1F5F9', fontWeight: 600 }}>Blocking Clarifications Status:</span>
              <span className="font-mono" style={{ color: isAllBlockingResolved ? '#34D399' : '#F87171', fontWeight: 700 }}>
                {resolvedBlockingCount} of {blockingCount} Resolved
              </span>
            </div>
            <div style={{ width: '100%', height: '8px', backgroundColor: 'rgba(255, 255, 255, 0.1)', borderRadius: '9999px', overflow: 'hidden' }}>
              <div style={{
                width: `${blockingCount > 0 ? (resolvedBlockingCount / blockingCount) * 100 : 100}%`,
                height: '100%',
                backgroundColor: isAllBlockingResolved ? '#10B981' : '#EF4444',
                borderRadius: '9999px',
                transition: 'width 0.4s ease'
              }} />
            </div>
          </div>
          <span className={`badge ${isAllBlockingResolved ? 'badge-emerald' : 'badge-rose'}`} style={{ fontSize: '0.7rem' }}>
            {isAllBlockingResolved ? 'Gate Unlocked' : 'Gate Blocked'}
          </span>
        </div>
      </section>

      {/* Ambiguity Question Cards List */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {ambiguities.length === 0 ? (
          <section className="card-panel" style={{ padding: '36px 24px', textAlign: 'center', backgroundColor: '#0D1526', border: '1px solid rgba(255, 255, 255, 0.08)' }}>
            <CheckCircle2 size={32} color="#34D399" style={{ margin: '0 auto 12px auto' }} />
            <h3 style={{ fontSize: '1.1rem', fontWeight: 600, color: '#F1F5F9', marginBottom: '6px' }}>
              No Ambiguities Detected
            </h3>
            <p style={{ fontSize: '0.85rem', color: '#94A3B8', maxWidth: '480px', margin: '0 auto 16px auto' }}>
              The requirement parser found sufficient explicit parameters to proceed without blocking questions.
            </p>
            <button type="button" onClick={onProceedToConfirmation} className="btn btn-primary">
              <span>Go to Confirmation Gate</span>
              <ArrowRight size={14} />
            </button>
          </section>
        ) : (
          ambiguities.map((amb) => {
            const isBlocking = amb.severity === 'blocking';
            const isResolving = resolvingId === amb.id;
            const currentVal = customAnswers[amb.id] !== undefined ? customAnswers[amb.id] : (amb.user_answer || '');

            return (
              <div 
                key={amb.id}
                className="card-panel"
                style={{
                  padding: '20px',
                  backgroundColor: '#0D1526',
                  border: `1px solid ${amb.resolved ? 'rgba(16, 185, 129, 0.3)' : (isBlocking ? 'rgba(239, 68, 68, 0.3)' : 'rgba(245, 158, 11, 0.3)')}`,
                  position: 'relative'
                }}
              >
                {/* Card Header */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '10px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span className="font-mono" style={{ fontSize: '0.75rem', color: '#94A3B8', backgroundColor: 'rgba(255, 255, 255, 0.05)', border: '1px solid rgba(255, 255, 255, 0.1)', padding: '2px 6px', borderRadius: '4px' }}>
                      {amb.id}
                    </span>
                    <span className={`badge ${amb.resolved ? 'badge-emerald' : (isBlocking ? 'badge-rose' : 'badge-amber')}`}>
                      {amb.resolved ? 'Resolved' : (isBlocking ? 'Blocking Ambiguity' : 'Non-Blocking Guideline')}
                    </span>
                  </div>

                  {amb.resolved && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.75rem', color: '#34D399', fontWeight: 600 }}>
                      <CheckCircle2 size={14} />
                      <span>Applied to Goal Model</span>
                    </div>
                  )}
                </div>

                {/* Question */}
                <h3 style={{ fontSize: '1.05rem', fontWeight: 600, color: '#F1F5F9', marginBottom: '6px', margin: '0 0 6px 0' }}>
                  {amb.question}
                </h3>

                {/* Context */}
                {amb.context && (
                  <p style={{ fontSize: '0.8rem', color: '#94A3B8', marginBottom: '14px', fontStyle: 'italic', margin: '0 0 14px 0' }}>
                    Rationale: {amb.context}
                  </p>
                )}

                {/* If already resolved */}
                {amb.resolved ? (
                  <div style={{
                    backgroundColor: 'rgba(16, 185, 129, 0.08)',
                    border: '1px solid rgba(16, 185, 129, 0.25)',
                    borderRadius: '6px',
                    padding: '12px 14px',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '4px'
                  }}>
                    <span style={{ fontSize: '0.7rem', color: '#94A3B8', textTransform: 'uppercase', fontWeight: 600 }}>
                      Confirmed Resolution:
                    </span>
                    <div className="font-mono" style={{ fontSize: '0.85rem', color: '#34D399', fontWeight: 600 }}>
                      {amb.user_answer}
                    </div>
                    {amb.resolved_at && (
                      <span style={{ fontSize: '0.675rem', color: '#94A3B8', marginTop: '2px' }}>
                        Timestamp: {new Date(amb.resolved_at).toLocaleTimeString()}
                      </span>
                    )}
                  </div>
                ) : (
                  /* Interactive Answer Options */
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                    {/* Suggested Options Pills */}
                    {amb.suggested_options && amb.suggested_options.length > 0 && (
                      <div>
                        <div style={{ fontSize: '0.725rem', color: '#94A3B8', textTransform: 'uppercase', marginBottom: '6px', fontWeight: 500 }}>
                          Suggested Options (Click to select):
                        </div>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                          {amb.suggested_options.map((opt) => (
                            <button
                              key={opt}
                              type="button"
                              onClick={() => handleSelectOption(amb.id, opt)}
                              className={`btn btn-sm ${currentVal === opt ? 'btn-primary' : 'btn-secondary'}`}
                              style={{ fontSize: '0.775rem' }}
                            >
                              {opt}
                            </button>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Default assumption note */}
                    {amb.default_assumption && (
                      <div style={{ fontSize: '0.75rem', color: '#94A3B8', display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <span>Default fallback if unspecified:</span>
                        <span className="font-mono" style={{ color: '#F1F5F9', fontWeight: 600 }}>{amb.default_assumption}</span>
                      </div>
                    )}

                    {/* Freeform Answer Input */}
                    <div style={{ display: 'flex', gap: '8px', marginTop: '4px' }}>
                      <input 
                        type="text"
                        value={currentVal}
                        onChange={(e) => setCustomAnswers({ ...customAnswers, [amb.id]: e.target.value })}
                        placeholder={amb.default_assumption ? `Enter custom resolution or use: ${amb.default_assumption}` : "Enter custom clarification decision..."}
                        style={{
                          flex: 1,
                          padding: '8px 12px',
                          backgroundColor: '#060A14',
                          border: '1px solid rgba(255, 255, 255, 0.1)',
                          borderRadius: '6px',
                          color: '#F1F5F9',
                          fontSize: '0.85rem',
                          outline: 'none'
                        }}
                      />
                      <button 
                        type="button"
                        onClick={() => handleTriggerResolve(amb)}
                        disabled={isResolving || !currentVal.trim()}
                        className={isBlocking ? "btn btn-danger" : "btn btn-primary"}
                        style={{ padding: '8px 16px' }}
                      >
                        <Send size={13} />
                        <span>{isResolving ? 'Applying...' : 'Resolve & Patch'}</span>
                      </button>
                    </div>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
