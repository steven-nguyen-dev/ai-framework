# Testbed MCP Server (`testbed`)

The only route agents use to reach the cloud mock server (`test.concavoi.com`, API in `lv1-servers/contracts/testbed-api.yaml`) and the testbed-dev suite engine (`testbed-dev/suite/cli.py`). Agents edit mock and suite files with Edit/Write, then push and run through these tools. Nothing else reads the credentials.

---

## ⚙️ Configuration & Setup

### Credentials
Create `~/.mcp/.testbed.env` with restricted permissions (`chmod 600`):

```bash
TESTBED_HOST=https://test.concavoi.com
TESTBED_API_TOKEN=<admin password>
TESTBED_PATH_KEY=<app route path key>
```

The server reads only these variables. Optional overrides: `LV1_SERVERS_ROOT` (default `~/Projects/lv1-servers`), `JPLUGER_ROOT` (default `~/Projects/jpluger-family/one/JPluger`), `TESTBED_MCP_DATA` (default `~/.local/share/lv1-testbed-mcp`).

- No tool returns `TESTBED_API_TOKEN` or `TESTBED_PATH_KEY`. Every string a tool returns has both masked, along with `/k/<key>/` URL segments and secret headers.
- Offline engine calls (`suite_*`) run with no secrets. `run_start` gives the engine the two values as `ADMIN_PASSWORD` and `PATH_KEY`, the names `cli.py` reads.

### Virtual Environment & Execution
On first run, the launcher creates its venv at `~/.local/share/lv1-testbed-mcp/venv` and installs `requirements.txt`. The engine runs in its own venv, `testbed-dev/.venv`.

```bash
bash launch.sh              # stdio MCP server
bash launch.sh --selftest   # config (secrets shown only as set/unset), mock list, lease
```

### Tests
```bash
python3 -m unittest testbed/test_server.py   # from lv1-mcp/; fake portal on 127.0.0.1, fake engine
```

---

## 🛠 Available MCP Tools (18 Tools)

| Tool | Parameters | Description |
| :--- | :--- | :--- |
| `mocks_diff` | `mock` | Lists added, changed and deleted files between the git checkout of `cloud-servers/mock-api/mocks/<content_path>/` and the cloud. |
| `mocks_push` | `mock`, `dry_run` | Uploads the changes under the lease and applies them, which restarts the mock. Refused while a run is active or anyone holds the lease. |
| `mocks_rollback` | `mock` | Puts the previous content back. Refused while busy. |
| `mocks_status` | `mock?` | Gives the server entry (status, `content_path`, pushed version) and health, or lists every mock. |
| `lease_status` | — | Gives the portal lease holder and this server's active run. |
| `stores_get` | `mock`, `name?` | Reads one store, or every store of the mock. |
| `stores_put` | `mock`, `name`, `value`, `mode` | Writes a store: `replace`, `append` or `merge`. |
| `reset` | `mock`, `stores?`, `log`, `files` | Resets stores, and optionally the call log and scenario files. |
| `call_log` | `mock`, `after_seq?`, `since?`, `limit` | Returns recorded calls (HAR) with secrets masked. |
| `suite_validate` | `items` | Runs `cli.py <items> --validate`. |
| `suite_lint` | `suite_dirs` | Runs `cli.py --lint <dirs>`. |
| `suite_list` | `items`, `markers?` | Runs `cli.py <items> --list [-m ...]`. |
| `suite_judge` | `case_file`, `run_dir`, `cases?` | Judges an existing run folder offline and writes nothing into it. |
| `run_start` | `target`, `cases?`, `markers?`, `fast` | Starts a live run in the background and returns `run_id`. Refused while a run is active or the lease is held. |
| `run_status` | `run_id`, `tail` | Gives the state (`running`, `finished` or `lost`), exit code, run folder, summary and output tail. |
| `run_result` | `run_id` | Gives the per-case verdict table, summary, run folder and `run.json`. |
| `run_list` | `limit` | Lists registry runs, newest first. |
| `run_stop` | `run_id` | Sends SIGTERM to a live run; the engine then releases the lease. |

Paths are relative to `testbed-dev/` unless absolute. Engine exit codes: 0 pass, 1 usage or validation error, 2 failure, 3 blocked (lease held or preflight failed; nothing fired).

The run registry lives at `~/.local/share/lv1-testbed-mcp/runs/<run_id>/` (`run.json`, `output.log`, `exit_code`). Each run starts under `sh -c`, which records the exit code, so a run's status survives a restart of this server.
