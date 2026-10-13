import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
const require = createRequire(path.resolve('package.json'));
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');
const { rolldown } = await import(pathToFileURL(require.resolve('rolldown')).href);
import { createRequire } from 'node:module';
import { executeTesting, runFullPipeline, parseTaskRequirement } from 'file:///C:/Users/Varsha%20Somashekar/OneDrive/Desktop/HorizonLab/frontend/src/services/api.js';

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
  const bundle = await rolldown({input, plugins:[proposalPlugin()], external:['react','react-dom','react/jsx-runtime','lucide-react']});
  try {
    const { output } = await bundle.generate({format:'cjs', exports:'named'});
    const module = {exports:{}};
    new Function('require','module','exports', output[0].code)(require, module, module.exports);
    return module.exports;
  } finally { await bundle.close(); }
}

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

function proposalPlugin() {
 return {name:'review-proposals',transform(code,id) {
  const name=path.basename(id);
  if (id.replaceAll('\\','/').includes('/src/components/') && ['EvaluationDashboard.jsx','OllamaSettingsModal.jsx'].includes(name)) {
   return {code:fs.readFileSync(path.resolve('../output/merge-review-2026-10-12/proposed',name),'utf8'),map:null};
  }
 }};
}
test('proposed settings preserves hidden state, selected model and zero temperature',async()=>{
 const {default:Modal}=await loadComponent('./src/components/OllamaSettingsModal.jsx');
 assert.equal(renderToStaticMarkup(React.createElement(Modal,{isOpen:false})), '');
 const html=renderToStaticMarkup(React.createElement(Modal,{isOpen:true,currentStatus:{host:'http://localhost:11434',current_model:'qwen3:8b',models:['qwen3:8b']},temperature:0,setTemperature:()=>{},onClose:()=>{},onStatusUpdated:()=>{}}));
 assert.match(html,/qwen3:8b/); assert.match(html,/value="0"/); assert.match(html,/Save &amp; Test Connection/);
});
test('settings API preserves the supplied configuration object',async()=>{
 const {configureOllama}=await import(pathToFileURL(path.resolve('src/services/api.js')).href);
 const previous=globalThis.fetch; let sent;
 globalThis.fetch=async(url,options)=>{sent={url,body:JSON.parse(options.body)};return {ok:true,json:async()=>({status:{connected:true}})};};
 try { await configureOllama({host:'http://localhost:11434',default_model:'qwen3:8b'});
 assert.equal(sent.url,'http://127.0.0.1:8000/api/ollama/configure');
 assert.deepEqual(sent.body,{host:'http://localhost:11434',default_model:'qwen3:8b'});
 }finally{globalThis.fetch=previous;}
});
test('production build with both proposed components',async()=>{
 const {build}=await import(pathToFileURL(require.resolve('vite')).href);
 await build({plugins:[{...proposalPlugin(),enforce:'pre'}],build:{outDir:path.resolve('../output/merge-review-2026-10-12/build'),emptyOutDir:false}});
});
