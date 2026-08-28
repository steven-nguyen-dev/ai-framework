#!/usr/bin/env bash
# ==============================================================================
# Distribution Packaging Script
# Reads VERSION dynamically and creates a portable standalone zip archive.
# ==============================================================================
set -e

HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"

SERVER_NAME="$(basename "$HERE")"
VERSION="$(cat "${HERE}/VERSION" 2>/dev/null || echo "1.0.0")"
ZIP_NAME="${SERVER_NAME}-${VERSION}.zip"

echo "📦 Packaging ${SERVER_NAME} v${VERSION} -> ${ZIP_NAME}..."
rm -f "${SERVER_NAME}-"*.zip

# Copy theme.css if available so zip is self-contained
THEME_CSS="${HERE}/../../local-theme/theme.css"
if [ -f "$THEME_CSS" ] && [ ! -f "${HERE}/theme.css" ]; then
    cp "$THEME_CSS" "${HERE}/theme.css"
fi

if [ -f "${HERE}/server.py" ]; then
    python3 "${HERE}/server.py" --export >/dev/null 2>&1 || true
fi

zip -r "${ZIP_NAME}" . \
  -x "__pycache__/*" \
  -x "*.pyc" \
  -x "*.zip" \
  -x ".DS_Store" \
  -x ".*"

echo "✔ Successfully created ${ZIP_NAME} (${VERSION})"
