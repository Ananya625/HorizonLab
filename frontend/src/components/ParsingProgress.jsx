import React, { useState, useEffect } from 'react';
import { Loader2, CheckCircle2, Clock, Activity, Cpu } from 'lucide-react';

const STAGES = [
  { id: 1, label: 'Normalizing request & detecting language context', delay: 400 },
  { id: 2, label: 'Extracting invariant Hard Constraints & Soft Preferences', delay: 1200 },
  { id: 3, label: 'Decomposing Hierarchical Sub-Goals & Agent Roles', delay: 2000 },
  { id: 4, label: 'Formulating Measurable Success Criteria & Verification Metrics', delay: 2800 },
  { id: 5, label: 'Detecting Blocking Ambiguities & Clarification Questions', delay: 3500 }
];

export default function ParsingProgress({ modelName }) {
  const [currentStageIndex, setCurrentStageIndex] = useState(0);
  const [elapsedSec, setElapsedSec] = useState(0);

  useEffect(() => {
    const timer = setInterval(() => {
      setElapsedSec((prev) => prev + 1);
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    STAGES.forEach((stage, idx) => {
      setTimeout(() => {
        setCurrentStageIndex((prev) => Math.max(prev, idx));
      }, stage.delay);
    });
  }, []);

  return (
    <div className="card-panel" style={{ padding: '32px', marginBottom: '24px', textAlign: 'center' }}>
      <div style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', position: 'relative', marginBottom: '20px' }}>
        <div style={{
          width: '64px',
          height: '64px',
          borderRadius: '50%',
          border: '2px solid rgba(56, 189, 248, 0.2)',
          borderTopColor: '#38bdf8',
          animation: 'spin 1.2s linear infinite'
        }} />
        <Activity size={26} color="#38bdf8" style={{ position: 'absolute' }} />
      </div>

      <style>{`
        @keyframes spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
      `}</style>

      <h3 style={{ fontSize: '1.2rem', fontWeight: 700, color: '#f8fafc', marginBottom: '6px' }}>
        AgentEval-X Interpreter Active
      </h3>
      <p style={{ fontSize: '0.825rem', color: '#94a3b8', marginBottom: '24px' }}>
        Translating unstructured task specification via <span className="font-mono" style={{ color: '#38bdf8' }}>{modelName || 'Ollama'}</span> into a verified Goal Model
      </p>

      {/* Elapsed Telemetry */}
      <div style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '8px',
        backgroundColor: '#0c121d',
        border: '1px solid #1e293b',
        padding: '4px 12px',
        borderRadius: '20px',
        fontSize: '0.775rem',
        color: '#94a3b8',
        marginBottom: '24px'
      }}>
        <Clock size={13} color="#38bdf8" />
        <span>Elapsed Time: </span>
        <span className="font-mono" style={{ color: '#f8fafc', fontWeight: 600 }}>{elapsedSec}s</span>
      </div>

      {/* Progress Steps list */}
      <div style={{ maxWidth: '580px', margin: '0 auto', textAlign: 'left', display: 'flex', flexDirection: 'column', gap: '10px' }}>
        {STAGES.map((stage, idx) => {
          const isDone = idx < currentStageIndex;
          const isCurrent = idx === currentStageIndex;

          return (
            <div 
              key={stage.id}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '12px',
                padding: '10px 14px',
                borderRadius: '8px',
                backgroundColor: isCurrent ? 'rgba(56, 189, 248, 0.08)' : (isDone ? 'rgba(16, 185, 129, 0.04)' : '#0c121d'),
                border: `1px solid ${isCurrent ? 'rgba(56, 189, 248, 0.3)' : (isDone ? 'rgba(16, 185, 129, 0.2)' : '#1a2333')}`,
                transition: 'all 0.3s'
              }}
            >
              <div>
                {isDone ? (
                  <CheckCircle2 size={18} color="#10b981" />
                ) : isCurrent ? (
                  <Loader2 size={18} color="#38bdf8" style={{ animation: 'spin 1s linear infinite' }} />
                ) : (
                  <div style={{ width: '18px', height: '18px', borderRadius: '50%', border: '1px solid #334155' }} />
                )}
              </div>
              <div style={{ flex: 1 }}>
                <span style={{ 
                  fontSize: '0.825rem', 
                  color: isCurrent ? '#38bdf8' : (isDone ? '#cbd5e1' : '#64748b'),
                  fontWeight: isCurrent ? 600 : 400
                }}>
                  {stage.label}
                </span>
              </div>
              <span className="font-mono" style={{ fontSize: '0.7rem', color: '#64748b' }}>
                Stage {stage.id}/5
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
