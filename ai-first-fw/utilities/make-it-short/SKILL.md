---
name: make-it-short
description: Rewrites one piece of writing inside this repository's limits and wording rules — 223-character items, 500-character paragraphs, 7-item lists, 6-column tables, one idea per sentence. Use on "make it short", "shorten this", "tighten this", "cut this down"; on checking a draft against the limits before it ships; and on every later draft of a session where the user has already asked for these rules once.
version: 1.0.0
disable-model-invocation: false
---

# make-it-short

One piece of writing, rewritten in place: the file the user names, or the reply this agent is about
to send.

This run starts on request. The user asks for it on one draft, and it holds for that draft alone.
Where the user asks for these rules over a session, every later draft of that session holds them,
until the user says otherwise.

`references/writing-limits.md` holds the unit limits, the wording rules, and the move that brings
each over-limit unit back inside its limit. It is this repository's one set, and the file every
other document points at for these rules. This file carries the run.

## Inputs

- **The draft** — the text this run rewrites. It arrives as the file the user names, or as the reply
  this agent holds, unsent.
- **The context files** — the repository's context file set, which gives the word for each system,
  party, key and field the draft names.

## Step 1 — Count the draft

Count every unit of the draft against the unit table in `references/writing-limits.md`. Write down
each unit whose count passes its limit, with that count.

**Completion:** every unit of the draft carries a count, and every count over its limit is written
down beside its unit.

## Step 2 — Rewrite the wording

Rewrite every sentence against the wording rules in `references/writing-limits.md`.

**Completion:** every sentence satisfies every wording rule, and each rewritten sentence carries the
claim its predecessor carried.

## Step 3 — Cut to the limits

Take each unit written down in step 1. Apply the move its kind states in
`references/writing-limits.md`. Where the move relocates meaning, name the section it lands in.

**Completion:** every unit from step 1 sits under its limit, and every piece of meaning it shed sits
in a named section of the same piece of writing.

## Step 4 — Recount and replace

Count the rewritten text against the unit table again. Put it in the draft's place: edit the file,
or send it as the reply.

**Completion:** no unit of the rewritten text passes its limit, and the rewritten text stands where
the draft stood.

## The bar

- The rewritten text carries the claims the draft carried, with nothing dropped and nothing added.
- Every unit holds the limit `references/writing-limits.md` states for it, counted against the
  rewritten text.
- Every sentence carries one idea, in the active voice, in the present tense.
- Every action keeps one verb across the whole piece.
- Every system, party, key and field appears in the word the context files give.
- Every over-limit unit of the draft sits under its limit by a move the reference states.
- The count of each unit is handed back, before and after.
