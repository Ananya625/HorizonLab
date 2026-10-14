import React, { useState } from 'react';
import { 
  FlaskConical, 
  CheckCircle2, 
  XCircle, 
  AlertTriangle, 
  Terminal, 
  ArrowRight, 
  RefreshCw, 
  ShieldCheck, 
  Clock, 
  FileCode2,
  ChevronDown,
  ChevronUp,
  GitCommit,
  Check,
  AlertCircle
} from 'lucide-react';

export default function TestingDebugView({
  testResults = [],
  recoveryAttempts = [],
  onExecuteTesting,
  isTesting,
  onExecuteVerification,
  isVerifying,
  onNavigateToStage
}) {
  const [selectedAttemptIndex, setSelectedAttemptIndex] = useState(
    testResults.length > 0 ? testResults.length - 1 : 0
  );
  const [expandedTestIdx, setExpandedTestIdx] = useState(null);

  if (!testResults || testResults.length === 0) {
    return (
      <div className="card-panel" style={{ padding: '48px 24px', textAlign: 'center', backgroundColor: '#FFFFFF' }}>
        <FlaskConical size={36} color="var(--text-muted, #98A2B3)" style={{ margin: '0 auto 12px' }} />
        <h3 style={{ fontSize: '1.15rem', color: 'var(--text-primary, #172033)', marginBottom: '8px' }}>
          No Test Executions Recorded Yet
        </h3>
        <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary, #667085)', maxWidth: '520px', margin: '0 auto 20px' }}>
          Execute the Test & Debugging Agent to run the automated pytest suite and trigger bounded self-healing recovery.
        </p>
        {onExecuteTesting && (
          <button
            type="button"
            className="btn btn-emerald"
            onClick={onExecuteTesting}
            disabled={isTesting}
            style={{ padding: '10px 20px', fontWeight: 600, margin: '0 auto' }}
          >
            <FlaskConical size={16} />
            <span>{isTesting ? 'Running Pytest Suite...' : 'Execute Test & Debugging (Stage 5)'}</span>
          </button>
        )}
      </div>
    );
  }

  const latestResult = testResults[selectedAttemptIndex] || testResults[testResults.length - 1];
  const isPassed = latestResult?.status === 'PASSED';
  const totalTests = latestResult?.total_tests ?? 0;
  const passedTests = latestResult?.passed_tests ?? 0;
  const failedTests = latestResult?.failed_tests ?? (totalTests - passedTests);
  const skippedTests = latestResult?.skipped_tests ?? 0;
  const durationSec = latestResult?.duration_seconds != null ? `${latestResult.duration_seconds}s` : '—';

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
            <span className="badge badge-purple">Stage 5: Test & Debug</span>
            <span className={`badge ${isPassed ? 'badge-emerald' : 'badge-rose'}`} style={{ fontSize: '0.65rem' }}>
              {isPassed ? '✓ All Tests Passed' : 'Failures Detected — Bounded Recovery'}
            </span>
          </div>
          <h2 style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--text-primary, #172033)', marginBottom: '4px' }}>
            Automated Pytest Execution & Diagnostic Dashboard
          </h2>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary, #667085)', margin: 0 }}>
            Executed {totalTests} test case(s) with {passedTests} passed, {failedTests} failed in {durationSec} across {testResults.length} test run attempt(s).
          </p>
        </div>

        {/* Action Buttons */}
        <div style={{ display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
          {onExecuteTesting && (
            <button
              type="button"
              className="btn btn-secondary"
              onClick={onExecuteTesting}
              disabled={isTesting || isVerifying}
              style={{ padding: '9px 16px', fontWeight: 600 }}
            >
              <RefreshCw size={14} className={isTesting ? 'animate-spin' : ''} />
              <span>{isTesting ? 'Running Pytest...' : 'Re-run Tests & Recovery'}</span>
            </button>
          )}

          <button
            type="button"
            className="btn btn-primary"
            onClick={onExecuteVerification}
            disabled={isVerifying || isTesting}
            style={{ padding: '9px 18px', fontWeight: 600 }}
          >
            <ShieldCheck size={16} />
            <span>{isVerifying ? 'Reviewing Code...' : 'Proceed to Code Review (Stage 6)'}</span>
            <ArrowRight size={15} />
          </button>
        </div>
      </section>

      {/* A. Test Summary Metrics Row */}
      <section style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '12px' }}>
        <div className="card-panel" style={{ padding: '14px 16px', backgroundColor: '#FFFFFF' }}>
          <span style={{ fontSize: '0.675rem', color: 'var(--text-secondary, #667085)', textTransform: 'uppercase', display: 'block', marginBottom: '4px', fontWeight: 500 }}>
            Suite Status
          </span>
          <span style={{ fontSize: '1.15rem', fontWeight: 700, color: isPassed ? 'var(--success-color, #16845B)' : 'var(--danger-color, #D14343)' }}>
            {latestResult.status || 'UNKNOWN'}
          </span>
        </div>

        <div className="card-panel" style={{ padding: '14px 16px', backgroundColor: '#FFFFFF' }}>
          <span style={{ fontSize: '0.675rem', color: 'var(--text-secondary, #667085)', textTransform: 'uppercase', display: 'block', marginBottom: '4px', fontWeight: 500 }}>
            Total Tests
          </span>
          <span style={{ fontSize: '1.15rem', fontWeight: 700, color: 'var(--text-primary, #172033)' }}>
            {totalTests}
          </span>
        </div>

        <div className="card-panel" style={{ padding: '14px 16px', backgroundColor: '#FFFFFF' }}>
          <span style={{ fontSize: '0.675rem', color: 'var(--text-secondary, #667085)', textTransform: 'uppercase', display: 'block', marginBottom: '4px', fontWeight: 500 }}>
            Passed Tests
          </span>
          <span style={{ fontSize: '1.15rem', fontWeight: 700, color: 'var(--success-color, #16845B)' }}>
            {passedTests}
          </span>
        </div>

        <div className="card-panel" style={{ padding: '14px 16px', backgroundColor: '#FFFFFF' }}>
          <span style={{ fontSize: '0.675rem', color: 'var(--text-secondary, #667085)', textTransform: 'uppercase', display: 'block', marginBottom: '4px', fontWeight: 500 }}>
            Failed Tests
          </span>
          <span style={{ fontSize: '1.15rem', fontWeight: 700, color: failedTests > 0 ? 'var(--danger-color, #D14343)' : 'var(--text-secondary, #667085)' }}>
            {failedTests}
          </span>
        </div>

        <div className="card-panel" style={{ padding: '14px 16px', backgroundColor: '#FFFFFF' }}>
          <span style={{ fontSize: '0.675rem', color: 'var(--text-secondary, #667085)', textTransform: 'uppercase', display: 'block', marginBottom: '4px', fontWeight: 500 }}>
            Skipped Tests
          </span>
          <span style={{ fontSize: '1.15rem', fontWeight: 700, color: 'var(--text-secondary, #667085)' }}>
            {skippedTests}
          </span>
        </div>

        <div className="card-panel" style={{ padding: '14px 16px', backgroundColor: '#FFFFFF' }}>
          <span style={{ fontSize: '0.675rem', color: 'var(--text-secondary, #667085)', textTransform: 'uppercase', display: 'block', marginBottom: '4px', fontWeight: 500 }}>
            Execution Duration
          </span>
          <span style={{ fontSize: '1.15rem', fontWeight: 700, color: 'var(--accent-primary, #6257D9)' }}>
            {durationSec}
          </span>
        </div>

        <div className="card-panel" style={{ padding: '14px 16px', backgroundColor: '#FFFFFF' }}>
          <span style={{ fontSize: '0.675rem', color: 'var(--text-secondary, #667085)', textTransform: 'uppercase', display: 'block', marginBottom: '4px', fontWeight: 500 }}>
            Recovery Retries
          </span>
          <span style={{ fontSize: '1.15rem', fontWeight: 700, color: recoveryAttempts.length > 0 ? 'var(--warning-color, #B7791F)' : 'var(--success-color, #16845B)' }}>
            {recoveryAttempts.length}
          </span>
        </div>
      </section>

      {/* Main Two Columns: B. Test Case List & C. Recovery Timeline */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: '16px', alignItems: 'flex-start' }}>
        
        {/* B. Test Case List */}
        <section className="card-panel" style={{ padding: '20px', backgroundColor: '#FFFFFF', display: 'flex', flexDirection: 'column', gap: '14px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px' }}>
            <h3 style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--text-primary, #172033)', display: 'flex', alignItems: 'center', gap: '8px', margin: 0 }}>
              <FlaskConical size={16} color="var(--accent-primary, #6257D9)" />
              <span>Executed Test Cases ({latestResult.test_items?.length || 0})</span>
            </h3>

            {testResults.length > 1 && (
              <div style={{ display: 'flex', gap: '4px', alignItems: 'center' }}>
                <span style={{ fontSize: '0.7rem', color: 'var(--text-secondary, #667085)' }}>Run:</span>
                {testResults.map((tr, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => setSelectedAttemptIndex(idx)}
                    style={{
                      background: selectedAttemptIndex === idx ? 'var(--accent-primary, #6257D9)' : '#FFFFFF',
                      color: selectedAttemptIndex === idx ? '#FFFFFF' : 'var(--text-secondary, #667085)',
                      border: '1px solid var(--border-subtle, #E5E7EF)',
                      borderRadius: '4px',
                      padding: '3px 8px',
                      fontSize: '0.7rem',
                      fontWeight: 600,
                      cursor: 'pointer'
                    }}
                  >
                    Attempt #{tr.attempt_number || idx + 1}
                  </button>
                ))}
              </div>
            )}
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {(latestResult.test_items || []).map((item, idx) => {
              const isTestPassed = item.status === 'PASSED';
              const isExpanded = expandedTestIdx === idx;
              return (
                <div
                  key={idx}
                  style={{
                    backgroundColor: isTestPassed ? 'var(--bg-page, #F6F7FB)' : '#FEF2F2',
                    border: `1px solid ${isTestPassed ? 'var(--border-subtle, #E5E7EF)' : '#FECACA'}`,
                    borderRadius: '6px',
                    padding: '10px 14px',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '6px'
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      {isTestPassed ? (
                        <CheckCircle2 size={16} color="var(--success-color, #16845B)" />
                      ) : (
                        <XCircle size={16} color="var(--danger-color, #D14343)" />
                      )}
                      <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-primary, #172033)' }}>
                        {item.name}
                      </span>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      {item.duration_ms != null && (
                        <span style={{ fontSize: '0.7rem', color: 'var(--text-secondary, #667085)' }}>
                          {item.duration_ms}ms
                        </span>
                      )}
                      <span className={`badge ${isTestPassed ? 'badge-emerald' : 'badge-rose'}`} style={{ fontSize: '0.65rem' }}>
                        {item.status}
                      </span>
                      {item.failure_message && (
                        <button
                          type="button"
                          onClick={() => setExpandedTestIdx(isExpanded ? null : idx)}
                          className="btn btn-ghost btn-sm"
                          style={{ padding: '2px 6px', fontSize: '0.7rem' }}
                        >
                          {isExpanded ? 'Hide Trace' : 'View Trace'}
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Expandable Failure Details */}
                  {isExpanded && item.failure_message && (
                    <div style={{
                      marginTop: '6px',
                      padding: '8px 10px',
                      backgroundColor: '#FFFFFF',
                      borderRadius: '4px',
                      border: '1px solid #FECACA',
                      fontSize: '0.75rem',
                      fontFamily: 'var(--font-mono)',
                      color: 'var(--danger-color, #D14343)',
                      whiteSpace: 'pre-wrap',
                      overflowX: 'auto'
                    }}>
                      {item.failure_message}
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {/* Test Runner Terminal Output (Collapsed by default) */}
          <details style={{ marginTop: '8px', borderTop: '1px solid var(--border-subtle, #E5E7EF)', paddingTop: '10px' }}>
            <summary style={{ fontSize: '0.8rem', color: 'var(--text-secondary, #667085)', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Terminal size={13} />
              <span>Raw Pytest Terminal Output</span>
            </summary>
            <pre style={{
              marginTop: '8px',
              backgroundColor: 'var(--bg-page, #F6F7FB)',
              border: '1px solid var(--border-subtle, #E5E7EF)',
              borderRadius: '6px',
              padding: '12px',
              fontSize: '0.75rem',
              fontFamily: 'var(--font-mono)',
              color: 'var(--text-primary, #172033)',
              maxHeight: '200px',
              overflowY: 'auto',
              whiteSpace: 'pre-wrap'
            }}>
              {latestResult.stdout || latestResult.stderr || '(No terminal output recorded)'}
            </pre>
          </details>
        </section>

        {/* C. Recovery Timeline */}
        <section className="card-panel" style={{ padding: '20px', backgroundColor: '#FFFFFF', display: 'flex', flexDirection: 'column', gap: '14px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h3 style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--text-primary, #172033)', display: 'flex', alignItems: 'center', gap: '8px', margin: 0 }}>
              <RefreshCw size={16} color="var(--warning-color, #B7791F)" />
              <span>Bounded Recovery Timeline</span>
            </h3>
            <span className="badge badge-slate" style={{ fontSize: '0.65rem' }}>
              {recoveryAttempts.length} Attempt(s)
            </span>
          </div>

          {recoveryAttempts.length === 0 ? (
            <div style={{
              backgroundColor: 'var(--success-subtle, #ECFDF5)',
              border: '1px solid var(--success-border, #A7F3D0)',
              borderRadius: '8px',
              padding: '24px 18px',
              textAlign: 'center'
            }}>
              <CheckCircle2 size={28} color="var(--success-color, #16845B)" style={{ margin: '0 auto 8px' }} />
              <h4 style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--success-color, #16845B)', marginBottom: '4px' }}>
                Zero Recovery Retries Needed
              </h4>
              <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary, #667085)', margin: 0 }}>
                Implementation passed test assertions on Attempt #1 with zero test failures or regressions.
              </p>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {recoveryAttempts.map((rec, idx) => {
                const isVerified = rec.verified_recovered === true;
                const isLocalPass = rec.local_tests_passed;
                let statusBadgeClass = 'badge-rose';
                let statusLabel = 'Recovery failed';
                if (isVerified) {
                  statusBadgeClass = 'badge-emerald';
                  statusLabel = 'Recovery verified';
                } else if (isLocalPass) {
                  statusBadgeClass = 'badge-amber';
                  statusLabel = 'Local tests passed · unverified';
                }

                return (
                  <div
                    key={rec.id || idx}
                    style={{
                      backgroundColor: 'var(--bg-page, #F6F7FB)',
                      border: '1px solid var(--border-subtle, #E5E7EF)',
                      borderRadius: '8px',
                      padding: '14px',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '8px'
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span className="badge badge-purple" style={{ fontSize: '0.675rem' }}>
                        Attempt #{rec.attempt_number || idx + 1}
                      </span>
                      <span className={`badge ${statusBadgeClass}`} style={{ fontSize: '0.65rem' }}>
                        {statusLabel}
                      </span>
                    </div>

                    <div style={{ fontSize: '0.825rem', fontWeight: 600, color: 'var(--danger-color, #D14343)' }}>
                      Failure: {rec.failure_reason}
                    </div>

                    <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary, #667085)', lineHeight: '1.4' }}>
                      <strong style={{ color: 'var(--text-primary, #172033)' }}>Diagnosis:</strong> {rec.diagnosis}
                    </div>

                    <div style={{ fontSize: '0.8rem', color: 'var(--accent-primary, #6257D9)', lineHeight: '1.4' }}>
                      <strong style={{ color: 'var(--text-primary, #172033)' }}>Applied Patch:</strong> {rec.proposed_fix}
                    </div>

                    {rec.files_modified && rec.files_modified.length > 0 && (
                      <div style={{ fontSize: '0.725rem', color: 'var(--text-secondary, #667085)', display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <span>Modified:</span>
                        <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-primary, #172033)' }}>
                          {rec.files_modified.join(', ')}
                        </span>
                      </div>
                    )}

                    {/* Verification & Outcome Details */}
                    <div style={{ 
                      fontSize: '0.725rem', 
                      display: 'flex', 
                      gap: '8px', 
                      alignItems: 'center',
                      borderTop: '1px solid var(--border-subtle, #E5E7EF)',
                      paddingTop: '6px',
                      marginTop: '2px',
                      color: 'var(--text-secondary, #667085)'
                    }}>
                      <span>Tests rerun: <strong>Yes</strong></span>
                      <span>·</span>
                      <span>Outcome: <strong style={{ color: isLocalPass ? 'var(--success-color, #16845B)' : 'var(--danger-color, #D14343)' }}>{isLocalPass ? 'Passed' : 'Failed'}</strong></span>
                      <span>·</span>
                      <span>Verification: <strong style={{ color: isVerified ? 'var(--success-color, #16845B)' : 'var(--warning-color, #B7791F)' }}>{isVerified ? 'Verified' : 'Unverified'}</strong></span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
