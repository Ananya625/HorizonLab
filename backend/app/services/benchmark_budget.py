"""Durable pilot-wide limits. Reserve before I/O, reconcile only complete responses."""
import json
import uuid


class PilotBudget:
    def __init__(self, database, manifest):
        self.db, self.manifest = database, manifest

    def _change(self, fn):
        m = self.manifest
        limits = {'trials':m.max_trials, 'calls':m.max_model_calls,
                  'generated_tokens':m.max_total_generated_tokens, 'per_call':m.max_output_tokens, 'model':m.model}
        with self.db._get_connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            row = conn.execute('SELECT data_json FROM benchmark_pilot_budgets WHERE pilot_id=?', (m.pilot_id,)).fetchone()
            state = json.loads(row[0]) if row else {'limits':limits, 'trials':[], 'calls':[], 'halted':False}
            if state['limits'] != limits:
                raise ValueError('Pilot identity already has different limits; limits cannot be reset on resume')
            result = fn(state)
            conn.execute('INSERT INTO benchmark_pilot_budgets VALUES (?, ?) ON CONFLICT(pilot_id) DO UPDATE SET data_json=excluded.data_json',
                (m.pilot_id, json.dumps(state, allow_nan=False)))
            return result

    def snapshot(self):
        return self._change(lambda state:state)

    def start_trial(self, run_id):
        def start(state):
            if run_id in state['trials']:
                return
            if state['halted'] or len(state['trials']) >= state['limits']['trials']:
                raise ValueError('Pilot halted or trial budget exhausted')
            state['trials'].append(run_id)
        self._change(start)

    def reserve(self, run_id):
        def reserve(state):
            if run_id not in state['trials']:
                raise ValueError('Trial must be registered before a model call')
            if state['halted'] or any(c['status']=='reserved' for c in state['calls']):
                raise ValueError('Pilot halted or an earlier response is unresolved; no retry is permitted')
            spent = sum(c.get('generated_tokens', c['reserved_tokens']) for c in state['calls'])
            remaining = state['limits']['generated_tokens']-spent
            if len(state['calls']) >= state['limits']['calls'] or remaining <= 0:
                raise ValueError('Pilot model-call or generated-token budget exhausted')
            entry = {'id':uuid.uuid4().hex,'run_id':run_id,'status':'reserved',
                     'reserved_tokens':min(state['limits']['per_call'], remaining)}
            state['calls'].append(entry)
            return entry
        return self._change(reserve)

    def finish(self, call_id, usage=None, error=None):
        def finish(state):
            entry = next(c for c in state['calls'] if c['id']==call_id)
            if entry['status'] != 'reserved':
                raise ValueError('Model call already finalized')
            if usage is None:
                entry.update(status='unknown', error=error or 'Response unavailable')
                state['halted'] = True
                return
            generated, inputs = usage['output_tokens'], usage['input_tokens']
            if type(generated) is not int or generated < 0 or type(inputs) is not int or inputs < 0:
                entry.update(status='unknown', error='Invalid usage')
                state['halted'] = True
                return
            entry.update(status='completed', generated_tokens=generated, input_tokens=inputs)
            if generated > entry['reserved_tokens']:
                state['halted'] = True
                entry['error'] = 'Provider exceeded the requested generation limit'
        self._change(finish)
