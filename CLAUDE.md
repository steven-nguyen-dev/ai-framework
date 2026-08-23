# ai-framework

Steve's workspace for building, testing, and refining AI skills, utilities, and local report servers.

## Managed Repositories
This workspace manages two repositories:
1. **`ai-framework`** (`https://github.com/steven-nguyen-dev/ai-framework`) — Primary monorepo containing skills, utilities, test harnesses, local report servers, and shared theme tokens.
2. **`ai-first-framework-skills`** (`https://github.com/nguyennguyen-anchanto/ai-first-framework-skills`) — Public skills and marketplace distribution repository.

## Pre-Requisites & Orientation
- Consult `ai-agent-paths.md` for canonical locations of skills, plugins, and manifests.
- Check a module's docstring for usage instructions before running or modifying it.

## Permissions & Scope
- For modifications outside this repository, request explicit confirmation naming the specific target file before editing.

## Repository Layout
- `ai-first-fw/skills/` — Core 6-stage lifecycle skills (`analysis-handoff`, `implementation-planner`, `specs-builder`, `plan-reviewer`, `specs-reviewer`, `code-reviewer`). Default location for lifecycle skills.
- `ai-first-fw/utilities/` — Standalone engineering utilities and API extractors.
- `ai-first-fw/local-report-servers/` — Local report and dashboard servers (managed by `portal.py` on port 24000).
- `ai-first-fw/local-theme/` — Shared dark report theme source of truth (`theme.css`, `theme.js`, `theme.json`).
- `ai-first-fw/local-test-servers/` — Mock HTTP servers and integration test suites for partner APIs.
- `ai-first-fw/local-mcps/` — FastMCP servers (Jira issue streaming, Kibana log search), each self-contained with its own `.venv` and `.env.sample`.
- `audits/` — Active skill reviews, formatted as `<skill-name>-<YYYY-MM-DD>.md`.
- `_to_delete/` — Staging area for deprecated files awaiting removal.

## Versioning Policy
- **Skill Version**: Every skill declares a `version` (e.g. `1.0.0`) in its `SKILL.md` frontmatter, versioning independently.
- **Plugin Patch (`x.y.Z` → `x.y.Z+1`)**: Increment when any individual skill within the plugin updates.
- **Plugin Minor (`x.Y.0` → `x.Y+1.0`)**: Increment when a new skill is added or when more than 3 skills update simultaneously.
- **Plugin Major (`X.0.0` → `X+1.0.0`)**: Increment when more than 5 skills undergo significant architectural changes.

## Conventions
- Cite sections by job and number (e.g., "the test contract (plan §4)").
- Reference files under a skill's directory use lower-kebab-case.
- `grade` is scoped specifically to:
  - Source column in `analysis-handoff` (reading source).
  - Confidence column in `specs-builder` (`A` / `B` / `C`).
- Skills opening a template copy create the working file in their initial step before gathering context.
- Keep self-check and strip operations as separate sequential steps.

## Audits & Findings
- An audit file remains in `audits/` while its findings are being addressed.
- Once addressed, promote durable rationale into the skill's `SKILL.md` or reference files and clear the audit file.

## Plugin & Marketplace Management
- Claude Code Marketplace: `.claude-plugin/marketplace.json` defines `ai-first-fw-skills` and `ai-first-fw-utilities`.
- Install plugins via `claude plugin install <plugin>@ai-framework`.
- Antigravity & Gemini discovery operates through plugin manifests and `.agents/skills.json`.
- Discover and manage plugins and skills through the local dashboard at `http://localhost:24003` (`ai-skills-report`).

## Dashboards & Local Servers
- All report, viewer, and test dashboards use the shared dark theme tokens from `ai-first-fw/local-theme/`.
- Manage live local servers through the Central Reports Portal (`portal.py` on port 24000).