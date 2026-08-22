# Dual-Artifact Planning and Resumable Raw Context

We adopt a dual-artifact planning structure (`spec.md` for business requirements and `plan.md` for technical design/test scaffolds) accompanied by a persistent `raw-context.md` state ledger. This decouples what to build from how to build it, and guarantees that multi-turn agent sessions can be paused, resumed, and handed off across tools without losing orchestration history or requiring full-context replays.
