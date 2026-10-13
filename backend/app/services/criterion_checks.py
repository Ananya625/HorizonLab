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
