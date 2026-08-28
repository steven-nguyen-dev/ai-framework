#!/usr/bin/env bash
# ==============================================================================
# Jira Reader MCP - Claude Code Global Installer & Setup
# ==============================================================================
# This script:
#   1. Prompts for and sets up Jira credentials in .env (if missing/reconfiguring)
#   2. Tests Jira connectivity and authentication
#   3. Configures Claude Code globally (~/.claude.json) to enable jira-reader MCP
# ==============================================================================

set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_PY="$DIR/server.py"
ENV_FILE="$DIR/.env"
CLAUDE_JSON="$HOME/.claude.json"

BOLD="\033[1m"
GREEN="\033[32m"
YELLOW="\033[33m"
CYAN="\033[36m"
RED="\033[31m"
RESET="\033[0m"

echo -e "${BOLD}${CYAN}==============================================================================${RESET}"
echo -e "${BOLD}${CYAN}  Jira Reader MCP — Claude Code Global Installer & Setup${RESET}"
echo -e "${BOLD}${CYAN}==============================================================================${RESET}"
echo

configure_env() {
    echo -e "${BOLD}${YELLOW}[1/3] Configuring Jira Credentials...${RESET}"
    
    local host=""
    local auth_choice="1"
    local email=""
    local token=""
    local pat=""
    local download_dir=".scratchpads/downloads"
    local api_version="3"

    while [ -z "$host" ]; do
        echo -ne "${BOLD}Enter Jira Host URL${RESET} (e.g. https://your-domain.atlassian.net or https://jira.company.com): "
        read -r host
        host=$(echo "$host" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' -e 's|/*$||')
        if [ -z "$host" ]; then
            echo -e "${RED}Error: Jira Host cannot be empty.${RESET}"
        fi
    done

    echo
    echo -e "${BOLD}Select Authentication Method:${RESET}"
    echo "  1) Jira Cloud (Email + API Token) [Default]"
    echo "  2) Jira Server / Data Center (Personal Access Token - PAT)"
    echo -ne "${BOLD}Choice [1/2] (default 1): ${RESET}"
    read -r auth_choice_input
    if [ "$auth_choice_input" = "2" ]; then
        auth_choice="2"
    else
        auth_choice="1"
    fi

    if [ "$auth_choice" = "1" ]; then
        while [ -z "$email" ]; do
            echo -ne "${BOLD}Enter Atlassian Login Email:${RESET} "
            read -r email
            email=$(echo "$email" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')
            if [ -z "$email" ]; then
                echo -e "${RED}Error: Email cannot be empty for Jira Cloud.${RESET}"
            fi
        done

        while [ -z "$token" ]; do
            echo -ne "${BOLD}Enter Jira API Token (hidden):${RESET} "
            read -rs token
            echo
            token=$(echo "$token" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')
            if [ -z "$token" ]; then
                echo -e "${RED}Error: API Token cannot be empty. Generate at: https://id.atlassian.com/manage-profile/security/api-tokens${RESET}"
            fi
        done
        api_version="3"
    else
        while [ -z "$pat" ]; do
            echo -ne "${BOLD}Enter Jira Personal Access Token (PAT) (hidden):${RESET} "
            read -rs pat
            echo
            pat=$(echo "$pat" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')
            if [ -z "$pat" ]; then
                echo -e "${RED}Error: PAT cannot be empty for Jira Server/DC.${RESET}"
            fi
        done
        api_version="2"
    fi

    echo
    echo -ne "${BOLD}Download directory for attachments [default: .scratchpads/downloads]: ${RESET}"
    read -r dl_input
    if [ -n "$dl_input" ]; then
        download_dir="$dl_input"
    fi

    echo "# Jira Reader MCP Configuration (.env)" > "$ENV_FILE"
    echo "JIRA_HOST=$host" >> "$ENV_FILE"
    echo "JIRA_DOWNLOAD_DIR=$download_dir" >> "$ENV_FILE"
    echo "JIRA_API_VERSION=$api_version" >> "$ENV_FILE"

    if [ "$auth_choice" = "1" ]; then
        echo "JIRA_EMAIL=$email" >> "$ENV_FILE"
        echo "JIRA_API_TOKEN=$token" >> "$ENV_FILE"
    else
        echo "JIRA_PAT=$pat" >> "$ENV_FILE"
    fi

    chmod 600 "$ENV_FILE"
    echo -e "${GREEN}✔ Successfully saved credentials to $ENV_FILE (chmod 600)${RESET}"
    echo
}

if [ -f "$ENV_FILE" ]; then
    echo -e "${GREEN}Existing credentials found at:${RESET} $ENV_FILE"
    echo -ne "${BOLD}Do you want to reconfigure them? [y/N]: ${RESET}"
    read -r reconfig
    if [[ "$reconfig" =~ ^[Yy]$ ]]; then
        configure_env
    else
        echo -e "${CYAN}Keeping existing .env credentials.${RESET}"
        echo
    fi
else
    configure_env
fi

echo -e "${BOLD}${YELLOW}[2/3] Verifying Jira Connection...${RESET}"
if python3 "$SERVER_PY" --test; then
    echo -e "${GREEN}✔ Connection and authentication test passed!${RESET}"
    echo
else
    echo -e "${RED}⚠ Connection test failed. Please check your credentials in $ENV_FILE${RESET}"
    echo -ne "${BOLD}Do you still want to proceed with Claude Code registration? [y/N]: ${RESET}"
    read -r proceed
    if [[ ! "$proceed" =~ ^[Yy]$ ]]; then
        echo -e "${RED}Setup aborted.${RESET}"
        exit 1
    fi
    echo
fi

echo -e "${BOLD}${YELLOW}[3/3] Registering 'jira-reader' globally for Claude Code...${RESET}"

python3 -c "
import json
from pathlib import Path

p = Path.home() / '.claude.json'
server_path = '/server.py'
config = {}
if p.exists():
    try:
        config = json.loads(p.read_text(encoding='utf-8'))
    except Exception:
        config = {}

mcp_servers = config.setdefault('mcpServers', {})
mcp_servers.pop('jira', None)
mcp_servers.pop('jira-local', None)
mcp_servers['jira-reader'] = {
    'type': 'stdio',
    'command': 'python3',
    'args': [server_path],
    'env': {}
}

p.write_text(json.dumps(config, indent=2), encoding='utf-8')
print(f'✔ Successfully configured jira-reader in {p}')
"

if command -v claude >/dev/null 2>&1; then
    claude mcp remove --scope user jira-local >/dev/null 2>&1 || true
    claude mcp remove --scope user jira >/dev/null 2>&1 || true
    claude mcp add --scope user jira-reader python3 "$SERVER_PY" >/dev/null 2>&1 || true
fi

echo
echo -e "${BOLD}${GREEN}==============================================================================${RESET}"
echo -e "${BOLD}${GREEN}  Setup Complete! 'jira-reader' MCP is now active globally in Claude Code.${RESET}"
echo -e "${BOLD}${GREEN}==============================================================================${RESET}"
echo
echo -e "You can now ask Claude Code:"
echo -e "  ${CYAN}• \"Fetch details and comments for Jira issue PROJ-1234\"${RESET}"
echo -e "  ${CYAN}• \"Read the latest comments on Jira issue PROJ-1234\"${RESET}"
echo -e "  ${CYAN}• \"Search Jira issues with JQL 'project = PROJ AND status = \\\"In Progress\\\"'\"${RESET}"
echo -e "  ${CYAN}• \"Download and inspect the log attachment for PROJ-1234\"${RESET}"
echo
