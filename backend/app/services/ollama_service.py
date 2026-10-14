from .workflow_service import observed, workflow
import httpx
import json
import time
import re
import logging
import uuid
from typing import Dict, Any, List, Optional, AsyncGenerator
from .telemetry_service import telemetry_manager

logger = logging.getLogger(__name__)

class OllamaService:
    def __init__(self, host: str = "http://127.0.0.1:11434", default_model: str = "qwen3:1.7b"):
        self.host = host.rstrip("/")
        self.default_model = default_model
        self.default_timeout = 180.0
        self.timeout = 180.0
        self.keep_alive = "30m"

    def update_config(self, host: str, default_model: Optional[str] = None):
        self.host = host.rstrip("/")
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
                    # Select best default: 1.5b if available, otherwise 7b, otherwise first
                    current_model = self.default_model
                    if current_model not in models:
                        for candidate in ["qwen2.5-coder:1.5b", "qwen2.5-coder:7b"]:
                            if candidate in models:
                                current_model = candidate
                                break
                        else:
                            current_model = models[0] if models else "none"
                    if current_model in models:
                        self.default_model = current_model

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
            "num_ctx": num_ctx,
            "repeat_penalty": 1.15
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
                if resp.status_code == 404 and "not found" in resp.text:
                    try:
                        tags_resp = await client.get(f"{self.host}/api/tags")
                        if tags_resp.status_code == 200:
                            avail = [m.get("name") for m in tags_resp.json().get("models", [])]
                            fallback = None
                            for cand in ["qwen2.5-coder:1.5b", "qwen2.5-coder:7b"]:
                                if cand in avail:
                                    fallback = cand
                                    break
                            if not fallback and avail:
                                fallback = avail[0]
                            if fallback and fallback != payload.get("model"):
                                logger.info(f"Model '{payload.get('model')}' not found; falling back to installed '{fallback}'")
                                self.default_model = fallback
                                active_model = fallback
                                payload["model"] = fallback
                                resp = await client.post(f"{self.host}/api/chat", json=payload)
                    except Exception:
                        pass
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
