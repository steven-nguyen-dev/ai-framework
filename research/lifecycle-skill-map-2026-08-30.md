# Lifecycle Skill Map

**Which skill to use at each stage of `ai-framework`'s development lifecycle**

30 August 2026. Stages: **Analysis + Research → Design → Implement → Local Test.**

---

## How to read the confidence grades

Your scale, applied strictly:

| Grade | Means |
|---|---|
| **A** | Backed by a benchmark or evaluation, or independently used and verified by multiple parties |
| **B** | Logic plus a few sources — the principle is measured, but not this specific skill |
| **C** | Logic only, from reading the skill file. No measurement of any kind |

**Read this before the table: most of what follows is C.** That is not a failure of the
research. It is the state of the field. Four things reach A, and two of those four are
*negative* findings — evidence that a popular thing does not work.

I grade the **specific skill**, not the idea behind it. "TDD is good" being well-evidenced
does not make superpowers' `test-driven-development` skill grade A. What was measured was
handing an agent human-written tests, which is a different intervention.

---

## The map at a glance

| Stage | Your skill today | Add | Grade | Why |
|---|---|---|---|---|
| **1. Analysis + Research** | `analysis-handoff` (6.7kB) | `brainstorming` (superpowers) — request classifier + hard gate | **C** | Nothing at this stage is measured |
| | | `grilling` (mattpocock) — *already installed* | **C** | |
| **2. Design** | `specs-builder` (30.7kB), `implementation-planner` (34kB), `plan-reviewer`, `specs-reviewer` | **7-rung ladder** (ponytail) | **A** | −10.3% cost, p=0.004, 80 paired tasks |
| | | Interfaces block (superpowers `writing-plans`) | **C** | |
| | | Converge loop (spec-kit) | **B** | |
| **3. Implement** | Governed by `lv1-coder` + CONTEXT.md rules | Human-authored test scaffold *before* code | **A** | TDFlow, EACL 2026 |
| | | Execution-feedback loop | **A** | Self-Debug, ICLR 2024 |
| | | `using-git-worktrees` (superpowers) | **B** | |
| | | **Do not** add parallel subagent fan-out | **A** *(negative)* | 5 of 6 systems lost to one agent |
| **4. Local Test** | Deterministic Ladder, Delta-Only Verification, Circuit Breaker, Tri-Axis Review, `code-reviewer` | Human gate before agent-drafted tests are trusted | **A** | IBM: 21.8% → 25.5% overfitting |
| | | `verification-before-completion` (superpowers) | **C** | |
| | | `receiving-code-review` (superpowers) | **C** | **Your biggest gap** |
| | | `systematic-debugging` (superpowers) | **C** | |

---

## Stage 1 — Analysis + Research

**What this stage must produce:** a correct understanding of the ask, and the facts the
design will rest on. Failure here is expensive because everything downstream inherits it.

**Your coverage today:** `analysis-handoff` (6,739 bytes) — the smallest of your six.

### Candidate: `brainstorming` — superpowers, 15.5kB — **C**

**What it does.** Classifies your request out loud as **spike / bounded / architectural**,
then runs the matching script. Architectural means: explore context, interview one question
per message, present 2–3 alternatives with a recommendation, get the design approved section
by section, write it to a dated spec file, self-review for placeholders and contradictions.
A `<HARD-GATE>` forbids writing code until you say yes. When in doubt between paths, it takes
the heavier one; complexity discovered mid-task upgrades the path but never downgrades.

**Pros.** The classifier is the valuable part — it is the only skill here that decides *how
much process this task deserves* before spending any. One question per message is a real
discipline; agents default to dumping six questions and getting three answered. It has an
explicit anti-pattern section for the "this is too simple to need a design" rationalisation.

**Cons.** 15.5kB, the second-largest thing you would add. Its own eval suite records it
firing on a trivial checkbox task — an open product decision unresolved since May 2026. So
the classifier that is supposed to right-size the process gets the sizing wrong, by the
vendor's own measurement.

**Grade C.** I read the file. Superpowers' 85-scenario harness measures whether skills
*trigger*, never whether they improve outcomes. No independent test exists.

**Verdict:** steal the three-way classifier and the hard gate into `analysis-handoff`. Do not
install the skill. You would be paying 15.5kB for two ideas.

### Candidate: `grilling` — mattpocock, 315 words — **C** — *already installed*

**What it does.** Interrogates a plan. Builds a design tree, works the "frontier," asks in
rounds using a `❓`/`➡️` format.

**Pros.** Tiny. Already in your session — you can run it today at zero cost. No
language-specific content, so no TypeScript problem.

**Cons.** No evidence of any kind. Its one quantitative claim — thirteen questions typically
land in about three rounds — is unsourced with no method. The author's own docs report that
`grill-with-docs` naming `grilling` does not reliably load it.

**Grade C.**

**Verdict:** you have it. Use it on your next real spec and judge for yourself. That is a
free experiment.

### Also available and already installed

`mattpocock-skills:research` (investigate against primary sources, capture as a repo .md),
`lv1-advisor` (stress-test a fork with a human on the loop), `lv1-fact-checker`. All **C**.
All free to try.

### Honest note on this stage

**Nothing in the survey reaches B or A for analysis and research.** No benchmark covers
requirements elicitation. SkillsBench's software-engineering tasks are single markdown files
with no existing codebase, so they do not test this at all. If you adopt something here, you
are adopting it on taste.

---

## Stage 2 — Design

**What this stage must produce:** a spec that says what to build and why, and a plan that
says how, with enough precision that an implementer with no context cannot drift.

**Your coverage:** `specs-builder` (30,680 bytes), `implementation-planner` (33,977),
reviewed by `plan-reviewer` and `specs-reviewer`. This is your heaviest stage by far — 65kB
across the two authoring skills.

### Candidate: the 7-rung ladder — ponytail, 6.6kB — **A**

**What it does.** Before writing code, walk down and stop at the first rung that holds:

> 1. Does this need to exist at all? (YAGNI)
> 2. Already in this codebase? → reuse it
> 3. Stdlib does it? → use it
> 4. Native platform feature covers it? → `<input type="date">` over a picker lib, CSS over JS, DB constraint over app code
> 5. Already-installed dependency solves it? → use it. Never add a new one for what a few lines can do
> 6. Can it be one line? → one line
> 7. Only then: the minimum code that works

**Pros.** The only design-stage intervention in this entire survey with an independent
measurement: JetBrains, 80 paired tasks, **−10.3% cost at p=0.004**, no detected quality
difference. It also has real guardrails — it never simplifies away input validation at trust
boundaries, error handling that prevents data loss, security, or accessibility, and
non-trivial logic must leave one runnable check behind. And its maintainer publicly corrected
his own inflated numbers when a critic showed the baseline was wrong.

**Cons.** The advertised −54% code reduction measured **−15.4%**, and that figure did not
reach significance (p=0.088). Its own README concedes the effect is "near zero on code that
is already minimal." Installed as a bare skill it self-activated **zero times across ten
sessions** — it needs the plugin's hooks. And it is a persistent mode, so it will shape every
response until switched off.

**Grade A.** Vendor benchmark with published method, plus an independent test by a third
party, plus a public adversarial critique that changed the published claims.

**Verdict: take it.** This is the strongest recommendation in the whole report. Your
`implementation-planner` plans *how* to build; nothing in your six stages asks *whether*.
Put the ladder at the top of that skill.

### Candidate: the Interfaces block — superpowers `writing-plans`, 7kB — **C**

**What it does.** Every task in a plan carries exact **Files** (create/modify with line
ranges) and an **Interfaces** block listing Consumes/Produces with exact signatures —
specifically because each implementer subagent only sees its own task. It bans "TBD", "add
appropriate error handling", "similar to Task N", and references to undefined types, then
self-reviews for cross-task name drift.

**Pros.** It solves a failure you will hit if you keep dispatching sub-agents: `clearLayers()`
in task 3 versus `clearFullLayers()` in task 7. The skill names that exact bug. Your
`implementation-planner` produces `plan.md` with seam mapping; an explicit Consumes/Produces
contract per task is a sharper version of the same idea.

**Cons.** No measurement. And it is designed for a fan-out execution model that the evidence
argues against (see stage 3), so you would be adopting a solution to a problem you should
consider not creating.

**Grade C.**

**Verdict:** steal the Consumes/Produces block and the no-placeholders list into
`implementation-planner`. Skip the rest of the skill.

### Candidate: the converge loop — spec-kit `/speckit.converge` — **B**

**What it does.** Assesses the codebase against the spec, plan and tasks, then **appends
remaining unbuilt work back into `tasks.md`**. You loop implement↔converge until it reports
"Converged".

**Pros.** This closes the gap between "the plan said" and "the code does." Your
`specs-reviewer` reviews the spec against intent; nothing re-derives remaining work *from the
code*. That is a genuine hole in your lifecycle. GitHub ships it, 113,709 PyPI downloads last
month, and it is the one tool in this survey that labels its own thesis a hypothesis rather
than a finding.

**Cons.** No benchmark. Spec-kit as a whole is ~130kB and would collide with your
`specs-builder`.

**Grade B** — the mechanism is simple enough to reason about, and it is in wide use by a
credible publisher, but nobody has measured it.

**Verdict:** add it as a *mode* of `specs-reviewer`. Do not install spec-kit.

### Candidate: `arena` — pstack — **C, with a caution**

Spawns N candidates at the same task on different models, cross-judges with a read-only judge
on a different model family, then grafts the strongest parts of the losers into a base.

**Pros.** Well-designed: the rubric is fixed before candidates run, candidates see only the
task while the judge sees the rubric, and every candidate writes to its own worktree.

**Cons.** It is exactly the fan-out shape the stage-3 evidence argues against, at N× the cost.

**Grade C**, and I would not take it.

### Already installed and relevant

`mattpocock-skills:domain-modeling`, `mattpocock-skills:codebase-design`,
`engineering:architecture` (ADRs), `engineering:system-design`. All **C**. All free.

---

## Stage 3 — Implement

**What this stage must produce:** working code that matches the plan, without scope drift.

**Your coverage:** CONTEXT.md rules plus `lv1-coder`. You have no dedicated implementation
skill, which is defensible — the plan carries the detail.

### The one A-grade intervention: correct tests, authored before code — **A**

**The evidence.** TDFlow (EACL 2026, peer-reviewed) reached **88.8%** on SWE-Bench Lite and
**94.3%** on Verified — **when handed human-written tests**. The paper's own conclusion is
that generating valid reproduction tests is the unsolved bottleneck. Separately, Self-Debug
(ICLR 2024) measured **+2–3%** improvement without unit tests versus **up to +12%** with them,
in the same system: the execution signal does the work, not the reflection.

**What this means for you, precisely.** Your Executable Test Scaffold is agent-drafted and
human-approved. TDFlow's result came from tests a human *wrote*. Those are not the same
intervention, and I will not tell you they are. What the evidence supports is: **the closer
your test contract is to human-authored, the more of that effect you capture.** Reviewing a
scaffold catches less than writing the invariants yourself.

**Grade A** for the principle. Note it is a principle, not a skill you install.

### Candidate: `test-driven-development` — superpowers, 9kB — **C**

**What it does.** Enforces RED → verify-red → GREEN → verify-green → REFACTOR with two
mandatory *observed* test runs, under the Iron Law `NO PRODUCTION CODE WITHOUT A FAILING TEST
FIRST`. If code was written before the test: **delete it** — not keep as reference, not adapt.
Verify-RED must confirm the test fails for the right reason; a test that passes immediately
means you tested existing behaviour.

**Pros.** "Verify RED for the right reason" is the part most TDD instructions omit and the
part that catches vacuous tests. Its rationalisation table pre-answers "I'll test after" and
"deleting X hours is wasteful."

**Cons.** No measurement of the skill. 9kB. And the delete-the-code rule will fight your
existing flow if your scaffold is drafted alongside a plan.

**Grade C.** The *idea* is A-backed; this file is not.

**Verdict:** you already gate on a test scaffold. Take the "verify RED for the right reason"
rule into your Deterministic Ladder and skip the file.

### Candidate: `using-git-worktrees` — superpowers, 6.8kB — **B**

**What it does.** Detects whether you are already in a linked worktree (with a submodule
guard), prefers the harness's native worktree tool over raw `git worktree add`, verifies the
directory is gitignored **before** creating anything, then installs deps and runs a
**baseline test run** so later failures are not ambiguous.

**Pros.** The baseline-test step is the non-obvious one: without it, you cannot tell whether a
failure is yours. Prevents committing a worktree into the repo. Mechanically sound and easy
to verify by reading.

**Cons.** Only pays off if you run concurrent work.

**Grade B** — git worktree isolation is standard, widely used practice, and the mechanism is
directly checkable. Not benchmarked.

### The A-grade negative: do not add parallel subagent fan-out — **A**

**The evidence, three sources pointing the same way.**

1. A controlled comparison normalising the harness across single-agent and six multi-agent
   systems found **five of the six trailed a matched single agent by 2.56 to 11.29 points, at
   higher cost.**
2. pstack's own `orchestrate.md` playbook — the author documenting his own heaviest
   mechanism: *"measured head-to-head, this playbook's ceremony turned a half-hour 12-unit job
   into 1 landed unit while a plain agent landed all 12."*
3. Anthropic's 90.2% multi-agent figure is on an undisclosed internal *research* eval, and
   Anthropic states plainly that "most coding tasks involve fewer truly parallelizable tasks
   than research."

**Grade A** — a controlled study plus a first-party admission from a tool author against his
own interest.

**What this means for your Multi-Tier Orchestration.** Count how many of your dispatches run
**in parallel on interdependent work**. Each is a place this evidence predicts you pay more
for less. Sequential dispatch over shared artifacts is the shape all three sources favour.
Superpowers' `subagent-driven-development` (32kB) is the most sophisticated orchestrator in
the survey and I am not recommending it, for exactly this reason.

### Already installed

`lv1-coder` (which already does scope-holding and independent check),
`mattpocock-skills:tdd` (TypeScript examples throughout — skip),
`mattpocock-skills:prototype`.

---

## Stage 4 — Local Test and Verification

**What this stage must produce:** proof the change works and broke nothing, plus review that
someone acts on correctly.

**Your coverage:** the strongest stage. Deterministic Ladder (Types → Lint → Tests → Format),
Delta-Only Verification, Circuit Breaker, Composite Evidence Packet, Tri-Axis Review,
`code-reviewer` (13.5kB).

### The A-grade finding: never let the agent write and trust its own tests — **A**

**The evidence.** IBM Research measured a **21.8%** overfitting rate for Claude 3.7 on
auto-generated tests — code that passes the generated tests but fails hidden golden tests.
Under **joint code-and-test refinement**, that rises to **25.5%**, and an apparent gain of +8
resolved instances is a real gain of only +5.

**What this means.** Your Circuit Breaker halts after two consecutive verification failures.
That breaks the joint-refinement loop, which is the right instinct. But state the size
honestly: **the sourced benefit of breaking that loop is at most the 3.7pp between those two
figures. Agent-drafted tests still overfit at 21.8% with your gate in place.** Keep the gate.
Do not believe it solves the problem.

**Grade A.**

### Candidate: `receiving-code-review` — superpowers, 6.2kB — **C** — **your biggest gap**

**What it does.** A six-step reception pattern: read → restate the requirement in your own
words → verify against the actual codebase → evaluate for *this* codebase → acknowledge or
push back → implement one item at a time, testing each. It **bans specific strings**: "You're
absolutely right!", "Great point!", "Let me implement that now" before verification, and
expressions of gratitude. If *any* item in a multi-item review is unclear, stop and clarify
everything before implementing anything. A suggested "professional" feature gets grepped for
actual callers first and proposed for deletion under YAGNI if unused.

**Pros.** This is the hole in your lifecycle. You have `code-reviewer` for *giving* review and
Tri-Axis Review for *producing* adversarial findings. **Nothing governs how the agent acts on
them.** Sycophantic compliance — implementing wrong feedback because agreeing is cheaper than
verifying — is the exact failure mode a three-axis adversarial reviewer will generate volume
for.

**Cons.** No measurement. The banned-strings mechanism is crude and a model can route around
it.

**Grade C.**

**Verdict: take it.** Highest-value C in the report, because it fills a structural gap rather
than duplicating something you have.

### Candidate: `verification-before-completion` — superpowers, 3.6kB — **C**

**What it does.** A gate before any status claim: identify the command that proves it, run it
fresh and in full, read the exit code and count failures, then speak.
*"If you haven't run the verification command in this message, you cannot claim it passes."*
It ships a claim→evidence table — "linter clean" does not prove "build succeeds"; "agent
completed" requires reading the VCS diff, not the agent's report. A regression test claim
requires the full dance: write → pass → revert the fix → **must fail** → restore → pass.
Expressions of satisfaction ("Great!", "Done!") count as claims.

**Pros.** 3.6kB. Your Composite Evidence Packet demands proof at task end; this is the same
idea as a per-message gate, which is cheaper and fires more often. The "agent completed
requires reading the diff" rule directly serves Multi-Tier Orchestration.

**Cons.** No measurement. Partially duplicates what you have.

**Grade C.**

### Candidate: `systematic-debugging` — superpowers, 9.5kB — **C**

**What it does.** Four gated phases under `NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST`.
Phase 1 adds diagnostic instrumentation at **every component boundary** and runs once to find
which layer breaks, before proposing anything. Phase 2 finds a working example in the same
codebase and lists every difference. Phase 3 states ONE hypothesis in writing and tests it
with the smallest possible change. Phase 4 writes a failing test reproducing the bug before
fixing. **At 3 failed fixes, stop and question the architecture** rather than attempting
fix #4.

**Pros.** Your Circuit Breaker is a *mechanical* stop — two failures, revert. This is a
*diagnostic* stop — three failures means your model of the system is wrong. Different halves
of the same problem. The boundary-instrumentation step is the strongest single idea.

**Cons.** 9.5kB. Only pays off if debugging is where your time actually goes.

**Grade C.**

### Candidate: `ponytail-review` and `ponytail-audit` — 2.4kB and 1.7kB — **B**

**What they do.** Review a diff (or the whole repo) for over-engineering *only*. One line per
finding, five tags: `delete:` `stdlib:` `native:` `yagni:` `shrink:`. Closes with
`net: -N lines possible.` Correctness, security and performance are explicitly out of scope.

**Pros.** Complements your Tri-Axis Review rather than duplicating it — yours covers
correctness, security and spec drift; this covers complexity, which yours does not. Tiny.
Produces a countable, actionable deletion list rather than hedged prose.

**Cons.** Not itself measured.

**Grade B** — its parent skill's mechanism is A-measured and these apply the same ladder in
review mode, but no one has tested these two specifically.

### Candidate: the `ponytail:` marker + `ponytail-debt` — 1.7kB — **B**

**What it does.** When the agent takes a deliberate shortcut with a known ceiling, it leaves
a marker naming the ceiling and the upgrade trigger:

```python
# ponytail: global lock, per-account locks if throughput matters
```

`ponytail-debt` greps the repo and renders a ledger. Markers with **no** trigger get flagged
`no-trigger` — "those are the ones that silently rot."

**Pros.** Same shape as your `audits/` convention — a durable marker that gets promoted or
cleared rather than forgotten — extended into the code itself.

**Cons.** JetBrains found agents actually wrote a marker **once across 80 trials**. The
convention is sound; getting the agent to use it is the unsolved part.

**Grade B.**

### Already installed

`mattpocock-skills:code-review` (runs Standards and Spec reviews in parallel sub-agents),
`mattpocock-skills:diagnosing-bugs`, `engineering:debug`, `engineering:code-review`,
`engineering:testing-strategy`, `lv1-judge`. All **C**. All free to try today.

---

## Grade distribution — the honest summary

| Grade | Count | What they are |
|---|---|---|
| **A** | 4 | ponytail's ladder · human-authored tests given to the agent · execution-feedback loops · **do not fan out parallel subagents on interdependent work** |
| **B** | 4 | git worktree isolation · spec-kit's converge loop · ponytail-review/audit · the `ponytail:` debt marker |
| **C** | everything else | Read the file, judged the logic, no evidence exists |

Two of the four A-grades are negative findings. One (human-authored tests) is a principle
rather than an installable skill. **That leaves exactly one A-grade thing you can install:
ponytail's rung ladder.**

If that seems like a thin return on a large survey — it is, and it is the accurate answer.
The ecosystem has enormous adoption and almost no measurement.

---

## Build order

Ranked by value per byte, not by stage order.

| # | Do this | Stage | Grade | Cost |
|---|---|---|---|---|
| 1 | Add the 7-rung ladder to `implementation-planner` | Design | **A** | 6.6kB |
| 2 | Write a receive-side review discipline into `code-reviewer` | Test | **C** | ~6kB |
| 3 | Add a converge mode to `specs-reviewer` — re-derive unbuilt work from code | Design | **B** | small |
| 4 | Audit Multi-Tier Orchestration: count parallel-and-interdependent dispatches, convert to sequential | Implement | **A** | free |
| 5 | Add the per-message verification gate to your Deterministic Ladder | Test | **C** | 3.6kB |
| 6 | Add the `ponytail:` marker convention, harvest into `audits/` | Test | **B** | 1.7kB |
| 7 | Trim `implementation-planner` (34kB) and `specs-builder` (31kB), then run two weeks | All | **C** | negative |
| 8 | Try `grilling`, `mattpocock:code-review`, `engineering:debug` — already installed | 1, 4 | **C** | free |

Items 1–6 are roughly 18kB of additions against your current 115.9kB. Item 7 should more than
pay for them.

**Install nothing.** Every one of these is a markdown file you can read, adapt into your
CONTEXT.md vocabulary, and version under your own policy. A plugin is a file whose author can
change it under you.

---

## What I could not grade

- **Whether any of this improves your software.** No tool author has measured it. Two tools
  have been independently tested for *harm* and showed none, at sample sizes that can only
  exclude large effects.
- **Anything outside Python.** Every benchmark cited is Python-only or single-file. Your WMS
  OpenAPI surface, FastMCP servers and report servers appear in no benchmark.
- **Whether your six skills' size actually hurts.** SkillsBench publishes no byte thresholds
  and grades one skill against one task, not a library. Item 7 is a hypothesis, not a finding.

---

## Sources

Skill contents and quoted rules were read from `raw.githubusercontent.com` on 30 August 2026
— every file quoted was fetched. Effectiveness numbers carry over from
`agent-skills-evidence-audit-2026-08-30.md`, which went through two rounds of independent
review and 28 corrections; read it for confidence intervals, methodology, and the numbers you
should not repeat.

**A-grade sources:** JetBrains ponytail test (80 paired tasks, 251 trials) · TDFlow, EACL
2026 · Self-Debug, ICLR 2024 · Investigating Test Overfitting on SWE-bench (IBM Research) ·
Do More Agents Help? (arXiv:2606.05670) · pstack `orchestrate.md`.

**This document has not been through independent review.** The stage mapping and the grade
assignments are mine.
