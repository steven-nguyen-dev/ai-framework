# Jira Attachment MCP Server

A local [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server built to interact with Jira, specifically designed to solve the limitation of standard plugins by providing full attachment downloading, streaming, and inspection capabilities.

---

## Features

- 📥 **Download Single Attachments**: Download any attachment by ID with automatic name resolution to a local directory.
- 📦 **Batch Download**: Download all attachments from a given Jira issue with a single command.
- 📄 **Direct Text Attachment Reader**: Stream and read log files, CSVs, JSON, code snippets, and text attachments directly into the AI agent's context without writing to disk.
- 🔍 **Issue & Attachment Metadata**: Fetch full issue details, descriptions (with Atlassian Document Format ADF decoding), and attachment metadata (size, MIME type, author, creation date).
- 🔎 **JQL Search**: Search issues with attachment counts and summaries.
- 🔒 **Secure Auth**: Supports both Jira Cloud (Email + API Token) and Jira Server / Data Center (Personal Access Token).

---

## Project Structure

```
ai-first-fw/local-mcps/jira/
├── .venv/             # Dedicated Python virtual environment
├── .env.sample        # Template for Jira credentials
├── requirements.txt   # Python dependencies
├── server.py          # FastMCP server implementation
└── README.md          # Documentation and setup guide
```

---

## Setup & Installation

The virtual environment in [`ai-first-fw/local-mcps/jira/.venv`](file:///Users/nguyennguyen.anchanto/Projects/ai-framework/ai-first-fw/local-mcps/jira/.venv) has already been created and populated.

If you ever need to recreate it on macOS:
```bash
# 1. Create a dedicated virtual environment
python3 -m venv ai-first-fw/local-mcps/jira/.venv

# 2. Install dependencies into the virtual environment
./ai-first-fw/local-mcps/jira/.venv/bin/pip install -r ai-first-fw/local-mcps/jira/requirements.txt
```

---

## Configuration

### 1. Set Your Jira Credentials

Copy the `.env.sample` file:
```bash
cp ai-first-fw/local-mcps/jira/.env.sample ai-first-fw/local-mcps/jira/.env
```

Edit [`ai-first-fw/local-mcps/jira/.env`](file:///Users/nguyennguyen.anchanto/Projects/ai-framework/ai-first-fw/local-mcps/jira/.env):
```env
JIRA_HOST=https://your-domain.atlassian.net
JIRA_EMAIL=your-email@company.com
JIRA_API_TOKEN=your_jira_api_token
JIRA_DOWNLOAD_DIR=./downloads
```

> **How to get a Jira API Token:**
> 1. Log in to [Atlassian Account Security](https://id.atlassian.com/manage-profile/security/api-tokens).
> 2. Click **Create API token**.
> 3. Copy the token and paste it into `JIRA_API_TOKEN`.

---

## MCP Client Configuration

By pointing the MCP client directly to the Python binary inside the virtual environment (`ai-first-fw/local-mcps/jira/.venv/bin/python3`), you don't need to manually activate the virtualenv.

### Antigravity (`~/.gemini/config/mcp_config.json`)

```json
{
  "mcpServers": {
    "jira": {
      "command": "/Users/nguyennguyen.anchanto/Projects/ai-framework/ai-first-fw/local-mcps/jira/.venv/bin/python3",
      "args": [
        "/Users/nguyennguyen.anchanto/Projects/ai-framework/ai-first-fw/local-mcps/jira/server.py"
      ]
    }
  }
}
```

### Claude Desktop (`claude_desktop_config.json`)

```json
{
  "mcpServers": {
    "jira": {
      "command": "/Users/nguyennguyen.anchanto/Projects/ai-framework/ai-first-fw/local-mcps/jira/.venv/bin/python3",
      "args": [
        "/Users/nguyennguyen.anchanto/Projects/ai-framework/ai-first-fw/local-mcps/jira/server.py"
      ]
    }
  }
}
```

---

## Available MCP Tools

| Tool | Parameters | Description |
| :--- | :--- | :--- |
| `jira_get_issue` | `issue_key` | Retrieves issue details, description, status, and all attachment metadata. |
| `jira_list_attachments` | `issue_key` | Lists all attachments with IDs, filenames, MIME types, and sizes. |
| `jira_download_attachment` | `attachment_id`, `filename` *(opt)*, `output_dir` *(opt)* | Downloads a specific attachment and saves it to local disk. |
| `jira_download_all_attachments` | `issue_key`, `output_dir` *(opt)* | Downloads all attachments of an issue to a directory (e.g. `./downloads/<KEY>`). |
| `jira_read_text_attachment` | `attachment_id`, `max_chars` *(opt)* | Fetches and reads text/log/CSV attachments directly in memory. |
| `jira_search_issues` | `jql`, `max_results` *(opt)* | Searches issues via JQL with attachment summaries. |
