#!/usr/bin/env python3
"""Central Portal for local test servers.

Unified dashboard and management portal for all mock test servers.
Provides real-time process monitoring, start/stop/restart/reset controls, live console logs,
and direct navigation links to each mock's API root, /log viewer, and /test runner.

    python3 portal.py              # runs portal on http://127.0.0.1:23000
    python3 portal.py --port 23000 # override port
    python3 mock.py portal         # via mock.py alias

Zero external dependencies (pure Python 3 standard library).
"""

import argparse
import collections
import datetime
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, unquote, urlparse

try:
    from http.server import ThreadingHTTPServer as _Server
except ImportError:
    _Server = HTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))

# ------------------------------------------------------------------------------------------- theme

THEME_DEFAULT = collections.OrderedDict([
    ("canvas", "#020617"), ("panel", "#0b0f19"), ("surface", "#0f172a"), ("surface-2", "#1e293b"),
    ("ink", "#f8fafc"), ("ink-2", "#cbd5e1"), ("muted", "#94a3b8"),
    ("line", "#1e293b"), ("line-2", "#334155"),
    ("pass-bg", "rgba(16, 185, 129, 0.15)"), ("pass-fg", "#34d399"),
    ("fail-bg", "rgba(239, 68, 68, 0.15)"), ("fail-fg", "#f87171"),
    ("run-bg", "rgba(59, 130, 246, 0.15)"), ("run-fg", "#60a5fa"),
    ("warn-bg", "rgba(245, 158, 11, 0.15)"), ("warn-fg", "#fbbf24"),
    ("mute-bg", "rgba(51, 65, 85, 0.4)"), ("mute-fg", "#cbd5e1"),
    ("teal-bg", "rgba(20, 184, 166, 0.15)"), ("teal-fg", "#2dd4bf"),
    ("violet-bg", "rgba(168, 85, 247, 0.15)"), ("violet-fg", "#c084fc"),
    ("slate-bg", "rgba(51, 65, 85, 0.4)"), ("slate-fg", "#cbd5e1"),
    ("code-bg", "#020617"), ("hover", "#1e293b"), ("selected", "#334155"),
    ("pass-bg-2", "rgba(16, 185, 129, 0.25)"), ("fail-bg-2", "rgba(239, 68, 68, 0.25)"),
    ("header-mute", "#94a3b8"), ("dot", "#34d399"), ("dim", "#64748b"),
    ("radius", "8px"),
    ("shadow", "0 1px 3px rgba(0, 0, 0, 0.4), 0 6px 20px -4px rgba(0, 0, 0, 0.6)"),
])


def load_theme():
    theme = collections.OrderedDict(THEME_DEFAULT)
    candidate_paths = [
        os.path.join(os.path.dirname(HERE), "local-theme", "theme.json"),
        os.path.join(HERE, "theme.json"),
    ]
    for path in candidate_paths:
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as handle:
                    loaded = json.load(handle)
                theme.update({k: v for k, v in loaded.items() if not k.startswith("_")})
                break
            except Exception:
                pass
    return theme


def theme_css(theme):
    return ":root{%s}" % "".join("--%s:%s;" % (k, v) for k, v in theme.items())


# --------------------------------------------------------------------------------- process manager

def is_port_listening(host, port, timeout=0.25):
    """Tests if a TCP port is currently listening."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect((host, int(port)))
        sock.close()
        return True
    except (socket.error, ValueError):
        return False


def find_pid_on_port(port):
    """Finds PID listening on a given port (macOS/Linux)."""
    try:
        output = subprocess.check_output(["lsof", "-t", "-i", "TCP:%d" % int(port), "-sTCP:LISTEN"],
                                         stderr=subprocess.DEVNULL).decode().strip()
        if output:
            pids = [int(p) for p in output.splitlines() if p.isdigit()]
            return pids[0] if pids else None
    except Exception:
        pass
    return None


class ServerInstance:
    """Represents one managed test server integration."""

    def __init__(self, key, folder_path, config_path, config_data):
        self.key = key
        self.folder_path = folder_path
        self.config_path = config_path
        self.config = config_data
        self.name = config_data.get("name", key)
        self.host = config_data.get("host", "127.0.0.1")
        self.port = int(config_data.get("port", 8080))
        self.log_ui_path = config_data.get("log_ui_path", "/log")
        self.test_ui_path = config_data.get("test_ui_path", "/")
        self.spec = config_data.get("spec")
        self.state_dir = config_data.get("state_dir", "mock-data")
        self.log_file = config_data.get("log_file")
        self.log_format = config_data.get("log_format", "har")
        self.log_redact_headers = config_data.get("log_redact_headers", ["authorization"])
        self.unmatched_status = config_data.get("unmatched_status", 404)

        # Classification by port blocks (from README.md)
        if 23001 <= self.port < 23100:
            self.category = "Anchanto Products"
            self.category_code = "anchanto"
        elif 23101 <= self.port < 23200:
            self.category = "Third-party Partners"
            self.category_code = "partner"
        else:
            self.category = "Other Integrations"
            self.category_code = "other"

        self.spec_info = self._parse_spec_details()
        self.routes_count = max(len(self.config.get("routes", [])), self.spec_info.get("operations_count", 0))
        self.configured_routes_count = len(self.config.get("routes", []))
        self.suites = self.config.get("test_suites", [])
        self.suites_count = len(self.suites)

        # Runtime process state
        self.lock = threading.RLock()
        self.process = None
        self.pid = None
        self.started_at = None
        self.logs = collections.deque(maxlen=1000)
        self.stopping = False

    def _parse_spec_details(self):
        methods = ("get", "put", "post", "delete", "patch", "head", "options")
        info_out = {
            "file": self.spec,
            "title": self.name,
            "version": "",
            "spec_type": "None",
            "base_path": self.config.get("spec_base_path", ""),
            "operations_count": 0,
            "paths_count": 0,
        }
        if self.spec:
            spec_path = os.path.join(self.folder_path, self.spec)
            if os.path.isfile(spec_path):
                try:
                    with open(spec_path, "r", encoding="utf-8") as h:
                        data = json.load(h)
                    info = data.get("info") or {}
                    info_out["title"] = info.get("title") or self.name
                    info_out["version"] = info.get("version") or ""
                    info_out["description"] = info.get("description") or ""
                    info_out["spec_type"] = "Swagger 2.0" if "swagger" in data else ("OpenAPI 3" if "openapi" in data else "Spec JSON")
                    info_out["base_path"] = data.get("basePath") or self.config.get("spec_base_path") or ""
                    paths = data.get("paths") or {}
                    info_out["paths_count"] = len(paths)
                    ops = 0
                    for _, operations in paths.items():
                        for m in operations:
                            if m.lower() in methods:
                                ops += 1
                    info_out["operations_count"] = ops
                except Exception:
                    pass
        return info_out

    def _parse_routes(self):
        out = []
        for r in self.config.get("routes", []):
            method = r.get("method")
            if not method and r.get("methods"):
                method = "/".join(m.upper() for m in r.get("methods"))
            out.append({
                "path": r.get("path", "/"),
                "method": (method or "ANY").upper(),
                "name": r.get("name") or "default fallback",
                "rules_count": len(r.get("rules", [])),
                "has_before": bool(r.get("before")),
                "has_rules": bool(r.get("rules")),
            })
        return out

    def _parse_stores(self):
        out = []
        for name, info in (self.config.get("stores") or {}).items():
            out.append({
                "name": name,
                "type": info.get("type", "list"),
                "file": info.get("file", ""),
                "comment": info.get("_comment", ""),
            })
        return out

    def _pump_logs(self, process):
        try:
            for raw in iter(process.stdout.readline, b""):
                line = raw.decode("utf-8", "replace").rstrip("\r\n")
                with self.lock:
                    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
                    self.logs.append("[%s] %s" % (timestamp, line))
        except Exception:
            pass
        finally:
            process.wait()
            with self.lock:
                if self.process == process:
                    self.process = None
                    self.pid = None
                    self.stopping = False

    def start(self, reset=False):
        with self.lock:
            if self.is_running():
                return False, "%s is already running on http://%s:%d" % (self.name, self.host, self.port)

            mock_script = os.path.join(HERE, "mock.py")
            cmd = [sys.executable, mock_script, self.key]
            if reset:
                cmd.append("--reset")

            timestamp = datetime.datetime.now().strftime("%H:%M:%S")
            self.logs.append("[%s] Starting: %s" % (timestamp, "python3 mock.py " + self.key + (" --reset" if reset else "")))

            try:
                process = subprocess.Popen(
                    cmd,
                    cwd=HERE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    bufsize=1,
                    preexec_fn=os.setsid if hasattr(os, "setsid") else None,
                )
            except Exception as error:
                self.logs.append("[%s] Failed to launch: %s" % (timestamp, error))
                return False, str(error)

            self.process = process
            self.pid = process.pid
            self.started_at = time.time()
            self.stopping = False

            threading.Thread(target=self._pump_logs, args=(process,), daemon=True).start()

            for _ in range(20):
                time.sleep(0.1)
                if process.poll() is not None:
                    return False, "Server process exited prematurely with code %d" % process.returncode
                if is_port_listening(self.host, self.port):
                    return True, "Started %s on http://%s:%d" % (self.name, self.host, self.port)

            return True, "Server process launched (PID %d), waiting for port..." % self.pid

    def stop(self):
        with self.lock:
            if not self.is_running():
                return True, "%s is not running" % self.name

            self.stopping = True
            timestamp = datetime.datetime.now().strftime("%H:%M:%S")
            self.logs.append("[%s] Stopping server..." % timestamp)

            if self.process and self.process.poll() is None:
                try:
                    if hasattr(os, "killpg") and hasattr(os, "getpgid"):
                        os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
                    else:
                        self.process.terminate()
                except Exception:
                    try:
                        self.process.terminate()
                    except Exception:
                        pass

                for _ in range(30):
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

            external_pid = find_pid_on_port(self.port)
            if external_pid:
                try:
                    os.kill(external_pid, signal.SIGTERM)
                    time.sleep(0.5)
                    if find_pid_on_port(self.port):
                        os.kill(external_pid, signal.SIGKILL)
                except Exception:
                    pass

            self.stopping = False
            self.started_at = None
            return True, "Stopped %s" % self.name

    def restart(self, reset=False):
        self.stop()
        for _ in range(20):
            if not is_port_listening(self.host, self.port):
                break
            time.sleep(0.1)
        return self.start(reset=reset)

    def reset_data(self):
        """Resets mock stores, call logs, and test results."""
        with self.lock:
            running = self.is_running()
            if running:
                return self.restart(reset=True)
            else:
                state_dir = os.path.join(self.folder_path, self.state_dir)
                if os.path.isdir(state_dir):
                    for store_info in (self.config.get("stores") or {}).values():
                        store_file = store_info.get("file")
                        if store_file:
                            path = os.path.join(state_dir, store_file)
                            if os.path.isfile(path):
                                try:
                                    os.remove(path)
                                except Exception:
                                    pass
                    if self.log_file:
                        log_path = os.path.normpath(
                            self.log_file if os.path.isabs(self.log_file) else os.path.join(state_dir, self.log_file)
                        )
                        if os.path.isfile(log_path):
                            try:
                                os.remove(log_path)
                            except Exception:
                                pass

                results_dir = os.path.join(self.folder_path, self.config.get("test_results_dir", "test-results"))
                if os.path.isdir(results_dir):
                    shutil.rmtree(results_dir, ignore_errors=True)

                timestamp = datetime.datetime.now().strftime("%H:%M:%S")
                self.logs.append("[%s] Reset stores, call log, and test results" % timestamp)
                return True, "Reset state for %s" % self.name

    def is_running(self):
        if self.process and self.process.poll() is None:
            return True
        return is_port_listening(self.host, self.port)

    def status_dict(self):
        with self.lock:
            running = self.is_running()
            external_pid = find_pid_on_port(self.port) if running and not self.pid else None
            effective_pid = self.pid or external_pid

            uptime_sec = int(time.time() - self.started_at) if (running and self.started_at) else None
            uptime_str = None
            if uptime_sec is not None:
                if uptime_sec < 60:
                    uptime_str = "%ds" % uptime_sec
                elif uptime_sec < 3600:
                    uptime_str = "%dm %ds" % (uptime_sec // 60, uptime_sec % 60)
                else:
                    uptime_str = "%dh %dm" % (uptime_sec // 3600, (uptime_sec % 3600) // 60)

            base_url = "http://%s:%d" % (self.host, self.port)
            api_url = "%s/api" % base_url

            return {
                "key": self.key,
                "name": self.name,
                "category": self.category,
                "category_code": self.category_code,
                "host": self.host,
                "port": self.port,
                "base_url": base_url,
                "api_url": api_url,
                "log_url": "%s%s" % (base_url, self.log_ui_path),
                "test_url": base_url,
                "spec": self.spec,
                "spec_info": self.spec_info,
                "routes_count": self.routes_count,
                "configured_routes_count": self.configured_routes_count,
                "routes": self._parse_routes(),
                "suites": self.suites,
                "suites_count": self.suites_count,
                "stores": self._parse_stores(),
                "state_dir": self.state_dir,
                "log_file": self.log_file,
                "log_format": self.log_format,
                "log_redact_headers": self.log_redact_headers,
                "unmatched_status": self.unmatched_status,
                "running": running,
                "pid": effective_pid,
                "uptime": uptime_str,
                "uptime_seconds": uptime_sec,
                "stopping": self.stopping,
                "logs_count": len(self.logs),
            }


class ServerManager:
    """Discovers and manages all mock test servers."""

    def __init__(self):
        self.lock = threading.RLock()
        self.servers = collections.OrderedDict()
        self.discover()

    def discover(self):
        with self.lock:
            current_keys = set()
            for name in sorted(os.listdir(HERE)):
                folder = os.path.join(HERE, name)
                if not os.path.isdir(folder) or name.startswith((".", "_")) or name == "suite":
                    continue
                configs = sorted(f for f in os.listdir(folder) if f.endswith(".mock.json"))
                if configs:
                    config_path = os.path.join(folder, configs[0])
                    try:
                        with open(config_path, "r", encoding="utf-8") as handle:
                            config_data = json.load(handle)
                        current_keys.add(name)
                        if name not in self.servers:
                            self.servers[name] = ServerInstance(name, folder, config_path, config_data)
                    except Exception as err:
                        print("  ! Error loading %s: %s" % (config_path, err), flush=True)

            for key in list(self.servers.keys()):
                if key not in current_keys:
                    del self.servers[key]

    def get(self, name):
        with self.lock:
            return self.servers.get(name)

    def all_status(self):
        self.discover()
        with self.lock:
            return [server.status_dict() for server in self.servers.values()]

    def start_all(self):
        results = []
        with self.lock:
            for server in self.servers.values():
                if not server.is_running():
                    ok, msg = server.start()
                    results.append({"name": server.name, "ok": ok, "message": msg})
        return results

    def stop_all(self):
        results = []
        with self.lock:
            for server in self.servers.values():
                if server.is_running():
                    ok, msg = server.stop()
                    results.append({"name": server.name, "ok": ok, "message": msg})
        return results

    def restart_all(self):
        results = []
        with self.lock:
            for server in self.servers.values():
                ok, msg = server.restart()
                results.append({"name": server.name, "ok": ok, "message": msg})
        return results


PORTAL_FAVICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect width="32" height="32" rx="7" fill="#1e293b"/><path d="M7 26V13C7 8.03 11.03 4 16 4C20.97 4 25 8.03 25 13V26" fill="none" stroke="#38bdf8" stroke-width="2.5" stroke-linecap="round"/><path d="M11 26V14C11 11.24 13.24 9 16 9C18.76 9 21 11.24 21 14V26" fill="#0f172a" stroke="#4ade80" stroke-width="1.5" stroke-dasharray="2 1"/><circle cx="16" cy="15" r="2.2" fill="#4ade80"/><path d="M5 26H27" stroke="#94a3b8" stroke-width="2" stroke-linecap="round"/></svg>"""

PORTAL_FAVICON_DATA_URI = "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAzMiAzMiI+PHJlY3Qgd2lkdGg9IjMyIiBoZWlnaHQ9IjMyIiByeD0iNyIgZmlsbD0iIzFlMjkzYiIvPjxwYXRoIGQ9Ik03IDI2VjEzQzcgOC4wMyAxMS4wMyA0IDE2IDRDMjAuOTcgNCAyNSA4LjAzIDI1IDEzVjI2IiBmaWxsPSJub25lIiBzdHJva2U9IiMzOGJkZjgiIHN0cm9rZS13aWR0aD0iMi41IiBzdHJva2UtbGluZWNhcD0icm91bmQiLz48cGF0aCBkPSJNMTEgMjZWMTRDMTEgMTEuMjQgMTMuMjQgOSAxNiA5QzE4Ljc2IDkgMjEgMTEuMjQgMjEgMTRWMjYiIGZpbGw9IiMwZjE3MmEiIHN0cm9rZT0iIzRhZGU4MCIgc3Ryb2tlLXdpZHRoPSIxLjUiIHN0cm9rZS1kYXNoYXJyYXk9IjIgMSIvPjxjaXJjbGUgY3g9IjE2IiBjeT0iMTUiIHI9IjIuMiIgZmlsbD0iIzRhZGU4MCIvPjxwYXRoIGQ9Ik01IDI2SDI3IiBzdHJva2U9IiM5NGEzYjgiIHN0cm9rZS13aWR0aD0iMiIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIi8+PC9zdmc+"

# ----------------------------------------------------------------------------------------- HTML UI

PORTAL_UI_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Local Test Servers Portal</title>
  <link rel="icon" type="image/svg+xml" href=\"""" + PORTAL_FAVICON_DATA_URI + """\">
  <link rel="alternate icon" href="/favicon.ico">
  <style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;600;700&display=swap');
/*THEME*/
*{box-sizing:border-box}
body{margin:0;font:13.5px/1.6 'Inter',-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;color:var(--ink);background:var(--canvas)}
code,pre{font-family:'JetBrains Mono',"SF Mono",Menlo,Consolas,"Liberation Mono",monospace}

header{background:rgba(15,23,42,.92);backdrop-filter:blur(10px);border-bottom:1px solid var(--line-2);color:var(--ink);padding:14px 24px;display:flex;align-items:center;gap:14px;box-shadow:var(--shadow);position:sticky;top:0;z-index:20}
header h1{margin:0;font-size:15px;font-weight:700;display:flex;align-items:center;gap:10px;letter-spacing:0.02em}
header .host{color:var(--header-mute);font-size:11.5px;font-family:'JetBrains Mono',monospace}
header .meta{margin-left:auto;display:flex;align-items:center;gap:16px;font-size:12px;color:var(--header-mute);font-family:'JetBrains Mono',monospace}
header .meta a{color:var(--header-mute);text-decoration:none}
header .meta a:hover{color:var(--ink)}

.dot{display:inline-block;width:8px;height:8px;border-radius:50%;background:var(--dot);flex:none;box-shadow:0 0 6px var(--dot)}
.dot.pulse{box-shadow:0 0 0 rgba(52,211,153,0.5);animation:pulse 2s infinite}
@keyframes pulse{0%{box-shadow:0 0 0 0 rgba(52,211,153,0.7)}70%{box-shadow:0 0 0 6px rgba(52,211,153,0)}100%{box-shadow:0 0 0 0 rgba(52,211,153,0)}}
.dot-off{display:inline-block;width:8px;height:8px;border-radius:50%;background:var(--dim);flex:none}

main{max-width:88rem;margin:0 auto;padding:20px 24px;min-width:0}

/* Stats and Overview Bar */
.overview{display:flex;gap:12px;margin-bottom:16px;flex-wrap:wrap}
.metric-card{flex:1;min-width:160px;background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);padding:10px 16px;box-shadow:var(--shadow);display:flex;flex-direction:column;gap:2px}
.metric-title{font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.04em;color:var(--muted)}
.metric-val{font-size:20px;font-weight:700;font-family:"SF Mono",Menlo,monospace}
.metric-val.green{color:var(--pass-fg)}
.metric-val.slate{color:var(--ink-2)}

/* Controls & Toolbar */
.toolbar{display:flex;gap:12px;align-items:center;margin-bottom:18px;flex-wrap:wrap;background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);padding:10px 16px;box-shadow:var(--shadow)}
.toolbar input[type=search]{flex:1;min-width:240px;padding:6px 12px;border:1px solid var(--line-2);border-radius:var(--radius);font-size:13px;background:var(--surface-2);color:var(--ink)}
.toolbar input[type=search]:focus{outline:none;border-color:var(--ink-2);background:var(--surface)}
.toolbar label{font-size:12px;color:var(--ink-2);display:flex;align-items:center;gap:6px;cursor:pointer;user-select:none}
.btn-group{display:flex;gap:6px;align-items:center}

.btn{display:inline-flex;align-items:center;justify-content:center;gap:5px;padding:5px 10px;border:1px solid var(--line-2);background:var(--surface);border-radius:6px;cursor:pointer;font-size:12px;font-weight:500;color:var(--ink-2);text-align:center;text-decoration:none;box-sizing:border-box;transition:background .12s, border-color .12s, color .12s}
.btn:hover{background:var(--hover);border-color:var(--line-2);color:var(--ink)}
.btn:active{background:var(--selected)}
.btn-primary{background:var(--pass-bg);color:var(--pass-fg);border-color:rgba(31,102,38,.28)}
.btn-primary:hover{background:var(--pass-bg-2);color:var(--pass-fg)}
.btn-danger{background:var(--fail-bg);color:var(--fail-fg);border-color:rgba(173,29,25,.28)}
.btn-danger:hover{background:var(--fail-bg-2);color:var(--fail-fg)}
.btn-sm{padding:4px 8px;font-size:11.5px}

/* Fixed width action buttons to prevent layout shifting */
.btn-action-main{min-width:68px}
.btn-action-restart{min-width:76px}
.btn-action-reset{min-width:68px}
.btn-action-console{min-width:78px}

/* Section Header */
.section-title{font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);margin:20px 0 10px;display:flex;align-items:center;gap:8px}
.section-title::after{content:"";flex:1;height:1px;background:var(--line)}

/* Structured Vertical List */
.server-stack{display:flex;flex-direction:column;gap:8px}

.server-item{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);box-shadow:var(--shadow);overflow:hidden;transition:border-color .15s}
.server-item:hover{border-color:var(--line-2)}
.server-item.is-running{border-left:4px solid var(--pass-fg)}
.server-item.is-stopped{border-left:4px solid var(--dim)}

/* Crisp Single-Line Grid Summary Bar */
.server-summary{display:grid;grid-template-columns:22px minmax(240px, 1.4fr) 140px auto auto;align-items:center;gap:16px;padding:9px 16px;min-height:52px;cursor:pointer;user-select:none;background:var(--surface);transition:background .12s}
.server-summary:hover{background:var(--surface-2)}
.server-item.open .server-summary{background:var(--surface-2);border-bottom:1px solid var(--line)}

.chevron-wrap{display:flex;align-items:center;justify-content:center;width:18px;height:18px}
.chevron-svg{transition:transform .2s ease;color:var(--muted)}
.server-item.open .chevron-svg{transform:rotate(90deg)}

.server-identity{display:flex;align-items:baseline;gap:8px;min-width:0}
.server-name{font-size:13.5px;font-weight:600;color:var(--ink);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.server-key{font-family:"SF Mono",Menlo,monospace;font-size:11.5px;color:var(--muted);white-space:nowrap}

.server-status-col{display:flex;align-items:center}
.badge{display:inline-flex;align-items:center;gap:6px;padding:3px 9px;border-radius:999px;font-size:11px;font-weight:600;letter-spacing:.02em;white-space:nowrap}
.badge-running{background:var(--pass-bg);color:var(--pass-fg)}
.badge-stopped{background:var(--mute-bg);color:var(--mute-fg)}
.badge-category{background:var(--slate-bg);color:var(--slate-fg);font-size:10.5px}

/* Segmented Direct Links */
.links-group{display:inline-flex;align-items:center;background:var(--surface-2);border:1px solid var(--line);border-radius:6px;padding:2px;gap:2px}
.nav-link-btn{display:inline-flex;align-items:center;gap:4px;padding:4px 9px;border:none;background:transparent;border-radius:4px;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;font-size:11.5px;font-weight:600;color:var(--muted);text-decoration:none;cursor:pointer;transition:all .12s;white-space:nowrap}
.nav-link-btn:hover{background:var(--surface);color:var(--ink)}
.nav-link-btn.active-link{color:var(--run-fg)}
.nav-link-btn.active-link:hover{background:var(--run-bg);color:var(--run-fg)}
.nav-link-btn.disabled{opacity:.35;pointer-events:none}

/* Expanded Detail Body */
.server-details{padding:16px 20px;display:none;background:var(--surface)}
.server-item.open .server-details{display:block}

.details-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:14px;margin-bottom:16px}
.detail-box{background:var(--surface-2);border:1px solid var(--line);border-radius:var(--radius);padding:12px 14px}
.detail-box-title{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.04em;color:var(--muted);margin-bottom:8px;display:flex;align-items:center;gap:6px}

.detail-table{width:100%;border-collapse:collapse;font-size:12px}
.detail-table td{padding:3px 0;vertical-align:top}
.detail-table td:first-child{color:var(--muted);width:38%;padding-right:8px}
.detail-table td:last-child{font-family:"SF Mono",Menlo,monospace;color:var(--ink-2);word-break:break-all}

/* Sub-tables for Routes and Suites */
.sub-header{font-size:11.5px;font-weight:700;text-transform:uppercase;letter-spacing:.04em;color:var(--muted);margin:14px 0 8px;display:flex;align-items:center;gap:8px}
.routes-table-wrap{border:1px solid var(--line);border-radius:var(--radius);overflow:hidden;margin-bottom:14px}
.routes-table{width:100%;border-collapse:collapse;font-size:12px;background:var(--surface)}
.routes-table th{background:var(--surface-2);color:var(--muted);font-weight:600;text-align:left;padding:6px 12px;border-bottom:1px solid var(--line);font-size:10.5px;text-transform:uppercase;letter-spacing:.04em}
.routes-table td{padding:6px 12px;border-bottom:1px solid var(--line);vertical-align:middle}
.routes-table tr:last-child td{border-bottom:none}

.method-tag{display:inline-block;width:54px;text-align:center;padding:1px 0;border-radius:999px;font-size:10px;font-weight:700;letter-spacing:.02em}
.method-GET{background:var(--run-bg);color:var(--run-fg)}
.method-POST{background:var(--pass-bg);color:var(--pass-fg)}
.method-PUT{background:var(--warn-bg);color:var(--warn-fg)}
.method-DELETE{background:var(--fail-bg);color:var(--fail-fg)}
.method-PATCH{background:var(--teal-bg);color:var(--teal-fg)}
.method-ANY{background:var(--slate-bg);color:var(--slate-fg)}

.suite-card{background:var(--surface-2);border:1px solid var(--line);border-radius:var(--radius);padding:10px 14px;margin-bottom:8px;display:flex;align-items:center;justify-content:space-between;gap:12px}
.suite-name{font-weight:600;font-size:12.5px;color:var(--ink)}
.suite-desc{font-size:11.5px;color:var(--muted);margin-top:2px}
.suite-cmd{font-family:"SF Mono",Menlo,monospace;font-size:11px;background:var(--surface);padding:3px 8px;border-radius:4px;border:1px solid var(--line);color:var(--ink-2);margin-top:4px;display:inline-block}

/* Console Modal */
.modal-backdrop{position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(15,23,42,.45);display:none;align-items:center;justify-content:center;z-index:100;backdrop-filter:blur(2px)}
.modal-backdrop.open{display:flex}
.modal{background:var(--surface);border-radius:var(--radius);box-shadow:0 20px 25px -5px rgba(0,0,0,.2),0 10px 10px -5px rgba(0,0,0,.1);width:90%;max-width:850px;max-height:85vh;display:flex;flex-direction:column;overflow:hidden;border:1px solid var(--line-2)}
.modal-head{background:var(--ink);color:var(--surface);padding:12px 18px;display:flex;align-items:center;justify-content:space-between}
.modal-head h3{margin:0;font-size:14px;font-weight:600;display:flex;align-items:center;gap:8px}
.modal-body{padding:14px 18px;flex:1;overflow:hidden;display:flex;flex-direction:column;gap:10px}
.console-view{flex:1;background:var(--ink);color:#e2e8f0;border-radius:6px;padding:12px;font-family:"SF Mono",Menlo,monospace;font-size:12px;line-height:1.5;overflow:auto;max-height:55vh;white-space:pre-wrap;word-break:break-all}
.modal-foot{padding:10px 18px;display:flex;align-items:center;justify-content:space-between;border-top:1px solid var(--line);background:var(--surface-2)}

/* Toast Notifications */
#toasts{position:fixed;bottom:20px;right:20px;display:flex;flex-direction:column;gap:8px;z-index:110}
.toast{padding:10px 16px;background:var(--ink);color:var(--surface);border-radius:var(--radius);font-size:12px;box-shadow:var(--shadow);display:flex;align-items:center;gap:8px;animation:slideIn .2s ease-out}
.toast.success{border-left:4px solid var(--dot)}
.toast.error{border-left:4px solid var(--fail-fg)}
@keyframes slideIn{from{transform:translateX(100%);opacity:0}to{transform:translateX(0);opacity:1}}
  </style>
</head>
<body>
<header>
  <span class="dot pulse" id="headerDot"></span>
  <h1><svg style="vertical-align:-3px;margin-right:6px;flex:none" width="18" height="18" viewBox="0 0 32 32"><rect width="32" height="32" rx="7" fill="#1e293b"/><path d="M7 26V13C7 8.03 11.03 4 16 4C20.97 4 25 8.03 25 13V26" fill="none" stroke="#38bdf8" stroke-width="2.5" stroke-linecap="round"/><path d="M11 26V14C11 11.24 13.24 9 16 9C18.76 9 21 11.24 21 14V26" fill="#0f172a" stroke="#4ade80" stroke-width="1.5" stroke-dasharray="2 1"/><circle cx="16" cy="15" r="2.2" fill="#4ade80"/><path d="M5 26H27" stroke="#94a3b8" stroke-width="2" stroke-linecap="round"/></svg>Local Test Servers Portal</h1>
  <span class="host" id="portalHost">DATA_HOST</span>
  <div class="meta">
    <a href="#about" onclick="alert('Central Portal for Local Test Servers.\nManage mock servers on port 23000.\nAnchanto block: 23001+\nPartner block: 23101+')">About</a>
  </div>
</header>

<main>
  <!-- Metrics Overview -->
  <div class="overview">
    <div class="metric-card">
      <span class="metric-title">Total Test Servers</span>
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

  <!-- Global Action Toolbar -->
  <div class="toolbar">
    <input type="search" id="searchFilter" placeholder="Filter by name, port, spec, category… ( / to search )">
    
    <div class="btn-group">
      <button class="btn btn-primary" id="btnStartAll" title="Start all stopped servers">
        <svg width="11" height="11" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg> Start All
      </button>
      <button class="btn btn-danger" id="btnStopAll" title="Stop all running servers">
        <svg width="11" height="11" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="6" width="12" height="12" rx="1"/></svg> Stop All
      </button>
      <button class="btn" id="btnRestartAll" title="Restart all running servers">
        <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67"/></svg> Restart All
      </button>
    </div>

    <label><input type="checkbox" id="autoRefresh"> Auto-refresh (23s)</label>
    <button class="btn btn-sm" id="btnReloadManual">Reload</button>
  </div>

  <!-- Server Vertical Groups -->
  <div id="groupsContainer"></div>
</main>

<!-- Console Logs Modal -->
<div class="modal-backdrop" id="consoleModal">
  <div class="modal">
    <div class="modal-head">
      <h3 id="modalTitle">Console Logs</h3>
      <button class="btn btn-sm" style="color:#fff;background:transparent;border:none;font-size:16px;cursor:pointer" onclick="closeConsole()">✕</button>
    </div>
    <div class="modal-body">
      <div class="console-view" id="consoleOutput">Waiting for logs...</div>
    </div>
    <div class="modal-foot">
      <label><input type="checkbox" id="consoleAutoScroll" checked> Auto-scroll</label>
      <div class="btn-group">
        <button class="btn btn-sm" id="btnClearConsole">Clear View</button>
        <button class="btn btn-sm" onclick="closeConsole()">Close</button>
      </div>
    </div>
  </div>
</div>

<div id="toasts"></div>

<script>
let state = { servers: [], activeLogServer: null, expandedKeys: new Set(), initialBuilt: false };
let timer = null;
let logTimer = null;

function toast(message, type = 'success') {
  const container = document.getElementById('toasts');
  const el = document.createElement('div');
  el.className = 'toast ' + type;
  el.textContent = message;
  container.appendChild(el);
  setTimeout(() => { el.remove(); }, 3500);
}

function copyText(text, label = 'Copied') {
  navigator.clipboard.writeText(text).then(() => {
    toast(label + ': ' + text);
  }).catch(() => {
    prompt('Copy to clipboard:', text);
  });
}

async function api(path, method = 'GET', body = null) {
  try {
    const opts = { method, headers: { 'Content-Type': 'application/json' } };
    if (body) opts.body = JSON.stringify(body);
    const res = await fetch(path, opts);
    return await res.json();
  } catch (err) {
    toast('API error: ' + err.message, 'error');
    return null;
  }
}

async function refresh() {
  const data = await api('/api/status');
  if (!data) return;
  state.servers = data.servers || [];
  if (!state.initialBuilt) {
    buildFullDom();
    state.initialBuilt = true;
  } else {
    updateDomInPlace();
  }
}

function toggleExpand(key) {
  const item = document.getElementById('server-' + key);
  if (!item) return;
  if (state.expandedKeys.has(key)) {
    state.expandedKeys.delete(key);
    item.classList.remove('open');
  } else {
    state.expandedKeys.add(key);
    item.classList.add('open');
  }
}

function filterItems() {
  const query = (document.getElementById('searchFilter').value || '').toLowerCase().trim();
  state.servers.forEach(s => {
    const item = document.getElementById('server-' + s.key);
    if (!item) return;
    const matches = !query ||
      s.name.toLowerCase().includes(query) ||
      s.key.toLowerCase().includes(query) ||
      String(s.port).includes(query) ||
      s.category.toLowerCase().includes(query) ||
      (s.spec && s.spec.toLowerCase().includes(query));
    item.style.display = matches ? 'block' : 'none';
  });

  // Also hide empty section headers if all servers under it are hidden
  document.querySelectorAll('[data-category-section]').forEach(sec => {
    const visibleChildren = sec.querySelectorAll('.server-item:not([style*="display: none"])');
    sec.style.display = visibleChildren.length > 0 ? 'block' : 'none';
  });
}

function updateDomInPlace() {
  const total = state.servers.length;
  const running = state.servers.filter(s => s.running).length;
  const stopped = total - running;

  document.getElementById('metricTotal').textContent = total;
  document.getElementById('metricRunning').textContent = running;
  document.getElementById('metricStopped').textContent = stopped;

  state.servers.forEach(s => {
    const item = document.getElementById('server-' + s.key);
    if (!item) return;

    const isRun = s.running;
    item.className = 'server-item ' + (isRun ? 'is-running' : 'is-stopped') + (state.expandedKeys.has(s.key) ? ' open' : '');

    const statusEl = item.querySelector('.server-status-col');
    if (statusEl) {
      statusEl.innerHTML = isRun
        ? `<span class="badge badge-running"><span class="dot pulse"></span> Running${s.uptime ? ' (' + s.uptime + ')' : ''}</span>`
        : `<span class="badge badge-stopped"><span class="dot-off"></span> Stopped</span>`;
    }

    const testLink = item.querySelector('.nav-link-test');
    if (testLink) testLink.className = 'nav-link-btn nav-link-test ' + (isRun ? 'active-link' : 'disabled');
    const logLink = item.querySelector('.nav-link-log');
    if (logLink) logLink.className = 'nav-link-btn nav-link-log ' + (isRun ? 'active-link' : 'disabled');
    const apiBtn = item.querySelector('.nav-link-api-copy');
    if (apiBtn) apiBtn.className = 'nav-link-btn nav-link-api-copy ' + (isRun ? '' : 'disabled');

    const mainBtn = item.querySelector('.btn-action-main');
    if (mainBtn) {
      if (isRun) {
        mainBtn.className = 'btn btn-danger btn-sm btn-action-main';
        mainBtn.innerHTML = '<svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="6" width="12" height="12" rx="1"/></svg> Stop';
        mainBtn.title = 'Stop server';
      } else {
        mainBtn.className = 'btn btn-primary btn-sm btn-action-main';
        mainBtn.innerHTML = '<svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg> Start';
        mainBtn.title = 'Start server';
      }
    }

    const restartBtn = item.querySelector('.btn-action-restart');
    if (restartBtn) {
      restartBtn.style.opacity = isRun ? '1' : '0.45';
      restartBtn.style.pointerEvents = isRun ? 'auto' : 'none';
    }
  });

  filterItems();
}

function buildFullDom() {
  const total = state.servers.length;
  const running = state.servers.filter(s => s.running).length;
  const stopped = total - running;

  document.getElementById('metricTotal').textContent = total;
  document.getElementById('metricRunning').textContent = running;
  document.getElementById('metricStopped').textContent = stopped;

  const groups = {};
  state.servers.forEach(s => {
    if (!groups[s.category]) groups[s.category] = [];
    groups[s.category].push(s);
  });

  const container = document.getElementById('groupsContainer');
  container.innerHTML = '';

  for (const [catName, servers] of Object.entries(groups)) {
    const section = document.createElement('div');
    section.setAttribute('data-category-section', catName);
    section.innerHTML = `<div class="section-title">${escapeHtml(catName)} (${servers.length})</div>`;
    
    const stack = document.createElement('div');
    stack.className = 'server-stack';

    servers.forEach(s => {
      const isRun = s.running;
      const isOpen = state.expandedKeys.has(s.key);
      const item = document.createElement('div');
      item.id = 'server-' + s.key;
      item.className = 'server-item ' + (isRun ? 'is-running' : 'is-stopped') + (isOpen ? ' open' : '');

      const statusBadge = isRun
        ? `<span class="badge badge-running"><span class="dot pulse"></span> Running${s.uptime ? ' (' + s.uptime + ')' : ''}</span>`
        : `<span class="badge badge-stopped"><span class="dot-off"></span> Stopped</span>`;

      const routesRows = (s.routes || []).map(r => {
        const methodClass = 'method-' + (['GET','POST','PUT','DELETE','PATCH'].includes(r.method) ? r.method : 'ANY');
        return `
          <tr>
            <td style="width:64px"><span class="method-tag ${methodClass}">${escapeHtml(r.method)}</span></td>
            <td style="font-family:'SF Mono',Menlo,monospace;font-size:12px;color:var(--ink);word-break:break-all">${escapeHtml(r.path)}</td>
            <td style="color:var(--ink-2);font-size:12px">${escapeHtml(r.name)}</td>
            <td style="text-align:right;color:var(--muted);font-size:11.5px">${r.rules_count ? r.rules_count + ' rule(s)' : 'spec default'}</td>
          </tr>
        `;
      }).join('');

      const suitesHtml = (s.suites || []).map(suite => {
        const cmdStr = (suite.command || []).join(' ');
        return `
          <div class="suite-card">
            <div>
              <div class="suite-name">${escapeHtml(suite.name || suite.id)}</div>
              ${suite.description ? `<div class="suite-desc">${escapeHtml(suite.description)}</div>` : ''}
              ${cmdStr ? `<div class="suite-cmd">$ ${escapeHtml(cmdStr)}</div>` : ''}
            </div>
            <div style="text-align:right">
              ${suite.estimate ? `<span class="badge badge-category" style="margin-bottom:4px">${escapeHtml(suite.estimate)}</span><br>` : ''}
              <a class="btn btn-sm ${isRun ? 'btn-primary' : ''}" href="${s.test_url}" target="_blank" onclick="event.stopPropagation()">Run Tests &rarr;</a>
            </div>
          </div>
        `;
      }).join('') || '<div style="color:var(--muted);font-size:12px;padding:8px 0">No test suites configured in mock.json</div>';

      const storesHtml = (s.stores || []).map(st => {
        return `
          <tr>
            <td><strong>${escapeHtml(st.name)}</strong></td>
            <td><code>${escapeHtml(st.file)}</code> (${escapeHtml(st.type)})</td>
            <td style="color:var(--muted)">${escapeHtml(st.comment || '')}</td>
          </tr>
        `;
      }).join('');

      item.innerHTML = `
        <div class="server-summary" onclick="toggleExpand('${s.key}')">
          <div class="chevron-wrap">
            <svg class="chevron-svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg>
          </div>
          
          <div class="server-identity">
            <span class="server-name" title="${escapeHtml(s.name)}">${escapeHtml(s.name)}</span>
            <span class="server-key">${escapeHtml(s.key)}/</span>
          </div>

          <div class="server-status-col">
            ${statusBadge}
          </div>

          <div class="server-nav-col" onclick="event.stopPropagation()">
            <div class="links-group">
              <a class="nav-link-btn nav-link-test ${isRun ? 'active-link' : 'disabled'}" href="${s.test_url}" target="_blank" title="Test Server (Living Specs & Tests at /)">
                Test Server
              </a>
              <a class="nav-link-btn nav-link-log ${isRun ? 'active-link' : 'disabled'}" href="${s.log_url}" target="_blank" title="Call Log Viewer (/log)">
                /log
              </a>
              <button class="nav-link-btn nav-link-api-copy ${isRun ? '' : 'disabled'}" onclick="event.stopPropagation();copyText('${s.api_url}', 'API URL copied')" title="Click to copy API URL: ${s.api_url}">
                /api <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
              </button>
            </div>
          </div>

          <div class="server-actions-col" onclick="event.stopPropagation()">
            <div class="btn-group">
              <button class="btn ${isRun ? 'btn-danger' : 'btn-primary'} btn-sm btn-action-main" onclick="handleMainAction('${s.key}')" title="${isRun ? 'Stop server' : 'Start server'}">
                ${isRun
                  ? '<svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="6" width="12" height="12" rx="1"/></svg> Stop'
                  : '<svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg> Start'
                }
              </button>
              
              <button class="btn btn-sm btn-action-restart" style="opacity:${isRun ? '1' : '0.45'};pointer-events:${isRun ? 'auto' : 'none'}" onclick="restartServer('${s.key}')" title="Restart server">
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67"/></svg> Restart
              </button>

              <button class="btn btn-sm btn-action-reset" onclick="resetServer('${s.key}')" title="Clear stores, call log & results">
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/></svg> Reset
              </button>
              
              <button class="btn btn-sm btn-action-console" onclick="openConsole('${s.key}', '${escapeHtml(s.name)}')" title="View process output">
                <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/></svg> Console
              </button>
            </div>
          </div>
        </div>

        <div class="server-details">
          <div class="details-grid">
            <!-- API Document & Spec -->
            <div class="detail-box">
              <div class="detail-box-title">📄 OpenAPI / Swagger API Document</div>
              <table class="detail-table">
                <tr><td>Spec File</td><td>${escapeHtml(s.spec_info.file || 'None (pure mock config)')}</td></tr>
                <tr><td>Spec Type</td><td>${escapeHtml(s.spec_info.spec_type)} ${s.spec_info.version ? '(' + escapeHtml(s.spec_info.version) + ')' : ''}</td></tr>
                <tr><td>Base Path</td><td>${escapeHtml(s.spec_info.base_path || '/')}</td></tr>
                <tr><td>Total Operations</td><td><strong>${s.routes_count}</strong> documented operations (${s.configured_routes_count} configured rules)</td></tr>
                <tr><td>Unmatched Status</td><td><code>${s.unmatched_status}</code></td></tr>
              </table>
            </div>

            <!-- Test Suites & Automation -->
            <div class="detail-box">
              <div class="detail-box-title">🧪 Test Suites & Runner</div>
              <table class="detail-table">
                <tr><td>Suites Count</td><td><strong>${s.suites_count}</strong> suite(s) runnable</td></tr>
                <tr><td>Results Directory</td><td><code>${escapeHtml(s.key)}/test-results/</code></td></tr>
                <tr><td>Suite Runner URL</td><td><a href="${s.test_url}" target="_blank" style="color:inherit;text-decoration:underline">${s.test_url}</a></td></tr>
              </table>
            </div>

            <!-- Call Log & State Directory -->
            <div class="detail-box">
              <div class="detail-box-title">💾 Storage, State & Call Log</div>
              <table class="detail-table">
                <tr><td>State Directory</td><td><code>${escapeHtml(s.key)}/${escapeHtml(s.state_dir)}/</code></td></tr>
                <tr><td>Call Log File</td><td><code>${escapeHtml(s.log_file || 'disabled')}</code> (${s.log_format})</td></tr>
                <tr><td>Log Viewer URL</td><td><a href="${s.log_url}" target="_blank" style="color:inherit;text-decoration:underline">${s.log_url}</a></td></tr>
                <tr><td>Redact Headers</td><td><code>${(s.log_redact_headers || []).join(', ')}</code></td></tr>
              </table>
            </div>
          </div>

          <!-- Test Suites Detail -->
          <div class="sub-header">🧪 Runnable Test Suites (${s.suites_count})</div>
          ${suitesHtml}

          <!-- Configured Routes Detail -->
          ${(s.routes && s.routes.length) ? `
            <div class="sub-header" style="margin-top:16px">🛣️ Configured Mock Routes (${s.routes.length})</div>
            <div class="routes-table-wrap">
              <table class="routes-table">
                <thead>
                  <tr>
                    <th>Method</th>
                    <th>Path</th>
                    <th>Route Name / Fallback Description</th>
                    <th style="text-align:right">Rules</th>
                  </tr>
                </thead>
                <tbody>
                  ${routesRows}
                </tbody>
              </table>
            </div>
          ` : ''}

          <!-- Stores Detail -->
          ${(s.stores && s.stores.length) ? `
            <div class="sub-header" style="margin-top:16px">📦 Mock Data Stores (${s.stores.length})</div>
            <div class="routes-table-wrap">
              <table class="routes-table">
                <thead>
                  <tr>
                    <th style="width:140px">Store Name</th>
                    <th style="width:220px">File & Type</th>
                    <th>Description / Usage</th>
                  </tr>
                </thead>
                <tbody>
                  ${storesHtml}
                </tbody>
              </table>
            </div>
          ` : ''}
        </div>
      `;

      stack.appendChild(item);
    });

    section.appendChild(stack);
    container.appendChild(section);
  }

  filterItems();
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function handleMainAction(name) {
  const s = state.servers.find(x => x.key === name);
  if (s && s.running) {
    stopServer(name);
  } else {
    startServer(name);
  }
}

async function startServer(name) {
  toast(`Starting ${name}...`);
  const res = await api(`/api/server/${name}/start`, 'POST');
  if (res && res.ok) {
    toast(res.message || `Started ${name}`, 'success');
  } else {
    toast((res && res.message) || `Failed to start ${name}`, 'error');
  }
  refresh();
}

async function stopServer(name) {
  toast(`Stopping ${name}...`);
  const res = await api(`/api/server/${name}/stop`, 'POST');
  if (res && res.ok) {
    toast(res.message || `Stopped ${name}`, 'success');
  } else {
    toast((res && res.message) || `Failed to stop ${name}`, 'error');
  }
  refresh();
}

async function restartServer(name) {
  toast(`Restarting ${name}...`);
  const res = await api(`/api/server/${name}/restart`, 'POST');
  if (res && res.ok) {
    toast(res.message || `Restarted ${name}`, 'success');
  } else {
    toast((res && res.message) || `Failed to restart ${name}`, 'error');
  }
  refresh();
}

async function resetServer(name) {
  if (!confirm(`Reset data for ${name}? (Clears stores, logs, and test results)`)) return;
  toast(`Resetting data for ${name}...`);
  const res = await api(`/api/server/${name}/reset`, 'POST');
  if (res && res.ok) {
    toast(res.message || `Reset ${name}`, 'success');
  } else {
    toast((res && res.message) || `Failed to reset ${name}`, 'error');
  }
  refresh();
}

function openConsole(key, name) {
  state.activeLogServer = key;
  document.getElementById('modalTitle').textContent = `Console: ${name} (${key})`;
  document.getElementById('consoleModal').classList.add('open');
  fetchLogs();
  if (logTimer) clearInterval(logTimer);
  logTimer = setInterval(fetchLogs, 1500);
}

function closeConsole() {
  document.getElementById('consoleModal').classList.remove('open');
  state.activeLogServer = null;
  if (logTimer) clearInterval(logTimer);
}

async function fetchLogs() {
  if (!state.activeLogServer) return;
  const res = await api(`/api/server/${state.activeLogServer}/logs`);
  if (res && res.logs) {
    const el = document.getElementById('consoleOutput');
    el.textContent = res.logs.join('\\n') || '(no console output captured yet)';
    if (document.getElementById('consoleAutoScroll').checked) {
      el.scrollTop = el.scrollHeight;
    }
  }
}

document.getElementById('btnClearConsole').addEventListener('click', () => {
  document.getElementById('consoleOutput').textContent = '';
});

document.getElementById('btnStartAll').addEventListener('click', async () => {
  toast('Starting all test servers...');
  await api('/api/all/start', 'POST');
  setTimeout(refresh, 1000);
});

document.getElementById('btnStopAll').addEventListener('click', async () => {
  toast('Stopping all test servers...');
  await api('/api/all/stop', 'POST');
  setTimeout(refresh, 500);
});

document.getElementById('btnRestartAll').addEventListener('click', async () => {
  toast('Restarting all test servers...');
  await api('/api/all/restart', 'POST');
  setTimeout(refresh, 1200);
});

document.getElementById('searchFilter').addEventListener('input', filterItems);

document.getElementById('btnReloadManual').addEventListener('click', () => {
  refresh();
  toast('Refreshed server statuses', 'success');
});

function setupTimer() {
  if (timer) clearInterval(timer);
  if (document.getElementById('autoRefresh').checked) {
    timer = setInterval(refresh, 23000);
  }
}

document.getElementById('autoRefresh').addEventListener('change', setupTimer);

window.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') closeConsole();
  if (e.key === '/' && document.activeElement !== document.getElementById('searchFilter')) {
    e.preventDefault();
    document.getElementById('searchFilter').focus();
  }
});

refresh();
setupTimer();
</script>
</body>
</html>
"""


# --------------------------------------------------------------------------------- HTTP handler

def make_portal_handler(manager, host, port, style=""):
    portal_host_str = "http://%s:%d" % (host, port)

    class PortalHandler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def _send_raw(self, status, payload, content_type):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(payload)

        def _send_json(self, status, data):
            payload = json.dumps(data).encode("utf-8")
            self._send_raw(status, payload, "application/json; charset=utf-8")

        def do_OPTIONS(self):
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()

        def do_GET(self):
            parsed = urlparse(self.path)
            path = parsed.path.rstrip("/")

            if path == "/favicon.ico":
                self._send_raw(200, PORTAL_FAVICON_SVG.encode("utf-8"), "image/svg+xml")
                return

            if path == "" or path == "/index.html":
                page = (PORTAL_UI_HTML.replace("/*THEME*/", style)
                                      .replace("DATA_HOST", portal_host_str))
                self._send_raw(200, page.encode("utf-8"), "text/html; charset=utf-8")
                return

            if path == "/api/status":
                statuses = manager.all_status()
                self._send_json(200, {"servers": statuses, "portal_host": portal_host_str})
                return

            match_logs = re.match(r"^/api/server/([A-Za-z0-9_.-]+)/logs$", path)
            if match_logs:
                key = match_logs.group(1)
                server = manager.get(key)
                if not server:
                    self._send_json(404, {"ok": False, "message": "Server %s not found" % key})
                    return
                with server.lock:
                    self._send_json(200, {"ok": True, "logs": list(server.logs)})
                return

            self._send_json(404, {"ok": False, "message": "Not Found"})

        def do_POST(self):
            parsed = urlparse(self.path)
            path = parsed.path.rstrip("/")

            if path == "/api/all/start":
                results = manager.start_all()
                self._send_json(200, {"ok": True, "results": results})
                return

            if path == "/api/all/stop":
                results = manager.stop_all()
                self._send_json(200, {"ok": True, "results": results})
                return

            if path == "/api/all/restart":
                results = manager.restart_all()
                self._send_json(200, {"ok": True, "results": results})
                return

            match_action = re.match(r"^/api/server/([A-Za-z0-9_.-]+)/(start|stop|restart|reset)$", path)
            if match_action:
                key, action = match_action.groups()
                server = manager.get(key)
                if not server:
                    self._send_json(404, {"ok": False, "message": "Server %s not found" % key})
                    return

                if action == "start":
                    reset_flag = "reset" in parse_qs(parsed.query)
                    ok, msg = server.start(reset=reset_flag)
                    self._send_json(200 if ok else 400, {"ok": ok, "message": msg})
                    return

                if action == "stop":
                    ok, msg = server.stop()
                    self._send_json(200 if ok else 400, {"ok": ok, "message": msg})
                    return

                if action == "restart":
                    reset_flag = "reset" in parse_qs(parsed.query)
                    ok, msg = server.restart(reset=reset_flag)
                    self._send_json(200 if ok else 400, {"ok": ok, "message": msg})
                    return

                if action == "reset":
                    ok, msg = server.reset_data()
                    self._send_json(200 if ok else 400, {"ok": ok, "message": msg})
                    return

            self._send_json(404, {"ok": False, "message": "Not Found"})

    return PortalHandler


def main():
    parser = argparse.ArgumentParser(description="Central Portal for local test servers")
    parser.add_argument("--port", type=int, default=23000, help="portal port (default 23000)")
    parser.add_argument("--host", default="127.0.0.1", help="portal host (default 127.0.0.1)")
    args = parser.parse_args()

    theme = load_theme()
    style = theme_css(theme)
    manager = ServerManager()

    server = _Server((args.host, args.port),
                     make_portal_handler(manager, args.host, args.port, style))

    print("=================================================================", flush=True)
    print(" Local Test Servers Central Portal running at:", flush=True)
    print("   http://%s:%d" % (args.host, args.port), flush=True)
    print("=================================================================", flush=True)
    print("Discovered %d test servers in %s:" % (len(manager.servers), HERE), flush=True)
    for key, s in manager.servers.items():
        print("  - %-16s http://%s:%-5d  [%s]" % (key, s.host, s.port, s.category), flush=True)
    print("", flush=True)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping portal and all spawned mock servers...", flush=True)
        manager.stop_all()
        print("Goodbye!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
