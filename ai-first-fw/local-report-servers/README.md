# Local Report Servers & Central Portal

Live dashboard servers generating actionable engineering reports and metric visualizations directly from local repositories and tools.

---

## 🧭 Central Reports Portal

The **Central Reports Portal** (`portal.py`) runs on **port 24000** (`http://localhost:24000`) and provides a unified dashboard to monitor, start, stop, and restart all report servers.

```bash
# Launch Central Portal
python3 portal.py
```

---

## 📊 Managed Report Servers

| Server | Port | Directory | Description |
| :--- | :--- | :--- | :--- |
| **Central Portal** | `24000` | `.` (`portal.py`) | Web portal to manage all report servers |
| **Daily Work Reports** | `24001` | [`daily-report/`](daily-report) | Live daily engineering report viewer and on-going matter aggregator |
| **JPluger PR Stats** | `24002` | [`jpluger-pr-stats/`](jpluger-pr-stats) | GitHub pull request backlog, review coverage, and velocity dashboard |
| **AI Skills & Plugins** | `24003` | [`ai-skills-report/`](ai-skills-report) | Claude & Antigravity skills, plugins, and extensions registry |
| **ELK AI Log Explorer** | `24004` | [`elk-log-explorer/`](elk-log-explorer) | Interactive ELK & Kibana log explorer with Claude & AGY Gemini AI agents |
| **Local Theme** | *Shared* | [`../local-theme/`](../local-theme) | Reusable Dark Report Theme CSS/JS toolkit & tokens |

---

## 🎨 Unified Theme (`local-theme`)

Unified design tokens, dark developer stylesheet, and visualization components shared by all test and report servers:
* **Single Token Source of Truth**: [`../local-theme/theme.json`](../local-theme/theme.json)
* **Design System & Typography**: `Inter` body font, `JetBrains Mono` badging/code font
* **Dual-Zone Zero Overlap Velocity Charts** & **Progress Tiers**: [`../local-theme/theme.js`](../local-theme/theme.js)
* **Soft Pill Status Badges**: Emerald (Pass/Run), Red (Fail/Stop), Amber (Warn), Blue (Action)

See [`../local-theme/README.md`](../local-theme/README.md) for full token specs and documentation.

---

## 🛠 Quick Start

### 1. Start the Portal
```bash
python3 portal.py
```
Open **`http://localhost:24000`** to view the status of all servers and start/stop them with one click.

### 2. Run Individual Servers
```bash
# Daily Reports Server
python3 daily-report/server.py --port 24001

# JPluger PR Stats Server
python3 jpluger-pr-stats/server.py --port 24002

# AI Skills & Plugins Registry Server
python3 ai-skills-report/server.py --port 24003

# ELK AI Log Explorer Server
python3 elk-log-explorer/server.py --port 24004
```

---

## 📦 Standalone Distribution Packages

Every server is fully packaged according to **[`SHAREABLE_SERVER_STANDARD.md`](SHAREABLE_SERVER_STANDARD.md)** with 1-click macOS `.app` installers, double-clickable terminal launchers, and distribution `.zip` archives:

| Server | Distribution Zip | Port | Launchers Included |
| :--- | :--- | :--- | :--- |
| **Daily Work Reports** | [`daily-report-1.0.0.zip`](daily-report/daily-report-1.0.0.zip) | `24001` | `Install.command`, `Start.command`, `install_app.sh` |
| **JPluger PR Stats** | [`jpluger-pr-stats-1.0.0.zip`](jpluger-pr-stats/jpluger-pr-stats-1.0.0.zip) | `24002` | `Install.command`, `Start.command`, `install_app.sh` |
| **AI Skills & Plugins** | [`ai-skills-report-1.0.0.zip`](ai-skills-report/ai-skills-report-1.0.0.zip) | `24003` | `Install.command`, `Start.command`, `install_app.sh` |
| **ELK AI Log Explorer** | [`elk-log-explorer-1.0.0.zip`](elk-log-explorer/elk-log-explorer-1.0.0.zip) | `24004` | `Install.command`, `Start.command`, `install_app.sh` |

