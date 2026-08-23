A gotchas file's opening and the rules for an entry. The opening is copied out; the rules stay here.
Numbering and citation live in [AUDIT-BRIEF.md](./AUDIT-BRIEF.md).

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
| headline, bold | the **wrong conclusion a reader reaches**, in one sentence |
| mechanism | why the code permits it, with `file:line` on every claim |
| `Do:` | one sentence — what the reader does instead |
| `Scope:` | only where the entry is partner- or tenant-specific, traced for the named one alone |

**The headline states the conclusion, not the cause.** "A successful 202 does not mean the order
reached the partner" is the headline; "the dispatcher swallows serialisation failures" is the
mechanism line.

**Every entry carries a `Do:`**, naming the artefact the reader consults instead or the check they
run — "confirm by the audit row", not "be careful". Without one the entry is a note, and it is
rewritten until it has one.

Where a trap is also a designation, the glossary carries the definition and this file carries the
`Do:`. Each cites across; neither repeats the other.

## Sections

`## N` sections, grouped however this partition's own structure groups its work. Where the partition
has shorthand, one section is `## Aliases` — two columns, resolving to live glossary headwords and
agreeing with the glossary's own shorthand entry, both of which the script checks:

```markdown
| alias | glossary |
|---|---|
| `WCONN` | connector (7.1) |
```

## What belongs elsewhere

- A `GAP` — unknown, and nobody could answer — ships as a question in the handover, not as an entry.
- A finding whose evidence spans two or more partitions belongs in `GOTCHAS-shared.md`, as one
  finding with its exceptions.
- Anything a search would have found is a glossary entry.
