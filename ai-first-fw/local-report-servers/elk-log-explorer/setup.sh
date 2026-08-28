#!/usr/bin/env bash
set -e

export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Setting up ELK AI Log Explorer ==="
if ! command -v python3 &>/dev/null; then
    echo "✗ Python 3 is required. Please install via: brew install python"
    exit 1
fi

# 1. Setup local .env from existing local-mcps/kibana/.env or .env.sample
if [ ! -f "$SCRIPT_DIR/.env" ]; then
    if [ -f "$SCRIPT_DIR/../../local-mcps/kibana/.env" ]; then
        cp "$SCRIPT_DIR/../../local-mcps/kibana/.env" "$SCRIPT_DIR/.env"
        echo "✔ Copied live .env from local-mcps/kibana"
    elif [ -f "$SCRIPT_DIR/.env.sample" ]; then
        cp "$SCRIPT_DIR/.env.sample" "$SCRIPT_DIR/.env"
        echo "✔ Created $SCRIPT_DIR/.env from .env.sample"
    fi
fi

# 2. Ensure theme.css is bundled locally if available
if [ ! -f "$SCRIPT_DIR/theme.css" ] && [ -f "$SCRIPT_DIR/../../local-theme/theme.css" ]; then
    cp "$SCRIPT_DIR/../../local-theme/theme.css" "$SCRIPT_DIR/theme.css" 2>/dev/null || true
fi

# 3. Permissions
chmod +x "$SCRIPT_DIR"/*.sh "$SCRIPT_DIR"/*.command "$SCRIPT_DIR"/*.py 2>/dev/null || true
echo "✔ Permissions configured."

# 4. Generate standalone static offline export
python3 "$SCRIPT_DIR/server.py" --export >/dev/null 2>&1 || true

echo "✔ Setup complete."
