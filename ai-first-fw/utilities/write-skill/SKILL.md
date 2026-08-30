---
name: write-skill
description: Write a new skill for this repo, or revise an existing one — its SKILL.md, its templates, its registration and its version. Use on "write a skill", "make a skill", "tidy this SKILL.md", or "review this skill".
version: 0.1.0
disable-model-invocation: false
---

# write-skill

One skill: a `SKILL.md`, the templates and reference files it needs, and its registration.

Read `references/levers.md` before Step 1 and hold it open through Step 4: it carries the eight
levers (§1–§8) the copy is written and pruned against.

`templates/skill.md` carries the shape of a `SKILL.md` and the rule for each of its sections, in
comments. This file carries the run.

## Step 1 — Interview

Settle five answers. The request settles what it settles; the user settles the rest.

| Answer | Settled when |
|---|---|
| **Issue** | One sentence naming what goes wrong today, and what the skill makes true instead |
| **Inputs** | Every input named, with what counts as it and where it comes from |
| **Bar** | What the output satisfies, in lines checkable against the output |
| **Name** | `lower-kebab-case`, and its home: `ai-first-fw/skills/<name>/` for a stage of the delivery lifecycle, `ai-first-fw/utilities/<name>/` for a tool that stands alone |
| **Invocation** | The user has chosen model-invoked or user-invoked, against the trade in §8 |

Put every answer still open to the user in one message, numbered, each carrying your recommended
answer, then wait. Their answer is what gets written; an answer still open after a round returns in
the next one.

**Completion:** all five are written down, each as the user's own answer.

## Step 2 — Open the copy

Copy `templates/skill.md` to `<home>/<name>/SKILL.md` and edit that copy. Revising an existing
skill, its `SKILL.md` is the copy.

**Completion:** the copy is open at its path.

## Step 3 — Fill the copy

Fill under the copy's own comments: the description as a pointer (§1), each step to a completion
criterion (§4), and the reference the run consults on demand into a `references/<name>.md` the copy
points at (§3). The writing rules of any document the new skill produces belong in that document's
template; the copy names where they live and carries the run.

**Completion:** every section of the copy is filled or deleted, and every branch the interview named
carries a trigger in the description.

## Step 4 — Prune

Work the copy line by line against §7, keeping each line that changes what the agent does.

**Completion:** every surviving line is quoted with what it changes against the default.

## Step 5 — Self-check

Quote the line of the copy that satisfies each `Check:` line in it, and each line of the bar below.

**Completion:** every `Check:` line and every bar line is quoted against. The copy still carries its
comments.

## Step 6 — Strip

Delete every block from `<!--` through the first `-->` after it.

**Completion:** the copy holds no `<!--`, and its headings and tables render.

## Step 7 — Register

Add `"./<name>"` to the home plugin's `plugin.json` skills list, name the skill in that plugin's
description and in the matching `.claude-plugin/marketplace.json` entry, and bump both versions
under the repo's versioning policy.

**Completion:** both JSON files parse, and the folder name, the frontmatter `name` and the
`plugin.json` entry are the same string.

## The bar

- The issue, the inputs, the bar, the name and the invocation are the user's answers.
- The frontmatter carries `name`, `description`, `version` and `disable-model-invocation`.
- The description carries one trigger per branch, and the invocation matches the user's choice (§1,
  §8).
- Every step ends on a completion criterion a second person checks by reading the output (§4).
- Every rule sits in exactly one file (§7).
- Every instruction states the behaviour to perform (§6).
