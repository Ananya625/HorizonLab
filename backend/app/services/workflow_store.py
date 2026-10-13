"""SQLite event extension using the project's existing database connection."""
import json
from ..models.workflow import WorkflowEvent


def initialize(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS workflow_events (
        run_id TEXT NOT NULL, sequence INTEGER NOT NULL, event_id TEXT NOT NULL,
        kind TEXT NOT NULL, action_id TEXT, data_json TEXT NOT NULL,
        PRIMARY KEY(run_id, sequence), UNIQUE(run_id, event_id))''')
    conn.execute('''CREATE UNIQUE INDEX IF NOT EXISTS workflow_action_phase
        ON workflow_events(run_id, action_id, kind) WHERE action_id IS NOT NULL
        AND kind IN ('action_start','action_result')''')


def append(db, event, connection=None):
    if not isinstance(event, WorkflowEvent):
        event = WorkflowEvent.model_validate(event)
    encoded = json.dumps(event.model_dump(), sort_keys=True, allow_nan=False)
    if len(encoded.encode()) > 65536:
        raise ValueError('Workflow event exceeds 64 KiB')
    if connection is None:
        with db._get_connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            return append(db, event, conn)
    conn = connection
    row = conn.execute('SELECT sequence,data_json FROM workflow_events WHERE run_id=? AND event_id=?',
                       (event.run_id, event.event_id)).fetchone()
    if row:
        if row['data_json'] != encoded:
            raise ValueError('Existing workflow evidence cannot be rewritten')
        return row['sequence']
    run = conn.execute('SELECT task_id FROM runs WHERE run_id=?', (event.run_id,)).fetchone()
    if not run:
        raise ValueError('Unknown run')
    if event.task_id and event.task_id != run['task_id']:
        raise ValueError('Mismatched task identity')
    if event.parent_action_id and not conn.execute("SELECT 1 FROM workflow_events WHERE run_id=? AND action_id=? AND kind='action_start'", (event.run_id,event.parent_action_id)).fetchone():
        raise ValueError('Unknown parent action for run')
    if event.kind == 'action_result':
        start = conn.execute("SELECT data_json FROM workflow_events WHERE run_id=? AND action_id=? AND kind='action_start'",
                             (event.run_id, event.action_id)).fetchone()
        if not start:
            raise ValueError('Result requires a recorded start')
        started = json.loads(start[0])
        for key in ('category', 'operation', 'goal_revision', 'attempt_id', 'parent_action_id', 'sub_goal_id'):
            if started[key] != getattr(event, key):
                raise ValueError(f'Result identity mismatch: {key}')
    sequence = conn.execute('SELECT COALESCE(MAX(sequence),0)+1 FROM workflow_events WHERE run_id=?',
                            (event.run_id,)).fetchone()[0]
    conn.execute('INSERT INTO workflow_events VALUES (?,?,?,?,?,?)',
                 (event.run_id, sequence, event.event_id, event.kind, event.action_id, encoded))
    return sequence


def read(db, run_id, after=0, limit=100, through=None):
    with db._get_connection() as conn:
        high = conn.execute('SELECT COALESCE(MAX(sequence),0) FROM workflow_events WHERE run_id=?', (run_id,)).fetchone()[0]
        high = min(high, through) if through is not None else high
        rows = conn.execute('SELECT sequence,data_json FROM workflow_events WHERE run_id=? AND sequence>? AND sequence<=? ORDER BY sequence LIMIT ?',
                            (run_id, after, high, limit)).fetchall()
        events = [dict(json.loads(row['data_json']), sequence=row['sequence']) for row in rows]
        return {'events': events, 'snapshot_sequence': high,
                'next_after': events[-1]['sequence'] if events and events[-1]['sequence'] < high else None}


def all_events(db, run_id):
    events, after, high = [], 0, None
    while True:
        page = read(db, run_id, after, 1000, high)
        high = page['snapshot_sequence']
        events.extend(page['events'])
        if page['next_after'] is None:
            return events
        after = page['next_after']
