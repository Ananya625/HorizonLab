import pytest
from datetime import datetime, timezone, timedelta
from app.models.workflow import WorkflowEvent
from app.services.workflow_analysis import analyze


class Trace:
    def __init__(self, run_id='r1'):
        self.run_id = run_id
        self.events = []

    def emit(self, kind, **fields):
        n = len(self.events) + 1
        event = WorkflowEvent(
            event_id=f'e{n}',
            run_id=self.run_id,
            kind=kind,
            timestamp=(datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=n)).isoformat(),
            **fields
        ).model_dump()
        event['sequence'] = n
        self.events.append(event)
        return event

    def goal(self, revision='g1', sub_goals=None, criteria=None):
        subs = sub_goals or [
            {'id': 's1', 'title': 'SubGoal 1', 'dependencies': []},
            {'id': 's2', 'title': 'SubGoal 2', 'dependencies': ['s1']},
            {'id': 's3', 'title': 'SubGoal 3', 'dependencies': ['s2']},
        ]
        crits = criteria or [
            {'id': 'c1', 'sub_goal_id': 's1'},
            {'id': 'c2', 'sub_goal_id': 's2'},
            {'id': 'c3', 'sub_goal_id': 's3'},
        ]
        return self.emit('goal_snapshot', goal_revision=revision, data={
            'sub_goals': subs,
            'criteria': crits,
        })

    def plan(self, revision='p1', steps=None):
        default_steps = [
            {'step_number': 1, 'description': 'Step 1', 'sub_goal_ids': ['s1'], 'dependencies': []},
            {'step_number': 2, 'description': 'Step 2', 'sub_goal_ids': ['s2'], 'dependencies': [1]},
            {'step_number': 3, 'description': 'Step 3', 'sub_goal_ids': ['s3'], 'dependencies': [2]},
        ]
        return self.emit('plan_snapshot', plan_revision=revision, data={
            'steps': steps or default_steps,
            'files': []
        })

    def action(self, op='file_read', state='v1', after=None, sub=None, plan_rev='p1', goal_rev='g1',
               category='tool', outcome='success', reason=None, **extra):
        n = len(self.events) + 1
        identity = dict(
            action_id=f'a{n}',
            category=category,
            operation=op,
            arguments_hash=f'{op}-{n}',
            goal_revision=goal_rev,
            plan_revision=plan_rev,
            target=op,
            sub_goal_id=sub,
            reason=reason
        )
        identity.update(extra)
        start = self.emit('action_start', before_state=state, **identity)
        result = self.emit('action_result', before_state=state, after_state=after or state,
                           observation_hash=f'obs-{n}', outcome=outcome, duration_seconds=0.1, **identity)
        return start, result

    def verify(self, criterion='c1', sub='s1', verdict='PASS', state='v1', goal_rev='g1', scope='criterion'):
        return self.emit(
            'verification',
            goal_revision=goal_rev,
            sub_goal_id=sub,
            after_state=state,
            evidence_refs=['evidence-check-ref'],
            data={'scope': scope, 'criterion_id': criterion, 'verdict': verdict, 'independent': True}
        )

    def report(self):
        return analyze(self.events, self.run_id)


def test_all_subgoals_freshly_verified_with_unmapped_telemetry():
    """
    Condition: 3/3 sub-goals verified with fresh evidence, but unmapped tool actions exist.
    Expected:
    - Task verification status: 'verified_passed'
    - Workflow evidence completeness: 'partial'
    - Sub-goal mapping coverage: captures mapped vs unmapped actions cleanly.
    - Partial evidence reasons explicitly explain unmapped activity.
    """
    t = Trace()
    t.goal()
    t.plan()

    # Unmapped initial discovery actions
    t.action(op='inspect_environment', state='v0', after='v0', sub=None)
    t.action(op='read_config', state='v0', after='v0', sub=None)

    # Sub-goal 1, 2, 3 actions
    t.action(op='file_write', state='v0', after='v1', sub='s1')
    t.action(op='file_write', state='v1', after='v2', sub='s2')
    t.action(op='file_write', state='v2', after='v3', sub='s3')

    # All sub-goals freshly verified against final state v3
    t.verify(criterion='c1', sub='s1', verdict='PASS', state='v3')
    t.verify(criterion='c2', sub='s2', verdict='PASS', state='v3')
    t.verify(criterion='c3', sub='s3', verdict='PASS', state='v3')

    rep = t.report()

    # Distinct concepts
    assert rep['task_verification_status'] == 'verified_passed'
    assert rep['workflow_evidence_completeness'] == 'partial'
    assert rep['evidence_status'] == 'partial'

    # Subgoals 3/3 verified
    assert rep['summary']['verified_sub_goals'] == 3
    assert rep['summary']['required_sub_goals'] == 3
    assert rep['summary']['progress_rate'] == 1.0

    # Sub-goal mapping coverage
    cov = rep['sub_goal_mapping_coverage']
    assert cov['total_actions'] == 5
    assert cov['mapped_actions'] == 3
    assert cov['unmapped_actions'] == 2
    assert cov['mapped_percentage'] == 60.0
    assert cov['unmapped_percentage'] == 40.0
    assert len(cov['unmapped_details']) == 2

    # Explanation explains the unmapped portion
    assert any('outside sub-goal scopes' in r for r in rep['partial_evidence_reasons'])


def test_missing_prerequisite_evidence():
    """
    Condition: Step 2 started when prerequisite Step 1 was never verified.
    Expected: finding identifies prerequisite as not_checked or unverified with clear reason and action.
    """
    t = Trace()
    t.goal()
    t.plan()

    # Step 2 starts immediately without Step 1 being verified
    t.action(op='file_write', state='v0', after='v1', sub='s2')
    rep = t.report()

    findings = [f for f in rep['findings'] if f['kind'] == 'plan_dependency_unverified']
    assert len(findings) == 1
    f = findings[0]
    assert f['prerequisite_step'] in (1, '1')
    assert f['dependent_step'] in (2, '2')
    assert f['status'] in ('not_checked', 'unverified')
    assert 'Step 1' in f['title']
    assert len(f['reason']) > 0
    assert len(f['recommended_action']) > 0


def test_stale_prerequisite_evidence():
    """
    Condition: Step 1 was verified at v1, but workspace modified to v2 before Step 2 starts.
    Expected: finding identifies prerequisite as 'stale'.
    """
    t = Trace()
    t.goal()
    t.plan()

    # Step 1 verified at v1
    t.action(op='file_write', state='v0', after='v1', sub='s1')
    t.verify(criterion='c1', sub='s1', verdict='PASS', state='v1')

    # Unscoped or subsequent write changes workspace state to v2
    t.action(op='file_write', state='v1', after='v2', sub=None)

    # Step 2 starts under state v2
    t.action(op='file_write', state='v2', after='v3', sub='s2')
    rep = t.report()

    findings = [f for f in rep['findings'] if f['kind'] == 'plan_dependency_unverified']
    assert len(findings) == 1
    f = findings[0]
    assert f['status'] == 'stale'
    assert 'stale' in f['reason'].lower()
    assert 're-run verification' in f['recommended_action'].lower()


def test_genuinely_failed_prerequisite():
    """
    Condition: Step 1 failed independent verification, but Step 2 was started anyway.
    Expected: finding identifies prerequisite as 'failed'.
    """
    t = Trace()
    t.goal()
    t.plan()

    # Step 1 attempted and verified FAIL at v1
    t.action(op='file_write', state='v0', after='v1', sub='s1')
    t.verify(criterion='c1', sub='s1', verdict='FAIL', state='v1')

    # Step 2 starts
    t.action(op='file_write', state='v1', after='v2', sub='s2')
    rep = t.report()

    findings = [f for f in rep['findings'] if f['kind'] == 'plan_dependency_unverified']
    assert len(findings) == 1
    f = findings[0]
    assert f['status'] == 'failed'
    assert 'failed' in f['reason'].lower()
    assert 'failing' in f['recommended_action'].lower()


def test_prerequisite_passes_with_fresh_evidence():
    """
    Condition: Step 1 verified with fresh evidence at current state, Step 2 starts.
    Expected: No false dependency warning emitted.
    """
    t = Trace()
    t.goal()
    t.plan()

    # Step 1 verified PASS at v1
    t.action(op='file_write', state='v0', after='v1', sub='s1')
    t.verify(criterion='c1', sub='s1', verdict='PASS', state='v1')

    # Step 2 starts at v1
    t.action(op='file_write', state='v1', after='v1', sub='s2')
    rep = t.report()

    # No dependency finding for Step 1 -> Step 2!
    step_findings = [f for f in rep['findings'] if f['kind'] in ('plan_dependency_unverified', 'dependency_unverified')]
    assert len(step_findings) == 0


def test_duplicate_findings_deduplicated_during_repeated_actions():
    """
    Condition: Step 2 executes 5 tool actions while prerequisite Step 1 remains unverified.
    Expected: Exactly 1 deduplicated finding with occurrence_count == 5 and all 5 event IDs recorded.
    """
    t = Trace()
    t.goal()
    t.plan()

    # 5 actions performed in Step 2 while Step 1 was not verified
    for i in range(5):
        t.action(op=f'tool_call_{i}', state='v0', after='v0', sub='s2')

    rep = t.report()
    findings = [f for f in rep['findings'] if f['kind'] == 'plan_dependency_unverified']
    assert len(findings) == 1
    f = findings[0]
    assert f['occurrence_count'] == 5
    assert len(f['event_ids']) == 5


def test_distinct_findings_not_deduplicated():
    """
    Condition: Two separate dependency violations occur (Step 1->Step 2, and Step 2->Step 3).
    Expected: Both distinct findings are preserved.
    """
    t = Trace()
    t.goal()
    t.plan()

    # Step 2 started without Step 1
    t.action(op='tool_step_2', state='v0', after='v0', sub='s2')
    # Step 3 started without Step 2
    t.action(op='tool_step_3', state='v0', after='v0', sub='s3')

    rep = t.report()
    findings = [f for f in rep['findings'] if f['kind'] == 'plan_dependency_unverified']
    assert len(findings) == 2
    targets = {str(f.get('dependent_step')) for f in findings}
    assert targets == {'2', '3'}


def test_empty_or_missing_finding_descriptions_gracefully_handled():
    """
    Condition: A finding is triggered with minimal or empty messages.
    Expected: System supplies default readable title, status, reason, and recommended action.
    """
    t = Trace()
    t.goal()
    # Trigger repetition finding with identical arguments_hash
    t.action(op='inspect', state='v1', after='v1', arguments_hash='same')
    t.action(op='inspect', state='v1', after='v1', arguments_hash='same')

    rep = t.report()
    findings = [f for f in rep['findings'] if f['kind'] == 'repetition']
    assert len(findings) == 1
    f = findings[0]
    assert bool(f['title'])
    assert bool(f['reason'])
    assert bool(f['status'])
    assert bool(f['recommended_action'])
