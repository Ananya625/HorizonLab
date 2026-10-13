"""Interactive benchmark smoke driver; every goal requires human confirmation."""
import asyncio
import json
from pipeline_smoke import isolated_pipeline, run_confirmed

TASKS = [{'id': 'task_1_cold', 'name': 'Task 1 (Cold Start): Small isolated function', 'prompt': 'Implement a helper function multiply(a: float, b: float) -> float in app/service.py and test it in tests/test_service.py.', 'type': 'simple'}, {'id': 'task_1_warm', 'name': 'Task 1 (Warm Run): Small isolated function (repeat)', 'prompt': 'Implement a helper function power(base: float, exponent: int) -> float in app/service.py and test it in tests/test_service.py.', 'type': 'simple'}, {'id': 'task_2_bugfix', 'name': 'Task 2: Small bug fix', 'prompt': 'Fix bug in app/service.py where calculate_discount(price: float, discount_percent: float) returns negative price when discount is over 100%. Clamp discount between 0 and 100. Add tests in tests/test_service.py.', 'type': 'simple'}, {'id': 'task_3_multifile', 'name': 'Task 3: Multi-file change', 'prompt': 'Add user account status field with UserStatus enum in app/models.py, update user response serializer in app/serializers.py, and verify in tests/test_models.py.', 'type': 'medium'}, {'id': 'task_4_recovery', 'name': 'Task 4: Failing-test recovery task (Escalation)', 'prompt': 'Implement string sanitizer in app/service.py with strict validation for HTML tags and test in tests/test_service.py.', 'type': 'recovery'}, {'id': 'task_5_complex', 'name': 'Task 5: Complex feature (JWT Authentication Suite)', 'prompt': 'Implement complete JWT authentication with user registration, login, and token verification with password hashing and expiring tokens in app/auth.py, app/routes/auth_routes.py, app/main.py, and tests/test_auth.py.', 'type': 'complex'}]

async def run_benchmark(confirm=input):
    results = []
    for task in TASKS:
        record = await run_confirmed(task['prompt'], confirm=confirm)
        results.append({'task': task['id'], 'status': record.status,
                        'evaluation': record.evaluation.model_dump() if record.evaluation else None})
    print(json.dumps(results, indent=2))
    return results

if __name__ == '__main__':
    with isolated_pipeline():
        asyncio.run(run_benchmark())
