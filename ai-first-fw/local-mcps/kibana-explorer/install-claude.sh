#!/usr/bin/env bash
# ==============================================================================
# Kibana Explorer MCP - Claude Code Global Installer & Setup
# ==============================================================================
# This script:
#   1. Prompts for and sets up Kibana credentials in .env (if missing/reconfiguring)
#   2. Bootstraps the Python venv dependencies and tests the live connection
#   3. Configures Claude Code globally (~/.claude.json) to enable kibana-explorer MCP
# ==============================================================================

set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAUNCH_SH="$DIR/launch.sh"
ENV_FILE="$DIR/.env"
CLAUDE_JSON="$HOME/.claude.json"

BOLD="\033[1m"
GREEN="\033[32m"
YELLOW="\033[33m"
CYAN="\033[36m"
RED="\033[31m"
RESET="\033[0m"

echo -e "${BOLD}${CYAN}==============================================================================${RESET}"
echo -e "${BOLD}${CYAN}  Kibana Explorer MCP — Claude Code Global Installer & Setup${RESET}"
echo -e "${BOLD}${CYAN}==============================================================================${RESET}"
echo

configure_env() {
    echo -e "${BOLD}${YELLOW}[1/3] Configuring Kibana Credentials...${RESET}"
    
    local url=""
    local username=""
    local password=""
    local cookie=""
    local index_pattern="logs-*-*,logs-*,filebeat-*"
    local verify_ssl="true"

    while [ -z "$url" ]; do
        echo -ne "${BOLD}Enter Kibana Base URL${RESET} (e.g. https://kibana.example.com:5601): "
        read -r url
        url=$(echo "$url" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' -e 's|/*$||')
        if [ -z "$url" ]; then
            echo -e "${RED}Error: Kibana URL cannot be empty.${RESET}"
        fi
    done

    while [ -z "$username" ]; do
        echo -ne "${BOLD}Enter Kibana Login Username / Email:${RESET} "
        read -r username
        username=$(echo "$username" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')
        if [ -z "$username" ]; then
            echo -e "${RED}Error: Username cannot be empty.${RESET}"
        fi
    done

    while [ -z "$password" ]; do
        echo -ne "${BOLD}Enter Kibana Login Password (hidden):${RESET} "
        read -rs password
        echo
        password=$(echo "$password" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')
        if [ -z "$password" ]; then
            echo -e "${RED}Error: Password cannot be empty.${RESET}"
        fi
    done

    echo -ne "${BOLD}(Optional) Browser Session Cookie (sid=... or press Enter to skip): ${RESET}"
    read -r cookie_input
    cookie=$(echo "$cookie_input" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')

    echo -ne "${BOLD}Default Index Pattern [default: logs-*-*,logs-*,filebeat-*]: ${RESET}"
    read -r idx_input
    if [ -n "$idx_input" ]; then
        index_pattern="$idx_input"
    fi

    echo -ne "${BOLD}Verify SSL? [Y/n, default: true]: ${RESET}"
    read -r ssl_input
    if [[ "$ssl_input" =~ ^[Nn]$ ]]; then
        verify_ssl="false"
    fi

    echo "# Kibana Explorer MCP Configuration (.env)" > "$ENV_FILE"
    echo "KIBANA_URL=$url" >> "$ENV_FILE"
    echo "KIBANA_USERNAME=$username" >> "$ENV_FILE"
    echo "KIBANA_PASSWORD=$password" >> "$ENV_FILE"
    if [ -n "$cookie" ]; then
        echo "KIBANA_COOKIE=$cookie" >> "$ENV_FILE"
    fi
    echo "KIBANA_INDEX_PATTERN=$index_pattern" >> "$ENV_FILE"
    echo "KIBANA_VERIFY_SSL=$verify_ssl" >> "$ENV_FILE"

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

echo -e "${BOLD}${YELLOW}[2/3] Bootstrapping virtualenv & verifying connection...${RESET}"
if bash "$LAUNCH_SH" --selftest; then
    echo -e "${GREEN}✔ Connection and selftest passed!"
    echo
else
    echo -e "${RED}⚠ Selftest probe had warnings or failed. Please check your credentials in $ENV_FILE${RESET}"
    echo -ne "${BOLD}Do you still want to proceed with Claude Code registration? [y/N]: ${RESET}"
    read -r proceed
    if [[ ! "$proceed" =~ ^[Yy]$ ]]; then
        echo -e "${RED}Setup aborted.${RESET}"
        exit 1
    fi
    echo
fi

echo -e "${BOLD}${YELLOW}[3/3] Registering 'kibana-explorer' globally for Claude Code...${RESET}"

python3 -c "
import json
from pathlib import Path

p = Path.home() / '.claude.json'
launch_path = '/launch.sh'
config = {}
if p.exists():
    try:
        config = json.loads(p.read_text(encoding='utf-8'))
    except Exception:
        config = {}

mcp_servers = config.setdefault('mcpServers', {})
mcp_servers.pop('kibana', None)
mcp_servers['kibana-explorer'] = {
    'type': 'stdio',
    'command': 'bash',
    'args': [launch_path],
    'env': {}
}

p.write_text(json.dumps(config, indent=2), encoding='utf-8')
print(f'✔ Successfully configured kibana-explorer in {p}')
"

if command -v claude >/dev/null 2>&1; then
    claude mcp remove --scope user kibana >/dev/null 2>&1 || true
    claude mcp add --scope user kibana-explorer bash "$LAUNCH_SH" >/dev/null 2>&1 || true
fi

echo
echo -e "${BOLD}${GREEN}==============================================================================${RESET}"
echo -e "${BOLD}${GREEN}  Setup Complete! 'kibana-explorer' MCP is now active globally in Claude Code.${RESET}"
echo -e "${BOLD}${GREEN}==============================================================================${RESET}"
echo
echo -e "You can now ask Claude Code:"
echo -e "  ${CYAN}• "Search Kibana logs with KQL 'log.level:ERROR AND service.name:oms' in the last 1 hour"${RESET}"
echo -e "  ${CYAN}• "Count how many error logs occurred in the last 24h"${RESET}"
echo -e "  ${CYAN}• "Show me a histogram of 500 errors over the past 7 days"${RESET}"
echo
