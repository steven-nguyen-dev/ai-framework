#!/usr/bin/env bash
# ==============================================================================
# JPluger PR Stats - macOS Application Uninstaller
# ==============================================================================

APP_NAME="JPluger PR Stats.app"

echo "Uninstalling ${APP_NAME}..."

# Kill running server on port 24002 if active
lsof -ti:24002 | xargs kill -9 2>/dev/null || true

rm -rf "/Applications/${APP_NAME}" 2>/dev/null || true
rm -rf "$HOME/Applications/${APP_NAME}" 2>/dev/null || true

echo "✓ ${APP_NAME} removed successfully."
