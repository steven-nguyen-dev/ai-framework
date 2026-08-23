#!/usr/bin/env python3
"""Cross-reference resolver for an ISO 704:2022 GLOSSARY.md and its GOTCHAS files.

Does only the work a reading pass cannot: resolving every designation, citation and alias against
every headword, across every document in the set. On a hundred-entry glossary that is thousands of
comparisons, and it is exactly where a reader's attention runs out silently.

It checks nothing visible inside a single entry — no definition wording, sentence count, punctuation,
article or field-order rules, and no missing `Do:`. Those are the writer's judgement, and a gate that
fires on defensible prose teaches its reader to ignore it.

Usage:
    python3 resolve.py GLOSSARY.md [GOTCHAS-*.md ...] [--against OLD.md ...] [--quiet]

    The first path is the glossary; every path after it is a gotchas file. A gotchas file whose
    name contains "shared" is the shared file; the rest are partition files.

    --against   a previous revision, repeatable, paired positionally with the paths above:
                the first --against is the glossary's, the second the first gotchas file's, and so
                on. Every number in a previous revision must still name the same thing.
    --quiet     print the summary line only

Exit codes: 0 clean, 1 findings, 2 a file could not be read or the glossary holds no entries.
"""
from __future__ import annotations
import argparse, os, re, sys
from collections import defaultdict

ENTRY = re.compile(r"^\*\*(\d+\.\d+)\s+(.+?)\*\*\s*$")
ROW = re.compile(r"^\|\s*(\d+\.\d+)\s*\|\s*(.+?)\s*\|")
SET = re.compile(r"^SET\s+(.+?)\s*((?:‹[^›]+›\s*)+)$")
FIELD = re.compile(r"^(ADMITTED|DEPRECATED|CONFUSABLE|BROADER|NARROWER|PART OF|PARTS|COORDINATE|RELATED)\b:?\s*(.+)$")
SUBJECT = re.compile(r"‹(.+?)›")
RELATIONS = {"BROADER", "NARROWER", "PART OF", "PARTS", "COORDINATE", "RELATED"}

# "connector (1.3)" / "`WCONN` (7.1)" / "the double POST (GOTCHAS-oms 2.3)"
CITE = re.compile(r"([`\w][`\w .\-/]{0,60}?)\s*\(\s*([A-Za-z][\w.\-]*)?\s*(\d+\.\d+)\s*\)")
ALIAS_HEAD = re.compile(r"^##\s+.*\balias(es)?\b", re.I)
TABLE_ROW = re.compile(r"^\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*$")


def key(text: str) -> str:
    """Designation identity: case- and backtick-insensitive, subject field stripped."""
    return SUBJECT.sub("", text).replace("`", "").strip().lower()


def norm(text: str) -> str:
    """Headline identity for duplicate detection across files."""
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", text.replace("`", "").lower()).split())


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


def load_gotchas(path: str):
    """-> (entries, retired, cites, aliases). entry = (number, headline). cite = (num, designation)."""
    entries, retired, cites, aliases = [], set(), [], []
    in_retired = in_alias = in_fence = False
    for raw in open(path, encoding="utf-8"):
        line = raw.strip()
        if line.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if line.startswith("## "):
            in_retired = bool(re.match(r"^##\s+Retired\b", line, re.I))
            in_alias = bool(ALIAS_HEAD.match(line))
        if m := ENTRY.match(line):
            (retired.add(m.group(1)) if in_retired else entries.append((m.group(1), m.group(2))))
            continue
        if in_alias and (t := TABLE_ROW.match(line)) and not set(t.group(1)) <= set("-: "):
            if t.group(1).strip().lower() not in ("alias", "designation"):
                aliases.append((key(t.group(1)), t.group(2).strip()))
        for who, qual, num in CITE.findall(line):
            cites.append((num, key(who), (qual or "").strip()))
    return entries, retired, cites, aliases


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


def resolve_gotchas(g_entries, g_retired, cites, aliases, glossary, gnames):
    """Every citation and alias in one gotchas file, against the glossary and the other files."""
    out = []

    def say(n, m):
        out.append(f"{n}: {m}")
    entries, _sets, _ret = glossary
    by_num = {e[0]: e for e in entries}
    heads = {e[1] for e in entries}
    admitted = {v: e[0] for e in entries for v in e[3]["ADMITTED"]}
    deprecated = {v: e[0] for e in entries for v in e[3]["DEPRECATED"]}

    seen = defaultdict(list)
    for num, _ in g_entries:
        seen[num].append(num)
    for num, group in sorted(seen.items()):
        if len(group) > 1:
            say(num, f"{len(group)} entries share this number — a citation cannot resolve")
        if num in g_retired:
            say(num, "reused by a live entry after retirement — every old citation now misreads")

    def named(who):
        """The designation a citation names, taken as the longest trailing phrase that is one."""
        w = who.split()
        for i in range(len(w)):
            cand = " ".join(w[i:])
            if cand in heads or cand in admitted:
                return cand
        return None

    for num, who, qual in cites:
        if qual and qual.lower().startswith("gotchas"):
            if qual.lower() not in gnames:
                say(num, f"cites '{qual} {num}', which is not a gotchas file in this set")
            continue
        cand = named(who)
        if num not in by_num:
            say(num, f"'{cand or who.split()[-1] if who.split() else who}' cites {num}, "
                     f"which is not a glossary number")
        elif cand and cand != by_num[num][1] and admitted.get(cand) != num:
            say(num, f"cites {num} as '{cand}'; that number is '{by_num[num][1]}'")

    for alias, target in aliases:
        m = re.search(r"(\d+\.\d+)", target)
        num = m.group(1) if m else None
        if not num:
            out.append(f"aliases: '{alias}' names no glossary number")
            continue
        if num not in by_num:
            out.append(f"aliases: '{alias}' points at {num}, which is not a glossary number")
            continue
        head = by_num[num][1]
        if alias in deprecated and deprecated[alias] == num:
            out.append(f"aliases: '{alias}' is DEPRECATED on {num} — this table teaches a wrong word")
        elif alias in heads and alias != head:
            out.append(f"aliases: '{alias}' is itself a headword; it cannot alias {num} '{head}'")
        elif alias != head and admitted.get(alias, num) != num:
            out.append(f"aliases: '{alias}' is ADMITTED on {admitted[alias]}, not on {num} '{head}'")
        elif alias != head and alias not in admitted:
            out.append(f"aliases: '{alias}' is not ADMITTED on {num} '{head}' — add it to the glossary or drop it")
    return out


def cross_files(files):
    """No trap in two partition files; no shared trap repeated in a partition file."""
    out = []
    where = defaultdict(list)
    for name, entries, _r, _c, _a in files:
        for num, head in entries:
            where[norm(head)].append((name, num))
    for head, places in sorted(where.items()):
        if len(places) < 2:
            continue
        shared = [p for p in places if "shared" in p[0].lower()]
        others = [p for p in places if p not in shared]
        if shared and others:
            for name, num in others:
                out.append(f"{name}:{num}: repeats a trap the shared file already carries "
                           f"({shared[0][0]} {shared[0][1]})")
        elif len(others) > 1:
            out.append(f"{', '.join(f'{n}:{m}' for n, m in others)}: one trap in "
                       f"{len(others)} partition files — it belongs in the shared file, once")
    return out


def drifted(old_entries, new_entries, label=""):
    old = {n: d for n, d, *_ in old_entries}
    new = {n: d for n, d, *_ in new_entries}
    p = f"{label}:" if label else ""
    return [f"{p}{n}: was '{old[n]}', now '{new[n]}' — every citation of {n} now misreads"
            for n in sorted(old.keys() & new.keys()) if old[n] != new[n]] \
         + [f"{p}{n}: '{old[n]}' lost its number — retire it instead, so citations still resolve"
            for n in sorted(old.keys() - new.keys())]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("paths", nargs="*", default=["GLOSSARY.md"],
                    help="the glossary first, then every gotchas file")
    ap.add_argument("--against", metavar="OLD.md", action="append", default=[],
                    help="previous revision, repeatable, paired positionally with paths")
    ap.add_argument("--quiet", action="store_true", help="print the summary line only")
    a = ap.parse_args()
    paths = a.paths or ["GLOSSARY.md"]
    if len(a.against) > len(paths):
        print(f"--against given {len(a.against)} times for {len(paths)} documents", file=sys.stderr)
        return 2

    try:
        glossary = load(paths[0])
    except OSError as e:
        print(f"{paths[0]}: {e.strerror}", file=sys.stderr); return 2
    if not glossary[0]:
        print(f"{paths[0]}: no entries found", file=sys.stderr); return 2

    findings = [f"{paths[0]}:{f}" for f in resolve(*glossary)]
    n_entries, n_retired = len(glossary[0]), len(glossary[2])

    gnames = {os.path.basename(p).rsplit(".", 1)[0].lower() for p in paths[1:]}
    files = []
    for p in paths[1:]:
        try:
            g_entries, g_retired, cites, aliases = load_gotchas(p)
        except OSError as e:
            print(f"{p}: {e.strerror}", file=sys.stderr); return 2
        if not g_entries:
            findings.append(f"{p}: no entries — an empty gotchas file claims a clean walk the run "
                            f"did not make; delete it")
        files.append((os.path.basename(p), g_entries, g_retired, cites, aliases))
        findings += [f"{p}:{f}" for f in
                     resolve_gotchas(g_entries, g_retired, cites, aliases, glossary, gnames)]
        n_entries += len(g_entries); n_retired += len(g_retired)
    findings += cross_files(files)

    for i, old_path in enumerate(a.against):
        try:
            if i == 0:
                findings += [f"{paths[0]}:{f}" for f in drifted(load(old_path)[0], glossary[0])]
            else:
                old = load_gotchas(old_path)[0]
                findings += [f"{paths[i]}:{f}" for f in drifted(old, files[i - 1][1])]
        except OSError as e:
            print(f"{old_path}: {e.strerror}", file=sys.stderr); return 2

    if not a.quiet:
        for f in findings:
            print(f)
    docs = f"{len(paths)} document{'s' if len(paths) != 1 else ''}"
    print(f"\n{docs}: {n_entries} entries, {n_retired} retired · {len(findings)} unresolved")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
