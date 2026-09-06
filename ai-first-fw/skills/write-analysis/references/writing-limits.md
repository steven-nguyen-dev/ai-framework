# Writing limits

Every document of the contract holds these limits. Each template's writing-rules block points here,
so a limit changes in one place.

## The units

| Unit | Limit |
| :--- | :--- |
| Change item, claim, `A-n`, `C-n`, `CR-n`, `D-n`, `P-n`, `N-n`, requirement cell, note | 223 characters |
| Paragraph | 500 characters |
| Bullet list, per section or subsection | 7 items |
| Table columns | 6, and 5 wherever 5 carries the meaning |
| Sequence diagram participants | 6 |

A table row carries no item limit: a change table runs as long as the endpoint's properties.

## Holding a sequence diagram inside 6 participants

Every participant is a component a reader names — a service, a store, a queue, an external party —
so the diagram reads at the level the change items land on.

- Group the components inside one boundary into that boundary's own participant, and name what the
  grouping holds in a line under the diagram.
- Give the hops inside a grouped boundary to the section that owns them, and keep the diagram on the
  hops that cross a boundary.
- Split a flow that carries two triggers into two flows, each with its own diagram.

## Holding a unit inside 223 characters

- State the action, its object and its system, and stop. One sentence.
- Put the rule the sentence points at in the section that owns it — the enum matrix, the numbered
  note, the payload sample comment — and name that section in the sentence.
- Split a unit carrying two actions into two units. A split item takes a letter: `C-6a`, `C-6b`.

## Holding a bullet list inside 7 items

- Group the items by the endpoint, flow or domain they land in, and head each group with that unit.
  Seven items in three groups reads as three groups.
- Where the items resist grouping, move them into a table, which carries no item limit.
- Where a section's own groups pass seven, promote the groups to subsections of their own.

## Holding a table inside 6 columns

The payload sample under a change table carries type, example and nesting, so those leave the table
and the table keeps the columns a reader scans:

| Document | Columns |
| :--- | :--- |
| Change requests, change table | Property path · Type · Status · Persistence impact · Requirement |
| Mapping, field mapping table | Source field path · Target property · Transformation · Reason · Claim |

Where a meaning lands outside the payload sample's reach, give it the sixth column, and hold the
table at 6.
