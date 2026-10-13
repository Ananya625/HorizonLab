"""Recalculable benchmark metrics. Missing producer evidence remains unavailable."""
import math
import statistics
from collections import Counter, defaultdict
from datetime import datetime
from .benchmark_analysis import classification, memory_metrics, prediction_metrics


def validate_evidence(event):
    datetime.fromisoformat(event.timestamp.replace('Z','+00:00'))
    data = event.data
    required = {'prediction':('probability','threshold','feature_end_step','model_version'),
        'drift':('predicted_drift','actual_drift','drift_type','severity','onset_step','resolved_step'),
        'memory':('relevant_available','relevant_retrieved','incorrect_retrieved','used_correctly'),
        'attribution':('cause','evidence','confidence'), 'human':('seconds','workload','simulated'),
        'intervention':('action','policy_version','reason')}[event.kind]
    if any(key not in data for key in required):
        raise ValueError(f'Incomplete {event.kind} event')
    if event.kind=='prediction':
        if not isinstance(data['model_version'],str) or not data['model_version']:
            raise ValueError('Prediction model version is required')
        for field in ('probability','threshold'):
            if type(data[field]) not in (float,int) or not math.isfinite(data[field]) or not 0<=data[field]<=1:
                raise ValueError('Invalid prediction probability/threshold')
        if type(data['feature_end_step']) is not int or not 0<=data['feature_end_step']<=event.step:
            raise ValueError('Prediction contains future features')
    if event.kind=='memory':
        memory_metrics([data])
        for key in ('written_count','discarded_count','stale_count','invalidated_count','contradictory_count'):
            if key in data and (type(data[key]) is not int or data[key]<0):
                raise ValueError('Memory state counts must be nonnegative integers')
    if event.kind=='drift':
        classification([data['actual_drift']], [data['predicted_drift']])
        if type(data['onset_step']) is not int or not 0<=data['onset_step']<=event.step:
            raise ValueError('Invalid drift onset')
        if data['resolved_step'] is not None and (type(data['resolved_step']) is not int or not data['onset_step']<=data['resolved_step']<=event.step):
            raise ValueError('Invalid drift resolution')
    if event.kind=='human':
        if 'intervention_count' in data and (type(data['intervention_count']) is not int or data['intervention_count']<0):
            raise ValueError('Human intervention count must be nonnegative')
        if type(data['seconds']) not in (float,int) or not math.isfinite(data['seconds']) or data['seconds']<0 or type(data['simulated']) is not bool:
            raise ValueError('Invalid human time')
        if data['workload'] is not None and (type(data['workload']) not in (int,float) or not math.isfinite(data['workload']) or not 0<=data['workload']<=100):
            raise ValueError('Workload must be 0..100 or unavailable')
    if event.kind=='attribution':
        if not data['evidence'] or type(data['confidence']) not in (int,float) or not math.isfinite(data['confidence']) or not 0<=data['confidence']<=1:
            raise ValueError('Attribution requires evidence and bounded confidence')


def trial_analytics(row):
    events = row['events']
    uses = {e['data']['retrieval_event_id']:e['data']['used_correctly'] for e in events if e['kind']=='memory_use'}
    memory = []
    for e in events:
        if e['kind']=='memory':
            data = dict(e['data'])
            if data.get('used_correctly') is None:
                data['used_correctly'] = uses.get(e['event_id'])
            if all(type(data.get(k)) is bool for k in ('relevant_available','relevant_retrieved','incorrect_retrieved','used_correctly')):
                memory.append(data)
    tools = [e for e in events if e['kind']=='tool']
    violations = [e['step'] for e in tools if not e['data']['expected_aligned']]
    failure_step = min(violations) if violations else row['tool_calls'] if not row['verified_success'] else None
    predictions = []
    for e in events:
        if e['kind']=='prediction':
            # Decisions after the failure are scored for classification but not as early warnings.
            predictions.append(dict(e['data'], step=e['step'], run_id=row['run_id'], split='evaluation',
                eventual_failure=not row['verified_success'], failure_step=failure_step if failure_step is not None and failure_step>=e['step'] else None))
    drift = [e['data'] for e in events if e['kind']=='drift']
    human = [e['data'] for e in events if e['kind']=='human' and not e['data']['simulated']]
    simulated_human = [e for e in events if e['kind']=='human' and e['data']['simulated']]
    workloads = [e['workload'] for e in human if e.get('workload') is not None]
    memory_result = memory_metrics(memory)
    for key in ('written_count','discarded_count','stale_count','invalidated_count','contradictory_count'):
        known = [e[key] for e in memory if key in e]
        memory_result[key] = sum(known) if known else None
    memory_result['write_rate_per_action'] = memory_result['written_count']/row['tool_calls'] if memory_result['written_count'] is not None and row['tool_calls'] else None
    drift_episodes = {}
    for d in drift:
        if d['actual_drift']:
            key = d.get('drift_id') or (d['drift_type'],d['onset_step'],d.get('constraint_id'))
            drift_episodes[key] = d
    delays = defaultdict(list)
    for e in memory:
        if e.get('delay_steps') is not None:
            delays[e['delay_steps']].append(e['used_correctly'])
    return {'memory':dict(memory_result, retention_by_delay=[{'delay_steps':d,'n':len(v),'correct_use_rate':sum(v)/len(v)} for d,v in sorted(delays.items())]),
        'prediction':prediction_metrics(predictions) if predictions else None,
        'goal_tracker':classification([d['actual_drift'] for d in drift],[d['predicted_drift'] for d in drift]) if drift else None,
        'drift':{'sample_count':len(drift), 'frequency':len(drift_episodes),
            'onsets':[d['onset_step'] for d in drift_episodes.values()],
            'durations_steps':[d['resolved_step']-d['onset_step'] for d in drift_episodes.values() if d['resolved_step'] is not None],
            'by_type':dict(Counter(d['drift_type'] for d in drift_episodes.values())),
            'by_severity':dict(Counter(d['severity'] for d in drift_episodes.values()))},
        'observed_requirement_violations':len(violations),
        'plausible_attribution':dict(Counter(e['data']['cause'] for e in events if e['kind']=='attribution')),
        'human':{'observed_events':len(human), 'interventions':sum(e.get('intervention_count',1) for e in human),
            'seconds':sum(e['seconds'] for e in human) if human else None,
            'mean_workload':statistics.mean(workloads) if workloads else None, 'simulated_events':len(simulated_human)},
        'efficiency':{'generated_tokens':row.get('generated_tokens') if row.get('token_usage_complete',True) else None,
            'model_calls':row.get('model_calls',0),'compute_cost':row.get('compute_cost'),
            'calls_per_verified_success':row['tool_calls'] if row['verified_success'] else None}}


def capability_history(trials):
    history, previous, counts = [], {}, Counter()
    for row in sorted(trials, key=lambda r:(r['finished_at'],r['run_id'])):
        analytics = trial_analytics(row)
        events = [e['data'] for e in row['events'] if e['kind']=='tool']
        scope = (row['adapter_id'],row['adapter_version'],row['condition'],row['task_id'],row['execution_mode'],row.get('cohort'))
        v = row['verification']['criteria']
        scores = {'planning':float(v['all_subtasks_correct']) if row['verification']['final_state']['checkpoints'] else None,
            'tools':sum('error' not in e for e in events)/len(events) if events else None,
            'memory':analytics['memory'].get('correct_use_rate'),
            'goal_adherence':sum(e['expected_aligned'] for e in events)/len(events) if events else None,
            'safety':float(v['no_prohibited_effects'] and row['verification']['duplicate_effects']==0),
            'robustness':float(row['verified_success']) if row['fault_occurred'] else None,
            'efficiency':min(1,row['task_length']/row['tool_calls']) if row['verified_success'] and row['tool_calls'] else None,
            'recovery':sum(e['verified_recovered'] for e in row['recovery_episodes'])/len(row['recovery_episodes']) if row['recovery_episodes'] else None}
        dimensions = {}
        for dimension, score in scores.items():
            key = (*scope,dimension)
            if score is not None:
                previous[key] = .7*previous[key]+.3*score if key in previous else score
                counts[key] += 1
            dimensions[dimension] = {'current_score':score,'ewma':previous.get(key),'sample_count':counts[key]}
        history.append({'run_id':row['run_id'],'timestamp':row['finished_at'],'task_id':row['task_id'],
            'agent':row['adapter_id'],'condition':row['condition'],'cohort':row.get('cohort'),'dimensions':dimensions,
            'normalization':'0..1 observed fixture performance; EWMA alpha=.3; unknown dimensions are not updated. Planning means prerequisite completion, not general reasoning ability.'})
    return history


def study_analytics(trials):
    matched = defaultdict(dict)
    for row in trials:
        key = (row['task_id'],row['task_length'],row['seed'])
        matched[key][row['condition']] = row
    pairs = defaultdict(list)
    for key, group in matched.items():
        reference = group.get('baseline') or group.get('memory_none')
        if reference:
            for condition, row in group.items():
                if row is reference or row['initial_state'] != reference['initial_state']:
                    continue
                pairs[(reference['condition'],condition)].append((row,reference))
    comparisons = []
    for (baseline,condition), values in sorted(pairs.items()):
        gains = [int(row['verified_success'])-int(ref['verified_success']) for row,ref in values]
        comparisons.append({'baseline':baseline,'condition':condition,'matched_pairs':len(values),
            'verified_success_difference':statistics.mean(gains),
            'mean_extra_calls':statistics.mean(row['tool_calls']-ref['tool_calls'] for row,ref in values),
            'difference_standard_error':statistics.stdev(gains)/math.sqrt(len(gains)) if len(gains)>1 else None,
            'interpretation':'Matched task, initial state, length and seed; descriptive fixture comparison, not proof of causal model improvement.'})
    return {'version':'study-analysis-v1','runs':{r['run_id']:trial_analytics(r) for r in trials},
        'paired_comparisons':comparisons,'capability_history':capability_history(trials)}
