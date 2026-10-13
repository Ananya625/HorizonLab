# AgentEval-X: Autonomous Multi-Agent Software Development & Verification Platform

AgentEval-X is a software engineering workflow prototype. It extracts requirements, requires goal confirmation, plans changes, generates code, executes pytest, and records evaluation evidence in SQLite. Benchmarking includes deterministic studies across seven categories and a bounded local Ollama pilot adapter. Real memory, drift, prediction, and adaptive-policy modules remain teammate-owned integrations. See [benchmark usage, metric definitions, validation, and team handoff](BENCHMARKING.md).

---

## 🚀 Correct 7-Stage Coding Agent Workflow

```
1. Coding Workspace & Request  ──►  2. Requirement Analyst  ──►  3. Codebase Planner  ──►  4. Coding Agent
   (Preset/Prompt & Repo Scan)         (Ollama / Goal Model)         (Inspect & Plan)         (Diffs & AST)
                                                                                                    │
                                                                                                    ▼
7. Evaluation Dashboard        ◄──  6. Independent Verifier  ◄──  5. Test & Debug Agent (Bounded Recovery)
   (SQLite Benchmarks)                 (Criteria Evidence)            (Pytest Real Execution)
```

1. **Coding Request**: Ingests coding tasks (e.g. *“Build a login API with JWT authentication”*, concurrency bug fix, async DB refactor, AST security patch) and inspects repository workspaces.
2. **Requirement Analyst**: Extracts structured Goal Models, hierarchical sub-goals, hard/soft constraints, and acceptance criteria using the selected local Ollama model (default `qwen3:1.7b`) with deterministic requirement fallback. Resolves ambiguities interactively.
3. **Codebase Analyst + Planner**: Scans file trees, ASTs, and dependencies, then generates an architecture overview, planned file targets (`CREATE`, `MODIFY`, `TEST`), sequential execution roadmap, and risk mitigations.
4. **Coding Agent**: Implements multi-file source changes, computes unified Git-style diffs (`+`/`-`), and performs AST syntax checks.
5. **Testing + Debugging Agents**: Executes real pytest test suites in the repository, parses test outputs, and runs a bounded self-healing recovery loop if tests fail.
6. **Independent Code Reviewer / Verifier**: Checks explicitly supported Python syntax criteria. Unsupported acceptance criteria, security constraints, drift, and quality measurements remain unverified. Controlled fixtures use protected behavioral and side-effect checks.
7. **Results + Evaluation Dashboard**: Persists measured outcomes, calls, durations, and recovery attempts, and runs controlled simulation comparisons. Legacy scores are labeled unvalidated; unavailable evidence is shown explicitly.

---

## 🛠️ Technology Stack

- **Frontend**: React 19, Vite, Lucide Icons, Canvas-Confetti, Custom Glassmorphic Dark Design System
- **Backend**: FastAPI, Uvicorn, Pydantic v2, HTTPX, SQLite3
- **Local LLM**: Ollama (default `qwen3:1.7b` / `qwen2.5-coder:7b`)
- **Research feature graph**: LangGraph-backed recovery analytics and dynamic, evidence-grounded capability profiles
- **Testing & Verification**: PyTest, PyTest-Asyncio, FastTestClient

---

## 📦 Quick Start & Local Execution

### 1. Prerequisites
- Python 3.11+
- Node.js 18+
- [Ollama](https://ollama.com/) running locally with `qwen3:1.7b` or your explicitly selected installed model. Required for general code generation; deterministic fixture benchmarks and supported independent checks can run without an LLM. Generation errors are reported rather than replaced with success stubs.

### 2. Backend Setup
```bash
cd backend
python -m venv .venv # for git bash - source .venv/Scripts/activate
# On Windows: .venv\Scripts\activate
# On Unix: source .venv/bin/activate
pip install -r requirements.txt   # (or pip install fastapi uvicorn pydantic httpx pytest pytest-asyncio pyjwt passlib[bcrypt])
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### 3. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```
Open `http://localhost:5173` in your browser.

---

## 📁 Repository Structure

```
SicProject/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── routes.py              # FastAPI stage & telemetry endpoints
│   │   ├── models/
│   │   │   └── schema.py              # Pydantic models for GoalModel, Plan, Diffs, Tests, Evals
│   │   ├── services/
│   │   │   ├── db.py                  # SQLite database engine & persistence
│   │   │   ├── ollama_service.py      # Local Ollama client with latency telemetry
│   │   │   ├── workspace_service.py   # Repo scanning, file writing, diff engine
│   │   │   ├── goal_parser_service.py # Requirement Analyst & Goal Model extractor
│   │   │   ├── planner_service.py     # Codebase Analyst & Planner Agent
│   │   │   ├── coder_service.py       # Coding Agent & multi-file generator
│   │   │   ├── test_runner_service.py # Real pytest runner & log parser
│   │   │   ├── debugger_service.py    # Bounded recovery self-healing loop
│   │   │   ├── verifier_service.py    # Independent Code Reviewer & Verifier
│   │   │   └── orchestrator_service.py# End-to-end pipeline orchestrator
│   │   └── main.py                    # FastAPI application entrypoint
│   ├── sandbox/                       # Isolated sandbox repository workspaces
│   └── test_pipeline.py               # E2E pipeline verification test & smoke check
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── Header.jsx             # Top bar, 7-stage stepper, Ollama status
│   │   │   ├── TaskInputSection.jsx   # Stage 1: Coding Workspace & Presets
│   │   │   ├── GoalModelView.jsx      # Stage 2: Requirement Analysis & Goal Model
│   │   │   ├── ClarificationCenter.jsx# Stage 2.1: Ambiguity resolution Q&A
│   │   │   ├── ConfirmationGate.jsx   # Stage 2.3: Lock & Confirm Gate
│   │   │   ├── PlannerView.jsx        # Stage 3: Codebase Analyst & Planner
│   │   │   ├── CodingAgentView.jsx    # Stage 4: Coding Agent (Diffs & Code)
│   │   │   ├── TestingDebugView.jsx   # Stage 5: Testing & Debugging Agents
│   │   │   ├── VerificationView.jsx   # Stage 6: Independent Code Reviewer
│   │   │   ├── EvaluationDashboard.jsx# Stage 7: Benchmark Comparisons & SQLite stats
│   │   │   └── ExecutionControlRoom.jsx# Live real-time agent telemetry drawer
│   │   ├── services/
│   │   │   └── api.js                 # API client for all stage endpoints
│   │   ├── App.jsx                    # Root multi-agent application container
│   │   └── index.css                  # Modern dark glassmorphic design system
│   └── package.json
└── README.md
```

---

## Research Feature Integration

The backend exposes recovery analytics and dynamic capability profiles:

- **Recovery Stats:** recovery attempts and outcomes, recovery rate, time spent in the testing/recovery stage, extra steps, human-intervention count, and a clearly labelled proxy cost.
- **Dynamic Agent Capability Profile:** directly observed outcomes for the seven pipeline agents, with the measured denominator and evidence basis shown in the Evaluation Dashboard. Missing outcomes remain unavailable; no prior-adjusted percentages are displayed.

A LangGraph feature-monitoring graph processes observed pipeline stages. The existing main coding pipeline is still implemented as sequential service calls; the graph currently orchestrates the monitoring feature nodes, rather than replacing the entire coding pipeline.

Feature endpoints:
- `GET /api/features/{run_id}` — run analytics and recovery stats.
- `GET /api/features/capabilities` — capability profiles across models.
- `GET /api/features/capabilities?model_name=qwen2.5-coder:7b` — profile for one model.
- `GET /api/runs/{run_id}/policy-approval` — inspect the pending human approval, if any.
- `POST /api/runs/{run_id}/policy-approval` — resume or stop a paused run with `{"approval_id":"…","approved":true|false,"comment":"…"}`.

Runtime policy decisions are persisted separately from execution outcomes. Recovery evidence can raise or lower the retry budget; `inspect` checks tracked changes for invalid AST, `switch_strategy` queues and verifies an alternate recovery strategy, `ask_human` pauses until approval, and `stop` prevents further autonomous mutations. Runs awaiting a person use status `awaiting_approval`; policy stops use `policy_stopped`.

Evaluation percentages use persisted outcomes only and remain unavailable when the relevant evidence is missing. The seven agent profiles show their measured denominator (runs, file paths, files, tests, recovery attempts, or constraints) and do not claim semantic requirement correctness without ground truth. Capability panels show observed outcome rates and sample counts rather than prior-driven posterior percentages.

After starting the backend, open `http://127.0.0.1:8000/docs` to inspect the endpoints. Feature values are populated after instrumented pipeline runs.
