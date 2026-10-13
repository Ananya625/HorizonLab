const BASE_URL = 'http://127.0.0.1:8000/api';

/**
 * Common fetch handler with error normalization
 */
async function request(endpoint, options = {}) {
  const url = `${BASE_URL}${endpoint}`;
  try {
    const res = await fetch(url, {
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      ...options,
    });

    if (!res.ok) {
      let errorDetail = `HTTP ${res.status}: ${res.statusText}`;
      try {
        const errorJson = await res.json();
        if (errorJson.detail) {
          errorDetail = typeof errorJson.detail === 'string' 
            ? errorJson.detail 
            : JSON.stringify(errorJson.detail);
        }
      } catch {
        // Failed to parse JSON error response, use default
      }
      throw new Error(errorDetail);
    }

    return await res.json();
  } catch (err) {
    console.error(`API Error on [${url}]:`, err);
    throw err;
  }
}

// --- Ollama Connectivity ---

export async function fetchOllamaStatus() {
  return request('/ollama/status');
}

export async function configureOllama(config) {
  return request('/ollama/configure', {
    method: 'POST',
    body: JSON.stringify(config),
  });
}

// --- Presets & Workspace ---

export async function fetchPresets() {
  return request('/presets');
}

export async function fetchSampleRepos() {
  return request('/workspace/sample-repos');
}

export async function inspectWorkspace(path) {
  const query = path ? `?path=${encodeURIComponent(path)}` : '';
  return request(`/workspace/inspect${query}`);
}

// --- Stage 2: Requirement Analysis & Goal Model ---

export async function parseTaskRequirement({ requestText, repoPath, modelName, language, temperature, runId }) {
  return request('/goals/parse', {
    method: 'POST',
    body: JSON.stringify({
      request_text: requestText,
      repo_path: repoPath,
      model_name: modelName,
      language: language || 'auto',
      temperature: temperature ?? 0.2,
      run_id: runId
    }),
  });
}

export async function patchGoalModel(patchPayload) {
  return request('/goals/patch', {
    method: 'POST',
    body: JSON.stringify(patchPayload),
  });
}

export async function resolveAmbiguityQuestion({ runId, ambiguityId, userAnswer, applyAsConstraint, constraintType }) {
  return request('/goals/resolve-ambiguity', {
    method: 'POST',
    body: JSON.stringify({
      run_id: runId,
      ambiguity_id: ambiguityId,
      user_answer: userAnswer,
      apply_as_constraint: applyAsConstraint,
      constraint_type: constraintType || 'hard',
    }),
  });
}

export async function confirmGoalModel(runId) {
  return request(`/goals/confirm/${runId}`, {
    method: 'POST',
  });
}

export async function fetchGoalModel(runId) {
  return request(`/goals/${runId}`);
}

export async function fetchGoalHistory(runId) {
  return request(`/goals/${runId}/history`);
}

export async function fetchRunHistory(runId) {
  return fetchGoalHistory(runId);
}

// --- Stage 3: Codebase Analyst & Planner ---

export async function generatePlan({ runId, repoPath }) {
  return request('/planner/generate', {
    method: 'POST',
    body: JSON.stringify({ run_id: runId, repo_path: repoPath }),
  });
}

export async function fetchPlan(runId) {
  return request(`/planner/${runId}`);
}

// --- Stage 4: Coding Agent ---

export async function executeCoding({ runId }) {
  return request('/coder/execute', {
    method: 'POST',
    body: JSON.stringify({ run_id: runId }),
  });
}

export async function fetchCodeChanges(runId) {
  return request(`/coder/${runId}/changes`);
}

// --- Stage 5: Testing & Debugging Agent ---

export async function executeTesting({ runId, maxRecoveryRetries }) {
  return request('/tester/execute', {
    method: 'POST',
    body: JSON.stringify({ run_id: runId, max_recovery_retries: maxRecoveryRetries ?? 3 }),
  });
}

export async function fetchTestResults(runId) {
  return request(`/tester/${runId}/results`);
}

// --- Stage 6: Independent Code Reviewer / Verifier ---

export async function verifyCode({ runId }) {
  return request('/verifier/verify', {
    method: 'POST',
    body: JSON.stringify({ run_id: runId }),
  });
}

export async function fetchVerification(runId) {
  return request(`/verifier/${runId}`);
}

// --- Stage 7: End-to-End Orchestrator Pipeline ---

export async function runFullPipeline({ requestText, repoPath, modelName, temperature, maxRecoveryRetries, runId }) {
  return request('/pipeline/run-all', {
    method: 'POST',
    body: JSON.stringify({
      request_text: requestText,
      repo_path: repoPath,
      model_name: modelName,
      temperature: temperature ?? 0.2,
      max_recovery_retries: maxRecoveryRetries ?? 3,
      run_id: runId,
    }),
  });
}

// --- Telemetry, Logs & Evaluations ---

export async function fetchRunsList() {
  return request('/runs');
}

export async function fetchRunDetails(runId) {
  return request(`/runs/${runId}`);
}

// Latest window in chronological order; offset counts backward from newest.
export async function fetchRunLogs(runId, limit = 200, offset = 0) {
  return request(`/runs/${encodeURIComponent(runId)}/logs?limit=${limit}&offset=${offset}`);
}

export async function fetchEvaluationDashboard() {
  return request('/evaluations/dashboard');
}

export async function fetchRunEvaluation(runId) {
  return request(`/evaluations/${runId}`);
}

export const fetchBenchmarkCapabilities = () => request('/benchmarks/capabilities');
export const fetchExperiments = () => request('/benchmarks/experiments');
export const runExperiment = (manifest) => request('/benchmarks/experiments', { method: 'POST', body: JSON.stringify(manifest) });
export const exportRun = (runId) => request(`/runs/${runId}/export`);
export const runStudy = (manifest) => request('/benchmarks/studies', { method: 'POST', body: JSON.stringify(manifest) });
export const resumeExperiment = (experimentId) => request(`/benchmarks/experiments/${experimentId}/resume`, { method: 'POST' });


export const fetchWorkflowReport = (runId, signal) => request(`/evaluations/${encodeURIComponent(runId)}/workflow`, { signal });
export const fetchWorkflowEvents = (runId, after = 0, through, signal) => request(`/evaluations/${encodeURIComponent(runId)}/workflow/events?after=${after}&limit=50${through == null ? '' : `&through=${through}`}`, { signal });
export const fetchWorkflowEvent = (runId, eventId, signal) => request(`/evaluations/${encodeURIComponent(runId)}/workflow/events/${encodeURIComponent(eventId)}`, { signal });
export const exportWorkflow = runId => request(`/evaluations/${encodeURIComponent(runId)}/workflow/export`);
