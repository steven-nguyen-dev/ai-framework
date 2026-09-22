# Herdr Swarm Leader — Technical Reference & Maintenance Guide

_Developer guide, component map, and implementation details for the `lead` skill and its execution engine._

---

## 1. Package Layout

The `lead` utility skill resides in `ai-framework/lv1-utilities/lead/`:

```
lead/
├── SKILL.md                  # Orchestrator directives, tiered roles, and operational steps
├── README.md                 # This technical reference and maintenance manual
└── scripts/
    └── pane-limits.py        # Core CLI engine (spawning, auto-naming, token limits, pre-flight prompt)
```

- **[`SKILL.md`](SKILL.md)**: User-invoked skill instructions (`disable-model-invocation: true`). Contains the `## Standing Orchestrator Directives` anchor that `pane-limits.py` dynamically extracts into the Claude Swarm Leader.
- **[`scripts/pane-limits.py`](scripts/pane-limits.py)**: The Python 3 script powering geometric sorting, worker auto-naming, token usage checks, and leader prompt generation.

---

## 2. CLI Tool & Slash Command

The skill operates entirely within Claude Code via its slash command and calls `pane-limits` from `$PATH`:

| Tool / Command | Purpose |
|---|---|
| `/lead` | Native slash command in Claude Code to claim leadership, spawn workers, and load directives. |
| `/lead <agent1, agent2, ...>` | Slash command with manual agent list (e.g. `/lead clan, cus, agg, agr`) to dynamically partition and spawn. |
| `~/.local/bin/pane-limits` | Main CLI helper. Checks token usage/headroom, initializes leader, or spawns dynamic swarm teams. |
| `pane-limits --spawn <cmd1,cmd2...>` | Partitions the tab (leader 50% left, $N$ workers right), launches agents, and outputs leader prompt. |
| `~/.local/bin/{clan,clone,agp,agr,agg,cus,gpt}` | Standard agent launchers (Claude, Gemini Flash, Gemini Pro, Grok, Cursor, GPT). |

---

## 3. Runtime Settings & Hooks

- **`~/.claude/settings.json` & `~/.claude-clone/settings.json`**:
  - Configures the session hook `~/.claude/hooks/herdr-agent-state.sh`.
  - Enforces `disallowedTools: ["Artifact", "ScheduleWakeup", "SendFeedback"]` to reduce initial token overhead.
- **`~/.claude/hooks/herdr-agent-state.sh`**:
  - Reports Claude session events directly to the Herdr UNIX domain socket (`$HERDR_SOCKET_PATH`) for live agent state tracking.

---

## 4. How the Engine Works (`pane-limits.py`)

### A. Geometric Sorting & Per-Model Renaming (`auto_name_panes()`)
1. Retrieves layout coordinates from `herdr pane layout --pane <leader_pane>`.
2. Sorts worker panes strictly by visual screen position: top-to-bottom, then left-to-right.
3. Detects model family via Herdr agent kind, terminal titles, or terminal buffer inspection.
4. Generates name as `<space_tag>-<model>-<n>`:
   - `space_tag` is the 3-letter prefix of the Herdr workspace (e.g. `one`, `zer`, `two`, `aif`).
   - Counter resets from `1` per model prefix strictly within the active tab.
   - Example: `one-opus-1`, `one-gemini-1`, `one-gemini-2`, `one-gpt-1`.
   - Leader is renamed to `<space_tag>-opus-leader`.

### B. Model Token Limits (Big Pool + Default Architecture)
Token limits are evaluated in `get_model_target_limit()`:
- **1M+ Big Pool (`gemini`, `claude`, `gpt`/`codex`)**:
  - Target ceiling: `<700K` (`BIG_POOL_LIMIT_K = 700.0`).
- **Default Fallback (All other models & unknown)**:
  - Target ceiling: `<210K` (`DEFAULT_LIMIT_K = 210.0`).

### C. Model Roles (`get_model_role()`)
- `opus` / `claude` $\rightarrow$ `Top tier (High complexity)`
- `gemini` / `agy` $\rightarrow$ `Workhorse (Normal & bulk work)`
- All other models $\rightarrow$ `Simple (Fire & forget)`

### D. Leader Pre-flight Injection (`generate_leader_prompt()`)
1. Formats the live active worker roster table including Target Name, Pane ID, Model, Recommended Role, Explicit Limit, Status, and Current Usage.
2. Dynamically loads `## Standing Orchestrator Directives` from `SKILL.md` (or embedded self-contained fallback with hardcoded `swarm-coordinator` and `wiki` MCPs).
3. Injected into Claude Code on startup via `--append-system-prompt "$leader_prompt"`.

---

## 5. Developer Maintenance Guide

### To Add a Model to the 1M+ Big Pool
- **File**: [`scripts/pane-limits.py`](scripts/pane-limits.py)
- **Function**: `get_model_target_limit()`
- Add the model identifier string to the `any(m in combined for m in [...])` check. Unlisted models automatically fall back to `<210K`.

### To Adjust Leader Directives
- **File**: [`SKILL.md`](SKILL.md)
- Edit under `## Standing Orchestrator Directives`. The engine extracts from this marker onward.
- If editing default fallback directives when `SKILL.md` is unmounted, update `load_lead_skill_directives()` in `scripts/pane-limits.py`.

### To Test Prompt Generation & Capacity
```bash
# Dynamically spawn arbitrary agents (e.g. Claude, Grok, Gemini, Gemini)
pane-limits --spawn clan,cus,agg,agr

# Verify pre-flight leader prompt generation
pane-limits --init-leader

# View compact summary table for active tab
pane-limits

# Check capacity and verdict for a specific worker
pane-limits <target-worker-name>
```
