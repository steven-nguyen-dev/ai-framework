# ai-framework

Steve's workspace for building, testing, and refining AI skills, plugins, and local MCP servers.

## Style
- `make-it-short` holds this workspace's writing limits and wording rules. Automatically invoke and apply it whenever the user requests or demands brevity, conciseness, directness, compact documentation, or shortened text. Once activated in a session, all subsequent writing and responses in that session must follow these rules until instructed otherwise.
- When reporting information to me, be extremely concise and sacrifice grammar for the sake of concision.
- Dereference every name before you write it — chat, docs, commits. A system to its full reach; a flow to its originator, every hop, its sink; a property, host or module name to the value it resolves to. Names drift from their targets and never say so.
- Stop where evidence stops. Every verb you write is one you read in the source; elsewhere the line reads `unknown` or `not found by this search`.
- Report each finding once.

## Managed Repositories
This workspace manages two repositories:
1. **`ai-framework`** (`https://github.com/steven-nguyen-dev/ai-framework`) — Primary monorepo containing plugins, skills, and local MCP servers.
2. **`ai-first-framework-skills`** (`https://github.com/nguyennguyen-anchanto/ai-first-framework-skills`) — Public skills and marketplace distribution repository.

## Pre-Requisites & Orientation
- Check a module's docstring for usage instructions before running or modifying it.
- Never introduce symlinks: maintain pure physical directories and direct paths across all plugins.

## Permissions & Scope
- For modifications outside this repository, request explicit confirmation naming the specific target file before editing.

## Repository Layout
- `lv1-mcp/` — Local stdio MCP servers plugin (`lv1-mcps`): `jira-reader`, `kibana-explorer`, `wiki`, `coordinator`.
- `lv1-fw-skills/` — Core lifecycle skills plugin (`lv1-fw-skills`): `write-analysis`, `implementation-planner`, `specs-builder`, `review-code`.
- `lv1-utilities/` — Standalone engineering utilities plugin (`lv1-utilities`): diagrams, extractors, PR sync, etc.
- `research/` — Research documents, audits, and asset files.

## Versioning Policy
- **Skill Version**: Every skill declares a `version` (e.g. `1.0.0`) in its `SKILL.md` frontmatter, versioning independently.
- **Plugin Patch (`x.y.Z` → `x.y.Z+1`)**: Increment when any individual skill or server within the plugin updates.
- **Plugin Minor (`x.Y.0` → `x.Y+1.0`)**: Increment when a new skill/server is added or when more than 3 skills update simultaneously.
- **Plugin Major (`X.0.0` → `X+1.0.0`)**: Increment when more than 5 skills undergo significant architectural changes.

## Conventions
- Reference files under a skill's directory use lower-kebab-case.
- `grade` is scoped specifically to:
  - Source column in `analysis-handoff` (reading source).
  - Confidence column in `specs-builder` (`A` / `B` / `C`).
- Skills opening a template copy create the working file in their initial step before gathering context.
- Keep self-check and strip operations as separate sequential steps.

## Plugin & Marketplace Management
- Claude Code Marketplace: `.claude-plugin/marketplace.json` defines `lv1-mcps`, `lv1-fw-skills`, and `lv1-utilities`.
- Install plugins via `claude plugin install <plugin>@ai-framework`.
- Antigravity & Gemini discovery operates through plugin manifests and `.agents/skills.json`.