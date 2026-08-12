#!/usr/bin/env bash
# Serve the viewer locally (with generated data if present).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PORT="${1:-8080}"
echo "Nickmapper viewer: http://localhost:$PORT/  (add #LevelName to deep-link)"
echo "If the viewer 404s, run: nix run .#extract -- --iso /path/nicktoonsunite.iso --out viewer"
exec python3 -m http.server "$PORT" --directory "$ROOT/viewer"
