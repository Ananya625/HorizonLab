import os
import tempfile
import sys
from pathlib import Path
import pytest

# Never initialize/migrate the user's stored database during collection.
# Windows sandbox TEMP can be discoverable but unusable by SQLite/child pytest.
# Keep test-only scratch files within the already-authorized project workspace;
# no ACL changes, administrator privileges, or sandbox disabling are required.
_workspace = Path(__file__).resolve().parents[2]
_scratch = _workspace / 'backend' / '.test-tmp'
_scratch.mkdir(exist_ok=True)
if not _scratch.resolve().is_relative_to(_workspace):
    raise RuntimeError('Test scratch storage must remain inside the workspace')
for _name in ('TEMP', 'TMP', 'TMPDIR'):
    os.environ[_name] = str(_scratch)
tempfile.tempdir = str(_scratch)
_bootstrap = tempfile.TemporaryDirectory(prefix='agenteval-test-db-')
os.environ['AGENTEVAL_DB_PATH'] = str(Path(_bootstrap.name) / 'bootstrap.sqlite3')

from app.services.db import DatabaseService
from app.services import verifier_service, test_runner_service, orchestrator_service
from app.api import routes


@pytest.fixture
def database(tmp_path, monkeypatch):
    db = DatabaseService(str(tmp_path / 'test.sqlite3'))
    for name, module in list(sys.modules.items()):
        if name.startswith('app.') and hasattr(module, 'db_service'):
            monkeypatch.setattr(module, 'db_service', db)
    return db


@pytest.fixture
def run(database, tmp_path):
    repo = tmp_path / 'repo'
    repo.mkdir()
    database.create_or_update_run('r1', 't1', 'Test', 'Test', str(repo))
    return database.get_run_record('r1')


@pytest.fixture(autouse=True)
def isolated_workspace_and_network(tmp_path, monkeypatch):
    import httpx
    from app.services.workspace_service import workspace_service
    monkeypatch.setattr(workspace_service, 'root_dir', str(tmp_path / 'sandbox'))
    workspace_service.ensure_default_sandboxes()

    async def no_async_network(*args, **kwargs):
        raise AssertionError('Tests must mock external HTTP/model requests')

    def no_network(*args, **kwargs):
        raise AssertionError('Tests must mock external HTTP/model requests')

    monkeypatch.setattr(httpx.AsyncHTTPTransport, 'handle_async_request', no_async_network)
    monkeypatch.setattr(httpx.HTTPTransport, 'handle_request', no_network)
