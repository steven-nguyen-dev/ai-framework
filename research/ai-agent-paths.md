# AI agent extension paths — Claude Code & Antigravity

Where skills, plugins, and their manifests live on disk.

**Verification basis:** checked against official docs and local macOS implementation for Claude Code and Antigravity.
All skills are packaged as official marketplace plugins (`.claude-plugin/marketplace.json` & `plugin.json`) and declarative Antigravity registries (`~/.gemini/config/plugins/` & `.agents/skills.json`).

---

## 1. Claude Code

Two extension layers: **skills** (a `SKILL.md` plus optional supporting files)
and **plugins** (bundles of skills, agents, commands, hooks, MCP servers).

### A. Skill locations and precedence

| Scope | Path | Availability |
| --- | --- | --- |
| Enterprise | Set via [managed settings](https://code.claude.com/docs/en/settings#settings-files) | All users in the org |
| Personal | `~/.claude/skills/<skill-name>/SKILL.md` | All your projects |
| Project | `.claude/skills/<skill-name>/SKILL.md` | That project only |
| Plugin | `<plugin>/skills/<skill-name>/SKILL.md` | Wherever the plugin is enabled |

**Precedence:** enterprise overrides personal, personal overrides project. A
skill at any of these levels overrides a bundled skill of the same name. Plugin
skills are namespaced `plugin-name:skill-name`, so they never collide.

**Discovery details:**

- Project skills load from `.claude/skills/` in the startup directory and every
  parent up to the repo root.
- Nested `.claude/skills/` below the startup directory load lazily — the first
  time Claude reads or edits a file in that subdirectory. A nested skill sharing
  a name appears directory-qualified, e.g. `apps/web:deploy`.
- `--add-dir` / `/add-dir` directories also get their `.claude/skills/` loaded.
  The `permissions.additionalDirectories` setting does *not* do this.
- Live reload: adding/editing/removing a skill under `~/.claude/skills/`, the
  project `.claude/skills/`, or an `--add-dir` skills dir takes effect in-session.
  Creating a top-level skills dir that didn't exist at startup needs a restart.
- Legacy: `.claude/commands/<name>.md` still works and is equivalent to
  `.claude/skills/<name>/SKILL.md`. If both exist, the skill wins.

### B. Plugin structure

```text
<plugin-name>/
├── .claude-plugin/
│   └── plugin.json          # Manifest — OPTIONAL, not required
├── skills/                  # <skill-name>/SKILL.md
├── commands/                # Flat .md files (legacy; prefer skills/)
├── agents/                  # Subagent definitions (.md)
├── workflows/               # Workflow scripts
├── output-styles/           # Output style definitions
├── themes/                  # Color themes (.json)
├── monitors/
│   └── monitors.json        # Background monitor config
├── hooks/
│   └── hooks.json           # Event handler config
├── bin/                     # Executables added to the Bash tool's PATH
├── settings.json            # Default settings when plugin is enabled
├── .mcp.json                # MCP server definitions
├── .lsp.json                # LSP server configurations
└── scripts/                 # Hook and utility scripts
```

**Hard rule:** only `plugin.json` goes inside `.claude-plugin/`. Every other
directory must sit at the plugin root. Components inside `.claude-plugin/` are
the most common cause of "skills not appearing".

Hooks, MCP, and LSP config can also be declared inline in `plugin.json` instead
of as separate files.

### C. Installed-plugin storage

| Thing | Path |
| --- | --- |
| Marketplace plugin cache | `~/.claude/plugins/cache` (plugins are copied here, not used in place) |
| Per-plugin data (`${CLAUDE_PLUGIN_DATA}`) | `~/.claude/plugins/data/<id>/` — `<id>` is the plugin identifier with non-`[a-zA-Z0-9_-]` chars replaced by `-`, e.g. `formatter@my-marketplace` → `formatter-my-marketplace` |

**Skills-dir plugins:** any folder under a skills directory that contains
`.claude-plugin/plugin.json` loads as a plugin named `<name>@skills-dir` on the
next session — no marketplace, no install step, discovered in place rather than
copied to the cache. Scaffold with `claude plugin init`.

**Management:** `/plugin` inside a session, or `claude plugin <list|install|
enable|disable|uninstall|validate|init>` from the shell. Changes to a skill's
`SKILL.md` apply immediately; changes to `hooks/`, `.mcp.json`, `agents/`,
`output-styles/` need `/reload-plugins` or a restart.

---

## 2. Antigravity

Antigravity spans three surfaces — **Antigravity 2.0 (desktop)**, **IDE
extension**, and **`agy` CLI**. All three surfaces share a **100% unified customization model**:

### A. Skills & Plugins Discovery

| Surface | Scope | Path |
| --- | --- | --- |
| All surfaces | Workspace | `<workspace-root>/.agents/skills/` & `<workspace-root>/.agents/skills.json` |
| All surfaces | Workspace Plugins | `<workspace-root>/.agents/plugins/` |
| All surfaces | Global Plugins | `~/.gemini/config/plugins/<plugin-name>/` |
| All surfaces | Global Declarative Registry | `~/.gemini/config/skills.json` |
| All surfaces | Built-in Core | `~/.gemini/antigravity/builtin/skills/` |

**Unified Architecture:** Setting up plugins in `~/.gemini/config/plugins/` or declaring them in `~/.gemini/config/skills.json` immediately enables them across CLI, Desktop App, and IDE simultaneously with zero duplication.

**CLI skills are shaped differently.** The CLI docs describe global and workspace
skills as *flat markdown files* (e.g. `.agents/skills/format-tests.md`) that
compile into slash commands, while the IDE/2.0 docs describe *folders* containing
`SKILL.md`. The folder form is the open-standard shape; if a skill must work on
both, use the folder + `SKILL.md` form and test the CLI.

**Skill folder layout** (only `SKILL.md` is required):

```text
.agents/skills/my-skill/
├── SKILL.md       # Main instructions (required)
├── scripts/       # Helper scripts (optional)
├── examples/      # Reference implementations (optional)
└── resources/     # Templates and other assets (optional)
```

**Frontmatter:** `description` is **required**; `name` is optional and defaults
to the folder name. (Note this is the inverse of the `plugin.json` rule below.)

### B. Plugins — `agy` CLI

Installed/imported plugins are staged at:

```text
~/.gemini/antigravity-cli/plugins/<plugin_name>/
├── plugin.json                 # Required package marker file
├── mcp_config.json             # Optional MCP servers
├── hooks.json                  # Optional pre/post tool event hooks
├── skills/                     # Optional skills
├── agents/                     # Optional subagent templates
└── rules/                      # Optional codebase rules files
```

There is **no `<namespace>/` path segment** — plugins stage directly under
`plugins/<plugin_name>/`, despite plugins being described as "namespaced bundles".

**`plugin.json` manifest** — schema is strict (`additionalProperties: false`),
so only these two fields plus `$schema` are accepted:

```json
{
  "$schema": "https://antigravity.google/schemas/v1/plugin.json",
  "name": "my-plugin",
  "description": "A brief description of what my plugin does."
}
```

`name` is required and must match `^[a-zA-Z0-9-_]+$`. `description` is optional.

**Commands:** `agy plugin list`, `agy plugin install /path/to/local/plugin`,
`agy plugin enable|disable <plugin_name>`, `agy plugin uninstall <plugin_name>`.
`plugins` works as a plural alias. Hooks can be inspected in the TUI with
`/hooks`.

### C. Plugins — Desktop / IDE — *unverified*

The following were in the source draft but are **not confirmed** by the official
docs pages I could reach (`/docs/plugins` and `/docs/ide/plugins` are
client-rendered and returned empty shells; no search result corroborated them):

- Global storage `~/.gemini/antigravity/plugins/<namespace>/<plugin-name>/` — *unverified*
- Workspace override `.agents/plugins/` inside the project root — *unverified*
- `agy plugin import <source>` as a subcommand — *unverified*; the docs' prose
  says "install or import", but only `install` appears in the command list
- Config file `~/.gemini/antigravity-cli/settings.json` — *plausible but unverified*;
  the CLI docs reference "your primary `settings.json`" for hooks without giving
  its path

Confirm these by inspecting the machine or loading those two doc pages in a
JS-capable browser before depending on them.

---

## 3. Quick comparison

| Concern | Claude Code | Antigravity |
| --- | --- | --- |
| Skill entrypoint | `SKILL.md` in a named folder | `SKILL.md` in a named folder (CLI also accepts flat `.md`) |
| Project skills | `.claude/skills/` | `.agents/skills/` |
| Personal skills | `~/.claude/skills/` | Varies by surface — see table above |
| Plugin manifest | `.claude-plugin/plugin.json` (optional) | `plugin.json` at plugin root (required) |
| Manifest location | Inside `.claude-plugin/` subdir | Plugin root |
| MCP config | `.mcp.json` | `mcp_config.json` |
| Hooks | `hooks/hooks.json` | `hooks.json` |
| Rules/context | Skills, agents, hooks (not `CLAUDE.md`) | `rules/` directory |
| Required frontmatter | `description` | `description` |

## Sources

- [Claude Code — Extend Claude with skills](https://code.claude.com/docs/en/skills)
- [Claude Code — Plugins reference](https://code.claude.com/docs/en/plugins-reference)
- [Antigravity 2.0 — Agent Skills](https://antigravity.google/docs/skills)
- [Antigravity IDE — Agent Skills](https://antigravity.google/docs/ide/skills)
- [Antigravity CLI — Plugins & Skills](https://antigravity.google/docs/cli/plugins)
