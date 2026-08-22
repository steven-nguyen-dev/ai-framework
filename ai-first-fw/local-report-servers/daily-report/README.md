# Daily Work Report Live Server

A lightweight, zero-dependency local report server and live viewer for daily engineering work reports and on-going matter tracking.

---

## 🚀 Features

- **Port 24001 Standard**: Dedicated report server running cleanly alongside `portal.py` (23000) and `jpluger-pr-stats` (24000).
- **Zero Configuration**: Automatically discovers `daily-reports/` and `matters/` in the project workspace without copying or modifying original markdown files.
- **Dynamic On-going Matters**: Live aggregation of matter states directly from `matters/<slug>/README.md` at request time (one home per activity).
- **Interactive Carry-Forward Age Visuals**: Real-time visualization of aging open actions and debt metrics.
- **Member Actions**: Verbatim daily pod action tracking.
- **Zero Python Dependencies**: Powered entirely by the Python 3 standard library (`http.server`, `json`, `argparse`, `pathlib`).

---

## 🛠 Quick Start

### 1. Launch the Server
```bash
python3 server.py
```
Open **`http://localhost:24001`** in your browser.

### 2. Custom Port or Workspace
```bash
python3 server.py --port 24001 --workspace /Users/nguyennguyen.anchanto/Projects/project-workspace
```

### 3. Using Helper Script
```bash
./serve-daily-report.sh
```

---

## 📡 API & Routes

| Route | Method | Description |
| :--- | :--- | :--- |
| `/` | `GET` | Main interactive daily report dashboard (`today-report.html`) |
| `/daily-reports/<file>` | `GET` | Streams specific daily report markdown from original directory |
| `/matters/<path>` | `GET` | Streams matter markdown files, diagrams, and assets live |
| `/api/status` | `GET` | Health check & configured paths JSON |
| `/api/reports` | `GET` | Lists all discovered daily report files and dates in JSON |
| `/favicon.ico` | `GET` | SVG favicon |

---

## 📋 Requirements
- macOS / Linux with **Python 3.10+** (Standard Library only)
