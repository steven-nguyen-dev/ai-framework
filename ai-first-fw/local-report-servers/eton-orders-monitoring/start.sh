#!/usr/bin/env bash
# ==============================================================================
# Eton Orders Monitoring - Terminal Launcher
# ==============================================================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PORT="${1:-24005}"
URL="http://localhost:${PORT}"

# Open browser in background after server binds
(
  sleep 1
  command -v open &>/dev/null && open "$URL" || command -v xdg-open &>/dev/null && xdg-open "$URL"
) &

echo "🚀 Launching Eton Orders Monitoring on ${URL}..."
python3 server.py --port "$PORT"
