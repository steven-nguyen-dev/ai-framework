#!/usr/bin/env bash
# ==============================================================================
# SonarQube Issues Explorer - macOS Application Uninstaller
# ==============================================================================
set -e

APP_NAME="SonarQube Issues Explorer"
BUNDLE_NAME="${APP_NAME}.app"
PORT="24006"

echo "🗑 Uninstalling ${APP_NAME}..."

for TARGET in "/Applications/${BUNDLE_NAME}" "$HOME/Applications/${BUNDLE_NAME}"; do
    if [ -d "$TARGET" ]; then
        rm -rf "$TARGET"
        echo "✓ Removed $TARGET"
    fi
done

# Kill running server on port if running
PID=$(lsof -ti :$PORT 2>/dev/null || true)
if [ -n "$PID" ]; then
    kill -9 "$PID" 2>/dev/null || true
    echo "✓ Stopped server process on port $PORT"
fi

echo "✓ ${APP_NAME} uninstalled successfully."
