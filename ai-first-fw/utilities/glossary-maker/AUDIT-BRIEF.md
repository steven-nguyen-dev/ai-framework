The gate's judging pass (the skill's Step 5b): the numbering contract both documents are written to,
and the brief for the sub-agent that audits them.

Auditor — your subject is the text of the documents you were given, plus the two format files and the
numbering contract below. You have no access to the target repo.

## Audit

- **Every field against its format file** — the rules for what each line carries, entry by entry.
- **`DEPRECATED` against `CONFUSABLE`** — the flagship check, because the resolve script proves a
  value resolves but cannot tell which field it belongs in. Confirm that every `DEPRECATED` value
  names this same concept, and every `CONFUSABLE` value a different one.
- **Duplication and conflict across documents** — one concept defined twice, two entries that define
  each other, a gotcha and an entry that disagree. A finding carried by **both** documents is
  correct — check that the glossary holds the definition and the gotcha holds the `Do:`.
- **Numbering** against the contract below.

## Verdicts

Key every finding to the entry number it concerns:

| Verdict | Meaning |
|---|---|
| `fix` | the text is wrong on its own terms |
| `pass` | the text holds |
| `cannot judge without the code` | the question is a fact, not a form — returns to the author |

Return findings, never edits: the author holds the evidence to fix them correctly.

## Numbering

One contract for both documents, and the spec the writer writes to.

Sections are `## N`, entries `N.M`, numbered per file. An entry keeps its number for life: new
entries append within their section, and one that no longer holds keeps its number and moves to
`## Retired` at the foot with one line saying what replaced it. A reused number rewrites every
citation that pointed at the old one.

Cite a glossary entry by designation and number — "<designation> (1.3)". Cite a trap by file and
number — "(GOTCHAS-<partition> 4.2)".
