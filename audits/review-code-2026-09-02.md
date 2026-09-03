# review-code — audit 2026-09-02

Scope: `ai-first-fw/skills/review-code/SKILL.md` v2.3.0 and its `references/quality-bar.md`, audited
on cost alone. Correctness of the review product is out of scope — the run under audit found a real
blocker and the skill is not accused of missing anything.

Held against one observed run: PR #22482, 53 carried files, reported by its own orchestrator as
1.94M total tokens / $24.22 — 155.2K main context, 1.78M across 13 agents.

**Verdict: 2 blockers · 6 defects · 2 notes.** Findings 1–7 applied in **v2.4.0** (plugin 2.0.10) and
measured on a re-run — see *Run 2*, which took the same PR from 1.94M to 954.3K. Findings 8, 9 and 10
came out of that re-run's forensics and are applied in **v2.5.0** (plugin 2.0.11), unmeasured.

**Findings 11–15 are a counter-audit of those ten** — what the cost fixes took out of the review when
held against a diff this PR does not resemble — applied in **v2.6.0** (plugin 2.0.12). Finding 11 is a
regression v2.5.0 introduced and v2.6.0 removes.

### What the counter-audit costs

v2.6.0 buys coverage back, and coverage is tokens. Against the ~600–670K v2.5.0 was projected to land
at:

| Fix | Effect on the run |
|---|---|
| 11 · inert-based marking | B's file set returns to ~40 of 55 from the ~10 the statement-based rule would have left. **+40–50K** — B reads their hunks, not their texts, so the file count no longer sets the cost |
| 12 · read the ask in full | **+0 measured.** The by-heading line was v2.5.0's and has never run; run 2 read all 127,476 bytes in full without it. It removes a projected saving, not a real one |
| 13 · items 5, 6, 7, 9 per file | 21 files leave the shape groups for 4 of 12 items. **+50–70K** on pass A |
| 14 · escalation on `not reached` | one extra agent, only where a pass returns short. **+0–60K, conditional** |
| 15 · C reads the ask on untraced behaviour | fires only on behaviour tracing to no requirement. **+10–30K, conditional** |

**Run 3 should land at ~700–820K rather than ~600–670K** — still 58–64% below the 1.94M baseline, at a
cost of roughly 100–150K for the authorisation-regression hole, the scope-creep pass and the
silent-partial-review failure.

Finding 11 is the one to read carefully before calling this a cost increase: run 2 already reviewed 40
files in pass B, because `mechanical` marked only 4. The statement-based rule would have *dropped* that
to ~10 in run 3. So finding 11 does not add cost against anything measured — **it prevents a saving
that would have been a coverage cut**, and the counter-audit exists because that distinction is not
visible from a token count.

**Findings 16 and 17** come from a third run — a different, smaller diff, which **ran v2.4.0, not
v2.6.0** — and are applied in **v2.7.0** (plugin 2.0.13). That run also closed the §1 tier question
and forced three retractions; see *Run 3*.

**Findings 8–17 have never run.** Every measurement in this file is of v2.3.0 or v2.4.0. The session
doing the reviewing loads the installed plugin, not this working copy, so a run that proves any of it
needs the plugin reinstalled first.

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

### The floor — why 300–400k is not reachable at this diff size

Run 2 settles this with a measurement rather than an argument. **The cheapest pass was C at 144,143
tokens**, and C is the reduced one: a pre-scoped brief, no full ask, 37 tool calls. No pass came in
under 144K, because every pass reads the same 55-file diff before it reasons about anything.

Three isolated passes therefore floor at roughly `3 × 144K = 432K`, and orchestration — which must
read the ask, build the artefacts and merge three returns — sits on top. **The floor of this design at
55 files is ~600–670K.** Findings 8, 9 and 10 take the run from 954K to roughly that floor; nothing
short of changing the design goes under it.

So the 300–400K target and the three-pass cold review are incompatible at 55 files. The choices are:

- **Accept ~600K** for a whole-PR three-pass review, at $8–9.
- **Review by scope, not by PR** — run the three passes over the files one requirement touches, and
  run it per requirement. Same passes, smaller diff each, and the total across a ticket may well
  exceed 954K even as each run lands under 400K.
- **Drop a pass for small or low-risk diffs** — a second invocation mode, chosen at step 1 from the
  inventory, where §2 folds into A's checklist. That is a coverage decision, and §2's two-run silence
  is an argument for it that §2's failure mode is an argument against.

The first is the honest recommendation until a third run's tagging says otherwise.

### What cutting §1 would actually cost

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
act on**, and run 2 proves it: §1.9 Terminus carried run 1's blocker and returned **zero** in run 2,
while §1.1 and §1.12, silent in run 1, both fired. Item yield moves run to run. Held across both runs,
only items **3, 4, 8 and 11** have never fired — and 5, 6 and 7 (authZ, untrusted input, secrets)
returning clean on every file *is* the deliverable, worth most on the run where it finds nothing.

So the §1 tier still waits on evidence, and now on more of it than one tagged run. Two runs say the
per-item table is noisy; a third and fourth say whether 3, 4, 8 and 11 are idle or merely unlucky.
Cutting §1 today trades a security floor for ~80K against a sample of two.

### What the estimate rests on

- Pass A's post-fix cost is the one projection left. Its 11 tool calls suggest most of its work
  happened in children, so absorbing that work is a real increase — 150–200k assumes fixes 2 and 3
  have already shrunk the list it absorbs. **Without fix 2, A absorbing 53 files at 12 items may not
  fit one context at all.** Ship 1, 2 and 3 together or not at all.
- The 4 unexplained agents are priced at the 158k mean. Their parentage is unmeasurable; their
  attribution to this review is confirmed.
- The orchestrator's own "4–6x a normal review" target was set against its accounted ~500–600k, not
  the observed 1.94M. Against the real baseline, 430–510k is ~6–8x a 60k single-pass review.

## Run 2 — v2.4.0 measured, same PR

| | v2.3.0 | v2.4.0 |
|---|---|---|
| total | 1.94M / $24.22 | **954.3K / $13.33** |
| main | 155.2K | 237.3K |
| sub | 1.78M across **12** agents | 717.0K across **3** |
| pass A | 99,491 · 11 calls | 330,721 · 60 calls |
| pass B | 87,415 · 33 calls | 262,530 · 73 calls |
| pass C | 166,959 · 52 calls | 144,143 · 37 calls |

**51% off.** The per-pass sum is 737,394 against a reported sub of 717.0K; the ~20K gap is
unexplained and small enough to leave.

Against the 430–510K this audit predicted, the miss is 2x, in two places. **Orchestration rose
instead of holding** — fixes 2 and 4 charge the orchestrator by design, so the "155k, untouched" row
was wrong. **And each pass cost ~2x the projection**: absorbing delegated work is dearer than the
projection allowed.

### What each fix did

| Fix | Verdict |
|---|---|
| 1 · no self-delegation | **worked, as designed.** 12 agents → 3, all three self-reporting one. −1.06M, and it is the whole of the saving. |
| 2 · shape groups | fired: 27 of 55 files in 6 groups, answered once each |
| 3 · B triage | **under-fired: 4 of 55 marked `mechanical`.** B still ran all 40 files carrying a deletion |
| 4 · C pre-scoped | worked: 167K → 144K, C still returned both its defects. C is now the cheapest pass |
| 5 · materialised text | **did not backfire** — `git show > file` in a Bash loop, 59 files / 1,364,544 bytes, none of it through the orchestrator's context |
| 6 · item tagging | **the decisive one.** It bought the table below |
| 7 · bounded close | no measurement |

### Yield per item, from the tagging fix 6 added

| Bar | Fired | Zero |
|---|---|---|
| §1, 12 items | 1.1 (note), 1.2 (defect), 1.12 (note) | **9 items** |
| §2, 5 duties | none | **all 5** — "corrections and confirmations, not findings" |
| §3, 14 smells | 8, one note each | 6 |

**Pass B has now returned zero unique findings across two runs, for 87,415 + 262,530 = 349,945
tokens.** Run 1's two defects were duplicates of A and C; run 2's output was confirmations. That is
the strongest cost signal in either run.

It is not yet permission to delete pass B. §1.9 Terminus carried the blocker in run 1 and returned
zero in run 2 — **one run's silence is not an item's value**, and §2 hunts exactly the failure that
carries no exception and no red test. What the number does license is making B cheap, which finding 8
does.

## Finding 8 — `defect` — pass B reads two full files where it needs two hunks

Step 3 sends B "every carried file the inventory marks with a non-zero deleted count", and fix 5 now
lays both texts on disk for it. Measured: 40 `@base` files at 685,772 bytes and 19 `@head` at 678,772.
B reports reading all 40 pairs. **That is B's 262K almost entirely** — and §2's five duties do not need
whole files. Provenance needs the removed read and its suppliers; conditionality needs the removed
branch; contract-at-the-edge needs the changed signature and its callers. Each is a hunk plus a
search, not a file.

Fix 3 was meant to cut the file count and fired on 4 of 55, because `mechanical` demands *every*
deleted line be trivial — one real deletion in a file of cleanups disqualifies it. The predicate is
the wrong way round.

**Fix — invert the mark, and cut what travels rather than only who gets it.** In step 1's
`inventory.md` row, replace `mechanical` with:

> `logic-removing` where a deleted line removes a branch, a call, a read, an assignment or an
> assertion — a file with no such line is left unmarked

In step 3's pass B cell:

> …every carried file the inventory marks `logic-removing` or renamed, and every added migration,
> schema and config file. An unmarked file with deletions answers one question — *does any caller or
> behaviour go with it?* — from its diff hunks alone, and closes there.

And in `quality-bar.md` §2, after its first paragraph:

> Read the hunks, then what they reach. A duty opens the fixed-point file where the hunk does not
> settle it — a supplier to trace, a caller to count — and not before.

## Finding 9 — `blocker` — step 1's artefact path collides between sessions, and this run adopted a peer's

Step 1 writes to `$(git rev-parse --git-dir)/review-code/<head short sha>/`. The key is the head SHA
alone, so **two sessions reviewing the same head write the same paths.** That is what happened: the
orchestrator found `inventory.md` (11,563 bytes) already on disk under
`.git/review-code/b4c115455ec/`, written moments before its own writes, mtimes interleaved, matching a
busy peer session in `ListAgents`.

It adopted the file. It verified the row counts against its own independently computed numstat first —
the right instinct, and **the skill nowhere asks for it.** A run that trusted instead of verifying
would review against another session's triage, at another session's skill version, with no signal that
it had.

The cost reading is also corrupted by it: step 1's shape-grouping and mechanical-marking cost was paid
by the peer, so **237.3K understates this version's orchestration** by an unmeasured amount.

**Fix — key the directory by run, not by SHA.** In step 1:

> …to `$(git rev-parse --git-dir)/review-code/<head short sha>-<run id>/`, where the run id is fresh
> per invocation, so a concurrent review of the same head writes its own directory. Where the
> directory already exists, it belongs to another run: write a new one rather than reading it.

## Finding 10 — `defect` — step 4's ladder has no rung for a local spec that supersedes the ticket

Step 4 orders its sources: documents the human supplied · the PR's description and links · the Jira
issue and attachments · failing those, commit messages and any spec beside the changed code.

This run read four local design docs — 127,476 bytes, full text, no truncation — that fit none of
them. Not human-supplied, not PR-linked. The orchestrator filed them under the last rung, "a spec
sitting beside the changed code", **while treating them as more authoritative than that rung implies,
because one of them self-declares supersession over the dated Jira attachment.** It reported the
judgement as its own, not the skill's.

The last rung is a fallback — reached only when the rungs above found nothing — so a document that
outranks the ticket cannot be expressed on this ladder at all. And 127KB read in full is a real share
of the orchestrator's context.

**Fix — give the ladder the rung, and bound the read.** In step 4, after the ordered list:

> A spec beside the changed code that names the ticket and declares itself the newer authority is read
> at the rung it claims, above the document it supersedes, and the report's authorities line names
> both with the claim that ordered them. Read each source's sections that bear on the changed files in
> full, and the rest by heading.

## Counter-audit — what the cost fixes cost the review

Every finding above was reasoned from one PR. Held against a diff that PR does not resemble, four of
the changes narrow the review itself, and one of them is worse than anything the original audit found.

**The organising error: cheapness was taken from reviewing fewer files, when it should have come from
reading less per file.** Finding 8's hunks-first rule is the sound version — it cuts bytes and keeps
every file in scope. The marking rules that decide *which* files a pass opens are where coverage dies,
because a file the inventory routes past is a file no pass ever answers for.

## Finding 11 — `blocker` — `logic-removing` does not match the deletions that matter most

The mark, as v2.5.0 states it:

> `logic-removing` where a deleted line removes a branch, a call, a read, an assignment or an
> assertion

Every item on that list is a *statement*. The deletions that cause the worst silent regressions are
not statements:

| Deleted | Matches the rule? | What it does |
|---|---|---|
| `@PreAuthorize` / `@RolesAllowed` | **no** | every caller now reaches the handler |
| `@Transactional` | **no** | the write no longer rolls back |
| `@Valid` / a constraint annotation | **no** | unvalidated input reaches the sink |
| `implements Serializable`, a removed interface | **no** | contract at the edge, silently |
| a changed constant value, a removed config key | **no** | behaviour moves with no code change |

A file whose only deletion is `@PreAuthorize` is left **unmarked**. Unmarked means pass B answers it
from its hunks with one question and closes, *and* step 1 writes it no `@base`/`@head` text — so the
one file in the diff that most needs both SHAs read gets neither. **v2.5.0 made the authorisation
regression cheaper to miss than v2.3.0 did.**

This is the inversion in finding 8 overshooting. `mechanical` under-fired at 4 of 55, which was a cost
problem; `logic-removing` under-fires on the dangerous cases, which is a correctness one. The safe
default is to mark unless every deleted line is provably inert.

**Fix — define the mark by what is inert, and let finding 8's hunks-first rule carry the cost:**

> `logic-removing` unless every deleted line is inert — an import, a comment, whitespace, a formatting
> change, or an `@Override`. A deleted annotation, type or interface declaration, constant value or
> config key is never inert: it moves behaviour without moving a statement, and it is the deletion
> most likely to regress in silence.

That marks most files with deletions, as it should. **The cost stays down because B reads their hunks,
not their texts** — which is what §2 now tells it to do.

## Finding 12 — `defect` — reading the ask by heading narrows the pass that found both blockers

v2.4.0 added to step 4:

> Read each source's sections that bear on the changed files in full, and the rest by heading.

Pass C is the only pass that catches *scope creep* — step 5's "every behaviour the diff adds traces to
a requirement, or stands in the report as scope creep" — and *business meaning over green tests*, which
step 5 itself calls "the highest-value finding available." Both need the ask entire. A requirement in
a section that does not obviously bear on the changed files is exactly the one the diff silently fails,
and it never reaches the requirement list to be marked absent.

C found the blocker in run 1 and both defects in run 2. **It is the last pass to economise on**, and
this line saves perhaps 25K of a 954K run.

**Fix — delete the sentence.** Step 4's reading is the orchestrator's one irreplaceable job.

## Finding 13 — `defect` — shape groups collapse the security items too

`quality-bar.md` now says a shape group carries one §1 answer between its files, qualified only by:

> An item that turns on a file's own identity — a name, a value, a call unique to it — is still
> answered per file.

That leaves the decision to the pass's judgement, on the items where judgement is least safe. Two
files can be identical in hunk shape and opposite in blast radius: the same added null-check in a
logging transformer and in a payment transformer is one shape and two different §1.5, §1.6 and §1.7
answers. Items 5, 6 and 7 are also the three that returned clean on every file in both runs — the
floor whose whole value is that it is unconditional.

**Fix — name the exception rather than describing it:**

> Items 5, 6, 7 and 9 — authorisation, untrusted input, secrets, terminus — are answered per file
> regardless of shape: the same hunk in two files reaches two sinks. Items 1–4, 8 and 10–12 carry one
> answer per group.

## Finding 14 — `defect` — "dispatch nothing further" degrades to partial coverage with no escalation

Step 3, as v2.4.0 wrote it:

> Where the list outruns one context, it reports the files it could not reach and returns short rather
> than delegating them.

Run 2 shows this beginning already at 55 files: pass A returned reduced confidence on
`AmazonDefinitionsUtilityTest.java` (1,635 lines) and `AmazonMPServiceTest.java` (910), reviewed "by
structure and representative bodies." Nothing failed, and nothing in the bar treats a short return as
incomplete — **the review reports itself complete either way.** On a 200-file diff this fix converts an
expensive review into a cheap partial one silently, which is the same failure the original audit
charged the fan-out with, running the other direction.

The rule is still right — the fan-out cost 74% of run 1. What is missing is the escalation.

**Fix — give the short return somewhere to go, in step 3:**

> …it returns the files it reached and names the rest as `not reached`. The orchestrator dispatches a
> second agent of the same pass over exactly those files and merges the two returns as one pass — a
> split it chose and can count, not one the pass took on its own. A `not reached` file that no second
> agent covered stands in the report's coverage line and in the verdict.

And in the bar:

> - Every carried file was reached by its pass, or stands in the report as `not reached`.

## Finding 15 — `note` — pass C cannot tell that a requirement is missing from the list

Step 5 hands C the requirement list and lets it open the documents "where a line it must settle is not
settled by the list". That covers a requirement C knows to look for. It does not cover one the
orchestrator's enumeration dropped — C has no way to miss what it was never told exists, and step 5's
completion criterion checks the list against the diff, never the list against the ask.

Cheap to close, and it keeps finding 4's saving:

> Where the diff carries behaviour that traces to no requirement in the list, C reads the ask itself
> before filing it as scope creep — an enumeration that dropped a requirement and a diff that exceeded
> the ask look identical from the list alone.

## Run 3 — a different diff, on v2.4.0, and three retractions

20 carried files, uncommitted working tree, Opus. **628.6K / $18.36** — main 166.7K, sub 480,346
across A 159,591 · B 136,128 · C 184,627. Not comparable to run 2's 55 files.

**It ran v2.4.0.** The frontmatter says so and the plugin cache says 2.0.10. Nothing from findings
8–15 was in it. Everything below is therefore evidence about the *original* design, not about the
fixes — which remain unmeasured.

### Retraction 1 — §1 cannot be tiered, and the run-2 table nearly cost us that

Run 3's yield, by item: **8 of 12 items produced 18 findings.** Union across all three runs:

| Item | Run 1 | Run 2 | Run 3 |
|---|---|---|---|
| 1 resource lifecycle | | ✓ | ✓ |
| 2 failure paths | ✓ | ✓ | ✓ (2 blockers) |
| 3 concurrency | | | ✓ |
| 4 boundaries | | | ✓ |
| 5, 6, 7 authz · input · secrets | — | — | — clean, answered by name |
| 8 cost per call | | | ✓ (blocker) |
| 9 terminus | ✓ | | ✓ (blocker) |
| 10 tests | ✓ | | ✓ |
| 11 stack traps | | | ✓ co-cited (blocker) |
| 12 naming/shape | | ✓ | ✓ |

**Every item except the security floor has now fired, and the floor is kept precisely because it is
clean.** Items 3, 4, 8 and 11 — the four this audit named as "never fired" after two runs — produced a
blocker and three findings in run 3. §1's twelve items all earn their place; the open question is
closed, against the direction two runs pointed.

### Retraction 2 — pass B is not zero-yield

Run 3: **6 findings from 4 of 5 §2 duties**, including the defect below. Run 2's silence was a
property of that diff. This audit's "zero unique findings across two runs, for 349,945 tokens" was a
sample-size artefact stated as a trend. Finding 8 stands — B should read hunks before files — but the
framing around it does not.

### Retraction 3 — the shared-reading idea is wrong, measured

The proposal was to have the orchestrator read the standard once and inline it in all three briefs.
Measured: **A read eight sections of `docs/CODING-GUIDELINES.md`, B read one, C never opened it.**
Inlining the file into three briefs costs three whole copies against one-plus-a-section-plus-nothing.
Six files were read by more than one pass, mostly at non-overlapping regions. The duplication is real
and it is cheaper than the fix.

### What is left to cut

Main's 166.7K, estimated by the orchestrator at ±15%: **27K fixed overhead** (system prompt, tool
schemas, `CLAUDE.md`) that the skill does not control, **28K the ask** — which finding 12 forbids
cutting, and rightly: two of run 3's four blockers exist only because the ask was read — and ~15K the
three returns. There is no large compressible block.

**§3 is the tiering candidate, not §1.** Run 3 matched all 14 smells and produced **zero standalone
findings**, one co-citation. Across three runs §3 has yielded 8 notes, ~7 notes, and none — and the bar
caps it at `note` by construction. That is the one part of the checklist whose ceiling is known in
advance to be below the severity anyone acts on.

## Finding 16 — `blocker` — step 1 pins a path where the tree is dirty, and the review goes stale under itself

Step 1 opens "Resolve the target to an immutable SHA pair", and the Inputs offer "a ref the diff runs
since; absent one, the current branch against its merge-base". **Neither admits uncommitted work**, and
run 3 reviewed exactly that. The tree then moved while the review ran:

| File | At pin | 87 minutes later |
|---|---|---|
| `AmazonMPService.java` | +134/−2 | +298/−3 |
| `AmazonMPServiceTest.java` | +220/−9 | +458/−9 |
| `AmazonMetadataSyncExecutor.java` | +54/−0 | **+139/−4** |

Three fixtures that did not exist at the pin now exist, mapping one-to-one onto three of the findings —
the author was fixing the review as it ran, which is the system working. The damage is that **every
line citation in the report is stale for seven files**, the artefacts describe a tree that is gone, and
`AmazonMetadataSyncExecutor.java` gained four deletions after pass B finished: **it was never answered
against §2 by anybody**, and nothing in the report says so.

**Fix — pin an object, not a path.** `git stash create` writes the working tree as a real commit
without touching it, and that SHA is immutable in the way step 1 already assumes. Applied in v2.7.0.

## Finding 17 — `defect` — the merge can drop a finding and still pass its completion criterion

Step 6's criterion: "every finding carries a severity and a named boundary, and each place appears
exactly once." **A finding that vanished satisfies all three.** Nothing counts the returns in against
the report out.

Run 3 lost one: pass B's §2 provenance defect — the mandatory `recommended_browse_nodes` column now
emitted blank for every product stored before the change, one rejected listing per SKU — was summarised
into the notes and never filed. The orchestrator caught it only while answering a forensics question,
and corrected the verdict to 4 blockers · 10 defects · 17 notes.

**Fix — number every return's findings and account for each: filed, or merged into a named finding at
no lower severity.** Applied in v2.7.0.

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
