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

    dedup_findings = {}

    def finding(kind, evidence, message='', confidence='observed', title=None, status=None,
                reason=None, recommended_action=None, **detail):
        ids = [e['event_id'] for e in evidence if e.get('event_id')]
        readable_kind = kind.replace('_', ' ')
        final_title = title or (message if message and len(message) <= 60 else f"{readable_kind.capitalize()}")
        final_message = message or final_title or f"A {readable_kind} condition was detected."
        final_status = status or ('observed' if confidence == 'observed' else 'heuristic')
        final_reason = reason or final_message
        final_action = recommended_action or "Review referenced execution events."

        dep_step = detail.get('prerequisite_step') or detail.get('dep')
        target_step = detail.get('dependent_step') or detail.get('step')
        if kind == 'plan_dependency_unverified':
            key = (run_id, 'plan_dependency_unverified', str(dep_step), str(target_step), str(final_status), revision)
        elif kind == 'dependency_unverified':
            key = (run_id, 'dependency_unverified', str(detail.get('prerequisite')), str(detail.get('dependent_sub_goal')), str(final_status), revision)
        elif kind == 'repetition':
            key = (run_id, 'repetition', str(detail.get('operation')), str(detail.get('target')), str(detail.get('arguments_hash')))
        elif kind == 'suspected_loop':
            key = (run_id, 'suspected_loop', detail.get('width'), detail.get('lo'), detail.get('hi'))
        elif kind in ('post_completion_work', 'premature_completion_claim'):
            key = (run_id, kind, revision)
        elif kind == 'regression':
            key = (run_id, 'regression', str(detail.get('criterion_id')), revision)
        elif kind in ('justified_revisit', 'unexplained_rework'):
            key = (run_id, kind, str(detail.get('sub_goal_id')), revision)
        else:
            key = (run_id, kind, str(detail.get('operation_id') or detail.get('criterion_id') or final_message))

        if key in dedup_findings:
            existing = dedup_findings[key]
            existing['occurrence_count'] += 1
            for eid in ids:
                if eid not in existing['event_ids']:
                    existing['event_ids'].append(eid)
            if evidence and evidence[-1].get('timestamp'):
                existing['last_seen'] = evidence[-1].get('timestamp')
        else:
            entry = {
                'id': digest([VERSION, kind, str(key)])[:20],
                'kind': kind,
                'title': final_title,
                'status': final_status,
                'confidence': confidence,
                'message': final_message,
                'reason': final_reason,
                'recommended_action': final_action,
                'occurrence_count': 1,
                'event_ids': ids,
                'detector_version': VERSION,
                'first_seen': evidence[0].get('timestamp') if evidence else None,
                'last_seen': evidence[-1].get('timestamp') if evidence else None,
                'details': detail
            }
            if dep_step is not None:
                entry['prerequisite_step'] = dep_step
            if target_step is not None:
                entry['dependent_step'] = target_step
            if 'prerequisite_sub_goals' in detail:
                entry['prerequisite_sub_goals'] = detail['prerequisite_sub_goals']
            if 'dependent_sub_goal' in detail:
                entry['dependent_sub_goal'] = detail['dependent_sub_goal']
            dedup_findings[key] = entry

    def sub_status(sg, rev=None, at_state=None, detailed=False):
        rev = rev or revision
        current = snapshots.get(rev, {})
        required = [c['id'] for c in current.get('criteria',[]) if c.get('sub_goal_id')==sg]
        if not required:
            return 'unverified'
        rows = [criterion_evidence.get((rev,c)) for c in required]
        target_state = at_state if at_state is not None else state
        fresh = [e for e in rows if e and e.get('after_state') and e['after_state']==target_state]
        if len(fresh)==len(required) and all(e['data'].get('verdict')=='PASS' for e in fresh):
            return 'verified'
        if any(e and e['data'].get('verdict')=='FAIL' for e in fresh) or any(e and e['data'].get('verdict')=='FAIL' for e in rows):
            return 'failed'
        if any(e and e['data'].get('verdict')=='PASS' for e in rows):
            return 'stale'
        if detailed and all(e is None for e in rows):
            return 'not_checked'
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
                            status = sub_status(dep, at_state=e.get('before_state'), detailed=True)
                            if status not in ('verified', 'passed'):
                                finding('dependency_unverified', [e],
                                        message=f'Prerequisite sub-goal {dep} was {status} before starting {sg}.',
                                        title=f'Sub-goal {sg} started before prerequisite {dep} was verified',
                                        prerequisite=dep, dependent_sub_goal=sg, status=status,
                                        reason=f'Sub-goal {sg} has explicit dependency on {dep}, which is currently {status}.',
                                        recommended_action=f'Verify sub-goal {dep} before proceeding with {sg}.')
                # Plan prerequisites are only checkable when explicit step-to-sub-goal mappings exist.
                plan = plans.get(e.get('plan_revision'), {})
                for step in plan.get('steps',[]):
                    if sg and sg in step.get('sub_goal_ids',[]):
                        for dep in step.get('dependencies',[]):
                            prerequisite = next((s for s in plan.get('steps',[]) if str(s['step_number'])==str(dep)), None)
                            if prerequisite and prerequisite.get('sub_goal_ids'):
                                dependency_checks += 1
                                prereq_statuses = {g: sub_status(g, at_state=e.get('before_state'), detailed=True) for g in prerequisite['sub_goal_ids']}
                                if any(st not in ('verified', 'passed') for st in prereq_statuses.values()):
                                    if any(st == 'failed' for st in prereq_statuses.values()):
                                        worst = 'failed'
                                        reason_text = f"Prerequisite Step {dep} failed independent verification."
                                        action_text = f"Fix failing requirements in Step {dep} before proceeding with Step {step['step_number']}."
                                    elif any(st == 'stale' for st in prereq_statuses.values()):
                                        worst = 'stale'
                                        reason_text = f"Prerequisite Step {dep} was verified previously, but subsequent workspace changes made its verification stale."
                                        action_text = f"Re-run verification test suite on the current workspace to re-establish Step {dep} evidence."
                                    elif any(st == 'not_checked' for st in prereq_statuses.values()):
                                        worst = 'not_checked'
                                        reason_text = f"Prerequisite Step {dep} ({', '.join(prerequisite['sub_goal_ids'])}) has no recorded verification checks."
                                        action_text = f"Execute and pass verification checks for Step {dep} before executing Step {step['step_number']}."
                                    else:
                                        worst = 'unverified'
                                        reason_text = f"Prerequisite Step {dep} lacks conclusive passing verification evidence."
                                        action_text = f"Execute and pass verification checks for Step {dep} before executing Step {step['step_number']}."

                                    finding('plan_dependency_unverified', [e],
                                            message=f'Plan step {step["step_number"]} prerequisites (Step {dep}) were {worst}.',
                                            title=f'Plan Step {step["step_number"]} started before Step {dep} was verified',
                                            status=worst,
                                            reason=reason_text,
                                            recommended_action=action_text,
                                            prerequisite_step=dep,
                                            dependent_step=step['step_number'],
                                            prerequisite_sub_goals=prerequisite['sub_goal_ids'],
                                            dependent_sub_goal=sg,
                                            step=step['step_number'])
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

    findings = list(dedup_findings.values())

    unmapped_leaf = [a for a in leaf if not a.get('sub_goal_id')]
    unmapped_count = len(unmapped_leaf) if measured else 0
    mapped_count = (len(leaf) - unmapped_count) if measured else 0
    mapped_pct = round(((mapped_count / len(leaf)) * 100.0), 1) if (measured and leaf) else 0.0
    unmapped_pct = round(((unmapped_count / len(leaf)) * 100.0), 1) if (measured and leaf) else 0.0

    if fresh_run:
        task_verification_status = 'verified_passed'
    elif run_evidence and run_outcome == 'FAIL' and run_evidence.get('after_state') == state and run_evidence.get('goal_revision') == revision:
        task_verification_status = 'verified_failed'
    elif goals and verified == len(goals) and len(goals) > 0:
        task_verification_status = 'verified_passed'
    elif goals and any(s['status'] == 'failed' for s in subgoals):
        task_verification_status = 'verified_failed'
    else:
        task_verification_status = 'unverified'

    unreferenced_state = sum(not a.get('before_state') or not a.get('result', {}).get('after_state') for a in leaf)
    is_partial = bool(evidence_gap or missing or resource['unknown_usage_calls'] or unmapped_count or unreferenced_state)
    if not measured:
        workflow_evidence_completeness = 'unavailable'
    elif is_partial:
        workflow_evidence_completeness = 'partial'
    else:
        workflow_evidence_completeness = 'complete'

    partial_evidence_reasons = []
    if not measured:
        partial_evidence_reasons.append("No workflow telemetry or actions recorded.")
    else:
        if evidence_gap:
            partial_evidence_reasons.append("Telemetry sequence gap or instrumentation error detected.")
        if missing:
            partial_evidence_reasons.append(f"{missing} recorded action(s) lack completion results.")
        if resource.get('unknown_usage_calls'):
            partial_evidence_reasons.append(f"{resource['unknown_usage_calls']} call(s) have unrecorded resource metrics.")
        if unmapped_leaf:
            partial_evidence_reasons.append(
                f"{len(unmapped_leaf)} of {len(leaf)} action(s) ({unmapped_pct}%) were executed outside sub-goal scopes (e.g., initial system inspection, planning, or independent verification)."
            )
        if unreferenced_state:
            partial_evidence_reasons.append(f"{unreferenced_state} action(s) lack before or after workspace state references.")

    sub_goal_mapping_coverage = {
        'total_actions': len(leaf) if measured else 0,
        'mapped_actions': mapped_count,
        'unmapped_actions': unmapped_count,
        'mapped_ratio': ratio(mapped_count, len(leaf)),
        'unmapped_ratio': ratio(unmapped_count, len(leaf)),
        'mapped_percentage': mapped_pct,
        'unmapped_percentage': unmapped_pct,
        'unmapped_details': [
            {
                'action_id': a['action_id'],
                'operation': a.get('operation'),
                'category': a.get('category'),
                'sequence': a.get('sequence'),
                'reason': a.get('reason') or ('Initial environment inspection / discovery' if a.get('sequence', 0) <= 5 else 'Telemetry / verification step')
            }
            for a in unmapped_leaf
        ] if measured else []
    }

    return {'version':VERSION,'run_id':run_id,'execution_mode':execution_mode,
        'snapshot_sequence':events[-1]['sequence'] if events else 0,
        'evidence_status':'unavailable' if not measured else 'partial' if evidence_gap or missing or resource['unknown_usage_calls'] or any(not a.get('before_state') or not a.get('sub_goal_id') for a in leaf) else 'observed',
        'task_verification_status': task_verification_status,
        'workflow_evidence_completeness': workflow_evidence_completeness,
        'partial_evidence_reasons': partial_evidence_reasons,
        'sub_goal_mapping_coverage': sub_goal_mapping_coverage,
        'limitations':['Observational coverage is not proof that all external actions were captured.',
                      'Unmapped work and unsupported criteria are not assigned inferred completion.',
                      'Suspected loops and unexplained rework are review findings, not automatic interventions.'],
        'summary':{'action_attempts':len(tool_actions) if measured else None,
                   'model_calls':sum(a['category']=='model' for a in all_actions) if measured else None,
                   'stages':sum(a['category']=='stage' for a in all_actions) if measured else None,
                   'incomplete_actions':missing if measured else None,'tool_outcomes':{key:counts[key] for key in ('success','failed','error','rejected','incomplete')} if measured else {},
                   'verified_sub_goals':verified if goals else None,'required_sub_goals':len(goals) if goals else None,
                   'progress_rate':ratio(verified,len(goals)), 'verified_outcome':True if fresh_run else False if run_evidence and run_outcome=='FAIL' and run_evidence.get('after_state')==state and run_evidence.get('goal_revision')==revision else None,
                   'task_verification_status': task_verification_status,
                   'workflow_evidence_completeness': workflow_evidence_completeness,
                   'partial_evidence_reasons': partial_evidence_reasons,
                   'sub_goal_mapping_coverage': sub_goal_mapping_coverage,
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
                    'mapped_actions':mapped_count,
                    'unmapped_actions':unmapped_count,
                    'mapped_percentage':mapped_pct,
                    'unmapped_percentage':unmapped_pct,
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
