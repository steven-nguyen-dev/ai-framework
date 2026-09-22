#!/usr/bin/env bash
# Launcher for the Swarm Coordinator MCP Server
# Stdio JSON-RPC transport for Claude and Antigravity.
set -euo pipefail

SOURCE="${BASH_SOURCE[0]}"
while [ -h "$SOURCE" ]; do
    DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"
    SOURCE="$(readlink "$SOURCE")"
    [[ $SOURCE != /* ]] && SOURCE="$DIR/$SOURCE"
done
DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"
VENV="${HOME}/.local/share/swarm/venv"
PY="${VENV}/bin/python3"

needs_bootstrap() {
    [ -x "$PY" ] || return 0
    "$PY" -c 'import mcp, redis' >/dev/null 2>&1 || return 0
    return 1
}

if needs_bootstrap; then
    echo "[coordinator] bootstrapping venv at $VENV ..." >&2
    mkdir -p "$(dirname "$VENV")"
    rm -rf "$VENV"
    python3 -m venv --clear "$VENV" >&2
    "$VENV/bin/pip" install --quiet --upgrade pip >&2
    "$VENV/bin/pip" install --quiet -r "$DIR/requirements.txt" >&2
    echo "[coordinator] dependencies installed" >&2
fi

PARENT_DIR="$(cd "$DIR/.." && pwd)"
export PYTHONPATH="${PARENT_DIR}:${PYTHONPATH:-}"

exec "$PY" -m coordinator.server "$@"
