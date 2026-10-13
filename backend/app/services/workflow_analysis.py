"""Deterministic replay of observed evidence, deliberately separate from policy."""
from collections import Counter, defaultdict
from datetime import datetime
from .workflow_service import digest

VERSION = 'workflow-v1'
TOOLS = {'file_read','file_write','pytest','inspect_targeted','inspect_directory'}
ALLOWED_REASONS = {'validation','reporting','cleanup','recovery','dependency_changed','requirements_changed','polling'}


def seconds(event):
    return datetime.fromisoformat(event['timestamp']).timestamp()


def resources(actions):
    """Leaf-operation resources; union intervals avoids double-counting overlap."""
    leaves = [a for a in actions if a['category'] in ('tool','model')]
    models = [a for a in leaves if a['category'] == 'model']
    intervals = []
    for a in leaves:
        result = a.get('result') or {}
        duration = result.get('duration_seconds')
        if duration is not None:
            end = seconds(result)
            intervals.append((end-duration, end))
    total, edge = 0, None
    for left, right in sorted(intervals):
        total += max(0, right-max(left, edge if edge is not None else left))
        edge = max(edge if edge is not None else right, right)
    unknown = sum(not a.get('result') or any(a['result'].get(k) is None for k in ('input_tokens','output_tokens')) for a in models)
    tokens = {}
    for key in ('input_tokens','output_tokens'):
        measured = [a['result'][key] for a in models if a.get('result') and a['result'].get(key) is not None]
        tokens[key] = sum(measured) if len(measured) == len(models) else None
        tokens['known_'+key] = sum(measured)
    return {'tool_calls':sum(a['category']=='tool' for a in leaves), 'model_calls':len(models),
            'duration_seconds':round(total,6) if len(intervals)==len(leaves) else None,
            'known_duration_seconds':round(total,6), 'unknown_usage_calls':unknown, **tokens}


def analyze(events, run_id, execution_mode='unknown', evidence_gap=False):
    # Store guarantees sequence order and idempotence; replay also tolerates duplicate delivery.
    events = sorted({e['event_id']:e for e in events}.values(), key=lambda e:e['sequence'])
    findings, actions, attempts, timeline = [], {}, {}, []
    snapshots = {e['goal_revision']:e['data'] for e in events if e['kind']=='goal_snapshot'}
    plans = {e['plan_revision']:e['data'] for e in events if e['kind']=='plan_snapshot'}
    revision = None
    state = None
    criterion_evidence = {}
    previous_passes = {}
    completed_history = {}
    run_pass = None
    last_progress = None
    verified_progress_sequences = []
    progress = []
    effect_ids = defaultdict(set)
    rework_ids = set()
    revisit_counts, regression_counts = Counter(), Counter()
    dependency_checks = 0
    completion_claims = 0
    reported_status = {}
    run_outcome = None
    run_evidence = None

    def finding(kind, evidence, message, confidence='observed', **detail):
        ids = [e['event_id'] for e in evidence]
        findings.append({'id':digest([VERSION,kind,ids])[:20], 'kind':kind,'confidence':confidence,
                         'message':message,'event_ids':ids,'detector_version':VERSION,'details':detail})

    def sub_status(sg, rev=None, at_state=None):
        rev = rev or revision
        current = snapshots.get(rev, {})
        required = [c['id'] for c in current.get('criteria',[]) if c.get('sub_goal_id')==sg]
        if not required:
            return 'unverified'
        rows = [criterion_evidence.get((rev,c)) for c in required]
        fresh = [e for e in rows if e and e.get('after_state') and e['after_state']==(at_state or state)]
        if any(e['data'].get('verdict')=='FAIL' for e in fresh):
            return 'failed'
        if len(fresh)==len(required) and all(e['data'].get('verdict')=='PASS' for e in fresh):
            return 'verified'
        if any(e and e['data'].get('verdict')=='PASS' and e not in fresh for e in rows):
            return 'stale'
        return 'unverified'

    for e in events:
        kind, data = e['kind'], e.get('data',{})
        if kind in ('action_start','verification','goal_snapshot','notice') and e.get('goal_revision'):
            if revision != e['goal_revision']:
                run_pass = None
                run_outcome = None
                run_evidence = None
            revision = e['goal_revision']
        if e.get('before_state') and kind=='action_start':
            state = e['before_state']
        if kind=='notice' and 'reported_status' in data:
            reported_status.update({(revision,k):v for k,v in data['reported_status'].items()})
        if kind=='attempt_start':
            attempts[e['attempt_id']] = dict(e)
        elif kind=='attempt_end' and e['attempt_id'] in attempts:
            attempts[e['attempt_id']]['result'] = e
        elif kind=='action_start':
            a = dict(e)
            actions[e['action_id']] = a
            sg = e.get('sub_goal_id')
            if e['category']=='tool':
                prior = completed_history.get((revision,sg)) if sg else None
                changed_requirement = False
                if sg and prior is None:
                    prior = max((value for (rev,goal_id),value in completed_history.items() if goal_id==sg),
                                key=lambda value:value['sequence'], default=None)
                    changed_requirement = prior is not None
                if prior:
                    revisit_counts[sg] += 1
                    reason = e.get('reason') or ('requirements_changed' if changed_requirement else None)
                    label = 'justified_revisit' if reason in ALLOWED_REASONS else 'unexplained_rework'
                    finding(label,[prior,e],f'Revisited verified sub-goal {sg}: {reason or "no reason recorded"}.',
                            confidence='observed' if reason else 'heuristic')
                    if label=='unexplained_rework':
                        rework_ids.add(e['action_id'])
                if run_pass and e.get('reason') not in ALLOWED_REASONS:
                    finding('post_completion_work',[run_pass,e],'Operational work continued after verified completion without a recorded reason.','heuristic')
                    rework_ids.add(e['action_id'])
                if e['operation'] not in TOOLS and not data.get('registered_tool'):
                    finding('invalid_tool',[e],'Tool name is absent from the recorded tool registry.')
                for sub in snapshots.get(revision,{}).get('sub_goals',[]):
                    if sub['id']==sg:
                        for dep in sub.get('dependencies',[]):
                            dependency_checks += 1
                            status = sub_status(dep, at_state=e.get('before_state'))
                            if status!='verified':
                                finding('dependency_unverified',[e],f'Prerequisite {dep} was not freshly verified before {sg}.',
                                        prerequisite=dep, status=status)
                # Plan prerequisites are only checkable when explicit step-to-sub-goal mappings exist.
                plan = plans.get(e.get('plan_revision'), {})
                for step in plan.get('steps',[]):
                    if sg and sg in step.get('sub_goal_ids',[]):
                        for dep in step.get('dependencies',[]):
                            prerequisite = next((s for s in plan.get('steps',[]) if s['step_number']==dep),None)
                            if prerequisite and prerequisite.get('sub_goal_ids'):
                                dependency_checks += 1
                                if any(sub_status(g)!='verified' for g in prerequisite['sub_goal_ids']):
                                    finding('plan_dependency_unverified',[e],f'Plan step {dep} prerequisites were not verified.', step=step['step_number'])
        elif kind=='action_result':
            a = actions.get(e['action_id'])
            if a:
                a['result'] = e
            if e.get('after_state'):
                state = e['after_state']
            if e.get('outcome')=='rejected':
                finding('rejected_arguments',[e],'Operation was rejected; inspect its validation error category.', error_category=data.get('error_category'))
            if e.get('effect_id') and e.get('intended_operation_id') and e.get('outcome')=='success':
                key = e['intended_operation_id']
                if effect_ids[key] and e['effect_id'] not in effect_ids[key]:
                    finding('duplicate_effect',[e],'One intended operation has multiple distinct committed effects.', operation_id=key)
                effect_ids[key].add(e['effect_id'])
        elif kind=='verification' and data.get('independent') and e.get('evidence_refs') and e.get('after_state'):
            state = e['after_state']
            if data.get('scope')=='criterion':
                key = (revision,data['criterion_id'])
                old_pass = previous_passes.get(key)
                sg = e.get('sub_goal_id')
                if data.get('verdict')=='FAIL' and old_pass and old_pass.get('after_state')!=state:
                    finding('regression',[old_pass,e],'Previously verified criterion failed after a state change.','verified', criterion_id=key[1])
                    if sg:
                        regression_counts[sg] += 1
                    previous_passes.pop(key,None)
                before_status = sub_status(sg) if sg else None
                criterion_evidence[key] = e
                if data.get('verdict')=='PASS':
                    previous_passes[key] = e
                if sg and sub_status(sg)=='verified' and before_status!='verified':
                    completed_history[(revision,sg)] = e
                    last_progress = e
                    verified_progress_sequences.append(e['sequence'])
            elif data.get('scope')=='run':
                run_outcome = data.get('verdict')
                run_evidence = e
                if run_outcome=='PASS':
                    if not run_pass or run_pass.get('after_state') != state:
                        last_progress = e
                        verified_progress_sequences.append(e['sequence'])
                    run_pass = e
                else:
                    run_pass = None
        elif kind=='completion_claim':
            completion_claims += 1
            if not run_pass or run_pass.get('after_state')!=state or run_pass.get('goal_revision')!=revision:
                finding('premature_completion_claim',[e],'Completion was claimed without fresh independently verified run success.','observed')
        if kind in ('verification','goal_snapshot','attempt_start','attempt_end','completion_claim','action_start','action_result','notice'):
            timeline.append({'event_id':e['event_id'],'sequence':e['sequence'],'kind':kind,
                'operation':e.get('operation'),'outcome':e.get('outcome'), 'sub_goal_id':e.get('sub_goal_id'),
                'timestamp':e['timestamp'],'reason':e.get('reason')})
        if kind=='verification' or (kind=='action_result' and e.get('before_state')!=e.get('after_state')):
            goals = snapshots.get(revision,{}).get('sub_goals',[])
            count = sum(sub_status(g['id'])=='verified' for g in goals)
            progress.append({'event_id':e['event_id'],'sequence':e['sequence'],'verified':count,'required':len(goals),
                             'rate':count/len(goals) if goals else None})

    tool_actions = [a for a in actions.values() if a['category']=='tool']
    repeats = 0
    window = []
    seen = {}
    for a in tool_actions:
        r = a.get('result') or {}
        fingerprint = (a['operation'], a.get('arguments_hash'),a.get('target'),a.get('before_state'),a.get('goal_revision'),a.get('plan_revision'))
        comparable = bool(a.get('arguments_hash') and a.get('before_state'))
        if comparable and fingerprint in seen:
            repeats += 1
            finding('repetition',[seen[fingerprint],a],'Equivalent operation repeated under the same recorded input state.')
        if comparable:
            seen[fingerprint] = a
        stable = comparable and bool(r.get('observation_hash')) and r.get('after_state')==a.get('before_state') and a.get('reason') not in ALLOWED_REASONS
        item = (fingerprint,r.get('observation_hash')) if stable else None
        window.append((item,a))
        window = window[-64:]
        for width in range(1,5):
            repetitions = 3 if width==1 else 2
            n = width*repetitions
            if len(window)<n:
                continue
            tail = window[-n:]
            keys = [x[0] for x in tail]
            if None in keys or any(keys[i]!=keys[i % width] for i in range(n)):
                continue
            lo, hi = tail[0][1]['sequence'],a['sequence']
            if any(lo<seq<hi for seq in verified_progress_sequences):
                continue
            finding('suspected_loop',[v for _,v in tail],f'Repeated sequence of {width} operation(s) without observed change or new information.','heuristic')
            break

    all_actions = list(actions.values())
    missing = sum(not a.get('result') for a in all_actions)
    leaf = [a for a in all_actions if a['category']!='stage']
    resource = resources(all_actions)
    goals = snapshots.get(revision,{}).get('sub_goals',[])
    subgoals = []
    for g in goals:
        sg = g['id']
        assigned = [a for a in all_actions if a.get('sub_goal_id')==sg and a.get('goal_revision')==revision]
        explicit = [a for a in attempts.values() if a.get('sub_goal_id')==sg and a.get('goal_revision')==revision]
        subgoals.append({**g,'status':sub_status(sg),'reported_status':reported_status.get((revision,sg),'unavailable'),'attempts':len(explicit),
                        'incomplete_attempts':sum(not a.get('result') for a in explicit),
                        'revisits':revisit_counts[sg],'regressions':regression_counts[sg],
                        'resources':resources(assigned)})
    recovery_actions = [a for a in all_actions if a.get('recovery_id')]
    # Children inherit recovery IDs; rework attribution expands to model children of the same attempt.
    rework_attempts = {actions[i].get('attempt_id') for i in rework_ids}-{None}
    rework_actions = [a for a in all_actions if a['action_id'] in rework_ids or a.get('attempt_id') in rework_attempts]
    overhead = {a['action_id']:a for a in recovery_actions+rework_actions}
    recoveries = []
    for recovery_id in sorted({a.get('recovery_id') for a in attempts.values()}-{None}):
        starts = [a for a in attempts.values() if a.get('recovery_id')==recovery_id]
        end = max((a.get('result',{}).get('sequence',10**18) for a in starts), default=10**18)
        later = [e for e in events if e['sequence']>end and e.get('goal_revision') in {a.get('goal_revision') for a in starts} and e['kind']=='verification' and e['data'].get('scope')=='run' and e['data'].get('independent') and e.get('evidence_refs') and e.get('after_state')]
        success = next((e for e in later if e['data'].get('verdict')=='PASS'),None)
        recurrence = bool(success and any(e['sequence']>success['sequence'] and e['data'].get('verdict')=='FAIL' for e in later))
        recoveries.append({'recovery_id':recovery_id,'verified_recovery':True if success else None,
                           'recurrence':recurrence,'resources':resources([a for a in recovery_actions if a['recovery_id']==recovery_id])})
    plan_observations = []
    for pr, plan in plans.items():
        planned = {f['path'] for f in plan.get('files',[])}
        written = {a.get('target') for a in tool_actions if a.get('plan_revision')==pr and a['operation']=='file_write' and a.get('result',{}).get('outcome')=='success'}
        plan_observations.append({'plan_revision':pr, 'planned_targets':sorted(planned),
            'observed_writes':sorted(written & planned), 'unobserved_targets':sorted(planned-written),
            'unplanned_targets':sorted(written-planned),
            'note':'A write is observed work, not independently verified plan completion. Alternative plans remain separate revisions.'})
    baseline = last_progress or (events[0] if events else None)
    measured = bool(events and actions)
    counts = Counter(a.get('result',{}).get('outcome','incomplete') for a in tool_actions)
    paired = sum(bool(a.get('result')) for a in all_actions)
    def ratio(n,d):
        return n/d if d else None
    verified = sum(s['status']=='verified' for s in subgoals)
    fresh_run = bool(run_pass and run_pass.get('after_state')==state and run_pass.get('goal_revision')==revision)
    def overhead_resources(group):
        return resources(group) if measured else {k:None for k in resources([])}
    return {'version':VERSION,'run_id':run_id,'execution_mode':execution_mode,
        'snapshot_sequence':events[-1]['sequence'] if events else 0,
        'evidence_status':'unavailable' if not measured else 'partial' if evidence_gap or missing or resource['unknown_usage_calls'] or any(not a.get('before_state') or not a.get('sub_goal_id') for a in leaf) else 'observed',
        'limitations':['Observational coverage is not proof that all external actions were captured.',
                      'Unmapped work and unsupported criteria are not assigned inferred completion.',
                      'Suspected loops and unexplained rework are review findings, not automatic interventions.'],
        'summary':{'action_attempts':len(tool_actions) if measured else None,
                   'model_calls':sum(a['category']=='model' for a in all_actions) if measured else None,
                   'stages':sum(a['category']=='stage' for a in all_actions) if measured else None,
                   'incomplete_actions':missing if measured else None,'tool_outcomes':{key:counts[key] for key in ('success','failed','error','rejected','incomplete')} if measured else {},
                   'verified_sub_goals':verified if goals else None,'required_sub_goals':len(goals) if goals else None,
                   'progress_rate':ratio(verified,len(goals)), 'verified_outcome':True if fresh_run else False if run_evidence and run_outcome=='FAIL' and run_evidence.get('after_state')==state and run_evidence.get('goal_revision')==revision else None,
                   'repeated_actions':repeats if measured else None,'completion_claims':completion_claims if measured else None,
                   'wall_seconds':max(0,seconds(events[-1])-seconds(events[0])) if len(events)>1 else None,
                   'unmapped_actions':sum(not a.get('sub_goal_id') for a in leaf) if measured else None,
                   'dependency_checks':dependency_checks if measured else None,
                   'duplicate_effects':sum(f['kind']=='duplicate_effect' for f in findings) if effect_ids else None,
                   'effect_identity_operations':len(effect_ids) if measured else None,
                   'resources':resource if measured else None,
                   'cost_per_verified_success':resource if fresh_run else None},
        'coverage':{'paired_outcomes':ratio(paired,len(all_actions)),
                    'state_references':ratio(sum(bool(a.get('before_state') and a.get('result',{}).get('after_state')) for a in leaf),len(leaf)),
                    'sub_goal_mapping':ratio(sum(bool(a.get('sub_goal_id')) for a in leaf),len(leaf)),
                    'instrumentation_error':evidence_gap},
        'stagnation':{'baseline':'last_verified_progress' if last_progress else 'first_observation',
                      'actions':sum(a['sequence']>baseline['sequence'] for a in tool_actions) if baseline else None,
                      'seconds':max(0,seconds(events[-1])-seconds(baseline)) if baseline else None},
        'sub_goals':subgoals,'progress':progress,'findings':findings,'plan_observations':plan_observations,
        'attempts':[{'attempt_id':a['attempt_id'],'sub_goal_id':a.get('sub_goal_id'),'recovery_id':a.get('recovery_id'),
                    'outcome':a.get('result',{}).get('outcome','incomplete'),
                    'resources':resources([x for x in all_actions if x.get('attempt_id')==a['attempt_id']])} for a in attempts.values()],
        'recovery':recoveries,'overhead':{'recovery':overhead_resources(recovery_actions),
            'rework':overhead_resources(rework_actions),'union':overhead_resources(list(overhead.values())),
            'note':'Categories overlap; only the union deduplicates them.'},
        'calculation':{'action_denominator':'explicit tool starts','progress_denominator':'required mapped goal sub-goals',
                       'loop_window':64,'max_sequence_length':4,'zero_denominator':None},
        'timeline':timeline}
