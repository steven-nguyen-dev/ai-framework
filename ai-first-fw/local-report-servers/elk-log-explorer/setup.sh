#!/usr/bin/env bash
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Setting up ELK AI Log Explorer ==="
if ! command -v python3 &>/dev/null; then
    echo "✗ Python 3 is required. Please install via: brew install python"
    exit 1
fi

# 1. Setup local .env from .env.sample if not present
if [ ! -f "$SCRIPT_DIR/.env" ]; then
    if [ -f "$SCRIPT_DIR/.env.sample" ]; then
        cp "$SCRIPT_DIR/.env.sample" "$SCRIPT_DIR/.env"
        echo "✔ Created $SCRIPT_DIR/.env from .env.sample"
    elif [ -f "$SCRIPT_DIR/../../local-mcps/kibana/.env" ]; then
        cp "$SCRIPT_DIR/../../local-mcps/kibana/.env" "$SCRIPT_DIR/.env"
        echo "✔ Copied .env from local-mcps/kibana"
    fi
fi

chmod +x "$SCRIPT_DIR"/*.sh "$SCRIPT_DIR"/*.command "$SCRIPT_DIR"/*.py 2>/dev/null || true
echo "✔ Permissions configured."
echo "✔ Setup complete."
