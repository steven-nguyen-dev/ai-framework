#!/usr/bin/env bash
# ==============================================================================
# SonarQube Issues Explorer - Setup & Environment Verifier
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

BOLD='\033[1m'
GREEN='\033[0;32m'
SKY='\033[0;36m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BOLD}${SKY}========================================================================${NC}"
echo -e "${BOLD}${SKY}  🚀 SonarQube Issues Explorer - Setup & Verification                    ${NC}"
echo -e "${BOLD}${SKY}========================================================================${NC}"
echo ""

# 1. Python 3
echo -e "${BOLD}[1/4] Checking Python 3...${NC}"
if command -v python3 &>/dev/null; then
    PY_VER=$(python3 --version 2>&1)
    echo -e "  ${GREEN}✓ Found ${PY_VER}${NC} (standard library only, zero pip dependencies)"
else
    echo -e "  ${RED}✗ Python 3 is not installed.${NC} Please install via: brew install python"
    exit 1
fi

# 2. Permissions
echo ""
echo -e "${BOLD}[2/4] Setting script permissions...${NC}"
chmod +x "$SCRIPT_DIR"/*.sh "$SCRIPT_DIR"/*.command "$SCRIPT_DIR"/*.py 2>/dev/null || true
echo -e "  ${GREEN}✓ Executable permissions granted.${NC}"

# 3. SonarQube Credentials Check
echo ""
echo -e "${BOLD}[3/4] Checking SonarQube API Credentials...${NC}"
TOKEN_FOUND=false
if [ -n "$SONAR_TOKEN" ]; then
    TOKEN_FOUND=true
    echo -e "  ${GREEN}✓ Found SONAR_TOKEN in environment.${NC}"
elif [ -f "$HOME/.jpluger-sonar.env" ]; then
    TOKEN_FOUND=true
    echo -e "  ${GREEN}✓ Found credentials at ~/.jpluger-sonar.env${NC}"
elif [ -f "/Users/nguyennguyen.anchanto/.jpluger-sonar.env" ]; then
    TOKEN_FOUND=true
    echo -e "  ${GREEN}✓ Found credentials at /Users/nguyennguyen.anchanto/.jpluger-sonar.env${NC}"
elif [ -f "$SCRIPT_DIR/.env" ]; then
    TOKEN_FOUND=true
    echo -e "  ${GREEN}✓ Found credentials at .env${NC}"
else
    if [ -f "$SCRIPT_DIR/.env.sample" ]; then
        cp "$SCRIPT_DIR/.env.sample" "$SCRIPT_DIR/.env"
        echo -e "  ${YELLOW}! Created .env from template.${NC}"
        echo -e "    Please add your SONAR_TOKEN to $SCRIPT_DIR/.env or ~/.jpluger-sonar.env"
    fi
fi

# 4. Java & H2 (Source B) Check
echo ""
echo -e "${BOLD}[4/4] Checking Local IDE Findings Runtime (Source B)...${NC}"
JAVA_BIN="/Applications/IntelliJ IDEA.app/Contents/jbr/Contents/Home/bin/java"
if [ -x "$JAVA_BIN" ]; then
    echo -e "  ${GREEN}✓ Found IntelliJ IDEA JBR:${NC} ${JAVA_BIN}"
elif command -v java &>/dev/null; then
    echo -e "  ${GREEN}✓ Found system java:${NC} $(java -version 2>&1 | head -n 1)"
else
    echo -e "  ${YELLOW}! Java runtime not found. Local IDE findings will be skipped (Server findings still work).${NC}"
fi

# Warm-up pre-scan / data export
echo ""
echo -e "${BOLD}Generating offline static report cache...${NC}"
python3 "$SCRIPT_DIR/server.py" --export >/dev/null 2>&1 || true
echo -e "  ${GREEN}✓ Offline cache ready.${NC}"

echo ""
echo -e "${BOLD}${GREEN}========================================================================${NC}"
echo -e "${BOLD}${GREEN}  🎉 Setup Complete! Run ./start.sh to launch the dashboard.             ${NC}"
echo -e "${BOLD}${GREEN}========================================================================${NC}"
echo ""
