# Cloud Drive MCP Server (`drive`)

Personal cloud drive, file storage, asset management, and direct download link server. Connects over secure HTTPS to the CloudDrive vault at `files.concavoi.com`.

---

## ⚙️ Configuration & Transport

- **Endpoint**: `https://files.concavoi.com/api/mcp`
- **Transport**: JSON-RPC 2.0 via `mcp-remote` stdio proxy
- **Web Interface**: `https://files.concavoi.com` (FileBrowser)

### Credentials Setup
Create `~/.mcp/.drive.env` with restricted permissions (`chmod 600`):

```bash
DRIVE_HOST=https://files.concavoi.com/api/mcp
DRIVE_API_TOKEN=concobebe!123
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

## 🛠 Available MCP Tools (5 Tools)

| Tool | Parameters | Description |
| :--- | :--- | :--- |
| `list_files` | `directory` | Lists files and folders in CloudDrive with sizes and download URLs. |
| `read_file` | `path` | Reads text content of files in the cloud drive. |
| `write_file` | `path`, `content`, `is_base64` | Saves files directly to cloud storage and returns direct URL on `files.concavoi.com`. |
| `delete_file` | `path` | Deletes a file or directory from the cloud drive. |
| `get_file_link` | `path` | Returns direct public link on `https://files.concavoi.com/files/...`. |
