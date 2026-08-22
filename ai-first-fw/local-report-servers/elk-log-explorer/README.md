# 🔍 ELK AI Log Explorer & Query Dashboard

An interactive AI-powered ELK / Kibana Log Explorer with dual AI Agent integrations (**Claude 3.7 Sonnet** & **Antigravity AGY Gemini 3.7 Flash**) and direct KQL querying.

---

## 🚀 1-Step Installation & Launch

Download **[`elk-log-explorer-1.0.0.zip`](./elk-log-explorer-1.0.0.zip)** into your **`~/Downloads`** folder, open **Terminal.app**, and copy & paste one of the two commands below:

---

### Option 1: Install as a macOS Application (Recommended)
Unzips, runs environment verification, and installs **`ELK AI Log Explorer.app`** directly into your **`/Applications`** folder:

```bash
unzip -o ~/Downloads/elk-log-explorer-1.0.0.zip -d ~/Downloads/elk-log-explorer && cd ~/Downloads/elk-log-explorer && chmod +x *.sh *.command *.py && ./setup.sh && ./install_app.sh
```

**How to open once installed:**
* **Spotlight**: Press `Cmd + Space` and type **`ELK AI Log Explorer`**.
* **Launchpad / Finder**: Click **`ELK AI Log Explorer.app`** in `/Applications`.
* **Dock**: Drag the app to your Dock for 1-click launching!

---

### Option 2: Install & Run as a Local Server (Terminal)
Unzips, runs setup verification, and starts the server on **`http://localhost:24004`**:

```bash
unzip -o ~/Downloads/elk-log-explorer-1.0.0.zip -d ~/Downloads/elk-log-explorer && cd ~/Downloads/elk-log-explorer && chmod +x *.sh *.command *.py && ./setup.sh && ./start.sh
```

* Automatically opens your default web browser to the dashboard.
* Press `Ctrl + C` in the terminal to stop the server anytime.

---

## 🛡️ Troubleshooting: If macOS Blocks Script Execution
If macOS displays a security warning because the zip was downloaded from Slack/Email/AirDrop, run:

```bash
xattr -dr com.apple.quarantine ~/Downloads/elk-log-explorer
```
Then re-run your chosen command above.

---

## 🛠️ Configuration & Customization

* **Configure Kibana Credentials**:
  Edit `~/Downloads/elk-log-explorer/.env` with your Kibana URL, username, and password:
  ```bash
  KIBANA_URL=https://apac-elk.anchanto.com:5601
  KIBANA_USERNAME=your-email@anchanto.com
  KIBANA_PASSWORD=your_password
  ```

* **Run on a custom port**:
  ```bash
  cd ~/Downloads/elk-log-explorer && ./start.sh 24005
  # Or: python3 server.py --port 24005
  ```

* **Uninstall macOS Application**:
  ```bash
  cd ~/Downloads/elk-log-explorer && ./uninstall_app.sh
  ```

* **Offline static export**:
  Open `report.html` directly in any web browser without running a server.

---

## 📁 Package Contents

| File | Description |
| :--- | :--- |
| **`elk-log-explorer-1.0.0.zip`** | Portable distribution archive (v1.0.0) |
| **`setup.sh`** | Automated environment verification & credential setup |
| **`install_app.sh`** | Native macOS Application installer (`ELK AI Log Explorer.app`) |
| **`start.sh`** | Terminal launcher (starts server & opens browser) |
| **`uninstall_app.sh`** | macOS App uninstaller script |
| **`Install.command`** | Double-click Finder installer script |
| **`Start.command`** | Double-click Finder launcher script |
| **`server.py`** | High-performance Python HTTP server (Python 3.9+ compatible) |
| **`kql.py`** | Pure Python KQL-to-Elasticsearch DSL translator |
| **`.env.sample`** | Environment configuration template |
| **`report.html`** | Standalone static offline HTML report & interactive template |
| **`appIcon.icns`** | High-resolution macOS application icon |

---

## 🌐 Server Endpoints & Capabilities

* **Dashboard Web UI**: `http://localhost:24004`
* **Agent Capabilities**: `GET /api/status`
* **Query API**: `POST /api/query` (`{"query": "...", "mode": "direct|ai", "agent": "claude|gemini"}`)
* **Explain API**: `POST /api/explain`
* **Standalone Static Export**: `GET /export`
