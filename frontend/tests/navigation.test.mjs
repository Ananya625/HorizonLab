import { test } from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import { rolldown } from 'rolldown';
import { createRequire } from 'node:module';

// Exercise App's real handlers and rendered component props, with HTTP and
// hook storage controlled by the test. Child components and effects do not run.
async function appHarness(t, { failConfirm = false, failResume = false, blocking = false } = {}) {
  const cells = [];
  let cursor = 0;
  const hooks = {...React, useEffect: () => {}, useState(initial) {
    const index = cursor++;
    if (!(index in cells)) cells[index] = initial;
    return [cells[index], value => { cells[index] = typeof value === 'function' ? value(cells[index]) : value; }];
  }};
  const bundle = await rolldown({input:'./src/App.jsx', external:['react','react/jsx-runtime','lucide-react']});
  const {output} = await bundle.generate({format:'cjs', exports:'named'});
  await bundle.close();
  const module = {exports:{}};
  const require = createRequire(import.meta.url);
  new Function('require','module','exports', output[0].code)(name => name === 'react' ? hooks : require(name), module, module.exports);
  const goal = {run_id:'navigation-run', main_goal:'Add numbers', is_confirmed:false,
    ambiguities:blocking ? [{severity:'blocking',resolved:false}] : []};
  const calls = [];
  t.mock.method(globalThis, 'fetch', async (url, options = {}) => {
    const path = new URL(url).pathname;
    calls.push({path, body:options.body ? JSON.parse(options.body) : null});
    let result;
    let ok = true;
    if (path === '/api/runs') result = {runs:[]};
    else if (path === '/api/goals/parse') result = goal;
    else if (path === '/api/goals/resolve-ambiguity') result = {...goal, ambiguities:[]};
    else if (path === '/api/goals/confirm/navigation-run') {
      ok = !failConfirm;
      result = ok ? {...goal,is_confirmed:true} : {detail:'Confirmation rejected'};
    } else if (path === '/api/pipeline/run-all') {
      const resume = !!JSON.parse(options.body).run_id;
      ok = !(resume && failResume);
      result = ok ? {run_id:goal.run_id,goal_model:{...goal,is_confirmed:resume},plan:resume ? {steps:[]} : null}
        : {detail:'Planner unavailable'};
    } else throw new Error(`Unexpected HTTP request: ${path}`);
    return {ok,status:ok ? 200 : 400,json:async () => result};
  });
  // Expected failure tests should not flood the test output.
  t.mock.method(console, 'error', () => {});
  const render = () => { cursor = 0; return module.exports.default(); };
  function find(node, predicate) {
    if (!node || typeof node !== 'object') return null;
    if (predicate(node)) return node;
    for (const child of React.Children.toArray(node.props?.children)) {
      const result = find(child, predicate);
      if (result) return result;
    }
    return null;
  }
  const component = name => find(render(), n => n.type?.name === name);
  const pipelineCalls = () => calls.filter(c => c.path === '/api/pipeline/run-all');
  return {component,calls,pipelineCalls,alert:() => find(render(), n => n.props?.role === 'alert')};
}

test('full workflow waits for confirmation then resumes the same run once', async t => {
  const app = await appHarness(t);
  await app.component('Header').props.onRunFullPipeline();
  assert.equal(app.pipelineCalls().length, 1);
  const review = app.component('GoalModelView');
  assert.ok(review);
  review.props.onProceedToConfirmation();
  const gate = app.component('ConfirmationGate');
  assert.equal(gate.props.continueFullWorkflow, true);
  await gate.props.onConfirm();
  assert.equal(app.pipelineCalls().length, 2);
  assert.equal(app.pipelineCalls()[1].body.run_id, 'navigation-run');
  assert.ok(app.component('EvaluationDashboard'));
  assert.ok(app.calls.findIndex(c => c.path.includes('/goals/confirm/')) < app.calls.findLastIndex(c => c.path.includes('/pipeline/')));
});

test('clicking full workflow again navigates to confirmation without executing', async t => {
  const app = await appHarness(t);
  await app.component('Header').props.onRunFullPipeline();
  await app.component('Header').props.onRunFullPipeline();
  assert.ok(app.component('ConfirmationGate'));
  assert.equal(app.pipelineCalls().length, 1);
});

test('blocking questions route to clarification before confirmation', async t => {
  const app = await appHarness(t, {blocking:true});
  await app.component('Header').props.onRunFullPipeline();
  await app.component('Header').props.onRunFullPipeline();
  const clarification = app.component('ClarificationCenter');
  assert.ok(clarification);
  assert.equal(app.pipelineCalls().length, 1);
  await clarification.props.onResolveQuestion({runId:'navigation-run',ambiguityId:'a',userAnswer:'yes'});
  app.component('ClarificationCenter').props.onProceedToConfirmation();
  await app.component('ConfirmationGate').props.onConfirm();
  assert.equal(app.pipelineCalls().length, 2);
});

test('manual requirement confirmation does not launch the full workflow', async t => {
  const app = await appHarness(t);
  await app.component('TaskInputSection').props.onAnalyze();
  app.component('GoalModelView').props.onProceedToConfirmation();
  await app.component('ConfirmationGate').props.onConfirm();
  assert.equal(app.pipelineCalls().length, 0);
  assert.ok(app.component('ConfirmationGate').props.onProceedToPlanner);
});

test('confirmation failure never starts the planner', async t => {
  const app = await appHarness(t, {failConfirm:true});
  await app.component('Header').props.onRunFullPipeline();
  app.component('GoalModelView').props.onProceedToConfirmation();
  await assert.rejects(app.component('ConfirmationGate').props.onConfirm(), /Confirmation rejected/);
  assert.equal(app.alert().props.children, 'Confirmation rejected');
  assert.equal(app.pipelineCalls().length, 1);
  assert.ok(app.component('ConfirmationGate'));
});

test('resume failures are visible on the confirmation screen without automatic retries', async t => {
  const app = await appHarness(t, {failResume:true});
  await app.component('Header').props.onRunFullPipeline();
  app.component('GoalModelView').props.onProceedToConfirmation();
  await app.component('ConfirmationGate').props.onConfirm();
  assert.equal(app.alert().props.children, 'Planner unavailable');
  assert.ok(app.component('ConfirmationGate'));
  assert.equal(app.pipelineCalls().length, 2);
});

test('reset cancels the pending full workflow for subsequent manual analysis', async t => {
  const app = await appHarness(t);
  await app.component('Header').props.onRunFullPipeline();
  app.component('Header').props.onReset();
  await app.component('TaskInputSection').props.onAnalyze();
  app.component('GoalModelView').props.onProceedToConfirmation();
  await app.component('ConfirmationGate').props.onConfirm();
  assert.equal(app.pipelineCalls().length, 1);
});
