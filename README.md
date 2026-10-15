# HorizonLab

A local-first evaluation platform for autonomous software engineering agents. HorizonLab turns software development into a measurable workflow: understand the task, extract requirements, inspect the repo, plan edits, implement changes, run tests, recover from failures, verify results, and persist evidence-backed metrics.

[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB)](https://www.python.org/)
[![Node.js 18+](https://img.shields.io/badge/Node.js-18%2B-339933)](https://nodejs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-19-61DAFB)](https://react.dev/)
[![Ollama](https://img.shields.io/badge/Ollama-Local%20LLM-5A2D82)](https://ollama.com/)

HorizonLab is built for research, benchmarking, and controlled experimentation with local LLM-driven coding agents. Instead of treating agent performance as a one-shot demo, the project models the full software engineering lifecycle as an observable, auditable system with real repo access, verification, and persistent metrics.

## Overview

HorizonLab is an autonomous multi-agent evaluation platform and benchmark harness for long-horizon coding tasks. It supports:

- requirement extraction from natural-language prompts
- repository inspection and planning
- code generation and patching
- real test execution in a working repo
- bounded debugging and recovery loops
- independent verification and evidence capture
- dashboard-based evaluation and benchmark tracking

The system is intentionally local-first, so it can be run on a developer machine without a hosted backend or cloud-only workflow.

## Why this project exists

Most coding assistants are judged by short demos and isolated examples. HorizonLab asks a more rigorous question:

> How well does an autonomous agent perform across a full software engineering workflow, under failure, with real repository context, and with measurable evidence?

The platform is designed to test the end-to-end lifecycle of software work:

1. intake the task and repository context
2. define goals, constraints, and acceptance criteria
3. inspect the codebase and plan changes
4. produce code patches or new implementation
5. run real tests and detect failures
6. recover from errors in a bounded, observable loop
7. verify the output and record outcomes

This makes the workflow auditable rather than opaque.

## Architecture

The project follows a seven-stage autonomous software engineering pipeline:

```text
1. Coding Workspace & Request
   └── Receive the task and inspect the repo context

2. Requirement Analyst
   └── Parse goals, constraints, and acceptance criteria

3. Codebase Planner
   └── Inspect the codebase and propose an implementation plan

4. Coding Agent
   └── Generate code changes and apply patches

5. Test & Debug Agent
   └── Run pytest and recover from failures in a bounded loop

6. Independent Verifier
   └── Check supported criteria with explicit evidence

7. Evaluation Dashboard
   └── Persist metrics, logs, and benchmark summaries
```

This is implemented as a FastAPI backend orchestration layer with a React frontend for interactive workflow visualization. A LangGraph monitoring layer is used for analytics and capability tracking without replacing the core sequential coding pipeline.

## Core capabilities

### Requirement analysis
- convert free-form tasks into structured goal models
- extract constraints, assumptions, and acceptance criteria
- support clarification and confirmation gates
- use local LLM inference through Ollama or deterministic fallback logic

### Codebase planning
- inspect repository structure and likely edit sites
- propose a file-level and task-level execution roadmap
- identify likely risks and verification steps
- map work to implementation, test, and validation stages

### Coding execution
- generate multi-file patches and diffs
- apply edits in local or sandboxed repositories
- perform syntax-aware validation before deeper testing
- maintain artifacts that can be reviewed and compared

### Testing and recovery
- execute real pytest suites against the repository
- parse failures and debug output into actionable next steps
- attempt bounded recovery loops when tests fail
- record retries, durations, and verification outcomes

### Independent verification
- validate supported checks with explicit evidence
- distinguish verified results from unsupported claims
- reduce over-claiming from model output

### Benchmarking and evaluation
- store run results in SQLite
- compare deterministic benchmark strategies
- track run duration, retries, failure patterns, and capability coverage
- surface only evidence-backed metrics in the dashboard

## Tech stack

### Backend
- Python 3.11+
- FastAPI
- Uvicorn
- Pydantic v2
- HTTPX
- SQLite
- pytest and pytest-asyncio
- Ollama integration for local LLM execution
- LangGraph for monitoring and analytics

### Frontend
- React 19
- Vite
- Lucide icons
- Canvas Confetti
- glassmorphism-style dark UI

### Research and evaluation
- controlled benchmark tasks
- failure and recovery analytics
- capability tracking
- persisted run evidence and comparison reports

## Repository structure

```text
HorizonLab/
├── README.md
├── LOCAL_RUN_GUIDE.md
├── BENCHMARKING.md
├── WORKFLOW_EVALUATION.md
├── PROJECT_REPAIR_PLAN.md
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── routes.py
│   │   ├── models/
│   │   │   └── schema.py
│   │   ├── services/
│   │   │   ├── db.py
│   │   │   ├── ollama_service.py
│   │   │   ├── workspace_service.py
│   │   │   ├── goal_parser_service.py
│   │   │   ├── planner_service.py
│   │   │   ├── coder_service.py
│   │   │   ├── test_runner_service.py
│   │   │   ├── debugger_service.py
│   │   │   ├── verifier_service.py
│   │   │   ├── orchestrator_service.py
│   │   │   ├── goal_tracker_service.py
│   │   │   ├── drift_controller_service.py
│   │   │   ├── feature_analytics_service.py
│   │   │   └── ...
│   │   ├── main.py
│   │   └── ...
│   ├── sandbox/
│   ├── tests/
│   ├── requirements.txt
│   ├── pytest.ini
│   ├── test_pipeline.py
│   └── benchmark_pipeline.py
├── frontend/
│   ├── src/
│   ├── public/
│   ├── tests/
│   ├── package.json
│   ├── vite.config.js
│   └── index.html
├── output/
│   └── benchmark outputs and generated artifacts
├── .gitignore
├── .env.example
└── .venv/
```

## Quick start

### Prerequisites

- Python 3.11+
- Node.js 18+
- Ollama installed and running locally
- Git (optional, but recommended)

### 1) Install Ollama and pull a model

```powershell
ollama --version
ollama list
ollama pull qwen2.5-coder:7b
```

If the model is not found, pull it again and confirm the exact name and tag match the model configured in the app.

### 2) Start the backend

```powershell
cd backend
python -m venv .venv # for git bash - source .venv/Scripts/activate
# On Windows: .venv\Scripts\activate
# On Unix: source .venv/bin/activate
pip install -r requirements.txt   # (or pip install fastapi uvicorn pydantic httpx pytest pytest-asyncio pyjwt passlib[bcrypt])
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

```

Then verify:

- http://127.0.0.1:8000/
- http://127.0.0.1:8000/docs
- http://127.0.0.1:8000/api/health

### 3) Start the frontend

Open a second terminal:

```powershell
cd frontend
npm ci
npm run dev
```

Then visit the local Vite URL, typically:

```text
http://localhost:5173
```

## Recommended workflow

1. Confirm Ollama is connected and the model is available.
2. Open the app and inspect a sample repo or disposable workspace.
3. Select a preset challenge or define a custom task.
4. Run a small evaluation before broader experiments.
5. Review logs, tests, and verifier output.
6. Inspect the dashboard for evidence-backed performance summaries.

Important: run coding tasks only in disposable repositories or isolated sandboxes. The agent can modify files and run tests in the workspace.

## Benchmarking and evaluation

The repository includes a benchmarking layer for controlled experiments and long-horizon software tasks. It tracks:

- task outcomes and run completion
- test pass/fail states
- recovery attempts and debug loops
- runtime duration and execution traces
- capability coverage and benchmark comparisons

For more detail, see:

- [LOCAL_RUN_GUIDE.md](LOCAL_RUN_GUIDE.md)
- [BENCHMARKING.md](BENCHMARKING.md)
- [WORKFLOW_EVALUATION.md](WORKFLOW_EVALUATION.md)
- [PROJECT_REPAIR_PLAN.md](PROJECT_REPAIR_PLAN.md)

## Important notes and limitations

This project is research-oriented and intentionally transparent about what is and is not validated.

- early failure prediction is currently a rule-based baseline, not a trained ML model
- recovery time and cost are proxy metrics, not raw money or token-level pricing
- human intervention is currently reported as zero because the workflow does not yet model formal human review
- capability percentages are displayed only when there is recorded evidence behind them
- the main coding pipeline is sequential; LangGraph is used for monitoring and analytics rather than replacing the whole agent workflow

## API highlights

The backend exposes endpoints for health checks, Ollama configuration, preset tasks, workspace inspection, requirement parsing, planning, code execution, testing, verification, and metrics.

```text
GET /api/health
GET /api/ollama/status
POST /api/ollama/configure
GET /api/presets
GET /api/workspace/sample-repos
GET /api/workspace/inspect
POST /api/goals/parse
POST /api/plans/start
POST /api/code/execute
POST /api/tests/execute
POST /api/verification/execute
POST /api/run/pipeline
GET /api/features/{run_id}
GET /api/features/capabilities
```

The interactive Swagger UI is available at:

```text
http://127.0.0.1:8000/docs
```

## Local development guidance

### Good practices
- use disposable repositories for task execution
- validate with small experiments before larger runs
- inspect logs and test output before trusting the result
- keep the Ollama host and model version consistent
- rely on benchmark dashboards for evidence-based comparison

### Avoid
- running large or sensitive tasks against production repos
- assuming model output is correct without test evidence
- treating estimated metrics as verified production data
- mixing benchmark DB state into normal app state unless intentionally configured

## Troubleshooting

### Ollama model not found

```powershell
ollama pull qwen2.5-coder:7b
ollama list
```

Make sure the exact model name and tag match what the application is configured to use.

### PowerShell blocks venv activation

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

### Backend fails to start

- confirm dependencies are installed with `pip install -r requirements.txt`
- ensure Python 3.11+ is active
- make sure you are in the `backend` folder before starting uvicorn

### Frontend fails to start

```powershell
npm install
npm run dev
```

## Contributing

This repository is best treated as a research and engineering prototype. Contributions should focus on:

- workflow reliability and observability
- evaluation rigor and evidence quality
- safer benchmark design and clearer reporting
- improvements in the planning, coding, debugging, and verification stages
- better setup flow and documentation

When changing the project, preserve the distinction between:

- real execution evidence
- estimated or simulated metrics
- research features that remain experimental

## Summary

HorizonLab is a practical, local-first framework for studying autonomous software engineering in a controlled and measurable way. It brings together requirement analysis, planning, code generation, real test execution, debugging, verification, and benchmark reporting in one platform.

It is particularly useful for:

- experimenting with autonomous coding workflows
- benchmarking agent behavior across full software tasks
- measuring recovery and failure handling in realistic conditions
- validating local LLM-driven engineering in a controlled environment

## License

This project is provided for research, evaluation, and local experimentation. Review the repository policies and project documentation before using it in production or external deployments.

---

Built for research, evaluation, and local experimentation in autonomous software engineering.
