"""Sequential, checkpointed benchmark studies with a durable model budget."""
import hashlib
import importlib.metadata
import json
import platform
import time
import uuid
from pathlib import Path
from ..models.benchmark_study import StudyManifest, BenchmarkAction
from ..models.schema import EvaluationMetrics
from .benchmark_adapters import resolve_adapter
from .benchmark_budget import PilotBudget
from .benchmark_environment import StudyEnvironment, now
from .benchmark_service import SimulatedFault, BudgetExceeded
from .benchmark_lock import experiment_lock
from .benchmark_analysis import summarize
from .benchmark_tasks import TASKS
from .db import db_service


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def provenance(manifest):
    modules = ['benchmark_study_service.py','benchmark_environment.py','benchmark_adapters.py',
        'benchmark_tasks.py','benchmark_analysis.py','benchmark_study_analysis.py','benchmark_budget.py',
        'benchmark_lock.py','benchmark_service.py','db.py','../models/benchmark_study.py']
    return {'python':platform.python_version(), 'platform':platform.platform(),
        'dependencies':{name:importlib.metadata.version(name) for name in ('fastapi','pydantic','httpx','pytest')},
        'code_sha256':{name:hashlib.sha256((Path(__file__).parent/name).read_bytes()).hexdigest() for name in modules},
        'task_sha256':{key:fingerprint(vars(TASKS[key])) for key in manifest.task_ids}}


class StudyService:
    def run(self, manifest: StudyManifest, experiment_id=None):
        adapter = resolve_adapter(manifest)  # Reject missing team adapters before creating runs.
        with experiment_lock(db_service.db_path):
            existing = next((r for r in db_service.get_experiments() if r['experiment_id']==experiment_id), None) if experiment_id else None
            if experiment_id and (not existing or existing['manifest'] != manifest.model_dump()):
                raise ValueError('Resume requires an identical persisted manifest')
            if existing and existing['status'] in ('completed', 'halted'):
                return existing
            current_provenance = provenance(manifest)
            if existing and existing['provenance'] != current_provenance:
                raise ValueError('Runtime, task or harness version changed; do not resume incompatible evidence')
            report = existing or {'experiment_id':f'exp_{uuid.uuid4().hex}', 'manifest':manifest.model_dump(),
                'created_at':now(),'trials':[], 'status':'running','active_trial':None,'provenance':current_provenance,
                'limitations':'Scripted conditions test fixtures, not learned team modules. Ollama chooses safe simulator actions; this is not arbitrary code-generation evaluation.'}
            if manifest.execution_mode=='local_ollama':
                description = adapter.describe()  # Metadata only; no warm-up or generation request.
                if existing and report.get('model_metadata') != description:
                    raise ValueError('Model digest, settings or server version changed; resume refused')
                report['model_metadata'] = description
            budget = PilotBudget(db_service, manifest) if manifest.execution_mode=='local_ollama' else None
            root = Path(db_service.db_path).resolve().parent/'benchmark_workspaces'/report['experiment_id']
            completed = {r['trial_key'] for r in report['trials']}
            report['status'] = 'running'
            try:
                for task in manifest.task_ids:
                    for length in manifest.task_lengths:
                        for repeat in range(manifest.repetitions):
                            for condition in manifest.conditions:
                                key = f'{task}:{length}:{repeat}:{condition}'
                                if key in completed:
                                    continue
                                if budget and budget.snapshot()['halted']:
                                    report['status'] = 'halted'
                                    break
                                run_id = 'bench_'+uuid.uuid5(uuid.NAMESPACE_URL, report['experiment_id']+key).hex
                                if budget:
                                    budget.start_trial(run_id)
                                report['active_trial'] = run_id
                                db_service.save_experiment(report['experiment_id'], report['manifest'], report)
                                row = self._trial(manifest, resolve_adapter(manifest), budget, task, length, manifest.seed+repeat, condition, run_id, root/run_id)
                                row['trial_key'] = key
                                report['trials'].append(row)
                                completed.add(key)
                                report['active_trial'] = None
                                db_service.save_experiment(report['experiment_id'], report['manifest'], report)
            except Exception as exc:
                report.update(status='interrupted', error=f'{type(exc).__name__}: {exc}')
                if budget:
                    report['model_budget'] = budget.snapshot()
                db_service.save_experiment(report['experiment_id'], report['manifest'], report)
                raise
            if budget:
                report['model_budget'] = budget.snapshot()
            report['comparisons'] = summarize(report['trials'])
            from .benchmark_study_analysis import study_analytics
            report['analytics'] = study_analytics(report['trials'])
            report['status'] = 'halted' if budget and budget.snapshot()['halted'] else 'completed'
            report['finished_at'] = now()
            report['planned_trials'] = len(manifest.task_ids)*len(manifest.task_lengths)*manifest.repetitions*len(manifest.conditions)
            db_service.save_experiment(report['experiment_id'], report['manifest'], report)
            return report

    def _trial(self, m, adapter, budget, task, length, seed, condition, run_id, workspace):
        saved = db_service.get_benchmark_checkpoint(run_id)
        if saved and saved.get('completed_row'):
            self._persist_final(saved['completed_row'])
            return saved['completed_row']
        if not db_service.get_run_record(run_id):
            db_service.create_or_update_run(run_id, task, TASKS[task].title, TASKS[task].title, str(workspace),
                current_stage='benchmark', status='in_progress', metadata={'manifest':m.model_dump(), 'execution_mode':m.execution_mode, 'condition':condition})
        env = StudyEnvironment(task, workspace, m, length, seed, saved.get('environment') if saved else None)
        state = saved or {'adapter_state':{}, 'initial_state':env.snapshot(), 'elapsed':0., 'index':0, 'retry':0,
            'retry_tool':None, 'last_result':None, 'error':None, 'events':[], 'episodes':[], 'pending_action':None,
            'model_usage':[], 'timing_complete':True, 'termination':'completed'}
        if saved:
            state['timing_complete'] = False  # A killed process leaves an unmeasured tail; do not invent its duration.
        started, previous_elapsed = time.perf_counter(), state['elapsed']

        def elapsed():
            return previous_elapsed+time.perf_counter()-started

        def event(kind, data, source='fixture', step=None):
            value = {'event_id':f"event-{len(state['events'])+1}", 'kind':kind, 'run_id':run_id, 'task_id':task,
                'step':env.calls if step is None else step, 'timestamp':now(), 'source':source, 'version':'2',
                'agent_id':m.adapter_id, 'data':data}
            state['events'].append(value)

        def checkpoint():
            state['environment'], state['elapsed'] = env.checkpoint_state(), elapsed()
            db_service.save_benchmark_checkpoint(run_id, state, state['events'])

        checkpoint()
        if saved and state.get('pending_model'):
            # A response lost with the worker cannot be charged as zero or repeated.
            entry = next(c for c in budget.snapshot()['calls'] if c['id']==state['pending_model'])
            if entry['status']=='reserved':
                budget.finish(state['pending_model'], error='Worker stopped with an unresolved response')
            if entry['status']=='completed':
                usage = {'input_tokens':entry['input_tokens'],'output_tokens':entry['generated_tokens']}
                state['model_usage'].append(usage)
                event('model_result', {'call_id':entry['id'], **usage, 'response_interrupted':True}, 'model')
            else:
                event('model_result', {'call_id':entry['id'], 'error':'Worker stopped with an unresolved response',
                    'usage_unknown':True}, 'model')
            state['termination'] = 'model_response_interrupted'
            state['pending_model'] = None
        while state['termination']=='completed' and (env.next_tool() is not None or state['retry_tool']):
            if env.calls >= m.max_steps or elapsed() >= m.timeout_seconds:
                state['termination'] = 'budget_exceeded'
                break
            operation_id = f'{seed}-{state["index"]}'
            observation = env.observation(operation_id, state['retry'], state['last_result'], state['error'])
            if state['retry_tool']:
                observation['next_tool'] = state['retry_tool']
            if state['pending_action']:
                action = BenchmarkAction.model_validate(state['pending_action'])
            else:
                telemetry = []
                if budget:
                    try:
                        reservation = budget.reserve(run_id)
                    except ValueError:
                        state['termination'] = 'model_budget_exhausted'
                        break
                    state['pending_model'] = reservation['id']
                    event('model_call', {'call_id':reservation['id'], 'max_generated_tokens':reservation['reserved_tokens']}, 'model')
                    checkpoint()  # Durable reservation and request intent precede network I/O.
                    try:
                        messages = adapter.request(observation, state['adapter_state'], condition)
                        content, new_state, usage = adapter.complete(messages, condition, state['adapter_state'],
                            min(m.model_timeout_seconds, max(.1, m.timeout_seconds-elapsed())), reservation['reserved_tokens'])
                    except Exception as exc:
                        budget.finish(reservation['id'], error=type(exc).__name__)
                        event('model_result', {'call_id':reservation['id'], 'error':f'{type(exc).__name__}: {exc}', 'usage_unknown':True}, 'model')
                        state.update(pending_model=None, termination='model_error')
                        checkpoint()
                        break
                    budget.finish(reservation['id'], usage=usage)
                    state['pending_model'] = None
                    state['model_usage'].append(usage)
                    event('model_result', {'call_id':reservation['id'], **usage, 'content':content}, 'model')
                    try:
                        action = BenchmarkAction.model_validate_json(content)
                    except ValueError:
                        state['termination'] = 'invalid_model_action'
                        checkpoint()
                        break
                    if budget.snapshot()['halted']:
                        state['termination'] = 'provider_limit_violation'
                        checkpoint()
                        break
                else:
                    action, new_state, telemetry = adapter.act(observation, state['adapter_state'], condition)
                    action = BenchmarkAction.model_validate(action)
                state['adapter_state'] = new_state
                for item in telemetry:
                    data = dict(item['data'])
                    if item['kind']=='memory':
                        retrieved = data.pop('retrieved', {})
                        data.update(relevant_available=True, relevant_retrieved=retrieved==env.contract,
                            incorrect_retrieved=bool(retrieved) and retrieved!=env.contract,
                            used_correctly=(action.arguments.get('publish_tag')==env.contract['publish_tag']) if action.tool=='notify' else None,
                            delay_steps=env.calls, memory_level='core', available_version='1')
                    event(item['kind'], data, 'fixture' if m.execution_mode=='trusted_simulation' else 'team_module')
                state['pending_action'] = action.model_dump()
                checkpoint()
            if elapsed() >= m.timeout_seconds:
                state['termination'] = 'budget_exceeded'
                break
            try:
                result = env.call_action(action)
                if state['retry']:
                    state['episodes'][-1]['local_action_succeeded'] = True
                state.update(last_result=result, error=None, retry=0, retry_tool=None, index=state['index']+1)
                if action.tool=='clarify':
                    event('human', {'intervention_count':1, 'seconds':0., 'workload':None, 'simulated':True})
            except SimulatedFault as exc:
                if state['retry']==0:
                    state['episodes'].append({'episode_id':f'{run_id}-recovery-{len(state["episodes"])+1}',
                        'failure_step':env.calls,'failure_type':str(exc),'detection_seconds':elapsed(),
                        'strategy':condition,'attempts':0,'extra_tool_calls':0,'local_action_succeeded':False})
                if condition=='baseline' or state['retry'] >= m.max_retries:
                    state['termination'] = 'fault_unrecovered'
                else:
                    state.update(retry=state['retry']+1, retry_tool=action.tool, error=str(exc))
                    state['episodes'][-1]['attempts'] += 1
                    state['episodes'][-1]['extra_tool_calls'] += 1
            except (ValueError, BudgetExceeded) as exc:
                state['termination'] = 'budget_exceeded' if isinstance(exc, BudgetExceeded) else 'invalid_tool_action'
            event('tool', env.events[-1], 'evaluator')
            if action.tool in ('checkpoint','notify'):
                for item in reversed(state['events']):
                    if item['kind']=='memory' and item['step']==env.calls-1 and item['data'].get('used_correctly') is None:
                        # Memory telemetry was already persisted as retrieval evidence; usage is a separate immutable event.
                        event('memory_use', {'retrieval_event_id':item['event_id'], 'used_correctly':env.events[-1]['expected_aligned']}, 'evaluator')
                        break
            state['pending_action'] = None
            checkpoint()
        verified = env.verify()
        if elapsed() >= m.timeout_seconds:
            state['termination'] = 'budget_exceeded'
        if state['termination'] != 'completed':
            verified['verified_success'] = False
        duration = elapsed()
        for episode in state['episodes']:
            episode.update(verified_recovered=verified['verified_success'] and episode['local_action_succeeded'],
                duration_seconds=duration-episode['detection_seconds'],
                post_recovery_violations=[k for k,v in verified['criteria'].items() if not v])
        tool_seconds = sum(e['duration_seconds'] for e in env.events)
        row = {'run_id':run_id,'task_id':task,'condition':condition,'seed':seed,'task_length':length,
            'cohort':fingerprint({'suite':m.suite_version,'scenario':m.scenario,'fault':m.fault.model_dump(),'length':length,
                'ambiguity':m.ambiguity,'feedback':m.feedback_policy,'model':m.model,'environment':m.environment_version,'verifier':m.verifier_version}),
            'scenario':m.scenario,'execution_mode':m.execution_mode,'adapter_id':m.adapter_id,'adapter_version':m.adapter_version,
            'fault':m.fault.model_dump(),'fault_occurred':env.fault_occurred,
            'initial_state':state['initial_state'],'verified_success':verified['verified_success'],
            'verification':verified,'termination_reason':state['termination'],'duration_seconds':duration,
            'timing_complete':state['timing_complete'],'tool_calls':env.calls,'tool_execution_seconds':tool_seconds,
            'harness_overhead_seconds':max(0,duration-tool_seconds-sum(u.get('model_duration_ns',0) or 0 for u in state['model_usage'])/1e9),
            'recovery_episodes':state['episodes'],'events':state['events'],'finished_at':now(),
            'model_calls':sum(e['kind']=='model_call' for e in state['events']),
            'generated_tokens':sum(u['output_tokens'] for u in state['model_usage']) if budget else None,
            'input_tokens':sum(u['input_tokens'] for u in state['model_usage']) if budget else None,
            'token_usage_complete':not any(e['kind']=='model_result' and e['data'].get('usage_unknown') for e in state['events']),
            'compute_cost':None}
        state['completed_row'] = row
        checkpoint()
        self._persist_final(row)
        return row

    def _persist_final(self, row):
        v = row['verification']
        outcome = 'success' if row['verified_success'] else 'budget_exceeded' if 'budget' in row['termination_reason'] else 'failed'
        db_service.finalize_run(EvaluationMetrics(run_id=row['run_id'],task_id=row['task_id'],metric_version='2',
            outcome=outcome, verified_success=row['verified_success'], success_rate=100*sum(v['criteria'].values())/len(v['criteria']),
            termination_reason=row['termination_reason'],execution_mode=row['execution_mode'],
            execution_time_seconds=row['duration_seconds'] if row['timing_complete'] else None,
            total_tool_calls=row['tool_calls'],total_model_calls=row['model_calls'],
            input_tokens=row['input_tokens'] if row['token_usage_complete'] else None,
            output_tokens=row['generated_tokens'] if row['token_usage_complete'] else None,
            recovery_attempts_count=sum(e['attempts'] for e in row['recovery_episodes']),
            tests_passed=v['tests_passed'],tests_total=v['tests_total'],
            measurement_scope='Sequential simulator actions, model time, verification and checkpoint overhead; downtime/unknown crash tail excluded and timing marked incomplete'))


study_service = StudyService()
