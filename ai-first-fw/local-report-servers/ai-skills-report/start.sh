#!/usr/bin/env bash
# ==============================================================================
# AI Skills & Plugins Registry - Launcher Script
# Starts the local HTTP dashboard server and opens in the default web browser.
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PORT="${1:-24003}"
URL="http://localhost:${PORT}"

# Colors
BOLD='\033[1m'
GREEN='\033[0;32m'
SKY='\033[0;36m'
YELLOW='\033[0;33m'
NC='\033[0m'

echo -e "${BOLD}${SKY}========================================================================${NC}"
echo -e "${BOLD}${SKY}  🧩 Starting AI Skills & Plugins Registry Server on port ${PORT}...     ${NC}"
echo -e "${BOLD}${SKY}========================================================================${NC}"
echo ""
echo -e "  Dashboard URL: 👉 ${BOLD}${GREEN}${URL}${NC}"
echo -e "  To stop:       Press ${YELLOW}Ctrl + C${NC}"
echo ""

# Open browser in background after 1 second
(
  sleep 1
  if command -v open &>/dev/null; then
      open "$URL"
  elif command -v xdg-open &>/dev/null; then
      xdg-open "$URL"
  fi
) &

# Run server
python3 server.py --port "$PORT"
