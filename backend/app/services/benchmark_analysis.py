"""Pure analysis; no model training or inferred missing upstream events."""
import math
import statistics
from collections import defaultdict


def wilson(successes, n):
    if not n:
        return None
    z, p = 1.959963984540054, successes / n
    denominator = 1 + z*z/n
    center = (p + z*z/(2*n))/denominator
    half = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n))/denominator
    return [max(0, center-half), min(1, center+half)]


def summarize(trials):
    groups = defaultdict(list)
    for trial in trials:
        groups[(trial['task_id'], trial['condition'], trial['task_length'], trial['fault']['kind'], trial['fault_occurred'])].append(trial)
    summaries = []
    for (task, condition, length, fault, occurred), rows in sorted(groups.items()):
        n = len(rows)
        success = sum(r['verified_success'] is True for r in rows)
        durations = [r['duration_seconds'] for r in rows if r.get('timing_complete', True)]
        episodes = [e for r in rows for e in r['recovery_episodes']]
        recovered = sum(e['verified_recovered'] is True for e in episodes)
        overhead = [r['harness_overhead_seconds'] for r in rows if r.get('harness_overhead_seconds') is not None]
        tokens = [r['generated_tokens'] for r in rows if r.get('generated_tokens') is not None and r.get('token_usage_complete',True)]
        summaries.append(dict(task_id=task, condition=condition, task_length=length,
            fault_kind=fault, fault_occurred=occurred, sample_count=n,
            verified_success_rate=success/n, success_ci95=wilson(success, n),
            mean_duration_seconds=statistics.mean(durations) if durations else None,
            stdev_duration_seconds=statistics.stdev(durations) if len(durations) > 1 else None,
            mean_tool_calls=statistics.mean(r['tool_calls'] for r in rows),
            mean_harness_overhead_seconds=statistics.mean(overhead) if overhead else None,
            successful_mean_tool_calls=statistics.mean(r['tool_calls'] for r in rows if r['verified_success']) if success else None,
            tool_calls_per_verified_success=sum(r['tool_calls'] for r in rows)/success if success else None,
            recovery_episode_count=len(episodes), recovery_rate=recovered/len(episodes) if episodes else None,
            recovery_ci95=wilson(recovered, len(episodes)),
            mean_recovery_seconds=statistics.mean(e['duration_seconds'] for e in episodes if e['verified_recovered']) if recovered else None,
            failed_trials=n-success,
            budget_exhausted=sum(r['termination_reason']=='budget_exceeded' for r in rows)))
        summaries[-1].update(token_usage_sample_count=len(tokens), known_generated_tokens=sum(tokens) if tokens else None,
            generated_tokens_per_verified_success=sum(tokens)/success if success and len(tokens)==n else None,
            duplicate_effects=sum(r.get('verification',{}).get('duplicate_effects',0) for r in rows))
    return summaries


def classification(labels, predictions):
    if len(labels) != len(predictions) or not labels or any(type(v) is not bool for v in [*labels, *predictions]):
        raise ValueError('Equal non-empty boolean labels/predictions required')
    tp = sum(y and p for y, p in zip(labels, predictions))
    fp = sum(not y and p for y, p in zip(labels, predictions))
    fn = sum(y and not p for y, p in zip(labels, predictions))
    tn = sum(not y and not p for y, p in zip(labels, predictions))
    return {'tp': tp, 'fp': fp, 'fn': fn, 'tn': tn,
        'precision': tp/(tp+fp) if tp+fp else None,
        'recall': tp/(tp+fn) if tp+fn else None,
        'f1': 2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None,
        'false_alarm_rate': fp/(fp+tn) if fp+tn else None,
        'missed_failure_rate': fn/(tp+fn) if tp+fn else None}


def prediction_metrics(events):
    """Adapter contract: one decision per labeled trajectory/window; labels evaluator-only."""
    labels, decisions, errors, leads = [], [], [], []
    bins = [[] for _ in range(10)]
    for e in events:
        required = {'probability', 'threshold', 'step', 'feature_end_step', 'eventual_failure', 'model_version', 'run_id', 'split'}
        if not required <= e.keys() or e['feature_end_step'] > e['step']:
            raise ValueError('Missing prediction provenance or future feature leakage')
        if e['split'] != 'evaluation':
            raise ValueError('Only held-out evaluation predictions may be scored')
        p, threshold = e['probability'], e['threshold']
        if not (math.isfinite(p) and 0 <= p <= 1 and math.isfinite(threshold) and 0 <= threshold <= 1):
            raise ValueError('Invalid probability or threshold')
        labels.append(e['eventual_failure'])
        decisions.append(p >= threshold)
        errors.append((p-int(e['eventual_failure']))**2)
        bins[min(int(p*10), 9)].append((p, int(e['eventual_failure'])))
        if p >= threshold and e['eventual_failure'] and e.get('failure_step') is not None:
            if e['failure_step'] < e['step']:
                raise ValueError('A post-failure prediction is not an early warning')
            leads.append((e['run_id'], e['failure_step']-e['step']))
    first_leads = {}
    for run, lead in leads:
        first_leads[run] = max(lead, first_leads.get(run, lead))
    return dict(classification(labels, decisions), sample_count=len(labels), brier_score=statistics.mean(errors),
        calibration=[{'count':len(b), 'mean_probability':statistics.mean(p for p,y in b), 'failure_rate':statistics.mean(y for p,y in b)} for b in bins if b],
        mean_warning_lead_steps=statistics.mean(first_leads.values()) if first_leads else None)


def validate_split_isolation(training, evaluation):
    """Reject overlap by task template and run, not by shuffled trajectory row."""
    for field in ('run_id', 'task_template_id'):
        if any(not row.get(field) for row in [*training, *evaluation]):
            raise ValueError(f'Missing {field}')
        if {row[field] for row in training} & {row[field] for row in evaluation}:
            raise ValueError(f'Training/evaluation overlap: {field}')


def memory_metrics(events):
    """Score evaluator-labeled retrieval decisions; never infer absent labels."""
    if not events:
        return {'sample_count':0, 'relevant_retrieval_rate':None, 'incorrect_retrieval_rate':None}
    fields = ('relevant_available', 'relevant_retrieved', 'incorrect_retrieved', 'used_correctly')
    for event in events:
        if any(type(event.get(field)) is not bool for field in fields):
            raise ValueError('Complete boolean memory labels required')
        if event['relevant_retrieved'] and not event['relevant_available']:
            raise ValueError('Relevant retrieval requires available memory')
    available = sum(e['relevant_available'] for e in events)
    return {'sample_count':len(events),
        'relevant_retrieval_rate':sum(e['relevant_retrieved'] for e in events)/available if available else None,
        'missing_memory_rate':sum(not e['relevant_available'] for e in events)/len(events),
        'available_but_not_retrieved_rate':sum(e['relevant_available'] and not e['relevant_retrieved'] for e in events)/available if available else None,
        'incorrect_retrieval_rate':sum(e['incorrect_retrieved'] for e in events)/len(events),
        'correct_use_rate':sum(e['used_correctly'] for e in events)/len(events)}
