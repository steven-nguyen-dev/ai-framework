# Jira Reader MCP Server (`jira-reader`)

Zero-dependency universal MCP server for Jira issue inspection, comments retrieval, JQL searches, attachment downloads, and text/log streaming (Python 3 standard library only).

---

## 🚀 Quick Setup & Claude Code Integration

### Option A: Interactive Global Setup for Claude Code (Recommended)
Run the automated installer to input credentials, test connection, and register `jira-reader` globally in Claude Code:
```bash
bash ai-first-fw/local-mcps/jira-reader/install-claude.sh
```

### Option B: Manual Setup
1. Copy `.env.example` to `.env` (or run `python3 server.py --init-env`):
```bash
cp .env.example .env
```

2. Open `.env` and fill in your Jira credentials (host, email, API token / PAT).

3. Verify connection:
```bash
python3 server.py --test
```

---

## Available Tools

| Tool | Description |
| :--- | :--- |
| `jira_get_issue` | Complete issue details: summary, status, assignee, description, comments thread with author details, and attachment metadata |
| `jira_get_comments` | Fetch comments for an issue with pagination (`start_at`, `max_results`) and ordering (`created`, `-created`) |
| `jira_search_issues` | JQL search (`jql`, `max_results`) with comment count and attachment count |
| `jira_list_attachments` | List attachments for an issue |
| `jira_read_text_attachment` | Stream log/CSV/JSON text attachment directly into context |
| `jira_download_attachment` | Download single attachment (`attachment_id`, `output_dir`) |
| `jira_download_all_attachments` | Batch download all attachments (`issue_key`, `output_dir`) |

