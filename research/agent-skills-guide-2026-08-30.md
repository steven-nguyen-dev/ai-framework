# Agent Skills and Plugins: What Each One Is For

**A decision guide for `ai-framework`**

Compiled 30 August 2026. Companion to `agent-skills-evidence-audit-2026-08-30.md`, which
answers "is the marketing true?" This one answers "what is it for, and should I take it?"

---

## 1. The mental model you need first

These tools are not one category. They are three, and they do not compete with each other.

**A. Workflow frameworks.** They impose a sequence of stages and produce artifacts at each
one. Spec → plan → tasks → implement → review. You adopt one, not three.
*Examples:* BMAD-METHOD, spec-kit, superpowers, agent-os, pstack's playbooks.
**You already have one.** Your six lifecycle skills are exactly this.

**B. Discipline layers.** Single rules that change how the agent behaves inside whatever
workflow you use. "Never claim done without running the command." "Write the failing test
first." They compose freely and cost 2–10kB each.
*Examples:* superpowers' individual skills, pstack's 21 `principle-*` skills, ponytail's
rung ladder, the Karpathy rules.
**This is where you should be shopping.**

**C. Output-style modes.** They change how the agent writes, not what it does.
*Examples:* caveman, and ponytail's prose-capping half.
**Mostly not worth it — see §5.**

The mistake almost everyone makes is treating A and B as the same shelf. You do not need
another framework. You need specific disciplines you are missing.

---

## 2. The decision table

Read the left column. If it describes a problem you actually have, the right column is what
to take.

| Problem you have | Take this | From | Cost |
|---|---|---|---|
| Agent says "done" without checking | `verification-before-completion` | superpowers | 3.6kB |
| Agent patches symptoms, fix #4 never works | `systematic-debugging` | superpowers | 9.5kB |
| Agent agrees with bad review feedback | `receiving-code-review` | superpowers | 6.2kB |
| Agent over-builds: abstractions, deps, scaffolding | the 7-rung ladder | ponytail | 6.6kB |
| Deliberate shortcuts rot into invisible debt | the `ponytail:` comment + debt harvest | ponytail | 1.7kB |
| You trust a subagent's summary instead of its diff | `principle-prove-it-works` | pstack | ~2kB |
| Agent asks permission on reversible work | `principle-never-block-on-the-human` | pstack | ~2kB |
| Parallel agents collide on one checkout | `using-git-worktrees` | superpowers | 6.8kB |
| Agent starts coding on a misread request | `brainstorming` | superpowers | 15.5kB |
| **You want a whole new process** | **Don't. You have one.** | — | — |

Everything else in this report is either something you already have, something aimed at a
different job, or something the evidence does not support.

### The five I would actually take

**1. `verification-before-completion`** (superpowers, 3.6kB). The rule:
*"If you haven't run the verification command in this message, you cannot claim it passes."*
It ships a claim→evidence table — "linter clean" does not prove "build succeeds"; "agent
completed" requires reading the VCS diff, not the agent's report. Expressions of
satisfaction ("Done!", "Perfect!") count as claims.

Why you: your Composite Evidence Packet requires proof at the end of a task. This is the
same idea as a cheap per-message gate, and it costs 3.6kB.

**2. ponytail's 7-rung ladder** (6.6kB). Before writing code, walk down:

> 1. Does this need to exist at all? (YAGNI)
> 2. Already in this codebase? → reuse it
> 3. Stdlib does it? → use it
> 4. Native platform feature covers it? → `<input type="date">` over a picker lib, CSS over JS, DB constraint over app code
> 5. Already-installed dependency solves it? → use it. Never add a new one for what a few lines can do
> 6. Can it be one line? → one line
> 7. Only then: the minimum code that works

Stop at the first rung that holds. This is the only over-building intervention in the survey
with an independent measurement behind it (−10.3% cost, p=0.004, JetBrains, 80 paired tasks).

**3. The `ponytail:` comment convention + `ponytail-debt`** (1.7kB). When the agent takes a
deliberate shortcut with a known ceiling, it leaves a marker naming the ceiling and the
upgrade trigger:

```python
# ponytail: global lock, per-account locks if throughput matters
```

`ponytail-debt` then greps the repo and renders a ledger: file, line, what was simplified,
ceiling, upgrade trigger. Markers with **no** trigger get flagged `no-trigger` — "those are
the ones that silently rot."

Why you: this is the same shape as your `audits/` convention — a durable marker that gets
promoted or cleared rather than forgotten. It extends that discipline into the code itself.
Note the honest caveat: JetBrains found agents actually wrote a `ponytail:` marker **once
across 80 trials**. The convention is good; getting the agent to use it is the hard part.

**4. `principle-prove-it-works`** (pstack, ~2kB). One rule that matters specifically for
your Multi-Tier Orchestration:

> "For delegated work, inspect the diff/artifact, never the subagent's summary — agents
> report what they intended, not always what happened."

**5. `systematic-debugging`** (superpowers, 9.5kB) — if debugging is where your time goes.
Four gated phases under the law *"NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST."* Phase 1
adds diagnostic instrumentation at every component boundary and runs once to find which
layer breaks, before proposing anything. It carries an explicit fix counter: **at 3 failed
fixes, stop and question the architecture** rather than attempting fix #4.

Your Circuit Breaker halts after 2 verification failures and reverts. That is a mechanical
stop. This is a diagnostic one. They solve different halves of the same problem.

### What I would not take, and why

**A second workflow framework.** You have six lifecycle stages that you wrote, that you
understand, and that your CONTEXT.md defines in your own vocabulary. BMAD gives you five
named personas and a 15-skill artifact chain. Spec-kit gives you nine slash commands writing
into a `specs/` folder. Both are competent. Both would replace something that works with
something you did not design.

**Anything in category C.** See §5.

---

## 3. What each tool is actually for

### `obra/superpowers` — a complete methodology, sold as one bundle

**What it is for:** running an agent autonomously for hours without it drifting. The README's
framing is that it writes plans for "an enthusiastic junior engineer with poor taste, no
judgement, no project context, and an aversion to testing."

**The intended flow:** brainstorming → git worktree → writing-plans →
subagent-driven-development → TDD enforced throughout → code review between tasks →
finishing-a-development-branch.

**The three skills worth reading even if you take nothing:**

*`brainstorming`* (15.5kB) classifies your request out loud as **spike / bounded /
architectural**, then runs the matching script. Architectural means: explore context,
interview one question per message, present 2–3 alternatives with a recommendation, get the
design approved section by section, write it to `docs/superpowers/specs/`, self-review for
placeholders and contradictions. A `<HARD-GATE>` forbids code until the human says yes. When
in doubt between paths, it takes the heavier one.

*`subagent-driven-development`* (32kB, the heaviest) is the orchestration loop, and it is the
most sophisticated thing in the survey. Per task: dispatch a fresh implementer subagent
(built from a script that extracts the task to its own file, so the brief and not the chat is
the requirements source), dispatch a reviewer against a recorded BASE SHA, then a bounded fix
loop of **max 5 rounds** — rounds ≤3 resume the same implementer, rounds ≥4 spawn a fresh one
on a stronger model. It keeps a ledger at `.superpowers/sdd/<plan>/progress.md` explicitly
because "conversation memory does not survive compaction," and controllers that lost their
place had been re-dispatching completed tasks.

*`writing-skills`* (26kB) applies TDD to skill authoring. A test case is a pressure scenario
run against a subagent. RED is the baseline run *without* the skill, where you record the
exact rationalizations the agent produces. The skill document is the production code. This is
the mechanism behind the rationalization tables in every other superpowers skill — and it is
directly relevant to how you write your own six.

**When it helps:** long autonomous runs on well-specified work.
**When it does not:** short tasks. Its own evals record `brainstorming` firing on a trivial
checkbox task, unresolved since May 2026.
**Evidence:** its 85-scenario harness measures whether skills *fire*, not whether they help.
No arm compares superpowers to no-superpowers on outcome quality.

---

### `ponytail` — one job: stop the agent over-building

**What it is for:** LLMs produce speculative abstractions, add dependencies for one-liners,
and write scaffolding "for later." Ponytail is six skills aimed at exactly that and nothing
else.

**The core skill** is a persistent mode running the 7-rung ladder (§2), plus a fixed rule
set. The rules that do the work:

> - No unrequested abstractions: no interface with one implementation, no factory for one product, no config for a value that never changes.
> - Deletion over addition. Boring over clever, clever is what someone decodes at 3am.
> - **Bug fix = root cause, not symptom.** A report names a symptom. Before you edit, grep every caller of the function you're about to touch. The lazy fix IS the root-cause fix: one guard in the shared function is a smaller diff than a guard in every caller.

Three intensity levels: `lite` (build what's asked, name the lazier option), `full` (default),
`ultra` (ship the one-liner and challenge the requirement in the same breath).

**Its guardrails are the reason it is safe.** It never simplifies away input validation at
trust boundaries, error handling that prevents data loss, security, or accessibility. And
non-trivial logic must leave one runnable check behind — an assert-based self-check or one
small test file. "YAGNI applies to tests too."

**The other five skills:**

| Skill | What it does |
|---|---|
| `ponytail-review` | Reviews a **diff** for over-engineering only. One line per finding, five tags: `delete:` `stdlib:` `native:` `yagni:` `shrink:`. Ends `net: -N lines possible.` Correctness and security explicitly out of scope. |
| `ponytail-audit` | Same, scaled to the whole repo, ranked biggest cut first. One-shot, applies nothing. |
| `ponytail-debt` | Harvests `ponytail:` markers into a ledger (§2). |
| `ponytail-gain` | Prints benchmark medians. Notable for refusing to print a per-repo number: "the unbuilt version was never written, so there is no real baseline to subtract from." |
| `ponytail-help` | Reference card. |

**When it helps:** greenfield features, and any codebase where the agent keeps reaching for a
library. **When it does not:** its own README concedes the effect is "near zero on code that
is already minimal."

**Evidence:** the strongest in the survey. Independent test at −10.3% cost (p=0.004), no
detected quality difference. Its advertised −54% code reduction measured −15.4%, and that
figure did not reach significance.

---

### `pstack` — a value system plus a dispatcher

**What it is for:** Lauren Tan's answer to "how do I run many agents at once and trust the
output." Not a workflow you step through — **one sticky mode that reads your request, matches
a playbook, and dispatches to other models as subagents.**

**Three parts:**

*21 `principle-*` skills* — one rule each, never auto-triggered. Roughly 15 are coding
principles, 6 are agent-process principles. The mode indexes them and requires the reply to
name which principle changed which decision. `principle-build-the-lever` has an enforcement
clause worth stealing outright: *"Applying this principle produces a file. If you cited it and
there is no codemod, script, generator, or delegate skill in the diff, you didn't apply it."*

*23 playbooks* — you never name one. You type `/poteto-mode <request>` and it matches. The
playbook's steps are copied into the todo list **verbatim before any task-specific todos**,
and a skipped step stays in the list annotated `skip: <reason>`. The named failure mode: an
agent reads a playbook then writes a bespoke plan that quietly drops its steps.

*A role→model map* at `~/.cursor/rules/pstack-models.mdc`. A role whose value is a **list**
is a panel — one subagent per entry, so list length sets fan-out. Three fan-out shapes:
`arena` (N candidates at the same task, cross-judged, graft the winners' parts into a base),
`swarm` (partition or race, one report back), `interrogate` (one reviewer per model, same
rubric, read-only — "the adversarial signal comes from model diversity, not assigned
personas").

**The finding that matters most for you.** Its own `orchestrate.md` playbook carries this
anti-recommendation, verbatim:

> "measured head-to-head, this playbook's ceremony turned a half-hour 12-unit job into 1
> landed unit while a plain agent landed all 12. Below that line, route to Autonomous run."

That is a first-party admission that heavy orchestration lost 12-to-1 to a plain agent. It
matches the controlled result in the evidence audit — five of six multi-agent systems trailed
a matched single agent once the harness was normalised. **Read that before you expand
Multi-Tier Orchestration.**

**When it helps:** genuinely parallel, independent work with strict output isolation.
**When it does not:** anything below the ceremony threshold its own playbook names. It is
also a Cursor plugin; the Claude port says "This is not a verbatim copy."
**Evidence:** none. No eval, no benchmark, no test directory. ~3,200 tokens of always-on skill
descriptions before work starts — the heaviest fixed cost here.

---

### `mattpocock/skills` — small composable disciplines, TypeScript-flavoured

**What it is for:** the anti-framework position, stated in its README: *"Approaches like GSD,
BMAD, and Spec-Kit try to help by owning the process. But while doing so, they take away your
control and make bugs in the process hard to resolve."*

**The two worth taking**, because they carry no language-specific content:

*`grilling`* (315 words) — stress-tests a plan by interrogating it. Builds a design tree,
works the "frontier," asks in rounds using a `❓`/`➡️` format. Its docs claim thirteen
questions typically land in about three rounds. That figure is unsourced.

*`writing-for-agents`* — the most substantial document in the survey, and entirely
assertion-based. Its central claim, which you will recognise if you have written skills:

> "**Negation** is the failure mode beside this lever: steering by prohibition drags the
> forbidden behaviour into context and makes it *more* available, not less."

**What to skip:** `tdd` and `prototype`. Every fenced programming-language code block in the
repo is TypeScript — 14 TS blocks, zero Python, Go, Rust, Java, C#, or Ruby. `tdd/tests.md`
is TypeScript-and-jest throughout. The README claims **model** portability, never stack
portability.

**Evidence:** none, and the author says so: *"There is no automated eval here; the check is a
manual run plus the failure-mode vocabulary as a diagnostic."* His docs also self-report the
trigger bug — `grill-with-docs` naming `grilling` does not reliably load it.

---

### `andrej-karpathy-skills` — four rules, 65 lines

**What it is for:** a minimum-viable discipline layer for someone with no framework at all.

Rules 2 and 3 are the useful ones for you. Rule 2: *"Minimum code that solves the problem…
If you write 200 lines and it could be 50, rewrite it."* Rule 3: *"Every changed line should
trace directly to the user's request."*

Rules 1 (ask before assuming) and 4 (define success criteria, loop until verified) overlap
what `lv1-coder` and your `plan-reviewer` already enforce.

**Honest note:** rule 4 is the only one with independent backing — Self-Debug (ICLR 2024)
measured +2–3% without unit tests versus up to +12% with them. It is also the one you already
have. If you had no verification loop, rule 4 would be the first thing to take.

Karpathy did not write this file and has not endorsed it. The circulating "41% → 11% error
reduction" figure is unsourced; the article headlining it states no methodology.

---

## 4. The workflow frameworks, compared to yours

You have one. This is what the alternatives would give you, so you can see what you are not
missing.

| | Stages | Artifacts | Aimed at |
|---|---|---|---|
| **Yours** | 6: analysis-handoff → specs-builder → implementation-planner → plan-reviewer / specs-reviewer → code-reviewer | `spec.md`, `plan.md`, `raw-context.md` in `.scratchpads/` | You |
| **spec-kit** | 9 commands: constitution → specify → clarify → plan → tasks → analyze → implement → converge | `constitution.md`, spec, `research.md`, `data-model.md`, `contracts/`, `tasks.md` | Teams wanting a version-controlled contract before code |
| **BMAD** | ~15 skills in plan/ship phases, 5 named personas (Mary the analyst, John the PM, Winston the architect, Sally the UX designer, Amelia the engineer) | Product brief, PRD, UX, architecture, epics, stories, sprint status | Product thinking preserved as durable documents |
| **superpowers** | 7: brainstorm → worktree → plan → execute → TDD → review → finish | Design doc, plan file, SDD progress ledger | Long autonomous runs |
| **agent-os v3** | 5 commands, **zero agents** — it retired its implementation phase | `mission.md`, `roadmap.md`, `standards/` | Injecting house style into any tool's plan mode |

**Two things worth knowing.**

*spec-kit has a loop you do not.* `/speckit.converge` assesses the codebase against the spec
and **appends remaining unbuilt work back into `tasks.md`**. You run implement↔converge until
it reports "Converged". That closes the gap between "the plan said" and "the code does." Your
`specs-reviewer` reviews the spec; nothing re-derives remaining work from the code. That is a
real gap and it is cheap to add to your own flow.

*agent-os v3 deleted most of itself, and said why.* Its changelog: spec writing defers to Plan
Mode, task breakdown to the agent's own todo lists, and "Implementation/orchestration phases
retired — frontier models handle this well on their own now." A framework author concluding
that the frontier caught up with his framework is a data point about all of them.

**`wshobson/agents` is not a framework at all.** It is a marketplace: 93 plugins, 202 agents,
181 skills. You install a *plugin* (e.g. `python-development` = 3 agents, 1 command, 16
skills), not individual skills, and its own docs say "install the 2–3 plugins that cover your
domain." Browse it if you want domain expertise on tap without adopting anyone's process.

**`claude-flow` (now Ruflo) is infrastructure, not methodology.** Its thesis is
`Agent = Model + Harness`, and it supplies the harness — persistent vector memory, hooks,
cross-machine agent federation, 12 auto-triggered background workers. Its own onboarding says
you do not drive it: "After `init`, just use Claude Code normally — the hooks system
automatically routes tasks." Its benchmarks measure cold start, single-turn latency and
resident memory. Nothing measures whether your software got better.

---

## 5. Output-style modes: skip these

**`caveman`** makes the agent write terse. Real rules — drop articles, filler, pleasantries;
fragments OK; never invent abbreviations because the tokenizer splits them the same and you
save nothing; never add words to sound caveman. It has an `Auto-Clarity` escape that suspends
compression for security warnings, irreversible-action confirmations, and any multi-step
sequence where dropped conjunctions risk misreading.

It is more carefully built than its reputation suggests. It is still not worth installing:

- It adds ~1–1.5k input tokens per turn, every turn
- Advertised 65% saving; JetBrains measured **8.5%**, and that was with the skill forced on
- An independent benchmark found the literal prompt `"Be brief."` matched baseline quality at
  34% fewer output tokens, with nothing installed
- Its own `docs/HONEST-NUMBERS.md` lists the output-reduction figure as **"Not published"**

**Use `"Be brief."` in your CLAUDE.md.** You already have a concision rule there. That is the
whole intervention.

The same applies to `rtk`, `headroom` and `lean-ctx`. All three advertise 60–95% reductions.
Independently measured: rtk +7.6% cost at low reasoning effort, headroom +56%, lean-ctx +23%.
The pattern is mechanical, not dishonest — compressing one input class by 90% barely moves a
bill where that class is a small share.

---

## 6. Applied to `ai-framework`

**What you have that these tools sell.** Your Test Contract is superpowers' TDD gate. Your
Artifact Reference Injection is `principle-guard-the-context-window` ("summaries in the main
thread, not raw payloads"). Your Tri-Axis Review is `interrogate`. Your Deterministic Ladder
is what `verification-before-completion` gates on. You built this stuff independently.

**The four gaps, in priority order.**

**1. No receive-side review discipline.** You have `code-reviewer` for *giving* review.
Nothing governs how the agent *receives* it. Superpowers' `receiving-code-review` bans the
strings "You're absolutely right!", "Great point!", and "Let me implement that now" before
verification, and requires the agent to restate the requirement in its own words and check it
against the actual codebase before acting. A suggested "professional" feature gets grepped
for callers first and proposed for deletion under YAGNI if unused. Given your Tri-Axis Review
produces adversarial findings that something must then act on, this is the sharpest missing
piece.

**2. No convergence loop.** spec-kit's `/speckit.converge` re-derives unbuilt work from the
code back into the task list. Your Execution Ledger tracks stage and gate status; it does not
close the spec-versus-reality gap. Worth adding to `specs-reviewer` as a mode.

**3. No over-building guard.** Nothing in your six stages asks "should this exist?" Your
`implementation-planner` plans how to build; it does not challenge whether to. The rung
ladder is the cheapest fix, and it is the one intervention here with an independent
measurement behind it.

**4. Your two largest skills are outliers.** Measured on your disk:

| Skill | Bytes |
|---|---|
| `implementation-planner` | 33,977 |
| `specs-builder` | 30,680 |
| `specs-reviewer` | 22,248 |
| `code-reviewer` | 13,536 |
| `plan-reviewer` | 8,721 |
| `analysis-handoff` | 6,739 |
| **Total** | **115,901** |

Superpowers averages ~2.5kB per skill. Ponytail's entire six-skill set is 17,144 bytes — half
of your `implementation-planner` alone. The only SkillsBench finding that plausibly transfers
is that compact and standard-length skills outperform detailed and comprehensive ones
(+19.0 and +21.5pp versus +14.5 and +0.7pp). SkillsBench publishes no byte thresholds, so I
cannot tell you which bucket a 34kB skill lands in. But you are at the opposite end of the
distribution from every tool that measures well, and trimming is cheap to test.

**On Multi-Tier Orchestration — the strongest thing I found for you.** pstack's own
orchestration playbook reports that its ceremony *"turned a half-hour 12-unit job into 1
landed unit while a plain agent landed all 12."* That is the tool's author documenting his own
heaviest mechanism losing 12-to-1. It corroborates the controlled finding that five of six
multi-agent systems underperform a matched single agent once the harness is normalised. If you
extend orchestration, extend it toward the shape both sources favour: fewer agents, sequential
where work is interdependent, shared artifacts rather than isolated context.

**On project management.** No tool here was built or measured for PM work. BMAD is the closest
— five personas producing a PRD, UX doc, architecture doc, epics and stories — and it has no
evidence of any kind. If you want PM structure, take BMAD's artifact chain as a checklist and
write your own. Do not install it.

---

## 7. What to do Monday

1. Copy `verification-before-completion` and `receiving-code-review` out of superpowers.
   Adapt the wording to your CONTEXT.md vocabulary. ~10kB total.
2. Add the 7-rung ladder to `implementation-planner`, before its planning steps.
3. Add the `ponytail:` marker convention to `code-reviewer`, and a debt-harvest mode that
   writes into `audits/`.
4. Trim `implementation-planner` and `specs-builder`. Run your normal work for two weeks.
   See whether anything degrades.
5. Install nothing.

Item 5 is deliberate. Every tool here is a `SKILL.md` file you can read. The ones worth having
are worth having in your vocabulary, in your repo, under your version policy — not as a
plugin whose author changes it under you.

---

## Sources and status

**Skill contents, mechanisms, and quoted rules** in this document were read from
`raw.githubusercontent.com` on 30 August 2026 — every `SKILL.md` quoted was fetched, not
paraphrased from a blog. **This purpose-level material has not been through independent
review.**

**Every effectiveness number** carries over from `agent-skills-evidence-audit-2026-08-30.md`,
which went through two rounds of independent review and 28 corrections. Its appendix lists
what earlier drafts got wrong. Read that document for the evidence, the confidence intervals,
and the numbers you should not repeat.

Repositories: obra/superpowers · DietrichGebert/ponytail · cursor/plugins (pstack) ·
mattpocock/skills · multica-ai/andrej-karpathy-skills · JuliusBrussee/caveman ·
github/spec-kit · bmad-code-org/BMAD-METHOD · wshobson/agents · ruvnet/claude-flow ·
buildermethods/agent-os
