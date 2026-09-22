"""Markdown -> wiki chunks, as pure string transforms. No filesystem, no database.

This is CONTRACT.md SS6's chunking rule set, in isolation from path mapping (`plan.py`)
and the database (`cli.py`), so it is exercised with plain strings and no fake store.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..common import count_words, first_paragraph, slugify, trim_words
from ..config import Limits

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
_TABLE_SEP_RE = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True)
class ParsedChunk:
    """One wiki row this file will produce: a section slug, its body and its summary."""

    section: str
    body: str
    summary: str


@dataclass(frozen=True)
class ParsedDocument:
    """A file's title (if any) plus its ordered chunks and every chunking warning raised.

    `warnings` pairs each message with the heading-derived section it came from (before
    any overflow-part suffixing), so a caller can count *sections* warned about rather
    than raw warning messages - one oversized paragraph can raise two messages (the
    split notice, then a "still too big" notice for one sentence) against a single
    section.
    """

    title: str | None
    chunks: list[ParsedChunk]
    warnings: list[tuple[str, str]]


@dataclass(frozen=True)
class _Block:
    """One indivisible unit of section text: a paragraph, a fence, or a table."""

    kind: str  # "text" | "fence" | "table"
    text: str


def parse_markdown(text: str, limits: Limits) -> ParsedDocument:
    """Splits one markdown document into a title and CONTRACT.md SS6 chunks.

    Title is the first level-1 (`# `) heading; sections come from `##`+ headings via
    `slugify`, with content before the first one landing in section `intro`. A heading
    line inside a fenced code block is not a heading. Each section's body is then packed
    into <= `limits.body_max_words`-word parts at paragraph/fence/table boundaries;
    parts beyond the first get `<slug>-2`, `<slug>-3`. A section with no body text at
    all (a heading immediately followed by another heading) is dropped rather than
    written as a blank chunk - `wiki.upsert` rejects an empty summary outright.
    """
    lines = text.splitlines()
    in_fence = _line_fence_states(lines)

    headings: list[tuple[int, int, str]] = []
    for idx, line in enumerate(lines):
        if in_fence[idx]:
            continue
        match = _HEADING_RE.match(line)
        if match:
            headings.append((idx, len(match.group(1)), match.group(2).strip()))

    title: str | None = None
    title_idx: int | None = None
    for idx, level, heading_text in headings:
        if level == 1:
            title, title_idx = heading_text, idx
            break

    sub_headings = [(idx, level, ht) for idx, level, ht in headings if level >= 2]
    first_sub_idx = sub_headings[0][0] if sub_headings else len(lines)

    raw_sections: list[tuple[str, str]] = []
    intro_lines = [ln for i, ln in enumerate(lines) if i < first_sub_idx and i != title_idx]
    raw_sections.append(("intro", "\n".join(intro_lines)))
    for pos, (idx, _level, heading_text) in enumerate(sub_headings):
        start = idx + 1
        end = sub_headings[pos + 1][0] if pos + 1 < len(sub_headings) else len(lines)
        raw_sections.append((slugify(heading_text), "\n".join(lines[start:end])))

    used_slugs: set[str] = set()
    warnings: list[tuple[str, str]] = []
    chunks: list[ParsedChunk] = []

    for base_slug, raw_text in raw_sections:
        section_slug = _next_free_slug(base_slug, used_slugs)
        blocks = _split_blocks(raw_text.splitlines())
        if not blocks:
            continue

        parts, part_warnings = _pack_blocks(blocks, limits.body_max_words)
        warnings.extend((section_slug, w) for w in part_warnings)
        for i, part in enumerate(parts):
            slug = (
                section_slug if i == 0 else _next_free_slug(f"{section_slug}-{i + 1}", used_slugs)
            )
            summary = trim_words(first_paragraph(part), limits.summary_max_words)
            if not summary:
                summary = trim_words(part, limits.summary_max_words)
            chunks.append(ParsedChunk(section=slug, body=part, summary=summary))

    return ParsedDocument(title=title, chunks=chunks, warnings=warnings)


def _next_free_slug(candidate: str, used: set[str]) -> str:
    """Returns `candidate` if unclaimed, else the first free `candidate-2`, `candidate-3`, ...

    CONTRACT.md SS6 assigns `-2`/`-3` twice over, independently: to a duplicate heading
    and to a section's overflow parts. The two can collide (a second `## Step` heading
    claims `step-2` right as `step`'s own body overflows into a part that wants the same
    name). Not addressed in the doc; resolved here by treating every slug in one file as
    one shared namespace, so uniqueness never depends on which rule got there first.
    """
    if candidate not in used:
        used.add(candidate)
        return candidate
    n = 2
    while f"{candidate}-{n}" in used:
        n += 1
    slug = f"{candidate}-{n}"
    used.add(slug)
    return slug


def _fence_open(line: str) -> tuple[str, int] | None:
    """Returns the fence character and run length if `line` opens a fenced code block."""
    match = _FENCE_RE.match(line)
    if not match:
        return None
    marker = match.group(1)
    return marker[0], len(marker)


def _fence_closes(line: str, char: str, length: int) -> bool:
    """A closing fence is a line of only `char`, at least `length` of them, nothing else."""
    stripped = line.strip()
    return bool(stripped) and set(stripped) == {char} and len(stripped) >= length


def _line_fence_states(lines: list[str]) -> list[bool]:
    """Marks each line True while it lies inside a fenced code block, opener/closer included.

    Heading detection reads this so a `#` inside a mermaid or SQL fence is never mistaken
    for a section break.
    """
    states: list[bool] = []
    open_char: str | None = None
    open_len = 0
    for line in lines:
        if open_char is None:
            states.append(False)
            fence = _fence_open(line)
            if fence is not None:
                open_char, open_len = fence
        else:
            states.append(True)
            if _fence_closes(line, open_char, open_len):
                open_char = None
    return states


def _split_blocks(lines: list[str]) -> list[_Block]:
    """Splits section text into paragraph/fence/table units; a fence or table is one unit.

    A blank line ends a plain-text paragraph. A fence runs from its opening ``` `` `` /
    ``~~~`` marker to a matching close - or to the end of the section if unterminated -
    and holds together regardless of blank lines inside it. A row containing `|`
    immediately followed by a separator row (`---|---`) starts a table block that keeps
    consuming rows containing `|` until a blank line or a non-row line; this is a
    heuristic, not a markdown parser, so a `|` outside a real table can be misread as one.
    """
    blocks: list[_Block] = []
    buffer: list[str] = []

    def flush() -> None:
        if buffer:
            blocks.append(_Block("text", "\n".join(buffer).strip()))
            buffer.clear()

    i, n = 0, len(lines)
    while i < n:
        line = lines[i]
        fence = _fence_open(line)
        if fence is not None:
            flush()
            char, length = fence
            fence_lines = [line]
            i += 1
            while i < n:
                fence_lines.append(lines[i])
                closed = _fence_closes(lines[i], char, length)
                i += 1
                if closed:
                    break
            blocks.append(_Block("fence", "\n".join(fence_lines)))
            continue

        if line.strip() == "":
            flush()
            i += 1
            continue

        if "|" in line and i + 1 < n and _TABLE_SEP_RE.match(lines[i + 1]):
            flush()
            table_lines = [line, lines[i + 1]]
            i += 2
            while i < n and lines[i].strip() != "" and "|" in lines[i]:
                table_lines.append(lines[i])
                i += 1
            blocks.append(_Block("table", "\n".join(table_lines)))
            continue

        buffer.append(line)
        i += 1

    flush()
    return [b for b in blocks if b.text.strip()]


def _pack_blocks(blocks: list[_Block], limit: int) -> tuple[list[str], list[str]]:
    """Greedily packs blocks into <= `limit`-word parts, never splitting a fence or table.

    A block that alone exceeds `limit`: a text paragraph is handed to
    `_split_oversized_paragraph`; a fence or table is kept whole and warned about, per
    CONTRACT.md SS6 ("a fence that alone exceeds the limit is kept whole and warned").
    """
    parts: list[str] = []
    warnings: list[str] = []
    current: list[str] = []
    current_words = 0

    def close() -> None:
        nonlocal current, current_words
        if current:
            parts.append("\n\n".join(current))
            current = []
            current_words = 0

    for block in blocks:
        words = count_words(block.text)
        if words > limit:
            close()
            if block.kind == "text":
                pieces, split_warnings = _split_oversized_paragraph(block.text, limit)
                parts.extend(pieces)
                warnings.extend(split_warnings)
            else:
                noun = "table" if block.kind == "table" else "fenced code block"
                warnings.append(
                    f"{noun} runs {words} words, over the {limit}-word limit; "
                    "kept whole rather than split"
                )
                parts.append(block.text)
            continue

        if current and current_words + words > limit:
            close()
        current.append(block.text)
        current_words += words

    close()
    return parts, warnings


def _split_oversized_paragraph(text: str, limit: int) -> tuple[list[str], list[str]]:
    """Splits one over-limit paragraph at sentence boundaries, packing sentences greedily.

    A single sentence that still exceeds `limit` on its own is hard-cut by word count -
    the last resort CONTRACT.md SS6 does not name, needed so the loader always terminates
    with parts at or under the limit rather than emitting one that still overflows.
    """
    total = count_words(text)
    warnings = [
        f"paragraph runs {total} words, over the {limit}-word limit; split at sentence boundaries"
    ]
    sentences = [s for s in _SENTENCE_SPLIT_RE.split(text.strip()) if s]
    pieces: list[str] = []
    current: list[str] = []
    current_words = 0

    def close() -> None:
        nonlocal current, current_words
        if current:
            pieces.append(" ".join(current))
            current = []
            current_words = 0

    for sentence in sentences:
        words = count_words(sentence)
        if words > limit:
            close()
            word_list = sentence.split()
            for start in range(0, len(word_list), limit):
                pieces.append(" ".join(word_list[start : start + limit]))
            warnings.append(
                "a single sentence still exceeds the word limit; hard-cut by word count"
            )
            continue
        if current and current_words + words > limit:
            close()
        current.append(sentence)
        current_words += words

    close()
    return pieces, warnings
