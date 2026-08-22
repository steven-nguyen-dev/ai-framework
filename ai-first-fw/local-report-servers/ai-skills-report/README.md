# 🧩 AI Skills & Plugins Registry Dashboard

Universal skills & plugins catalog, marketplace manager, and multi-agent environment inspector for **Claude Code**, **Claude Cowork**, **Antigravity 2.0**, and **Gemini** on macOS.

---

## 🚀 1-Step Installation & Launch

Download **[`ai-skills-report-1.0.0.zip`](./ai-skills-report-1.0.0.zip)** into your **`~/Downloads`** folder, open **Terminal.app**, and copy & paste one of the two commands below:

---

### Option 1: Install as a macOS Application (Recommended)
Unzips, runs environment verification, and installs **`AI Skills & Plugins Registry.app`** directly into your **`/Applications`** folder:

```bash
unzip ~/Downloads/ai-skills-report-1.0.0.zip -d ~/Downloads && cd ~/Downloads/ai-skills-report && chmod +x *.sh && ./setup.sh && ./install_app.sh
```

**How to open once installed:**
* **Spotlight**: Press `Cmd + Space` and type **`AI Skills & Plugins Registry`**.
* **Launchpad / Finder**: Click **`AI Skills & Plugins Registry.app`** in `/Applications`.
* **Dock**: Drag the app to your Dock for 1-click launching!

---

### Option 2: Install & Run as a Local Server (Terminal)
Unzips, runs setup verification, and starts the server on **`http://localhost:24003`**:

```bash
unzip ~/Downloads/ai-skills-report-1.0.0.zip -d ~/Downloads && cd ~/Downloads/ai-skills-report && chmod +x *.sh && ./setup.sh && ./start.sh
```

* Automatically opens your default web browser to the registry dashboard.
* Press `Ctrl + C` in the terminal to stop the server anytime.

---

## 🛡️ Troubleshooting: If macOS Blocks Script Execution
If macOS displays a security warning because the zip was downloaded from Slack/Email/AirDrop, run:

```bash
xattr -dr com.apple.quarantine ~/Downloads/ai-skills-report
```
Then re-run your chosen command above.

---

## 🛠️ Configuration & Customization

* **Run on a custom port**:
  ```bash
  cd ~/Downloads/ai-skills-report && ./start.sh 24005
  # Or: python3 server.py --port 24005
  ```

* **Uninstall macOS Application**:
  ```bash
  cd ~/Downloads/ai-skills-report && ./uninstall_app.sh
  ```

* **Offline static export**:
  Open `ai-skills-report.html` directly in any web browser without running a server (100% self-contained).

---

## 📁 Package Contents

| File | Description |
| :--- | :--- |
| **`ai-skills-report-1.0.0.zip`** | Portable distribution archive (v1.0.0) |
| **`setup.sh`** | Automated environment verification & cache generator |
| **`install_app.sh`** | Native macOS Application installer (`AI Skills & Plugins Registry.app`) |
| **`start.sh`** | Terminal launcher (starts server & opens browser) |
| **`uninstall_app.sh`** | macOS App uninstaller script |
| **`Install.command`** | Double-click Finder installer script |
| **`Start.command`** | Double-click Finder launcher script |
| **`server.py`** | High-performance Python HTTP server (Python 3.9+ compatible) |
| **`scanner.py`** | Multi-agent skill & plugin discovery engine (Claude & Antigravity/Gemini) |
| **`report.html`** | Interactive dark-theme dashboard UI template |
| **`ai-skills-report.html`** | Standalone static offline HTML report |
| **`appIcon.icns`** | High-resolution macOS application icon |

---

## 🌐 Server Endpoints & Capabilities

* **Dashboard Web UI**: `http://localhost:24003`
* **JSON Inventory API**: `GET /api/data`
* **Add Marketplace**: `POST /api/marketplace/add` (`{"source": "owner/repo"}`)
* **Remove Marketplace**: `POST /api/marketplace/remove` (`{"name": "marketplace_name"}`)
* **Uninstall Plugin**: `POST /api/plugin/uninstall` (`{"plugin_id": "...", "install_path": "..."}`)
* **Standalone Static Export**: `GET /export`
