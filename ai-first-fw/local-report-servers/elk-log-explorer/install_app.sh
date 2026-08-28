#!/usr/bin/env bash
# ==============================================================================
# ELK AI Log Explorer - macOS Native Application Installer
# Installs "ELK AI Log Explorer.app" to /Applications (or ~/Applications)
# ==============================================================================

set -e

# ANSI Colors
BOLD="\033[1m"
GREEN="\033[32m"
SKY="\033[36m"
YELLOW="\033[33m"
RED="\033[31m"
NC="\033[0m"

APP_NAME="ELK AI Log Explorer"
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
    <string>ELK AI Log Explorer</string>
    <key>CFBundleExecutable</key>
    <string>launcher</string>
    <key>CFBundleIconFile</key>
    <string>appIcon.icns</string>
    <key>CFBundleIdentifier</key>
    <string>com.anchanto.tools.elklogexplorer</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundleName</key>
    <string>ELK AI Log Explorer</string>
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
# ELK AI Log Explorer - macOS App Launcher
# ==============================================================================

DIR="$(cd "$(dirname "$0")/../Resources/app" && pwd)"
PORT="24004"

# Ensure common Homebrew and system PATHs are accessible
export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

# 1. If server is already responsive on port 24004, just focus/open the browser
if curl -s -m 1 "http://127.0.0.1:${PORT}/api/status" >/dev/null 2>&1; then
    open "http://localhost:${PORT}"
    exit 0
fi

# 2. Launch local server in background
cd "$DIR" || exit 1
LOG_DIR="$HOME/Library/Logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/elk-log-explorer.log"

nohup python3 server.py --port "$PORT" > "$LOG_FILE" 2>&1 &

# 3. Wait up to 3 seconds for server startup
for i in {1..15}; do
    if curl -s -m 1 "http://127.0.0.1:${PORT}/api/status" >/dev/null 2>&1; then
        break
    fi
    sleep 0.2
done

# 4. Open dashboard in default browser
open "http://localhost:${PORT}"

# 5. Native macOS notification
osascript -e 'display notification "ELK AI Log Explorer running on http://localhost:24004" with title "ELK AI Log Explorer" sound name "Glass"' 2>/dev/null || true
LAUNCHER

chmod +x "${APP_PATH}/Contents/MacOS/launcher"

# ------------------------------------------------------------------------------
# 6. Copy Icon and Application Assets
# ------------------------------------------------------------------------------
if [ -f "${HERE}/appIcon.icns" ]; then
    cp "${HERE}/appIcon.icns" "${APP_PATH}/Contents/Resources/appIcon.icns"
fi

echo "  • Copying application core files..."
# Pre-generate static export if needed
if [ -f "${HERE}/server.py" ]; then
    python3 "${HERE}/server.py" --export >/dev/null 2>&1 || true
fi

# Ensure theme.css is copied
if [ -f "${HERE}/../../local-theme/theme.css" ]; then
    cp "${HERE}/../../local-theme/theme.css" "${APP_PATH}/Contents/Resources/app/theme.css"
elif [ -f "${HERE}/theme.css" ]; then
    cp "${HERE}/theme.css" "${APP_PATH}/Contents/Resources/app/theme.css"
fi

cp "${HERE}/server.py" "${APP_PATH}/Contents/Resources/app/"
cp "${HERE}/kql.py" "${APP_PATH}/Contents/Resources/app/" 2>/dev/null || true
cp "${HERE}/report.html" "${APP_PATH}/Contents/Resources/app/" 2>/dev/null || true
cp "${HERE}/elk-log-explorer.html" "${APP_PATH}/Contents/Resources/app/" 2>/dev/null || true
cp "${HERE}/start.sh" "${APP_PATH}/Contents/Resources/app/" 2>/dev/null || true
cp "${HERE}/setup.sh" "${APP_PATH}/Contents/Resources/app/" 2>/dev/null || true
cp "${HERE}/VERSION" "${APP_PATH}/Contents/Resources/app/" 2>/dev/null || true
cp "${HERE}/.env.sample" "${APP_PATH}/Contents/Resources/app/" 2>/dev/null || true
if [ -f "${HERE}/.env" ]; then
    cp "${HERE}/.env" "${APP_PATH}/Contents/Resources/app/" 2>/dev/null || true
elif [ -f "${HERE}/../../local-mcps/kibana/.env" ]; then
    cp "${HERE}/../../local-mcps/kibana/.env" "${APP_PATH}/Contents/Resources/app/.env" 2>/dev/null || true
fi

chmod +x "${APP_PATH}/Contents/Resources/app/"*.py 2>/dev/null || true
chmod +x "${APP_PATH}/Contents/Resources/app/"*.sh 2>/dev/null || true

# Clear quarantine extended attributes
xattr -dr com.apple.quarantine "$APP_PATH" 2>/dev/null || true

# Register with macOS LaunchServices database
LSREGISTER="/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister"
if [ ! -f "$LSREGISTER" ]; then
    LSREGISTER="/System/Library/Frameworks/CoreServices.framework/Versions/A/Frameworks/LaunchServices.framework/Versions/A/Support/lsregister"
fi
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
echo -e "  🌐 ${BOLD}Dashboard URL:${NC} ${SKY}http://localhost:24004${NC}"
echo -e "  📝 ${BOLD}Logs Location:${NC} ~/Library/Logs/elk-log-explorer.log"
echo ""

# Ask to open now if in interactive shell
if [ -t 0 ]; then
    read -p "Would you like to open ${APP_NAME} now? [Y/n] " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]] || [[ -z $REPLY ]]; then
        open "$APP_PATH"
    fi
fi
