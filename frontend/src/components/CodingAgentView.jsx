import React, { useState } from 'react';
import { 
  FileCode2, 
  CheckCircle2, 
  ArrowRight, 
  Copy, 
  Check, 
  Layers, 
  ShieldCheck, 
  Plus, 
  Minus 
} from 'lucide-react';

export default function CodingAgentView({
  codeChanges = [],
  onExecuteTesting,
  isTesting,
  onNavigateToStage
}) {
  const [selectedFileIndex, setSelectedFileIndex] = useState(0);
  const [viewMode, setViewMode] = useState('diff'); // 'diff' or 'full'
  const [copied, setCopied] = useState(false);

  if (!codeChanges || codeChanges.length === 0) {
    return (
      <div className="card-panel" style={{ padding: '48px 24px', textAlign: 'center', backgroundColor: '#FFFFFF' }}>
        <FileCode2 size={36} color="var(--text-muted, #98A2B3)" style={{ margin: '0 auto 12px' }} />
        <h3 style={{ fontSize: '1.15rem', color: 'var(--text-primary, #172033)', marginBottom: '8px' }}>
          No Code Changes Generated Yet
        </h3>
        <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary, #667085)', maxWidth: '520px', margin: '0 auto 16px' }}>
          Execute the Coding Agent from Stage 3 to generate source code files and unified diffs.
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
      <section className="card-panel" style={{
        padding: '20px 24px',
        backgroundColor: '#FFFFFF',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        flexWrap: 'wrap',
        gap: '16px'
      }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
            <span className="badge badge-purple">Stage 4: Coding Agent</span>
            <span className={`badge ${allAstValid ? 'badge-emerald' : 'badge-rose'}`} style={{ fontSize: '0.65rem' }}>
              {allAstValid ? '✓ AST Syntax Validated' : 'Syntax Errors Flagged'}
            </span>
          </div>
          <h2 style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--text-primary, #172033)', marginBottom: '4px' }}>
            Source Code Implementation & Unified Diffs
          </h2>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary, #667085)', margin: 0 }}>
            Generated {codeChanges.length} implementation files (<span style={{ color: 'var(--success-color, #16845B)', fontWeight: 600 }}>+{totalAdded} lines</span>, <span style={{ color: 'var(--danger-color, #D14343)', fontWeight: 600 }}>-{totalRemoved} lines</span>) with automated AST syntax checks.
          </p>
        </div>

        {/* Action Button */}
        <button
          type="button"
          className="btn btn-emerald"
          onClick={onExecuteTesting}
          disabled={isTesting}
          style={{
            padding: '10px 20px',
            fontWeight: 600
          }}
        >
          <span>{isTesting ? 'Running Pytest & Diagnostics...' : 'Execute Test & Debugging (Stage 5)'}</span>
          <ArrowRight size={15} />
        </button>
      </section>

      {/* Main Diff & Code Inspector Workspace */}
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(240px, 280px) 1fr', gap: '16px', alignItems: 'flex-start' }}>
        {/* Left: File Navigator */}
        <div className="card-panel" style={{ padding: '14px', backgroundColor: '#FFFFFF', display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-secondary, #667085)', textTransform: 'uppercase', marginBottom: '4px' }}>
            Generated Files ({codeChanges.length})
          </div>

          {codeChanges.map((change, idx) => {
            const isSelected = selectedFileIndex === idx;
            return (
              <button
                key={change.id || idx}
                type="button"
                onClick={() => setSelectedFileIndex(idx)}
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '4px',
                  padding: '10px 12px',
                  borderRadius: '6px',
                  border: `1px solid ${isSelected ? 'var(--accent-primary, #6257D9)' : 'var(--border-subtle, #E5E7EF)'}`,
                  background: isSelected ? 'var(--accent-primary-subtle, #F0EEFF)' : '#FFFFFF',
                  color: isSelected ? 'var(--accent-primary, #6257D9)' : 'var(--text-primary, #172033)',
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
                <span style={{ fontSize: '0.7rem', color: 'var(--text-secondary, #667085)', fontFamily: 'var(--font-mono)' }}>
                  {change.file_path}
                </span>
                <div style={{ display: 'flex', gap: '8px', fontSize: '0.675rem', marginTop: '2px' }}>
                  <span style={{ color: 'var(--success-color, #16845B)', fontWeight: 600 }}>+{change.lines_added}</span>
                  <span style={{ color: 'var(--danger-color, #D14343)', fontWeight: 600 }}>-{change.lines_removed}</span>
                  {change.ast_valid && (
                    <span style={{ color: 'var(--accent-primary, #6257D9)', marginLeft: 'auto', fontWeight: 500 }}>
                      AST OK
                    </span>
                  )}
                </div>
              </button>
            );
          })}
        </div>

        {/* Right: Diff / Code Content Viewer */}
        <div className="card-panel" style={{ backgroundColor: '#FFFFFF', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          {/* Header Bar */}
          <div style={{
            padding: '12px 18px',
            backgroundColor: 'var(--bg-page, #F6F7FB)',
            borderBottom: '1px solid var(--border-subtle, #E5E7EF)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: '10px'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <FileCode2 size={16} color="var(--accent-primary, #6257D9)" />
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary, #172033)' }}>
                {currentChange.file_path}
              </span>
              <span className={`badge ${currentChange.action === 'created' ? 'badge-emerald' : 'badge-cyan'}`} style={{ fontSize: '0.65rem' }}>
                {currentChange.action}
              </span>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              {/* View Toggle */}
              <div style={{ display: 'flex', backgroundColor: '#FFFFFF', borderRadius: '6px', padding: '2px', border: '1px solid var(--border-subtle, #E5E7EF)' }}>
                <button
                  type="button"
                  onClick={() => setViewMode('diff')}
                  style={{
                    background: viewMode === 'diff' ? 'var(--accent-primary, #6257D9)' : 'transparent',
                    color: viewMode === 'diff' ? '#FFFFFF' : 'var(--text-secondary, #667085)',
                    border: 'none',
                    padding: '4px 10px',
                    borderRadius: '4px',
                    fontSize: '0.725rem',
                    fontWeight: 600,
                    cursor: 'pointer'
                  }}
                >
                  Unified Diff
                </button>
                <button
                  type="button"
                  onClick={() => setViewMode('full')}
                  style={{
                    background: viewMode === 'full' ? 'var(--accent-primary, #6257D9)' : 'transparent',
                    color: viewMode === 'full' ? '#FFFFFF' : 'var(--text-secondary, #667085)',
                    border: 'none',
                    padding: '4px 10px',
                    borderRadius: '4px',
                    fontSize: '0.725rem',
                    fontWeight: 600,
                    cursor: 'pointer'
                  }}
                >
                  Full Source
                </button>
              </div>

              {/* Copy Button */}
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={handleCopy}
                style={{ padding: '4px 8px', fontSize: '0.725rem' }}
              >
                {copied ? <Check size={13} color="var(--success-color, #16845B)" /> : <Copy size={13} />}
                <span>{copied ? 'Copied' : 'Copy'}</span>
              </button>
            </div>
          </div>

          {/* Code Viewer Body */}
          <div style={{
            padding: '16px',
            backgroundColor: '#FFFFFF',
            fontFamily: 'var(--font-mono)',
            fontSize: '0.8rem',
            lineHeight: '1.6',
            maxHeight: '520px',
            overflowY: 'auto',
            color: 'var(--text-primary, #172033)'
          }}>
            {viewMode === 'diff' ? (
              <div>
                {(currentChange.diff_patch || '').split('\n').map((line, idx) => {
                  let bg = 'transparent';
                  let color = '#475569';
                  if (line.startsWith('+') && !line.startsWith('+++')) {
                    bg = '#ECFDF5';
                    color = '#16845B';
                  } else if (line.startsWith('-') && !line.startsWith('---')) {
                    bg = '#FEF2F2';
                    color = '#D14343';
                  } else if (line.startsWith('@@')) {
                    color = '#6257D9';
                    bg = '#F0EEFF';
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
                      <span style={{ color: '#98A2B3', display: 'inline-block', width: '36px', userSelect: 'none' }}>
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
                    <span style={{ color: '#98A2B3', display: 'inline-block', width: '36px', userSelect: 'none' }}>
                      {idx + 1}
                    </span>
                    <span style={{ color: 'var(--text-primary, #172033)' }}>{line}</span>
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
