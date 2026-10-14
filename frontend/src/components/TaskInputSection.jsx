import React, { useState, useEffect } from 'react';
import { 
  FolderGit2, 
  Terminal, 
  Sparkles, 
  ArrowRight, 
  Code2, 
  RefreshCw, 
  CheckCircle, 
  FolderOpen,
  ChevronDown,
  ChevronUp,
  Layers,
  Shield,
  FileCode,
  Box,
  GitBranch,
  ListChecks,
  Bot,
  ShieldCheck,
  Bug,
  KeyRound
} from 'lucide-react';
import { inspectWorkspace, fetchSampleRepos } from '../services/api';

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
  goalModel
}) {
  const [sampleRepos, setSampleRepos] = useState([]);
  const [repoInspection, setRepoInspection] = useState(null);
  const [inspectingRepo, setInspectingRepo] = useState(false);
  const [selectedPresetId, setSelectedPresetId] = useState(null);
  const [isExamplesOpen, setIsExamplesOpen] = useState(true);

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

  const subGoals = goalModel?.sub_goals || [];
  const languageLabel = {
    auto: 'Auto detect',
    en: 'English',
    py: 'Python',
    ts: 'TypeScript'
  }[selectedLanguage] || selectedLanguage || 'Auto detect';
  const getPresetIcon = (category = '') => {
    const normalizedCategory = category.toLowerCase();
    if (normalizedCategory.includes('security') || normalizedCategory.includes('auth')) return ShieldCheck;
    if (normalizedCategory.includes('debug') || normalizedCategory.includes('concurrency')) return Bug;
    if (normalizedCategory.includes('refactor') || normalizedCategory.includes('architecture')) return GitBranch;
    if (normalizedCategory.includes('api')) return KeyRound;
    return FileCode;
  };

  return (
    <div className="workspace-view" style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
      
      {/* 1. Main Task Input: Primary Visual Focus */}
      <section className="card-panel workspace-composer" style={{ padding: '24px 28px', backgroundColor: '#FFFFFF' }}>
        <div style={{ marginBottom: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
            <span className="badge badge-purple">Stage 1: Workspace</span>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary, #667085)' }}>
              Developer Input & Configuration
            </span>
          </div>
          <h2 style={{ 
            fontSize: '1.45rem', 
            fontFamily: 'var(--font-heading, "Plus Jakarta Sans")', 
            fontWeight: 700, 
            color: 'var(--text-primary, #172033)',
            marginBottom: '6px'
          }}>
            What would you like to build?
          </h2>
          <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary, #667085)', lineHeight: '1.5', margin: 0 }}>
            Describe your software task, API endpoint, or feature. The multi-agent pipeline analyzes requirements, generates code, executes tests, repairs failures, and independently verifies criteria.
          </p>
        </div>

        {/* Multiline Task Prompt Textarea */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginBottom: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <label htmlFor="task-prompt-input" style={{ 
              fontSize: '0.825rem', 
              fontWeight: 600, 
              color: 'var(--text-primary, #172033)',
              display: 'flex',
              alignItems: 'center',
              gap: '6px'
            }}>
              <Terminal size={15} color="var(--accent-primary, #6257D9)" />
              <span>Task Specification Prompt</span>
            </label>
            <span className="workspace-prompt-count" aria-live="polite">
              {taskPrompt.length.toLocaleString()} characters
            </span>
          </div>

          <textarea
            id="task-prompt-input"
            value={taskPrompt}
            onChange={(e) => {
              setTaskPrompt(e.target.value);
              setSelectedPresetId(null);
            }}
            placeholder="Describe your goal. HorizonLab will break it into actionable subgoals."
            rows={6}
            className="workspace-prompt-editor"
            aria-describedby="goal-breakdown-caption"
            style={{
              width: '100%',
              backgroundColor: '#FFFFFF',
              border: '1px solid var(--border-subtle, #E5E7EF)',
              borderRadius: '8px',
              padding: '14px 16px',
              color: 'var(--text-primary, #172033)',
              fontSize: '0.9rem',
              fontFamily: 'var(--font-sans)',
              lineHeight: '1.6',
              resize: 'vertical',
              outline: 'none',
              boxShadow: 'inset 0 1px 2px rgba(16, 24, 40, 0.04)'
            }}
          />
        </div>

        <section className="goal-breakdown-panel" aria-labelledby="goal-breakdown-title">
          <div className="goal-breakdown-heading">
            <div>
              <span className="workspace-section-eyebrow">How HorizonLab works</span>
              <h3 id="goal-breakdown-title">Goal Breakdown</h3>
            </div>
            {subGoals.length > 0 && (
              <span className="goal-breakdown-count">
                {subGoals.length} actual subgoal{subGoals.length === 1 ? '' : 's'}
              </span>
            )}
          </div>
          <div className="goal-breakdown-flow" role="list" aria-label="Task execution workflow">
            <div className="goal-flow-step" role="listitem">
              <span className="goal-flow-icon"><Terminal size={15} /></span>
              <span><strong>Goal</strong><small>Task brief</small></span>
            </div>
            <ArrowRight className="goal-flow-arrow" size={15} aria-hidden="true" />
            <div className="goal-flow-step goal-flow-subgoals" role="listitem">
              <span className="goal-flow-icon"><ListChecks size={15} /></span>
              <span><strong>Subgoals</strong><small>{subGoals.length ? `${subGoals.length} from requirements` : 'Created from requirements'}</small></span>
            </div>
            <ArrowRight className="goal-flow-arrow" size={15} aria-hidden="true" />
            <div className="goal-flow-step" role="listitem">
              <span className="goal-flow-icon"><Bot size={15} /></span>
              <span><strong>Agent execution</strong><small>Plan and implement</small></span>
            </div>
            <ArrowRight className="goal-flow-arrow" size={15} aria-hidden="true" />
            <div className="goal-flow-step" role="listitem">
              <span className="goal-flow-icon"><ShieldCheck size={15} /></span>
              <span><strong>Verification</strong><small>Evidence-backed checks</small></span>
            </div>
          </div>
          <div id="goal-breakdown-caption" className="goal-breakdown-detail">
            {subGoals.length > 0 ? (
              <ul aria-label="Requirements-derived subgoals">
                {subGoals.map((subGoal) => (
                  <li key={subGoal.id}>
                    <span className={`goal-subgoal-status goal-status-${subGoal.status || 'pending'}`} aria-hidden="true" />
                    <span className="goal-subgoal-copy">
                      <strong>{subGoal.title}</strong>
                      <small>{subGoal.assigned_agent_role || 'Agent assignment pending'} · {subGoal.status || 'pending'}</small>
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <p>
                Subgoals appear here after requirements are analyzed. No execution steps or results are assumed in advance.
              </p>
            )}
          </div>
        </section>

        {/* Workspace Mode & Execution Parameters */}
        <details className="workspace-settings">
          <summary className="workspace-settings-summary">
            <span className="workspace-settings-title">
              <FolderGit2 size={16} />
              <span>
                <strong>Execution Settings</strong>
                <small>{repoPath ? `Workspace: ${repoPath}` : 'Clean isolated sandbox'} · {languageLabel} · {maxRecoveryRetries ?? 3} recovery retries</small>
              </span>
            </span>
            <span className="workspace-settings-action"><span>Configure</span><ChevronDown size={16} /></span>
          </summary>
          <div className="workspace-settings-content" style={{
          background: 'var(--bg-page, #F6F7FB)', 
          border: '1px solid var(--border-subtle, #E5E7EF)', 
          borderRadius: '8px', 
          padding: '16px',
          display: 'flex',
          flexDirection: 'column',
          gap: '14px',
          marginBottom: '20px'
        }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
              <label style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-primary, #172033)', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <FolderGit2 size={15} color="var(--accent-primary, #6257D9)" />
                <span>Target Workspace & Sandbox Mode:</span>
              </label>
              {inspectingRepo && (
                <span style={{ fontSize: '0.7rem', color: 'var(--accent-primary, #6257D9)' }}>
                  Scanning repository...
                </span>
              )}
            </div>

            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', alignItems: 'center' }}>
              <button
                type="button"
                className="workspace-mode-option"
                aria-pressed={!repoPath}
                onClick={() => setRepoPath('')}
                style={{
                  background: !repoPath ? 'var(--accent-primary, #6257D9)' : '#FFFFFF',
                  color: !repoPath ? '#FFFFFF' : 'var(--text-primary, #172033)',
                  border: `1px solid ${!repoPath ? 'var(--accent-primary, #6257D9)' : 'var(--border-subtle, #E5E7EF)'}`,
                  borderRadius: '6px',
                  padding: '6px 12px',
                  fontSize: '0.775rem',
                  fontWeight: !repoPath ? 600 : 500,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  transition: 'all 0.15s ease'
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
                    background: repoPath === sr.path ? 'var(--accent-primary-subtle, #F0EEFF)' : '#FFFFFF',
                    color: repoPath === sr.path ? 'var(--accent-primary, #6257D9)' : 'var(--text-primary, #172033)',
                    border: `1px solid ${repoPath === sr.path ? 'var(--accent-primary, #6257D9)' : 'var(--border-subtle, #E5E7EF)'}`,
                    borderRadius: '6px',
                    padding: '6px 12px',
                    fontSize: '0.75rem',
                    fontWeight: repoPath === sr.path ? 600 : 500,
                    cursor: 'pointer',
                    transition: 'all 0.15s ease'
                  }}
                >
                  {sr.name.split('(')[0].trim()}
                </button>
              ))}
            </div>

            {/* Custom Path Input if user wants custom directory */}
            <div style={{ marginTop: '10px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '0.725rem', color: 'var(--text-secondary, #667085)', minWidth: '95px' }}>
                Or Custom Path:
              </span>
              <input
                type="text"
                value={repoPath || ''}
                onChange={(e) => setRepoPath(e.target.value)}
                placeholder="Relative or absolute folder path (e.g. sandbox/my_project)"
                style={{
                  flex: 1,
                  backgroundColor: '#FFFFFF',
                  border: '1px solid var(--border-subtle, #E5E7EF)',
                  borderRadius: '6px',
                  padding: '6px 10px',
                  color: 'var(--text-primary, #172033)',
                  fontSize: '0.8rem',
                  fontFamily: 'var(--font-mono, monospace)',
                  outline: 'none'
                }}
              />
            </div>
          </div>

          {/* Additional Options: Language & Max Recovery Retries */}
          <div style={{ 
            display: 'flex', 
            flexWrap: 'wrap', 
            gap: '16px', 
            paddingTop: '10px', 
            borderTop: '1px solid var(--border-subtle, #E5E7EF)' 
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <label htmlFor="recovery-retries-select" style={{ fontSize: '0.75rem', color: 'var(--text-secondary, #667085)', fontWeight: 500 }}>
                Max Recovery Retries:
              </label>
              <select
                id="recovery-retries-select"
                value={maxRecoveryRetries ?? 3}
                onChange={(e) => setMaxRecoveryRetries && setMaxRecoveryRetries(Number(e.target.value))}
                style={{
                  backgroundColor: '#FFFFFF',
                  color: 'var(--text-primary, #172033)',
                  border: '1px solid var(--border-subtle, #E5E7EF)',
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
              <label htmlFor="language-spec-select" style={{ fontSize: '0.75rem', color: 'var(--text-secondary, #667085)', fontWeight: 500 }}>
                Language Specification:
              </label>
              <select
                id="language-spec-select"
                value={selectedLanguage || 'auto'}
                onChange={(e) => setSelectedLanguage(e.target.value)}
                style={{
                  backgroundColor: '#FFFFFF',
                  color: 'var(--text-primary, #172033)',
                  border: '1px solid var(--border-subtle, #E5E7EF)',
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

        {/* Primary Execution Buttons Row */}
        <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
          <button
            type="button"
            className="btn btn-primary workspace-run-button"
            onClick={onRunFullPipeline}
            disabled={loading || !taskPrompt.trim()}
            style={{ 
              flex: '1 1 240px', 
              padding: '11px 20px', 
              fontSize: '0.9rem',
              fontWeight: 600,
              gap: '8px'
            }}
          >
            <Sparkles size={16} />
            <span>Run Full Autonomous Pipeline</span>
          </button>

          <button
            type="button"
            className="btn btn-secondary"
            onClick={onAnalyze}
            disabled={loading || !taskPrompt.trim()}
            style={{ 
              flex: '1 1 200px', 
              padding: '11px 18px', 
              fontSize: '0.85rem',
              fontWeight: 600,
              gap: '8px'
            }}
          >
            <span>Analyze Requirements (Stage 2)</span>
            <ArrowRight size={15} />
          </button>
        </div>

        {error && (
          <div role="alert" style={{
            marginTop: '16px',
            padding: '12px 16px',
            backgroundColor: 'var(--danger-subtle, #FEF2F2)',
            border: '1px solid var(--danger-border, #FECACA)',
            borderRadius: '6px',
            fontSize: '0.825rem',
            color: 'var(--danger-color, #D14343)'
          }}>
            {error}
          </div>
        )}
      </section>

      {/* 2. Repository Workspace Inspector Details (if repoPath is active) */}
      {repoInspection && (
        <section className="card-panel" style={{ padding: '18px 22px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
            <h3 style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--text-primary, #172033)', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <FolderOpen size={16} color="var(--accent-primary, #6257D9)" />
              <span>Workspace Inspection: {repoPath}</span>
            </h3>
            <span className="badge badge-cyan" style={{ fontSize: '0.675rem' }}>
              {repoInspection.test_framework}
            </span>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '10px', marginBottom: '12px' }}>
            <div style={{ background: '#F8F9FD', padding: '10px 14px', borderRadius: '6px', border: '1px solid #E5E7EF' }}>
              <span style={{ fontSize: '0.65rem', color: '#667085', textTransform: 'uppercase', display: 'block' }}>Files Scanned</span>
              <span style={{ fontSize: '1.1rem', fontWeight: 700, color: '#172033' }}>{repoInspection.total_files}</span>
            </div>
            <div style={{ background: '#F8F9FD', padding: '10px 14px', borderRadius: '6px', border: '1px solid #E5E7EF' }}>
              <span style={{ fontSize: '0.65rem', color: '#667085', textTransform: 'uppercase', display: 'block' }}>Lines of Code</span>
              <span style={{ fontSize: '1.1rem', fontWeight: 700, color: '#16845B' }}>{repoInspection.total_lines_of_code}</span>
            </div>
            <div style={{ background: '#F8F9FD', padding: '10px 14px', borderRadius: '6px', border: '1px solid #E5E7EF' }}>
              <span style={{ fontSize: '0.65rem', color: '#667085', textTransform: 'uppercase', display: 'block' }}>Languages</span>
              <span style={{ fontSize: '0.85rem', fontWeight: 600, color: '#6257D9' }}>{repoInspection.detected_languages?.join(', ') || 'None'}</span>
            </div>
          </div>

          {repoInspection.files?.length > 0 && (
            <details style={{ fontSize: '0.775rem' }}>
              <summary style={{ color: '#667085', cursor: 'pointer', marginBottom: '6px' }}>
                View scanned workspace files ({repoInspection.files.length})
              </summary>
              <div style={{ 
                maxHeight: '130px', 
                overflowY: 'auto', 
                background: '#F8F9FD', 
                padding: '8px 12px', 
                borderRadius: '6px',
                border: '1px solid #E5E7EF',
                fontFamily: 'var(--font-mono)'
              }}>
                {repoInspection.files.map((f, i) => (
                  <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '2px 0' }}>
                    <span style={{ color: '#172033' }}>{f.path}</span>
                    <span style={{ color: '#667085' }}>{f.lines_of_code} loc</span>
                  </div>
                ))}
              </div>
            </details>
          )}
        </section>
      )}

      {/* 3. Collapsible Example Tasks Section (Moved BELOW main task prompt) */}
      <section className="card-panel quick-start-missions" style={{ padding: '18px 24px', backgroundColor: '#FFFFFF' }}>
        <button
          type="button"
          aria-expanded={isExamplesOpen}
          className="quick-start-toggle"
          onClick={() => setIsExamplesOpen(!isExamplesOpen)}
          style={{ 
            display: 'flex', 
            justifyContent: 'space-between', 
            alignItems: 'center', 
            userSelect: 'none'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Code2 size={16} color="var(--accent-primary, #6257D9)" />
            <h3 style={{ 
              fontSize: '0.95rem', 
              fontFamily: 'var(--font-heading, "Plus Jakarta Sans")', 
              fontWeight: 600, 
              color: 'var(--text-primary, #172033)',
              margin: 0
            }}>
              Quick Start Missions
            </h3>
            <span style={{ fontSize: '0.725rem', color: 'var(--text-secondary, #667085)' }}>
              ({presets.length} curated engineering presets)
            </span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--text-secondary, #667085)', fontSize: '0.775rem' }}>
            <span>{isExamplesOpen ? 'Collapse presets' : 'Explore presets'}</span>
            {isExamplesOpen ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </div>
        </button>

        {isExamplesOpen && (
          <div style={{ marginTop: '16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <p style={{ fontSize: '0.775rem', color: 'var(--text-secondary, #667085)', margin: 0 }}>
              Click any preset below to pre-fill the task prompt without triggering execution.
            </p>

            <div className="quick-start-grid" style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
              gap: '12px'
            }}>
              {presets.map((p) => {
                const isSelected = selectedPresetId === p.id;
                const PresetIcon = getPresetIcon(p.category);
                return (
                  <button
                    key={p.id}
                    type="button"
                    aria-pressed={isSelected}
                    className="mission-card"
                    onClick={() => handleSelectPreset(p)}
                    style={{
                      padding: '12px 14px',
                      cursor: 'pointer',
                      borderRadius: '8px',
                      border: `1px solid ${isSelected ? 'var(--accent-primary, #6257D9)' : 'var(--border-subtle, #E5E7EF)'}`,
                      backgroundColor: isSelected ? 'var(--accent-primary-subtle, #F0EEFF)' : '#FFFFFF',
                      transition: 'all 0.15s ease',
                      boxShadow: isSelected ? '0 2px 6px rgba(98, 87, 217, 0.15)' : 'none',
                      textAlign: 'left',
                      font: 'inherit'
                    }}
                  >
                    <div className="mission-card-top">
                      <span className="mission-card-icon"><PresetIcon size={17} /></span>
                      <span className="badge badge-purple" style={{ fontSize: '0.65rem' }}>
                        {p.category}
                      </span>
                      {isSelected && <CheckCircle size={15} color="var(--accent-primary, #6257D9)" aria-label="Selected" />}
                    </div>
                    <h4 style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary, #172033)', marginBottom: '4px' }}>
                      {p.title}
                    </h4>
                    <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary, #667085)', lineHeight: '1.4', margin: 0 }}>
                      {p.description}
                    </p>
                  </button>
                );
              })}
            </div>
          </div>
        )}
      </section>

    </div>
  );
}
