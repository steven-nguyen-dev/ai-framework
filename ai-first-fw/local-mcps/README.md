# Local MCP Servers

This directory contains Model Context Protocol (MCP) servers designed for local developer tool integrations and AI agent capabilities.

---

## 🔐 Security & Environment Standard (.env.example)

Every MCP server requiring authentication follows a strict security standard:

1. **`.env` files are strictly gitignored**:
   * Real usernames, passwords, API tokens, and cookies must **NEVER** be committed to version control.
   * `*.env` is enforced by `.gitignore` across the entire repository.
2. **Every tool ships a `.env.example` template**:
   * Contains dummy placeholder values with clear documentation for each required variable.
3. **Automated Setup (`setup.sh` / `--init-env`)**:
   * Running `bash setup.sh` at the root of `local-mcps/` provides a unified interactive wizard to configure both Jira and Kibana credentials, test connections, and save configurations.
   * `kibana-explorer/launch.sh` automatically seeds `.env` and builds `.venv` if missing.

---

## 🛠 Available MCP Servers

| MCP Server | Description | Transport / Protocol | Setup / Diagnostics |
| :--- | :--- | :--- | :--- |
| **[`jira-reader`](jira-reader/)** | Jira issue metadata, ADF description parsing, JQL search, batch attachment downloads & text streaming | stdio (Zero-Dependency Python stdlib) | `python3 ai-first-fw/local-mcps/jira-reader/server.py --test` |
| **[`kibana-explorer`](kibana-explorer/)** | Kibana enterprise logs search via KQL with browser-like session cookie auth | stdio (FastMCP) | `bash ai-first-fw/local-mcps/kibana-explorer/launch.sh --selftest` |

---

## 🚀 Unified 1-Click Setup & Configuration

### Option A: Interactive Wizard (Terminal)
Run the single unified setup script to configure both Jira and Kibana credentials and test connectivity:
```bash
bash ai-first-fw/local-mcps/setup.sh
```

### Option B: Inside Claude Code (Plugin Command)
If you have installed the `ai-first-fw-mcps` plugin, run:
```bash
/ai-first-fw-mcps:config
```

### Option C: Individual Component Setup
```bash
# Jira Reader only
bash ai-first-fw/local-mcps/jira-reader/install-claude.sh

# Kibana Explorer only
bash ai-first-fw/local-mcps/kibana-explorer/install-claude.sh
```

---

## 🔄 Verification in Claude Code

1. Reload plugins:
   ```bash
   /reload-plugins
   ```
2. Check MCP status:
   ```bash
   /mcp
   ```
   Both `jira-reader` and `kibana-explorer` should display `● connected`.
