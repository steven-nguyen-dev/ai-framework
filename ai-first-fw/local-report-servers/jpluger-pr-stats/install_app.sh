#!/usr/bin/env bash
# ==============================================================================
# JPluger PR Stats - macOS Native Application Installer
# Installs "JPluger PR Stats.app" to /Applications (or ~/Applications)
# ==============================================================================

set -e

# ANSI Colors
BOLD="\033[1m"
GREEN="\033[32m"
SKY="\033[36m"
YELLOW="\033[33m"
RED="\033[31m"
NC="\033[0m"

APP_NAME="JPluger PR Stats"
BUNDLE_NAME="${APP_NAME}.app"
HERE="$(cd "$(dirname "$0")" && pwd)"

echo -e "${BOLD}${SKY}========================================================================${NC}"
echo -e "${BOLD} 🍎 Installing ${APP_NAME} as a macOS Application ${NC}"
echo -e "${BOLD}${SKY}========================================================================${NC}"
echo ""

# ------------------------------------------------------------------------------
# 1. Determine Target Applications Directory
# ------------------------------------------------------------------------------
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

# ------------------------------------------------------------------------------
# 2. Construct macOS App Bundle Structure
# ------------------------------------------------------------------------------
echo "  • Creating Application Bundle structure..."
mkdir -p "${APP_PATH}/Contents/MacOS"
mkdir -p "${APP_PATH}/Contents/Resources/app"

APP_VERSION="$(cat "${HERE}/VERSION" 2>/dev/null || echo "1.0.0")"

# ------------------------------------------------------------------------------
# 3. Create Info.plist
# ------------------------------------------------------------------------------
cat << PLIST > "${APP_PATH}/Contents/Info.plist"
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDevelopmentRegion</key>
    <string>en</string>
    <key>CFBundleDisplayName</key>
    <string>JPluger PR Stats</string>
    <key>CFBundleExecutable</key>
    <string>launcher</string>
    <key>CFBundleIconFile</key>
    <string>appIcon.icns</string>
    <key>CFBundleIdentifier</key>
    <string>com.anchanto.jpluger.prstats</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundleName</key>
    <string>JPluger PR Stats</string>
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

# ------------------------------------------------------------------------------
# 4. Create PkgInfo
# ------------------------------------------------------------------------------
echo -n "APPL????" > "${APP_PATH}/Contents/PkgInfo"

# ------------------------------------------------------------------------------
# 5. Create Executable Launcher (Contents/MacOS/launcher)
# ------------------------------------------------------------------------------
cat << 'LAUNCHER' > "${APP_PATH}/Contents/MacOS/launcher"
#!/bin/bash
# ==============================================================================
# JPluger PR Stats - macOS App Launcher
# ==============================================================================

DIR="$(cd "$(dirname "$0")/../Resources/app" && pwd)"
PORT="24002"

# Ensure common Homebrew and system PATHs are accessible
export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

# 1. Check if gh is installed & authenticated. If not, launch interactive Terminal setup
if ! gh auth status >/dev/null 2>&1; then
    osascript -e '
    tell application "Terminal"
        activate
        do script "cd \"'"$DIR"'\" && ./setup.sh"
    end tell'
    exit 0
fi

# 2. If server is already responsive on port 24002, just focus/open the browser
if curl -s -m 1 "http://127.0.0.1:${PORT}/api/stats" >/dev/null 2>&1; then
    open "http://localhost:${PORT}"
    exit 0
fi

# 3. Launch local server in background
cd "$DIR" || exit 1
LOG_DIR="$HOME/Library/Logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/jpluger-pr-stats.log"

nohup python3 server.py --port "$PORT" > "$LOG_FILE" 2>&1 &

# 3. Wait up to 3 seconds for server startup
for i in {1..15}; do
    if curl -s -m 1 "http://127.0.0.1:${PORT}/api/stats" >/dev/null 2>&1; then
        break
    fi
    sleep 0.2
done

# 4. Open dashboard in default browser
open "http://localhost:${PORT}"

# 5. Native macOS notification
osascript -e 'display notification "Dashboard running on http://localhost:24002" with title "JPluger PR Stats" sound name "Glass"' 2>/dev/null || true
LAUNCHER

chmod +x "${APP_PATH}/Contents/MacOS/launcher"

# ------------------------------------------------------------------------------
# 6. Copy Icon and Application Assets
# ------------------------------------------------------------------------------
if [ -f "${HERE}/appIcon.icns" ]; then
    cp "${HERE}/appIcon.icns" "${APP_PATH}/Contents/Resources/appIcon.icns"
fi

echo "  • Copying application core files..."
cp "${HERE}/server.py" "${APP_PATH}/Contents/Resources/app/"
cp "${HERE}/fetcher.py" "${APP_PATH}/Contents/Resources/app/"
cp "${HERE}/template.html" "${APP_PATH}/Contents/Resources/app/"
cp "${HERE}/data.json" "${APP_PATH}/Contents/Resources/app/"
cp "${HERE}/report.html" "${APP_PATH}/Contents/Resources/app/" 2>/dev/null || true
cp "${HERE}/start.sh" "${APP_PATH}/Contents/Resources/app/" 2>/dev/null || true
cp "${HERE}/setup.sh" "${APP_PATH}/Contents/Resources/app/" 2>/dev/null || true

chmod +x "${APP_PATH}/Contents/Resources/app/"*.py 2>/dev/null || true
chmod +x "${APP_PATH}/Contents/Resources/app/"*.sh 2>/dev/null || true

# Clear quarantine extended attributes
xattr -dr com.apple.quarantine "$APP_PATH" 2>/dev/null || true

# Register with macOS LaunchServices database
LSREGISTER="/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister"
if [ -f "$LSREGISTER" ]; then
    "$LSREGISTER" -f "$APP_PATH" 2>/dev/null || true
fi

# Force Finder to refresh bundle icon & attributes
touch "$APP_PATH"

echo ""
echo -e "${BOLD}${GREEN}========================================================================${NC}"
echo -e "${BOLD}${GREEN}  🎉 ${APP_NAME} Installed Successfully! ${NC}"
echo -e "${BOLD}${GREEN}========================================================================${NC}"
echo ""
echo -e "  ▶ ${BOLD}How to Launch:${NC}"
echo -e "      • Double-click ${BOLD}${SKY}${APP_PATH}${NC} in Finder"
echo -e "      • Press ${BOLD}Cmd + Space${NC} (Spotlight) and search for ${BOLD}${SKY}\"${APP_NAME}\"${NC}"
echo -e "      • Or run in terminal: ${BOLD}open \"${APP_PATH}\"${NC}"
echo ""
echo -e "  🌐 ${BOLD}Dashboard URL:${NC} ${SKY}http://localhost:24002${NC}"
echo -e "  📝 ${BOLD}Logs Location:${NC} ~/Library/Logs/jpluger-pr-stats.log"
echo ""

# Ask to open now if in interactive shell
if [ -t 0 ]; then
    read -p "Would you like to open ${APP_NAME} now? [Y/n] " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]] || [[ -z $REPLY ]]; then
        open "$APP_PATH"
    fi
fi
