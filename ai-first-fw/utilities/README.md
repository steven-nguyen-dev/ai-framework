# Utility Skills

Standalone utility and helper skills. Each one does its own job and composes with
nothing — no shared artifacts, no handoffs, no gates.

> **Not part of the AI-First Framework lifecycle.** The AI-First Framework lifecycle skills
> live exclusively in [`skills/`](../skills). This folder
> sits in the same repository only so the utilities ship in the same git repo. Nesting
> is packaging, not status: nothing here participates in the lifecycle, and no
> framework rule reaches down into this folder unless it says so explicitly.

Read a skill's own `SKILL.md` for what it does — this file deliberately keeps no
inventory, because a list here is a second place to update and the first one to go
stale.

## What belongs here

A skill belongs in this folder when it stands alone: it takes an input, produces an
output, and no other skill needs to have run first or runs after. A skill that
reads or writes a framework artifact, or that sits behind a gate, is a framework
skill and belongs one level up.

## Invocation mode

- **Model-invoked** (`draw-diagram`, `sync-pr`, `write-pr-desc`, `write-skill`): Automatically discovered and invoked by AI models whenever performing their matching tasks.
- **User-invoked** (`disable-model-invocation: true`): Interactive utilities (`write-docs`, `lv1-architecture-review`, `naver-api-extractor`, `lotteon-api-extractor`) that run only when explicitly typed by the human.
