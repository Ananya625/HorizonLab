"""Trusted software-task simulator. Does not execute user/model supplied code.

Its scripted strategies test the harness and recovery controls, not LLM capability.
Evaluator answers and state are held outside the gateway's public observations.
"""
import copy
import hashlib
import random
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from ..models.benchmark import ExperimentManifest
from ..models.schema import EvaluationMetrics
from .benchmark_tasks import TASKS, public_tasks
from .benchmark_analysis import summarize
from .db import db_service
from .benchmark_lock import experiment_lock

_lock = threading.Lock()


class BudgetExceeded(RuntimeError):
    pass


class SimulatedFault(RuntimeError):
    pass


def source_hash(source):
    return hashlib.sha256(source.encode()).hexdigest()


class SoftwareEnvironment:
    def __init__(self, task_id, workspace, manifest):
        self.task = TASKS[task_id]
        self.workspace = Path(workspace)
        self.workspace.mkdir(parents=True, exist_ok=False)
        self.source_path = self.workspace / 'solution.py'
        self.source_path.write_text(self.task.initial, encoding='utf-8')
        self.manifest = manifest
        self.started = time.perf_counter()
        self.calls = 0
        self.tool_counts = {}
        self.fault_occurred = False
        self.events = []
        self.commits = []
        self.notifications = []
        self.operations = {}
        self.check_digest = None
        self.prohibited = []

    def _check_source(self):
        source = self.source_path.read_text(encoding='utf-8')
        # Defense in depth: this demo may only execute immutable server-owned strings.
        if source not in (self.task.initial, self.task.solution):
            return {'passed': 0, 'total': len(self.task.cases), 'error': 'Untrusted source rejected'}
        namespace = {}
        exec(compile(source, '<trusted-fixture>', 'exec'), namespace)
        passed = 0
        for args, expected in self.task.cases:
            try:
                passed += namespace['solve'](*copy.deepcopy(args)) == expected
            except Exception:
                pass
        return {'passed': passed, 'total': len(self.task.cases)}

    def call(self, tool, operation_id):
        if tool not in {'read', 'apply_patch', 'run_checks', 'commit', 'notify'} or not isinstance(operation_id, str) or not operation_id:
            raise ValueError('Invalid tool or operation identity')
        if self.calls >= self.manifest.max_steps or time.perf_counter()-self.started >= self.manifest.timeout_seconds:
            raise BudgetExceeded('Trial resource limit reached')
        self.calls += 1
        self.tool_counts[tool] = self.tool_counts.get(tool, 0)+1
        fault = self.manifest.fault
        inject = (not self.fault_occurred and fault.kind != 'none' and tool == fault.tool and self.tool_counts[tool] == fault.occurrence)
        event = {'step': self.calls, 'timestamp': datetime.now().isoformat(), 'tool': tool,
                 'operation_id': operation_id, 'fault_occurred': inject,
                 'state_before': self.snapshot(), 'agent_id': 'scripted-agent', 'sub_goal_id': tool}
        start = time.perf_counter()
        try:
            if inject:
                self.fault_occurred = True
            if inject and fault.kind == 'transient':
                raise SimulatedFault('Transient tool failure before effects')
            key = (tool, operation_id)
            if key in self.operations:
                result = self.operations[key]
            elif tool == 'read':
                result = {'source_digest': source_hash(self.source_path.read_text(encoding='utf-8'))}
            elif tool == 'apply_patch':
                self.source_path.write_text(self.task.solution, encoding='utf-8')
                self.check_digest = None
                result = {'applied': True}
            elif tool == 'run_checks':
                result = self._check_source()
                if result['passed'] == result['total']:
                    self.check_digest = source_hash(self.source_path.read_text(encoding='utf-8'))
            elif tool == 'commit':
                digest = source_hash(self.source_path.read_text(encoding='utf-8'))
                if digest != self.check_digest:
                    self.prohibited.append({'step': self.calls, 'type': 'commit_without_passing_checks'})
                    raise ValueError('Passing checks required before commit')
                self.commits.append({'operation_id': operation_id, 'digest': digest, 'step': self.calls})
                result = {'committed': True}
            else:
                if not self.commits:
                    self.prohibited.append({'step': self.calls, 'type': 'notify_before_commit'})
                    raise ValueError('Commit required before notification')
                self.notifications.append({'operation_id': operation_id, 'step': self.calls})
                result = {'notified': True}
            if tool in {'commit', 'notify'}:
                self.operations[key] = result
            if inject and fault.kind == 'timeout_after_commit':
                raise SimulatedFault('Response timed out after committed effect')
            event['result'] = result
            return result
        except Exception as exc:
            event['error'] = type(exc).__name__
            raise
        finally:
            event['duration_seconds'] = time.perf_counter()-start
            event['state_after'] = self.snapshot()
            self.events.append(event)

    def snapshot(self):
        return {'source_digest': source_hash(self.source_path.read_text(encoding='utf-8')),
                'commits': copy.deepcopy(self.commits), 'notifications': copy.deepcopy(self.notifications),
                'prohibited_effects': copy.deepcopy(self.prohibited)}

    def verify(self):
        checks = self._check_source()
        digest = source_hash(self.source_path.read_text(encoding='utf-8'))
        criteria = {
            'behavior': checks['passed'] == checks['total'],
            'single_current_commit': len(self.commits) == 1 and self.commits[0]['digest'] == digest,
            'single_ordered_notification': len(self.notifications) == 1 and bool(self.commits) and self.notifications[0]['step'] > self.commits[-1]['step'],
            'no_prohibited_effects': not self.prohibited,
        }
        return {'verified_success': all(criteria.values()), 'criteria': criteria,
                'tests_passed': checks['passed'], 'tests_total': checks['total'],
                'duplicate_effects': max(0,len(self.commits)-1)+max(0,len(self.notifications)-1),
                'final_state': self.snapshot(), 'verifier_version': 'protected-checks-v1'}


class BenchmarkService:
    def capabilities(self):
        return {'tasks': public_tasks(), 'conditions': ['baseline', 'generic_retry', 'idempotent_retry'],
                'execution_mode': 'trusted_simulation',
                'unavailable': {name: 'Upstream team module is not implemented' for name in
                    ['live_enhanced_agent', 'live_prediction', 'live_diagnosis', 'live_memory', 'live_drift_tracking']},
                'study_api': '/api/benchmarks/studies',
                'study_features': ['seven_scenarios','scripted_ablations','labeled_event_ingestion','human_effort_metrics','capability_history','checkpoint_resume','bounded_ollama_pilot'],
                'limitations': 'Fixed scripted patches validate the harness, not LLM coding ability. Step and wall-time budgets are implemented; token and compute costs are unavailable.'}

    def run(self, manifest: ExperimentManifest, experiment_id=None):
        if not _lock.acquire(blocking=False):
            raise ValueError('An experiment is already executing in this process')
        try:
            with experiment_lock(db_service.db_path):
                return self._run(manifest, experiment_id)
        finally:
            _lock.release()

    def _run(self, manifest, experiment_id):
        existing = None
        if experiment_id:
            existing = next((e for e in db_service.get_experiments() if e['experiment_id'] == experiment_id), None)
            if not existing or existing['manifest'] != manifest.model_dump():
                raise ValueError('Resume requires an existing identical manifest')
            if existing.get('active_trial'):
                raise ValueError('Interrupted active trial requires review; start a new experiment rather than overwrite its evidence')
            if existing.get('status') == 'running':
                raise ValueError('Experiment is running or was interrupted; inspect its evidence before restarting')
        else:
            experiment_id = f'exp_{uuid.uuid4().hex}'
        report = existing or {'experiment_id': experiment_id, 'manifest': manifest.model_dump(),
            'created_at': datetime.now().isoformat(), 'trials': [], 'status': 'running',
            'limitations': self.capabilities()['limitations']}
        root = Path(db_service.db_path).resolve().parent / 'benchmark_workspaces' / experiment_id
        completed = {r['trial_key'] for r in report['trials']}
        report['status'] = 'running'
        for task_id in manifest.task_ids:
            for length in manifest.task_lengths:
                for repetition in range(manifest.repetitions):
                    seed = manifest.seed + repetition
                    for condition in manifest.conditions:
                        key = f'{task_id}:{length}:{repetition}:{condition}'
                        if key in completed:
                            continue
                        run_id = f'bench_{uuid.uuid5(uuid.NAMESPACE_URL, experiment_id+key).hex}'
                        report['active_trial'] = run_id
                        db_service.save_experiment(experiment_id, manifest.model_dump(), report)
                        try:
                            row = self._trial(manifest, task_id, length, seed, condition, run_id, root/run_id)
                        except Exception as exc:
                            report['status'] = 'interrupted'
                            report['error'] = type(exc).__name__
                            record = db_service.get_run_record(run_id)
                            if record:
                                db_service.finalize_run(EvaluationMetrics(run_id=run_id, task_id=task_id,
                                    metric_version='2', outcome='error', verified_success=False,
                                    execution_mode='trusted_simulation', termination_reason=f'runner:{type(exc).__name__}'))
                            db_service.save_experiment(experiment_id, manifest.model_dump(), report)
                            raise
                        row['trial_key'] = key
                        report['trials'].append(row)
                        report['active_trial'] = None
                        db_service.save_experiment(experiment_id, manifest.model_dump(), report)
        report['comparisons'] = summarize(report['trials'])
        report['status'] = 'completed'
        db_service.save_experiment(experiment_id, manifest.model_dump(), report)
        return report

    def _trial(self, manifest, task_id, length, seed, condition, run_id, workspace):
        started = time.perf_counter()
        db_service.create_or_update_run(run_id, task_id, TASKS[task_id].title, TASKS[task_id].title, str(workspace),
            current_stage='benchmark', status='in_progress', metadata={'manifest':manifest.model_dump(), 'condition':condition, 'seed':seed, 'task_length':length, 'execution_mode':'trusted_simulation'})
        env = SoftwareEnvironment(task_id, workspace, manifest)
        initial = env.snapshot()
        episodes, termination = [], 'completed'
        actions = ['read']*(length-4)+['apply_patch','run_checks','commit','notify']
        rng = random.Random(seed)
        try:
            for index, tool in enumerate(actions):
                operation_id = f'{index}-{rng.getrandbits(64):016x}'
                retries = 0
                episode = None
                while True:
                    try:
                        env.call(tool, operation_id)
                        if episode:
                            episode['local_action_succeeded'] = True
                        break
                    except SimulatedFault:
                        if episode is None:
                            episode = {'episode_id':uuid.uuid4().hex, 'failure_step':env.calls,
                                'detection_seconds':time.perf_counter()-started, 'strategy':condition,
                                'attempts':0, 'extra_tool_calls':0, 'verified_recovered':False,
                                'local_action_succeeded':False}
                            episodes.append(episode)
                        if condition == 'baseline' or retries >= manifest.max_retries:
                            raise
                        retries += 1
                        episode['attempts'] = retries
                        episode['extra_tool_calls'] += 1
                        if condition == 'generic_retry':
                            operation_id = f'{operation_id}-retry-{retries}'
        except BudgetExceeded:
            termination = 'budget_exceeded'
        except SimulatedFault:
            termination = 'fault_unrecovered'
        except Exception as exc:
            termination = f'error:{type(exc).__name__}'
        verification = env.verify()
        if time.perf_counter()-env.started >= manifest.timeout_seconds:
            termination = 'budget_exceeded'
        if termination != 'completed':
            verification['verified_success'] = False
        elapsed = time.perf_counter()-started
        agent_tool_seconds = sum(e['duration_seconds'] for e in env.events)
        for episode in episodes:
            episode['verified_recovered'] = verification['verified_success'] and episode['local_action_succeeded']
            episode['duration_seconds'] = elapsed-episode['detection_seconds']
            episode['post_recovery_violations'] = [k for k,v in verification['criteria'].items() if not v]
        row = {'run_id':run_id, 'task_id':task_id, 'condition':condition, 'seed':seed,
            'task_length':length, 'fault':manifest.fault.model_dump(), 'fault_occurred':env.fault_occurred,
            'fault_not_triggered_reason':None if env.fault_occurred or manifest.fault.kind=='none' else 'Scheduled occurrence not reached',
            'initial_state':initial, 'verified_success':verification['verified_success'],
            'termination_reason':termination, 'duration_seconds':elapsed, 'tool_calls':env.calls,
            'tool_execution_seconds':agent_tool_seconds,
            'harness_overhead_seconds':max(0, elapsed-agent_tool_seconds),
            'tokens':None, 'compute_cost':None, 'recovery_episodes':episodes, 'verification':verification,
            'events':[dict(e, run_id=run_id, task_id=task_id) for e in env.events]}
        for event in row['events']:
            db_service.add_log(run_id, 'benchmark', 'Scripted Agent', 'tool_call', event['tool'], event)
        coverage = 100*sum(verification['criteria'].values())/len(verification['criteria'])
        db_service.finalize_run(EvaluationMetrics(run_id=run_id, task_id=task_id, metric_version='2',
            verified_success=row['verified_success'], outcome='budget_exceeded' if termination == 'budget_exceeded' else 'success' if row['verified_success'] else 'failed',
            success_rate=coverage, termination_reason=termination, execution_mode='trusted_simulation',
            execution_time_seconds=elapsed, total_tool_calls=env.calls, total_model_calls=0,
            measurement_scope='Simulator duration includes run/workspace initialization, scripted actions, and final verification; excludes final trace/report persistence',
            recovery_attempts_count=sum(e['attempts'] for e in episodes),
            tests_passed=verification['tests_passed'], tests_total=verification['tests_total']))
        return row


benchmark_service = BenchmarkService()
