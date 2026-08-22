# AI-First Personal Workflow

A review-driven, author-side operational model for software engineers leveraging multi-agent orchestration within team codebases.

## Language

**Author-Side Pre-Review**:
A personal verification and adversarial review cycle executed by the author and sub-agents before publishing a change to team review.
_Avoid_: Self-review, pre-PR check, local review

**Bimodal Gating**:
The discipline of placing human review strictly at upfront intent/test-contract specification and downstream critical-surface audit, delegating routine mechanical checks to agents.
_Avoid_: Two-stage gating, split review, front-and-back review

**Composite Evidence Packet**:
A structured bundle combining deterministic verification results, empirical execution traces (logs, captures), and adversarial agent diff analyses that proves a task is complete.
_Avoid_: Proof of done, test summary, verification report

**Multi-Tier Orchestration**:
An operational pattern where the developer acts as the synthesizing orchestrator dispatching discrete background sub-agents for exploration, implementation, and adversarial review.
_Avoid_: Subagent pipeline, swarm management, autonomous agent loop

**Test Contract**:
The explicit set of invariants, edge cases, and failure properties that tests must enforce before code implementation begins.
_Avoid_: Test suite, test plan, testing strategy

**Circuit Breaker**:
An automated execution guard that halts agent code changes and reverts uncommitted files to baseline after two consecutive verification failures.
_Avoid_: Retry limit, fail-safe, auto-rollback

**Compact Lifecycle**:
A three-stage task workflow consisting of (1) Planning with Test Scaffolding, (2) Implementation with Self-Verification, and (3) Evidence Audit with PR Packaging.
_Avoid_: 3-stage loop, quick pipeline, standard flow

**Executable Test Scaffold**:
A suite of failing automated test files authored and human-reviewed prior to writing implementation code to validate test invariants.
_Avoid_: Test stub, TDD scaffold, initial test suite

**Tri-Axis Review**:
An automated adversarial diff audit evaluating correctness bugs, security vulnerabilities, and spec drift with mandatory line citations.
_Avoid_: Three-point review, comprehensive review, multi-factor audit

**Delta-Only Verification**:
The discipline of gating only errors, warnings, or broken tests introduced by the current change, isolating pre-existing codebase debt.
_Avoid_: Partial check, diff check, debt isolation

**Deterministic Ladder**:
A strict four-step verification sequence (Types ➔ Lint ➔ Tests ➔ Format) required to pass before code enters adversarial review.
_Avoid_: CI script, test pipeline, check sequence

**Dual-Artifact Planning**:
The explicit separation of business requirements and scope (`spec.md`) from architectural design, seam mapping, and test scaffolds (`plan.md`).
_Avoid_: Split specs, two-file planning, multi-doc plan

**Raw Context**:
A persistent markdown state ledger that tracks task objectives, current lifecycle stage, gate approvals, and execution history to support interruption and resumption across sessions.
_Avoid_: Checkpoint file, session dump, state log

**Artifact Reference Injection**:
The pattern of passing minimal prompts with file paths to sub-agents rather than inlining broad conversational history, ensuring isolated and focused context windows.
_Avoid_: Context copying, prompt injection, conversation inheritance

**Execution Ledger**:
The structured schema within `raw-context.md` that explicitly records task metadata, active stage, human gate status, circuit breaker attempts, and session logs.
_Avoid_: Status file, execution log, session state

**Interactive Dual-Mode Handshake**:
A human gate interaction protocol permitting either conversational chat feedback or direct in-editor file adjustments before giving authorization to proceed.
_Avoid_: Prompt gate, chat-only review, manual gate

**Scratchpads Directory**:
A dedicated, gitignored local directory (`.scratchpads/<task-slug>/`) housing transient task artifacts (`spec.md`, `plan.md`, `raw-context.md`) during active execution.
_Avoid_: Temp dir, work folder, task cache, flat scratchpad

**Semi-Automated Git Stager**:
A packaging phase where the agent stages verified changes, authors a structured semantic commit, and outputs a ready-to-run pull request command without pushing autonomously.
_Avoid_: Auto-committer, git pusher, PR generator




