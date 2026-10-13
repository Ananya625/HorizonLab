from pathlib import Path
from app.services.test_runner_service import test_runner_service
import pytest


@pytest.mark.parametrize('mode', ['module', 'script'])
def test_entrypoint_resolves_package_and_binds_loopback(monkeypatch, mode):
    import runpy
    import uvicorn
    calls = []
    monkeypatch.setattr(uvicorn, 'run', lambda *args, **kwargs: calls.append((args, kwargs)))
    if mode == 'module':
        runpy.run_module('app.main', run_name='__main__')
    else:
        runpy.run_path(str(Path(__file__).parents[1] / 'app/main.py'), run_name='__main__')
    assert calls[0][0] == ('app.main:app',)
    assert calls[0][1]['host'] == '127.0.0.1'


@pytest.mark.parametrize('word', ['block', 'trace', 'author', 'hashtag'])
def test_router_does_not_match_keyword_substrings(word):
    from app.services.task_router_service import task_router_service
    result = task_router_service.route_task(f'Implement a helper function for {word}', '')
    assert not result.security_sensitive
    assert not result.concurrency_sensitive
    assert result.task_tier == 'simple'


def test_router_uses_configured_default(monkeypatch):
    from app.services.task_router_service import task_router_service
    from app.services.ollama_service import ollama_service
    monkeypatch.setattr(ollama_service, 'default_model', 'configured')
    assert task_router_service.route_task('JWT authentication', '').model_name == 'configured'


@pytest.mark.asyncio
async def test_async_recovery_runner_keeps_event_loop_responsive(monkeypatch):
    import asyncio
    import threading
    from types import SimpleNamespace
    from app.services.debugger_service import debugger_service
    entered, released = threading.Event(), threading.Event()
    def blocking(**kwargs):
        entered.set()
        assert released.wait(2), 'Event loop was blocked by test execution'
        return SimpleNamespace(status='PASSED')
    monkeypatch.setattr(test_runner_service, 'run_tests', blocking)
    task = asyncio.create_task(debugger_service.run_testing_and_recovery_loop('fixture'))
    while not entered.is_set():
        await asyncio.sleep(0.001)
    released.set()
    assert (await task)['local_tests_passed'] is True


def test_latest_logs_advance_beyond_two_hundred(database, run):
    for i in range(205):
        database.add_log(run.run_id, 'test', 'Fixture', 'info', str(i))
    logs = database.get_execution_logs(run.run_id, limit=200)
    assert [log.message for log in logs] == [str(i) for i in range(5, 205)]
    assert [log.message for log in database.get_execution_logs(run.run_id, limit=2, offset=200)] == ['3', '4']


def test_foreign_keys_reject_orphans_and_cascade(database, run):
    import sqlite3
    import pytest
    database.add_log(run.run_id, 'test', 'Fixture', 'info', 'child')
    with database._get_connection() as conn:
        assert conn.execute('PRAGMA foreign_keys').fetchone()[0] == 1
        conn.execute('DELETE FROM runs WHERE run_id=?', (run.run_id,))
    assert database.get_execution_logs(run.run_id) == []
    with pytest.raises(sqlite3.IntegrityError):
        with database._get_connection() as conn:
            conn.execute("INSERT INTO goal_models (run_id, data_json, created_at, updated_at) VALUES ('missing', '{}', 'now', 'now')")


def test_recovery_migration_runs_once_and_is_idempotent(tmp_path):
    import sqlite3
    from app.services.db import DatabaseService
    path = tmp_path / 'legacy.sqlite3'
    with sqlite3.connect(path) as conn:
        conn.execute('CREATE TABLE recovery_attempts (id TEXT PRIMARY KEY)')
    first = DatabaseService(str(path))
    DatabaseService(str(path))
    with first._get_connection() as conn:
        columns = {row[1] for row in conn.execute('PRAGMA table_info(recovery_attempts)')}
    assert {'error_summary', 'subsequent_test_run_id', 'test_result_status', 'data_json'} <= columns


def test_runner_does_not_load_parent_pytest_configuration(run, tmp_path):
    repo = Path(run.repo_path)
    (tmp_path / 'pytest.ini').write_text('[pytest]\naddopts = --invalid-parent-option\n')
    (repo / 'tests').mkdir()
    (repo / 'tests/test_value.py').write_text('def test_value(): assert 2 + 3 == 5\n')
    result = test_runner_service.run_tests(run.run_id)
    assert result.status == 'PASSED', result.stderr
    assert result.passed_tests == 1

