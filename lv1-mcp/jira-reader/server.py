#!/usr/bin/env python3
# /// script
# requires-python = ">=3.8"
# dependencies = []
# ///
"""
Jira Reader Model Context Protocol (MCP) Server
-----------------------------------------------
A zero-dependency, universal MCP server providing full Jira issue inspection,
JQL search, board and sprint reads (Agile API), dashboard and gadget reads,
attachment downloads, and
in-memory text/log streaming for AI agents.

Runs out-of-the-box on Python 3 standard library on any machine (macOS, Linux, Windows).
"""

import argparse
import base64
import json
import os
import re
import ssl
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

SERVER_NAME = "jira-reader"
SERVER_VERSION = "1.4.0"
MCP_PROTOCOL_VERSION = "2024-11-05"

# ---------------------------------------------------------------------------
# Environment and Configuration Loader
# ---------------------------------------------------------------------------

DEFAULT_ENV_TEMPLATE = """# ==============================================================================
# Jira Reader MCP Server Configuration (.env)
# ==============================================================================
# Instructions:
# 1. Copy this file to .env:
#    cp .env.example .env   (or run: python3 server.py --init-env)
# 2. Fill in your Jira credentials below.
# 3. Test your connection:
#    python3 server.py --test
# ==============================================================================

# [Required] Your Jira instance base URL
# Cloud: https://your-domain.atlassian.net
# Server / Data Center: https://jira.yourcompany.com
JIRA_HOST=https://your-domain.atlassian.net

# [Required for Jira Cloud] Your Atlassian login email address
JIRA_EMAIL=your-email@company.com

# [Required for Jira Cloud] Jira API Token
# Generate token at: https://id.atlassian.com/manage-profile/security/api-tokens
JIRA_API_TOKEN=your_jira_api_token_here

# [Alternative for Jira Server / Data Center] Personal Access Token (PAT)
# Uncomment and fill if using Jira Server/Data Center instead of email + API token
# JIRA_PAT=your_personal_access_token_here

# [Optional] Default directory for downloaded attachments (relative to project root)
# Default: .scratchpads/downloads
JIRA_DOWNLOAD_DIR=.scratchpads/downloads

# [Optional] Jira REST API Version
# Default: 3 (Jira Cloud). Set to 2 for Jira Server / Data Center
JIRA_API_VERSION=3
"""

def _find_project_root() -> Optional[Path]:
    """Locate active user project root by searching upwards from cwd.
    
    Never treats the MCP server's own source repository as the user's project.
    """
    cwd = Path.cwd().resolve()
    script_dir = Path(__file__).resolve().parent
    server_roots = {script_dir, *script_dir.parents}

    for p in [cwd, *cwd.parents]:
        if p in server_roots:
            continue
        if (p / ".git").exists() or (p / ".cursor").is_dir():
            return p
    return None


def _load_env_file(filepath: Path) -> bool:
    """Parse a .env file and populate os.environ without third-party libraries."""
    if not filepath.is_file():
        return False
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("export "):
                    line = line[7:].strip()
                if "=" in line:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip()
                    # Strip outer quotes if present
                    if len(val) >= 2 and (
                        (val.startswith('"') and val.endswith('"')) or
                        (val.startswith("'") and val.endswith("'"))
                    ):
                        val = val[1:-1]
                    # Only set if key is not already defined in environment
                    if key and key not in os.environ:
                        os.environ[key] = val
        return True
    except Exception as exc:
        sys.stderr.write(f"[{SERVER_NAME}] Warning: Failed reading {filepath}: {exc}\n")
        return False


def _get_global_env_path() -> Path:
    d = Path.home() / ".mcp"
    try:
        d.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return d / ".jira-reader.env"


def _auto_discover_env() -> None:
    """Search and load .env from standard global hidden directory and local locations."""
    script_dir = Path(__file__).resolve().parent
    project_root = _find_project_root()
    candidates = [
        Path.home() / ".mcp/.jira-reader.env",
        Path.home() / ".mcp/jira-reader.env",
        Path.home() / ".mcps/.jira-reader.env",
        Path.home() / ".mcps/jira-reader.env",
        Path.home() / ".config/mcps/jira-reader.env",
        Path.home() / ".jira.env",
        script_dir / ".env",
    ]
    if project_root:
        candidates.append(project_root / ".env")
    candidates.append(Path.cwd() / ".env")
    for candidate in candidates:
        if candidate.is_file():
            _load_env_file(candidate)
            break


# Run auto-discovery on startup
_auto_discover_env()


def _is_placeholder(val: str) -> bool:
    if not val:
        return True
    lower = val.lower()
    return any(p in lower for p in ["example.com", "your-domain", "your_api_token", "your-email", "xxx", "your_token", "your_pat", "your_username", "your_password", "your_kibana_password"])


def _get_config() -> Dict[str, str]:
    """Retrieve and validate Jira configuration from environment variables."""
    host = os.environ.get("JIRA_HOST", "").strip().rstrip("/")
    email = os.environ.get("JIRA_EMAIL", "").strip()
    api_token = os.environ.get("JIRA_API_TOKEN", "").strip()
    pat = os.environ.get("JIRA_PAT", "").strip()
    api_version = os.environ.get("JIRA_API_VERSION", "3").strip()

    if not host or _is_placeholder(host):
        raise ValueError(
            "JIRA_HOST environment variable is missing or placeholder.\n"
            "Please set JIRA_HOST (e.g. 'https://anchantoplan.atlassian.net')."
        )

    if (not pat or _is_placeholder(pat)) and (not email or not api_token or _is_placeholder(email) or _is_placeholder(api_token)):
        raise ValueError(
            "Jira authentication credentials missing or placeholder.\n"
            "Please configure JIRA_EMAIL and JIRA_API_TOKEN."
        )

    return {
        "host": host,
        "email": email,
        "api_token": api_token,
        "pat": pat,
        "api_version": api_version,
    }


def _resolve_download_dir(custom_path: Optional[str] = None) -> Path:
    """Resolve download directory safely.

    - If custom_path is provided by caller/AI, honor it directly (including /tmp).
    - If JIRA_DOWNLOAD_DIR is configured, honor it.
    - If inside a user project, default to <project_root>/.scratchpads/downloads.
    - If outside any project, default to system temp directory (/tmp/jira-downloads).
    """
    if custom_path:
        p = Path(custom_path).expanduser()
        if p.is_absolute():
            return p.resolve()
        project_root = _find_project_root()
        base = project_root if project_root else (Path(tempfile.gettempdir()) / "jira-downloads")
        return (base / p).resolve()

    env_dir = os.environ.get("JIRA_DOWNLOAD_DIR", "").strip()
    if env_dir:
        base_dir = Path(env_dir).expanduser()
        if base_dir.is_absolute():
            return base_dir.resolve()
        project_root = _find_project_root()
        if project_root:
            return (project_root / base_dir).resolve()
        return (Path(tempfile.gettempdir()) / base_dir).resolve()

    project_root = _find_project_root()
    if project_root:
        return (project_root / ".scratchpads/downloads").resolve()

    # Fallback when outside any project: system temp directory
    return (Path(tempfile.gettempdir()) / "jira-downloads").resolve()


def _format_size(size_bytes: int) -> str:
    """Format bytes into a human-readable size string."""
    size = float(size_bytes)
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024.0:
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024.0
    return f"{size:.1f} TB"


# ---------------------------------------------------------------------------
# Jira HTTP API Client (Zero-Dependency urllib)
# ---------------------------------------------------------------------------

def _make_request(
    method: str,
    path_or_url: str,
    params: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 60,
) -> Tuple[int, bytes, Dict[str, str]]:
    """Execute an authenticated HTTP request to Jira using standard library urllib."""
    config = _get_config()
    
    if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
        full_url = path_or_url
    else:
        path = path_or_url if path_or_url.startswith("/") else f"/{path_or_url}"
        full_url = f"{config['host']}{path}"

    if params:
        query_string = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
        if query_string:
            sep = "&" if "?" in full_url else "?"
            full_url = f"{full_url}{sep}{query_string}"

    req = urllib.request.Request(full_url, method=method.upper())
    req.add_header("Accept", "application/json")
    req.add_header("User-Agent", f"{SERVER_NAME}/{SERVER_VERSION}")

    if config["pat"]:
        req.add_header("Authorization", f"Bearer {config['pat']}")
    else:
        creds = f"{config['email']}:{config['api_token']}"
        encoded_creds = base64.b64encode(creds.encode("utf-8")).decode("ascii")
        req.add_header("Authorization", f"Basic {encoded_creds}")

    if headers:
        for k, v in headers.items():
            req.add_header(k, v)

    ssl_context = ssl.create_default_context()

    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ssl_context) as resp:
            status_code = resp.status
            content = resp.read()
            resp_headers = dict(resp.headers.items())
            return status_code, content, resp_headers
    except urllib.error.HTTPError as err:
        error_body = ""
        try:
            error_body = err.read().decode("utf-8", errors="replace")
        except Exception:
            pass

        if err.code == 401:
            raise PermissionError(
                "Jira Authentication failed (401). Please check JIRA_EMAIL and JIRA_API_TOKEN / JIRA_PAT."
            ) from err
        elif err.code == 403:
            raise PermissionError(
                f"Jira Access forbidden (403). You do not have permission for this resource.\nDetails: {error_body}"
            ) from err
        elif err.code == 404:
            raise FileNotFoundError(
                f"Jira resource not found (404) at {path_or_url}\nDetails: {error_body}"
            ) from err
        else:
            raise RuntimeError(
                f"Jira API HTTP Error {err.code}: {err.reason}\n{error_body}"
            ) from err
    except urllib.error.URLError as err:
        raise ConnectionError(
            f"Failed to connect to Jira host '{config['host']}': {err.reason}"
        ) from err


def _download_stream(url: str, target_file: Path, timeout: int = 120) -> int:
    """Download a file stream directly to local disk in chunks without high memory consumption."""
    config = _get_config()
    req = urllib.request.Request(url, method="GET")
    req.add_header("Accept", "*/*")
    req.add_header("User-Agent", f"{SERVER_NAME}/{SERVER_VERSION}")

    if config["pat"]:
        req.add_header("Authorization", f"Bearer {config['pat']}")
    else:
        creds = f"{config['email']}:{config['api_token']}"
        encoded_creds = base64.b64encode(creds.encode("utf-8")).decode("ascii")
        req.add_header("Authorization", f"Basic {encoded_creds}")

    ssl_context = ssl.create_default_context()
    total_bytes = 0

    with urllib.request.urlopen(req, timeout=timeout, context=ssl_context) as resp:
        with open(target_file, "wb") as f:
            while True:
                chunk = resp.read(32768)
                if not chunk:
                    break
                f.write(chunk)
                total_bytes += len(chunk)

    return total_bytes


# ---------------------------------------------------------------------------
# ADF (Atlassian Document Format) Parser
# ---------------------------------------------------------------------------

def _extract_adf_text(node: Any, depth: int = 0) -> str:
    """
    Recursively converts Atlassian Document Format (ADF) JSON structure
    into clean, readable Markdown/plaintext.
    """
    if not node:
        return ""
    if isinstance(node, str):
        return node
    if isinstance(node, list):
        return "\n".join(filter(None, (_extract_adf_text(item, depth) for item in node)))
    if not isinstance(node, dict):
        return str(node)

    node_type = node.get("type", "")
    content = node.get("content", [])
    text = node.get("text", "")
    attrs = node.get("attrs", {})

    # Formatting marks (strong, em, code, strike, underline, link)
    marks = node.get("marks", [])
    for mark in marks:
        m_type = mark.get("type", "")
        if m_type == "code":
            text = f"`{text}`"
        elif m_type == "strong":
            text = f"**{text}**"
        elif m_type == "em":
            text = f"*{text}*"
        elif m_type == "strike":
            text = f"~~{text}~~"
        elif m_type == "underline":
            text = f"<u>{text}</u>"
        elif m_type == "link":
            href = mark.get("attrs", {}).get("href", "")
            text = f"[{text}]({href})" if href else text

    if node_type == "text":
        return text

    if node_type == "hardBreak":
        return "\n"

    if node_type == "mention":
        m_text = attrs.get("text", "")
        return m_text if m_text else f"@{attrs.get('id', 'user')}"

    if node_type == "emoji":
        return attrs.get("text", "") or attrs.get("shortName", "")

    if node_type == "inlineCard":
        url = attrs.get("url", "")
        return f"[{url}]({url})" if url else ""

    if node_type == "blockCard":
        url = attrs.get("url", "")
        return f"\n[{url}]({url})\n" if url else ""

    if node_type in ("mediaSingle", "mediaGroup"):
        return "".join(_extract_adf_text(c, depth) for c in content)

    if node_type in ("media", "mediaInline"):
        alt = attrs.get("alt", "") or "attachment"
        media_id = attrs.get("id", "")
        return f"![{alt}]({media_id})" if media_id else ""

    if node_type == "panel":
        panel_type = attrs.get("panelType", "info").upper()
        inner = "".join(_extract_adf_text(c, depth) for c in content)
        lines = [f"> **[{panel_type}]** {l}" if i == 0 else f"> {l}" for i, l in enumerate(inner.splitlines())]
        return "\n".join(lines) + "\n"

    if node_type in ("expand", "nestedExpand"):
        title = attrs.get("title", "Details")
        inner = "".join(_extract_adf_text(c, depth) for c in content)
        return f"\n<details><summary>{title}</summary>\n\n{inner}\n</details>\n"

    if node_type == "status":
        status_text = attrs.get("text", "")
        return f"[{status_text}]"

    if node_type == "date":
        ts = attrs.get("timestamp", "")
        return f"`{ts}`"

    if node_type == "paragraph":
        inner = "".join(_extract_adf_text(c, depth) for c in content)
        return f"{inner}\n"

    if node_type == "heading":
        level = attrs.get("level", 1)
        prefix = "#" * max(1, min(6, level))
        inner = "".join(_extract_adf_text(c, depth) for c in content)
        return f"{prefix} {inner}\n"

    if node_type == "bulletList":
        items = [_extract_adf_text(c, depth + 1) for c in content]
        return "\n".join(f"- {it.strip()}" for it in items if it.strip()) + "\n"

    if node_type == "orderedList":
        items = [_extract_adf_text(c, depth + 1) for c in content]
        return "\n".join(f"{idx+1}. {it.strip()}" for idx, it in enumerate(items) if it.strip()) + "\n"

    if node_type == "listItem":
        return "".join(_extract_adf_text(c, depth) for c in content).strip()

    if node_type == "codeBlock":
        lang = attrs.get("language", "")
        code_text = "".join(_extract_adf_text(c, depth) for c in content)
        return f"\n```{lang}\n{code_text}\n```\n"

    if node_type == "blockquote":
        inner = "".join(_extract_adf_text(c, depth) for c in content)
        lines = [f"> {line}" for line in inner.splitlines()]
        return "\n".join(lines) + "\n"

    if node_type == "rule":
        return "\n---\n"

    if node_type in ("table", "tableRow", "tableHeader", "tableCell"):
        sub = " | ".join(filter(None, (_extract_adf_text(c, depth).strip() for c in content)))
        return f"| {sub} |" if node_type == "tableRow" else sub

    # Generic container fallback
    if content:
        return "".join(_extract_adf_text(c, depth) for c in content)

    return text


def _format_comment(c: Dict[str, Any]) -> Dict[str, Any]:
    """Format a raw Jira comment into a clean structured dictionary."""
    raw_body = c.get("body")
    if isinstance(raw_body, dict):
        body_text = _extract_adf_text(raw_body).strip()
    elif isinstance(raw_body, str):
        body_text = raw_body.strip()
    else:
        body_text = ""

    author_obj = c.get("author") or {}
    author_name = author_obj.get("displayName") or author_obj.get("name") or "Unknown"
    author_email = author_obj.get("emailAddress")

    update_author_obj = c.get("updateAuthor") or {}
    update_author_name = update_author_obj.get("displayName") or update_author_obj.get("name")

    res = {
        "id": str(c.get("id", "")),
        "author": author_name,
        "created": c.get("created"),
        "updated": c.get("updated"),
        "body": body_text,
    }
    if author_email:
        res["author_email"] = author_email
    if update_author_name and update_author_name != author_name:
        res["update_author"] = update_author_name
    return res


# ---------------------------------------------------------------------------
# Jira Tools Implementation
# ---------------------------------------------------------------------------

def _clean_jira_field_value(val: Any) -> Any:
    """Recursively converts Jira field values, ADF nodes, options, and lists into clean primitives."""
    if val is None:
        return None
    if isinstance(val, dict):
        if val.get("type") == "doc":
            text = _extract_adf_text(val).strip()
            return text if text else None
        if "value" in val and isinstance(val["value"], str):
            return val["value"]
        if "displayName" in val and isinstance(val["displayName"], str):
            return val["displayName"]
        if "name" in val and isinstance(val["name"], str):
            return val["name"]
        cleaned_dict = {}
        for k, v in val.items():
            if k in ("self", "iconUrl", "avatarUrls"):
                continue
            cleaned = _clean_jira_field_value(v)
            if cleaned is not None:
                cleaned_dict[k] = cleaned
        return cleaned_dict if cleaned_dict else None
    if isinstance(val, list):
        cleaned_list = [_clean_jira_field_value(item) for item in val]
        filtered = [item for item in cleaned_list if item is not None and item != ""]
        return filtered if filtered else None
    return val


def jira_get_issue(issue_key: str) -> Dict[str, Any]:
    """
    Fetch complete details for a Jira issue by its key (e.g. 'PROJ-123'), including
    summary, description (ADF parsed), status, assignee, reporter, parent,
    subtasks, issue links, custom fields, screen fields, comments, and attachments.
    """
    config = _get_config()
    v = config["api_version"]
    key = str(issue_key).strip().upper()
    
    # Request issue with editmeta and names expanded in a single call
    _, content, _ = _make_request("GET", f"/rest/api/{v}/issue/{urllib.parse.quote(key)}?expand=editmeta,names")
    data = json.loads(content.decode("utf-8"))
    fields = data.get("fields", {})
    names = data.get("names", {})
    editmeta = data.get("editmeta", {}).get("fields", {})

    raw_desc = fields.get("description")
    if isinstance(raw_desc, dict):
        description = _extract_adf_text(raw_desc).strip()
    elif isinstance(raw_desc, str):
        description = raw_desc.strip()
    else:
        description = ""

    attachments = []
    for att in fields.get("attachment", []):
        size_b = att.get("size", 0)
        attachments.append({
            "id": str(att.get("id")),
            "filename": att.get("filename"),
            "mimeType": att.get("mimeType"),
            "size_bytes": size_b,
            "size_human": _format_size(size_b),
            "created": att.get("created"),
            "author": att.get("author", {}).get("displayName"),
            "content_url": att.get("content"),
        })

    comments_data = fields.get("comment", {})
    raw_comments = list(comments_data.get("comments", []))
    total_comments = comments_data.get("total", len(raw_comments))

    # If the issue has more comments than returned in the initial payload,
    # fetch the remaining comments so the complete comment thread is available.
    if total_comments > len(raw_comments):
        try:
            _, c_content, _ = _make_request(
                "GET",
                f"/rest/api/{v}/issue/{urllib.parse.quote(key)}/comment",
                params={"maxResults": 100, "startAt": len(raw_comments)},
            )
            more_c_data = json.loads(c_content.decode("utf-8"))
            raw_comments.extend(more_c_data.get("comments", []))
        except Exception:
            pass

    comments = [_format_comment(c) for c in raw_comments]

    # Parent issue (for subtasks or nested issues)
    parent = None
    parent_obj = fields.get("parent")
    if parent_obj and isinstance(parent_obj, dict):
        parent = {
            "key": parent_obj.get("key"),
            "summary": parent_obj.get("fields", {}).get("summary"),
            "status": parent_obj.get("fields", {}).get("status", {}).get("name"),
            "issue_type": parent_obj.get("fields", {}).get("issuetype", {}).get("name"),
        }

    # Subtasks
    subtasks = []
    for st in fields.get("subtasks", []):
        if isinstance(st, dict):
            subtasks.append({
                "key": st.get("key"),
                "summary": st.get("fields", {}).get("summary"),
                "status": st.get("fields", {}).get("status", {}).get("name"),
                "priority": st.get("fields", {}).get("priority", {}).get("name") if st.get("fields", {}).get("priority") else None,
                "issue_type": st.get("fields", {}).get("issuetype", {}).get("name"),
            })

    # Issue links
    issue_links = []
    for link in fields.get("issuelinks", []):
        link_type = link.get("type", {})
        if "outwardIssue" in link:
            out_issue = link["outwardIssue"]
            issue_links.append({
                "relationship": link_type.get("outward", link_type.get("name")),
                "direction": "outward",
                "key": out_issue.get("key"),
                "summary": out_issue.get("fields", {}).get("summary"),
                "status": out_issue.get("fields", {}).get("status", {}).get("name"),
            })
        elif "inwardIssue" in link:
            in_issue = link["inwardIssue"]
            issue_links.append({
                "relationship": link_type.get("inward", link_type.get("name")),
                "direction": "inward",
                "key": in_issue.get("key"),
                "summary": in_issue.get("fields", {}).get("summary"),
                "status": in_issue.get("fields", {}).get("status", {}).get("name"),
            })

    # Screen fields & required fields (from editmeta)
    screen_fields = []
    required_fields = []
    for fid, finfo in editmeta.items():
        fname = finfo.get("name", names.get(fid, fid))
        is_req = finfo.get("required", False)
        if is_req:
            required_fields.append(fname)
        screen_fields.append({
            "id": fid,
            "name": fname,
            "required": is_req,
            "value": _clean_jira_field_value(fields.get(fid)),
        })

    # Populated custom fields (mapped by human-readable display name)
    custom_fields = {}
    for fid, raw_val in fields.items():
        if fid.startswith("customfield_"):
            display_name = names.get(fid, fid)
            cleaned = _clean_jira_field_value(raw_val)
            if cleaned is not None and cleaned != "" and cleaned != []:
                custom_fields[display_name] = cleaned

    issue_type_obj = fields.get("issuetype", {})
    project_obj = fields.get("project", {})

    return {
        "key": data.get("key"),
        "summary": fields.get("summary"),
        "status": fields.get("status", {}).get("name"),
        "issue_type": issue_type_obj.get("name"),
        "is_subtask": issue_type_obj.get("subtask", False),
        "priority": fields.get("priority", {}).get("name") if fields.get("priority") else None,
        "assignee": fields.get("assignee", {}).get("displayName") if fields.get("assignee") else "Unassigned",
        "reporter": fields.get("reporter", {}).get("displayName") if fields.get("reporter") else None,
        "created": fields.get("created"),
        "updated": fields.get("updated"),
        "due_date": fields.get("duedate"),
        "project": {
            "key": project_obj.get("key"),
            "name": project_obj.get("name"),
        } if project_obj else None,
        "parent": parent,
        "subtasks": subtasks,
        "issue_links": issue_links,
        "labels": fields.get("labels", []),
        "components": [c.get("name") for c in fields.get("components", []) if isinstance(c, dict) and "name" in c],
        "fix_versions": [v.get("name") for v in fields.get("fixVersions", []) if isinstance(v, dict) and "name" in v],
        "description": description,
        "required_fields": required_fields,
        "custom_fields": custom_fields,
        "screen_fields": screen_fields,
        "comment_count": len(comments),
        "comments": comments,
        "attachment_count": len(attachments),
        "attachments": attachments,
    }


def jira_get_comments(
    issue_key: str,
    max_results: int = 50,
    start_at: int = 0,
    order_by: str = "created",
) -> Dict[str, Any]:
    """
    Fetch comments for a specific Jira issue (e.g. 'PROJ-123') with pagination
    and sorting support.
    """
    config = _get_config()
    v = config["api_version"]
    key = str(issue_key).strip().upper()

    params: Dict[str, Any] = {
        "startAt": start_at,
        "maxResults": max_results,
    }
    if order_by:
        params["orderBy"] = order_by

    _, content, _ = _make_request(
        "GET",
        f"/rest/api/{v}/issue/{urllib.parse.quote(key)}/comment",
        params=params,
    )
    data = json.loads(content.decode("utf-8"))

    raw_comments = data.get("comments", [])
    comments = [_format_comment(c) for c in raw_comments]

    return {
        "issue_key": key,
        "total": data.get("total", len(comments)),
        "start_at": data.get("startAt", start_at),
        "max_results": data.get("maxResults", max_results),
        "returned": len(comments),
        "comments": comments,
    }


def jira_list_attachments(issue_key: str) -> List[Dict[str, Any]]:
    """
    List all attachments for a specific Jira issue (e.g. 'PROJ-123')
    with their ID, filename, size, and MIME type.
    """
    issue = jira_get_issue(issue_key)
    return issue.get("attachments", [])


def jira_download_attachment(
    attachment_id: str,
    filename: Optional[str] = None,
    output_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Download a single Jira attachment by its ID and save it to a local folder.
    """
    config = _get_config()
    v = config["api_version"]
    att_id = str(attachment_id).strip()

    if not filename:
        try:
            _, meta_bytes, _ = _make_request("GET", f"/rest/api/{v}/attachment/{att_id}")
            meta = json.loads(meta_bytes.decode("utf-8"))
            filename = meta.get("filename", f"attachment_{att_id}")
        except Exception:
            filename = f"attachment_{att_id}"

    dest_folder = _resolve_download_dir(output_dir)
    dest_folder.mkdir(parents=True, exist_ok=True)
    target_path = dest_folder / filename

    content_url = f"{config['host']}/rest/api/{v}/attachment/content/{att_id}"
    total_bytes = _download_stream(content_url, target_path)

    return {
        "status": "success",
        "attachment_id": att_id,
        "filename": filename,
        "saved_path": str(target_path),
        "size_bytes": total_bytes,
        "size_human": _format_size(total_bytes),
    }


def jira_download_all_attachments(
    issue_key: str,
    output_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Download all attachments associated with a Jira issue into a local directory.
    """
    issue = jira_get_issue(issue_key)
    attachments = issue.get("attachments", [])

    if not attachments:
        return {
            "issue_key": issue_key,
            "message": "No attachments found for this issue.",
            "downloaded_files": [],
        }

    base_dir = _resolve_download_dir(output_dir)
    target_dir = base_dir / issue_key.strip().upper()
    target_dir.mkdir(parents=True, exist_ok=True)
    results = []

    for att in attachments:
        att_id = att["id"]
        fname = att["filename"]
        res = jira_download_attachment(
            attachment_id=att_id,
            filename=fname,
            output_dir=str(target_dir),
        )
        results.append(res)

    return {
        "issue_key": issue_key,
        "total_downloaded": len(results),
        "target_directory": str(target_dir),
        "downloaded_files": results,
    }


def jira_read_text_attachment(
    attachment_id: str,
    max_chars: int = 50000,
) -> Dict[str, Any]:
    """
    Read the contents of a text-based attachment (logs, JSON, CSV, code, markdown, txt)
    directly into context without saving to disk.
    """
    config = _get_config()
    v = config["api_version"]
    att_id = str(attachment_id).strip()

    try:
        _, meta_bytes, _ = _make_request("GET", f"/rest/api/{v}/attachment/{att_id}")
        meta = json.loads(meta_bytes.decode("utf-8"))
        filename = meta.get("filename", f"attachment_{att_id}")
        mime_type = meta.get("mimeType", "text/plain")
    except Exception:
        filename = f"attachment_{att_id}"
        mime_type = "unknown"

    _, raw_content, _ = _make_request(
        "GET",
        f"/rest/api/{v}/attachment/content/{att_id}",
        headers={"Accept": "*/*"},
    )

    try:
        text_content = raw_content.decode("utf-8")
    except UnicodeDecodeError:
        try:
            text_content = raw_content.decode("latin-1")
        except Exception as e:
            return {
                "error": f"Failed to decode attachment as text: {str(e)}",
                "filename": filename,
                "mime_type": mime_type,
            }

    truncated = False
    if len(text_content) > max_chars:
        text_content = text_content[:max_chars]
        truncated = True

    return {
        "attachment_id": att_id,
        "filename": filename,
        "mime_type": mime_type,
        "character_count": len(text_content),
        "is_truncated": truncated,
        "content": text_content,
    }


SEARCH_FIELDS = "summary,status,priority,assignee,reporter,attachment,comment,created,updated,issuetype,parent,duedate,labels"


def _format_issue_summary(item: Dict[str, Any]) -> Dict[str, Any]:
    """Format one issue from a search or Agile issue list into a compact dictionary."""
    fields = item.get("fields", {}) or {}
    att_list = fields.get("attachment", []) or []
    comment_obj = fields.get("comment", {}) or {}
    comment_count = comment_obj.get("total", len(comment_obj.get("comments", [])))

    parent_obj = fields.get("parent")
    parent = None
    if parent_obj and isinstance(parent_obj, dict):
        parent = {
            "key": parent_obj.get("key"),
            "summary": parent_obj.get("fields", {}).get("summary"),
        }

    return {
        "key": item.get("key"),
        "summary": fields.get("summary"),
        "issue_type": (fields.get("issuetype") or {}).get("name"),
        "is_subtask": (fields.get("issuetype") or {}).get("subtask", False),
        "status": fields.get("status", {}).get("name") if fields.get("status") else None,
        "priority": fields.get("priority", {}).get("name") if fields.get("priority") else None,
        "assignee": fields.get("assignee", {}).get("displayName") if fields.get("assignee") else "Unassigned",
        "reporter": fields.get("reporter", {}).get("displayName") if fields.get("reporter") else None,
        "parent": parent,
        "due_date": fields.get("duedate"),
        "labels": fields.get("labels", []),
        "comment_count": comment_count,
        "attachment_count": len(att_list),
        "attachments": [
            {
                "id": str(a.get("id")),
                "filename": a.get("filename"),
                "size_human": _format_size(a.get("size", 0)),
            }
            for a in att_list
        ],
        "created": fields.get("created"),
        "updated": fields.get("updated"),
    }


# ---------------------------------------------------------------------------
# Jira Agile (Boards & Sprints) — /rest/agile/1.0, same path on Cloud and Server/DC
# ---------------------------------------------------------------------------

AGILE_BASE = "/rest/agile/1.0"


def _parse_board_id(board: Any) -> str:
    """Accept a numeric board ID or any Jira board URL (…/boards/579, ?rapidView=579)."""
    raw = str(board).strip()
    if raw.isdigit():
        return raw
    match = re.search(r"/boards?/(\d+)", raw) or re.search(r"[?&]rapidView=(\d+)", raw)
    if match:
        return match.group(1)
    raise ValueError(f"Cannot read a board ID from '{board}'. Pass the number or the board URL.")


def _agile_get(path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    _, content, _ = _make_request("GET", f"{AGILE_BASE}{path}", params=params)
    return json.loads(content.decode("utf-8")) if content else {}


def _board_columns(board_id: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]], Dict[str, str]]:
    """Return (raw configuration, columns, status_id -> column name)."""
    config = _agile_get(f"/board/{board_id}/configuration")
    columns = []
    status_to_column: Dict[str, str] = {}
    for col in (config.get("columnConfig") or {}).get("columns", []):
        status_ids = [str(s.get("id")) for s in col.get("statuses", []) if s.get("id") is not None]
        entry: Dict[str, Any] = {"name": col.get("name"), "status_ids": status_ids}
        if col.get("min") is not None:
            entry["min"] = col["min"]
        if col.get("max") is not None:
            entry["max"] = col["max"]
        columns.append(entry)
        for sid in status_ids:
            status_to_column[sid] = col.get("name")
    return config, columns, status_to_column


def _format_board_issue(item: Dict[str, Any], status_to_column: Dict[str, str]) -> Dict[str, Any]:
    """Issue summary plus the board column, sprint, epic and flag that the Agile API adds."""
    res = _format_issue_summary(item)
    fields = item.get("fields", {}) or {}
    status_id = str((fields.get("status") or {}).get("id", ""))
    if status_to_column:
        res["column"] = status_to_column.get(status_id)
    sprint = fields.get("sprint")
    if isinstance(sprint, dict):
        res["sprint"] = {"id": sprint.get("id"), "name": sprint.get("name"), "state": sprint.get("state")}
    epic = fields.get("epic")
    if isinstance(epic, dict):
        res["epic"] = {"key": epic.get("key"), "name": epic.get("name") or epic.get("summary")}
    if fields.get("flagged"):
        res["flagged"] = True
    return res


def _paged_issue_result(data: Dict[str, Any], issues: List[Dict[str, Any]]) -> Dict[str, Any]:
    res: Dict[str, Any] = {
        "total": data.get("total"),
        "start_at": data.get("startAt"),
        "max_results": data.get("maxResults"),
        "returned": len(issues),
        "issues": issues,
    }
    if data.get("isLast") is not None:
        res["is_last"] = data["isLast"]
    return res


def jira_get_board(board: str) -> Dict[str, Any]:
    """Board metadata, its saved filter (ID and JQL), columns with status mapping, and sprint support."""
    board_id = _parse_board_id(board)
    meta = _agile_get(f"/board/{board_id}")
    config, columns, _ = _board_columns(board_id)

    # Resolve column status IDs to names for readability.
    v = _get_config()["api_version"]
    status_names: Dict[str, str] = {}
    try:
        _, s_content, _ = _make_request("GET", f"/rest/api/{v}/status")
        for s in json.loads(s_content.decode("utf-8")):
            status_names[str(s.get("id"))] = s.get("name")
    except Exception:
        pass
    for col in columns:
        col["statuses"] = [status_names.get(sid, sid) for sid in col["status_ids"]]

    filter_obj = config.get("filter") or {}
    filter_info: Dict[str, Any] = {"id": str(filter_obj.get("id")) if filter_obj.get("id") else None}
    if filter_info["id"]:
        try:
            _, f_content, _ = _make_request("GET", f"/rest/api/{v}/filter/{filter_info['id']}")
            f_data = json.loads(f_content.decode("utf-8"))
            filter_info["name"] = f_data.get("name")
            filter_info["jql"] = f_data.get("jql")
        except Exception as exc:
            filter_info["error"] = f"Filter not readable: {type(exc).__name__}"

    sub_query = (config.get("subQuery") or {}).get("query")
    location = meta.get("location") or {}
    estimation = config.get("estimation") or {}

    return {
        "id": meta.get("id"),
        "name": meta.get("name"),
        "type": meta.get("type"),
        "supports_sprints": meta.get("type") == "scrum",
        "location": {
            k: location.get(k)
            for k in ("type", "projectKey", "projectName", "displayName", "name")
            if location.get(k)
        } or None,
        "filter": filter_info,
        "sub_query": sub_query,
        "columns": columns,
        "estimation_field": (estimation.get("field") or {}).get("displayName"),
        "ranking_field_id": (config.get("ranking") or {}).get("rankCustomFieldId"),
    }


def jira_board_issues(
    board: str,
    scope: str = "board",
    jql: Optional[str] = None,
    max_results: int = 50,
    start_at: int = 0,
) -> Dict[str, Any]:
    """Issues on a board in rank order, each tagged with its board column."""
    board_id = _parse_board_id(board)
    scope_paths = {"board": "issue", "backlog": "backlog"}
    if scope not in scope_paths:
        raise ValueError("scope must be 'board' or 'backlog'.")

    try:
        _, _, status_to_column = _board_columns(board_id)
    except Exception:
        status_to_column = {}

    data = _agile_get(
        f"/board/{board_id}/{scope_paths[scope]}",
        params={
            "startAt": start_at,
            "maxResults": max_results,
            "jql": jql,
            "fields": SEARCH_FIELDS + ",sprint,epic,flagged",
        },
    )
    issues = [_format_board_issue(i, status_to_column) for i in data.get("issues", [])]
    res = _paged_issue_result(data, issues)
    res["board_id"] = board_id
    res["scope"] = scope
    return res


def jira_board_sprints(
    board: str,
    state: str = "active,future",
    max_results: int = 50,
    start_at: int = 0,
) -> Dict[str, Any]:
    """Sprints on a scrum board, filtered by state."""
    board_id = _parse_board_id(board)
    try:
        data = _agile_get(
            f"/board/{board_id}/sprint",
            params={"state": state or None, "startAt": start_at, "maxResults": max_results},
        )
    except RuntimeError as exc:
        if "HTTP Error 400" in str(exc):
            return {
                "board_id": board_id,
                "supports_sprints": False,
                "message": "This board does not support sprints (kanban). Use jira_board_issues instead.",
            }
        raise

    sprints = [
        {
            "id": s.get("id"),
            "name": s.get("name"),
            "state": s.get("state"),
            "goal": s.get("goal") or None,
            "start_date": s.get("startDate"),
            "end_date": s.get("endDate"),
            "complete_date": s.get("completeDate"),
        }
        for s in data.get("values", [])
    ]
    return {
        "board_id": board_id,
        "supports_sprints": True,
        "start_at": data.get("startAt"),
        "max_results": data.get("maxResults"),
        "is_last": data.get("isLast"),
        "returned": len(sprints),
        "sprints": sprints,
    }


def jira_sprint_issues(
    sprint_id: str,
    board: Optional[str] = None,
    jql: Optional[str] = None,
    max_results: int = 50,
    start_at: int = 0,
) -> Dict[str, Any]:
    """Issues in one sprint; pass the board to tag each issue with its column."""
    sid = str(sprint_id).strip()
    status_to_column: Dict[str, str] = {}
    if board:
        try:
            _, _, status_to_column = _board_columns(_parse_board_id(board))
        except Exception:
            pass

    data = _agile_get(
        f"/sprint/{sid}/issue",
        params={
            "startAt": start_at,
            "maxResults": max_results,
            "jql": jql,
            "fields": SEARCH_FIELDS + ",sprint,epic,flagged",
        },
    )
    issues = [_format_board_issue(i, status_to_column) for i in data.get("issues", [])]
    res = _paged_issue_result(data, issues)
    res["sprint_id"] = sid
    return res


# ---------------------------------------------------------------------------
# Jira Dashboards — gadgets and their saved settings (/rest/api/{v}/dashboard)
# ---------------------------------------------------------------------------

def _parse_dashboard_id(dashboard: Any) -> str:
    """Accept a numeric dashboard ID or a dashboard URL (…/dashboards/12634, ?selectPageId=12634)."""
    raw = str(dashboard).strip()
    if raw.isdigit():
        return raw
    match = re.search(r"/dashboards?/(\d+)", raw) or re.search(r"[?&]selectPageId=(\d+)", raw)
    if match:
        return match.group(1)
    raise ValueError(f"Cannot read a dashboard ID from '{dashboard}'. Pass the number or the dashboard URL.")


def _api_get(path: str, params: Optional[Dict[str, Any]] = None) -> Any:
    v = _get_config()["api_version"]
    _, content, _ = _make_request("GET", f"/rest/api/{v}{path}", params=params)
    return json.loads(content.decode("utf-8")) if content else {}


def _find_gadget_source(props: Any) -> Optional[Dict[str, str]]:
    """Find the filter, project or JQL a gadget reads from inside its saved properties."""
    if isinstance(props, dict):
        for k, val in props.items():
            lk = k.lower()
            if isinstance(val, str) and lk == "jql" and val.strip():
                return {"type": "jql", "value": val.strip()}
            if lk in ("filterid", "savedfilterid") and str(val).strip().isdigit():
                return {"type": "filter", "value": str(val).strip()}
        for val in props.values():
            found = _find_gadget_source(val)
            if found:
                return found
        return None
    if isinstance(props, list):
        for val in props:
            found = _find_gadget_source(val)
            if found:
                return found
        return None
    if isinstance(props, str):
        s = props.strip()
        if s.startswith("{") or s.startswith("["):
            try:
                return _find_gadget_source(json.loads(s))
            except ValueError:
                pass
        m = re.fullmatch(r"(filter|project|jql)-(.+)", s)
        if m:
            value = urllib.parse.unquote_plus(m.group(2)) if m.group(1) == "jql" else m.group(2)
            return {"type": m.group(1), "value": value}
    return None


def _gadget_properties(dashboard_id: str, gadget_id: str) -> Dict[str, Any]:
    keys = _api_get(f"/dashboard/{dashboard_id}/items/{gadget_id}/properties").get("keys", [])
    props: Dict[str, Any] = {}
    for k in keys:
        key = k.get("key")
        if not key:
            continue
        try:
            props[key] = _api_get(
                f"/dashboard/{dashboard_id}/items/{gadget_id}/properties/{urllib.parse.quote(key)}"
            ).get("value")
        except Exception as exc:
            props[key] = f"<unreadable: {type(exc).__name__}>"
    return props


def jira_get_dashboard(
    dashboard: str,
    include_issues: bool = False,
    max_issues_per_gadget: int = 10,
) -> Dict[str, Any]:
    """Dashboard details, every gadget with its saved settings and data source, and optionally each source's issues."""
    dashboard_id = _parse_dashboard_id(dashboard)
    meta = _api_get(f"/dashboard/{dashboard_id}")

    try:
        raw_gadgets = _api_get(f"/dashboard/{dashboard_id}/gadget").get("gadgets", [])
        gadget_error = None
    except FileNotFoundError:
        raw_gadgets = []
        gadget_error = "Gadget listing not available on this Jira version (needs Jira Cloud)."

    filter_cache: Dict[str, Dict[str, Any]] = {}
    gadgets = []
    for g in sorted(raw_gadgets, key=lambda x: ((x.get("position") or {}).get("column", 0), (x.get("position") or {}).get("row", 0))):
        gid = str(g.get("id"))
        entry: Dict[str, Any] = {
            "id": gid,
            "title": g.get("title"),
            "type": g.get("moduleKey") or g.get("uri"),
            "position": g.get("position"),
        }
        try:
            props = _gadget_properties(dashboard_id, gid)
        except Exception as exc:
            props = {}
            entry["properties_error"] = f"{type(exc).__name__}: {exc}"[:200]
        entry["properties"] = props

        source = _find_gadget_source(props)
        jql = None
        if source:
            if source["type"] == "filter":
                fid = source["value"]
                if fid not in filter_cache:
                    try:
                        f = _api_get(f"/filter/{fid}")
                        filter_cache[fid] = {"id": fid, "name": f.get("name"), "jql": f.get("jql")}
                    except Exception as exc:
                        filter_cache[fid] = {"id": fid, "error": f"Filter not readable: {type(exc).__name__}"}
                entry["source"] = {"type": "filter", **filter_cache[fid]}
                jql = filter_cache[fid].get("jql")
            elif source["type"] == "project":
                jql = f"project = {source['value']}"
                entry["source"] = {"type": "project", "id": source["value"], "jql": jql}
            else:
                jql = source["value"]
                entry["source"] = {"type": "jql", "jql": jql}

        if include_issues and jql:
            try:
                found = jira_search_issues(jql=jql, max_results=max_issues_per_gadget)
                entry["issues"] = {
                    "returned": found["returned"],
                    "is_last": found.get("is_last"),
                    "items": [
                        {k: i.get(k) for k in ("key", "summary", "status", "assignee", "priority", "updated")}
                        for i in found["issues"]
                    ],
                }
            except Exception as exc:
                entry["issues"] = {"error": f"{type(exc).__name__}: {exc}"[:300]}
        gadgets.append(entry)

    res: Dict[str, Any] = {
        "id": meta.get("id"),
        "name": meta.get("name"),
        "description": meta.get("description") or None,
        "owner": (meta.get("owner") or {}).get("displayName"),
        "view_url": meta.get("view"),
        "share_permissions": [
            p.get("type") + (f":{(p.get('project') or p.get('group') or {}).get('name')}" if (p.get("project") or p.get("group")) else "")
            for p in meta.get("sharePermissions", []) if p.get("type")
        ],
        "gadget_count": len(gadgets),
        "gadgets": gadgets,
    }
    if gadget_error:
        res["gadget_error"] = gadget_error
    return res


def jira_search_issues(
    jql: str,
    max_results: int = 10,
    start_at: Optional[int] = None,
    next_page_token: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Search Jira issues using JQL (Jira Query Language).
    Supports both Jira Cloud (/search/jql with nextPageToken) and Jira Server/DC (/search with startAt).
    """
    config = _get_config()
    v = config["api_version"]
    params: Dict[str, Any] = {
        "jql": jql,
        "maxResults": max_results,
        "fields": SEARCH_FIELDS,
    }
    if start_at is not None:
        params["startAt"] = start_at
    if next_page_token:
        params["nextPageToken"] = next_page_token

    # Atlassian Jira Cloud uses /rest/api/{v}/search/jql (CHANGE-2046)
    # Jira Server / Data Center uses /rest/api/{v}/search
    primary_path = f"/rest/api/{v}/search/jql"
    fallback_path = f"/rest/api/{v}/search"

    content = None
    try:
        _, content, _ = _make_request("GET", primary_path, params=params)
    except FileNotFoundError:
        # Fall back to legacy /search only if /search/jql endpoint does not exist (404)
        _, content, _ = _make_request("GET", fallback_path, params=params)

    data = json.loads(content.decode("utf-8"))

    issues = [_format_issue_summary(item) for item in data.get("issues", [])]

    res: Dict[str, Any] = {
        "returned": len(issues),
        "issues": issues,
    }
    if "total" in data and data["total"] is not None:
        res["total"] = data["total"]
    if "startAt" in data and data["startAt"] is not None:
        res["start_at"] = data["startAt"]
    if "nextPageToken" in data and data["nextPageToken"] is not None:
        res["next_page_token"] = data["nextPageToken"]
    if "isLast" in data and data["isLast"] is not None:
        res["is_last"] = data["isLast"]

    return res


def jira_configure(
    host: str,
    email: Optional[str] = None,
    api_token: Optional[str] = None,
    pat: Optional[str] = None,
    download_dir: Optional[str] = None,
    api_version: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Self-Service In-Chat Configuration Tool for Jira Reader.
    Configure Jira connection credentials directly from chat without running terminal scripts.
    Automatically tests authentication and persists credentials to ~/.jira.env and local .env.
    """
    clean_host = host.strip().rstrip("/")
    clean_email = (email or "").strip()
    clean_token = (api_token or "").strip()
    clean_pat = (pat or "").strip()
    clean_dir = (download_dir or "").strip() or ".scratchpads/downloads"
    clean_ver = (api_version or "").strip() or ("2" if clean_pat else "3")

    if not clean_host:
        return {"status": "ERROR", "message": "Jira host URL is required (e.g. 'https://anchantoplan.atlassian.net')."}

    if not clean_pat and (not clean_email or not clean_token):
        return {
            "status": "ERROR",
            "message": (
                "Please provide either:\n"
                "1. Jira Cloud: email and api_token (generate at https://id.atlassian.com/manage-profile/security/api-tokens)\n"
                "2. Jira Server/Data Center: pat (Personal Access Token)"
            )
        }

    env_content = f"""# Jira Reader MCP Configuration (.env)
JIRA_HOST={clean_host}
JIRA_DOWNLOAD_DIR={clean_dir}
JIRA_API_VERSION={clean_ver}
"""
    if clean_pat:
        env_content += f"JIRA_PAT={clean_pat}\n"
    else:
        env_content += f"JIRA_EMAIL={clean_email}\nJIRA_API_TOKEN={clean_token}\n"

    # Save to global discovery and local .env
    for target_path in [_get_global_env_path(), Path(__file__).resolve().parent / ".env"]:
        try:
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(env_content)
            target_path.chmod(0o600)
        except Exception:
            pass

    # Update current process environment
    os.environ["JIRA_HOST"] = clean_host
    os.environ["JIRA_DOWNLOAD_DIR"] = clean_dir
    os.environ["JIRA_API_VERSION"] = clean_ver
    if clean_pat:
        os.environ["JIRA_PAT"] = clean_pat
        os.environ.pop("JIRA_EMAIL", None)
        os.environ.pop("JIRA_API_TOKEN", None)
    else:
        os.environ["JIRA_EMAIL"] = clean_email
        os.environ["JIRA_API_TOKEN"] = clean_token
        os.environ.pop("JIRA_PAT", None)

    # Test connection
    try:
        status, body, _ = _make_request("GET", "/rest/api/3/myself" if clean_ver == "3" else "/rest/api/2/myself", timeout=15)
        if status in (200, 201):
            user_data = json.loads(body.decode("utf-8"))
            display_name = user_data.get("displayName") or user_data.get("name") or "Authenticated User"
            return {
                "status": "CONFIGURED_AND_CONNECTED",
                "message": f"Successfully connected to Jira as '{display_name}' at {clean_host}.",
                "user": display_name,
            }
        else:
            return {
                "status": "CONFIGURED_BUT_FAILED",
                "message": f"Saved credentials, but Jira returned HTTP {status}: {body.decode('utf-8')[:200]}",
            }
    except Exception as exc:
        return {
            "status": "CONFIGURED_BUT_FAILED",
            "message": f"Saved credentials, but connection test failed: {exc}",
        }


# ---------------------------------------------------------------------------
# MCP Tool Schemas & Tool Registry
# ---------------------------------------------------------------------------

TOOLS_SPEC = [
    {
        "name": "jira_configure",
        "description": "Self-service in-chat configuration tool. Use when Jira credentials are missing or need updating. Configures host, email, and API token directly from chat.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "host": {
                    "type": "string",
                    "description": "Jira base URL, e.g. 'https://anchantoplan.atlassian.net'.",
                },
                "email": {
                    "type": "string",
                    "description": "(For Jira Cloud) Atlassian login email address.",
                },
                "api_token": {
                    "type": "string",
                    "description": "(For Jira Cloud) API token generated at https://id.atlassian.com/manage-profile/security/api-tokens.",
                },
                "pat": {
                    "type": "string",
                    "description": "(For Jira Server / Data Center) Personal Access Token.",
                },
                "download_dir": {
                    "type": "string",
                    "description": "(Optional) Attachment download directory (defaults to .scratchpads/downloads).",
                },
            },
            "required": ["host"],
        },
        "handler": jira_configure,
    },
    {
        "name": "jira_get_issue",
        "description": "Fetch complete details for a Jira issue by its key (e.g. 'PROJ-123'), including summary, description (ADF parsed), status, assignee, reporter, parent, subtasks, issue links, custom fields, screen fields with required flags, comments list with author details, and metadata of all attachments.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "issue_key": {
                    "type": "string",
                    "description": "The Jira issue key, e.g. 'PROJ-123'.",
                }
            },
            "required": ["issue_key"],
        },
        "handler": jira_get_issue,
    },
    {
        "name": "jira_get_comments",
        "description": "Fetch all comments or a paginated list of comments for a Jira issue (e.g. 'PROJ-123'), with ADF-parsed Markdown bodies and author metadata.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "issue_key": {
                    "type": "string",
                    "description": "The Jira issue key, e.g. 'PROJ-123'.",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of comments to return (default: 50).",
                    "default": 50,
                },
                "start_at": {
                    "type": "integer",
                    "description": "Index of the first comment to return (0-indexed offset for pagination, default: 0).",
                    "default": 0,
                },
                "order_by": {
                    "type": "string",
                    "description": "Order comments by date: 'created' (oldest first, default) or '-created' (newest first).",
                    "default": "created",
                },
            },
            "required": ["issue_key"],
        },
        "handler": jira_get_comments,
    },
    {
        "name": "jira_list_attachments",
        "description": "List all attachments for a specific Jira issue with their ID, filename, size, and MIME type.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "issue_key": {
                    "type": "string",
                    "description": "The Jira issue key, e.g. 'PROJ-123'.",
                }
            },
            "required": ["issue_key"],
        },
        "handler": jira_list_attachments,
    },
    {
        "name": "jira_download_attachment",
        "description": "Download a single Jira attachment by its ID and save it to the project download directory (JIRA_DOWNLOAD_DIR).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "attachment_id": {
                    "type": "string",
                    "description": "The numerical ID of the attachment in Jira (e.g. '10045').",
                },
                "filename": {
                    "type": "string",
                    "description": "(Optional) Destination filename. If omitted, fetched automatically from Jira metadata.",
                },
                "output_dir": {
                    "type": "string",
                    "description": "(Optional) Target directory to save the file. Defaults to project downloads or system temp if outside a project.",
                },
            },
            "required": ["attachment_id"],
        },
        "handler": jira_download_attachment,
    },
    {
        "name": "jira_download_all_attachments",
        "description": "Download all attachments associated with a Jira issue into a folder under JIRA_DOWNLOAD_DIR or system temp.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "issue_key": {
                    "type": "string",
                    "description": "The Jira issue key (e.g. 'PROJ-123').",
                },
                "output_dir": {
                    "type": "string",
                    "description": "(Optional) Base directory to save files. Defaults to project downloads or system temp if outside a project.",
                },
            },
            "required": ["issue_key"],
        },
        "handler": jira_download_all_attachments,
    },
    {
        "name": "jira_read_text_attachment",
        "description": "Read the contents of a text-based attachment (logs, JSON, CSV, code, markdown, txt) directly into memory context without writing to disk.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "attachment_id": {
                    "type": "string",
                    "description": "The Jira attachment ID.",
                },
                "max_chars": {
                    "type": "integer",
                    "description": "Maximum characters to return (default: 50,000 to prevent context overflow).",
                    "default": 50000,
                },
            },
            "required": ["attachment_id"],
        },
        "handler": jira_read_text_attachment,
    },
    {
        "name": "jira_search_issues",
        "description": "Search Jira issues using JQL (Jira Query Language).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "jql": {
                    "type": "string",
                    "description": "The JQL query string (e.g. 'project = PROJ AND status = \"In Progress\"'). Note: Jira Cloud requires bounded queries (e.g. with project, text search, or date filter).",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of issues to return (default: 10).",
                    "default": 10,
                },
                "start_at": {
                    "type": "integer",
                    "description": "(Optional) The starting index for pagination (used by Jira Server / Data Center).",
                },
                "next_page_token": {
                    "type": "string",
                    "description": "(Optional) Cursor pagination token returned from previous search call (used by Jira Cloud).",
                },
            },
            "required": ["jql"],
        },
        "handler": jira_search_issues,
    },
    {
        "name": "jira_get_board",
        "description": "Read a Jira board's setup: name, type (scrum/kanban), location, saved filter ID and JQL, sub-query, columns with their statuses, and estimation field. Accepts the board ID or any board URL.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "board": {
                    "type": "string",
                    "description": "Board ID (e.g. '579') or board URL (e.g. 'https://anchantoplan.atlassian.net/jira/people/<id>/boards/579').",
                }
            },
            "required": ["board"],
        },
        "handler": jira_get_board,
    },
    {
        "name": "jira_board_issues",
        "description": "List issues on a Jira board in board rank order, each tagged with its board column, sprint, epic and flag. scope='board' returns everything on the board; scope='backlog' returns only backlog issues (scrum).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "board": {
                    "type": "string",
                    "description": "Board ID or board URL.",
                },
                "scope": {
                    "type": "string",
                    "enum": ["board", "backlog"],
                    "description": "'board' (default) or 'backlog'.",
                    "default": "board",
                },
                "jql": {
                    "type": "string",
                    "description": "(Optional) Extra JQL to narrow the board's issues, e.g. 'assignee = currentUser()'.",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum issues to return (default: 50).",
                    "default": 50,
                },
                "start_at": {
                    "type": "integer",
                    "description": "Index of the first issue (pagination, default: 0).",
                    "default": 0,
                },
            },
            "required": ["board"],
        },
        "handler": jira_board_issues,
    },
    {
        "name": "jira_board_sprints",
        "description": "List sprints on a scrum board with state, goal and dates. Returns supports_sprints=false for kanban boards.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "board": {
                    "type": "string",
                    "description": "Board ID or board URL.",
                },
                "state": {
                    "type": "string",
                    "description": "Comma-separated states: active, future, closed (default: 'active,future').",
                    "default": "active,future",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum sprints to return (default: 50).",
                    "default": 50,
                },
                "start_at": {
                    "type": "integer",
                    "description": "Index of the first sprint (pagination, default: 0).",
                    "default": 0,
                },
            },
            "required": ["board"],
        },
        "handler": jira_board_sprints,
    },
    {
        "name": "jira_sprint_issues",
        "description": "List issues in one sprint. Pass the board to tag each issue with its board column.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "sprint_id": {
                    "type": "string",
                    "description": "Sprint ID from jira_board_sprints.",
                },
                "board": {
                    "type": "string",
                    "description": "(Optional) Board ID or URL, used only to map statuses to columns.",
                },
                "jql": {
                    "type": "string",
                    "description": "(Optional) Extra JQL to narrow the sprint's issues.",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum issues to return (default: 50).",
                    "default": 50,
                },
                "start_at": {
                    "type": "integer",
                    "description": "Index of the first issue (pagination, default: 0).",
                    "default": 0,
                },
            },
            "required": ["sprint_id"],
        },
        "handler": jira_sprint_issues,
    },
    {
        "name": "jira_get_dashboard",
        "description": "Read a Jira dashboard: name, owner, sharing, and every gadget with its title, type, position, saved settings and data source (filter name + JQL, project, or JQL). Set include_issues=true to also run each gadget's JQL and return its issues. Rendered chart values are not available through the API.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "dashboard": {
                    "type": "string",
                    "description": "Dashboard ID (e.g. '12634') or dashboard URL (e.g. 'https://anchantoplan.atlassian.net/jira/dashboards/12634').",
                },
                "include_issues": {
                    "type": "boolean",
                    "description": "Run each gadget's JQL and include its issues (default: false).",
                    "default": False,
                },
                "max_issues_per_gadget": {
                    "type": "integer",
                    "description": "Issues per gadget when include_issues is true (default: 10).",
                    "default": 10,
                },
            },
            "required": ["dashboard"],
        },
        "handler": jira_get_dashboard,
    },
]

TOOL_HANDLERS = {tool["name"]: tool["handler"] for tool in TOOLS_SPEC}


# ---------------------------------------------------------------------------
# Universal Stdio JSON-RPC 2.0 MCP Protocol Server
# ---------------------------------------------------------------------------

def _send_json_rpc(response_dict: Dict[str, Any]) -> None:
    """Send a JSON-RPC response to stdout followed by newline and flush immediately."""
    payload = json.dumps(response_dict, ensure_ascii=False)
    sys.stdout.write(payload + "\n")
    sys.stdout.flush()


def _handle_json_rpc_message(msg: Dict[str, Any]) -> None:
    """Handle a single MCP JSON-RPC 2.0 request or notification."""
    msg_id = msg.get("id")
    method = msg.get("method")
    params = msg.get("params", {})

    # Notification (no id field)
    if msg_id is None:
        if method == "notifications/initialized":
            sys.stderr.write(f"[{SERVER_NAME}] Client initialized successfully.\n")
        return

    # Request handlers
    if method == "initialize":
        _send_json_rpc({
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {
                    "tools": {
                        "listChanged": False,
                    }
                },
                "serverInfo": {
                    "name": SERVER_NAME,
                    "version": SERVER_VERSION,
                },
            },
        })
        return

    if method == "ping":
        _send_json_rpc({
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {},
        })
        return

    if method == "tools/list":
        is_configured = False
        try:
            cfg = _get_config()
            is_configured = bool(cfg.get("host") and (cfg.get("pat") or (cfg.get("email") and cfg.get("api_token"))))
        except Exception:
            is_configured = False

        tools_list = []
        for t in TOOLS_SPEC:
            desc = t["description"]
            if not is_configured:
                if t["name"] == "jira_configure":
                    desc = "👉 [SETUP REQUIRED - START HERE] " + desc
                else:
                    desc = "⚠️ [UNCONFIGURED - Run /config or call jira_configure first] " + desc

            tools_list.append({
                "name": t["name"],
                "description": desc,
                "inputSchema": t["inputSchema"],
            })

        _send_json_rpc({
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "tools": tools_list,
            },
        })
        return

    if method == "resources/list":
        is_configured = False
        try:
            cfg = _get_config()
            is_configured = bool(cfg.get("host") and (cfg.get("pat") or (cfg.get("email") and cfg.get("api_token"))))
        except Exception:
            is_configured = False

        status_text = "Connected" if is_configured else "⚠️ UNCONFIGURED (Run /config)"
        _send_json_rpc({
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "resources": [
                    {
                        "uri": "jira://status",
                        "name": f"Jira Connection Status: {status_text}",
                        "description": "Current authentication and connection status for Jira Reader.",
                        "mimeType": "application/json",
                    }
                ],
            },
        })
        return

    if method == "prompts/list":
        _send_json_rpc({
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "prompts": [
                    {
                        "name": "setup",
                        "description": "Configure credentials for Jira Reader and Kibana Explorer.",
                    }
                ],
            },
        })
        return

    if method == "tools/call":
        tool_name = params.get("name")
        tool_args = params.get("arguments", {})

        if tool_name not in TOOL_HANDLERS:
            _send_json_rpc({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Error: Unknown tool '{tool_name}'",
                        }
                    ],
                    "isError": True,
                },
            })
            return

        handler = TOOL_HANDLERS[tool_name]
        try:
            result = handler(**tool_args)
            text_output = json.dumps(result, indent=2, ensure_ascii=False) if isinstance(result, (dict, list)) else str(result)
            _send_json_rpc({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": text_output,
                        }
                    ],
                    "isError": False,
                },
            })
        except Exception as exc:
            _send_json_rpc({
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Tool execution failed: {type(exc).__name__}: {str(exc)}",
                        }
                    ],
                    "isError": True,
                },
            })
        return

    if method in ("resources/list", "prompts/list"):
        field_name = method.split("/")[0]
        _send_json_rpc({
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                field_name: [],
            },
        })
        return

    # Method not found
    _send_json_rpc({
        "jsonrpc": "2.0",
        "id": msg_id,
        "error": {
            "code": -32601,
            "message": f"Method '{method}' not found",
        },
    })


def run_stdio_server() -> None:
    """Main JSON-RPC stdio event loop."""
    try:
        cfg = _get_config()
    except Exception:
        sys.stderr.write(f"[{SERVER_NAME}] ⚠️ Notice: Jira credentials not configured yet. Run /config to setup.\n")

    sys.stderr.write(f"[{SERVER_NAME}] Starting stdio transport (MCP v{MCP_PROTOCOL_VERSION})...\n")
    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break
            line = line.strip()
            if not line:
                continue

            # Handle possible Content-Length header prefix if sent by certain clients
            if line.startswith("Content-Length:"):
                length = int(line.split(":", 1)[1].strip())
                # Read empty line separating header from body
                sys.stdin.readline()
                body = sys.stdin.read(length)
                msg = json.loads(body)
            else:
                msg = json.loads(line)

            if isinstance(msg, dict):
                _handle_json_rpc_message(msg)
        except (KeyboardInterrupt, BrokenPipeError):
            break
        except json.JSONDecodeError as err:
            sys.stderr.write(f"[{SERVER_NAME}] JSON decode error: {err}\n")
        except Exception as exc:
            sys.stderr.write(f"[{SERVER_NAME}] Unexpected loop error: {exc}\n")


# ---------------------------------------------------------------------------
# CLI Diagnostics & Self-Test Mode
# ---------------------------------------------------------------------------

def run_test_mode() -> None:
    """Test Jira connectivity and print diagnostic status."""
    print(f"=== {SERVER_NAME} v{SERVER_VERSION} Diagnostics ===")
    try:
        cfg = _get_config()
        print(f"✔ Host: {cfg['host']}")
        if cfg['pat']:
            print("✔ Auth: Personal Access Token (PAT)")
        else:
            print(f"✔ Auth: Basic Auth ({cfg['email']} + API Token)")
        print(f"✔ API Version: {cfg['api_version']}")
        print(f"✔ Download Directory: {_resolve_download_dir()}")

        print("\nTesting connectivity to Jira API...")
        v = cfg["api_version"]
        status, content, _ = _make_request("GET", f"/rest/api/{v}/myself")
        if status == 200:
            user_data = json.loads(content.decode("utf-8"))
            display_name = user_data.get("displayName", "Unknown")
            email = user_data.get("emailAddress", "N/A")
            active = user_data.get("active", True)
            print(f"✔ Connection successful! Logged in as: {display_name} ({email}) [Active: {active}]")
        else:
            print(f"⚠ Unexpected response status: {status}")
    except Exception as exc:
        print(f"✖ Diagnostics failed: {type(exc).__name__}: {exc}")
        sys.exit(1)


def run_init_env() -> None:
    """Create a default .env file in the script directory if it doesn't already exist."""
    script_dir = Path(__file__).resolve().parent
    target = script_dir / ".env"
    if target.exists():
        print(f"ℹ .env file already exists at: {target}")
        return

    example_candidates = [
        script_dir / ".env.example",
        script_dir / ".env.sample",
    ]
    content = None
    for cand in example_candidates:
        if cand.is_file():
            content = cand.read_text(encoding="utf-8")
            break

    if not content:
        content = DEFAULT_ENV_TEMPLATE

    target.write_text(content, encoding="utf-8")
    print(f"✔ Created .env template at: {target}")
    print("Please edit the file and fill in your Jira credentials.")


def run_tools_list_cli() -> None:
    """Print registered tools in JSON format."""
    out = [
        {
            "name": t["name"],
            "description": t["description"],
            "inputSchema": t["inputSchema"],
        }
        for t in TOOLS_SPEC
    ]
    print(json.dumps(out, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(
        description=f"{SERVER_NAME} - Universal Zero-Dependency Jira MCP Server"
    )
    parser.add_argument("--test", action="store_true", help="Test Jira connectivity and auth")
    parser.add_argument("--init-env", action="store_true", help="Create a .env file template")
    parser.add_argument("--tools", action="store_true", help="List registered MCP tools and schemas")
    parser.add_argument("--stdio", action="store_true", help="Run MCP server over stdio (default)")

    args = parser.parse_args()

    if args.test:
        run_test_mode()
    elif args.init_env:
        run_init_env()
    elif args.tools:
        run_tools_list_cli()
    else:
        run_stdio_server()


if __name__ == "__main__":
    main()
