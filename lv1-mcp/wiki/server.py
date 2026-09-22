"""FastMCP wiring for `wiki-mcp`: registers five tools over one `WikiStore`.

Only this module imports `mcp` or builds a real `psycopg` connection.
`queries.py`, `store.py` and `tools.py` stay importable - and are exercised by
tests - with neither package installed.

CONTRACT.md SS5b: `upsert` and `retire` are **not registered here**. The earlier design
enforced a write boundary at this layer (`_agent_write_rejection`, rejecting a `source_id`
outside `agent_write_prefix`) and has been replaced entirely - an agent cannot be argued
into calling, or misspell its way into calling, a tool that was never registered. Those two
tools still exist in `tools.py` for `wiki-ingest` and `scripts/inbox.py`, which import and
call them directly, never through this server.
"""

from __future__ import annotations

from functools import partial
from typing import Any

import anyio
from mcp.server.fastmcp import FastMCP

from .config import load_config

from . import tools
from .embed import Embedder
from .store import ConnectionFactory, WikiStore

SERVER_NAME = "wiki"

_CONNECT_TIMEOUT_S = 5
_STATEMENT_TIMEOUT_MS = 15_000


def _connect_factory(dsn: str) -> ConnectionFactory:
    """Builds a connection factory that imports `psycopg` only when actually called."""

    def _connect() -> Any:
        """Opens a psycopg connection to `dsn`, binding connect and statement timeouts."""
        import psycopg

        return psycopg.connect(
            dsn,
            connect_timeout=_CONNECT_TIMEOUT_S,
            options=f"-c statement_timeout={_STATEMENT_TIMEOUT_MS}",
        )

    return _connect


def _make_connection_pool(dsn: str) -> Any:
    """Builds a psycopg_pool.ConnectionPool holding warm in-memory connections for concurrency."""
    try:
        from psycopg_pool import ConnectionPool

        return ConnectionPool(
            conninfo=dsn,
            min_size=1,
            max_size=10,
            timeout=10.0,
            kwargs={
                "connect_timeout": _CONNECT_TIMEOUT_S,
                "options": f"-c statement_timeout={_STATEMENT_TIMEOUT_MS}",
            },
            open=True,
        )
    except Exception:
        return _connect_factory(dsn)


def build_server(store: WikiStore | None = None) -> FastMCP:
    """Registers the wiki tools on a fresh `FastMCP("wiki")` and returns it."""
    if store is None:
        config = load_config()
        embedder = Embedder(
            config.embedder.url,
            config.embedder.model,
            config.embedder.dimensions,
            config.embedder.timeout_s,
            config.embedder.batch_size,
            enabled=config.embedder.enabled,
        )
        store = WikiStore(
            _make_connection_pool(config.postgres_dsn),
            config.limits,
            embedder,
            inbox_prefix=config.wiki.inbox_prefix,
        )

    mcp = FastMCP(
        SERVER_NAME,
        instructions="Anchanto Internal Engineering Wiki: query domain knowledge, business rules, order lifecycles, and architecture specs.",
    )

    @mcp.tool()
    async def search(
        query: str,
        k: int = 5,
        source_prefix: str | None = None,
        include_inbox: bool = False,
    ) -> dict[str, Any]:
        """Searches Anchanto internal engineering wiki for domain knowledge, business rules, order lifecycles (RFP, RTS, in-transit), marketplace integrations (Shopee, Lazada, TikTok, etc.), WMS/OMS workflows, and system architecture using hybrid RRF search."""
        return await anyio.to_thread.run_sync(
            partial(
                tools.search,
                store,
                query,
                k=k,
                source_prefix=source_prefix,
                include_inbox=include_inbox,
            )
        )

    @mcp.tool()
    async def get(
        source_id: str, section: str | None = None, include_retired: bool = False
    ) -> dict[str, Any]:
        """Fetches one wiki source document and its sections by exact source ID (e.g. knowledges/core/oms/01-order-lifecycle-and-fulfillment)."""
        return await anyio.to_thread.run_sync(
            partial(tools.get, store, source_id, section=section, include_retired=include_retired)
        )

    @mcp.tool()
    async def note(slug: str, body: str, summary: str) -> dict[str, Any]:
        """Files one note into the inbox/ namespace for curated knowledge."""
        return await anyio.to_thread.run_sync(partial(tools.note, store, slug, body, summary))

    @mcp.tool()
    async def render(source_id: str) -> dict[str, Any]:
        """Renders one wiki source's live sections as citable markdown."""
        return await anyio.to_thread.run_sync(partial(tools.render, store, source_id))

    @mcp.tool()
    async def changelog(since: str, limit: int = 200) -> dict[str, Any]:
        """Lists changelog entries at or after `since`, oldest first."""
        return await anyio.to_thread.run_sync(partial(tools.changelog, store, since, limit=limit))

    return mcp


def main() -> None:
    """Serves the five wiki tools over stdio; the `wiki-mcp` console script's entry point."""
    build_server().run()


if __name__ == "__main__":  # pragma: no cover - exercised only by a live stdio client
    main()
