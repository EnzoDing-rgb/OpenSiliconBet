#!/usr/bin/env bash
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TUNNEL_LOG="${ROOT_DIR}/.tunnel.log"
FRONTEND_LOG="${ROOT_DIR}/.frontend.log"
BACKEND_LOG="${ROOT_DIR}/.backend.log"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "🧹 Killing any existing dev.sh/cloudflared..."
pkill -9 -f "dev.sh" 2>/dev/null || true
pkill -9 -f cloudflared 2>/dev/null || true
sleep 1
lsof -t -i:5173 -i:9000 | xargs -r kill -9 2>/dev/null || true
sleep 1

echo "🚀 Starting ./dev.sh --tunnel in background..."
./dev.sh --tunnel > /dev/null 2>&1 &
DEV_PID=$!

# Wait for tunnel URL
echo "⏳ Waiting for cloudflared URL (max 90s)..."
PUBLIC_URL=""
TUNNEL_READY="0"
for i in $(seq 1 180); do
    PUBLIC_URL=$(grep -oE 'https://[a-zA-Z0-9.-]*trycloudflare\.com' "$TUNNEL_LOG" 2>/dev/null | tail -1 || true)
    if [[ -n "$PUBLIC_URL" ]]; then
        TUNNEL_READY="1"
        break
    fi
    sleep 0.5
done

if [[ -z "$PUBLIC_URL" ]]; then
    echo -e "${RED}❌ Timeout: cloudflared did not produce a URL${NC}"
    echo "Last 20 lines of tunnel log:"
    tail -20 "$TUNNEL_LOG"
    kill $DEV_PID 2>/dev/null || true
    exit 1
fi

echo -e "${GREEN}✅ Tunnel URL: $PUBLIC_URL${NC}"
echo ""

# Test 1: Local 127.0.0.1
echo "--- Test 1: http://127.0.0.1:5173 ---"
curl -s -o /dev/null -w "HTTP_CODE: %{http_code}  SIZE: %{size_download}  TIME: %{time_total}s\n" \
     --connect-timeout 10 --max-time 15 \
     http://127.0.0.1:5173/ 2>/dev/null

# Test 2: Cloudflare Public URL (with retries)
echo ""
echo "--- Test 2: $PUBLIC_URL ---"
CF_OK=0
for i in $(seq 1 12); do
    RESULT=$(curl -s -o /dev/null -w "%{http_code}" \
             --connect-timeout 10 --max-time 15 \
             "$PUBLIC_URL/" 2>/dev/null || echo "000")
    echo "Attempt $i: HTTP $RESULT"
    if [[ "$RESULT" == "200" ]] || [[ "$RESULT" == "301" ]] || [[ "$RESULT" == "302" ]]; then
        CF_OK=1
        break
    fi
    sleep 5
done

echo ""
if [[ "$CF_OK" == "1" ]]; then
    echo -e "${GREEN}✅ Public URL is reachable!${NC}"
    echo ""
    echo "Fetching page content (first 500 bytes):"
    curl -s --max-time 10 "$PUBLIC_URL/" 2>/dev/null | head -c 500
    echo ""
else
    echo -e "${RED}❌ Public URL returned non-200 responses${NC}"
fi

# Diagnose
echo ""
echo "--- Diagnostics ---"
echo "Frontend log last 5 lines:"
tail -5 "$FRONTEND_LOG"
echo ""
echo "Backend log last 5 lines:"
tail -5 "$BACKEND_LOG"
echo ""
echo "Tunnel log last 10 lines:"
tail -10 "$TUNNEL_LOG"

echo ""
echo "Stopping dev.sh..."
kill $DEV_PID 2>/dev/null || true
wait $DEV_PID 2>/dev/null || true
pkill -9 -f cloudflared 2>/dev/null || true
echo "Done."
