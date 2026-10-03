#!/usr/bin/env bash
# Launcher for the Testbed MCP Server ('testbed')
# Stdio JSON-RPC transport; the only route agents use to reach the cloud mock server and the suite engine.
#
# Credentials:
#   Reads from ~/.mcp/.testbed.env, with fallbacks to environment variables:
#     TESTBED_HOST="https://test.concavoi.com"
#     TESTBED_API_TOKEN="<admin password>"
#     TESTBED_PATH_KEY="<app route path key>"
#   Optional: LV1_SERVERS_ROOT, JPLUGER_ROOT, TESTBED_MCP_DATA.
#
# Diagnostics:
#   bash launch.sh --selftest
#
set -euo pipefail

SOURCE="${BASH_SOURCE[0]}"
while [ -h "$SOURCE" ]; do
    DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"
    SOURCE="$(readlink "$SOURCE")"
    [[ $SOURCE != /* ]] && SOURCE="$DIR/$SOURCE"
done
DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"

# 1. Load credentials from ~/.mcp/.testbed.env if present
ENV_FILE="${HOME}/.mcp/.testbed.env"
if [ -f "$ENV_FILE" ]; then
    set -a
    # shellcheck disable=SC1090
    source "$ENV_FILE"
    set +a
fi

export TESTBED_HOST="${TESTBED_HOST:-https://test.concavoi.com}"
export TESTBED_API_TOKEN="${TESTBED_API_TOKEN:-}"
export TESTBED_PATH_KEY="${TESTBED_PATH_KEY:-}"

if [ -z "$TESTBED_API_TOKEN" ]; then
    echo "[testbed] ERROR: TESTBED_API_TOKEN is not set. Create ~/.mcp/.testbed.env with TESTBED_API_TOKEN=<admin password>" >&2
    exit 1
fi

# 2. Bootstrap the venv on first run or when a dependency is missing
VENV="${HOME}/.local/share/lv1-testbed-mcp/venv"
PY="${VENV}/bin/python3"
if ! { [ -x "$PY" ] && "$PY" -c 'import mcp, certifi' >/dev/null 2>&1; }; then
    echo "[testbed] bootstrapping venv at $VENV ..." >&2
    mkdir -p "$(dirname "$VENV")"
    python3 -m venv --clear "$VENV" >&2
    "$VENV/bin/pip" install --quiet --upgrade pip >&2
    "$VENV/bin/pip" install --quiet -r "$DIR/requirements.txt" >&2
    echo "[testbed] dependencies installed" >&2
fi

PARENT_DIR="$(cd "$DIR/.." && pwd)"
export PYTHONPATH="${PARENT_DIR}:${PYTHONPATH:-}"

# 3. Diagnostics mode (--selftest) or stdio server
exec "$PY" -m testbed.server "$@"
