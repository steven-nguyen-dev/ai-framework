#!/usr/bin/env python3
"""
Kibana Explorer MCP Server (KQL)
--------------------------------
A local Model Context Protocol server that searches Kibana Observability /
Logs the way a human does: by typing KQL.

Transport
    Kibana on :5601 is the only endpoint available here (no direct
    Elasticsearch, no API key), so this server logs in the way the browser
    does -- POST /internal/security/login for a `sid` cookie -- and runs
    queries through POST /internal/bsearch, polling the async search until
    the shards finish. The session cookie is cached in memory and silently
    renewed on 401/403.

KQL
    Kibana parses KQL in the browser and sends plain Query DSL over the wire,
    so there is no KQL endpoint to call. `kql.py` reimplements the parser;
    every tool below takes a `kql` string and translates it locally. Use
    `kibana_translate_kql` to see the DSL a query produces, and
    `kibana_raw_bsearch` when you need something KQL cannot express.

Configuration (.env beside this file, see .env.example)
    KIBANA_URL, KIBANA_USERNAME, KIBANA_PASSWORD
    KIBANA_COOKIE          optional  paste a `sid=...` cookie to skip login
    KIBANA_VERSION         optional  autodetected from /api/status
    KIBANA_INDEX_PATTERN   optional  default index pattern
    KIBANA_VERIFY_SSL      optional  false to accept a self-signed cert

Usage
    python3 server.py              run as an MCP stdio server
    python3 server.py --selftest   check credentials and run one live query
"""

from __future__ import annotations

import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

from kql import KqlError, to_dsl  # noqa: E402

GLOBAL_MCPS_DIR = Path.home() / ".mcp"
try:
    GLOBAL_MCPS_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    pass

GLOBAL_KIBANA_ENV = GLOBAL_MCPS_DIR / ".kibana-explorer.env"
LEGACY_DOT_KIBANA_ENV = GLOBAL_MCPS_DIR / "kibana-explorer.env"
LEGACY_MCPS_ENV = Path.home() / ".mcps/.kibana-explorer.env"
LEGACY_KIBANA_ENV = Path.home() / ".kibana.env"
LOCAL_KIBANA_ENV = Path(__file__).resolve().parent / ".env"
_ENV_PATH = LOCAL_KIBANA_ENV

try:
    from dotenv import load_dotenv
    if LEGACY_KIBANA_ENV.exists():
        load_dotenv(dotenv_path=LEGACY_KIBANA_ENV)
    if LEGACY_MCPS_ENV.exists():
        load_dotenv(dotenv_path=LEGACY_MCPS_ENV)
    if LEGACY_DOT_KIBANA_ENV.exists():
        load_dotenv(dotenv_path=LEGACY_DOT_KIBANA_ENV)
    if GLOBAL_KIBANA_ENV.exists():
        load_dotenv(dotenv_path=GLOBAL_KIBANA_ENV, override=True)
    if LOCAL_KIBANA_ENV.exists():
        load_dotenv(dotenv_path=LOCAL_KIBANA_ENV, override=True)
except ImportError:  # pragma: no cover - dotenv is a soft dependency
    pass

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:  # pragma: no cover
    try:
        from fastmcp import FastMCP
    except ImportError:
        sys.stderr.write(
            "Error: the 'mcp' package is not installed.\n"
            "Install it with: pip install -r requirements.txt\n"
        )
        sys.exit(1)

mcp = FastMCP("kibana-explorer")

DEFAULT_INDEX_PATTERN = "logs-*-*,logs-*,filebeat-*"
FALLBACK_VERSION = "8.19.18"

_SEARCH_OPTIONS = {
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
}

_BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

_CACHED_COOKIE: Optional[str] = None
_CACHED_VERSION: Optional[str] = None


# ---------------------------------------------------------------------------
# Configuration & transport
# ---------------------------------------------------------------------------

def _is_placeholder(val: str) -> bool:
    if not val:
        return True
    lower = val.lower()
    return any(p in lower for p in ["example.com", "your-email", "your_kibana_password", "your-domain", "your_api_token", "xxx", "your_username", "your_password"])


def _config() -> Dict[str, Any]:
    try:
        from dotenv import load_dotenv
        if _ENV_PATH.exists():
            load_dotenv(dotenv_path=_ENV_PATH, override=True)
    except Exception:
        pass

    url = os.environ.get("KIBANA_URL", "").strip().rstrip("/")
    if not url or _is_placeholder(url):
        raise ValueError(
            "KIBANA_URL is not configured yet. "
            "Please ask the user for Kibana URL and login credentials, then call `kibana_configure`."
        )

    verify = os.environ.get("KIBANA_VERIFY_SSL", "true").strip().lower()
    return {
        "url": url,
        "username": os.environ.get("KIBANA_USERNAME", "").strip(),
        "password": os.environ.get("KIBANA_PASSWORD", "").strip(),
        "static_cookie": os.environ.get("KIBANA_COOKIE", "").strip().strip('"').strip("'"),
        "version": os.environ.get("KIBANA_VERSION", "").strip(),
        "index_pattern": os.environ.get("KIBANA_INDEX_PATTERN", "").strip() or DEFAULT_INDEX_PATTERN,
        "verify_ssl": verify not in ("false", "0", "no", "off"),
    }


def _ssl_context(cfg: Dict[str, Any]) -> Optional[ssl.SSLContext]:
    if cfg["verify_ssl"]:
        return None
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _open(req: urllib.request.Request, cfg: Dict[str, Any], timeout: int = 30):
    ctx = _ssl_context(cfg)
    if ctx is not None:
        return urllib.request.urlopen(req, timeout=timeout, context=ctx)
    return urllib.request.urlopen(req, timeout=timeout)


def _kbn_version(cfg: Dict[str, Any]) -> str:
    """Kibana rejects requests whose kbn-version header does not match. Ask it."""
    global _CACHED_VERSION
    if cfg["version"]:
        return cfg["version"]
    if _CACHED_VERSION:
        return _CACHED_VERSION

    import base64
    headers = {"kbn-xsrf": "true", "User-Agent": _BROWSER_UA}
    if cfg["username"] and cfg["password"]:
        raw = f"{cfg['username']}:{cfg['password']}".encode("utf-8")
        headers["Authorization"] = "Basic " + base64.b64encode(raw).decode("ascii")
    try:
        req = urllib.request.Request(f"{cfg['url']}/api/status", headers=headers, method="GET")
        with _open(req, cfg, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        version = (data.get("version") or {}).get("number")
        if version:
            _CACHED_VERSION = version
            return version
    except Exception as exc:  # noqa: BLE001 - version detection is best effort
        sys.stderr.write(f"kibana: version autodetect failed ({exc}); using {FALLBACK_VERSION}\n")

    _CACHED_VERSION = FALLBACK_VERSION
    return _CACHED_VERSION


def _authenticate(force: bool = False) -> str:
    """Return a valid `sid=...` cookie, logging in the way the browser does."""
    global _CACHED_COOKIE
    if _CACHED_COOKIE and not force:
        return _CACHED_COOKIE

    cfg = _config()

    if cfg["username"] and cfg["password"]:
        payload = {
            "providerType": "basic",
            "providerName": "basic",
            "currentURL": cfg["url"],
            "params": {"username": cfg["username"], "password": cfg["password"]},
        }
        req = urllib.request.Request(
            f"{cfg['url']}/internal/security/login",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "kbn-version": _kbn_version(cfg),
                "kbn-xsrf": "true",
                "x-elastic-internal-origin": "Kibana",
                "User-Agent": _BROWSER_UA,
            },
            method="POST",
        )
        try:
            with _open(req, cfg, timeout=20) as resp:
                for cookie in resp.headers.get_all("Set-Cookie") or []:
                    part = cookie.split(";")[0].strip()
                    if part.startswith("sid="):
                        _CACHED_COOKIE = part
                        return _CACHED_COOKIE
            sys.stderr.write("kibana: login returned no sid cookie\n")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:400]
            sys.stderr.write(f"kibana: login failed ({exc.code}): {body}\n")
        except Exception as exc:  # noqa: BLE001
            sys.stderr.write(f"kibana: login failed: {exc}\n")

    if cfg["static_cookie"]:
        _CACHED_COOKIE = cfg["static_cookie"]
        return _CACHED_COOKIE

    raise PermissionError(
        "Could not obtain a Kibana session. Check KIBANA_USERNAME / KIBANA_PASSWORD "
        "in .env, or paste a browser `sid=...` cookie into KIBANA_COOKIE."
    )


def _bsearch(body: Dict[str, Any], index_pattern: Optional[str] = None, max_polls: int = 60) -> Dict[str, Any]:
    """POST an async search to /internal/bsearch and poll until the shards finish."""
    cfg = _config()
    index_pattern = index_pattern or cfg["index_pattern"]
    endpoint = f"{cfg['url']}/internal/bsearch"
    cookie = _authenticate()
    version = _kbn_version(cfg)

    def headers(c: str) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "kbn-version": version,
            "kbn-xsrf": "true",
            "x-elastic-internal-origin": "Kibana",
            "Cookie": c,
            "User-Agent": _BROWSER_UA,
        }

    def post(payload: Dict[str, Any], c: str) -> Dict[str, Any]:
        req = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers(c),
            method="POST",
        )
        with _open(req, cfg, timeout=45) as resp:
            return json.loads(resp.read().decode("utf-8"))

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
            "options": _SEARCH_OPTIONS,
        }]
    }

    try:
        data = post(initial, cookie)
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            cookie = _authenticate(force=True)
            data = post(initial, cookie)
        else:
            detail = exc.read().decode("utf-8", errors="replace")[:800]
            raise RuntimeError(f"Kibana bsearch failed ({exc.code}): {detail}") from exc

    result = data.get("result", {})
    if "error" in data and not result:
        raise RuntimeError(f"Kibana bsearch error: {json.dumps(data['error'])[:800]}")

    async_id = result.get("id")
    raw = result.get("rawResponse") or {}

    # A search is only finished when Kibana stops reporting isRunning AND has
    # actually attached a rawResponse. Wide time ranges routinely return an
    # empty first response; treating that as "zero hits" is silently wrong.
    def _done(res: Dict[str, Any], payload: Dict[str, Any]) -> bool:
        if res.get("isRunning"):
            return False
        return bool(payload) and "hits" in payload

    completed = _done(result, raw)

    if async_id and not completed:
        for _ in range(max_polls):
            time.sleep(1.0)
            poll = {
                "batch": [{
                    "request": {"id": async_id, "params": {"index": index_pattern}},
                    "options": _SEARCH_OPTIONS,
                }]
            }
            try:
                polled = post(poll, cookie).get("result", {})
            except urllib.error.HTTPError as exc:
                if exc.code in (401, 403):
                    cookie = _authenticate(force=True)
                continue
            except Exception:  # noqa: BLE001 - transient poll failures are retried
                continue
            raw = polled.get("rawResponse") or raw
            if _done(polled, raw):
                completed = True
                break

    if not completed:
        raise RuntimeError(
            f"Kibana search did not finish within {max_polls}s. Narrow the time range, "
            f"add a filter, or lower the limit and retry."
        )

    return raw


# ---------------------------------------------------------------------------
# Query building
# ---------------------------------------------------------------------------

def _time_filter(time_range: str, start: Optional[str], end: Optional[str]) -> Dict[str, Any]:
    gte = start or time_range or "now-15m"
    lte = end or "now"
    return {"range": {"@timestamp": {"format": "strict_date_optional_time", "gte": gte, "lte": lte}}}


def _service_filter(service_name: str) -> Dict[str, Any]:
    return {
        "bool": {
            "should": [
                {"wildcard": {"application": f"*{service_name}*"}},
                {"wildcard": {"service.name": f"*{service_name}*"}},
                {"wildcard": {"log.file.path": f"*{service_name}*"}},
            ],
            "minimum_should_match": 1,
        }
    }


def _level_filter(log_level: str) -> Dict[str, Any]:
    return {
        "bool": {
            "should": [
                {"term": {"log.level": log_level.lower()}},
                {"term": {"log.level": log_level.upper()}},
                {"term": {"level": log_level.lower()}},
                {"term": {"level": log_level.upper()}},
            ],
            "minimum_should_match": 1,
        }
    }


_RELATIVE_UNITS = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}


def _auto_interval(time_range: str, target_buckets: int = 50) -> str:
    """Pick a fixed_interval that splits a relative window into ~target_buckets."""
    match = re.match(r"^now-(\d+)([smhdw])$", (time_range or "").strip())
    seconds = int(match.group(1)) * _RELATIVE_UNITS[match.group(2)] if match else 86400
    step = max(1, seconds // target_buckets)
    for size, label in (
        (60, "1m"), (300, "5m"), (600, "10m"), (1800, "30m"),
        (3600, "1h"), (10800, "3h"), (21600, "6h"), (43200, "12h"),
    ):
        if step <= size:
            return label
    return "1d"


def _filters(kql, time_range, start, end, service_name, log_level) -> List[Dict[str, Any]]:
    filters = [_time_filter(time_range, start, end)]
    if kql and kql.strip():
        filters.append(to_dsl(kql))
    if service_name:
        filters.append(_service_filter(service_name))
    if log_level:
        filters.append(_level_filter(log_level))
    return filters


def _parse_or_error(kql: Optional[str]) -> Optional[Dict[str, Any]]:
    """Return an error payload if the KQL is malformed, else None."""
    if not kql or not kql.strip():
        return None
    try:
        to_dsl(kql)
        return None
    except KqlError as exc:
        return {
            "error": "invalid_kql",
            "message": str(exc),
            "kql": kql,
            "hint": "Call kibana_translate_kql to inspect syntax, or kibana_raw_bsearch for raw DSL.",
        }


def _clean(value: Any) -> Any:
    if isinstance(value, str):
        s = value.strip()
        if (s.startswith("{") and s.endswith("}")) or (s.startswith("[") and s.endswith("]")):
            try:
                return json.loads(s)
            except Exception:  # noqa: BLE001
                pass
    return value


def _format_hit(hit: Dict[str, Any]) -> Dict[str, Any]:
    fields = hit.get("fields", {}) or {}
    source = hit.get("_source", {}) or {}

    def get(key: str, default=None):
        if key in fields:
            v = fields[key]
            return v[0] if isinstance(v, list) and v else v
        return source.get(key, default)

    message = get("message", "")
    entry = {
        "timestamp": get("@timestamp"),
        "level": get("log.level") or get("level"),
        "app": get("application") or get("service.name") or get("app"),
        "message": _clean(message),
        "source_file": get("log.file.path"),
        "host": get("agent.hostname") or get("host.hostname") or get("host.name"),
        "container": get("container.name"),
    }
    return {k: v for k, v in entry.items() if v is not None}


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def kibana_search_logs(
    kql: Optional[str] = None,
    query: Optional[str] = None,
    time_range: str = "now-15m",
    start: Optional[str] = None,
    end: Optional[str] = None,
    service_name: Optional[str] = None,
    log_level: Optional[str] = None,
    limit: int = 25,
    index_pattern: Optional[str] = None,
    sort: str = "desc",
) -> Dict[str, Any]:
    """
    Search Kibana logs with a KQL query, exactly as typed in the Kibana search bar.

    Parameters:
    - kql: KQL query string. Examples: 'log.level:ERROR', 'service.name:(oms or wms) and message:*timeout*',
      'not message:"health check" and http.response.status_code >= 500', 'error.stack_trace:*'.
      Supports field:value, quoted phrases, wildcards, AND/OR/NOT, parentheses, ranges (>=, <=, >, <)
      and bare free text. Omit for no query filter.
    - query: Deprecated alias for `kql`, kept so older clients keep filtering instead of
      silently matching everything. Ignored when `kql` is given.
    - time_range: Relative window such as 'now-15m', 'now-1h', 'now-24h', 'now-7d'. Default 'now-15m'.
    - start / end: Absolute ISO-8601 bounds (e.g. '2026-08-22T00:00:00Z'). Override time_range when given.
    - service_name: Convenience substring filter over application / service.name / log.file.path.
    - log_level: Convenience filter, e.g. 'ERROR', 'WARN', 'INFO' (matches either case).
    - limit: Max documents to return, 1-500. Default 25.
    - index_pattern: Elasticsearch index pattern. Defaults to KIBANA_INDEX_PATTERN.
    - sort: 'desc' for newest first (default) or 'asc' for oldest first.
    """
    kql = kql if (kql and kql.strip()) else query
    bad = _parse_or_error(kql)
    if bad:
        return bad

    limit = min(max(1, limit), 500)
    order = "asc" if str(sort).lower() == "asc" else "desc"

    body = {
        "sort": [
            {"@timestamp": {"order": order, "format": "strict_date_optional_time", "unmapped_type": "boolean"}},
            {"_doc": {"order": order, "unmapped_type": "boolean"}},
        ],
        "fields": [
            {"field": "*", "include_unmapped": True},
            {"field": "@timestamp", "format": "strict_date_optional_time"},
        ],
        "size": limit,
        "version": True,
        "_source": False,
        "query": {"bool": {
            "must": [],
            "filter": _filters(kql, time_range, start, end, service_name, log_level),
            "should": [],
            "must_not": [],
        }},
        "stored_fields": ["*"],
    }

    raw = _bsearch(body, index_pattern)
    hits = raw.get("hits", {}) or {}
    total = hits.get("total", {})
    return {
        "total_hits": total.get("value") if isinstance(total, dict) else total,
        "returned_count": len(hits.get("hits", [])),
        "kql": kql,
        "time_range": {"start": start or time_range, "end": end or "now"},
        "logs": [_format_hit(h) for h in hits.get("hits", [])],
    }


@mcp.tool()
def kibana_count_logs(
    kql: Optional[str] = None,
    time_range: str = "now-1h",
    start: Optional[str] = None,
    end: Optional[str] = None,
    service_name: Optional[str] = None,
    log_level: Optional[str] = None,
    index_pattern: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Count matching log documents without returning them. Cheap way to size a query
    before pulling documents, or to compare volumes between two KQL queries.

    Parameters mirror kibana_search_logs; there is no limit because nothing is returned.
    """
    bad = _parse_or_error(kql)
    if bad:
        return bad

    body = {
        "size": 0,
        "track_total_hits": True,
        "query": {"bool": {"filter": _filters(kql, time_range, start, end, service_name, log_level)}},
    }
    raw = _bsearch(body, index_pattern)
    total = (raw.get("hits", {}) or {}).get("total", {})
    return {
        "count": total.get("value") if isinstance(total, dict) else total,
        "relation": total.get("relation") if isinstance(total, dict) else None,
        "kql": kql,
        "time_range": {"start": start or time_range, "end": end or "now"},
    }


@mcp.tool()
def kibana_log_histogram(
    kql: Optional[str] = None,
    time_range: str = "now-24h",
    interval: str = "auto",
    start: Optional[str] = None,
    end: Optional[str] = None,
    breakdown_field: Optional[str] = None,
    service_name: Optional[str] = None,
    log_level: Optional[str] = None,
    index_pattern: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Bucket matching logs over time to find when a problem started or spiked.

    Parameters:
    - kql / time_range / start / end / service_name / log_level / index_pattern: as in kibana_search_logs.
    - interval: Bucket size such as '1m', '5m', '30m', '1h', '1d', or 'auto' (default) to fit ~50 buckets.
    - breakdown_field: Optional keyword field to split each bucket by, e.g. 'log.level' or 'service.name'.
      Use the keyword sub-field (e.g. 'service.name.keyword') if the plain field is text-analyzed.
    """
    bad = _parse_or_error(kql)
    if bad:
        return bad

    resolved = interval if (interval and interval.lower() != "auto") else _auto_interval(time_range)
    date_hist: Dict[str, Any] = {
        "field": "@timestamp",
        "min_doc_count": 0,
        "fixed_interval": resolved,
    }

    aggs: Dict[str, Any] = {"timeline": {"date_histogram": date_hist}}
    if breakdown_field:
        aggs["timeline"]["aggs"] = {"breakdown": {"terms": {"field": breakdown_field, "size": 10}}}

    body = {
        "size": 0,
        "track_total_hits": True,
        "query": {"bool": {"filter": _filters(kql, time_range, start, end, service_name, log_level)}},
        "aggs": aggs,
    }
    raw = _bsearch(body, index_pattern)

    buckets = []
    for bucket in ((raw.get("aggregations", {}) or {}).get("timeline", {}) or {}).get("buckets", []):
        item = {"time": bucket.get("key_as_string"), "count": bucket.get("doc_count")}
        if breakdown_field:
            item["breakdown"] = {
                b.get("key"): b.get("doc_count")
                for b in (bucket.get("breakdown", {}) or {}).get("buckets", [])
            }
        buckets.append(item)

    total = (raw.get("hits", {}) or {}).get("total", {})
    return {
        "total_hits": total.get("value") if isinstance(total, dict) else total,
        "kql": kql,
        "interval": resolved,
        "buckets": buckets,
    }


@mcp.tool()
def kibana_field_values(
    field: str,
    kql: Optional[str] = None,
    time_range: str = "now-1h",
    start: Optional[str] = None,
    end: Optional[str] = None,
    size: int = 20,
    index_pattern: Optional[str] = None,
) -> Dict[str, Any]:
    """
    List the most common values of a field, with counts. Use it to discover what to
    filter on -- which services log here, which hosts, which log levels, which error types.

    Parameters:
    - field: Keyword field to aggregate, e.g. 'service.name', 'log.level', 'host.name',
      'kubernetes.container.name'. Text fields need their '.keyword' sub-field.
    - kql / time_range / start / end / index_pattern: as in kibana_search_logs.
    - size: Number of distinct values to return (default 20, max 200).
    """
    bad = _parse_or_error(kql)
    if bad:
        return bad

    size = min(max(1, size), 200)
    body = {
        "size": 0,
        "query": {"bool": {"filter": _filters(kql, time_range, start, end, None, None)}},
        "aggs": {"values": {"terms": {"field": field, "size": size, "order": {"_count": "desc"}}}},
    }
    raw = _bsearch(body, index_pattern)
    agg = (raw.get("aggregations", {}) or {}).get("values", {}) or {}
    return {
        "field": field,
        "values": [{"value": b.get("key"), "count": b.get("doc_count")} for b in agg.get("buckets", [])],
        "other_count": agg.get("sum_other_doc_count"),
        "hint": "Empty result usually means the field is text-analyzed; try '<field>.keyword'.",
    }


@mcp.tool()
def kibana_get_recent_errors(
    service_name: Optional[str] = None,
    time_range: str = "now-1h",
    limit: int = 20,
    index_pattern: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Shortcut for recent errors and exceptions across all services or one service.

    Parameters:
    - service_name: (Optional) Substring of the application / service name.
    - time_range: (Optional) e.g. 'now-30m', 'now-1h', 'now-6h', 'now-24h'. Default 'now-1h'.
    - limit: (Optional) Max entries to return. Default 20.
    - index_pattern: (Optional) Elasticsearch index pattern.
    """
    return kibana_search_logs(
        kql="error or exception or fatal or traceback",
        time_range=time_range,
        service_name=service_name,
        log_level="ERROR",
        limit=limit,
        index_pattern=index_pattern,
    )


@mcp.tool()
def kibana_translate_kql(kql: str) -> Dict[str, Any]:
    """
    Show the Elasticsearch Query DSL a KQL string translates to, without running it.
    Use this to debug a query that returns nothing, or to hand the DSL to kibana_raw_bsearch.

    Parameters:
    - kql: The KQL string to translate.
    """
    try:
        return {"kql": kql, "dsl": to_dsl(kql), "valid": True}
    except KqlError as exc:
        return {"kql": kql, "valid": False, "error": str(exc)}


@mcp.tool()
def kibana_raw_bsearch(
    body: Dict[str, Any],
    index_pattern: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Escape hatch: run a raw Elasticsearch query body through Kibana's bsearch backend.
    Use for aggregations, nested queries, ES features KQL cannot express, or when you
    already have DSL from kibana_translate_kql.

    Parameters:
    - body: Elasticsearch request body, e.g. {"query": {...}, "size": 10, "aggs": {...}}.
    - index_pattern: (Optional) Elasticsearch index pattern.
    """
    return _bsearch(body, index_pattern)


# ---------------------------------------------------------------------------
# Generic Pipeline Flow & Health Tools
# ---------------------------------------------------------------------------

DEFAULT_GENERIC_STAGES = [
    {"name": "1. Internal Trigger", "match": "order_creation, webhook.worker, on_order_creation"},
    {"name": "2. Ingress / Publish", "match": "CREATE order API is called, publishMessageToKafkaTopic, createOrders"},
    {"name": "3. Queue Consume", "match": "WMSKafkaConsumerService consume, consumed message, KafkaListener"},
    {"name": "4. External Dispatch", "match": "success response, response_code, execute.request, fetchOrderDetailList"},
]


@mcp.tool()
def kibana_trace_pipeline(
    ids: List[str],
    stages: Optional[List[Dict[str, str]]] = None,
    time_range: str = "now-24h",
    start: Optional[str] = None,
    end: Optional[str] = None,
    index_pattern: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generic End-to-End Pipeline Hop Tracer.
    
    WHEN TO USE:
    - Use when the user asks to "trace", "track", or "debug" one or more entity IDs (e.g. order numbers, 
      tracking SNs, SKU IDs, transaction IDs, webhook payloads) across an integration lifecycle.
    - Identifies exactly which pipeline hop succeeded and which stage dropped/lost the entity.
    
    DEFAULT 4-HOP STAGES (if `stages` is omitted):
    1. Internal Trigger (OMS / Core webhook event)
    2. Ingress / Publish (Integration API received & published to Kafka/RabbitMQ)
    3. Queue Consume (Worker / KafkaListener picked up the message)
    4. External Dispatch (Dispatched to external 3PL / WMS / Marketplace API & returned response)

    Parameters:
    - ids: List of identifiers to trace, e.g. ['260824600GYHEN', '585694778777765166'].
    - stages: (Optional) Custom list of stages with 'name' and 'match' keywords.
      Example for Cancellation flow:
        [
          {"name": "1. Webhook Ingress", "match": "mpc/shopee/orders, push"},
          {"name": "2. Callback Worker", "match": "mark_complete_and_cancel_by_callback"},
          {"name": "3. State Transition", "match": "STATE_LOG, mark_cancel"}
        ]
    - start / end: Absolute ISO-8601 timestamps (e.g. '2026-08-23T00:00:00Z').
    - time_range: Relative window like 'now-24h', 'now-7d' (ignored if start/end given).
    """
    if not ids:
        return {"error": "empty_ids", "message": "Please provide at least one ID to trace."}

    resolved_stages = stages if (stages and isinstance(stages, list)) else DEFAULT_GENERIC_STAGES
    stage_names = [s.get("name", f"Stage {i+1}") for i, s in enumerate(resolved_stages)]
    
    # Parse match terms (supports comma or 'or' separation)
    stage_matchers = []
    for s in resolved_stages:
        raw_m = s.get("match", "")
        if " or " in raw_m:
            terms = [t.strip().lower() for t in raw_m.split(" or ") if t.strip()]
        else:
            terms = [t.strip().lower() for t in raw_m.split(",") if t.strip()]
        stage_matchers.append(terms)

    # Process IDs in chunks of 10
    chunk_size = 10
    all_logs: List[Dict[str, Any]] = []

    for i in range(0, len(ids), chunk_size):
        chunk = [str(x).strip() for x in ids[i : i + chunk_size] if str(x).strip()]
        if not chunk:
            continue
        chunk_kql = " or ".join(f'"{cid}"' for cid in chunk)
        res = kibana_search_logs(
            kql=chunk_kql,
            time_range=time_range,
            start=start,
            end=end,
            limit=500,
            sort="asc",
            index_pattern=index_pattern,
        )
        if isinstance(res, dict) and "logs" in res:
            all_logs.extend(res["logs"])

    # Build per-ID trace
    traces: Dict[str, Any] = {}
    funnel_counts: Dict[str, int] = {name: 0 for name in stage_names}

    for entity_id in ids:
        str_id = str(entity_id).strip()
        matched_stages: Dict[str, Dict[str, Any]] = {}

        for log in all_logs:
            msg_str = json.dumps(log.get("message", "")) if not isinstance(log.get("message"), str) else log.get("message", "")
            if str_id not in msg_str:
                continue

            msg_lower = msg_str.lower()
            for idx, stage_name in enumerate(stage_names):
                if stage_name in matched_stages:
                    continue
                match_terms = stage_matchers[idx]
                if any(term in msg_lower for term in match_terms):
                    matched_stages[stage_name] = {
                        "timestamp": log.get("timestamp"),
                        "app": log.get("app"),
                        "snippet": (msg_str[:200] + "...") if len(msg_str) > 200 else msg_str,
                    }

        timeline = []
        last_stage = None
        for name in stage_names:
            if name in matched_stages:
                funnel_counts[name] += 1
                last_stage = name
                timeline.append({"stage": name, **matched_stages[name]})

        is_complete = len(timeline) == len(stage_names)
        drop_stage = None
        if not is_complete:
            for name in stage_names:
                if name not in matched_stages:
                    drop_stage = name
                    break

        traces[str_id] = {
            "status": "COMPLETED" if is_complete else "DROPPED",
            "last_successful_stage": last_stage or "NONE",
            "drop_stage": drop_stage,
            "stages_completed": f"{len(timeline)} / {len(stage_names)}",
            "timeline": timeline,
        }

    total_ids = len(ids)
    completed_count = sum(1 for t in traces.values() if t["status"] == "COMPLETED")
    dropped_count = total_ids - completed_count
    completion_rate = round((completed_count / total_ids) * 100, 1) if total_ids > 0 else 0.0

    return {
        "total_ids": total_ids,
        "completed": completed_count,
        "dropped": dropped_count,
        "completion_rate_pct": completion_rate,
        "stages": stage_names,
        "funnel": funnel_counts,
        "traces": traces,
    }


@mcp.tool()
def kibana_pipeline_health(
    ingress_kql: str,
    egress_kql: str,
    error_kql: Optional[str] = None,
    time_range: str = "now-1h",
    start: Optional[str] = None,
    end: Optional[str] = None,
    interval: str = "auto",
    index_pattern: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generic Pipeline Health, Throughput & Lag Monitor.
    
    WHEN TO USE:
    - Use when the user asks to "check health", "monitor throughput", "measure lag", or "detect drop rate" 
      between any upstream ingress event (e.g. OMS Webhook / Stock Event) and downstream egress event (e.g. Queue Consumer / External Dispatch).
    - Returns overall status ('HEALTHY', 'DEGRADED', 'CRITICAL_OUTAGE'), drop/lag percentage, error counts, and interval timeline.

    Parameters:
    - ingress_kql: KQL matching incoming events (e.g. 'application: "NEW_OMS_PROD" and "WebhookWorker"').
    - egress_kql: KQL matching outbound/dispatched events (e.g. 'application: "APAC_INTEGRATIONS_WMS" and "consumed message"').
    - error_kql: (Optional) KQL matching pipeline errors.
    - time_range / start / end / interval / index_pattern: standard time and index parameters.
    """
    bad_in = _parse_or_error(ingress_kql)
    if bad_in:
        return bad_in
    bad_eg = _parse_or_error(egress_kql)
    if bad_eg:
        return bad_eg

    hist_in = kibana_log_histogram(
        kql=ingress_kql, time_range=time_range, start=start, end=end, interval=interval, index_pattern=index_pattern
    )
    hist_eg = kibana_log_histogram(
        kql=egress_kql, time_range=time_range, start=start, end=end, interval=interval, index_pattern=index_pattern
    )

    total_in = hist_in.get("total_hits", 0) or 0
    total_eg = hist_eg.get("total_hits", 0) or 0

    total_err = 0
    hist_err = {}
    if error_kql and error_kql.strip():
        bad_err = _parse_or_error(error_kql)
        if not bad_err:
            hist_err = kibana_log_histogram(
                kql=error_kql, time_range=time_range, start=start, end=end, interval=interval, index_pattern=index_pattern
            )
            total_err = hist_err.get("total_hits", 0) or 0

    # Align timeline buckets
    in_buckets = {b["time"]: b["count"] for b in hist_in.get("buckets", []) if "time" in b}
    eg_buckets = {b["time"]: b["count"] for b in hist_eg.get("buckets", []) if "time" in b}
    err_buckets = {b["time"]: b["count"] for b in hist_err.get("buckets", []) if "time" in b}

    all_times = sorted(set(in_buckets.keys()) | set(eg_buckets.keys()))
    timeline = []
    for t in all_times:
        inc = in_buckets.get(t, 0)
        egc = eg_buckets.get(t, 0)
        errc = err_buckets.get(t, 0)
        diff = inc - egc
        timeline.append({
            "time": t,
            "ingress": inc,
            "egress": egc,
            "diff_lag": diff,
            "errors": errc,
        })

    drop_lag = max(0, total_in - total_eg)
    drop_rate = round((drop_lag / total_in) * 100, 1) if total_in > 0 else 0.0
    err_rate = round((total_err / total_in) * 100, 1) if total_in > 0 else 0.0

    status = "HEALTHY"
    if total_in > 0 and total_eg == 0:
        status = "CRITICAL_OUTAGE"
    elif drop_rate > 10.0 or err_rate > 10.0:
        status = "DEGRADED"

    return {
        "status": status,
        "summary": {
            "total_ingress": total_in,
            "total_egress": total_eg,
            "net_drop_lag": drop_lag,
            "drop_rate_pct": drop_rate,
            "total_errors": total_err,
            "error_rate_pct": err_rate,
        },
        "time_range": {"start": start or time_range, "end": end or "now"},
        "interval": hist_in.get("interval"),
        "timeline": timeline,
    }


@mcp.tool()
def kibana_detect_service_gaps(
    kql: str,
    time_range: str = "now-24h",
    start: Optional[str] = None,
    end: Optional[str] = None,
    min_gap_minutes: int = 5,
    index_pattern: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generic Silent Gap, Downtime & Service Outage Detector.
    
    WHEN TO USE:
    - Use when investigating outages, downtime, service restarts, dead queue consumers, 
      or wondering "when did the service crash or stop processing messages?".
    - Scans log streams for unexpected silence (0 logs emitted for >= min_gap_minutes) and checks for restart events following each gap.

    Parameters:
    - kql: KQL targeting the service or consumer (e.g. 'application: "APAC_INTEGRATIONS_WMS" and "consumed message"').
    - min_gap_minutes: Minimum consecutive silence in minutes to flag as an outage (default: 5).
    - time_range / start / end / index_pattern: standard time parameters.
    """
    bad = _parse_or_error(kql)
    if bad:
        return bad

    # Use 1m intervals to precisely measure gaps
    hist = kibana_log_histogram(
        kql=kql, time_range=time_range, start=start, end=end, interval="1m", index_pattern=index_pattern
    )
    buckets = hist.get("buckets", [])
    if not buckets:
        return {
            "kql": kql,
            "gaps_found": 0,
            "total_downtime_minutes": 0,
            "min_gap_threshold_minutes": min_gap_minutes,
            "gaps": [],
            "message": "No log activity found in the specified window."
        }

    gaps = []
    current_gap_start = None
    zero_count = 0

    for b in buckets:
        cnt = b.get("count", 0)
        t = b.get("time")
        if cnt == 0:
            if current_gap_start is None:
                current_gap_start = t
            zero_count += 1
        else:
            if zero_count >= min_gap_minutes:
                gaps.append({
                    "gap_start": current_gap_start,
                    "gap_end": t,
                    "duration_minutes": zero_count,
                })
            current_gap_start = None
            zero_count = 0

    # Catch trailing gap
    if zero_count >= min_gap_minutes:
        gaps.append({
            "gap_start": current_gap_start,
            "gap_end": buckets[-1].get("time"),
            "duration_minutes": zero_count,
        })

    # For each gap, check if there was a startup/restart event right after the gap ended
    for g in gaps:
        restart_probe = kibana_search_logs(
            kql=f'{kql} and ("Starting" or "Started" or "Initializing" or "boot" or "Spring" or "JVM")',
            start=g["gap_end"],
            time_range="now-15m",
            limit=3,
            index_pattern=index_pattern,
        )
        has_restart = bool(restart_probe.get("total_hits", 0) > 0)
        g["restart_detected"] = has_restart
        if has_restart and restart_probe.get("logs"):
            first_log = restart_probe["logs"][0]
            g["restart_log_timestamp"] = first_log.get("timestamp")
            g["restart_log_snippet"] = str(first_log.get("message"))[:150]

    total_downtime = sum(g["duration_minutes"] for g in gaps)

    return {
        "kql": kql,
        "gaps_found": len(gaps),
        "total_downtime_minutes": total_downtime,
        "min_gap_threshold_minutes": min_gap_minutes,
        "gaps": gaps,
    }


@mcp.tool()
def kibana_configure(
    url: str,
    username: str,
    password: str,
    index_pattern: Optional[str] = None,
    verify_ssl: bool = True,
) -> Dict[str, Any]:
    """
    👉 [SETUP REQUIRED - START HERE] Self-Service In-Chat Configuration Tool.
    Configure or update Kibana connection credentials directly from chat without running terminal scripts.
    Automatically tests authentication and persists credentials to ~/.mcp/kibana-explorer.env.

    Parameters:
    - url: Kibana base URL (e.g. 'https://kibana.internal.company.com:5601').
    - username: Login username.
    - password: Login password.
    - index_pattern: (Optional) Default Elasticsearch index pattern (defaults to 'logs-*-*,logs-*,filebeat-*').
    - verify_ssl: Set False if your Kibana instance uses internal/self-signed SSL certificates.
    """
    clean_url = url.strip().rstrip("/")
    clean_user = username.strip()
    clean_pass = password.strip()
    clean_pattern = (index_pattern or "").strip() or DEFAULT_INDEX_PATTERN
    ssl_str = "true" if verify_ssl else "false"

    content = f"""# Kibana Explorer MCP Configuration (.env)
KIBANA_URL={clean_url}
KIBANA_USERNAME={clean_user}
KIBANA_PASSWORD={clean_pass}
KIBANA_INDEX_PATTERN={clean_pattern}
KIBANA_VERIFY_SSL={ssl_str}
"""
    for target in [GLOBAL_KIBANA_ENV, LOCAL_KIBANA_ENV]:
        try:
            with open(target, "w", encoding="utf-8") as f:
                f.write(content)
            target.chmod(0o600)
        except Exception:
            pass

    # Update process environment
    os.environ["KIBANA_URL"] = clean_url
    os.environ["KIBANA_USERNAME"] = clean_user
    os.environ["KIBANA_PASSWORD"] = clean_pass
    os.environ["KIBANA_INDEX_PATTERN"] = clean_pattern
    os.environ["KIBANA_VERIFY_SSL"] = ssl_str

    # Invalidate cached cookies
    global _CACHED_COOKIE, _CACHED_VERSION
    _CACHED_COOKIE = None
    _CACHED_VERSION = None

    test_result = kibana_check_connection()
    if test_result.get("ok"):
        return {
            "status": "CONFIGURED_AND_CONNECTED",
            "message": f"Successfully connected to Kibana at {clean_url} (Version: {test_result.get('kibana_version')}).",
            "details": test_result,
        }
    else:
        return {
            "status": "CONFIGURED_BUT_CONNECTION_FAILED",
            "message": "Saved credentials to .env, but authentication test failed.",
            "error": test_result.get("error"),
            "hint": "Please verify URL, username, password, or check if VPN is required.",
        }


@mcp.tool()
def kibana_check_connection() -> Dict[str, Any]:
    """
    Verify the configured Kibana URL and credentials: detect the Kibana version,
    perform a login, and run a one-document probe query. Call this first when
    another tool fails, to tell a credential problem from a query problem.
    """
    cfg = _config()
    report: Dict[str, Any] = {
        "url": cfg["url"],
        "username": cfg["username"] or "(not set)",
        "index_pattern": cfg["index_pattern"],
        "verify_ssl": cfg["verify_ssl"],
    }
    try:
        report["kibana_version"] = _kbn_version(cfg)
        cookie = _authenticate(force=True)
        report["authenticated"] = bool(cookie)
        probe = kibana_search_logs(time_range="now-15m", limit=1)
        report["probe_total_hits"] = probe.get("total_hits")
        report["probe_returned"] = probe.get("returned_count")
        report["ok"] = True
    except Exception as exc:  # noqa: BLE001 - the whole point is to report the failure
        report["ok"] = False
        report["error"] = f"{type(exc).__name__}: {exc}"
    return report


def _interactive_setup() -> int:
    """Interactive step-by-step CLI configuration wizard for Kibana Explorer."""
    import getpass
    print("=" * 70)
    print("  Kibana Explorer MCP — Interactive Configuration Wizard")
    print("=" * 70)
    print("This wizard will ask for each required setting step-by-step.\n")

    current = {}
    if _ENV_PATH.exists():
        try:
            with open(_ENV_PATH, "r", encoding="utf-8") as f:
                for line in f:
                    if "=" in line and not line.strip().startswith("#"):
                        k, v = line.strip().split("=", 1)
                        current[k.strip()] = v.strip().strip('"').strip("'")
        except Exception:
            pass

    default_url = current.get("KIBANA_URL", "https://kibana.internal.company.com:5601")
    url = input(f"1. Kibana Base URL [{default_url}]: ").strip() or default_url
    url = url.rstrip("/")

    default_user = current.get("KIBANA_USERNAME", "admin")
    username = input(f"2. Kibana Username [{default_user}]: ").strip() or default_user

    password = getpass.getpass("3. Kibana Password (input hidden): ").strip()
    if not password and "KIBANA_PASSWORD" in current:
        password = current["KIBANA_PASSWORD"]

    default_pattern = current.get("KIBANA_INDEX_PATTERN", DEFAULT_INDEX_PATTERN)
    pattern = input(f"4. Default Index Pattern [{default_pattern}]: ").strip() or default_pattern

    default_ssl = current.get("KIBANA_VERIFY_SSL", "true")
    ssl_in = input(f"5. Verify SSL certificates? (Y/n) [{default_ssl}]: ").strip().lower()
    verify_ssl = "false" if ssl_in in ("n", "no", "false") else "true"

    content = f"""# Kibana Explorer MCP Configuration (.env)
KIBANA_URL={url}
KIBANA_USERNAME={username}
KIBANA_PASSWORD={password}
KIBANA_INDEX_PATTERN={pattern}
KIBANA_VERIFY_SSL={verify_ssl}
"""
    with open(_ENV_PATH, "w", encoding="utf-8") as f:
        f.write(content)
    try:
        _ENV_PATH.chmod(0o600)
    except Exception:
        pass

    print(f"\n✔ Configuration saved to {_ENV_PATH}")
    print("Testing connection against Kibana...")
    return _selftest()


def _selftest() -> int:
    print("Kibana MCP self-test")
    print("=" * 60)
    report = kibana_check_connection()
    print(json.dumps(report, indent=2, default=str))
    if not report.get("ok"):
        return 1
    print("\nKQL probe: log.level:ERROR over the last hour")
    print("-" * 60)
    result = kibana_search_logs(kql="log.level:ERROR", time_range="now-1h", limit=3)
    print(json.dumps(result, indent=2, default=str)[:4000])
    return 0


if __name__ == "__main__":
    if "--setup" in sys.argv or "--init-env" in sys.argv or "--configure" in sys.argv:
        sys.exit(_interactive_setup())
    if "--selftest" in sys.argv:
        sys.exit(_selftest())

    # Check configuration on startup
    try:
        cfg = _config()
        if not cfg.get("url") or _is_placeholder(cfg["url"]):
            raise ValueError("Kibana URL missing")
    except Exception:
        sys.stderr.write("[kibana-explorer] ⚠️ Notice: Kibana credentials not configured yet. Run /config to setup.\n")

    mcp.run(transport="stdio")
