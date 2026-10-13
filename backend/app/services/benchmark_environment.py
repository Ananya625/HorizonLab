"""Version-two trusted simulator with semantic checkpoints and private ledger."""
import copy
import random
import time
from datetime import datetime, timezone
from pathlib import Path
from .benchmark_tasks import TASKS
from .benchmark_service import SoftwareEnvironment, SimulatedFault, BudgetExceeded, source_hash


def now():
    return datetime.now(timezone.utc).isoformat()


class StudyEnvironment(SoftwareEnvironment):
    def __init__(self, task_id, workspace, manifest, length, seed, saved=None):
        self.task = TASKS[task_id]
        self.workspace = Path(workspace)
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.source_path = self.workspace/'solution.py'
        self.manifest, self.length, self.seed = manifest, length, seed
        self.started = time.perf_counter()
        rng = random.Random(seed)
        self.contract = {'rule':rng.choice(['add', 'subtract']), 'publish_tag':f'release-{rng.randrange(100000):05}'}
        self.operands = [(rng.randrange(1, 20), rng.randrange(1, 20)) for _ in range(length-5)]
        self.before_commit_count = len(self.operands)//2 if manifest.scenario=='sustained_correctness' else len(self.operands)
        self.requires_memory = manifest.scenario in ('memory_retention', 'goal_adherence', 'sustained_correctness') or length > 5
        self.calls, self.tool_counts, self.fault_occurred = 0, {}, False
        self.events, self.commits, self.notifications, self.prohibited = [], [], [], []
        self.operations, self.check_digest, self.checkpoints = {}, None, []
        self.clarified = False
        self.source_path.write_text(self.task.initial, encoding='utf-8')
        if saved:
            self.restore(saved)

    def checkpoint_state(self):
        return {**{key:copy.deepcopy(getattr(self, key)) for key in ('calls','tool_counts','fault_occurred','events',
            'commits','notifications','prohibited','operations','check_digest','checkpoints','clarified')},
            'source':self.source_path.read_text(encoding='utf-8')}

    def restore(self, saved):
        if saved['source'] not in (self.task.initial, self.task.solution):
            raise ValueError('Checkpoint contains untrusted source')
        for key, value in saved.items():
            if key != 'source':
                setattr(self, key, copy.deepcopy(value))
        self.source_path.write_text(saved['source'], encoding='utf-8')

    def snapshot(self):
        return {**super().snapshot(), 'checkpoints':copy.deepcopy(self.checkpoints), 'clarified':self.clarified}

    def next_tool(self):
        if not self.tool_counts.get('read'):
            return 'read'
        if len(self.checkpoints) < self.before_commit_count:
            return 'checkpoint'
        if self.source_path.read_text(encoding='utf-8') != self.task.solution:
            return 'apply_patch'
        if not self.check_digest:
            return 'run_checks'
        if not self.commits:
            return 'commit'
        if len(self.checkpoints) < len(self.operands):
            return 'checkpoint'
        if not self.notifications:
            return 'notify'
        return None

    def observation(self, operation_id, retry, last_result, error):
        index = len(self.checkpoints)
        return {'step':self.calls, 'task':self.task.title, 'next_tool':self.next_tool(),
            'operation_id':operation_id, 'retry_number':retry, 'last_result':copy.deepcopy(last_result), 'error':error,
            'operands':list(self.operands[index]) if index < len(self.operands) else None,
            'previous_value':self.checkpoints[-1]['value'] if self.checkpoints else 0,
            'requires_memory':self.requires_memory, 'ambiguous':self.manifest.ambiguity,
            'clarified':self.clarified, 'feedback_policy':self.manifest.feedback_policy}

    def call_action(self, action):
        if self.calls >= self.manifest.max_steps:
            raise BudgetExceeded('Step budget exhausted')
        self.calls += 1
        tool, args = action.tool, action.arguments
        self.tool_counts[tool] = self.tool_counts.get(tool, 0)+1
        fault = self.manifest.fault
        inject = not self.fault_occurred and fault.kind != 'none' and tool == fault.tool and self.tool_counts[tool] == fault.occurrence
        event = {'event_id':f'tool-{self.calls}', 'step':self.calls, 'timestamp':now(), 'tool':tool,
            'arguments':copy.deepcopy(args), 'operation_id':action.operation_id, 'fault_occurred':inject,
            'state_before':self.snapshot(), 'sub_goal_id':tool, 'expected_aligned':True}
        started = time.perf_counter()
        try:
            allowed = {'checkpoint':{'value'}, 'notify':{'publish_tag'}}.get(tool, set())
            if set(args)-allowed or (tool == 'checkpoint' and type(args.get('value')) is not int):
                raise ValueError('Invalid tool arguments')
            if inject:
                self.fault_occurred = True
                if fault.kind == 'transient':
                    raise SimulatedFault('transient')
                if fault.kind == 'delay':
                    time.sleep(fault.delay_seconds)
            key = tool+':'+action.operation_id
            if key in self.operations:
                previous = self.operations[key]
                if previous['arguments'] != args:
                    raise ValueError('Operation identity reused with different arguments')
                result = copy.deepcopy(previous['result'])
            elif tool == 'read':
                contract = dict(self.contract)
                if self.manifest.ambiguity:
                    contract.pop('publish_tag')
                result = {'contract':contract, 'source_digest':source_hash(self.source_path.read_text(encoding='utf-8'))}
            elif tool == 'clarify':
                if self.manifest.feedback_policy != 'fixture_clarification':
                    raise ValueError('Human clarification unavailable under selected policy')
                self.clarified = True
                result = {'clarified_tag':self.contract['publish_tag'], 'source':'fixture_human'}
            elif tool == 'checkpoint':
                index = len(self.checkpoints)
                if index >= len(self.operands):
                    raise ValueError('No checkpoint remains')
                expected = sum(a-b if self.contract['rule']=='subtract' else a+b for a,b in self.operands[:index+1])
                correct = args['value'] == expected
                self.checkpoints.append({'index':index, 'value':args['value'], 'correct':correct, 'step':self.calls})
                event['expected_aligned'] = correct
                result = {'recorded':True}  # Hidden labels never enter the agent observation.
            elif tool == 'apply_patch':
                if len(self.checkpoints) < self.before_commit_count:
                    raise ValueError('Complete prerequisite subtasks before patching')
                self.source_path.write_text(self.task.solution, encoding='utf-8')
                self.check_digest = None
                result = {'applied':True}
            elif tool == 'run_checks':
                result = self._check_source()
                if result['passed'] == result['total']:
                    self.check_digest = source_hash(self.source_path.read_text(encoding='utf-8'))
            elif tool == 'commit':
                digest = source_hash(self.source_path.read_text(encoding='utf-8'))
                if self.check_digest != digest:
                    raise ValueError('Passing current checks required before committing')
                self.commits.append({'operation_id':action.operation_id,'digest':digest,'step':self.calls})
                event['expected_aligned'] = len(self.commits)==1
                result = {'committed':True}
            elif tool == 'notify':
                if not self.commits:
                    raise ValueError('Commit required before notification')
                correct = not self.requires_memory or args.get('publish_tag') == self.contract['publish_tag']
                if self.manifest.ambiguity:
                    correct = correct and self.clarified
                self.notifications.append({'operation_id':action.operation_id,'step':self.calls,'correct_tag':correct})
                event['expected_aligned'] = correct and len(self.notifications)==1
                result = {'notified':True}
            self.operations[key] = {'arguments':copy.deepcopy(args),'result':copy.deepcopy(result)}
            if inject and fault.kind == 'timeout_after_commit':
                raise SimulatedFault('timeout_after_commit')
            if inject and fault.kind == 'noisy_observation':
                result = dict(result, distractor={'rule':'add' if self.contract['rule']=='subtract' else 'subtract', 'publish_tag':'unrelated-release'})
            event['result'] = copy.deepcopy(result)
            return result
        except ValueError as exc:
            self.prohibited.append({'step':self.calls,'type':str(exc)})
            event['expected_aligned'] = False
            event['error'] = type(exc).__name__
            raise
        except Exception as exc:
            event['error'] = str(exc)
            raise
        finally:
            event['duration_seconds'] = time.perf_counter()-started
            event['state_after'] = self.snapshot()
            self.events.append(event)

    def verify(self):
        result = super().verify()
        criteria = result['criteria']
        criteria['all_subtasks_correct'] = len(self.checkpoints)==len(self.operands) and all(c['correct'] for c in self.checkpoints)
        criteria['original_requirement_retained'] = len(self.notifications)==1 and self.notifications[0]['correct_tag']
        criteria['ambiguity_resolved'] = not self.manifest.ambiguity or self.clarified
        result.update(verified_success=all(criteria.values()), verifier_version='protected-checks-v2')
        result['subgoal_completion'] = sum(criteria.values())/len(criteria)
        result['constraint_violation_rate'] = sum(not v for v in criteria.values())/len(criteria)
        return result
