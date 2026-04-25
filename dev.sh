#!/usr/bin/env bash
set -euo pipefail

# Colors
GREEN='\033[0;32m'
NC='\033[0m' # No Color

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Clean up all previous processes, ports, and leftovers
cleanup_all() {
  echo "🧹 Cleaning up all previous processes and占用..."

  # Kill any cloudflared processes started by this script
  pkill -f "cloudflared.*national_security" 2>/dev/null || true
  pkill -9 -f "cloudflared" 2>/dev/null || true

  # Kill any uvicorn/vite processes on our ports
  local ports=("9000" "5173" "20242")
  for port in "${ports[@]}"; do
    if command -v lsof >/dev/null 2>&1; then
      local pids
      pids="$(lsof -t -i:"$port" 2>/dev/null || true)"
      if [[ -n "$pids" ]]; then
        kill -9 $pids >/dev/null 2>&1 || true
      fi
    fi
    if command -v fuser >/dev/null 2>&1; then
      fuser -k -9 "${port}/tcp" >/dev/null 2>&1 || true
    fi
  done

  # Clean up log files
  rm -f "${ROOT_DIR}/.backend.log" "${ROOT_DIR}/.frontend.log" "${ROOT_DIR}/.tunnel.log"

  # Also clean up any leftover child processes from previous runs
  if [[ -f "${ROOT_DIR}/.frontend.pid" ]]; then
    kill -9 $(<"${ROOT_DIR}/.frontend.pid") 2>/dev/null || true
    rm -f "${ROOT_DIR}/.frontend.pid"
  fi
  if [[ -f "${ROOT_DIR}/.backend.pid" ]]; then
    kill -9 $(<"${ROOT_DIR}/.backend.pid") 2>/dev/null || true
    rm -f "${ROOT_DIR}/.backend.pid"
  fi
  if [[ -f "${ROOT_DIR}/.tunnel.pid" ]]; then
    kill -9 $(<"${ROOT_DIR}/.tunnel.pid") 2>/dev/null || true
    rm -f "${ROOT_DIR}/.tunnel.pid"
  fi

  # Give OS time to release sockets
  sleep 0.5
  echo "✅ Cleanup complete."
  echo
}

# Run cleanup at startup
cleanup_all

TUNNEL_MODE="0"          # Quick Tunnel (trycloudflare.com)
PROD_MODE="0"            # Serve built frontend via FastAPI (single-port)
NAMED_TUNNEL_NAME=""     # Cloudflare named tunnel (requires pre-created tunnel)
INIT_ENV_MODE="0"        # Create .env from .env.example if missing
SETUP_CLOUDFLARE_MODE="0"
PUBLIC_HOSTNAME="app.enzoding.net"
DEFAULT_TUNNEL_NAME="enzo-amusement-park"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --tunnel)
      TUNNEL_MODE="1"
      shift
      ;;
    --prod)
      PROD_MODE="1"
      shift
      ;;
    --tunnel-name)
      NAMED_TUNNEL_NAME="${2:-}"
      shift 2
      ;;
    --hostname)
      PUBLIC_HOSTNAME="${2:-}"
      shift 2
      ;;
    --init-env)
      INIT_ENV_MODE="1"
      shift
      ;;
    --setup-cloudflare)
      SETUP_CLOUDFLARE_MODE="1"
      shift
      ;;
    -h|--help)
      cat <<'EOF'
Usage:
  ./dev.sh
  ./dev.sh --init-env
  ./dev.sh --tunnel
  ./dev.sh --prod --tunnel-name enzo-amusement-park
  ./dev.sh --setup-cloudflare --hostname app.enzoding.net --tunnel-name enzo-amusement-park

Modes:
  --init-env: create .env from .env.example if .env is missing
  default: start backend (9000) + vite dev server (5173)
  --tunnel: Cloudflare Quick Tunnel to vite dev server (URL changes on restart)
  --prod --tunnel-name: build frontend and serve via FastAPI on 9000, then run named tunnel to 9000
  --setup-cloudflare: login/create tunnel/write config/route DNS as much as Cloudflare allows
EOF
      exit 0
      ;;
    *)
      echo "Unknown argument: $1"
      exit 1
      ;;
  esac
done

BACKEND_HOST="${BACKEND_HOST:-0.0.0.0}"
BACKEND_PORT="${BACKEND_PORT:-9000}"
FRONTEND_HOST="${FRONTEND_HOST:-0.0.0.0}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"

PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${VENV_DIR:-$ROOT_DIR/.venv}"

if [[ -z "${NAMED_TUNNEL_NAME}" ]]; then
  NAMED_TUNNEL_NAME="${TUNNEL_NAME:-}"
fi

backend_pid=""
frontend_pid=""
tunnel_pid=""

init_env() {
  if [[ -f "${ROOT_DIR}/.env" ]]; then
    echo ".env already exists; leaving it unchanged."
    return 0
  fi
  if [[ ! -f "${ROOT_DIR}/.env.example" ]]; then
    echo ".env.example not found."
    return 1
  fi
  cp "${ROOT_DIR}/.env.example" "${ROOT_DIR}/.env"
  echo "Created .env from .env.example."
  echo "Fill API_KEY in .env before starting the app."
}

tunnel_id_for_name() {
  local name="$1"
  local tunnel_json
  tunnel_json="$(cloudflared tunnel list --output json 2>/dev/null || true)"
  TUNNEL_LIST_JSON="${tunnel_json}" python - "$name" <<'PY'
import json
import os
import sys

name = sys.argv[1]
try:
    tunnels = json.loads(os.environ.get("TUNNEL_LIST_JSON", "[]"))
except Exception:
    tunnels = []
if isinstance(tunnels, dict):
    tunnels = tunnels.get("tunnels", [])
for tunnel in tunnels:
    if tunnel.get("name") == name:
        print(tunnel.get("id", ""))
        break
PY
}

setup_cloudflare() {
  local tunnel_name="${NAMED_TUNNEL_NAME:-$DEFAULT_TUNNEL_NAME}"
  local hostname="${PUBLIC_HOSTNAME:-app.enzoding.net}"

  if ! command -v cloudflared >/dev/null 2>&1; then
    echo "cloudflared not found. Install it first."
    exit 1
  fi

  mkdir -p "${HOME}/.cloudflared"

  if [[ ! -f "${HOME}/.cloudflared/cert.pem" ]]; then
    echo "Opening Cloudflare login. Complete it in the browser, then return here."
    cloudflared tunnel login
  fi

  local tunnel_id
  tunnel_id="$(tunnel_id_for_name "${tunnel_name}")"
  if [[ -z "${tunnel_id}" ]]; then
    echo "Creating Cloudflare tunnel: ${tunnel_name}"
    cloudflared tunnel create "${tunnel_name}"
    tunnel_id="$(tunnel_id_for_name "${tunnel_name}")"
  fi

  if [[ -z "${tunnel_id}" ]]; then
    echo "Could not resolve tunnel id for ${tunnel_name}."
    exit 1
  fi

  cat >"${HOME}/.cloudflared/config.yml" <<EOF
tunnel: ${tunnel_id}
credentials-file: ${HOME}/.cloudflared/${tunnel_id}.json

ingress:
  - hostname: ${hostname}
    service: http://127.0.0.1:${BACKEND_PORT}
  - service: http_status:404
EOF

  echo "Wrote ${HOME}/.cloudflared/config.yml"
  echo "Routing ${hostname} to tunnel ${tunnel_name}..."
  if ! cloudflared tunnel route dns "${tunnel_name}" "${hostname}"; then
    echo "DNS route failed. This is expected if enzoding.net is not purchased or not in this Cloudflare account yet."
    echo "After buying/adding the domain, rerun:"
    echo "  ./dev.sh --setup-cloudflare --hostname ${hostname} --tunnel-name ${tunnel_name}"
    return 0
  fi

  echo "Cloudflare setup complete."
  echo "Start production with:"
  echo "  ./dev.sh --prod --tunnel-name ${tunnel_name}"
}

if [[ "${INIT_ENV_MODE}" == "1" ]]; then
  init_env
  exit 0
fi

if [[ "${SETUP_CLOUDFLARE_MODE}" == "1" ]]; then
  if [[ -z "${NAMED_TUNNEL_NAME}" ]]; then
    NAMED_TUNNEL_NAME="${DEFAULT_TUNNEL_NAME}"
  fi
  setup_cloudflare
  exit 0
fi

# Kill any process using our ports before starting
kill_port() {
  local port="$1"
  local killed="0"
  if command -v lsof >/dev/null 2>&1; then
    local pids
    pids="$(lsof -t -i:"$port" 2>/dev/null || true)"
    if [[ -n "$pids" ]]; then
      echo "Killing old processes on port $port..."
      kill -9 $pids >/dev/null 2>&1 || true
      killed="1"
    fi
  fi
  if command -v fuser >/dev/null 2>&1; then
    # Some environments don't report pids via lsof; fuser is a good fallback even if lsof exists.
    fuser -k -9 "${port}/tcp" >/dev/null 2>&1 || true
    killed="1"
  fi
  if [[ "${killed}" == "1" ]]; then
    # Give the OS a brief moment to release the socket.
    sleep 0.2
  fi
}

kill_port "$BACKEND_PORT"
kill_port "$FRONTEND_PORT"

is_fake_ip() {
  local ip="${1:-}"
  [[ "$ip" =~ ^198\.18\.[0-9]{1,3}\.[0-9]{1,3}$ ]]
}

detect_argotunnel_fake_ip() {
  python - <<'PY'
import socket
hosts = ["region1.v2.argotunnel.com", "api.trycloudflare.com"]
for host in hosts:
    try:
        infos = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except Exception:
        continue
    for info in infos:
        ip = info[4][0]
        if ip.startswith("198.18."):
            print(ip)
            raise SystemExit(0)
print("")
PY
}

write_argotunnel_hosts_block() {
  python - <<'PY'
import json
import urllib.request

fallback = {
    "region1.v2.argotunnel.com": ["198.41.192.37"],
    "region2.v2.argotunnel.com": ["198.41.200.193"],
    "api.trycloudflare.com": ["104.16.230.132"],
    "update.argotunnel.com": ["104.18.24.129"],
}

def resolve(host):
    url = f"https://cloudflare-dns.com/dns-query?name={host}&type=A"
    req = urllib.request.Request(url, headers={"accept": "application/dns-json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.load(resp)
        ips = [
            answer.get("data")
            for answer in data.get("Answer", [])
            if answer.get("type") == 1 and answer.get("data")
        ]
    except Exception:
        ips = []
    return ips or fallback[host]

print("# BEGIN national_security cloudflared real DNS")
for host in fallback:
    print(f"{resolve(host)[0]}\t{host}")
print("# END national_security cloudflared real DNS")
PY
}

install_argotunnel_hosts_fix() {
  local tmp_hosts_block
  tmp_hosts_block="$(mktemp)"
  write_argotunnel_hosts_block >"${tmp_hosts_block}"

  echo "Fixing Cloudflare Tunnel DNS for this Linux machine..."
  echo "This needs sudo once because it writes /etc/hosts."

  if sudo sh -c "sed -i '/# BEGIN national_security cloudflared real DNS/,/# END national_security cloudflared real DNS/d' /etc/hosts && cat '${tmp_hosts_block}' >> /etc/hosts"; then
    rm -f "${tmp_hosts_block}"
    echo "Cloudflare Tunnel DNS fix installed."
    return 0
  fi

  rm -f "${tmp_hosts_block}"
  echo "Could not update /etc/hosts automatically."
  return 1
}

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

# In prod mode we need a built frontend at frontend/dist
if [[ "${PROD_MODE}" == "1" ]]; then
  echo "Building frontend for production..."
  (cd "${ROOT_DIR}/frontend" && npm run build >/dev/null)
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

if [[ "${PROD_MODE}" != "1" ]]; then
  # Start frontend in background, logs to .frontend.log
  echo "Starting frontend on ${FRONTEND_HOST}:${FRONTEND_PORT}"
  : >"${ROOT_DIR}/.frontend.log"
  (cd "${ROOT_DIR}/frontend" && npm run dev -- --host "${FRONTEND_HOST}" --port "${FRONTEND_PORT}" --strictPort) \
    >>"${ROOT_DIR}/.frontend.log" 2>&1 &
  frontend_pid="$!"
else
  : >"${ROOT_DIR}/.frontend.log"
fi

# Print access URLs with ONLY URLs in green
echo
echo "Local access (Linux):"
if [[ "${PROD_MODE}" == "1" ]]; then
  echo -e "  ${GREEN}http://127.0.0.1:${BACKEND_PORT}${NC}"
else
  echo -e "  ${GREEN}http://127.0.0.1:${FRONTEND_PORT}${NC}"
fi
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
  if [[ "${PROD_MODE}" == "1" ]]; then
    echo -e "  ${GREEN}http://${linux_ip}:${BACKEND_PORT}${NC}"
  else
    echo -e "  ${GREEN}http://${linux_ip}:${FRONTEND_PORT}${NC}"
  fi
  echo
fi

if [[ "${TUNNEL_MODE}" == "1" ]]; then
  if ! command -v cloudflared >/dev/null 2>&1; then
    echo "cloudflared not found. Install it first, or run without --tunnel."
    exit 1
  fi

  tunnel_log="${ROOT_DIR}/.tunnel.log"
  : > "${tunnel_log}"
  fake_ip_hint="$(detect_argotunnel_fake_ip)"
  if [[ -n "${fake_ip_hint}" ]] && is_fake_ip "${fake_ip_hint}"; then
    echo "Cloudflare Quick Tunnel needs real DNS, but this Linux currently gets fake-ip (${fake_ip_hint})."
    echo "I will try to fix it automatically so ./dev.sh --tunnel can produce a working trycloudflare.com URL."
    echo
    if install_argotunnel_hosts_fix; then
      fake_ip_hint="$(detect_argotunnel_fake_ip)"
    fi
    echo
    if [[ -n "${fake_ip_hint}" ]] && is_fake_ip "${fake_ip_hint}"; then
      echo "Cloudflare DNS is still fake-ip. Quick Tunnel will likely fail until Clash DNS is changed to real-ip/redir-host."
      if [[ -n "${linux_ip}" ]]; then
        echo
        echo "Temporary LAN URL from your Mac Chrome:"
        if [[ "${PROD_MODE}" == "1" ]]; then
          echo -e "  ${GREEN}http://${linux_ip}:${BACKEND_PORT}${NC}"
        else
          echo -e "  ${GREEN}http://${linux_ip}:${FRONTEND_PORT}${NC}"
        fi
      fi
      echo
    fi
  fi

  # Run cloudflared without HTTP proxies — they break the QUIC/TLS handshake to Cloudflare edge.
  # SOCKS proxies are fine, but http(s)_proxy interferes with the tunnel control plane.
  # Try http2 first because QUIC can have UDP blocking issues.
  cf_cmd="cloudflared tunnel --no-autoupdate --protocol http2"
  if [[ "${PROD_MODE}" == "1" ]]; then
    cf_cmd="${cf_cmd} --url http://127.0.0.1:${BACKEND_PORT}"
  else
    cf_cmd="${cf_cmd} --url http://127.0.0.1:${FRONTEND_PORT}"
  fi
  env -u http_proxy -u https_proxy -u HTTP_PROXY -u HTTPS_PROXY \
      -u all_proxy -u ALL_PROXY \
      ${cf_cmd} >"${tunnel_log}" 2>&1 &
  tunnel_pid="$!"

  public_url=""
  tunnel_ready="0"
  for i in {1..180}; do
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
    tunnel_ready="$(
      python - <<'PY' "${tunnel_log}"
import re, sys
path = sys.argv[1]
try:
    data = open(path, "r", encoding="utf-8", errors="ignore").read()
except FileNotFoundError:
    print("0")
    raise SystemExit(0)
ok = (
    "Registered tunnel connection" in data
    or "Connection registered" in data
    or bool(re.search(r"connIndex=\d+.*registered", data, re.IGNORECASE))
)
print("1" if ok else "0")
PY
    )"
    if [[ -n "${public_url}" ]] && [[ "${tunnel_ready}" == "1" ]]; then
      break
    fi
    sleep 0.5
  done

  if [[ -n "${public_url}" ]] && [[ "${tunnel_ready}" == "1" ]]; then
    echo "Public tunnel URL:"
    echo -e "  ${GREEN}${public_url}${NC}"
    echo
  else
    echo "Cloudflare Tunnel did not become healthy within timeout."
    echo "Check ${tunnel_log} for details."
    if [[ -n "${fake_ip_hint}" ]] && is_fake_ip "${fake_ip_hint}"; then
      echo "Likely cause: DNS fake-ip (198.18.x.x) from Clash. See preflight warning above."
    fi
    echo
  fi
fi

if [[ -n "${NAMED_TUNNEL_NAME}" ]]; then
  if ! command -v cloudflared >/dev/null 2>&1; then
    echo "cloudflared not found. Install it first."
    exit 1
  fi
  if [[ "${PROD_MODE}" != "1" ]]; then
    echo "Named tunnel requires --prod (single-port backend serving frontend)."
    exit 1
  fi
  echo "Starting named tunnel: ${NAMED_TUNNEL_NAME}"
  env -u http_proxy -u https_proxy -u HTTP_PROXY -u HTTPS_PROXY \
      -u all_proxy -u ALL_PROXY \
      cloudflared tunnel run "${NAMED_TUNNEL_NAME}" >>"${ROOT_DIR}/.tunnel.log" 2>&1 &
  tunnel_pid="$!"
fi

echo "📝 Disclaimer: 推理观点由LLM基于公开思想蒸馏生成，仅为学术讨论，非本人观点。"
echo

echo "⚡ Running. Press Ctrl+C to stop all services."
echo "----------------------------------------"
echo

# Filter logs to greenify URLs before tailing
tail -f "${ROOT_DIR}/.backend.log" "${ROOT_DIR}/.frontend.log" "${ROOT_DIR}/.tunnel.log" | while IFS= read -r line; do
  if [[ "$line" =~ http:// ]]; then
    # Greenify the whole line if it contains URL (vite outputs the URLs on its own line)
    echo -e "${GREEN}${line}${NC}"
  else
    echo "$line"
  fi
done
