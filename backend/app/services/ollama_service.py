from .workflow_service import observed
import httpx
import json
import time
import re
import logging
import uuid
import os
import ipaddress
from urllib.parse import urlsplit
from typing import Dict, Any, List, Optional, AsyncGenerator
from .telemetry_service import telemetry_manager

logger = logging.getLogger(__name__)

class OllamaService:
    @staticmethod
    def validate_host(host: str) -> str:
        parsed = urlsplit(host)
        name = (parsed.hostname or '').lower()
        allowed = {h.strip().lower() for h in os.environ.get('AGENTEVAL_OLLAMA_HOSTS', '').split(',') if h.strip()}
        try:
            loopback = ipaddress.ip_address(name).is_loopback
        except ValueError:
            loopback = name == 'localhost'
        if (parsed.scheme not in {'http', 'https'} or not name or parsed.username or parsed.password
                or parsed.path not in {'', '/'} or parsed.query or parsed.fragment
                or not (loopback or name in allowed)):
            raise ValueError('Ollama URL must use loopback or an explicitly allowed host')
        parsed.port  # Validate malformed/out-of-range ports before storing configuration.
        return host.rstrip('/')

    def __init__(self, host: str = "http://127.0.0.1:11434", default_model: str = "qwen3:1.7b"):
        self.host = self.validate_host(host)
        self.default_model = default_model
        self.default_timeout = 45.0
        self.keep_alive = "30m"

    def update_config(self, host: str, default_model: Optional[str] = None):
        self.host = self.validate_host(host)
        if default_model:
            self.default_model = default_model

    async def check_connection(self) -> Dict[str, Any]:
        """Checks if Ollama is running, returns status, latency, and available models."""
        start_time = time.time()
        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                resp = await client.get(f"{self.host}/api/tags")
                latency_ms = round((time.time() - start_time) * 1000, 1)
                
                if resp.status_code == 200:
                    data = resp.json()
                    models = [m.get("name") for m in data.get("models", [])]
                    current_model = self.default_model if self.default_model in models else (models[0] if models else "none")

                    return {
                        "connected": True,
                        "host": self.host,
                        "latency_ms": latency_ms,
                        "models": models,
                        "current_model": current_model,
                        "raw_models": data.get("models", []),
                        "message": f"Connected to Ollama ({len(models)} models available)"
                    }
                else:
                    return {
                        "connected": False,
                        "host": self.host,
                        "latency_ms": latency_ms,
                        "models": [],
                        "current_model": self.default_model,
                        "message": f"Ollama returned HTTP {resp.status_code}"
                    }
        except Exception as e:
            return {
                "connected": False,
                "host": self.host,
                "latency_ms": None,
                "models": [],
                "current_model": self.default_model,
                "message": f"Cannot reach Ollama at {self.host}: {str(e)}"
            }

    @observed('ollama.chat', 'model', reason=None)
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.2,
        format_json: bool = True,
        num_ctx: int = 2048,
        num_predict: Optional[int] = 512,
        timeout: Optional[float] = None,
        run_id: Optional[str] = None,
        stage: str = "llm"
    ) -> Dict[str, Any]:
        """Runs non-streaming chat completion with structured telemetry."""
        active_model = model or self.default_model
        req_timeout = timeout or self.default_timeout

        options: Dict[str, Any] = {
            "temperature": temperature,
            "num_ctx": num_ctx
        }
        if num_predict:
            options["num_predict"] = num_predict

        payload = {
            "model": active_model,
            "messages": messages,
            "stream": False,
            "keep_alive": self.keep_alive,
            "options": options
        }
        if format_json:
            payload["format"] = "json"
        if active_model.startswith('qwen3:'):
            # Keep the bounded response budget for the requested code/JSON.
            # The approved local pilot already uses the same non-thinking mode.
            payload['think'] = False

        from .db import db_service
        operation_id = uuid.uuid4().hex
        if run_id:
            db_service.add_log(run_id, 'model', 'Model Client', 'model_call', 'Model request', {'operation_id':operation_id, 'model':active_model, 'temperature':temperature})
        start_time = time.time()
        error_msg = None
        data = {}

        try:
            async with httpx.AsyncClient(timeout=req_timeout) as client:
                resp = await client.post(f"{self.host}/api/chat", json=payload)
                if resp.status_code != 200:
                    raise RuntimeError(f"Ollama API error {resp.status_code}: {resp.text}")
                data = resp.json()
        except httpx.TimeoutException:
            error_msg = f"Ollama timed out after {req_timeout}s"
            raise TimeoutError(error_msg)
        except Exception as e:
            error_msg = str(e) or type(e).__name__
            raise
        finally:
            duration_ms = (time.time() - start_time) * 1000
            prompt_tokens = data.get("prompt_eval_count", 0)
            eval_tokens = data.get("eval_count", 0)
            eval_dur_sec = data.get("eval_duration", 1) / 1e9 if data.get("eval_duration") else (duration_ms / 1000)
            tok_per_sec = (eval_tokens / eval_dur_sec) if eval_dur_sec > 0 else 0.0

            if run_id:
                db_service.add_log(run_id, 'model', 'Model Client', 'model_result', 'Model request failed' if error_msg else 'Model response', {'operation_id':operation_id,'input_tokens':data.get('prompt_eval_count'),'output_tokens':data.get('eval_count'),'status':'error' if error_msg else 'completed','duration_seconds':duration_ms/1000})
                tracker = telemetry_manager.get(run_id)
                if tracker:
                    tracker.record_model_call(
                        model_name=active_model,
                        duration_ms=duration_ms,
                        tokens_in=prompt_tokens,
                        tokens_out=eval_tokens,
                        error_status=error_msg,
                        tok_per_sec=tok_per_sec,
                        stage=stage
                    )

        return data

    async def stream_chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.2,
        num_ctx: int = 2048,
        num_predict: Optional[int] = 512
    ) -> AsyncGenerator[str, None]:
        """Streams response tokens from Ollama chat API."""
        active_model = model or self.default_model
        payload = {
            "model": active_model,
            "messages": messages,
            "stream": True,
            "keep_alive": self.keep_alive,
            "options": {
                "temperature": temperature,
                "num_ctx": num_ctx,
                "num_predict": num_predict or 512
            }
        }

        async with httpx.AsyncClient(timeout=self.default_timeout) as client:
            async with client.stream("POST", f"{self.host}/api/chat", json=payload) as response:
                if response.status_code != 200:
                    yield f"Error: Ollama status {response.status_code}"
                    return
                async for chunk in response.aiter_lines():
                    if not chunk.strip():
                        continue
                    try:
                        data = json.loads(chunk)
                        content = data.get("message", {}).get("content", "")
                        if content:
                            yield content
                    except json.JSONDecodeError:
                        continue

    @staticmethod
    def extract_json_object(raw_text: str) -> Dict[str, Any]:
        """Extract and clean JSON object from LLM response."""
        text = raw_text.strip()
        # Strip markdown fences ```json ... ```
        if text.startswith("```"):
            lines = text.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()

        # Search for first { to last }
        match = re.search(r"(\{.*\})", text, re.DOTALL)
        if match:
            text = match.group(1)

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Try cleaning trailing commas
            cleaned = re.sub(r",\s*([\]}])", r"\1", text)
            return json.loads(cleaned)

ollama_service = OllamaService()
