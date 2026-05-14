import asyncio
import base64
import json
import re
import threading
import time
from typing import Optional, Callable, List, Any
import dashscope
from dashscope.audio.qwen_tts_realtime import QwenTtsRealtime, QwenTtsRealtimeCallback
from fastapi import WebSocket, WebSocketDisconnect

from .models import DebateRun, Turn, Speaker, RunStatus


# ========== Configuration ==========
# Get from environment variable
DASHSCOPE_API_KEY = None
# speaker.value -> DashScope voice id（过渡期可五键同一克隆）
VOICE_BY_SPEAKER: dict[str, Optional[str]] = {
    Speaker.LEX.value: None,
    Speaker.WUWEI.value: None,
    Speaker.LIPTAN.value: None,
    Speaker.COOK.value: None,
    Speaker.JENSEN.value: None,
}
# TTS model (must match voice cloning target_model)
TTS_MODEL = "qwen3-tts-vc-realtime-2026-01-15"
# Aliyun websocket url (for China region)
TTS_WS_URL = "wss://dashscope.aliyuncs.com/api-ws/v1/realtime"
# Text chunking config
MIN_CHARS = 40
MAX_CHARS = 180
FLUSH_PUNCT = r"[。！？；\n]"


def init_tts(
    api_key: str,
    speaker_voices: dict[str, str],
    model: str = "qwen3-tts-vc-realtime-2026-01-15",
    url: str = "wss://dashscope.aliyuncs.com/api-ws/v1/realtime",
) -> None:
    """Initialize TTS config, call this once at startup. speaker_voices keys: lex,wuwei,liptan,cook,jensen."""
    global DASHSCOPE_API_KEY, VOICE_BY_SPEAKER, TTS_MODEL, TTS_WS_URL
    DASHSCOPE_API_KEY = api_key
    for k in (Speaker.LEX.value, Speaker.WUWEI.value, Speaker.LIPTAN.value, Speaker.COOK.value, Speaker.JENSEN.value):
        VOICE_BY_SPEAKER[k] = (speaker_voices.get(k) or "").strip() or None
    TTS_MODEL = model
    TTS_WS_URL = url
    dashscope.api_key = api_key


class TextChunker:
    """Cut full text into chunks for streaming TTS:
    - flush when reach MIN_CHARS and hit punctuation
    - flush when reach MAX_CHARS regardless
    - balance between low latency and good prosody
    """

    def __init__(self, min_chars: int = MIN_CHARS, max_chars: int = MAX_CHARS, punct_re: str = FLUSH_PUNCT):
        self.min_chars = min_chars
        self.max_chars = max_chars
        self.punct_re = re.compile(punct_re)
        self._buffer: List[str] = []
        self._len = 0

    def push(self, text: str) -> List[str]:
        """Push new text, return ready chunks to send"""
        out: List[str] = []
        words = list(text)
        for c in words:
            self._buffer.append(c)
            self._len += 1

            # Check if we should flush
            need_flush = False
            # Hard boundary
            if self._len >= self.max_chars:
                need_flush = True
            # Sentence-ending punctuation should flush immediately (even if < min_chars)
            elif self.punct_re.search(c):
                need_flush = True
            # Soft boundary: once we reached min_chars, allow flushing on weaker separators
            elif self._len >= self.min_chars and c in ("，", "、", "：", ":", ",", "\n"):
                need_flush = True

            if need_flush:
                chunk = "".join(self._buffer)
                out.append(chunk)
                self._buffer.clear()
                self._len = 0

        return out

    def flush_remaining(self) -> Optional[str]:
        """Flush any remaining text in buffer"""
        if self._len == 0:
            return None
        chunk = "".join(self._buffer)
        self._buffer.clear()
        self._len = 0
        return chunk


class TtsSession:
    """One TTS session for a single debate turn"""

    def __init__(
        self,
        websocket: WebSocket,
        speaker: Speaker,
        full_text: str,
        round_num: int,
        turn_index: int,
        *,
        runner: Any = None,
        run_id: Optional[str] = None,
        turn_kind: str = "forum",
    ):
        self.websocket = websocket
        self.speaker = speaker
        self.full_text = full_text
        self.round_num = round_num
        self.turn_index = turn_index
        self.runner = runner
        self.run_id = run_id
        self.turn_kind = turn_kind or "forum"
        self.chunker = TextChunker()
        self._done = asyncio.Event()
        self._error: Optional[Exception] = None
        self._phase_playing_sent = False

    def _should_abort_tts(self) -> bool:
        if not self.runner or not self.run_id:
            return False
        run = self.runner.get_run_status(self.run_id)
        if not run or not getattr(run, "tts_skip_to_jensen", False):
            return False
        return self.turn_kind != "jensen_vc"

    def _get_voice_id(self) -> str:
        key = self.speaker.value if isinstance(self.speaker, Speaker) else str(self.speaker)
        vid = VOICE_BY_SPEAKER.get(key) if VOICE_BY_SPEAKER else None
        if not vid:
            raise RuntimeError(f"No DashScope voice id configured for speaker={key!r}")
        return vid

    async def _emit_phase(self, phase: str, message: Optional[str] = None) -> None:
        sp = self.speaker.value if hasattr(self.speaker, "value") else str(self.speaker)
        payload: dict = {
            "type": "phase",
            "phase": phase,
            "turn_index": self.turn_index,
            "round": self.round_num,
            "speaker": sp,
        }
        if message:
            payload["message"] = message
        await self.websocket.send_text(json.dumps(payload))

    async def run(self) -> None:
        """Run the full session: chunk text → send to aliyun → forward audio to browser"""
        # 1. Send meta to browser first
        # Format: PCM_24000HZ_MONO_16BIT matches what dashscope returns
        meta = {
            "type": "meta",
            "format": "PCM_24000HZ_MONO_16BIT",
            "speaker": self.speaker.value if hasattr(self.speaker, 'value') else self.speaker,
            "round": self.round_num,
            "turn_index": self.turn_index,
        }
        await self.websocket.send_text(json.dumps(meta))
        await self._emit_phase("connecting", message="正在连接语音合成服务…")

        # 2. Setup callback for dashscope: forward audio to browser
        class Callback(QwenTtsRealtimeCallback):
            def __init__(self, outer: "TtsSession"):
                self.outer = outer
                self.complete_event = threading.Event()
                self.loop = asyncio.get_running_loop()

            def on_open(self) -> None:
                pass

            def on_close(self, close_status_code, close_msg) -> None:
                self.complete_event.set()

            def on_event(self, response: dict) -> None:
                """Handle events from aliyun: audio delta goes to browser"""
                try:
                    event_type = response.get("type", "")
                    if event_type == "response.audio.delta":
                        recv_audio_b64 = response.get("delta")
                        if not recv_audio_b64:
                            return
                        if not self.outer._phase_playing_sent:
                            self.outer._phase_playing_sent = True
                            asyncio.run_coroutine_threadsafe(self.outer._emit_phase("playing"), self.loop)
                        pcm_bytes = base64.b64decode(recv_audio_b64)
                        asyncio.run_coroutine_threadsafe(
                            self.outer.websocket.send_bytes(pcm_bytes),
                            self.loop,
                        )
                    elif event_type == "response.done":
                        # End of current response (may arrive before session.finished)
                        pass
                    elif event_type == "session.finished":
                        self.complete_event.set()
                except Exception as e:
                    self.outer._error = e
                    self.complete_event.set()

        callback = Callback(self)
        aborted_early = False

        # 3. Connect to ali yun websocket (with retries because SDK has fixed 5s connect timeout)
        qwen_tts = None
        try:
            qwen_tts = QwenTtsRealtime(
                model=TTS_MODEL,
                callback=callback,
                url=TTS_WS_URL,
            )
            last_connect_err: Optional[Exception] = None
            for attempt in range(1, 5):
                try:
                    qwen_tts.connect()
                    last_connect_err = None
                    break
                except TimeoutError as e:
                    last_connect_err = e
                    # exponential-ish backoff: 0.6s, 1.2s, 2.4s, 4.8s
                    await asyncio.sleep(0.6 * (2 ** (attempt - 1)))
            if last_connect_err is not None:
                raise last_connect_err
            voice_id = self._get_voice_id()
            qwen_tts.update_session(
                voice=voice_id,
                response_format=dashscope.audio.qwen_tts_realtime.AudioFormat.PCM_24000HZ_MONO_16BIT,
                mode="server_commit",
            )
            await self._emit_phase("generating", message="正在合成语音…")

            # 4. Chunk text and send to ali yun
            chunks = self.chunker.push(self.full_text)
            for chunk in chunks:
                if self._should_abort_tts():
                    aborted_early = True
                    break
                qwen_tts.append_text(chunk)
                await asyncio.sleep(0.05)

            if not aborted_early:
                remaining = self.chunker.flush_remaining()
                if remaining:
                    qwen_tts.append_text(remaining)
                qwen_tts.finish()
                await asyncio.to_thread(callback.complete_event.wait)
            else:
                try:
                    qwen_tts.finish()
                except Exception:
                    pass
                try:
                    qwen_tts.close()
                except Exception:
                    pass
                callback.complete_event.set()
        finally:
            try:
                if qwen_tts is not None:
                    qwen_tts.close()
            except Exception:
                pass

        if self._error:
            # Send error to browser
            await self.websocket.send_text(json.dumps({
                "type": "error",
                "message": str(self._error),
                "turn_index": self.turn_index,
            }))
            self._done.set()
            return

        # 5. Done, notify browser
        await self._emit_phase("completed", message="本段语音已生成完毕")
        await self.websocket.send_text(json.dumps({
            "type": "turn_done",
            "speaker": self.speaker.value if hasattr(self.speaker, 'value') else self.speaker,
            "round": self.round_num,
            "turn_index": self.turn_index,
            "skip_playback": aborted_early,
        }))
        self._done.set()

    async def wait_done(self) -> None:
        await self._done.wait()


class TtsManager:
    """Manager for TTS sessions: one at a time, matches fixed debate order"""

    def __init__(self):
        self._current_session: Optional[TtsSession] = None
        # Prevent accidental multi-client “duel playback” for same run_id
        self._active_run_audio: dict[str, int] = {}

    def _claim_run_audio(self, run_id: str) -> bool:
        cur = self._active_run_audio.get(run_id, 0)
        if cur > 0:
            return False
        self._active_run_audio[run_id] = 1
        return True

    def _release_run_audio(self, run_id: str) -> None:
        if run_id in self._active_run_audio:
            self._active_run_audio.pop(run_id, None)

    async def handle_connection(self, websocket: WebSocket, runner) -> None:
        """Handle incoming websocket connection from browser"""
        run_id: Optional[str] = None
        is_test = False
        try:
            # Wait for start message
            start_msg = await websocket.receive_text()
            data = json.loads(start_msg)
            if data.get("type") != "start":
                await websocket.close()
                return

            # Resolve run_id from query params (preferred), fallback to latest run
            run_id = websocket.query_params.get("run_id")
            is_test = websocket.query_params.get("test") == "1"
            if run_id and not is_test:
                if not self._claim_run_audio(run_id):
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": "This run is already playing audio in another tab/device.",
                    }))
                    await websocket.close()
                    return

            if is_test:
                # Minimal E2E: single fixed sentence
                session = TtsSession(
                    websocket=websocket,
                    speaker=Speaker.LEX,
                    full_text="你好，这是实时语音合成链路的最小自测。",
                    round_num=1,
                    turn_index=0,
                )
                self._current_session = session
                await session.run()
                self._current_session = None
                await websocket.send_text(json.dumps({"type": "all_done"}))
                return

            # Stream turns as they appear while debate is running
            cmd_queue: asyncio.Queue = asyncio.Queue()

            async def pump_ws() -> None:
                try:
                    while True:
                        raw = await websocket.receive_text()
                        data = json.loads(raw)
                        if data.get("type") == "skip_audio_until_jensen":
                            r = runner.get_run_status(run_id) if run_id else None
                            if r is not None:
                                r.tts_skip_to_jensen = True
                            continue
                        await cmd_queue.put(data)
                except WebSocketDisconnect:
                    await cmd_queue.put({"type": "__disconnect__"})

            async def wait_ack(expected_turn: int) -> bool:
                while True:
                    msg = await cmd_queue.get()
                    if msg.get("type") == "__disconnect__":
                        return False
                    if msg.get("type") == "skip_audio_until_jensen":
                        r = runner.get_run_status(run_id) if run_id else None
                        if r is not None:
                            r.tts_skip_to_jensen = True
                        continue
                    if msg.get("type") == "ack_turn_done" and msg.get("turn_index") == expected_turn:
                        return True

            pump_task = asyncio.create_task(pump_ws())
            turn_index = 0
            last_wait_phase = 0.0
            try:
                while True:
                    run = runner.get_run_status(run_id) if run_id else runner.get_current_run()
                    if not run:
                        await websocket.send_text(json.dumps({"type": "error", "message": "Run not found"}))
                        await websocket.close()
                        return

                    if run.status == RunStatus.ERROR:
                        await websocket.send_text(json.dumps({"type": "error", "message": run.error or "Debate run error"}))
                        await websocket.close()
                        return

                    if turn_index < len(run.turns):
                        turn = run.turns[turn_index]
                        run = runner.get_run_status(run_id) if run_id else run
                        tkind = getattr(turn, "kind", None) or "forum"
                        if run is not None and getattr(run, "tts_skip_to_jensen", False) and tkind != "jensen_vc":
                            await websocket.send_text(json.dumps({
                                "type": "turn_done",
                                "speaker": turn.speaker.value if hasattr(turn.speaker, "value") else str(turn.speaker),
                                "round": turn.round,
                                "turn_index": turn_index,
                                "skip_playback": True,
                            }))
                            ok = await wait_ack(turn_index)
                            if not ok:
                                return
                            turn_index += 1
                            continue

                        if tkind == "jensen_vc" and run is not None and getattr(run, "tts_skip_to_jensen", False):
                            run.tts_skip_to_jensen = False

                        from .debate_runner import _tts_speech_optimization
                        tts_text = _tts_speech_optimization(turn.text)
                        session = TtsSession(
                            websocket,
                            turn.speaker,
                            tts_text,
                            turn.round,
                            turn_index=turn_index,
                            runner=runner,
                            run_id=run_id,
                            turn_kind=tkind,
                        )
                        self._current_session = session
                        await session.run()
                        self._current_session = None
                        ok = await wait_ack(turn_index)
                        if not ok:
                            return
                        turn_index += 1
                        continue

                    if run.status == RunStatus.DONE:
                        break

                    if run.status == RunStatus.RUNNING:
                        now = time.monotonic()
                        if now - last_wait_phase >= 2.0:
                            last_wait_phase = now
                            await websocket.send_text(json.dumps({
                                "type": "phase",
                                "phase": "waiting_content",
                                "turn_index": turn_index,
                                "message": "正在等待下一位研究者的文本生成…",
                            }))

                    await asyncio.sleep(0.2)
            finally:
                pump_task.cancel()
                try:
                    await pump_task
                except asyncio.CancelledError:
                    pass

            # All done
            await websocket.send_text(json.dumps({"type": "all_done"}))

        except WebSocketDisconnect:
            # Client disconnected, clean up
            if self._current_session:
                # No need to keep going
                pass
        finally:
            if run_id and not is_test:
                self._release_run_audio(run_id)
