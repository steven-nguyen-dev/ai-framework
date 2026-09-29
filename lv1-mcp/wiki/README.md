# Wiki & Cloud Files MCP Server (`wiki`)

Engineering knowledge base, architecture documentation retrieval, and cloud storage server. Connects over secure HTTPS to the Central Brain knowledge base and Cloud Files drive at `wiki.concavoi.com`.

---

## ⚙️ Configuration & Transport

- **Endpoint**: `https://wiki.concavoi.com/api/mcp`
- **Transport**: JSON-RPC 2.0 via `mcp-remote` stdio proxy
- **Cloud Files**: `https://files.concavoi.com`

### Credentials Setup
Create `~/.mcp/.wiki.env` with restricted permissions (`chmod 600`):

```bash
WIKI_HOST=https://wiki.concavoi.com/api/mcp
WIKI_API_TOKEN=concobebe!123
```

### Diagnostics & Verification
Run the built-in selftest to verify endpoint connectivity, handshake, and tool discovery:

```bash
bash launch.sh --selftest
```

### Execution
Run the stdio MCP server proxy:

```bash
bash launch.sh
```

---

## 🛠 Available MCP Tools (12 Tools)

### 🧠 Knowledge Base & Wiki Tools
| Tool | Parameters | Description |
| :--- | :--- | :--- |
| `search` | `query`, `source_prefix`, `include_inbox`, `limit` | Hybrid RRF vector + keyword search. Returns snippet cards. |
| `get` | `slug`, `section` | Retrieves an article or targeted heading section. |
| `save_article` | `title`, `content`, `tags`, `slug`, `source_prefix` | Publishes authoritative documentation into the knowledge base. |
| `note` | `title`, `content`, `tags` | Saves an agent discovery or task finding into `inbox/`. |
| `ingest_file` | `filename`, `content`, `tags`, `destination` | Ingests text/markdown files into inbox drafts or core articles. |
| `list_articles`| `source_prefix`, `include_inbox`, `tag`, `limit` | Discovers available articles and tags. |
| `changelog` | `since`, `limit` | Lists article modifications since an ISO 8601 timestamp. |

### 📁 Cloud Files & Drive Tools
| Tool | Parameters | Description |
| :--- | :--- | :--- |
| `list_files` | `directory` | Lists files and folders with download URLs. |
| `read_file` | `path` | Reads text content of files in the cloud drive. |
| `write_file` | `path`, `content`, `is_base64` | Saves files directly to cloud storage and returns direct URL. |
| `delete_file` | `path` | Deletes a file or directory from the cloud drive. |
| `get_file_link` | `path` | Returns direct public link on `https://files.concavoi.com`. |

