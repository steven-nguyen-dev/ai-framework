# Local MCP Servers

This directory contains Model Context Protocol (MCP) servers designed for local developer tool integrations and AI agent capabilities.

---

## 🔐 Security & Environment Standard (.env.sample)

Every MCP server requiring authentication follows a strict security standard:

1. **`.env` files are strictly gitignored**:
   * Real usernames, passwords, API tokens, and cookies must **NEVER** be committed to version control.
   * `*.env` is enforced by `.gitignore` across the entire repository.
2. **Every tool ships a `.env.sample` template**:
   * Contains dummy placeholder values with clear documentation for each required variable.
3. **Automated Setup (`setup.sh`)**:
   * Running `./setup.sh` in any MCP directory automatically copies `.env.sample` -> `.env` if `.env` does not already exist, and reminds the developer to fill in their personal credentials.

---

## 🛠 Available MCP Servers

| MCP Server | Description | Transport / Protocol | Setup Command |
| :--- | :--- | :--- | :--- |
| **[`jira`](jira/)** | Jira issue metadata, description parsing, attachment downloads | stdio (FastMCP) | `bash ai-first-fw/local-mcps/jira/setup.sh` |
| **[`kibana`](kibana/)** | Kibana enterprise logs search via KQL with session cookie auth | stdio (FastMCP) | `bash ai-first-fw/local-mcps/kibana/setup.sh` |

---

## 🚀 Quick Setup

```bash
# 1. Set up Jira MCP (auto-creates .env from .env.sample)
bash ai-first-fw/local-mcps/jira/setup.sh

# 2. Set up Kibana MCP (auto-creates .env from .env.sample)
bash ai-first-fw/local-mcps/kibana/setup.sh
```
