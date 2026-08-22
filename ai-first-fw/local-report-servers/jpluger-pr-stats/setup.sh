#!/usr/bin/env bash
# ==============================================================================
# JPluger PR Stats Dashboard - Automated Setup & Configuration Guide
# Installs GitHub CLI (gh), verifies Python 3, checks auth & repo permissions,
# and provides clear configuration instructions.
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

TARGET_REPO="${1:-Anchanto/JPluger}"

echo -e "${BOLD}${SKY}========================================================================${NC}"
echo -e "${BOLD}${SKY}  🚀 JPluger PR Stats Dashboard - Setup & Configuration                 ${NC}"
echo -e "${BOLD}${SKY}========================================================================${NC}"
echo -e "  Target Repository: ${BOLD}${YELLOW}${TARGET_REPO}${NC}"
echo -e "  Directory:         ${GRAY}${SCRIPT_DIR}${NC}"
echo ""

# ------------------------------------------------------------------------------
# 1. Check Python 3 Environment
# ------------------------------------------------------------------------------
echo -e "${BOLD}[1/4] Checking Python 3 Environment...${NC}"
if command -v python3 &>/dev/null; then
    PY_VER=$(python3 --version 2>&1)
    echo -e "  ${GREEN}✓ Found ${PY_VER}${NC} (standard library only, zero pip packages needed)"
else
    echo -e "  ${RED}✗ Python 3 is not installed.${NC}"
    echo -e "  💡 To install Python 3:"
    echo -e "     • Via Homebrew: ${SKY}brew install python${NC}"
    echo -e "     • Or download:  ${SKY}https://www.python.org/downloads/macos/${NC}"
    exit 1
fi

# ------------------------------------------------------------------------------
# 2. Check / Install GitHub CLI (`gh`)
# ------------------------------------------------------------------------------
echo ""
echo -e "${BOLD}[2/4] Checking GitHub CLI (gh)...${NC}"
if command -v gh &>/dev/null; then
    GH_VER=$(gh --version | head -n 1)
    echo -e "  ${GREEN}✓ Found ${GH_VER}${NC}"
else
    echo -e "  ${YELLOW}! GitHub CLI (gh) is not installed.${NC}"
    echo -e "  ${SKY}Auto-installing official GitHub CLI...${NC}"
    
    if command -v brew &>/dev/null; then
        echo -e "  Running: ${SKY}brew install gh${NC}"
        brew install gh
    else
        echo "  Homebrew not found. Downloading official macOS binary from GitHub Releases..."
        ARCH=$(uname -m)
        if [ "$ARCH" = "arm64" ]; then
            GH_ARCH="macOS_arm64"
        else
            GH_ARCH="macOS_amd64"
        fi
        
        GH_LATEST_TAG=$(curl -s https://api.github.com/repos/cli/cli/releases/latest | grep '"tag_name":' | sed -E 's/.*"([^"]+)".*/\1/')
        if [ -z "$GH_LATEST_TAG" ]; then
            GH_LATEST_TAG="v2.55.0"
        fi
        GH_VER_NUM="${GH_LATEST_TAG#v}"
        TAR_NAME="gh_${GH_VER_NUM}_${GH_ARCH}.tar.gz"
        DOWNLOAD_URL="https://github.com/cli/cli/releases/download/${GH_LATEST_TAG}/${TAR_NAME}"
        
        echo "  Downloading ${DOWNLOAD_URL}..."
        curl -sL "$DOWNLOAD_URL" -o "/tmp/${TAR_NAME}"
        
        mkdir -p "/tmp/gh_install"
        tar -xzf "/tmp/${TAR_NAME}" -C "/tmp/gh_install" --strip-components=1
        
        mkdir -p "$SCRIPT_DIR/bin"
        cp "/tmp/gh_install/bin/gh" "$SCRIPT_DIR/bin/gh"
        chmod +x "$SCRIPT_DIR/bin/gh"
        export PATH="$SCRIPT_DIR/bin:$PATH"
        
        rm -rf "/tmp/${TAR_NAME}" "/tmp/gh_install"
        echo -e "  ${GREEN}✓ Installed gh to $SCRIPT_DIR/bin/gh${NC}"
    fi
fi

# ------------------------------------------------------------------------------
# 3. Check GitHub CLI Authentication & Repo Access
# ------------------------------------------------------------------------------
echo ""
echo -e "${BOLD}[3/4] Verifying GitHub Authentication & Permissions...${NC}"
if ! gh auth status &>/dev/null; then
    echo -e "  ${YELLOW}! GitHub CLI is not logged in.${NC}"
    echo -e "  ${BOLD}Starting interactive GitHub authentication...${NC}"
    echo -e "  ${GRAY}Tip: Select 'GitHub.com' -> 'HTTPS' -> 'Login with a web browser'${NC}"
    echo ""
    gh auth login -w -p https
fi

# Print logged-in user
AUTH_USER=$(gh api user -q .login 2>/dev/null || echo "authenticated")
echo -e "  ${GREEN}✓ Logged in as GitHub user:${NC} ${BOLD}${SKY}@${AUTH_USER}${NC}"

# Test read permission on the target repository
echo -n "  Checking read access to '${TARGET_REPO}'... "
if gh repo view "${TARGET_REPO}" &>/dev/null; then
    echo -e "${GREEN}✓ Access confirmed.${NC}"
else
    echo -e "${YELLOW}⚠️ Limited or No Access${NC}"
    echo -e "  ${YELLOW}Note:${NC} If '${TARGET_REPO}' is protected by Organization SAML SSO:"
    echo -e "  Run this in your terminal to authorize:"
    echo -e "    ${SKY}gh auth refresh -h github.com -s repo,read:org${NC}"
fi

# ------------------------------------------------------------------------------
# 4. Fetch Fresh Data & Initialize Cache
# ------------------------------------------------------------------------------
echo ""
echo -e "${BOLD}[4/4] Initializing Dashboard Dataset...${NC}"
chmod +x setup.sh start.sh fetcher.py server.py 2>/dev/null || true

echo "  Fetching open PRs and 12-month metrics from ${TARGET_REPO}..."
if python3 fetcher.py --static; then
    echo -e "  ${GREEN}✓ Live dataset fetched and static offline report generated.${NC}"
else
    echo -e "  ${YELLOW}! Live fetch encountered an issue. Using pre-bundled cached dataset in data.json.${NC}"
fi

# ------------------------------------------------------------------------------
# Configuration Summary & User Instructions
# ------------------------------------------------------------------------------
echo ""
echo -e "${BOLD}${GREEN}========================================================================${NC}"
echo -e "${BOLD}${GREEN}  🎉 Setup Complete! JPluger PR Stats Dashboard is Ready!                ${NC}"
echo -e "${BOLD}${GREEN}========================================================================${NC}"
echo ""
echo -e "  ${BOLD}▶ How to Start the Server:${NC}"
echo -e "      ${BOLD}${SKY}./start.sh${NC}"
echo -e "      ${GRAY}(or: python3 server.py --port 24002)${NC}"
echo ""
echo -e "  ${BOLD}🌐 Dashboard URL:${NC}"
echo -e "      👉 ${BOLD}${GREEN}http://localhost:24002${NC}"
echo ""
echo -e "  ${BOLD}⚙️ Configuration & Customization:${NC}"
echo -e "      • ${BOLD}Change Port:${NC}        ${SKY}./start.sh 24005${NC}  ${GRAY}(or: python3 server.py --port 24005)${NC}"
echo -e "      • ${BOLD}Change Target Repo:${NC} Edit ${SKY}fetcher.py${NC}"
echo -e "      • ${BOLD}Offline Report:${NC}     Open ${SKY}report.html${NC}"
echo -e "      • ${BOLD}Manual Sync:${NC}        Click '${BOLD}Sync GitHub${NC}' in top right of dashboard"
echo -e "      • ${BOLD}Auto-Sync Timer:${NC}    Select interval (30m, 60m, 4h) in top right dropdown"
echo ""
echo -e "  ${BOLD}⏹️ How to Stop the Server:${NC}"
echo -e "      Press ${YELLOW}Ctrl + C${NC} in the terminal."
echo -e "${BOLD}${GREEN}========================================================================${NC}"
echo ""
