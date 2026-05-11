import json
import os
from dotenv import load_dotenv
from fastapi import FastAPI, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional
from .models import StartDebateResponse, DebateStatusResponse, Speaker, ChatMessage
from .debate_runner import runner
from .tts_manager import init_tts, TtsManager

# Load environment
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

# Get TTS config from environment
api_key = os.getenv("DASHSCOPE_API_KEY", "").strip()


def _speaker_voice_map() -> dict[str, str]:
    """五角色音色；未单独配置时退回 VOICE_ID_DEFAULT / VOICE_ID_MEARSHEIMER / VOICE_ID_JERVIS（旧 .env）。"""
    default = (
        os.getenv("VOICE_ID_DEFAULT", "").strip()
        or os.getenv("VOICE_ID_MEARSHEIMER", "").strip()
        or os.getenv("VOICE_ID_JERVIS", "").strip()
    )

    def one(env_name: str) -> str:
        v = os.getenv(env_name, "").strip()
        return v or default

    return {
        "lex": one("VOICE_ID_LEX"),
        "wuwei": one("VOICE_ID_WUWEI"),
        "liptan": one("VOICE_ID_LIPTAN"),
        "cook": one("VOICE_ID_COOK"),
        "jensen": one("VOICE_ID_JENSEN"),
    }


_speaker_voices = _speaker_voice_map()
tts_model = os.getenv("TTS_MODEL", "qwen3-tts-vc-realtime-2026-01-15")
tts_ws_url = os.getenv("TTS_WS_URL", "wss://dashscope.aliyuncs.com/api-ws/v1/realtime")

# Initialize TTS（至少有一个非空 voice id 即可全员复用）
if api_key and any(_speaker_voices.values()):
    init_tts(api_key, _speaker_voices, tts_model, tts_ws_url)

tts_manager = TtsManager()

app = FastAPI(title="Debate Book API", version="1.0")

# Allow CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    speaker: Speaker
    message: str


class ChatResponse(BaseModel):
    reply: str
    chat_history: List[ChatMessage]


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


@app.post("/api/debate/chat/{run_id}", response_model=ChatResponse)
async def post_chat(run_id: str, request: ChatRequest):
    """Continue chat with selected debater in shared room; full history returned every time."""
    run = runner.get_run_status(run_id)
    if not run:
        return ChatResponse(
            reply="Run not found",
            chat_history=[]
        )

    reply = await runner.chat_with_debater(run_id, request.speaker, request.message)
    return ChatResponse(
        reply=reply if reply else "",
        chat_history=run.chat_history
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


@app.websocket("/ws/debate-audio")
async def websocket_debate_audio(websocket: WebSocket):
    """WebSocket endpoint for real-time debate audio streaming.
    Flow:
    1. Client connects
    2. Client sends {"type":"start"} → start automatic sequential TTS for all turns
    3. Server sends:
       - meta {"type":"meta", "format": "...", "speaker": "...", "round": N}
       - binary audio chunks → direct to browser WebAudio
       - round_done {"type":"round_done", ...}
       - all_done {"type":"all_done"}
    4. On disconnect → clean up resources
    """
    await websocket.accept()
    await tts_manager.handle_connection(websocket, runner)


# ---- Production: serve frontend dist (single-port deployment) ----
# We only mount if the build output exists, so local dev remains unchanged.
_FRONTEND_DIST = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
_FRONTEND_DIST = os.path.abspath(_FRONTEND_DIST)
if os.path.isdir(_FRONTEND_DIST):
    app.mount("/", StaticFiles(directory=_FRONTEND_DIST, html=True), name="frontend")

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        # Let StaticFiles handle real assets; for client-side routes return index.html
        index_path = os.path.join(_FRONTEND_DIST, "index.html")
        if os.path.isfile(index_path):
            return FileResponse(index_path)
        return {"error": "frontend build not found"}

