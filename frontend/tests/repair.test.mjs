import { test } from 'node:test';
import assert from 'node:assert/strict';
import { request } from '../src/services/api.js';
import { startLogPolling } from '../src/services/logPolling.js';

test('log polling discards stale responses and never schedules idle or disposed work', async () => {
  let resolve;
  const seen = [], timers = [];
  const stop = startLogPolling({runId:'old', active:true,
    fetchLogs:() => new Promise(r => { resolve = r; }), onLogs:logs => seen.push(logs),
    schedule:fn => timers.push(fn), cancel:() => {}});
  stop();
  resolve({logs:['stale']});
  await new Promise(setImmediate);
  assert.deepEqual(seen, []);
  assert.deepEqual(timers, []);
  startLogPolling({runId:'new', active:false, fetchLogs:async () => ({logs:['final']}),
    onLogs:logs => seen.push(logs), schedule:fn => timers.push(fn), cancel:() => {}});
  await new Promise(setImmediate);
  assert.deepEqual(seen, [['final']]);
  assert.deepEqual(timers, []);
});

test('request preserves default content type when custom headers are supplied', async t => {
  let options;
  t.mock.method(globalThis, 'fetch', async (url, opts) => {
    options = opts;
    return {ok:true, json:async () => ({})};
  });
  await request('/health', {headers:{'X-Test':'yes'}, method:'POST'});
  assert.equal(options.headers['Content-Type'], 'application/json');
  assert.equal(options.headers['X-Test'], 'yes');
  assert.equal(options.method, 'POST');
  await request('/health', {headers:{'Content-Type':'text/plain'}});
  assert.equal(options.headers['Content-Type'], 'text/plain');
});

async function componentHarness(path) {
  const React = (await import('react')).default;
  const {rolldown} = await import('rolldown');
  const {createRequire} = await import('node:module');
  const require = createRequire(import.meta.url);
  const cells = [], effects = [];
  let cursor = 0;
  const hooks = {...React, useEffect:fn => effects.push(fn), useRef:() => ({current:null}),
    useState(initial) {
      const i = cursor++;
      if (!(i in cells)) cells[i] = initial;
      return [cells[i], value => { cells[i] = value; }];
    }};
  const bundle = await rolldown({input:path, transform:{define:{'import.meta.env':'{}'}}, external:['react','react/jsx-runtime','lucide-react']});
  const {output} = await bundle.generate({format:'cjs',exports:'named'});
  await bundle.close();
  const module = {exports:{}};
  new Function('require','module','exports',output[0].code)(name => name === 'react' ? hooks : require(name), module, module.exports);
  function nodes(node) {
    if (!node || typeof node !== 'object') return [];
    return [node, ...React.Children.toArray(node.props?.children).flatMap(nodes)];
  }
  return {effects, render(props) {cursor=0; return nodes(module.exports.default(props));}};
}

test('audit history renders saved snapshots and permits version selection', async t => {
  const history = [{version:1, change_summary:'original', model:{main_goal:'first'}},
    {version:2, change_summary:'revision', model:{main_goal:'second'}}];
  t.mock.method(globalThis, 'fetch', async () => ({ok:true,json:async () => ({versions:history})}));
  const view = await componentHarness('./src/components/AuditHistoryView.jsx');
  view.render({runId:'r'});
  const dispose = view.effects[0]();
  await new Promise(setImmediate);
  let nodes = view.render({runId:'r'});
  assert.match(nodes.find(n => n.type === 'pre').props.children, /second/);
  nodes.find(n => n.type === 'button').props.onClick();
  nodes = view.render({runId:'r'});
  assert.match(nodes.find(n => n.type === 'pre').props.children, /first/);
  dispose();
});

test('log controls refresh and toggle auto-scroll', async () => {
  const view = await componentHarness('./src/components/ExecutionControlRoom.jsx');
  let refreshed = 0;
  const props = {runId:'r', onRefreshLogs:() => refreshed++};
  const nodes = view.render(props);
  nodes.find(n => n.type === 'button' && n.props.children === 'Refresh logs').props.onClick();
  assert.equal(refreshed, 1);
  nodes.find(n => n.props.type === 'checkbox').props.onChange({target:{checked:false}});
  assert.equal(view.render(props).find(n => n.props.type === 'checkbox').props.checked, false);
});
