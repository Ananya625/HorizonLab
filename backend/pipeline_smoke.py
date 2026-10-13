"""Safe storage and an explicit human confirmation gate for CLI experiments."""
import os
import sys
import tempfile
from contextlib import contextmanager, ExitStack
from pathlib import Path
from unittest.mock import patch


@contextmanager
def isolated_pipeline():
    scratch = Path(__file__).parent / '.test-tmp'
    scratch.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='pipeline-', dir=scratch) as directory, ExitStack() as stack:
        root = Path(directory)
        stack.enter_context(patch.dict(os.environ, {'AGENTEVAL_DB_PATH': str(root / 'run.sqlite3')}))
        # Import only after the temporary database environment is configured.
        from app.services.db import DatabaseService
        from app.services.orchestrator_service import orchestrator_service  # noqa: F401
        from app.services.workspace_service import workspace_service
        database = DatabaseService(str(root / 'run.sqlite3'))
        for name, module in list(sys.modules.items()):
            if name.startswith('app.') and hasattr(module, 'db_service'):
                stack.enter_context(patch.object(module, 'db_service', database))
        stack.enter_context(patch.object(workspace_service, 'root_dir', str(root / 'sandbox')))
        workspace_service.ensure_default_sandboxes()
        yield database


async def run_confirmed(prompt, confirm=input):
    from app.services.orchestrator_service import orchestrator_service
    from app.services.goal_parser_service import goal_parser_service
    record = await orchestrator_service.run_full_pipeline(request_text=prompt)
    print(record.goal_model.model_dump_json(indent=2))
    if confirm('Confirm this goal and execute generated code? Type yes: ').strip().lower() != 'yes':
        raise ValueError('Goal confirmation declined; no code executed')
    goal_parser_service.confirm_goal_model(record.run_id)
    return await orchestrator_service.run_full_pipeline(request_text=prompt, existing_run_id=record.run_id)
