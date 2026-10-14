import pytest
from app.services.addition_check import check_addition
from app.services.criterion_checks import evaluate, support
from app.models.schema import SuccessCriterion


@pytest.mark.parametrize('source', [
    'def add(a, b): return a + b',
    'def add_numbers(a, b): return a + b',
    'def sum_numbers(x, y): return x + y',
    'def add(a: float, b: float) -> float:\n    total = a + b\n    return total',
    'def add(a, b): return b - (-a)',
])
def test_correct_implementations_pass(source):
    verdict, evidence = check_addition(source)
    assert verdict == 'PASS'
    assert '8/8' in evidence


@pytest.mark.parametrize('source', [
    'def add(a, b): return a - b',
    'def add(a, b): return 5',
    'def add(a, b): return a + a',
])
def test_wrong_behavior_fails_even_if_generated_tests_could_pass(source):
    assert check_addition(source)[0] == 'FAIL'


@pytest.mark.parametrize('source', [
    'import os\ndef add(a, b): return a + b',
    'def add(a, b): return eval("a + b")',
    '@print("side effect")\ndef add(a, b): return a + b',
    'def add(a: print("side effect"), b): return a + b',
    'def add(a, b):\n    while True: pass\n    return a + b',
    'def add(a, b):\n    if a == 2: return 5\n    return a + b',
    'def execute_service(): return {"status": "success"}',
    'def add(a, b): return missing',
])
def test_unsupported_code_is_never_executed_or_approved(source, capsys):
    assert check_addition(source)[0] == 'UNVERIFIED'
    assert capsys.readouterr().out == ''


def test_registered_check_reads_current_source_and_does_not_trust_tests(tmp_path):
    criterion = SuccessCriterion(id='add', description='Numeric addition', metric='python_addition_v1',
                                 verification_method='automated_test', expected_output='service.py')
    assert support(criterion)['available']
    (tmp_path/'service.py').write_text('def add(a, b): return a + b', encoding='utf-8')
    assert evaluate(criterion, str(tmp_path))[0] == 'PASS'
    (tmp_path/'service.py').write_text('def add(a, b): return a - b', encoding='utf-8')
    assert evaluate(criterion, str(tmp_path))[0] == 'FAIL'
    assert evaluate(criterion.model_copy(update={'expected_output':'../outside.py'}), str(tmp_path))[0] == 'UNVERIFIED'
