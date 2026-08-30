---
name: draw-diagram
description: Draws one Mermaid block — flowchart, sequence, state machine or ER — from a subject the agent has read, styled to the repo's dark palette and parsed before it ships. Use on "draw a diagram", "diagram this flow", "visualise this architecture"; on restyling or fixing a Mermaid block that already exists; and on reviewing one before it ships.
version: 1.0.0
disable-model-invocation: false
---

# draw-diagram

One Mermaid block, in the markdown file the user names, or in the reply when they name none.

`references/palette.md` holds the semantic roles and the fill, border and text value of each.
`references/recipes.md` holds the init header and the skeleton for each diagram type.

## Inputs

- **Subject** — what gets drawn: repository paths, a spec or ticket, or the user's own description.
- **Type** — `flowchart`, `sequenceDiagram`, `stateDiagram-v2` or `erDiagram`; the user's, or the one
  the subject's own shape settles.
- **Destination** — the markdown file and the heading the block lands under.
- **Existing block** — the Mermaid block already at the destination, on an edit or a review.

## Step 1 — Read the subject

Read the subject to its edges: every participant, every hop between them, every state or column the
diagram will carry. An edit or a review reads the existing block here too, so that what it already
claims stands against the same source.

**Completion:** every node and every edge the block will carry is quoted from a line of the subject,
with its file and line; a hop the subject does not state is written down as `unknown`.

## Step 2 — Assign a role to every element

Take the roles from `references/palette.md`, and give one to each element from step 1. An element
that carries no role either takes `utility` or leaves the diagram.

**Completion:** every element from step 1 carries one role name, or is named as dropped with its
reason.

## Step 3 — Draw the block

Follow the skeleton for the type in `references/recipes.md`. Label each edge with the verb the
subject uses for that hop. Label each node with its name and its role.

**Completion:** every element from step 2 stands in the block carrying its role's class, and the
block carries the init header and one `classDef` per role used.

## Step 4 — Parse and check

Write the block to a file and run `npx -y @mermaid-js/mermaid-cli -i <file> -o /tmp/diagram.svg`.
Fix what it reports and run it again. Then quote the block against each line of the bar.

**Completion:** the parse reports no error, and every bar line is quoted against a line of the block.

## The bar

- Mermaid parses the block without error.
- Every node carries a palette class matching its role.
- Every edge label is an active verb read from the subject.
- Every node dereferences to a thing the subject names.
- The block carries a `title:` block.
