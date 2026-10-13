"""Regression cases for the user's addition request; no external model calls."""
from pathlib import Path
import json
import pytest
from app.services.coder_service import coder_service
from app.services.goal_parser_service import goal_parser_service
from app.services.ollama_service import ollama_service
from app.services.orchestrator_service import orchestrator_service
from app.services.task_router_service import task_router_service, is_basic_addition_request

PROMPT = 'write a python code to add two numbers'


@pytest.mark.parametrize('goal', ['author a utility', 'token counter', 'pool statistics', 'login form'])
def test_loose_keywords_do_not_select_demo_templates(goal):
    assert coder_service.template_kind('app/main.py', goal) is None


@pytest.mark.asyncio
async def test_pool_template_detects_duplicate_simultaneous_handles(monkeypatch):
    import sys
    import types
    impl = types.ModuleType('src.core.connection_pool')
    exec(coder_service._get_deterministic_code('src/core/connection_pool.py', None, None), impl.__dict__)
    monkeypatch.setitem(sys.modules, 'src.core.connection_pool', impl)
    namespace = {}
    exec(coder_service._get_deterministic_code('tests/test_pool_concurrency.py', None, None), namespace)
    await namespace['test_concurrent_socket_acquisition']()
    async def broken_acquire(self):
        return 1
    monkeypatch.setattr(impl.ConnectionPool, 'acquire', broken_acquire)
    with pytest.raises(AssertionError, match='Duplicate simultaneously'):
        await namespace['test_concurrent_socket_acquisition']()


@pytest.mark.parametrize('source', [
    "def execute_service( ): return {'status':'success'}",
    "def renamed(): return dict_placeholder",  # replaced below with an actual metadata dictionary
    'def add(a, b): pass',
    'def add(a, b): ...',
])
def test_structural_placeholder_guard(source):
    from app.services.coder_service import reject_placeholder_code
    source = source.replace('dict_placeholder', "{'task': 'add', 'status': 'ok'}")
    with pytest.raises(ValueError, match='placeholder'):
        reject_placeholder_code(source)
    reject_placeholder_code('def add(a, b): return a + b')


@pytest.mark.parametrize('wrap', [lambda s: {'content':s}, lambda s: {'tests/test_service.py':{'code':s}}])
def test_json_fenced_python_is_decoded_before_extraction(wrap):
    from app.services.coder_service import extract_clean_python_code
    source = 'from app.service import add\ndef test_add():\n    assert add(2, 3) == 5'
    cleaned = extract_clean_python_code(json.dumps(wrap('```python\n' + source + '\n```')))
    assert cleaned == source
    compile(cleaned, 'tests/test_service.py', 'exec')


@pytest.mark.asyncio
@pytest.mark.parametrize('metadata', [{'done_reason':'length','done':True}, {'done':False}])
async def test_truncated_generation_is_rejected_even_when_prefix_compiles(database, monkeypatch, metadata):
    goal = await goal_parser_service.parse_request(PROMPT)
    calls = []
    async def completion(**kwargs):
        calls.append(kwargs)
        return {'message':{'content':'def add(a, b): return a + b'}, **metadata}
    monkeypatch.setattr(ollama_service, 'chat_completion', completion)
    with pytest.raises(RuntimeError, match='incomplete or reached its output limit'):
        await coder_service._generate_code_for_file('app/service.py','create','add',None,goal,None,None,0,goal.run_id)
    assert len(calls) == 1  # No automatic generation retry.
    assert calls[0]['num_predict'] == 1000


@pytest.mark.asyncio
async def test_invalid_tests_preserve_diagnostic_without_claiming_connection_failure(database, monkeypatch):
    goal = await goal_parser_service.parse_request(PROMPT)
    raw = 'from app.service import add\ndef test_add(:'
    async def completion(**kwargs):
        return {'message':{'content':raw}, 'done':True, 'done_reason':'stop'}
    monkeypatch.setattr(ollama_service, 'chat_completion', completion)
    with pytest.raises(RuntimeError, match='invalid at line 2') as error:
        await coder_service._generate_code_for_file('tests/test_service.py','test','add',None,goal,None,None,0,goal.run_id)
    assert 'Check the selected Ollama model and connection' not in str(error.value)
    logs = database.get_execution_logs(goal.run_id)
    diagnostic = next(entry for entry in logs if entry.event_type == 'error')
    assert diagnostic.details['rejected_output'] == raw
    assert diagnostic.details['line'] == 2


@pytest.mark.asyncio
async def test_simple_requirements_need_no_model_and_still_require_confirmation(database, monkeypatch):
    async def forbidden(**kwargs):
        pytest.fail('Simple requirement parsing must not call a model')
    monkeypatch.setattr(ollama_service, 'chat_completion', forbidden)
    goal = await goal_parser_service.parse_request(PROMPT)
    assert goal.main_goal == PROMPT
    assert not goal.ambiguities
    assert not goal.is_confirmed
    assert 'add(a, b)' in goal.expected_output.schema_summary
    assert task_router_service.route_task(goal.main_goal, '').use_fast_path


@pytest.mark.parametrize('text', [PROMPT + ' and build a login API', PROMPT + ' from a database', 'fix arithmetic in the payment service'])
def test_compound_requests_do_not_use_narrow_requirement_shortcut(text):
    assert not is_basic_addition_request(text)


@pytest.mark.asyncio
async def test_requirement_timeout_and_no_invented_blocking_coverage(database, monkeypatch):
    calls = []
    async def timeout(**kwargs):
        calls.append(kwargs)
        raise TimeoutError('fixture timeout')
    monkeypatch.setattr(ollama_service, 'chat_completion', timeout)
    goal = await goal_parser_service.parse_request('Build an image utility', model_name='selected-model')
    assert calls[0]['timeout'] == 15
    assert calls[0]['model'] == 'selected-model'
    assert not goal.ambiguities
    assert not goal.is_confirmed


@pytest.mark.asyncio
@pytest.mark.parametrize('response', [None, '', 'return 1', 'def add(:'])
async def test_failed_generation_does_not_write_placeholder(database, monkeypatch, response):
    prepared = await orchestrator_service.run_full_pipeline(PROMPT, model_name='selected-model')
    goal_parser_service.confirm_goal_model(prepared.run_id)
    path = Path(prepared.repo_path) / 'app' / 'service.py'
    original = path.read_bytes() if path.exists() else None
    async def completion(**kwargs):
        if response is None:
            raise ConnectionError('provider unavailable')
        return {'message': {'content': response}}
    monkeypatch.setattr(ollama_service, 'chat_completion', completion)
    with pytest.raises(RuntimeError, match='No placeholder was written'):
        await orchestrator_service.run_full_pipeline(PROMPT, existing_run_id=prepared.run_id, max_recovery_retries=0)
    assert (path.read_bytes() if path.exists() else None) == original
    assert database.get_run_record(prepared.run_id).evaluation.outcome == 'error'


@pytest.mark.asyncio
async def test_addition_pipeline_imports_actual_code_and_preserves_selected_model(database, monkeypatch):
    prepared = await orchestrator_service.run_full_pipeline(PROMPT, model_name='selected-model')
    goal_parser_service.confirm_goal_model(prepared.run_id)
    calls = []
    async def completion(**kwargs):
        calls.append(kwargs)
        prompt = kwargs['messages'][-1]['content']
        assert 'add(a, b)' in prompt
        code = ('from app.service import add\n'
                'def test_add():\n'
                '    assert add(2, 3) == 5\n'
                '    assert add(-4, 2) == -2\n'
                '    assert add(0, 0) == 0\n'
                '    assert add(1.5, 2.5) == 4\n'
                if 'File to write: tests/' in prompt else 'def add(a, b):\n    return a + b\n')
        return {'message': {'content': code}}
    monkeypatch.setattr(ollama_service, 'chat_completion', completion)
    result = await orchestrator_service.run_full_pipeline(PROMPT, existing_run_id=prepared.run_id, max_recovery_retries=0)
    assert len(calls) == 2
    assert all(c['model'] == 'selected-model' for c in calls)
    assert result.test_results[-1].passed_tests == 1
    assert result.test_results[-1].failed_tests == 0
    assert len(result.code_changes) == 2
    assert result.evaluation.verified_success is True  # Evaluator-owned behavior checks are independent of generated tests.
    assert 'python_addition_v1: 8/8' in result.verification.criteria_evaluations[1].evidence
    # Existing public interfaces remain available to callers.
    assert coder_service._get_deterministic_code('app/service.py', result.goal_model, None) is None


@pytest.mark.asyncio
@pytest.mark.parametrize('code', [
    'def add(a, b): return a + b\ndef test_add(): assert add(2, 3) == 5',
    'from app.service import add\ndef add(a, b): return 5\ndef test_add(): assert add(2, 3) == 5',
])
async def test_tests_cannot_replace_implementation_with_a_local_copy(database, monkeypatch, code):
    goal = await goal_parser_service.parse_request(PROMPT)
    async def completion(**kwargs):
        return {'message': {'content': code}}
    monkeypatch.setattr(ollama_service, 'chat_completion', completion)
    with pytest.raises(RuntimeError, match='Generated tests'):
        await coder_service._generate_code_for_file('tests/test_service.py', 'test', 'test addition', None,
            goal, None, None, 0, goal.run_id, {'app/service.py': 'def add(a, b): return a + b'})


@pytest.mark.asyncio
async def test_demo_template_cannot_replace_existing_implementation(database, monkeypatch):
    goal = await goal_parser_service.parse_request(PROMPT)
    goal = goal.model_copy(update={'main_goal': 'Update authentication'})
    monkeypatch.setattr(coder_service, '_get_deterministic_code', lambda *args: 'def login(): return True')
    async def unavailable(**kwargs):
        raise ConnectionError('provider unavailable')
    monkeypatch.setattr(ollama_service, 'chat_completion', unavailable)
    with pytest.raises(RuntimeError, match='provider unavailable'):
        await coder_service._generate_code_for_file('app/auth.py', 'modify', 'Preserve login interface',
            'def login(user, password): return False', goal, None, None, 0, goal.run_id)


@pytest.mark.asyncio
async def test_passing_generated_tests_cannot_approve_wrong_addition(database, monkeypatch):
    prepared = await orchestrator_service.run_full_pipeline(PROMPT)
    goal_parser_service.confirm_goal_model(prepared.run_id)
    async def completion(**kwargs):
        code = ('from app.service import add\ndef test_add(): assert add(2, 3) == -1'
                if 'File to write: tests/' in kwargs['messages'][-1]['content']
                else 'def add(a, b): return a - b')
        return {'message': {'content': code}}
    monkeypatch.setattr(ollama_service, 'chat_completion', completion)
    result = await orchestrator_service.run_full_pipeline(PROMPT, existing_run_id=prepared.run_id, max_recovery_retries=0)
    assert result.test_results[-1].status == 'PASSED'
    assert result.verification.criteria_evaluations[1].verdict == 'FAIL'
    assert result.evaluation.verified_success is False
