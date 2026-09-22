#!/usr/bin/env bash
# Launcher for the Wiki markdown loader (wiki-ingest)
set -euo pipefail

SOURCE="${BASH_SOURCE[0]}"
while [ -h "$SOURCE" ]; do
    DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"
    SOURCE="$(readlink "$SOURCE")"
    [[ $SOURCE != /* ]] && SOURCE="$DIR/$SOURCE"
done
DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"
VENV="${HOME}/.local/share/wiki-mcp/venv"
PY="${VENV}/bin/python3"

needs_bootstrap() {
    [ -x "$PY" ] || return 0
    "$PY" -c 'import psycopg' >/dev/null 2>&1 || return 0
    return 1
}

if needs_bootstrap; then
    echo "[wiki-ingest] bootstrapping venv at $VENV ..." >&2
    mkdir -p "$(dirname "$VENV")"
    rm -rf "$VENV"
    python3 -m venv --clear "$VENV" >&2
    "$VENV/bin/pip" install --quiet --upgrade pip >&2
    "$VENV/bin/pip" install --quiet -r "$DIR/requirements.txt" >&2
    echo "[wiki-ingest] dependencies installed" >&2
fi

PARENT_DIR="$(cd "$DIR/.." && pwd)"
export PYTHONPATH="${PARENT_DIR}:${PYTHONPATH:-}"

exec "$PY" -m wiki.ingest.cli "$@"
