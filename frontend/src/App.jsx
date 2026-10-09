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
import ExecutionControlRoom from './components/ExecutionControlRoom';

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
        .catch(() => {});
    }, 20000);

    return () => clearInterval(interval);
  }, []);

  // Poll logs for active run
  useEffect(() => {
    if (!runId) return;
    const fetchLogs = () => {
      fetchRunLogs(runId)
        .then((data) => setLogs(data.logs || []))
        .catch(() => {});
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
    setLoading(true);
    setError(null);
    try {
      const parsed = await parseTaskRequirement({
        requestText: taskPrompt,
        repoPath: repoPath,
        modelName: ollamaStatus?.current_model || 'qwen2.5-coder:7b',
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
    try {
      const confirmed = await confirmGoalModel(goalModel.run_id);
      setGoalModel(confirmed);
      setActiveTab('confirm');
    } catch (err) {
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
      const res = await executeCoding({ runId });
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
      const res = await executeTesting({ runId, maxRecoveryRetries });
      const testRes = await fetchTestResults(runId);
      setTestResults(testRes.test_runs || []);
      setRecoveryAttempts(testRes.recovery_attempts || []);
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
      setActiveTab('verifier');
    } catch (err) {
      alert(`Verification failed: ${err.message}`);
    } finally {
      setIsExecuting(false);
    }
  };

  // Handler: Full End-to-End Autonomous Pipeline Runner (Stages 1-7)
  const handleRunFullPipeline = async () => {
    if (!taskPrompt.trim()) return;
    setIsExecuting(true);
    setError(null);
    try {
      const fullRecord = await runFullPipeline({
        requestText: taskPrompt,
        repoPath: repoPath,
        modelName: ollamaStatus?.current_model || 'qwen2.5-coder:7b',
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

      setActiveTab('evaluations');
    } catch (err) {
      console.error('Full pipeline execution error:', err);
      setError(err.message || 'Pipeline execution failed.');
    } finally {
      setIsExecuting(false);
    }
  };

  // Handler: Reset to New Task
  const handleReset = () => {
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
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', paddingBottom: '160px' }}>
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
        isRunning={isExecuting || loading}
        hasRun={!!runId}
        runsList={runsList}
        onSelectRun={handleSelectRun}
      />

      {/* Main Workspace Container */}
      <main style={{ flex: 1, maxWidth: '1440px', width: '100%', margin: '0 auto', padding: '24px 20px' }}>
        {/* Loading Telemetry Stepper */}
        {(loading || isExecuting) && (
          <ParsingProgress modelName={ollamaStatus?.current_model} />
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
            error={error}
            ollamaStatus={ollamaStatus}
            selectedLanguage={selectedLanguage}
            setSelectedLanguage={setSelectedLanguage}
            repoPath={repoPath}
            setRepoPath={setRepoPath}
            maxRecoveryRetries={maxRecoveryRetries}
            setMaxRecoveryRetries={setMaxRecoveryRetries}
          />
        )}

        {/* State 2: Requirement Analysis (Goal Model View) */}
        {!loading && !isExecuting && activeTab === 'goal_model' && goalModel && (
          <GoalModelView 
            goalModel={goalModel}
            onSavePatch={handleSavePatch}
            onNavigateToClarifications={() => setActiveTab('clarifications')}
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
    </div>
  );
}
