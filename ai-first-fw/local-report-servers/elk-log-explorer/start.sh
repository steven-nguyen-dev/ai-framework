#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PORT="${1:-24004}"
URL="http://localhost:${PORT}"

# Open browser
(
  sleep 1
  command -v open &>/dev/null && open "$URL" || command -v xdg-open &>/dev/null && xdg-open "$URL"
) &

python3 server.py --port "$PORT"
