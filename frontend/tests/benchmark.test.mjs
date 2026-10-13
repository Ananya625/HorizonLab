import { test } from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { rolldown } from 'rolldown';
import { createRequire } from 'node:module';
import { executeTesting, runFullPipeline, parseTaskRequirement } from '../src/services/api.js';

test('zero settings survive serialization in every request', async () => {
  const original = globalThis.fetch;
  const bodies = [];
  globalThis.fetch = async (url, options) => { bodies.push(JSON.parse(options.body)); return { ok:true, json:async()=>({}) }; };
  try {
    await executeTesting({runId:'r', maxRecoveryRetries:0});
    await runFullPipeline({requestText:'test', temperature:0, maxRecoveryRetries:0});
    await parseTaskRequirement({requestText:'test', temperature:0});
    assert.equal(bodies[0].max_recovery_retries, 0);
    assert.equal(bodies[1].temperature, 0);
    assert.equal(bodies[1].max_recovery_retries, 0);
    assert.equal(bodies[2].temperature, 0);
  } finally { globalThis.fetch = original; }
});

async function loadComponent(input) {
  const bundle = await rolldown({input, external:['react','react-dom','react/jsx-runtime','lucide-react']});
  try {
    const { output } = await bundle.generate({format:'cjs', exports:'named'});
    const module = {exports:{}};
    new Function('require','module','exports', output[0].code)(createRequire(import.meta.url), module, module.exports);
    return module.exports;
  } finally { await bundle.close(); }
}

test('rejected generation is inspectable as escaped text in the execution log', async () => {
  const {default: View} = await loadComponent('./src/components/ExecutionControlRoom.jsx');
  const html = renderToStaticMarkup(React.createElement(View, {runId:'r', logs:[{
    id:'e',event_type:'error',message:'Invalid code',details:{rejected_output:'<script>bad()</script>'}
  }]}));
  assert.match(html, /Show rejected model output/);
  assert.match(html, /&lt;script&gt;/);
  assert.doesNotMatch(html, /<script>bad/);
});

test('model settings use the smaller default and preserve the configured selection', async () => {
  const {default: Settings} = await loadComponent('./src/components/OllamaSettingsModal.jsx');
  const props = {isOpen:true, temperature:0, setTemperature:()=>{}, onClose:()=>{}, onStatusUpdated:()=>{}};
  const fallback = renderToStaticMarkup(React.createElement(Settings, props));
  assert.match(fallback, /qwen3:1\.7b/);
  assert.doesNotMatch(fallback, /qwen2\.5-coder:7b/);
  const configured = renderToStaticMarkup(React.createElement(Settings, {...props,
    currentStatus:{current_model:'qwen3:8b', models:['qwen3:1.7b','qwen3:8b']}}));
  assert.match(configured, /value="qwen3:8b" selected=""/);
});

test('requirements always expose the next action even without clarification questions', async () => {
  const {default: View} = await loadComponent('./src/components/GoalModelView.jsx');
  const props = {goalModel:{main_goal:'Add numbers',ambiguities:[]},
    onProceedToConfirmation:()=>{},onNavigateToClarifications:()=>{}};
  const html = renderToStaticMarkup(React.createElement(View, props));
  assert.match(html, /Review and confirm requirements/);
  const blocked = renderToStaticMarkup(React.createElement(View, {...props,
    goalModel:{...props.goalModel,ambiguities:[{severity:'blocking',resolved:false}]}}));
  assert.match(blocked, /Resolve questions to continue/);
});

test('execution progress no longer claims to be preparing requirements after confirmation', async () => {
  const {default: View} = await loadComponent('./src/components/ParsingProgress.jsx');
  const html = renderToStaticMarkup(React.createElement(View, {requirements:false}));
  assert.match(html, /Running the requested workflow stages/);
  assert.doesNotMatch(html, /Preparing requirements for your review/);
});

test('dashboard displays zero measurements without fabricated defaults', async () => {
  const {default: Dashboard} = await loadComponent('./src/components/EvaluationDashboard.jsx');
  const html = renderToStaticMarkup(React.createElement(Dashboard, {currentRunRecord:{run_id:'r', evaluation:{
    metric_version:'2', success_rate:0, execution_time_seconds:0, total_tool_calls:0,
    tests_passed:0, tests_total:0, recovery_attempts_count:0, goal_drift_score:null,
  }}}));
  assert.match(html, />0%<\/span>/);
  assert.match(html, />0s<\/span>/);
  assert.doesNotMatch(html, />100%<\/span>/);
  assert.match(html, /Unavailable/);
});

test('verification does not approve unknown constraints or label missing drift optimal', async () => {
  const {default: View} = await loadComponent('./src/components/VerificationView.jsx');
  const html = renderToStaticMarkup(React.createElement(View, {verification:{
    overall_verdict:'UNVERIFIED', goal_drift_score:null, code_quality_score:null,
    security_verdict:'UNVERIFIED', constraint_compliances:[{constraint_text:'x',compliant:null}],
    criteria_evaluations:[], recommendations:[],
  }}));
  assert.match(html, /UNVERIFIED/);
  assert.doesNotMatch(html, /Optimal/);
  assert.match(html, /Unavailable/);
});

test('evaluation starts with the selected run and keeps benchmark controls out of the overview', async () => {
  const {default: Dashboard} = await loadComponent('./src/components/EvaluationDashboard.jsx');
  const html = renderToStaticMarkup(React.createElement(Dashboard, {}));
  assert.match(html, /aria-label="Evaluation sections"/);
  assert.match(html, /aria-pressed="true"[^>]*>This run/);
  assert.match(html, /Run history/);
  assert.doesNotMatch(html, /Run deterministic studies/);
  assert.doesNotMatch(html, /Historical Run Benchmark Comparisons/);
});

test('review distinguishes failed checks from unknown evidence and tolerates missing ratings', async () => {
  const {default: View} = await loadComponent('./src/components/VerificationView.jsx');
  const html = renderToStaticMarkup(React.createElement(View, {verification:{
    verifier_version:'2', overall_verdict:'UNVERIFIED',
    criteria_evaluations:[{criterion_id:'c1',criterion_description:'Addition',verdict:'UNVERIFIED',evidence:'No independent check'},
      {criterion_id:'c2',criterion_description:'Syntax',verdict:'FAIL',evidence:'Syntax error'}],
  }}));
  assert.match(html, /0 passed · 1 failed · 1 unverified/);
  assert.match(html, /badge-amber">UNVERIFIED/);
  assert.match(html, /badge-rose">FAIL/);
  assert.doesNotMatch(html, /Verified Evidence|Confidence: Not calibrated/);
  assert.match(html, /<details[^>]*><summary>Additional ratings/);
});

test('requirement waiting screen does not invent completed analysis stages', async () => {
  const {default: Progress} = await loadComponent('./src/components/ParsingProgress.jsx');
  const html = renderToStaticMarkup(React.createElement(Progress, {modelName:'qwen3:8b'}));
  assert.match(html, /Preparing requirements for your review/);
  assert.match(html, /qwen3:8b/);
  assert.doesNotMatch(html, /Stage [0-9]|Detecting Blocking|verified Goal Model/);
});

test('pilot report keeps unknown generated usage separate from known totals', async () => {
  const {StudyResults} = await loadComponent('./src/components/BenchmarkStudies.jsx');
  const html = renderToStaticMarkup(React.createElement(StudyResults, {report:{
    experiment_id:'pilot',status:'halted',manifest:{execution_mode:'local_ollama',model:'qwen3:8b'},trials:[],
    model_budget:{limits:{calls:15,generated_tokens:6000},calls:[
      {status:'completed',generated_tokens:80,reserved_tokens:1000},
      {status:'unknown',reserved_tokens:1000},
    ]},
  }}));
  assert.match(html,/qwen3:8b/);
  assert.match(html,/Known generated tokens: 80\/6000/);
  assert.match(html,/Unresolved reserved tokens: 1000/);
  assert.match(html,/Model calls: 2\/15/);
});
