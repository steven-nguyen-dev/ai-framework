"""The wiki tools as plain functions over a `WikiStore`, testable without MCP.

Each returns the CONTRACT.md SS3 envelope directly - `{"ok": True, ...}` on success,
`{"ok": False, "error": {...}}` on an expected failure - so a test calls one with a
fake store and asserts on a plain dict, and `server.py` only has to bind a real
store and register the function under its MCP name.

`upsert` and `retire` live here too, unchanged, for `wiki-ingest` and
`scripts/inbox.py` to call directly - CONTRACT.md SS5b keeps both off the MCP
surface (`swarm.wiki.server` registers `note` instead), but neither this module
nor `store.py` enforces that boundary; it is structural, a fact about which
tools `build_server` registers, not a check either of them runs.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Any

from .common import NotFoundError, ToolError, ValidationError, VersionConflict, ok, slugify
from .common import actor as _default_actor

from .store import WikiStore


def _enveloped(fn: Callable[..., dict[str, Any]]) -> Callable[..., dict[str, Any]]:
    """Turns a raised `ToolError` into the failure envelope; a plain return into success.

    The wrapped function returns tool-specific fields only (e.g. `{"hits": [...]}`);
    this applies `ok(**fields)` around them, so no tool below repeats that shape.
    """

    @wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> dict[str, Any]:
        """Calls `fn`, turning a raised `ToolError` into its envelope, else into `ok`."""
        try:
            fields = fn(*args, **kwargs)
        except ToolError as exc:
            return exc.to_dict()
        return ok(**fields)

    return wrapper


@_enveloped
def search(
    store: WikiStore,
    query: str,
    k: int = 5,
    source_prefix: str | None = None,
    include_inbox: bool = False,
) -> dict[str, Any]:
    """Searches live wiki chunks by full text, trigram similarity and vector distance, RRF-fused.

    See `WikiStore.search` for the ranking, the CJK fallback, the fusion, and the inbox
    exclusion it documents. Returns `{ok, vector_available, hits:
    [{source_id, section, version, summary, body, score, matched_by}]}`.
    """
    hits, vector_available = store.search(
        query, k=k, source_prefix=source_prefix, include_inbox=include_inbox
    )
    return {"vector_available": vector_available, "hits": hits}


@_enveloped
def get(
    store: WikiStore,
    source_id: str,
    section: str | None = None,
    include_retired: bool = False,
) -> dict[str, Any]:
    """Fetches one source and its chunks by exact identity; retired rows are opt-in.

    Returns `{ok, source: {source_id, title, version, updated_at, updated_by}, chunks: [...]}`.
    """
    source, chunks = store.fetch(source_id, section=section, include_retired=include_retired)
    return {"source": source, "chunks": chunks}


_NOTE_SECTION = "note"
"""The one fixed section every `note` writes to.

CONTRACT.md SS5b: `note` takes no `section` argument at all - "one note is one chunk"
needs exactly one section name to express that, and a caller-supplied one would just
recreate the field the tool exists to remove. `"note"` is an ordinary slug (`slugify`
leaves it unchanged), so it satisfies `WikiStore.upsert_section`'s own "already a slug"
check the same as any section a human-authored source picks."""


def _validate_slug(slug: str) -> None:
    """Rejects anything that is not already a bare, non-empty slug with no `/` in it.

    CONTRACT.md SS5b: `note` builds `source_id` by interpolating `slug` after
    `<inbox_prefix><pane>/`, so a `slug` carrying its own `/` - plain, `../`, or a leading
    `/` - could otherwise walk the result outside the pane's own inbox namespace
    (`inbox/<pane>/../../trap/x` names a source the pane was never granted). The explicit
    `/` check names that risk directly; the `slugify` equality check behind it catches
    every other non-slug shape - capitals, spaces, dots, a bare empty string once
    stripped - for the same reason `upsert_section` rejects a non-slug `section`: a value
    `slugify` would still change was never a slug to begin with.

    @raises ValidationError if `slug` is empty or whitespace-only, contains `/`, or is not
        already in `slugify` form
    """
    if not slug.strip():
        raise ValidationError("slug must not be empty", field="slug", actual=slug)
    if "/" in slug:
        raise ValidationError(
            "slug must not contain '/' - it would escape the pane's own inbox namespace",
            field="slug",
            actual=slug,
        )
    if slug != slugify(slug):
        raise ValidationError(
            "slug must already be a slug (lowercase, hyphenated) - call swarm.common.slugify first",
            field="slug",
            actual=slug,
        )


def _current_note_version(store: WikiStore, source_id: str) -> int:
    """Returns the note's stored version, or `0` when nothing is filed there yet.

    `store.fetch` raises `NotFoundError` alike for an unknown source and an unknown
    section - both mean the same thing to a fresh note: there is nothing to overwrite, so
    the write below goes in as `expected_version=0`, matching CONTRACT.md SS5 rule 3
    ("new section -> pass 0").
    """
    try:
        _source, chunks = store.fetch(source_id, section=_NOTE_SECTION)
    except NotFoundError:
        return 0
    return chunks[0]["version"] if chunks else 0


@_enveloped
def note(
    store: WikiStore,
    slug: str,
    body: str,
    summary: str,
    actor: str | None = None,
) -> dict[str, Any]:
    """Files one inbox note at `<inbox_prefix><pane>/<slug>`; re-noting overwrites it.

    CONTRACT.md SS5b: the swarm's *only* write tool, replacing `upsert`/`retire` on the
    MCP surface entirely - `slug`, `body` and `summary` are the whole signature. There is
    no `source_id`, `section` or `expected_version` parameter here for a caller to name a
    curated chunk with; every note lands in `_NOTE_SECTION`, the one section this function
    ever writes.

    Version handling is internal and invisible, per the doc: this reads the note's current
    version (`_current_note_version`, `0` when it does not exist yet) and writes against
    it, so a second `note` call for the same `slug` overwrites in place rather than ever
    surfacing a version to the caller. If a concurrent write already moved the version
    between that read and this write - the same pane racing itself - this retries exactly
    once, against the version the resulting `VersionConflict` itself reports, rather than
    letting that conflict become a `version_conflict` envelope the caller was never meant
    to see.

    @param slug validated by `_validate_slug` before `actor` is even resolved: empty,
        whitespace, containing `/`, or any other non-slug shape is `validation`
    @param actor overrides `swarm.common.actor()`; the MCP-registered `note` tool never
        passes it - mirrors the override hook `upsert`/`retire` already carry, present for
        parity and any future direct caller rather than anything the swarm itself uses
    @return `{ok, source_id}` - the identity this note was filed under, for the agent to
        cite
    """
    _validate_slug(slug)
    resolved_actor = actor if actor is not None else _default_actor()
    source_id = f"{store.inbox_prefix}{resolved_actor}/{slug}"
    expected_version = _current_note_version(store, source_id)
    try:
        store.upsert_section(
            source_id, _NOTE_SECTION, body, summary, expected_version, actor=resolved_actor
        )
    except VersionConflict as exc:
        store.upsert_section(
            source_id,
            _NOTE_SECTION,
            body,
            summary,
            exc.extra["current_version"],
            actor=resolved_actor,
        )
    return {"source_id": source_id}


@_enveloped
def upsert(
    store: WikiStore,
    source_id: str,
    section: str,
    body: str,
    summary: str,
    expected_version: int,
    title: str | None = None,
    actor: str | None = None,
) -> dict[str, Any]:
    """Writes one section, versioned against `expected_version`; this is the wiki's one write path.

    **Shared entry point.** `wiki-ingest` imports this function directly and
    calls it exactly as `wiki-mcp` does, so the loader never reimplements the
    chunk validation or the SQL in `WikiStore.upsert_section`. The `actor`
    keyword is that reuse point: the MCP-registered tool never passes it (it
    always resolves to `swarm.common.actor()`, this pane's identity from
    `SWARM_PANE`), while the loader passes its own `--actor NAME` override so a
    batch ingest run is attributed to the name the operator chose, not to
    whichever pane happened to run it.

    Returns `{ok, source_id, section, version, embedded}`. `embedded` is `False` whenever
    the embedder was absent, disabled or failed for this call - the write itself never
    fails for it (CONTRACT.md SS5a). A version mismatch returns `{ok: False, error:
    {code: "version_conflict", current_version, current_body, current_summary, ...}}` to
    merge against, per CONTRACT.md SS5 rule 3.
    """
    resolved_actor = actor if actor is not None else _default_actor()
    version, embedded = store.upsert_section(
        source_id,
        section,
        body,
        summary,
        expected_version,
        title=title,
        actor=resolved_actor,
    )
    return {"source_id": source_id, "section": section, "version": version, "embedded": embedded}


@_enveloped
def retire(
    store: WikiStore,
    source_id: str,
    section: str | None = None,
    note: str = "",
    actor: str | None = None,
) -> dict[str, Any]:
    """Retires one section, or every live section of a source; `note` is required.

    Returns `{ok, retired: [section, ...]}`. `actor` mirrors `upsert`'s override
    hook for callers outside the MCP path; it is not part of the registered
    `wiki.retire` tool signature.
    """
    resolved_actor = actor if actor is not None else _default_actor()
    retired = store.retire_sections(source_id, section=section, note=note, actor=resolved_actor)
    return {"retired": retired}


@_enveloped
def render(store: WikiStore, source_id: str) -> dict[str, Any]:
    """Renders one source's live sections as citable markdown. Returns `{ok, markdown}`."""
    markdown = store.render_source(source_id)
    return {"markdown": markdown}


@_enveloped
def changelog(store: WikiStore, since: str, limit: int = 200) -> dict[str, Any]:
    """Lists changelog entries at or after `since`, oldest first.

    Returns `{ok, entries: [{source_id, section, version, action, actor, at, note}]}`.
    """
    entries = store.changelog_since(since, limit=limit)
    return {"entries": entries}
