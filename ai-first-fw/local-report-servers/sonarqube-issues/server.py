#!/usr/bin/env python3
"""HTTP Live Report Server for SonarQube Issues Explorer.

Provides live server-parity filtering, clean code taxonomy navigation,
remediation effort rollups, and local IntelliJ IDE SonarLint findings.

Usage:
    python3 server.py                  # runs on http://127.0.0.1:24006
    python3 server.py --port 24006     # specify port
    python3 server.py --fetch          # fetch fresh data before launching
    python3 server.py --export         # generate static standalone report and exit

Zero external dependencies (pure Python 3 standard library).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import threading
from http import HTTPStatus
from http.server import HTTPServer, SimpleHTTPRequestHandler
from typing import Any, Dict, List
from urllib.parse import parse_qs, urlparse

try:
    from http.server import ThreadingHTTPServer as _Server
except ImportError:
    _Server = HTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))

def find_theme_dir() -> str:
    candidates = [
        os.path.abspath(os.path.join(HERE, "..", "..", "local-theme")),
        os.path.abspath(os.path.join(HERE, "..", "local-theme")),
        os.path.abspath(os.path.join(HERE, "local-theme")),
    ]
    for c in candidates:
        if os.path.isdir(c):
            return c
    return candidates[0]

THEME_DIR = find_theme_dir()

DATA_LOCK = threading.Lock()


def _read_version() -> str:
    try:
        with open(os.path.join(HERE, "VERSION"), "r", encoding="utf-8") as f:
            return f.read().strip() or "1.0.0"
    except Exception:
        return "1.0.0"


__version__ = _read_version()

from fetcher import (
    fetch_all,
    format_effort_minutes,
    generate_static_report,
    load_cached_data,
    load_export_file,
    load_rules_cache,
    normalize_dataset,
    parse_effort_minutes,
    sync_local_findings_if_updated,
)

FAVICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect width="32" height="32" rx="7" fill="#020617"/><path d="M7 26V9C7 7.34 8.34 6 10 6H22C23.66 6 25 7.34 25 9V26" fill="none" stroke="#60a5fa" stroke-width="2" stroke-linecap="round"/><path d="M11 11H21M11 16H21M11 21H17" stroke="#34d399" stroke-width="2" stroke-linecap="round"/><circle cx="21" cy="21" r="2.5" fill="#f87171"/></svg>"""


class SonarReportHandler(SimpleHTTPRequestHandler):
    """Custom HTTP request handler serving dashboard, static assets, and filtering APIs."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=HERE, **kwargs)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path in ("/", "/index.html"):
            self._serve_dashboard()
        elif path == "/favicon.ico":
            self._serve_favicon()
        elif path.startswith("/theme/"):
            self._serve_theme_file(path)
        elif path == "/api/stats":
            self._serve_stats()
        elif path == "/api/projects":
            self._serve_projects()
        elif path == "/api/issues":
            self._serve_issues(parsed.query)
        elif path == "/api/rule":
            self._serve_rule(parsed.query)
        elif path == "/api/refresh":
            self._handle_refresh()
        elif path in ("/export", "/report.html", "/sonarqube-issues.html"):
            self._serve_export()
        else:
            super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/refresh":
            self._handle_refresh()
        elif parsed.path == "/api/import":
            self._handle_import()
        else:
            self.send_error(HTTPStatus.NOT_FOUND, "Endpoint not found")

    def _handle_import(self):
        content_length = int(self.headers.get("Content-Length", 0))
        if not content_length:
            self.send_error(HTTPStatus.BAD_REQUEST, "Missing request body")
            return
        body = self.rfile.read(content_length).decode("utf-8")
        try:
            raw_data = json.loads(body)
            normalized = normalize_dataset(raw_data)
            data_file = os.path.join(HERE, "data.json")
            with DATA_LOCK:
                with open(data_file, "w", encoding="utf-8") as f:
                    json.dump(normalized, f)
            resp = json.dumps({"success": True, "totalIssues": normalized.get("totalIssues", 0)}).encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(resp)))
            self.end_headers()
            self.wfile.write(resp)
        except Exception as e:
            self.send_error(HTTPStatus.BAD_REQUEST, f"Invalid import data: {e}")

    def _serve_favicon(self):
        data = FAVICON_SVG.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "image/svg+xml")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _serve_theme_file(self, req_path: str):
        filename = os.path.basename(req_path)
        target = os.path.join(THEME_DIR, filename)
        if os.path.isfile(target):
            ctype = "text/css" if filename.endswith(".css") else "application/javascript"
            with open(target, "rb") as f:
                content = f.read()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", f"{ctype}; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        else:
            self.send_error(HTTPStatus.NOT_FOUND, f"Theme file {filename} not found")

    def _serve_dashboard(self):
        template_file = os.path.join(HERE, "template.html")
        if not os.path.exists(template_file):
            self.send_error(HTTPStatus.NOT_FOUND, "template.html not found")
            return

        with open(template_file, "r", encoding="utf-8") as f:
            content = f.read()

        data_file = os.path.join(HERE, "data.json")
        data = None
        if os.path.isfile(data_file):
            try:
                with open(data_file, "r", encoding="utf-8") as df:
                    raw = json.load(df)
                    data = normalize_dataset(raw)
            except Exception:
                pass

        if not data:
            data = load_cached_data()
        if not data:
            with DATA_LOCK:
                data = fetch_all()

        if data:
            with DATA_LOCK:
                data, _ = sync_local_findings_if_updated(data)

        json_str = json.dumps(data)
        content = content.replace("__REPORT_DATA_JSON__", json_str)

        body = content.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.end_headers()
        self.wfile.write(body)

    def _serve_stats(self):
        data = load_cached_data()
        if not data:
            with DATA_LOCK:
                data = fetch_all()

        stats = {
            "totalIssues": data.get("totalIssues", 0),
            "serverCount": data.get("serverCount", 0),
            "localCount": data.get("localCount", 0),
            "qualityCounts": data.get("qualityCounts", {}),
            "severityCounts": data.get("severityCounts", {}),
            "statusCounts": data.get("statusCounts", {}),
            "projectsCount": len(data.get("projects", [])),
            "localMeta": data.get("localMeta", {}),
            "timestamp": data.get("timestamp"),
        }

        body = json.dumps(stats).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _serve_projects(self):
        data = load_cached_data()
        if not data:
            with DATA_LOCK:
                data = fetch_all()

        projects = data.get("projects", [])
        body = json.dumps({"projects": projects, "total": len(projects)}).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _serve_rule(self, query_string: str):
        params = parse_qs(query_string)
        rule_key = params.get("key", [""])[0]
        if not rule_key:
            self.send_error(HTTPStatus.BAD_REQUEST, "Missing 'key' query parameter")
            return

        cache = load_rules_cache()
        rule_info = cache.get(rule_key)
        if not rule_info:
            from fetcher import fetch_single_rule
            _, rule_info = fetch_single_rule(rule_key)

        body = json.dumps({"key": rule_key, "rule": rule_info}).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _serve_issues(self, query_string: str):
        data = load_cached_data()
        if not data:
            with DATA_LOCK:
                data = fetch_all()

        issues = data.get("issues", [])
        params = parse_qs(query_string)

        project = params.get("project", [""])[0]
        branch = params.get("branch", [""])[0]
        quality = params.get("quality", params.get("softwareQuality", []))
        severity = params.get("severity", params.get("impactSeverity", []))
        status = params.get("status", [])
        source = params.get("source", [""])[0]
        repo = params.get("repo", [""])[0]
        rule = params.get("rule", [])
        search = params.get("search", params.get("q", [""]))[0].strip().lower()
        group_by = params.get("groupBy", [""])[0]

        filtered = []
        for iss in issues:
            if repo and iss.get("repoPath") != repo:
                continue
            if project and iss.get("project") != project:
                continue
            if branch and branch != "all" and iss.get("branch") != branch:
                continue
            if quality and iss.get("softwareQuality") not in quality:
                continue
            if severity and iss.get("impactSeverity") not in severity:
                continue
            if status and iss.get("status") not in status:
                continue
            if source and source != "all" and iss.get("source") != source:
                continue
            if rule and iss.get("rule") not in rule:
                continue
            if search:
                fp = iss.get("filePath", "").lower()
                msg = iss.get("message", "").lower()
                rk = iss.get("rule", "").lower()
                rn = iss.get("ruleName", "").lower()
                if search not in fp and search not in msg and search not in rk and search not in rn:
                    continue
            filtered.append(iss)

        # Handle grouping
        groups = None
        if group_by in ("rule", "file", "module"):
            group_dict: Dict[str, Dict[str, Any]] = {}
            for iss in filtered:
                if group_by == "rule":
                    gkey = iss.get("rule", "Unknown")
                    gtitle = f"{gkey} — {iss.get('ruleName', gkey)}"
                elif group_by == "file":
                    gkey = iss.get("filePath", "Unknown")
                    gtitle = f"<{iss.get('module', 'general')}> {os.path.basename(gkey)}"
                else:
                    gkey = iss.get("module", "General")
                    gtitle = f"Module: {gkey}"

                if gkey not in group_dict:
                    group_dict[gkey] = {
                        "key": gkey,
                        "title": gtitle,
                        "count": 0,
                        "issues": [],
                    }
                group_dict[gkey]["count"] += 1
                group_dict[gkey]["issues"].append(iss)

            groups = sorted(group_dict.values(), key=lambda x: x["count"], reverse=True)

        result = {
            "total": len(filtered),
            "issues": filtered[:1000] if not groups else None,
            "groups": groups,
        }

        body = json.dumps(result).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _handle_refresh(self):
        try:
            with DATA_LOCK:
                data = fetch_all(force=True)
            body = json.dumps({
                "status": "ok",
                "totalIssues": data.get("totalIssues"),
                "serverCount": data.get("serverCount"),
                "localCount": data.get("localCount"),
            }).encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
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
        self.send_header("Content-Disposition", 'inline; filename="sonarqube-issues.html"')
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format, *args):
        try:
            msg = format % args
        except Exception:
            msg = " ".join(str(a) for a in args)
        sys.stderr.write(f"[{self.log_date_time_string()}] {msg}\n")


def run_server(port: int = 24006, host: str = "127.0.0.1", auto_fetch: bool = False):
    if auto_fetch or not load_cached_data():
        print("[*] Initializing SonarQube dataset...")
        with DATA_LOCK:
            fetch_all()

    server_address = (host, port)

    class CustomServer(_Server):
        allow_reuse_address = True

    try:
        httpd = CustomServer(server_address, SonarReportHandler)
    except OSError as e:
        if e.errno == 48:
            print(f"\n❌ Port {port} is already in use!")
            print(f"👉 Release it with: kill -9 $(lsof -ti :{port})")
            print(f"👉 Or specify a different port: python3 server.py --port <NEW_PORT>\n")
        else:
            print(f"❌ Failed to bind to {host}:{port}: {e}")
        sys.exit(1)

    print(f"\n=======================================================")
    print(f"  SonarQube Issues Explorer running at:")
    print(f"  ➜  http://localhost:{port}")
    print(f"  ➜  http://{host}:{port}")
    print(f"=======================================================\n")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Shutting down SonarQube Issues Server.")
        httpd.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Live Report Server for SonarQube Issues Explorer")
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "24006")), help="HTTP port (default: 24006)")
    parser.add_argument("--host", type=str, default=os.getenv("HOST", "127.0.0.1"), help="Host address (default: 127.0.0.1)")
    parser.add_argument("-f", "--file", type=str, default=None, help="Path to an existing export file (.html or .json) to load as dataset")
    parser.add_argument("--fetch", action="store_true", help="Fetch fresh data from SonarQube on start")
    parser.add_argument("--export", action="store_true", help="Generate static standalone HTML report and exit")
    args = parser.parse_args()

    if args.file:
        loaded = load_export_file(args.file)
        if loaded:
            data_file = os.path.join(HERE, "data.json")
            with open(data_file, "w", encoding="utf-8") as f:
                json.dump(loaded, f)
            print(f"✔ Loaded {loaded.get('totalIssues', 0):,} issues from export file: {args.file}")
        else:
            print(f"❌ Failed to parse export file: {args.file}")
            sys.exit(1)

    if args.export:
        p = generate_static_report()
        print(f"✔ Static standalone report generated: {p}")
        sys.exit(0)

    run_server(port=args.port, host=args.host, auto_fetch=args.fetch)
