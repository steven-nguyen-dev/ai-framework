#!/usr/bin/env bash
set -e

APP_NAME="ELK AI Log Explorer"
BUNDLE_NAME="${APP_NAME}.app"
HERE="$(cd "$(dirname "$0")" && pwd)"

TARGET_DIR="/Applications"
if [ ! -w "$TARGET_DIR" ]; then
    TARGET_DIR="$HOME/Applications"
    mkdir -p "$TARGET_DIR"
fi

APP_PATH="${TARGET_DIR}/${BUNDLE_NAME}"
echo "Installing ${APP_NAME} to ${APP_PATH}..."

rm -rf "$APP_PATH"
mkdir -p "${APP_PATH}/Contents/MacOS"
mkdir -p "${APP_PATH}/Contents/Resources/app"

cat << 'PLIST' > "${APP_PATH}/Contents/Info.plist"
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDisplayName</key>
    <string>ELK AI Log Explorer</string>
    <key>CFBundleExecutable</key>
    <string>launcher</string>
    <key>CFBundleIconFile</key>
    <string>appIcon.icns</string>
    <key>CFBundleIdentifier</key>
    <string>com.anchanto.tools.elklogexplorer</string>
    <key>CFBundleName</key>
    <string>ELK AI Log Explorer</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0.0</string>
    <key>LSMinimumSystemVersion</key>
    <string>11.0</string>
</dict>
</plist>
PLIST

echo "APPL????" > "${APP_PATH}/Contents/PkgInfo"

cat << 'LAUNCHER' > "${APP_PATH}/Contents/MacOS/launcher"
#!/usr/bin/env bash
APP_DIR="$(cd "$(dirname "$0")/../Resources/app" && pwd)"
cd "$APP_DIR"

PORT=24004
URL="http://127.0.0.1:${PORT}"

if lsof -ti :${PORT} >/dev/null 2>&1; then
    open "$URL"
    exit 0
fi

(
    sleep 1
    open "$URL"
) &

exec python3 server.py --port "$PORT"
LAUNCHER

chmod +x "${APP_PATH}/Contents/MacOS/launcher"

if [ -f "${HERE}/appIcon.icns" ]; then
    cp "${HERE}/appIcon.icns" "${APP_PATH}/Contents/Resources/"
fi

# Copy app files
cp "${HERE}/server.py" "${APP_PATH}/Contents/Resources/app/"
cp "${HERE}/report.html" "${APP_PATH}/Contents/Resources/app/" 2>/dev/null || true
cp "${HERE}/setup.sh" "${APP_PATH}/Contents/Resources/app/"
cp "${HERE}/start.sh" "${APP_PATH}/Contents/Resources/app/"

echo "✔ Successfully installed ${APP_NAME}.app into ${TARGET_DIR}!"
