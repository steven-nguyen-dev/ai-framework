# 📊 JPluger Pull Request Statistics Dashboard

Executive engineering dashboard, velocity tracker, and pull request triage system for **`Anchanto/JPluger`**.

---

## 🚀 1-Step Installation & Launch

Download **[`jpluger-pr-stats-1.0.0.zip`](./jpluger-pr-stats-1.0.0.zip)** into your **`~/Downloads`** folder, open **Terminal.app**, and copy & paste one of the two commands below:

---

### Option 1: Install as a macOS Application (Recommended)
Unzips, runs setup, prompts for GitHub login, and installs **`JPluger PR Stats.app`** directly into your **`/Applications`** folder:

```bash
unzip ~/Downloads/jpluger-pr-stats-1.0.0.zip -d ~/Downloads && cd ~/Downloads/jpluger-pr-stats && chmod +x *.sh && ./setup.sh && ./install_app.sh
```

**How to open once installed:**
* **Spotlight**: Press `Cmd + Space` and type **`JPluger PR Stats`**.
* **Launchpad / Finder**: Click **`JPluger PR Stats.app`** in `/Applications`.
* **Dock**: Drag the app to your Dock for 1-click launching!

---

### Option 2: Install & Run as a Local Server (Terminal)
Unzips, runs setup, prompts for GitHub login, and starts the server on **`http://localhost:24002`**:

```bash
unzip ~/Downloads/jpluger-pr-stats-1.0.0.zip -d ~/Downloads && cd ~/Downloads/jpluger-pr-stats && chmod +x *.sh && ./setup.sh && ./start.sh
```

* Automatically opens your default web browser to the dashboard.
* Press `Ctrl + C` in the terminal to stop the server anytime.

---

## 🛡️ Troubleshooting: If macOS Blocks Script Execution
If macOS displays a security warning because the zip was downloaded from Slack/Email/AirDrop, run:

```bash
xattr -dr com.apple.quarantine ~/Downloads/jpluger-pr-stats
```
Then re-run your chosen command above.

---

## 🛠️ Configuration & Customization

* **Run on a custom port**:
  ```bash
  cd ~/Downloads/jpluger-pr-stats && ./start.sh 24005
  # Or: python3 server.py --port 24005
  ```

* **Uninstall macOS Application**:
  ```bash
  cd ~/Downloads/jpluger-pr-stats && ./uninstall_app.sh
  ```

* **Offline static export**:
  Open `~/Downloads/jpluger-pr-stats/report.html` directly in any web browser without running a server.

---

## 📁 Package Contents

| File | Description |
| :--- | :--- |
| **`jpluger-pr-stats-1.0.0.zip`** | Portable distribution archive (v1.0.0) |
| **`setup.sh`** | Automated installer (`gh` CLI + Auth check + Data fetch) |
| **`install_app.sh`** | Native macOS Application installer (`JPluger PR Stats.app`) |
| **`start.sh`** | Terminal launcher (starts server & opens browser) |
| **`uninstall_app.sh`** | macOS App uninstaller script |
| **`server.py`** | Multi-threaded Python HTTP server (Python 3.8+ compatible) |
| **`fetcher.py`** | GitHub GraphQL & REST API data fetching engine |
| **`template.html`** | Interactive dashboard UI template |
| **`data.json`** | Pre-bundled cache dataset |
| **`report.html`** | Standalone static offline HTML report |
| **`appIcon.icns`** | High-resolution macOS application icon |

---

## 🌐 Server Endpoints
* **Dashboard Web UI**: `http://localhost:24002`
* **Live Refresh API**: `POST /api/refresh`
* **JSON Metrics API**: `GET /api/stats`
* **Standalone Static Export**: `GET /export`
