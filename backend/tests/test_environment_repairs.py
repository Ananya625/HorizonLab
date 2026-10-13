from pathlib import Path
from app.services.test_runner_service import test_runner_service


def test_runner_does_not_load_parent_pytest_configuration(run, tmp_path):
    repo = Path(run.repo_path)
    (tmp_path / 'pytest.ini').write_text('[pytest]\naddopts = --invalid-parent-option\n')
    (repo / 'tests').mkdir()
    (repo / 'tests/test_value.py').write_text('def test_value(): assert 2 + 3 == 5\n')
    result = test_runner_service.run_tests(run.run_id)
    assert result.status == 'PASSED', result.stderr
    assert result.passed_tests == 1
