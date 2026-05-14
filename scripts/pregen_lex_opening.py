#!/usr/bin/env python3
"""
Synthesize Lex 0.5 opening MP3s (long + skip short) via DashScope Qwen realtime TTS.

Reads exact copy from docs/background/lex-opening-script.md.
Uses VOICE_ID_LEX if set, else VOICE_ID_MEARSHEIMER (legacy).
Writes frontend/public/audio/lex-opening-{long,short}.mp3 (needs ffmpeg).

Run from repo root:
  .venv/bin/python scripts/pregen_lex_opening.py
"""
from __future__ import annotations

import argparse
import base64
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

import dashscope
from dashscope.audio.qwen_tts_realtime import (
    AudioFormat,
    QwenTtsRealtime,
    QwenTtsRealtimeCallback,
)

REPO = Path(__file__).resolve().parents[1]
SCRIPT_MD = REPO / "docs" / "background" / "lex-opening-script.md"
OUT_DIR = REPO / "frontend" / "public" / "audio"
OUT_LONG = OUT_DIR / "lex-opening-long.mp3"
OUT_SHORT = OUT_DIR / "lex-opening-short.mp3"

# Import after REPO on path
sys.path.insert(0, str(REPO))
from backend.tts_manager import TextChunker, TTS_MODEL, TTS_WS_URL  # noqa: E402


def _load_dotenv() -> None:
    p = REPO / ".env"
    if not p.is_file():
        return
    for raw in p.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


def parse_script_md(md: str) -> tuple[str, str]:
    m_long = re.search(r"## 长版[^\n]*\n+(.+?)\n+---\s*\n+## 短版", md, re.DOTALL)
    if not m_long:
        raise ValueError("Could not parse long script from lex-opening-script.md")
    long_text = m_long.group(1).strip()
    short_sec = md.split("## 短版", 1)[1]
    m_short = re.search(r">\s*(.+)", short_sec)
    if not m_short:
        raise ValueError("Could not parse short line (blockquote) from lex-opening-script.md")
    short_text = m_short.group(1).strip()
    return long_text, short_text


class _Collect(QwenTtsRealtimeCallback):
    def __init__(self) -> None:
        self.pcm = bytearray()
        self.done = threading.Event()
        self.error: str | None = None

    def on_open(self) -> None:
        pass

    def on_close(self, _code, _msg) -> None:
        self.done.set()

    def on_event(self, response: dict) -> None:
        et = response.get("type", "")
        if et == "response.audio.delta":
            b64 = response.get("delta")
            if b64:
                self.pcm.extend(base64.b64decode(b64))
        elif et == "session.finished":
            self.done.set()
        elif et == "error":
            self.error = str(response)
            self.done.set()


def synth_pcm(text: str, *, voice: str, model: str, ws_url: str, api_key: str) -> bytes:
    dashscope.api_key = api_key
    cb = _Collect()
    tts = QwenTtsRealtime(model=model, callback=cb, url=ws_url)
    last_err: Exception | None = None
    for attempt in range(1, 5):
        try:
            tts.connect()
            last_err = None
            break
        except TimeoutError as e:
            last_err = e
            time.sleep(0.6 * (2 ** (attempt - 1)))
    if last_err is not None:
        raise last_err
    try:
        tts.update_session(
            voice=voice,
            response_format=AudioFormat.PCM_24000HZ_MONO_16BIT,
            mode="server_commit",
        )
        chunker = TextChunker()
        for piece in chunker.push(text):
            tts.append_text(piece)
            time.sleep(0.05)
        tail = chunker.flush_remaining()
        if tail:
            tts.append_text(tail)
        tts.finish()
        if not cb.done.wait(timeout=600):
            raise TimeoutError("TTS session did not finish in 600s")
        if cb.error:
            raise RuntimeError(cb.error)
        return bytes(cb.pcm)
    finally:
        try:
            tts.close()
        except Exception:
            pass


def pcm_to_mp3(pcm: bytes, out_mp3: Path) -> None:
    out_mp3.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen(
        [
            "ffmpeg",
            "-y",
            "-f",
            "s16le",
            "-ar",
            "24000",
            "-ac",
            "1",
            "-i",
            "pipe:0",
            "-codec:a",
            "libmp3lame",
            "-qscale:a",
            "4",
            str(out_mp3),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    assert proc.stdin
    proc.stdin.write(pcm)
    proc.stdin.close()
    err = proc.stderr.read().decode("utf-8", errors="replace") if proc.stderr else ""
    code = proc.wait(timeout=120)
    if code != 0:
        raise RuntimeError(f"ffmpeg failed ({code}): {err[-2000:]}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    _load_dotenv()
    api_key = (os.getenv("DASHSCOPE_API_KEY") or "").strip()
    voice = (
        (os.getenv("VOICE_ID_LEX") or "").strip()
        or (os.getenv("VOICE_ID_MEARSHEIMER") or "").strip()
        or (os.getenv("VOICE_ID_DEFAULT") or "").strip()
    )
    model = (os.getenv("TTS_MODEL") or "").strip() or TTS_MODEL
    ws_url = (os.getenv("TTS_WS_URL") or "").strip() or TTS_WS_URL

    if not SCRIPT_MD.is_file():
        print(f"Missing {SCRIPT_MD}", file=sys.stderr)
        return 2
    md = SCRIPT_MD.read_text(encoding="utf-8")
    long_text, short_text = parse_script_md(md)

    if args.dry_run:
        print(f"voice={voice[:40]}... model={model}")
        print(f"long chars={len(long_text)} short={short_text!r}")
        return 0

    if not api_key:
        print("Missing DASHSCOPE_API_KEY", file=sys.stderr)
        return 2
    if not voice:
        print("Missing VOICE_ID_LEX (or VOICE_ID_MEARSHEIMER fallback)", file=sys.stderr)
        return 2

    print("Synthesizing long opening (realtime TTS → mp3)...", flush=True)
    pcm_long = synth_pcm(long_text, voice=voice, model=model, ws_url=ws_url, api_key=api_key)
    if len(pcm_long) < 1000:
        raise SystemExit(f"Long PCM too small ({len(pcm_long)} bytes); check API / voice / model")
    pcm_to_mp3(pcm_long, OUT_LONG)
    print(f"Wrote {OUT_LONG} ({OUT_LONG.stat().st_size} bytes)")

    print("Synthesizing short skip line...", flush=True)
    pcm_short = synth_pcm(short_text, voice=voice, model=model, ws_url=ws_url, api_key=api_key)
    pcm_to_mp3(pcm_short, OUT_SHORT)
    print(f"Wrote {OUT_SHORT} ({OUT_SHORT.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130) from None
