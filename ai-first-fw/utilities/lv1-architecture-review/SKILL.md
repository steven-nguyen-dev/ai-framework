---
name: lv1-architecture-review
description: Audit a backend codebase against the architecture checklist and write architecture-review.md at the repo root.
disable-model-invocation: true
version: 0.0.2
---

# lv1-architecture-review

The whole run is judged by one test — the **handover test**: a reader who has never opened this
codebase can follow every citation in the report, see what you saw, and act on it without asking
you a question.

Three disciplines hold across all four steps:

- **Fact, not claim.** A fact is something you read in code, config, or a manifest, recorded as
  `file · Class.method`. A README sentence, a doc-comment, or a class name is a claim, and the report cites
  the code that confirms it.
- **`undetermined` is a status, not a gap.** A check the code cannot settle is graded, never
  skipped — Step 3 sets what each status carries.
- **Delegate the reading.** Reading the codebase, reading multiple files for context, and researching
  multiple online sources each go to a sub-agent. A sub-agent returns verdicts, facts and `file · Class.method`
  — never file bodies, never its search narrative, and never a chosen answer. `references/checklist.md`
  you read yourself: you grade against its words. Online research covers public material only.

## Step 1 — Scope and stack

Delegate the manifest read: the dependency manifest (`pom.xml`, `build.gradle`, `package.json`, …),
the runtime config (`application.yml`, `.env.example`), and the deploy manifests (Dockerfile, compose,
k8s, CI). It returns the coordinates and settings found or absent, each with `file · Class.method` — not the
files.

1. **Name the target** — one service, or the module the user named. A monorepo with no named target
   takes one question, then proceeds.
2. **Decide each §7 block** in `references/checklist.md` — `applicable` or `n/a` — from the
   manifest, naming the dependency found or the dependency absent. A `spring-boot-starter-data-redis`
   coordinate makes `CACHE` applicable; that coordinate absent from `pom.xml` with no cache
   abstraction anywhere retires it. Where a block applies but its examples name a different product
   (SQS where the block says Kafka), keep the block and read its checks against the broker in hand.

Completion: target named; every §7 block marked `applicable` or `n/a`, each citing the manifest read
and the dependency found or absent.

## Step 2 — Fire two tracers, then sweep

A **tracer** is one real request read end to end. Two tracers plus one sweep produce the facts every
check is graded against.

**Each tracer and each sweep area is one sub-agent, run concurrently.** Every one returns its ordered
`file · Class.method` fact list and nothing besides. The fact list is the deliverable of this step, so the code
that produced it never needs to enter this context.

**Tracer 1 — the critical write path.** The flow that takes money, creates the core entity, or is
the reason the service exists. Read it through every layer it crosses: entry point → authn/authz →
input validation → transaction boundary → data access → cache → outbound call → published event →
error handler → response.

**Tracer 2 — the highest-volume read path.** Usually a list or search endpoint. Same discipline,
with attention on pagination, query shape, and what is cached.

**The sweep.** Targeted reads for what no request touches: CI and deploy config, secret handling,
migration folder, health and metrics wiring, scheduled jobs, alert definitions.

Record each observation as a fact — `file · Class.method` plus what it shows. An absence is a fact and takes
the same form: *"`PaymentClient.java:24` — `RestClient` built with no timeout set"* is the shape
most findings take.

Completion: two traces recorded as ordered `file · Class.method` fact lists; every layer listed above cited or
stated absent; each sweep area cited or stated absent.

## Step 3 — Grade every check

Read `references/checklist.md` and hold every check against the Step 2 facts, in ID order. Each
check takes exactly one status:

| Status | When | Carries |
|---|---|---|
| `pass` | A fact shows the check satisfied | the `file · Class.method` |
| `finding` | A fact shows it violated | the `file · Class.method` |
| `n/a` | Step 1 retired the block | the reason |
| `undetermined` | The code does not answer it | the question — plus the empty search, if unfound |

`undetermined` takes two forms, and each carries its own evidence. **Out-of-repo** — *was a restore
ever run? does that alert page anyone?* — is `undetermined` on sight, carrying the question.
**Unfound** — the repo should answer it and does not — takes one delegated targeted search first, and
carries the question plus the search that came back empty: the pattern and the paths it covered.

Every check tagged `+team` in `references/checklist.md` produces one status **and** one question:
grade the clause the code answers, send the clause it cannot to **Ask the team**. OPS-1 is the
shape — the deploy workflow settles *automated end to end*, and nothing in the repo settles
*rollback someone has actually used*.

Severity is the checklist's own tag. Move one downward with the reason written into the finding: a
`critical` on a path that carries no user data may be worth a note, and saying so is part of the
finding.

Completion: every check in `references/checklist.md` carries a status; every `pass` and `finding`
carries a `file · Class.method`; every `undetermined` carries a question, and every **unfound**
`undetermined` also carries the search that came back empty; every `n/a` carries its reason; every
`+team` check carries a row in **Ask the team**.

## Step 4 — Write the report

Write `architecture-review.md` at the repo root, overwriting any previous run. Where the session can
hand a file to the user, hand this one over as well.

````markdown
# Architecture Review — <project>

<date> · <k> findings (<c> critical) · <u> undetermined · <n> n/a
**Scope**: <what was read> · **Stack**: <blocks applicable · blocks n/a>

## Verdict
<Three sentences: what the system is, how it is built, and what hurts first.>

## Raise these three
1. **<ID> — <defect>** · `file · Class.method` · <why this one ahead of the rest>
2. …
3. …

## Findings
### <ID> · `<severity>` · <one-sentence defect>
- **Where** — `file · Class.method`, with the line quoted
- **What the code does** — the observed behaviour
- **What it costs** — the failure this produces, in this system's own terms
- **Check** — the checklist text it violates

<one block per finding, critical first>

## Ask the team
| Check | Question | Why the code cannot answer it |
|---|---|---|

## Coverage
| Check | Status | Evidence |
|---|---|---|
| OPS-1 | pass | `.github/workflows/deploy.yml:31` |

<one row per check, ID order>
````

**Raise these three** ranks by repair impact — the three whose fix changes the system most — and
each says why it beat the rest. A run holding fewer than three findings lists every finding it has.

Completion: `architecture-review.md` at the repo root; one coverage row per check in
`references/checklist.md`, every Evidence cell filled; the header counts recomputed from the
coverage table and matching it.
