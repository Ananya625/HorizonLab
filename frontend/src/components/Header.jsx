import React from 'react';
import { 
  Cpu, 
  Settings, 
  RotateCcw, 
  ShieldCheck, 
  FileCode2, 
  Layers, 
  Sparkles, 
  BarChart3, 
  FlaskConical, 
  Database
} from 'lucide-react';

const STAGES = [
  { id: 'input', label: '1. Workspace', icon: Database },
  { id: 'goal_model', label: '2. Requirements', icon: Layers },
  { id: 'planner', label: '3. Planner', icon: Cpu },
  { id: 'coder', label: '4. Coding Agent', icon: FileCode2 },
  { id: 'testing', label: '5. Test & Debug', icon: FlaskConical },
  { id: 'verifier', label: '6. Code Review', icon: ShieldCheck },
  { id: 'evaluations', label: '7. Evaluation', icon: BarChart3 },
];

export default function Header({
  runId,
  activeTab,
  setActiveTab,
  ollamaStatus,
  onOpenSettings,
  onReset,
  onRunFullPipeline,
  isRunning,
  runsList = [],
  onSelectRun
}) {
  return (
    <header style={{
      backgroundColor: '#0c101a',
      borderBottom: '1px solid #1e293b',
      position: 'sticky',
      top: 0,
      zIndex: 50,
      backdropFilter: 'blur(12px)',
      boxShadow: '0 4px 20px rgba(0, 0, 0, 0.4)'
    }}>
      {/* Top Telemetry & Global Controls Row */}
      <div style={{
        padding: '10px 24px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        borderBottom: '1px solid rgba(30, 41, 59, 0.6)'
      }}>
        {/* Logo & Platform Branding */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{
            width: '36px',
            height: '36px',
            borderRadius: '8px',
            background: 'linear-gradient(135deg, #0284c7 0%, #0369a1 50%, #4338ca 100%)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 0 15px rgba(2, 132, 199, 0.4)',
            border: '1px solid rgba(56, 189, 248, 0.4)'
          }}>
            <Cpu size={20} color="#ffffff" />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <h1 style={{ fontSize: '1.05rem', fontWeight: 700, letterSpacing: '-0.02em', color: '#ffffff' }}>
                AgentEval-X
              </h1>
              <span className="badge badge-cyan" style={{ fontSize: '0.65rem', padding: '1px 6px' }}>
                Autonomous SE Agent
              </span>
            </div>
            <p style={{ fontSize: '0.725rem', color: '#94a3b8' }}>
              Multi-Stage Coding, Testing, Bounded Recovery & Independent Verification
            </p>
          </div>
        </div>

        {/* Global Action Buttons */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          {/* Run History Quick Select */}
          {runsList.length > 0 && (
            <select
              value={runId || ''}
              onChange={(e) => onSelectRun && onSelectRun(e.target.value)}
              style={{
                backgroundColor: '#151d2e',
                color: '#cbd5e1',
                border: '1px solid #2a3b53',
                borderRadius: '6px',
                padding: '5px 10px',
                fontSize: '0.75rem',
                fontFamily: 'var(--font-mono)',
                outline: 'none',
                cursor: 'pointer'
              }}
            >
              <option value="">-- Recent Runs ({runsList.length}) --</option>
              {runsList.map((r) => (
                <option key={r.run_id} value={r.run_id}>
                  {r.run_id} ({r.title ? r.title.slice(0, 30) : 'Run'}) [{r.status}]
                </option>
              ))}
            </select>
          )}

          {/* Ollama Status Pill */}
          <div 
            onClick={onOpenSettings}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              backgroundColor: ollamaStatus?.connected ? 'rgba(16, 185, 129, 0.1)' : 'rgba(244, 63, 94, 0.1)',
              border: `1px solid ${ollamaStatus?.connected ? 'rgba(52, 211, 153, 0.3)' : 'rgba(244, 63, 94, 0.3)'}`,
              padding: '4px 10px',
              borderRadius: '9999px',
              cursor: 'pointer',
              fontSize: '0.725rem'
            }}
            title="Click to configure Ollama endpoint"
          >
            <span style={{
              width: '7px',
              height: '7px',
              borderRadius: '50%',
              backgroundColor: ollamaStatus?.connected ? '#10b981' : '#f43f5e',
              boxShadow: ollamaStatus?.connected ? '0 0 6px #10b981' : 'none'
            }} />
            <span style={{ color: ollamaStatus?.connected ? '#34d399' : '#fb7185', fontWeight: 600 }}>
              {ollamaStatus?.connected ? `Ollama (${ollamaStatus?.current_model || 'online'})` : 'Ollama Offline'}
            </span>
            {ollamaStatus?.latency_ms && (
              <span style={{ color: '#64748b', fontSize: '0.65rem' }}>{ollamaStatus.latency_ms}ms</span>
            )}
          </div>

          {/* Full Pipeline Action Button */}
          <button
            className="btn btn-primary btn-sm"
            onClick={onRunFullPipeline}
            disabled={isRunning}
            style={{
              background: 'linear-gradient(135deg, #2563eb 0%, #7c3aed 100%)',
              border: '1px solid rgba(167, 139, 250, 0.4)',
              boxShadow: '0 0 14px rgba(124, 58, 237, 0.35)',
              fontWeight: 600
            }}
          >
            <Sparkles size={14} />
            <span>{isRunning ? 'Running Multi-Agent Engine...' : '⚡ Run Full Autonomous Pipeline'}</span>
          </button>

          {/* Reset / New Task Button */}
          <button
            className="btn btn-secondary btn-sm"
            onClick={onReset}
            title="Start new software task"
          >
            <RotateCcw size={13} />
            <span>New Task</span>
          </button>

          {/* Settings Button */}
          <button
            className="btn btn-ghost btn-sm"
            onClick={onOpenSettings}
            title="Ollama Settings"
          >
            <Settings size={15} />
          </button>
        </div>
      </div>

      {/* Stage Stepper Navigation Bar */}
      <div style={{
        padding: '0 24px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        overflowX: 'auto',
        backgroundColor: '#0a0d14'
      }}>
        <nav style={{ display: 'flex', gap: '4px', minWidth: 'max-content' }}>
          {STAGES.map((stage) => {
            const Icon = stage.icon;
            const isActive = activeTab === stage.id;
            return (
              <button
                key={stage.id}
                onClick={() => setActiveTab(stage.id)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  padding: '10px 14px',
                  fontSize: '0.8rem',
                  fontWeight: isActive ? 600 : 500,
                  color: isActive ? '#38bdf8' : '#94a3b8',
                  background: isActive ? 'rgba(56, 189, 248, 0.08)' : 'transparent',
                  border: 'none',
                  borderBottom: `2px solid ${isActive ? '#38bdf8' : 'transparent'}`,
                  cursor: 'pointer',
                  transition: 'all 0.15s ease'
                }}
              >
                <Icon size={15} color={isActive ? '#38bdf8' : '#64748b'} />
                <span>{stage.label}</span>
              </button>
            );
          })}
        </nav>

        {/* Active Run Telemetry Badge */}
        {runId && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '6px 0' }}>
            <span style={{ fontSize: '0.725rem', color: '#64748b' }}>Active Run:</span>
            <span className="badge badge-purple" style={{ fontSize: '0.7rem' }}>
              {runId}
            </span>
          </div>
        )}
      </div>
    </header>
  );
}
