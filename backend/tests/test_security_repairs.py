from pathlib import Path
import pytest
from app.services.workspace_service import workspace_service


@pytest.mark.asyncio
async def test_planner_uses_stored_repo(run, monkeypatch):
    from app.api.routes import generate_plan, planner_service
    from app.models.schema import StartPlanRequest
    captured = {}
    async def generate(**kwargs):
        captured.update(kwargs)
        return 'plan'
    monkeypatch.setattr(planner_service, 'generate_plan', generate)
    assert await generate_plan(StartPlanRequest(run_id=run.run_id, repo_path='attacker')) == 'plan'
    assert captured['repo_path'] == run.repo_path


def test_digest_does_not_use_write_filename_validation(tmp_path, monkeypatch):
    (tmp_path / 'normal.py').write_text('value = 1')
    def forbidden(*args):
        pytest.fail('Digest must not apply Windows write-name restrictions')
    monkeypatch.setattr(workspace_service, 'resolve_path', forbidden)
    before = workspace_service.digest(str(tmp_path))
    (tmp_path / 'normal.py').write_text('value = 2')
    assert workspace_service.digest(str(tmp_path)) != before


@pytest.mark.parametrize('path', ['../../../README.md', '..\\outside.py', '/absolute.py', 'C:\\outside.py'])
def test_targeted_inspection_rejects_traversal(path):
    with pytest.raises(ValueError):
        workspace_service.inspect_targeted(workspace_service.get_default_repo_path(), [path])


def test_inspection_missing_directory_is_read_only(tmp_path):
    target = tmp_path / 'missing'
    with pytest.raises(ValueError, match='does not exist'):
        workspace_service.inspect_directory(str(target))
    assert not target.exists()


def test_inspection_skips_symlinks(tmp_path):
    repo = tmp_path / 'repo'
    repo.mkdir()
    (repo / 'ok.py').write_text('value = 1')
    try:
        (repo / 'broken.py').symlink_to(tmp_path / 'missing.py')
        (repo / 'outside.py').symlink_to(Path(__file__))
    except OSError:
        pytest.skip('Symlink creation unavailable')
    result = workspace_service.inspect_directory(str(repo))
    assert [f['path'] for f in result['files']] == ['ok.py']


@pytest.mark.parametrize('host', ['http://example.com', 'file:///tmp/model', 'http://localhost@evil.test', 'http://localhost/api', 'http://127.0.0.1:99999', 'http://169.254.169.254'])
def test_ollama_rejects_unapproved_hosts(host):
    from app.services.ollama_service import OllamaService
    service = OllamaService()
    with pytest.raises(ValueError):
        service.update_config(host, 'changed')
    assert service.host == 'http://127.0.0.1:11434'
    assert service.default_model == 'qwen3:1.7b'


def test_ollama_explicit_hosts_and_loopback(monkeypatch):
    from app.services.ollama_service import OllamaService
    monkeypatch.setenv('AGENTEVAL_OLLAMA_HOSTS', 'models.internal')
    for host in ('http://localhost:11434', 'http://[::1]:11434', 'https://models.internal'):
        assert OllamaService(host).host == host


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
