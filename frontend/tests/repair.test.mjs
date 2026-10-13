import { test } from 'node:test';
import assert from 'node:assert/strict';
import { request } from '../src/services/api.js';

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
