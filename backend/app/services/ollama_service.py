import httpx
import json
import time
import re
from typing import Dict, Any, List, Optional, AsyncGenerator

class OllamaService:
    def __init__(self, host: str = "http://127.0.0.1:11434", default_model: str = "qwen2.5-coder:7b"):
        self.host = host.rstrip("/")
        self.default_model = default_model
        self.timeout = 12.0

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
                    return {
                        "connected": True,
                        "host": self.host,
                        "latency_ms": latency_ms,
                        "models": models,
                        "current_model": self.default_model if self.default_model in models else (models[0] if models else "none"),
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

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.2,
        format_json: bool = True
    ) -> Dict[str, Any]:
        """Runs non-streaming chat completion."""
        active_model = model or self.default_model
        payload = {
            "model": active_model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature
            }
        }
        if format_json:
            payload["format"] = "json"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(f"{self.host}/api/chat", json=payload)
            if resp.status_code != 200:
                raise RuntimeError(f"Ollama API error {resp.status_code}: {resp.text}")
            return resp.json()

    async def stream_chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.2
    ) -> AsyncGenerator[str, None]:
        """Streams response tokens from Ollama chat API."""
        active_model = model or self.default_model
        payload = {
            "model": active_model,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": temperature
            }
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
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
