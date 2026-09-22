# Swarm Coordinator MCP Server (`swarm-coordinator`)

Model Context Protocol server for inter-agent task delegation, scratchpad data sharing, status reporting, and event streaming across multi-agent swarms. Backed by Redis with Herdr pane prompt integration.

---

## ⚙️ Configuration & Setup

### 1. Configuration File
Reads from `~/.config/swarm/config.toml` (or `SWARM_CONFIG` env var):

```toml
[redis]
# Dedicated host port 26379 avoids collisions with default Redis on 6379
url = "redis://127.0.0.1:26379/0"

[herdr]
# Prompt command to submit wake-up notifications to worker agent panes
prompt_argv = ["herdr", "agent", "prompt", "{pane}", "{text}"]
prompt_timeout_s = 10.0

[limits]
ttl_seconds = 604800          # 7 days key expiration in Redis
body_max_words = 200
summary_max_words = 120
complete_summary_max_lines = 3
scratch_max_bytes = 16777216  # 16 MB maximum size for scratch payloads
```

### 2. Environment Variables
When running inside a multi-agent session, the swarm launcher exports these variables into each pane:
- `SWARM_SESSION_ID`: Active session identifier (isolates Redis keys under `swarm:<session-id>:*`).
- `SWARM_LEADER`: Pane identity of the swarm leader (target for task completion notifications).
- `SWARM_PANE`: Identity of the current running agent pane.

### 3. Virtual Environment & Execution
The launcher script automatically creates its virtual environment at `~/.local/share/swarm/venv` and installs dependencies:

```bash
# Run stdio MCP server
bash launch.sh
```

Or via global symlink:
```bash
swarm-coordinator-mcp
```

---

## 🛠 Available MCP Tools

| Tool | Parameters | Description |
| :--- | :--- | :--- |
| `delegate` | `target`, `brief`, `wiki_refs` | Assigns a task to `target` pane, stores `task:<id>`, and prompts the target agent. |
| `complete` | `task_id`, `status`, `summary`, `result` | Concludes a task (`done`, `failed`, `blocked`), stores `result:<id>`, and prompts the leader. |
| `get` | `key` | Reads any key in the current session (`task:*`, `result:*`, `scratch:*`, `roster`). |
| `put` | `key`, `value` | Writes or updates a shared scratchpad payload accessible by session agents. |
| `session_log` | `limit` | Returns the team roster and the latest chronological session activity entries. |
