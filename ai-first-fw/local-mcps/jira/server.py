#!/usr/bin/env python3
"""
Jira Attachment MCP Server
---------------------------
A local Model Context Protocol (MCP) server providing Jira tools with full
attachment retrieval, download, and inspection capabilities.
"""

import os
import sys
import json
from pathlib import Path
from typing import Dict, Any, List, Optional

# Attempt to load environment variables from a nearby .env file if available
try:
    from dotenv import load_dotenv
    # Load .env from current directory or script directory
    env_path = Path(__file__).resolve().parent / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
    else:
        load_dotenv()
except ImportError:
    pass

# Import FastMCP (supports both 'mcp' SDK and standalone 'fastmcp')
try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    try:
        from fastmcp import FastMCP
    except ImportError:
        sys.stderr.write(
            "Error: 'mcp' package is not installed.\n"
            "Install it via: pip install mcp requests python-dotenv\n"
        )
        sys.exit(1)

import requests

# Initialize FastMCP Server
mcp = FastMCP("jira-attachment-server")

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent


def _resolve_download_dir(custom_path: Optional[str] = None) -> Path:
    """Resolve download path safely relative to current working directory or project root."""
    cwd = Path.cwd()
    base_root = cwd if str(cwd) != "/" else PROJECT_ROOT

    if custom_path:
        p = Path(custom_path).expanduser()
        if not p.is_absolute():
            return (base_root / p).resolve()
        return p.resolve()

    env_dir = os.environ.get("JIRA_DOWNLOAD_DIR", "").strip()
    if env_dir:
        p = Path(env_dir).expanduser()
        if not p.is_absolute():
            return (base_root / p).resolve()
        return p.resolve()

    return (base_root / "downloads").resolve()


def _get_config() -> Dict[str, str]:
    """Retrieve and validate Jira configuration from environment variables."""
    host = os.environ.get("JIRA_HOST", "").rstrip("/")
    email = os.environ.get("JIRA_EMAIL", "").strip()
    api_token = os.environ.get("JIRA_API_TOKEN", "").strip()
    pat = os.environ.get("JIRA_PAT", "").strip()
    api_version = os.environ.get("JIRA_API_VERSION", "3").strip()

    if not host:
        raise ValueError(
            "JIRA_HOST environment variable is missing. "
            "Please set JIRA_HOST (e.g. https://your-domain.atlassian.net)."
        )

    if not pat and (not email or not api_token):
        raise ValueError(
            "Jira authentication missing. Please provide either:\n"
            "  1. JIRA_EMAIL and JIRA_API_TOKEN (for Jira Cloud)\n"
            "  2. JIRA_PAT (Personal Access Token for Jira Server/Data Center)"
        )

    return {
        "host": host,
        "email": email,
        "api_token": api_token,
        "pat": pat,
        "api_version": api_version,
    }


def _make_request(
    method: str,
    path: str,
    stream: bool = False,
    params: Optional[dict] = None,
    headers: Optional[dict] = None,
) -> requests.Response:
    """Execute an authenticated HTTP request to Jira."""
    config = _get_config()
    url = f"{config['host']}{path}"
    req_headers = {"Accept": "application/json"}
    if headers:
        req_headers.update(headers)

    auth = None
    if config["pat"]:
        req_headers["Authorization"] = f"Bearer {config['pat']}"
    else:
        auth = (config["email"], config["api_token"])

    response = requests.request(
        method=method,
        url=url,
        auth=auth,
        headers=req_headers,
        params=params,
        stream=stream,
        timeout=60,
    )

    if response.status_code == 401:
        raise PermissionError("Jira Authentication failed (401). Check JIRA_EMAIL and JIRA_API_TOKEN / PAT.")
    elif response.status_code == 403:
        raise PermissionError("Access forbidden (403). You do not have permission for this Jira resource.")
    elif response.status_code == 404:
        raise FileNotFoundError(f"Resource not found (404) at {path}")

    response.raise_for_status()
    return response


def _extract_adf_text(node: Any) -> str:
    """Recursively extract plain text from Atlassian Document Format (ADF) JSON."""
    if not node:
        return ""
    if isinstance(node, str):
        return node
    if isinstance(node, dict):
        text = node.get("text", "")
        if "content" in node and isinstance(node["content"], list):
            sub_texts = [_extract_adf_text(child) for child in node["content"]]
            return text + "".join(sub_texts)
        return text
    if isinstance(node, list):
        return "\n".join(_extract_adf_text(item) for item in node)
    return str(node)


def _format_size(size_bytes: int) -> str:
    """Format bytes into a human-readable size string."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


@mcp.tool()
def jira_get_issue(issue_key: str) -> Dict[str, Any]:
    """
    Fetch details for a Jira issue by its key (e.g. 'PROJ-123'), including
    summary, description, status, assignee, and metadata of all attachments.
    """
    config = _get_config()
    v = config["api_version"]
    resp = _make_request("GET", f"/rest/api/{v}/issue/{issue_key.strip()}")
    data = resp.json()
    fields = data.get("fields", {})

    # Parse description (could be ADF in API v3 or markdown/raw string in v2)
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

    return {
        "key": data.get("key"),
        "summary": fields.get("summary"),
        "status": fields.get("status", {}).get("name"),
        "priority": fields.get("priority", {}).get("name") if fields.get("priority") else None,
        "assignee": fields.get("assignee", {}).get("displayName") if fields.get("assignee") else "Unassigned",
        "reporter": fields.get("reporter", {}).get("displayName") if fields.get("reporter") else None,
        "description": description,
        "attachment_count": len(attachments),
        "attachments": attachments,
    }


@mcp.tool()
def jira_list_attachments(issue_key: str) -> List[Dict[str, Any]]:
    """
    List all attachments for a specific Jira issue (e.g. 'PROJ-123')
    with their ID, filename, size, and MIME type.
    """
    issue = jira_get_issue(issue_key)
    return issue.get("attachments", [])


@mcp.tool()
def jira_download_attachment(
    attachment_id: str,
    filename: Optional[str] = None,
    output_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Download a single Jira attachment by its ID and save it to a local folder.

    Parameters:
    - attachment_id: The numerical ID of the attachment in Jira (e.g. '10045').
    - filename: (Optional) Destination filename. If not provided, it is fetched from Jira.
    - output_dir: (Optional) Local directory to save the file (defaults to JIRA_DOWNLOAD_DIR or './downloads').
    """
    config = _get_config()
    v = config["api_version"]
    att_id = str(attachment_id).strip()

    # If filename is not provided, fetch attachment metadata
    if not filename:
        try:
            meta_resp = _make_request("GET", f"/rest/api/{v}/attachment/{att_id}")
            meta = meta_resp.json()
            filename = meta.get("filename", f"attachment_{att_id}")
        except Exception:
            filename = f"attachment_{att_id}"

    # Determine destination path
    dest_folder = _resolve_download_dir(output_dir)
    dest_folder.mkdir(parents=True, exist_ok=True)
    target_path = dest_folder / filename

    # Download file content stream
    resp = _make_request(
        "GET",
        f"/rest/api/{v}/attachment/content/{att_id}",
        stream=True,
        headers={"Accept": "*/*"},
    )

    total_bytes = 0
    with open(target_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=16384):
            if chunk:
                f.write(chunk)
                total_bytes += len(chunk)

    return {
        "status": "success",
        "attachment_id": att_id,
        "filename": filename,
        "saved_path": str(target_path),
        "size_bytes": total_bytes,
        "size_human": _format_size(total_bytes),
    }


@mcp.tool()
def jira_download_all_attachments(
    issue_key: str,
    output_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Download all attachments associated with a Jira issue into a local directory.

    Parameters:
    - issue_key: The Jira issue key (e.g. 'PROJ-123').
    - output_dir: (Optional) Destination directory (defaults to ./downloads/<issue_key>).
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


@mcp.tool()
def jira_read_text_attachment(
    attachment_id: str,
    max_chars: int = 50000,
) -> Dict[str, Any]:
    """
    Read the contents of a text-based attachment (logs, JSON, CSV, code, markdown, txt)
    directly into context without saving to disk.

    Parameters:
    - attachment_id: The Jira attachment ID.
    - max_chars: Maximum characters to return (default: 50,000 to prevent context overflow).
    """
    config = _get_config()
    v = config["api_version"]
    att_id = str(attachment_id).strip()

    # Get metadata for filename & MIME type
    try:
        meta_resp = _make_request("GET", f"/rest/api/{v}/attachment/{att_id}")
        meta = meta_resp.json()
        filename = meta.get("filename", f"attachment_{att_id}")
        mime_type = meta.get("mimeType", "text/plain")
    except Exception:
        filename = f"attachment_{att_id}"
        mime_type = "unknown"

    # Fetch raw content
    resp = _make_request(
        "GET",
        f"/rest/api/{v}/attachment/content/{att_id}",
        headers={"Accept": "*/*"},
    )

    # Decode text content
    try:
        text_content = resp.content.decode("utf-8")
    except UnicodeDecodeError:
        try:
            text_content = resp.content.decode("latin-1")
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


@mcp.tool()
def jira_search_issues(jql: str, max_results: int = 10) -> Dict[str, Any]:
    """
    Search Jira issues using JQL (Jira Query Language).

    Parameters:
    - jql: The JQL query string (e.g. 'project = PROJ AND status = "In Progress"').
    - max_results: Maximum number of issues to return (default: 10).
    """
    config = _get_config()
    v = config["api_version"]
    params = {
        "jql": jql,
        "maxResults": max_results,
        "fields": "summary,status,assignee,attachment,created,updated",
    }

    resp = _make_request("GET", f"/rest/api/{v}/search", params=params)
    data = resp.json()

    issues = []
    for item in data.get("issues", []):
        fields = item.get("fields", {})
        att_list = fields.get("attachment", [])
        issues.append({
            "key": item.get("key"),
            "summary": fields.get("summary"),
            "status": fields.get("status", {}).get("name"),
            "assignee": fields.get("assignee", {}).get("displayName") if fields.get("assignee") else "Unassigned",
            "attachment_count": len(att_list),
            "attachments": [
                {
                    "id": str(a.get("id")),
                    "filename": a.get("filename"),
                    "size_human": _format_size(a.get("size", 0)),
                }
                for a in att_list
            ],
        })

    return {
        "total": data.get("total", 0),
        "returned": len(issues),
        "issues": issues,
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")
