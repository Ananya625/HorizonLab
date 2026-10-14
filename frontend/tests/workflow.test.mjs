import { test } from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { rolldown } from 'rolldown';
import { createRequire } from 'node:module';
import { createWorkflowController } from '../src/services/workflowController.js';
import { fetchWorkflowEvents, fetchWorkflowEvent } from '../src/services/api.js';

const pending = () => { let resolve; const promise = new Promise(r => { resolve = r; }); return { promise, resolve }; };

test('finding selection during pagination does not strand the loading indicator', async () => {
  let state; const page = pending();
  const controller = createWorkflowController({
    report: async () => ({ snapshot_sequence: 100 }),
    events: async (run, after) => after ? page.promise : { events: [], next_after: 50 },
    event: async (run, id) => ({ event_id: id }),
  }, s => { state = s; });
  await controller.select('run'); const paging = controller.page('next');
  await controller.inspect({ event_ids: ['e1'] });
  assert.equal(state.loading, true);
  page.resolve({ events: [{ event_id: 'page2' }], next_after: null }); await paging;
  assert.equal(state.loading, false); assert.equal(state.evidence[0].event_id, 'e1');
});

test('switching runs rejects slow reports and finding evidence from a previous run', async () => {
  const slow = pending(), slowEvidence = pending(); let state;
  const api = {
    report: async id => id === 'old' ? slow.promise : { run_id: id, snapshot_sequence: 20 },
    events: async id => ({ events: [{ run_id: id }], next_after: null }),
    event: async () => slowEvidence.promise,
  };
  const controller = createWorkflowController(api, s => { state = s; });
  const old = controller.select('old');
  await controller.select('new');
  slow.resolve({ run_id: 'old', snapshot_sequence: 8 }); await old;
  assert.equal(state.report.run_id, 'new');
  const inspect = controller.inspect({ event_ids: ['secret-old'] });
  await controller.select('newer');
  slowEvidence.resolve({ event_id: 'secret-old' }); await inspect;
  assert.equal(state.report.run_id, 'newer'); assert.deepEqual(state.evidence, []);
});

test('timeline navigation pins the report snapshot and finding buttons load exact event IDs', async () => {
  let state; const requests = [];
  const controller = createWorkflowController({
    report: async () => ({ snapshot_sequence: 100 }),
    events: async (id, after, through) => { requests.push([id, after, through]); return { events: [], next_after: after === 0 ? 50 : null }; },
    event: async (id, event) => ({ run_id: id, event_id: event }),
  }, s => { state = s; });
  await controller.select('run'); await controller.page('next'); await controller.page('previous');
  assert.deepEqual(requests, [['run', 0, 100], ['run', 50, 100], ['run', 0, 100]]);
  await controller.inspect({ event_ids: ['e8', 'e2'], kind: 'suspected_loop' });
  assert.deepEqual(state.evidence.map(e => e.event_id), ['e8', 'e2']);
});

test('failed page can retry and disposed component cannot receive late updates', async () => {
  let state; let fail = true; const slow = pending();
  const controller = createWorkflowController({
    report: async () => ({ snapshot_sequence: 2 }),
    events: async () => { if (fail) throw new Error('offline'); return slow.promise; },
  }, s => { state = s; });
  await controller.select('run'); assert.equal(state.error, 'offline'); assert.equal(state.loading, false);
  fail = false; const retry = controller.select('run'); await Promise.resolve();
  controller.dispose(); const before = state;
  slow.resolve({ events: [], next_after: null }); await retry; assert.equal(state, before);
});

test('workflow endpoint encodes IDs and preserves zero snapshot', async () => {
  const original = globalThis.fetch; const urls = [];
  globalThis.fetch = async url => { urls.push(url); return { ok: true, json: async () => ({}) }; };
  try {
    await fetchWorkflowEvents('a/b', 0, 0); await fetchWorkflowEvent('a/b', 'event?x');
    assert.match(urls[0], /a%2Fb\/workflow\/events\?after=0&limit=50&through=0$/);
    assert.match(urls[1], /events\/event%3Fx$/);
  } finally { globalThis.fetch = original; }
});

test('workflow UI renders zeros, unknowns, stale verification and evidence controls', async () => {
  const bundle = await rolldown({ input: './src/components/WorkflowAnalysis.jsx', external: ['react', 'react/jsx-runtime'] });
  try {
    const { output } = await bundle.generate({ format: 'cjs', exports: 'named' }); const module = { exports: {} };
    new Function('require', 'module', 'exports', output[0].code)(createRequire(import.meta.url), module, module.exports);
    const resource = { tool_calls: 0, model_calls: 0, duration_seconds: 0, output_tokens: null };
    const report = { version: 'workflow-v1', execution_mode: 'mixed_demo', evidence_status: 'partial', snapshot_sequence: 1,
      summary: { action_attempts: 0, resources: resource, progress_rate: 0, verified_sub_goals: 0, required_sub_goals: 1, verified_outcome: null }, coverage: { paired_outcomes: 0 },
      stagnation: { baseline: 'first_observation', actions: 0 }, sub_goals: [{ id: 's', title: 'A', status: 'stale', attempts: 1, incomplete_attempts: 0, revisits: 0, regressions: 0, resources: resource }],
      overhead: { recovery: resource, rework: resource, union: resource }, recovery: [], progress: [], limitations: [], calculation: {},
      saved_measurements: { source: 'Stored records only', recorded_model_requests: 2, latest_test: { reported_status: 'PASSED', passed: 3, total: 3, evidence_version: 'legacy', freshness: 'Not revalidated' } },
      verification_support: [{ criterion_id: 'syntax', description: 'Syntax', available: true, checker: 'python_syntax_workspace' }, { criterion_id: 'regression', description: 'Regression', available: false, next_step: 'Supply a trusted baseline' }],
      findings: [{ id: 'f', kind: 'suspected_loop', confidence: 'heuristic', message: 'Review evidence' }] };
    const html = renderToStaticMarkup(React.createElement(module.exports.WorkflowView, { state: { runId: 'r', report, history: [0], evidence: [], page: { events: [{ event_id: 'e1', sequence: 1, kind: 'action_start' }] } } }));
    assert.match(html, /Actual Workflow Analysis/); assert.match(html, /Unavailable/); assert.match(html, /0.0%/);
    assert.match(html, /stale/); assert.match(html, /heuristic/); assert.match(html, /Inspect event 1/);
    assert.match(html, /Workflow visual summary/); assert.match(html, /Sub-goal verification/);
    assert.match(html, /Evidence coverage/); assert.match(html, /Effort by sub-goal/);
    assert.match(html, /aria-valuenow="0"/);
    assert.doesNotMatch(html, /Verified success/);
    assert.match(html, /Not revalidated/); assert.match(html, /Supply a trusted baseline/);
    assert.match(html, /Run verification to obtain a result/);
  } finally { await bundle.close(); }
});
