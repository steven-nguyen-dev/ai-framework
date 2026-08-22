#!/usr/bin/env bash
# Launches the Daily Report Live Server on port 24001.
# Serves interactive dashboard and reads daily-reports and matters from project workspace.

set -euo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

PORT="${1:-24001}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Launching Daily Report Server on port ${PORT}..."
exec python3 "${HERE}/server.py" --port "${PORT}"
