#!/usr/bin/env python3
"""HTTP Live Report Server for JPluger Pull Request Statistics.

Serves the interactive dashboard on a local HTTP port (default: 24002).
Supports live fetching, JSON API, and static HTML exports.

Usage:
    python3 server.py                  # runs on http://127.0.0.1:24002
    python3 server.py --port 24002     # specify port
    python3 server.py --fetch          # fetch fresh data before launching
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
from http import HTTPStatus
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse

try:
    from http.server import ThreadingHTTPServer as _Server
except ImportError:
    _Server = HTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))

def _read_version() -> str:
    try:
        with open(os.path.join(HERE, "VERSION"), "r", encoding="utf-8") as f:
            return f.read().strip() or "1.0.0"
    except Exception:
        return "1.0.0"

__version__ = _read_version()

from fetcher import check_gh_installed, fetch_all, generate_static_report, load_cached_data

DATA_LOCK = threading.Lock()


class ReportHandler(SimpleHTTPRequestHandler):
    """Custom request handler serving live report and API endpoints."""

    def __init__(self, *args, repo="Anchanto/JPluger", **kwargs):
        self.repo = repo
        super().__init__(*args, directory=HERE, **kwargs)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path in ("/", "/index.html"):
            self._serve_dashboard()
        elif path == "/favicon.ico":
            self.send_response(HTTPStatus.NO_CONTENT)
            self.end_headers()
        elif path == "/api/stats":
            self._serve_stats()
        elif path in ("/export", "/report.html"):
            self._serve_export()
        elif path == "/api/refresh":
            self._handle_refresh()
        else:
            super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/refresh":
            self._handle_refresh()
        else:
            self.send_error(HTTPStatus.NOT_FOUND, "Endpoint not found")

    def _serve_dashboard(self):
        template_file = os.path.join(HERE, "template.html")
        if not os.path.exists(template_file):
            self.send_error(HTTPStatus.NOT_FOUND, "template.html not found")
            return

        with open(template_file, "r", encoding="utf-8") as f:
            content = f.read()

        stats = load_cached_data() or {}
        json_str = json.dumps(stats)
        content = content.replace("__REPORT_DATA_JSON__", json_str)

        data = content.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.end_headers()
        self.wfile.write(data)

    def _serve_stats(self):
        stats = load_cached_data()
        if not stats:
            if check_gh_installed():
                with DATA_LOCK:
                    stats = fetch_all(self.server.repo)
            else:
                stats = {"error": "No cached data and gh CLI unavailable."}

        data = json.dumps(stats).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def _handle_refresh(self):
        if not check_gh_installed():
            self.send_response(HTTPStatus.INTERNAL_SERVER_ERROR)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "gh CLI is not installed or authenticated"}).encode("utf-8"))
            return

        try:
            with DATA_LOCK:
                stats = fetch_all(self.server.repo)
            data = json.dumps(stats).encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            self.send_response(HTTPStatus.INTERNAL_SERVER_ERROR)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))

    def _serve_export(self):
        report_path = generate_static_report()
        with open(report_path, "rb") as f:
            data = f.read()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Disposition", 'attachment; filename="jpluger-pr-report.html"')
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format, *args):
        try:
            msg = format % args
        except Exception:
            msg = " ".join(str(a) for a in args)
        sys.stderr.write(f"[{self.log_date_time_string()}] {msg}\n")


def run_server(port: int = 24002, repo: str = "Anchanto/JPluger", auto_fetch: bool = False):
    if auto_fetch or not load_cached_data():
        print(f"[*] Initializing dataset for {repo}...")
        if check_gh_installed():
            fetch_all(repo)
        else:
            print("[!] Warning: `gh` CLI not available; fallback mock data will be used.")

    server_address = ("", port)
    
    class CustomServer(_Server):
        allow_reuse_address = True
        def __init__(self, *args, **kwargs):
            self.repo = repo
            super().__init__(*args, **kwargs)

    httpd = CustomServer(server_address, ReportHandler)
    print(f"\n=======================================================")
    print(f"  JPluger Live PR Stats Server running at:")
    print(f"  ➜  http://localhost:{port}")
    print(f"  ➜  http://127.0.0.1:{port}")
    print(f"=======================================================\n")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Shutting down server.")
        httpd.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Live Report Server for JPluger PR Stats")
    parser.add_argument("--port", type=int, default=24002, help="HTTP port (default: 24002)")
    parser.add_argument("--repo", default="Anchanto/JPluger", help="GitHub repo in Owner/Repo format")
    parser.add_argument("--fetch", action="store_true", help="Fetch fresh data from GitHub on start")
    args = parser.parse_args()

    run_server(port=args.port, repo=args.repo, auto_fetch=args.fetch)
