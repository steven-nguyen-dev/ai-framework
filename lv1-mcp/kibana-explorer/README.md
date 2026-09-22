# Kibana Explorer MCP Server (`kibana-explorer`)

FastMCP server for searching, analyzing, and diagnosing enterprise application logs in Elasticsearch via Kibana using KQL (Kibana Query Language).

---

## ⚙️ Configuration & Setup

### 1. Credentials File
Create or edit `~/.mcp/kibana-explorer.env` (or a local `.env` in this directory):

```ini
KIBANA_URL=https://apac-elk.anchanto.com:5601
KIBANA_USERNAME=your.email@anchanto.com
KIBANA_PASSWORD=your_kibana_password
KIBANA_INDEX_PATTERN=logs-*-*,logs-*,filebeat-*
KIBANA_VERIFY_SSL=true
```

### 2. Verify Connectivity & Self-Test
The launcher script automatically creates its virtual environment (`.venv/`), installs dependencies, and tests authentication:
```bash
bash launch.sh --selftest
```
Output confirms valid session cookie authentication and reports total indexed hit count.

### 3. Running as MCP Server
Run over stdio transport:
```bash
bash launch.sh
```

---

## 🛠 Available MCP Tools

| Tool | Parameters | Description |
| :--- | :--- | :--- |
| `kibana_search_logs` | `kql`, `time_range`, `limit`, `sort_field`, `sort_order` | Searches logs matching KQL query within time window (e.g. `log.level:ERROR`). |
| `kibana_count_logs` | `kql`, `time_range` | Fast count of documents matching KQL criteria. |
| `kibana_log_histogram` | `kql`, `interval`, `time_range` | Aggregates log frequency over time intervals (e.g. `5m`, `1h`). |
| `kibana_field_values` | `field`, `kql`, `time_range`, `limit` | Returns top distinct values for a field (e.g. error codes, service names). |
| `kibana_get_recent_errors` | `service_name`, `hours`, `limit` | Quick error triage extracting stack traces and error messages. |
| `kibana_translate_kql` | `kql` | Compiles a KQL query into raw Elasticsearch DSL syntax. |
| `kibana_raw_bsearch` | `request_body` | Direct raw multisearch query against Kibana's internal bsearch endpoint. |
| `kibana_trace_pipeline` | `correlation_id`, `pipeline_name` | Follows an entity or message across multiple services. |
| `kibana_pipeline_health` | `pipeline_name`, `window_minutes` | Ingestion health metrics, error rates, and volume statistics. |
| `kibana_detect_service_gaps`| `service_name`, `threshold_minutes` | Identifies processing stalls or gaps in heartbeats. |
| `kibana_check_connection` | *none* | Verifies Kibana session cookie auth and network latency. |
| `kibana_configure` | `url`, `username`, `password`, `index_pattern` | Reconfigures credentials live in-session. |
