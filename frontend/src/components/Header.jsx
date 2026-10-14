import React from 'react';
import { 
  Cpu, 
  Settings, 
  RotateCcw, 
  Sparkles, 
  CheckCircle2, 
  ShieldCheck, 
  FileCode2, 
  Layers, 
  BarChart3, 
  FlaskConical, 
  Database,
  Terminal,
  Circle,
  Sun,
  Moon,
  Route
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
  theme = 'light',
  onToggleTheme,
  onOpenTour
}) {
  return (
    <header className="app-header" style={{
      backgroundColor: '#FFFFFF',
      borderBottom: '1px solid var(--border-subtle, #E5E7EF)',
      position: 'sticky',
      top: 0,
      zIndex: 50,
      boxShadow: '0 1px 3px rgba(16, 24, 40, 0.05)'
    }}>
      {/* Top Application Header Row */}
      <div className="app-header-top" style={{
        padding: '10px 24px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        borderBottom: '1px solid var(--border-subtle, #E5E7EF)',
        gap: '16px',
        flexWrap: 'wrap'
      }}>
        {/* Brand & Platform Identity */}
        <div className="app-header-brand" style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div className="app-header-brand-mark" style={{
            width: '34px',
            height: '34px',
            borderRadius: '8px',
            backgroundColor: 'var(--accent-primary, #6257D9)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#FFFFFF',
            boxShadow: '0 2px 6px rgba(98, 87, 217, 0.3)'
          }}>
            <Cpu size={18} />
          </div>
          <div className="app-header-brand-copy">
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ 
                fontFamily: 'var(--font-heading, "Plus Jakarta Sans")', 
                fontSize: '1.05rem', 
                fontWeight: 700, 
                color: 'var(--text-primary, #172033)',
                letterSpacing: '-0.02em'
              }}>
                HorizonLab
              </span>
              <span className="badge badge-purple" style={{ fontSize: '0.65rem', padding: '1px 6px' }}>
                Autonomous Developer Platform
              </span>
            </div>
            <p style={{ fontSize: '0.725rem', color: 'var(--text-secondary, #667085)', margin: 0 }}>
              Closed-Loop Coding, Test Diagnostics, Recovery & Independent Verification
            </p>
          </div>
        </div>

        {/* Global Action & Status Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
          {/* Active / Previous Run Selector */}
          {runsList.length > 0 && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <label htmlFor="run-selector" style={{ fontSize: '0.75rem', color: 'var(--text-secondary, #667085)', fontWeight: 500 }}>
                Run:
              </label>
              <select
                id="run-selector"
                value={runId || ''}
                onChange={(e) => onSelectRun && onSelectRun(e.target.value)}
                style={{
                  backgroundColor: '#F6F7FB',
                  color: 'var(--text-primary, #172033)',
                  border: '1px solid var(--border-subtle, #E5E7EF)',
                  borderRadius: '6px',
                  padding: '5px 10px',
                  fontSize: '0.75rem',
                  fontFamily: 'var(--font-mono, monospace)',
                  outline: 'none',
                  cursor: 'pointer',
                  maxWidth: '240px'
                }}
              >
                <option value="">-- Recent Runs ({runsList.length}) --</option>
                {runsList.map((r) => (
                  <option key={r.run_id} value={r.run_id}>
                    {r.run_id} ({r.title ? r.title.slice(0, 24) : 'Run'}) [{r.status}]
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
              backgroundColor: ollamaStatus?.connected ? '#ECFDF5' : '#FEF2F2',
              border: `1px solid ${ollamaStatus?.connected ? '#A7F3D0' : '#FECACA'}`,
              padding: '5px 10px',
              borderRadius: '9999px',
              cursor: 'pointer',
              fontSize: '0.725rem',
              color: ollamaStatus?.connected ? '#16845B' : '#D14343',
              fontWeight: 600
            }}
            title="Click to configure model settings"
          >
            <span style={{
              width: '7px',
              height: '7px',
              borderRadius: '50%',
              backgroundColor: ollamaStatus?.connected ? '#16845B' : '#D14343'
            }} />
            <span>
              {ollamaStatus?.connected ? `Ollama (${ollamaStatus?.current_model || 'active'})` : 'Ollama Offline'}
            </span>
            {ollamaStatus?.latency_ms && (
              <span style={{ color: 'var(--text-secondary, #667085)', fontSize: '0.65rem', fontWeight: 400 }}>
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
            style={{ fontWeight: 600 }}
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
          >
            <RotateCcw size={13} />
            <span>New Task</span>
          </button>

          <button
            type="button"
            className="btn btn-secondary btn-sm header-tour-button"
            onClick={onOpenTour}
            title="Walk through the existing workflow and its evidence"
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
            style={{ padding: '6px 8px' }}
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
        backgroundColor: '#FFFFFF'
      }}>
        <nav className="app-stage-navigation" aria-label="Workflow navigation" style={{ display: 'flex', gap: '2px', minWidth: 'max-content' }}>
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
                  padding: '10px 14px',
                  fontSize: '0.8rem',
                  fontFamily: 'var(--font-heading, "Plus Jakarta Sans")',
                  fontWeight: isActive ? 700 : 500,
                  color: isActive ? 'var(--accent-primary, #6257D9)' : 'var(--text-secondary, #667085)',
                  background: isActive ? 'var(--accent-primary-subtle, #F0EEFF)' : 'transparent',
                  border: 'none',
                  borderBottom: `2px solid ${isActive ? 'var(--accent-primary, #6257D9)' : 'transparent'}`,
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                  borderRadius: '4px 4px 0 0'
                }}
              >
                <Icon size={14} color={isActive ? '#6257D9' : '#667085'} />
                <span>{stage.label}</span>
              </button>
            );
          })}
        </nav>

        {/* Compact Active Run Indicator */}
        {runId && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '6px 0', fontSize: '0.725rem' }}>
            <span style={{ color: 'var(--text-secondary, #667085)' }}>Active Run:</span>
            <span className="badge badge-purple" style={{ fontSize: '0.7rem' }}>
              {runId}
            </span>
          </div>
        )}
      </div>
    </header>
  );
}
