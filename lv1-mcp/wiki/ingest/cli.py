"""`wiki-ingest`: argparse, the run loop over `swarm.wiki`, report printing, `main()`.

Imports neither `mcp` nor `psycopg` at module scope, and never imports `swarm.wiki.server`
- only `_build_store`'s inner closure touches `psycopg`, lazily, the first time a real
`WikiStore` method actually runs. That keeps this module importable, and `run` callable
against a fake store, with neither dependency installed.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Protocol

from ..common import actor as default_actor
from ..config import Config, Limits, load_config
from ..tools import get as wiki_get
from ..tools import upsert as wiki_upsert

from .parse import parse_markdown
from .plan import PlannedFile, Report, SourceCollision, discover


class Store(Protocol):
    """The narrow slice of `WikiStore` this loader needs: read and write one section.

    A Protocol, not an import of `swarm.wiki.store.WikiStore` - a test builds a plain
    object with these two methods and passes it to `run`, proving the whole loader
    (path mapping, chunking, idempotence, dry-run) with no `psycopg` and no live
    PostgreSQL. `swarm.wiki.tools.get`/`.upsert` are what actually call these methods;
    this loader calls only those two functions, never `fetch`/`upsert_section` directly.
    """

    def fetch(
        self, source_id: str, section: str | None = None, include_retired: bool = False
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]: ...

    def upsert_section(
        self,
        source_id: str,
        section: str,
        body: str,
        summary: str,
        expected_version: int,
        title: str | None = None,
        actor: str = "user",
    ) -> tuple[int, bool]: ...


def _current_chunks(store: Store, source_id: str) -> dict[str, dict[str, Any]]:
    """Reads a source's live sections as `{section: {version, body, summary, ...}}`.

    `wiki.get` is enveloped, not exception-raising: a source with no row yet comes back
    as `{"ok": False, "error": {"code": "not_found", ...}}`, which this reads as "nothing
    live yet" rather than a failure to handle - a brand-new source_id is the common case,
    not an edge case.
    """
    result = wiki_get(store, source_id, include_retired=False)
    if not result["ok"]:
        return {}
    return {chunk["section"]: chunk for chunk in result["chunks"]}


def ingest_file(
    store: Store,
    planned: PlannedFile,
    limits: Limits,
    report: Report,
    dry_run: bool,
    actor: str | None,
) -> None:
    """Parses one file, diffs it against the wiki's current live sections, writes the delta.

    Idempotence (CONTRACT.md SS6, the loader's central requirement): `expected_version`
    always comes from a version just read for that exact section, and a chunk whose body
    and summary already match what is stored is counted as skipped and never sent to
    `wiki.upsert` - so a no-op re-ingest bumps no version and adds no changelog row.
    `--dry-run` runs every read and every comparison but stops short of the `upsert` call
    itself, so the counters describe what the run *would* do without writing anything.
    A section still live in the wiki but no longer produced by this file is listed as an
    orphan, never retired - CONTRACT.md SS6 forbids automatic retirement.
    """
    text = planned.path.read_text(encoding="utf-8")
    report.files_read += 1

    document = parse_markdown(text, limits)
    title = document.title or planned.path.stem

    warned_sections = {section for section, _message in document.warnings}
    report.sections_warned += len(warned_sections)
    report.chunk_warnings.extend(
        f"{planned.source_id}#{section}: {message}" for section, message in document.warnings
    )

    current = _current_chunks(store, planned.source_id)
    new_sections = {chunk.section for chunk in document.chunks}
    wrote_any = False

    for chunk in document.chunks:
        existing = current.get(chunk.section)
        expected_version = existing["version"] if existing else 0
        unchanged = (
            existing is not None
            and existing["body"] == chunk.body
            and existing["summary"] == chunk.summary
        )
        if unchanged:
            report.sections_skipped += 1
            continue

        wrote_any = True
        if dry_run:
            report.sections_written += 1
            continue

        result = wiki_upsert(
            store,
            planned.source_id,
            chunk.section,
            chunk.body,
            chunk.summary,
            expected_version,
            title=title,
            actor=actor,
        )
        if result["ok"]:
            report.sections_written += 1
        else:
            error = result["error"]
            report.write_errors.append(
                (planned.source_id, chunk.section, f"{error['code']}: {error['message']}")
            )

    if wrote_any:
        report.sources_written.add(planned.source_id)

    for section in sorted(set(current) - new_sections):
        report.orphans.append((planned.source_id, section))


def run(
    store: Store,
    roots: list[Path],
    prefix: str | None,
    dry_run: bool,
    actor: str | None,
    limits: Limits,
) -> Report:
    """Discovers every `*.md` file under ROOTS, then ingests each in sorted path order.

    `plan.discover` walks every ROOT and checks the whole run's source_ids for collisions
    before this function reads or writes a single file - CONTRACT.md SS6's "abort the
    whole run before ANY write". A `SourceCollision` therefore propagates out of `run`
    with nothing touched.
    """
    report = Report(dry_run=dry_run)
    for planned in discover(roots, prefix=prefix):
        ingest_file(store, planned, limits, report, dry_run, actor)
    return report


def _build_store(config: Config) -> Any:
    """Builds a real `WikiStore` whose connection is opened lazily, per call, not here."""
    from ..embed import Embedder
    from ..store import WikiStore

    def connect() -> Any:
        import psycopg

        return psycopg.connect(config.postgres_dsn)

    # Ingest allows oversized fenced code blocks and tables kept whole by parse.py to be stored
    limits = config.limits
    ingest_limits = Limits(
        body_max_words=100_000,
        summary_max_words=limits.summary_max_words,
    )
    embedder = Embedder(
        config.embedder.url,
        config.embedder.model,
        config.embedder.dimensions,
        config.embedder.timeout_s,
        config.embedder.batch_size,
        enabled=config.embedder.enabled,
    )
    return WikiStore(connect, ingest_limits, embedder, inbox_prefix=config.wiki.inbox_prefix)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="wiki-ingest", description="One-time markdown loader into the wiki."
    )
    parser.add_argument(
        "roots", metavar="ROOT", nargs="+", help="Directories to walk for *.md files."
    )
    parser.add_argument("--prefix", default=None, help="Prepended to every derived source_id.")
    parser.add_argument(
        "--dry-run", action="store_true", help="Print the report; write nothing to the wiki."
    )
    parser.add_argument(
        "--actor", default=None, help="Changelog actor for every write; defaults to actor()."
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Entry point registered as `wiki-ingest`. Loads config, runs, prints the report.

    @return 0 whether or not individual sections hit a write error (the report lists
        those); 1 only if `plan.discover` finds a source_id collision, printed to stderr
        instead of a report, since nothing ran
    """
    args = _parse_args(argv)
    config = load_config()
    roots = [Path(r) for r in args.roots]

    try:
        store = _build_store(config)
        report = run(store, roots, args.prefix, args.dry_run, args.actor, config.limits)
    except SourceCollision as exc:
        print(f"wiki-ingest aborted: {exc}", file=sys.stderr)
        return 1

    print(report.render())
    return 0


if __name__ == "__main__":  # pragma: no cover - manual run
    raise SystemExit(main())
