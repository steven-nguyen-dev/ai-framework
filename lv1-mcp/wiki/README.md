# Wiki MCP Server (`wiki`)

Standalone engineering knowledge base and technical documentation retrieval server. Provides hybrid Full-Text Search (PostgreSQL FTS) and semantic vector search (Ollama `embeddinggemma`) over Anchanto system architecture, order lifecycle, RTS/RFP, OMS/WMS, and marketplace integrations.

---

## ⚙️ Configuration & Setup

### 1. Configuration File
Reads from `~/.config/wiki-mcp/config.toml` (or `WIKI_CONFIG` env var, with fallback to `~/.config/swarm/config.toml`):

```toml
[postgres]
# Host port 25432 avoids conflicts with standard postgres on 5432
dsn = "postgresql://wiki:wiki@127.0.0.1:25432/wiki"

[wiki]
inbox_prefix = "inbox/"   # Namespace for scratch notes, excluded from default search

[embedder]
enabled = true            # Enable semantic vector search via Ollama
url = "http://127.0.0.1:11434"
model = "embeddinggemma"
dimensions = 768          # Matches schema vector(768)
timeout_s = 30.0
batch_size = 32

[limits]
body_max_words = 200      # Word limit per chunk body
summary_max_words = 120   # Word limit per chunk summary
```

### 2. Prerequisites
1. **PostgreSQL with pgvector** on port 25432:
   ```bash
   # Schema initialization
   psql "postgresql://wiki:wiki@127.0.0.1:25432/wiki" -f schema.sql
   ```
2. **Ollama Embedding Model** (optional, for vector search):
   ```bash
   ollama pull embeddinggemma
   ```

### 3. Virtual Environment & Execution
The launcher script automatically creates and manages its isolated virtual environment outside Git and OneDrive at `~/.local/share/wiki-mcp/venv`:

```bash
# Run stdio MCP server
bash launch.sh

# Ingest markdown files into the wiki
bash launch-ingest.sh /path/to/markdown/docs
```

Or via global symlinks:
```bash
wiki-mcp
wiki-ingest /path/to/markdown/docs --prefix "knowledges"
```

---

## 🛠 Available MCP Tools

| Tool | Parameters | Description |
| :--- | :--- | :--- |
| `search` | `query`, `k`, `source_prefix`, `include_inbox` | Hybrid reciprocal rank fusion (FTS + vector search) returning complete chunk bodies and match sources. |
| `get` | `source_id`, `section`, `include_retired` | Fetches a source document and its structured sections by exact identity. |
| `render` | `source_id`, `include_retired` | Reconstructs the complete markdown document from stored chunks. |
| `note` | `slug`, `body`, `summary`, `title` | Writes a developer or agent note into the `inbox/` namespace. |
| `changelog` | `source_id`, `limit` | Audit history of versions, modifications, and actors for a document. |
