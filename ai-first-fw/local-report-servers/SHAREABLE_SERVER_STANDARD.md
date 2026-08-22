# 📦 Standard for Building Shareable Local Report & Tool Servers

This standard defines how to transform any local HTTP dashboard or utility server in this repository into a **portable, self-contained, 1-click installable macOS Application and Terminal service** packaged as a `.zip` archive with an executive README.

---

## 🎯 The Goal

When a user prompts:
> **"Make this local server shareable"**

The AI agent must automatically scaffold the standard 7-file launcher suite, generate the distribution zip archive, and format the executive `README.md` following the exact blueprint below.

---

## 📋 Required Package Blueprint

Every shareable server directory must contain the following manifest:

```
<server-name>/
├── Install.command          # Double-click Finder installer
├── Start.command            # Double-click Finder launcher
├── setup.sh                 # Environment & dependency verifier
├── install_app.sh           # Native macOS Application installer (.app bundle)
├── start.sh                 # Terminal launcher with auto browser opening
├── uninstall_app.sh         # Application uninstaller
├── appIcon.icns             # High-resolution macOS application icon
├── server.py                # Python HTTP server (machine-independent, handles --port & --export)
├── report.html / template   # UI template using shared dark theme tokens
├── <server-name>.html       # Pre-generated 100% self-contained offline export
├── README.md                # Executive 1-Step Installation & Launch documentation
└── <server-name>-1.0.0.zip  # Pre-packaged distribution archive
```

---

## 🛠️ Step-by-Step AI Implementation Checklist

### Step 1: Ensure Server Portability & Inlined Export (`server.py`)
1. **Zero hardcoded user paths**: Use `Path.home()`, `os.getenv("HOME")`, and dynamic workspace root resolution (`find_workspace_root()`).
2. **Dynamic port binding**:
   ```python
   parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "<DEFAULT_PORT>")))
   parser.add_argument("--host", type=str, default=os.getenv("HOST", "127.0.0.1"))
   parser.add_argument("--export", action="store_true", help="Generate static standalone HTML report and exit")
   ```
3. **Port collision handling**: Catch `OSError: [Errno 48] Address already in use` and print helpful commands (`kill -9 $(lsof -ti :<PORT>)` or `--port`).
4. **Self-contained static export**: When `--export` is called, inline `theme.css` so the generated HTML report opens offline with zero server dependencies.

---

### Step 2: Scaffold Launcher & Installer Scripts

#### 1. `setup.sh` (Environment Verifier)
```bash
#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 1. Verify Python 3
if ! command -v python3 &>/dev/null; then
    echo "✗ Python 3 is not installed. Please install via: brew install python"
    exit 1
fi

# 2. Verify any required CLI tools (e.g. gh, git) if applicable
# 3. Grant permissions
chmod +x "$SCRIPT_DIR"/*.sh "$SCRIPT_DIR"/*.command "$SCRIPT_DIR"/*.py 2>/dev/null || true

# 4. Warm-up pre-scan / data export
python3 "$SCRIPT_DIR/server.py" --export >/dev/null 2>&1 || true
```

#### 2. `start.sh` (Terminal Launcher)
```bash
#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PORT="${1:-<DEFAULT_PORT>}"
URL="http://localhost:${PORT}"

# Open browser in background
(
  sleep 1
  command -v open &>/dev/null && open "$URL" || command -v xdg-open &>/dev/null && xdg-open "$URL"
) &

python3 server.py --port "$PORT"
```

#### 3. `install_app.sh` (macOS Application Bundle Installer)
Creates `<App Name>.app` in `/Applications` (fallback `~/Applications`):
* `Contents/Info.plist`: Declares `CFBundleDisplayName`, `CFBundleExecutable` (`launcher`), `CFBundleIconFile` (`appIcon.icns`), `CFBundleIdentifier` (`com.anchanto.<domain>.<app>`).
* `Contents/PkgInfo`: `APPL????`.
* `Contents/MacOS/launcher`:
  - If server already running on port, opens browser immediately.
  - Else launches `server.py` in background, pipes logs to `~/Library/Logs/<server-name>.log`.
  - Waits up to 3 seconds for server response, opens browser, and triggers native notification (`display notification`).
* Copies core files to `Contents/Resources/app/`.
* Clears quarantine: `xattr -dr com.apple.quarantine "$APP_PATH"`.
* Registers with `lsregister`.

#### 4. `uninstall_app.sh` (App Uninstaller)
```bash
#!/usr/bin/env bash
APP_NAME="<App Name>"
BUNDLE_NAME="${APP_NAME}.app"

for TARGET in "/Applications/${BUNDLE_NAME}" "$HOME/Applications/${BUNDLE_NAME}"; do
    [ -d "$TARGET" ] && rm -rf "$TARGET" && echo "✓ Removed $TARGET"
done

kill -9 $(lsof -ti :<DEFAULT_PORT>) 2>/dev/null || true
echo "✓ ${APP_NAME} uninstalled successfully."
```

#### 5. `Install.command` & `Start.command` (Finder Double-Click Helpers)
* **`Install.command`**:
  ```bash
  #!/bin/bash
  cd -- "$(dirname "$0")"
  chmod +x *.sh *.command *.py 2>/dev/null || true
  bash ./setup.sh && bash ./install_app.sh
  ```
* **`Start.command`**:
  ```bash
  #!/bin/bash
  cd -- "$(dirname "$0")"
  chmod +x *.sh *.command *.py 2>/dev/null || true
  bash ./start.sh "$@"
  ```

#### 6. `appIcon.icns`
Copy high-resolution macOS application icon (e.g. from existing report servers or local theme assets).

---

### Step 3: Format the Executive README (`README.md`)

The `README.md` must strictly follow this executive template:

````markdown
# <Icon> <App Title> Dashboard

<One-line executive summary of what this tool / report server provides.>

---

## 🚀 1-Step Installation & Launch

Download **[`<server-name>-1.0.0.zip`](./<server-name>-1.0.0.zip)** into your **`~/Downloads`** folder, open **Terminal.app**, and copy & paste one of the two commands below:

---

### Option 1: Install as a macOS Application (Recommended)
Unzips, runs setup verification, and installs **`<App Name>.app`** directly into your **`/Applications`** folder:

```bash
unzip ~/Downloads/<server-name>-1.0.0.zip -d ~/Downloads && cd ~/Downloads/<server-name> && chmod +x *.sh && ./setup.sh && ./install_app.sh
```

**How to open once installed:**
* **Spotlight**: Press `Cmd + Space` and type **`<App Name>`**.
* **Launchpad / Finder**: Click **`<App Name>.app`** in `/Applications`.
* **Dock**: Drag the app to your Dock for 1-click launching!

---

### Option 2: Install & Run as a Local Server (Terminal)
Unzips, runs setup verification, and starts the server on **`http://localhost:<PORT>`**:

```bash
unzip ~/Downloads/<server-name>-1.0.0.zip -d ~/Downloads && cd ~/Downloads/<server-name> && chmod +x *.sh && ./setup.sh && ./start.sh
```

* Automatically opens your default web browser to the dashboard.
* Press `Ctrl + C` in the terminal to stop the server anytime.

---

## 🛡️ Troubleshooting: If macOS Blocks Script Execution
If macOS displays a security warning because the zip was downloaded from Slack/Email/AirDrop, run:

```bash
xattr -dr com.apple.quarantine ~/Downloads/<server-name>
```
Then re-run your chosen command above.

---

## 🛠️ Configuration & Customization

* **Run on a custom port**:
  ```bash
  cd ~/Downloads/<server-name> && ./start.sh <NEW_PORT>
  # Or: python3 server.py --port <NEW_PORT>
  ```

* **Uninstall macOS Application**:
  ```bash
  cd ~/Downloads/<server-name> && ./uninstall_app.sh
  ```

* **Offline static export**:
  Open `<server-name>.html` directly in any web browser without running a server.

---

## 📁 Package Contents

| File | Description |
| :--- | :--- |
| **`<server-name>-1.0.0.zip`** | Portable distribution archive (v1.0.0) |
| **`setup.sh`** | Automated environment verification & setup |
| **`install_app.sh`** | Native macOS Application installer (`<App Name>.app`) |
| **`start.sh`** | Terminal launcher (starts server & opens browser) |
| **`uninstall_app.sh`** | macOS App uninstaller script |
| **`Install.command`** | Double-click Finder installer script |
| **`Start.command`** | Double-click Finder launcher script |
| **`server.py`** | High-performance Python HTTP server |
| **`report.html`** | Interactive dark-theme dashboard UI template |
| **`<server-name>.html`** | Standalone static offline HTML report |
| **`appIcon.icns`** | High-resolution macOS application icon |

---

## 🌐 Server Endpoints & Capabilities

* **Dashboard Web UI**: `http://localhost:<PORT>`
* **API Endpoints**: `<LIST OF APIS>`
* **Standalone Static Export**: `GET /export`
````

---

### Step 4: Package the Distribution Zip Archive (Inside Server Folder Only)

The distribution `.zip` archive **must reside strictly inside the server directory** (e.g. `elk-log-explorer/elk-log-explorer-1.0.0.zip`). Never copy or leave stray zip files in parent or root directories.

Run the standard packaging command to generate clean, portable archives without cache or temporary files:

```bash
cd local-report-servers && \
rm -f <server-name>/<server-name>-1.0.0.zip && \
zip -r <server-name>/<server-name>-1.0.0.zip <server-name>/ \
  -x "<server-name>/__pycache__/*" \
  -x "<server-name>/*.pyc" \
  -x "<server-name>/*.zip" \
  -x "<server-name>/.DS_Store" \
  -x "<server-name>/.*"
```

---

## 🔐 Security & Server Lifecycle Rules

1. **`.env.sample` Security Rule**:
   - If the server connects to an external API (e.g. Kibana, Jira, GitHub), commit only `.env.sample` with dummy placeholders.
   - `setup.sh` must automatically copy `.env.sample` $\rightarrow$ `.env` if `.env` does not exist.
   - `*.env` is strictly gitignored — zero credentials in git history.
2. **Server Lifecycle Rule**:
   - Never launch long-running background daemon servers directly from AI agent background tasks.
   - Always prompt the user to start or manage servers through the **Central Reports Portal** (`python3 portal.py` on port `24000`) or via `Start.command`.

---

## 🤖 Summary Prompt to Trigger This Workflow

Whenever you need a server packaged, you can prompt:
> **"Please make `<server_folder>` shareable following the Shareable Server Standard: scaffold the installer & launcher scripts, generate the 1.0.0 zip package, and format the executive README."**
