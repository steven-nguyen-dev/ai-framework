#!/usr/bin/env bash
# ==============================================================================
# AI-First Framework: Unified MCP Configuration & Diagnostics Wizard
# ==============================================================================
# Configures credentials and validates connectivity for:
#   1. Jira Reader MCP Server (jira-reader)
#   2. Kibana Explorer MCP Server (kibana-explorer)
# ==============================================================================

set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
JIRA_DIR="$DIR/jira-reader"
KIBANA_DIR="$DIR/kibana-explorer"
GLOBAL_MCPS_DIR="$HOME/.mcp"
mkdir -p "$GLOBAL_MCPS_DIR"
GLOBAL_JIRA_ENV="$GLOBAL_MCPS_DIR/jira-reader.env"
GLOBAL_KIBANA_ENV="$GLOBAL_MCPS_DIR/kibana-explorer.env"
LOCAL_JIRA_ENV="$JIRA_DIR/.env"
KIBANA_ENV="$KIBANA_DIR/.env"

BOLD="\033[1m"
GREEN="\033[32m"
YELLOW="\033[33m"
CYAN="\033[36m"
RED="\033[31m"
RESET="\033[0m"

echo -e "${BOLD}${CYAN}==============================================================================${RESET}"
echo -e "${BOLD}${CYAN}  AI-First Framework — Unified MCP Configuration Wizard${RESET}"
echo -e "${BOLD}${CYAN}==============================================================================${RESET}"
echo -e "This wizard configures authentication credentials for ${BOLD}Jira Reader${RESET} and ${BOLD}Kibana Explorer${RESET}."
echo

configure_jira() {
    echo -e "${BOLD}${YELLOW}--- [1/2] Configuring Jira Reader (jira-reader) ---${RESET}"
    
    local host=""
    local auth_choice="1"
    local email=""
    local token=""
    local pat=""
    local download_dir=".scratchpads/downloads"
    local api_version="3"

    # Suggest existing values if present
    local existing_host=""
    local existing_email=""
    if [ -f "$GLOBAL_JIRA_ENV" ]; then
        existing_host=$(grep -E "^JIRA_HOST=" "$GLOBAL_JIRA_ENV" 2>/dev/null | cut -d= -f2- | tr -d '"' | tr -d "'" || true)
        existing_email=$(grep -E "^JIRA_EMAIL=" "$GLOBAL_JIRA_ENV" 2>/dev/null | cut -d= -f2- | tr -d '"' | tr -d "'" || true)
    elif [ -f "$LOCAL_JIRA_ENV" ]; then
        existing_host=$(grep -E "^JIRA_HOST=" "$LOCAL_JIRA_ENV" 2>/dev/null | cut -d= -f2- | tr -d '"' | tr -d "'" || true)
        existing_email=$(grep -E "^JIRA_EMAIL=" "$LOCAL_JIRA_ENV" 2>/dev/null | cut -d= -f2- | tr -d '"' | tr -d "'" || true)
    fi

    echo -ne "${BOLD}Enter Jira Host URL${RESET} [default: ${existing_host:-https://anchantoplan.atlassian.net}]: "
    read -r host_input
    host="${host_input:-${existing_host:-https://anchantoplan.atlassian.net}}"
    host=$(echo "$host" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' -e 's|/*$||')

    echo
    echo -e "${BOLD}Select Jira Authentication Method:${RESET}"
    echo "  1) Jira Cloud (Email + API Token) [Default]"
    echo "  2) Jira Server / Data Center (Personal Access Token - PAT)"
    echo -ne "${BOLD}Choice [1/2] (default 1): ${RESET}"
    read -r auth_choice_input
    if [ "$auth_choice_input" = "2" ]; then
        auth_choice="2"
        api_version="2"
    else
        auth_choice="1"
        api_version="3"
    fi

    if [ "$auth_choice" = "1" ]; then
        echo -ne "${BOLD}Enter Atlassian Login Email${RESET} [default: ${existing_email:-you@company.com}]: "
        read -r email_input
        email="${email_input:-$existing_email}"
        email=$(echo "$email" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')

        while [ -z "$token" ]; do
            echo -ne "${BOLD}Enter Jira API Token (hidden):${RESET} "
            read -rs token
            echo
            token=$(echo "$token" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')
            if [ -z "$token" ]; then
                echo -e "${RED}Error: API Token cannot be empty. Generate at: https://id.atlassian.com/manage-profile/security/api-tokens${RESET}"
            fi
        done
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
    fi

    echo
    echo -ne "${BOLD}Download directory for attachments [default: .scratchpads/downloads]: ${RESET}"
    read -r dl_input
    if [ -n "$dl_input" ]; then
        download_dir="$dl_input"
    fi

    local env_content="# Jira Reader MCP Configuration (.env)
JIRA_HOST=$host
JIRA_DOWNLOAD_DIR=$download_dir
JIRA_API_VERSION=$api_version"

    if [ "$auth_choice" = "1" ]; then
        env_content="$env_content
JIRA_EMAIL=$email
JIRA_API_TOKEN=$token"
    else
        env_content="$env_content
JIRA_PAT=$pat"
    fi

    # Write to ~/.jira.env (global discovery) and local .env
    echo "$env_content" > "$GLOBAL_JIRA_ENV"
    chmod 600 "$GLOBAL_JIRA_ENV"
    echo "$env_content" > "$LOCAL_JIRA_ENV"
    chmod 600 "$LOCAL_JIRA_ENV"

    echo -e "${GREEN}✔ Saved Jira credentials to $GLOBAL_JIRA_ENV and $LOCAL_JIRA_ENV${RESET}"
    echo -e "${CYAN}Testing Jira connectivity...${RESET}"
    if python3 "$JIRA_DIR/server.py" --test; then
        echo -e "${GREEN}✔ Jira Reader connection test PASSED!${RESET}"
    else
        echo -e "${YELLOW}⚠ Jira test failed. Please verify host URL and API token.${RESET}"
    fi
    echo
}

configure_kibana() {
    echo -e "${BOLD}${YELLOW}--- [2/2] Configuring Kibana Explorer (kibana-explorer) ---${RESET}"

    local kibana_url=""
    local kibana_user=""
    local kibana_pass=""
    local kibana_pattern="filebeat-*"
    local kibana_ssl="true"

    local existing_url=""
    local existing_user=""
    local existing_pattern=""
    if [ -f "$KIBANA_ENV" ]; then
        existing_url=$(grep -E "^KIBANA_URL=" "$KIBANA_ENV" 2>/dev/null | cut -d= -f2- | tr -d '"' | tr -d "'" || true)
        existing_user=$(grep -E "^KIBANA_USERNAME=" "$KIBANA_ENV" 2>/dev/null | cut -d= -f2- | tr -d '"' | tr -d "'" || true)
        existing_pattern=$(grep -E "^KIBANA_INDEX_PATTERN=" "$KIBANA_ENV" 2>/dev/null | cut -d= -f2- | tr -d '"' | tr -d "'" || true)
    fi

    echo -ne "${BOLD}Enter Kibana Base URL${RESET} [default: ${existing_url:-https://kibana.internal.company.com:5601}]: "
    read -r url_input
    kibana_url="${url_input:-${existing_url:-https://kibana.internal.company.com:5601}}"
    kibana_url=$(echo "$kibana_url" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' -e 's|/*$||')

    echo -ne "${BOLD}Enter Kibana Username${RESET} [default: ${existing_user:-admin}]: "
    read -r user_input
    kibana_user="${user_input:-${existing_user:-admin}}"

    while [ -z "$kibana_pass" ]; do
        echo -ne "${BOLD}Enter Kibana Password (hidden):${RESET} "
        read -rs kibana_pass
        echo
        kibana_pass=$(echo "$kibana_pass" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')
        if [ -z "$kibana_pass" ]; then
            echo -e "${RED}Error: Kibana password cannot be empty.${RESET}"
        fi
    done

    echo -ne "${BOLD}Default Index Pattern [default: ${existing_pattern:-filebeat-*}]: ${RESET}"
    read -r pattern_input
    kibana_pattern="${pattern_input:-${existing_pattern:-filebeat-*}}"

    echo -ne "${BOLD}Verify SSL Certificates? [Y/n] (choose 'n' for self-signed certs): ${RESET}"
    read -r ssl_input
    if [[ "$ssl_input" =~ ^[Nn]$ ]]; then
        kibana_ssl="false"
    else
        kibana_ssl="true"
    fi

    cat <<EOF > "$KIBANA_ENV"
# Kibana Explorer MCP Configuration (.env)
KIBANA_URL=$kibana_url
KIBANA_USERNAME=$kibana_user
KIBANA_PASSWORD=$kibana_pass
KIBANA_INDEX_PATTERN=$kibana_pattern
KIBANA_VERIFY_SSL=$kibana_ssl
EOF
    chmod 600 "$KIBANA_ENV"
    cp "$KIBANA_ENV" "$GLOBAL_KIBANA_ENV"
    chmod 600 "$GLOBAL_KIBANA_ENV"

    echo -e "${GREEN}✔ Saved Kibana credentials to $GLOBAL_KIBANA_ENV and $KIBANA_ENV${RESET}"
    echo -e "${CYAN}Bootstrapping virtual environment and verifying connectivity...${RESET}"
    if bash "$KIBANA_DIR/launch.sh" --selftest; then
        echo -e "${GREEN}✔ Kibana Explorer selftest PASSED!${RESET}"
    else
        echo -e "${YELLOW}⚠ Kibana selftest failed. Check URL/credentials in $KIBANA_ENV or VPN connection.${RESET}"
    fi
    echo
}

test_all() {
    echo -e "${BOLD}${CYAN}--- Testing Connectivity for All MCP Servers ---${RESET}"
    echo
    echo -e "${BOLD}1. Jira Reader:${RESET}"
    python3 "$JIRA_DIR/server.py" --test || true
    echo
    echo -e "${BOLD}2. Kibana Explorer:${RESET}"
    bash "$KIBANA_DIR/launch.sh" --selftest || true
    echo
}

# Main interactive menu
echo -e "${BOLD}Select an action:${RESET}"
echo "  1) Configure Both Jira Reader & Kibana Explorer [Recommended]"
echo "  2) Configure Jira Reader only"
echo "  3) Configure Kibana Explorer only"
echo "  4) Test connection status for both servers"
echo "  5) Exit"
echo
echo -ne "${BOLD}Enter choice [1-5] (default 1): ${RESET}"
read -r choice
choice="${choice:-1}"
echo

case "$choice" in
    1)
        configure_jira
        configure_kibana
        ;;
    2)
        configure_jira
        ;;
    3)
        configure_kibana
        ;;
    4)
        test_all
        ;;
    5)
        echo "Exiting."
        exit 0
        ;;
    *)
        echo -e "${RED}Invalid option.${RESET}"
        exit 1
        ;;
esac

echo -e "${BOLD}${GREEN}==============================================================================${RESET}"
echo -e "${BOLD}${GREEN}  Configuration Complete!${RESET}"
echo -e "${BOLD}${GREEN}==============================================================================${RESET}"
echo -e "Next steps in Claude Code:"
echo -e "  1. Run ${BOLD}/reload-plugins${RESET}"
echo -e "  2. Type ${BOLD}/mcp${RESET} to verify both servers are connected."
echo
