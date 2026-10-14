import asyncio
import ast
import sys
from app.services.ollama_service import ollama_service
from app.services.coder_service import extract_clean_python_code, CODER_SYSTEM_PROMPT

async def smoke_test():
    print("=== OLLAMA LIVE SMOKE TEST ===")
    conn = await ollama_service.check_connection()
    print(f"Connection: {conn['connected']}, Current model: {conn['current_model']}")
    if not conn["connected"]:
        print("ERROR: Ollama is not connected.")
        sys.exit(1)

    model = "qwen2.5-coder:1.5b"
    prompt = "Generate a complete Python module for password hashing with two functions: hash_password(password: str) -> str and verify_password(plain: str, hashed: str) -> bool."

    messages = [
        {"role": "system", "content": CODER_SYSTEM_PROMPT},
        {"role": "user", "content": f"Task: Password hashing module\nFile to write: app/auth.py\nAction: create\nDescription: {prompt}\nGenerate complete, executable, clean Python code for 'app/auth.py'."}
    ]

    print(f"Sending request to Ollama using model '{model}'...")
    resp = await ollama_service.chat_completion(
        messages=messages,
        model=model,
        temperature=0.2,
        format_json=False,
        num_ctx=2048,
        num_predict=512
    )

    raw = resp.get("message", {}).get("content", "")
    print(f"Received {len(raw)} chars from Ollama.")
    print(f"Done reason: {resp.get('done_reason')}, Eval tokens: {resp.get('eval_count')}")

    cleaned = extract_clean_python_code(raw, requested_file="app/auth.py")
    print(f"Extracted clean code length: {len(cleaned)} chars.")

    # Validate compilation
    try:
        compile(cleaned, "app/auth.py", "exec")
        tree = ast.parse(cleaned)
        funcs = [n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        classes = [n.name for n in tree.body if isinstance(n, ast.ClassDef)]
        print(f"Successfully compiled! Defined functions: {funcs}, classes: {classes}")
        assert len(funcs) > 0 or len(classes) > 0, "No functions or classes defined!"
        print("=== LIVE SMOKE TEST PASSED SUCCESSFULLY ===")
    except Exception as e:
        print(f"Validation failed: {e}")
        print("Raw output excerpt:\n", raw[:500])
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(smoke_test())
