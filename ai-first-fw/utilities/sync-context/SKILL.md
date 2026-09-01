---
name: sync-context
description: Brings every project sharing a context folder to one identical set — reports the drift, settles each contradiction with you, promotes the merge to every copy.
version: 1.0.0
disable-model-invocation: true
---

# sync-context

One context folder, the same in every project that shares it: the latest text of every block, every
block any copy holds, and no block said twice.

`scripts/context_sync.py` does the mechanical half — `discover` reads the roster, `diff` reports
every difference and drafts the merge, `promote` copies the draft to every project, `verify` proves
the copies converged. The merge rules below are the half it leaves to judgement.

## Inputs

- **Roster** — the projects sharing the context system, read from the `CLAUDE.md` that names them:
  one list item each, alias bolded, path in backticks.
- **Context folder** — the folder under each project root holding the context files, `.context`
  unless that repo names another; `--context-dir` and `--glob` carry both.
- **Working copies** — each project's checkout. Where git tracks the context folder, `promote`
  refuses over uncommitted changes under it, so a dirty copy is committed or stashed before step 5.
  Where git ignores or excludes it, `git status` reports it clean however it stands and holds no
  version to restore, so `promote` backs the folder up instead and names the path.

## Step 1 — Settle the roster

Run `discover`. Put its list to the user, naming any project it found that the roster did not lead
you to expect, and any the user names that it missed — a project whose context folder sits under
another name, or whose path in `CLAUDE.md` has moved, is found by neither.

**Completion:** every project the run will touch is written down with its context folder, as the
user's own list.

## Step 2 — Report the drift

Run `diff --out <temp>` and read `report.md` whole, not its summary table alone.

**Completion:** every difference `report.json` counts is accounted for as one of four — a file some
copies lack, a block some copies lack, a block two copies contradict, a pair the report reads as a
rename.

## Step 3 — Settle each contradiction

An addition carries silently: a block one copy holds and another lacks belongs in the merge, and
the draft already carries it. A contradiction and a rename do not — put every one of them to the
user in a single numbered message, each with both texts, who holds each, when each was last
touched, and your recommended answer, then wait. Write each answer into the draft, replacing the
marker block whole.

**Completion:** the draft holds no `<<<<<<< CONFLICT` and no rename with both halves standing, and
every question is written down against the user's answer.

## Step 4 — Check the draft

Quote a line of the draft against every merge rule below and every line of the bar.

**Completion:** every merge rule and every bar line is quoted against a line of the draft, and each
failing one is fixed and re-quoted.

## Step 5 — Promote

Give the user the draft path and what changed per file. On the user's word run
`promote --draft <temp>/draft`, then `verify`. A refusal names the file and the block to fix, so
fix that and run it again. Report the backup path `promote` prints alongside the result: where git
does not track the context folders, that copy is the only way back.

**Completion:** `verify` reports 0 differences and an identical file set, the backup path is
reported, and the context folders changed only on the user's word.

## Merge rules

- **The fuller text wins only where it carries every claim of the shorter.** Where it drops one, the
  two contradict, and the contradiction goes to the user.
- **A rename is one block, not two.** Where the report pairs two blocks as a rename, one name
  survives and the other is deleted — including its heading, and including the title of a file.
- **A term is defined in one file.** The Map table of the roster's own `CONTEXT.md` says which file
  owns a sense where two collide; a term standing in two files is settled by that row, not by
  keeping both.
- **An enumeration merges as its union.** Where two variants of one block differ only in a list —
  an `_Avoid_` line, a Map row, a set of status values — the merged block carries every item, and
  only two items that contradict reach the user.
- **Every merged sentence stands word for word in one of the copies**, or is one the user dictated.
- **A date is evidence, not a verdict.** Where git tracks the context folder a date is the block's
  own; where it does not, every date in the report falls back to the file's mtime and dates the
  whole file, so it separates two copies but not two blocks within one. The report labels which.

## The bar

- The roster is the user's own list.
- Every difference the report counted is either carried into the draft or written down as dropped,
  with the user's word for dropping it.
- Every merged sentence stands word for word in one of the copies, or the user dictated it.
- No context file defines one headword twice, carries a second title, or keeps both halves of a
  rename.
- `verify` reports 0 differences and an identical file set across every project on the roster.
- Every context folder the run overwrote has a backup, and the user has its path.
- The context folders changed only on the user's word.
