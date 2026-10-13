import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models.workflow import WorkflowEvent
from app.models.schema import GoalModel, SubGoal, SuccessCriterion, PlannedFile, ImplementationPlan
from app.services import workflow_store
from app.services.workflow_service import workflow, goal_revision, observed
from app.services.workflow_analysis import analyze
from app.services.workflow_reports import workflow_report


class Trace:
    def __init__(self):
        self.events = []

    def emit(self, kind, **fields):
        n = len(self.events)+1
        event = WorkflowEvent(event_id=f'e{n}',run_id='r1',kind=kind,
            timestamp=(datetime(2026,1,1,tzinfo=timezone.utc)+timedelta(seconds=n)).isoformat(),**fields).model_dump()
        event['sequence'] = n
        self.events.append(event)
        return event

    def goal(self):
        self.emit('goal_snapshot',goal_revision='g1',data={
            'sub_goals':[{'id':'s1','title':'One','dependencies':[]},{'id':'s2','title':'Two','dependencies':['s1']}],
            'criteria':[{'id':'c1','sub_goal_id':'s1'},{'id':'c2','sub_goal_id':'s2'}]})

    def action(self, op='file_read', state='v1', after=None, observation='same', reason=None,
               sub=None, category='tool', outcome='success', **extra):
        identity = dict(action_id=f'a{len(self.events)}',category=category,operation=op,
            arguments_hash=op,goal_revision='g1',target=op,sub_goal_id=sub,reason=reason)
        for key in ('attempt_id','recovery_id','parent_action_id'):
            if key in extra:
                identity[key] = extra.pop(key)
        start = self.emit('action_start',before_state=state,**identity)
        result = self.emit('action_result',before_state=state,after_state=after or state,
            observation_hash=observation,outcome=outcome,duration_seconds=1,**identity,**extra)
        return start,result

    def verify(self, criterion='c1', sub='s1', verdict='PASS', state='v1', scope='criterion', independent=True):
        return self.emit('verification',goal_revision='g1',sub_goal_id=sub,after_state=state,
            evidence_refs=['protected-check'],data={'scope':scope,'criterion_id':criterion,'verdict':verdict,'independent':independent})

    def report(self):
        return analyze(self.events,'r1')


def kinds(report):
    return {f['kind'] for f in report['findings']}


def test_storage_idempotence_migration_and_interrupted_action(database, run):
    # Existing run schema remains usable; additive initialization is safe twice.
    database._init_db()
    event = WorkflowEvent(run_id='r1',kind='action_start',action_id='a',operation='file_read',category='tool')
    assert workflow_store.append(database,event)==1
    assert workflow_store.append(database,event)==1
    with pytest.raises(ValueError,match='rewritten'):
        workflow_store.append(database,event.model_copy(update={'target':'changed'}))
    report,_ = workflow_report(database,'r1')
    assert report['summary']['action_attempts']==1
    assert report['summary']['incomplete_actions']==1
    assert report['evidence_status']=='partial'
    assert database.get_run_record('r1').task_id=='t1'


def test_atomic_event_sequences_and_snapshot_pagination(database, run):
    def add(i):
        return workflow_store.append(database,WorkflowEvent(run_id='r1',event_id=str(i),kind='notice'))
    with ThreadPoolExecutor(max_workers=4) as pool:
        assert sorted(pool.map(add,range(12)))==list(range(1,13))
    page = workflow_store.read(database,'r1',0,5)
    add(13)
    following = workflow_store.read(database,'r1',page['next_after'],100,page['snapshot_sequence'])
    assert len(following['events'])==7 and following['snapshot_sequence']==12
    assert len(workflow_store.all_events(database,'r1'))==13


def test_reject_mismatched_action_result(database, run):
    start=WorkflowEvent(run_id='r1',kind='action_start',action_id='a',operation='file_read',category='tool',goal_revision='one')
    workflow_store.append(database,start)
    with pytest.raises(ValueError,match='identity mismatch'):
        workflow_store.append(database,WorkflowEvent(run_id='r1',kind='action_result',action_id='a',operation='file_read',category='tool',goal_revision='two',outcome='success'))


def test_legacy_analysis_unknown_and_scoped_api(database, run):
    client = TestClient(app)
    report = client.get('/api/evaluations/r1/workflow').json()
    assert report['summary']['action_attempts'] is None and report['evidence_status']=='unavailable'
    assert report['overhead']['recovery']['tool_calls'] is None
    assert client.get('/api/evaluations/missing/workflow').status_code==404
    assert client.get('/api/evaluations/r1/workflow/events?limit=201').status_code==422
    event=WorkflowEvent(run_id='r1',event_id='one',kind='notice')
    workflow_store.append(database,event)
    assert client.get('/api/evaluations/r1/workflow/events/one').json()['event_id']=='one'
    assert client.get('/api/evaluations/other/workflow/events/one').status_code==404
    export=client.get('/api/evaluations/r1/workflow/export').json()
    assert len(export['events'])==1
    assert client.get('/api/runs/r1/export').json()['run_id']=='r1'
    assert export==client.get('/api/evaluations/r1/workflow/export').json()


def test_counts_tokens_and_no_nested_duration_double_count():
    t=Trace()
    t.action('pipeline',category='stage')
    t.action()
    t.action('ollama.chat',category='model',input_tokens=10,output_tokens=0)
    t.action('ollama.chat',category='model',outcome='error')
    r=t.report()
    assert r['summary']['action_attempts']==1 and r['summary']['stages']==1 and r['summary']['model_calls']==2
    assert r['summary']['resources']['output_tokens'] is None
    assert r['summary']['resources']['known_output_tokens']==0
    assert r['summary']['resources']['known_input_tokens']==10
    assert r['summary']['resources']['duration_seconds']==3


@pytest.mark.parametrize('case, expected', [
    ('identical_reads',True),('alternation',True),('edit_between',False),('retry',False),
    ('polling',False),('new_observation',False),('missing_state',False),('validation',False),
])
def test_labeled_loop_replays(case,expected):
    t=Trace()
    if case=='alternation':
        for op in ['file_read','inspect_directory']*2:
            t.action(op)
    elif case=='edit_between':
        t.action('pytest',reason='validation');t.action('file_write',after='v2');t.action('pytest',state='v2',reason='validation')
    else:
        for i in range(3):
            t.action(state=None if case=='missing_state' else 'v1',
                     observation=str(i) if case=='new_observation' else 'same',
                     reason={'retry':'recovery','polling':'polling','validation':'validation'}.get(case))
    predicted='suspected_loop' in kinds(t.report())
    assert predicted is expected


def test_stale_is_not_regression_then_verified_regression():
    t=Trace();t.goal();t.verify();t.action('file_write',sub='s1',after='v2')
    r=t.report()
    assert r['sub_goals'][0]['status']=='stale'
    assert 'regression' not in kinds(r) and 'unexplained_rework' in kinds(r)
    t.verify(verdict='FAIL',state='v2')
    assert 'regression' in kinds(t.report()) and t.report()['sub_goals'][0]['regressions']==1


def test_failure_evidence_also_becomes_stale_after_changes():
    t=Trace();t.goal();t.verify(scope='run',verdict='FAIL',sub=None)
    assert t.report()['summary']['verified_outcome'] is False
    t.action('file_write',after='new-state')
    assert t.report()['summary']['verified_outcome'] is None


def test_untrusted_claims_and_goal_changes_never_complete():
    t=Trace();t.goal();t.verify(independent=False)
    t.emit('completion_claim',goal_revision='g1',data={'scope':'run'})
    assert 'premature_completion_claim' in kinds(t.report())
    assert t.report()['sub_goals'][0]['status']=='unverified'
    t.verify();t.emit('goal_snapshot',goal_revision='g2',data={'sub_goals':[{'id':'s1','title':'Changed','dependencies':[]}],'criteria':[{'id':'c1','sub_goal_id':'s1'}]})
    assert t.report()['sub_goals'][0]['status']=='unverified'


def test_post_completion_and_allowed_finalization():
    t=Trace();t.goal();t.verify(scope='run',sub=None)
    t.action('pytest',reason='validation')
    assert 'post_completion_work' not in kinds(t.report())
    t.action('file_write',after='v2')
    assert 'post_completion_work' in kinds(t.report())


def test_changed_requirements_reopen_work_without_false_regression():
    t=Trace();t.goal();t.verify()
    changed=t.events[0]['data']
    t.emit('goal_snapshot',goal_revision='g2',data=changed)
    start,result=t.action(sub='s1',reason=None)
    start['goal_revision']=result['goal_revision']='g2'
    assert 'justified_revisit' in kinds(t.report())
    assert 'regression' not in kinds(t.report()) and 'unexplained_rework' not in kinds(t.report())


def test_dependencies_and_valid_alternative_order():
    t=Trace();t.goal();t.action(sub='s2')
    assert 'dependency_unverified' in kinds(t.report())
    t=Trace();t.goal();t.verify();t.action(sub='s2')
    assert 'dependency_unverified' not in kinds(t.report())
    t=Trace();t.goal();t.action(sub='s1');t.action(sub=None)
    assert 'dependency_unverified' not in kinds(t.report())


def test_duplicate_effect_requires_distinct_committed_effects():
    t=Trace()
    for _ in range(2):
        t.action(intended_operation_id='operation',effect_id='same')
    assert 'duplicate_effect' not in kinds(t.report())
    t.action(intended_operation_id='operation',effect_id='different')
    assert 'duplicate_effect' in kinds(t.report())


def test_recovery_rework_union_and_recurrence():
    t=Trace();t.goal();t.verify()
    t.emit('attempt_start',attempt_id='attempt',recovery_id='recovery',sub_goal_id='s1',goal_revision='g1')
    t.action('file_write',sub='s1',attempt_id='attempt',recovery_id='recovery',after='v2')
    t.action('ollama.chat',category='model',sub='s1',attempt_id='attempt',recovery_id='recovery',input_tokens=4,output_tokens=7)
    t.emit('attempt_end',attempt_id='attempt',recovery_id='recovery',goal_revision='g1',outcome='success')
    t.verify(scope='run',state='v2',sub=None)
    t.verify(scope='run',state='v3',sub=None,verdict='FAIL')
    report=t.report()
    assert report['overhead']['union']['output_tokens']==7
    assert report['overhead']['union']['model_calls']==1
    assert report['recovery'][0]['verified_recovery'] and report['recovery'][0]['recurrence']


def make_goal(database):
    goal=GoalModel(run_id='r1',task_id='t1',original_request='Test',normalized_request='Test',
        main_goal='Test',summary='Test',is_confirmed=True,
        sub_goals=[SubGoal(id='sg',title='Syntax',description='Syntax')],
        success_criteria=[SuccessCriterion(id='syntax',sub_goal_id='sg',description='Syntax',
            metric='python_syntax',verification_method='ast_check',expected_output='app.py')])
    database.save_goal_model(goal)
    return goal


@pytest.mark.asyncio
async def test_real_instrumentation_and_independent_subgoal_progress(database, run):
    from app.services.workspace_service import workspace_service
    from app.services.verifier_service import verifier_service
    make_goal(database)
    with workflow.attempt('r1','sg'):
        with workflow.action('r1','coder','stage'):
            workspace_service.write_file(run.repo_path,'app.py','x = 1\n')
            assert workspace_service.read_file(run.repo_path,'app.py')=='x = 1\n'
    await verifier_service.verify_run('r1')
    report, events=workflow_report(database,'r1')
    assert report['summary']['action_attempts']==3  # write, read, independent verifier read
    assert report['summary']['model_calls']==0
    assert report['sub_goals'][0]['attempts']==1 and report['sub_goals'][0]['status']=='verified'
    assert report['summary']['verified_outcome'] is True
    serialized=json.dumps(events)
    assert 'x = 1' not in serialized
    with workflow.action('r1','coder','stage'):
        workspace_service.write_file(run.repo_path,'app.py','x = (\n')
    before,_=workflow_report(database,'r1')
    assert before['sub_goals'][0]['status']=='stale' and 'regression' not in kinds(before)
    await verifier_service.verify_run('r1')
    after,_=workflow_report(database,'r1')
    assert 'regression' in kinds(after)


def test_numeric_goal_version_collision_and_concurrent_edits(database, run):
    from app.services.goal_parser_service import goal_parser_service
    goal=make_goal(database)
    original=goal_revision(goal)
    edited=goal_parser_service.patch_goal_model('r1',{'main_goal':'Different'})
    assert goal_revision(edited)!=original
    stale=goal.model_copy(update={'main_goal':'Lost update'})
    with pytest.raises(ValueError,match='concurrently'):
        database.save_goal_model(stale,expected_version=goal.goal_model_version)
    assert database.get_goal_model('r1').main_goal=='Different'
    # Even a legacy direct save reusing a numeric version has a different identity.
    stale.goal_model_version=edited.goal_model_version
    assert goal_revision(stale)!=goal_revision(edited)


@pytest.mark.asyncio
async def test_plan_content_binding_rejects_reused_numeric_goal_version(database, run):
    from app.services.coder_service import coder_service
    goal=make_goal(database)
    database.save_plan(ImplementationPlan(run_id='r1',goal_model_version=goal.goal_model_version,
        architecture_overview='test',target_repo_path=run.repo_path,testing_strategy='pytest',risk_assessment='low'))
    assert database.get_plan('r1').goal_revision==goal_revision(goal)
    changed=goal.model_copy(update={'main_goal':'Different requirement with reused version'})
    database.save_goal_model(changed)
    with pytest.raises(ValueError,match='current confirmed goal content'):
        await coder_service.execute_plan('r1')


def test_observer_failure_does_not_change_action(database, run, monkeypatch):
    def fail(*args,**kwargs): raise OSError('disk unavailable')
    monkeypatch.setattr(workflow_store,'append',fail)
    @observed('file_read','tool')
    def read(run_id): return 'still works'
    assert read('r1')=='still works'
    assert database.get_run_record('r1').metadata['workflow_evidence_partial']


def test_event_validation_rejects_negative_usage_and_naive_time():
    with pytest.raises(ValueError):
        WorkflowEvent(run_id='r',kind='notice',output_tokens=-1)
    with pytest.raises(ValueError):
        WorkflowEvent(run_id='r',kind='notice',timestamp='2026-01-01T00:00:00')


def test_replay_is_deterministic_under_duplicate_delivery():
    t=Trace();t.goal();t.action();t.verify()
    assert analyze(t.events,'r1')==analyze(t.events+t.events,'r1')


@pytest.mark.asyncio
async def test_instrumented_model_usage_and_timeout_without_network(database, run, monkeypatch):
    from app.services.ollama_service import ollama_service
    import httpx
    class Client:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def post(self, *args, **kwargs):
            if kwargs['json']['messages'][0]['content']=='timeout':
                raise httpx.ReadTimeout('test fixture timeout')
            class Response:
                status_code=200
                def json(self): return {'prompt_eval_count':3,'eval_count':0,'message':{'content':'private response'}}
            return Response()
    monkeypatch.setattr(httpx,'AsyncClient',Client)
    await ollama_service.chat_completion([{'role':'user','content':'secret-token-123'}],run_id='r1')
    with pytest.raises(TimeoutError):
        await ollama_service.chat_completion([{'role':'user','content':'timeout'}],run_id='r1')
    report,events=workflow_report(database,'r1')
    assert report['summary']['model_calls']==2
    assert report['summary']['resources']['output_tokens'] is None
    assert report['summary']['resources']['known_input_tokens']==3
    assert report['summary']['resources']['known_output_tokens']==0
    assert 'secret-token-123' not in json.dumps(events) and 'private response' not in json.dumps(events)


def test_overlapping_operation_durations_use_union():
    t=Trace();a,r=t.action();a2,r2=t.action()
    r2['timestamp']=r['timestamp'];r2['duration_seconds']=1
    assert t.report()['summary']['resources']['duration_seconds']==1


def test_unchanged_reverification_does_not_reset_stagnation():
    t=Trace();t.goal();first=t.verify(scope='run',sub=None)
    t.action(reason='validation');t.verify(scope='run',sub=None)
    report=t.report()
    assert report['stagnation']['actions']==1
    assert report['stagnation']['seconds']==seconds_between(first,t.events[-1])


def seconds_between(first,last):
    return (datetime.fromisoformat(last['timestamp'])-datetime.fromisoformat(first['timestamp'])).total_seconds()


def test_labeled_detector_scorecard():
    """Small hand-labeled sanity set, not a real-world accuracy estimate."""
    cases=[]
    for label, ops, reason, expected in [
        ('unchanged reads',['file_read']*3,None,True),
        ('alternating unchanged',['file_read','inspect_directory']*2,None,True),
        ('recovery',['file_read']*3,'recovery',False),
        ('polling',['file_read']*3,'polling',False),
        ('validation',['pytest']*3,'validation',False),
    ]:
        t=Trace()
        for op in ops: t.action(op,reason=reason)
        cases.append((label,'suspected_loop',t,expected))
    t=Trace();t.goal();t.verify();t.action('file_write',after='v2')
    cases.append(('stale criterion','regression',t,False))
    t=Trace();t.goal();t.verify();t.action('file_write',after='v2');t.verify(verdict='FAIL',state='v2')
    cases.append(('changed protected check fails','regression',t,True))
    for reason, expected in [('validation',False),(None,True)]:
        t=Trace();t.verify(scope='run',sub=None);t.action('file_write',reason=reason)
        cases.append(('post completion '+str(reason),'post_completion_work',t,expected))
    for effect,expected in [('same',False),('different',True)]:
        t=Trace();t.action(intended_operation_id='op',effect_id='same');t.action(intended_operation_id='op',effect_id=effect)
        cases.append(('committed effect '+effect,'duplicate_effect',t,expected))
    matrix={'true_positive':0,'true_negative':0,'false_positive':0,'false_negative':0}
    for label, detector, trace, expected in cases:
        predicted=detector in kinds(trace.report())
        matrix[('true_' if predicted==expected else 'false_')+('positive' if predicted else 'negative')]+=1
        assert predicted==expected,label
    print('Labeled evaluator scorecard:',json.dumps(matrix,sort_keys=True))
    assert matrix=={'true_positive':5,'true_negative':6,'false_positive':0,'false_negative':0}
