import pytest
from app.models.schema import Constraint, CodeChange

def test_constraint_verification_preserves_assertions():
    hc = Constraint(id="HC-1", text="Never delete, comment out, or skip existing test assertions to force a pass", is_hard=True)
    
    # Passing case: diff adds assertions without deletions
    clean_change = CodeChange(
        id="c1",
        run_id="r1",
        file_path="tests/test_service.py",
        action="created",
        new_content="def test_add(): assert 1 + 1 == 2",
        diff_patch="+def test_add():\n+    assert 1 + 1 == 2\n",
        lines_added=2,
        lines_removed=0,
        ast_valid=True
    )
    from app.services.verifier_service import verifier_service
    res = verifier_service._verify_constraint(hc, [clean_change], [], None)
    assert res.compliant is True
    assert res.status == "compliant"

    # Failing case: diff removes an assertion that is not replaced
    violation_change = CodeChange(
        id="c2",
        run_id="r1",
        file_path="tests/test_service.py",
        action="modified",
        new_content="def test_add(): pass",
        diff_patch="-    assert 1 + 1 == 2\n+    pass\n",
        lines_added=1,
        lines_removed=1,
        ast_valid=True
    )
    res_fail = verifier_service._verify_constraint(hc, [violation_change], [], None)
    assert res_fail.compliant is False
    assert res_fail.status == "violated"

def test_constraint_verification_plaintext_secrets():
    hc = Constraint(id="HC-3", text="Never commit plaintext API secrets, credentials, or private keys to source code", is_hard=True)
    
    # Clean code
    clean_change = CodeChange(
        id="c1",
        run_id="r1",
        file_path="app/service.py",
        action="created",
        new_content="def get_user(): return 'ok'",
        diff_patch="+def get_user(): return 'ok'\n",
        lines_added=1,
        lines_removed=0,
        ast_valid=True
    )
    from app.services.verifier_service import verifier_service
    res = verifier_service._verify_constraint(hc, [clean_change], [], None)
    assert res.compliant is True
    assert res.status == "compliant"

    # Secret leaked
    leaked_change = CodeChange(
        id="c2",
        run_id="r1",
        file_path="app/service.py",
        action="created",
        new_content="api_key = 'sk-1234567890abcdef1234567890'",
        diff_patch="+api_key = 'sk-1234567890abcdef1234567890'\n",
        lines_added=1,
        lines_removed=0,
        ast_valid=True
    )
    res_leak = verifier_service._verify_constraint(hc, [leaked_change], [], None)
    assert res_leak.compliant is False
    assert res_leak.status == "violated"

def test_constraint_verification_pep8_clean_code():
    sc = Constraint(id="SC-1", text="Maintain clean modular code adhering to standard PEP 8 / Clean Code conventions", is_hard=False)
    
    clean_change = CodeChange(
        id="c1",
        run_id="r1",
        file_path="app/service.py",
        action="created",
        new_content="def sum_numbers(a: int, b: int) -> int:\n    return a + b\n",
        diff_patch="+def sum_numbers(a: int, b: int) -> int:\n+    return a + b\n",
        lines_added=2,
        lines_removed=0,
        ast_valid=True
    )
    from app.services.verifier_service import verifier_service
    res = verifier_service._verify_constraint(sc, [clean_change], [], None)
    assert res.compliant is True
    assert res.status == "compliant"

def test_constraint_verification_docstrings_and_annotations():
    sc = Constraint(id="SC-2", text="Include clear docstrings and typing annotations on newly created functions", is_hard=False)
    
    # Function with docstrings and annotations
    documented_change = CodeChange(
        id="c1",
        run_id="r1",
        file_path="app/service.py",
        action="created",
        new_content="def calculate(x: int) -> int:\n    '''Calculate square.'''\n    return x * x\n",
        diff_patch="+def calculate(x: int) -> int:\n+    '''Calculate square.'''\n+    return x * x\n",
        lines_added=3,
        lines_removed=0,
        ast_valid=True
    )
    from app.services.verifier_service import verifier_service
    res = verifier_service._verify_constraint(sc, [documented_change], [], None)
    assert res.compliant is True
    assert res.status == "compliant"
