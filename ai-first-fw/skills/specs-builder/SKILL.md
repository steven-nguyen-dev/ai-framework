---
name: specs-builder
description: Fills an integration's spec folder from the area's own harness, writes the mapping-plan.md grading every field mapping, and clears both against a cold review. Use when an integration needs specs built, when an existing spec folder needs updating, or when a mapping plan needs writing.
version: 0.10.0
disable-model-invocation: false
---

# Specs builder

Two deliverables. A **spec folder** a generator can build from, and a **`mapping-plan.md`** saying
where every field came from and how sure you are.

**The area owns the spec format.** Its `specs/README.md`, `_templates/FIELD-REFERENCE.md` and
`_templates/master-template.yml` *are* the format — the copy step, the fill order, sample placement,
the kinds, the `recommended:` resolution rule, precedence and escalation all live there. Read them at
runtime and follow them. **This file does not repeat them**, and every area's conventions are read
fresh from that area.

**`templates/mapping-plan.md` carries the writing** — its own fill order, writing rules, column
legend, grade and coverage list, in comments it keeps until 5 · Strip.

**`references/quality-bar.md` carries the bar** — 3 · Fill reads its blank-field rules while filling;
6 · Cold review hands the whole file to a reader that never saw the fill.

What this file carries is what no harness supplies: the output contract, and the review loop.

---

## Inputs

- **The area** — the directory whose `specs/_templates/` holds the harness. Pin it with
  `ls -d */specs/_templates/`; more than one match means name them and ask.
- **The intake** — partner API documentation, the mapping document, captured payloads, and the
  integration's own module where the partner already runs.
- **The scope** — which features this integration supports.
- **What is already there** — the integration's spec folder and any `mapping-plan.md` beside it,
  left by an earlier run. Present or absent, it is read before anything is written.

---

## 1 · Pin the area, read its harness, and settle fresh against update

Name the area by repo-relative path on first mention in each message. **The bar for how much detail a
filled spec carries is the area's own filled `EXAMPLE.*.spec.yaml`**; read it, and read the
`feature.<KIND>` form for any kind it does not cover. Filled folders elsewhere in the area are
context, never authority — the README ranks spec files last, and nothing on disk distinguishes a
decade of convention from a defect nobody corrected. Read only the ones on your checkout.

**Read what is already there before writing anything.** List the integration's spec folder and open
any `mapping-plan.md` beside it. What you find decides the run, and there are three findings:

| Found | The run | What opens |
|---|---|---|
| Neither | **Fresh** | Copy `templates/mapping-plan.md` → `mapping-plan.md` |
| A stripped `mapping-plan.md` with graded rows, and spec files that parse | **Update** | The existing `mapping-plan.md`, edited in place |
| Either one partial — a copy still holding `<!--`, rows without grades, a spec file that does not parse | **Update from the break** | The existing file, with what is unfinished named before filling resumes |

**Copying the template over a filled `mapping-plan.md` destroys the prior run's grades and its
`MAP-xx` numbering.** Copy it only where no `mapping-plan.md` exists. Everywhere else the existing
file is the copy, and its comments are already stripped — 5 · Strip has nothing to do on a file that
never carried them, so say so rather than reporting a strip you did not run.

**An update re-reads before it re-grades.** Name what changed since the prior run — the harness
(`_templates/`), the intake, the scope — and re-derive only what those changes reach. A row whose
evidence did not move keeps its grade and its `MAP-xx`; a row whose evidence moved is re-graded and
says so. Nothing is renumbered.

**State the verdict in your first message** — fresh, update, or update from the break — with the
paths you read to reach it. An update that announces itself as a fresh build silently discards work
the human already reviewed.

Then open the copy the table names, so every read lands the moment it comes back and the legend is
in view during the interview.

**Completion:** the area is named by path, the kinds its harness exemplifies and the ones it does not
are stated, the run is declared fresh or update against the paths that were read, and the copy that
decision names is open.

## 2 · Intake and interview — the frontier is empty

Ask for the materials in one round, listing what already arrived alongside, and ask whether that is
everything.

The **frontier** is every open question whose prerequisites are settled. Ask the whole frontier in one
message, numbered, each carrying your recommended answer, then stop and wait; a question hanging off
another still open returns next round, and silence never accepts a recommendation. Two tests, both
written on the question's line: **grounded** — the document section or `file:line` that failed to
answer it; **material** — what changes in the specs or the plan. A question failing materiality is not
asked — **assume and state**: record the assumption and what would overturn it, and surface it under
*Assumed, correct me* in the read-back. Drive the payload rounds from the copy's coverage comment.
Two answers the human owns outright: a decision, and a fact living only in their email or a call —
quote that verbatim and let the copy's grade rule price it.

**Finding facts is your job.** Anything the harness, the partner's docs, the payloads or the codebase
answers is a lookup, and lookups go to a sub-agent returning verdicts, facts and
`file · Class.method` — never file bodies, never a chosen answer.

**Where the integration already runs**, read its identity out of the module instead of interviewing
for it — service annotation, per-profile config, rate-limit annotations, request-manager methods and
their DTOs, status mapper — scoped to the integration module, not the reactor holding every partner
it serves, and cited as a bare FQCN with a line number. Read what is on disk, not what is committed:
`git grep` cannot see an unstaged file and comes back clean. **A DTO is not the wire** — a sample
rebuilt from one drops unmapped fields, enum values and null-versus-absent, then parses, resolves and
generates against a shape the partner never sends. Ask for a real capture, which API version is
current, and whether the existing behaviour is correct or a bug being specified.

Read the settled decisions back in one message. **Their confirmation authorises the fill.**

**Completion:** every branch is visited, nothing is silently assumed, and the human has confirmed the
read-back.

## 3 · Fill — every feature routed, every authored line a directive

Follow the area's instructions. Beyond them:

- **Trim by role.** Prefer `enabled: false` over deleting a stub — it keeps the pre-filled
  `contract:`. Report every trim and which way it went.
- **Absence is a statement.** "Supplied later" builds the feature empty — form, seed, explicit empty
  collection — rather than skipping it.
- **Check the master template**, not just the stub, for fields applicable and absent.
- **On an update, edit in place and hold the numbering.** A `MAP-xx` keeps its number for the life of
  the mapping plan; a new field takes the next free one, and a field the scope dropped is marked
  withdrawn rather than deleted, so a reviewer's earlier citation still resolves.
- **Read every blank and pre-filled slot** by `references/quality-bar.md` § *Reading a blank — or a
  pre-filled — field*, starting with the `grep` it opens with: marker semantics are per-area.
- **Harness-authored text is frozen** — stub headers, pre-filled values and shipped `notes` are
  byte-identical, and anything you add to a `notes` block goes below it. A frozen line that does not
  hold here is answered in `mapping-plan.md`, never beside it: a rebuttal under a stub header is the
  most common way narrative enters a spec folder.
- **An operation with no stub** folds into an existing feature more often than not — check that
  first, then number it the way the area's `ordered/` already numbers, fill the `contract:` marking
  symbols that do not exist yet as `# NEW — not yet in <Symbol>`, and collect them as platform gaps
  for the hand-off. Naming a symbol that does not exist yet is a specification; referencing one
  silently is not.
- **Two checkpoints end a turn**: `checkpoint · scoping` once scope is routed to numbered features
  (features in scope, every trim and its direction, precedents chosen), and
  `checkpoint · global spec + auth` once both are filled (what was filled, what is still open). Show
  your work, then wait to be waved on.

### The output contract

Every line you author is a **directive**: a value, a wire fact, an instruction the generator acts on.
Everything else is **narrative** — reasoning, status, provenance, an open question — and narrative
lives in `mapping-plan.md`, never in a spec.

The second test is **the cloner**: someone who cloned this repo and never saw `mapping-plan.md`. A
spec line carries the fact, never where it was decided — no plan ID, no document name, no section
number, no "see". Pointers run plan → spec, never back. **The cloner only removes lines**: a line
that is already narrative stays out even when its reference resolves cleanly, and
`samples/PROVENANCE.md` resolves perfectly and is still provenance.

| Authored form | Write | Not this |
|---|---|---|
| A field with its value | `perCall: unbounded` | `perCall: "unbounded — no per-call cap is documented"` |
| A one-line comment stating the fact | `# 'N' means the marketplace reports 999,999,999` | `# sentinel value — see ADR-01 for the reasoning` |
| A `notes:` entry in the harness's register | *(blank — the fact is the field above)* | `notes: spdNo comes from the DTO's parent-sku field` |

A fact needing a clause of justification to stand up is a `mapping-plan.md` row. Keep every `notes`
block at or under the longest one the harness itself ships, in length and in density.

**The placement map** — every kind of information has exactly one home:

| Information | Home |
|---|---|
| Wire directives and wire facts | spec fields, comments, `notes` |
| Implementation status | the `mapping-plan.md` file tree (§1) |
| Reasoning, consequences, trade-offs, a harness claim that does not hold here | the `mapping-plan.md` row (§2) |
| Sample provenance | per sample file, where the area puts it |
| Open questions, platform gaps | the hand-off report |

**Completion:** every feature in scope is routed or trimmed with the trim reported, and both
checkpoints were shown and cleared.

## 4 · Self-check — both deliverables before either is finished

**The copy first.** Every comment in `mapping-plan.md` ends in a `Check:` line; work the copy top to
bottom and quote the line of it satisfying each one, counting them off the copy in front of you: a
deleted section deletes its comment, so any count written down in advance is wrong.

**Then the spec folder**, which has no comments of its own:

- **Every sample says where it came from.** "Unknown origin" is an open question, not a pass.
- **Every file parses and every `sample:` pointer resolves** — by parsing, not reading. A duplicate
  key survives a careful read; an unresolvable pointer means the payload does not exist.
- **Every authored line is one of the three forms and survives the cloner.** Walk them; the forms are
  not self-enforcing.
- **Derived values line up** — kinds against the area's forms, buckets against the global spec, the
  integration code against the registration doc.
- **Identifier and silent-failure fields sit on the right side of the wire**: who assigns each one,
  and whether the spec places it in a request input or a response payload.
- **Both `notes` commands in `references/quality-bar.md` (Pass 2) come back clean** — density at or
  under the harness ceiling, `PASS` on stub-`notes` survival. Each takes seconds and buys back a
  review round.

**Completion:** every `Check:` line is quoted against, every bar above is satisfied, and both
measurement results are quoted.

## 5 · Strip — the copy holds no comments

Delete every block opening at `<!--` through the first `-->` after it, the ones you just checked
against included. Separate from 4 because it cannot be undone while 4 is still running; before 6
because the file the cold reader judges is the file that ships.

**Completion:** `mapping-plan.md` holds no `<!--`, and its headings and tables still render.

## 6 · Cold review — a reader who did not fill the folder finds nothing left

Dispatch a sub-agent holding paths only: the spec folder, the intake material,
`references/quality-bar.md` — its conduct, entry conditions, four passes and the shape of a finding —
and this file's *output contract* and *placement map*, which those passes cite.

**What you withhold is the instrument.** Which fields you doubted, what you assumed, which precedent
you chose: each tells the reader what to conclude, and a round that receives them returns your own
reasoning graded as evidence.

Findings come back; the repairs are yours. Close every `blocker` and every `defect`, then dispatch a
**new** sub-agent for the next round — the one holding the last round's findings is no longer cold.

**Three rounds is the ceiling.** A finding alive after the third round is a gap rather than a defect:
it goes to the human in the hand-off with a named disposition. Ship on the third verdict.

**Completion:** the last round's verdict line is quoted, every `blocker` and `defect` in it is
repaired or carries a named disposition, and the round count is 3 or fewer.

## 7 · Hand off

Report in chat — features ready · every trim and its direction · the final verdict line and every
finding that outlived it · open questions and owners · platform gaps · contradictions for the PR
description. The chat message is the report; no file on disk records it.

**When sources disagree**, apply the area's declared precedence and stop and flag where its README
says to. Only a conflict the precedence does not settle goes to the human — name both, quote them,
offer a reading.

**Completion:** the report carries every item above.

---

## The bar

- The spec folder follows the area's own README, field reference and master template, and no
  convention is carried in from another area.
- Every authored line is a directive in one of the three forms and survives the cloner; every
  harness-authored line is byte-identical.
- Every boundary field carries a graded `MAP-xx` row, and `mapping-plan.md` ships stripped with every
  `Check:` line quoted against.
- A sub-agent that never saw the fill ran the four passes of `references/quality-bar.md` against the
  delivered folder, in three rounds or fewer, and its last verdict line is quoted with every
  surviving finding carrying a disposition.
- The run declared itself fresh or update from what the spec folder and `mapping-plan.md` already
  held, and no filled `mapping-plan.md` was overwritten by the template.
- Every `MAP-xx` carried over from a prior run kept its number, and every re-graded row says what
  moved.
- Nothing was asked of the human that a lookup could have found.
