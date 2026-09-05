#!/usr/bin/env bash
# ==============================================================================
# Eton Orders Monitoring - macOS Native Application Installer
# Installs "Eton Orders Monitoring.app" to /Applications (or ~/Applications)
# ==============================================================================

set -e

BOLD="\033[1m"
GREEN="\033[32m"
SKY="\033[36m"
YELLOW="\033[33m"
RED="\033[31m"
NC="\033[0m"

APP_NAME="Eton Orders Monitoring"
BUNDLE_NAME="${APP_NAME}.app"
HERE="$(cd "$(dirname "$0")" && pwd)"

echo -e "${BOLD}${SKY}========================================================================${NC}"
echo -e "${BOLD} 🍎 Installing ${APP_NAME} as a macOS Application ${NC}"
echo -e "${BOLD}${SKY}========================================================================${NC}"
echo ""

TARGET_DIR="/Applications"
if [ ! -w "$TARGET_DIR" ]; then
    TARGET_DIR="$HOME/Applications"
    mkdir -p "$TARGET_DIR"
fi

APP_PATH="${TARGET_DIR}/${BUNDLE_NAME}"
echo -e "  • Target Location: ${BOLD}${GREEN}${APP_PATH}${NC}"

if [ -d "$APP_PATH" ]; then
    echo -e "  • Updating existing installation at ${APP_PATH}..."
    rm -rf "$APP_PATH"
fi

mkdir -p "${APP_PATH}/Contents/MacOS"
mkdir -p "${APP_PATH}/Contents/Resources/app"

APP_VERSION="$(cat "${HERE}/VERSION" 2>/dev/null || echo "1.0.0")"

cat << PLIST > "${APP_PATH}/Contents/Info.plist"
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDevelopmentRegion</key>
    <string>en</string>
    <key>CFBundleDisplayName</key>
    <string>Eton Orders Monitoring</string>
    <key>CFBundleExecutable</key>
    <string>launcher</string>
    <key>CFBundleIconFile</key>
    <string>appIcon.icns</string>
    <key>CFBundleIdentifier</key>
    <string>com.anchanto.tools.etonordersmonitoring</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundleName</key>
    <string>Eton Orders Monitoring</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>${APP_VERSION}</string>
    <key>CFBundleVersion</key>
    <string>${APP_VERSION}</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.13</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>NSHumanReadableCopyright</key>
    <string>Copyright © 2026 Anchanto. All rights reserved.</string>
</dict>
</plist>
PLIST

echo -n "APPL????" > "${APP_PATH}/Contents/PkgInfo"

cat << 'LAUNCHER' > "${APP_PATH}/Contents/MacOS/launcher"
#!/bin/bash
DIR="$(cd "$(dirname "$0")/../Resources/app" && pwd)"
PORT="24005"

export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

if curl -s -m 1 "http://127.0.0.1:${PORT}/api/stats" >/dev/null 2>&1; then
    open "http://localhost:${PORT}"
    exit 0
fi

cd "$DIR" || exit 1
LOG_DIR="$HOME/Library/Logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/eton-orders-monitoring.log"

nohup python3 server.py --port "$PORT" > "$LOG_FILE" 2>&1 &

for i in {1..15}; do
    if curl -s -m 1 "http://127.0.0.1:${PORT}/api/stats" >/dev/null 2>&1; then
        break
    fi
    sleep 0.2
done

open "http://localhost:${PORT}"
osascript -e 'display notification "Eton Orders Monitoring running on http://localhost:24005" with title "Eton Orders Monitoring" sound name "Glass"' 2>/dev/null || true
LAUNCHER

chmod +x "${APP_PATH}/Contents/MacOS/launcher"

if [ -f "${HERE}/appIcon.icns" ]; then
    cp "${HERE}/appIcon.icns" "${APP_PATH}/Contents/Resources/appIcon.icns"
fi

if [ -f "${HERE}/server.py" ]; then
    python3 "${HERE}/server.py" --export >/dev/null 2>&1 || true
fi

cp "${HERE}/server.py" "${APP_PATH}/Contents/Resources/app/"
cp "${HERE}/report.html" "${APP_PATH}/Contents/Resources/app/" 2>/dev/null || true
cp "${HERE}/eton-orders-monitoring.html" "${APP_PATH}/Contents/Resources/app/" 2>/dev/null || true
cp "${HERE}/theme.css" "${APP_PATH}/Contents/Resources/app/" 2>/dev/null || true
cp "${HERE}/theme.js" "${APP_PATH}/Contents/Resources/app/" 2>/dev/null || true
cp "${HERE}/start.sh" "${APP_PATH}/Contents/Resources/app/" 2>/dev/null || true
cp "${HERE}/setup.sh" "${APP_PATH}/Contents/Resources/app/" 2>/dev/null || true
cp "${HERE}/VERSION" "${APP_PATH}/Contents/Resources/app/" 2>/dev/null || true
cp "${HERE}/.env.sample" "${APP_PATH}/Contents/Resources/app/" 2>/dev/null || true
if [ -f "${HERE}/.env" ]; then
    cp "${HERE}/.env" "${APP_PATH}/Contents/Resources/app/" 2>/dev/null || true
fi

chmod +x "${APP_PATH}/Contents/Resources/app/"*.py 2>/dev/null || true
chmod +x "${APP_PATH}/Contents/Resources/app/"*.sh 2>/dev/null || true

xattr -dr com.apple.quarantine "$APP_PATH" 2>/dev/null || true

LSREGISTER="/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister"
if [ ! -f "$LSREGISTER" ]; then
    LSREGISTER="/System/Library/Frameworks/CoreServices.framework/Versions/A/Frameworks/LaunchServices.framework/Versions/A/Support/lsregister"
fi
if [ -f "$LSREGISTER" ]; then
    "$LSREGISTER" -f "$APP_PATH" 2>/dev/null || true
fi

touch "$APP_PATH"

echo ""
echo -e "${BOLD}${GREEN}========================================================================${NC}"
echo -e "${BOLD}${GREEN}  🎉 ${APP_NAME} Installed Successfully! ${NC}"
echo -e "${BOLD}${GREEN}========================================================================${NC}"
echo -e "  🌐 ${BOLD}Dashboard URL:${NC} ${SKY}http://localhost:24005${NC}"
echo -e "  📝 ${BOLD}Logs Location:${NC} ~/Library/Logs/eton-orders-monitoring.log"
echo ""
