#!/usr/bin/env python3
"""
Kibana Logs MCP Server (KQL)
----------------------------
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

Configuration (.env beside this file, see .env.sample)
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

try:
    from dotenv import load_dotenv
    _ENV_PATH = Path(__file__).resolve().parent / ".env"
    load_dotenv(dotenv_path=_ENV_PATH) if _ENV_PATH.exists() else load_dotenv()
except ImportError:  # pragma: no cover - dotenv is a soft dependency
    _ENV_PATH = Path(__file__).resolve().parent / ".env"

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

mcp = FastMCP("kibana-logs")

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

def _config() -> Dict[str, Any]:
    try:
        from dotenv import load_dotenv
        if _ENV_PATH.exists():
            load_dotenv(dotenv_path=_ENV_PATH, override=True)
    except Exception:
        pass

    url = os.environ.get("KIBANA_URL", "").strip().rstrip("/")
    if not url:
        raise ValueError("KIBANA_URL is not set. Copy .env.sample to .env and fill it in.")

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
    if "--selftest" in sys.argv:
        sys.exit(_selftest())
    mcp.run(transport="stdio")
