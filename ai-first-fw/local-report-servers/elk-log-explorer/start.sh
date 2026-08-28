#!/usr/bin/env bash
export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PORT="${1:-24004}"
URL="http://localhost:${PORT}"

# If already running on port, open browser immediately and exit
if curl -s -m 1 "http://127.0.0.1:${PORT}/api/status" >/dev/null 2>&1; then
    echo "✔ ELK AI Log Explorer is already running on ${URL}."
    command -v open &>/dev/null && open "$URL" || command -v xdg-open &>/dev/null && xdg-open "$URL"
    exit 0
fi

# Open browser in background
(
  sleep 1
  command -v open &>/dev/null && open "$URL" || command -v xdg-open &>/dev/null && xdg-open "$URL"
) &

python3 server.py --port "$PORT"
