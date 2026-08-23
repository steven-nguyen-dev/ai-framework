# mattpocock-skills:code-review — audit 2026-08-23

Scope: `skills/engineering/code-review/SKILL.md` (87 lines, plugin `mattpocock-skills` 1.2.3), read against
the plugin's own `writing-for-agents` standard, its sibling skills, its `CHANGELOG.md`, and its published
doc `docs/engineering/code-review.md`. Filename carries the plugin qualifier so it never collides with
audits of this workspace's own `code-reviewer`.

**Verdict.** The two-axis design is sound and worth keeping — the separation argument (skill §*Why two
axes*) is the skill's real asset. The failures are all in the machinery around it: the run is unbounded
(F1), the parallelism it advertises has no mechanism left in the file (F2), and its largest reference block
sits in the wrong tier and is re-transcribed by hand every run (F4). Three findings are contradictions
between the skill and its own shipped documentation, which makes them cheap to argue and cheap to fix.

| # | Finding | Severity | Fix cost |
|---|---|---|---|
| F1 | Sub-agent briefs permit delegation — unbounded fan-out | **critical** | 2 lines |
| F2 | "Parallel" carries no dispatch instruction after PR #781 | high | 1 line |
| F3 | Frontmatter advertises WIP review; the diff command excludes it | high | 1 line + gate |
| F4 | Smell baseline is in-file reference, pasted by hand into the brief | high | new file + 1 line |
| F5 | `refactoring.md` promised by CHANGELOG #464, absent from the tree | medium | fold into F4 |
| F6 | Hardcoded `docs/agents/issue-tracker.md` — the bug #472 fixed in wayfinder | medium | 2 lines |
| F7 | 400-word cap with no drop rule — silent truncation | medium | 1 clause |
| F8 | Steps 2–5 carry no completion criteria | medium | 4 lines |
| F9 | No diff-size gate — a large diff returns a partial review that reads clean | medium | 1 gate |
| F10 | Step 2 ranks an inferred issue ref above the user's own argument | low | reorder |
| F11 | The two-axis rule stated three times, twice as negation | low | prune |

---

## F1 — the briefs permit delegation, so the run has no ceiling

Step 4 hands each sub-agent a brief that says what to report and nothing about how to get there. A
sub-agent that greps for how this repo reviews code rediscovers the skill and fires it again; each new
invocation reaches step 4 and spawns two more.

This is not hypothetical. The skill's own published doc carries it as a known open bug:

> **Its sub-agents keep invoking `/code-review` again and spawn more agents.** Known open bug, reproduced
> by several people and in more than one harness. […] one report reached 50-plus agents. […] Neither is in
> the shipped skill yet. If you run this unattended, watch the agent count. — `docs/engineering/code-review.md`

A documented bug with a known one-line fix, shipping unfixed, is the whole finding. Everything else in this
audit is a cost; this one is a runaway.

**Fix — one line in each brief, positive first.** `writing-for-agents` (§Leading words) is explicit that
prohibition drags the banned behaviour into context, and that a ban earns its place only as a hard
guardrail *paired* with the positive target. Both halves, in that order:

> "Perform this review yourself, in this context — read the files and run git directly; you are the only
> agent on this axis. Do not invoke `/code-review` or spawn further agents."

## F2 — the parallelism has no mechanism left in the file

The frontmatter sells "Runs both reviews in parallel sub-agents"; the preamble repeats it; step 4 is titled
"Spawn both sub-agents in parallel" — and then never says how. CHANGELOG #781 is why:

> Drop Claude Code's tool and agent-type names from the subagent-dispatch instructions in `code-review`,
> `codebase-design` and `improve-codebase-architecture`, so the step is followable on Codex and other harnesses.

Harness-agnostic was the right call; it removed the only sentence that made *parallel* real. What is left is
a word, and an agent that dispatches one brief, reads its report, then composes the second satisfies every
literal instruction in the step.

The cost is not only wall-clock. Composing the Spec brief with the Standards report already in context is
exactly the cross-contamination the two-axis separation exists to prevent — the aggregator is the one
context both axes meet in, and sequential dispatch lets the first report reach the second brief.

**Fix — name the ordering, not the tool.** Replace the step's opening with a dispatch bound that any harness
can satisfy: *dispatch both briefs before reading either report.* No tool name, and the failure mode is now
observable.

## F3 — the description advertises a review the diff command cannot perform

Frontmatter: "Use when the user wants to review a branch, a PR, **work-in-progress changes**, or asks to
'review since X'." Step 1: `git diff <fixed-point>...HEAD`, three-dot, measured from the merge-base —
staged and working-tree changes are invisible to it. The published doc confirms the mechanics and
contradicts the pointer:

> **Does it review my uncommitted work?** No. It diffs `<fixed-point>...HEAD`, three-dot […] If `implement`
> has not made an interim commit, the work about to be committed is invisible to the review.

So the trigger most likely to fire on a half-finished branch is the one the skill silently cannot serve —
and step 1's only gate (`diff` non-empty) passes happily on a branch whose real change is all uncommitted.
The user gets a review of the last commit and believes they got a review of their work.

**Fix — one gate, one honest pointer.** Add `git status --porcelain` to step 1: when it returns anything,
name the uncommitted files and ask whether to commit first or review the committed diff only. Then either
keep "work-in-progress changes" in the description (now true, because the skill handles the case) or drop
the branch. Keeping the pointer and not handling the case is the one combination to avoid.

## F4 — the smell baseline sits one rung too high, and is copied by hand

The twelve-smell baseline (skill §3) is 376 words of flat reference in a 1,043-word file — better than a
third of it. Two things are wrong with where it lives:

**It loads on every run, and only one branch reads it.** `writing-for-agents` §Information hierarchy puts
this case plainly: *inline what every branch needs, and push behind a pointer what only some branches
reach.* Exactly one of two axes consumes the baseline. A spec-only run — the user says there is no
documented standard, or asks only whether the change matches the ticket — pays for all twelve smells and
uses none. Every sibling skill with a reference block of this size has already made the move:
`tdd/tests.md`, `tdd/mocking.md`, `triage/AGENT-BRIEF.md`, `codebase-design/DEEPENING.md`,
`domain-modeling/ADR-FORMAT.md` — and every one of them holds a smaller `SKILL.md` than this one for having
made it (tdd 551 words, prototype 482, codebase-design 830, triage 975, against code-review's 1,043 with no
reference file at all).

**It is transcribed at run time.** Step 4 says: *"plus the smell baseline from step 3 **pasted in full** —
the sub-agent has no other access to it."* That parenthetical is the tell — the mechanism is a manual copy
of 376 words, and the paste is where a smell quietly goes missing or gets paraphrased into something looser
than what was written. Nothing downstream can detect a baseline that arrived eleven-twelfths complete.

**Fix — `smell-baseline.md` in the skill folder; the brief names the path.** The sub-agent reads the file,
which removes the transcription entirely and drops the always-loaded block to a single pointer line. The two
binding rules (*the repo overrides*, *always a judgement call*) move into the file's own preamble, so the
brief no longer has to restate them either.

## F5 — the refactoring reference the suite thinks it has does not exist

CHANGELOG #464, reshaping `tdd`:

> Also dropped the refactor stage — TDD is now red → green; refactoring belongs to the review stage, so the
> refactor rule and `refactoring.md` moved out (**its home is `code-review`**).

`find` across the plugin returns no `refactoring.md`, in `code-review` or anywhere else. So `tdd` gave up
its refactor stage on the grounds that this skill holds refactoring, and this skill holds twelve one-clause
`→ how to fix` arrows and nothing more. The suite's refactoring guidance was not moved; it was dropped.

**Fix — this is F4's destination.** `smell-baseline.md` is where `refactoring.md` was always meant to land;
build it as the file that was promised rather than a lift of the current block, and the two findings close
together.

## F6 — the hardcoded tracker path reintroduces a fixed bug

Two sites name the path directly: the preamble ("run `/setup-matt-pocock-skills` if
`docs/agents/issue-tracker.md` is missing") and step 2 ("fetch via the workflow in
`docs/agents/issue-tracker.md`"). The suite settled this in CHANGELOG #472:

> Fix **`wayfinder`** hardcoding the issue-tracker doc path, which broke the indirection the rest of the
> suite relies on. `to-issues`, `to-prd` and `triage` never name a path — they resolve the tracker through
> the `### Issue tracker` block that `setup-matt-pocock-skills` writes into `CLAUDE.md` / `AGENTS.md`, which
> points at the tracker doc wherever it lives.

The siblings hold the line — `to-tickets` §11 and `to-spec` §9 both say only *"should have been provided to
you — run `/setup-matt-pocock-skills` if not"*, with no path. `code-review` names it twice. In a repo that
keeps agent docs elsewhere, the preamble tells the user to re-run a setup that already ran, and step 2's
first spec source silently fails through to sources 2–4.

**Fix — copy the sibling wording verbatim** in the preamble, and in step 2 resolve the tracker through the
`### Issue tracker` block rather than a literal path.

## F7 — a 400-word cap over twelve smells and a whole diff, with no drop rule

Both briefs end "Under 400 words." Two problems. The cap is identical across axes whose workloads are not:
the Spec axis reports against one document, the Standards axis against every documented rule *plus* twelve
smells across every hunk. And nothing says what to drop when the findings exceed the budget — so the
sub-agent truncates on whatever it happened to look at last, and a run that hit the cap is
indistinguishable from a run that found little.

**Fix — make the cap an ordering, not a guillotine.** "Hard violations first, then judgement calls, worst
first within each. Under 400 words; if the findings exceed it, cut from the judgement-call tail and say how
many you cut." The count is what makes the truncation visible.

## F8 — steps 2–5 have no completion criteria

`writing-for-agents` §Steps and completion criteria: every step ends on a condition that tells the agent
done from not-done, and a vague bound invites premature completion. Step 1 has a real one (ref resolves,
diff non-empty). The rest have none, and step 3 is the worst of them — *"Anything in the repo that documents
how code should be written"* has no bound at all, no stop, and no answer for a monorepo with nested
`CONTRIBUTING.md` files.

Four criteria, one per step:

| Step | Completion criterion |
|---|---|
| 2 Spec source | Either a spec is in hand with its origin named (issue id, path, or user-supplied), or the user has said there is none and the Spec axis is recorded as skipped. |
| 3 Standards sources | Every standards file found is listed with its path; the search covered the repo root and the directories the diff touches; a repo documenting nothing is recorded as such, not left blank. |
| 4 Dispatch | Both briefs dispatched before either report is read; each brief carries the diff command, the commit list, its sources, and the delegation guardrail. |
| 5 Aggregate | Both axes present under their own heading (or Spec explicitly marked skipped); every finding carries its citation; the closing line gives a count and a worst issue per axis and no cross-axis ranking. |

## F9 — no size gate, so a large diff returns a partial review that reads clean

Step 1 gates on the ref resolving and the diff being non-empty. Nothing gates on the diff being reviewable.
A branch-length diff over a monorepo overflows a sub-agent's context; what comes back is a review of
however much fitted, in the same shape and tone as a complete one. Combined with F7's cap, a run can lose
material twice over and report neither loss.

**Fix — measure before dispatch and shard by path.** `git diff --stat <fixed-point>...HEAD` costs nothing.
Past a threshold, shard the Standards axis **by directory** and run every rule inside each shard — never by
rule, which re-reads the same files once per rule. Record the shard boundaries: a smell spanning two shards
(Shotgun Surgery and Duplicated Code both are, by definition) belongs to the aggregation step, not to
either shard. The Spec axis does not shard — it needs the whole diff against one document.

## F10 — the user's own argument loses to an inferred issue reference

Step 2's order puts commit-message issue refs first and *"a path the user passed as an argument"* second. A
user who typed the spec path is stating the spec; a `#123` in a commit message is a guess about which
document was originating. The explicit input should win. Swap 1 and 2.

## F11 — the two-axis rule is stated three times, twice as negation

Step 5: *"Do **not** merge or rerank findings"*; then *"Don't pick a single winner across axes"*; then
§*Why two axes* argues the same point a third time. `writing-for-agents` §Pruning wants one source of
truth per meaning, and §Leading words wants the positive stated so the banned behaviour is never spoken.

Keep the rationale in §*Why two axes* — it is the skill's best paragraph and it earns its place. Reduce
step 5 to the positive instruction: *"Present each axis under its own heading, in the order the sub-agents
returned them, and close with a count and a worst issue **per axis**."* The behaviour is now fully specified
without naming the failure once.

---

## Drop-in — Step 4

### 4. Dispatch both sub-agents

**Dispatch both briefs before reading either report.** A report read before the second brief is composed
puts one axis's findings into the other's framing, which is the contamination the two axes exist to
prevent.

Both briefs carry the diff command, the commit list, and this line:

> Perform this review yourself, in this context — read the files and run git directly; you are the only
> agent on this axis. Do not invoke `/code-review` or spawn further agents.

**Standards brief** — plus the standards files found in step 3 by path, and
[`smell-baseline.md`](smell-baseline.md) by path.

> Report, per file or hunk: (a) every place the diff breaks a documented standard — cite the file and the
> rule; (b) every baseline smell you spot — name it and quote the hunk. Mark each finding *hard* or
> *judgement call*: a documented breach can be hard, a baseline smell never is, and a documented repo
> standard overrides the baseline. Skip anything tooling enforces. Order hard violations first, then
> judgement calls, worst first within each. Under 400 words; if the findings exceed it, cut from the
> judgement-call tail and say how many you cut.

**Spec brief** — plus the spec, by path or contents.

> Report: (a) requirements the spec asked for that are missing or partial; (b) behaviour in the diff nobody
> asked for; (c) requirements that look implemented but implemented wrong. Quote the spec line for each
> finding, worst first. Under 400 words; if the findings exceed it, cut from the tail and say how many you
> cut.

Where step 1 found the diff too large for one context, shard the Standards brief **by directory** and run
every rule inside each shard; record the boundaries, and leave any smell spanning two shards to step 5. The
Spec axis stays whole. Where step 2 found no spec, the Spec brief is not dispatched and step 5 records the
axis as skipped.

Completion: both briefs dispatched before either report is read; each carries the diff command, the commit
list, its sources and the guardrail line; every shard boundary recorded.

## Knock-on edits

| File | Edit |
|---|---|
| `skills/engineering/code-review/smell-baseline.md` | **new** — the twelve smells, the two binding rules, and the refactoring guidance CHANGELOG #464 promised (F4, F5) |
| `SKILL.md` frontmatter | drop "work-in-progress changes" from the description, or keep it and ship F3's gate — not both |
| `SKILL.md` preamble | tracker line → the sibling wording, no path (F6); baseline claim in the parallelism sentence unchanged |
| `SKILL.md` §1 | add `git status --porcelain` and `git diff --stat` gates (F3, F9) |
| `SKILL.md` §2 | user-supplied path to first (F10); tracker resolved via the `### Issue tracker` block (F6); completion criterion (F8) |
| `SKILL.md` §3 | twelve-smell block → one pointer line to `smell-baseline.md` (F4); completion criterion (F8) |
| `SKILL.md` §4 | replaced above |
| `SKILL.md` §5 | reduce to the positive instruction; the rationale stays in §*Why two axes* only (F11) |
| `docs/engineering/code-review.md` | the fan-out and uncommitted-work Q&As become "fixed in 1.2.4" rather than open bugs (F1, F3) |
| `.claude-plugin/plugin.json` | `1.2.3` → `1.2.4` — plugin patch, one skill updated |

No `version` frontmatter to bump: 0 of the plugin's 35 skills declare one, so this workspace's per-skill
versioning policy has nothing to act on upstream. It applies from the moment the skill is forked.

## Where the fix lands

The synced copy under `~/.claude/plugins/synced/` is overwritten by `npx skills update`, and the skill's own
doc says frontmatter and directory renames get undone the same way. Three routes, in order of preference:

1. **Upstream PR.** F1, F5 and F6 are contradictions against the plugin's own changelog and docs — the
   cheapest possible review for a maintainer. F1 alone is worth the PR on its own.
2. **Fork into `ai-first-fw/skills/`** under a name that does not collide, dropping `code-review` from the
   managed set and recording the commit forked from. The route the doc reports users actually taking.
3. **Leave it and run it knowing F1.** Viable interactively, where a runaway agent count is visible.
   Not viable unattended.

## The name collision, in this workspace specifically

Three pointers now compete on one trigger: Claude Code's built-in `/code-review`, this skill, and this
workspace's own `ai-first-fw-skills:code-reviewer` ("Cold review of a pull request or branch diff …"). The
built-in clash is documented and unfixed upstream; the third is ours, and both of ours are model-invoked, so
both descriptions sit in context every turn competing to fire on "review this branch".

They are genuinely different skills — ours is requirements-first and cold, takes a PR URL or number, and
needs no file; this one is diff-since-a-ref along two axes. The discriminator already exists in the wording
and is not doing its job because both pointers lead with the same words. Sharpen ours to lead with *PR URL
or number* and *requirements-first*, and if the fork in route 2 happens, lead its pointer with *since a ref*
— or make one of the two user-invoked and pay no context load for it at all.

## Not addressed here

- **No measurement.** F4's context argument and F9's overflow argument are structural, not benchmarked. One
  instrumented run against a real branch would price both, and would tell you whether F7's cap ever binds.
- **The findings ship unverified.** Step 5 aggregates "verbatim or lightly cleaned", and the doc concedes a
  finding can cite the wrong location or overstate impact. A verification pass over hard violations only
  would be cheap; it is a design change to the axis contract, not a defect in it, so it is out of scope for
  this audit.
- **No convergence guarantee.** The doc is upfront that repeated runs keep finding new judgement calls. That
  is a property of the judgement-call half, not a bug to fix, but the report never tells the user, and a
  reader who does not find the doc will run it in a loop.
- **Bugs are nobody's axis.** By design — the doc routes bug-hunting to the built-in review. The skill body
  never says so, so a user who asked to "review this branch" gets no bug hunt and no notice that none
  happened. One line in step 5's closing summary would close it.
