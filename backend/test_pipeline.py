"""Interactive pipeline smoke check using only temporary storage."""
import asyncio
from pipeline_smoke import isolated_pipeline, run_confirmed

async def test_full_pipeline(confirm=input):
    record = await run_confirmed('write a python code to add two numbers', confirm=confirm)
    print(record.model_dump_json(indent=2))
    return record

if __name__ == '__main__':
    with isolated_pipeline():
        asyncio.run(test_full_pipeline())
