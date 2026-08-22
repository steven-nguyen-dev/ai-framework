#!/usr/bin/env bash
APP_NAME="Daily Work Report"
BUNDLE_NAME="${APP_NAME}.app"
TARGET_DIR="/Applications"
[ ! -w "$TARGET_DIR" ] && TARGET_DIR="$HOME/Applications"

rm -rf "${TARGET_DIR}/${BUNDLE_NAME}"
echo "✔ Uninstalled ${APP_NAME}."
