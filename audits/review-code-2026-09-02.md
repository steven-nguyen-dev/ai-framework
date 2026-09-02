# review-code — audit 2026-09-02

Scope: `ai-first-fw/skills/review-code/SKILL.md` v2.3.0 and its `references/quality-bar.md`, audited
on cost alone. Correctness of the review product is out of scope — the run under audit found a real
blocker and the skill is not accused of missing anything.

Held against one observed run: PR #22482, 53 carried files, reported by its own orchestrator as
1.94M total tokens / $24.22 — 155.2K main context, 1.78M across 13 agents.

**Verdict: 1 blocker · 4 defects · 2 notes. All seven applied in v2.4.0** (plugin 2.0.10) — each fix
below is in the skill, with its rationale carried inline at the line it changes.

**This file stays in `audits/` until the §1 tier decision closes.** Its findings are addressed; what
holds it open is the Open questions — the measured 1.94M baseline is what a re-run is checked against,
and the §1 yield table is the only evidence there is for the coverage trade that reaching 300–400k
would need. Clear it once that decision is made on a tagged run.

---

## The evidence

Measured by the orchestrator on request, from its own `<usage>` blocks and two `ListAgents` calls:

| Agent | Dispatched by | Tokens | Tool calls | Findings returned |
|---|---|---|---|---|
| A · intrinsic | the skill | 99,491 | 11 | 1 blocker, 3 defects, ~8 notes |
| B · regression | the skill | 87,415 | 33 | 0 blockers, 2 defects (both duplicates of A/C), 5 notes |
| C · ask conformance | the skill | 166,959 | 52 | the one blocker that mattered |
| 9 further agents | **not the skill** | unmeasurable individually | — | never surfaced to the orchestrator |
| orchestration (main) | — | 155,200 | — | read the ask, found the lead C confirmed |

**The skill dispatched 3 agents. Twelve ran, and the orchestrator confirms all twelve belong to this
review — no unrelated work in that session.** So nine agents were dispatched by passes, not by the
skill. Measured against the run total that is `1.78M − 353,865 = 1,426,135` across nine agents,
**~158k each, and 74% of the entire 1.94M run.**

Pass A self-reports five of them ("5 parallel sub-reviews"). Four are explained by nothing. The
orchestrator cannot close that gap: `ListAgents` returns no parent field and no token count for an
agent it did not dispatch itself, so **the fan-out is structurally invisible from where the skill
runs** — which is why finding 1's fix has to be a self-report in the return.

Two corrections the orchestrator made against its own earlier summary, adopted here: pass B's file
list was **40 files, not 38**; and the connector `CategoryAttributesDTO.java` deletion is mechanical
dead code, not logic.

## The root

No line in `SKILL.md` or `quality-bar.md` changes what an agent does as the diff grows. A 3-file diff
and a 53-file diff hit identical instructions, and every demand in the skill is written *per file* or
*per item*:

- `quality-bar.md` line 3: "Every file a pass was given carries a §1 answer."
- `quality-bar.md` §3: "Match all fourteen against the diff every run."
- `SKILL.md` bar: "Every carried file carries a §1 answer, and every §2 duty is answered at both SHAs
  over B's inventory."

§1 holds 12 items. Over 53 carried files that is 636 mandatory answers for pass A, plus 14 smell
matches, before a single finding is written. The demand is exactly what §4 of `levers.md` asks a
completion criterion to be — exhaustive and checkable — and at this file count exhaustive is the whole
bill. The skill needs a **scale lever**: one axis on which depth varies with what a file is, decided
once by the orchestrator and carried in the brief.

---

## Finding 1 — `blocker` — nothing bounds a pass's own delegation

Step 3, the sentence that describes what a pass does:

> Each agent reads `inventory.md` for the files its own row below names, opens them at the SHA its
> brief gives it, performs its own review in its own context, and returns findings in step 7's shape.

"performs its own review in its own context" is satisfied by an agent that dispatches children and
merges their returns. Nothing in the step, the brief, or the bar says the pass is the last agent in
its own chain. Handed 53 files and a 12-item checklist per file, pass A did the arithmetic and fanned
out "one per functional area."

**This is not a share of the cost, it is the cost: 1.43M of 1.94M, 74% of the run.** And it is not
the children's review work — it is the layer around it: nine agent spin-ups, nine loads of
`quality-bar.md`, nine sets of `git show` calls, nine reports written and merged. Nothing stops a
child from doing the same, so the multiplier has no ceiling.

It is also silent, in two ways. Step 3's completion criterion — "both agents were dispatched … and
each return is in hand or named as failed, timed out or empty" — is satisfied identically whether 2
agents ran or 12. And the harness offers no help: `ListAgents` returns no parent and no token count
for an agent the orchestrator did not dispatch, so the orchestrator could not have detected the
fan-out even had it looked. **The count has to come back inside the return, because there is nowhere
else it can come from.**

**Fix — add one line to step 3, in the paragraph that says what travels to a pass:**

> A pass is the last agent in its own chain: it works its own file list itself and dispatches nothing
> further. Where its list is larger than one context holds, it reports the files it could not reach in
> its return rather than delegating them.

**And make it observable — replace step 3's completion criterion:**

> **Completion:** both agents were dispatched from a context holding the four paths, the standard and
> the bar; each return is in hand or named as failed, timed out or empty; and each return names the
> agent count it ran as, which is one.

---

## Finding 2 — `defect` — the §1 answer is demanded per file, over files that are one file

`quality-bar.md` line 3 demands an answer per file. Step 3 gives pass A "every carried file". Neither
knows that a diff can carry the same file seven times under seven names.

Counted directly against the run's diff, **20 of the 53 carried files — 38% — verifiably share a
shape with a sibling**, collapsing to 5 representatives:

| Group | Files | Verified by |
|---|---|---|
| Amazon asset transformers, AE/AU/FR/IN/JP/SG/UK/US | 8 | byte-identical after substituting the country code; US differs by one Javadoc line |
| DTO mirror pairs across connector and core-model | 6 (3 pairs) | field-by-field identical, snake_case against camelCase |
| deleted boilerplate DTOs | 6 | zero `if`/`for`/`while`/`switch` at base; `DefObjectDTO`'s two branch lines sit inside a generated `equals()` |

Pass A returned ~8 low-severity notes, ~7 of them from §3 over these shapes — full reasoning cost per
file, re-deriving the same finding, for notes.

The waste is `Duplicated Code` itself: §3 names it as a smell, and the checklist is not allowed to act
on its own finding.

**Fix — give step 1's inventory the shape column, so the collapsing is decided once, cheaply, by the
orchestrator, and travels in the brief.** Replace the `inventory.md` row of step 1's table:

> | `inventory.md` | one row per changed file: path, added, deleted, `carried` or `excluded`,
> `addition-only` where the deleted count is zero, and a `shape` group name shared by files whose
> hunks are the same shape under different names — a generated method, a near-clone transformer, a
> boilerplate DTO |

**And add to `quality-bar.md`, under the paragraph at line 3:**

> Files sharing a `shape` group carry one answer between them, written against the representative the
> group names and closing `N others share this shape: <paths>`. A finding that turns on a
> file's own identity — a name, a value, a call unique to it — is answered per file regardless.

---

## Finding 3 — `defect` — pass B's file set admits a two-line deletion at full §2 depth

Step 3's table, pass B's file set:

> every carried file the inventory marks with a non-zero deleted count or a rename

A file that deleted an unused constant and a file that deleted a guard clause enter §2 identically,
and §2 holds five duties each requiring both-SHA reads — provenance, conditionality, contract at the
edge, load-bearing tests, both versions running. Pass B ran this over all 40 qualifying files for 33
tool calls and returned 0 blockers and 2 defects that A and C had already found.

Of those 40: **14 are mechanical deletions** — two schema JSONs, four DTOs, an interface, the 6
deleted boilerplate DTOs, and the connector `CategoryAttributesDTO` dead copy-constructor — each
individually eyeballed. 23 are logic-bearing and 3 mixed, both counts by keyword heuristic over
deleted lines, not per-file read; the one file that *was* read by hand came back misclassified by that
heuristic, so treat 26 of the 40 as directional. **35% of pass B's list, verified, needs no §2 at
all.**

`non-zero deleted count` is the cheapest possible predicate and it is doing the work of a triage.

**Fix — replace pass B's file cell in step 3's table:**

> every carried file the inventory marks with a rename, and every added migration, schema and config
> file — an added one carries no fixed-point version and still answers §2 against the rows and
> messages the base wrote. Of the files carrying a non-zero deleted count, those whose deletion
> removes logic — a branch, a call, a read, an assertion — answer §2 in full; a file whose deletion is
> mechanical answers one question, *does any caller or behaviour go with it?*, and closes there.

---

## Finding 4 — `defect` — pass C is handed the ask in full after step 4 has already reduced it

Step 5, first sentence:

> Pass C's brief is step 3's, plus the ask in full and the prescription list.

Step 4 is where the orchestrator reads every source, marks each `read` / `not found` / `unreachable`,
and lists every technical prescription as its own quoted sentence. That is a reduction of the ask,
paid for in the orchestrator's own context — and step 5 then ships the unreduced ask on top of it, so
pass C re-derives what step 4 already derived. C came back the most expensive pass in the run: 167k,
52 tool calls, against a 20-FR epic of which ~8 gated the diff. The orchestrator had already spotted
the `browse_node_ids` contradiction itself, before dispatching, and did not hand C the lead.

Step 5's completion criterion needs every requirement accounted for, so the *list* must travel. The
raw documents need not.

**Fix — replace step 5's first sentence, and add step 4's second product:**

Step 4, appended to **Mark the technical prescriptions**:

> **Enumerate the requirements, and mark the suspects.** List every requirement the ask states, one
> line each, with the source it came from. Where reading the ask against the change already raises a
> contradiction, name it — that is pass C's lead, and it is free here.

Step 5, first sentence:

> Pass C's brief is step 3's, plus the requirement list, the prescription list, and the suspects step 4
> named. The documents behind them travel by path, opened by C where a line it must settle is not
> settled by the list.

Step 4's completion criterion gains:

> …and every requirement in the ask stands in the list with its source.

---

## Finding 5 — `note` — the three passes each rediscover the same files, and only the discovery is recoverable

Step 1 materialises `code.diff` and `inventory.md`; it does not materialise file text. Step 3 has each
agent "open them at the SHA its brief gives it", so A reads at head, B reads at both SHAs, C reads at
head — 96 `git show` calls across the run.

The content tokens here are not recoverable: three isolated contexts reading the same file cost three
reads by construction, and that isolation is what the skill is for. What is recoverable is the search
around each read — resolving which path at which SHA, and re-listing. Small per call, 96 calls deep.

**Fix — one line in step 1, after the artefact table:**

> Where a carried file's row is B's, write its fixed-point and head text beside the artefacts as
> `<path>@base` and `<path>@head`, so a pass opens a path instead of resolving one.

Grade it a note: it buys tool calls and latency, not the bulk of the tokens.

---

## Finding 6 — `defect` — a finding never names the checklist item it came from, so cost per item is unmeasurable

`quality-bar.md` demands the answer be item by item. Step 7's finding shape does not carry the item
back. Part 4 of a finding is:

> **What it contradicts** — the requirement source, the standard's rule, the named sibling, the stack
> practice, the named smell, or `quality`.

A §1 finding lands in `quality`, and the item number is gone. Pass A cited items 2, 9 and 10 by number
of its own accord; items 1, 3, 4, 8, 11 and 12 are cited nowhere in its return, though some of its
notes read like item 3 and item 8 untagged. Items 5, 6 and 7 were stated clean across every file.

So after a 1.94M run, the question *what did §1's twelve items each cost and each buy* is not
answerable — and that is the exact question the tiering in findings 2 and 3 needs answered before it
can be extended to §1. **The reporting shape is what stops the skill from being tuned against its own
runs.**

The §3 line has the same defect in a sharper form. §4 demands `smells: <n>/14 applied · suppressed:
…`. Pass A returned `8/14 applied` followed by **eleven** smell names, one of which — Message Chains —
was separately marked suppressed in the same report. The count, the list and the suppression
contradict each other, and the criterion that was supposed to make coverage checkable passed anyway.

**Fix — replace part 4 of step 7's finding shape:**

> 4. **What it contradicts** — the requirement source, the standard's rule, the named sibling, the
>    stack practice, or the bar's own item by number: `§1.7`, `§2 provenance`, `§3 Feature Envy`.
>    Every finding names one.

**And make §4's line self-consistent — replace its last bullet in `quality-bar.md`:**

> - **Every suppression is reported.** Close with one line — `smells: <applied>/14 · applied:
>   <names> · suppressed: <smell> (<rule or file that earned it>), …` — where the applied names
>   number exactly `<applied>` and no name appears in both lists.

## Finding 7 — `note` — the closing coverage list is unbounded

Step 7's close:

> an *Adjacent, not reviewed* list carrying everything else you noticed

"everything else you noticed" has no floor, and it is written by every pass and again by the merge. At
53 files it is the one part of the report whose length is set by how much the agent looked at rather
than by what it found.

**Fix:**

> an *Adjacent, not reviewed* list — each entry a place the review touched and left, with the reason
> it was left; a place with no reason to name is not an entry.

---

## What is not the problem

The three-pass structure is not the waste, and the audit does not recommend collapsing it.

- The passes read **disjoint** checklists — A holds §1/§3/§4, B holds §2, C holds the ask — so the
  duplication is in file reading, not in reasoning.
- Ticket-blindness for A and B is what kept the regression findings from being framed by the
  requirement, and cross-pass agreement on the same schema drift is confidence the single pass cannot
  produce.
- The orchestrator reading the ticket and the attachment itself, in step 4, is what surfaced the run's
  only blocker.

Every fix above leaves all three intact.

---

## Expected effect

Built as a target-state budget rather than a subtraction, against the same run — PR #22482, 53
carried files, SHA pair pinned, so a re-run settles every line. Baseline 1.94M / $24.22.

| Component | Now | After | What moves it |
|---|---|---|---|
| orchestration (main) | 155k | **155k** | untouched by every fix below |
| pass A | 99k **+ ~790k in 5 children** | **150–200k** | fix 1 removes the layer; fix 2 takes 53 files to 38 shapes |
| pass B | 87k | **55–65k** | fix 3 drops 14 of 40 files to a one-shot question |
| pass C | 167k | **70–90k** | fix 4 hands it the reduced ask instead of the epic |
| 4 further agents | ~630k | **0** | fix 1 |
| fixes 5, 6, 7 | — | ±0 | tool calls, report length, tagging — not bulk |
| **total** | **1.94M / $24** | **430–510k / $5–6** | |

**~1.45M off, 74–78% of the run.** Against your ceiling of 600k this clears. Against 300–400k it does
not, and the reason is the first row.

### The orchestration wall

Every fix here shrinks the passes, and the passes are no longer where the floor is. **Orchestration
is 155k — at a 400k target that is 39% of the whole budget, spent before a pass is dispatched.** It
covers reading the Jira ticket and the `IA-5105-oms-api-changes.md` attachment (which earned it — that
read found the only real blocker), building the four step 1 artefacts, marking step 4's sources, then
step 6's merge and step 7's report holding all three returns at once.

Which of those five costs what is **unknown** — the orchestrator has no per-step split of its own
context. That is the single measurement still missing, and it decides whether 300–400k is reachable
without cutting coverage.

### What 300–400k actually costs

Below ~430k, the fixes stop being efficiency and start being coverage. `quality-bar.md` line 3 —
"Every file a pass was given carries a §1 answer" — is a floor of 12 items × every carried file, and
nothing goes under a floor. Reaching 300–400k means tiering §1 itself. The run's own yield says what
that would have cost:

| §1 item | Yield across all 53 files |
|---|---|
| 2 · failure paths | blocker 1 |
| 9 · terminus | blocker 1, and the `browseNodeIds` schema defect |
| 10 · tests | the `searchProductTypes` untested defect |
| 5, 6, 7 · authZ, untrusted input, secrets | explicitly clean on every file — zero findings |
| 1, 3, 4, 8, 11, 12 | never cited by number; two notes read like items 3 and 8, untagged |

Three of twelve items produced every §1 finding. But **the reading that gives is not the reading to
act on.** Items 5, 6 and 7 returning clean across 53 files *is* the deliverable — a security floor is
worth most on the run where it finds nothing, and one run is not evidence to cut it. And items 1, 3,
4, 8, 11, 12 are un-cited rather than idle: finding 6 is precisely that the report cannot tell those
two apart.

So the honest ordering is: **ship fixes 1–7, land at 430–510k, and let finding 6's tagging measure one
run.** After that the §1 tier is a decision on evidence rather than on this table. Cutting §1 now, on
one run's citations, trades a security floor for ~80k.

### What the estimate rests on

- Pass A's post-fix cost is the one projection left. Its 11 tool calls suggest most of its work
  happened in children, so absorbing that work is a real increase — 150–200k assumes fixes 2 and 3
  have already shrunk the list it absorbs. **Without fix 2, A absorbing 53 files at 12 items may not
  fit one context at all.** Ship 1, 2 and 3 together or not at all.
- The 4 unexplained agents are priced at the 158k mean. Their parentage is unmeasurable; their
  attribution to this review is confirmed.
- The orchestrator's own "4–6x a normal review" target was set against its accounted ~500–600k, not
  the observed 1.94M. Against the real baseline, 430–510k is ~6–8x a 60k single-pass review.

## Open questions

- **Orchestration's 155k has no per-step split.** Ticket-reading, artefact-building, source-marking,
  merge and report are one undifferentiated number, and it is 39% of a 400k target. This is the one
  measurement that decides whether the target is reachable without cutting coverage.
- **Nine agents' parentage is unmeasurable.** `ListAgents` returns no parent field and no `<usage>`
  for an agent the orchestrator did not dispatch. Pass A self-reports five; four are explained by
  nothing, and whether B or C also fanned out is `not found` — neither return mentions it.
- **Whether an agent obeys "dispatch nothing further" is untested.** Finding 1's completion criterion
  makes a breach visible in the return; it does not prevent one, and a child could self-report
  falsely.
- **26 of pass B's 40 files were classified by keyword heuristic, not read.** The one file read by
  hand was misclassified by that heuristic, so finding 3's 14-file mechanical count is verified and
  its 23-file logic-bearing count is directional.
- **§1 items 1, 3, 4, 8, 11 and 12 are un-cited, not proven idle.** Finding 6 exists because the
  report cannot distinguish those two, and no §1 tier should be cut until it can.
