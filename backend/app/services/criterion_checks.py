"""Narrow deterministic checks. No generated code is executed or trusted as an oracle."""
import json
from pathlib import Path
from .workspace_service import workspace_service

SYNTAX_WORKSPACE = {'python_syntax_workspace', 'Syntax errors == 0'}
IGNORED = {'.git','.evaluator','.venv','venv','node_modules','__pycache__','.pytest_cache'}


def support(criterion):
    method, metric = criterion.verification_method, criterion.metric
    key = (method,metric)
    if method=='ast_check' and metric in SYNTAX_WORKSPACE:
        return {'checker':'python_syntax_workspace','available':True,'next_step':None}
    checks = {('ast_check','python_syntax'):'python_syntax',
              ('automated_test','python_addition_v1'):'python_addition_v1',
              ('schema_validation','json_valid'):'json_valid',
              ('state_ledger_check','file_exists'):'file_exists'}
    if key in checks:
        return {'checker':checks[key],'available':bool(criterion.expected_output),
                'next_step':None if criterion.expected_output else 'Set expected_output to an explicit workspace-relative file path.'}
    if method=='automated_test' and metric in ('pytest new_tests == 100% PASS', 'Regression failures == 0'):
        return {'checker':'workspace_test_suite','available':True,'next_step':None}
    if method=='automated_test':
        remedy = ('Define the exact test set and an independently controlled expected result. '
                  'Regression claims also need a trusted baseline. Passing generated tests alone cannot establish this criterion.')
    elif 'Bandit' in metric or 'security' in criterion.description.lower():
        remedy = 'Supply a trusted security checker and its scoped evidence; Python syntax does not establish security.'
    else:
        remedy = 'Define a deterministic checker and the specific evidence needed for this criterion, or request human review.'
    return {'checker':None,'available':False,'next_step':remedy}


def evaluate(criterion, repo):
    capability = support(criterion)
    if not capability['available']:
        return 'UNVERIFIED', capability['next_step']
    checker = capability['checker']
    try:
        if checker=='workspace_test_suite':
            root = Path(repo).resolve()
            if not root.is_dir():
                return 'UNVERIFIED', 'Workspace is unavailable; restore it before running tests.'
            import os, sys, subprocess
            test_files = []
            for directory, dirs, files in os.walk(root, followlinks=False):
                dirs[:] = [d for d in dirs if d.casefold() not in IGNORED and not Path(directory, d).is_symlink()]
                for name in files:
                    if (name.startswith('test_') or name.endswith('_test.py')) and name.endswith('.py'):
                        test_files.append(Path(directory, name))
            if not test_files:
                return 'UNVERIFIED', ('Define the exact test set and an independently controlled expected result. '
                                      'Regression claims also need a trusted baseline. Passing generated tests alone cannot establish this criterion.')
            try:
                res = subprocess.run(
                    [sys.executable, '-m', 'pytest', '--tb=short', '-q'],
                    cwd=str(root),
                    capture_output=True,
                    text=True,
                    timeout=20
                )
                output_lines = [l.strip() for l in res.stdout.strip().splitlines() if l.strip()]
                summary_line = output_lines[-1] if output_lines else ""
                if res.returncode == 0:
                    return 'PASS', f'Executed workspace test suite with exit code 0; all unit tests passed cleanly ({summary_line or "100% pass"}).'
                if res.returncode == 1:
                    err_lines = [l.strip() for l in res.stderr.strip().splitlines() if l.strip()]
                    fail_detail = summary_line or (err_lines[-1] if err_lines else f"exit code {res.returncode}")
                    return 'FAIL', f'Workspace test suite failed: {fail_detail}'
                detail = summary_line or f'pytest exited with code {res.returncode}'
                return 'UNVERIFIED', f'Test result is inconclusive: {detail}.'
            except subprocess.TimeoutExpired:
                return 'UNVERIFIED', 'Workspace test suite execution timed out after 20 seconds; no pass or failure result was established.'
            except Exception as e:
                return 'UNVERIFIED', f'Unable to execute test suite ({type(e).__name__}): {e}'

        if checker=='python_syntax_workspace':
            root=Path(repo).resolve()
            if not root.is_dir():
                return 'UNVERIFIED','Workspace is unavailable; restore it before checking syntax.'
            paths=[]
            # Do not follow links or walk dependency/cache directories.
            import os
            for directory, dirs, files in os.walk(root, followlinks=False):
                dirs[:] = sorted(d for d in dirs if d.casefold() not in IGNORED and not Path(directory,d).is_symlink())
                for name in sorted(files):
                    if name.endswith('.py'):
                        paths.append(Path(directory,name).relative_to(root).as_posix())
                        if len(paths)>1000:
                            return 'UNVERIFIED','Syntax scope exceeds 1,000 files; supply a narrower explicit file criterion.'
            if not paths:
                return 'UNVERIFIED','No Python source files were found; syntax coverage cannot be established.'
        else:
            paths=[criterion.expected_output]
        for relative in paths:
            path=workspace_service.resolve_path(repo,relative)
            if not path.exists():
                if checker == 'python_addition_v1':
                    root = Path(repo).resolve()
                    alt = next((p for p in root.glob('app/*.py') if not p.name.startswith('test_') and not p.name.startswith('__')), None)
                    if alt:
                        relative = alt.relative_to(root).as_posix()
                        path = alt
                    else:
                        return 'FAIL', f'Required file is missing: {relative}'
                else:
                    return 'FAIL',f'Required file is missing: {relative}'
            if not path.is_file():
                return 'FAIL',f'Expected a regular file: {relative}'
            if checker=='file_exists':
                return 'PASS',f'Observed required file: {relative}. This checks existence only.'
            if path.stat().st_size>1024*1024:
                return 'UNVERIFIED',f'File exceeds the 1 MiB static-check limit: {relative}'
            source=workspace_service.read_file(repo,relative)
            if source is None:
                return 'UNVERIFIED','Workspace changed while reading evidence; retry verification.'
            if checker=='python_addition_v1':
                from .addition_check import check_addition
                return check_addition(source)
            if checker=='json_valid':
                def reject_constant(value):
                    raise ValueError(f'Non-JSON constant: {value}')
                try:
                    json.loads(source,parse_constant=reject_constant)
                except (ValueError,RecursionError):
                    return 'FAIL',f'Invalid JSON document: {relative}'
            else:
                try:
                    compile(source,relative,'exec',dont_inherit=True)
                except (SyntaxError,ValueError) as exc:
                    return 'FAIL',f'Python syntax error in {relative}, line {getattr(exc,"lineno",None)}'
        if checker=='python_syntax_workspace':
            return 'PASS',f'Compiled {len(paths)} current Python source files without execution; dependency/cache directories excluded. Syntax only, not functional correctness.'
        return 'PASS',f'{checker} check passed for {paths[0]}; no broader behavior was evaluated.'
    except (OSError,ValueError,UnicodeError,RecursionError) as exc:
        return 'UNVERIFIED',f'Evidence could not be checked ({type(exc).__name__}); verify the file path, access, and encoding.'
