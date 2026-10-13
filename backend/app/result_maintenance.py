"""Explicit local maintenance; never imported by request handlers or test startup."""
import argparse
import sqlite3
from pathlib import Path

# Child records first. Preserve schemas, sequence values and pilot-budget usage.
RESULT_TABLES = (
    'workflow_events', 'benchmark_events', 'benchmark_checkpoints', 'experiment_runs',
    'evaluation_history', 'execution_logs', 'evaluations', 'verifications',
    'recovery_attempts', 'test_results', 'code_changes', 'plans',
    'goal_model_history', 'goal_models', 'runs',
)


def clear_saved_results(database_path, backup_path):
    database_path, backup_path = Path(database_path).resolve(), Path(backup_path).resolve()
    if not database_path.is_file() or database_path == backup_path or backup_path.exists():
        raise ValueError('Use an existing database and a new, distinct backup path')
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    # Read/write existing file only; a typo must not create an empty database.
    with sqlite3.connect(database_path.as_uri() + '?mode=rw', uri=True, timeout=10) as conn:
        conn.execute('PRAGMA foreign_keys=ON')
        if conn.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
            raise ValueError('Database integrity check failed; cleanup refused')
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if 'runs' not in tables:
            raise ValueError('This is not a recognized AgentEval database')
        # Lock out writers while the backup and deletion use the same snapshot.
        conn.execute('BEGIN IMMEDIATE')
        try:
            with sqlite3.connect(database_path.as_uri() + '?mode=ro', uri=True) as reader:
                with sqlite3.connect(backup_path) as backup:
                    reader.backup(backup)
                    if backup.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
                        raise ValueError('Backup integrity check failed')
            removed = {}
            for table in RESULT_TABLES:
                if table in tables:
                    removed[table] = conn.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0]
                    conn.execute(f'DELETE FROM "{table}"')
            if conn.execute('PRAGMA foreign_key_check').fetchall():
                raise ValueError('Cleanup would leave inconsistent references')
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
    return removed


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', required=True)
    parser.add_argument('--backup', required=True)
    parser.add_argument('--clear-saved-results', action='store_true', required=True)
    args = parser.parse_args()
    print(clear_saved_results(args.database, args.backup))
