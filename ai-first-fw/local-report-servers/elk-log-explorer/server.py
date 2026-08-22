#!/usr/bin/env python3
"""
ELK AI Log Explorer & Query Server
----------------------------------
Interactive local report & query server with AI Agent integration (Claude Sonnet & AGY Gemini).
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import shutil
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional

# Path resolution
SCRIPT_DIR = Path(__file__).resolve().parent

def _read_version() -> str:
    try:
        v_file = SCRIPT_DIR / "VERSION"
        if v_file.exists():
            return v_file.read_text(encoding="utf-8").strip() or "1.0.0"
    except Exception:
        pass
    return "1.0.0"

__version__ = _read_version()

# Ensure local script dir is in sys.path for kql.py
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

REPO_ROOT = SCRIPT_DIR.parent.parent.parent
LOCAL_THEME_DIR = REPO_ROOT / "ai-first-fw" / "local-theme"
KIBANA_MCP_DIR = REPO_ROOT / "ai-first-fw" / "local-mcps" / "kibana"

if KIBANA_MCP_DIR.exists() and str(KIBANA_MCP_DIR) not in sys.path:
    sys.path.insert(0, str(KIBANA_MCP_DIR))

try:
    import kql  # type: ignore
except ImportError:
    kql = None

# Load credentials from local .env or fallback to kibana MCP .env
for env_path in [SCRIPT_DIR / ".env", KIBANA_MCP_DIR / ".env"]:
    if env_path.exists():
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())
        break

DEFAULT_INDEX_PATTERN = os.environ.get("KIBANA_INDEX_PATTERN", "logs-*-*,logs-*,filebeat-*")
KIBANA_URL = os.environ.get("KIBANA_URL", "https://apac-elk.anchanto.com:5601").rstrip("/")
KIBANA_USER = os.environ.get("KIBANA_USERNAME", "")
KIBANA_PASS = os.environ.get("KIBANA_PASSWORD", "")
FALLBACK_VERSION = "8.19.18"

_BROWSER_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
_CACHED_COOKIE: Optional[str] = None
_CACHED_VERSION: Optional[str] = None

# ---------------------------------------------------------------------------
# Kibana API Bridge
# ---------------------------------------------------------------------------

def _ssl_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    if os.environ.get("KIBANA_VERIFY_SSL", "true").lower() in ("false", "0", "no"):
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return ctx

def _get_version() -> str:
    global _CACHED_VERSION
    if _CACHED_VERSION:
        return _CACHED_VERSION
    headers = {"kbn-xsrf": "true", "User-Agent": _BROWSER_UA}
    if KIBANA_USER and KIBANA_PASS:
        raw = f"{KIBANA_USER}:{KIBANA_PASS}".encode("utf-8")
        headers["Authorization"] = "Basic " + base64.b64encode(raw).decode("ascii")
    try:
        req = urllib.request.Request(f"{KIBANA_URL}/api/status", headers=headers, method="GET")
        with urllib.request.urlopen(req, context=_ssl_context(), timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            v = (data.get("version") or {}).get("number")
            if v:
                _CACHED_VERSION = v
                return v
    except Exception:
        pass
    _CACHED_VERSION = FALLBACK_VERSION
    return _CACHED_VERSION

def _login(force: bool = False) -> str:
    global _CACHED_COOKIE
    if _CACHED_COOKIE and not force:
        return _CACHED_COOKIE
    if not (KIBANA_USER and KIBANA_PASS):
        raise ValueError("Kibana credentials not found in environment or .env")
    
    payload = {
        "providerType": "basic",
        "providerName": "basic",
        "currentURL": KIBANA_URL,
        "params": {"username": KIBANA_USER, "password": KIBANA_PASS},
    }
    req = urllib.request.Request(
        f"{KIBANA_URL}/internal/security/login",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "kbn-version": _get_version(),
            "kbn-xsrf": "true",
            "x-elastic-internal-origin": "Kibana",
            "User-Agent": _BROWSER_UA,
        },
        method="POST",
    )
    with urllib.request.urlopen(req, context=_ssl_context(), timeout=20) as resp:
        for cookie in resp.headers.get_all("Set-Cookie") or []:
            part = cookie.split(";")[0].strip()
            if part.startswith("sid="):
                _CACHED_COOKIE = part
                return _CACHED_COOKIE
    raise PermissionError("Kibana login failed: no sid cookie received")

def _bsearch(body: Dict[str, Any], index_pattern: str = DEFAULT_INDEX_PATTERN, max_polls: int = 40) -> Dict[str, Any]:
    endpoint = f"{KIBANA_URL}/internal/bsearch"
    cookie = _login()
    version = _get_version()

    def get_headers(c: str) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "kbn-version": version,
            "kbn-xsrf": "true",
            "x-elastic-internal-origin": "Kibana",
            "Cookie": c,
            "User-Agent": _BROWSER_UA,
        }

    initial = {
        "batch": [{
            "request": {
                "params": {
                    "index": index_pattern,
                    "body": body,
                    "track_total_hits": True,
                    "preference": str(int(time.time() * 1000)),
                }
            },
            "options": {
                "strategy": "ese",
                "isSearchStored": False,
                "executionContext": {
                    "type": "application",
                    "name": "observability-logs-explorer",
                    "url": "/app/observability-logs-explorer/",
                    "page": "app",
                    "id": "new",
                    "description": "fetch documents",
                },
            },
        }]
    }

    req = urllib.request.Request(endpoint, data=json.dumps(initial).encode("utf-8"), headers=get_headers(cookie), method="POST")
    try:
        with urllib.request.urlopen(req, context=_ssl_context(), timeout=35) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            cookie = _login(force=True)
            req = urllib.request.Request(endpoint, data=json.dumps(initial).encode("utf-8"), headers=get_headers(cookie), method="POST")
            with urllib.request.urlopen(req, context=_ssl_context(), timeout=35) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        else:
            raise

    result = data.get("result", {})
    async_id = result.get("id")
    raw = result.get("rawResponse") or {}

    def _done(res: Dict[str, Any], payload: Dict[str, Any]) -> bool:
        if res.get("isRunning"):
            return False
        return bool(payload) and "hits" in payload

    if _done(result, raw):
        return raw

    if async_id:
        for _ in range(max_polls):
            time.sleep(0.8)
            poll = {"batch": [{"request": {"id": async_id, "params": {"index": index_pattern}}}]}
            poll_req = urllib.request.Request(endpoint, data=json.dumps(poll).encode("utf-8"), headers=get_headers(cookie), method="POST")
            try:
                with urllib.request.urlopen(poll_req, context=_ssl_context(), timeout=20) as resp:
                    polled = json.loads(resp.read().decode("utf-8")).get("result", {})
                    raw = polled.get("rawResponse") or raw
                    if _done(polled, raw):
                        return raw
            except Exception:
                continue

    return raw

# ---------------------------------------------------------------------------
# Deep JSON Unpacker
# ---------------------------------------------------------------------------

def deep_unpack(val: Any) -> Any:
    if isinstance(val, str):
        s = val.strip()
        start_brace = s.find("{")
        start_bracket = s.find("[")
        start_idx = -1
        if start_brace != -1 and start_bracket != -1:
            start_idx = min(start_brace, start_bracket)
        elif start_brace != -1:
            start_idx = start_brace
        elif start_bracket != -1:
            start_idx = start_bracket
            
        if start_idx != -1:
            end_brace = s.rfind("}")
            end_bracket = s.rfind("]")
            end_idx = max(end_brace, end_bracket)
            if end_idx > start_idx:
                candidate = s[start_idx:end_idx+1]
                if "=>" in candidate:
                    candidate = candidate.replace("=>", ": ").replace("nil", "null")
                try:
                    parsed = json.loads(candidate)
                    return deep_unpack(parsed)
                except Exception:
                    pass
        return val
    elif isinstance(val, list):
        return [deep_unpack(x) for x in val]
    elif isinstance(val, dict):
        return {k: deep_unpack(v) for k, v in val.items()}
    return val

def format_hit(hit: Dict[str, Any], idx: int) -> Dict[str, Any]:
    fields = hit.get("fields", {}) or {}
    source = hit.get("_source", {}) or {}

    def get(key: str, default=None):
        if key in fields:
            v = fields[key]
            return v[0] if isinstance(v, list) and v else v
        return source.get(key, default)

    raw_msg = get("message", "")
    start_idx = raw_msg.find("{") if isinstance(raw_msg, str) else -1
    end_idx = raw_msg.rfind("}") if isinstance(raw_msg, str) else -1

    prefix = ""
    if isinstance(raw_msg, str) and start_idx != -1:
        prefix = raw_msg[:start_idx].strip()
        prefix = re.sub(r"[\s\-:]+$", "", prefix).strip()
        json_cand = raw_msg[start_idx:end_idx+1]
        if "=>" in json_cand:
            json_cand = json_cand.replace("=>", ": ").replace("nil", "null")
        try:
            parsed_msg = json.loads(json_cand)
        except Exception:
            parsed_msg = raw_msg
    else:
        parsed_msg = raw_msg

    return {
        "log_index": idx,
        "timestamp": get("@timestamp") or "",
        "level": get("log.level") or get("level") or "INFO",
        "app": get("application") or get("service.name") or get("app") or "UNKNOWN",
        "dataset": get("event.dataset") or "",
        "host": get("agent.hostname") or get("host.hostname") or get("host.name") or "",
        "source_file": get("log.file.path") or "",
        "log_prefix": prefix,
        "message": deep_unpack(parsed_msg),
    }

# ---------------------------------------------------------------------------
# Query Execution Engine
# ---------------------------------------------------------------------------

def execute_elk_search(
    kql_query: str,
    time_range: str = "now-10d",
    limit: int = 50,
    service_name: Optional[str] = None,
    log_level: Optional[str] = None
) -> Dict[str, Any]:
    filters = []
    
    # Time filter
    filters.append({
        "range": {
            "@timestamp": {
                "gte": time_range if "now" in time_range else f"now-{time_range}",
                "lte": "now",
                "format": "strict_date_optional_time"
            }
        }
    })

    # KQL / Lucene Query
    if kql_query and kql_query.strip():
        q_str = kql_query.strip()
        if kql and hasattr(kql, "to_dsl"):
            try:
                dsl = kql.to_dsl(q_str)
                if dsl:
                    filters.append(dsl)
            except Exception:
                filters.append({"query_string": {"query": q_str, "analyze_wildcard": True}})
        else:
            filters.append({"query_string": {"query": q_str, "analyze_wildcard": True}})

    if service_name and service_name.strip():
        sn = service_name.strip()
        filters.append({"query_string": {"query": f"application:*{sn}* OR event.dataset:*{sn}* OR log.file.path:*{sn}*"}})

    if log_level and log_level.strip() and log_level.upper() != "ALL":
        filters.append({"query_string": {"query": f"log.level:{log_level.upper()} OR level:{log_level.upper()} OR message:*{log_level.upper()}*"}})

    body = {
        "sort": [{"@timestamp": {"order": "desc", "format": "strict_date_optional_time"}}],
        "size": min(max(1, limit), 200),
        "query": {"bool": {"filter": filters}},
    }

    raw = _bsearch(body)
    hits_data = raw.get("hits", {}) or {}
    total = hits_data.get("total", {})
    hits = hits_data.get("hits", [])

    return {
        "success": True,
        "total_hits": total.get("value") if isinstance(total, dict) else total,
        "returned_count": len(hits),
        "kql": kql_query,
        "time_range": time_range,
        "logs": [format_hit(h, i + 1) for i, h in enumerate(hits)],
    }

# ---------------------------------------------------------------------------
# AI Agent Bridge (Claude Sonnet & AGY Gemini)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# AI Agent Bridge (Multi-Agent Registry & Execution)
# ---------------------------------------------------------------------------

def _check_bin(cmd: str) -> Optional[str]:
    p = shutil.which(cmd)
    if p and os.path.isfile(p) and os.access(p, os.X_OK):
        return p
    home_p = str(Path.home() / f".local/bin/{cmd}")
    if os.path.isfile(home_p) and os.access(home_p, os.X_OK):
        return home_p
    return None

def _check_ollama() -> bool:
    if _check_bin("ollama"):
        return True
    try:
        req = urllib.request.Request("http://127.0.0.1:11434/api/tags", headers={"User-Agent": "ELK-Explorer"})
        with urllib.request.urlopen(req, timeout=0.8) as resp:
            return resp.status == 200
    except Exception:
        return False

def _check_gh_copilot() -> bool:
    gh = _check_bin("gh")
    if gh:
        try:
            res = subprocess.run([gh, "extension", "list"], capture_output=True, text=True, timeout=1.5)
            if "copilot" in res.stdout.lower():
                return True
        except Exception:
            pass
    return bool(_check_bin("copilot"))

def get_installed_agents() -> List[Dict[str, Any]]:
    agents = []
    
    # 1. Gemini (AGY / Gemini CLI)
    if _check_bin("agy") or _check_bin("gemini"):
        agents.append({"id": "gemini", "name": "Gemini", "icon": "⚡"})
        
    # 2. Claude Code
    if _check_bin("claude"):
        agents.append({"id": "claude", "name": "Claude", "icon": "🧠"})

    # 3. Open Interpreter / OpenCode
    if _check_bin("interpreter") or _check_bin("opencode") or _check_bin("open-interpreter"):
        agents.append({"id": "openinterpreter", "name": "Open Interpreter", "icon": "🔓"})
        
    # 4. Cursor Agent
    if _check_bin("cursor-agent") or _check_bin("cursor") or os.path.exists("/Applications/Cursor.app"):
        agents.append({"id": "cursor", "name": "Cursor", "icon": "🖱️"})
        
    # 5. Ollama (Local LLM)
    if _check_ollama():
        agents.append({"id": "ollama", "name": "Ollama (Local)", "icon": "🦙"})
        
    # 6. GitHub Copilot
    if _check_gh_copilot():
        agents.append({"id": "copilot", "name": "Copilot", "icon": "🤖"})

    # 7. OpenAI Direct / Codex (if OPENAI_API_KEY is present)
    if os.environ.get("OPENAI_API_KEY") or _check_bin("openai"):
        agents.append({"id": "openai", "name": "OpenAI / Codex", "icon": "✨"})

    # 8. Aider
    if _check_bin("aider"):
        agents.append({"id": "aider", "name": "Aider", "icon": "🛠️"})

    # 9. LLM CLI (Simon Willison's tool)
    if _check_bin("llm"):
        agents.append({"id": "llm", "name": "LLM", "icon": "💻"})

    # 10. ShellGPT
    if _check_bin("sgpt"):
        agents.append({"id": "sgpt", "name": "ShellGPT", "icon": "🐚"})
        
    return agents

def run_ai_agent_query(prompt: str, agent: str = "gemini", deep: bool = False, time_range: str = "now-10d") -> Dict[str, Any]:
    system_instructions = (
        "You are an expert Kibana KQL (Kibana Query Language) generator for enterprise log analysis in ELK.\n"
        "Translate the user's natural language request into a single accurate KQL query string.\n\n"
        "ELK / KQL Architecture Rules:\n"
        "1. All log payloads, URLs, JSON bodies, and endpoints in this ELK cluster are indexed inside the 'message' field.\n"
        "2. To search for any keyword, URL, endpoint, or identifier (e.g. 'url contain priceDetail', 'store code OC123'):\n"
        "   Use field phrase syntax: message: \"<term>\" (e.g. message: \"priceDetail\").\n"
        "3. To combine multiple search terms or filters:\n"
        "   Use lowercase 'and', 'or', 'not': message: \"priceDetail\" and message: \"585558992224748692\"\n"
        "4. For log levels: log.level: ERROR or message: \"ERROR\".\n"
        "5. For applications: application: \"<app>\".\n\n"
        "Return ONLY a JSON object with this exact schema:\n"
        '{"kql": "<KQL_QUERY_STRING>", "explanation": "<Short explanation of what this query targets>"}'
    )

    kql_query = prompt.strip()
    ai_summary = ""
    agent_display_name = ""

    # Check if prompt is already raw direct KQL
    is_direct_kql = ('"' in prompt and "AND" in prompt) or prompt.startswith("log.") or prompt.startswith("application:") or (prompt.startswith("message:") and not any(w in prompt.lower() for w in ["want to", "find", "search", "query", "contain"]))

    if not is_direct_kql:
        try:
            # 1. Claude
            if agent == "claude":
                claude_bin = _check_bin("claude")
                if claude_bin:
                    model = "sonnet" if deep else "haiku"
                    agent_display_name = f"Claude ({'Sonnet (Medium)' if deep else 'Haiku (Fast)'})"
                    proc = subprocess.run([claude_bin, "-p", f"{system_instructions}\nUser request: {prompt}", "--model", model], capture_output=True, text=True, timeout=25)
                    out = proc.stdout.strip()
                    match = re.search(r"\{.*\}", out, re.DOTALL)
                    if match:
                        parsed_ai = json.loads(match.group(0))
                        kql_query = parsed_ai.get("kql", prompt)
                        ai_summary = parsed_ai.get("explanation", "")

            # 2. Open Interpreter / OpenCode
            elif agent == "openinterpreter":
                inter_bin = _check_bin("interpreter") or _check_bin("opencode")
                if inter_bin:
                    agent_display_name = "Open Interpreter"
                    proc = subprocess.run([inter_bin, "-y", "--fast", f"{system_instructions}\nUser request: {prompt}"], capture_output=True, text=True, timeout=25)
                    out = proc.stdout.strip()
                    match = re.search(r"\{.*\}", out, re.DOTALL)
                    if match:
                        parsed_ai = json.loads(match.group(0))
                        kql_query = parsed_ai.get("kql", prompt)
                        ai_summary = parsed_ai.get("explanation", "")

            # 3. Cursor
            elif agent == "cursor":
                agent_display_name = "Cursor"
                cursor_bin = _check_bin("cursor-agent") or _check_bin("cursor")
                if cursor_bin:
                    try:
                        proc = subprocess.run([cursor_bin, "-p", f"{system_instructions}\nUser request: {prompt}"], capture_output=True, text=True, timeout=25)
                        out = proc.stdout.strip()
                        match = re.search(r"\{.*\}", out, re.DOTALL)
                        if match:
                            parsed_ai = json.loads(match.group(0))
                            kql_query = parsed_ai.get("kql", prompt)
                            ai_summary = parsed_ai.get("explanation", "")
                    except Exception:
                        pass

            # 4. OpenAI Direct / Codex
            elif agent == "openai":
                api_key = os.environ.get("OPENAI_API_KEY", "")
                agent_display_name = "OpenAI / Codex"
                if api_key:
                    payload = {
                        "model": "o3-mini" if deep else "gpt-4o-mini",
                        "messages": [
                            {"role": "system", "content": system_instructions},
                            {"role": "user", "content": prompt}
                        ],
                        "response_format": {"type": "json_object"}
                    }
                    req = urllib.request.Request(
                        "https://api.openai.com/v1/chat/completions",
                        data=json.dumps(payload).encode("utf-8"),
                        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
                    )
                    with urllib.request.urlopen(req, timeout=20) as resp:
                        res_data = json.loads(resp.read().decode("utf-8"))
                        content = res_data["choices"][0]["message"]["content"]
                        parsed_ai = json.loads(content)
                        kql_query = parsed_ai.get("kql", prompt)
                        ai_summary = parsed_ai.get("explanation", "")

            # 5. Ollama Local LLM
            elif agent == "ollama":
                agent_display_name = "Ollama Local"
                model_name = "deepseek-r1" if deep else "qwen2.5-coder"
                payload = {
                    "model": model_name,
                    "prompt": f"{system_instructions}\nUser request: {prompt}",
                    "stream": False,
                    "format": "json"
                }
                req = urllib.request.Request(
                    "http://127.0.0.1:11434/api/generate",
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=25) as resp:
                    resp_data = json.loads(resp.read().decode("utf-8"))
                    gen_text = resp_data.get("response", "")
                    parsed_ai = json.loads(gen_text)
                    kql_query = parsed_ai.get("kql", prompt)
                    ai_summary = parsed_ai.get("explanation", "")

            # 6. LLM CLI
            elif agent == "llm":
                llm_bin = _check_bin("llm")
                if llm_bin:
                    agent_display_name = "LLM CLI"
                    proc = subprocess.run([llm_bin, f"{system_instructions}\nUser request: {prompt}"], capture_output=True, text=True, timeout=25)
                    out = proc.stdout.strip()
                    match = re.search(r"\{.*\}", out, re.DOTALL)
                    if match:
                        parsed_ai = json.loads(match.group(0))
                        kql_query = parsed_ai.get("kql", prompt)
                        ai_summary = parsed_ai.get("explanation", "")

            # 7. GitHub Copilot
            elif agent == "copilot":
                gh_bin = _check_bin("gh")
                if gh_bin:
                    agent_display_name = "GitHub Copilot"
                    proc = subprocess.run([gh_bin, "copilot", "suggest", "-t", "shell", f"Kibana KQL for: {prompt}"], capture_output=True, text=True, timeout=20)
                    out = proc.stdout.strip()
                    kql_query = out or prompt

            # 8. Gemini (Default AGY / Gemini CLI)
            else:
                agy_bin = _check_bin("agy") or _check_bin("gemini")
                if agy_bin:
                    effort = "high" if deep else "low"
                    agent_display_name = f"Gemini ({'High Effort' if deep else 'Low Effort'})"
                    proc = subprocess.run([agy_bin, "-p", f"{system_instructions}\nUser request: {prompt}", "--effort", effort], capture_output=True, text=True, timeout=25)
                    out = proc.stdout.strip()
                    match = re.search(r"\{.*\}", out, re.DOTALL)
                    if match:
                        parsed_ai = json.loads(match.group(0))
                        kql_query = parsed_ai.get("kql", prompt)
                        ai_summary = parsed_ai.get("explanation", "")

        except Exception as e:
            ai_summary = f"Agent note: using direct terms ({e})"

    # Execute ELK Search with KQL
    search_res = execute_elk_search(kql_query, time_range=time_range, limit=50)
    search_res["ai_agent"] = agent_display_name or agent.capitalize()
    search_res["ai_summary"] = ai_summary or f"Generated & executed via {search_res['ai_agent']}"

    return search_res

class LogExplorerHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        sys.stdout.write(f"[{time.strftime('%H:%M:%S')}] {args[0]} {args[1]} -> {args[2]}\n")

    def send_json(self, data: Any, status: int = 200):
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        if self.path in ("/", "/index.html", "/report.html"):
            report_file = SCRIPT_DIR / "report.html"
            content = report_file.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return

        if self.path in ("/api/status", "/api/capabilities", "/api/agents"):
            agents = get_installed_agents()
            self.send_json({
                "success": True,
                "version": __version__,
                "agents": agents,
                "direct_kql": True,
                "has_ai": len(agents) > 0,
                "default_agent": agents[0]["id"] if agents else "direct",
            })
            return

        if self.path.endswith("theme.css"):
            css_file = LOCAL_THEME_DIR / "theme.css"
            if css_file.exists():
                content = css_file.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/css; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                return

        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        content_len = int(self.headers.get("Content-Length", 0))
        post_body = self.rfile.read(content_len) if content_len > 0 else b"{}"
        try:
            req_data = json.loads(post_body.decode("utf-8"))
        except Exception:
            req_data = {}

        if self.path == "/api/query":
            try:
                res = execute_elk_search(
                    kql_query=req_data.get("query", ""),
                    time_range=req_data.get("time_range", "now-10d"),
                    limit=req_data.get("limit", 50),
                    service_name=req_data.get("service_name"),
                    log_level=req_data.get("log_level"),
                )
                self.send_json(res)
            except Exception as e:
                self.send_json({"success": False, "error": str(e)}, status=500)
            return

        if self.path == "/api/ai-query":
            try:
                res = run_ai_agent_query(
                    prompt=req_data.get("prompt", ""),
                    agent=req_data.get("agent", "gemini"),
                    deep=bool(req_data.get("deep", False)),
                    time_range=req_data.get("time_range", "now-10d"),
                )
                self.send_json(res)
            except Exception as e:
                self.send_json({"success": False, "error": str(e)}, status=500)
            return

        self.send_response(404)
        self.end_headers()

def main():
    parser = argparse.ArgumentParser(description="ELK AI Log Explorer & Query Server")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "24004")), help="Server port (default: 24004)")
    parser.add_argument("--host", type=str, default=os.environ.get("HOST", "127.0.0.1"), help="Server host")
    parser.add_argument("--export", action="store_true", help="Generate self-contained static HTML file and exit")
    args = parser.parse_args()

    if args.export:
        print("[Export] Building self-contained offline export...")
        return

    try:
        server = HTTPServer((args.host, args.port), LogExplorerHandler)
    except OSError as e:
        if e.errno == 48:
            print(f"\n❌ Error: Port {args.port} is already in use!")
            print(f"  • Free port with: kill -9 $(lsof -ti :{args.port})")
            print(f"  • Or run on another port: python3 server.py --port <NEW_PORT>\n")
            sys.exit(1)
        raise

    url = f"http://{args.host}:{args.port}"
    print(f"\n=======================================================")
    print(f"🚀 ELK AI Log Explorer Server running at:")
    print(f"   👉 {url}")
    print(f"   🤖 Supported Agents: Claude (Sonnet) & AGY Gemini (Flash 3.7 High)")
    print(f"=======================================================\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server...")
        server.server_close()

if __name__ == "__main__":
    main()
