#!/usr/bin/env bash
# Debug cloudflared connection to local vite

# Kill everything
pkill -9 -f cloudflared 2>/dev/null || true
pkill -9 -f "vite" 2>/dev/null || true
sleep 1

# Start vite in background
cd frontend
npm run dev -- --host 0.0.0.0 --port 5173 --strictPort > ../.vite.log 2>&1 &
VITE_PID=$!
cd ..

# Wait for vite
sleep 3

# Test that 127.0.0.1:5173 is reachable WITHOUT proxy
echo "=== Test 1: Local curl to 127.0.0.1:5173 (no proxy) ==="
env -u http_proxy -u https_proxy -u HTTP_PROXY -u HTTPS_PROXY \
    -u all_proxy -u ALL_PROXY \
    curl -v -m 5 http://127.0.0.1:5173/ -o /dev/null -w "Exit code: %{exit_code}, HTTP: %{http_code}\n"

echo ""
echo "=== Starting cloudflared ==="
# Start cloudflared WITHOUT proxy env
env -u http_proxy -u https_proxy -u HTTP_PROXY -u HTTPS_PROXY \
    -u all_proxy -u ALL_PROXY \
    cloudflared tunnel --no-autoupdate --protocol quic --url http://127.0.0.1:5173 > .cloudflared_debug.log 2>&1 &
CF_PID=$!

# Wait for URL
echo "Waiting for cloudflared URL..."
for i in $(seq 1 60); do
    URL=$(grep -oE 'https://[a-zA-Z0-9.-]*trycloudflare\.com' .cloudflared_debug.log 2>/dev/null | tail -1 || true)
    if [[ -n "$URL" ]]; then
        break
    fi
    sleep 1
done

if [[ -z "$URL" ]]; then
    echo "No URL from cloudflared! Log tail:"
    tail -30 .cloudflared_debug.log
    kill $VITE_PID $CF_PID 2>/dev/null
    exit 1
fi

echo "Got URL: $URL"
echo ""
echo "Waiting 10s for tunnel to establish..."
sleep 10

echo "=== Testing public URL $URL (no proxy) ==="
env -u http_proxy -u https_proxy -u HTTP_PROXY -u HTTPS_PROXY \
    -u all_proxy -u ALL_PROXY \
    curl -v -m 20 "$URL/" -o test_output.html 2>&1 | head -50

echo ""
echo "=== HTTP Status code ==="
env -u http_proxy -u https_proxy -u HTTP_PROXY -u HTTPS_PROXY \
    -u all_proxy -u ALL_PROXY \
    curl -s -o /dev/null -w "%{http_code}\n" "$URL/"

echo ""
echo "=== Full cloudflared log tail (last 40 lines) ==="
tail -40 .cloudflared_debug.log

kill $VITE_PID $CF_PID 2>/dev/null
pkill -9 -f cloudflared 2>/dev/null || true
pkill -9 -f "vite" 2>/dev/null || true
