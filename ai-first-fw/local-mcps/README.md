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
   * Running `python3 server.py --init-env` (in `jira-reader`) or `./setup.sh` (in `kibana-explorer`) automatically seeds `.env` from `.env.example` if `.env` does not already exist, and reminds the developer to fill in their personal credentials.
   * `kibana-explorer/launch.sh` — the entry point `.mcp.json` invokes — performs the same `.env` seeding and builds `.venv` if it is missing, so a fresh clone starts without a manual setup step.

---

## 🛠 Available MCP Servers

| MCP Server | Description | Transport / Protocol | Setup / Diagnostics |
| :--- | :--- | :--- | :--- |
| **[`jira-reader`](jira-reader/)** | Jira issue metadata, ADF description parsing, JQL search, batch attachment downloads & text streaming | stdio (Zero-Dependency Python stdlib) | `python3 ai-first-fw/local-mcps/jira-reader/server.py --test` |
| **[`kibana-explorer`](kibana-explorer/)** | Kibana enterprise logs search via KQL with browser-like session cookie auth | stdio (FastMCP) | `bash ai-first-fw/local-mcps/kibana-explorer/launch.sh --selftest` |

---

## 🚀 Quick Setup & Claude Code Integration

### 1-Click Global Claude Code Setup (Interactive)
```bash
# Set up Jira Reader MCP globally in Claude Code
bash ai-first-fw/local-mcps/jira-reader/install-claude.sh

# Set up Kibana Explorer MCP globally in Claude Code
bash ai-first-fw/local-mcps/kibana-explorer/install-claude.sh
```

### Local Workspace Setup & Diagnostics
```bash
# Test Jira Reader connection
python3 ai-first-fw/local-mcps/jira-reader/server.py --init-env
python3 ai-first-fw/local-mcps/jira-reader/server.py --test

# Bootstrap & test Kibana Explorer
bash ai-first-fw/local-mcps/kibana-explorer/setup.sh
bash ai-first-fw/local-mcps/kibana-explorer/launch.sh --selftest
```
