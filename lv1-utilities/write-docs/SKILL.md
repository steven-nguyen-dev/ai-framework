---
name: write-docs
description: Writes one technical knowledge note in this repo's house style — drafted in temp, every fact traced to its source, every uncertainty carried to an Open questions section.
version: 1.0.0
disable-model-invocation: true
---

# write-docs

One technical knowledge note, drafted in the agent's temp directory and promoted to the destination
the user names.

`templates/note.md` holds the note's sections and the writing rule for each.
`references/house-style.md` holds voice, headings, shape-to-format, provenance and the ship
checklist.
`references/hld.md` holds the extra layer a note carries when it is a high-level design.
Diagram and colour rules live in `draw-diagram`, which governs every diagram in every note.

## Inputs

- **Subject** — what the note is about: repository paths, a spec or ticket, a partner's
  documentation, or what the user states first-hand.
- **Destination** — the file path the promoted note lands at.
- **Scope** — the one sentence the note covers, and by omission what it does not.
- **Existing note** — the file already at the destination, when one is there.
- **Self-containment** — whether the note set this note joins carries links or stands alone
  (`references/house-style.md` §2).

## Step 1 — Settle the note

Put the scope sentence, the destination and the self-containment choice to the user in one
numbered message, each carrying your recommended answer, then wait. Ask only what changes the
output.

**Completion:** the scope sentence, the destination path and the self-containment choice are
written down as the user's own answers.

## Step 2 — Read the subject to its edges

Read every source the subject names, and record each fact with where it came from. Quote
wire-format facts — endpoints, payload shapes, field names, status values, auth — rather than
inferring them. Where an existing note stands at the destination, read it here too and mark every
claim the subject no longer supports.

**Completion:** every fact the note will carry is written down against one of four origins —
quoted from a source line with its file and line, quoted from a named document with its date,
stated by a named human, or `unknown`; and every claim of the existing note is marked as holding
or superseded.

## Step 3 — Draft the note

Copy `templates/note.md` to a scratch file in the agent's temp directory and fill that copy from
step 2. Apply `references/house-style.md` to every block, and `references/hld.md` on top of it when
the note is a high-level design. Carry each uncertainty you hit while writing into Open questions
as a question with the answer that would settle it.

**Completion:** the draft stands in the temp directory with every section of the template filled or
deleted, and every fact from step 2 either stands in the note or is written down as dropped.

## Step 4 — Check the draft

Quote a line of the draft against every row of the ship checklist (`references/house-style.md` §6),
against every row of the HLD checklist (`references/hld.md` §5) where the note is a design, and
against every line of the bar below.

**Completion:** every checklist row and every bar line is quoted against a line of the draft, and
each failing row is fixed and re-quoted.

## Step 5 — Hand the draft over

Give the user the temp path and the list of Open questions. Promote the draft to the destination on
the user's word. When the user disputes a fact, re-read the source line that fact came from before
defending or conceding it.

**Completion:** the user has the temp path and the Open questions list, and the destination file
holds the note only where the user said to promote it.

## The bar

- The scope sentence, the destination and the self-containment choice are the user's own answers.
- Every fact in the note dereferences to a source line, a named document, a named human, or
  `unknown`.
- Every wire-format fact is quoted from its source, not inferred.
- Every uncertainty hit while writing stands in `## Open questions` with the answer that settles it.
- Every row of `references/house-style.md` §6 is quoted against a line of the note.
- The destination file changed only on the user's word.

