import React, { useState } from 'react';
import { 
  FileCode2, 
  ArrowRight, 
  Copy, 
  Check 
} from 'lucide-react';

export default function CodingAgentView({
  codeChanges = [],
  onExecuteTesting,
  isTesting
}) {
  const [selectedFileIndex, setSelectedFileIndex] = useState(0);
  const [viewMode, setViewMode] = useState('diff'); // 'diff' or 'full'
  const [copied, setCopied] = useState(false);

  if (!codeChanges || codeChanges.length === 0) {
    return (
      <div className="card-panel" style={{ padding: '40px', textAlign: 'center' }}>
        <FileCode2 size={36} color="#64748b" style={{ margin: '0 auto 12px' }} />
        <h3 style={{ fontSize: '1.1rem', color: '#f1f5f9', marginBottom: '8px' }}>No Code Changes Generated Yet</h3>
        <p style={{ fontSize: '0.85rem', color: '#94a3b8', maxWidth: '500px', margin: '0 auto 16px' }}>
          Execute the Coding Agent from Stage 3 to generate source code and unified git diffs.
        </p>
      </div>
    );
  }

  const currentChange = codeChanges[selectedFileIndex] || codeChanges[0];
  const totalAdded = codeChanges.reduce((acc, c) => acc + (c.lines_added || 0), 0);
  const totalRemoved = codeChanges.reduce((acc, c) => acc + (c.lines_removed || 0), 0);
  const allAstValid = codeChanges.every((c) => c.ast_valid);

  const handleCopy = () => {
    const textToCopy = viewMode === 'diff' ? currentChange.diff_patch : currentChange.new_content;
    navigator.clipboard.writeText(textToCopy);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Top Banner */}
      <div className="card-panel" style={{
        padding: '20px 24px',
        background: 'linear-gradient(135deg, #101626 0%, #0d121f 100%)',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        flexWrap: 'wrap',
        gap: '16px'
      }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
            <span className="badge badge-cyan">Stage 4: Coding Agent</span>
            <span className={`badge ${allAstValid ? 'badge-emerald' : 'badge-rose'}`} style={{ fontSize: '0.65rem' }}>
              {allAstValid ? '✓ AST Syntax Verified' : 'AST Errors Detected'}
            </span>
          </div>
          <h2 style={{ fontSize: '1.25rem', fontWeight: 700, color: '#f8fafc', marginBottom: '4px' }}>
            Source Code Implementation & Unified Diffs
          </h2>
          <p style={{ fontSize: '0.825rem', color: '#94a3b8' }}>
            Generated {codeChanges.length} production files (<span style={{ color: '#34d399' }}>+{totalAdded} lines</span>, <span style={{ color: '#fb7185' }}>-{totalRemoved} lines</span>) with automated syntax validation.
          </p>
        </div>

        {/* Action Button */}
        <button
          className="btn btn-emerald"
          onClick={onExecuteTesting}
          disabled={isTesting}
          style={{
            padding: '10px 20px',
            fontWeight: 600
          }}
        >
          <span>{isTesting ? 'Running Pytest & Self-Healing...' : 'Execute Test & Debugging (Stage 5)'}</span>
          <ArrowRight size={15} />
        </button>
      </div>

      {/* Main Diff & Code Inspector Workspace */}
      <div style={{ display: 'grid', gridTemplateColumns: '260px 1fr', gap: '16px', alignItems: 'flex-start' }}>
        {/* Left: File Navigator */}
        <div className="card-panel" style={{ padding: '14px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <div style={{ fontSize: '0.75rem', fontWeight: 600, color: '#64748b', textTransform: 'uppercase', marginBottom: '4px' }}>
            Generated Files ({codeChanges.length})
          </div>

          {codeChanges.map((change, idx) => {
            const isSelected = selectedFileIndex === idx;
            return (
              <button
                key={change.id || idx}
                onClick={() => setSelectedFileIndex(idx)}
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '4px',
                  padding: '10px 12px',
                  borderRadius: '6px',
                  border: `1px solid ${isSelected ? '#38bdf8' : '#1e293b'}`,
                  background: isSelected ? 'rgba(56, 189, 248, 0.1)' : '#0c121d',
                  color: isSelected ? '#38bdf8' : '#cbd5e1',
                  textAlign: 'left',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
                  <span style={{ fontSize: '0.8rem', fontWeight: 600, fontFamily: 'var(--font-mono)' }}>
                    {change.file_path.split('/').pop()}
                  </span>
                  <span className={`badge ${change.action === 'created' ? 'badge-emerald' : 'badge-cyan'}`} style={{ fontSize: '0.6rem', padding: '1px 5px' }}>
                    {change.action}
                  </span>
                </div>
                <span style={{ fontSize: '0.7rem', color: '#64748b', fontFamily: 'var(--font-mono)' }}>
                  {change.file_path}
                </span>
                <div style={{ display: 'flex', gap: '8px', fontSize: '0.675rem', marginTop: '2px' }}>
                  <span style={{ color: '#34d399' }}>+{change.lines_added}</span>
                  <span style={{ color: '#fb7185' }}>-{change.lines_removed}</span>
                  {change.ast_valid && <span style={{ color: '#38bdf8', marginLeft: 'auto' }}>AST OK</span>}
                </div>
              </button>
            );
          })}
        </div>

        {/* Right: Diff / Code Content Viewer */}
        <div className="card-panel" style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          {/* Header Bar */}
          <div style={{
            padding: '12px 18px',
            backgroundColor: '#0c121d',
            borderBottom: '1px solid #1e293b',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <FileCode2 size={16} color="#38bdf8" />
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.85rem', fontWeight: 600, color: '#f8fafc' }}>
                {currentChange.file_path}
              </span>
              <span className={`badge ${currentChange.action === 'created' ? 'badge-emerald' : 'badge-cyan'}`} style={{ fontSize: '0.65rem' }}>
                {currentChange.action}
              </span>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              {/* View Toggle */}
              <div style={{ display: 'flex', backgroundColor: '#151d2e', borderRadius: '6px', padding: '2px', border: '1px solid #1e293b' }}>
                <button
                  onClick={() => setViewMode('diff')}
                  style={{
                    background: viewMode === 'diff' ? '#0284c7' : 'transparent',
                    color: viewMode === 'diff' ? '#fff' : '#94a3b8',
                    border: 'none',
                    padding: '3px 10px',
                    borderRadius: '4px',
                    fontSize: '0.725rem',
                    cursor: 'pointer'
                  }}
                >
                  Unified Diff
                </button>
                <button
                  onClick={() => setViewMode('full')}
                  style={{
                    background: viewMode === 'full' ? '#0284c7' : 'transparent',
                    color: viewMode === 'full' ? '#fff' : '#94a3b8',
                    border: 'none',
                    padding: '3px 10px',
                    borderRadius: '4px',
                    fontSize: '0.725rem',
                    cursor: 'pointer'
                  }}
                >
                  Full Source
                </button>
              </div>

              {/* Copy Button */}
              <button
                className="btn btn-secondary btn-sm"
                onClick={handleCopy}
                style={{ padding: '4px 8px', fontSize: '0.725rem' }}
              >
                {copied ? <Check size={13} color="#10b981" /> : <Copy size={13} />}
                <span>{copied ? 'Copied!' : 'Copy'}</span>
              </button>
            </div>
          </div>

          {/* Code Viewer Body */}
          <div style={{
            padding: '16px',
            backgroundColor: '#070a10',
            fontFamily: 'var(--font-mono)',
            fontSize: '0.8rem',
            lineHeight: '1.6',
            maxHeight: '520px',
            overflowY: 'auto',
            color: '#f8fafc'
          }}>
            {viewMode === 'diff' ? (
              <div>
                {(currentChange.diff_patch || '').split('\n').map((line, idx) => {
                  let bg = 'transparent';
                  let color = '#94a3b8';
                  if (line.startsWith('+') && !line.startsWith('+++')) {
                    bg = 'rgba(16, 185, 129, 0.12)';
                    color = '#34d399';
                  } else if (line.startsWith('-') && !line.startsWith('---')) {
                    bg = 'rgba(244, 63, 94, 0.12)';
                    color = '#fb7185';
                  } else if (line.startsWith('@@')) {
                    color = '#38bdf8';
                    bg = 'rgba(56, 189, 248, 0.05)';
                  }
                  return (
                    <div 
                      key={idx} 
                      style={{ 
                        backgroundColor: bg, 
                        color: color, 
                        padding: '1px 8px',
                        borderRadius: '2px',
                        whiteSpace: 'pre-wrap',
                        wordBreak: 'break-all'
                      }}
                    >
                      <span style={{ color: '#475569', display: 'inline-block', width: '36px', userSelect: 'none' }}>
                        {idx + 1}
                      </span>
                      {line}
                    </div>
                  );
                })}
              </div>
            ) : (
              <div>
                {(currentChange.new_content || '').split('\n').map((line, idx) => (
                  <div key={idx} style={{ padding: '1px 8px', whiteSpace: 'pre-wrap' }}>
                    <span style={{ color: '#475569', display: 'inline-block', width: '36px', userSelect: 'none' }}>
                      {idx + 1}
                    </span>
                    <span style={{ color: '#e2e8f0' }}>{line}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
