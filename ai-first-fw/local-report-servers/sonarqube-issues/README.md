# 🔍 SonarQube Issues Explorer Dashboard

Live SonarQube server-parity issue browser, clean code taxonomy filters, remediation effort rollups, and local IntelliJ IDE SonarLint findings for JPluger.

---

## 🚀 1-Step Installation & Launch

Download **[`sonarqube-issues-1.0.0.zip`](./sonarqube-issues-1.0.0.zip)** into your **`~/Downloads`** folder, open **Terminal.app**, and copy & paste one of the two commands below:

---

### Option 1: Install as a macOS Application (Recommended)
Unzips, runs setup verification, and installs **`SonarQube Issues Explorer.app`** directly into your **`/Applications`** folder:

```bash
unzip -o ~/Downloads/sonarqube-issues-1.0.0.zip -d ~/Downloads/sonarqube-issues && cd ~/Downloads/sonarqube-issues && chmod +x *.sh *.command *.py && ./setup.sh && ./install_app.sh
```

**How to open once installed:**
* **Spotlight**: Press `Cmd + Space` and type **`SonarQube Issues Explorer`**.
* **Launchpad / Finder**: Click **`SonarQube Issues Explorer.app`** in `/Applications`.
* **Dock**: Drag the app to your Dock for 1-click launching!

---

### Option 2: Install & Run as a Local Server (Terminal)
Unzips, runs setup verification, and starts the server on **`http://localhost:24006`**:

```bash
unzip -o ~/Downloads/sonarqube-issues-1.0.0.zip -d ~/Downloads/sonarqube-issues && cd ~/Downloads/sonarqube-issues && chmod +x *.sh *.command *.py && ./setup.sh && ./start.sh
```

* Automatically opens your default web browser to the dashboard.
* Press `Ctrl + C` in the terminal to stop the server anytime.

---

## 🛡️ Troubleshooting: If macOS Blocks Script Execution
If macOS displays a security warning because the zip was downloaded from Slack/Email/AirDrop, run:

```bash
xattr -dr com.apple.quarantine ~/Downloads/sonarqube-issues
```
Then re-run your chosen command above.

---

## 🛠️ Configuration & Customization

* **Run on a custom port**:
  ```bash
  cd ~/Downloads/sonarqube-issues && ./start.sh <NEW_PORT>
  # Or: python3 server.py --port <NEW_PORT>
  ```

* **Load an existing or old export file**:
  ```bash
  python3 server.py --file /path/to/sonarqube-issues-report.html
  # Or click "📂 Load Export" / drag & drop any .html or .json export into the dashboard UI
  ```

* **Uninstall macOS Application**:
  ```bash
  cd ~/Downloads/sonarqube-issues && ./uninstall_app.sh
  ```

* **Offline static export**:
  Open `sonarqube-issues.html` or `report.html` directly in any web browser without running a server.

---

## 📁 Package Contents

| File | Description |
| :--- | :--- |
| **`sonarqube-issues-1.0.0.zip`** | Portable distribution archive (v1.0.0) |
| **`setup.sh`** | Automated environment verification & setup |
| **`install_app.sh`** | Native macOS Application installer (`SonarQube Issues Explorer.app`) |
| **`start.sh`** | Terminal launcher (starts server & opens browser on port 24006) |
| **`uninstall_app.sh`** | macOS App uninstaller script |
| **`Install.command`** | Double-click Finder installer script |
| **`Start.command`** | Double-click Finder launcher script |
| **`server.py`** | High-performance Python HTTP server (zero pip dependencies) |
| **`fetcher.py`** | Read-only SonarQube API engine & local H2 database findings bridge |
| **`H2Dump.java`** / **`H2Dump.class`** | Read-only H2 connector utility dumping IntelliJ SonarLint findings |
| **`template.html`** | Interactive dark-theme dashboard UI template |
| **`sonarqube-issues.html`** | Standalone static offline HTML report |
| **`appIcon.icns`** | High-resolution macOS application icon |
| **`data.json`** | Pre-cached snapshot of 16 JPluger projects and issues |
| **`rules_cache.json`** | Cached SonarQube rule descriptions, root causes, and remediation examples |

---

## 🌐 Server Endpoints & Capabilities

* **Dashboard Web UI**: `http://localhost:24006`
* **API Summary KPIs**: `GET /api/stats`
* **API Discovered Projects**: `GET /api/projects`
* **API Server-Parity Issues Search**: `GET /api/issues?project=...&branch=...&quality=...&severity=...&status=...&groupBy=...`
* **API Rule Documentation**: `GET /api/rule?key=...`
* **API Refresh Data**: `POST /api/refresh`
* **Standalone Static Export**: `GET /export`
