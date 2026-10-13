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
  Check
} from 'lucide-react';

export default function TestingDebugView({
  testResults = [],
  recoveryAttempts = [],
  onExecuteVerification,
  isVerifying,
  onNavigateToStage
}) {
  const [selectedAttemptIndex, setSelectedAttemptIndex] = useState(
    testResults.length > 0 ? testResults.length - 1 : 0
  );

  if (!testResults || testResults.length === 0) {
    return (
      <div className="card-panel" style={{ padding: '40px', textAlign: 'center' }}>
        <FlaskConical size={36} color="#64748b" style={{ margin: '0 auto 12px' }} />
        <h3 style={{ fontSize: '1.1rem', color: '#f1f5f9', marginBottom: '8px' }}>No Test Executions Recorded Yet</h3>
        <p style={{ fontSize: '0.85rem', color: '#94a3b8', maxWidth: '500px', margin: '0 auto 16px' }}>
          Execute the Test & Debugging Agent from Stage 4 to run the pytest suite and trigger bounded self-healing recovery.
        </p>
      </div>
    );
  }

  const latestResult = testResults[selectedAttemptIndex] || testResults[testResults.length - 1];
  const isPassed = latestResult?.status === 'PASSED';

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
            <span className="badge badge-cyan">Stage 5: Testing & Debugging Agents</span>
            <span className={`badge ${isPassed ? 'badge-emerald' : 'badge-rose'}`} style={{ fontSize: '0.65rem' }}>
              {isPassed ? '✓ All Tests Passed' : 'Tests Failed — Self-Healing Triggered'}
            </span>
          </div>
          <h2 style={{ fontSize: '1.25rem', fontWeight: 700, color: '#f8fafc', marginBottom: '4px' }}>
            Automated Pytest Execution & Bounded Recovery
          </h2>
          <p style={{ fontSize: '0.825rem', color: '#94a3b8' }}>
            Executed {latestResult.total_tests} test assertions ({latestResult.passed_tests} passed, {latestResult.failed_tests} failed) in {latestResult.duration_seconds}s across {testResults.length} test run attempt(s).
          </p>
        </div>

        {/* Action Button */}
        <button
          className="btn btn-primary"
          onClick={onExecuteVerification}
          disabled={isVerifying}
          style={{
            padding: '10px 20px',
            fontWeight: 600,
            background: 'linear-gradient(135deg, #0284c7 0%, #0369a1 100%)'
          }}
        >
          <ShieldCheck size={16} />
          <span>{isVerifying ? 'Reviewing Code & Evidence...' : 'Proceed to Code Review & Verifier (Stage 6)'}</span>
          <ArrowRight size={15} />
        </button>
      </div>

      {/* Test Telemetry KPI Row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '12px' }}>
        <div className="card-panel" style={{ padding: '14px 16px' }}>
          <span style={{ fontSize: '0.675rem', color: '#64748b', textTransform: 'uppercase', display: 'block', marginBottom: '2px' }}>
            Suite Status
          </span>
          <span style={{ fontSize: '1.1rem', fontWeight: 700, color: isPassed ? '#34d399' : '#fb7185' }}>
            {latestResult.status}
          </span>
        </div>

        <div className="card-panel" style={{ padding: '14px 16px' }}>
          <span style={{ fontSize: '0.675rem', color: '#64748b', textTransform: 'uppercase', display: 'block', marginBottom: '2px' }}>
            Passed / Total Tests
          </span>
          <span style={{ fontSize: '1.1rem', fontWeight: 700, color: '#38bdf8' }}>
            {latestResult.passed_tests} / {latestResult.total_tests} ({Math.round((latestResult.passed_tests / (latestResult.total_tests || 1)) * 100)}%)
          </span>
        </div>

        <div className="card-panel" style={{ padding: '14px 16px' }}>
          <span style={{ fontSize: '0.675rem', color: '#64748b', textTransform: 'uppercase', display: 'block', marginBottom: '2px' }}>
            Execution Time
          </span>
          <span style={{ fontSize: '1.1rem', fontWeight: 700, color: '#a78bfa' }}>
            {latestResult.duration_seconds}s
          </span>
        </div>

        <div className="card-panel" style={{ padding: '14px 16px' }}>
          <span style={{ fontSize: '0.675rem', color: '#64748b', textTransform: 'uppercase', display: 'block', marginBottom: '2px' }}>
            Recovery Retries
          </span>
          <span style={{ fontSize: '1.1rem', fontWeight: 700, color: '#fbbf24' }}>
            {recoveryAttempts.length} Attempt(s)
          </span>
        </div>
      </div>

      {/* Two Column: Test Cases List & Bounded Recovery Center */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: '16px' }}>
        
        {/* Left: Test Case Assertions Breakdown */}
        <div className="card-panel" style={{ padding: '18px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h3 style={{ fontSize: '0.9rem', fontWeight: 600, color: '#f1f5f9', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <FlaskConical size={16} color="#38bdf8" />
              <span>Executed Test Cases ({latestResult.test_items?.length || 0})</span>
            </h3>
            {testResults.length > 1 && (
              <div style={{ display: 'flex', gap: '4px' }}>
                {testResults.map((tr, idx) => (
                  <button
                    key={idx}
                    onClick={() => setSelectedAttemptIndex(idx)}
                    style={{
                      background: selectedAttemptIndex === idx ? '#0284c7' : '#151d2e',
                      color: selectedAttemptIndex === idx ? '#fff' : '#94a3b8',
                      border: '1px solid #1e293b',
                      borderRadius: '4px',
                      padding: '2px 6px',
                      fontSize: '0.65rem',
                      cursor: 'pointer'
                    }}
                  >
                    Attempt #{tr.attempt_number}
                  </button>
                ))}
              </div>
            )}
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {(latestResult.test_items || []).map((item, idx) => (
              <div
                key={idx}
                style={{
                  backgroundColor: '#0c121d',
                  border: `1px solid ${item.status === 'PASSED' ? '#1e293b' : 'rgba(244, 63, 94, 0.4)'}`,
                  borderRadius: '6px',
                  padding: '10px 12px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  {item.status === 'PASSED' ? (
                    <CheckCircle2 size={16} color="#10b981" />
                  ) : (
                    <XCircle size={16} color="#f43f5e" />
                  )}
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem', color: '#f8fafc' }}>
                    {item.name}
                  </span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ fontSize: '0.675rem', color: '#64748b' }}>{item.duration_ms}ms</span>
                  <span className={`badge ${item.status === 'PASSED' ? 'badge-emerald' : 'badge-rose'}`} style={{ fontSize: '0.65rem' }}>
                    {item.status}
                  </span>
                </div>
              </div>
            ))}
          </div>

          {/* Test Runner Terminal Output */}
          <div style={{ marginTop: '8px' }}>
            <div style={{ fontSize: '0.75rem', fontWeight: 600, color: '#64748b', marginBottom: '4px', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Terminal size={13} />
              <span>Raw Pytest Terminal Output:</span>
            </div>
            <pre style={{
              backgroundColor: '#070a10',
              border: '1px solid #1e293b',
              borderRadius: '6px',
              padding: '12px',
              fontSize: '0.75rem',
              fontFamily: 'var(--font-mono)',
              color: '#cbd5e1',
              maxHeight: '160px',
              overflowY: 'auto',
              whiteSpace: 'pre-wrap'
            }}>
              {latestResult.stdout || latestResult.stderr || '(No output recorded)'}
            </pre>
          </div>
        </div>

        {/* Right: Bounded Self-Healing Recovery Center */}
        <div className="card-panel" style={{ padding: '18px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <h3 style={{ fontSize: '0.9rem', fontWeight: 600, color: '#f1f5f9', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <RefreshCw size={16} color="#fbbf24" />
            <span>Bounded Self-Healing Recovery Loop</span>
          </h3>

          {recoveryAttempts.length === 0 ? (
            <div style={{
              backgroundColor: 'rgba(16, 185, 129, 0.08)',
              border: '1px solid rgba(52, 211, 153, 0.3)',
              borderRadius: '8px',
              padding: '18px',
              textAlign: 'center'
            }}>
              <CheckCircle2 size={28} color="#10b981" style={{ margin: '0 auto 8px' }} />
              <h4 style={{ fontSize: '0.9rem', fontWeight: 600, color: '#34d399', marginBottom: '4px' }}>
                Zero Recovery Retries Needed
              </h4>
              <p style={{ fontSize: '0.775rem', color: '#94a3b8' }}>
                Implementation passed all test assertions on Attempt #1 with zero test failures or regressions.
              </p>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {recoveryAttempts.map((rec, idx) => (
                <div
                  key={rec.id || idx}
                  style={{
                    backgroundColor: '#0c121d',
                    border: '1px solid #1e293b',
                    borderRadius: '8px',
                    padding: '12px 14px'
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                    <span className="badge badge-amber" style={{ fontSize: '0.65rem' }}>
                      Recovery Attempt #{rec.attempt_number}
                    </span>
                    <span className={`badge ${rec.resolved ? 'badge-emerald' : 'badge-rose'}`} style={{ fontSize: '0.65rem' }}>
                      {rec.resolved ? '✓ Resolved 100% Pass' : 'Failure Diagnosed'}
                    </span>
                  </div>

                  <div style={{ fontSize: '0.8rem', fontWeight: 600, color: '#fb7185', marginBottom: '4px' }}>
                    Failure: {rec.failure_reason}
                  </div>

                  <p style={{ fontSize: '0.75rem', color: '#cbd5e1', marginBottom: '6px' }}>
                    <strong>Diagnosis:</strong> {rec.diagnosis}
                  </p>

                  <p style={{ fontSize: '0.75rem', color: '#38bdf8', marginBottom: '6px' }}>
                    <strong>Applied Fix:</strong> {rec.proposed_fix}
                  </p>

                  <div style={{ fontSize: '0.7rem', color: '#64748b' }}>
                    Modified: {rec.files_modified?.join(', ')}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
