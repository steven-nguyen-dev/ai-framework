#!/usr/bin/env python3
"""HTTP Live Report Server for AI Skills & Plugins Registry.

Serves the interactive skills and plugins dashboard on a local HTTP port (default: 24003).
Scans and discovers all Claude and Antigravity skills, plugins, and desktop extensions.
Supports real-time installation and uninstallation management across target surfaces.

Usage:
    python3 server.py                  # runs on http://127.0.0.1:24003
    python3 server.py --port 24003     # specify port
    python3 server.py --export         # export standalone report HTML
"""

from __future__ import annotations

import argparse
import importlib
import json
import mimetypes
import os
import subprocess
import sys
import threading
from datetime import datetime
from http import HTTPStatus
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import parse_qs, unquote, urlparse

try:
    from http.server import ThreadingHTTPServer as _Server
except ImportError:
    _Server = HTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
THEME_DIR = os.path.abspath(os.path.join(HERE, "../../local-theme"))

def _read_version() -> str:
    try:
        with open(os.path.join(HERE, "VERSION"), "r", encoding="utf-8") as f:
            return f.read().strip() or "1.0.0"
    except Exception:
        return "1.0.0"

__version__ = _read_version()

import scanner
from scanner import (
    add_marketplace,
    clean_legacy_symlinks,
    pull_updates_from_marketplaces,
    remove_marketplace,
    scan_all,
    sync_and_update_all_marketplaces,
    toggle_mcp_target,
    uninstall_plugin_item,
)

DATA_LOCK = threading.Lock()
CACHED_DATA: dict | None = None
LAST_SCAN_TIME: str | None = None

FAVICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect width="32" height="32" rx="7" fill="#0f1115"/><path d="M7 26V9C7 7.34 8.34 6 10 6H22C23.66 6 25 7.34 25 9V26" fill="none" stroke="#60a5fa" stroke-width="2" stroke-linecap="round"/><path d="M11 11H21M11 16H21M11 21H17" stroke="#34d399" stroke-width="2" stroke-linecap="round"/><circle cx="21" cy="21" r="2.5" fill="#c084fc"/></svg>"""


def get_data(force_refresh: bool = False) -> dict:
    """Returns scanned data, caching in memory unless force_refresh is True."""
    global CACHED_DATA, LAST_SCAN_TIME
    with DATA_LOCK:
        if CACHED_DATA is None or force_refresh:
            try:
                importlib.reload(scanner)
            except Exception:
                pass
            CACHED_DATA = scanner.scan_all()
            LAST_SCAN_TIME = CACHED_DATA.get("scan_time")
        return CACHED_DATA


def generate_static_report(force_refresh: bool = False) -> str:
    """Renders report.html with current scan data and theme styles inlined for universal portability."""
    template_path = os.path.join(HERE, "report.html")
    if not os.path.isfile(template_path):
        return "<html><body><h1>report.html not found</h1></body></html>"

    with open(template_path, "r", encoding="utf-8") as f:
        html = f.read()

    # Read theme.css if available to inline for 100% offline portability on any machine
    theme_css_file = os.path.join(THEME_DIR, "theme.css")
    if os.path.isfile(theme_css_file):
        try:
            with open(theme_css_file, "r", encoding="utf-8") as f:
                theme_css = f.read()
            html = html.replace('<link rel="stylesheet" href="/theme/theme.css">', f'<style id="inlined-theme">\n{theme_css}\n</style>')
        except Exception:
            pass

    data = get_data(force_refresh=force_refresh)
    data_json = json.dumps(data)
    return html.replace("__REPORT_DATA_JSON__", data_json)


class SkillsReportHandler(SimpleHTTPRequestHandler):
    """Custom request handler serving dashboard, theme, API, and management endpoints."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=HERE, **kwargs)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = unquote(parsed.path)

        if path in ("/", "/index.html", "/report.html"):
            self._serve_dashboard()
        elif path == "/favicon.ico":
            self._serve_favicon()
        elif path == "/api/status":
            self._serve_status()
        elif path in ("/api/skills", "/api/data"):
            self._serve_skills_data()
        elif path == "/api/refresh":
            self._handle_refresh()
        elif path == "/export":
            self._serve_export()
        elif path.startswith("/theme/"):
            rel_path = path[len("/theme/"):]
            self._serve_file_from_dir(THEME_DIR, rel_path)
        else:
            super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = unquote(parsed.path)

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"
        try:
            payload = json.loads(body) if body.strip().startswith("{") else {}
        except Exception:
            payload = {}

        if path == "/api/refresh":
            self._handle_refresh()
        elif path in ("/api/pull_updates", "/api/marketplace/pull_updates", "/api/sync", "/api/marketplace/sync_down", "/api/skills/sync_down"):
            self._handle_pull_updates()
        elif path == "/api/plugin/uninstall":
            self._handle_uninstall_plugin(payload)
        elif path == "/api/marketplace/add":
            self._handle_add_marketplace(payload)
        elif path == "/api/marketplace/remove":
            self._handle_remove_marketplace(payload)
        elif path == "/api/mcp/toggle":
            self._handle_toggle_mcp(payload)
        else:
            self.send_error(HTTPStatus.NOT_FOUND, "Endpoint not found")

    def do_HEAD(self):
        parsed = urlparse(self.path)
        path = unquote(parsed.path)

        if path in ("/", "/index.html", "/report.html", "/api/status", "/api/skills"):
            self.send_response(HTTPStatus.OK)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
        else:
            super().do_HEAD()

    def _serve_dashboard(self):
        content = generate_static_report(force_refresh=True)
        data = content.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
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
        data = {
            "status": "ok",
            "server": "ai-skills-report",
            "port": getattr(self.server, "server_port", 24003),
            "last_scan_time": LAST_SCAN_TIME,
        }
        self._send_json(data)

    def _serve_skills_data(self):
        data = get_data()
        self._send_json(data)

    def _handle_refresh(self):
        data = get_data(force_refresh=True)
        self._send_json(data)

    def _handle_pull_updates(self):
        pull_res = pull_updates_from_marketplaces()
        data = get_data(force_refresh=True)
        self._send_json({
            "success": pull_res.get("success", True),
            "pull_details": pull_res,
            "sync_details": pull_res,
            "data": data,
        })

    def _handle_uninstall_plugin(self, payload: dict):
        plugin_id = payload.get("plugin_id")
        install_path = payload.get("install_path")
        if not plugin_id or not install_path:
            self._send_json({"success": False, "message": "Missing 'plugin_id' or 'install_path'"}, status=HTTPStatus.BAD_REQUEST)
            return

        res = uninstall_plugin_item(plugin_id, install_path)
        get_data(force_refresh=True)
        self._send_json(res)

    def _handle_add_marketplace(self, payload: dict):
        source = payload.get("source", "").strip()
        repo = payload.get("repo", "").strip()
        name = payload.get("name", "").strip()
        if not source and not repo:
            self._send_json({"success": False, "message": "Source (GitHub repo or directory path) is required."}, status=HTTPStatus.BAD_REQUEST)
            return

        res = add_marketplace(source=source or repo, repo=repo, name=name)
        get_data(force_refresh=True)
        self._send_json(res)

    def _handle_remove_marketplace(self, payload: dict):
        name = payload.get("name", "").strip()
        if not name:
            self._send_json({"success": False, "message": "Marketplace name is required."}, status=HTTPStatus.BAD_REQUEST)
            return

        res = remove_marketplace(name=name)
        get_data(force_refresh=True)
        self._send_json(res)

    def _handle_toggle_mcp(self, payload: dict):
        server_id = payload.get("server_id", "").strip()
        target = payload.get("target", "").strip()
        enable = bool(payload.get("enable", True))

        if not server_id or not target:
            self._send_json({"success": False, "message": "server_id and target are required"}, status=HTTPStatus.BAD_REQUEST)
            return

        try:
            res = toggle_mcp_target(server_id, target, enable)
            get_data(force_refresh=True)
            self._send_json(res)
        except Exception as e:
            self._send_json({"success": False, "message": str(e)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)

    def _serve_export(self):
        content = generate_static_report()
        data = content.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Disposition", 'attachment; filename="ai-skills-report.html"')
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_json(self, data: dict, status: HTTPStatus = HTTPStatus.OK):
        res = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(res)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(res)

    def _serve_file_from_dir(self, base_dir: str, rel_path: str):
        full_path = os.path.abspath(os.path.join(base_dir, rel_path.lstrip("/")))
        if not full_path.startswith(base_dir) or not os.path.isfile(full_path):
            self.send_error(HTTPStatus.NOT_FOUND, f"File {rel_path} not found")
            return

        mime_type, _ = mimetypes.guess_type(full_path)
        mime_type = mime_type or "application/octet-stream"

        try:
            with open(full_path, "rb") as f:
                content = f.read()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", mime_type)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "max-age=3600")
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, f"Error reading file: {e}")


def main():
    parser = argparse.ArgumentParser(description="Live Report Server for AI Skills & Plugins Registry")
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "24003")), help="Port to listen on (default: 24003 or $PORT)")
    parser.add_argument("--host", type=str, default=os.getenv("HOST", "127.0.0.1"), help="Host address (default: 127.0.0.1 or $HOST)")
    parser.add_argument("--export", action="store_true", help="Generate static standalone HTML report and exit")
    parser.add_argument("--pull-updates", action="store_true", help="Pull down latest updates from registered public marketplaces and exit")
    args = parser.parse_args()

    if args.pull_updates:
        print("🔄 Pulling latest updates from registered public marketplaces...")
        res = pull_updates_from_marketplaces()
        print("\n" + "=" * 60)
        print("📊 Public Marketplace Pull Summary:")
        print(f"  • Status: {'✔ SUCCESS' if res.get('success') else '❌ FAILED'}")
        if "marketplaces_updated" in res:
            mps = res.get("marketplaces_updated", [])
            print(f"  • Public Marketplaces Pulled: {len(mps)}")
            for mp in mps:
                print(f"      - {mp}")
        if "plugins_updated" in res:
            plugins = res.get("plugins_updated", [])
            print(f"  • Plugins Updated: {len(plugins)}")
            for p in plugins:
                print(f"      - {p.get('plugin_id')}: v{p.get('old_version')} ➔ v{p.get('new_version')} ({p.get('skills_count')} skills)")
        if "cowork_sessions_synced" in res:
            print(f"  • Claude Cowork Sessions Updated: {res.get('cowork_sessions_synced')}")
        if "antigravity_plugins_synced" in res:
            print(f"  • Antigravity Plugins Updated: {res.get('antigravity_plugins_synced')}")
        if res.get("errors"):
            print("  • Errors encountered:")
            for err in res["errors"]:
                print(f"      ⚠️ {err}")
        print("=" * 60)
        print("✔ Pull updates complete (0 pushes performed).\n")
        return

    if args.export:
        html = generate_static_report()
        out_file = os.path.join(HERE, "ai-skills-report.html")
        with open(out_file, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"Exported static report to {out_file}")
        return

    # Warm up cache
    get_data()

    server_address = (args.host, args.port)
    try:
        httpd = _Server(server_address, SkillsReportHandler)
    except OSError as e:
        if "Address already in use" in str(e):
            print(f"⚠️  Port {args.port} is already in use by another process.")
            print(f"    Run with --port <another_port> or terminate the existing process:")
            print(f"    kill -9 $(lsof -ti :{args.port})")
            sys.exit(1)
        raise

    print(f"AI Skills & Plugins Report Server running at http://{args.host}:{args.port}/")
    print("Press Ctrl+C to stop.")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        httpd.server_close()


if __name__ == "__main__":
    main()
