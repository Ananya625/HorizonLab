import React, { useState } from 'react';
import { 
  HelpCircle, 
  AlertTriangle, 
  CheckCircle2, 
  ShieldCheck, 
  ArrowRight, 
  MessageSquare, 
  CornerDownRight, 
  SlidersHorizontal,
  Clock,
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
      <div className="card-panel" style={{ padding: '24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div style={{
              width: '36px',
              height: '36px',
              borderRadius: '8px',
              background: isAllBlockingResolved ? 'rgba(16, 185, 129, 0.1)' : 'rgba(244, 63, 94, 0.1)',
              border: `1px solid ${isAllBlockingResolved ? 'rgba(16, 185, 129, 0.3)' : 'rgba(244, 63, 94, 0.3)'}`,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}>
              {isAllBlockingResolved ? <ShieldCheck size={20} color="#10b981" /> : <AlertTriangle size={20} color="#f43f5e" />}
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span className="badge badge-amber">State 2.1: Clarifications</span>
                <span className="badge badge-purple">Run {goalModel?.run_id}</span>
              </div>
              <h2 style={{ fontSize: '1.25rem', fontWeight: 700, color: '#f8fafc', marginTop: '2px' }}>
                Ambiguity Detection & Human-in-the-Loop Clarifications
              </h2>
            </div>
          </div>

          {/* Proceed Button if all blocking resolved */}
          {isAllBlockingResolved && (
            <button 
              onClick={onProceedToConfirmation}
              className="btn btn-emerald"
              style={{ padding: '8px 18px', fontWeight: 600 }}
            >
              <span>Proceed to Confirmation Gate</span>
              <ArrowRight size={14} />
            </button>
          )}
        </div>

        <p style={{ fontSize: '0.85rem', color: '#94a3b8', lineHeight: '1.5', marginBottom: '16px' }}>
          AgentEval-X scans for underspecified parameters, missing safety boundaries, or unstated business rules before execution. Resolving ambiguities dynamically injects explicit constraints into the Goal Model.
        </p>

        {/* Progress Bar */}
        <div style={{
          backgroundColor: '#0a0f18',
          border: '1px solid #1e293b',
          borderRadius: '8px',
          padding: '12px 16px',
          display: 'flex',
          alignItems: 'center',
          gap: '16px'
        }}>
          <div style={{ flex: 1 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', marginBottom: '6px' }}>
              <span style={{ color: '#cbd5e1', fontWeight: 500 }}>Blocking Clarifications Status:</span>
              <span className="font-mono" style={{ color: isAllBlockingResolved ? '#10b981' : '#f43f5e', fontWeight: 600 }}>
                {resolvedBlockingCount} of {blockingCount} Resolved
              </span>
            </div>
            <div style={{ width: '100%', height: '6px', backgroundColor: '#1e293b', borderRadius: '3px', overflow: 'hidden' }}>
              <div style={{
                width: `${blockingCount > 0 ? (resolvedBlockingCount / blockingCount) * 100 : 100}%`,
                height: '100%',
                backgroundColor: isAllBlockingResolved ? '#10b981' : '#f43f5e',
                transition: 'width 0.4s'
              }} />
            </div>
          </div>
          <span className={`badge ${isAllBlockingResolved ? 'badge-emerald' : 'badge-rose'}`} style={{ fontSize: '0.7rem' }}>
            {isAllBlockingResolved ? 'Gate Unlocked' : 'Gate Blocked'}
          </span>
        </div>
      </div>

      {/* Ambiguity Question Cards List */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {ambiguities.length === 0 ? (
          <div className="card-panel" style={{ padding: '32px', textAlign: 'center' }}>
            <CheckCircle2 size={32} color="#10b981" style={{ margin: '0 auto 12px auto' }} />
            <h3 style={{ fontSize: '1.1rem', fontWeight: 600, color: '#f8fafc', marginBottom: '6px' }}>
              No Ambiguities Detected
            </h3>
            <p style={{ fontSize: '0.825rem', color: '#94a3b8', maxWidth: '480px', margin: '0 auto 16px auto' }}>
              The requirement parser found sufficient explicit parameters to proceed without blocking questions.
            </p>
            <button onClick={onProceedToConfirmation} className="btn btn-primary">
              <span>Go to Confirmation Gate</span>
              <ArrowRight size={14} />
            </button>
          </div>
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
                  backgroundColor: amb.resolved ? '#0c141e' : (isBlocking ? '#140f18' : '#0e1522'),
                  border: `1px solid ${amb.resolved ? 'rgba(16, 185, 129, 0.3)' : (isBlocking ? 'rgba(244, 63, 94, 0.4)' : 'rgba(245, 158, 11, 0.3)')}`,
                  position: 'relative'
                }}
              >
                {/* Card Header */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '10px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span className="font-mono" style={{ fontSize: '0.75rem', color: '#94a3b8', backgroundColor: '#182234', padding: '2px 6px', borderRadius: '4px' }}>
                      {amb.id}
                    </span>
                    <span className={`badge ${amb.resolved ? 'badge-emerald' : (isBlocking ? 'badge-rose' : 'badge-amber')}`}>
                      {amb.resolved ? 'Resolved' : (isBlocking ? 'Blocking Ambiguity' : 'Non-Blocking Guideline')}
                    </span>
                  </div>

                  {amb.resolved && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.75rem', color: '#10b981' }}>
                      <CheckCircle2 size={14} />
                      <span>Applied to Goal Model</span>
                    </div>
                  )}
                </div>

                {/* Question */}
                <h3 style={{ fontSize: '1.05rem', fontWeight: 600, color: '#f8fafc', marginBottom: '6px' }}>
                  {amb.question}
                </h3>

                {/* Context */}
                {amb.context && (
                  <p style={{ fontSize: '0.8rem', color: '#94a3b8', marginBottom: '14px', fontStyle: 'italic' }}>
                    Rationale: {amb.context}
                  </p>
                )}

                {/* If already resolved */}
                {amb.resolved ? (
                  <div style={{
                    backgroundColor: '#081219',
                    border: '1px solid rgba(16, 185, 129, 0.2)',
                    borderRadius: '6px',
                    padding: '12px 14px',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '4px'
                  }}>
                    <span style={{ fontSize: '0.7rem', color: '#64748b', textTransform: 'uppercase' }}>
                      Confirmed Resolution:
                    </span>
                    <div className="font-mono" style={{ fontSize: '0.85rem', color: '#34d399', fontWeight: 600 }}>
                      {amb.user_answer}
                    </div>
                    {amb.resolved_at && (
                      <span style={{ fontSize: '0.675rem', color: '#64748b', marginTop: '2px' }}>
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
                        <div style={{ fontSize: '0.725rem', color: '#64748b', textTransform: 'uppercase', marginBottom: '6px' }}>
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
                      <div style={{ fontSize: '0.75rem', color: '#64748b', display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <span>Default fallback if unspecified:</span>
                        <span className="font-mono" style={{ color: '#cbd5e1' }}>{amb.default_assumption}</span>
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
                          backgroundColor: '#070b12',
                          border: '1px solid #24344d',
                          borderRadius: '6px',
                          color: '#f8fafc',
                          fontSize: '0.85rem',
                          outline: 'none'
                        }}
                      />
                      <button 
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
