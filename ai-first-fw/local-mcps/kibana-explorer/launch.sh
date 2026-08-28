#!/usr/bin/env bash
# Launcher for the Kibana Explorer MCP server.
#
# .mcp.json points here rather than straight at .venv/bin/python3 so a missing
# or half-built virtualenv self-heals instead of failing the server at startup
# with an exec error the client reports only as "server exited". The venv is
# gitignored, so a fresh clone or a machine change always starts without one.
#
#     bash ai-first-fw/local-mcps/kibana-explorer/launch.sh            run as MCP stdio server
#     bash ai-first-fw/local-mcps/kibana-explorer/launch.sh --selftest  check credentials
#
# Anything this script prints goes to stderr: stdout belongs to the MCP stdio
# transport and any stray byte there corrupts the JSON-RPC stream.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$DIR/.venv"
PY="$VENV/bin/python3"

needs_bootstrap() {
    [ -x "$PY" ] || return 0
    "$PY" -c 'import mcp' >/dev/null 2>&1 || return 0
    return 1
}

# --clear is required: without it, `venv` keeps a pre-existing bin/python3
# symlink, so rebuilding over a venv made by another interpreter leaves
# bin/python3 on the OLD version while pyvenv.cfg and site-packages are the
# new one. Packages then install where bin/python3 cannot see them.

if needs_bootstrap; then
    echo "[kibana-explorer] bootstrapping $VENV ..." >&2
    rm -rf "$VENV"
    python3 -m venv --clear "$VENV" >&2
    "$VENV/bin/pip" install --quiet --upgrade pip >&2
    "$VENV/bin/pip" install --quiet -r "$DIR/requirements.txt" >&2
    echo "[kibana-explorer] dependencies installed" >&2
fi

if [ ! -f "$DIR/.env" ]; then
    if [ -f "$DIR/.env.example" ]; then
        cp "$DIR/.env.example" "$DIR/.env"
        echo "[kibana-explorer] created $DIR/.env from .env.example - fill in your Kibana credentials" >&2
    elif [ -f "$DIR/.env.sample" ]; then
        cp "$DIR/.env.sample" "$DIR/.env"
        echo "[kibana-explorer] created $DIR/.env from .env.sample - fill in your Kibana credentials" >&2
    fi
fi

exec "$PY" "$DIR/server.py" "$@"
