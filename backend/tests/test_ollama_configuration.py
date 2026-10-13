import httpx
import pytest
from app.services.ollama_service import OllamaService


@pytest.mark.asyncio
@pytest.mark.parametrize('model,think', [(None, False), ('other-model:latest', None)])
async def test_selected_model_and_bounded_non_thinking_qwen_payload(monkeypatch, model, think):
    requests = []
    class Client:
        def __init__(self, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def post(self, url, json):
            requests.append(json)
            return httpx.Response(200, json={'message': {'content':'answer'}, 'prompt_eval_count':5, 'eval_count':2})
    monkeypatch.setattr(httpx, 'AsyncClient', Client)
    client = OllamaService()
    await client.chat_completion([{'role':'user','content':'fixture'}], model=model, num_predict=123)
    assert requests[0]['model'] == (model or 'qwen3:1.7b')
    assert requests[0].get('think') is think
    assert requests[0]['options']['num_predict'] == 123
    assert requests[0]['stream'] is False
