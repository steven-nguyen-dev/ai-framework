# Writing limits

This repository's one set, applied on request. Any kind of writing takes it — a chat reply, a
document, a commit message, a pull request body, a code comment — and chat and documents carry the
same limits.

Any other file that needs these limits points here. A document that carries a limit of its own —
its own column set, its own section order — states that limit in its own template and points here
for the rest.

## The units

| Unit | Limit |
| :--- | :--- |
| Item, claim, cell, note — any identified single-statement unit | 223 characters |
| Paragraph | 500 characters |
| Bullet list, per section or subsection | 7 items |
| Table columns | 6, and 5 wherever 5 carries the meaning |
| Sequence diagram participants | 6 |

A table row carries no item limit: a table runs as long as the thing it lists.

## The wording

- One sentence, one idea. Split the sentence at `and`, `but`, `which`, and at every semicolon.
- 20 words for an instruction, 25 for a statement of fact.
- Active voice: name the actor. "The connector sends", not "is sent".
- One word, one meaning, across the whole piece. The verb picked for an action keeps that action, and
  every later mention of that action uses the same verb.
- Present tense — the state that holds when the work is done.
- Write the contraction out in full. Write the idiom or the metaphor as the thing it stands for.
- Noun strings at 3 words. Break a longer one with a preposition: "order line item count" becomes
  "the count of line items in the order".
- A noun or a finite verb where an `-ing` form sits: "the sync runs nightly", not "running the sync
  nightly".
- Keep the articles: "the payload", not "payload".
- Name each system, party, key and field in the word the context files give, and name the context
  file that owns a term two files share.
- Start an item with a verb, and name the system it lands in.
- Pure Markdown headings and links. A bullet list from three items up. Counts written as numbers.
- Say each thing once, in the section that owns it.

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

- Push type, example and nesting out of the table into the sample or the note beneath it, and keep
  the columns a reader scans.
- Where a meaning lands outside that sample's reach, give it the sixth column, and hold the table
  at 6.

## Holding a diagram inside 6 participants

Every participant is a component a reader names — a service, a store, a queue, an external party —
so the diagram reads at the level the items land on.

- Group the components inside one boundary into that boundary's own participant, and name what the
  grouping holds in a line under the diagram.
- Give the hops inside a grouped boundary to the section that owns them, and keep the diagram on the
  hops that cross a boundary.
- Split a flow that carries two triggers into two flows, each with its own diagram.
