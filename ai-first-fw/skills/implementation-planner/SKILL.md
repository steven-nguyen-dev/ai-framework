---
name: implementation-planner
description: Review-driven implementation lifecycle from input fitness demand to approved production code.
version: 0.7.1
disable-model-invocation: true
---

# Implementation planning

**The first act is to judge the material the human supplied — not to read code to fill its silence.**
**No production code changes before a human approves the plan.**

This skill governs one piece of work from *a human describes what they want* to *the code is
approved*. This file is the run: the steps, the gates, and when to demand approval.

**The templates carry the writing.** Each one holds its own fill order, its rules and its done-when
list, in comments it keeps until its step ends. Copy the template, fill it under its own comments,
and do not look for the rules anywhere else — this file does not repeat them.

---

## Principles

**P1 — Review-driven.** A human approves before the work proceeds. A gate is `Approved` only on an
explicit human utterance containing `"approve"` / `"approved"`. Never inferred.

**P2 — Business-first.** Understand the business before planning the build, and prove that
understanding in writing for a human to approve. `business-requirements.md` is the proof.

**P3 — No gap crosses a gate unattended.** Every open gap takes an explicit human disposition at
every gate.

**P4 — Delegate the reading.** Reading the codebase, reading multiple files for context, and
researching multiple online sources each go to a sub-agent. A sub-agent returns verdicts, facts and
`file · Class.method` — never file bodies, never its search narrative, and never a chosen answer.
Material you quote or fill from — a template, the coding standard, a spec harness form — you read
yourself. Online research covers public material only; a partner's contract is supplied by the
human, never researched.

**P5 — A turn ends with work or with a question, never with an intention.** Announcing the next step
is not performing it. Where the work does not fit the turn, say what is written and what is not.

**The human's two roles, and no third.** At a gate they are the **reviewer**. For any question
neither the codebase nor a document can answer, they are the **coordinator**.

---

## Weight class

| Class | When | Artifacts |
|---|---|---|
| **Light** | Bug fix, no new business rule, no new external contact | **No files** — the plan is one chat message |
| **Standard** | Everything else | `raw-context.md`, `business-requirements.md`, `implementation-plan.md` |

Anything not **fit** escalates Light to Standard. Any debt the human accepts escalates to Standard.

**Light, defined.** The one message still carries the rule set read back, the file list with
`[NEW]` / `UPDATE`, and one test line per criterion in the shape of the test plan's phase 1
(plan §4). G1 and G2 may be approved in a single human
turn, and the work ends when the tests are green. A gap at Light lives in the message; on escalation
the files are created and every open gap moves into the log.

Light has no folder and no cold review.

---

## The artifacts

Per feature, in **`<repo-root>/.scratchpads/<feature-slug>/`**:

- `raw-context.md` — **the state** (§0) and **the record** (§1, the log). Read it first, write it on
  the way out of every step. Never stripped.
- `refined/` — extracts a command produced from a large material.
- `business-requirements.md` — **the intent**. Stripped of its comments at the end of Step 1.
- `implementation-plan.md` — **the design**. Stripped of its comments at the end of Step 3.
- *(If specs were generated: `mapping-plan.md` — written by `specs-builder`, never inline.)*

Reviewers add their own: `plan-review-report.md`, `specs-review-report.md`, `code-review-report.md`.
Each re-review overwrites its own.

**Strip the comments before the artifact is reviewed.** A reviewer judges the result, not the
method. Rules left in a reviewed file invite a compliance check instead of a quality one. Delete each
block from its opening `<!--` through the first `-->` after it, then **confirm the file holds no
`<!--` at all** — a partial strip leaves rules in a reviewed file and passes silently.

**Revising a stripped artifact means re-reading its template first.** A gate that comes back with
corrections sends you into a file whose rules are gone. Open `templates/<the artifact>` from this
skill, read its comment blocks, then edit the stripped copy.

---

## The run

### Step 0 — Intake

**Owes:** the weight class is stated — and recorded, at Standard; every artifact the human supplied
has its `SRC` line and a written verdict; and anything not **fit** has been demanded back or opened
as a gap.

**Before the project `CLAUDE.md`. Before any prior planning folder. Before any router or any code.**
The first output of this skill is a message to the human about their material, and the only thing
that precedes it is the ledger the message's lines land in — opening the folder is not reading the
repo.

**This rule governs fitness, not content.** It stops you reading the repo to fill the silence where
material should be. It never stops you reading the material you hold, and it never licenses a
question. A `grep` proving nothing in the repo consumes a named deliverable is part of judging that
deliverable — run it before demanding the file.

**State the weight class first**, against its two tests — a new business rule, a new external
contact. At **Standard**, create the feature folder, confirm `.scratchpads/` is gitignored, copy
`templates/raw-context.md` in, and record the classification as the folder's first `DEC` line;
every line this step mints lands there as it is minted. At **Light**, the ledger is the message
itself.

Inventory everything supplied — image, screenshot, pasted text, ticket body, doc link, payload
sample. Mint each one's `SRC` line **on arrival, before judging it**; an unusable artifact keeps its
ID, because a gap needs something to name. Then judge each, and demand every replacement in one
round.

**Nothing supplied is itself a defect.** A one-sentence request with no ticket, no spec and no
payload means the inventory is empty and the demand is for the source material by name. Reading the
repo to fill that silence is the failure this step exists to prevent.

**A defect leaves this step by one of three doors.** The replacement arrives; a gap is opened at
birth where the source does not exist; or it is **noted, not blocking** — logged, and mentioned in
one line. Recording a defect without routing it is not a door.

**The third door is for what does not block the work** — a hygiene or security observation about the
human's own scratch material, a defect in an artifact nothing downstream reads. Worth saying, not
worth a numbered demand that ends the turn. Route by what the defect blocks, never by the rule that
found it.

**Word the demand like a round question.** One defect per numbered demand, never two compounded.
Most important first — the artifact blocking the most downstream work leads. Name the defect as a
gap and request the replacement precisely: not *"could you re-send the screenshot?"* but *"GAP-1:
the status enum is cut off at the right edge after the fourth value — I need the full list, as text
or an uncropped capture"*. Add one line of why it matters only where the request could be misread.

**The demand ends the turn.** Do not read ahead while waiting.

Then, and only then: read the project `CLAUDE.md` and resolve write restrictions, domain routing,
the target module's area spec or harness, the coding standard and output conventions. Confirm the
target module — which domain owns it, whether it is current, whether it deploys — each from a
document rather than from memory.

### Step 1 — Requirements

**Owes:** you and the human share one understanding, written down as criteria a reviewer could hold
code against, with every question that shaped it on the record.

Copy `templates/business-requirements.md` into the feature folder — the folder and its
`raw-context.md` exist from Step 0 — and fill it under its own comments.

**A fitness verdict is not a read.** Step 0 judged whether the material is legible; it did not learn
what it says. Before the first round, extract every in-scope statement from the supplied material
into the file — scope, criteria, compatibility rules, exclusions — each with its `SRC`. A question
whose answer sits in a section you already quoted from is the failure this prevents.

Interview in rounds until the frontier is empty, then read the rule set back in one message and ask
the human to confirm it. Their confirmation moves the state to `interviewed`.

Sort every gap by owner before the gate: **codebase** — verify in Step 2; **docs** — read the doc;
**the human** — ask in the gate request.

Strip the comment blocks from `business-requirements.md`. **→ G1.**

### Step 2 — Read the codebase

**Owes:** every unverifiable claim from the interview is settled against the code, and the tests are
demonstrably runnable.

**Read yourself**, because their words enter the plan: the project `CLAUDE.md`, the area spec folder
and harness, the coding standard.

**Delegate under P4:** the domain router for the target module, the feature code path, the reuse
search targets, and the nearest working sibling pattern. **One sub-agent per unsettled claim, run
concurrently.** Each returns its verdict and the `file · Class.method` that settles it, and nothing
else. A claim that arrived with its citation is settled by opening that citation — re-tracing
evidence you were handed is wasted work. Refuted claims go back to the human.

**Record the test invocation and its output, and re-confirm the target module scope.** A plan whose
tests cannot be run is a plan Step 4 discovers is unbuildable.

**Specs handoff — a rule, not a judgement.** Hand off to `specs-builder` **if and only if** the
target area ships a spec harness (`<area>/specs/_templates/` exists) **and** the target module's
full path contains no folder ending in `legacy`. If both hold: print `specs-builder <feature folder
path>`, set §0 `Next action` to it, and end the turn. The human runs it, then the cold spec review,
then re-invokes this skill to resume at Step 3. `specs-builder` is the only author of
`mapping-plan.md`, and the rules governing it — schema completeness, data lineage, and what makes a
field mapping evidenced rather than asserted — live in that skill, not this one. If either fails: go
to Step 3 and plan the whole feature.

### Step 3 — Plan

**Owes:** a design a reviewer can hold against the requirements — every file change justified, every
criterion given a test, every disagreement with the specs already settled.

Fill `templates/implementation-plan.md` under its own comments. Strip its comment blocks. Run the
cold review, then **→ G2.**

### Step 4 — Implement

**Only after G2.** **Owes:** code that does what G2 approved, with a red run proving the acceptance
tests bite and an unfiltered green run proving the module still works.

**The order is fixed, and the same for every feature.** It exists because tests written after the
code tend to describe it rather than judge it.

1. **Phase 1 tests.** One per phase 1 row of the test plan (plan §4). Commit them.
2. **Red run.** Record the failing invocation, the output and the commit SHA. A phase 1 row naming a
   spec file has no test to write — the spec carries it and the spec review verified it, so the log
   line names it as excluded and says which spec it rests on.
3. **Implement the file changes (plan §1)**, honouring `Sequencing constraints`. Report each file
   as it lands.
4. **Compile.**
5. **Phase 2 tests**, against the plan's phase 2 targets, now the branches exist.
6. **Green run.** The whole module's suite, **unfiltered** — a filter can exclude the very class
   that fails, so a filtered run is not evidence. Record it.

**Build from the specs first where they exist**, then the file changes (plan §1) for the remainder.
The two do not overlap, so nothing is built twice. Where no specs were generated, the file changes
(plan §1) are the sole blueprint.

**Keep planning-folder IDs out of shipped code.** `SRC`, `AC`, `NFR`, `TD` and `MAP` mean nothing to
a reader without the folder, which is every reader after cleanup. Comments in code and spec files
cover what the code does not, and never repeat it.

**Phase 2 tests are expected additions, not tampering.** `code-reviewer` diffs the phase 1 tests
from the red-run SHA and treats any weakening as a finding.

**There is no gate here.** Step 4 ends on its own checks, and the developer decides when the work is
ready. Three things hold before the state moves to `code reviewed`: the cold `code-reviewer` report
is on disk and every blocker in it is fixed or dispositioned; every open gap carries a human
disposition; and the artifacts' done-when lists are satisfied. Then report the diff, the red-run and
green-run output, and the reviewer verdict line — that is what the pull request body carries.

### Cleanup

**Owes:** what the folder learned outlives the folder.

Promote hard-to-reverse findings into the durable document that owns them, **de-referencing on
promotion — strip line numbers and planning-folder IDs**, which go stale and mean nothing to a
reader without the folder. Record a promotion decision for every debt line.

**Name every place the implementation departed from the plan, and why** — one `DEC` line each, or one
line saying there were none. A plan the build had to correct is the cheapest signal available about
which part of the planning was weak, and it is discarded unless it is written here.

Set the state to `closed`. Leave the folder on disk.

---

## The log

`raw-context.md` §1 is the record: one line per event, appended in time order, never edited.

```
- <YYYY-MM-DD> · <ID> · <short name> · <one sentence>
```

**What earns a line.** Material arrived, with its fitness verdict. A fact settled. A question the
human answered. A decision made. A gap opened. A gap closed. Debt accepted. The state moved. A gate
ticked. A run, review or commit recorded.

**What never earns one.** Search narrative. File bodies. Your reasoning. A hypothesis you discarded.
An intermediate step that produced no fact, decision or answer. **The file is minutes, not a
transcript.**

**The latest line wins, and nothing is edited.** A decision that changes is a new line naming what it
supersedes. A gap that closes is a new line — `GAP-3 closed by DEC-5`. A decision that changes under
a passed gate returns the work to that gate: set §0 back and log why.

**§0 is rewritten on the way out of every step that moved the work.** A step that changed the state
without rewriting §0 has left the folder lying to the next session, which is the one reader §0 exists
for. `Open gaps` lists the open IDs with their names, never a count — a count forces a reconcile of
the whole log, a list does not.

**Append with a shell append, not a rewrite.** Rewriting the file to add one line risks the lines
already in it, and re-reads a file that grows all run.

### What a line says, by kind

**`SRC`** — the document, its fitness verdict, and what the work uses it for. Verdicts: **fit** —
complete and legible; **degraded** — usable in part, with a named defect; **unusable** — cannot be
transcribed with confidence. Write the verdict even when it is fit: a defect absorbed silently reads
exactly like a fact afterwards. Anything not fit is demanded back, or opens a gap in the same breath.
A defective artifact keeps its ID.

- **The defects that recur:** unreadable image · cropped screenshot · elided identifier · truncated
  paste · missing referent · a sample offered as a schema · two artifacts specifying different
  behaviour · a hand-authored fixture presented as production data · claims whose evidence file was
  not supplied. **A sample never closes a value set** — only a schema or a documented enumeration
  does. Where a document names a companion file holding its citations, questions or disputed sources,
  demand that file like any other missing referent.
- **A document carrying a source cell per claim takes its verdicts by the row, not the whole.** One
  verdict over the entire file launders its ungrounded rows into a fit artifact.
  The document still takes a verdict on its legibility alone. Then: a row with a citation enters as
  an unverifiable `FACT` naming that citation; a row claiming a source without one enters as an
  unverifiable `FACT` to be traced; a row reading `none` or empty enters as a `GAP`, never a `FACT`.
- **A large artifact gets a refined file.** Extract the operations the work touches **with a
  command**, write it to `refined/`, and name both paths on the line. A model's retelling is not a
  refined file. Claims still cite the original — the extract is how it was read, the source is what
  it says.
- **An authored document is an original.** A handoff, an analysis, a memo — anything with an author
  and a date — takes the original path, even where it summarises artifacts you also hold. The refined
  path is for a command's extract of one larger artifact, and no claim may cite it.

**`FACT`** — what is true, its citation, and its verdict: `verified`, `refuted`, `superseded` or
`unverifiable`. A claim the human volunteered is unverifiable until the codebase settles it.

**A citation names the source, never your rendering of it.** Cite the operation, section, schema path
or field — never a line number in an extract, a generated file, or anything this run produced. Those
numbers hold only for the command that made the file.

- ❌ `FACT-12 · customs currency · refined/spec-fulltext.txt:974 defines consignment.customsCurrency`
- ✅ `FACT-12 · customs currency · POST /shipping/shipment field table defines
  consignment.customsCurrency; read via refined/spec-fulltext.txt`

**`DEC`** — what the work decided, the short reason, and what lost. `none — forced by <ID>` is the
only empty answer for what lost. Name the parent ID it hangs off, or `root`.

**`GAP`** — the precise question, its owner, and the search that justifies routing it there. *"The
document does not say X"* is claimable only with the search that failed to find X. **A future action
is not a search record:** *"one real call would settle it"* records nothing.

- ❌ `GAP-4 · retry on refusal · Does a refused mapping get retried? Owner: human.`
- ✅ `GAP-4 · retry on refusal · Does a refused mapping get retried? Owner: human. Searched: grep
  RetryHandler across carrier-integrations — zero files; sole retry is CarrierGlobalUtility.retry,
  guarded on 5xx and 429.`
- **Fog is not a gap.** Fog is an area you cannot yet phrase as a question. Log it as a plain line
  carrying what is unclear, why no question can be written yet, and what would clear it. It takes no
  ID and no disposition, because there is nothing to dispose of. Fog stops the work: write what is
  specified, log the fog, hand it back for direction.
- **Fog is not a bypass route.** An item is fog only if no precise question can be written for it,
  and its line says why. Anything phrasable is a gap, with a search record and a disposition.

**`TD`** — what the work leaves behind, and **what would settle it**. The settlement condition is
mandatory. A debt line with a blank one is an open gap wearing a debt label.

- ❌ `TD-7 · retry coverage · Refusal path has no retry. Settles when: revisited.`
- ✅ `TD-7 · retry coverage · Refusal path has no retry. Settles when: the partner confirms whether a
  422 refusal is retryable, or one live refusal is captured.`

### Writing a line

Short, active, one action or concept, the actor named. Instructions under 15 words, descriptions
under 20. Literal plain words and consistent terms. These rules bind every sentence you author in
the folder — the templates point here rather than restating them.

**Evidence is copied, never simplified** — quoted source text, payloads, enum values, code, paths,
identifiers, error strings, and a human's words. A rewritten quote is a defect, not a shorter
sentence.

- ❌ `the ticket says backward compatibility matters`
- ✅ `IA-4752 §4.1: "Backward compatibility for current DPD domestic and international flows"`

**The verbatim carve-out.** A human's answer and a gate approval are copied whole and quoted. Those
words are the mechanism, not a summary of it. They are the only lines the one-sentence rule does not
bind.

### Done when, at every step exit

- §0 `State` spells one rung from the ladder exactly — no blank, no `n/a`, no `<placeholder>`;
- §0 `Open gaps` lists every gap opened in the log (§1) and not yet closed there, with its name;
- every `SRC` line's paths open on disk, or the line records the artifact as not supplied;
- every `GAP` line carries an owner and a search record;
- every `TD` line carries what would settle it;
- every `SRC`, `FACT`, `DEC`, `GAP` or `TD` mentioned anywhere in the folder has its declaring
  line here;
- the log's numbers run without a hole.

---

## The round

Every question you put to the human goes out in a round, never one at a time.

**Two tests before any question reaches the human. Both, in writing, on the gap's line.**

1. **Grounded** — name the document section or the `file:line` that failed to answer it. A question
   with no failed search is a search you have not run.
2. **Material** — name what changes in the plan depending on the answer. If you cannot name it, do
   not ask: assume, and state the assumption.

**The frontier is every open question whose prerequisites are settled** — the ones you can ask now
without guessing an answer you have not heard. Prerequisites are the parent decisions and facts
already on the record, and the fill order the template states. Nobody draws the tree.

Compute the frontier. Ask **every** question on it in one message, numbered, each carrying your
recommended answer. Then stop and wait; answer nothing yourself. Record each answer, recompute,
ask the next round. A question that depends on another open question waits for the next round; that
is the only limit on a round's size — order the rest by what blocks the most work. A skipped
question stays on the frontier and is re-asked. **Silence never accepts a recommendation.**

### Finding facts is your job

**Never ask the human for a fact you can find.** The filesystem, the codebase and the tools are
searched by a sub-agent, under P4. A running lookup is an unsettled prerequisite: it holds back only
the questions beneath it, so ask the rest of the frontier now.

### Assume and state

A question that fails the materiality test takes the third exit. Record it as a `DEC` whose line
opens `assumed —`, carrying the assumption, the default it rests on, and what would overturn it.
Surface every one of them in the gate request under **Assumed, correct me** — one list the human
scans in ten seconds, instead of a round that ends the turn.

An assumption the human corrects becomes a new `DEC` naming what it supersedes. Left standing, it is
covered by the gate approval that saw it.

**Assumption is not a bypass route.** An item is assumable only where the answer changes nothing you
can name. Anything that moves a criterion, a file in the plan or a test is a question or a gap.

### The escalation ladder

Work a gap down this ladder in order, stopping at the first resolution. **Write what each step
found before moving to the next** — a gap reaching the human with no search record is unfinished
work, whatever disposition it later takes.

1. **Supplied artifacts** — search the whole document, not the local neighbourhood. A defect in one
   operation may be systematic; check sibling operations to find out.
2. **Target codebase** — if the codebase does not consume the missing field, it is not a gap. Prove
   that by checking the target model's implementation; inferring "no consumer needs this" from the
   source contract is not proof.
3. **Design resolution** — test whether one design choice safely handles every surviving reading. If
   one does, record it as a decision listing the readings it survived, and close the gap. Do not ask
   the human to choose between identical practical outcomes.
4. **The human** — escalate only when 1 to 3 failed.

**Split the frontier by owner.** A question this human owns — a decision, a budget, a scope call, a
fact only they hold — is asked. A question owned by anyone else stays a gap line with an assumption
standing in.

### Conflicts stop the work

A contradiction between code, legacy behaviour and human-supplied docs or directives stops the work
and goes to the human. Where several approaches are viable, present them with their trade-offs and
data-integrity implications and let the human pick.

**Carve-out:** where a single artifact contradicts itself — API prose against its own schema — apply
the ladder first and resolve it by codebase check or design resolution. Escalate only if that fails.

### The prototype branch

**A question answerable in twenty minutes of throwaway code should not become permanent debt** — the
behaviour of a retry annotation under a particular failure, whether a state machine does what its
diagram says.

**Offer one; never build one unprompted.** Offer at a gate, once the question is stated in writing
and steps 1 to 3 of the ladder have failed. If you cannot state it, you have fog. The human's answer
is a scope call, recorded as a decision.

**Throwaway, and outside the production tree** — scratch branch, one command, no persistence, no
tests, no integration. One that cannot be built without touching production code is not a prototype;
the question goes back as a gap. One that grows features has become the thing it was meant to inform.

**Capture it or it was worthless.** Record the verdict and the question it settled as a decision,
cite the branch by name, fold the answer into the requirements or the plan, and close the gap under
disposition 2 — this is a route by which a gap gets *closed* rather than *recorded*.

### The format

| Marker | Use |
|---|---|
| 🧭 | Round header |
| ❓ | A question |
| 💡 | Your recommended answer |
| ⏳ | A question held back by a running lookup |
| 🔍 | Where you searched, and what it failed to answer |
| ✅ | A settled rule in the read-back |

```
🧭 **Round 2** — 3 questions · ⏳ 1 held for a lookup

❓ **Q1 — <question title>**
<the question, the options, and what hangs on the answer>

🔍 **Searched:** <the document section or file:line that failed to answer it>
💡 **Recommend:** <your answer, and the reason in one line>
```

Markers belong in the chat round. The artifacts stay plain text.

*The round — the frontier, the one-message rule, this marker table — is duplicated by design with
`specs-builder`: installs symlink each skill directory whole, so a shared file would not ship. The
two copies are edited in the same change; only the ✅ row differs, naming what each skill reads
back.*

---

## The gates

**A gate ends the turn.** Stop and wait. A gate is `Approved` only when the human explicitly says
`"approve"` / `"approved"`.

| Gate | After | The human approves | Blocks |
|---|---|---|---|
| **G1** | Step 1 | The business understanding — the value, the workflow, every criterion and constraint | Reading code on wrong assumptions |
| **G2** | Step 3 | The plan — file changes, debt, governance, the test plan — plus `mapping-plan.md` and the specs where they exist, the spec review verdict line, and every open gap's disposition | **Any production code change** |

**Spec files are contract, not production code.** The G2 block covers the production code tree. A
spec folder under `<area>/specs/<integration>/` is written before G2 by design — it is what G2
approves, alongside the plan.

### The gate-request pass — before every gate, and before Step 4 ends

**Satisfy the done-when list in every artifact you are presenting**, and satisfy it by opening the
files and listing the IDs — **never by recalling what this session did.** A count you did not
enumerate is a guess, and a guessed count is the failure this pass exists to catch. Two artifacts
whose counts must match are compared as two written lists.

**Three done-when items have a command, and the command is the evidence:**

- strip complete — `grep -c '<!--' <file>` returns `0`;
- criteria against phase 1 — `grep -o 'AC-[0-9]*' business-requirements.md | sort -u` against the
  same over `implementation-plan.md`, diffed;
- the baseline — `git rev-parse HEAD`, and at G2 `git hash-object` per planning artifact.

**Then read each artifact top to bottom as its reader**, who has the file and nothing else. The list
above is every check a script could run, and a file passes all of them while being unreadable. Three
questions, answered by reading, not by grepping:

- **Does every name mean something?** An alias, an initial, a bare number — `W`, `§15` — is a defect.
- **Does the altitude hold?** Requirements: rename every class in the repo, and not a word changes.
  Plan: nothing re-argues what G1 settled.
- **Does every diagram render?** Render it. Where no renderer exists on this machine, say so in the
  gate request — an unrendered diagram is presented as unverified, never as checked.

**Then run the cold review — before G2 and at the end of Step 4 only; G1 has no reviewer.** Print
the invocation — `plan-reviewer <feature folder path>` before G2, `code-reviewer <feature folder
path>` at the end of Step 4 — set §0 `Next action` to it, and end the turn. The human runs it in a
fresh session. The review is mandatory at both.

**The review loop.** On re-entry, read the report the reviewer left in the folder. Blockers return
the work to its step: fix the artifacts, then hand the human the re-review invocation. **At most 2
cycles** — findings that survive go to the human as gap dispositions, at the gate or in the pull
request body. **A G2 request always carries the latest report's verdict line, and so does the pull
request.**

Both are skipped at **Light**.

### The four dispositions

Exactly one per gap, each requiring an explicit human utterance. There is no fifth. **Approving a
gate with a gap still open *is* disposition 4**, and it mints a debt line.

| # | Disposition | The human, in substance | Recorded as |
|---|---|---|---|
| 1 | **Answered** | Supplies the missing information | A decision line, or a criterion in the requirements; gap closed |
| 2 | **Resolved** | Accepts empirical evidence the agent produced | A fact line with its citation; gap closed |
| 3 | **Ignored** | *"ignore it"* / *"out of scope"* | Gap closed as accepted-unresolved, with who, when, and the instruction quoted. Moves to requirements *Out of scope* |
| 4 | **Tech debt** | *"log it as debt"*, *"approve anyway"*, or any explicit instruction to proceed with it open | A debt line, with **what would settle it** filled in, plus the instruction quoted, who and when. Gap closed; the debt line is the open item |

- **Silence is not a disposition.** A gap the gate request never surfaced blocks the gate; an
  `approve` spoken over a surfaced one is disposition 4, not silence.
- **An answer to a gap is not a gate approval.** Approval needs the word `"approve"` *in addition
  to* the dispositions. Merging them is exactly the inference P1 forbids.
- **`What would settle it` is mandatory, not decorative.** A debt line with a blank settlement
  condition is an open gap wearing a debt label, and the gate is not approved until it is filled.
- **Gaps opened after a gate re-open the log, not the gate.** A gap surfaced in Step 2 is
  dispositioned before G2; it does not retroactively invalidate G1.

### The baseline

On approval, record it in §0 `Baseline`: the branch commit SHA (`git rev-parse HEAD`) and, at G2,
one content hash per planning artifact (`git hash-object <file>`) — the folder is gitignored and has
no commit SHA of its own. G2's SHA is the fixed point `code-reviewer` diffs against, so it is the
one that must be right.

---

## The IDs

| Prefix | Zone |
|---|---|
| `AC`, `NFR` | **Document** — minted in `business-requirements.md`, contiguous and local to their table |
| `SRC`, `FACT`, `DEC`, `GAP`, `TD` | **Log** — minted in `raw-context.md` §1, one shared counter across the folder |
| `MAP` | `specs-builder`'s, in `mapping-plan.md` |

**Mint a log ID by reading the highest number under `raw-context.md`'s `## 1. Log` heading and adding
one.** Nowhere else — an example elsewhere in the folder is not a minted ID. The prefix says what
kind, the number says when. A duplicate is impossible, and a hole in the sequence means a line was
deleted. No zero-padding. Every log ID carries a short name at birth, and every later mention copies
that name exactly.

---

## Re-entry

**Only when the invocation named an existing feature folder.** That run is a resumption: read §0
first, state the rung aloud, and **let the rung choose the step**. Demanding source material for
work that reached rung 6 is the failure this prevents.

| §0 `State` | Resume at |
|---|---|
| `awaiting source material`, `intake complete` | Step 0 |
| `interviewed`, `requirements generated` | Step 1 |
| `requirements approved` | Step 2 |
| `codebase read` | Step 2's specs handoff, or Step 3 where it does not fire |
| `specs generated` | Step 3 — read the spec review's verdict line first |
| `plan generated` | The gate-request pass, then G2 |
| `plan approved` | Step 4 |
| `code generated` | Step 4's exit checks |
| `code reviewed` | Cleanup |

Then diff the folder's artifacts against §0's expectations and state any partial work aloud.
**Where §0 and the folder disagree, say so and stop** — a resumption on a wrong rung writes over
work.
