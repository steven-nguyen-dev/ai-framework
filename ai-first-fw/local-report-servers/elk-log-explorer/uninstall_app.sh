#!/usr/bin/env bash
APP_NAME="ELK AI Log Explorer"
BUNDLE_NAME="${APP_NAME}.app"

for TARGET in "/Applications/${BUNDLE_NAME}" "$HOME/Applications/${BUNDLE_NAME}"; do
    [ -d "$TARGET" ] && rm -rf "$TARGET" && echo "✓ Removed $TARGET"
done

kill -9 $(lsof -ti :24004) 2>/dev/null || true
echo "✓ ${APP_NAME} uninstalled successfully."
