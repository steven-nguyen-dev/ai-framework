#!/usr/bin/env bash
APP_NAME="Eton Orders Monitoring"
BUNDLE_NAME="${APP_NAME}.app"

for TARGET in "/Applications/${BUNDLE_NAME}" "$HOME/Applications/${BUNDLE_NAME}"; do
    [ -d "$TARGET" ] && rm -rf "$TARGET" && echo "✓ Removed $TARGET"
done

kill -9 $(lsof -ti :24005) 2>/dev/null || true
echo "✓ ${APP_NAME} uninstalled successfully."
