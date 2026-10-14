import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .api.routes import router

app = FastAPI(
    title="HorizonLab API",
    description="Evaluation, Goal Governance, Memory-Aware Recovery & Benchmarking Platform for Long-Horizon AI Agents",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")

@app.get("/")
def root():
    return {
        "platform": "HorizonLab",
        "description": "Closed-loop evaluation, goal governance, memory-aware recovery & benchmarking platform",
        "docs": "/docs",
        "status": "online"
    }

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
