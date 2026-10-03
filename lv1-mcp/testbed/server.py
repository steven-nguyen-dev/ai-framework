"""FastMCP wiring for the `testbed` server. A thin async adapter over `tools.py`.

Every tool does network or subprocess work, so each wrapper runs the sync tool function in a thread:
a sync `@mcp.tool()` would block the stdio loop for the whole call.

    python -m testbed.server              stdio MCP server
    python -m testbed.server --selftest   config, servers and lease check (secrets never printed)
"""

from __future__ import annotations

import json
import sys
from typing import Any

import anyio.to_thread
from mcp.server.fastmcp import FastMCP

from . import tools
from .config import load_config

mcp = FastMCP("testbed")


async def _call(fn, *args: Any, **kwargs: Any) -> dict[str, Any]:
    config = load_config()
    return await anyio.to_thread.run_sync(lambda: fn(config, *args, **kwargs))


# ---- mock content ----

@mcp.tool()
async def mocks_diff(mock: str) -> dict[str, Any]:
    """Lists added / changed / deleted files between the git checkout of the mock's content and the cloud."""
    return await _call(tools.mocks_diff, mock)


@mcp.tool()
async def mocks_push(mock: str, dry_run: bool = False) -> dict[str, Any]:
    """Uploads the mock's changed and deleted files from git and applies them (restarts the mock). Refused while a run is active or the lease is held."""
    return await _call(tools.mocks_push, mock, dry_run)


@mcp.tool()
async def mocks_rollback(mock: str) -> dict[str, Any]:
    """Swaps the mock's previous content back in and restarts it. Refused while a run is active or the lease is held."""
    return await _call(tools.mocks_rollback, mock)


@mcp.tool()
async def mocks_status(mock: str | None = None) -> dict[str, Any]:
    """Returns one mock's server entry (status, content_path, pushed version) and health, or all mocks when omitted."""
    return await _call(tools.mocks_status, mock)


# ---- mock runtime ----

@mcp.tool()
async def lease_status() -> dict[str, Any]:
    """Returns the portal lease (holder, purpose, expiry) and this server's active run, if any."""
    return await _call(tools.lease_status)


@mcp.tool()
async def stores_get(mock: str, name: str | None = None) -> dict[str, Any]:
    """Returns one store's value, or every store of the mock when `name` is omitted."""
    return await _call(tools.stores_get, mock, name)


@mcp.tool()
async def stores_put(mock: str, name: str, value: Any, mode: str = "replace") -> dict[str, Any]:
    """Writes a mock store. mode: replace | append (value is a list) | merge (value is an object)."""
    return await _call(tools.stores_put, mock, name, value, mode)


@mcp.tool()
async def reset(mock: str, stores: list[str] | None = None, log: bool = False, files: bool = False) -> dict[str, Any]:
    """Resets the mock's stores (all when omitted), optionally its call log and scenario files."""
    return await _call(tools.reset, mock, stores, log, files)


@mcp.tool()
async def call_log(mock: str, after_seq: int | None = None, since: str | None = None, limit: int = 50) -> dict[str, Any]:
    """Returns the mock's recorded calls (HAR entries, secrets masked): the last `limit` after `after_seq` or `since`."""
    return await _call(tools.call_log, mock, after_seq, since, limit)


# ---- engine, offline ----

@mcp.tool()
async def suite_validate(items: list[str]) -> dict[str, Any]:
    """Validates case files or suite folders (schema, registry, references). Paths: relative to testbed-dev (`suites/...`), relative to the lv1-servers root (`testbed-dev/suites/...`) or absolute inside testbed-dev; anything resolving outside testbed-dev is rejected."""
    return await _call(tools.suite_validate, items)


@mcp.tool()
async def suite_lint(suite_dirs: list[str]) -> dict[str, Any]:
    """Checks suite folders against the five-type layout (suite/LAYOUT.md). Paths: relative to testbed-dev (`suites/...`), relative to the lv1-servers root (`testbed-dev/suites/...`) or absolute inside testbed-dev; anything resolving outside testbed-dev is rejected."""
    return await _call(tools.suite_lint, suite_dirs)


@mcp.tool()
async def suite_list(items: list[str], markers: str | None = None) -> dict[str, Any]:
    """Lists cases (id, reqs, title, stage, skip reason) of case files or suite folders; `markers` filters by REQ[,REQ]. Paths: relative to testbed-dev (`suites/...`), relative to the lv1-servers root (`testbed-dev/suites/...`) or absolute inside testbed-dev; anything resolving outside testbed-dev is rejected."""
    return await _call(tools.suite_list, items, markers)


@mcp.tool()
async def suite_judge(case_file: str, run_dir: str, cases: list[str] | None = None) -> dict[str, Any]:
    """Re-judges a case file against an existing run folder offline. Writes nothing into the folder. `case_file`: relative to testbed-dev (`suites/...`), relative to the lv1-servers root (`testbed-dev/suites/...`) or absolute inside testbed-dev; anything resolving outside testbed-dev is rejected. `run_dir` is an absolute run folder (it lives outside testbed-dev)."""
    return await _call(tools.suite_judge, case_file, run_dir, cases)


# ---- engine, live ----

@mcp.tool()
async def run_start(target: str, cases: list[str] | None = None, markers: str | None = None, fast: bool = False) -> dict[str, Any]:
    """Starts a live suite run in the background and returns its run_id. Refused while a run is active or the lease is held. `target`: relative to testbed-dev (`suites/...`), relative to the lv1-servers root (`testbed-dev/suites/...`) or absolute inside testbed-dev; anything resolving outside testbed-dev is rejected."""
    return await _call(tools.run_start, target, cases, markers, fast)


@mcp.tool()
async def run_status(run_id: str, tail: int = 40) -> dict[str, Any]:
    """Returns a run's state (running / finished / lost), exit code, run folder, summary and output tail."""
    return await _call(tools.run_status, run_id, tail)


@mcp.tool()
async def run_result(run_id: str) -> dict[str, Any]:
    """Returns a run's per-case verdict table, summary, run folder and run.json."""
    return await _call(tools.run_result, run_id)


@mcp.tool()
async def run_list(limit: int = 20) -> dict[str, Any]:
    """Lists registry runs, newest first."""
    return await _call(tools.run_list, limit)


@mcp.tool()
async def run_stop(run_id: str) -> dict[str, Any]:
    """Stops a running live run (SIGTERM; the engine releases the lease)."""
    return await _call(tools.run_stop, run_id)


def selftest() -> int:
    config = load_config()
    print("config:", json.dumps(config.describe()))
    servers = tools.mocks_status(config)
    print("servers:", "ok, %d mocks" % len(servers["mocks"]) if servers["ok"] else json.dumps(servers))
    lease = tools.lease_status(config)
    print("lease:", json.dumps(lease))
    return 0 if servers["ok"] and lease["ok"] else 1


def main() -> None:
    if "--selftest" in sys.argv[1:] or "--test" in sys.argv[1:]:
        sys.exit(selftest())
    mcp.run()


if __name__ == "__main__":  # pragma: no cover - manual run
    main()
