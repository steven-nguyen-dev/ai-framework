"""Files -> source_ids, collision detection, and the ingest report shape.

Path mapping and collision detection are pure over a file list. Directory discovery
touches the filesystem (`Path.rglob`) to build that list but never reads a file's
content - `cli.py` reads each planned file's text and hands it to `parse.parse_markdown`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath


@dataclass(frozen=True)
class PlannedFile:
    """One markdown file paired with the ROOT it was found under and its derived source_id."""

    root: Path
    path: Path
    source_id: str


class SourceCollision(Exception):
    """Two files map to the same source_id. Raised before any file is read or any write runs.

    CONTRACT.md SS6: a silent overwrite would destroy a source, so this is the whole
    run's abort signal - `cli.py` lets it propagate past every read and every upsert.
    """

    def __init__(self, source_id: str, paths: list[Path]) -> None:
        joined = ", ".join(str(p) for p in paths)
        super().__init__(f"source_id '{source_id}' is claimed by {len(paths)} files: {joined}")
        self.source_id = source_id
        self.paths = paths


def source_id_for(root: Path, file_path: Path, prefix: str | None = None) -> str:
    """Derives a source_id from `file_path`'s POSIX-relative path under `root`, minus its suffix.

    CONTRACT.md SS6: `knowledges/external-systems/lotteon.md` under ROOT `knowledges/`
    becomes `external-systems/lotteon`; `--prefix p` yields `p/external-systems/lotteon`.

    @raises ValueError if `file_path` does not lie under `root`
    """
    relative = file_path.resolve().relative_to(root.resolve())
    without_ext = relative.with_suffix("")
    posix = PurePosixPath(without_ext.as_posix()).as_posix()
    return f"{prefix}/{posix}" if prefix else posix


def discover(roots: list[Path], prefix: str | None = None) -> list[PlannedFile]:
    """Walks every ROOT for `*.md` files and maps each to its source_id, sorted by path.

    Every root is scanned and every source_id computed before the collision check runs,
    so the check sees the whole run's namespace at once - a collision across two
    different ROOTs is caught exactly like one within a single ROOT.

    @raises SourceCollision on the first (sorted) source_id two or more files share
    """
    planned: list[PlannedFile] = []
    by_source: dict[str, list[Path]] = {}

    for root in roots:
        resolved_root = root.resolve()
        if resolved_root.is_file():
            if resolved_root.suffix == ".md":
                base_dir = resolved_root.parent
                source_id = f"{prefix}/{resolved_root.stem}" if prefix else resolved_root.stem
                try:
                    rel_to_cwd = resolved_root.relative_to(Path.cwd().resolve())
                    if len(rel_to_cwd.parts) > 1:
                        base_candidate = (Path.cwd() / rel_to_cwd.parts[0]).resolve()
                        if base_candidate.is_dir():
                            base_dir = base_candidate
                            source_id = source_id_for(base_dir, resolved_root, prefix)
                except ValueError:
                    pass
                planned.append(PlannedFile(root=base_dir, path=resolved_root, source_id=source_id))
                by_source.setdefault(source_id, []).append(resolved_root)
            continue
        for file_path in sorted(resolved_root.rglob("*.md")):
            if not file_path.is_file():
                continue
            source_id = source_id_for(resolved_root, file_path, prefix)
            planned.append(PlannedFile(root=resolved_root, path=file_path, source_id=source_id))
            by_source.setdefault(source_id, []).append(file_path)

    collisions = {sid: paths for sid, paths in by_source.items() if len(paths) > 1}
    if collisions:
        source_id = sorted(collisions)[0]
        raise SourceCollision(source_id, collisions[source_id])

    return planned


@dataclass
class Report:
    """Everything CONTRACT.md SS6's "Output" row asks for, plus the warnings behind them.

    `sources_written` and the section counters describe what the run did (real) or would
    do (`--dry-run`, which never calls `wiki.upsert`) - the two runs fill this identically
    except that a dry run's sections never actually reach the database.
    """

    files_read: int = 0
    sources_written: set[str] = field(default_factory=set)
    sections_written: int = 0
    sections_skipped: int = 0
    sections_warned: int = 0
    chunk_warnings: list[str] = field(default_factory=list)
    orphans: list[tuple[str, str]] = field(default_factory=list)
    write_errors: list[tuple[str, str, str]] = field(default_factory=list)
    dry_run: bool = False

    def render(self) -> str:
        """Renders the report as plain text, in CONTRACT.md SS6's field order."""
        lines = [
            "wiki-ingest report" + (" (dry run - nothing written)" if self.dry_run else ""),
            f"files read: {self.files_read}",
            f"sources written: {len(self.sources_written)}",
            f"sections written: {self.sections_written}",
            f"sections skipped (unchanged): {self.sections_skipped}",
            f"sections warned: {self.sections_warned}",
        ]
        if self.chunk_warnings:
            lines.append("warnings:")
            lines.extend(f"  - {w}" for w in self.chunk_warnings)
        if self.orphans:
            lines.append("orphans (still in the wiki, no longer in any file - not retired):")
            lines.extend(f"  - {source_id}#{section}" for source_id, section in self.orphans)
        if self.write_errors:
            lines.append("write errors:")
            lines.extend(
                f"  - {source_id}#{section}: {message}"
                for source_id, section, message in self.write_errors
            )
        return "\n".join(lines)
