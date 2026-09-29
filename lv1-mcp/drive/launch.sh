#!/usr/bin/env bash
# Launcher for the Cloud Drive MCP Server ('drive')
# Connects over HTTPS via mcp-remote stdio proxy.
#
# Credentials:
#   Reads from ~/.mcp/.drive.env, with fallbacks to environment variables:
#     DRIVE_HOST="https://files.concavoi.com/api/mcp"
#     DRIVE_API_TOKEN="<token>"
#
# Diagnostics:
#   bash launch.sh --selftest
#
set -euo pipefail

# 1. Load credentials from ~/.mcp/.drive.env if present
ENV_FILE="${HOME}/.mcp/.drive.env"
if [ -f "$ENV_FILE" ]; then
    # shellcheck disable=SC1090
    source "$ENV_FILE"
fi

DRIVE_HOST="${DRIVE_HOST:-https://files.concavoi.com/api/mcp}"
DRIVE_API_TOKEN="${DRIVE_API_TOKEN:-}"

if [ -z "$DRIVE_API_TOKEN" ]; then
    echo "[drive] ERROR: DRIVE_API_TOKEN is not set. Create ~/.mcp/.drive.env with DRIVE_API_TOKEN=<token>" >&2
    exit 1
fi

# 2. Diagnostics mode (--selftest)
if [ "${1:-}" = "--selftest" ] || [ "${1:-}" = "--test" ]; then
    echo "=== Drive MCP Server Selftest ==="
    echo "Endpoint: $DRIVE_HOST"

    # Test initialize handshake
    echo -n "Testing MCP handshake (initialize)... "
    INIT_RESP=$(curl -s -X POST "$DRIVE_HOST" \
        -H "Authorization: Bearer $DRIVE_API_TOKEN" \
        -H "Content-Type: application/json" \
        -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"selftest","version":"1.0.0"}}}')

    SERVER_NAME=$(echo "$INIT_RESP" | grep -o '"name":"[^"]*"' | head -n 1 | cut -d'"' -f4 || echo "")
    if [ "$SERVER_NAME" = "drive" ]; then
        echo "OK (serverInfo.name: $SERVER_NAME)"
    else
        echo "FAILED"
        echo "Response: $INIT_RESP"
        exit 1
    fi

    # Test tools/list
    echo -n "Testing tool discovery (tools/list)... "
    TOOLS_RESP=$(curl -s -X POST "$DRIVE_HOST" \
        -H "Authorization: Bearer $DRIVE_API_TOKEN" \
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
    "$DRIVE_HOST" \
    --transport http-only \
    --header "Authorization:Bearer ${DRIVE_API_TOKEN}" \
    "$@"
