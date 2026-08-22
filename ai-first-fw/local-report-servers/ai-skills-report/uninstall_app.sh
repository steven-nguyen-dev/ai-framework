#!/usr/bin/env bash
# ==============================================================================
# AI Skills & Plugins Registry - macOS Application Uninstaller
# ==============================================================================

APP_NAME="AI Skills & Plugins Registry"
BUNDLE_NAME="${APP_NAME}.app"

echo "Uninstalling ${APP_NAME}..."

for TARGET in "/Applications/${BUNDLE_NAME}" "$HOME/Applications/${BUNDLE_NAME}"; do
    if [ -d "$TARGET" ]; then
        rm -rf "$TARGET"
        echo "✓ Removed $TARGET"
    fi
done

# Kill running server process if active
kill -9 $(lsof -ti :24003) 2>/dev/null || true

echo "✓ ${APP_NAME} uninstalled successfully."
