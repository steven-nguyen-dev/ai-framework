#!/usr/bin/env python3
"""Compare, draft and promote one context folder across every project that shares it.

Four verbs:

  discover  read the roster out of a CLAUDE.md and print each project's context folder
  diff      compare every context file across every project, write report.md, report.json
            and a draft/ holding the merged files with each contradiction left as a marker
  promote   copy draft/ into every project's context folder, once no marker remains
  verify    re-run the comparison and exit non-zero while any difference stands

A *block* is the unit compared: one `**Term**:` entry, one heading line, or one run of
prose. An entry is keyed by its headword alone, so retitling the group above it moves the
entry rather than deleting and re-adding it; a rewrap is not a difference either, since
bodies compare with their line breaks collapsed.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path

# A roster line: "- **zero** — `/abs/path`"
ROSTER_RE = re.compile(
    r"^\s*[-*]\s+\*\*(?P<alias>[^*]+)\*\*\s*[—–:-]\s*[`\"']?(?P<path>[^`\"'\s]+)"
)
# An entry headword: "**Term**:" opening a line that follows a blank line or a heading.
ENTRY_RE = re.compile(r"^\*\*([^*]+)\*\*:")
CONFLICT_OPEN = "<<<<<<< CONFLICT"
CONFLICT_CLOSE = ">>>>>>> RESOLVE"


# --------------------------------------------------------------------------- model


@dataclass
class Block:
    """One comparable unit of a context file, with the lines it occupies."""

    kind: str  # "heading" | "entry" | "prose"
    key: str
    heading: str = ""  # the "## / ###" path the block sits under
    lines: list[str] = field(default_factory=list)
    start: int = 0
    end: int = 0

    @property
    def text(self) -> str:
        return "\n".join(self.lines)

    @property
    def norm(self) -> str:
        """The block's text with wrapping removed, so a reflow is not a difference."""
        paras = re.split(r"\n\s*\n", self.text)
        return "\n\n".join(" ".join(p.split()) for p in paras).strip()


@dataclass
class Project:
    alias: str
    root: Path
    context_dir: Path


# --------------------------------------------------------------------------- parsing


def parse_blocks(text: str) -> list[Block]:
    """Split one context file into blocks keyed by heading path and headword."""
    lines = text.splitlines()
    blocks: list[Block] = []
    h2 = h3 = ""
    prose_n = 0
    cur: Block | None = None
    prev_blank = True

    def flush() -> None:
        nonlocal cur
        if cur is not None:
            while cur.lines and not cur.lines[-1].strip():
                cur.lines.pop()
                cur.end -= 1
            if cur.lines:
                blocks.append(cur)
            cur = None

    for i, line in enumerate(lines, 1):
        if line.startswith("#"):
            flush()
            if line.startswith("### "):
                h3 = line[4:].strip()
            elif line.startswith("## "):
                h2, h3, prose_n = line[3:].strip(), "", 0
            elif line.startswith("# "):
                h2, h3, prose_n = "", "", 0
            blocks.append(Block("heading", f"H:{line.strip()}", f"{h2}/{h3}", [line], i, i))
            prev_blank = False
            continue

        m = ENTRY_RE.match(line)
        if m and prev_blank:
            flush()
            cur = Block("entry", f"E:{m.group(1).strip()}", f"{h2}/{h3}", [line], i, i)
        elif cur is None:
            if line.strip():
                prose_n += 1
                cur = Block("prose", f"P:{h2}/#{prose_n}", f"{h2}/{h3}", [line], i, i)
        else:
            cur.lines.append(line)
            cur.end = i
        prev_blank = not line.strip()

    flush()
    return blocks


# --------------------------------------------------------------------------- git


def repo_root(path: Path) -> Path | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=20,
        )
        return Path(out.stdout.strip()) if out.returncode == 0 else None
    except Exception:
        return None


def file_time(file: Path) -> str:
    return datetime.fromtimestamp(file.stat().st_mtime, tz=timezone.utc).isoformat()


def block_time(file: Path, start: int, end: int) -> str:
    """The newest author time across the block's lines; the file's mtime where git cannot say.

    A context folder is commonly untracked — `.git/info/exclude` — and blame then knows
    nothing about it, so every date falls back to the file and dates whole files, not blocks.
    """
    root = repo_root(file.parent)
    if root is None:
        return f"{file_time(file)} (file mtime)"
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "blame", "--porcelain",
             "-L", f"{start},{end}", "--", str(file.relative_to(root))],
            capture_output=True, text=True, timeout=60,
        )
        stamps = [
            int(l.split()[1]) for l in out.stdout.splitlines() if l.startswith("author-time ")
        ] if out.returncode == 0 else []
        if not stamps:
            return f"{file_time(file)} (file mtime)"
        return datetime.fromtimestamp(max(stamps), tz=timezone.utc).isoformat()
    except Exception:
        return f"{file_time(file)} (file mtime)"


def tracked(context_dir: Path) -> bool:
    """Whether git holds any file in this context folder.

    An ignored or excluded folder is invisible to `git status`, which then reports it clean
    however it stands, and holds no version to restore — so the caller backs it up instead
    of trusting the check.
    """
    root = repo_root(context_dir)
    if root is None:
        return False
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "ls-files", "--", str(context_dir)],
            capture_output=True, text=True, timeout=30,
        )
        return out.returncode == 0 and bool(out.stdout.strip())
    except Exception:
        return False


def dirty(context_dir: Path) -> list[str]:
    """Paths under the context folder that git reports as uncommitted."""
    root = repo_root(context_dir)
    if root is None:
        return []
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain", "--", str(context_dir)],
            capture_output=True, text=True, timeout=30,
        )
        return [l.strip() for l in out.stdout.splitlines() if l.strip()]
    except Exception:
        return []


# --------------------------------------------------------------------------- roster


def discover(claude_md: Path, context_dir_name: str) -> list[Project]:
    """Every project named in the CLAUDE.md roster whose context folder exists."""
    projects: list[Project] = []
    seen: set[Path] = set()
    for line in claude_md.read_text(encoding="utf-8").splitlines():
        m = ROSTER_RE.match(line)
        if not m:
            continue
        raw = m.group("path").strip()
        root = Path(raw).expanduser()
        if not root.is_absolute():
            root = (claude_md.parent / root).resolve()
        for candidate in (root / context_dir_name, root):
            if candidate.is_dir() and any(candidate.glob("*.md")):
                if candidate.resolve() in seen:
                    break
                seen.add(candidate.resolve())
                projects.append(Project(m.group("alias").strip(), root, candidate))
                break
    return projects


# --------------------------------------------------------------------------- compare


def tokens(text: str) -> set[str]:
    return set(re.sub(r"[^\w\s]", " ", text.lower()).split())


def rename_candidates(diffs: list[dict]) -> list[dict]:
    """Pairs of missing blocks that read as one block renamed, not two blocks added.

    Merging a rename as two additions leaves both names standing — two titles on one file,
    two glossary entries for one term — so each pair is reported for a deliberate call.
    """
    missing = [d for d in diffs if d["status"] == "missing"]
    pairs = []
    for i, a in enumerate(missing):
        for b in missing[i + 1:]:
            if a["kind"] != b["kind"]:
                continue
            held_a = {x for v in a["variants"] for x in v["held_by"]}
            held_b = {x for v in b["variants"] for x in v["held_by"]}
            if held_a & held_b:
                continue  # one copy holds both, so they are two blocks, not one renamed
            ta, tb = a["variants"][0]["text"], b["variants"][0]["text"]

            def sim(x: str, y: str) -> float:
                return SequenceMatcher(None, " ".join(x.split()), " ".join(y.split())).ratio()

            # A renamed entry keeps its body and changes only its headword line, so the body
            # carries the stronger signal of the two.
            ba, bb = ta.split("\n", 1)[-1], tb.split("\n", 1)[-1]
            body = sim(ba, bb) if a["kind"] == "entry" else 0.0
            ratio = max(sim(ta, tb), body)
            # A rewritten rename expands its body, which a character ratio penalises for
            # length; how much of the shorter body the longer one contains does not.
            wa, wb = tokens(ba), tokens(bb)
            held = len(wa & wb) / min(len(wa), len(wb)) if wa and wb else 0.0
            sub = tokens(ta) <= tokens(tb) or tokens(tb) <= tokens(ta)
            if ratio >= 0.6 or held >= 0.7 or sub:
                pairs.append({
                    "kind": a["kind"],
                    "keys": [a["key"], b["key"]],
                    "held_by": [sorted(held_a), sorted(held_b)],
                    "similarity": round(ratio, 2),
                    "containment": round(held, 2),
                })
    return pairs


def spine_of(parsed: dict[str, list[Block]]) -> str:
    """The copy whose block order the merge follows — the longest, ties by alias."""
    return max(sorted(parsed), key=lambda a: len(parsed[a]))


def merged_order(parsed: dict[str, list[Block]]) -> list[str]:
    """Every block key across every copy, each absent one placed after its own neighbour."""
    order = [b.key for b in parsed[spine_of(parsed)]]
    for blocks in parsed.values():
        for idx, b in enumerate(blocks):
            if b.key in order:
                continue
            at = len(order)
            for prev in reversed(blocks[:idx]):
                if prev.key in order:
                    at = order.index(prev.key) + 1
                    break
            order.insert(at, b.key)
    return order


def parse_all(projects: list[Project], name: str, aliases: list[str]) -> dict[str, list[Block]]:
    by = {p.alias: p for p in projects}
    return {
        a: parse_blocks((by[a].context_dir / name).read_text(encoding="utf-8")) for a in aliases
    }


def compare(projects: list[Project], pattern: str) -> dict:
    """Every difference across every context file, as a JSON-shaped dict."""
    names: list[str] = sorted({p.name for pr in projects for p in pr.context_dir.glob(pattern)})
    report: dict = {
        "projects": [{"alias": p.alias, "context_dir": str(p.context_dir)} for p in projects],
        "files": [],
    }

    for name in names:
        present = [p.alias for p in projects if (p.context_dir / name).is_file()]
        absent = [p.alias for p in projects if p.alias not in present]
        by_alias = {p.alias: p for p in projects}
        parsed = parse_all(projects, name, present)
        by_key = {a: {b.key: b for b in bs} for a, bs in parsed.items()}
        order = merged_order(parsed)

        # A file only one copy holds has nothing to compare block by block: the file-level
        # absence is the whole difference, and promoting the draft settles it.
        entries = []
        for key in order if len(present) > 1 else []:
            holders = [a for a in by_key if key in by_key[a]]
            variants: dict[str, list[str]] = {}
            for a in holders:
                variants.setdefault(by_key[a][key].norm, []).append(a)
            missing = [a for a in by_key if a not in holders]
            headings = {by_key[a][key].heading for a in holders}
            if len(variants) == 1 and not missing and len(headings) == 1:
                continue
            status = "conflict" if len(variants) > 1 else ("missing" if missing else "moved")
            entries.append({
                "key": key,
                "kind": by_key[holders[0]][key].kind,
                "status": status,
                "missing_from": sorted(missing),
                "variants": [
                    {
                        "held_by": sorted(aliases),
                        "heading": by_key[aliases[0]][key].heading,
                        "text": by_key[aliases[0]][key].text,
                        "last_touched": block_time(
                            by_alias[aliases[0]].context_dir / name,
                            by_key[aliases[0]][key].start,
                            by_key[aliases[0]][key].end,
                        ),
                    }
                    for aliases in variants.values()
                ],
            })

        report["files"].append({
            "name": name,
            "present_in": present,
            "absent_from": absent,
            "spine": spine_of(parsed),
            "block_count": len(order),
            "differences": entries,
            "rename_candidates": rename_candidates(entries),
        })

    report["difference_count"] = sum(len(f["differences"]) for f in report["files"]) + sum(
        len(f["absent_from"]) for f in report["files"]
    )
    report["rename_candidate_count"] = sum(len(f["rename_candidates"]) for f in report["files"])
    return report


# --------------------------------------------------------------------------- draft


def build_draft(projects: list[Project], report: dict, draft_dir: Path) -> None:
    """Write the merged union of every file, each contradiction left as a marker block."""
    draft_dir.mkdir(parents=True, exist_ok=True)
    diffs = {f["name"]: {d["key"]: d for d in f["differences"]} for f in report["files"]}

    for f in report["files"]:
        name = f["name"]
        parsed = parse_all(projects, name, f["present_in"])
        by_key = {a: {b.key: b for b in bs} for a, bs in parsed.items()}
        order = merged_order(parsed)

        out: list[str] = []
        for key in order:
            d = diffs[name].get(key)
            if d and d["status"] == "conflict":
                out.append(f"{CONFLICT_OPEN} {key}")
                for v in d["variants"]:
                    stamp = v["last_touched"] or "not in git"
                    out.append(f"--- {', '.join(v['held_by'])} ({stamp})")
                    out.append(v["text"])
                out.append(CONFLICT_CLOSE)
            else:
                holder = next(a for a in by_key if key in by_key[a])
                out.append(by_key[holder][key].text)
            out.append("")

        (draft_dir / name).write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")


def markers(draft_dir: Path) -> list[str]:
    """Every draft file still holding an unresolved conflict marker."""
    return sorted(
        p.name for p in draft_dir.glob("*.md")
        if CONFLICT_OPEN in p.read_text(encoding="utf-8")
    )


def duplicates(draft_dir: Path, report: dict | None = None) -> list[str]:
    """Every draft file that says one thing twice.

    Three shapes: a headword defined twice, a second `#` title, and a rename pair the merge
    kept both halves of — the last is why the report is read here rather than the file alone.
    """
    renames = {
        f["name"]: f["rename_candidates"] for f in (report or {}).get("files", [])
    }
    out = []
    for p in sorted(draft_dir.glob("*.md")):
        blocks = parse_blocks(p.read_text(encoding="utf-8"))
        keys = [b.key for b in blocks if b.kind == "entry"]
        found = []
        found += [f"`{k}` defined twice" for k in sorted({k for k in keys if keys.count(k) > 1})]
        titles = [b.lines[0] for b in blocks if b.kind == "heading" and b.lines[0].startswith("# ")]
        if len(titles) > 1:
            found.append(f"{len(titles)} titles: {', '.join(titles)}")
        present = {b.key for b in blocks}
        for rc in renames.get(p.name, []):
            if all(k in present for k in rc["keys"]):
                found.append(f"both halves of a rename: `{rc['keys'][0]}` and `{rc['keys'][1]}`")
        if found:
            out.append(f"{p.name}: " + "; ".join(found))
    return out


# --------------------------------------------------------------------------- report


def write_report(report: dict, path: Path) -> None:
    L: list[str] = ["# Context drift", ""]
    L.append(f"Projects: {', '.join(p['alias'] for p in report['projects'])}")
    for p in report["projects"]:
        L.append(f"- **{p['alias']}** — `{p['context_dir']}`")
    L += ["", f"Differences: **{report['difference_count']}**", "", "| file | present in | absent from | blocks | differences |", "|---|---|---|---|---|"]
    for f in report["files"]:
        L.append(
            f"| {f['name']} | {', '.join(f['present_in'])} | "
            f"{', '.join(f['absent_from']) or '—'} | {f['block_count']} | {len(f['differences'])} |"
        )

    for f in report["files"]:
        if not f["differences"] and not f["absent_from"]:
            continue
        L += ["", f"## {f['name']}", ""]
        if f["absent_from"]:
            L.append(f"Absent from: **{', '.join(f['absent_from'])}** — the whole file is a difference.")
            L.append("")
        if f["rename_candidates"]:
            L.append("**Reads as a rename** — keep one name, delete the other, rather than merging both:")
            for rc in f["rename_candidates"]:
                a, b = rc["keys"]
                ha, hb = rc["held_by"]
                L.append(
                    f"- `{a}` ({', '.join(ha)}) ↔ `{b}` ({', '.join(hb)}) — "
                    f"similarity {rc['similarity']}, containment {rc['containment']}"
                )
            L.append("")
        for d in f["differences"]:
            L.append(f"### `{d['key']}` — {d['status']} ({d['kind']})")
            if d["missing_from"]:
                L.append(f"Missing from: {', '.join(d['missing_from'])}")
            for v in d["variants"]:
                L.append(
                    f"- **{', '.join(v['held_by'])}** — under `{v['heading']}`, "
                    f"last touched {v['last_touched'] or 'not in git'}"
                )
                L.append("")
                L.append("  ```")
                L += [f"  {line}" for line in v["text"].splitlines()]
                L.append("  ```")
            L.append("")

    path.write_text("\n".join(L) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------- verbs


def cmd_discover(a) -> int:
    projects = discover(Path(a.claude_md), a.context_dir)
    for p in projects:
        print(f"{p.alias}\t{p.context_dir}")
    print(f"\n{len(projects)} project(s).")
    return 0 if projects else 1


def cmd_diff(a) -> int:
    projects = discover(Path(a.claude_md), a.context_dir)
    if len(projects) < 2:
        print("Fewer than two projects found — nothing to compare.", file=sys.stderr)
        return 1
    report = compare(projects, a.glob)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    write_report(report, out / "report.md")
    build_draft(projects, report, out / "draft")
    print(f"{report['difference_count']} difference(s) across {len(report['files'])} file(s); "
          f"{report['rename_candidate_count']} reading as a rename.")
    print(f"report: {out / 'report.md'}")
    print(f"draft:  {out / 'draft'}")
    left = markers(out / "draft")
    if left:
        print(f"conflict markers to resolve in: {', '.join(left)}")
    return 0


def cmd_promote(a) -> int:
    projects = discover(Path(a.claude_md), a.context_dir)
    draft_dir = Path(a.draft)
    left = markers(draft_dir)
    if left:
        print(f"Refusing: unresolved conflict markers in {', '.join(left)}", file=sys.stderr)
        return 2
    report_path = draft_dir.parent / "report.json"
    report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.is_file() else None
    dup = duplicates(draft_dir, report)
    if dup:
        print("Refusing: the draft says one thing twice — keep one, delete the other:", file=sys.stderr)
        for line in dup:
            print(f"  {line}", file=sys.stderr)
        return 2
    untracked = [p for p in projects if not tracked(p.context_dir)]
    if not a.force:
        for p in projects:
            if p in untracked:
                continue  # git reports an excluded folder clean however it stands
            d = dirty(p.context_dir)
            if d:
                print(f"Refusing: {p.alias} has uncommitted changes under its context folder:",
                      file=sys.stderr)
                for line in d:
                    print(f"  {line}", file=sys.stderr)
                return 2

    # An untracked folder has no committed version to restore, so the copy on disk is the
    # only one there is until the promote overwrites it.
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = Path(a.backup_dir) if a.backup_dir else draft_dir.parent / f"backup-{stamp}"
    for p in projects:
        dest = backup / p.alias
        dest.mkdir(parents=True, exist_ok=True)
        for f in sorted(p.context_dir.glob(a.glob)):
            shutil.copyfile(f, dest / f.name)
    print(f"backup: {backup}")
    if untracked:
        print(f"  (git holds no version of the context folder in: "
              f"{', '.join(p.alias for p in untracked)} — this backup is the only undo)")

    files = sorted(draft_dir.glob("*.md"))
    for p in projects:
        p.context_dir.mkdir(parents=True, exist_ok=True)
        for f in files:
            shutil.copyfile(f, p.context_dir / f.name)
        extra = sorted(
            x.name for x in p.context_dir.glob(a.glob) if x.name not in {f.name for f in files}
        )
        for name in extra:
            if a.prune:
                (p.context_dir / name).unlink()
        note = f" (pruned: {', '.join(extra)})" if extra and a.prune else (
            f" (extra, kept: {', '.join(extra)})" if extra else "")
        print(f"{p.alias}: {len(files)} file(s) written{note}")
    return 0


def cmd_verify(a) -> int:
    projects = discover(Path(a.claude_md), a.context_dir)
    report = compare(projects, a.glob)
    n = report["difference_count"]
    names = {tuple(sorted(x.name for x in p.context_dir.glob(a.glob))) for p in projects}
    same_set = len(names) == 1
    print(f"differences: {n}; identical file set: {same_set}")
    if n:
        for f in report["files"]:
            for d in f["differences"]:
                print(f"  {f['name']} :: {d['key']} :: {d['status']}")
            for miss in f["absent_from"]:
                print(f"  {f['name']} :: absent from {miss}")
    return 0 if n == 0 and same_set else 1


# --------------------------------------------------------------------------- cli


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--claude-md", required=True, help="the CLAUDE.md holding the project roster")
    ap.add_argument("--context-dir", default=".context", help="context folder name under each project root")
    ap.add_argument("--glob", default="*.md", help="which files in the context folder are compared")
    sub = ap.add_subparsers(dest="verb", required=True)

    sub.add_parser("discover").set_defaults(fn=cmd_discover)

    d = sub.add_parser("diff")
    d.add_argument("--out", required=True, help="directory for report.md, report.json and draft/")
    d.set_defaults(fn=cmd_diff)

    p = sub.add_parser("promote")
    p.add_argument("--draft", required=True, help="the resolved draft folder")
    p.add_argument("--force", action="store_true", help="promote over uncommitted changes")
    p.add_argument("--backup-dir", help="where each context folder is copied before it is overwritten")
    p.add_argument("--prune", action="store_true", help="delete context files absent from the draft")
    p.set_defaults(fn=cmd_promote)

    sub.add_parser("verify").set_defaults(fn=cmd_verify)

    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
