#!/usr/bin/env bash
# Checks if Jira and Kibana MCP credentials exist in ~/.mcp/
# Prints a friendly banner on session start if unconfigured.

JIRA_ENV="$HOME/.mcp/jira-reader.env"
KIBANA_ENV="$HOME/.mcp/kibana-explorer.env"

MISSING=()

if [ ! -f "$JIRA_ENV" ]; then
    MISSING+=("Jira Reader")
fi

if [ ! -f "$KIBANA_ENV" ]; then
    MISSING+=("Kibana Explorer")
fi

if [ ${#MISSING[@]} -gt 0 ]; then
    echo -e "\033[1;33m⚠️  [AI-First Framework] Setup Required:\033[0m"
    echo -e "   The following MCP server(s) are not configured yet: \033[1m${MISSING[*]}\033[0m"
    echo -e "   👉 Type \033[1;36m/config\033[0m in chat to set up your credentials interactively."
    echo
fi
