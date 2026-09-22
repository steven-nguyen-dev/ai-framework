---
name: make-it-short
description: Rewrites or produces writing to comply with repository conciseness limits and direct wording rules. Automatically activate whenever the user requests or demands brevity, conciseness, directness, compact documentation, or tightened prose; on checking drafts before shipping; and across all subsequent replies once requested in a session.
version: 4.1.0
disable-model-invocation: false
---

# make-it-short

Rewrites one piece of writing in place: the file the user names, or the reply this agent holds
unsent.

Automatically activates whenever the user requests or demands brevity, conciseness, directness,
compact documentation, or tightened prose. Once activated in a session, all subsequent writing and
documentation in that session must follow these limits and wording rules until told otherwise.

## The bar

- Each unit's count is handed back before and after, and holds its limit after.
- The rewritten text carries every claim the draft carried, nothing added.
- Meaning an over-limit unit sheds sits in a named section of the same piece.

## The limits

223 characters an item — a claim, a cell, a note, any single-statement unit. 500 a paragraph. 7
items a bullet list, per section. 6 table columns, 5 where 5 carries the meaning. 6 diagram
participants.

## The wording

- One idea per sentence, split at `and`, `but`, `which` and every semicolon: 20 words for an
  instruction, 25 for a fact. A split unit letters its parts: `C-6a`, `C-6b`.
- Active voice, present tense, actor named. An item opens with its verb and names the system it
  lands in: "the connector sends", not "is sent".
- One word, one meaning: a verb keeps its action everywhere, and each system, party, key and field
  takes the context files' word.
- Contractions written out, idioms as the thing they stand for, articles kept.
- Noun strings at 3 words, a noun or a finite verb where an `-ing` sits: "order line item count"
  becomes "the count of line items in the order".
- Say each thing once, in the section that owns it: a unit names that section, and a table leaves
  type, example and nesting to the sample beneath.
- Group to get under a limit: list items by endpoint, flow or domain under a heading, diagram
  components by boundary named under the diagram. A table takes what resists grouping, carrying no
  item limit.
