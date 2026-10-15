import React from 'react';
import { 
  Cpu, 
  Settings, 
  RotateCcw, 
  Sparkles, 
  ShieldCheck, 
  FileCode2, 
  Layers, 
  BarChart3, 
  FlaskConical, 
  Database,
  Sun,
  Moon,
  Route,
  Activity
} from 'lucide-react';

const STAGES = [
  { id: 'input', label: '1. Workspace', icon: Database },
  { id: 'goal_model', label: '2. Requirements', icon: Layers },
  { id: 'planner', label: '3. Planner', icon: Cpu },
  { id: 'coder', label: '4. Coding Agent', icon: FileCode2 },
  { id: 'testing', label: '5. Test & Debug', icon: FlaskConical },
  { id: 'verifier', label: '6. Code Review', icon: ShieldCheck },
  { id: 'evaluations', label: '7. Evaluation', icon: BarChart3 },
  { id: 'performance', label: '8. Agent Performance', icon: Activity },
];

export default function Header({
  runId,
  currentStage,
  activeTab,
  setActiveTab,
  ollamaStatus,
  onOpenSettings,
  onReset,
  onRunFullPipeline,
  onStepNext,
  isRunning,
  hasRun,
  runsList = [],
  onSelectRun,
  theme = 'dark',
  onToggleTheme,
  onOpenTour
}) {
  return (
    <header className="app-header" style={{
      backgroundColor: 'rgba(10, 15, 29, 0.88)',
      backdropFilter: 'blur(16px)',
      WebkitBackdropFilter: 'blur(16px)',
      borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
      position: 'sticky',
      top: 0,
      zIndex: 50,
      boxShadow: '0 4px 20px rgba(0, 0, 0, 0.4)'
    }}>
      {/* Top Application Header Row */}
      <div className="app-header-top" style={{
        padding: '12px 24px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        borderBottom: '1px solid rgba(255, 255, 255, 0.06)',
        gap: '16px',
        flexWrap: 'wrap'
      }}>
        {/* Brand & Platform Identity */}
        <div className="app-header-brand" style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div className="app-header-brand-mark" style={{
            width: '36px',
            height: '36px',
            borderRadius: '10px',
            background: 'linear-gradient(135deg, #6366F1 0%, #8B5CF6 100%)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#FFFFFF',
            boxShadow: '0 0 16px rgba(99, 102, 241, 0.45)',
            border: '1px solid rgba(255, 255, 255, 0.2)'
          }}>
            <Cpu size={19} />
          </div>
          <div className="app-header-brand-copy">
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ 
                fontFamily: 'var(--font-heading, "Plus Jakarta Sans")', 
                fontSize: '1.1rem', 
                fontWeight: 700, 
                color: '#F8FAFC',
                letterSpacing: '-0.02em'
              }}>
                HorizonLab
              </span>
              <span className="badge badge-purple" style={{ 
                fontSize: '0.65rem', 
                padding: '2px 8px',
                background: 'rgba(99, 102, 241, 0.15)',
                color: '#A5B4FC',
                border: '1px solid rgba(99, 102, 241, 0.3)'
              }}>
                Autonomous Developer Platform
              </span>
            </div>
            <p style={{ fontSize: '0.72rem', color: '#94A3B8', margin: 0 }}>
              Closed-Loop Coding, Test Diagnostics, Recovery & Independent Verification
            </p>
          </div>
        </div>

        {/* Global Action & Status Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
          {/* Active / Previous Run Selector */}
          {runsList.length > 0 && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <label htmlFor="run-selector" style={{ fontSize: '0.75rem', color: '#94A3B8', fontWeight: 500 }}>
                Run:
              </label>
              <select
                id="run-selector"
                value={runId || ''}
                onChange={(e) => onSelectRun && onSelectRun(e.target.value)}
                style={{
                  backgroundColor: '#0F172A',
                  color: '#F1F5F9',
                  border: '1px solid rgba(255, 255, 255, 0.12)',
                  borderRadius: '6px',
                  padding: '5px 10px',
                  fontSize: '0.75rem',
                  fontFamily: 'var(--font-mono, monospace)',
                  outline: 'none',
                  cursor: 'pointer',
                  maxWidth: '220px'
                }}
              >
                <option value="">-- Recent Runs ({runsList.length}) --</option>
                {runsList.map((r) => (
                  <option key={r.run_id} value={r.run_id}>
                    {r.run_id} ({r.title ? r.title.slice(0, 20) : 'Run'}) [{r.status}]
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Ollama Connection Pill */}
          <button 
            type="button"
            className="app-header-model-status"
            onClick={onOpenSettings}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              backgroundColor: ollamaStatus?.connected ? 'rgba(16, 185, 129, 0.12)' : 'rgba(239, 68, 68, 0.12)',
              border: `1px solid ${ollamaStatus?.connected ? 'rgba(16, 185, 129, 0.3)' : 'rgba(239, 68, 68, 0.3)'}`,
              padding: '5px 10px',
              borderRadius: '9999px',
              cursor: 'pointer',
              fontSize: '0.725rem',
              color: ollamaStatus?.connected ? '#34D399' : '#F87171',
              fontWeight: 600,
              transition: 'all 0.15s ease'
            }}
            title="Click to configure model settings"
          >
            <span style={{
              width: '7px',
              height: '7px',
              borderRadius: '50%',
              backgroundColor: ollamaStatus?.connected ? '#10B981' : '#EF4444',
              boxShadow: ollamaStatus?.connected ? '0 0 8px #10B981' : '0 0 8px #EF4444'
            }} />
            <span>
              {ollamaStatus?.connected ? `Ollama (${ollamaStatus?.current_model || 'active'})` : 'Ollama Offline'}
            </span>
            {ollamaStatus?.latency_ms && (
              <span style={{ color: '#94A3B8', fontSize: '0.65rem', fontWeight: 400 }}>
                {ollamaStatus.latency_ms}ms
              </span>
            )}
          </button>

          {/* Primary Run Full Pipeline Button */}
          <button
            type="button"
            className="btn btn-primary btn-sm"
            onClick={onRunFullPipeline}
            disabled={isRunning}
            style={{ 
              fontWeight: 600,
              background: 'linear-gradient(135deg, #6366F1 0%, #8B5CF6 100%)',
              border: '1px solid rgba(255, 255, 255, 0.2)',
              boxShadow: '0 0 16px rgba(99, 102, 241, 0.45)',
              color: '#FFFFFF'
            }}
          >
            <Sparkles size={14} />
            <span>{isRunning ? 'Running Full Pipeline...' : 'Run Full Pipeline'}</span>
          </button>

          {/* New Task Reset Button */}
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={onReset}
            disabled={isRunning}
            title="Start a new software engineering task"
            style={{
              backgroundColor: 'rgba(255, 255, 255, 0.05)',
              borderColor: 'rgba(255, 255, 255, 0.12)',
              color: '#F1F5F9'
            }}
          >
            <RotateCcw size={13} />
            <span>New Task</span>
          </button>

          <button
            type="button"
            className="btn btn-secondary btn-sm header-tour-button"
            onClick={onOpenTour}
            title="Walk through the existing workflow and its evidence"
            style={{
              backgroundColor: 'rgba(255, 255, 255, 0.05)',
              borderColor: 'rgba(255, 255, 255, 0.12)',
              color: '#F1F5F9'
            }}
          >
            <Route size={14} />
            <span>Guided Tour</span>
          </button>

          <button
            type="button"
            className="btn btn-ghost btn-sm header-theme-button"
            onClick={onToggleTheme}
            aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}
            title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}
            style={{ color: '#94A3B8' }}
          >
            {theme === 'dark' ? <Sun size={15} /> : <Moon size={15} />}
            <span>{theme === 'dark' ? 'Light' : 'Dark'}</span>
          </button>

          {/* Settings Button */}
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={onOpenSettings}
            title="Configure Ollama model & inference parameters"
            style={{ padding: '6px 8px', color: '#94A3B8' }}
          >
            <Settings size={15} />
          </button>
        </div>
      </div>

      {/* Stage Navigation & Workflow Tabs Row */}
      <div className="app-header-navigation" style={{
        padding: '0 24px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        overflowX: 'auto',
        backgroundColor: 'rgba(10, 15, 29, 0.6)'
      }}>
        <nav className="app-stage-navigation" aria-label="Workflow navigation" style={{ display: 'flex', gap: '4px', minWidth: 'max-content' }}>
          {STAGES.map((stage) => {
            const Icon = stage.icon;
            const isActive = activeTab === stage.id;
            return (
              <button
                key={stage.id}
                type="button"
                className={`app-stage-tab${isActive ? ' is-active' : ''}`}
                aria-current={isActive ? 'step' : undefined}
                onClick={() => setActiveTab(stage.id)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '7px',
                  padding: '9px 14px',
                  fontSize: '0.8rem',
                  fontFamily: 'var(--font-heading, "Plus Jakarta Sans")',
                  fontWeight: isActive ? 700 : 500,
                  color: isActive ? '#FFFFFF' : '#94A3B8',
                  background: isActive ? 'rgba(99, 102, 241, 0.16)' : 'transparent',
                  border: 'none',
                  borderBottom: `2px solid ${isActive ? '#6366F1' : 'transparent'}`,
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                  borderRadius: '6px 6px 0 0',
                  boxShadow: isActive ? 'inset 0 1px 0 rgba(255, 255, 255, 0.1)' : 'none'
                }}
              >
                <Icon size={14} color={isActive ? '#818CF8' : '#64748B'} />
                <span>{stage.label}</span>
              </button>
            );
          })}
        </nav>

        {/* Compact Active Run Indicator */}
        {runId && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '6px 0', fontSize: '0.725rem' }}>
            <span style={{ color: '#94A3B8' }}>Active Run:</span>
            <span className="badge badge-purple" style={{ 
              fontSize: '0.7rem',
              background: 'rgba(99, 102, 241, 0.15)',
              color: '#A5B4FC',
              borderColor: 'rgba(99, 102, 241, 0.3)'
            }}>
              {runId}
            </span>
          </div>
        )}
      </div>
    </header>
  );
}
