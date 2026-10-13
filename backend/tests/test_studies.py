import json
import subprocess
import sys
import pytest
from pydantic import ValidationError
from app.models.benchmark_study import StudyManifest, BenchmarkAction
from app.services.benchmark_study_service import study_service
from app.services.benchmark_budget import PilotBudget
from app.services.benchmark_adapters import OllamaAdapter, ScriptedAdapter
from app.services.benchmark_lock import experiment_lock


@pytest.fixture(autouse=True)
def offline_model_metadata(monkeypatch):
    monkeypatch.setattr(OllamaAdapter,'describe',lambda self: {'model':'qwen3:8b','digest':'mock-only'})


def small(**updates):
    values = dict(task_ids=['sum_fix'], task_lengths=[5], conditions=['baseline'], repetitions=1)
    values.update(updates)
    return StudyManifest(**values)


def model_manifest(**updates):
    values = dict(execution_mode='local_ollama',adapter_id='ollama-v1',adapter_version='1',
        model='qwen3:8b',pilot_id='test-pilot',max_retries=0)
    values.update(updates)
    return small(**values)


@pytest.mark.parametrize('updates', [dict(repetitions=4),dict(max_model_calls=16),dict(max_total_generated_tokens=6001),
    dict(max_output_tokens=1001),dict(max_retries=1),dict(model='another-model')])
def test_pilot_limits_rejected(updates):
    with pytest.raises(ValidationError):
        model_manifest(**updates)


def test_generated_budget_not_input_tokens(database):
    budget = PilotBudget(database,model_manifest(max_total_generated_tokens=1200))
    budget.start_trial('one')
    first = budget.reserve('one')
    assert first['reserved_tokens']==1000
    budget.finish(first['id'],{'input_tokens':9000,'output_tokens':950})
    second = budget.reserve('one')
    assert second['reserved_tokens']==250
    budget.finish(second['id'],{'input_tokens':9000,'output_tokens':250})
    with pytest.raises(ValueError):
        budget.reserve('one')


def test_smaller_model_continuation_keeps_remaining_limits(database):
    from pathlib import Path
    manifest_path = Path(__file__).resolve().parents[1] / 'benchmarks' / 'qwen3_1_7b_remaining_pilot.json'
    manifest = StudyManifest.model_validate_json(manifest_path.read_text(encoding='utf-8'))
    assert manifest.model == 'qwen3:1.7b'
    assert (manifest.max_trials, manifest.max_model_calls, manifest.max_total_generated_tokens) == (1, 13, 4000)
    assert manifest.max_output_tokens == 1000 and manifest.max_retries == 0
    budget = PilotBudget(database, manifest)
    budget.start_trial('remaining')
    with pytest.raises(ValueError):
        budget.start_trial('extra')
    for _ in range(4):
        call = budget.reserve('remaining')
        budget.finish(call['id'], {'input_tokens': 200, 'output_tokens': 1000})
    with pytest.raises(ValueError):
        budget.reserve('remaining')
    changed = manifest.model_copy(update={'max_total_generated_tokens': 6000})
    with pytest.raises(ValueError, match='cannot be reset'):
        PilotBudget(database, changed).snapshot()


def test_failure_halts_without_refunding_or_retry(database):
    m = model_manifest()
    budget = PilotBudget(database,m)
    budget.start_trial('r')
    call = budget.reserve('r')
    budget.finish(call['id'],error='timeout')
    restarted = PilotBudget(database,m)
    assert restarted.snapshot()['calls'][0]['reserved_tokens']==1000
    assert restarted.snapshot()['calls'][0]['status']=='unknown'
    with pytest.raises(ValueError):
        restarted.reserve('r')
    with pytest.raises(ValueError):
        restarted.start_trial('another')


def test_call_and_trial_limits_are_pilot_wide(database):
    budget = PilotBudget(database,model_manifest())
    for r in ('r1','r2','r3'):
        budget.start_trial(r)
        for i in range(5):
            call = budget.reserve(r)
            budget.finish(call['id'],{'input_tokens':1,'output_tokens':1})
    with pytest.raises(ValueError):
        budget.reserve('r3')
    with pytest.raises(ValueError):
        budget.start_trial('r4')
    assert len(budget.snapshot()['calls'])==15


@pytest.mark.parametrize('scenario', ['normal','goal_adherence','memory_retention','tool_recovery','sustained_correctness','task_length','efficiency'])
def test_all_seven_studies(database,scenario):
    report = study_service.run(small(scenario=scenario,task_lengths=[8]))
    row = report['trials'][0]
    assert row['verified_success'] and row['tool_calls']==8
    assert len(row['verification']['final_state']['checkpoints'])==3
    assert len(database.get_execution_logs(row['run_id']))==8
    assert report['analytics']['capability_history'][0]['dimensions']['robustness']['ewma'] is None


@pytest.mark.parametrize('fault,expected', [('transient',[False,True,True]),('timeout_after_commit',[False,False,True])])
def test_fault_recovery_verifies_state(database,fault,expected):
    report = study_service.run(small(conditions=['baseline','generic_retry','idempotent_retry'],fault={'kind':fault}))
    assert [r['verified_success'] for r in report['trials']]==expected


def test_memory_ablations_are_actual_fixture_behaviors(database):
    report = study_service.run(small(scenario='memory_retention',task_lengths=[8],
        conditions=['memory_none','memory_full_history','memory_goal_aware']))
    assert [r['verified_success'] for r in report['trials']]==[False,True,True]
    assert report['analytics']['runs'][report['trials'][0]['run_id']]['memory']['correct_use_rate']<1
    assert report['analytics']['paired_comparisons'][0]['matched_pairs']==1


def test_noisy_observation_and_ambiguity(database):
    noisy = study_service.run(small(task_lengths=[8],scenario='memory_retention',
        conditions=['memory_semantic','memory_goal_aware'],fault={'kind':'noisy_observation','tool':'read'}))
    assert [r['verified_success'] for r in noisy['trials']]==[False,True]
    ambiguous = study_service.run(small(ambiguity=True,feedback_policy='fixture_clarification'))
    assert ambiguous['trials'][0]['verified_success']
    effort = ambiguous['analytics']['runs'][ambiguous['trials'][0]['run_id']]['human']
    assert effort['simulated_events']==1 and effort['seconds'] is None


def test_resume_after_durable_commit_keeps_identity(database,monkeypatch):
    manifest = small(conditions=['idempotent_retry'],fault={'kind':'timeout_after_commit'})
    original = database.save_benchmark_checkpoint
    fired = []
    def interrupted(run_id,state,events=()):
        original(run_id,state,events)
        if state and state.get('environment',{}).get('commits') and not fired:
            fired.append(True)
            raise RuntimeError('Worker disappeared after durable checkpoint')
    monkeypatch.setattr(database,'save_benchmark_checkpoint',interrupted)
    with pytest.raises(RuntimeError):
        study_service.run(manifest)
    interrupted_report = database.get_experiments()[0]
    run_id = interrupted_report['active_trial']
    resumed = study_service.run(manifest,interrupted_report['experiment_id'])
    row = resumed['trials'][0]
    assert row['run_id']==run_id and row['verified_success']
    assert row['verification']['duplicate_effects']==0
    assert not row['timing_complete']
    assert resumed['comparisons'][0]['mean_duration_seconds'] is None
    assert study_service.run(manifest,resumed['experiment_id'])==resumed


def test_private_evaluator_state_never_sent_to_adapter(database,monkeypatch):
    original = ScriptedAdapter.act
    def inspect(self,observation,state,condition):
        assert not {'cases','solution','verification','expected_aligned','fault','state_before','state_after'} & observation.keys()
        assert 'correct' not in (observation.get('last_result') or {})
        return original(self,observation,state,condition)
    monkeypatch.setattr(ScriptedAdapter,'act',inspect)
    assert study_service.run(small(task_lengths=[8]))['trials'][0]['verified_success']


def test_fake_model_three_trials_fifteen_calls(database,monkeypatch):
    calls = []
    def complete(self,messages,condition,state,timeout,output_limit):
        observation = json.loads(messages[-1]['content'])
        calls.append(output_limit)
        action = BenchmarkAction(tool=observation['next_tool'],operation_id=observation['operation_id'])
        return action.model_dump_json(),{},dict(input_tokens=100,output_tokens=30)
    monkeypatch.setattr(OllamaAdapter,'complete',complete)
    report = study_service.run(model_manifest(task_ids=['sum_fix','empty_average','stable_unique']))
    assert len(report['trials'])==3 and all(r['verified_success'] for r in report['trials'])
    assert len(calls)==15 and all(n<=1000 for n in calls)
    assert sum(c['generated_tokens'] for c in report['model_budget']['calls'])==450


def test_model_error_stops_all_remaining_trials(database,monkeypatch):
    calls = []
    def fail(*args,**kwargs):
        calls.append(1)
        raise RuntimeError('memory unavailable')
    monkeypatch.setattr(OllamaAdapter,'complete',fail)
    report = study_service.run(model_manifest(task_ids=['sum_fix','empty_average','stable_unique']))
    assert report['status']=='halted' and len(report['trials'])==1 and len(calls)==1
    assert report['trials'][0]['termination_reason']=='model_error'
    assert not report['trials'][0]['token_usage_complete']


def test_cross_process_lock(database):
    code = 'from app.services.benchmark_lock import experiment_lock\nimport sys\ntry:\n with experiment_lock(sys.argv[1]): pass\nexcept ValueError:\n sys.exit(23)\n'
    with experiment_lock(database.db_path):
        process = subprocess.run([sys.executable,'-c',code,database.db_path],capture_output=True,timeout=15)
        assert process.returncode==23, process.stderr


def test_evidence_import_metrics_and_immutable_outcome(database):
    from fastapi.testclient import TestClient
    from app.main import app
    report = study_service.run(small())
    row = report['trials'][0]
    event = dict(event_id='human-label-1',run_id=row['run_id'],task_id=row['task_id'],step=1,
        timestamp=row['finished_at'],source='human',kind='human',version='1',
        data={'seconds':12,'workload':20,'simulated':False})
    url = '/api/benchmarks/experiments/'+report['experiment_id']+'/evidence'
    client = TestClient(app)
    response = client.post(url,json={'events':[event]})
    assert response.status_code==200, response.text
    updated = response.json()
    assert updated['analytics']['runs'][row['run_id']]['human']['seconds']==12
    assert updated['trials'][0]['verified_success']==row['verified_success']
    assert client.post(url,json={'events':[event]}).status_code==200
    event['data']['seconds']=15
    assert client.post(url,json={'events':[event]}).status_code==400


def test_provider_request_enforces_output_limit_and_thinking_mode(monkeypatch):
    requests = []
    class Client:
        def __init__(self,**kwargs):
            assert kwargs['trust_env'] is False
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def post(self,url,json):
            requests.append((url,json))
            return self
        def raise_for_status(self): pass
        def json(self):
            return {'done':True,'message':{'content':'{"tool":"read","operation_id":"x","arguments":{}}'},
                'prompt_eval_count':500,'eval_count':20}
    monkeypatch.setattr('app.services.benchmark_adapters.httpx.Client',Client)
    adapter = OllamaAdapter(model_manifest())
    _,_,usage = adapter.complete([{'role':'user','content':'test'}],'baseline',{},10,250)
    assert requests[0][1]['options']['num_predict']==250
    assert requests[0][1]['think'] is False and requests[0][1]['stream'] is False
    assert usage['output_tokens']==20 and usage['input_tokens']==500


def test_batch_evidence_rolls_back_if_report_write_fails(database,monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    report = study_service.run(small())
    row = report['trials'][0]
    event = dict(event_id='new-human-event',run_id=row['run_id'],task_id=row['task_id'],step=1,
        timestamp=row['finished_at'],source='human',kind='human',version='1',
        data={'seconds':12,'workload':20,'simulated':False})
    def fail(*args,**kwargs):
        raise RuntimeError('database write failed')
    monkeypatch.setattr(database,'save_experiment',fail)
    with pytest.raises(RuntimeError):
        TestClient(app).post('/api/benchmarks/experiments/'+report['experiment_id']+'/evidence',json={'events':[event]})
    assert not any(e['event_id']=='new-human-event' for e in database.get_benchmark_events(row['run_id']))


def test_prediction_and_drift_labeled_ingestion(database):
    from fastapi.testclient import TestClient
    from app.main import app
    report = study_service.run(small())
    row = report['trials'][0]
    common = dict(run_id=row['run_id'],task_id=row['task_id'],step=2,timestamp=row['finished_at'],version='1')
    events = [dict(common,event_id='risk',source='team_module',kind='prediction',
        data={'probability':.9,'threshold':.5,'feature_end_step':2,'model_version':'team-test'}),
        dict(common,event_id='drift-label',source='human',kind='drift',data={'actual_drift':False,'predicted_drift':True,
            'drift_type':'goal','severity':'low','onset_step':1,'resolved_step':None})]
    client = TestClient(app)
    url = '/api/benchmarks/experiments/'+report['experiment_id']+'/evidence'
    response = client.post(url,json={'events':events})
    assert response.status_code==200,response.text
    analytics = response.json()['analytics']['runs'][row['run_id']]
    assert analytics['prediction']['fp']==1 and analytics['goal_tracker']['fp']==1
    events[0]['event_id']='future-leak'
    events[0]['data']['feature_end_step']=3
    assert client.post(url,json={'events':[events[0]]}).status_code==400


def test_sustained_correctness_checks_later_work_after_recovery(database,monkeypatch):
    original = ScriptedAdapter.act
    def forget_after_commit(self,observation,state,condition):
        action,new_state,events = original(self,observation,state,condition)
        if action.tool=='checkpoint' and observation['step']>=6:
            action.arguments['value'] += 1
        return action,new_state,events
    monkeypatch.setattr(ScriptedAdapter,'act',forget_after_commit)
    report = study_service.run(small(scenario='sustained_correctness',task_lengths=[8],
        conditions=['idempotent_retry'],fault={'kind':'timeout_after_commit'}))
    row = report['trials'][0]
    assert not row['verified_success']
    episode = row['recovery_episodes'][0]
    assert episode['local_action_succeeded'] and not episode['verified_recovered']
    assert 'all_subtasks_correct' in episode['post_recovery_violations']


def test_duplicate_commit_is_a_recorded_alignment_violation(database):
    row = study_service.run(small(conditions=['generic_retry'],fault={'kind':'timeout_after_commit'}))['trials'][0]
    commits = [e for e in row['events'] if e['kind']=='tool' and e['data']['tool']=='commit']
    assert len(commits)==2 and not commits[-1]['data']['expected_aligned']


def test_local_provider_error_preserves_diagnosis_without_retry(monkeypatch):
    import httpx
    requests = []
    class Client:
        def __init__(self,**kwargs): pass
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def post(self,url,json):
            requests.append(url)
            return httpx.Response(500,json={'error':'model requires more system memory'},request=httpx.Request('POST',url))
    monkeypatch.setattr('app.services.benchmark_adapters.httpx.Client',Client)
    with pytest.raises(RuntimeError,match='model requires more system memory'):
        OllamaAdapter(model_manifest()).complete([], 'baseline',{},10,1000)
    assert len(requests)==1


def test_interrupted_model_request_resumes_without_call_or_false_zero_usage(database,monkeypatch):
    calls = []
    def killed(*args,**kwargs):
        calls.append(1)
        raise KeyboardInterrupt('worker lost during model request')
    monkeypatch.setattr(OllamaAdapter,'complete',killed)
    manifest = model_manifest()
    with pytest.raises(KeyboardInterrupt):
        study_service.run(manifest)
    interrupted = database.get_experiments()[0]
    resumed = study_service.run(manifest,interrupted['experiment_id'])
    row = resumed['trials'][0]
    assert len(calls)==1 and resumed['status']=='halted'
    assert row['termination_reason']=='model_response_interrupted'
    assert not row['token_usage_complete']
    assert resumed['model_budget']['calls'][0]['status']=='unknown'
