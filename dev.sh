#!/usr/bin/env bash
set -euo pipefail

# Colors
GREEN='\033[0;32m'
NC='\033[0m' # No Color

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

TUNNEL_MODE="0"
if [[ "${1:-}" == "--tunnel" ]]; then
  TUNNEL_MODE="1"
fi

BACKEND_HOST="${BACKEND_HOST:-0.0.0.0}"
BACKEND_PORT="${BACKEND_PORT:-9000}"
FRONTEND_HOST="${FRONTEND_HOST:-0.0.0.0}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"

PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${VENV_DIR:-$ROOT_DIR/.venv}"

backend_pid=""
frontend_pid=""
tunnel_pid=""

# Kill any process using our ports before starting
kill_port() {
  local port="$1"
  if command -v lsof >/dev/null 2>&1; then
    local pids
    pids="$(lsof -t -i:"$port" 2>/dev/null || true)"
    if [[ -n "$pids" ]]; then
      echo "Killing old processes on port $port..."
      kill -9 $pids >/dev/null 2>&1 || true
    fi
  elif command -v fuser >/dev/null 2>&1; then
    fuser -k -9 "${port}/tcp" >/dev/null 2>&1 || true
  fi
}

kill_port "$BACKEND_PORT"
kill_port "$FRONTEND_PORT"

cleanup() {
  if [[ -n "${frontend_pid}" ]] && kill -0 "${frontend_pid}" >/dev/null 2>&1; then
    kill "${frontend_pid}" >/dev/null 2>&1 || true
  fi
  if [[ -n "${backend_pid}" ]] && kill -0 "${backend_pid}" >/dev/null 2>&1; then
    kill "${backend_pid}" >/dev/null 2>&1 || true
  fi
  if [[ -n "${tunnel_pid}" ]] && kill -0 "${tunnel_pid}" >/dev/null 2>&1; then
    kill "${tunnel_pid}" >/dev/null 2>&1 || true
  fi
  # Final kill any leftover processes on ports
  kill_port "$BACKEND_PORT"
  kill_port "$FRONTEND_PORT"
  echo -e "\n👋 All services stopped."
}
trap cleanup EXIT INT TERM

# Ensure venv
if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
  "${PYTHON_BIN}" -m venv "${VENV_DIR}"
fi
# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"

# Install deps silently
python -m pip install --upgrade pip >/dev/null
pip install -r "${ROOT_DIR}/backend/requirements.txt" >/dev/null
if [[ ! -d "${ROOT_DIR}/frontend/node_modules" ]]; then
  (cd "${ROOT_DIR}/frontend" && npm install >/dev/null)
fi

# Start backend in background, logs to .backend.log
echo "Starting backend on ${BACKEND_HOST}:${BACKEND_PORT}"
: >"${ROOT_DIR}/.backend.log"
(cd "${ROOT_DIR}" && uvicorn backend.app:app \
  --host "${BACKEND_HOST}" \
  --port "${BACKEND_PORT}") \
  >>"${ROOT_DIR}/.backend.log" 2>&1 &
backend_pid="$!"

# Wait for health check
health_url="http://127.0.0.1:${BACKEND_PORT}/api/health"
for i in {1..60}; do
  if curl -fsS "${health_url}" >/dev/null 2>&1; then
    break
  fi
  sleep 0.5
done

# Start frontend in background, logs to .frontend.log
echo "Starting frontend on ${FRONTEND_HOST}:${FRONTEND_PORT}"
: >"${ROOT_DIR}/.frontend.log"
(cd "${ROOT_DIR}/frontend" && npm run dev -- --host "${FRONTEND_HOST}" --port "${FRONTEND_PORT}") \
  >>"${ROOT_DIR}/.frontend.log" 2>&1 &
frontend_pid="$!"

# Print access URLs with ONLY URLs in green
echo
echo "Local access (Linux):"
echo -e "  ${GREEN}http://127.0.0.1:${FRONTEND_PORT}${NC}"
echo

linux_ip="$(
  python - <<'PY'
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
try:
    s.connect(("8.8.8.8", 80))
    print(s.getsockname()[0])
except Exception:
    print("")
finally:
    s.close()
PY
)"
if [[ -n "${linux_ip}" ]]; then
  echo "LAN access (Mac/other devices):"
  echo -e "  ${GREEN}http://${linux_ip}:${FRONTEND_PORT}${NC}"
  echo
fi

if [[ "${TUNNEL_MODE}" == "1" ]]; then
  if ! command -v cloudflared >/dev/null 2>&1; then
    echo "cloudflared not found. Install it first, or run without --tunnel."
    exit 1
  fi

  tunnel_log="${ROOT_DIR}/.tunnel.log"
  : > "${tunnel_log}"
  cloudflared tunnel --url "http://127.0.0.1:${FRONTEND_PORT}" >"${tunnel_log}" 2>&1 &
  tunnel_pid="$!"

  public_url=""
  for i in {1..120}; do
    public_url="$(
      python - <<'PY' "${tunnel_log}"
import re, sys
path = sys.argv[1]
try:
    data = open(path, "r", encoding="utf-8", errors="ignore").read()
except FileNotFoundError:
    print("")
    raise SystemExit(0)
m = re.findall(r"https://[a-zA-Z0-9.-]*trycloudflare\.com", data)
print(m[-1] if m else "")
PY
    )"
    if [[ -n "${public_url}" ]]; then
      break
    fi
    sleep 0.5
  done

  if [[ -n "${public_url}" ]]; then
    echo "Public tunnel URL:"
    echo -e "  ${GREEN}${public_url}${NC}"
    echo
  fi
fi

echo "📝 Disclaimer: 推理观点由LLM基于公开思想蒸馏生成，仅为学术讨论，非本人观点。"
echo

echo "⚡ Running. Press Ctrl+C to stop all services."
echo "----------------------------------------"
echo

# Filter frontend log to greenify URLs before tailing
# Greenify any http:// URLs in output
tail -f "${ROOT_DIR}/.backend.log" "${ROOT_DIR}/.frontend.log" | while IFS= read -r line; do
  if [[ "$line" =~ http:// ]]; then
    # Greenify the whole line if it contains URL (vite outputs the URLs on its own line)
    echo -e "${GREEN}${line}${NC}"
  else
    echo "$line"
  fi
done
