import React from 'react';
import { 
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
      case 'completed': 
        return { 
          bg: 'rgba(16, 185, 129, 0.12)', 
          text: '#34D399', 
          border: 'rgba(16, 185, 129, 0.3)', 
          dot: '#10B981',
          shadow: '0 0 8px rgba(16, 185, 129, 0.4)'
        };
      case 'active': 
        return { 
          bg: 'rgba(99, 102, 241, 0.16)', 
          text: '#818CF8', 
          border: 'rgba(99, 102, 241, 0.4)', 
          dot: '#6366F1',
          shadow: '0 0 10px rgba(99, 102, 241, 0.6)'
        };
      case 'failed':
      case 'blocked': 
        return { 
          bg: 'rgba(239, 68, 68, 0.12)', 
          text: '#F87171', 
          border: 'rgba(239, 68, 68, 0.3)', 
          dot: '#EF4444',
          shadow: '0 0 8px rgba(239, 68, 68, 0.4)'
        };
      case 'attention':
      case 'pending_review': 
        return { 
          bg: 'rgba(245, 158, 11, 0.12)', 
          text: '#FBBF24', 
          border: 'rgba(245, 158, 11, 0.3)', 
          dot: '#F59E0B',
          shadow: '0 0 8px rgba(245, 158, 11, 0.4)'
        };
      case 'skipped': 
        return { 
          bg: 'rgba(255, 255, 255, 0.03)', 
          text: '#94A3B8', 
          border: 'rgba(255, 255, 255, 0.06)', 
          dot: '#64748B',
          shadow: 'none'
        };
      default: 
        return { 
          bg: 'rgba(255, 255, 255, 0.02)', 
          text: '#64748B', 
          border: 'rgba(255, 255, 255, 0.06)', 
          dot: '#334155',
          shadow: 'none'
        };
    }
  };

  return (
    <div className="card-panel workflow-progress" style={{
      padding: '14px 20px',
      backgroundColor: '#0D1526',
      border: '1px solid rgba(255, 255, 255, 0.08)',
      borderRadius: '12px',
      marginBottom: '16px',
      display: 'flex',
      flexDirection: 'column',
      gap: '12px',
      boxShadow: '0 4px 20px rgba(0, 0, 0, 0.3)'
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '0.725rem', fontFamily: 'var(--font-heading, "Plus Jakarta Sans")', fontWeight: 700, color: '#F1F5F9', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
            Workflow Pipeline Status
          </span>
          {runId && (
            <span className="badge badge-purple" style={{ 
              fontSize: '0.65rem',
              background: 'rgba(99, 102, 241, 0.15)',
              color: '#A5B4FC',
              border: '1px solid rgba(99, 102, 241, 0.3)'
            }}>
              Run: {runId}
            </span>
          )}
        </div>

        {currentRunRecord && (
          <div style={{ fontSize: '0.75rem', color: '#94A3B8', display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span>Stage: <strong style={{ color: '#F1F5F9' }}>{currentRunRecord.current_stage || activeTab}</strong></span>
            <span>·</span>
            <span>Status: <strong style={{ color: currentRunRecord.status === 'success' ? '#34D399' : currentRunRecord.status === 'failed' ? '#F87171' : '#818CF8' }}>{currentRunRecord.status || 'running'}</strong></span>
            {currentRunRecord.evaluation?.execution_time_seconds != null && (
              <>
                <span>·</span>
                <span>Elapsed: <strong style={{ color: '#F1F5F9' }}>{currentRunRecord.evaluation.execution_time_seconds}s</strong></span>
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
        gap: '6px',
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
                  '--step-bg': isTargetTab ? 'rgba(99, 102, 241, 0.2)' : c.bg,
                  '--step-border': isTargetTab ? 'rgba(99, 102, 241, 0.5)' : c.border,
                  '--step-text': isTargetTab ? '#FFFFFF' : '#E2E8F0',
                  '--step-status': c.text,
                  '--step-dot': c.dot,
                  backgroundColor: isTargetTab ? 'rgba(99, 102, 241, 0.2)' : c.bg,
                  borderColor: isTargetTab ? 'rgba(99, 102, 241, 0.5)' : c.border,
                  borderRadius: '8px',
                  boxShadow: isTargetTab ? '0 0 12px rgba(99, 102, 241, 0.3)' : 'none'
                }}
              >
                <span className="workflow-progress-dot" style={{ backgroundColor: c.dot, boxShadow: c.shadow }} />
                <span className="workflow-progress-name">
                  {stage.name}
                </span>
                <span className="workflow-progress-label">{stage.label}</span>
              </button>

              {idx < stages.length - 1 && (
                <div className="workflow-progress-connector" style={{ color: '#475569' }}>
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
