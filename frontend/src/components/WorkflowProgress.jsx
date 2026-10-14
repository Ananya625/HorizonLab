import React from 'react';
import { 
  CheckCircle2, 
  Circle, 
  AlertCircle, 
  Clock, 
  Layers, 
  Cpu, 
  FileCode2, 
  FlaskConical, 
  ShieldCheck, 
  BarChart3, 
  RefreshCw,
  ArrowRight
} from 'lucide-react';

export default function WorkflowProgress({
  runId,
  currentRunRecord,
  goalModel,
  plan,
  codeChanges = [],
  testResults = [],
  recoveryAttempts = [],
  verification,
  activeTab,
  onNavigateTab,
  isExecuting,
  loading
}) {
  const blockingAmbiguities = (goalModel?.ambiguities || []).filter(a => a.severity === 'blocking' && !a.resolved);
  const hasBlocking = blockingAmbiguities.length > 0;
  const isReqConfirmed = !!goalModel?.is_confirmed;

  const latestTest = testResults.length > 0 ? testResults[testResults.length - 1] : null;
  const isTestPassed = latestTest?.status === 'PASSED';

  const stages = [
    {
      id: 'goal_model',
      name: 'Requirements',
      status: isReqConfirmed 
        ? 'completed' 
        : (hasBlocking ? 'blocked' : (goalModel ? 'pending_review' : (loading ? 'active' : 'pending'))),
      label: isReqConfirmed ? 'Confirmed' : (hasBlocking ? 'Blocked' : (goalModel ? 'Review' : 'Pending'))
    },
    {
      id: 'planner',
      name: 'Planning',
      status: plan ? 'completed' : (isExecuting && activeTab === 'planner' ? 'active' : 'pending'),
      label: plan ? 'Ready' : (isExecuting && activeTab === 'planner' ? 'Planning' : 'Pending')
    },
    {
      id: 'coder',
      name: 'Coding',
      status: codeChanges.length > 0 ? 'completed' : (isExecuting && activeTab === 'coder' ? 'active' : 'pending'),
      label: codeChanges.length > 0 ? `${codeChanges.length} Files` : (isExecuting && activeTab === 'coder' ? 'Writing' : 'Pending')
    },
    {
      id: 'testing',
      name: 'Testing',
      status: latestTest ? (isTestPassed ? 'completed' : 'failed') : (isExecuting && activeTab === 'testing' ? 'active' : 'pending'),
      label: latestTest ? (isTestPassed ? 'Passed' : 'Failed') : (isExecuting && activeTab === 'testing' ? 'Running' : 'Pending')
    },
    {
      id: 'recovery',
      name: 'Recovery',
      status: recoveryAttempts.length > 0 
        ? (recoveryAttempts.some(r => r.verified_recovered) ? 'completed' : 'attention')
        : (isTestPassed ? 'skipped' : 'pending'),
      label: recoveryAttempts.length > 0 
        ? `${recoveryAttempts.length} Retry` 
        : (isTestPassed ? 'None Needed' : 'Pending')
    },
    {
      id: 'verifier',
      name: 'Verification',
      status: verification ? (verification.overall_verdict === 'VERIFIED_PASSED' ? 'completed' : 'attention') : (isExecuting && activeTab === 'verifier' ? 'active' : 'pending'),
      label: verification ? (verification.overall_verdict || 'Reviewed') : (isExecuting && activeTab === 'verifier' ? 'Reviewing' : 'Pending')
    },
    {
      id: 'evaluations',
      name: 'Evaluation',
      status: currentRunRecord?.evaluation ? 'completed' : (activeTab === 'evaluations' ? 'active' : 'pending'),
      label: currentRunRecord?.evaluation ? 'Measured' : 'Pending'
    }
  ];

  const getStatusColor = (status) => {
    switch (status) {
      case 'completed': return { bg: 'var(--success-subtle)', text: 'var(--success-color)', border: 'var(--success-border)', dot: 'var(--success-color)' };
      case 'active': return { bg: 'var(--accent-primary-subtle)', text: 'var(--accent-primary)', border: 'var(--accent-primary-border)', dot: 'var(--accent-primary)' };
      case 'failed':
      case 'blocked': return { bg: 'var(--danger-subtle)', text: 'var(--danger-color)', border: 'var(--danger-border)', dot: 'var(--danger-color)' };
      case 'attention':
      case 'pending_review': return { bg: 'var(--warning-subtle)', text: 'var(--warning-color)', border: 'var(--warning-border)', dot: 'var(--warning-color)' };
      case 'skipped': return { bg: 'var(--bg-card-subtle)', text: 'var(--text-secondary)', border: 'var(--border-subtle)', dot: 'var(--text-muted)' };
      default: return { bg: 'var(--bg-card)', text: 'var(--text-muted)', border: 'var(--border-subtle)', dot: 'var(--text-dim)' };
    }
  };

  return (
    <div className="card-panel workflow-progress" style={{
      padding: '14px 20px',
      backgroundColor: '#FFFFFF',
      marginBottom: '16px',
      display: 'flex',
      flexDirection: 'column',
      gap: '10px'
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '0.725rem', fontFamily: 'var(--font-heading, "Plus Jakarta Sans")', fontWeight: 700, color: '#172033', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
            Workflow Pipeline Status
          </span>
          {runId && (
            <span className="badge badge-purple" style={{ fontSize: '0.65rem' }}>
              Run: {runId}
            </span>
          )}
        </div>

        {currentRunRecord && (
          <div style={{ fontSize: '0.75rem', color: '#667085', display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span>Stage: <strong style={{ color: '#172033' }}>{currentRunRecord.current_stage || activeTab}</strong></span>
            <span>·</span>
            <span>Status: <strong style={{ color: currentRunRecord.status === 'success' ? '#16845B' : currentRunRecord.status === 'failed' ? '#D14343' : '#6257D9' }}>{currentRunRecord.status || 'running'}</strong></span>
            {currentRunRecord.evaluation?.execution_time_seconds != null && (
              <>
                <span>·</span>
                <span>Elapsed: <strong style={{ color: '#172033' }}>{currentRunRecord.evaluation.execution_time_seconds}s</strong></span>
              </>
            )}
          </div>
        )}
      </div>

      {/* Stepper track */}
      <div className="workflow-progress-track" style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        overflowX: 'auto',
        gap: '4px',
        padding: '2px 0'
      }}>
        {stages.map((stage, idx) => {
          const c = getStatusColor(stage.status);
          const isTargetTab = activeTab === stage.id || (stage.id === 'recovery' && activeTab === 'testing');
          return (
            <React.Fragment key={stage.id}>
              <button
                type="button"
                className={`workflow-progress-step${isTargetTab ? ' is-current' : ''}`}
                data-status={stage.status}
                aria-current={isTargetTab ? 'step' : undefined}
                aria-label={`${stage.name}: ${stage.label}. Open stage`}
                onClick={() => onNavigateTab && onNavigateTab(stage.id === 'recovery' ? 'testing' : stage.id)}
                style={{
                  '--step-bg': isTargetTab ? 'var(--accent-primary-subtle)' : c.bg,
                  '--step-border': isTargetTab ? 'var(--accent-primary-border)' : c.border,
                  '--step-text': isTargetTab ? 'var(--accent-primary)' : 'var(--text-primary)',
                  '--step-status': c.text,
                  '--step-dot': c.dot
                }}
              >
                <span className="workflow-progress-dot" />
                <span className="workflow-progress-name">
                  {stage.name}
                </span>
                <span className="workflow-progress-label">{stage.label}</span>
              </button>

              {idx < stages.length - 1 && (
                <div className="workflow-progress-connector">
                  <ArrowRight size={12} />
                </div>
              )}
            </React.Fragment>
          );
        })}
      </div>
    </div>
  );
}
