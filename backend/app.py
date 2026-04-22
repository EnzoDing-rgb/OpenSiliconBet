from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from .models import StartDebateResponse, DebateStatusResponse
from .debate_runner import runner

app = FastAPI(title="Debate Book API", version="1.0")

# Allow CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/debate/start", response_model=StartDebateResponse)
async def start_debate(background_tasks: BackgroundTasks):
    """Start a new debate run in background"""
    run_id = runner.create_new_run()
    background_tasks.add_task(runner.run_debate, run_id)
    return StartDebateResponse(run_id=run_id)


@app.get("/api/debate/status/{run_id}", response_model=DebateStatusResponse)
async def get_debate_status(run_id: str):
    """Get current debate status with accumulated turns"""
    run = runner.get_run_status(run_id)
    if not run:
        return DebateStatusResponse(
            status="error",
            current_round=0,
            turns=[],
            error="Run not found"
        )

    current_round = len(run.turns) // 2 + 1 if run.status == "running" else 3
    return DebateStatusResponse(
        status=run.status,
        current_round=current_round,
        turns=run.turns,
        error=run.error,
        judge_result=run.judge_result
    )


@app.get("/api/debate/result/{run_id}")
async def get_debate_result(run_id: str):
    """Return full debate markdown"""
    content = runner.get_result_markdown(run_id)
    if content is None:
        return {"error": "Result not found"}
    return {"content": content}


@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok"}
