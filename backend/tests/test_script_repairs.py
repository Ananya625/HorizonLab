from pathlib import Path
import pytest
from pipeline_smoke import isolated_pipeline, run_confirmed


@pytest.mark.asyncio
async def test_script_confirms_then_resumes_same_run(database, monkeypatch):
    from app.services.orchestrator_service import orchestrator_service
    from app.services.goal_parser_service import goal_parser_service
    from types import SimpleNamespace
    calls = []
    async def pipeline(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(run_id='script', goal_model=SimpleNamespace(model_dump_json=lambda **kw:'goal'))
    monkeypatch.setattr(orchestrator_service, 'run_full_pipeline', pipeline)
    monkeypatch.setattr(goal_parser_service, 'confirm_goal_model', lambda rid:calls.append(rid))
    await run_confirmed('task', confirm=lambda _: 'yes')
    assert calls == [{'request_text':'task'}, 'script', {'request_text':'task', 'existing_run_id':'script'}]
    calls.clear()
    with pytest.raises(ValueError, match='declined'):
        await run_confirmed('task', confirm=lambda _: 'no')
    assert calls == [{'request_text':'task'}]


def test_script_storage_is_temporary_and_restored(database):
    from app.services.workspace_service import workspace_service
    before = workspace_service.root_dir
    with isolated_pipeline() as temporary:
        path = Path(temporary.db_path)
        assert path.exists() and path != Path(database.db_path)
        assert Path(workspace_service.root_dir).parent == path.parent
    assert not path.exists()
    assert workspace_service.root_dir == before
