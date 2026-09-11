# Herdr Swarm Leader — Technical Reference & Maintenance Guide

_Developer guide, component map, and implementation details for the `herdr-leader` skill and its execution engine._

---

## 1. Package Layout

The `herdr-leader` utility skill resides in `ai-framework/ai-first-fw/utilities/herdr-leader/`:

```
herdr-leader/
├── SKILL.md                  # Orchestrator directives, tiered roles, and operational steps
├── README.md                 # This technical reference and maintenance manual
└── scripts/
    └── pane-limits.py        # Core CLI engine (spawning, auto-naming, token limits, pre-flight prompt)
```

- **[`SKILL.md`](file:///Users/nguyennguyen.anchanto/Projects/ai-framework/ai-first-fw/utilities/herdr-leader/SKILL.md)**: User-invoked skill instructions (`disable-model-invocation: true`). Contains the `## Standing Orchestrator Directives` anchor that `pane-limits.py` dynamically extracts into the Claude Swarm Leader.
- **[`scripts/pane-limits.py`](file:///Users/nguyennguyen.anchanto/Projects/ai-framework/ai-first-fw/utilities/herdr-leader/scripts/pane-limits.py)**: The Python 3 script powering layout splitting, worker spawning, geometry sorting, token usage checks, and leader prompt generation.

---

## 2. System Wrappers & CLI Integrations

The skill integrates with the local terminal environment via wrapper binaries in `~/.local/bin/`:

| Path | Purpose |
|---|---|
| `~/.local/bin/pane-limits` | Main CLI wrapper. Calls `pane-limits.py "$@"`. |
| `~/.local/bin/clan-leader`<br/>`~/.local/bin/clone-leader` | Swarm Launchers. Parse spawn options (`3`, `4`, `5`), call `pane-limits.py`, inject `--append-system-prompt "$leader_prompt"`, and launch Claude with preflight greeting. |
| `~/.local/bin/clan-l[3-5]`<br/>`~/.local/bin/clone-l[3-5]` | Convenience shortcuts calling `clan-leader 3`, `clone-leader 4`, etc. |
| `~/.local/bin/{clan,clone,agp,agr,agg,cus,gpt}` | Agent launcher wrappers (Claude, Gemini Flash, Gemini Pro, Grok, Cursor, GPT). |
| `jpluger-shared/scripts/herdr-pane-limits.py` | Backward-compatible symlink pointing to `ai-framework/.../scripts/pane-limits.py`. |

---

## 3. Runtime Settings & Hooks

- **`~/.claude/settings.json` & `~/.claude-clone/settings.json`**:
  - Configures the session hook `~/.claude/hooks/herdr-agent-state.sh`.
  - Enforces `disallowedTools: ["Artifact", "ScheduleWakeup", "SendFeedback"]` to reduce initial token overhead.
- **`~/.claude/hooks/herdr-agent-state.sh`**:
  - Reports Claude session events directly to the Herdr UNIX domain socket (`$HERDR_SOCKET_PATH`) for live agent state tracking.

---

## 4. How the Engine Works (`pane-limits.py`)

### A. Spawning (`spawn_swarm(option_num)`)
1. Confirms caller tab (`$HERDR_TAB_ID`) and pane (`$HERDR_PANE_ID`).
2. Closes all other existing panes in the active tab via `herdr pane close <id>`.
3. Splits the leader pane into the left 50% (`ratio=0.5`).
4. Iteratively subdivides the right 50% into worker slots:
   - **Option 3 (`clan-l3`)**: `clan` (Opus), `agp` (Gemini), `agr` (Gemini) — 2 Gemini workhorses.
   - **Option 4 (`clan-l4`)**: `clan` (Opus), `agp` (Gemini), `agr` (Gemini), `agg` (Gemini) — 3 Gemini workhorses.
   - **Option 5 (`clan-l5`)**: `clan` (Opus), `agp` (Gemini), `agr` (Gemini), `cus` (Grok), `gpt` (GPT) — 2 Gemini, 1 Grok, 1 GPT.
5. Launches worker agent commands and auto-names all panes.

### B. Geometric Sorting & Per-Model Renaming (`auto_name_panes()`)
1. Retrieves layout coordinates from `herdr pane layout --pane <leader_pane>`.
2. Sorts worker panes strictly by visual screen position: top-to-bottom, then left-to-right.
3. Detects model family via Herdr agent kind, terminal titles, or terminal buffer inspection.
4. Generates name as `<space_tag>-<model>-<n>`:
   - `space_tag` is the 3-letter prefix of the Herdr workspace (e.g. `one`, `zer`, `two`, `aif`).
   - Counter resets from `1` per model prefix strictly within the active tab.
   - Example: `one-opus-1`, `one-gemini-1`, `one-gemini-2`, `one-gpt-1`.
   - Leader is renamed to `<space_tag>-opus-leader`.

### C. Model Token Limits (Big Pool + Default Architecture)
Token limits are evaluated in `get_model_target_limit()`:
- **1M+ Big Pool (`gemini`, `claude`, `gpt`/`codex`)**:
  - Target ceiling: `<650K` (`BIG_POOL_LIMIT_K = 650.0`).
  - High warning threshold: `550.0K`.
- **Default Fallback (All other models & unknown)**:
  - Target ceiling: `<210K` (`DEFAULT_LIMIT_K = 210.0`).
  - High warning threshold: `175.0K`.

### D. Model Roles (`get_model_role()`)
- `opus` / `claude` $\rightarrow$ `Top tier (High complexity)`
- `gemini` / `agy` $\rightarrow$ `Workhorse (Normal & bulk work)`
- All other models $\rightarrow$ `Simple (Fire & forget)`

### E. Leader Pre-flight Injection (`generate_leader_prompt()`)
1. Formats the live active worker roster table including Target Name, Pane ID, Model, Recommended Role, Explicit Limit, Status, and Current Usage.
2. Dynamically loads `## Standing Orchestrator Directives` from `SKILL.md`.
3. Injected into Claude Code on startup via `--append-system-prompt "$leader_prompt"`.

---

## 5. Developer Maintenance Guide

### To Change Worker Presets or Agent Commands
- **File**: [`scripts/pane-limits.py`](file:///Users/nguyennguyen.anchanto/Projects/ai-framework/ai-first-fw/utilities/herdr-leader/scripts/pane-limits.py)
- **Function**: `spawn_swarm(option_num)`
- Modify the `workers` tuples `(pane_id, command, assigned_name)`.

### To Add a Model to the 1M+ Big Pool
- **File**: [`scripts/pane-limits.py`](file:///Users/nguyennguyen.anchanto/Projects/ai-framework/ai-first-fw/utilities/herdr-leader/scripts/pane-limits.py)
- **Function**: `get_model_target_limit()`
- Add the model identifier string to the `any(m in combined for m in [...])` check. Unlisted models automatically fall back to `<210K`.

### To Adjust Leader Directives
- **File**: [`SKILL.md`](file:///Users/nguyennguyen.anchanto/Projects/ai-framework/ai-first-fw/utilities/herdr-leader/SKILL.md)
- Edit under `## Standing Orchestrator Directives`. The engine extracts from this marker onward.
- If editing default fallback directives when `SKILL.md` is unmounted, update `load_lead_skill_directives()` in `scripts/pane-limits.py`.

### To Test Prompt Generation & Capacity
```bash
# Verify pre-flight leader prompt generation
pane-limits --init-leader

# View compact summary table for active tab
pane-limits

# Check capacity and verdict for a specific worker
pane-limits <target-worker-name>
```
