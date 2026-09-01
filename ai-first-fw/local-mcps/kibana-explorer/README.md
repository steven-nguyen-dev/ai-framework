# Kibana Explorer MCP Server (`kibana-explorer`)

A local [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server that searches
Kibana Observability / Logs **using KQL** — the same query string you type into the Kibana search bar.

---

## Why this exists rather than the official server

Elastic's official [`mcp-server-elasticsearch`](https://github.com/elastic/mcp-server-elasticsearch)
talks to **Elasticsearch** directly: it needs a cluster endpoint (`:9200`) plus an API key, and it
speaks ES|QL / Query DSL. Two things rule it out here:

1. Only Kibana (`:5601`) is reachable, with a UI username and password. There is no ES endpoint and
   no API key.
2. It does not accept KQL, which was the stated requirement.

So this server takes the Kibana-only path, and reimplements KQL locally.

### How KQL works here

Kibana never exposes a KQL endpoint. The **browser** parses KQL and ships plain Elasticsearch Query
DSL to `/internal/bsearch`. `kql.py` reimplements that parser, so the tools accept KQL and translate
it before the request goes out. `kibana_translate_kql` shows you exactly what DSL a query produces.

### Authentication

The server logs in the way the browser does — `POST /internal/security/login` for a `sid` cookie —
then queries `POST /internal/bsearch`, polling the async search until the shards finish. The cookie
is cached in memory and silently renewed on `401`/`403`, so long sessions do not go stale. The
`kbn-version` header is read from `/api/status` at startup rather than hardcoded, which is what
breaks these servers after a Kibana upgrade.

---

## Supported KQL

| Syntax | Example |
| :--- | :--- |
| Field term | `log.level:ERROR` |
| Quoted phrase | `message:"connection reset by peer"` |
| Wildcard | `service.name:carrier-*` |
| Field exists | `error.stack_trace:*` |
| Value list | `service.name:(oms or wms or pms)` |
| Boolean | `a:1 and not b:2`, `a:1 or b:2` (case insensitive) |
| Implicit AND | `log.level:ERROR service.name:oms` |
| Grouping | `a:1 and (b:2 or c:3)` |
| Ranges | `http.response.status_code >= 500`, `@timestamp >= "2026-08-01T00:00:00Z"` |
| Free text | `NullPointerException`, `"order sync failed"` |
| Escapes | `message:foo\:bar`, `message:"he said \"hi\""` |

Not supported: `nested:{ ... }` syntax and runtime-field functions. Use `kibana_raw_bsearch` for those.
Malformed KQL returns a structured `invalid_kql` error rather than silently matching everything.

---

## Project Structure

```
ai-first-fw/local-mcps/kibana-explorer/
├── .venv/             # Dedicated Python virtual environment (created by launch.sh or setup.sh)
├── .env               # Live credentials (git-ignored)
├── .env.example       # Template
├── kql.py             # KQL -> Elasticsearch Query DSL translator
├── test_kql.py        # 34 offline unit tests for the KQL translator
├── test_server.py     # 6 offline regression tests for the bsearch polling loop
├── requirements.txt   # Python dependencies
├── launch.sh          # Entry point used by .mcp.json; builds .venv if missing, then execs server.py
├── setup.sh           # One-shot venv + dependency install
├── server.py          # FastMCP server implementation
└── README.md          # This file
```

---

## Setup & Claude Code Integration

### Option A: Interactive Global Setup for Claude Code (Recommended)
Run the automated installer to input credentials, bootstrap the environment, and register `kibana-explorer` globally in Claude Code:
```bash
bash ai-first-fw/local-mcps/kibana-explorer/install-claude.sh
```

### Option B: Local Bootstrap & Verification
`.venv/` is gitignored, so a fresh clone or a new machine starts without one. `launch.sh` builds it
on first start, which means registering the server in `.mcp.json` is enough. To build it up front:

```bash
bash ai-first-fw/local-mcps/kibana-explorer/setup.sh
```

Then verify against the live cluster:

```bash
bash ai-first-fw/local-mcps/kibana-explorer/launch.sh --selftest
```

`--selftest` reports the detected Kibana version, whether login succeeded, and the hit count of a
probe query — enough to tell a credential problem from a query problem before wiring up any client.

---

## Configuration

Credentials live in `.env` beside `server.py` (git-ignored; `.env.example` is the template).

| Variable | Required | Notes |
| :--- | :--- | :--- |
| `KIBANA_URL` | yes | Base URL with port, no trailing slash. |
| `KIBANA_USERNAME` | yes | Same login as the Kibana UI. |
| `KIBANA_PASSWORD` | yes | |
| `KIBANA_COOKIE` | no | Paste a browser `sid=...` cookie; used if password login fails. |
| `KIBANA_VERSION` | no | Pins the `kbn-version` header. Leave unset to autodetect. |
| `KIBANA_INDEX_PATTERN` | no | Default index pattern for every tool. |
| `KIBANA_VERIFY_SSL` | no | `false` accepts a self-signed / internal CA certificate. |

---

## MCP Client Configuration

Registered for this repository in `.mcp.json` at the repo root. The client runs `launch.sh`, which
execs the virtualenv's interpreter, so there is no venv to activate and a missing `.venv` rebuilds
itself instead of failing startup with an exec error the client reports only as "server exited".

```json
{
  "mcpServers": {
    "kibana-explorer": {
      "command": "bash",
      "args": [
        "${CLAUDE_PROJECT_DIR}/ai-first-fw/local-mcps/kibana-explorer/launch.sh"
      ]
    }
  }
}
```

`launch.sh` writes only to stderr; stdout is left to the JSON-RPC stream.

The same block works for Antigravity (`~/.gemini/config/mcp_config.json`) and Claude Desktop
(`claude_desktop_config.json`).

> If an older `kibana` server is still registered globally (e.g. in `~/.claude.json`), remove that
> entry — two servers claiming the same name is what produces `Server kibana unavailable`.

---

## Available MCP Tools

| Tool | Parameters | Description / When to Use |
| :--- | :--- | :--- |
| `kibana_trace_pipeline` | `ids`, `stages`, `time_range`, `start`, `end`, `index_pattern` | **Trace specific entities (orders, SKUs, events, tracking SNs) across multi-hop integration stages.** Pinpoints exact drop stage. |
| `kibana_pipeline_health` | `ingress_kql`, `egress_kql`, `error_kql`, `time_range`, `start`, `end`, `interval`, `index_pattern` | **Measure throughput, backlog, and drop rate between any upstream and downstream stage over time.** Returns overall health status. |
| `kibana_detect_service_gaps` | `kql`, `time_range`, `start`, `end`, `min_gap_minutes`, `index_pattern` | **Detect service downtime, silent periods, crashed workers, or dead queue consumers.** Checks for restart events following gaps. |
| `kibana_search_logs` | `kql`, `query`, `time_range`, `start`, `end`, `service_name`, `log_level`, `limit`, `index_pattern`, `sort` | Search logs by KQL and return formatted documents. `query` is a deprecated alias for `kql`. |
| `kibana_count_logs` | `kql`, `time_range`, `start`, `end`, `service_name`, `log_level`, `index_pattern` | Count matches without returning documents. |
| `kibana_log_histogram` | `kql`, `time_range`, `interval`, `start`, `end`, `breakdown_field`, `service_name`, `log_level`, `index_pattern` | Bucket matches over time to find when a spike started. |
| `kibana_field_values` | `field`, `kql`, `time_range`, `start`, `end`, `size`, `index_pattern` | Top values of a field with counts — discover services, hosts, levels. |
| `kibana_get_recent_errors` | `service_name`, `time_range`, `limit`, `index_pattern` | Shortcut for recent errors and exceptions. |
| `kibana_translate_kql` | `kql` | Show the Query DSL a KQL string produces, without running it. |
| `kibana_raw_bsearch` | `body`, `index_pattern` | Escape hatch for raw Query DSL and aggregations. |
| `kibana_check_connection` | — | Version, login, and probe-query health check. |

---

## AI Agent Decision Guide (Which Tool to Choose?)

```
                     USER REQUEST / GOAL
                              │
  ┌───────────────────────────┼───────────────────────────┐
  ▼                           ▼                           ▼
"Why is order X stuck?"    "Is the stock sync        "Did the service crash?"
"Trace these 50 IDs"       healthy right now?"       "Find downtime windows"
"Where did message drop?"  "Measure drop/lag"        "Check dead consumers"
  │                           │                           │
  ▼                           ▼                           ▼
[kibana_trace_pipeline]   [kibana_pipeline_health]   [kibana_detect_service_gaps]
  │                           │                           │
  ├─> Traces sequential hops  ├─> Ingress vs Egress       ├─> Scans 0-log periods
  └─> Funnel drop-off matrix  └─> Drop rate % & Status    └─> Flags restart events
```

* **Need raw log details for a single query?** $\rightarrow$ `kibana_search_logs`
* **Need quick hit count only?** $\rightarrow$ `kibana_count_logs`
* **Need time-series spike chart?** $\rightarrow$ `kibana_log_histogram`
* **Need recent ERROR stack traces?** $\rightarrow$ `kibana_get_recent_errors`

---

## Behaviour notes

Two things here are deliberate, and both cost a debugging session to find.

**Async search is polled to completion, and a timeout raises.** Kibana's first
`/internal/bsearch` response for a wide time range routinely arrives with no `rawResponse`
attached. Returning it as-is reads as *zero hits* — a silent wrong answer, and far worse than
an error, because nothing about the result looks broken. The loop therefore waits until Kibana
both stops reporting `isRunning` **and** has attached a response, and raises `RuntimeError`
after 60s rather than reporting an empty result. If you hit that error, narrow the window or
add a filter; do not read it as "no matching logs".

**`query` is a deprecated alias for `kql`.** The parameter was originally named `query`.
Renaming it outright meant any client still holding the old tool schema sent `query`, had it
silently dropped, and got an unfiltered match against the whole index. The alias exists so a
stale caller keeps filtering. Prefer `kql` in new work.

---

## Tests

Both suites run offline — no Kibana, no network, standard library only:

```bash
V=ai-first-fw/local-mcps/kibana-explorer/.venv/bin/python3
$V ai-first-fw/local-mcps/kibana-explorer/test_kql.py     # 34 tests — KQL translation
$V ai-first-fw/local-mcps/kibana-explorer/test_server.py  # 6 tests  — bsearch polling
```

Run `test_kql.py` after any change to `kql.py`, and `test_server.py` after any change to
`_bsearch`. The polling tests stub the HTTP layer, so they catch the silent-zero-hits
regression without a live cluster.
