"""FastMCP wiring for `swarm-coordinator-mcp`. A thin adapter over `tools.py`.

The `mcp` import lives only in this module, so `swarm.coordinator.tools` and
`swarm.coordinator.store` import and run without `mcp` installed - useful for a test that
drives the tool functions directly against `fakeredis`, with no MCP runtime in the loop.

CONTRACT §5's MCP adapter rule applies to both servers: FastMCP calls a sync `@mcp.tool()`
function inline on the asyncio event loop, with no offload of its own. Every tool function in
`tools.py` does a Redis round trip (and `delegate`/`complete` also run `subprocess.run` via
`prompt.py`, up to `prompt_timeout_s`), so a sync wrapper here would block the stdio server from
reading stdin - and answering any other pane - for that whole duration. Each wrapper below is
therefore `async def` and awaits `anyio.to_thread.run_sync` around the sync tool function, which
itself stays sync and stays testable without an event loop.
"""

from __future__ import annotations

from typing import Any

import anyio.to_thread
from mcp.server.fastmcp import FastMCP

from .config import Config, load_config

from . import tools
from .store import TaskStore, make_redis_client

_SERVER_NAME = "swarm-coordinator"

mcp = FastMCP(_SERVER_NAME)

_state: tuple[TaskStore, Config] | None = None


def _get_state() -> tuple[TaskStore, Config]:
    """Builds the store and config once per process, lazily.

    One redis client for the process lifetime. Every piece of per-call state (session id,
    leader, actor) still comes from the environment, read fresh inside `tools.py` on each
    call, not from anything cached here.
    """
    global _state
    if _state is None:
        config = load_config()
        client = make_redis_client(config)
        _state = (TaskStore(client, config), config)
    return _state


@mcp.tool()
async def delegate(target: str, brief: str, wiki_refs: list[str] = []) -> dict[str, Any]:  # noqa: B006 - CONTRACT §4 freezes this signature; tools.delegate copies the list and never mutates it
    """Delegates a task to `target`, writing `task:<id>` and prompting it. See CONTRACT.md §4."""
    store, config = _get_state()
    return await anyio.to_thread.run_sync(tools.delegate, store, config, target, brief, wiki_refs)


@mcp.tool()
async def complete(
    task_id: str, status: str, summary: str, result: str | None = None
) -> dict[str, Any]:
    """Reports a task's outcome, writing `result:<task_id>` and prompting the leader."""
    store, config = _get_state()
    return await anyio.to_thread.run_sync(
        tools.complete, store, config, task_id, status, summary, result
    )


@mcp.tool()
async def get(key: str) -> dict[str, Any]:
    """Reads any key in this session's namespace: `task:*`, `result:*`, `scratch:*`, `roster`."""
    store, _config = _get_state()
    return await anyio.to_thread.run_sync(tools.get, store, key)


@mcp.tool()
async def put(key: str, value: str) -> dict[str, Any]:
    """Writes a scratch payload and returns the key callers pass back to `get`."""
    store, config = _get_state()
    return await anyio.to_thread.run_sync(tools.put, store, config, key, value)


@mcp.tool()
async def session_log(limit: int = 20) -> dict[str, Any]:
    """Returns the roster plus the last `limit` session entries, oldest-first."""
    store, _config = _get_state()
    return await anyio.to_thread.run_sync(tools.session_log, store, limit)


def main() -> None:
    """Runs the stdio MCP server; registered as the `swarm-coordinator-mcp` entry point."""
    mcp.run()


if __name__ == "__main__":  # pragma: no cover - manual run
    main()
