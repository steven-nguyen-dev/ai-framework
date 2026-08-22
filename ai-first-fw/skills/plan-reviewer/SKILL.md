---
name: plan-reviewer
description: Cold, document-only review of an implementation plan and its mapping plan against the business requirements, before Gate G2.
version: 0.7.1
disable-model-invocation: true
context: fork
background: false
---

# Plan review

Execute a **cold reader** review. Evaluate assertions strictly against disk artifacts and cited evidence; reject inferred intent.

- **Diagnostic-only**: Name what is wrong, where it is, and what it contradicts. Omit rewrites or suggested wording.
- **Read-only state**: Read `raw-context.md` §0 for current state and preserve it exactly as found.
- **Document-only**: Inspect only the feature folder artifacts, the spec files `mapping-plan.md` §1 names, and cited lines. Omit codebase surveys, sibling searches, and verifying reuse-search `FACT-xx` rows against the repository tree.
- **Clean context**: Use nothing from the invocation conversation. Read only the sources on disk.
- **Contamination abort**: If any prior history for this feature is present in context — the planning conversation, the interview, the folder being filled, or an earlier review — abort immediately and report the contamination instead of reviewing.

---

## Inputs

You are given a **feature folder path** — `<repo-root>/.scratchpads/<feature-slug>/`.

| File | What you use it for |
|---|---|
| `raw-context.md` §0 | **Read first** — where the work is, and whether the artifact exists |
| `implementation-plan.md` | The artifact under review |
| `mapping-plan.md` | The approved boundary contract |

| `business-requirements.md` | The authority on what should happen |
| `raw-context.md` §1–§8 | The record — the ask (§1), materials and fitness verdicts (§2), `FACT-xx` (§3), the answers (§4), `DEC-xx` / `ADR-xx` (§5), the references (§6), the gap ledger (§7), the debt register (§8) |

**Entry condition**: Stop and report the missing artifact if `raw-context.md`, `implementation-plan.md`, `business-requirements.md` is absent. A `raw-context.md` carrying no §0 is the same stop — without the state there is nothing to hold the plan against.

---

## The three passes

Run them **in this order, each finished before the next begins**. Keep findings strictly isolated per pass section.

### Pass 1 — Evidence

Verify every claim in the plan carries evidence or is marked `unverified`.

- **Citations resolve**: Open every `file · Class.method` and `package.ClassName#member` citation. Verify the target exists and supports the claim.
- **Current-behaviour marked**: Any current-behaviour claim without a citation must carry the word `unverified`.
- **Source attribution resolves**: Every `SRC-xx` cited in a requirements `Source` column has a row in `raw-context.md` §2, and every path that row names exists on disk.
- **Artifact accountability**: A §2 row with a blank `Description`, or with no fitness verdict, is a finding.
- **Refined files**: A claim citing a `Path — refined` instead of the original artifact is a finding (Rule 4).
- **Verbal vs Documented**: A claim with `Source` `<who>, <date>` that a §2 material already states is untraced.
- **Search misses**: Every `[NEW]` in the plan's file tree must have a recorded search-miss `FACT-xx` in `raw-context.md` §3 naming the scopes searched (the reuse-first discipline).
- **Provenance**: Hand-authored test data presented as observed production data is a finding.

> **Read `references/mapping-rules.md`** if `mapping-plan.md` exists, and apply its checks here in Pass 1.

*Completion Criterion*: Every `file · Class.method` citation opened and its symbol found, every `SRC-xx` matched to a §2 row with a live path, every `[NEW]` matched to a search-miss `FACT-xx` — counts stated; Evidence findings recorded.

### Pass 2 — Brief

Verify the plan implements `business-requirements.md` — **all of it, and nothing more**.

- **Completeness counts match**: Count `AC-xx` rows in requirements §3 and phase 1 rows in plan §4. Report both numbers. They are equal, and each `AC-xx` has exactly one phase 1 row.
- **Every `AC-xx` mapped**: An acceptance criterion with no phase 1 row is a finding.
- **Every row mapped**: A phase 1 row citing an `AC-xx` that requirements §3 does not hold is scope creep.
- **Phase 1 restates nothing**: A phase 1 row carrying a Given / When / Then is a finding — the scenario lives in requirements §3, and a copy drifts.
- **Phase 2 targets exist**: Plan §4 phase 2 names at least one target class or method, or states in one line why it has none. Every target traces to a file plan §1 creates or changes.
- **Every `NFR-xx` checked**: Every `NFR-xx` (requirements §4) is addressed by a phase 1 row, a phase 2 target, or an explicit plan note; absence is a finding.
- **Boundary fully mapped**: If `mapping-plan.md` is present, walk the partner doc and that file; an unmapped boundary field is a finding.
- **Mappings identified**: Every mapping row in `mapping-plan.md` carries a `MAP-xx` ID, a stated reason, and a confidence grade.
- **Delegation declared**: If specs were generated, plan §1 carries a `Covered by specs` list, every entry names a spec file that exists, and no plan §1 file change re-implements work that list delegates. A spec-delegated `AC-xx` still has its phase 1 row, naming the spec file and its `MAP-xx`.

*Completion Criterion*: Both counts reported, and every `AC-xx` and `NFR-xx` either traced to a plan row or named as unmapped; Brief findings recorded.

### Pass 3 — Coherence

Verify the plan does not contradict itself or the record.

- **Section against section**: Check the file tree (plan §1) against the test plan (§4) — every non-test file appears as a phase 2 target or carries a stated reason for needing none; governance (§3) against the file changes. Check the §1 `Sequencing constraints` line: it states a constraint the file list does not imply, or reads `none`.
- **Mapping against plan**: A transformation the plan's per-file notes describe that the mapping plan does not reflect, or a mapping whose rule the plan contradicts, is a finding.
- **Plan against record**: Any section contradicting a `DEC-xx`/`ADR-xx` in `raw-context.md` is a finding.
- **ID ownership**: An ID minted in the wrong document or renumbered is a finding.
- **Requirement series intent**: An `AC-xx` or `NFR-xx` naming wire-format details (endpoint, field name, status) is a finding.
- **Debt vs Open Questions**: Every `TD-xx` derived from a gap must state what would settle it.
- **Undispositioned gaps**: Report any gap in `raw-context.md` §7 with no human disposition.
- **Decision tree complete**: Every `raw-context.md` §5 row carries `Because`, `Rejected` and `Depends on`. A `Depends on` naming an ID that does not exist is a finding.
- **Writing standard**: Read `implementation-planner`'s `references/writing-standard.md`. Report agent-written sentences over the word limits, passive-voice sentences that hide the actor, and any `raw-context.md` table row over 223 characters outside a §4 verbatim answer.

*Completion Criterion*: Every plan section checked against every other, and against the decision tree (§5), the gap ledger (§7) and the debt register (§8); Coherence findings recorded.

---

## The report

Format report with the folder path, the `raw-context.md` §0 state, and a **verdict line** — `blockers: n · defects: n · notes: n` — followed by one section per pass.

A **finding** is four things and no more:
1. **What is wrong** — one sentence.
2. **Where** — the section and the quoted line from the plan.
3. **What it contradicts** — the requirement ID, the `DEC-xx` or `ADR-xx`, the citation that does not resolve, or the other section of the plan.
4. **Severity** — `blocker` (the gate must not pass), `defect` (fix before the gate, or take a disposition like a gap), or `note`.

Close each pass section with a summary line stating finding count and worst finding within that pass. Where a pass has none, that line reads `0 findings`.

**Write the report to disk**: save the formatted report as `plan-review-report.md` in the feature folder — the same folder as `implementation-plan.md` and the other plan files. A re-review overwrites this file, so the file on disk always reflects the latest run. Post the same report in chat as well.

---

## Done when

- [ ] Folder path, state, and verdict line stated at head of report.
- [ ] Report contains exactly 3 pass sections with individual pass summary lines.
- [ ] All findings carry the diagnostic format plus a severity, without remediation patches.
- [ ] Report written to `plan-review-report.md` in the feature folder, and also posted in chat.
- [ ] `raw-context.md` §0 is exactly as you found it.
