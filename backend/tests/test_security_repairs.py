from pathlib import Path
import pytest
from app.services.workspace_service import workspace_service


def test_child_environment_does_not_inherit_secrets(tmp_path, monkeypatch):
    from app.services.test_runner_service import test_runner_service
    for key in ('AWS_SECRET_ACCESS_KEY', 'JWT_SECRET_KEY', 'PYTEST_ADDOPTS', 'AGENTEVAL_DB_PATH'):
        monkeypatch.setenv(key, 'private')
    env = test_runner_service.subprocess_env(tmp_path)
    assert not {'AWS_SECRET_ACCESS_KEY', 'JWT_SECRET_KEY', 'PYTEST_ADDOPTS', 'AGENTEVAL_DB_PATH'} & env.keys()
    assert env['PYTEST_DISABLE_PLUGIN_AUTOLOAD'] == '1'


def test_repository_boundary_and_explicit_allowlist(tmp_path, monkeypatch):
    monkeypatch.delenv('AGENTEVAL_ALLOWED_REPO_ROOTS')
    allowed = Path(workspace_service.root_dir)
    assert workspace_service.validate_repo(str(allowed / 'project')) == str(allowed / 'project')
    for path in (allowed / '..' / 'outside', Path(str(allowed) + '-sibling')):
        with pytest.raises(ValueError, match='allowed workspace'):
            workspace_service.validate_repo(str(path))
    monkeypatch.setenv('AGENTEVAL_ALLOWED_REPO_ROOTS', str(tmp_path))
    assert workspace_service.validate_repo(str(tmp_path / 'explicit')) == str(tmp_path / 'explicit')


def test_cors_is_local_and_without_credentials():
    from app.main import app
    middleware = next(m for m in app.user_middleware if m.cls.__name__ == 'CORSMiddleware')
    assert middleware.kwargs['allow_origins'] == ['http://localhost:5173', 'http://127.0.0.1:5173']
    assert middleware.kwargs['allow_credentials'] is False


def test_runner_rejects_outside_repository_before_subprocess(database, tmp_path, monkeypatch):
    from app.services.test_runner_service import test_runner_service
    monkeypatch.delenv('AGENTEVAL_ALLOWED_REPO_ROOTS')
    database.create_or_update_run('outside', 'task', 'title', 'prompt', str(tmp_path))
    with pytest.raises(ValueError, match='allowed workspace'):
        test_runner_service.run_tests('outside')
