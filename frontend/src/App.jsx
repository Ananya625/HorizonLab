import React, { useState, useEffect } from 'react';
import Header from './components/Header';
import OllamaSettingsModal from './components/OllamaSettingsModal';
import TaskInputSection from './components/TaskInputSection';
import ParsingProgress from './components/ParsingProgress';
import GoalModelView from './components/GoalModelView';
import ClarificationCenter from './components/ClarificationCenter';
import AuditHistoryView from './components/AuditHistoryView';
import ConfirmationGate from './components/ConfirmationGate';
import PlannerView from './components/PlannerView';
import CodingAgentView from './components/CodingAgentView';
import TestingDebugView from './components/TestingDebugView';
import VerificationView from './components/VerificationView';
import EvaluationDashboard from './components/EvaluationDashboard';
import AgentPerformanceView from './components/AgentPerformanceView';
import ExecutionControlRoom from './components/ExecutionControlRoom';
import WorkflowProgress from './components/WorkflowProgress';
import GuidedTour from './components/GuidedTour';
import {
  fetchOllamaStatus,
  fetchPresets,
  parseTaskRequirement,
  patchGoalModel,
  resolveAmbiguityQuestion,
  confirmGoalModel,
  generatePlan,
  fetchPlan,
  executeCoding,
  fetchCodeChanges,
  executeTesting,
  fetchTestResults,
  verifyCode,
  fetchVerification,
  runFullPipeline,
  fetchRunsList,
  fetchRunDetails,
  fetchRunLogs
} from './services/api';

export default function App() {
  const [theme, setTheme] = useState(() => (
    typeof window !== 'undefined' && window.localStorage.getItem('horizonlab-theme-v2') === 'light'
      ? 'light'
      : 'dark'
  ));
  const [isTourOpen, setIsTourOpen] = useState(false);

  useEffect(() => {
    window.localStorage.setItem('horizonlab-theme-v2', theme);
  }, [theme]);

  // Workspace & Input State
  const [taskPrompt, setTaskPrompt] = useState('Build a login API with JWT authentication using FastAPI. Implement user registration with password hashing, login endpoint returning JWT bearer token, protected route GET /api/auth/me, invalid credentials rejection (HTTP 401), expired token rejection, and automated pytest suite.');
  const [repoPath, setRepoPath] = useState('');
  const [selectedLanguage, setSelectedLanguage] = useState('auto');
  const [temperature, setTemperature] = useState(0.2);
  const [maxRecoveryRetries, setMaxRecoveryRetries] = useState(3);

  // Platform & Multi-Agent State
  const [ollamaStatus, setOllamaStatus] = useState(null);
  const [presets, setPresets] = useState([]);
  const [runsList, setRunsList] = useState([]);
  const [activeTab, setActiveTab] = useState('input');

  // Pipeline Data State
  const [runId, setRunId] = useState(null);
  const [goalModel, setGoalModel] = useState(null);
  const [plan, setPlan] = useState(null);
  const [codeChanges, setCodeChanges] = useState([]);
  const [testResults, setTestResults] = useState([]);
  const [recoveryAttempts, setRecoveryAttempts] = useState([]);
  const [verification, setVerification] = useState(null);
  const [currentRunRecord, setCurrentRunRecord] = useState(null);
  const [logs, setLogs] = useState([]);

  // UI Status
  const [loading, setLoading] = useState(false);
  const [isExecuting, setIsExecuting] = useState(false);
  const [error, setError] = useState(null);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [resolvingId, setResolvingId] = useState(null);
  const [isConfirming, setIsConfirming] = useState(false);
  const [pendingFullRunId, setPendingFullRunId] = useState(null);

  // Initial load: Fetch Ollama status, Presets, and Runs list
  useEffect(() => {
    fetchOllamaStatus()
      .then((status) => setOllamaStatus(status))
      .catch((err) => console.warn('Ollama status initial fetch error:', err));

    fetchPresets()
      .then((data) => setPresets(data.presets || []))
      .catch((err) => console.warn('Presets initial fetch error:', err));

    loadRunsList();

    // Poll Ollama status every 20 seconds
    const interval = setInterval(() => {
      fetchOllamaStatus()
        .then((status) => setOllamaStatus(status))
        .catch(() => { });
    }, 20000);

    return () => clearInterval(interval);
  }, []);

  // Poll logs for active run
  useEffect(() => {
    if (!runId) return;
    const fetchLogs = () => {
      fetchRunLogs(runId)
        .then((data) => setLogs(data.logs || []))
        .catch(() => { });
    };

    fetchLogs();
    const logInterval = setInterval(fetchLogs, 3000);
    return () => clearInterval(logInterval);
  }, [runId]);

  const loadRunsList = async () => {
    try {
      const data = await fetchRunsList();
      setRunsList(data.runs || []);
    } catch (err) {
      console.warn('Failed to load runs list:', err);
    }
  };

  // Handler: Select and hydrate previous SQLite Run
  const handleSelectRun = async (selectedRunId) => {
    if (!selectedRunId) return;
    setPendingFullRunId(null);
    setError(null);
    setLoading(true);
    try {
      const record = await fetchRunDetails(selectedRunId);
      setCurrentRunRecord(record);
      setRunId(record.run_id);
      setTaskPrompt(record.prompt);
      setRepoPath(record.repo_path);
      setGoalModel(record.goal_model);
      setPlan(record.plan);
      setCodeChanges(record.code_changes || []);
      setTestResults(record.test_results || []);
      setRecoveryAttempts(record.recovery_attempts || []);
      setVerification(record.verification);
      setLogs(record.logs || []);

      if (record.verification) {
        setActiveTab('verifier');
      } else if (record.test_results?.length > 0) {
        setActiveTab('testing');
      } else if (record.code_changes?.length > 0) {
        setActiveTab('coder');
      } else if (record.plan) {
        setActiveTab('planner');
      } else if (record.goal_model) {
        setActiveTab('goal_model');
      }
    } catch (err) {
      alert(`Failed to load run ${selectedRunId}: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  // Handler: Stage 2 - Analyze Requirements with Ollama
  const handleAnalyzeTask = async () => {
    if (!taskPrompt.trim()) return;
    setPendingFullRunId(null);
    setLoading(true);
    setError(null);
    try {
      const parsed = await parseTaskRequirement({
        requestText: taskPrompt,
        repoPath: repoPath,
        modelName: (ollamaStatus?.current_model === 'none' ? undefined : ollamaStatus?.current_model),
        language: selectedLanguage,
        temperature: temperature,
        runId: runId
      });
      setGoalModel(parsed);
      setRunId(parsed.run_id);
      loadRunsList();

      const hasBlocking = (parsed.ambiguities || []).some((a) => a.severity === 'blocking' && !a.resolved);
      if (hasBlocking) {
        setActiveTab('clarifications');
      } else {
        setActiveTab('goal_model');
      }
    } catch (err) {
      console.error('Task requirement analysis error:', err);
      setError(err.message || 'Failed to analyze task requirements.');
    } finally {
      setLoading(false);
    }
  };

  // Handler: Patch Goal Model
  const handleSavePatch = async (patchPayload) => {
    setIsSaving(true);
    try {
      const updated = await patchGoalModel(patchPayload);
      setGoalModel(updated);
    } catch (err) {
      alert(`Save failed: ${err.message}`);
    } finally {
      setIsSaving(false);
    }
  };

  // Handler: Resolve Ambiguity
  const handleResolveQuestion = async ({ runId: rId, ambiguityId, userAnswer, applyAsConstraint, constraintType }) => {
    setResolvingId(ambiguityId);
    try {
      const updated = await resolveAmbiguityQuestion({
        runId: rId || runId,
        ambiguityId,
        userAnswer,
        applyAsConstraint,
        constraintType
      });
      setGoalModel(updated);
    } catch (err) {
      alert(`Resolution failed: ${err.message}`);
    } finally {
      setResolvingId(null);
    }
  };

  // Handler: Confirm Goal Model
  const handleConfirmGoal = async () => {
    if (!goalModel?.run_id) return;
    setIsConfirming(true);
    setError(null);
    try {
      const confirmed = await confirmGoalModel(goalModel.run_id);
      setGoalModel(confirmed);
      setActiveTab('confirm');
      setError(null);
      if (pendingFullRunId === confirmed.run_id) {
        await handleRunFullPipeline(confirmed);
      }
    } catch (err) {
      setError(err.message || 'Requirement confirmation failed.');
      throw err;
    } finally {
      setIsConfirming(false);
    }
  };

  // Handler: Stage 3 - Generate Codebase Plan
  const handleGeneratePlan = async () => {
    if (!runId) return;
    setIsExecuting(true);
    try {
      const generatedPlan = await generatePlan({ runId, repoPath });
      setPlan(generatedPlan);
      setActiveTab('planner');
    } catch (err) {
      alert(`Planning failed: ${err.message}`);
    } finally {
      setIsExecuting(false);
    }
  };

  // Handler: Stage 4 - Execute Coding Agent
  const handleExecuteCoding = async () => {
    if (!runId) return;
    setIsExecuting(true);
    try {
      const activeModel = (ollamaStatus?.current_model === 'none' ? undefined : ollamaStatus?.current_model);
      const res = await executeCoding({ runId, modelName: activeModel, temperature });
      setCodeChanges(res.changes || []);
      setActiveTab('coder');
    } catch (err) {
      alert(`Coding execution failed: ${err.message}`);
    } finally {
      setIsExecuting(false);
    }
  };

  // Handler: Stage 5 - Execute Testing & Debugging Loop
  const handleExecuteTesting = async () => {
    if (!runId) return;
    setIsExecuting(true);
    try {
      const activeModel = (ollamaStatus?.current_model === 'none' ? undefined : ollamaStatus?.current_model);
      const res = await executeTesting({ runId, maxRecoveryRetries, modelName: activeModel });
      const testRes = await fetchTestResults(runId);
      setTestResults(testRes.test_runs || []);
      setRecoveryAttempts(testRes.recovery_attempts || []);
      const updatedRun = await fetchRunDetails(runId);
      if (updatedRun) {
        setCurrentRunRecord(updatedRun);
        if (updatedRun.code_changes) setCodeChanges(updatedRun.code_changes);
        if (updatedRun.logs) setLogs(updatedRun.logs);
      }
      loadRunsList();
      setActiveTab('testing');
    } catch (err) {
      alert(`Testing and recovery failed: ${err.message}`);
    } finally {
      setIsExecuting(false);
    }
  };

  // Handler: Stage 6 - Run Independent Verifier
  const handleVerifyCode = async () => {
    if (!runId) return;
    setIsExecuting(true);
    try {
      const verReport = await verifyCode({ runId });
      setVerification(verReport);
      setCurrentRunRecord(await fetchRunDetails(runId));
      loadRunsList();
      setActiveTab('verifier');
    } catch (err) {
      alert(`Verification failed: ${err.message}`);
    } finally {
      setIsExecuting(false);
    }
  };

  // Handler: Full End-to-End Autonomous Pipeline Runner (Stages 1-7)
  const handleRunFullPipeline = async (confirmedGoal = null) => {
    if (!taskPrompt.trim()) return;
    const executionGoal = confirmedGoal?.is_confirmed ? confirmedGoal : goalModel;
    if (executionGoal?.run_id === runId && !executionGoal.is_confirmed) {
      setPendingFullRunId(runId);
      setError(null);
      setActiveTab((executionGoal.ambiguities || []).some(a => a.severity === 'blocking' && !a.resolved)
        ? 'clarifications' : 'confirm');
      return;
    }
    setPendingFullRunId(null);
    setIsExecuting(true);
    setError(null);
    try {
      const fullRecord = await runFullPipeline({
        requestText: taskPrompt,
        repoPath: repoPath,
        modelName: (ollamaStatus?.current_model === 'none' ? undefined : ollamaStatus?.current_model),
        temperature: temperature,
        maxRecoveryRetries: maxRecoveryRetries,
        runId: runId
      });

      setCurrentRunRecord(fullRecord);
      setRunId(fullRecord.run_id);
      setGoalModel(fullRecord.goal_model);
      setPlan(fullRecord.plan);
      setCodeChanges(fullRecord.code_changes || []);
      setTestResults(fullRecord.test_results || []);
      setRecoveryAttempts(fullRecord.recovery_attempts || []);
      setVerification(fullRecord.verification);
      setLogs(fullRecord.logs || []);
      loadRunsList();
      if (!fullRecord.goal_model?.is_confirmed) setPendingFullRunId(fullRecord.run_id);
      setActiveTab(fullRecord.goal_model?.is_confirmed ? 'evaluations' : 'goal_model');
    } catch (err) {
      console.error('Full pipeline execution error:', err);
      setError(err.message || 'Pipeline execution failed.');
    } finally {
      setIsExecuting(false);
    }
  };

  // Handler: Reset to New Task
  const handleReset = () => {
    setPendingFullRunId(null);
    setGoalModel(null);
    setPlan(null);
    setCodeChanges([]);
    setTestResults([]);
    setRecoveryAttempts([]);
    setVerification(null);
    setCurrentRunRecord(null);
    setRunId(null);
    setLogs([]);
    setActiveTab('input');
    setError(null);
  };

  return (
    <div className="app-shell" data-theme={theme} style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', paddingBottom: '160px' }}>
      {/* Top Telemetry Header */}
      <Header
        runId={runId}
        currentStage={currentRunRecord?.current_stage || 'workspace'}
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        ollamaStatus={ollamaStatus}
        onOpenSettings={() => setIsSettingsOpen(true)}
        onReset={handleReset}
        onRunFullPipeline={handleRunFullPipeline}
        isRunning={isExecuting || loading || isConfirming}
        hasRun={!!runId}
        runsList={runsList}
        onSelectRun={handleSelectRun}
        theme={theme}
        onToggleTheme={() => setTheme((current) => current === 'dark' ? 'light' : 'dark')}
        onOpenTour={() => setIsTourOpen(true)}
      />

      {/* Main Workspace Container */}
      <main className="dashboard-main" style={{ flex: 1, maxWidth: '1440px', width: '100%', margin: '0 auto', padding: '24px 20px' }}>
        {error && (
          <div role="alert" className="card-panel" style={{ padding: '12px 18px', marginBottom: 16, color: '#D14343', backgroundColor: '#FEF2F2', border: '1px solid #FECACA', borderRadius: '8px', fontSize: '0.85rem' }}>
            {error}
          </div>
        )}
        {runId && currentRunRecord?.run_id === runId && currentRunRecord.status === 'in_progress' && goalModel && !goalModel.is_confirmed && !isExecuting && (
          <div role="status" className="card-panel" style={{ padding: '14px 18px', marginBottom: 16, color: '#B7791F', backgroundColor: '#FFFBEB', border: '1px solid #FDE68A', borderRadius: '8px', fontSize: '0.85rem' }}>
            <strong>Requirements awaiting review.</strong> This run is paused, not actively executing. Resolve blocking questions, confirm the goal, then choose the next stage or run the full pipeline.
          </div>
        )}



        {/* Consistent Workflow Progress Indicator */}
        <WorkflowProgress
          runId={runId}
          currentRunRecord={currentRunRecord}
          goalModel={goalModel}
          plan={plan}
          codeChanges={codeChanges}
          testResults={testResults}
          recoveryAttempts={recoveryAttempts}
          verification={verification}
          activeTab={activeTab}
          onNavigateTab={setActiveTab}
          isExecuting={isExecuting}
          loading={loading}
        />

        {/* Loading Telemetry Stepper */}
        {(loading || isExecuting) && (
          <ParsingProgress modelName={ollamaStatus?.current_model} requirements={!goalModel?.is_confirmed} />
        )}

        {/* State 1: Coding Workspace & Presets */}
        {!loading && !isExecuting && activeTab === 'input' && (
          <TaskInputSection
            taskPrompt={taskPrompt}
            setTaskPrompt={setTaskPrompt}
            presets={presets}
            onAnalyze={handleAnalyzeTask}
            onRunFullPipeline={handleRunFullPipeline}
            loading={loading || isExecuting}
            error={null}
            ollamaStatus={ollamaStatus}
            selectedLanguage={selectedLanguage}
            setSelectedLanguage={setSelectedLanguage}
            repoPath={repoPath}
            setRepoPath={setRepoPath}
            maxRecoveryRetries={maxRecoveryRetries}
            setMaxRecoveryRetries={setMaxRecoveryRetries}
            goalModel={goalModel}
            currentRunRecord={currentRunRecord}
            runId={runId}
            logs={logs}
            runsList={runsList}
            onSelectRun={handleSelectRun}
            onNavigateTab={setActiveTab}
            plan={plan}
            codeChanges={codeChanges}
            testResults={testResults}
            recoveryAttempts={recoveryAttempts}
            verification={verification}
          />
        )}

        {/* State 2: Requirement Analysis (Goal Model View) */}
        {!loading && !isExecuting && activeTab === 'goal_model' && goalModel && (
          <GoalModelView
            goalModel={goalModel}
            onSavePatch={handleSavePatch}
            onNavigateToClarifications={() => setActiveTab('clarifications')}
            onProceedToConfirmation={() => setActiveTab('confirm')}
            isSaving={isSaving}
          />
        )}

        {/* State 2.1: Clarification Center */}
        {!loading && !isExecuting && activeTab === 'clarifications' && goalModel && (
          <ClarificationCenter
            goalModel={goalModel}
            onResolveQuestion={handleResolveQuestion}
            onProceedToConfirmation={() => setActiveTab('confirm')}
            resolvingId={resolvingId}
          />
        )}

        {/* State 2.2: Audit History */}
        {!loading && !isExecuting && activeTab === 'audit' && goalModel && (
          <AuditHistoryView
            runId={goalModel.run_id}
            currentModel={goalModel}
          />
        )}

        {/* State 2.3: Confirmation Gate */}
        {!loading && !isExecuting && activeTab === 'confirm' && goalModel && (
          <ConfirmationGate
            goalModel={goalModel}
            onConfirm={handleConfirmGoal}
            continueFullWorkflow={pendingFullRunId === runId}
            isConfirming={isConfirming}
            onNavigateToClarifications={() => setActiveTab('clarifications')}
            onProceedToPlanner={handleGeneratePlan}
          />
        )}

        {/* State 3: Codebase Analyst & Planner */}
        {!loading && !isExecuting && activeTab === 'planner' && (
          <PlannerView
            plan={plan}
            onExecuteCoding={handleExecuteCoding}
            isExecutingCode={isExecuting}
            onNavigateToStage={setActiveTab}
          />
        )}

        {/* State 4: Coding Agent (Diffs & Source Code) */}
        {!loading && !isExecuting && activeTab === 'coder' && (
          <CodingAgentView
            codeChanges={codeChanges}
            onExecuteTesting={handleExecuteTesting}
            isTesting={isExecuting}
            onNavigateToStage={setActiveTab}
          />
        )}

        {/* State 5: Testing + Debugging Agents */}
        {!loading && !isExecuting && activeTab === 'testing' && (
          <TestingDebugView
            testResults={testResults}
            recoveryAttempts={recoveryAttempts}
            onExecuteTesting={handleExecuteTesting}
            isTesting={isExecuting}
            onExecuteVerification={handleVerifyCode}
            isVerifying={isExecuting}
            onNavigateToStage={setActiveTab}
          />
        )}

        {/* State 6: Independent Code Reviewer / Verifier */}
        {!loading && !isExecuting && activeTab === 'verifier' && (
          <VerificationView
            verification={verification}
            onNavigateToEvaluations={() => setActiveTab('evaluations')}
          />
        )}

        {/* State 7: Evaluation Dashboard & Benchmarks */}
        {!loading && !isExecuting && activeTab === 'evaluations' && (
          <EvaluationDashboard
            currentRunRecord={currentRunRecord}
            onSelectRun={handleSelectRun}
            onReset={handleReset}
          />
        )}

        {/* State 8: Agent Performance */}
        {!loading && !isExecuting && (activeTab === 'performance' || activeTab === 'agent_performance') && (
          <AgentPerformanceView
            currentRunRecord={currentRunRecord}
            onSelectRun={handleSelectRun}
          />
        )}
      </main>

      {/* Execution Control Room (Bottom Live Telemetry & Log Drawer) */}
      <ExecutionControlRoom
        runId={runId}
        logs={logs}
        onRefreshLogs={() => runId && fetchRunLogs(runId).then((d) => setLogs(d.logs || []))}
      />

      {/* Ollama Settings Modal */}
      <OllamaSettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        currentStatus={ollamaStatus}
        onStatusUpdated={(newStatus) => setOllamaStatus(newStatus)}
        temperature={temperature}
        setTemperature={setTemperature}
      />
      {isTourOpen && (
        <GuidedTour
          onClose={() => setIsTourOpen(false)}
          onNavigate={setActiveTab}
          runId={runId}
          goalModel={goalModel}
          codeChanges={codeChanges}
          testResults={testResults}
          verification={verification}
        />
      )}
    </div>
  );
}
