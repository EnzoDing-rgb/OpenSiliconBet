#!/usr/bin/env python3
"""
Batch Qwen-TTS voice enrollment (Beijing) for OpenSiliconBet five debaters.

Reads local audio under assets/, calls DashScope customization API, writes
VOICE_ID_LEX / WUWEI / LIPTAN / COOK / JENSEN into project .env.

Requires: DASHSCOPE_API_KEY in environment (or .env next to repo root).
target_model must match TTS_MODEL (default realtime 2026-01-15).
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from pathlib import Path

try:
    import requests
except ImportError as e:
    print("Install requests: pip install requests", file=sys.stderr)
    raise SystemExit(1) from e

REPO_ROOT = Path(__file__).resolve().parents[1]
ASSETS_DIR = REPO_ROOT / "assets"
ENV_PATH = REPO_ROOT / ".env"
CUSTOMIZATION_URL = "https://dashscope.aliyuncs.com/api/v1/services/audio/tts/customization"
DEFAULT_TARGET = "qwen3-tts-vc-realtime-2026-01-15"

# Filename stem (case-insensitive) -> (env var, preferred_name for API)
DEBATER_FILES: list[tuple[str, str, str]] = [
    ("Lex", "VOICE_ID_LEX", "lex"),
    ("Wuwei", "VOICE_ID_WUWEI", "wuwei"),
    ("Lip-Bu", "VOICE_ID_LIPTAN", "liptan"),
    ("Tim_Cook", "VOICE_ID_COOK", "cook"),
    ("Jensen_Huang", "VOICE_ID_JENSEN", "jensen"),
]

MIME_BY_SUFFIX = {".m4a": "audio/mp4", ".mp3": "audio/mpeg", ".wav": "audio/wav"}


def _load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


def _find_audio(stem: str) -> Path | None:
    for p in ASSETS_DIR.iterdir():
        if not p.is_file():
            continue
        if p.stem.lower() == stem.lower():
            return p
    return None


def _mime(path: Path) -> str:
    return MIME_BY_SUFFIX.get(path.suffix.lower(), "audio/mpeg")


def create_voice(
    api_key: str,
    audio_path: Path,
    preferred_name: str,
    target_model: str,
) -> str:
    b64 = base64.b64encode(audio_path.read_bytes()).decode("ascii")
    data_uri = f"data:{_mime(audio_path)};base64,{b64}"
    payload = {
        "model": "qwen-voice-enrollment",
        "input": {
            "action": "create",
            "target_model": target_model,
            "preferred_name": preferred_name,
            "audio": {"data": data_uri},
        },
    }
    r = requests.post(
        CUSTOMIZATION_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=120,
    )
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:2000]}")
    data = r.json()
    try:
        return str(data["output"]["voice"])
    except (KeyError, TypeError) as e:
        raise RuntimeError(f"Bad response JSON: {json.dumps(data, ensure_ascii=False)[:2000]}") from e


def _merge_env(keys_to_set: dict[str, str]) -> str:
    replace = set(keys_to_set.keys())
    lines: list[str] = []
    if ENV_PATH.is_file():
        for raw in ENV_PATH.read_text(encoding="utf-8", errors="replace").splitlines():
            key = raw.split("=", 1)[0].strip() if "=" in raw else None
            if key in replace:
                continue
            lines.append(raw.rstrip("\n"))
    # append block
    lines.append("")
    lines.append("# --- Qwen voice enrollment (scripts/enroll_voices.py) ---")
    for k in sorted(keys_to_set.keys()):
        lines.append(f"{k}={keys_to_set[k]}")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="Print actions only, no API / no .env write")
    ap.add_argument(
        "--target-model",
        default=os.getenv("TTS_MODEL", DEFAULT_TARGET),
        help="Must match realtime TTS model (default: %(default)s)",
    )
    args = ap.parse_args()

    _load_dotenv(ENV_PATH)
    api_key = (os.getenv("DASHSCOPE_API_KEY") or "").strip()
    if not api_key and not args.dry_run:
        print("Missing DASHSCOPE_API_KEY (set env or add to .env)", file=sys.stderr)
        return 2

    if not ASSETS_DIR.is_dir():
        print(f"Missing assets dir: {ASSETS_DIR}", file=sys.stderr)
        return 2

    resolved: list[tuple[str, str, Path]] = []
    for stem, env_key, preferred in DEBATER_FILES:
        p = _find_audio(stem)
        if not p:
            print(f"Missing audio for {stem} under {ASSETS_DIR}", file=sys.stderr)
            return 2
        resolved.append((env_key, preferred, p))

    print(f"target_model={args.target_model}")
    for env_key, preferred, p in resolved:
        print(f"  {env_key} <- {p.name} (preferred_name={preferred})")

    if args.dry_run:
        print("dry-run: no API calls")
        return 0

    results: dict[str, str] = {}
    for env_key, preferred, p in resolved:
        print(f"enrolling {env_key} ...", flush=True)
        voice = create_voice(api_key, p, preferred, args.target_model)
        results[env_key] = voice
        print(f"  ok voice={voice[:48]}...")

    ENV_PATH.write_text(_merge_env(results), encoding="utf-8")
    print(f"Wrote {len(results)} keys to {ENV_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
