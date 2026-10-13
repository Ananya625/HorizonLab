"""Small fail-open instrumentation scopes. No model calls or policy decisions."""
import functools
import hashlib
import inspect
import json
import logging
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from ..models.workflow import WorkflowEvent
from . import workflow_store

logger = logging.getLogger(__name__)
_context = ContextVar('workflow_evidence_context', default={})


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str, ensure_ascii=False).encode()).hexdigest()


def goal_revision(goal):
    if not goal:
        return None
    data = goal.model_dump(exclude={'created_at', 'updated_at', 'audit_history', 'confirmed_at', 'is_confirmed', 'goal_model_version'})
    for item in data.get('sub_goals', []):
        item.pop('status', None)
    return digest(data)


def plan_revision(plan):
    return digest(plan.model_dump(exclude={'created_at'})) if plan else None


class WorkflowService:
    def emit(self, run_id, kind, **fields):
        from .db import db_service
        try:
            if 'task_id' not in fields:
                with db_service._get_connection() as conn:
                    row = conn.execute('SELECT task_id FROM runs WHERE run_id=?', (run_id,)).fetchone()
                if row:
                    fields['task_id'] = row['task_id']
            event = WorkflowEvent(run_id=run_id, kind=kind, **fields)
            workflow_store.append(db_service, event)
            return event
        except Exception:
            # Evidence outages never change action policy or conceal the action's own error.
            logger.exception('Workflow evidence could not be saved for %s', run_id)
            try:
                db_service.update_metadata(run_id, workflow_evidence_partial=True)
            except Exception:
                pass
            return None

    def snapshots(self, run_id):
        from .db import db_service
        goal, plan = db_service.get_goal_model(run_id), db_service.get_plan(run_id)
        gr, pr = goal_revision(goal), plan_revision(plan)
        for kind, revision, data in [
            ('goal_snapshot', gr, {
                'sub_goals': [{'id':s.id,'title':s.title[:160],'dependencies':s.dependencies} for s in goal.sub_goals],
                'criteria': [{'id':c.id,'sub_goal_id':c.sub_goal_id} for c in goal.success_criteria],
                'label':goal.goal_model_version} if goal else {}),
            ('plan_snapshot', pr, {'steps':[s.model_dump() for s in plan.steps],
                                  'files':[{'path':f.path,'sub_goal_id':f.sub_goal_id} for f in plan.planned_files]} if plan else {})]:
            if revision:
                event_id = kind+'_'+revision
                with db_service._get_connection() as conn:
                    exists = conn.execute('SELECT 1 FROM workflow_events WHERE run_id=? AND event_id=?', (run_id,event_id)).fetchone()
                if not exists:
                    if kind == 'plan_snapshot':
                        # Store identifiers/dependencies, never generated prose or source.
                        data['steps'] = [{k:v for k,v in s.items() if k in ('step_number','dependencies','sub_goal_ids','target_files')} for s in data['steps']]
                    self.emit(run_id, kind, event_id=event_id, goal_revision=gr, plan_revision=pr, data=data)
        return gr, pr

    def state(self, run_id):
        from .db import db_service
        from .workspace_service import workspace_service
        try:
            record = db_service.get_run_record(run_id)
            return workspace_service.digest(record.repo_path) if record else None
        except Exception:
            return None

    @contextmanager
    def action(self, run_id, operation, category='tool', target=None, arguments=None, reason=None):
        from .db import db_service
        parent = _context.get()
        run_id = run_id or parent.get('run_id')
        try:
            record_exists = run_id and db_service.get_run_record(run_id)
        except Exception:
            logger.exception('Workflow identity unavailable')
            record_exists = False
        if not record_exists:
            yield {}
            return
        try:
            gr, pr = self.snapshots(run_id)
        except Exception:
            logger.exception('Workflow snapshots unavailable')
            gr, pr = None, None
        if parent.get('run_id') != run_id:
            parent = {}
        identity = dict(task_id=record_exists.task_id, action_id=uuid.uuid4().hex, parent_action_id=parent.get('action_id'),
            attempt_id=parent.get('attempt_id'), recovery_id=parent.get('recovery_id'),
            sub_goal_id=parent.get('sub_goal_id'), goal_revision=gr, plan_revision=pr,
            operation=operation, category=category, target=str(target)[:300] if target else None,
            arguments_hash=digest(arguments) if arguments is not None else None,
            agent=parent.get('agent') or operation, reason=reason or parent.get('reason'))
        before = self.state(run_id)
        self.emit(run_id, 'action_start', before_state=before, **identity)
        token = _context.set({**parent, **identity, 'run_id':run_id})
        started = time.perf_counter()
        result = {'outcome':'success'}
        try:
            yield result
        except BaseException as exc:
            result.update(outcome='rejected' if isinstance(exc, ValueError) else 'error', data={'error_category':type(exc).__name__})
            raise
        finally:
            _context.reset(token)
            self.emit(run_id, 'action_result', **identity, before_state=before,
                      after_state=self.state(run_id), duration_seconds=time.perf_counter()-started, **result)

    @contextmanager
    def attempt(self, run_id, sub_goal_id=None, recovery_id=None, reason=None):
        from .db import db_service
        try:
            goal = db_service.get_goal_model(run_id)
        except Exception:
            goal = None
        if sub_goal_id and (not goal or sub_goal_id not in {s.id for s in goal.sub_goals}):
            sub_goal_id = None  # Invalid attribution remains unmapped, not guessed.
        parent = _context.get()
        if parent.get('run_id') != run_id:
            parent = {}
        fields = dict(attempt_id=uuid.uuid4().hex, sub_goal_id=sub_goal_id, recovery_id=recovery_id,
                      goal_revision=goal_revision(goal), reason=reason)
        self.emit(run_id, 'attempt_start', **fields)
        token = _context.set({**parent, **fields, 'run_id':run_id})
        outcome = 'unknown'  # Finishing an attempt is not proof that its sub-goal succeeded.
        try:
            yield
        except BaseException:
            outcome = 'error'
            raise
        finally:
            _context.reset(token)
            self.emit(run_id, 'attempt_end', outcome=outcome, **fields)

    def verification(self, run_id, report, checked_state=None):
        try:
            self._verification(run_id, report, checked_state)
        except Exception:
            logger.exception('Independent verification evidence could not be recorded')
            from .db import db_service
            try:
                db_service.update_metadata(run_id, workflow_evidence_partial=True)
            except Exception:
                pass

    def _verification(self, run_id, report, checked_state=None):
        from .db import db_service
        goal = db_service.get_goal_model(run_id)
        gr, pr = self.snapshots(run_id)
        state = checked_state if checked_state is not None else self.state(run_id)
        mapping = {c.id:c.sub_goal_id for c in goal.success_criteria} if goal else {}
        for c in report.criteria_evaluations:
            self.emit(run_id, 'verification', sub_goal_id=mapping.get(c.criterion_id),
                goal_revision=gr, plan_revision=pr, after_state=state,
                evidence_refs=[report.id, c.criterion_id],
                data={'scope':'criterion','criterion_id':c.criterion_id,
                      'verdict':c.verdict,'independent':True})
        self.emit(run_id, 'verification', goal_revision=gr, plan_revision=pr, after_state=state,
            evidence_refs=[report.id], data={'scope':'run','independent':True,
                'verdict':'PASS' if report.verified_success is True else 'FAIL' if report.verified_success is False else 'UNVERIFIED'})


workflow = WorkflowService()


def observed(operation, category='stage', reason=None):
    """Preserve public signatures; ContextVar links nested tool/model work safely."""
    def decorate(function):
        signature = inspect.signature(function)

        def prepare(args, kwargs):
            bound = signature.bind(*args, **kwargs)
            bound.apply_defaults()
            params = bound.arguments
            run_id = params.get('run_id') or params.get('existing_run_id') or _context.get().get('run_id')
            target = params.get('relative_file_path')
            if target:
                target = target.replace('\\','/')
            if operation == 'pytest':
                target = ' '.join(params.get('target_test_files') or [params.get('test_file_target') or 'tests'])
            # Exact tool-specific keys: no removal of semantically relevant values.
            keys = {'file_read':['relative_file_path'], 'file_write':['relative_file_path','content'],
                    'pytest':['test_file_target','target_test_files'],
                    'ollama.chat':['messages','model','temperature','num_ctx','num_predict','format_json'],
                    'inspect_targeted':['file_list'], 'inspect_directory':['target_path']}.get(operation, [])
            arguments = {key:params.get(key) for key in keys}
            if operation in ('file_read','file_write'):
                arguments['relative_file_path'] = target
            if operation == 'pytest':
                arguments = {'targets':[p.replace('\\','/') for p in (params.get('target_test_files') or [params.get('test_file_target') or 'tests'])]}
                target = ' '.join(arguments['targets'])
            return workflow.action(run_id, operation, category, target, arguments, reason)

        def finish(result, evidence):
            if not evidence:
                return
            if category == 'model' and isinstance(result, dict):
                def measured(key):
                    value = result.get(key)
                    return value if type(value) is int and value >= 0 else None
                evidence.update(input_tokens=measured('prompt_eval_count'), output_tokens=measured('eval_count'))
            elif operation == 'pytest':
                evidence.update(outcome='success' if result.status == 'PASSED' else 'error' if result.status == 'ERROR' else 'failed',
                    observation_hash=digest([(i.name,i.status,i.error_message) for i in result.test_items]),
                    evidence_refs=[result.id], data={'error_category':'execution_failure' if result.execution_error else None})
            elif category == 'tool':
                evidence['observation_hash'] = digest(result)

        if inspect.iscoroutinefunction(function):
            @functools.wraps(function)
            async def async_call(*args, **kwargs):
                with prepare(args, kwargs) as evidence:
                    result = await function(*args, **kwargs)
                    finish(result, evidence)
                    return result
            return async_call
        @functools.wraps(function)
        def sync_call(*args, **kwargs):
            with prepare(args, kwargs) as evidence:
                result = function(*args, **kwargs)
                finish(result, evidence)
                return result
        return sync_call
    return decorate
