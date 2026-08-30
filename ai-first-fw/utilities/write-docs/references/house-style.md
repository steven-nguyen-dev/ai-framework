# House style

Applies to every technical knowledge note. `references/hld.md` adds a layer on top where the note is
a high-level design.

## §1 Voice

- **Open on scope, not a hook.** One sentence, at the top, stating what the note covers.
- **Bullets and tables carry the content.** Write a paragraph where it makes a single point in three
  sentences or fewer.
- **One fact per bullet**, leading with the load-bearing clause in bold.
- **Measurable over adjectival**: "82 partner modules", not "many modules".
- **Every name dereferences.** A system resolves to its full reach, a flow to its originator, every
  hop and its sink, a property or host or module name to the value it resolves to.
- **Every verb is one read in the source.** Elsewhere the line reads `unknown`.
- **Each finding appears once**, in the section that owns it.

## §2 Self-containment

Decided once per note set, and held for every note in that set.

- **Self-contained** — no links, no "see X", no cross-note section references. Each note stands
  alone for a reader holding only that file.
- The cost is two notes at adjacent levels stating the same summary twice. Take it deliberately,
  keeping the summary line in one and the evidence in the other — or drop the requirement for the
  set.
- Provenance in `## Source` is not a cross-reference. Removing it to satisfy self-containment makes
  the note claim first-hand verification it does not have.

## §3 Headings

- **A heading names its subject**, not the act of reading it: "Order sync", not "How order sync
  works".
- **Sentence case**, and depth stops at three levels.
- **Number a section only where something outside the note cites it**, and check who cites
  `<note> §N` before renumbering.

## §4 Shape to format

The content's own shape settles its format.

| The content | The format |
|---|---|
| Items carrying the same fields | A table, one row per item |
| Items each carrying one fact, sharing no fields | A bullet list |
| Hops between named parties, or states and their transitions | A diagram |
| A single point in three sentences or fewer | A paragraph |
| One item | A sentence — never a one-row table |

## §5 Provenance

- **Every fact traces to one of four**: derived from a source line, quoted from a named document,
  stated by a named human, or marked `unknown`.
- **Quote wire-format facts, never infer them** — endpoints, payload shapes, field names, status
  values, auth.
- **Declare a section compiled from other documents as second-hand**, with the dates of the material
  and its own sample-size limits.
- **`## Source` records the boundary of what was checked**, including an explicit not-verified
  clause.
- **Delete a pointer to a file that no longer exists.** Keep the finding IDs, drop the dead link,
  and state that the evidence is no longer reachable.

## §6 Ship checklist

Every row passes. The diagram rows in `draw-diagram` pass too.

| # | Check |
|---|---|
| 1 | The note opens on `## At a glance` and the scope sentence |
| 2 | No sentence explains the note to itself |
| 3 | Contents rows match real headings, in note order |
| 4 | Every link resolves — or, under self-containment, there are none |
| 5 | No one-row table; no bullet list whose items repeat the same fields |
| 6 | `## Source` states what was read, when, what is second-hand, and what was not verified |
| 7 | Every uncertainty hit while writing stands in `## Open questions` |
| 8 | Checked who cites `<note> §N` before renumbering |

Where a note already stood at the destination, these rows pass as well:

| # | Check |
|---|---|
| 9 | Every claim the old note made is marked as holding or superseded |
| 10 | Every superseded claim is deleted, not carried forward |
| 11 | Every `## Open questions` entry the old note settled has moved into the body |
