import uvicorn
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .api.routes import router

app = FastAPI(
    title="AgentEval-X API",
    description="Evaluation, Goal Governance, Memory-Aware Recovery & Benchmarking Platform for Long-Horizon AI Agents",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in os.environ.get('AGENTEVAL_CORS_ORIGINS', 'http://localhost:5173,http://127.0.0.1:5173').split(',') if origin.strip() and origin.strip() != '*'],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")

@app.get("/")
def root():
    return {
        "platform": "AgentEval-X",
        "description": "Closed-loop evaluation, goal governance, memory-aware recovery & benchmarking platform",
        "docs": "/docs",
        "status": "online"
    }

if __name__ == "__main__":
    uvicorn.run("app.main:app", host=os.environ.get('AGENTEVAL_BIND_HOST', '127.0.0.1'), port=8000, reload=True)
