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
