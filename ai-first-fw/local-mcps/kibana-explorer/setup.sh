#!/usr/bin/env bash
# Create the dedicated virtual environment for the Kibana Explorer MCP server and
# install its dependencies. Run once, on the machine that will host the server:
#
#     bash ai-first-fw/local-mcps/kibana-explorer/setup.sh
#
# Safe to re-run; it reuses an existing .venv and upgrades the packages.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

python3 -m venv "$DIR/.venv"
"$DIR/.venv/bin/pip" install --quiet --upgrade pip
"$DIR/.venv/bin/pip" install --quiet -r "$DIR/requirements.txt"

# Create .env from .env.example if not present
if [ ! -f "$DIR/.env" ]; then
    if [ -f "$DIR/.env.example" ]; then
        cp "$DIR/.env.example" "$DIR/.env"
        echo "✔ Created $DIR/.env from .env.example (fill in your Kibana credentials)"
    elif [ -f "$DIR/.env.sample" ]; then
        cp "$DIR/.env.sample" "$DIR/.env"
        echo "✔ Created $DIR/.env from .env.sample (fill in your Kibana credentials)"
    fi
fi

echo "Dependencies installed into $DIR/.venv"

"$DIR/.venv/bin/python3" "$DIR/test_kql.py" 2>&1 | tail -3

echo
echo "Now verify the live connection:"
echo "  $DIR/.venv/bin/python3 $DIR/server.py --selftest"
