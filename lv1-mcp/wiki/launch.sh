#!/usr/bin/env bash
# Launcher for the Central Brain & Cloud Files Wiki MCP Server
# Connects over HTTPS via mcp-remote stdio proxy.
#
# Credentials:
#   Reads from ~/.mcp/.wiki.env, with fallbacks to environment variables:
#     WIKI_HOST="https://wiki.concavoi.com/api/mcp"
#     WIKI_API_TOKEN="<token>"
#
# Diagnostics:
#   bash launch.sh --selftest
#
set -euo pipefail

# 1. Load credentials from ~/.mcp/.wiki.env if present
ENV_FILE="${HOME}/.mcp/.wiki.env"
if [ -f "$ENV_FILE" ]; then
    # shellcheck disable=SC1090
    source "$ENV_FILE"
fi

WIKI_HOST="${WIKI_HOST:-https://wiki.concavoi.com/api/mcp}"
WIKI_API_TOKEN="${WIKI_API_TOKEN:-}"

if [ -z "$WIKI_API_TOKEN" ]; then
    echo "[wiki] ERROR: WIKI_API_TOKEN is not set. Create ~/.mcp/.wiki.env with WIKI_API_TOKEN=<token>" >&2
    exit 1
fi

# 2. Diagnostics mode (--selftest)
if [ "${1:-}" = "--selftest" ] || [ "${1:-}" = "--test" ]; then
    echo "=== Wiki MCP Server Selftest ==="
    echo "Endpoint: $WIKI_HOST"

    # Test initialize handshake
    echo -n "Testing MCP handshake (initialize)... "
    INIT_RESP=$(curl -s -X POST "$WIKI_HOST" \
        -H "Authorization: Bearer $WIKI_API_TOKEN" \
        -H "Content-Type: application/json" \
        -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"selftest","version":"1.0.0"}}}')

    SERVER_NAME=$(echo "$INIT_RESP" | grep -o '"name":"[^"]*"' | head -n 1 | cut -d'"' -f4 || echo "")
    if [ "$SERVER_NAME" = "wiki" ]; then
        echo "OK (serverInfo.name: $SERVER_NAME)"
    else
        echo "FAILED"
        echo "Response: $INIT_RESP"
        exit 1
    fi

    # Test tools/list
    echo -n "Testing tool discovery (tools/list)... "
    TOOLS_RESP=$(curl -s -X POST "$WIKI_HOST" \
        -H "Authorization: Bearer $WIKI_API_TOKEN" \
        -H "Content-Type: application/json" \
        -d '{"jsonrpc":"2.0","id":2,"method":"tools/list"}')

    TOOL_NAMES=$(echo "$TOOLS_RESP" | grep -o '"name":"[^"]*"' | cut -d'"' -f4 | sort -u | tr '\n' ' ')
    TOOL_COUNT=$(echo "$TOOLS_RESP" | grep -o '"name":"[^"]*"' | wc -l | tr -d ' ')

    if [ "$TOOL_COUNT" -gt 0 ]; then
        echo "OK ($TOOL_COUNT tools available)"
        echo "Registered tools: $TOOL_NAMES"
    else
        echo "FAILED (no tools found)"
        exit 1
    fi

    echo "=== All Selftests Passed ==="
    exit 0
fi

# 3. Normal stdio execution via mcp-remote
exec npx -y mcp-remote@latest \
    "$WIKI_HOST" \
    --transport http-only \
    --header "Authorization:Bearer ${WIKI_API_TOKEN}" \
    "$@"
