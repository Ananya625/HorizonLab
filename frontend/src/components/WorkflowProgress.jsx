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
      case 'completed': return { bg: '#ECFDF5', text: '#16845B', border: '#A7F3D0', dot: '#16845B' };
      case 'active': return { bg: '#F0EEFF', text: '#6257D9', border: '#D8D2FB', dot: '#6257D9' };
      case 'failed': return { bg: '#FEF2F2', text: '#D14343', border: '#FECACA', dot: '#D14343' };
      case 'blocked': return { bg: '#FEF2F2', text: '#D14343', border: '#FECACA', dot: '#D14343' };
      case 'attention': return { bg: '#FFFBEB', text: '#B7791F', border: '#FDE68A', dot: '#B7791F' };
      case 'pending_review': return { bg: '#FFFBEB', text: '#B7791F', border: '#FDE68A', dot: '#B7791F' };
      case 'skipped': return { bg: '#F1F4F9', text: '#667085', border: '#E2E8F0', dot: '#98A2B3' };
      default: return { bg: '#FFFFFF', text: '#98A2B3', border: '#E5E7EF', dot: '#D0D5DD' };
    }
  };

  return (
    <div className="card-panel" style={{
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
      <div style={{ 
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
              <div
                onClick={() => onNavigateTab && onNavigateTab(stage.id === 'recovery' ? 'testing' : stage.id)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  padding: '6px 10px',
                  borderRadius: '6px',
                  backgroundColor: isTargetTab ? 'var(--accent-primary-subtle, #F0EEFF)' : c.bg,
                  border: `1px solid ${isTargetTab ? 'var(--accent-primary, #6257D9)' : c.border}`,
                  cursor: 'pointer',
                  flexShrink: 0,
                  transition: 'all 0.15s ease'
                }}
              >
                <span style={{
                  width: '8px',
                  height: '8px',
                  borderRadius: '50%',
                  backgroundColor: c.dot
                }} />
                <span style={{ fontSize: '0.775rem', fontWeight: 600, color: isTargetTab ? '#6257D9' : '#172033' }}>
                  {stage.name}
                </span>
                <span style={{ fontSize: '0.675rem', color: c.text, fontWeight: 500 }}>
                  ({stage.label})
                </span>
              </div>

              {idx < stages.length - 1 && (
                <div style={{ color: '#CBD2E0', flexShrink: 0 }}>
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
