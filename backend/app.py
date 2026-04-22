import json
import os
from dotenv import load_dotenv
from fastapi import FastAPI, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from .models import StartDebateResponse, DebateStatusResponse, Speaker, ChatMessage
from .debate_runner import runner
from .tts_manager import init_tts, TtsManager

# Load environment
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

# Get TTS config from environment
api_key = os.getenv("DASHSCOPE_API_KEY", "")
voice_jervis = os.getenv("VOICE_ID_JERVIS", "")
voice_mearsheimer = os.getenv("VOICE_ID_MEARSHEIMER", "")
tts_model = os.getenv("TTS_MODEL", "qwen3-tts-vc-realtime-2026-01-15")
tts_ws_url = os.getenv("TTS_WS_URL", "wss://dashscope.aliyuncs.com/api-ws/v1/realtime")

# Initialize TTS
if api_key and voice_jervis and voice_mearsheimer:
    init_tts(api_key, voice_jervis, voice_mearsheimer, tts_model, tts_ws_url)

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

