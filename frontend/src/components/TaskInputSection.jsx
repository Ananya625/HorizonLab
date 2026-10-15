import React, { useState, useEffect } from 'react';
import { 
  FolderGit2, 
  Terminal, 
  Sparkles, 
  ArrowRight, 
  Code2, 
  FolderOpen,
  ChevronDown,
  ChevronUp,
  Layers,
  FileCode,
  Box,
  GitBranch,
  Bot,
  ShieldCheck,
  Bug,
  KeyRound,
  Clock,
  Activity,
  Cpu,
  Check,
  ChevronRight,
  Database,
  FlaskConical,
  BarChart3,
  ExternalLink
} from 'lucide-react';
import { inspectWorkspace, fetchSampleRepos } from '../services/api';
const agentMascot = '/agent-mascot.png';

export default function TaskInputSection({
  taskPrompt,
  setTaskPrompt,
  presets = [],
  onAnalyze,
  onRunFullPipeline,
  loading,
  error,
  ollamaStatus,
  selectedLanguage,
  setSelectedLanguage,
  repoPath,
  setRepoPath,
  maxRecoveryRetries,
  setMaxRecoveryRetries,
  goalModel,
  currentRunRecord,
  runId,
  logs = [],
  runsList = [],
  onSelectRun,
  onNavigateTab,
  plan,
  codeChanges = [],
  testResults = [],
  recoveryAttempts = [],
  verification
}) {
  const [sampleRepos, setSampleRepos] = useState([]);
  const [repoInspection, setRepoInspection] = useState(null);
  const [inspectingRepo, setInspectingRepo] = useState(false);
  const [selectedPresetId, setSelectedPresetId] = useState(null);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isPresetsOpen, setIsPresetsOpen] = useState(true);

  // Load sample repositories
  useEffect(() => {
    fetchSampleRepos()
      .then((data) => {
        const repos = data.repositories || [];
        setSampleRepos(repos);
      })
      .catch((err) => console.warn('Failed to load sample repos:', err));
  }, []);

  // Inspect workspace directory whenever repoPath changes
  useEffect(() => {
    if (!repoPath) {
      setRepoInspection(null);
      return;
    }
    setInspectingRepo(true);
    inspectWorkspace(repoPath)
      .then((data) => setRepoInspection(data))
      .catch((err) => console.warn('Workspace inspection error:', err))
      .finally(() => setInspectingRepo(false));
  }, [repoPath]);

  const handleSelectPreset = (preset) => {
    setSelectedPresetId(preset.id);
    setTaskPrompt(preset.prompt);
  };

  const languageLabel = {
    auto: 'Auto detect',
    en: 'English',
    py: 'Python',
    ts: 'TypeScript'
  }[selectedLanguage] || selectedLanguage || 'Auto detect';

  const getPresetIcon = (category = '') => {
    const normalized = category.toLowerCase();
    if (normalized.includes('security') || normalized.includes('auth')) return ShieldCheck;
    if (normalized.includes('debug') || normalized.includes('concurrency')) return Bug;
    if (normalized.includes('refactor') || normalized.includes('architecture')) return GitBranch;
    if (normalized.includes('api')) return KeyRound;
    return FileCode;
  };

  // Determine stage execution status for current task
  const hasRequirements = !!goalModel;
  const hasPlan = !!plan;
  const hasCode = codeChanges.length > 0;
  const latestTest = testResults.length > 0 ? testResults[testResults.length - 1] : null;
  const hasTesting = !!latestTest;
  const hasVerification = !!verification;

  return (
    <div className="workspace-view" style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      
      {/* 1. Welcoming Hero Card with 3D AI Robot Mascot */}
      <section 
        className="card-panel workspace-hero-card"
        style={{
          background: 'linear-gradient(135deg, rgba(17, 26, 46, 0.95) 0%, rgba(13, 21, 38, 0.9) 100%)',
          border: '1px solid rgba(255, 255, 255, 0.08)',
          borderRadius: '16px',
          padding: '24px 32px',
          display: 'grid',
          gridTemplateColumns: '1fr minmax(240px, 320px)',
          alignItems: 'center',
          gap: '28px',
          position: 'relative',
          overflow: 'hidden',
          boxShadow: '0 8px 32px rgba(0, 0, 0, 0.4), inset 0 1px 0 rgba(255, 255, 255, 0.1)'
        }}
      >
        {/* Ambient background light orb */}
        <div style={{
          position: 'absolute',
          top: '-40px',
          right: '180px',
          width: '240px',
          height: '240px',
          borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(99, 102, 241, 0.25) 0%, transparent 70%)',
          pointerEvents: 'none',
          zIndex: 0
        }} />

        {/* Left Side: Greeting & Quick Access */}
        <div style={{ position: 'relative', zIndex: 1, display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
              <span className="badge badge-purple" style={{ 
                fontSize: '0.68rem',
                background: 'rgba(99, 102, 241, 0.18)',
                color: '#A5B4FC',
                border: '1px solid rgba(99, 102, 241, 0.35)'
              }}>
                HorizonLab Agent OS
              </span>
              <span style={{ fontSize: '0.75rem', color: '#94A3B8' }}>
                Autonomous Developer Workspace
              </span>
            </div>
            <h1 style={{ 
              fontSize: '1.8rem', 
              fontFamily: 'var(--font-heading, "Plus Jakarta Sans")', 
              fontWeight: 800, 
              color: '#FFFFFF',
              letterSpacing: '-0.02em',
              lineHeight: '1.2',
              marginBottom: '8px'
            }}>
              Hello Engineer <span style={{ display: 'inline-block' }}>👋</span>
            </h1>
            <p style={{ fontSize: '0.925rem', color: '#94A3B8', lineHeight: '1.5', margin: 0, maxWidth: '580px' }}>
              Your autonomous coding agent is ready. Describe your task, and HorizonLab will plan, implement, run test diagnostics, self-heal failures, and independently verify requirements.
            </p>
          </div>

          {/* Quick Action Navigation Buttons */}
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', paddingTop: '4px' }}>
            <button
              type="button"
              onClick={() => {
                const el = document.getElementById('task-prompt-input');
                if (el) { el.focus(); el.scrollIntoView({ behavior: 'smooth' }); }
              }}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '8px',
                padding: '9px 14px',
                background: 'rgba(99, 102, 241, 0.12)',
                border: '1px solid rgba(99, 102, 241, 0.3)',
                borderRadius: '8px',
                color: '#E0E7FF',
                fontSize: '0.8rem',
                fontWeight: 600,
                cursor: 'pointer',
                transition: 'all 0.15s ease'
              }}
            >
              <Code2 size={15} color="#818CF8" />
              <span>Start a new task</span>
              <ChevronRight size={13} color="#818CF8" />
            </button>

            <button
              type="button"
              onClick={() => {
                const el = document.getElementById('quick-presets-section');
                if (el) el.scrollIntoView({ behavior: 'smooth' });
              }}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '8px',
                padding: '9px 14px',
                background: 'rgba(255, 255, 255, 0.04)',
                border: '1px solid rgba(255, 255, 255, 0.1)',
                borderRadius: '8px',
                color: '#F1F5F9',
                fontSize: '0.8rem',
                fontWeight: 500,
                cursor: 'pointer',
                transition: 'all 0.15s ease'
              }}
            >
              <FileCode size={15} color="#38BDF8" />
              <span>Browse presets ({presets.length})</span>
              <ChevronRight size={13} color="#94A3B8" />
            </button>

            <button
              type="button"
              onClick={() => setIsSettingsOpen(!isSettingsOpen)}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '8px',
                padding: '9px 14px',
                background: 'rgba(255, 255, 255, 0.04)',
                border: '1px solid rgba(255, 255, 255, 0.1)',
                borderRadius: '8px',
                color: '#F1F5F9',
                fontSize: '0.8rem',
                fontWeight: 500,
                cursor: 'pointer',
                transition: 'all 0.15s ease'
              }}
            >
              <FolderGit2 size={15} color="#34D399" />
              <span>{repoPath ? `Workspace: ${repoPath.slice(0, 18)}...` : 'Isolated Sandbox'}</span>
              <ChevronDown size={13} color="#94A3B8" />
            </button>
          </div>
        </div>

        {/* Right Side: 3D AI Robot Mascot Asset */}
        <div style={{
          position: 'relative',
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          zIndex: 1
        }}>
          <div style={{
            position: 'relative',
            width: '240px',
            height: '240px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}>
            {/* Subtle glow underneath */}
            <div style={{
              position: 'absolute',
              bottom: '10px',
              width: '180px',
              height: '40px',
              borderRadius: '50%',
              background: 'radial-gradient(ellipse, rgba(6, 182, 212, 0.4) 0%, rgba(99, 102, 241, 0.2) 60%, transparent 80%)',
              filter: 'blur(10px)',
              zIndex: 0
            }} />
            <img 
              src={agentMascot} 
              alt="HorizonLab 3D AI Coding Mascot"
              style={{
                width: '100%',
                height: '100%',
                objectFit: 'contain',
                position: 'relative',
                zIndex: 1,
                filter: 'drop-shadow(0 12px 24px rgba(0, 0, 0, 0.5))'
              }}
            />
          </div>
        </div>
      </section>

      {/* 2. Main Dashboard 2-Column Grid */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'minmax(0, 1fr) 340px',
        gap: '20px',
        alignItems: 'start'
      }}>
        
        {/* Left Column: Task Composer Area */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>

          {/* Task Composer Section */}
          <section 
            className="card-panel workspace-composer"
            style={{ 
              padding: '26px 28px', 
              backgroundColor: '#0D1526',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              borderRadius: '16px',
              display: 'flex',
              flexDirection: 'column',
              gap: '18px',
              boxShadow: '0 8px 32px rgba(0, 0, 0, 0.35)'
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <label 
                htmlFor="task-prompt-input" 
                style={{ 
                  fontSize: '0.9rem', 
                  fontWeight: 700, 
                  color: '#F8FAFC',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px'
                }}
              >
                <Terminal size={17} color="#818CF8" />
                <span>Task Specification & Goal Description</span>
              </label>
              <span className="workspace-prompt-count" style={{ fontSize: '0.75rem', color: '#94A3B8' }} aria-live="polite">
                {taskPrompt.length.toLocaleString()} characters
              </span>
            </div>

            {/* Prompt Textarea */}
            <div style={{ position: 'relative' }}>
              <textarea
                id="task-prompt-input"
                value={taskPrompt}
                onChange={(e) => {
                  setTaskPrompt(e.target.value);
                  setSelectedPresetId(null);
                }}
                placeholder="Describe your goal in detail. HorizonLab will analyze requirements, break it into subgoals, generate code, and verify."
                rows={9}
                className="workspace-prompt-editor"
                aria-describedby="goal-breakdown-caption"
                style={{
                  width: '100%',
                  minHeight: '220px',
                  backgroundColor: '#060A14',
                  border: '1px solid rgba(255, 255, 255, 0.12)',
                  borderRadius: '12px',
                  padding: '18px 20px',
                  color: '#F1F5F9',
                  fontSize: '0.95rem',
                  fontFamily: 'var(--font-sans)',
                  lineHeight: '1.65',
                  resize: 'vertical',
                  outline: 'none',
                  boxShadow: 'inset 0 2px 6px rgba(0, 0, 0, 0.5)',
                  transition: 'border-color 0.15s ease, box-shadow 0.15s ease'
                }}
              />
            </div>

            {/* Execution Controls Row */}
            <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
              <button
                type="button"
                className="btn btn-primary workspace-run-button"
                onClick={onRunFullPipeline}
                disabled={loading || !taskPrompt.trim()}
                style={{ 
                  flex: '1 1 240px', 
                  padding: '12px 22px', 
                  fontSize: '0.88rem',
                  fontWeight: 600,
                  gap: '8px',
                  background: 'linear-gradient(135deg, #6366F1 0%, #8B5CF6 100%)',
                  border: '1px solid rgba(255, 255, 255, 0.2)',
                  boxShadow: '0 0 20px rgba(99, 102, 241, 0.45)',
                  color: '#FFFFFF'
                }}
              >
                <Sparkles size={16} />
                <span>{loading ? 'Running Full Pipeline...' : 'Run Full Autonomous Pipeline'}</span>
              </button>

              <button
                type="button"
                className="btn btn-secondary"
                onClick={onAnalyze}
                disabled={loading || !taskPrompt.trim()}
                style={{ 
                  flex: '1 1 200px', 
                  padding: '12px 18px', 
                  fontSize: '0.85rem',
                  fontWeight: 600,
                  gap: '8px',
                  backgroundColor: 'rgba(255, 255, 255, 0.05)',
                  borderColor: 'rgba(255, 255, 255, 0.12)',
                  color: '#F1F5F9'
                }}
              >
                <span>Analyze Requirements (Stage 2)</span>
                <ArrowRight size={15} />
              </button>
            </div>

            {error && (
              <div role="alert" style={{
                padding: '12px 16px',
                backgroundColor: 'rgba(239, 68, 68, 0.12)',
                border: '1px solid rgba(239, 68, 68, 0.3)',
                borderRadius: '8px',
                fontSize: '0.825rem',
                color: '#F87171'
              }}>
                {error}
              </div>
            )}
          </section>

          {/* Execution Settings (Sandbox / Target Workspace) */}
          <details 
            className="workspace-settings"
            open={isSettingsOpen}
            onToggle={(e) => setIsSettingsOpen(e.currentTarget.open)}
            style={{
              backgroundColor: '#0D1526',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              borderRadius: '12px',
              padding: '14px 18px'
            }}
          >
            <summary style={{ 
              cursor: 'pointer', 
              display: 'flex', 
              justifyContent: 'space-between', 
              alignItems: 'center',
              userSelect: 'none',
              listStyle: 'none'
            }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#F1F5F9', fontSize: '0.85rem', fontWeight: 600 }}>
                <FolderGit2 size={16} color="#818CF8" />
                <span>Execution Settings & Target Workspace</span>
              </span>
              <span style={{ fontSize: '0.75rem', color: '#94A3B8', display: 'flex', alignItems: 'center', gap: '4px' }}>
                <span>{repoPath ? `Workspace: ${repoPath}` : 'Isolated Sandbox'} · {languageLabel}</span>
                {isSettingsOpen ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
              </span>
            </summary>

            <div style={{ marginTop: '16px', display: 'flex', flexDirection: 'column', gap: '14px', borderTop: '1px solid rgba(255, 255, 255, 0.06)', paddingTop: '14px' }}>
              <div>
                <label style={{ fontSize: '0.78rem', color: '#94A3B8', marginBottom: '8px', display: 'block', fontWeight: 600 }}>
                  Workspace Sandbox Mode:
                </label>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', alignItems: 'center' }}>
                  <button
                    type="button"
                    className="workspace-mode-option"
                    aria-pressed={!repoPath}
                    onClick={() => setRepoPath('')}
                    style={{
                      background: !repoPath ? 'linear-gradient(135deg, #6366F1, #8B5CF6)' : 'rgba(255, 255, 255, 0.05)',
                      color: '#FFFFFF',
                      border: `1px solid ${!repoPath ? 'rgba(99, 102, 241, 0.5)' : 'rgba(255, 255, 255, 0.1)'}`,
                      borderRadius: '6px',
                      padding: '6px 12px',
                      fontSize: '0.75rem',
                      fontWeight: 600,
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px'
                    }}
                  >
                    <Box size={13} />
                    <span>Clean Workspace (Isolated Sandbox)</span>
                  </button>

                  {sampleRepos.map((sr) => (
                    <button
                      key={sr.id}
                      type="button"
                      className="workspace-mode-option"
                      aria-pressed={repoPath === sr.path}
                      onClick={() => setRepoPath(sr.path)}
                      style={{
                        background: repoPath === sr.path ? 'rgba(99, 102, 241, 0.2)' : 'rgba(255, 255, 255, 0.04)',
                        color: repoPath === sr.path ? '#A5B4FC' : '#94A3B8',
                        border: `1px solid ${repoPath === sr.path ? 'rgba(99, 102, 241, 0.4)' : 'rgba(255, 255, 255, 0.08)'}`,
                        borderRadius: '6px',
                        padding: '6px 12px',
                        fontSize: '0.75rem',
                        fontWeight: repoPath === sr.path ? 600 : 500,
                        cursor: 'pointer'
                      }}
                    >
                      {sr.name.split('(')[0].trim()}
                    </button>
                  ))}
                </div>

                {/* Custom Path */}
                <div style={{ marginTop: '10px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ fontSize: '0.725rem', color: '#94A3B8', minWidth: '95px' }}>
                    Or Custom Path:
                  </span>
                  <input
                    type="text"
                    value={repoPath || ''}
                    onChange={(e) => setRepoPath(e.target.value)}
                    placeholder="Relative or absolute folder path (e.g. sandbox/my_project)"
                    style={{
                      flex: 1,
                      backgroundColor: '#060A14',
                      border: '1px solid rgba(255, 255, 255, 0.1)',
                      borderRadius: '6px',
                      padding: '6px 10px',
                      color: '#F1F5F9',
                      fontSize: '0.78rem',
                      fontFamily: 'var(--font-mono, monospace)',
                      outline: 'none'
                    }}
                  />
                </div>
              </div>

              {/* Language & Recovery Retries */}
              <div style={{ 
                display: 'flex', 
                flexWrap: 'wrap', 
                gap: '16px', 
                paddingTop: '10px', 
                borderTop: '1px solid rgba(255, 255, 255, 0.06)' 
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <label htmlFor="recovery-retries-select" style={{ fontSize: '0.75rem', color: '#94A3B8', fontWeight: 500 }}>
                    Max Recovery Retries:
                  </label>
                  <select
                    id="recovery-retries-select"
                    value={maxRecoveryRetries ?? 3}
                    onChange={(e) => setMaxRecoveryRetries && setMaxRecoveryRetries(Number(e.target.value))}
                    style={{
                      backgroundColor: '#060A14',
                      color: '#F1F5F9',
                      border: '1px solid rgba(255, 255, 255, 0.12)',
                      borderRadius: '6px',
                      padding: '4px 8px',
                      fontSize: '0.75rem',
                      outline: 'none'
                    }}
                  >
                    <option value={0}>0 (No Recovery)</option>
                    <option value={1}>1 Retry</option>
                    <option value={2}>2 Retries</option>
                    <option value={3}>3 Retries (Recommended)</option>
                    <option value={5}>5 Retries</option>
                  </select>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <label htmlFor="language-spec-select" style={{ fontSize: '0.75rem', color: '#94A3B8', fontWeight: 500 }}>
                    Language Specification:
                  </label>
                  <select
                    id="language-spec-select"
                    value={selectedLanguage || 'auto'}
                    onChange={(e) => setSelectedLanguage(e.target.value)}
                    style={{
                      backgroundColor: '#060A14',
                      color: '#F1F5F9',
                      border: '1px solid rgba(255, 255, 255, 0.12)',
                      borderRadius: '6px',
                      padding: '4px 8px',
                      fontSize: '0.75rem',
                      outline: 'none'
                    }}
                  >
                    <option value="auto">Auto Detect</option>
                    <option value="en">English (Standard)</option>
                    <option value="py">Python</option>
                    <option value="ts">TypeScript</option>
                  </select>
                </div>
              </div>
            </div>
          </details>

          {/* Scanned Workspace Inspector (if repoPath active) */}
          {repoInspection && (
            <section 
              className="card-panel" 
              style={{ 
                padding: '16px 20px',
                backgroundColor: '#0D1526',
                border: '1px solid rgba(255, 255, 255, 0.08)',
                borderRadius: '12px'
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                <h3 style={{ fontSize: '0.85rem', fontWeight: 600, color: '#F1F5F9', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <FolderOpen size={15} color="#818CF8" />
                  <span>Workspace Inspection: {repoPath}</span>
                </h3>
                <span className="badge badge-cyan" style={{ fontSize: '0.675rem' }}>
                  {repoInspection.test_framework}
                </span>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: '10px' }}>
                <div style={{ background: '#060A14', padding: '8px 12px', borderRadius: '6px', border: '1px solid rgba(255, 255, 255, 0.06)' }}>
                  <span style={{ fontSize: '0.65rem', color: '#94A3B8', textTransform: 'uppercase', display: 'block' }}>Files</span>
                  <span style={{ fontSize: '1rem', fontWeight: 700, color: '#F8FAFC' }}>{repoInspection.total_files}</span>
                </div>
                <div style={{ background: '#060A14', padding: '8px 12px', borderRadius: '6px', border: '1px solid rgba(255, 255, 255, 0.06)' }}>
                  <span style={{ fontSize: '0.65rem', color: '#94A3B8', textTransform: 'uppercase', display: 'block' }}>Lines of Code</span>
                  <span style={{ fontSize: '1rem', fontWeight: 700, color: '#34D399' }}>{repoInspection.total_lines_of_code}</span>
                </div>
                <div style={{ background: '#060A14', padding: '8px 12px', borderRadius: '6px', border: '1px solid rgba(255, 255, 255, 0.06)' }}>
                  <span style={{ fontSize: '0.65rem', color: '#94A3B8', textTransform: 'uppercase', display: 'block' }}>Languages</span>
                  <span style={{ fontSize: '0.8rem', fontWeight: 600, color: '#A5B4FC' }}>{repoInspection.detected_languages?.join(', ') || 'None'}</span>
                </div>
              </div>
            </section>
          )}

          {/* Quick Start Missions (Engineering Presets) */}
          <section 
            id="quick-presets-section"
            className="card-panel quick-start-missions" 
            style={{ 
              padding: '18px 22px', 
              backgroundColor: '#0D1526',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              borderRadius: '14px',
              display: 'flex',
              flexDirection: 'column',
              gap: '12px'
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Code2 size={16} color="#818CF8" />
                <h3 style={{ fontSize: '0.88rem', fontWeight: 700, color: '#F8FAFC', margin: 0 }}>
                  Curated Engineering Presets
                </h3>
                <span style={{ fontSize: '0.72rem', color: '#94A3B8' }}>
                  ({presets.length} production scenarios)
                </span>
              </div>
              <button
                type="button"
                onClick={() => setIsPresetsOpen(!isPresetsOpen)}
                style={{ background: 'none', border: 'none', color: '#94A3B8', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.72rem' }}
              >
                <span>{isPresetsOpen ? 'Collapse' : 'Expand'}</span>
                {isPresetsOpen ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
              </button>
            </div>

            {isPresetsOpen && (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '10px' }}>
                {presets.map((preset) => {
                  const Icon = getPresetIcon(preset.category);
                  const isSelected = selectedPresetId === preset.id;
                  return (
                    <article
                      key={preset.id}
                      onClick={() => handleSelectPreset(preset)}
                      style={{
                        padding: '12px 14px',
                        backgroundColor: isSelected ? 'rgba(99, 102, 241, 0.16)' : '#080D1A',
                        border: `1px solid ${isSelected ? 'rgba(99, 102, 241, 0.45)' : 'rgba(255, 255, 255, 0.06)'}`,
                        borderRadius: '10px',
                        cursor: 'pointer',
                        transition: 'all 0.15s ease',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '6px'
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span style={{
                          fontSize: '0.65rem',
                          padding: '1px 6px',
                          borderRadius: '4px',
                          background: 'rgba(99, 102, 241, 0.12)',
                          color: '#A5B4FC',
                          fontWeight: 600
                        }}>
                          {preset.category || 'Engineering'}
                        </span>
                        <Icon size={14} color="#818CF8" />
                      </div>
                      <strong style={{ fontSize: '0.8rem', color: '#F1F5F9', lineHeight: '1.3' }}>
                        {preset.title}
                      </strong>
                      <p style={{ fontSize: '0.72rem', color: '#94A3B8', margin: 0, lineHeight: '1.4' }}>
                        {preset.description || (preset.prompt ? preset.prompt.slice(0, 80) + '...' : '')}
                      </p>
                    </article>
                  );
                })}
              </div>
            )}
          </section>
        </div>

        {/* Right Column: Secondary Panels (Agent Workflow, Recent Tasks, System Status) */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>

          {/* 1. Agent Workflow Card (Inspired by reference image right column) */}
          <section 
            className="card-panel"
            style={{
              backgroundColor: '#0D1526',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              borderRadius: '14px',
              padding: '18px 20px',
              boxShadow: '0 4px 20px rgba(0, 0, 0, 0.35)',
              display: 'flex',
              flexDirection: 'column',
              gap: '12px'
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h3 style={{ fontSize: '0.88rem', fontWeight: 700, color: '#F8FAFC', margin: 0, display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Activity size={15} color="#818CF8" />
                <span>Agent Workflow</span>
              </h3>
              <span style={{ fontSize: '0.7rem', color: '#94A3B8' }}>7 Stages</span>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {[
                { id: 'goal_model', title: '1. Requirements', desc: 'Parse goal, extract criteria', done: hasRequirements, icon: Layers },
                { id: 'planner', title: '2. Architecture', desc: 'Generate execution plan', done: hasPlan, icon: Cpu },
                { id: 'coder', title: '3. Code Generation', desc: 'Implement clean code', done: hasCode, icon: Code2 },
                { id: 'testing', title: '4. Test & Debug', desc: 'Execute suite, self-heal', done: hasTesting, icon: FlaskConical },
                { id: 'verifier', title: '5. Independent Review', desc: 'Verify constraints & safety', done: hasVerification, icon: ShieldCheck },
                { id: 'evaluations', title: '6. Benchmark & Eval', desc: 'Goal alignment & metrics', done: !!currentRunRecord?.evaluation, icon: BarChart3 }
              ].map((wf) => {
                const Icon = wf.icon;
                return (
                  <div
                    key={wf.id}
                    onClick={() => onNavigateTab && onNavigateTab(wf.id)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '10px',
                      padding: '8px 10px',
                      backgroundColor: 'rgba(255, 255, 255, 0.02)',
                      border: '1px solid rgba(255, 255, 255, 0.04)',
                      borderRadius: '8px',
                      cursor: 'pointer',
                      transition: 'all 0.15s ease'
                    }}
                    onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'rgba(99, 102, 241, 0.1)'}
                    onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'rgba(255, 255, 255, 0.02)'}
                  >
                    <div style={{
                      width: '28px',
                      height: '28px',
                      borderRadius: '8px',
                      backgroundColor: wf.done ? 'rgba(16, 185, 129, 0.15)' : 'rgba(255, 255, 255, 0.05)',
                      border: `1px solid ${wf.done ? 'rgba(16, 185, 129, 0.35)' : 'rgba(255, 255, 255, 0.08)'}`,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: wf.done ? '#34D399' : '#94A3B8',
                      flexShrink: 0
                    }}>
                      {wf.done ? <Check size={14} /> : <Icon size={14} />}
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <strong style={{ fontSize: '0.78rem', color: '#F1F5F9', display: 'block' }}>{wf.title}</strong>
                      <span style={{ fontSize: '0.68rem', color: '#94A3B8' }}>{wf.desc}</span>
                    </div>
                    <ChevronRight size={13} color="#64748B" />
                  </div>
                );
              })}
            </div>
          </section>

          {/* 2. Recent Tasks Card */}
          <section 
            className="card-panel"
            style={{
              backgroundColor: '#0D1526',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              borderRadius: '14px',
              padding: '18px 20px',
              boxShadow: '0 4px 20px rgba(0, 0, 0, 0.35)',
              display: 'flex',
              flexDirection: 'column',
              gap: '12px'
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h3 style={{ fontSize: '0.88rem', fontWeight: 700, color: '#F8FAFC', margin: 0, display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Clock size={15} color="#818CF8" />
                <span>Recent Tasks</span>
              </h3>
              <span style={{ fontSize: '0.7rem', color: '#94A3B8' }}>
                {runsList.length} recorded
              </span>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {runsList.length > 0 ? (
                runsList.slice(0, 5).map((r) => {
                  const isCurrent = r.run_id === runId;
                  const isSuccess = r.status === 'success';
                  const isFailed = r.status === 'failed';
                  return (
                    <div
                      key={r.run_id}
                      onClick={() => onSelectRun && onSelectRun(r.run_id)}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        padding: '8px 10px',
                        backgroundColor: isCurrent ? 'rgba(99, 102, 241, 0.14)' : 'rgba(255, 255, 255, 0.02)',
                        border: `1px solid ${isCurrent ? 'rgba(99, 102, 241, 0.35)' : 'rgba(255, 255, 255, 0.04)'}`,
                        borderRadius: '8px',
                        cursor: 'pointer',
                        transition: 'all 0.15s ease'
                      }}
                      onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'rgba(99, 102, 241, 0.1)'}
                      onMouseLeave={(e) => e.currentTarget.style.backgroundColor = isCurrent ? 'rgba(99, 102, 241, 0.14)' : 'rgba(255, 255, 255, 0.02)'}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: 0 }}>
                        <div style={{
                          width: '8px',
                          height: '8px',
                          borderRadius: '50%',
                          backgroundColor: isSuccess ? '#10B981' : isFailed ? '#EF4444' : '#6366F1',
                          flexShrink: 0
                        }} />
                        <div style={{ minWidth: 0 }}>
                          <span style={{ fontSize: '0.76rem', fontWeight: 600, color: '#F1F5F9', display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            {r.title || r.run_id}
                          </span>
                          <span style={{ fontSize: '0.67rem', color: '#94A3B8' }}>
                            {r.run_id} · {r.status}
                          </span>
                        </div>
                      </div>
                      <ChevronRight size={13} color="#64748B" />
                    </div>
                  );
                })
              ) : (
                <div style={{ fontSize: '0.75rem', color: '#64748B', textAlign: 'center', padding: '12px 0' }}>
                  No previous runs in SQLite database.
                </div>
              )}
            </div>
          </section>

          {/* 3. System Status Card (Matching Reference Image bottom right) */}
          <section 
            className="card-panel"
            style={{
              backgroundColor: '#0D1526',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              borderRadius: '14px',
              padding: '18px 20px',
              boxShadow: '0 4px 20px rgba(0, 0, 0, 0.35)',
              display: 'flex',
              flexDirection: 'column',
              gap: '12px'
            }}
          >
            <h3 style={{ fontSize: '0.88rem', fontWeight: 700, color: '#F8FAFC', margin: 0, display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Cpu size={15} color="#818CF8" />
              <span>System Status</span>
            </h3>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {/* Ollama Status */}
              <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '8px 10px',
                backgroundColor: 'rgba(255, 255, 255, 0.02)',
                border: '1px solid rgba(255, 255, 255, 0.04)',
                borderRadius: '8px'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Bot size={15} color="#34D399" />
                  <span style={{ fontSize: '0.76rem', color: '#F1F5F9' }}>
                    Ollama ({ollamaStatus?.current_model || 'active'})
                  </span>
                </div>
                <span style={{ 
                  fontSize: '0.7rem', 
                  color: ollamaStatus?.connected ? '#34D399' : '#F87171',
                  fontWeight: 600,
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px'
                }}>
                  <span style={{
                    width: '6px',
                    height: '6px',
                    borderRadius: '50%',
                    backgroundColor: ollamaStatus?.connected ? '#10B981' : '#EF4444'
                  }} />
                  {ollamaStatus?.connected ? 'Online' : 'Offline'}
                </span>
              </div>

              {/* Workspace Readiness */}
              <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '8px 10px',
                backgroundColor: 'rgba(255, 255, 255, 0.02)',
                border: '1px solid rgba(255, 255, 255, 0.04)',
                borderRadius: '8px'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <FolderOpen size={15} color="#38BDF8" />
                  <span style={{ fontSize: '0.76rem', color: '#F1F5F9' }}>
                    Workspace
                  </span>
                </div>
                <span style={{ 
                  fontSize: '0.7rem', 
                  color: '#34D399',
                  fontWeight: 600,
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px'
                }}>
                  <span style={{
                    width: '6px',
                    height: '6px',
                    borderRadius: '50%',
                    backgroundColor: '#10B981'
                  }} />
                  {repoPath ? 'Custom Target' : 'Ready'}
                </span>
              </div>
            </div>

            <div style={{ 
              fontSize: '0.68rem', 
              color: '#64748B', 
              textAlign: 'center', 
              borderTop: '1px solid rgba(255, 255, 255, 0.06)',
              paddingTop: '8px'
            }}>
              Build. Think. Execute. With your AI coding partner.
            </div>
          </section>

        </div>
      </div>
    </div>
  );
}
