"""Ingest package: the `wiki-ingest` one-time markdown loader.

`parse.py` is pure (markdown text -> chunks); `plan.py` maps files to source_ids and
detects collisions; `cli.py` wires both to `swarm.wiki`'s shared write path and runs
the loop. Nothing here imports `mcp`, and `psycopg` is touched only lazily, inside
`cli._build_store`, never at import time.
"""

from __future__ import annotations

from .parse import ParsedChunk, ParsedDocument, parse_markdown
from .plan import PlannedFile, Report, SourceCollision, discover, source_id_for

__all__ = [
    "ParsedChunk",
    "ParsedDocument",
    "PlannedFile",
    "Report",
    "SourceCollision",
    "discover",
    "parse_markdown",
    "source_id_for",
]
