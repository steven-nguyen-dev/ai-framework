"""Wiki package: chunked PostgreSQL storage for the swarm's blackboard.

`wiki-ingest` imports `upsert` and `get` directly from this package - the same
validation, locking and changelog path `wiki-mcp` runs, so the loader never
reimplements the chunk rules or the SQL. Nothing here imports `mcp` or opens a
real database connection at import time; `swarm.wiki.server` is the only
submodule that does either, and only when its `main()` runs.
"""

from __future__ import annotations

from .store import WikiStore
from .tools import changelog, get, render, retire, search, upsert

__all__ = [
    "WikiStore",
    "changelog",
    "get",
    "render",
    "retire",
    "search",
    "upsert",
]
