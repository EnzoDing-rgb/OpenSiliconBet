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
    # forum | jensen_vc | liptan_tag — 前端可渲染串场/收尾样式
    kind: str = "forum"


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
    # 为 True 时：下一轮论坛发言开始前跳出循环，直接进入黄仁勋串场
    skip_to_jensen: bool = False
    # Video Call：串场独白流式输出（仅轮询展示；落库后清空）
    jensen_stream_text: Optional[str] = None
    # TTS：跳过当前及后续非 jensen_vc 段，只播黄仁勋（由 WS skip_audio_until_jensen 置位）
    tts_skip_to_jensen: bool = False
    # Lex review triggered: set after audience Q&A ends; TTS checks this before playing Lex
    lex_review_pending: bool = False


class StartDebateResponse(BaseModel):
    run_id: str


class DebateStatusResponse(BaseModel):
    status: RunStatus
    current_round: int
    turns: List[Turn]
    error: Optional[str] = None
    judge_result: Optional[str] = None
    jensen_stream_text: Optional[str] = None
