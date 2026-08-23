# code-reviewer — audit 2026-08-23

Scope: all of `SKILL.md` v0.7.1, frontmatter through Step 5. Seven findings, ordered by severity, each
with a drop-in replacement. Held against `implementation-planner` v0.7.1 (the caller), `plan-reviewer`
and `specs-reviewer` v0.7.1 (the sibling cold readers), and the repo `CLAUDE.md`.

**Verdict: 3 blockers · 3 defects · 1 note.** Two blockers break the handshake with the lifecycle that
invokes this skill; the third lets a hot context through the door the header calls cold.

---

## Finding 1 — `blocker` — the invocation the lifecycle prints is a mode this skill does not have

`implementation-planner` (§the gate-request pass) tells the human, verbatim:

> Print the invocation — `plan-reviewer <feature folder path>` before G2, `code-reviewer <feature
> folder path>` at the end of Step 4

Step 1 of this skill recognises two arguments. A PR URL or number → PR mode. Nothing → local mode,
"the fixed point is the ref the human names, else the default branch." **A feature folder path is
neither.** It is not a PR, and it is not a ref, so the argument parse falls through the only branch
left — *no PR named* — and the folder is discarded in silence. Nothing in the step says an
unrecognised argument is a stop, so the run proceeds and reviews something.

What it reviews is the second half of the break. The planner ends with:

> G2's SHA is the fixed point `code-reviewer` diffs against, so it is the one that must be right.

That SHA lives in `raw-context.md` §0 `Baseline`. This skill never reads `raw-context.md`, never reads
a baseline, and never mentions `.scratchpads/`. Having dropped the folder, local mode falls back to
the default branch — a **wider** range that re-reviews every commit G2 already approved, and a range
that moves under the reviewer whenever the default branch advances. The planner's one sentence about
the fixed point that "must be right" is enforced by nothing on this side.

The third surface is the report. The planner's §the artifacts:

> Reviewers add their own: `plan-review-report.md`, `specs-review-report.md`, `code-review-report.md`.

and its review loop: *"On re-entry, read the report the reviewer left in the folder."* Step 5 of this
skill writes to disk **conditionally** — "Where Step 2 found written requirements beside the feature,
also save it beside them" — and the planning folder is reached only if Step 2's source 3 happens to
find it. On every run where it does not, the planner's re-entry reads a file that was never written,
and the mandatory review leaves no trace on disk.

Both sibling reviewers take a folder path as a *declared input* with a stated entry condition, and
both write their report unconditionally. This skill's "**Authorities are found, not demanded**" is the
right stance for authorities. It is the wrong stance for the argument, and folder-mode is not an
authority — it is where the fixed point and the report live.

**Fix: make the folder a third mode, read the baseline from §0, and write the report unconditionally.**
`no file is required` survives intact — folder mode is offered, never demanded.

### Replacement — Step 1

## Step 1 — Resolve the target

The argument decides the mode, and the mode decides where everything — this step and every later
one — is read from:

- **Folder mode** — the argument is a feature folder path, `<repo-root>/.scratchpads/<feature-slug>/`.
  The local repo is the source. Read `raw-context.md` §0 and preserve it exactly as found; its
  `Baseline` SHA — the one G2 approved — **is** the fixed point. Where §0 is absent, or carries no
  `Baseline`, stop and report the missing state: without it there is nothing to diff against, and
  guessing the fixed point silently widens the review.
- **PR mode** — the argument is a PR URL or number. The pull request's own repo is the sole source
  of truth.
- **Local mode** — no folder and no PR named. The local repo is the source; the fixed point is the ref
  the human names, else the default branch.

An argument matching none of the three is a stop, not a fall-through to local mode. Say which argument
was given and which mode it failed to match.

Under review is **the branch's own work**: the changes since branch and base last agreed. Capture that
diff and its commit list, and pin both endpoints as SHAs — resolve any ref, branch name or PR head to
an immutable SHA here and carry the pair forward; every later step and both sub-agents read that pair,
never the ref that produced it. Stop and report if the target does not resolve or the diff is empty.

*Done when*: the mode is named, the fixed-point SHA and head SHA are both pinned and stated — PR
number alongside them in PR mode — with changed-file count and commit count. In folder mode, §0 is
exactly as it was found.

### Replacement — Step 5, the report-to-disk paragraph

Post the report in chat. **Also write it to disk, every run** — a mandatory review that leaves no file
behind cannot be re-entered. In folder mode, save it as `code-review-report.md` in the feature folder,
beside `raw-context.md`, which is where the lifecycle's review loop reads it. Otherwise save it beside
the written requirements Step 2 found; where Step 2 found none, save it at the repo root. Name the
path in the report's authorities line. A re-review overwrites it, so the file on disk always reflects
the latest run. Posting to the PR itself is the human's move, on their ask.

---

## Finding 2 — `blocker` — the cold read is warm by default, and nothing catches it

Frontmatter across the three cold readers:

| Skill | `disable-model-invocation` | `context` | Contamination abort |
|---|---|---|---|
| `plan-reviewer` | `true` | `fork` | yes |
| `specs-reviewer` | `true` | `fork` | yes |
| **`code-reviewer`** | **`false`** | `fork` | **none** |

Line 1 of this skill is *"Execute a **cold read**"*, and its description ends *"or at the end of
implementation before the pull request."* Those two clauses point in opposite directions. `context:
fork` carries the invoking conversation in, and `disable-model-invocation: false` means the model may
invoke this skill on its own — most plausibly at exactly the moment the description advertises, from
inside the session that just wrote the code. **The whole implementation conversation is then in the
reviewer's context: the author's reasoning, the trade-offs it talked itself into, the tests it wrote
to pass.** That is the one context a cold read must not have, and it is the context the frontmatter
invites.

Both siblings close this two ways: they refuse model invocation, and they abort on contamination even
so. This skill does neither. `reject inferred intent` is a good instruction and no defence — inferred
intent read out of a conversation the reviewer remembers does not present as inference.

The value of `disable-model-invocation: false` is real: reviewing on the human's ask, mid-session,
without a fresh session. Keep it — and pay for it with the abort the siblings already carry.

**Fix: add the clause block the siblings have, and let the abort — not the frontmatter — be what
enforces coldness.**

### Replacement — insert after the **Priority** paragraph, before the Step 1 rule

- **Clean context**: Use nothing from the invocation conversation. Read only the diff, the sources
  Step 2 finds and the standard Step 3 finds.
- **Contamination abort**: Run this skill in a fresh session. If any prior history for this change is
  present in context — the implementation conversation, the planning conversation, the folder being
  filled, or an earlier review of this branch — abort immediately and report the contamination instead
  of reviewing. **Being invoked from the session that wrote the diff is contamination**, whoever
  invoked it; the fix is to re-run cold, not to try harder to forget.
- **Read-only state**: In folder mode, read `raw-context.md` §0 and preserve it exactly as found. This
  skill never writes it.

---

## Finding 3 — `blocker` — the smell baseline's floor is erodible by its own three clauses

Step 3 introduces the baseline as *"the floor under it — a fixed set of code smells … carried on
**every** run."* Three rules then bind it, and each one hands back the ground it stands on.

**"Nothing tooling already catches. A lint or formatter config found above is the list of smells not
to report."** As written, the *existence* of a config is the suppression list — not the rules enabled
in it. A repo with `.prettierrc` and nothing else has a formatter config, and a formatter catches none
of the twelve smells; the sentence still nominates it as the list. Worse for lint: an ESLint config
with `complexity` and `max-depth` off is indistinguishable, under this clause, from one that enforces
them. Coverage is being read off a file's presence rather than its contents.

**"Suppress any smell the standard or the sibling endorses"** (Step 4, standards reviewer) is
circular against half the list. Duplicated Code, Primitive Obsession, Message Chains, Middle Man and
Repeated Switches are *habits*; the nearest sibling in the same module is the most likely place for
the habit to already be visible. A sibling that duplicates endorses duplication, so the smell cannot
fire on the codebase that most needs it. The clause was written for a sibling that makes a *deliberate*
local choice — a naming convention, an error-handling shape — and it reads as a licence for anything
done twice.

**"Never a blocker on its own"** is correct and untouched. It is also the only one of the three that
cannot be gamed by the repo under review.

Net: the sibling clause alone reaches five of the twelve by name, and the tooling clause's reach is
whatever a found config file is taken to cover — which the clause never bounds. On a repo with a
`.prettierrc` and one duplicative neighbour, much of the "fixed set carried on every run" is
suppressible, **and the report says nothing about which smells went missing or why.** That is the
failure this skill names in its own opening — *"a verdict earned against nothing must say so"* —
occurring inside the mechanism that was meant to prevent it.

**Fix: suppression must be earned per smell and named in the report.** A config suppresses only the
smells it has an *enabled* rule for; a sibling suppresses only what it demonstrates *deliberately*,
and only where the reviewer can name the file; and every suppression is listed, so the coverage line
carries what the floor lost.

### Replacement — Step 3, the three binding rules

- **Found authority overrides.** A documented rule always wins. Where a found standard endorses what
  the baseline would flag, the smell is suppressed and no finding is written.
- **A sibling suppresses only a deliberate choice, named.** The nearest working sibling is evidence of
  a convention only where it is one — a naming shape, an error-handling shape, a layering rule the
  module holds consistently. **A habit is not an endorsement**: Duplicated Code, Primitive Obsession,
  Message Chains, Middle Man and Repeated Switches are never suppressed by a sibling exhibiting them,
  because the sibling exhibiting them is the finding's own evidence. A sibling-based suppression names
  the file and states what it demonstrates, or it does not hold.
- **Never a blocker on its own.** A smell is a labelled heuristic — "possible Feature Envy" — so alone
  it is severity `note`, and its *what it contradicts* cell names the smell. Only a rule in a found
  standard, or a requirement, lifts a finding above `note`.
- **Only what tooling actually catches, rule by rule.** A lint config suppresses a smell only where it
  carries an **enabled** rule covering it — open the config and name the rule. A formatter config
  suppresses nothing on this list; formatting is not a smell here. Suppression is per smell, never per
  config file.
- **Suppression is reported.** Close the baseline pass with one line — `baseline: <n>/12 applied ·
  suppressed: <smell> (<rule or file that earned it>), …`. A silent suppression is indistinguishable
  from a clean read, which is the outcome this baseline exists to prevent.

---

## Finding 4 — `defect` — the sub-agents are handed a target, and owe a SHA nobody gave them

Step 4: *"Both sub-agents receive the target and the mode."* Step 4's own contract then demands the
`+`-side line number *"read from the reviewed SHA"*, and Step 5's completion criterion demands *"every
finding carries a `path:line` resolved against the reviewed SHA."*

**No SHA is passed down.** Each agent re-resolves "the target" itself, which is three independent
resolutions of the same range — the parent's in Step 1 and one per agent — over a repo that can move
between them. In PR mode it does move: an author pushing mid-review shifts the head, and two agents
resolving *the PR* a minute apart return `path:line` pairs anchored to different trees. Both returns
then satisfy the contract as written, Step 5 merges them by `path:line`, and the merge silently
compares coordinates from two files. The condition Step 5 checks is one Step 4 gave no agent the means
to satisfy.

Finding 1's replacement pins the SHA pair. This step has to hand it down.

**Fix: pass the pinned pair and the captured diff; forbid re-resolution.**

### Replacement — Step 4, the dispatch paragraph

Both sub-agents receive the **pinned SHA pair from Step 1** — fixed point and head — the mode, and the
captured diff as text. Neither re-resolves the target, and neither reads a ref, a branch name or a PR
head: a range resolved twice is two ranges, and `path:line` coordinates from different trees merge
into nonsense at Step 5. Every file either agent opens, it opens at the head SHA it was given. Each
performs its review directly: it invokes no review skill and spawns no further agent.

---

## Finding 5 — `defect` — an authority that could not be reached is recorded as one that does not exist

Step 2 has two outcomes per source: read, or `not found`. Step 3 has two: named, or `none found`. The
opening promise rests on that record — *"Each authority the search does not find is written into the
report as `none found`"*, and the authorities line is what a clean verdict is *"only as strong as."*

Some of these sources fail a third way. Step 2 instructs: *"where a Jira item is mentioned anywhere —
title, body, branch, commits — search Jira for it and read it, description and attachments both."*
Jira is reached through a connector that may be unauthorised, rate-limited or simply absent; a
PR attachment can sit behind a login the reviewer does not have. **The item exists, is named in the
diff, and was not read.** Written as `not found`, that is a false statement about the world, and it is
the one falsehood this skill's authorities line is built to exclude — an unreachable requirement
source reads on the report exactly like a change that had no requirements at all.

The distinction also changes what the human does next. `not found` is a fact about the repo, and the
review is as good as it will get. `unreachable` is a fact about the reviewer's access, and one
authorisation makes the review meaningfully better.

**Fix: three states, not two, wherever a source is fetched rather than read from disk.**

### Replacement — Step 2, the *Done when* line, plus one clause above it

**A named source that could not be fetched is `unreachable`, never `not found`.** `not found` says the
search ran and the thing does not exist. Where a source is named in the diff, the description or a
commit and the fetch failed — no connector, no authorisation, a rate limit, a dead link, a login —
record `unreachable: <what> · <why>` and carry it to the authorities line. Do not stop: an unreachable
source degrades the verdict, and saying so is the point. Never substitute a search of your own memory
for a fetch that failed.

*Done when*: a source list exists, every entry a path, URL or ref, or `not found`, or `unreachable`
with its reason — attachments included. An empty list is a result, recorded — not a stop.

---

## Finding 6 — `defect` — the merge rule leaves the merged severity undefined, so the verdict line is not reproducible

Step 5.1: *"The same `path:line` flagged on both axes is one finding with two citations."* Step 5.3
then reports `blockers: n · defects: n · notes: n`, and the planner carries that line into the G2
request and the pull request body.

A line the requirements reviewer calls `blocker` and the standards reviewer calls `note` merges into
one finding of unstated severity. Nothing says which survives, so `blockers: 1 · notes: 0` and
`blockers: 0 · notes: 1` are both conformant readings of the same two returns — and the number the
lifecycle quotes back at a gate is the one that changed. Ordering has the same hole: rule 2 breaks
severity ties by axis, and a merged finding has two axes.

**Fix: the worst severity survives, and the merged finding keeps the requirements axis for ordering.**

### Replacement — Step 5, items 1 and 2

1. Merge the two returns. The same `path:line` flagged on both axes is one finding with two citations.
   **The merged finding takes the worst of the two severities** — `blocker` over `defect` over `note`
   — and both citations are kept, each labelled with its axis. A merged finding is counted once, at
   that severity.
2. Order: severity first; at equal severity, requirements findings, then standard, then quality. **A
   merged finding orders as a requirements finding** — it carries a requirements citation, and that is
   the axis the priority rule ranks first.

---

## Finding 7 — `note` — the smell baseline is a reference file pasted into a prompt

Step 4 hands the standards reviewer *"its smell baseline, **pasted in full**; it has no other access
to the baseline."* Twelve smells and their binding rules — 479 words of `SKILL.md` — re-emitted into a
sub-agent prompt on every run.

`plan-reviewer` puts its shared rules in `references/mapping-rules.md` and tells Pass 1 to read it.
`code-reviewer` and `specs-reviewer` are the two skills here carrying no supporting file at all — but
`specs-reviewer` states its reason in the text, twice: *"installs symlink the whole skill directory,
so a shared file outside either does not ship."* **That argument is about sharing across two skill
directories, and this baseline is shared with nothing** — it is one skill's reference material, and a
file under `code-reviewer/references/` ships with the skill, symlink or not. CLAUDE.md already fixes
its naming: *"Reference files under a skill's directory use lower-kebab-case."*

The cost of inline is not only the tokens. The baseline cannot be edited without touching the step
that dispatches it, and "pasted in full" makes the parent context responsible for transcribing all of
it correctly on every run — a silent partial paste reads as a short baseline, and Finding 3's new
suppression line is the only thing that would ever reveal it.

**Fix: move Step 3's *The smell baseline* section verbatim to `code-reviewer/references/smell-baseline.md`
(carrying Finding 3's replacement rules), and dispatch by reference.**

### Replacement — Step 3, the baseline intro, and Step 4's standards-reviewer hand-off

Step 3, replacing *The smell baseline* section body:

> ### The smell baseline
>
> A found standard is the authority; the baseline is the floor under it — a fixed set of code smells
> (Fowler, *Refactoring*, ch.3) carried on **every** run, whether or not a standard was found. It lives
> in `references/smell-baseline.md`: the twelve smells, and the rules that bind when each is
> suppressed. Read it here, and hand its path to the standards reviewer.

Step 4, standards reviewer:

> **Standards reviewer** — gets the Step 3 standard list and the path to `references/smell-baseline.md`,
> which it reads itself. Duties:

---

## Convention drift — smaller than a finding, fixed in the same pass

| Where | Drift | Fix |
|---|---|---|
| Severity ladder (Step 4) | `blocker` = "must not merge"; siblings read "the gate must not pass". The planner has **no gate** at Step 4 and disposition 4 explicitly permits proceeding with a blocker logged as debt — "must not merge" forbids what the lifecycle allows. | `blocker` (must not merge without a human disposition) |
| Severity ladder (Step 4) | `defect` = "fix before merge"; siblings carry the escape — "fix before the gate, **or take a disposition like a gap**". | `defect` (fix before merge, or take a disposition) |
| No closing checklist | Both siblings end with a `## Done when` checkbox list; this skill has only a per-step *Done when* italic line. The final-state check nobody can skim is the one that gets skipped. | Add `## Done when` — mode and SHA pair pinned · both returns satisfy the contract · every finding once, with a resolvable `path:line` · authorities line has no blank cell · suppression line present · report on disk **and** in chat · §0 unchanged in folder mode |
| Header, "Diagnostic-only" | Stated as prose in the opening paragraph; siblings use a labelled bullet in a rule block. Cosmetic, but Finding 2 adds that block anyway. | Fold into the new bullet list |
| `disable-model-invocation` | `false` here, `true` on both sibling reviewers. Keep `false` (Finding 2 argues the value), but it is now the only reviewer the model can start, so the abort is load-bearing rather than belt-and-braces. | No change beyond Finding 2 |

---

## Knock-on edits

| File | Edit |
|---|---|
| `ai-first-fw/skills/code-reviewer/SKILL.md` | `version: 0.7.1` → `0.8.0` — Steps 1, 3, 4 and 5 restructure and a rule block is added; not a patch |
| `ai-first-fw/skills/code-reviewer/references/smell-baseline.md` | **New** (Finding 7) — the twelve smells plus Finding 3's suppression rules, lower-kebab-case per CLAUDE.md |
| `ai-first-fw/skills/implementation-planner/SKILL.md` | §the gate-request pass — the printed invocation now names a mode that exists; no text change needed once Finding 1 lands, but confirm §0 `Baseline` is written before the invocation is printed, since folder mode now stops without it |
| `ai-first-fw/skills/plugin.json` and `.claude-plugin/plugin.json` | `1.0.1` → `1.0.2` — plugin patch, one skill updated (both copies; they are byte-identical today and must stay so) |
| `.claude-plugin/marketplace.json` | `ai-first-fw-skills` `1.0.1` → `1.0.2` — mirrors the plugin manifests |
| `audits/code-reviewer-2026-08-23.md` | Clear once the findings are addressed; promote Findings 2, 3 and 5's rationale into `SKILL.md` rather than leaving it here |

---

## Not addressed here

- **The distribution copy is unverified.** `nguyennguyen-anchanto/ai-first-framework-skills` is not
  mounted in this session, so whether it carries the same `SKILL.md` — and needs the same edit — was
  not checked. Diff the two before the version bump.
- **No measurement.** Every finding is structural: read against the caller, the siblings and the
  skill's own completion criteria. Finding 3's reach is counted from the clauses' wording, not from an
  observed run — one instrumented review against a repo with a `.prettierrc` and a duplicative module
  would put a number on it.
- **All six lifecycle skills sit at `0.7.1`.** CLAUDE.md says each skill versions independently;
  lockstep across six suggests a synchronised release rather than independent versioning. Bumping this
  one to `0.8.0` breaks the pattern deliberately — worth a decision, not a silent divergence.
- **Step 2's source ordering is untouched.** Sources 1–4 are searched in order but nothing states
  precedence when two disagree. `specs-reviewer` handles the same problem explicitly — *"name both,
  quote what each says, and stop there"* — and this skill has no equivalent. Left out because it needs
  a decision about which source wins, not a wording fix.
- **`context: fork` itself.** Finding 2 adds an abort rather than changing the mode. Whether a cold
  reader should fork at all — `plan-reviewer` and `specs-reviewer` do, and lean on `true` to make it
  safe — is a question for all three at once, not for this skill alone.
