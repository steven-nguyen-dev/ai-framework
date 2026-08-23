A gotchas file's opening and the rules for writing an entry. The opening is copied into each
`GOTCHAS-<partition>.md`; everything below it stays here.

## The opening — copy verbatim, filling `<the partition>`

````markdown
Traps in <the partition>. Each entry states a wrong conclusion a competent reader reaches, why the
code lets them reach it, and what to do instead.

An entry belongs here when all three hold: a reader following the code reaches the wrong conclusion
or none; the finding names a **behaviour** rather than an identifier a search could find; and it
costs either a wrong conclusion or time. A thing search can find belongs in `GLOSSARY.md`.

Cite an entry by file and number — "the swallowed dispatch (GOTCHAS-oms 4.2)". A number never
changes meaning.
````

## Entry shape

Four lines, in this order:

```markdown
**4.2 A successful 202 does not mean the order reached the partner**

The queue acknowledges before the dispatcher runs, so a serialisation failure is logged and
swallowed — `OrderDispatcher.java:88`, `QueueConfig.java:41`. Nothing reaches the caller.

`Do:` confirm dispatch by the outbound audit row, never by the 202.

Scope: ETON only. The other partners dispatch synchronously.
```

| Line | Carries |
|---|---|
| `**N.M the trap in one sentence, bold**` | the **wrong conclusion a reader reaches**, not the mechanism |
| the mechanism | why the code permits it, with `file:line` on every claim |
| `Do:` | one sentence — what the reader does instead |
| `Scope:` | only where the entry is partner- or tenant-specific, traced for the named one alone |

**Every entry carries a `Do:`.** Without one it is a note, and it is rewritten until it has one. A
`Do:` names the artefact the reader consults instead, or the check they run — "confirm by the audit
row", not "be careful".

**The headline states the conclusion, not the cause.** "A successful 202 does not mean the order
reached the partner" is a headline; "the dispatcher swallows serialisation failures" is the
mechanism line. A reader scanning headlines is looking for the belief they hold, not for the code
they have not read.

Where a trap is also a designation, the glossary carries the definition and this file carries the
`Do:`. Each cites across; neither repeats the other.

## Section order

Sections are `## N`, ordered by the spine, so a reader walking a flow meets them in order:

1. **Entry and admission** — how data gets in, including what no route table lists
2. **Transformation and identity** — what the datum is called and shaped like between hops
3. **Persistence** — write keys, read keys, and where they drift apart
4. **Emission and terminus** — what leaves, and what silently does not
5. **Human-only knowledge** — what the code cannot answer, with what was tried before asking
6. **Aliases** — this partition's shorthand, as a local extension of the glossary's shorthand section

A section with entries is written; the rest are dropped. An empty section reads as a clean walk.

## Aliases

Two columns, designation and glossary citation:

```markdown
| alias | glossary |
|---|---|
| `WCONN` | connector (7.1) |
```

Every alias resolves to a live headword and agrees with the glossary's own shorthand entry — the
gate checks both. This table extends the glossary locally; the glossary defines.

## Numbers

Entries are `N.M`, numbered per file. An entry keeps its number for life: new traps append within
their section, and a trap that no longer holds keeps its number and moves to `## Retired` at the
foot with one line saying what changed. A reused number rewrites every citation that pointed at the
old one.

## What belongs elsewhere

- A **`GAP`** — walked, still unknown, and nobody could answer. It ships as a question in the
  handover.
- A finding whose evidence spans two or more partitions. It belongs in the shared file, as one shape
  with its exceptions.
- Anything a search would have found. That is a glossary entry.
