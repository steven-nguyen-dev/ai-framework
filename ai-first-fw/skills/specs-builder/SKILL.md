---
name: specs-builder
description: Fills an integration's spec folder from the area's own harness and writes the mapping-plan.md that grades every field mapping. Use at the planner's hand-off, when an integration needs specs built, or when an existing spec folder needs updating.
version: 0.7.1
disable-model-invocation: false
---

# Specs builder

Two deliverables. A **spec folder** a generator can build from, and a **`mapping-plan.md`** saying
where every field came from and how sure you are.

**The template carries the writing.** `templates/mapping-plan.md` holds its own fill order, its
writing rules, its column legend, the grade, the order's passport and its hand-over list, in
comments it keeps until stage 6 strips them. Copy it, fill the copy under its own comments, and do
not look for those rules here — **this file does not repeat them.**

**The area owns the spec format.** Its `specs/README.md`, `FIELD-REFERENCE.md` and
`master-template.yml` *are* the format — read them at runtime and follow them. Never guess a
convention, and never carry one over from another area. There is no template of ours for the spec
folder and there cannot be one, so for *that* artifact this file carries what no harness supplies:
the output contract, and the line between a spec and a plan.

Where this file names a section of another document, it names the job, not a verbatim heading.

---

## Entry

**Input:** a feature folder, `<repo-root>/.scratchpads/<feature-slug>/`. You usually run at the
planner's hand-off — after the codebase read, **before** the plan is written.

1. **Read `raw-context.md` §0 and state the rung aloud** before anything else. §0 is where the work
   is, and this run writes it back on the way out. A run that never read it can stamp
   `specs generated` over a rung the work was moved *back* to.
2. **Confirm hand-off.** The planner sent you here because the module supports specs. Proceed.
3. **Read `raw-context.md` §2** for partner docs, captured payloads and mapping documents already
   supplied, before asking for any of them.
4. **Open the copy.** Copy `templates/mapping-plan.md` to `mapping-plan.md` in the planning folder
   and edit that copy from here on; the bundled template stays unedited. The copy is opened now,
   not at Fill, so that every read has somewhere to land the moment it comes back, and so that the
   template's own passport and column legend are in front of you during the interview, which is
   where they are needed. What that buys is the template's to explain.

**Stop and report** if `raw-context.md` or its §0 is absent. A folder without §0 is a folder in an
unknown state, and writing `specs generated` into it invents one.

Running with no feature folder is supported — this skill runs against a repo either way, and the
planning folder exists to write `mapping-plan.md` into. Ask the human directly for the intake
materials, skip the §0 reads, and skip the §0 writes at hand-off. Step 4 still happens.

**Sections this run touches, and no others:** §0 (read at entry, written at hand-off), §2 (**read
only** — never mint an `SRC-xx`), §6 (a row at each checkpoint and at hand-off), §7 (`GAP-xx`
for blockers that survive validation).

This skill is `mapping-plan.md`'s only author. The planner never writes one inline.

---

## The run

Seven stages, each a goal with a bar. Reach the bar however the work in front of you demands.

`mapping-plan.md` is the authority the specs are filled from. **How to fill it is the template's
business, in the template's own comments** — the fill order included. What follows is the run.

### 1 · Intake — you hold every source that exists

The materials: partner API documentation, the mapping document, captured request/response payloads,
a sibling integration's filled spec, and the integration's source code where the partner already
runs. §2 names what arrived. Ask for the rest **in one round**, list what you already received
alongside, and ask whether that is everything.

Find the registration doc, take the integration's registration code, and list every place the code
must match.

### 2 · Explore — the area is pinned and its harness is read

Every area's spec framework has the same skeleton. **The skeleton is fixed; the vocabulary is not.**

```
<area>/specs/README.md              fill order, sample placement, precedence, escalation
<area>/specs/_templates/
  FIELD-REFERENCE.md                every field per kind, + the expression catalog
  master-template.yml               the full field superset
  _<area>.spec.yaml                 the global spec (glob `_templates/_*.spec.yaml`)
  feature.<KIND>.spec.yaml          one annotated form per kind
  ordered/NN-*.spec.yaml            pre-numbered stubs, `contract:` pre-filled
```

Copy `_templates/` → `specs/<code>/`; fill the global spec first, then `ordered/` in number order.
Samples go in one shared folder at the integration root, with `sample:` paths resolved from there.

Read at runtime, never assumed: the kinds, the field set, the `contract:` keys, the marker
conventions, and whether the area ships filled `EXAMPLE.*.spec.yaml` references at all — some ship
none. Kinds differ per area, and kind↔form is not one-to-one.

The area usually arrives with the work. Standalone, find it — `ls -d */specs/_templates/`. One match
is the area; several means near-duplicate area names, so list them and ask. Once pinned, name every
harness document by its repo-relative path on first mention in each message: two areas in scope
means two READMEs.

Read the area's README and its `CLAUDE.md`, and identify each instruction by its functional role
rather than by the heading it sits under.

**The bar for how much detail a filled spec carries is the area's own filled example.** Read it, read
the `feature.<KIND>` form for any kind it does not cover, and state which kinds the harness
exemplifies and which it does not.

Filled spec folders already in the area are optional context, and only the ones on your checkout —
`ls -d */specs/*/ordered | grep -v _templates`. **Never reach into another branch for one:** nothing
on disk distinguishes a decade of convention from a defect nobody corrected. The area's README ranks
spec files below the coding standard, the platform docs and its own reference docs, so another
integration's filled folder is the weakest evidence you have. Context, never authority.

#### When the harness does not fit what is in front of you

Three cases. More than one can be true at once.

**A spec folder exists and something changed.** Change what changed. Ask what moved, grep the folder
for the affected field or endpoint, and re-verify the samples for those features only. Leave the rest
alone — unrelated fixes hide the real change in the diff. The trap is the sample nobody re-captured:
a spec that was right last quarter still parses, still resolves, still passes every structural check,
and generates against a payload the partner no longer sends.

**The integration runs in code and has never had a spec.** Most of the global spec's identity is
already written down in the integration module. Read it out rather than interviewing for it — the
service annotation, the per-profile config, the rate-limit annotations, the request-manager methods
and their DTOs, the status mapper.

Scope the search to the **integration module**, not the reactor containing it: a reactor holds every
partner it serves. Point your file-search tool at that one module path and look for the per-profile
config files (`resources/config/integration-config*`) and the annotations declaring the service and
its rate limits (`IntegrationService`, `RateLimiter`). Cite what you find as a bare FQCN with a line
number, so the human can check you in one click. Where a module keeps these somewhere unexpected,
that is information about how it was built — say so rather than smoothing it over.

*Build output is not a source.* A build leaves copies of the same config filenames under
`target/classes/`, and a stale copy can answer a question about current behaviour with no symptom.
Your file-search tool honours `.gitignore`, which is what keeps `target/` out; a raw `grep -r` does
not.

*Read what is on disk, not what is committed.* `git ls-files` and `git grep` see the index and
tracked files, so an unstaged source file is invisible to them — the search comes back clean and the
answer is wrong with nothing to notice. A build directory that slips into results is visible and you
correct it; a missing file is not.

*The trap: code has DTOs, not wire.* A DTO is what the last developer decided to keep. Rebuilding a
sample from one drops the unmapped fields, the enum values the partner sends, the difference between
null and absent, and every formatting quirk. The result is present, parses, resolves — and is not
what came off the wire. Nothing downstream fails; the generator builds against the wrong shape. The
repo's own guidance runs the other way, warning that a *missing* sample produces wrong DTOs, so
nothing there catches a fabricated one. Only provenance will. Three questions close the gap: can you
get me a real capture? Which API version is current, and is this integration still on it? Is the
existing behaviour correct, or are we specifying a bug?

**An operation has no stub.** First check it does not fold into an existing feature — most do, and a
new file is the expensive answer. Check the master template too: a field can be applicable and
documented without any stub exposing it, which is a different problem with a much cheaper fix.

Where the operation genuinely has no home:

1. **Number it so it sorts where it belongs.** Practice varies — a variant of an existing stub
   sometimes takes that stub's number with a suffix, a genuinely new operation sometimes takes the
   next free one. Look at how the area's `ordered/` and any filled spec already do it, then say which
   you chose.
2. **Fill the `contract:`** naming the operation enum, param class and publisher method —
   **including ones that do not exist yet**, each marked so the reader sees a request rather than a
   reference: `# NEW — not yet in <Symbol>`.
3. **Collect every platform addition in the hand-off report's Platform gaps list**, one line per
   symbol, named as core work landing before generation — and as `GAP-xx` rows where a feature folder
   exists. The spec itself carries only the `# NEW —` markers.

Naming a symbol that does not exist yet is a specification, not an invention — it is how new
operations get into core. What causes trouble is referencing one *silently*, or picking a name that
merely looks plausible beside the ones nearby.

The `# NEW —` marker is a practice, not a repo convention — no template documents it. Say you are
using it, so the human can tell you to do it differently.

Scheduled jobs and other non-dispatched features extend the same way, by copying — but check the
field reference first. Some feature kinds are integration-defined beans rather than dispatched
interface methods, and those introduce no operation enum and no publisher, so steps 2 and 3 mostly do
not apply. A `feature:` line naming a bare class, rather than `IFace.method`, is the tell.

### 3 · Interview — the frontier is empty

**Every open question hangs off a decision already settled.** A field's mapping row hangs off the
feature being in scope; a feature's scope hangs off the area's kinds; an enum's value set hangs off
the field carrying it. The **frontier** is every open question whose prerequisites are settled.

Ask every frontier question in one message, numbered, each with your recommended answer. Then stop
and wait — answer nothing yourself. A question depending on another still open this round waits for
the next round; that is the only limit on a round's size. A skipped question stays on the frontier
and is re-asked: silence never accepts a recommendation.

**Two tests before any question reaches the human. Both, in writing, on the gap's line.**

1. **Grounded** — name the document section or the `file:line` that failed to answer it. A question
   with no failed search is a search you have not run.
2. **Material** — name what changes in the specs or the mapping plan depending on the answer. If you
   cannot name it, do not ask: assume, and state the assumption.

**Assume and state.** A question that fails the materiality test takes a third exit. Record it in the
log as a line opening `assumed —`, carrying the assumption, the default it rests on, and what would
overturn it, and surface every one under **Assumed, correct me** in the read-back. An item is
assumable only where the answer changes nothing you can name — anything that moves a mapping row, a
value set or a spec file is a question, not an assumption.

**Drive the payload rounds from the open copy.** The copy's coverage comment carries the order's
passport — the data that has to survive the round trip across sale channel, OMS, WMS and carrier —
and its §2 comment carries what closes a value set and what each column has to answer. Those are the
questions worth a round. Read them there; they are not repeated here.

**The format.**

| Marker | Use |
|---|---|
| 🧭 | Round header |
| ❓ | A question |
| 💡 | Your recommended answer |
| ⏳ | A question held back by a running lookup |
| 🔍 | Where you searched, and what it failed to answer |
| ✅ | A settled decision in the read-back |

```
🧭 **Round 2** — 3 questions · ⏳ 1 held for a lookup

❓ **Q1 — <question title>**
<the question, the options, and what hangs on the answer>

🔍 **Searched:** <the document section or file:line that failed to answer it>
💡 **Recommend:** <your answer, and the reason in one line>
```

Markers belong in the chat round. The spec files stay plain text.

*The round — the frontier, the one-message rule, this marker table — is duplicated by design with
`implementation-planner`: installs symlink each skill directory whole, so a shared file would not
ship. The two copies are edited in the same change; only the ✅ row differs, naming what each skill
reads back.*

**Finding facts is your job.** A question the area's README, the partner's docs, the payloads or the
codebase already answers is a lookup, and a lookup is delegated. A running lookup holds back only the
questions beneath it; ask the rest of the frontier now.

**Delegate the reading.** Reading the codebase, reading multiple files for context, and researching
multiple online sources each go to a sub-agent. A sub-agent returns verdicts, facts and
`file · Class.method` — never file bodies, never its search narrative, and never a chosen answer.
Material you quote or fill from — the area's harness forms, the template, the coding standard — you
read yourself. Online research covers public material only; the partner's contract is supplied by the
human, never researched.

**Two answers the human owns outright.** A decision — what to trim, which precedent to follow, which
reading of a conflict wins — is theirs, and no lookup substitutes. A fact only they hold, living in a
partner email or a call, is evidence: quote it exactly, and let the copy's grade rule say what it is
worth.

The frontier is empty when every branch has been visited and nothing is silently assumed. List the
settled decisions back in one message and ask the human to confirm. **Their confirmation authorises
4 · Fill.**

### 4 · Fill — every feature routed, every authored line a directive

Follow the area's instructions: its README for fill order and sample placement, `FIELD-REFERENCE.md`
for what each field means per kind, `master-template.yml` for the superset.

- **Trim by role.** A feature the partner does not support is trimmed by **disabling** it
  (`enabled: false`) or deleting the stub. Prefer disabling — it keeps the pre-filled `contract:`
  block that deletion discards. Report every trim and which way it went.
- **Route scope** sentences to numbered features.
- **Absence is a statement.** "Supplied later" or "empty for now" builds the feature empty — form,
  seed, explicit empty collection — rather than skipping it.
- **Check the master template**, not just the stub, for fields that are applicable and absent.
- **Cross-check** master template, stubs and global spec. A divergence the files' own roles or
  comments explain is not a defect: `ordered/` stubs ship disabled scaffolding while a
  `feature.KIND` form shows an enabled feature. Report only what no role or comment accounts for,
  and only structurally — a key the stubs use that the master lacks, a kind with no form, a pointer
  that does not resolve.

#### Reading a blank — or a pre-filled — field

A blank slot is not one thing. It can mean *take the default*, *you decide*, *nobody knows yet*, or
*this field doesn't belong to this kind* — and the wrong reading is silent. A pre-filled slot is the
same problem inverted: a contract the generator relies on, or a demonstration of what most partners
do.

**Marker semantics are documented per area, and they differ.** The skeleton is fixed, so the places
to look are always the same; what you find there is not. Search before interpreting anything:

```bash
T=<area>/specs/_templates
grep -rn 'esolution rule' $T/
grep -rniE 'USER INPUT|recommended:|required when|TODO|verify' $T/ | head -30
```

Read what those turn up in the area's field reference, and use its rule. **An area that defines none
of it is telling you a blank there carries no marker semantics** — that is an answer, not a gap in
your search. This is a real split: some areas define a full resolution rule (blank falls back to a
recommendation block, a literal `none` is an explicit opt-out, any other value wins) and some define
none at all, and two areas that both define one may still differ clause for clause. Read the rule
where that area states it, every time.

What the field reference will not tell you:

- **A field scoped to another kind is omitted, not blanked.** The `Kind` column says which fields
  belong; it does not say that a blank is itself an answer, so blanking an inapplicable field states
  something you did not mean.
- **A doc-pointed placeholder is not a gap.** A value shaped like `"<by authType — some-doc-name>"`
  is an instruction to resolve from that doc at generation time — leave it in place. Where a shipped
  example resolves one by hand, the field reference wins and the example is one data point; say which
  you followed.
- **A dangling key parses as null**, identical to a considered choice. Where the area states no
  resolution rule, write `{}` or `[]` out. Where it states one, that rule wins — and an explicit
  empty collection may then mean the opposite of "empty".
- **A `""` in a filled spec can be a positive instruction** rather than a gap. Read the comment
  beside it first.
- **An empty call list can be the answer.** Where credentials are minted locally, or the partner
  documents no auth endpoint, an auth feature legitimately makes no call — write the empty collection
  out and say why. A stub shipping a worked call is showing the common case; the partner's contract
  decides whether it applies.
- **A feature whose data comes from a seed file is still a feature.** Build the form, the seed file,
  and an explicit empty collection where the data will go. An empty set is a statement about the
  data, not a reason to skip the feature.
- **A block-level "do not edit" can have field-level exceptions.** Where an area's field reference
  defines user-input slots inside a pre-filled block, the README's blanket prohibition does not reach
  them. Where it defines no such convention, the block is frozen — check which case you are in.
- **Content type can be set globally and overridden per call**, so the global setting does not tell
  you any particular request's payload format. Outbound transport, where an area has one, is set
  once. Find where this area decides each before assuming JSON; for XML, the mapping's nesting *is*
  the payload structure.

*This subsection is duplicated by design in `specs-builder` and `specs-reviewer` — installs symlink
the whole skill directory, so a shared file outside it does not ship. The two copies are edited in
the same change.*

#### The output contract

Every line you author is a **directive**: a value, a wire fact, an instruction the generator acts on.
Everything else is **narrative** — reasoning, status, provenance, an open question — and narrative
lives in `mapping-plan.md`, never in a spec.

The second test is **the cloner**: someone who cloned this codebase and has never seen the planning
folder. `mapping-plan.md`, `raw-context.md` and every ID either of them mints are absent from their
hands. A spec line carries **the fact**, never where the fact was decided — no artifact ID, no
document name, no section number, no "see". Pointers run plan → spec, never back.

**The cloner only removes lines.** A line that is already narrative stays out even when its reference
resolves cleanly: `samples/PROVENANCE.md` resolves perfectly and is still provenance.

An authored line is one of three forms, and both tests apply to all three — a field value carries a
justification clause as easily as a comment does.

1. **A template field with its value** — the resolved value, nothing trailing it.
2. **A comment: one line, stating the fact itself** — a type hint, a wire fact, or a cross-reference
   to another spec in this folder.
3. **A `notes:` entry, in the shape and register the area's own harness sets** — its `EXAMPLE.*`
   where it ships one, otherwise the `notes:` description in its `master-template.yml`. **Blank is
   the common case.** Never import a shape from another area, and never let your `notes` run longer
   or denser than the longest block that harness itself ships.

| Form | Write | Not this |
|---|---|---|
| 1 | `perCall: unbounded` | `perCall: "unbounded — this endpoint documents no per-call cap"` |
| 2 | `# 'N' means the marketplace reports 999,999,999` | `# sentinel value — see ADR-01 for the reasoning` |
| 2 | `# NEW — not yet in <Symbol>` | `# NEW — tracked as GAP-04` |
| 3 | *(blank — the fact is the field above)* | `notes: spdNo comes from the DTO's parent-sku field` |

A fact needing a clause of justification to stand up is a `mapping-plan.md` row; the spec line is the
fact alone, or there is no line. A `notes` line whose every identifier already appears as a field in
the same file is a restatement — delete it rather than reword it.

**The placement map** — every kind of information has exactly one home:

| Information | Home |
|---|---|
| Wire directives and wire facts | spec fields, comments, `notes` |
| Implementation status | the `mapping-plan.md` file tree (§1) |
| Reasoning, consequences, trade-offs | the `mapping-plan.md` mapping row (§2) |
| A harness claim that does not hold here | the `mapping-plan.md` row (§2) and the hand-off report |
| Sample provenance | per sample file, where the area puts it — samples are shared across features |
| Open questions | the gap ledger (`raw-context.md` §7) — search it first; most are already a `GAP-xx` |
| Platform gaps (new symbols for core) | the hand-off report, plus `GAP-xx` rows |

#### Harness-authored text is frozen

Stub headers, pre-filled values, and the `notes` a stub shipped are copied byte-identical. They are
not yours to audit, trim, normalise or rewrite. Where such text flags something integration-specific
— an area's README may name `recommended:` blocks and `notes` as exactly that channel — **confirm it
against the partner** and record the answer where the area puts answers. Stripping it removes the
signal you were told to act on.

**A frozen line that does not hold for this integration is still frozen, and it is answered nowhere
in the spec** — not by editing it, not in a comment beneath it, not in `notes`. A stub header states
the fill order the stub sits in, not a claim about *your* feature. A rebuttal placed next to a frozen
line is the most common way narrative enters a spec folder, because the line reads as a question the
spec owes an answer to. It is not. The divergence is a `mapping-plan.md` row and a hand-off line.

Where a stub shipped a `notes` block it stays as that block's opening lines, byte-identical, and
anything you add goes **below** it. Where the two together run long, what *you* added comes out.

#### Checkpoints

Two turn-ending stops. At each one, in this order: **log a row in `raw-context.md` §6, show your
work, then wait** for the human to wave you on.

| Checkpoint | Reached when | What the §6 row and the message carry |
|---|---|---|
| `checkpoint · scoping` | scope is routed to numbered features | features in scope, every trim and which way it went, precedents chosen |
| `checkpoint · global spec + auth` | the global spec and the auth feature are filled | what was filled, what is still open |

The §6 row goes first because it is what an interrupted Fill resumes from — a checkpoint shown but
not logged leaves nothing behind. On re-entry, extend the record; never duplicate it. Where a round
empties the last prerequisite of a checkpoint, log and show in that same stop rather than stopping
twice for one frontier.

### 5 · Self-check — both deliverables are checked before either is finished

**The copy first.** Every comment in `mapping-plan.md` ends in a `Check:` line, except `HOW TO FILL`,
which ends in the hand-over list. Together those lines are the checklist, and they are countable:
work the copy top to bottom and quote the line of the copy that satisfies each one. Do not write the
number of checks down anywhere — a run that deletes a section deletes its comment, so any fixed count
is wrong on the ordinary run.

**Then the spec folder**, which has no comments of its own to check against. Satisfy each of these:

- **Every sample says where it came from**, one line per sample file. A sample rebuilt from a DTO
  passes every structural check and is still not what came off the wire; "unknown origin" is an open
  question, not a pass.
- **Every folder the area's instructions require exists**, and **every file parses and every
  `sample:` pointer resolves** — established by parsing, not by reading. A duplicate key survives a
  careful read. An unresolvable pointer means the payload does not exist.
- **Every stub's `notes` line is still present** in the filled file. A dropped line is gone from the
  delivery *and* from the planning folder, so nothing downstream can recover it.
- **Every authored line is a directive that survives the cloner**, and is one of the three forms.
  Walk them; the forms are not self-enforcing.
- **Derived values line up**: kinds match the area's forms, buckets match the global spec, the
  integration code matches the registration doc.
- **Identifier and silent-failure fields sit on the right side of the wire** — who assigns each one,
  and whether the spec places it in a request input or a response payload.

Blockers surviving this pass are genuine gaps, and become `GAP-xx` rows needing a human disposition.

**The copy is still unstripped when this stage ends.** Stage 6 is what ends that.

### 6 · Strip — the copy holds no comments

Delete every block opening at `<!--` through the first `-->` after it, the ones you just checked
against included. Nearest-match is the whole rule: every comment in the template closes before the
next live `-->`.

This is a separate stage because it cannot be undone and stage 5 is the run's heaviest work. Merging
them puts an irreversible act in view while the demanding work is still going, which is what invites
the rush to be done. Strip only after stage 5 has passed, never during it.

**Completion:** `mapping-plan.md` holds no `<!--`, its headings and tables still render, and no live
row left with a comment.

### 7 · Hand off — the folder survives a cold read

Report in chat: features ready · trims and which way each went · open questions and owners · platform
gaps · contradictions for the PR description. Do not write to status files.

**When sources disagree**, apply the area's declared precedence first — both known areas declare one
in their README, the coding standard first and the spec files last, with escalation: a spec
conflicting with a platform contract doc is a **stop and flag**, not a guess. A shipped example that
loses to a platform doc is neither an edit nor a harness defect. Only a conflict the precedence does
not settle goes to the human — name both, quote them, offer a reading, and let them choose.

**With a feature folder**, also:

- Set §0 `State` to `specs generated` with today's date, and log a §6 row.
- **Print the invocation** — `specs-reviewer <spec folder path> <feature folder path>` — **set §0
  `Next action` to it, and end the turn.** The cold spec review is mandatory. Write the move *after*
  the review into the same cell: `implementation-planner <feature folder path>` on a clean verdict.
  `specs-reviewer` preserves §0 exactly as it finds it and will not repoint `Next action`, so a cell
  holding only the review points backwards from the moment it starts.
- **Say what follows the review, in the same message.** Blockers in `specs-review-report.md` come
  back **here** — this skill authored the specs, so it repairs them and prints the re-review
  invocation, at most 2 cycles, after which surviving findings go to the human at G2 as gap
  dispositions. A clean verdict moves on to `implementation-planner <feature folder path>`, which
  resumes at Step 3 and reads the verdict line at C6b.

The human runs the review in a fresh session, before the plan is written: the plan is written against
these specs, so a spec the review sends back is a plan not yet worth writing.

---

## Done when

Each stage heading states its own bar. Three more hold across all of them:

1. **`mapping-plan.md`** — every line of its hand-over list is quoted against, every `Check:` line in
   it is satisfied, and the file ships stripped. The list is the template's, and this file does not
   restate it.
2. **The spec folder** — every authored line is a directive that survives the cloner, every
   harness-authored line is byte-identical, and every bar in 5 · Self-check is satisfied.
3. **The exit** — with a feature folder, §0 `State` reads `specs generated`, §0 `Next action` holds
   the `specs-reviewer` invocation followed by the `implementation-planner` one, and the turn ended
   there. Nothing was asked of the human that a sub-agent could have found.
