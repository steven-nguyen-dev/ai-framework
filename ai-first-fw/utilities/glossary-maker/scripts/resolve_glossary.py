#!/usr/bin/env python3
"""Cross-reference resolver for an ISO 704:2022 GLOSSARY.md.

Does only the work a reading pass cannot: resolving every designation in the file against every
headword. On a hundred-entry glossary that is thousands of comparisons, and it is exactly where a
reader's attention runs out silently.

It checks nothing visible inside a single entry — no definition wording, sentence count, punctuation,
article or field-order rules. Those are the writer's judgement, and a gate that fires on defensible
prose teaches its reader to ignore it.

Usage:
    python3 resolve_glossary.py GLOSSARY.md [--against OLD.md] [--quiet]

    --against   a previous revision: every number in it must still name the same designation
    --quiet     print the summary line only

Exit codes: 0 clean, 1 findings, 2 the file could not be read or holds no entries.
"""
from __future__ import annotations
import argparse, re, sys
from collections import defaultdict

ENTRY = re.compile(r"^\*\*(\d+\.\d+)\s+(.+?)\*\*\s*$")
ROW = re.compile(r"^\|\s*(\d+\.\d+)\s*\|\s*(.+?)\s*\|")
SET = re.compile(r"^SET\s+(.+?)\s*((?:‹[^›]+›\s*)+)$")
FIELD = re.compile(r"^(ADMITTED|DEPRECATED|CONFUSABLE|BROADER|NARROWER|PART OF|PARTS|COORDINATE|RELATED)\b:?\s*(.+)$")
SUBJECT = re.compile(r"‹(.+?)›")
RELATIONS = {"BROADER", "NARROWER", "PART OF", "PARTS", "COORDINATE", "RELATED"}


def key(text: str) -> str:
    """Designation identity: case- and backtick-insensitive, subject field stripped."""
    return SUBJECT.sub("", text).replace("`", "").strip().lower()


def load(path: str):
    """-> (entries, sets, retired). entry = (number, designation, subject, {field: [values]})."""
    entries, sets, retired, cur, in_retired = [], {}, set(), None, False
    for raw in open(path, encoding="utf-8"):
        line = raw.strip()
        if re.match(r"^##\s+Retired\b", line, re.I):
            in_retired = True
        elif line.startswith("## "):
            in_retired = False
        m = ENTRY.match(line) or ROW.match(line)
        if m and not line.startswith("| #"):
            sub = SUBJECT.search(m.group(2))
            cur = (m.group(1), key(m.group(2)), sub.group(1) if sub else None, defaultdict(list))
            (retired.add(m.group(1)) if in_retired else entries.append(cur))
            continue
        if s := SET.match(line):
            sets[key(s.group(1))] = set(SUBJECT.findall(s.group(2)))
            continue
        if cur and (f := FIELD.match(line)):
            cur[3][f.group(1)] += [key(v) for v in f.group(2).split(",") if v.strip()]
    return entries, sets, retired


def resolve(entries, sets, retired):
    out = []

    def say(n, m):
        out.append(f"{n}: {m}")
    heads = {e[1] for e in entries}
    by_num, by_name = defaultdict(list), defaultdict(list)
    for e in entries:
        by_num[e[0]].append(e); by_name[e[1]].append(e)

    for num, group in sorted(by_num.items()):
        if len(group) > 1:
            say(num, f"{len(group)} entries share this number — a citation cannot resolve")
        if num in retired:
            say(num, "reused by a live entry after retirement — every old citation now misreads")

    for name, group in sorted(by_name.items()):
        if len(group) < 2:
            continue
        senses = {e[2] for e in group}
        if None in senses:
            say(group[0][0], f"'{name}' has {len(group)} senses; each needs a ‹subject field›")
        elif name not in sets:
            say(group[0][0], f"'{name}' has {len(group)} senses and no SET line: add SET {name} "
                             + " ".join(f"‹{s}›" for s in sorted(senses)))
        elif sets[name] != senses:
            for miss in sorted(senses - sets[name]):
                say(group[0][0], f"SET {name} omits ‹{miss}›")
            for extra in sorted(sets[name] - senses):
                say(group[0][0], f"SET {name} names ‹{extra}›, which no entry carries")

    for num, name, _sub, fields in entries:
        dep, adm = set(fields["DEPRECATED"]), set(fields["ADMITTED"])
        con = set(fields["CONFUSABLE"])
        for v in sorted(dep & heads):
            say(num, f"DEPRECATED '{v}' is a headword — it names another concept, so it belongs on CONFUSABLE")
        for v in sorted(dep & adm):
            say(num, f"'{v}' is both ADMITTED and DEPRECATED")
        for v in sorted(dep & con):
            say(num, f"'{v}' is both DEPRECATED and CONFUSABLE — it names this concept or another, not both")
        for label in RELATIONS:
            for v in fields[label]:
                if v == name:
                    say(num, f"{label} points at itself")
                elif v not in heads:
                    say(num, f"{label} '{v}' is not a headword")
        for v in sorted(con & sets.get(name, set())):
            say(num, f"CONFUSABLE '{v}' is in this designation's declared set — the SET line carries it")
    return out


def drifted(old_entries, new_entries):
    old = {n: d for n, d, _, _ in old_entries}
    new = {n: d for n, d, _, _ in new_entries}
    return [f"{n}: was '{old[n]}', now '{new[n]}' — every citation of {n} now misreads"
            for n in sorted(old.keys() & new.keys()) if old[n] != new[n]] \
         + [f"{n}: '{old[n]}' lost its number — retire it instead, so citations still resolve"
            for n in sorted(old.keys() - new.keys())]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("path", nargs="?", default="GLOSSARY.md")
    ap.add_argument("--against", metavar="OLD.md", help="previous revision; numbers must still mean what they meant")
    ap.add_argument("--quiet", action="store_true", help="print the summary line only")
    a = ap.parse_args()
    try:
        entries, sets, retired = load(a.path)
    except OSError as e:
        print(f"{a.path}: {e.strerror}", file=sys.stderr); return 2
    if not entries:
        print(f"{a.path}: no entries found", file=sys.stderr); return 2

    findings = resolve(entries, sets, retired)
    if a.against:
        try:
            old, _, _ = load(a.against)
            findings += drifted(old, entries)
        except OSError as e:
            print(f"{a.against}: {e.strerror}", file=sys.stderr); return 2
    if not a.quiet:
        for f in findings:
            print(f"{a.path}:{f}")
    print(f"\n{a.path}: {len(entries)} entries, {len(retired)} retired · {len(findings)} unresolved")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
