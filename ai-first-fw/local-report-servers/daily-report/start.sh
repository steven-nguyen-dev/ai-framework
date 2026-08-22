#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
PORT="${1:-24001}"

echo "Starting Daily Work Report server on port $PORT..."
(sleep 1 && open "http://127.0.0.1:$PORT") &
exec python3 server.py --port "$PORT"
