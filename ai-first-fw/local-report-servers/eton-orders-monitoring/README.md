# 📦 Eton Orders Monitoring Dashboard

High-performance local monitoring and audit server for Eton replay and live orders, tracking the three-stage funnel, drop-offs, duplicate creations, and price push status.

---

## 🎯 Purpose & Features

- **Funnel Drop-off Tracking**:
  - **Stage 1**: `order_creation (warehouse_code=eton)`
  - **Stage 2**: `EtonWmsService.executeEtonCreateOrderApi response`
  - **Stage 3**: `EtonUtils.pushPriceDetail response`
- **Replay Audit Classification**:
  - `BESO05`: Expected replay duplicates (Order already exists in Eton WMS).
  - `DUPLICATE CREATED`: **CRITICAL ALARM** indicating a replay unexpectedly created a brand-new order in WMS!
  - `Creation Other Errors`: Execution errors returned by Eton CreateOrder API.
  - `Missing at Stage 2`: Orders pushed in Stage 1 with no Stage 2 response log (silent drop).
  - `Stage 3 Price OK` vs `Price Failed` vs `Never Priced`.
- **Quality Bar**:
  - Supports **50,000+ orders** via indexed SQLite WAL engine (`data/eton_orders.db`).
  - Strict batch size: **queries only 100 orders per request** from Kibana.
  - **Incremental high-water checkpointing**: results are persisted immediately by batch, and subsequent syncs only query what has not yet been stored.
  - Mandatory columns: `timestamp`, `orderNumber`, `wmsOrderId`, `response of creation`, `response of push price`.

---

## 🚀 1-Step Installation & Launch

Download **[`eton-orders-monitoring-1.0.0.zip`](./eton-orders-monitoring-1.0.0.zip)** into your **`~/Downloads`** folder, open **Terminal.app**, and copy & paste one of the two commands below:

---

### Option 1: Install as a macOS Application (Recommended)
Unzips, runs setup verification, and installs **`Eton Orders Monitoring.app`** directly into your **`/Applications`** folder:

```bash
unzip -o ~/Downloads/eton-orders-monitoring-1.0.0.zip -d ~/Downloads/eton-orders-monitoring && cd ~/Downloads/eton-orders-monitoring && chmod +x *.sh *.command *.py && ./setup.sh && ./install_app.sh
```

**How to open once installed:**
* **Spotlight**: Press `Cmd + Space` and type **`Eton Orders Monitoring`**.
* **Launchpad / Finder**: Click **`Eton Orders Monitoring.app`** in `/Applications`.
* **Dock**: Drag the app to your Dock for 1-click launching!

---

### Option 2: Install & Run as a Local Server (Terminal)
Unzips, runs setup verification, and starts the server on **`http://localhost:24005`**:

```bash
unzip -o ~/Downloads/eton-orders-monitoring-1.0.0.zip -d ~/Downloads/eton-orders-monitoring && cd ~/Downloads/eton-orders-monitoring && chmod +x *.sh *.command *.py && ./setup.sh && ./start.sh
```

* Automatically opens your default web browser to the dashboard.
* Press `Ctrl + C` in the terminal to stop the server anytime.

---

## 🛡️ Troubleshooting: If macOS Blocks Script Execution
If macOS displays a security warning because the zip was downloaded from Slack/Email/AirDrop, run:

```bash
xattr -dr com.apple.quarantine ~/Downloads/eton-orders-monitoring
```
Then re-run your chosen command above.

---

## 🛠️ Configuration & Customization

* **Run on a custom port**:
  ```bash
  cd ~/Downloads/eton-orders-monitoring && ./start.sh <NEW_PORT>
  # Or: python3 server.py --port <NEW_PORT>
  ```

* **Uninstall macOS Application**:
  ```bash
  cd ~/Downloads/eton-orders-monitoring && ./uninstall_app.sh
  ```

* **Offline static export**:
  Open `eton-orders-monitoring.html` directly in any web browser without running a server.

---

## 📁 Package Contents

| File | Description |
| :--- | :--- |
| **`eton-orders-monitoring-1.0.0.zip`** | Portable distribution archive (v1.0.0) |
| **`setup.sh`** | Automated environment verification & setup |
| **`install_app.sh`** | Native macOS Application installer (`Eton Orders Monitoring.app`) |
| **`start.sh`** | Terminal launcher (starts server on port 24005 & opens browser) |
| **`uninstall_app.sh`** | macOS App uninstaller script |
| **`Install.command`** | Double-click Finder installer script |
| **`Start.command`** | Double-click Finder launcher script |
| **`server.py`** | High-performance Python HTTP & SQLite server (port 24005) |
| **`report.html`** | Interactive dark-theme dashboard UI template |
| **`eton-orders-monitoring.html`** | Standalone static offline HTML report |
| **`appIcon.icns`** | High-resolution macOS application icon |
| **`theme.css` / `theme.js`** | Unified dark theme tokens from `local-theme` |

---

## 🌐 Server Endpoints & Capabilities

* **Dashboard Web UI**: `http://localhost:24005`
* **Stats API**: `GET /api/stats`
* **Orders List API (Paginated & Filterable)**: `GET /api/orders?page=1&limit=50&search=&filter=`
* **Single Order Timeline & Detail**: `GET /api/order?id=<orderNumber>`
* **Trigger Batch Sync (100 per query)**: `POST /api/sync`
* **Cancel/Stop Sync**: `POST /api/sync/stop`
* **Sync Engine Live Status**: `GET /api/sync/status`
* **Export Filtered CSV**: `GET /api/export/csv`
* **Funnel JSON**: `GET /api/funnel`
* **Standalone Static Export**: `GET /export`
