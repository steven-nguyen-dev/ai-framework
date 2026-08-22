#!/usr/bin/env bash
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Setting up Daily Work Report Server ==="
if ! command -v python3 &>/dev/null; then
    echo "✗ Python 3 is required. Please install via: brew install python"
    exit 1
fi

chmod +x "$SCRIPT_DIR"/*.sh "$SCRIPT_DIR"/*.command "$SCRIPT_DIR"/*.py 2>/dev/null || true
echo "✔ Permissions configured."
python3 "$SCRIPT_DIR/server.py" --export >/dev/null 2>&1 || true
echo "✔ Setup complete."
