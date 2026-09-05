#!/usr/bin/env bash
# ==============================================================================
# Eton Orders Monitoring - Environment & Dependency Verifier
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🔍 Verifying environment for Eton Orders Monitoring..."

# 1. Verify Python 3
if ! command -v python3 &>/dev/null; then
    echo "✗ Python 3 is required but not installed. Please install via: brew install python"
    exit 1
fi

PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "  ✓ Python ${PY_VER} detected"

# 2. Grant executable permissions
chmod +x "$SCRIPT_DIR"/*.sh "$SCRIPT_DIR"/*.command "$SCRIPT_DIR"/*.py 2>/dev/null || true

# 3. Ensure data directory exists
mkdir -p "$SCRIPT_DIR/data"

# 4. Warm-up pre-export
python3 "$SCRIPT_DIR/server.py" --export >/dev/null 2>&1 || true

echo "✓ Environment verification complete."
