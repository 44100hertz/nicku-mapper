#!/bin/sh
# Serve the repo root so the web viewer can fetch levels/*/Entities.ini.
# Then open http://localhost:8000/web/ (add #LevelName to deep-link).
cd "$(dirname "$0")"
echo "Nickmapper 3D viewer: http://localhost:8000/web/"
echo "e.g. http://localhost:8000/web/#SpongeBobLevel2"
exec python3 -m http.server 8000
