import sqlite3
import pytest
from app.result_maintenance import clear_saved_results


def test_cleanup_preserves_budget_and_backup_restores_results(database, run, tmp_path):
    with database._get_connection() as conn:
        conn.execute('INSERT INTO benchmark_pilot_budgets VALUES (?, ?)', ('approved', '{"halted":true}'))
    backup = tmp_path / 'recovery.sqlite3'
    removed = clear_saved_results(database.db_path, backup)
    assert removed['runs'] == 1
    with sqlite3.connect(database.db_path) as conn:
        assert conn.execute('SELECT count(*) FROM runs').fetchone()[0] == 0
        assert conn.execute('SELECT data_json FROM benchmark_pilot_budgets').fetchone()[0] == '{"halted":true}'
    with sqlite3.connect(backup) as conn:
        assert conn.execute('SELECT count(*) FROM runs').fetchone()[0] == 1
    with pytest.raises(ValueError):
        clear_saved_results(database.db_path, backup)


def test_cleanup_refuses_missing_database(tmp_path):
    with pytest.raises(ValueError):
        clear_saved_results(tmp_path/'missing.sqlite3', tmp_path/'backup.sqlite3')
    assert not (tmp_path/'missing.sqlite3').exists()
