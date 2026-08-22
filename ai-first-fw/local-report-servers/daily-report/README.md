# 📝 Daily Work Report Live Server & Dashboard

A lightweight, zero-dependency local report server and live viewer for daily engineering work reports, carry-forward actions, and on-going matter tracking.

---

## 🚀 1-Step Installation & Launch

Download **[`daily-report-1.0.0.zip`](./daily-report-1.0.0.zip)** into your **`~/Downloads`** folder, open **Terminal.app**, and copy & paste one of the two commands below:

---

### Option 1: Install as a macOS Application (Recommended)
Unzips, runs environment verification, and installs **`Daily Work Report.app`** directly into your **`/Applications`** folder:

```bash
unzip -o ~/Downloads/daily-report-1.0.0.zip -d ~/Downloads/daily-report && cd ~/Downloads/daily-report && chmod +x *.sh *.command *.py && ./setup.sh && ./install_app.sh
```

**How to open once installed:**
* **Spotlight**: Press `Cmd + Space` and type **`Daily Work Report`**.
* **Launchpad / Finder**: Click **`Daily Work Report.app`** in `/Applications`.
* **Dock**: Drag the app to your Dock for 1-click launching!

---

### Option 2: Install & Run as a Local Server (Terminal)
Unzips, runs setup verification, and starts the server on **`http://localhost:24001`**:

```bash
unzip -o ~/Downloads/daily-report-1.0.0.zip -d ~/Downloads/daily-report && cd ~/Downloads/daily-report && chmod +x *.sh *.command *.py && ./setup.sh && ./start.sh
```

* Automatically opens your default web browser to the dashboard.
* Press `Ctrl + C` in the terminal to stop the server anytime.

---

## 🛡️ Troubleshooting: If macOS Blocks Script Execution
If macOS displays a security warning because the zip was downloaded from Slack/Email/AirDrop, run:

```bash
xattr -dr com.apple.quarantine ~/Downloads/daily-report
```
Then re-run your chosen command above.

---

## 🛠️ Configuration & Customization

* **Run on a custom port**:
  ```bash
  cd ~/Downloads/daily-report && ./start.sh 24005
  # Or: python3 server.py --port 24005
  ```

* **Custom workspace directory**:
  ```bash
  python3 server.py --workspace /path/to/project-workspace
  ```

* **Uninstall macOS Application**:
  ```bash
  cd ~/Downloads/daily-report && ./uninstall_app.sh
  ```

* **Offline static export**:
  Open `daily-report.html` (or `today-report.html`) directly in any web browser without running a server.

---

## 📁 Package Contents

| File | Description |
| :--- | :--- |
| **`daily-report-1.0.0.zip`** | Portable distribution archive (v1.0.0) |
| **`setup.sh`** | Automated environment verification & cache generator |
| **`install_app.sh`** | Native macOS Application installer (`Daily Work Report.app`) |
| **`start.sh`** | Terminal launcher (starts server & opens browser) |
| **`uninstall_app.sh`** | macOS App uninstaller script |
| **`Install.command`** | Double-click Finder installer script |
| **`Start.command`** | Double-click Finder launcher script |
| **`server.py`** | High-performance Python HTTP server (Python 3.9+ compatible) |
| **`today-report.html`** | Interactive dark-theme dashboard UI template |
| **`daily-report.html`** | Standalone static offline HTML report |
| **`appIcon.icns`** | High-resolution macOS application icon |

---

## 🌐 Server Endpoints & Capabilities

* **Dashboard Web UI**: `http://localhost:24001`
* **Health & Status**: `GET /api/status`
* **Reports List API**: `GET /api/reports`
* **Daily Report Raw Markdown**: `GET /daily-reports/<filename>`
* **Matters Raw Markdown**: `GET /matters/<path>`
* **Standalone Static Export**: `python3 server.py --export`
