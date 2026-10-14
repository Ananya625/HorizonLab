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
  Box
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
  setMaxRecoveryRetries
}) {
  const [sampleRepos, setSampleRepos] = useState([]);
  const [repoInspection, setRepoInspection] = useState(null);
  const [inspectingRepo, setInspectingRepo] = useState(false);
  const [selectedPresetId, setSelectedPresetId] = useState(null);
  const [isExamplesOpen, setIsExamplesOpen] = useState(false);

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

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      
      {/* 1. Main Task Input: Primary Visual Focus */}
      <section className="card-panel" style={{ padding: '24px 28px', backgroundColor: '#FFFFFF' }}>
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
            <span style={{ fontSize: '0.725rem', color: 'var(--text-secondary, #667085)', fontFamily: 'var(--font-mono)' }}>
              {taskPrompt.length} characters
            </span>
          </div>

          <textarea
            id="task-prompt-input"
            value={taskPrompt}
            onChange={(e) => {
              setTaskPrompt(e.target.value);
              setSelectedPresetId(null);
            }}
            placeholder="e.g. Build a login API with JWT authentication using FastAPI. Implement user registration with password hashing, login endpoint returning JWT bearer token, protected route GET /api/auth/me, invalid credentials rejection (HTTP 401), and automated pytest suite..."
            rows={6}
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

        {/* Workspace Mode & Execution Parameters */}
        <div style={{ 
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

        {/* Primary Execution Buttons Row */}
        <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
          <button
            type="button"
            className="btn btn-primary"
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
      <section className="card-panel" style={{ padding: '18px 24px', backgroundColor: '#FFFFFF' }}>
        <div 
          onClick={() => setIsExamplesOpen(!isExamplesOpen)}
          style={{ 
            display: 'flex', 
            justifyContent: 'space-between', 
            alignItems: 'center', 
            cursor: 'pointer',
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
              Example Tasks
            </h3>
            <span style={{ fontSize: '0.725rem', color: 'var(--text-secondary, #667085)' }}>
              ({presets.length} curated engineering presets available)
            </span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--text-secondary, #667085)', fontSize: '0.775rem' }}>
            <span>{isExamplesOpen ? 'Collapse presets' : 'Explore presets'}</span>
            {isExamplesOpen ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </div>
        </div>

        {isExamplesOpen && (
          <div style={{ marginTop: '16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <p style={{ fontSize: '0.775rem', color: 'var(--text-secondary, #667085)', margin: 0 }}>
              Click any preset below to pre-fill the task prompt without triggering execution.
            </p>

            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
              gap: '12px'
            }}>
              {presets.map((p) => {
                const isSelected = selectedPresetId === p.id;
                return (
                  <div
                    key={p.id}
                    onClick={() => handleSelectPreset(p)}
                    style={{
                      padding: '12px 14px',
                      cursor: 'pointer',
                      borderRadius: '8px',
                      border: `1px solid ${isSelected ? 'var(--accent-primary, #6257D9)' : 'var(--border-subtle, #E5E7EF)'}`,
                      backgroundColor: isSelected ? 'var(--accent-primary-subtle, #F0EEFF)' : '#FFFFFF',
                      transition: 'all 0.15s ease',
                      boxShadow: isSelected ? '0 2px 6px rgba(98, 87, 217, 0.15)' : 'none'
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                      <span className="badge badge-purple" style={{ fontSize: '0.65rem' }}>
                        {p.category}
                      </span>
                      {isSelected && <CheckCircle size={14} color="var(--accent-primary, #6257D9)" />}
                    </div>
                    <h4 style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary, #172033)', marginBottom: '4px' }}>
                      {p.title}
                    </h4>
                    <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary, #667085)', lineHeight: '1.4', margin: 0 }}>
                      {p.description}
                    </p>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </section>

    </div>
  );
}
