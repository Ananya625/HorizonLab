"""Evaluator-owned addition cases, interpreted without executing Python source.

Supports a deliberately small straight-line numeric language. Unsupported code
is UNVERIFIED, never run through exec/import or treated as a failing behavior.
"""
import ast
import operator

CASES = ((2, 3, 5), (-4, 2, -2), (0, 0, 0), (1.5, 2.5, 4),
         (-7, -9, -16), (10**30, 1, 10**30 + 1), (0.25, -0.5, -0.25), (8, 0, 8))


class Unsupported(ValueError):
    pass


def _expression(node, values):
    if isinstance(node, ast.Name) and node.id in values:
        return values[node.id]
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        if abs(node.value) <= 10**100:
            return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub)):
        fn = operator.add if isinstance(node.op, ast.Add) else operator.sub
        return fn(_expression(node.left, values), _expression(node.right, values))
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        value = _expression(node.operand, values)
        return value if isinstance(node.op, ast.UAdd) else -value
    raise Unsupported('Only numeric names, constants, addition and subtraction are supported')


def _docstring(node):
    return isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)


def check_addition(source):
    """Return a scoped PASS/FAIL/UNVERIFIED with reproducible checker evidence."""
    try:
        if len(source) > 16000:
            raise Unsupported('Source exceeds the 16,000 character limit')
        tree = ast.parse(source)
        if sum(1 for _ in ast.walk(tree)) > 300:
            raise Unsupported('Source exceeds the 300 AST node limit')
        body = list(tree.body)
        if body and _docstring(body[0]):
            body.pop(0)
        if len(body) != 1 or not isinstance(body[0], ast.FunctionDef) or body[0].name != 'add':
            raise Unsupported('Expected one standalone add(a, b) function without imports or module-level effects')
        fn = body[0]
        args = fn.args
        if (fn.decorator_list or getattr(fn, 'type_params', []) or args.posonlyargs or args.kwonlyargs
                or args.defaults or args.vararg or args.kwarg or [a.arg for a in args.args] != ['a', 'b']):
            raise Unsupported('Expected an undecorated add(a, b) interface without defaults')
        for annotation in [fn.returns, *(a.annotation for a in args.args)]:
            if annotation is not None and not (isinstance(annotation, ast.Name) and annotation.id in ('int', 'float')):
                raise Unsupported('Only simple int/float annotations are supported')
        statements = list(fn.body)
        if statements and _docstring(statements[0]):
            statements.pop(0)
        if not statements or not isinstance(statements[-1], ast.Return):
            raise Unsupported('Expected a final return statement')
        for statement in statements[:-1]:
            if not (isinstance(statement, ast.Assign) and len(statement.targets) == 1
                    and isinstance(statement.targets[0], ast.Name)):
                raise Unsupported('Only local numeric assignments followed by return are supported')
        passed = 0
        for a, b, expected in CASES:
            values = {'a': a, 'b': b}
            for statement in statements[:-1]:
                values[statement.targets[0].id] = _expression(statement.value, values)
            actual = _expression(statements[-1].value, values)
            passed += actual == expected
        verdict = 'PASS' if passed == len(CASES) else 'FAIL'
        return verdict, (f'python_addition_v1: {passed}/{len(CASES)} evaluator-owned numeric cases passed. '
                         'Checked the supported AST without executing workspace code. '
                         'Covers these addition cases only; not a general security or quality audit.')
    except (Unsupported, SyntaxError, RecursionError, OverflowError, ValueError) as exc:
        return 'UNVERIFIED', f'python_addition_v1 cannot interpret this implementation: {exc}. Supply an independent checker for this code shape.'
