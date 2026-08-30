# Do Agent Skills Actually Work?

**An evidence audit of the popular Claude Code skills and plugins**

Compiled 30 August 2026. Every load-bearing claim is either sourced to a primary document
or labelled **unmeasured**. Numbers taken from a README are marked as vendor claims, not
findings.

This is version 3. Two independent reviewers rejected version 1 (20 major defects) and
version 2 (8 more). The appendix lists every error. Three are worth flagging here because
they changed the conclusions:

- Version 1 quoted SkillsBench v4 and used v1 body numbers. v4 reverses the sign of the
  finding the lead recommendation rested on.
- Version 2 attributed a methodological caveat to a named benchmarker who never wrote it.
  Removed.
- Version 2 asserted that your six skills are compact without measuring them. **I have now
  measured them, and they are not.** Recommendation 1 changed as a result.

---

## 1. Recommendations first

### Adopt

**1. Keep the six-stage architecture. Trim two of the six skills.**

Your lifecycle skills total **115,901 bytes** across six `SKILL.md` files (measured on your
disk, 30 August 2026):

| Skill | Bytes | ≈ tokens |
|---|---|---|
| `implementation-planner` | 33,977 | ~8,500 |
| `specs-builder` | 30,680 | ~7,700 |
| `specs-reviewer` | 22,248 | ~5,600 |
| `code-reviewer` | 13,536 | ~3,400 |
| `plan-reviewer` | 8,721 | ~2,200 |
| `analysis-handoff` | 6,739 | ~1,700 |
| **Total** | **115,901** | **~29,000** |

For scale: superpowers averages ~2.5k tokens per skill. Ponytail's entire six-skill set is
17,144 bytes — less than your `specs-builder` alone.

This matters because of the one SkillsBench finding that plausibly transfers to your setup:

> "compact and standard-length Skills (+19.0 and +21.5 pp) outperform detailed (+14.5 pp)
> and comprehensive documentation (+0.7 pp); focused procedural guidance beats exhaustive
> prose."

**Two honest caveats before you act on that.** SkillsBench publishes no byte threshold for
those four buckets, so I cannot tell you which bucket a 34kB skill falls into. And its
buckets grade *one skill paired with one task*, not a library — the gap in §3 applies here
too. What I can say is that your two largest skills are at the opposite end of the
distribution from the tools that measure well, and that this is a testable hypothesis: trim
`implementation-planner` and `specs-builder`, and see whether anything degrades.

Version 2 of this document told you your skills were compact and to change nothing. That
was an unmeasured assertion, and it was wrong.

**Do not replace the architecture with a framework.** Six named stages you control beat 59
or 359 you do not. But that is a maintainability argument, not an evidence-backed one.

**2. Keep the Test Contract and the Executable Test Scaffold.**

Verification loops are the best-evidenced intervention in this field. TDFlow (EACL 2026,
peer-reviewed) reached **88.8%** on SWE-Bench Lite and **94.3%** on Verified — **when handed
human-written tests**. The paper's own conclusion is that generating valid reproduction
tests is the unsolved bottleneck.

Your gate has a human *approve* an agent-drafted scaffold. TDFlow handed the agent tests a
human *wrote*. Not the same intervention, and version 1 overstated the match.

What your gate has direct evidence behind is the negative case. IBM Research measured a
**21.8%** overfitting rate for Claude 3.7 on auto-generated tests, rising to **25.5%** under
joint code-and-test refinement. **State the size of that honestly: breaking the refinement
loop is worth at most the 3.7pp between those figures. Agent-drafted tests still overfit at
21.8% even with your gate.** The gate is worth keeping and it is not a solution.

**3. Trial `ponytail` for two weeks, installed as a plugin.**

The only tool here with both a vendor benchmark and an independent test. JetBrains ran 80
paired SkillsBench tasks and measured **−10.3% cost (p=0.004)** — a real effect. Their
code-reduction figure was **−15.4% median at p=0.088**, which is *not* significant.

Install as a plugin, not a bare skill: JetBrains found it self-activated **zero times across
ten sessions** when offered as an optional skill.

Expect roughly a 2× discount on the advertised cost saving (−20% claimed, −10.3% measured).
I am not giving you a discount factor for the code figure, because dividing by a
non-significant point estimate would be making up precision.

**Measurement:** record cost per task across your normal work for two weeks, then two weeks
without. Read §5 pattern 2 first on what a sample that size can and cannot detect.

**4. Borrow rules 2 and 3 from the Karpathy `CLAUDE.md` — but audit for overlap first.**

"Simplicity first" and "surgical changes" span about 28 lines of a 65-line file. They are
**unmeasured**. Rules 1 and 4 appear to overlap what `lv1-coder` and your `plan-reviewer`
already enforce; that is my reading of their stated purposes, not a measured finding.

**On the cost of that overlap, I have to be careful.** The 24.1pp compliance loss measured
in §3 is from *irrelevant* instructions injected from unrelated tasks. A duplicated rule is
a *relevant* rule stated twice, which is a different case, and no study I found prices it.
Version 2 of this document used that number to price duplication. That was wrong.

What §3 does support: adding relevant rules lowers the chance the agent honours all of them
simultaneously, while leaving per-rule compliance roughly unchanged. That is a reason for
restraint, not a measured penalty.

**5. Read `humanlayer/advanced-context-engineering-for-coding-agents`.**

Five markdown documents, nothing to install, zero cost. It is the only entry that ran an
independent academic benchmark and published a result unflattering to itself. Its evidence
grade is **C** — below ponytail and caveman, both **A**. It earns a recommendation on cost,
not on evidence rank.

### Trial

Two things to understand about the protocol below before you use it.

**A ten-pair trial cannot detect the effects these tools actually have.** JetBrains needed
80 paired tasks to reach p=0.004 on a −10.3% cost effect, and still landed at p=0.088 on a
−15.4% code effect. Ten pairs will only catch something large. Treat these trials as *fit
checks* — does it trigger, does it fight my workflow, does it change the shape of the diff —
not as efficacy tests. Nothing in this report gives you a cheap way to measure efficacy,
because nobody has found one.

**`obra/superpowers`, one skill — `brainstorming`.** Highest adoption in the ecosystem, and
the only credible detailed first-hand reports, positive and negative. Before you judge it:
superpowers' *own* evals record `brainstorming` firing on a trivial checkbox task,
unresolved since May 2026. Check it is triggering appropriately first.
*Fit check:* does it fire when you want it and stay quiet when you don't.

**`mattpocock/skills`, prose skills only — `grilling` and `writing-for-agents`.** Light,
well-crafted, zero evidence, honest about having zero evidence. Skip `tdd` and `prototype`:
every programming-language example in that repo is TypeScript.
*Fit check:* these produce questions and documents, not diffs, so cost-per-task and
files-touched do not apply. Judge whether `grilling` surfaces a constraint you had not
stated, and whether `writing-for-agents` changes how you write your own `SKILL.md` files.
Both are subjective. Say so rather than dressing it up.

### Read, don't install

**`github/spec-kit`.** Take the spec structure and the framing. Your `specs-builder` and
`specs-reviewer` already occupy that slot, and running both would duplicate a stage. It is
the only tool here that labels its own thesis a hypothesis, which is the correct posture.

### Avoid

**The token-compression class** — `caveman`, `rtk`, `headroom`, `lean-ctx` (§4.11). Not
because they damage output: independent tests detected no quality difference, though at
sample sizes that can only rule out large effects. Because the savings do not survive
contact with agent work. Caveman advertises 65%; JetBrains measured **8.5%**. An independent
benchmark found `"Be brief."` matched baseline quality at 34% fewer output tokens with
nothing installed. `headroom` measured **+56% cost** and `lean-ctx` **+23% cost**, both with
confidence intervals entirely above 1.

**`pstack`.** Strongest qualitative claims in the survey, zero measurement of any kind, and
the heaviest always-on context cost (~3,200 tokens of skill descriptions before work
starts). Also a Cursor plugin; the Claude port's README says it is not a verbatim copy.

**`cc-sessions`.** 1.6k stars, **102 npm downloads last month** (verified). Its evidence is
two testimonial screenshots. Its README carries a crypto donation badge.

**The heavyweight frameworks** — `claude-flow`, `BMAD-METHOD`, `SuperClaude`,
`wshobson/agents` — on a weaker argument than version 1 gave. SkillsBench v4 does **not**
find large bundles harmful: ≥4 skills still gained **+10.1pp**. The case against them is
that none has measured its own effect, they cost far more context, and they take ownership
of a process you already control. Not that they will make your agent worse.

### The honest limit

**No tool author in this survey has demonstrated that their tool improves software
outcomes.** Two tools have been independently tested for *harm* — caveman and ponytail —
and neither showed any, at sample sizes that can only exclude large effects. That is the
state of the evidence. Every recommendation above is a hypothesis, including the one about
trimming your own skills.

---

## 2. How to read this report

Version 1 used a single A–F grade and applied it inconsistently, grading caveman **F** when
caveman is the most independently measured tool here. Version 2 split it into two columns
and the second column still tracked maintainer behaviour rather than what it claimed to
measure. This version makes both columns mechanical.

**Evidence grade — how well is this tool's effect on software outcomes measured?**

| Grade | Meaning |
|---|---|
| **A** | An independent party ran a controlled test of this tool |
| **B** | Vendor benchmark with published method and results, measuring outcomes |
| **C** | Verifiable real-world case study |
| **D** | No measurement of outcomes exists |

A tool that benchmarks something other than outcomes — runtime latency, whether its own
skills fire — scores **D** on this column, with the artifacts credited in prose. Building
good measurement apparatus is not the same as measuring your effect.

**Advertised number — what is the status of the tool's headline figure?**

| Mark | Meaning |
|---|---|
| **none** | The tool makes no numeric claim |
| **unbacked** | A number is advertised with no published measurement behind it |
| **contradicted** | An advertised number is contradicted by measurement, and is still live |

These are mutually exclusive and about the number only. Whether a maintainer has behaved
well — conceded on HN, corrected an earlier figure — belongs in prose and is noted there.
Ponytail's maintainer publicly corrected an *earlier, superseded* figure; his live 54% has
never been corrected, so it is **contradicted**, the same mark caveman gets.

### On adoption numbers

**Stars measure reach, not use.** Install figures circulating for these tools do not agree
with each other. Version 1 quoted marketplace install counts I could not source, and a
reviewer found a different service reporting the opposite ranking. They are removed.

The only usage figures here are ones I fetched myself on **30 August 2026** from
`api.npmjs.org` and `pypistats.org`. Star counts come from shields.io badge JSON, same date,
rounded — read as scale, not precision. Where a tool ships through the Claude plugin
marketplace rather than npm or PyPI, **I have no verified usage number and say so.**

---

## 3. The measurement that constrains everything

### SkillsBench — the only controlled evaluation of the skills category

*SkillsBench: Benchmarking How Well Agent Skills Work Across Diverse Tasks*,
arXiv:2602.12670. **v4, 14 June 2026, is the version cited throughout.** Lead author
Xiangyi Li, final author Dawn Song, 78 authors. **Preprint, not peer-reviewed.**

From the v4 abstract, verbatim:

> "Our latest aggregate evaluation runs the 87-task benchmark under matched no-Skills and
> curated-Skills conditions for 18 model-harness configurations. Curated Skills raise the
> average pass rate from 33.9% to 50.5% (+16.6 percentage points; 25.5% normalized gain),
> with configuration-level gains ranging from +4.1 to +25.7 pp."

**The +16.6pp headline is not the software-engineering number.** v4's Table 3:

| Domain | N | No Skills | With Skills | Δ |
|---|---|---|---|---|
| Natural Science | 14 | 42.0% | 70.8% | +28.8 |
| Media & Content Production | 5 | 23.3% | 47.4% | +24.1 |
| Cybersecurity | 7 | 29.5% | 48.4% | +18.9 |
| Industrial & Physical Systems | 14 | 23.9% | 39.6% | +15.7 |
| Finance & Economics | 9 | 19.1% | 33.3% | +14.2 |
| Office & White Collar | 14 | 40.5% | 53.0% | +12.6 |
| **Software Engineering** | **16** | **37.6%** | **49.2%** | **+11.6** |
| Mathematics & Operations Research | 8 | 45.7% | 55.4% | +9.7 |

Software engineering is **second-lowest of eight domains**. The paper's explanation, v4
wording, quoted in full:

> "Domains requiring specialized procedural knowledge underrepresented in model pretraining
> (e.g., scientific signal processing, security analysis, and multimedia transformation
> workflows) improve most, whereas domains with stronger pretraining and tooling coverage
> benefit less from external procedural guidance."

Every tool in this report is a software-engineering skill set. They operate where the
measured benefit is near the bottom, because the models already know how to code.

**Two design ablations, from v4 §5.2. The paper presents them side by side and ranks
neither:**

> "tasks paired with one Skill gain +18.0 pp, 2–3 Skills gain +19.0 pp, and ≥4 Skills give
> only +10.1 pp"

> "compact and standard-length Skills (+19.0 and +21.5 pp) outperform detailed (+14.5 pp)
> and comprehensive documentation (+0.7 pp); focused procedural guidance beats exhaustive
> prose."

> "Self-generated Skills land below the no-Skills baseline on all three configurations
> (−8.1 pp on Claude Code + Opus 4.7, −11.3 pp on Codex + GPT-5.5, −11.5 pp on Gemini CLI +
> Gemini 3.1 Pro)"

Read those carefully, because version 1 got them wrong.

- **Large bundles are not harmful.** ≥4 skills still gained +10.1pp — less than compact
  sets, not less than nothing.
- **Standard-length beat compact** (+21.5 vs +19.0). The finding is against *exhaustive*
  prose, not in favour of maximum terseness. Both beat detailed (+14.5) and comprehensive
  (+0.7).
- **The genuinely negative case is self-generated skills**, −8.1 to −11.5pp. That means the
  *model* wrote the skill cold, before the task, with no feedback loop. Your hand-written,
  audit-revised skills are a different thing and this finding does not apply to them.
- **The verbosity span (20.8pp) is wider than the count span (9.0pp).** Reading that as
  "verbosity matters more" is my inference from the spans, not a claim the paper makes.

### The gap I could not close — and it applies to both ablations

SkillsBench measures **one skill paired with one task**. Both ablations grade that unit: how
many skills accompanied a task, and how long each one was.

Every argument the ecosystem builds on this — including mine — is about **libraries you
install**. A 48-skill library from which two skills fire is not the condition tested. Nor is
"this framework ships 934k tokens of material" the same as "this framework's individual
skills are comprehensive"; I did not compute per-skill length for every framework and cannot
tell you which verbosity bucket their skills fall in.

I found no study bridging per-task to per-library. The nearest is arXiv:2601.04748, a
single-author, self-described *preliminary* technical report suggesting selection accuracy
collapses past a critical library size, driven by semantic confusability between similar
skills rather than raw count. Hypothesis, not finding, and on reasoning benchmarks rather
than coding.

**So when this document reasons from a tool's size or bulk to its likely value, that is my
inference and not the benchmark's.** I have tried to flag it at each use. Where I have
per-skill data — your six skills in §1, superpowers at ~2.5k tokens per skill, ponytail's
17,144 bytes total — the comparison is at least like-for-like. Where I only have library
totals, it is not.

### SkillsBench is weakest where you need it

The HN thread (364 points) carried substantive critique. Commenter *btown* noted tasks are
"limited to a single markdown file of instructions, plus an opaque verifier… No problems
involving existing codebases, refactors." Commenter *JB_5000* noted skills are generated
before the task with no feedback loop, testing "cold generation, which is a different (and
less realistic) setup."

That applies to both ablations as much as to the headline, since they come from the same 87
tasks. **I use SkillsBench because it is the only controlled evidence that exists, not
because it settles anything.** A reader who concludes it is too weak to act on is drawing a
defensible conclusion.

### The context-file study, read correctly

*Evaluating AGENTS.md: Are Repository-Level Context Files Helpful for Coding Agents?*,
arXiv:2602.11988, ETH Zurich SRI Lab and LogicStar.ai. **The arXiv entry lists no venue and
no journal reference. Treat it as a well-executed preprint.** Version 1 claimed a workshop
oral; I could not confirm that against a primary source and have withdrawn it.

Setup: SWE-bench Lite (300 tasks) plus CTXbench (138 instances from 12 repos carrying real
developer-written context files). Four agent-model pairs. One sample per instance. Python
only.

> "Surprisingly, we find that providing context files does not generally improve task
> success rates, while increasing inference cost by over 20% on average."

> "while instructions in the context files are well followed by coding agents, repository
> overviews, although popular and recommended by model providers, are not helpful."

Three things it does **not** say:

1. **It does not show context files are harmful.** Every success comparison against no-file
   is non-significant: LLM-generated p=0.87 and p=0.37; developer-written files improved
   performance by 2.4% on average at p=0.21. The defensible reading is a **null result on
   success plus a significant cost penalty** (p<0.00001).
2. **It does not show agents ignore your rules.** When a file mentioned `uv`, the agent used
   it **1.6 times per instance** versus under **0.01** when it did not. The paper: "the
   absence of improvements when using context files is not due to a lack of
   instruction-following capabilities."
3. **It does not show longer files are worse.** Appendix B: "We find no correlation between
   the resolution rate and the length of the context files."

### The rule-count question, corrected

**WildIFEval** (GEM @ ACL 2026, workshop-reviewed). This sentence is in the v3 HTML abstract
and body, but **not** on the current arXiv abstract page:

> "as constraint count grows, models' overall success drops sharply while per-constraint
> success remains stable, indicating a capacity bottleneck in juggling multiple constraints"

**FollowBench** (ACL 2024, peer-reviewed) shows the same split. GPT-4's hard satisfaction
rate falls **84.7 → 61.9** across five constraint levels; its soft satisfaction rate falls
only **84.7 → 72.3**.

The defensible claim: *as you add rules, the chance an agent honours all of them at once
falls sharply; the chance it honours any given one is roughly unchanged.*

**The exception is irrelevant rules.** The catastrophic-remembering preprint
(arXiv:2608.11095, unreviewed, single author) injected 16 noisy instructions **drawn from
other tasks** and measured per-constraint compliance on the *true* instructions drop from
**65.6% to 41.5%** — 24.1pp, 95% CI [−33.4, −14.9]. Chroma's report found even a single
distractor hurts, across 18 models.

**This number prices irrelevant context. It does not price duplication** — a rule you
already have, stated twice, is relevant. Version 2 of this document used it that way and was
wrong. Nothing I found measures the cost of duplicated rules.

That same paper found context files grow **+226%** over their lifetime, median 39
instructions, with **77.3%** of instruction deaths arriving in a wholesale rewrite or a
migration to a sibling file rather than a considered deletion.

---

## 4. The tools

### 4.1 `mattpocock/skills` — Matt Pocock

| | |
|---|---|
| Repo | github.com/mattpocock/skills · MIT |
| Reach | 241k stars (shields.io, 30 Aug 2026) |
| Use | **No verified figure** (marketplace-distributed) |
| Weight | 37 `SKILL.md` in repo; 25 in the plugin manifest; 21 in the marketplace listing. Three inconsistent counts. |
| Evidence | **D** |
| Advertised number | **none** |

**Claim, verbatim:** *"These skills are designed to be small, easy to adapt, and composable.
They work with any model."* Note what that claims: **model** portability, not stack
portability.

**Evidence.** None. A fresh clone contains no `eval/`, no `benchmark/`, no `test/`
directory, and `package.json` has no test script.

**The author says so himself**, in `docs/productivity/writing-for-agents.md`:

> "How do I know when it's done? When it works, and you can no longer find duplication,
> sediment or no-ops. **There is no automated eval here**; the check is a manual run plus
> the failure-mode vocabulary as a diagnostic."

That is the most honest sentence in any repo in this survey.

**Pros.** The prose skills — `grilling`, `writing-for-agents`, `domain-modeling`,
`codebase-design` — contain no language-specific content and should port to any stack.
`writing-for-agents` is the most substantial document in the survey. Makes no numeric claim,
so has nothing to be wrong about.

**Cons.**

*TypeScript bias, counted.* Every fenced programming-language code block in the repo is
TypeScript: 14 TS blocks, zero Python, Go, Rust, Java, C#, or Ruby. `tdd/tests.md` and
`mocking.md` are TypeScript-and-jest throughout. This bites hardest on `tdd` and
`prototype` — the two skills closest to your daily work.

*Documented trigger failures*, from the author's own docs:

> "`grill-with-docs` ran, but it never loaded `grilling`. A real and unfixed rough edge…
> a skill that names another skill does not reliably cause that skill to load."

> "It ran out of questions and started building. … Weaker and faster models still break it."

**Trade-off.** A light, well-crafted, honestly-labelled set with no evidence and a stack
mismatch. The prose skills port; the code skills do not.

**Independent reports.** Essentially none. The HN submission got **2 points, 0 comments**.
One forum "week with it" post exists but describes a superseded version — it praises a
`caveman` skill the CHANGELOG confirms was removed — so I cannot confirm it is genuine.

---

### 4.2 `obra/superpowers` — Jesse Vincent

| | |
|---|---|
| Repo | github.com/obra/superpowers · MIT · v6.3.0 |
| Reach | 279k stars — highest in survey |
| Use | **No verified figure** (marketplace-distributed) |
| Weight | 14 skills · ~35k tokens of skill bodies (**~2.5k per skill**) · ~610 tokens of always-on descriptions · session-start hook injecting ~780 tokens → **~1,390 always-on** |
| Evidence | **D** — its harness measures compliance, not outcomes |
| Advertised number | **unbacked** |

**Claim, verbatim:** *"An agentic skills framework & software development methodology that
works."* The only quantitative claim, from v6.0.0 release notes, quoted with its hedge:

> "**While these numbers won't hold on every harness and for every workload**, in our evals,
> Claude Code and Codex produce similar high-quality results roughly twice as fast and while
> spending almost 50% fewer tokens."

**Evidence.** `prime-radiant-inc/superpowers-evals` is a genuine harness: 85 scenario
directories, dated baselines, published pass/fail results. That is real infrastructure and
deserves credit. It does not raise the evidence grade, because of its own scope statement:

> "This is not a generic benchmark suite. It is an eval lab for workflow compliance: skill
> triggering, worktree behavior, subagent coordination, verification reflexes, review
> quality, and cost-shaping patterns."

**Every scenario is pass/fail compliance. No arm compares superpowers to no-superpowers on
outcome quality.** The "twice as fast, 50% fewer tokens" line compares superpowers 6.0 to
*older superpowers*, not to a bare agent, with no table, n, or model published.

**Pros.** Most-used and most-scrutinised system in the ecosystem. The best body of
independent first-hand reports in the field, including negative ones — itself a quality
signal. Its skills average ~2.5k tokens, the leanest per-skill figure I could compute for
any multi-skill tool here. v6.1.0 was titled "Lower Per-Session Token Cost", so the
maintainer responds to cost complaints.

**Cons.** Its own evals document over-triggering: the `cost-*` cluster fails on both
backends because "both fire brainstorming on a trivial checkbox task", an open product
decision unresolved since 27 May 2026. A user-measured issue (#190) reported ~22k tokens of
preloaded skills against an expected ~1,400; on v6.3.0 the hook injects ~780 tokens, so that
appears version-specific, but I could not verify its resolution.

**Trade-off.** The best-built measurement infrastructure in the field, aimed at compliance
rather than outcomes. Take `brainstorming` alone, verify it is not firing on trivia.

**Independent reports**, HN item 47623101, read in full:

- *tao_oat*, detailed and mixed: "the brainstorming skill is great… it uses subagents to
  adversarially review its own spec/plan; that has caught several things I would've missed.
  I do not like the separation of spec/plan."
- *d--b*, negative: "I think Claude makes more mistakes when using superpowers than when
  not… Just don't believe it's a silver bullet. It's still the same Claude."
- *raesene9*, on the non-Claude install path: "it's like curl|bash but with added LLM
  agents..."

---

### 4.3 `ponytail` — Dietrich Gebert

| | |
|---|---|
| Repo | github.com/DietrichGebert/ponytail · MIT · v4.9.0 |
| Reach | 117k stars |
| Use | **No verified figure** (marketplace-distributed) |
| Weight | 6 skills, **17,144 bytes total** (~4–5k tokens). Always-on hooks, ~1.5k tokens/session. |
| Evidence | **A** — independently tested by JetBrains, 251 billed trials |
| Advertised number | **contradicted** — the live 54% has never been corrected |

**Claim, verbatim, README header:**

> "~54% less code (up to 94%) · ~20% cheaper · ~27% faster · 100% safe"

**Vendor evidence — the best in-repo methodology in the survey.** Claude Code 2.1.177
headless, Haiku 4.5, a real repo pinned at a commit, 12 feature tasks plus 6 adversarial
safety tasks, n=4, four arms including a terse-prose control. Three marks of real rigour:

1. **Rebuilt after public critique.** Colin Eberhardt showed the original baseline was a
   chatty bare model padding with prose. The benchmark write-up
   (`benchmarks/results/2026-06-18-agentic.md`, not the README) states: *"The original
   80–94% single-shot numbers were inflated by a chatty baseline, Colin was right."*
   **Note what was corrected: the superseded 80–94% figure. The 54% now on the README has
   not been.**
2. **It self-reports a contamination bug in its own numbers** — a SessionStart hook fired on
   every arm, so "the baseline was secretly running ponytail."
3. It publishes a real Limitations section.

**Independent test.** JetBrains, July 2026: 80 paired SkillsBench tasks, Claude Code
2.1.201, claude-sonnet-5, 251 billed trials. *Interest: JetBrains ships a competing AI
coding assistant.*

| Metric | Vendor claim | JetBrains measured |
|---|---|---|
| Code reduction | −54% | **−15.4% median, p=0.088 — not significant** |
| Cost | −20% | **−10.3%, p=0.004 — significant** |
| Quality | — | **"no statistically significant quality difference across 80 tasks — 65 scored identically, 9 slightly worse, 6 slightly better. This is a null result, not a clean bill of health."** |
| Self-activation as optional skill | — | **"zero times. Not rarely. Never."** |

JetBrains: *"Ponytail works. Across 80 paired tasks, it cut the typical bill by 10.3% and
reduced code written by 15%, with no quality difference we could detect."* And: *"It is also
nowhere near 54%."*

An independent **test**, not a replication: different task suite, model, and harness.
JetBrains attribute the gap to task selection — ponytail's suite uses tasks with obvious
over-building traps — consistent with ponytail's own README conceding the effect is "near
zero on code that is already minimal."

**Pros.** Six skills totalling 17,144 bytes — the leanest set in the survey by total weight.
A real vendor benchmark, an independent test confirming a significant cost effect, and a
maintainer who publicly corrected an earlier number under criticism.

**Cons.** The live 54% is ~3.5× the independently measured median and has not been
corrected. The code reduction did not reach significance independently. It does not
self-activate without the hook. Design-system interaction untested — the benchmark repo has
no component library. Its `ponytail:` debt-comment convention was used once across 80
trials. **And its actual adoption is unmeasured**; 117k stars is reach, not use.

**Trade-off.** A measured ~10% cost reduction with no detected quality cost, for ~1.5k
always-on tokens and a headline you cannot take at face value.

---

### 4.4 `caveman` — Julius Brussee

| | |
|---|---|
| Repo | github.com/JuliusBrussee/caveman · MIT skill, BSL-1.1 engine components |
| Reach | 102k stars |
| Weight | ~1–1.5k input tokens added **per turn** |
| Evidence | **A** — the most independently measured tool in the survey (three harnesses) |
| Advertised number | **contradicted** |

**Claim, verbatim, GitHub repo description:** *"why use many token when few token do trick —
Claude Code skill that cuts 65% of tokens by talking like caveman"*. The plugin manifest
adds: *"Cuts 65% of output tokens against an unprompted baseline (measured) while keeping
full technical accuracy."*

**The repo contradicts its own marketing.** From `docs/HONEST-NUMBERS.md`:

| What | Number | How measured |
|---|---|---|
| Output reduction vs default verbose replies | **Not published** | **Harness exists, but repository has no committed reviewed raw result** |
| Input reduction from the skill | 0% | It's an output-style instruction |
| Input cost the skill *adds* | ~1–1.5k tokens per turn | SKILL.md rules injected into context |

**Quality was never measured by the project.** From `evals/README.md`:

> "**Fidelity** — does the compressed answer preserve the technical claims? **A skill that
> replies `k` to everything would score −99% and 'win'.** A future v2 could add a
> judge-model rubric."

`evals/judge.py` and `evals/quality.py` both return 404.

**The baseline problem, named in the repo's own docs:**

> "The honest delta for any skill is `<skill>` vs `__terse__`… Comparing a skill to the
> no-system-prompt baseline conflates the skill with the generic terseness ask, **which is
> what an earlier version of this harness did and is why its numbers were inflated.**"

**Three independent measurements.**

*JetBrains*, 86-task SkillsBench, ~240 billed trials, ~$106: **"Advertised saving: 65%.
Measured saving: 8.5%."** Output tokens 592k → 542k over 82 paired tasks. Quality: 8 better,
10 worse, 64 tied, sign test **p=0.82** — a null result. They forced the skill on in every
reply, so 8.5% is its *best case*.

*Max Taylor*, 24 prompts × 5 arms, blind LLM judge against per-record rubrics. He reports
every arm scoring within 1.5% of every other: baseline 0.985, brief 0.985, caveman lite
0.976, full 0.975, ultra 0.970, with 100% key-point coverage and zero `must_avoid` triggers
across 120 responses. **`"Be brief."` matched baseline at 34% fewer output tokens.** *(My
own caution, not his: at n=24 with arms this close, this design distinguishes large
differences, not small ones. He states no power threshold, and version 2 of this document
wrongly attributed one to him.)*

*THOL leaderboard*, 17 tasks × 10 reps, programmatic verifiers: aggregate cost ratio
**0.9807, CI [0.861, 1.111]** — indistinguishable from doing nothing. On short sessions,
**7% more expensive**. *(THOL is maintained by the author of `tokenade`, a competing tool;
the conflict is declared in its repo, and caveman's row is not one they would gain from
bending.)*

**Pros.** Genuinely candid internal documents. The author conceded on HN: *"The fair
criticism is that my '~75%' README number is from preliminary testing, not a rigorous
benchmark."* Where quality was tested by outsiders, no degradation was detected.

**Cons.** The ~1–1.5k input tokens per turn make it net-negative on terse workloads — issue
#145 reports exactly that. No effect on per-request pricing such as Copilot credits. The
advertised figure is chat-shaped; agent sessions are dominated by code and tool output,
which the skill preserves by design. The 65% claim is still live on the repo description and
marketplace manifest despite the author's concession.

**Trade-off.** ~1–1.5k tokens per turn and a large change in output style, for a measured
~8.5% best-case output reduction that one sentence beats. Use `"Be brief."` instead.

**Sentiment worth recording.** From the caveman launch thread (904 points), *prodigycorp*:
"The burden of proof is on the author to provide at least one type of eval for making that
claim." From the Max Taylor benchmark thread, *oezi*: "Maybe we need a term such as **prompt
homeopathy** to call out prompt engineering without any empirical proof."

---

### 4.5 `andrej-karpathy-skills` — multica-ai

| | |
|---|---|
| Repo | github.com/multica-ai/andrej-karpathy-skills · MIT |
| Reach | 209k stars |
| Weight | One `CLAUDE.md`, 65 lines |
| Evidence | **D** |
| Advertised number | **none** |

**Provenance.** Andrej Karpathy did not write this file and has not endorsed it. He posted
on X about coding-agent failure modes — wrong assumptions run with silently, over-complicated
and bloated abstractions, changing code he does not understand. Those observations were
distilled into four rules and packaged by multica-ai, whose install instructions point at
`forrestchang/andrej-karpathy-skills`.

**The four rules, verbatim:**

1. **Think before coding.** "State your assumptions explicitly. If uncertain, ask."
2. **Simplicity first.** "Minimum code that solves the problem. Nothing speculative… If you
   write 200 lines and it could be 50, rewrite it."
3. **Surgical changes.** "Touch only what you must… Every changed line should trace directly
   to the user's request."
4. **Goal-driven execution.** "Define success criteria. Loop until verified."

**Evidence.** None. No benchmark, no eval, no test directory. The file states its own
trade-off: "These guidelines bias toward caution over speed. For trivial tasks, use
judgment."

**The circulating "41% → 11% error reduction" figure is unsourced.** It headlines
`aibuilderclub.com/blog/karpathy-claude-md-rules`. I opened it: the number appears only in
the title and meta description, with no methodology, sample size, task set, or definition of
"error" in the body. Do not repeat it. **Note that the figure is not the repo's — the repo
makes no numeric claim.**

**Pros.** Sixty-five lines. Rule 4 has independent backing: Self-Debug (ICLR 2024) measured
**+2–3%** improvement without unit tests versus **up to +12%** with them, in the same
system — the execution signal does the work. Rule 2 targets over-building, which ponytail's
independent test confirms is real and reducible.

**Cons.** Rules 1 and 4 appear to overlap `lv1-coder` and your `plan-reviewer`. That is my
reading of their stated purposes, not a measured claim, **and I have no measured cost for
that overlap either** — §3's 24.1pp figure prices irrelevant instructions, not duplicated
ones. What §3 does support is that adding relevant rules lowers all-at-once compliance while
leaving per-rule compliance roughly unchanged.

**Trade-off.** Note the awkwardness honestly: the two rules I suggest taking (2, 3) are
**unmeasured**, and the rule with the best independent backing (4) is the one I suggest
dropping as a duplicate. That is a judgement about your existing setup, not a claim rule 4
is weak. If you did *not* already run a verification loop, rule 4 would be the one to take
first.

---

### 4.6 `pstack` — Lauren Tan (Cursor)

| | |
|---|---|
| Repo | github.com/cursor/plugins/tree/main/pstack · MIT · v0.14.5 |
| Reach | **No pstack-specific star count exists.** `cursor/plugins` has 6.2k stars across many plugins. The Claude port `michael-denyer/pstack-claude` has 138. |
| Weight | **48 `SKILL.md`** (21 `principle-*`), 23 playbooks, ~58k tokens of skill bodies, **~3,200 tokens of always-on descriptions** |
| Evidence | **D** |
| Advertised number | **none** |

**Claim, verbatim:**

> "pstack is my answer. these are the same skills i use everyday to ship high quality code at
> Cursor. this turns cursor into a real engineering team… pstack gives you fearless
> parallelism."

**Evidence.** None. No `eval/`, no `benchmark/`, no `test/` directory. There *is* an `eval`
playbook — a tool telling *the user* how to run blinded evals on their own skill changes.
A feature, not evidence.

**Pros.** Lauren Tan's credentials are real (React core team, now Cursor), and the skills are
visibly carefully written. The `principle-*` decomposition is a genuinely interesting design.
Makes no numeric claim.

**Cons.** *It is a Cursor plugin*, native to Cursor's monorepo, not Claude Code; the Claude
port's README says "This is not a verbatim copy", and whether it behaves equivalently is
unverified. *Heaviest always-on cost in the survey* — ~3,200 tokens before any work starts,
roughly **2.3×** superpowers' ~1,390. (Version 1 said 5×, comparing against superpowers'
descriptions while ignoring its hook.) *Zero independent evidence*: no HN presence at all,
and the most-cited write-up — Flavio Copes' "deep dive" — is a documentation review with
conditional statements ("I *would* use pstack for work where…") and no benchmarks.

**Trade-off.** The strongest qualitative claims in the survey, the heaviest fixed context
cost, no measurement of any kind. Copes' own criticism is the fair summary: *"The machinery
has a cost. pstack can start several agents for one task. If they all use frontier models,
the tokens add up fast."*

---

### 4.7 The heavyweight frameworks

| Tool | Stars | Verified monthly downloads (30 Aug 2026) | Weight | Evidence | Advertised number |
|---|---|---|---|---|---|
| `ruvnet/claude-flow` | 70k | `@claude-flow/cli` **193,076**; `claude-flow` **75,395** | 359 skills, ~1.5M tokens | **D** | **unbacked** |
| `BMAD-METHOD` | 52k | `bmad-method` **80,763** | 59 skills, ~218k tokens | **D** | none |
| `wshobson/agents` | 39k | none published | 181 skills, ~934k tokens | **D** | none |
| `SuperClaude_Framework` | 24k | not retrievable (PyPI rate-limited) | ~152k tokens | **D** | none |

*Weight figures are library totals. I did not compute per-skill length for these, so I
cannot place them in SkillsBench's verbosity buckets — see §3.*

**`claude-flow`.** *Pros:* the only tool publishing reproducible benchmark artifacts — a
benchmark script, a workload spec, raw matrix JSON — and the largest verified usage figure
in this survey (193k monthly downloads of its CLI package). Its vector-memory numbers are
qualified and directional, which is good practice. *Cons:* what it benchmarks is **runtime
performance**, not code quality, which is why it scores D on the evidence column despite
having the artifacts. The headline "ruflo wins cold start, single turn, RSS by 1.3×–1953×" is
a process-startup comparison against orchestration libraries. Its "intelligent routing (89%
accuracy)" claim has no linked method, dataset, or artifact — hence **unbacked**. Independent
assessment (rywalker.com) notes the signature claims "lack independent third-party
validation" and "production case studies remain anecdotal"; engineer Steven Gonsalvez, quoted
there: *"If you need one agent to fix a bug, it's massive overkill."* *Trade-off:* the
largest, best-instrumented framework in the field, measuring the one thing that does not tell
you whether your software got better.

**`BMAD-METHOD`.** *Pros:* real adoption (80,763 monthly npm downloads — more than
`claude-flow`'s own base package), a stated "right-sized process" philosophy that lets you
skip planning for clear changes, and `test/adversarial-review-tests/`, the closest thing to a
skill-behaviour test in this tier. *Cons:* that test is manual and qualitative, covers one
input to one skill, and produces no numbers. The rest of `test/` is tooling tests — its own
README: "Tests for the BMAD-METHOD tooling infrastructure." Zero substantive HN discussion
(best post: 4 points, 0 comments). *Trade-off:* the adoption is real and the evidence is
absent; you would be buying 59 skills on other people's satisfaction.

**`wshobson/agents`.** *Pros:* **the only project here that built machinery capable of
falsifying its own claims.** `plugins/plugin-eval/` is a real Python package with Elo
ratings, Monte Carlo reliability simulation over 50–100 runs, an LLM judge, and its own
pytest suite. *Cons:* it publishes no scores, so infrastructure is all there is; and it
measures plugin quality and triggering rather than software outcomes. "Production-ready"
remains a bare assertion. *Trade-off:* the best-designed measurement apparatus in the
ecosystem, with nothing measured, and 181 skills of cost for it.

**`SuperClaude_Framework`.** *Pros:* the shipped plugin directory contains exactly 30
commands and 20 agents, matching its advertised counts — version 1 of this document claimed
otherwise and was wrong. *Cons:* its own README warns *"The TypeScript plugin system
described in older documentation is not yet available (planned for v5.0)"* — its docs
describe features that do not exist. Its `tests/` directory holds 14 files covering
confidence, parallelism, reflection, self-check, token budget and an execution engine; only
one is an installer test. None measures efficacy. No quality independent reports; best HN
post is 6 points, 0 comments. *Trade-off:* ~152k tokens for a system whose documentation you
cannot trust to describe the system.

**The shared point, at its correct strength.** SkillsBench v4 does **not** find large bundles
harmful — ≥4 skills gained +10.1pp. What it finds is that compact and standard-length skills
gain more (+19.0 and +21.5pp) while comprehensive documentation gains almost nothing (+0.7pp)
— **per skill, per task**. Whether these frameworks' individual skills are comprehensive, I
did not measure. The defensible conclusion is narrower than version 1's: **none of these has
measured its own effect, all cost far more context than a small set, and the benchmark gives
no reason to expect a large bundle to outperform a small one.** Not: they will make your
agent worse.

---

### 4.8 `github/spec-kit`

| | |
|---|---|
| Repo | github.com/github/spec-kit · MIT · v1.0.0 |
| Reach | 132k stars |
| Use | **113,709 PyPI downloads last month** (`specify-cli`, verified 30 Aug 2026) |
| Weight | 36 commands, ~130k tokens of material |
| Evidence | **D** |
| Advertised number | **none** |

**Claim, verbatim:** *"specifications become executable, directly generating working
implementations rather than just guiding them."*

**Why it is worth reading despite grade D.** It has a section titled "🎯 Experimental Goals"
containing:

> "Validate the hypothesis that Spec-Driven Development is a process not tied to specific
> technologies, programming languages, or frameworks"

**It frames its own central claim as an unvalidated hypothesis.** No other tool here adopts
that posture.

**Pros.** Real, verified adoption. The only tool with sustained named third-party analytical
coverage — Martin Fowler's site ran a comparative piece (128 HN points, 32 comments).

**Cons.** ~130k tokens. Named by Pocock as process-owning ceremony: *"they take away your
control and make bugs in the process hard to resolve."* Whether specifications actually
become executable is unverified — and the project says so.

**Trade-off.** Read it, take the spec structure, install nothing. Your `specs-builder` and
`specs-reviewer` already occupy that stage.

---

### 4.9 `humanlayer/advanced-context-engineering-for-coding-agents`

| | |
|---|---|
| Repo | github.com/humanlayer/advanced-context-engineering-for-coding-agents |
| Reach | 2.6k stars — lowest of the installable-or-influential entries |
| Weight | **5 markdown documents.** Nothing to install. |
| Evidence | **C** |
| Advertised number | **unbacked** |

Not a skills system. A methodology writeup, "frequent intentional compaction" (ACE-FCA).

**Claim, verbatim:**

> "We've gotten claude code to handle 300k LOC Rust codebases, ship a week's worth of work in
> a day, and maintain code quality that passes expert review."

**Why it earns C where most earn D.** The claims attach to specific,
third-party-inspectable artifacts: four named PRs against BoundaryML/baml, a codebase the
authors do not own. Anyone can check whether they merged. *(Caveat: GitHub HTML was blocked
from the research sandbox, so the citation is checkable, not checked.)*

More importantly, the repo runs the technique against **SlopCodeBench**, an independent
academic benchmark it did not build, and reports a result bad for the hype:

> "Opus 5 got a 24% on the small subset of the benchmark that I ran — not much higher than
> Opus 4.6's 17% strict pass rate in the original paper."

> "for real-shaped software engineering work, building one issue at a time, today's models
> can't be relied on to run lights-off without steering."

**Pros.** The only entry that ran an independent benchmark and published an unflattering
number. States its methodology limits plainly: "i had claude pick out 3 problems from the
repo, 17 checkpoints total". Zero install cost.

**Cons.** Tiny adoption. Nothing installable, so nothing to A/B. The productivity claims rest
on four PRs by the technique's own authors — anecdote in one codebase. The document reports
both 24% and 23% for the same run.

**Trade-off.** No install cost and no measurable effect to claim. Read it for the compaction
discipline, close to what your Artifact Reference Injection already does.

---

### 4.10 Short entries

**`buildermethods/agent-os`** — 5.3k stars, MIT, ~12k tokens across 12 agent files, zero
`SKILL.md`. **Evidence D · Advertised number: none.** *Pros:* the lightest thing in the
survey by token weight; claims "Any language, any framework" without a numeric claim.
*Cons:* no eval, no benchmark, no test directory; the README functions largely as a funnel to
a newsletter, YouTube, and a paid community; no independent reports found. *Trade-off:*
almost free to try, with nothing to tell you whether it did anything.

**`GWUDCAP/cc-sessions`** — 1.6k stars, **102 npm downloads last month** (verified).
**Evidence D · Advertised number: none** — its strapline "it's basically autopilot" is not a
number. *Pros:* small, and honest about being opinionated. *Cons:* its evidence is two
testimonial screenshots; its README carries a Solana donation badge linking to dexscreener.
*Trade-off:* no upside case I can source.

**`disler/infinite-agentic-loop`** — 613 stars, one slash command. **Evidence D · Advertised
number: none.** *Pros:* honest about what it is — *"An experimental project demonstrating
Infinite Agentic Loop in a two prompt system using Claude Code."* *Cons:* a demo, not a
system; it appears on "top frameworks" listicles purely as an SEO artifact. *Trade-off:*
none to make — it is not competing for the slot.

---

### 4.11 The rest of the compression class

These three sit in §1's Avoid tier and earn the same treatment as the tools above.

**`rtk`** (rtk-ai/rtk, Apache-2.0, 78k stars). Claims *"60-90%"* reduction on dev commands.
**Evidence A · Advertised number: contradicted.** *Pros:* unusually honest scoping in its own
README — it states that bash output is one contributor to input tokens and that "the
percentages are reliable but the absolute token numbers are approximate". *Cons:* JetBrains
measured it **+7.6% more expensive at low reasoning effort (p=0.004)** and **+0.1% at high
effort (p=0.99)**, with task quality unchanged at both. Their pre-analysis found rtk's hook
touches ~33% of Bash calls carrying under 20% of tool-result characters, capping its
theoretical reach at ~3% of input tokens. A still-open issue on the repo asks for the README
to be updated. *Trade-off:* an accurate component ratio advertised as a session saving; the
component is too small a share to matter.

**`headroom`** (headroomlabs-ai/headroom, Apache-2.0, 68k stars). Claims *"60–95% fewer
tokens (for JSON data), 15-20% fewer tokens (for coding agents)"*. **Evidence A · Advertised
number: contradicted.** *Pros:* the only compression tool shipping accuracy benchmarks
alongside compression numbers (GSM8K, TruthfulQA, SQuAD, BFCL at N=100 each) with a runnable
reproduce command. *Cons:* those accuracy benchmarks are single-turn QA, not the agent tool
output the savings table measures — nothing links the two. THOL measured it at **1.557× cost,
CI [1.301, 1.898]**, last place and entirely above 1; its token breakdown shows fresh input
tokens of 244k against a control's 34.5k, consistent with a rewriting proxy destroying the
provider's cache prefix. *Trade-off:* the best accuracy instrumentation in the class,
attached to the worst measured end-to-end result.

**`lean-ctx`** (yvgude/lean-ctx, 3.7k stars). Claims *"60–90% fewer tokens"*. **Evidence A ·
Advertised number: contradicted.** *Pros:* none I can source beyond the claim itself. *Cons:*
THOL measured **1.234× cost, CI [1.042, 1.456]** — ~23% more expensive, interval entirely
above 1. *Trade-off:* there is no upside case in the evidence I found.

*All three THOL figures come from a leaderboard maintained by the author of `tokenade`, a
competing tool. The conflict is declared in the repo, which publishes raw run data and an
impartiality charter. Weight accordingly; the direction is corroborated by JetBrains for rtk.*

---

## 5. Cross-cutting patterns

**1. Advertised numbers are component ratios. Measured numbers are end-to-end.**

| Tool | Advertised | Independently measured |
|---|---|---|
| caveman | 65% token cut | **8.5%** (JetBrains) |
| ponytail | −54% code, −20% cost | **−15.4% code (p=0.088, ns); −10.3% cost (p=0.004)** |
| rtk | 60–90% | **+7.6% cost at low reasoning effort (p=0.004); +0.1% at high (p=0.99)** |
| headroom | 60–95% | **+56% cost**, CI [1.301, 1.898] (THOL) |
| lean-ctx | 60–90% | **+23% cost**, CI [1.042, 1.456] (THOL) |

A positive percentage in the right column means the arm cost *more* than doing nothing.

The pattern is mechanical rather than dishonest. Compressing one input class by 90% moves
the total bill by a few percent, because that class is a small share of a session. Read every
claim as "of the thing we compress", not "of your bill".

**2. No degradation has been detected where anyone looked — and these are null results.**

JetBrains found p=0.82 on caveman across 82 pairs, and called their ponytail quality finding
"a null result, not a clean bill of health". Max Taylor's arms all landed within 1.5% of each
other at n=24. The correct reading is **absence of detected harm at these sample sizes**, not
demonstrated safety. Same class of statistic as the AGENTS.md null result in §3, deserving
the same restraint — including in §1's Avoid tier, which is why that tier says "independent
tests detected no quality difference" rather than "found no quality loss".

**3. Triggering is the ecosystem's weak joint.** Superpowers' own evals show over-triggering
on trivial tasks, unresolved since May. JetBrains showed ponytail self-activates *zero* times
without a hook. Pocock's own docs report a skill that names another skill failing to load it.
SkillsBench found some harnesses "acknowledge Skills content but proceed without invoking
it." Whichever tool you pick, verify it is firing before you evaluate whether it helps.

**4. Adoption in this ecosystem cannot be measured consistently.** Stars are a virality
measure. Marketplace install counts I found were unsourced and contradicted each other
between services, so they are absent from this report. Only npm and PyPI figures are
verifiable, covering only the subset of tools shipping through those registries. For
`superpowers`, `ponytail`, `mattpocock/skills` and `caveman` — four of the most-discussed
tools here — **I have no trustworthy usage figure at all.**

---

## 6. What this means for `ai-framework`

**Your six skills are heavier than any tool in this survey that measures well.** 115,901
bytes across six files, against ponytail's 17,144 across six and superpowers' ~2.5k tokens
per skill. `implementation-planner` alone (33,977 bytes) is twice ponytail's entire set.

I cannot tell you that is bad. SkillsBench publishes no byte thresholds, its buckets grade
per-skill-per-task rather than libraries, and its software-engineering domain gains the
second-least of eight. But it is the one place where your setup sits at the opposite end of
the distribution from the tools with the best measured results, and it is cheap to test:
trim the two largest, run your normal work, see whether anything degrades.

**Your Bimodal Gating is supported at the front gate and unsupported in the middle.** The
front gate — human attention on the test contract before implementation — is backed by the
overfitting result (21.8%, rising to 25.5% under joint refinement). Delegating the middle to
agents has no evidence I found. Self-Debug compares feedback signals inside an autonomous
loop; it says nothing about where human attention should be spent. Version 2 cited it for
that and was overreaching.

**Do not misread the self-generated-skills finding.** SkillsBench measured skills the *model*
wrote cold, before the task, scoring −8.1 to −11.5pp. Your skills are hand-written and
audit-revised. That finding does not apply, and I flag it because it is the sort of number
that gets quoted at people who write their own skills.

**Your Delta-Only Verification and Artifact Reference Injection reduce irrelevant context.**
That is the one context effect with a clean per-constraint measurement behind it: 24.1pp lost
to 16 injected irrelevant instructions. This is the correct use of that number — irrelevant
material, not duplicated material.

**Your Circuit Breaker has no direct evidence.** Halting after two consecutive verification
failures caps the joint code-and-test refinement loop IBM measured. The sourced size of that
benefit is at most 3.7pp. I found no study of retry limits specifically. Indirect support.

**Multi-Tier Orchestration — what I can and cannot tell you.**

The controlled comparison (arXiv:2606.05670) normalised the harness across single-agent and
six multi-agent systems. **Five of the six trailed a matched single agent by 2.56 to 11.29
points, at higher cost.** That is the solid finding, and it argues for fewer agents, not for
a particular dispatch shape.

Anthropic's 90.2% multi-agent figure is on an undisclosed internal *research* eval.
Separately, its variance decomposition — token usage explaining 80% of performance variance —
is from the BrowseComp evaluation, not from the run that produced 90.2%. Version 1 joined
those incorrectly.

**On context-sharing versus isolated-context dispatch, I have to withdraw the claim version 2
made.** That distinction rested on a 66.72% GAIA result from the same paper. GAIA is a
general-assistant benchmark, and I discount Anthropic's result for being non-coding;
consistency requires me to discount this one too. Once discounted, the discriminator has
nothing behind it but Cognition's essay, which contains no data. **So: the evidence supports
"fewer agents", and does not establish that context-sharing is what makes the difference.**

**The concrete action, at the strength the evidence actually supports:** count how many of
your dispatches run in parallel on interdependent work. Each one is a place where the
five-of-six result predicts you are paying more for less. Converting them to sequential is a
reasonable experiment. The mechanism I offered in version 2 — conflicting implicit decisions
from isolated context — is Cognition's hypothesis, not a finding.

**Your CONTEXT.md holds 21 defined terms.** The growth research measured a median context
file at 39 instructions, +226% growth over its lifetime, and 77.3% of instruction deaths
arriving as wholesale rewrites or migrations rather than considered deletions. Your audit
convention — promote durable rationale into the skill, then clear the audit file — is a
deliberate pruning mechanism. Keep it.

**On the project-management half.** No tool in this survey was built or measured for project
management. SkillsBench's software-engineering figure (+11.6pp) does not transfer, and no
benchmark covers PM work. I have not read the `product-management` skills in your session and
make no claim about them. **The PM recommendation in §1 is spec-kit's framing only, resting
on a hypothesis its own authors have not validated.** If you want an evidence-backed PM tool,
none exists.

---

## 7. What nobody has measured

- **Whether any skill or plugin improves software outcomes.** No tool author has measured
  this. Two tools have been independently tested for *harm* and showed none, at sample sizes
  that can only rule out large effects.
- **Whether installed library size matters, as opposed to skills-per-task** — and whether
  library bulk maps to per-skill verbosity at all. Both gaps in §3. Unbridged.
- **The cost of duplicated rules.** Priced nowhere. §3's 24.1pp is about irrelevant rules.
- **Anything outside Python.** The AGENTS.md paper names this as its first limitation.
  SkillsBench's software tasks are single-file. Your work spans a WMS OpenAPI surface, FastMCP
  servers, and local report servers — none of that shape appears in any benchmark here.
- **Code quality, security, review burden, or convention adherence.** Every quantitative
  result in this evidence base is task success, token cost, or constraint satisfaction.
- **Context-file size versus coding performance.** The AGENTS.md paper found *no correlation*
  between context-file length and resolution rate.
- **Retry limits and circuit breakers.** No study found.
- **Actual adoption of the four most-discussed tools here.** See §5 pattern 4.
- **A cheap way for you to measure any of this.** Ten-pair trials catch only large effects.
  JetBrains spent 251 billed trials to reach p=0.004 on one number.

**Numbers you will see quoted that you should not repeat:**

- *"41% → 11% error reduction from the Karpathy rules."* Unsourced; the article headlining it
  states no methodology, and the figure is not the repo's.
- *"Studies prove CLAUDE.md files hurt performance."* Every success comparison is
  non-significant. Null result plus cost penalty.
- *"Comprehensive skills hurt performance by 2.9pp."* That is SkillsBench **v1**. v4 measures
  **+0.7pp**. Version 1 of this document made exactly this error.
- *"TDD gets agents to 88.8% on SWE-bench."* Only when handed human-written tests.
- *"Multi-agent systems are 90.2% better."* Undisclosed eval, undisclosed n, research not
  coding.
- *"Context rot causes an X% drop at Y tokens."* Chroma published charts without stated
  numerical deltas; any precise percentage was invented downstream. Use NoLiMa (ICML 2025):
  11 of 13 models below half their short-context baseline at 32K; GPT-4o 99.3% → 69.7%.
- *"Lost in the Middle shows long context degrades performance."* It shows *positional*
  sensitivity, on 2023-era models.

---

## 8. Sources

**Peer-reviewed at a main venue**

- NoLiMa: Long-Context Evaluation Beyond Literal Matching — ICML 2025 — https://arxiv.org/abs/2502.05167
- Lost in the Middle: How Language Models Use Long Contexts — TACL 2023 — https://arxiv.org/abs/2307.03172
- FollowBench: A Multi-level Fine-grained Constraints Following Benchmark — ACL 2024 — https://arxiv.org/abs/2310.20410
- TDFlow: Agentic Workflows for Test Driven Development — EACL 2026 — https://arxiv.org/abs/2510.23761
- Teaching Large Language Models to Self-Debug — ICLR 2024 — https://arxiv.org/abs/2304.05128

**Workshop-reviewed**

- WildIFEval: Instruction Following in the Wild — GEM @ ACL 2026 — https://arxiv.org/abs/2503.06573

**Preprints (no venue confirmed against a primary source)**

- SkillsBench — https://arxiv.org/abs/2602.12670 (v4 cited: https://arxiv.org/html/2602.12670v4)
- Evaluating AGENTS.md — https://arxiv.org/abs/2602.11988
- Why Does CLAUDE.md Keep Growing? Catastrophic Remembering in Agentic Coding — https://arxiv.org/abs/2608.11095
- Investigating Test Overfitting on SWE-bench — https://arxiv.org/abs/2511.16858
- Do More Agents Help? Controlled and Protocol-Aligned Evaluation of LLM Agent Workflows — https://arxiv.org/abs/2606.05670
- When Single-Agent with Skills Replace Multi-Agent Systems and When They Fail — https://arxiv.org/abs/2601.04748

**Vendor and industry — interests noted**

- Anthropic, How we built our multi-agent research system — https://www.anthropic.com/engineering/multi-agent-research-system *(sells agent orchestration)*
- Cognition, Don't Build Multi-Agents — https://cognition.com/blog/dont-build-multi-agents *(sells a coding agent; contains no quantitative data)*
- Chroma, Context Rot — https://research.trychroma.com/context-rot *(sells retrieval, the alternative to long context)*

**Independent tool measurement**

- JetBrains, caveman tested — https://blog.jetbrains.com/ai/2026/07/speak-to-ai-agents-like-cavemen-tosave-tokens/ *(JetBrains ships a competing AI coding assistant)*
- JetBrains, ponytail tested — https://blog.jetbrains.com/ai/2026/07/ponytail-skill-claude-tested/ *(same interest)*
- JetBrains, rtk tested — https://blog.jetbrains.com/ai/2026/07/rtk-claude-code-token-savings/ *(same interest)*
- Max Taylor, caveman vs two words — https://www.maxtaylor.me/articles/i-benchmarked-caveman-against-two-words
- THOL leaderboard — https://github.com/pi-infected/token-harness-optimizer-leaderboard *(maintained by the author of `tokenade`, one of the measured tools; conflict declared in the repo, raw run data published)*
- Ryan Walker, claude-flow research — https://rywalker.com/research/claude-flow

**The unsourced claim criticised in §4.5**

- https://www.aibuilderclub.com/blog/karpathy-claude-md-rules

**Measurements I made myself, 30 August 2026**

- Your six `SKILL.md` files, byte sizes, read from `ai-first-fw/skills/` on your disk
- `api.npmjs.org/downloads/point/last-month/` for `@claude-flow/cli` (193,076), `claude-flow` (75,395), `bmad-method` (80,763), `cc-sessions` (102)
- `pypistats.org/api/packages/specify-cli/recent` (113,709 last month)
- `img.shields.io/github/stars/<repo>.json` for all star counts

**Tool repositories**

- https://github.com/mattpocock/skills
- https://github.com/obra/superpowers · https://github.com/prime-radiant-inc/superpowers-evals
- https://github.com/DietrichGebert/ponytail
- https://github.com/JuliusBrussee/caveman
- https://github.com/multica-ai/andrej-karpathy-skills
- https://github.com/cursor/plugins/tree/main/pstack · https://github.com/michael-denyer/pstack-claude
- https://github.com/bmad-code-org/BMAD-METHOD
- https://github.com/github/spec-kit
- https://github.com/ruvnet/claude-flow
- https://github.com/wshobson/agents
- https://github.com/SuperClaude-Org/SuperClaude_Framework
- https://github.com/buildermethods/agent-os
- https://github.com/GWUDCAP/cc-sessions
- https://github.com/humanlayer/advanced-context-engineering-for-coding-agents
- https://github.com/rtk-ai/rtk · https://github.com/headroomlabs-ai/headroom · https://github.com/yvgude/lean-ctx

**Discussion threads read in full**

- HN 47623101 (superpowers) · 47040430 (SkillsBench) · 47647455 and 47650509 (caveman launch
  and author reply) · 47954745 (Max Taylor benchmark)

**Treated as indexing evidence only, never cited for effectiveness:** claudedirectory.org,
claudepluginhub.com, claudeskills.info, skillsmp.com, mindstudio.ai, aiagentstore.ai,
explainx.ai, topgit.dev, mcp.directory.

---

## Appendix: what earlier versions got wrong

Listed because the report's own standard demands it.

**Version 1 → 2 (20 defects).** SkillsBench version mixing: quoted the v4 abstract, used v1
body numbers, making software engineering +4.5pp instead of +11.6pp, comprehensive skills
−2.9pp instead of +0.7pp, the count bands +18.6/+5.9 instead of +19.0/+10.1, and
self-generated skills −1.3pp instead of −8.1 to −11.5pp. This inverted the sign of the
finding the lead recommendation rested on, and the claim "size is negatively correlated with
success" was withdrawn entirely. Unsourced marketplace install counts (1,745 / 1,009,371)
were presented as the report's most reliable metric and removed. A `claude-flow` download
figure was attributed to the wrong package. The A–F rubric conflated evidence quality with
headline honesty, producing an F for the best-measured tool. "The highest grades in this
report" was applied to a C/B entry in a report containing an A. `mattpocock/skills` and
humanlayer were absent from the recommendations despite being asked about and best-graded.
The skill-count threshold was applied inconsistently across tools. The per-task-to-installed
inference was never disclosed. TDFlow was said to match a human-approval gate "exactly".
`lean-ctx` carried an Avoid verdict with no evidence. Null results were read as positive
findings in §5 while correctly refused in §3. Ponytail's inflation was stated three
incompatible ways. Seven of fourteen tools lacked pros/cons/trade-off. Misquotes and
misattributions: the SkillsBench pretraining sentence, ponytail's correction quote, JetBrains'
ponytail quality finding, the `oezi` comment's thread, superpowers' release-note hedge,
Anthropic's two separate evaluations, the catastrophic-remembering deletion statistic, rtk's
reasoning-effort condition. Miscounts: pstack skills, humanlayer documents and PRs,
SuperClaude commands and agents, the Karpathy file's line span, pstack's always-on multiple.
An unverified venue was asserted for the AGENTS.md paper.

**Version 2 → 3 (8 defects).**

1. **A methodological caveat was attributed to Max Taylor that he never wrote** — a "noise
   floor" and "stated power threshold" at n=24 appear nowhere in his article. The caution is
   sound; it is now labelled as mine. A score of "0.9854" was also supplied; he reports 0.985.
2. **"Best-evidenced entry in the survey"** was applied to a C-graded entry in a report
   awarding two A's. The superlative is gone.
3. **The Advertised-number column's marks overlapped by definition** and tracked maintainer
   contrition rather than the number. Redefined as none / unbacked / contradicted, mutually
   exclusive. Ponytail moved from ~ to contradicted: its corrected figure was the superseded
   80–94%, not the live 54%. SuperClaude and cc-sessions moved off ✗, having no contradicted
   number.
4. **The per-task/installed conflation was moved onto the verbosity axis** rather than
   removed, and applied to library totals with no caveat. §3's gap now covers both ablations
   explicitly, and §4.7 states I did not compute per-skill length for the frameworks.
5. **"Your six skills are compact" was asserted without measurement.** Measured: 115,901
   bytes. They are not. Recommendation 1 reversed.
6. **Duplication was priced at 24.1pp** using a study of *irrelevant* instructions.
   Withdrawn in all three places; duplication is now listed in §7 as unmeasured.
7. **A ten-pair trial protocol** was prescribed without saying it cannot detect these
   effects, applied code metrics to prose skills, and gave the Adopt-tier trial no
   measurement at all. All three fixed.
8. **The GAIA result was declared discounted and then relied on** for the
   context-sharing-versus-isolated fork and the action it licensed. The claim is withdrawn;
   §6 now supports only "fewer agents".

Also corrected in v3: `claude-flow` regraded D (it benchmarks runtime, not outcomes);
SuperClaude's `tests/` described accurately; standard-length skills' +21.5pp restored as the
higher figure; the 3.5× code discount dropped as derived from a non-significant estimate;
§1's Avoid tier reworded from "found no quality loss" to a null-result phrasing; THOL's
conflict disclosed inline; `rtk`, `headroom` and `lean-ctx` given a full section; the IBM
gate benefit netted at 3.7pp; humanlayer's document count fixed in §1; pstack's 48 skills
fixed throughout.
