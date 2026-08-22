# ai-framework

Steve's workspace for building, testing, and refining Claude skills.

## Read before acting
- `ai-agent-paths.md` — before any question of where a skill or plugin folder lives, where to install or scaffold one, or what a manifest is named. The file is the source; memory is not.
- a script's module docstring — before running or changing that script.

## Permissions
Outside this repo: one file per question. Name the file, wait for the answer, touch that file only. A blanket "ok" over a list grants nothing, and neither does an approved plan.

## Where things live
- `ai-first-fw/skills/` — the six AI-First FW skills (`analysis-handoff`, `implementation-planner`, `specs-builder`, `plan-reviewer`, `specs-reviewer`, `code-reviewer`), direct children, nowhere else. Default place to read from and write to. A skill here wins over an installed skill of the same name; if you fall back to an installed copy, say so.
- `ai-first-fw/utilities/` — standalone skills outside the lifecycle; separate install source.
- `ai-first-fw/local-report-servers/` — live report and dashboard servers (managed by `portal.py` on port 24000).
- `ai-first-fw/local-theme/` — single source of truth for the shared dark report theme (`theme.css`, `theme.js`, `theme.json`).
- `ai-first-fw/local-test-servers/` — mock HTTP servers and integration test suites for partner APIs.
- `ai-first-fw/local-mcps/` — local Model Context Protocol (MCP) servers (Jira attachments, Kibana KQL log search). Each is a self-contained folder: `server.py`, `.env` (git-ignored) beside `.env.sample`, `requirements.txt`, `setup.sh`, its own `.venv`, and offline tests. Registered for this repo in `.mcp.json` at the root.
- `audits/` — one skill review per file, `<skill-name>-<YYYY-MM-DD>.md`. Never inside a skill folder.
- `scripts/` — all runnable tooling, and where new tooling goes.
- `docs/adr/` — one decision per file, numbered. Reasoning too broad for any one skill.
- `_to_delete/` — what is on its way out. `device_bash` cannot delete, so anything an agent retires lands here and a human empties it.

## Versioning Policy (Skills & Plugins)
- **Skill Versioning**: Every skill MUST declare a `version` (e.g. `0.7.1`, `1.0.0`) in its `SKILL.md` YAML frontmatter. Skills version independently — versions do NOT need to stay in lockstep across skills inside the plugin.
- **Plugin Patch Version (`x.y.Z` → `x.y.Z+1`)**: Bumped whenever *any* individual skill version inside the plugin increases.
- **Plugin Minor Version (`x.Y.0` → `x.Y+1.0`)**: Bumped when a *new skill* is added, OR when *more than 3 skills* are updated simultaneously.
- **Plugin Major Version (`X.0.0` → `X+1.0.0`)**: Bumped when *more than 5 skills* undergo significant changes (modifying >20% of lines in their `SKILL.md` files).

## Conventions
- Cite a section by job *and* number — "the test contract (plan §4)". A bare job name is a finding; so is a bare number.
- Files under a skill's `references/` are lower-kebab. Two still have one — `plan-reviewer` (`mapping-rules.md`) and the `lv1-architecture-review` utility. The other five carry no `references/` at all: their rules live in `SKILL.md` and in the templates' own comments, which is the direction the rest are going.
- `grade` is skill-scoped and does not travel: it is the Source column in `analysis-handoff` (what you read for a row), the Confidence column in `specs-builder` (`A`/`B`/`C`, how sure you are). Never spend the word on a Status or Reach column — both take `unknown`, so the check ends up with three readings.
- No document writes down how many comments a template holds. A run deletes the sections it has nothing for, and deleting a section deletes its comment, so any count is wrong on the ordinary run — `analysis-handoff` carried "twelve" in four places until 2026-08-18. Name the structure; the copy is the source of truth for what survives.
- A skill that fills a copy of a template opens that copy in its first step, before any reading. `analysis-handoff` created it in Step 2 until 2026-08-18, so Step 1's sub-agent returns had nowhere to land and were transcribed from memory later — the exact failure its own self-check hunts for.
- `analysis-handoff` (Steps 3 and 4) and `specs-builder` (stages 5 and 6) each keep their self-check and their strip as separate steps: merging them puts an irreversible act in view while the demanding work is still going, which is what invites the rush to be done. A sub-agent checker was weighed and rejected 2026-08-18 — it needs the copy and every comment passed to it explicitly, and sharpening the step's bound was the cheaper defence. Take the sub-agent if the rush still shows up in practice.

## Audits
- An audit lives only while its findings are unapplied. Empty `audits/` is the normal state; a file there means work outstanding.
- Applying one ends in promotion, then deletion: move what is durable — a decision's reasoning, an option deliberately rejected — into the skill's `SKILL.md` or a sibling reference file, then delete the audit. Test: could a reader rebuild the thing the audit argued against?
- For context on a skill, read the skill.

## Tooling & Plugin Rules
- Plugins and marketplaces are the canonical delivery mechanism:
  - Claude Code Marketplace: `.claude-plugin/marketplace.json` defines `ai-first-fw-skills` and `ai-first-fw-utilities`.
  - Install via `claude plugin install ai-first-fw-skills@ai-framework` or `claude plugin install ai-first-fw-utilities@ai-framework`.
  - Antigravity Unified Engine: Shared across CLI (`agy`), Desktop App 2.0, and IDE via `~/.gemini/config/plugins/` and `.agents/skills.json`.
- Do not create manual symlinks into `~/.claude/skills/` or `~/.gemini/config/skills/`. All tools discover skills through plugin manifests and declarative registries.

## Report Pages & Dashboards
- All report, viewer, and dashboard pages across the repository MUST use the shared dark developer theme from `ai-first-fw/local-theme/` (`theme.css`, `theme.js`, `theme.json`).
- Live report servers live under `ai-first-fw/local-report-servers/` and are registered in `portal.py` (`KNOWN_SERVERS`).