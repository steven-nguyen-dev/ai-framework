---
name: pr-desc-writer
description: Write the pull request description for the current branch, from this session's work and the file changes, shaped by the repo's PR template. Use when asked for a PR description, a PR body, or to open or raise a PR.
disable-model-invocation: true
version: 0.1.0
---

# pr-desc-writer

Read the session, read the file changes, write the PR into the template.

## 1. Read the session

The work is usually in this conversation, and the reasons behind the branch live there. Take them
from it.

## 2. Read the file changes

The diff says what the branch does. Read it.

## 3. Write the PR into the template

[`TEMPLATE.md`](TEMPLATE.md) beside this file holds the shape. Fill it.

Section 4 repeats what the user said about testing. Where the changes touch tests, *run the unit
tests* says it.

Output goes to chat as one fenced markdown block ready to paste; to a file when a file was asked for.

## Principles

**Boundaries.** The description covers this branch and stands alone for its reader.

**Tone.** Whatever changed is the grammatical subject, in the present tense, stating what now holds
of it. Report the facts and let the reviewer appraise them.

**Concision.** Length tracks the size of the change. Each thing said once. Keep every line the
reviewer would miss.
