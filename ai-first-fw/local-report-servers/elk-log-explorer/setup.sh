#!/usr/bin/env bash
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Setting up ELK AI Log Explorer ==="
if ! command -v python3 &>/dev/null; then
    echo "✗ Python 3 is required. Please install via: brew install python"
    exit 1
fi

KIBANA_DIR="$SCRIPT_DIR/../../local-mcps/kibana"
if [ -d "$KIBANA_DIR" ] && [ ! -f "$KIBANA_DIR/.env" ] && [ -f "$KIBANA_DIR/.env.sample" ]; then
    cp "$KIBANA_DIR/.env.sample" "$KIBANA_DIR/.env"
    echo "✔ Created $KIBANA_DIR/.env from .env.sample"
fi

chmod +x "$SCRIPT_DIR"/*.sh "$SCRIPT_DIR"/*.command "$SCRIPT_DIR"/*.py 2>/dev/null || true
echo "✔ Permissions configured."
echo "✔ Setup complete."
