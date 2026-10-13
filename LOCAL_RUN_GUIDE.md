# AgentEval-X local run guide (Windows)

## 1. Prerequisites
- Python 3.11+
- Node.js 18+
- Ollama installed
- Git (optional if you already downloaded the project ZIP)

## 2. Start Ollama
In PowerShell:
```powershell
ollama --version
ollama list
ollama pull qwen2.5-coder:7b
```
Ollama normally runs as a background app on Windows. If the backend says it cannot connect, open Ollama first and check `http://127.0.0.1:11434/api/tags` in a browser.

### If a run reports `model 'qwen2.5-coder:7b' not found`
In PowerShell, pull the model and confirm that Ollama lists it:
```powershell
ollama pull qwen2.5-coder:7b
ollama list
```
The model name shown by `ollama list` (or `/api/tags`) must match the model selected in AgentEval-X, including its tag. If the model is listed but the error persists, make sure AgentEval-X is connected to the same Ollama host where you pulled it; the default is `http://127.0.0.1:11434`. Then refresh the Ollama status in the UI and retry the run.

## 3. Start the backend
Open a PowerShell terminal in this project folder:
```powershell
cd backend
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
If PowerShell blocks environment activation, run:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```
Keep this terminal open. Check `http://127.0.0.1:8000/` and `http://127.0.0.1:8000/docs`.

## 4. Start the frontend
Open a second terminal at the project root:
```powershell
cd frontend
npm ci
npm run dev
```
Open the local URL Vite prints, normally `http://localhost:5173`.

## 5. Smoke-test before a full run
1. In the UI, confirm the Ollama status is connected and the expected model appears.
2. Inspect the sample workspace.
3. Start with a small, harmless coding task on a disposable sample repository.
4. Check the run's logs, tests, and verifier output.
5. Open the Evaluation Dashboard. Agent and capability percentages use persisted run outcomes and show the evidence basis; metrics without recorded outcomes remain unavailable.

API checks:
- `GET http://127.0.0.1:8000/api/health`
- `GET http://127.0.0.1:8000/api/ollama/status`
- `GET http://127.0.0.1:8000/api/features/capabilities`
- `GET http://127.0.0.1:8000/docs`

## Important notes about the three research features
- Early failure prediction is currently a rule-based baseline over observed pipeline/test signals. It is not yet a trained scikit-learn model and does not itself override the existing debugger's recovery policy.
- Recovery time measures the testing/recovery stage duration. `estimated_cost_units` is a transparent proxy based on recovery attempts and additional test runs, not actual money or token usage.
- Human intervention is currently reported as zero because the existing workflow does not yet have a human approval/review interaction.
- Capability percentages use persisted observed outcomes, and task-duration summaries include only timestamp-consistent evaluations or durations reconstructed from execution logs. Unverifiable legacy durations are omitted rather than guessed.
- LangGraph currently orchestrates the feature-monitoring nodes. The existing seven-stage coding pipeline remains sequential service calls; converting the entire coding pipeline into a LangGraph graph is a separate next step.
- Run full coding tasks only against disposable repositories. The agent can modify files and execute tests.
