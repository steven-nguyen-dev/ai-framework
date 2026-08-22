#!/usr/bin/env python3
"""HTTP Live Report Server for Daily Work Reports.

Serves the interactive daily report dashboard on a local HTTP port (default: 24001).
Directly serves markdown report sources and matter files from their original workspace folder.

Usage:
    python3 server.py                         # runs on http://127.0.0.1:24001
    python3 server.py --port 24001            # specify port
    python3 server.py --workspace /path/to/ws # specify project workspace
"""

import argparse
import json
import mimetypes
import os
import re
import sys
import threading
from http import HTTPStatus
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

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


def find_default_workspace() -> str:
    """Finds the default project workspace directory dynamically across any machine."""
    candidates = [
        os.getenv("WORKSPACE"),
        os.getenv("PROJECT_WORKSPACE"),
        os.path.abspath(os.path.join(HERE, "../../../project-workspace")),
        os.path.abspath(os.path.join(Path.home(), "Projects/project-workspace")),
        os.path.abspath(os.path.join(Path.home(), "Projects")),
        os.path.abspath(os.path.join(HERE, "../../..")),
        os.getcwd(),
    ]
    for ws in candidates:
        if ws and os.path.isdir(ws) and os.path.isdir(os.path.join(ws, "daily-reports")):
            return ws
    for ws in candidates:
        if ws and os.path.isdir(ws):
            return ws
    return os.path.abspath(os.path.join(Path.home(), "Projects"))


FAVICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect width="32" height="32" rx="7" fill="#0f1115"/><path d="M7 26V9C7 7.34 8.34 6 10 6H22C23.66 6 25 7.34 25 9V26" fill="none" stroke="#4f8cff" stroke-width="2" stroke-linecap="round"/><path d="M11 11H21M11 16H21M11 21H17" stroke="#3fb97d" stroke-width="2" stroke-linecap="round"/><circle cx="21" cy="21" r="2.5" fill="#4f8cff"/></svg>"""


class DailyReportHandler(SimpleHTTPRequestHandler):
    """Custom request handler serving dashboard, reports, matters, and API endpoints."""

    def __init__(self, *args, workspace_dir=None, reports_dir=None, matters_dir=None, **kwargs):
        self.workspace_dir = workspace_dir or find_default_workspace()
        self.reports_dir = reports_dir or os.path.join(self.workspace_dir, "daily-reports")
        self.matters_dir = matters_dir or os.path.join(self.workspace_dir, "matters")
        super().__init__(*args, directory=HERE, **kwargs)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = unquote(parsed.path)

        if path in ("/", "/index.html", "/today-report.html", "/tools/today-report.html"):
            self._serve_dashboard()
        elif path == "/favicon.ico":
            self._serve_favicon()
        elif path == "/api/status":
            self._serve_status()
        elif path == "/api/reports":
            self._serve_reports_list()
        elif path.startswith("/daily-reports/"):
            rel_path = path[len("/daily-reports/"):]
            self._serve_file_from_dir(self.reports_dir, rel_path, default_mime="text/markdown; charset=utf-8")
        elif path.startswith("/matters/"):
            rel_path = path[len("/matters/"):]
            self._serve_file_from_dir(self.matters_dir, rel_path, default_mime="text/markdown; charset=utf-8")
        elif path.startswith("/theme/"):
            theme_dir = os.path.join(os.path.dirname(os.path.dirname(HERE)), "local-theme")
            rel_path = path[len("/theme/"):]
            self._serve_file_from_dir(theme_dir, rel_path)
        else:
            # Fallback to local files in HERE
            super().do_GET()

    def do_HEAD(self):
        parsed = urlparse(self.path)
        path = unquote(parsed.path)

        if path in ("/", "/index.html", "/today-report.html", "/tools/today-report.html", "/api/status"):
            self.send_response(HTTPStatus.OK)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
        else:
            super().do_HEAD()

    def _serve_dashboard(self):
        ui_file = os.path.join(HERE, "today-report.html")
        if not os.path.exists(ui_file):
            self.send_error(HTTPStatus.NOT_FOUND, "today-report.html not found")
            return

        with open(ui_file, "r", encoding="utf-8") as f:
            content = f.read()

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
        payload = {
            "status": "ok",
            "server": "daily-report",
            "version": __version__,
            "port": self.server.server_port,
            "workspace_dir": self.workspace_dir,
            "reports_dir": self.reports_dir,
            "matters_dir": self.matters_dir,
            "reports_count": len(self._get_report_files()),
        }
        data = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(data)

    def _get_report_files(self):
        if not os.path.isdir(self.reports_dir):
            return []
        files = []
        for f in os.listdir(self.reports_dir):
            if f.endswith("_daily-report.md"):
                files.append(f)
        return sorted(files, reverse=True)

    def _serve_reports_list(self):
        report_files = self._get_report_files()
        reports = []
        for filename in report_files:
            date_match = re.match(r"^(\d{4}-\d{2}-\d{2})_daily-report\.md$", filename)
            date_str = date_match.group(1) if date_match else filename
            full_path = os.path.join(self.reports_dir, filename)
            stat = os.stat(full_path)
            reports.append({
                "date": date_str,
                "filename": filename,
                "size": stat.st_size,
                "modified": stat.st_mtime,
            })

        data = json.dumps({"reports": reports}, indent=2).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(data)

    def _serve_file_from_dir(self, base_dir, rel_path, default_mime="text/plain; charset=utf-8"):
        # Prevent directory traversal attacks
        safe_rel_path = os.path.normpath(rel_path).lstrip("/\\")
        if safe_rel_path.startswith("..") or os.path.isabs(safe_rel_path):
            self.send_error(HTTPStatus.FORBIDDEN, "Access denied")
            return

        target_file = os.path.join(base_dir, safe_rel_path)
        if not os.path.exists(target_file) or os.path.isdir(target_file):
            self.send_error(HTTPStatus.NOT_FOUND, f"File not found: {safe_rel_path}")
            return

        mime_type, _ = mimetypes.guess_type(target_file)
        if target_file.endswith(".md"):
            mime_type = "text/markdown; charset=utf-8"
        elif target_file.endswith(".html"):
            mime_type = "text/html; charset=utf-8"
        elif not mime_type:
            mime_type = default_mime

        try:
            with open(target_file, "rb") as f:
                data = f.read()

            stat = os.stat(target_file)
            last_modified = self.date_time_string(stat.st_mtime)

            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", mime_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Last-Modified", last_modified)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
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


def export_report(output_file: str = None) -> str:
    """Generates standalone static report HTML file."""
    src_file = os.path.join(HERE, "today-report.html")
    dest_file = output_file or os.path.join(HERE, "daily-report.html")
    if os.path.exists(src_file):
        with open(src_file, "r", encoding="utf-8") as f:
            content = f.read()
        with open(dest_file, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"✔ Static report exported to: {dest_file}")
        return dest_file
    return ""


def run_server(port: int = 24001, host: str = "127.0.0.1", workspace_dir: str = None, reports_dir: str = None, matters_dir: str = None):
    ws = workspace_dir or find_default_workspace()
    r_dir = reports_dir or os.path.join(ws, "daily-reports")
    m_dir = matters_dir or os.path.join(ws, "matters")

    class CustomServer(_Server):
        allow_reuse_address = True
        def __init__(self, server_address, RequestHandlerClass):
            super().__init__(server_address, RequestHandlerClass)

    def handler_factory(*args, **kwargs):
        return DailyReportHandler(*args, workspace_dir=ws, reports_dir=r_dir, matters_dir=m_dir, **kwargs)

    server_address = (host, port)
    try:
        httpd = CustomServer(server_address, handler_factory)
    except OSError as e:
        if e.errno == 48:
            print(f"\n❌ Error: Port {port} is already in use!")
            print(f"  • Free port with: kill -9 $(lsof -ti :{port})")
            print(f"  • Or run on another port: python3 server.py --port <NEW_PORT>\n")
            sys.exit(1)
        raise

    print("\n=======================================================")
    print("  Daily Report Live Server running at:")
    print(f"  ➜  http://localhost:{port}")
    print(f"  ➜  http://127.0.0.1:{port}")
    print("-------------------------------------------------------")
    print(f"  • Workspace: {ws}")
    print(f"  • Reports:   {r_dir}")
    print(f"  • Matters:   {m_dir}")
    print("=======================================================\n", flush=True)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Shutting down server.")
        httpd.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Live Report Server for Daily Work Reports")
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "24001")), help="HTTP port (default: 24001)")
    parser.add_argument("--host", default=os.getenv("HOST", "127.0.0.1"), help="Host/bind address (default: 127.0.0.1)")
    parser.add_argument("--workspace", default=None, help="Project workspace root directory")
    parser.add_argument("--reports-dir", default=None, help="Daily reports directory path")
    parser.add_argument("--matters-dir", default=None, help="Matters directory path")
    parser.add_argument("--export", action="store_true", help="Generate standalone static HTML report and exit")
    args = parser.parse_args()

    if args.export:
        export_report()
        sys.exit(0)

    run_server(port=args.port, host=args.host, workspace_dir=args.workspace, reports_dir=args.reports_dir, matters_dir=args.matters_dir)
