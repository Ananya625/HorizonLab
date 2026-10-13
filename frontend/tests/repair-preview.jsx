// Read-only UI fixture. All fetches are intercepted; no backend or model calls.
import React, { useState } from 'react';
import { createRoot } from 'react-dom/client';
import '../src/index.css';
import EvaluationDashboard from '../src/components/EvaluationDashboard';
import VerificationView from '../src/components/VerificationView';

const resources = { tool_calls: 4, model_calls: 2, duration_seconds: 8, output_tokens: 110 };
const evaluation = { metric_version: '2', success_rate: 50, outcome: 'unverified', execution_time_seconds: 8,
  total_tool_calls: 4, tests_passed: 4, tests_total: 4, recovery_attempts_count: 0 };
const run = { run_id: 'preview-addition', title: 'Add two numbers', evaluation };
const event = { event_id: 'event-1', sequence: 1, kind: 'action_result', operation: 'read_file', outcome: 'success', timestamp: '2026-10-13T00:00:00Z' };
const report = {
  run_id: run.run_id, version: 'workflow-v1', evidence_status: 'partial', execution_mode: 'preview_fixture', snapshot_sequence: 1,
  summary: { verified_outcome: null, action_attempts: 4, model_calls: 2, stages: 3, progress_rate: 0,
    repeated_actions: 1, wall_seconds: 8, resources, incomplete_actions: 0, duplicate_effects: 0, dependency_checks: 0, unmapped_actions: 0 },
  coverage: { paired_outcomes: 1, state_references: 1, sub_goal_mapping: 1 },
  stagnation: { baseline: 'first_observation', actions: 4, seconds: 8 },
  sub_goals: [{ id: 'SG-1', title: 'Add two numbers', reported_status: 'completed', status: 'unverified', attempts: 1,
    incomplete_attempts: 0, revisits: 0, regressions: 0, resources }],
  overhead: { recovery: resources, rework: resources, union: resources, note: 'Illustrative fixture values only.' },
  recovery: [], attempts: [], plan_observations: [], progress: [],
  findings: [{ id: 'f1', kind: 'repeated_action', confidence: 'heuristic', message: 'The same read was repeated without observed progress.', event_ids: ['event-1'] }],
  limitations: ['Preview fixtures are not real measurements.'], calculation: {},
};
const review = { verifier_version: '2', overall_verdict: 'UNVERIFIED',
  review_summary: 'Syntax is valid. Addition behavior needs independent evidence.',
  criteria_evaluations: [
    { criterion_id: 'SC-1', criterion_description: 'Python files compile', verdict: 'PASS', evidence: 'All Python files compiled.' },
    { criterion_id: 'SC-2', criterion_description: 'Addition returns the correct sum', verdict: 'UNVERIFIED', evidence: 'Generated tests passed, but no independent behavior checker was supplied.' },
  ], recommendations: ['Provide independent acceptance checks before approving task completion.'], constraint_compliances: [],
};
globalThis.fetch = async (input, options = {}) => {
  if (options.method && options.method !== 'GET') throw new Error('Read-only preview: execution is disabled.');
  const path = new URL(input, location.href).pathname;
  let payload;
  if (path.endsWith('/workflow')) payload = report;
  else if (path.endsWith('/workflow/events')) payload = { events: [event], next_after: null };
  else if (path.endsWith('/workflow/events/event-1')) payload = event;
  else if (path.endsWith('/evaluations/dashboard')) payload = { aggregate_stats: { total_runs: 1, unverified_runs: 1 }, recent_evaluations: [{ ...run, ...evaluation }] };
  else if (path.endsWith('/benchmarks/experiments')) payload = { experiments: [] };
  else if (path.endsWith('/benchmarks/capabilities')) payload = { tasks: [], limitations: [] };
  else throw new Error(`Unrecognized preview route: ${path}`);
  return { ok: true, json: async () => payload };
};

function Preview() {
  const [screen, setScreen] = useState('evaluation');
  return <main style={{ maxWidth: 1120, margin: '0 auto', padding: 24 }}>
    <p>Read-only preview · Synthetic examples · Execution disabled</p>
    <nav style={{ display: 'flex', gap: 8, margin: '12px 0' }}>
      <button className="btn btn-secondary" onClick={() => setScreen('evaluation')}>Preview evaluation</button>
      <button className="btn btn-secondary" onClick={() => setScreen('review')}>Preview review</button>
    </nav>
    {screen === 'evaluation' ? <EvaluationDashboard currentRunRecord={run} onSelectRun={() => {}} /> : <VerificationView verification={review} onNavigateToEvaluations={() => setScreen('evaluation')} />}
  </main>;
}
createRoot(document.getElementById('root')).render(<Preview />);
