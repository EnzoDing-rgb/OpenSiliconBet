from enum import Enum
from pydantic import BaseModel
from typing import List, Dict, Optional


class RunStatus(str, Enum):
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"


class Speaker(str, Enum):
    """论坛五角色（与 baton 别名、前端 types 一致，小写值）。"""

    LEX = "lex"
    WUWEI = "wuwei"
    LIPTAN = "liptan"
    COOK = "cook"
    JENSEN = "jensen"


class Turn(BaseModel):
    round: int
    speaker: Speaker
    text: str
    created_at: float


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    speaker: str  # "user" | lex|wuwei|liptan|cook|jensen
    target_speaker: Optional[str] = None
    content: str
    created_at: float


class DebateRun(BaseModel):
    run_id: str
    status: RunStatus
    topic: str
    turns: List[Turn]
    error: Optional[str] = None
    finished_at: Optional[float] = None
    judge_result: Optional[str] = None
    chat_history: List[ChatMessage] = []


class StartDebateResponse(BaseModel):
    run_id: str


class DebateStatusResponse(BaseModel):
    status: RunStatus
    current_round: int
    turns: List[Turn]
    error: Optional[str] = None
    judge_result: Optional[str] = None
