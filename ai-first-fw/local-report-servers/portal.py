#!/usr/bin/env python3
"""Central Reports Portal for Local Live Report Servers.

Unified dashboard and management portal on port 24000 to monitor, start, stop,
and restart all local report servers (Daily Report, JPluger PR Stats, etc.).

Usage:
    python3 portal.py              # runs on http://127.0.0.1:24000
    python3 portal.py --port 24000 # override port

Zero external dependencies (pure Python 3 standard library).
"""

import argparse
import collections
import datetime
import json
import os
import signal
import socket
import subprocess
import sys
import threading
import time
from http import HTTPStatus
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import parse_qs, unquote, urlparse

try:
    from http.server import ThreadingHTTPServer as _Server
except ImportError:
    _Server = HTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))

KNOWN_SERVERS = {
    "daily-report": {
        "key": "daily-report",
        "name": "Daily Work Reports",
        "description": "Live daily engineering report viewer and on-going matter aggregator",
        "port": 24001,
        "folder": "daily-report",
        "script": "server.py",
    },
    "jpluger-pr-stats": {
        "key": "jpluger-pr-stats",
        "name": "JPluger PR Stats",
        "description": "GitHub pull request backlog, review coverage, and velocity dashboard",
        "port": 24002,
        "folder": "jpluger-pr-stats",
        "script": "server.py",
    },
    "ai-skills-report": {
        "key": "ai-skills-report",
        "name": "AI Skills & Plugins Registry",
        "description": "Claude & Antigravity skills, plugins, and desktop extensions dashboard",
        "port": 24003,
        "folder": "ai-skills-report",
        "script": "server.py",
    },
    "elk-log-explorer": {
        "key": "elk-log-explorer",
        "name": "ELK AI Log Explorer",
        "description": "Interactive ELK & Kibana log explorer with Claude & AGY Gemini AI agents",
        "port": 24004,
        "folder": "elk-log-explorer",
        "script": "server.py",
    },
}


def is_port_listening(host: str, port: int, timeout: float = 0.25) -> bool:
    """Tests if a TCP port is currently listening."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect((host, int(port)))
        sock.close()
        return True
    except (socket.error, ValueError):
        return False


def find_pid_on_port(port: int) -> int | None:
    """Finds PID listening on a given port (macOS/Linux)."""
    try:
        output = subprocess.check_output(
            ["lsof", "-t", "-i", f"TCP:{int(port)}", "-sTCP:LISTEN"],
            stderr=subprocess.DEVNULL,
        ).decode().strip()
        if output:
            pids = [int(p) for p in output.splitlines() if p.isdigit()]
            return pids[0] if pids else None
    except Exception:
        pass
    return None


class ManagedReportServer:
    """Represents a single report server instance."""

    def __init__(self, key: str, name: str, description: str, port: int, folder_path: str, script_name: str = "server.py"):
        self.key = key
        self.name = name
        self.description = description
        self.port = port
        self.host = "127.0.0.1"
        self.folder_path = folder_path
        self.script_name = script_name
        self.lock = threading.RLock()
        self.process = None
        self.pid = None
        self.started_at = None

    def is_running(self) -> bool:
        if self.process and self.process.poll() is None:
            return True
        return is_port_listening(self.host, self.port)

    def start(self) -> tuple[bool, str]:
        with self.lock:
            if self.is_running():
                return False, f"{self.name} is already running on port {self.port}"

            script_path = os.path.join(self.folder_path, self.script_name)
            if not os.path.isfile(script_path):
                return False, f"Server script {script_path} not found"

            cmd = [sys.executable, script_path, "--port", str(self.port)]
            try:
                self.process = subprocess.Popen(
                    cmd,
                    cwd=self.folder_path,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    preexec_fn=os.setsid if hasattr(os, "setsid") else None,
                )
                self.pid = self.process.pid
                self.started_at = time.time()
            except Exception as e:
                return False, f"Failed to launch {self.name}: {e}"

            for _ in range(25):
                time.sleep(0.1)
                if self.process.poll() is not None:
                    return False, f"{self.name} exited prematurely with code {self.process.returncode}"
                if is_port_listening(self.host, self.port):
                    return True, f"Started {self.name} on http://localhost:{self.port}"

            return True, f"Launched {self.name} (PID {self.pid})"

    def stop(self) -> tuple[bool, str]:
        with self.lock:
            if not self.is_running():
                return True, f"{self.name} is not running"

            if self.process and self.process.poll() is None:
                try:
                    if hasattr(os, "killpg") and hasattr(os, "getpgid"):
                        os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
                    else:
                        self.process.terminate()
                except Exception:
                    pass

                for _ in range(20):
                    time.sleep(0.1)
                    if self.process.poll() is not None:
                        break
                else:
                    try:
                        if hasattr(os, "killpg") and hasattr(os, "getpgid"):
                            os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
                        else:
                            self.process.kill()
                    except Exception:
                        pass

                self.process = None
                self.pid = None

            # Check external PID listening on port
            ext_pid = find_pid_on_port(self.port)
            if ext_pid:
                try:
                    os.kill(ext_pid, signal.SIGTERM)
                    time.sleep(0.3)
                    if find_pid_on_port(self.port):
                        os.kill(ext_pid, signal.SIGKILL)
                except Exception:
                    pass

            self.started_at = None
            return True, f"Stopped {self.name}"

    def restart(self) -> tuple[bool, str]:
        self.stop()
        time.sleep(0.2)
        return self.start()

    def status_dict(self) -> dict:
        with self.lock:
            running = self.is_running()
            effective_pid = self.pid or (find_pid_on_port(self.port) if running else None)
            uptime_str = None
            if running and self.started_at:
                sec = int(time.time() - self.started_at)
                if sec < 60:
                    uptime_str = f"{sec}s"
                elif sec < 3600:
                    uptime_str = f"{sec // 60}m {sec % 60}s"
                else:
                    uptime_str = f"{sec // 3600}h {(sec % 3600) // 60}m"

            return {
                "key": self.key,
                "name": self.name,
                "description": self.description,
                "port": self.port,
                "host": self.host,
                "url": f"http://localhost:{self.port}",
                "running": running,
                "pid": effective_pid,
                "uptime": uptime_str,
            }


class ReportServerManager:
    """Manages all report servers."""

    def __init__(self):
        self.lock = threading.RLock()
        self.servers: dict[str, ManagedReportServer] = collections.OrderedDict()
        self.discover()

    def discover(self):
        with self.lock:
            # First register known servers
            for key, info in KNOWN_SERVERS.items():
                folder = os.path.join(HERE, info["folder"])
                if os.path.isdir(folder) and key not in self.servers:
                    self.servers[key] = ManagedReportServer(
                        key=key,
                        name=info["name"],
                        description=info["description"],
                        port=info["port"],
                        folder_path=folder,
                        script_name=info.get("script", "server.py"),
                    )

            # Discover any other subdirectories containing server.py
            for entry in sorted(os.listdir(HERE)):
                folder = os.path.join(HERE, entry)
                if os.path.isdir(folder) and not entry.startswith((".", "_")) and entry not in self.servers:
                    script = os.path.join(folder, "server.py")
                    if os.path.isfile(script):
                        # Extract default port or assign fallback
                        port = 24000 + len(self.servers) + 1
                        self.servers[entry] = ManagedReportServer(
                            key=entry,
                            name=entry.replace("-", " ").title(),
                            description=f"Local live report server in {entry}",
                            port=port,
                            folder_path=folder,
                        )

    def get(self, key: str) -> ManagedReportServer | None:
        with self.lock:
            return self.servers.get(key)

    def all_status(self) -> list[dict]:
        self.discover()
        with self.lock:
            return [s.status_dict() for s in self.servers.values()]

    def start_all(self) -> list[dict]:
        results = []
        with self.lock:
            for s in self.servers.values():
                if not s.is_running():
                    ok, msg = s.start()
                    results.append({"key": s.key, "name": s.name, "ok": ok, "message": msg})
        return results

    def stop_all(self) -> list[dict]:
        results = []
        with self.lock:
            for s in self.servers.values():
                if s.is_running():
                    ok, msg = s.stop()
                    results.append({"key": s.key, "name": s.name, "ok": ok, "message": msg})
        return results

    def restart_all(self) -> list[dict]:
        results = []
        with self.lock:
            for s in self.servers.values():
                ok, msg = s.restart()
                results.append({"key": s.key, "name": s.name, "ok": ok, "message": msg})
        return results


MANAGER = ReportServerManager()

FAVICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect width="32" height="32" rx="7" fill="#0f1115"/><path d="M7 26V9C7 7.34 8.34 6 10 6H22C23.66 6 25 7.34 25 9V26" fill="none" stroke="#4f8cff" stroke-width="2" stroke-linecap="round"/><path d="M11 11H21M11 16H21M11 21H17" stroke="#3fb97d" stroke-width="2" stroke-linecap="round"/><circle cx="21" cy="21" r="2.5" fill="#4f8cff"/></svg>"""

PORTAL_HTML = """<!doctype html>
<html lang="en" class="dark">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Central Reports Portal (Port 24000)</title>
  <link rel="icon" type="image/svg+xml" href="/favicon.ico">
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;600;700&display=swap');

    :root {
      --bg: #020617;
      --panel: #0f172a;
      --surface: #1e293b;
      --border: #1e293b;
      --border-hover: #334155;
      --text: #f8fafc;
      --text-sec: #cbd5e1;
      --muted: #94a3b8;
      --accent: #60a5fa;
      --accent-bg: rgba(59, 130, 246, 0.15);
      --accent-border: rgba(96, 165, 250, 0.35);
      --ok: #34d399;
      --ok-bg: rgba(16, 185, 129, 0.15);
      --ok-border: rgba(52, 211, 153, 0.35);
      --bad: #f87171;
      --bad-bg: rgba(239, 68, 68, 0.15);
      --bad-border: rgba(248, 113, 113, 0.35);
      --warn: #fbbf24;
      --warn-bg: rgba(245, 158, 11, 0.15);
      --warn-border: rgba(251, 191, 36, 0.35);
      --neutral-bg: rgba(51, 65, 85, 0.4);
      --neutral-border: rgba(100, 116, 139, 0.35);
      --radius: 8px;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      line-height: 1.6;
      font-size: 14px;
    }
    header {
      background: rgba(15, 23, 42, 0.92);
      backdrop-filter: blur(10px);
      border-bottom: 1px solid var(--border);
      padding: 14px 24px;
      display: flex;
      align-items: center;
      gap: 16px;
      position: sticky;
      top: 0;
      z-index: 10;
    }
    header h1 {
      margin: 0;
      font-size: 15px;
      font-weight: 700;
      display: flex;
      align-items: center;
      gap: 10px;
      letter-spacing: 0.02em;
    }
    .portal-badge {
      font-size: 11px;
      background: var(--surface);
      color: var(--accent);
      border: 1px solid var(--accent-border);
      padding: 2px 8px;
      border-radius: 999px;
      font-family: 'JetBrains Mono', monospace;
      font-weight: 600;
    }
    .spacer { flex: 1; }
    main {
      max-width: 960px;
      margin: 0 auto;
      padding: 24px 20px 80px;
    }
    .overview {
      display: flex;
      gap: 12px;
      margin-bottom: 20px;
      flex-wrap: wrap;
    }
    .metric-card {
      flex: 1;
      min-width: 140px;
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 14px 18px;
      display: flex;
      flex-direction: column;
      gap: 4px;
      transition: border-color 0.15s ease;
    }
    .metric-card:hover {
      border-color: var(--border-hover);
    }
    .metric-title {
      font-size: 11px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--muted);
      font-family: 'JetBrains Mono', monospace;
    }
    .metric-val {
      font-size: 24px;
      font-weight: 700;
      font-family: 'JetBrains Mono', monospace;
    }
    .metric-val.green { color: var(--ok); }
    .metric-val.slate { color: var(--text); }
    
    .toolbar {
      display: flex;
      align-items: center;
      gap: 10px;
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 12px 18px;
      margin-bottom: 20px;
      flex-wrap: wrap;
    }
    .btn-group {
      display: flex;
      gap: 8px;
      align-items: center;
    }
    .btn {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 6px;
      padding: 6px 13px;
      border-radius: 6px;
      font-size: 12px;
      font-family: 'JetBrains Mono', monospace;
      font-weight: 600;
      cursor: pointer;
      border: 1px solid var(--border-hover);
      background: var(--surface);
      color: var(--text);
      text-decoration: none;
      transition: all 0.15s ease;
    }
    .btn:hover {
      border-color: var(--accent);
      color: #fff;
    }
    .btn-primary {
      background: var(--ok-bg);
      border-color: var(--ok-border);
      color: var(--ok);
    }
    .btn-primary:hover {
      background: rgba(52, 211, 153, 0.25);
      border-color: var(--ok);
      color: #fff;
    }
    .btn-danger {
      background: var(--bad-bg);
      border-color: var(--bad-border);
      color: var(--bad);
    }
    .btn-danger:hover {
      background: rgba(248, 113, 113, 0.25);
      border-color: var(--bad);
      color: #fff;
    }
    .btn-action {
      background: var(--accent-bg);
      border-color: var(--accent-border);
      color: var(--accent);
    }
    .btn-action:hover {
      background: rgba(96, 165, 250, 0.25);
      border-color: var(--accent);
      color: #fff;
    }
    .btn-sm {
      padding: 4px 10px;
      font-size: 11.5px;
    }
    
    .server-list {
      display: flex;
      flex-direction: column;
      gap: 12px;
    }
    .server-card {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 18px 22px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      flex-wrap: wrap;
      transition: border-color 0.15s ease;
    }
    .server-card:hover {
      border-color: var(--border-hover);
    }
    .server-card.running {
      border-left: 4px solid var(--ok);
    }
    .server-card.stopped {
      border-left: 4px solid #475569;
    }
    
    .server-info {
      flex: 1;
      min-width: 260px;
    }
    .server-title-row {
      display: flex;
      align-items: center;
      gap: 10px;
      margin-bottom: 4px;
    }
    .server-name {
      font-size: 15px;
      font-weight: 600;
      color: var(--text);
    }
    .server-port-tag {
      font-family: 'JetBrains Mono', monospace;
      font-size: 11.5px;
      background: var(--surface);
      border: 1px solid var(--border-hover);
      padding: 2px 8px;
      border-radius: 4px;
      color: var(--muted);
      font-weight: 600;
    }
    .server-desc {
      font-size: 13px;
      color: var(--muted);
      margin-bottom: 8px;
    }
    .server-status-row {
      display: flex;
      align-items: center;
      gap: 12px;
      font-size: 12px;
    }
    .status-badge {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 2px 9px;
      border-radius: 999px;
      font-weight: 700;
      font-size: 11px;
      font-family: 'JetBrains Mono', monospace;
      text-transform: uppercase;
      letter-spacing: 0.02em;
    }
    .status-badge.running {
      background: var(--ok-bg);
      color: var(--ok);
      border: 1px solid var(--ok-border);
    }
    .status-badge.stopped {
      background: var(--neutral-bg);
      color: var(--text-sec);
      border: 1px solid var(--neutral-border);
    }
    .status-dot {
      width: 7px;
      height: 7px;
      border-radius: 50%;
      display: inline-block;
    }
    .status-badge.running .status-dot {
      background: var(--ok);
      box-shadow: 0 0 6px var(--ok);
    }
    .status-badge.stopped .status-dot {
      background: #64748b;
    }
    .server-meta {
      color: var(--muted);
      font-family: 'JetBrains Mono', monospace;
      font-size: 11.5px;
    }
    
    .server-controls {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
    }
    
    #toasts {
      position: fixed;
      bottom: 24px;
      right: 24px;
      z-index: 100;
      display: flex;
      flex-direction: column;
      gap: 8px;
    }
    .toast {
      background: var(--panel);
      border: 1px solid var(--border-hover);
      border-radius: 8px;
      padding: 12px 18px;
      font-size: 13px;
      box-shadow: 0 12px 32px rgba(0, 0, 0, 0.6);
      display: flex;
      align-items: center;
      gap: 8px;
      animation: toastIn 0.2s ease;
      font-family: 'JetBrains Mono', monospace;
    }
    .toast.success { border-left: 4px solid var(--ok); color: var(--text); }
    .toast.error { border-left: 4px solid var(--bad); color: #fca5a5; }
    @keyframes toastIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }

    /* Sleek Scrollbars */
    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-track { background: var(--bg); }
    ::-webkit-scrollbar-thumb { background: #334155; border-radius: 4px; }
    ::-webkit-scrollbar-thumb:hover { background: #475569; }
  </style>
</head>
<body>
<header>
  <h1>
    <svg width="20" height="20" viewBox="0 0 32 32" style="vertical-align:-3px"><rect width="32" height="32" rx="7" fill="#020617"/><path d="M7 26V9C7 7.34 8.34 6 10 6H22C23.66 6 25 7.34 25 9V26" fill="none" stroke="#60a5fa" stroke-width="2" stroke-linecap="round"/><path d="M11 11H21M11 16H21M11 21H17" stroke="#34d399" stroke-width="2" stroke-linecap="round"/><circle cx="21" cy="21" r="2.5" fill="#60a5fa"/></svg>
    Local Reports Portal
  </h1>
  <span class="portal-badge">Port 24000</span>
  <div class="spacer"></div>
  <button class="btn btn-sm" onclick="refresh()">&#8635; Refresh</button>
</header>

<main>
  <div class="overview">
    <div class="metric-card">
      <span class="metric-title">Total Report Servers</span>
      <span class="metric-val slate" id="metricTotal">0</span>
    </div>
    <div class="metric-card">
      <span class="metric-title">Running Servers</span>
      <span class="metric-val green" id="metricRunning">0</span>
    </div>
    <div class="metric-card">
      <span class="metric-title">Stopped Servers</span>
      <span class="metric-val slate" id="metricStopped">0</span>
    </div>
  </div>

  <div class="toolbar">
    <div class="btn-group">
      <button class="btn btn-primary" onclick="startAll()">▶ Start All</button>
      <button class="btn btn-danger" onclick="stopAll()">⏹ Stop All</button>
      <button class="btn" onclick="restartAll()">🔄 Restart All</button>
    </div>
    <div class="spacer"></div>
    <label style="font-size:12px;color:var(--muted);cursor:pointer;display:flex;align-items:center;gap:6px">
      <input type="checkbox" id="autoRefresh" checked> Auto-refresh (2s)
    </label>
  </div>

  <div class="server-list" id="serverContainer">
    <div style="color:var(--muted);padding:20px;text-align:center">Loading report servers...</div>
  </div>
</main>

<div id="toasts"></div>

<script>
let serversData = [];

function showToast(msg, type = 'success', duration = 3000) {
  const container = document.getElementById('toasts');
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.textContent = msg;
  container.appendChild(toast);
  setTimeout(() => { toast.remove(); }, duration);
}

async function api(path, method = 'GET') {
  try {
    const res = await fetch(path, { method });
    return await res.json();
  } catch (e) {
    showToast(`Error: ${e.message}`, 'error');
    return null;
  }
}

async function refresh() {
  const data = await api('/api/status');
  if (!data || !data.servers) return;
  serversData = data.servers;
  render();
}

function render() {
  const total = serversData.length;
  const running = serversData.filter(s => s.running).length;
  const stopped = total - running;

  document.getElementById('metricTotal').textContent = total;
  document.getElementById('metricRunning').textContent = running;
  document.getElementById('metricStopped').textContent = stopped;

  const container = document.getElementById('serverContainer');
  container.innerHTML = serversData.map(s => {
    const statusClass = s.running ? 'running' : 'stopped';
    const statusLabel = s.running ? 'Running' : 'Stopped';
    const metaInfo = s.running
      ? (s.pid ? `PID ${s.pid}` : '') + (s.uptime ? ` · Up ${s.uptime}` : '')
      : 'Offline';

    return `
      <div class="server-card ${statusClass}">
        <div class="server-info">
          <div class="server-title-row">
            <span class="server-name">${s.name}</span>
            <span class="server-port-tag">:${s.port}</span>
          </div>
          <div class="server-desc">${s.description}</div>
          <div class="server-status-row">
            <span class="status-badge ${statusClass}">
              <span class="status-dot"></span> ${statusLabel}
            </span>
            <span class="server-meta">${metaInfo}</span>
          </div>
        </div>
        <div class="server-controls">
          ${s.running
            ? `<a href="${s.url}" target="_blank" class="btn btn-action">➜ Open Dashboard</a>
               <button class="btn" onclick="actionServer('${s.key}', 'restart')">🔄 Restart</button>
               <button class="btn btn-danger" onclick="actionServer('${s.key}', 'stop')">⏹ Stop</button>`
            : `<button class="btn btn-primary" onclick="actionServer('${s.key}', 'start')">▶ Start Server</button>`
          }
        </div>
      </div>
    `;
  }).join('');
}

async function actionServer(key, act) {
  const data = await api(`/api/server/${key}/${act}`, 'POST');
  if (data && data.ok) {
    showToast(data.message || `Server ${act} successful!`, 'success');
  } else if (data) {
    showToast(data.message || `Failed to ${act} server`, 'error');
  }
  refresh();
}

async function startAll() {
  const data = await api('/api/start-all', 'POST');
  showToast('Starting all servers...', 'success');
  setTimeout(refresh, 800);
}

async function stopAll() {
  const data = await api('/api/stop-all', 'POST');
  showToast('Stopping all servers...', 'success');
  setTimeout(refresh, 600);
}

async function restartAll() {
  const data = await api('/api/restart-all', 'POST');
  showToast('Restarting all servers...', 'success');
  setTimeout(refresh, 800);
}

refresh();
setInterval(() => {
  if (document.getElementById('autoRefresh').checked) {
    refresh();
  }
}, 2000);
</script>
</body>
</html>
"""


class PortalHandler(SimpleHTTPRequestHandler):
    """HTTP Request Handler for Reports Portal."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=HERE, **kwargs)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = unquote(parsed.path)

        if path in ("/", "/index.html", "/portal", "/portal.html"):
            self._serve_portal()
        elif path == "/favicon.ico":
            self._serve_favicon()
        elif path == "/api/status":
            self._serve_status()
        elif path.startswith("/theme/"):
            theme_dir = os.path.join(os.path.dirname(HERE), "local-theme")
            rel_path = path[len("/theme/"):]
            self._serve_file(theme_dir, rel_path)
        else:
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def do_POST(self):
        parsed = urlparse(self.path)
        path = unquote(parsed.path)

        if path == "/api/start-all":
            results = MANAGER.start_all()
            self._serve_json({"ok": True, "results": results})
        elif path == "/api/stop-all":
            results = MANAGER.stop_all()
            self._serve_json({"ok": True, "results": results})
        elif path == "/api/restart-all":
            results = MANAGER.restart_all()
            self._serve_json({"ok": True, "results": results})
        elif path.startswith("/api/server/"):
            parts = path.strip("/").split("/")
            if len(parts) == 4 and parts[0] == "api" and parts[1] == "server":
                key = parts[2]
                action = parts[3]
                server = MANAGER.get(key)
                if not server:
                    self._serve_json({"ok": False, "message": f"Server {key} not found"}, status=HTTPStatus.NOT_FOUND)
                    return

                if action == "start":
                    ok, msg = server.start()
                elif action == "stop":
                    ok, msg = server.stop()
                elif action == "restart":
                    ok, msg = server.restart()
                else:
                    self._serve_json({"ok": False, "message": f"Unknown action: {action}"}, status=HTTPStatus.BAD_REQUEST)
                    return

                self._serve_json({"ok": ok, "message": msg})
                return
            self._serve_json({"ok": False, "message": "Invalid route"}, status=HTTPStatus.NOT_FOUND)
        else:
            self._serve_json({"ok": False, "message": "Not found"}, status=HTTPStatus.NOT_FOUND)

    def _serve_portal(self):
        data = PORTAL_HTML.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(data)

    def _serve_favicon(self):
        data = FAVICON_SVG.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "image/svg+xml")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "max-age=86400")
        self.end_headers()
        self.wfile.write(data)

    def _serve_status(self):
        servers = MANAGER.all_status()
        self._serve_json({"status": "ok", "portal_port": self.server.server_port, "servers": servers})

    def _serve_json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK):
        data = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(data)

    def _serve_file(self, base_dir: str, rel_path: str):
        safe_rel_path = os.path.normpath(rel_path).lstrip(os.sep)
        target_file = os.path.abspath(os.path.join(base_dir, safe_rel_path))
        if not target_file.startswith(os.path.abspath(base_dir)) or not os.path.isfile(target_file):
            self.send_error(HTTPStatus.NOT_FOUND, f"File not found: {safe_rel_path}")
            return

        import mimetypes
        mime_type, _ = mimetypes.guess_type(target_file)
        if target_file.endswith(".css"):
            mime_type = "text/css; charset=utf-8"
        elif target_file.endswith(".js"):
            mime_type = "application/javascript; charset=utf-8"
        elif target_file.endswith(".json"):
            mime_type = "application/json; charset=utf-8"
        elif not mime_type:
            mime_type = "text/plain; charset=utf-8"

        try:
            with open(target_file, "rb") as f:
                data = f.read()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", mime_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, f"Error reading file: {e}")

    def log_message(self, format, *args):
        try:
            msg = format % args
        except Exception:
            msg = " ".join(str(a) for a in args)
        sys.stderr.write(f"[{self.log_date_time_string()}] {msg}\n")


def run_portal(port: int = 24000, host: str = "127.0.0.1"):
    _Server.allow_reuse_address = True
    server_address = (host, port)
    httpd = _Server(server_address, PortalHandler)

    print("\n=======================================================")
    print("  Central Reports Portal running at:")
    print(f"  ➜  http://localhost:{port}")
    print(f"  ➜  http://127.0.0.1:{port}")
    print("-------------------------------------------------------")
    for s in MANAGER.all_status():
        print(f"  • {s['name']:<22} : Port {s['port']} ({s['url']})")
    print("=======================================================\n", flush=True)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Shutting down Central Reports Portal.")
        httpd.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Central Reports Portal")
    parser.add_argument("--port", type=int, default=24000, help="HTTP port (default: 24000)")
    parser.add_argument("--host", default="127.0.0.1", help="Host/bind address (default: 127.0.0.1)")
    args = parser.parse_args()

    run_portal(port=args.port, host=args.host)
