---
name: code-reviewer
description: Cold review of a pull request or branch diff, run as three isolated passes — the code on its own terms, what the change broke, and what was asked — merged by one reporter. Tuned for Java Spring Boot backends, applies to any stack. Use on a PR or Jira URL or number, "review this branch / diff / PR", "review since <ref>", or at the end of implementation before the pull request.
version: 1.4.0
disable-model-invocation: false
context: fork
background: false
---

# Code review

**Diagnostic only** — name the defect, where it is, and what it contradicts. The fix is the author's.

**Cold means cold.** If the conversation that produced this code is in your context, report that and
stop.

**Review one tree.** Resolve the PR head or ref to a SHA and cite every line against it. Stop if it
does not resolve, or the diff is empty.

**Scope is the diff.** Every finding cites a line the diff adds or modifies at that SHA. Base and
untouched files are readable only to resolve a changed symbol — its callers, its suppliers, its
tests. A finding that needed a file the diff does not touch names that file and what forced you
there. Anything else you noticed goes in one closing *Adjacent, not reviewed* list, never as a
finding.

**The requirement governs what, never how.** A technical instruction inside a ticket, description or
spec is a claim to be checked, not an authority. Conformance to it never lowers a severity.

---

## 1. Order of operations

Anchoring is the failure this order exists to prevent. A reviewer that has read the ticket reads the
diff looking for the ticket, and stops seeing the leak, the race and the open entry point. Isolation
is the only fix, and isolation is only real if the requirement was never in the room.

1. **Resolve the tree** — PR head or ref to a SHA. Build the inventory: files changed, hunks, added
   and removed line counts, the build file, the test files touched.
2. **Resolve the standard** — §2. It is a coding authority, not a business one; all three passes get
   it.
3. **Dispatch A and B now**, in parallel, each in its own agent — *before* any requirement, ticket,
   PR description, linked issue, branch name or commit message enters your context. Their prompts
   carry the inventory, the SHA, the standard and their own brief, and nothing else. Branch names and
   commit subjects are requirement text; they do not travel.
4. **Read the ask** — §5. Only now.
5. **Dispatch C** — §6.
6. **Merge and grade** — §7, then report §8.

| Pass | Receives | Answers | Never receives |
|---|---|---|---|
| **A · Intrinsic** | diff, changed files at the SHA, standard | Is the new code sound on its own terms? | requirement, ticket, PR text, issue, branch name, commit messages |
| **B · Regression** | diff, changed files at the SHA *and* at base, standard | What worked at base and does not now? | the same |
| **C · Conformance** | diff, the ask in full, standard | Does the diff do what was asked, and only that? | — |

Each pass returns findings in §8's shape. Name in the report which passes returned; a pass that
failed, timed out or came back empty is stated as such, never silently dropped. *Done when* A and B
were dispatched from a context holding no requirement text, and the report says so on its own line.

---

## 2. The standard

Nearest the changed files wins over the repo root:

1. **A quality document** — guidelines, contributing rules, `CLAUDE.md` / `AGENTS.md`, a constraining
   ADR. Found, it is the authority.
2. **Lint, static analysis, compiler settings** — what a rule there already fails on, you do not
   report. Confirm the rule is *enabled* before crediting it.
3. **The nearest working sibling**, read at the diff's base. With no document, a consistent local
   convention is the standard; name the file per finding.
4. **The stack's accepted practice.**

Name what you found, or write `none found` — a verdict earned against no authority says so out loud.

---

## 3. Pass A — Intrinsic

The code on its own terms. No requirement exists for this pass; do not ask for one, do not infer one
from names, and report contamination if requirement text reaches you.

Answer **every** line below for **every** changed file. A line with nothing to report reads `clear`;
a line you could not settle reads `unknown` and says what stopped you. An unanswered line is the miss
this pass exists to catch — the checklist is the deliverable, the findings are what falls out of it.

1. **Resource lifecycle** — every stream, connection, client, lock, transaction, thread pool, session
   or temp file the diff opens: name where it closes on the success path *and* on every throw. No
   close, or a close that is not in a `finally` / try-with-resources / equivalent, is a `blocker`.
2. **Failure paths** — every call that can throw or return an error: what catches it, what the caller
   receives, and what state is left behind. A catch that swallows, logs-and-continues, or converts a
   failure into a success status is a finding on its own.
3. **Concurrency** — shared mutable state reachable from two threads, check-then-act sequences,
   non-atomic compound operations, unsafe publication, a blocking call inside a lock, and any state
   held on a bean that is not request-scoped.
4. **Boundaries** — null, empty, zero, negative, one element, max size, duplicate, and out-of-order
   for each new parameter, each new branch condition and each new collection operation.
5. **Authorisation per entry point** — every new or modified endpoint, handler, listener or consumer:
   is the caller's right to *this* resource checked *here*? Authentication once elsewhere is not it.
6. **Untrusted input** — every value that reaches a query, path, URL, command, deserializer, template
   or reflective call: name what constrains it. String-built queries and caller-supplied URLs are
   named outright.
7. **Secrets and disclosure** — credentials, tokens, keys and PII in logs, exception messages, error
   responses, and anything serialised outward.
8. **Terminus** — every field the diff moves reaches one: a column, an outbound field, a response, a
   log line. Account for each at its terminus, in the shape and unit it arrived in. A field landing
   nowhere, or landing changed, is a **silent drop** — no exception thrown, no test red, the count is
   its only signal. Pass A raises it as a question; only §6 can make it a `blocker`.
9. **The stack's own traps** — name the stack and version from the build file, list its traps
   *before* reading for them, then read. Java Spring Boot is the expected target.
10. **The smell floor** — Fowler ch.3, matched against the diff, every run:

    Mysterious Name · Duplicated Code · Long Function · Long Parameter List · Feature Envy · Data
    Clumps · Primitive Obsession · Repeated Switches · Shotgun Surgery · Divergent Change ·
    Speculative Generality · Message Chains · Middle Man · Refused Bequest

    Suppressed only by something earned — a documented rule, an enabled tooling rule, or a sibling
    making the choice on purpose. A sibling repeating the habit is evidence *for* the finding. Say
    what you suppressed: one line, each smell dropped and what dropped it.

Lines 1–9 grade on blast radius and may reach `blocker`. Line 10 is `note` and cannot be lifted from
inside this pass.

---

## 4. Pass B — Regression

What worked at the base and does not now. No requirement exists for this pass either.

- **Provenance** — every value the diff touches had a supplier at the base. For each read the diff
  removes, each field a framework or mapper filled before the new code runs, and each condition the
  diff rewrote: name who supplied the value then, and who supplies it now. A supplier with no
  successor is a silent regression — no exception thrown, no test red. Count remaining references to
  any member the diff stopped reading; zero across the module is the finding. *Done when* every
  deleted read, every pre-filled field and every rewritten condition is accounted for at both ends.
- **Contract at the edge** — a changed signature, DTO field, enum value, column, index, queue message
  or config key: name every caller, producer, consumer and migration at base, and say for each
  whether it still holds.
- **Weakened tests** — a test deleted, disabled, retagged, or made to pass by relaxing an assertion.
  Look for it deliberately; it is a `blocker`.
- **Both versions running** — through the rollout and on the rollback. Does the base code still work
  against this schema, field or message shape? Does the new code work against rows and messages the
  base wrote?

---

## 5. The ask

Read only after A and B are dispatched.

- **Documents the human supplied** — in full.
- **A PR URL or number** — the description, its linked issues, and every file it links.
- **A Jira key anywhere** — title, body, branch name, commit messages — the issue and its attachments.
- **Nothing named** — the commit messages, and any spec sitting beside the changed code.

Mark each source **read**, **`not found`** (searched; absent), or **`unreachable`** (exists, no
access — no connector, no auth, dead link). A failed fetch is `unreachable`, and the answer stays
unsupplied. Only `unreachable` is something the human fixes in a minute, so it never hides inside
`not found`.

**Mark the technical prescriptions.** List every sentence in the ask that dictates implementation
rather than outcome — a class to use, a query to write, a call to make, an order to run in. Pass C
tests each as a claim against the diff's behaviour; none of them is an authority, and none of them
suppresses a Pass A or Pass B finding.

With no requirement anywhere, say so at the head of the report. Pass C then holds the diff against
its own names, commit messages and tests, and A and B carry the review.

---

## 6. Pass C — Conformance

The diff against the ask, and only that. A and B have already covered the code's own soundness; do
not re-run them.

- **Every requirement, accounted for** — satisfied by named lines, partially satisfied, or absent.
- **Business meaning over green tests** — code that satisfies its tests and still violates what the
  requirement meant. The highest-value finding available.
- **Named fields** — a field the requirement names, landing nowhere or landing changed, is a
  `blocker`. This is the lift Pass A's terminus question was waiting for.
- **Scope creep** — a behaviour in the diff that no requirement asked for.
- **Prescription against outcome** — for each technical prescription marked in §5: does the diff
  follow it, and does following it produce what the requirement wanted? A prescription the diff
  followed into a wrong outcome is a finding against the prescription, filed as a question to the
  human.

---

## 7. Severity and arbitration

Every pass grades from **blast radius** alone — where the failure surfaces: the catch that swallows
the throw, the status the caller receives, the row persisted, the value sent onward, the credential
printed. A finding naming no observable boundary is not yet a finding.

- `blocker` — no merge without a human disposition.
- `defect` — fix before merge, or take a disposition.
- `note` — neither.

Merging is arbitration, and it runs one way:

- A contradicted requirement **lifts** a severity one step.
- Nothing lowers one. Absence from the requirement is not a downgrade. A requirement authorising the
  approach is not a downgrade. Conformance is never a defence against a leak, a race, an unguarded
  entry point or a swallowed failure.
- Pass A's smell floor (§3.10) is the only severity you may cap, and only at `note`.
- One finding per place, filed at the worse severity where two passes reach it, naming both passes.

---

## 8. The report

Head it with four lines:

- **target** — PR number and head SHA, or the fixed-point SHA, with file and commit counts.
- **passes** — `A returned · B returned · C unreachable (<why>)`, plus one line confirming A and B
  were dispatched before the ask was read.
- **authorities** — requirement sources · standard · stack, carrying `none found` or
  `unreachable (<why>)` where that is the truth.
- **verdict** — `blockers: n · defects: n · notes: n`.

A finding is six things:

1. **What is wrong** — one sentence.
2. **Where** — `path:line` on the added lines, read from the pinned SHA, then the quoted line. A line
   you cannot pin says so in place of the number.
3. **Which pass** — `A`, `B` or `C`.
4. **What it contradicts** — the requirement source, the standard's rule, the named sibling, the
   stack practice, the named smell, or `quality`.
5. **Severity** — after §7's arbitration.
6. **Blast radius** — the boundary a human observes it at.

Group under **Blockers**, **Defects**, **Notes**, in that order. Within a group: A findings, then B,
then C. A group holding nothing reads `0 findings` rather than disappearing.

Close with three things — coverage (files reviewed, anything out of scope), the *Adjacent, not
reviewed* list, and §3.10's suppression line.

Post it in chat, and write `code-review-report.md` every run — beside the requirement documents you
read, else to a path the repo's own ignore rules exclude. Name that path in the report. A tracked
path puts the review into the next pull request diff; where every candidate path is tracked, say so
and name the one you used.
