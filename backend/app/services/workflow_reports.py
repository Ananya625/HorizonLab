from fastapi import HTTPException
from . import workflow_store
from .workflow_analysis import analyze
from .criterion_checks import support


def workflow_report(db, run_id):
    record = db.get_run_record(run_id)
    if not record:
        raise HTTPException(404, 'Unknown run')
    events = workflow_store.all_events(db, run_id)
    report = analyze(events, run_id, record.metadata.get('execution_mode','unknown'),
                     record.metadata.get('workflow_evidence_partial',False))
    report['verification_support'] = [dict(criterion_id=c.id, description=c.description,
        metric=c.metric, **support(c)) for c in record.goal_model.success_criteria] if record.goal_model else []
    # Read-only recovery of recorded facts, never synthetic action/verification events.
    logs = db.get_execution_logs(run_id)
    requests = [e for e in logs if e.event_type=='model_call']
    results = [e for e in logs if e.event_type=='model_result']
    latest = record.test_results[-1] if record.test_results else None
    report['saved_measurements'] = {
        'source':'Existing stored records; not a reconstructed workflow trace',
        'recorded_tool_log_entries':sum(e.event_type=='tool_call' for e in logs) if logs else None,
        'recorded_model_requests':len(requests) if requests or results else None,
        'recorded_recovery_episodes':len(record.recovery_attempts) if record.recovery_attempts else None,
        'latest_test':{'result_id':latest.id,'reported_status':latest.status,
            'passed':latest.passed_tests,'total':latest.total_tests,'evidence_version':latest.evidence_version,
            'recorded_at':latest.created_at,'freshness':'Not revalidated against the current workspace'} if latest else None,
        'limitations':'Log entries may be incomplete or duplicated. They are not distinct action counts, loop evidence, or independent goal verification.'}
    # Benchmark execution modes are labeled explicitly; no reconstruction from legacy logs.
    return report, events
