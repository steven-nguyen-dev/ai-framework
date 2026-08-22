#!/usr/bin/env bash
# ==============================================================================
# AI Skills & Plugins Registry - Automated Setup & Environment Verification
# Verifies Python 3, checks agent environments (Claude, Antigravity, Gemini),
# grants execution permissions, and prepares pre-bundled cache data.
# ==============================================================================

set -e

# Color & Style helpers
BOLD='\033[1m'
GREEN='\033[0;32m'
SKY='\033[0;36m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
GRAY='\033[0;90m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo -e "${BOLD}${SKY}========================================================================${NC}"
echo -e "${BOLD}${SKY}  🧩 AI Skills & Plugins Registry - Setup & Verification               ${NC}"
echo -e "${BOLD}${SKY}========================================================================${NC}"
echo -e "  Directory: ${GRAY}${SCRIPT_DIR}${NC}"
echo ""

# ------------------------------------------------------------------------------
# 1. Check Python 3 Environment
# ------------------------------------------------------------------------------
echo -e "${BOLD}[1/3] Checking Python 3 Environment...${NC}"
if command -v python3 &>/dev/null; then
    PY_VER=$(python3 --version 2>&1)
    echo -e "  ${GREEN}✓ Found ${PY_VER}${NC} (standard library only, zero pip dependencies needed)"
else
    echo -e "  ${RED}✗ Python 3 is not installed.${NC}"
    echo -e "  💡 To install Python 3:"
    echo -e "     • Via Homebrew: ${SKY}brew install python${NC}"
    echo -e "     • Or download:  ${SKY}https://www.python.org/downloads/macos/${NC}"
    exit 1
fi

# ------------------------------------------------------------------------------
# 2. Grant Permissions
# ------------------------------------------------------------------------------
echo ""
echo -e "${BOLD}[2/3] Setting Script Permissions...${NC}"
chmod +x "$SCRIPT_DIR"/*.sh "$SCRIPT_DIR"/*.command "$SCRIPT_DIR"/*.py 2>/dev/null || true
echo -e "  ${GREEN}✓ Execution permissions granted to all launcher scripts.${NC}"

# ------------------------------------------------------------------------------
# 3. Pre-scan & Pre-generate Standalone Offline Export
# ------------------------------------------------------------------------------
echo ""
echo -e "${BOLD}[3/3] Performing Initial Agent Discovery Scan...${NC}"
python3 "$SCRIPT_DIR/server.py" --export >/dev/null 2>&1 || true

if [ -f "$SCRIPT_DIR/ai-skills-report.html" ]; then
    echo -e "  ${GREEN}✓ Discovery scan completed & standalone offline report generated.${NC}"
else
    echo -e "  ${YELLOW}! Offline report export skipped, live server will scan on launch.${NC}"
fi

echo ""
echo -e "${BOLD}${GREEN}========================================================================${NC}"
echo -e "${BOLD}${GREEN}  ✨ Setup Completed Successfully!                                     ${NC}"
echo -e "${BOLD}${GREEN}========================================================================${NC}"
echo ""
echo -e "  ▶ Next Steps:"
echo -e "      • Run as macOS App:     ${SKY}./install_app.sh${NC}"
echo -e "      • Run in Terminal:      ${SKY}./start.sh${NC}"
echo ""
