# Jira Reader MCP Server (`jira-reader`)

Zero-dependency universal MCP server for Jira issue inspection, comments retrieval, JQL searches, board and sprint reads (Agile API `/rest/agile/1.0`), dashboard and gadget reads, attachment downloads, and text/log streaming. Uses Python 3 standard library only.

---

## ⚙️ Configuration & Setup

### 1. Credentials File
Create or edit `~/.mcp/jira-reader.env` (or a local `.env` in this directory):

```ini
# Jira Cloud Authentication
JIRA_HOST=https://your-domain.atlassian.net
JIRA_EMAIL=your.email@anchanto.com
JIRA_API_TOKEN=your_atlassian_api_token

# Optional: Download directory for attachments (defaults to .scratchpads/downloads)
JIRA_DOWNLOAD_DIR=.scratchpads/downloads

# Optional: For Jira Server / Data Center using Personal Access Token (PAT):
# JIRA_BEARER_TOKEN=your_pat_token
```

> **API Token Generation:** Generate a Jira API token at [id.atlassian.com/manage-profile/security/api-tokens](https://id.atlassian.com/manage-profile/security/api-tokens).

### 2. Verify Connectivity
Test credentials and Jira API access directly:
```bash
python3 server.py --test
```

### 3. Running as MCP Server
Run over stdio transport:
```bash
python3 server.py
```

---

## 🛠 Available MCP Tools

| Tool | Parameters | Description |
| :--- | :--- | :--- |
| `jira_get_issue` | `issue_key` | Complete issue details: summary, description (ADF parsed), status, assignee, parent, subtasks, issue links, custom fields, screen fields (with required flags), comments, and attachments. |
| `jira_get_comments` | `issue_key`, `start_at`, `max_results`, `order_by` | Paginated comments with author details and timestamps. |
| `jira_search_issues` | `jql`, `max_results`, `start_at` | JQL search query returning matching issues with comment/attachment counts. |
| `jira_get_board` | `board` | Board setup: type, location, saved filter ID + JQL, sub-query, columns with statuses. `board` = ID or board URL. |
| `jira_board_issues` | `board`, `scope`, `jql`, `max_results`, `start_at` | Board issues in rank order, tagged with column, sprint, epic, flag. `scope`: `board` or `backlog`. |
| `jira_board_sprints` | `board`, `state`, `max_results`, `start_at` | Sprints on a scrum board (`active`, `future`, `closed`). Kanban → `supports_sprints: false`. |
| `jira_sprint_issues` | `sprint_id`, `board`, `jql`, `max_results`, `start_at` | Issues in one sprint; `board` adds column mapping. |
| `jira_get_dashboard` | `dashboard`, `include_issues`, `max_issues_per_gadget` | Dashboard name, owner, sharing, and each gadget's title, type, position, saved settings and source (filter + JQL, project, or JQL). `include_issues` runs each gadget's JQL. Chart values not exposed by the API. |
| `jira_list_attachments` | `issue_key` | Lists attachment filenames, sizes, MIME types, and download URLs. |
| `jira_read_text_attachment` | `attachment_id`, `max_chars` | Streams log, CSV, JSON, or text attachments directly into model context. |
| `jira_download_attachment` | `attachment_id`, `filename`, `output_dir` | Downloads a specific attachment file to local disk. |
| `jira_download_all_attachments`| `issue_key`, `output_dir` | Batch downloads all attachments for a ticket into an issue-named directory. |
| `jira_configure` | `host`, `email`, `api_token` | Configure and persist credentials interactively in session. |
