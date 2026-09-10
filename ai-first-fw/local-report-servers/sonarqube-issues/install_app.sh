#!/usr/bin/env bash
# ==============================================================================
# SonarQube Issues Explorer - macOS Native Application Installer
# Installs "SonarQube Issues Explorer.app" to /Applications (or ~/Applications)
# ==============================================================================

set -e

BOLD="\033[1m"
GREEN="\033[32m"
SKY="\033[36m"
YELLOW="\033[33m"
RED="\033[31m"
NC="\033[0m"

APP_NAME="SonarQube Issues Explorer"
BUNDLE_NAME="${APP_NAME}.app"
HERE="$(cd "$(dirname "$0")" && pwd)"
DEFAULT_PORT="24006"

echo -e "${BOLD}${SKY}========================================================================${NC}"
echo -e "${BOLD} 🍎 Installing ${APP_NAME} as a macOS Application ${NC}"
echo -e "${BOLD}${SKY}========================================================================${NC}"
echo ""

# 1. Determine Target Applications Directory
TARGET_DIR="/Applications"
if [ ! -w "$TARGET_DIR" ]; then
    TARGET_DIR="$HOME/Applications"
    mkdir -p "$TARGET_DIR"
fi

APP_PATH="${TARGET_DIR}/${BUNDLE_NAME}"
echo -e "  • Target Location: ${BOLD}${GREEN}${APP_PATH}${NC}"

# Remove existing version if present
if [ -d "$APP_PATH" ]; then
    echo -e "  • Updating existing installation at ${APP_PATH}..."
    rm -rf "$APP_PATH"
fi

# 2. Construct macOS App Bundle Structure
mkdir -p "${APP_PATH}/Contents/MacOS"
mkdir -p "${APP_PATH}/Contents/Resources/app"

APP_VERSION="$(cat "${HERE}/VERSION" 2>/dev/null || echo "1.0.0")"

# 3. Create Info.plist
cat << PLIST > "${APP_PATH}/Contents/Info.plist"
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDevelopmentRegion</key>
    <string>en</string>
    <key>CFBundleDisplayName</key>
    <string>SonarQube Issues Explorer</string>
    <key>CFBundleExecutable</key>
    <string>launcher</string>
    <key>CFBundleIconFile</key>
    <string>appIcon.icns</string>
    <key>CFBundleIdentifier</key>
    <string>com.anchanto.jpluger.sonarqube.issues</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundleName</key>
    <string>SonarQube Issues Explorer</string>
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

# 4. Create PkgInfo
echo -n "APPL????" > "${APP_PATH}/Contents/PkgInfo"

# 5. Create Executable Launcher
cat << 'LAUNCHER' > "${APP_PATH}/Contents/MacOS/launcher"
#!/bin/bash
DIR="$(cd "$(dirname "$0")/../Resources/app" && pwd)"
PORT="24006"

export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

# If server already running on port, open browser immediately
if curl -s -m 1 "http://127.0.0.1:${PORT}/api/stats" >/dev/null 2>&1; then
    open "http://localhost:${PORT}"
    exit 0
fi

cd "$DIR" || exit 1
LOG_DIR="$HOME/Library/Logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/sonarqube-issues.log"

nohup python3 server.py --port "$PORT" > "$LOG_FILE" 2>&1 &

for i in {1..15}; do
    if curl -s -m 1 "http://127.0.0.1:${PORT}/api/stats" >/dev/null 2>&1; then
        break
    fi
    sleep 0.2
done

open "http://localhost:${PORT}"
osascript -e 'display notification "Dashboard running on http://localhost:24006" with title "SonarQube Issues Explorer" sound name "Glass"' 2>/dev/null || true
LAUNCHER

chmod +x "${APP_PATH}/Contents/MacOS/launcher"

# 6. Copy Icon and Application Assets
if [ -f "${HERE}/appIcon.icns" ]; then
    cp "${HERE}/appIcon.icns" "${APP_PATH}/Contents/Resources/appIcon.icns"
fi

echo "  • Copying application core files..."
cp "${HERE}/server.py" "${APP_PATH}/Contents/Resources/app/"
cp "${HERE}/fetcher.py" "${APP_PATH}/Contents/Resources/app/"
cp "${HERE}/template.html" "${APP_PATH}/Contents/Resources/app/"
cp "${HERE}/data.json" "${APP_PATH}/Contents/Resources/app/" 2>/dev/null || true
cp "${HERE}/rules_cache.json" "${APP_PATH}/Contents/Resources/app/" 2>/dev/null || true
cp "${HERE}/VERSION" "${APP_PATH}/Contents/Resources/app/" 2>/dev/null || true
cp "${HERE}/H2Dump.class" "${APP_PATH}/Contents/Resources/app/" 2>/dev/null || true
cp "${HERE}/H2Dump.java" "${APP_PATH}/Contents/Resources/app/" 2>/dev/null || true
cp "${HERE}/setup.sh" "${APP_PATH}/Contents/Resources/app/" 2>/dev/null || true
cp "${HERE}/start.sh" "${APP_PATH}/Contents/Resources/app/" 2>/dev/null || true
cp "${HERE}/.env.sample" "${APP_PATH}/Contents/Resources/app/" 2>/dev/null || true

# Copy local-theme folder if exists
if [ -d "${HERE}/../../local-theme" ]; then
    mkdir -p "${APP_PATH}/Contents/Resources/local-theme"
    cp -r "${HERE}/../../local-theme/"* "${APP_PATH}/Contents/Resources/local-theme/"
elif [ -d "${HERE}/../local-theme" ]; then
    mkdir -p "${APP_PATH}/Contents/Resources/local-theme"
    cp -r "${HERE}/../local-theme/"* "${APP_PATH}/Contents/Resources/local-theme/"
fi

# 7. Clear Quarantine and register
xattr -dr com.apple.quarantine "$APP_PATH" 2>/dev/null || true
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f "$APP_PATH" 2>/dev/null || true

echo ""
echo -e "${BOLD}${GREEN}========================================================================${NC}"
echo -e "${BOLD}${GREEN}  ✓ ${APP_NAME} installed successfully!${NC}"
echo -e "${BOLD}${GREEN}========================================================================${NC}"
echo -e "  Location: ${BOLD}${SKY}${APP_PATH}${NC}"
echo -e "  Launch anytime via Spotlight (Cmd + Space) or Finder!"
echo ""
