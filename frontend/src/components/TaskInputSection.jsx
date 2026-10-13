import React, { useState, useEffect } from 'react';
import { 
  FolderGit2, 
  Terminal, 
  Sparkles, 
  ArrowRight, 
  Code2, 
  ShieldAlert, 
  RefreshCw, 
  Sliders, 
  FileText, 
  Cpu, 
  CheckCircle,
  FolderOpen
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
      {/* Hero Intro Banner */}
      <div className="card-panel" style={{
        padding: '24px',
        background: 'linear-gradient(135deg, #101626 0%, #0d121f 100%)',
        borderColor: '#1e293b',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        flexWrap: 'wrap',
        gap: '16px'
      }}>
        <div style={{ maxWidth: '800px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
            <span className="badge badge-cyan">Stage 1: Coding Workspace</span>
            <span style={{ fontSize: '0.75rem', color: '#64748b' }}>Repository Selection & Task Ingestion</span>
          </div>
          <h2 style={{ fontSize: '1.4rem', fontWeight: 700, color: '#f8fafc', marginBottom: '6px' }}>
            Autonomous Software Development & Closed-Loop Verification
          </h2>
          <p style={{ fontSize: '0.875rem', color: '#94a3b8', lineHeight: '1.5' }}>
            Enter your coding request (e.g. <strong style={{ color: '#38bdf8' }}>“Build a login API with JWT authentication”</strong>), select the target repository, and let the multi-agent engine analyze requirements, inspect existing code, write implementations, run tests, debug failures, and verify results.
          </p>
        </div>

        {/* Action Highlights */}
        <div style={{ display: 'flex', gap: '10px' }}>
          <button
            className="btn btn-primary"
            onClick={onRunFullPipeline}
            disabled={loading || !taskPrompt.trim()}
            style={{
              padding: '10px 20px',
              fontWeight: 600,
              background: 'linear-gradient(135deg, #2563eb 0%, #7c3aed 100%)'
            }}
          >
            <Sparkles size={16} />
            <span>⚡ Run End-to-End Pipeline</span>
          </button>
        </div>
      </div>

      {/* Preset Tasks Gallery */}
      <div>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
          <h3 style={{ fontSize: '0.95rem', fontWeight: 600, color: '#e2e8f0', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Code2 size={16} color="#38bdf8" />
            <span>Curated Software Engineering Tasks & Presets</span>
          </h3>
          <span style={{ fontSize: '0.75rem', color: '#64748b' }}>Click a preset to pre-fill prompt</span>
        </div>

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
                className="card-panel"
                style={{
                  padding: '14px 16px',
                  cursor: 'pointer',
                  borderColor: isSelected ? '#38bdf8' : '#1e293b',
                  background: isSelected ? 'rgba(56, 189, 248, 0.08)' : '#151d2e',
                  transition: 'all 0.2s ease'
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                  <span className="badge badge-purple" style={{ fontSize: '0.65rem' }}>
                    {p.category}
                  </span>
                  {isSelected && <CheckCircle size={14} color="#38bdf8" />}
                </div>
                <h4 style={{ fontSize: '0.85rem', fontWeight: 600, color: '#f1f5f9', marginBottom: '4px' }}>
                  {p.title}
                </h4>
                <p style={{ fontSize: '0.75rem', color: '#94a3b8', lineHeight: '1.4' }}>
                  {p.description}
                </p>
              </div>
            );
          })}
        </div>
      </div>

      {/* Two-Column Grid: Task Prompt & Repository Workspace Inspector */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr', gap: '20px' }}>
        
        {/* Left: Task Prompt Textarea & Execution Controls */}
        <div className="card-panel" style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <label style={{ fontSize: '0.875rem', fontWeight: 600, color: '#f1f5f9', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Terminal size={15} color="#38bdf8" />
              <span>Software Engineering Task Prompt</span>
            </label>
            <span style={{ fontSize: '0.725rem', color: '#64748b' }}>
              {taskPrompt.length} chars
            </span>
          </div>

          <textarea
            value={taskPrompt}
            onChange={(e) => {
              setTaskPrompt(e.target.value);
              setSelectedPresetId(null);
            }}
            placeholder="e.g. Build a login API with JWT authentication using FastAPI. Implement password hashing with bcrypt, token generation, protected route GET /api/auth/me, and automated pytest suite..."
            rows={7}
            style={{
              width: '100%',
              backgroundColor: '#0c121d',
              border: '1px solid #1e293b',
              borderRadius: '8px',
              padding: '12px 14px',
              color: '#f8fafc',
              fontSize: '0.875rem',
              fontFamily: 'var(--font-sans)',
              lineHeight: '1.6',
              resize: 'vertical',
              outline: 'none',
              boxShadow: 'inset 0 2px 4px rgba(0, 0, 0, 0.4)'
            }}
          />

          {/* Prompt Parameters Row */}
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '14px', alignItems: 'center' }}>
            {/* Max Recovery Retries */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '0.775rem', color: '#94a3b8' }}>Max Recovery Retries:</span>
              <select
                value={maxRecoveryRetries || 3}
                onChange={(e) => setMaxRecoveryRetries && setMaxRecoveryRetries(Number(e.target.value))}
                style={{
                  backgroundColor: '#0c121d',
                  color: '#f8fafc',
                  border: '1px solid #1e293b',
                  borderRadius: '6px',
                  padding: '4px 8px',
                  fontSize: '0.75rem',
                  outline: 'none'
                }}
              >
                <option value={1}>1 Retry</option>
                <option value={2}>2 Retries</option>
                <option value={3}>3 Retries (Recommended)</option>
                <option value={5}>5 Retries</option>
              </select>
            </div>

            {/* Language / Spec */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '0.775rem', color: '#94a3b8' }}>Language Spec:</span>
              <select
                value={selectedLanguage}
                onChange={(e) => setSelectedLanguage(e.target.value)}
                style={{
                  backgroundColor: '#0c121d',
                  color: '#f8fafc',
                  border: '1px solid #1e293b',
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

          {/* Action Buttons */}
          <div style={{ display: 'flex', gap: '10px', marginTop: '8px' }}>
            <button
              className="btn btn-primary"
              onClick={onAnalyze}
              disabled={loading || !taskPrompt.trim()}
              style={{ flex: 1, padding: '10px 16px', fontWeight: 600 }}
            >
              <span>{loading ? 'Analyzing Requirements with Ollama...' : 'Analyze Requirements (Stage 2)'}</span>
              <ArrowRight size={15} />
            </button>

            <button
              className="btn btn-emerald"
              onClick={onRunFullPipeline}
              disabled={loading || !taskPrompt.trim()}
              style={{ flex: 1, padding: '10px 16px', fontWeight: 600 }}
            >
              <Sparkles size={15} />
              <span>⚡ Execute Full Workflow (1-7)</span>
            </button>
          </div>

          {error && (
            <div style={{
              padding: '10px 14px',
              backgroundColor: 'rgba(244, 63, 94, 0.1)',
              border: '1px solid rgba(244, 63, 94, 0.3)',
              borderRadius: '6px',
              fontSize: '0.8rem',
              color: '#fb7185'
            }}>
              {error}
            </div>
          )}
        </div>

        {/* Right: Target Repository & Workspace Inspector */}
        <div className="card-panel" style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '14px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h3 style={{ fontSize: '0.875rem', fontWeight: 600, color: '#f1f5f9', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <FolderGit2 size={16} color="#38bdf8" />
              <span>Target Repository Workspace</span>
            </h3>
            {inspectingRepo && <span style={{ fontSize: '0.7rem', color: '#38bdf8' }}>Scanning...</span>}
          </div>

          {/* Repo Selection Preset / Custom Path */}
          <div>
            <label style={{ fontSize: '0.725rem', color: '#94a3b8', display: 'block', marginBottom: '4px' }}>
              Sandbox / Target Project Folder:
            </label>
            <div style={{ display: 'flex', gap: '6px' }}>
              <input
                type="text"
                value={repoPath || ''}
                onChange={(e) => setRepoPath(e.target.value)}
                placeholder="Repository file path..."
                style={{
                  flex: 1,
                  backgroundColor: '#0c121d',
                  border: '1px solid #1e293b',
                  borderRadius: '6px',
                  padding: '6px 10px',
                  color: '#f8fafc',
                  fontSize: '0.775rem',
                  fontFamily: 'var(--font-mono)',
                  outline: 'none'
                }}
              />
            </div>
          </div>

          {/* Sample Sandboxes Quick Switch */}
          <div>
            <span style={{ fontSize: '0.7rem', color: '#64748b' }}>Select Target Repository Mode:</span>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginTop: '4px' }}>
              <button
                onClick={() => setRepoPath('')}
                style={{
                  background: !repoPath ? 'rgba(56, 189, 248, 0.2)' : '#0c121d',
                  border: `1px solid ${!repoPath ? '#38bdf8' : '#1e293b'}`,
                  borderRadius: '4px',
                  padding: '4px 9px',
                  color: !repoPath ? '#38bdf8' : '#94a3b8',
                  fontSize: '0.725rem',
                  fontWeight: !repoPath ? 600 : 400,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px'
                }}
              >
                <Sparkles size={12} color={!repoPath ? '#38bdf8' : '#64748b'} />
                <span>+ New Clean Workspace (Isolated)</span>
              </button>

              {sampleRepos.map((sr) => (
                <button
                  key={sr.id}
                  onClick={() => setRepoPath(sr.path)}
                  style={{
                    background: repoPath === sr.path ? 'rgba(56, 189, 248, 0.15)' : '#0c121d',
                    border: `1px solid ${repoPath === sr.path ? '#38bdf8' : '#1e293b'}`,
                    borderRadius: '4px',
                    padding: '4px 9px',
                    color: repoPath === sr.path ? '#38bdf8' : '#94a3b8',
                    fontSize: '0.7rem',
                    cursor: 'pointer'
                  }}
                >
                  {sr.name.split('(')[0].trim()}
                </button>
              ))}
            </div>
          </div>

          {/* New Clean Workspace Information Card */}
          {!repoPath && (
            <div style={{
              backgroundColor: '#0c121d',
              border: '1px solid #1e293b',
              borderRadius: '8px',
              padding: '14px',
              display: 'flex',
              flexDirection: 'column',
              gap: '8px'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span className="badge badge-emerald" style={{ fontSize: '0.65rem' }}>Isolated Mode</span>
                <span style={{ fontSize: '0.775rem', fontWeight: 600, color: '#f8fafc' }}>Fresh Task Folder</span>
              </div>
              <p style={{ fontSize: '0.75rem', color: '#94a3b8', lineHeight: '1.4', margin: 0 }}>
                A brand-new isolated workspace folder (<code>sandbox/workspace_&lt;run_id&gt;</code>) will be created automatically for this task with clean <code>app/</code> and <code>tests/</code> directories. Code and tests will not pollute existing repositories.
              </p>
            </div>
          )}

          {/* Existing Workspace Telemetry Cards */}
          {repoInspection && (
            <div style={{
              backgroundColor: '#0c121d',
              border: '1px solid #1e293b',
              borderRadius: '8px',
              padding: '12px',
              display: 'flex',
              flexDirection: 'column',
              gap: '8px'
            }}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                <div style={{ background: '#151d2e', padding: '8px', borderRadius: '6px' }}>
                  <span style={{ fontSize: '0.65rem', color: '#64748b', display: 'block' }}>Files in Repo</span>
                  <span style={{ fontSize: '1rem', fontWeight: 700, color: '#38bdf8' }}>{repoInspection.total_files}</span>
                </div>
                <div style={{ background: '#151d2e', padding: '8px', borderRadius: '6px' }}>
                  <span style={{ fontSize: '0.65rem', color: '#64748b', display: 'block' }}>Lines of Code</span>
                  <span style={{ fontSize: '1rem', fontWeight: 700, color: '#34d399' }}>{repoInspection.total_lines_of_code}</span>
                </div>
              </div>

              <div style={{ fontSize: '0.725rem', color: '#94a3b8', display: 'flex', justifyContent: 'space-between' }}>
                <span>Test Framework:</span>
                <span className="badge badge-cyan" style={{ fontSize: '0.65rem' }}>
                  {repoInspection.test_framework}
                </span>
              </div>

              <div style={{ fontSize: '0.725rem', color: '#94a3b8', display: 'flex', justifyContent: 'space-between' }}>
                <span>Detected Languages:</span>
                <span style={{ color: '#cbd5e1' }}>{repoInspection.detected_languages.join(', ')}</span>
              </div>

              {/* Scanned Files List */}
              <div style={{ marginTop: '4px' }}>
                <span style={{ fontSize: '0.675rem', color: '#64748b', display: 'block', marginBottom: '4px' }}>
                  Existing Files:
                </span>
                <div style={{
                  maxHeight: '120px',
                  overflowY: 'auto',
                  backgroundColor: '#070a10',
                  padding: '6px 8px',
                  borderRadius: '4px',
                  fontSize: '0.7rem',
                  fontFamily: 'var(--font-mono)',
                  color: '#94a3b8'
                }}>
                  {repoInspection.files.length > 0 ? (
                    repoInspection.files.map((f, idx) => (
                      <div key={idx} style={{ display: 'flex', justifyContent: 'space-between', padding: '2px 0' }}>
                        <span>{f.path}</span>
                        <span style={{ color: '#475569' }}>{f.lines_of_code} loc</span>
                      </div>
                    ))
                  ) : (
                    <span style={{ color: '#64748b' }}>Empty repository (files will be created)</span>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
