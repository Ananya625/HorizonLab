# AgentEval-X: Autonomous Multi-Agent Software Development & Verification Platform

AgentEval-X is an autonomous closed-loop software engineering and verification platform. It takes natural language software development requests, extracts structured requirements, inspects repositories, plans architectural changes, generates production source code, executes automated pytest test suites, applies bounded self-healing recovery fixes, independently audits results against acceptance criteria, and tracks persistent evaluation benchmarks in SQLite.

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
2. **Requirement Analyst**: Extracts structured Goal Models, hierarchical sub-goals, hard/soft constraints, and acceptance criteria using local Ollama (`qwen2.5-coder:7b`) with deterministic fallback. Resolves ambiguities interactively.
3. **Codebase Analyst + Planner**: Scans file trees, ASTs, and dependencies, then generates an architecture overview, planned file targets (`CREATE`, `MODIFY`, `TEST`), sequential execution roadmap, and risk mitigations.
4. **Coding Agent**: Implements multi-file source changes, computes unified Git-style diffs (`+`/`-`), and performs AST syntax checks.
5. **Testing + Debugging Agents**: Executes real pytest test suites in the repository, parses test outputs, and runs a bounded self-healing recovery loop if tests fail.
6. **Independent Code Reviewer / Verifier**: Objectively evaluates code diffs and test evidence against Stage 2 acceptance criteria, calculates Goal Drift Score (0.0% optimal), audits security invariants, and issues an audit verdict (`VERIFIED_PASSED`).
7. **Verified Results + Evaluation Dashboard**: SQLite persistence storing all runs, tool calls, latencies, recovery counts, pass rates, and comparative benchmark tables.

---

## 🛠️ Technology Stack

- **Frontend**: React 19, Vite, Lucide Icons, Canvas-Confetti, Custom Glassmorphic Dark Design System
- **Backend**: FastAPI, Uvicorn, Pydantic v2, HTTPX, SQLite3
- **Local LLM**: Ollama (`qwen2.5-coder:7b`)
- **Testing & Verification**: PyTest, PyTest-Asyncio, FastTestClient

---

## 📦 Quick Start & Local Execution

### 1. Prerequisites
- Python 3.11+
- Node.js 18+
- [Ollama](https://ollama.com/) running locally with `qwen2.5-coder:7b` (optional, intelligent fallback included)

### 2. Backend Setup
```bash
cd backend
python -m venv .venv
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
│   └── test_pipeline.py               # E2E pipeline verification test
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
