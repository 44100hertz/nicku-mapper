#!/usr/bin/env bash
# Smoke test for the 3D viewer: serves the repo root and loads the app in
# headless chromium, then checks that a level rendered without JS errors.
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PORT=8123
CHROME="${CHROME:-$HOME/.cache/puppeteer/chrome/linux-*/chrome-linux64/chrome}"
CHROME="$(echo $CHROME)"  # expand glob

cd "$ROOT"
python3 -m http.server "$PORT" >/dev/null 2>&1 &
SERVER_PID=$!
trap 'kill $SERVER_PID 2>/dev/null' EXIT
sleep 0.5

"$CHROME" \
  --headless=new --password-store=basic --no-sandbox --disable-gpu \
  --enable-unsafe-swiftshader --use-angle=swiftshader \
  --virtual-time-budget=20000 --dump-dom \
  "http://localhost:$PORT/web/" > /tmp/nickmapper-dom.html 2>/tmp/nickmapper-chrome.log

echo "--- page title (first line) ---"
grep -o '<title>[^<]*</title>' /tmp/nickmapper-dom.html | head -1
echo "--- status line ---"
grep -o 'id="status">[^<]*' /tmp/nickmapper-dom.html | head -1
echo "--- legend rows ---"
grep -c 'class="legend-row"' /tmp/nickmapper-dom.html || true
echo "--- chrome errors (if any) ---"
grep -iE "error|failed|exception" /tmp/nickmapper-chrome.log | grep -v "dbus\|gpu\|GPU\|dawn\|swiftshader\|vulkan\|sandbox" | head -5 || echo "(none)"
