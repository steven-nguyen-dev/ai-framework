# Local MCP Servers Plugin (`lv1-mcps`)

Independent Claude Code and Antigravity plugin bundling 4 local Model Context Protocol (MCP) servers for enterprise development, log diagnosis, documentation search, and agent orchestration.

---

## 🧩 Included MCP Servers

| Server | Directory | Protocol / Transport | Configuration | Diagnostics |
| :--- | :--- | :--- | :--- | :--- |
| **`jira-reader`** | [`jira-reader/`](jira-reader/) | stdio (Python stdlib) | `~/.mcp/jira-reader.env` | `python3 jira-reader/server.py --test` |
| **`kibana-explorer`** | [`kibana-explorer/`](kibana-explorer/) | stdio (FastMCP) | `~/.mcp/kibana-explorer.env` | `bash kibana-explorer/launch.sh --selftest` |
| **`wiki`** | [`wiki/`](wiki/) | stdio (FastMCP) | `~/.config/wiki-mcp/config.toml` | `echo '{"jsonrpc":"2.0","method":"ping","id":1}' \| bash wiki/launch.sh` |
| **`swarm-coordinator`** | [`coordinator/`](coordinator/) | stdio (FastMCP) | `~/.config/swarm/config.toml` | `echo '{"jsonrpc":"2.0","method":"ping","id":1}' \| bash coordinator/launch.sh` |

---

## ⚙️ Setup & Configuration Overview

Each server manages its own isolated configuration and environment:

1. **Jira Reader**: See [jira-reader/README.md](jira-reader/README.md) for Jira host URL, user email, and API token setup.
2. **Kibana Explorer**: See [kibana-explorer/README.md](kibana-explorer/README.md) for Kibana host URL and user credentials setup.
3. **Wiki**: See [wiki/README.md](wiki/README.md) for PostgreSQL (`pgvector`) DSN and local Ollama embedding configuration.
4. **Swarm Coordinator**: See [coordinator/README.md](coordinator/README.md) for Redis endpoint and swarm session variables.

---

## 🚀 Plugin Registration

This plugin is registered with Claude Code and Google Antigravity via `.claude-plugin/plugin.json`:

```json
{
  "$schema": "https://json.schemastore.org/claude-code-plugin.json",
  "name": "lv1-mcps",
  "version": "1.0.0",
  "mcpServers": {
    "jira-reader": { "command": "python3", "args": ["${CLAUDE_PLUGIN_ROOT}/jira-reader/server.py"] },
    "kibana-explorer": { "command": "bash", "args": ["${CLAUDE_PLUGIN_ROOT}/kibana-explorer/launch.sh"] },
    "wiki": { "command": "bash", "args": ["${CLAUDE_PLUGIN_ROOT}/wiki/launch.sh"] },
    "swarm-coordinator": { "command": "bash", "args": ["${CLAUDE_PLUGIN_ROOT}/coordinator/launch.sh"] }
  }
}
```

No hidden files or duplicate nested directories are required.
