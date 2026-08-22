---
name: code-reviewer
description: Cold review of a pull request or branch diff — requirements first, coding standard second, code quality always; no file is required. Use on a PR URL or number, "review this branch / diff", "review since <ref>", or at the end of implementation before the pull request.
version: 0.7.1
disable-model-invocation: false
context: fork
background: false
---

# Code review

Execute a **cold read** of a pull request or branch diff. Diagnostic-only: report defects,
locations and contradictions; remediation belongs to the author. Every claim cites a location as
`path:line` and quotes the line it names; reject inferred intent.

**Authorities are found, not demanded.** No file is required. Each authority the search does not
find is written into the report as `none found` — a clean verdict is only as strong as the
authorities line above it, and a verdict earned against nothing must say so.

**Priority.** Business correctness outranks standard compliance; standard compliance outranks code
quality.

---

## Step 1 — Resolve the target

The argument decides the mode, and the mode decides where everything — this step and every later
one — is read from:

- **PR mode** — the argument is a PR URL or number. The pull request's own repo is the sole source
  of truth.
- **Local mode** — no PR named. The local repo is the source; the fixed point is the ref the human
  names, else the default branch.

Under review is **the branch's own work**: the changes since branch and base last agreed. Capture
that diff and its commit list. Stop and report if the
target does not resolve or the diff is empty.

*Done when*: the target is stated — PR number and head SHA, or fixed-point SHA — with changed-file
count and commit count.

---

## Step 2 — Find the requirements

Collect **the sources themselves** — the requirements reviewer reads them cold, so hand it the
material and its locations, verbatim. Search in order; each source is read or recorded `not found`:

1. **The task** — the PR description, and **every attachment it links**: read each linked file,
   image or document; an attachment is a source like any other, recorded by URL. Then the issue or
   ticket it links or names: where a Jira item is mentioned anywhere — title, body, branch,
   commits — search Jira for it and read it, description and attachments both.
2. **The commit messages** in the range (already captured).
3. **Written business requirements beside the feature**, where they exist — what the business
   asked for, in its own words. The strongest source when found.
4. **Docs the diff touches or names** — the nearest README or docs page to the changed files.

*Done when*: a source list exists, every entry a path, URL or ref, or `not found` — attachments
included. An empty list is a result, recorded — not a stop.

---

## Step 3 — Find the coding standard

Whatever documents how code here should be written: coding guidelines, contributing rules, agent
instructions (`CLAUDE.md` / `AGENTS.md`), lint or formatter configs. Nearest wins — a rule sitting
beside the changed files outranks one at the repo root.

### The smell baseline

A found standard is the authority; this baseline is the floor under it — a fixed set of code smells
(Fowler, *Refactoring*, ch.3) carried on **every** run, whether or not a standard was found. Three
rules bind it:

- **Found authority overrides.** A documented rule, or the nearest working sibling, always wins.
  Where either endorses what the baseline would flag, the smell is suppressed and no finding is
  written.
- **Never a blocker on its own.** A smell is a labelled heuristic — "possible Feature Envy" — so
  alone it is severity `note`, and its *what it contradicts* cell names the smell. Only a rule in a
  found standard, or a requirement, lifts a finding above `note`.
- **Nothing tooling already catches.** A lint or formatter config found above is the list of smells
  not to report.

Each smell reads *what it is* → *how to fix*, matched against the diff, never the file at large:

- **Mysterious Name** — a function, variable or type whose name does not reveal what it does or
  holds. → rename it; if no honest name comes, the design is murky.
- **Duplicated Code** — the same logic shape in more than one hunk or file in the change. → extract
  the shared shape, call it from both.
- **Feature Envy** — a method that reaches into another object's data more than its own. → move the
  method onto the data it envies.
- **Data Clumps** — the same few fields or params keep travelling together, a type wanting to be
  born. → bundle them into one type, pass that.
- **Primitive Obsession** — a primitive or string standing in for a domain concept that deserves its
  own type. → give the concept its own small type.
- **Repeated Switches** — the same `switch` or `if`-cascade on the same type recurs across the
  change. → replace with polymorphism, or one map both sites share.
- **Shotgun Surgery** — one logical change forces scattered edits across many files in the diff. →
  gather what changes together into one module.
- **Divergent Change** — one file or module edited for several unrelated reasons. → split so each
  module changes for one reason.
- **Speculative Generality** — abstraction, parameters or hooks added for needs no requirement
  states. → delete it; inline back until a real need shows.
- **Message Chains** — long `a.b().c().d()` navigation the caller should not depend on. → hide the
  walk behind one method on the first object.
- **Middle Man** — a class or function that mostly just delegates onward. → cut it, call the real
  target direct.
- **Refused Bequest** — a subclass or implementer that ignores or overrides most of what it
  inherits. → drop the inheritance, use composition.

*Done when*: standard file(s) named, or `none found` recorded — a result, not a stop. The baseline
travels either way.

---

## Step 4 — Dispatch two cold readers in parallel

Both sub-agents receive the target and the mode, and return the same contract. Each performs its
review directly: it invokes no review skill and spawns no further agent.

**The return contract** — findings only, each one four things and no more:

1. **What is wrong** — one sentence.
2. **Where** — `path:line`, then the quoted line. The path is repo-relative; the number is the
   line in the file **as the diff leaves it** (the `+` side), read from the reviewed SHA, never a
   hunk offset or a guess. A finding spanning consecutive lines writes `path:start-end`; a finding
   in several places writes each location, comma-separated, and every one of them is a real line.
   A finding whose line cannot be pinned says so in place of the number — it does not omit it.
3. **What it contradicts** — the requirement source, the standard rule, the named sibling file, or
   `quality` where no authority covers it.
4. **Severity** — `blocker` (must not merge), `defect` (fix before merge), `note`.

Each return closes with one coverage line — `reviewed: <n> changed files · out of scope: <which,
or none>`. Quotes stay verbatim; the searching that produced a finding stays out of the return.

**Requirements reviewer** — gets the Step 2 source list and fetched attachments. Duties:

- Every requirement the sources state is traceable in the diff.
- Every diff behaviour is traceable to a requirement, or flagged as scope creep.
- Code that satisfies its tests but violates the requirement's business meaning.
- Where the source list is empty: review the diff's internal coherence — does the code do what its
  own names, commit messages and tests claim? — and open the return by stating that no
  requirements source exists.

**Standards reviewer** — gets the Step 3 standard list **and its smell baseline, pasted in
full**; it has no other access to the baseline. Duties:

- Every rule the standard states, held against the diff. Documented rules outrank generic
  heuristics.
- Then code quality, with or without a standard: conformance to the nearest working sibling in the
  same module — read from the target's repo at the base the diff builds on — error handling,
  naming, dead code, comments that repeat the code, test quality.
- Then the smell baseline, every run: name the smell, quote the hunk, severity `note` unless a
  found rule or a requirement lifts it. Suppress any smell the standard or the sibling endorses,
  and any one tooling already catches.
- Where no standard was found, the nearest sibling **is** the standard — name it per finding, and
  open the return by stating that no written standard exists.

*Done when*: both returns satisfy the contract — every finding located as `path:line` — coverage
line included.

---

## Step 5 — Aggregate

1. Merge the two returns. The same `path:line` flagged on both axes is one finding with two
   citations.
2. Order: severity first; at equal severity, requirements findings, then standard, then quality.
3. Report:
   - **Authorities line** — target (PR number and head SHA, or fixed-point SHA) · requirements
     sources · standard — `none found` written where nothing was.
   - **Verdict line** — `blockers: n · defects: n · notes: n`.
   - The findings, numbered, in order, in contract format. Each one carries its `path:line` in
     the finding itself — not in a trailing appendix, not left to the reader to find.
   - The two coverage lines, verbatim.

Post the report in chat. Where Step 2 found written requirements beside the feature, also save it
beside them as `code-review-report.md` — a re-review overwrites it, so the file on disk always
reflects the latest run. Posting to the PR itself is the human's move, on their ask.

*Done when*: every finding from both returns appears exactly once, every finding carries a
`path:line` resolved against the reviewed SHA, and the authorities line has no blank cell.
