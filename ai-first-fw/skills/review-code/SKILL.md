---
name: review-code
description: Cold review of a branch or pull request diff — three isolated passes, one report in chat. Use on "review this code", "review the diff", "review this branch", "review this PR", or when a change needs checking against the repo's coding standard before it merges.
version: 2.3.0
disable-model-invocation: false
---

# review-code

One review of one diff, reported in chat. A finding names what is wrong and what it contradicts;
the fix is the author's.

Run it in a session holding no history of this change — the conversation that wrote the code is the
one context a cold read is defined against. Where that history is in your context, say so at the head
of the report and hand the review to a fresh session.

`references/quality-bar.md` holds what the passes read: how a finding is graded, the checklist every
carried file is answered against (§1), what the base did and this does not (§2), the smells (§3), and
what earns a suppression (§4).

## Inputs

- **Target** — a pull request URL or number, or a ref the diff runs since; absent one, the current
  branch against its merge-base with the default branch.
- **The ask** — the requirement the change answers, from the sources step 4 orders.
- **The standard** — the coding authority nearest the changed files, from the ladder step 2 orders.

## Step 1 — Pin the tree

Resolve the target to an immutable SHA pair — fixed point and head — and write the run's four
artefacts to `$(git rev-parse --git-dir)/review-code/<head short sha>/`, a directory outside the
worktree, so the review's own files stay clear of the diff it reviews:

| Artefact | Holds |
|---|---|
| `inventory.md` | one row per changed file: path, added, deleted, `carried` or `excluded`, and `addition-only` where the deleted count is zero |
| `code.diff` | the rename-aware diff over the carried files |
| `excluded.numstat` | the counts for the excluded files |
| `commits.txt` | the commit list over the pair |

A file is excluded where its path holds data rather than code — a fixture, a test resource, a
snapshot, a lock or a generated file; every other file is carried. Every later step and every pass
reads this pair and these four paths, so a ref resolves once, here, and a pass opens an excluded file
on demand.

Where the target resolves to no pair, or the diff is empty, report that and stop.

**Completion:** the four artefacts exist at named paths, and `inventory.md` holds a row for every
changed file.

## Step 2 — Resolve the standard

Take the first authority that exists, nearest the changed files winning over the repo root:

1. **A quality document** — guidelines, contributing rules, `CLAUDE.md` / `AGENTS.md`, a constraining
   ADR. Found, it is the authority.
2. **Lint, static analysis, compiler settings** — what an enabled rule already fails on belongs to
   the tooling. Quote the line that switches a rule on before crediting it.
3. **The nearest working sibling**, read at the fixed point. With no document, a consistent local
   convention is the standard; name the file per finding.
4. **The stack's accepted practice**, with stack and version read from the build file.

**Completion:** the standard is named by file, or reads `none found`, and each tooling rule credited
is quoted from the line that enables it.

## Step 3 — Dispatch pass A and pass B

Dispatch both briefs while the ask is still unread: a reviewer holding the ticket reads the diff
looking for the ticket, and stops seeing the leak, the race and the open entry point. Branch names,
commit subjects and pull request text are requirement text, and they travel in step 5.

Every brief carries the SHA pair, the four step 1 paths, the standard and the path to
`references/quality-bar.md` — that is the whole of what travels to a pass. Each agent reads
`inventory.md` for the files its own row below names, opens them at the SHA its brief gives it,
performs its own review in its own context, and returns findings in step 7's shape.

| Pass | Brief | Its files | Reads |
|---|---|---|---|
| **A · Intrinsic** | Is the new code sound on its own terms? | every carried file | `quality-bar.md` §1, §3, §4 |
| **B · Regression** | What worked at the fixed point and does not now? Read each file at both SHAs. | every carried file the inventory marks with a non-zero deleted count or a rename, and every added migration, schema and config file — an added one carries no fixed-point version and still answers §2 against the rows and messages the base wrote | `quality-bar.md` §2 |

**Completion:** both agents were dispatched from a context holding the four paths, the standard and
the bar, and each return is in hand or named as failed, timed out or empty.

## Step 4 — Read the ask

Only now, and in this order: the documents the human supplied, in full · a pull request's
description, its linked issues and every file it links · the issue and attachments behind any Jira
key in the title, body, branch name or commit messages · with none of those, the commit messages and
any spec sitting beside the changed code.

Mark each source **read**, **`not found`** (searched, absent), or **`unreachable (<why>)`** — the
source exists and the fetch failed for want of a connector, an authorisation, a live link. Only
`unreachable` is something the human fixes in a minute, so it carries its own word.

**Mark the technical prescriptions.** List every sentence in the ask that dictates implementation
rather than outcome — a class to use, a query to write, a call to make, an order to run in. Each is a
claim pass C tests against the diff's behaviour.

**Completion:** every source carries `read`, `not found` or `unreachable (<why>)`, and every
technical prescription stands in a list as its own quoted sentence.

## Step 5 — Dispatch pass C

Pass C's brief is step 3's, plus the ask in full and the prescription list. It holds the diff against
the ask, and against that alone — A and B have already settled the code's own soundness. It answers:

- **Every requirement, accounted for** — satisfied by named lines, partially satisfied, or absent.
- **Business meaning over green tests** — code that satisfies its tests and still lands what the
  requirement meant somewhere else. The highest-value finding available.
- **Named fields** — a field the requirement names, landing nowhere or landing changed, is a
  `blocker`. This is the lift §1's terminus question waits for.
- **Behaviour beyond the ask** — every behaviour the diff adds traces to a requirement, or stands in
  the report as scope creep.
- **Prescription against outcome** — for each prescription: does the diff follow it, and does
  following it produce what the requirement wanted? A prescription the diff followed into a wrong
  outcome is a finding against the prescription, filed as a question to the human.

Where every source in step 4 came back `not found`, say so at the head of the report, and pass C
holds the diff against its own names, commit messages and tests.

**Completion:** every requirement in the ask carries satisfied, partial or absent with the lines that
settle it, and every prescription from step 4 carries a verdict.

## Step 6 — Merge and grade

Grade every returned finding by `quality-bar.md` Grading. File one finding per place, at the worst
severity any pass gave it, naming every pass that reached it and keeping every citation, each
labelled with its pass.

**Completion:** every finding carries a severity and a named boundary, and each place appears exactly
once.

## Step 7 — Report in chat

Head the report with four lines:

- **target** — the SHA pair, the pull request number where there is one, the commit count, and the
  carried and excluded file counts with their line counts.
- **passes** — `A returned · B returned · C unreachable (<why>)`, and one line stating that A and B
  were dispatched before the ask was read.
- **authorities** — requirement sources · standard · stack, each carrying its own `none found` or
  `unreachable (<why>)` where that is the truth.
- **verdict** — `blockers: n · defects: n · notes: n`.

A finding is six things:

1. **What is wrong** — one sentence.
2. **Where** — `path:line` on an added or modified line, read at the head SHA, then the quoted line.
   A line you place by hunk alone says so in place of the number.
3. **Which pass** — `A`, `B` or `C`.
4. **What it contradicts** — the requirement source, the standard's rule, the named sibling, the
   stack practice, the named smell, or `quality`.
5. **Severity** — after step 6.
6. **Blast radius** — its named boundary.

Group under **Blockers**, **Defects**, **Notes**, in that order; within a group, A findings, then B,
then C. A group holding nothing reads `0 findings`.

Close with three lines: coverage (files reviewed, every excluded file with its counts, and anything
you read outside the diff with what sent you there), an *Adjacent, not reviewed* list carrying
everything else you noticed, and §4's suppression line.

**Completion:** the report stands in chat with its four head lines, every finding in the six-part
shape, three groups each carrying findings or `0 findings`, and the three closing lines.

## The bar

- The review ran in a session holding no history of the change, and A and B were dispatched before
  any requirement text was read.
- Every finding cites a line the diff adds or modifies at the head SHA, and carries a severity earned
  from a named boundary.
- Every carried file carries a §1 answer, and every §2 duty is answered at both SHAs over B's
  inventory.
- Every requirement carries satisfied, partial or absent with the lines that settle it, and every
  prescription carries a verdict.
- Every suppressed smell stands in the suppression line with what earned it.
