#!/usr/bin/env python3
"""Structural validator for an ISO 704:2022 GLOSSARY.md.

Checks the rules a reading pass talks itself out of: circular and negative definitions,
DEPRECATED designations that actually name another concept, homonyms missing their subject
field or their cross-references, relation targets that resolve to nothing, and duplicate
or misnumbered entries.

It checks structure and cross-references only. It cannot tell you a definition is wrong,
only that it is malformed.

It does not police style. Article, sentence count and length rulings were cut deliberately:
a gate that fires on defensible prose trains its reader to ignore it, and the errors go with
the warnings.

Usage:
    python3 validate_glossary.py GLOSSARY.md [--strict] [--quiet]

    --strict   treat warnings as errors
    --quiet    print the summary line only

Exit codes: 0 clean, 1 findings, 2 the file could not be read or holds no entries.

Expected shape, per entry:

    ## 1 Section name

    **1.2 term ‹subject field›**
    ADMITTED: other designation for this same concept
    DEPRECATED: designation that must not be used

    definition, one noun phrase, no closing period

    NOTE 1  something true but not definitional
    CONFUSABLE: a designation naming a DIFFERENT concept
    BROADER: superordinate
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field

# ---------------------------------------------------------------- patterns

SECTION_RE = re.compile(r"^##\s+(\d+)\s+(.+?)\s*$")
ENTRY_RE = re.compile(r"^\*\*(\d+)\.(\d+)\s+(.+?)\*\*\s*$")
RETIRED_RE = re.compile(r"^##\s+Retired\s*$", re.IGNORECASE)
SUBJECT_RE = re.compile(r"‹(.+?)›")
RULE_RE = re.compile(r"^(-{3,}|\*{3,}|_{3,})$")

# Longest first so "PART OF" is matched before "PART".
INLINE_FIELDS = [
    "ADMITTED",
    "DEPRECATED",
]
TRAILING_FIELDS = [
    "CONFUSABLE",
    "COORDINATE",
    "NARROWER",
    "BROADER",
    "PART OF",
    "PARTS",
    "RELATED",
    "EXAMPLE",
    "GAP",
]
# Relations that name a concept in this same file and must resolve.
TAXONOMIC = {"BROADER", "NARROWER", "PART OF", "PARTS", "COORDINATE"}
# Relations that may legitimately point outside the concept system.
SOFT = {"RELATED", "CONFUSABLE"}

FIELD_RE = re.compile(
    r"^(NOTE\s+\d+|" + "|".join(sorted(INLINE_FIELDS + TRAILING_FIELDS, key=len, reverse=True)) + r")\b[:\s]\s*(.*)$"
)

# Used to strip a leading article before the circularity test, not to police articles:
# "an area's connector deployable" is correct English and the validator leaves it alone.
ARTICLE_RE = re.compile(r"^(a|an|the)\s+", re.IGNORECASE)
ABBREV_RE = re.compile(r"^(abbreviation|shorthand|short form|acronym|initialism)\b", re.IGNORECASE)
QUALIFIER_RE = re.compile(
    r"^(in|as|for|when|where|only|outside|inside|within|per|which|the|a|an)\b", re.IGNORECASE
)
NEGATIVE_RE = re.compile(
    r"^not\s+|\bis\s+not\b|\bare\s+not\b|\bdoes\s+not\s+(mean|denote|name)\b|\bnever\s+means\b",
    re.IGNORECASE,
)
SENTENCE_SPLIT_RE = re.compile(r"\.\s+[A-Z]")
GLOSS_RE = re.compile(r",\s+(which|for|the|a|an)\s+.*$", re.IGNORECASE)


def designation_key(text: str) -> str:
    """Comparison key that KEEPS the subject field — 'SS' and 'SS ‹deployable›' are different."""
    text = text.replace("`", "").replace("*", "").strip().strip(".,;:")
    return " ".join(text.lower().split())


def normalise(text: str) -> str:
    """Fold a designation to its comparison key: no subject field, no markup, no case."""
    text = SUBJECT_RE.sub("", text)
    text = text.replace("`", "").replace("*", "").replace("_", "")
    text = text.strip().strip(".,;:").strip()
    return " ".join(text.lower().split())


# ---------------------------------------------------------------- model


@dataclass
class Entry:
    major: int
    minor: int
    headword: str
    line: int
    subject: str | None = None
    definition: str = ""
    definition_line: int = 0
    fields: list[tuple[str, str, int]] = field(default_factory=list)

    @property
    def number(self) -> str:
        return f"{self.major}.{self.minor}"

    @property
    def base(self) -> str:
        return normalise(self.headword)

    @property
    def signature(self) -> str:
        """The full designation, subject field included — what makes two homonyms distinct."""
        if self.subject:
            return f"{self.base} ‹{normalise(self.subject)}›"
        return self.base

    def values(self, label: str) -> list[tuple[str, bool, int]]:
        out: list[tuple[str, bool, int]] = []
        for name, value, line in self.fields:
            if name != label:
                continue
            for part, qualified in split_targets(value):
                out.append((part, qualified, line))
        return out


def split_targets(value: str) -> list[tuple[str, bool]]:
    """Split a relation value into (designation, qualified) pairs.

    A designation may carry a register qualifier ("OIP, in prose") or an explanatory gloss
    ("titan, which is its repository"). Both are dropped from the designation; a qualifier
    is remembered, because a ruling scoped to one register is not a contradiction of a
    ruling scoped to another.
    """
    out: list[tuple[str, bool]] = []
    for chunk in value.split(";"):
        chunk = chunk.split("—")[0].strip()
        parts = [p.strip().strip(".") for p in chunk.split(",")]
        parts = [p for p in parts if p]
        if not parts:
            continue
        head, tail = parts[0], parts[1:]
        qualified = False
        for extra in tail:
            if QUALIFIER_RE.match(extra):
                qualified = True
            else:
                out.append((extra, False))
        out.append((head, qualified))
    return out


@dataclass
class Finding:
    level: str  # ERROR | WARN
    code: str
    line: int
    message: str


# ---------------------------------------------------------------- parsing


def parse(lines: list[str]) -> tuple[list[Entry], list[tuple[int, str, int]], list[Finding]]:
    entries: list[Entry] = []
    sections: list[tuple[int, str, int]] = []
    findings: list[Finding] = []
    current: Entry | None = None
    stage = "idle"  # idle | inline | definition | trailing
    retired = False

    for idx, raw in enumerate(lines, start=1):
        line = raw.rstrip("\n")
        stripped = line.strip()

        if RULE_RE.match(stripped):
            current = None
            stage = "idle"
            continue

        if RETIRED_RE.match(stripped):
            retired = True
            current = None
            stage = "idle"
            continue

        m = SECTION_RE.match(stripped)
        if m and not retired:
            sections.append((int(m.group(1)), m.group(2), idx))
            current = None
            stage = "idle"
            continue

        m = ENTRY_RE.match(stripped)
        if m and not retired:
            headword = m.group(3).strip()
            subject = SUBJECT_RE.search(headword)
            current = Entry(
                major=int(m.group(1)),
                minor=int(m.group(2)),
                headword=headword,
                line=idx,
                subject=subject.group(1).strip() if subject else None,
            )
            entries.append(current)
            stage = "inline"
            continue

        if current is None or retired:
            continue

        if not stripped:
            if stage == "inline":
                stage = "definition"
            elif stage == "definition" and current.definition:
                stage = "trailing"
            continue

        fm = FIELD_RE.match(stripped)
        if fm:
            label = " ".join(fm.group(1).split())
            if label.startswith("NOTE"):
                label = "NOTE"
            current.fields.append((label, fm.group(2).strip(), idx))
            if stage == "definition" and not current.definition:
                findings.append(
                    Finding("ERROR", "E02", idx, f"{current.number} '{current.headword}': field before any definition")
                )
            continue

        if stage in ("definition", "inline"):
            if current.definition:
                current.definition += " " + stripped
            else:
                current.definition = stripped
                current.definition_line = idx
            stage = "definition"
        elif current.fields:
            # a wrapped field value — fold it back onto the field it continues
            label, value, line_no = current.fields[-1]
            current.fields[-1] = (label, f"{value} {stripped}", line_no)
        else:
            findings.append(
                Finding("WARN", "W05", idx, f"{current.number} '{current.headword}': prose after the field block")
            )

    return entries, sections, findings


# ---------------------------------------------------------------- checks


def check(entries: list[Entry], sections: list[tuple[int, str, int]]) -> list[Finding]:
    out: list[Finding] = []

    # Homonyms are grouped case-sensitively: an all-caps enum value and a lower-case concept
    # are different designations, not two senses of one.
    by_base: dict[str, list[Entry]] = {}
    for e in entries:
        by_base.setdefault(SUBJECT_RE.sub("", e.headword).replace("`", "").strip().strip(".,;:"), []).append(e)

    # Resolution of a relation target is case-insensitive and accepts either the bare
    # designation or the designation with its subject field.
    resolvable: dict[str, list[Entry]] = {}
    for e in entries:
        for key in {e.base, e.signature, normalise(e.headword)}:
            resolvable.setdefault(key, []).append(e)

    section_numbers = {n for n, _, _ in sections}

    # numbering
    seen: dict[int, int] = {}
    for e in entries:
        if section_numbers and e.major not in section_numbers:
            out.append(Finding("ERROR", "E01", e.line, f"{e.number}: no '## {e.major}' section heading"))
        expected = seen.get(e.major, 0) + 1
        if e.minor != expected:
            out.append(Finding("ERROR", "E01", e.line, f"{e.number} '{e.headword}': expected {e.major}.{expected}"))
        seen[e.major] = max(expected, e.minor)

    for e in entries:
        d = e.definition.strip()
        where = e.definition_line or e.line

        if not d:
            out.append(Finding("ERROR", "E02", e.line, f"{e.number} '{e.headword}': no definition"))
            continue
        if d.endswith("."):
            out.append(Finding("ERROR", "E03", where, f"{e.number} '{e.headword}': definition ends with a period"))
        if NEGATIVE_RE.search(d):
            out.append(
                Finding(
                    "ERROR",
                    "E06",
                    where,
                    f"{e.number} '{e.headword}': negative definition — state what the concept is and "
                    f"move the contrast to CONFUSABLE",
                )
            )
        bare = ARTICLE_RE.sub("", normalise(d))
        if bare.startswith(e.base + " ") or bare == e.base:
            out.append(Finding("ERROR", "E04", where, f"{e.number} '{e.headword}': definition opens with its own term"))
        if SENTENCE_SPLIT_RE.search(d):
            out.append(
                Finding("WARN", "W02", where, f"{e.number} '{e.headword}': definition runs to more than one sentence")
            )

        deprecated = {v: q for v, q, _ in e.values("DEPRECATED")}
        admitted = {v: q for v, q, _ in e.values("ADMITTED")}
        confusable = {designation_key(v) for v, _, _ in e.values("CONFUSABLE")}
        dep_keys = {designation_key(v) for v in deprecated}

        # Admitted in one register and deprecated in another is a ruling, not a contradiction.
        for name, qual in admitted.items():
            for other, other_qual in deprecated.items():
                if normalise(name) == normalise(other) and not (qual or other_qual):
                    out.append(
                        Finding("ERROR", "E09", e.line, f"{e.number} '{e.headword}': '{name}' is both ADMITTED and DEPRECATED")
                    )
        for clash in sorted(dep_keys & confusable):
            out.append(
                Finding(
                    "ERROR",
                    "E16",
                    e.line,
                    f"{e.number} '{e.headword}': '{clash}' sits on both DEPRECATED and CONFUSABLE — "
                    f"it names this concept or another, not both",
                )
            )

        # The defect that makes a glossary actively harmful: a designation banned as a wrong
        # word for THIS concept, when it is in fact the right word for ANOTHER one.
        for value, _qual, line in e.values("DEPRECATED"):
            if normalise(value) == e.base:
                continue  # a register ruling on this entry's own designation, not a wrong turn
            others = [o for o in resolvable.get(normalise(value), []) if o is not e]
            if not others:
                continue
            # An entry that exists only to record an abbreviation of this concept is not another concept.
            if any(ABBREV_RE.match(o.definition) and e.base in normalise(o.definition) for o in others):
                continue
            target = others[0]
            out.append(
                Finding(
                    "ERROR",
                    "E08",
                    line,
                    f"{e.number} '{e.headword}': DEPRECATED '{value}' is the headword of {target.number} "
                    f"'{target.headword}' — it names another concept, so it belongs on CONFUSABLE",
                )
            )

        for label in TAXONOMIC:
            for value, _qual, line in e.values(label):
                if normalise(value) not in resolvable:
                    out.append(
                        Finding("ERROR", "E13", line, f"{e.number} '{e.headword}': {label} '{value}' is not a headword")
                    )
        for value, _qual, line in e.values("RELATED"):
            if normalise(value) not in resolvable:
                out.append(Finding("WARN", "W01", line, f"{e.number} '{e.headword}': RELATED '{value}' is not a headword"))

        for value, _qual, line in e.values("GAP"):
            if not value.lower().startswith(("no consulted source", "no source")):
                out.append(
                    Finding("WARN", "W03", line, f"{e.number} '{e.headword}': GAP does not name the silence it declares")
                )

    # homonyms
    for base, group in sorted(by_base.items()):
        if len(group) < 2:
            continue
        for e in group:
            if not e.subject:
                out.append(
                    Finding(
                        "ERROR",
                        "E11",
                        e.line,
                        f"{e.number} '{e.headword}': '{base}' has {len(group)} entries; each needs a ‹subject field›",
                    )
                )
        signatures = [e.signature for e in group]
        if len(set(signatures)) != len(signatures):
            out.append(Finding("ERROR", "E10", group[0].line, f"'{base}': two entries carry the same designation"))
        for e in group:
            listed = {normalise(v) for v, _q, _l in e.values("CONFUSABLE")}
            listed |= {SUBJECT_RE.sub("", v).strip().lower() for v, _q, _l in e.values("CONFUSABLE")}
            for sibling in group:
                if sibling is e:
                    continue
                if normalise(sibling.headword) not in listed and sibling.base not in listed:
                    out.append(
                        Finding(
                            "ERROR",
                            "E12",
                            e.line,
                            f"{e.number} '{e.headword}': does not list its homonym {sibling.number} "
                            f"'{sibling.headword}' as CONFUSABLE",
                        )
                    )

    # circularity between two entries — an error when each is the other's genus,
    # a warning when they merely mention each other
    unique = {e.base: e for e in entries if len(by_base.get(SUBJECT_RE.sub("", e.headword).strip(), [])) == 1}
    for a in entries:
        for b_base, b in unique.items():
            if b is a or b_base == a.base or (a.major, a.minor) >= (b.major, b.minor):
                continue
            a_def, b_def = normalise(a.definition), normalise(b.definition)
            mutual = re.search(rf"\b{re.escape(b_base)}\b", a_def) and re.search(rf"\b{re.escape(a.base)}\b", b_def)
            if not mutual:
                continue
            a_genus = " ".join(a_def.split()[:4])
            b_genus = " ".join(b_def.split()[:4])
            if b_base in a_genus and a.base in b_genus:
                out.append(
                    Finding(
                        "ERROR",
                        "E05",
                        a.definition_line or a.line,
                        f"{a.number} '{a.headword}' and {b.number} '{b.headword}' define each other",
                    )
                )
            else:
                out.append(
                    Finding(
                        "WARN",
                        "W07",
                        a.definition_line or a.line,
                        f"{a.number} '{a.headword}' and {b.number} '{b.headword}' each name the other",
                    )
                )

    return out


# ---------------------------------------------------------------- cli


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate a GLOSSARY.md against ISO 704:2022 entry rules.")
    ap.add_argument("path", nargs="?", default="GLOSSARY.md")
    ap.add_argument("--strict", action="store_true", help="treat warnings as errors")
    ap.add_argument("--quiet", action="store_true", help="print the summary line only")
    args = ap.parse_args()

    try:
        with open(args.path, encoding="utf-8") as fh:
            lines = fh.readlines()
    except OSError as exc:
        print(f"cannot read {args.path}: {exc}", file=sys.stderr)
        return 2

    entries, sections, findings = parse(lines)
    if not entries:
        print(f"{args.path}: no entries found — expected '**N.M designation**' headwords", file=sys.stderr)
        return 2

    findings += check(entries, sections)
    findings.sort(key=lambda f: (f.line, f.code))

    errors = [f for f in findings if f.level == "ERROR"]
    warns = [f for f in findings if f.level == "WARN"]

    if not args.quiet:
        for f in findings:
            print(f"{args.path}:{f.line}: {f.level.lower()}[{f.code}] {f.message}")
        if findings:
            print()

    print(
        f"{args.path}: {len(entries)} entries in {len(sections)} sections · "
        f"{len(errors)} errors · {len(warns)} warnings"
    )

    if errors or (args.strict and warns):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
