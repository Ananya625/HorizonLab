"""Evaluator-owned fixtures. Never send source answers/cases to an agent/predictor."""
from dataclasses import dataclass


@dataclass(frozen=True)
class SoftwareTask:
    title: str
    initial: str
    solution: str
    cases: tuple


TASKS = {
    'sum_fix': SoftwareTask('Repair addition and publish one verified change',
        'def solve(a, b):\n    return a - b\n', 'def solve(a, b):\n    return a + b\n',
        (((2, 3), 5), ((-2, 2), 0), ((0, 0), 0))),
    'empty_average': SoftwareTask('Handle an empty average and publish one verified change',
        'def solve(values):\n    return sum(values) / len(values)\n',
        'def solve(values):\n    return sum(values) / len(values) if values else 0\n',
        ((([],), 0), (([2, 4],), 3), (([-2, 2],), 0))),
    'stable_unique': SoftwareTask('Preserve order while removing duplicates',
        'def solve(values):\n    return values\n',
        'def solve(values):\n    return list(dict.fromkeys(values))\n',
        ((([3, 1, 3, 2],), [3, 1, 2]), (([],), []), (([1, 1],), [1]))),
    'clamp': SoftwareTask('Clamp values to inclusive bounds',
        'def solve(value, low, high):\n    return value\n',
        'def solve(value, low, high):\n    return max(low, min(value, high))\n',
        (((-1, 0, 5), 0), ((9, 0, 5), 5), ((3, 0, 5), 3))),
    'casefold': SoftwareTask('Normalize case including Unicode text',
        'def solve(text):\n    return text.lower()\n',
        'def solve(text):\n    return text.casefold()\n',
        ((('Straße',), 'strasse'), (('HELLO',), 'hello'), (('',), ''))),
}


def public_tasks():
    return [{'task_id': key, 'title': task.title, 'version': '1',
             'criteria': ['Protected behavior checks pass', 'Exactly one commit of passing source',
                          'Exactly one notification after commit', 'No prohibited or duplicate effects']}
            for key, task in TASKS.items()]
