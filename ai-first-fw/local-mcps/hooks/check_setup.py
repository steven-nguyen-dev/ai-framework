#!/usr/bin/env python3
import json
import sys
from pathlib import Path

jira_env = Path.home() / ".mcp" / "jira-reader.env"
kibana_env = Path.home() / ".mcp" / "kibana-explorer.env"

missing = []
if not jira_env.exists():
    missing.append("Jira Reader")
if not kibana_env.exists():
    missing.append("Kibana Explorer")

if missing:
    missing_str = ", ".join(missing)
    msg = f"\n⚠️ [AI-First Framework] Setup Required: {missing_str} not configured yet.\n👉 Type /setup-mcps in chat to set up credentials.\n"
    output = {
        "systemMessage": msg,
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": f"NOTICE: The following MCP servers are unconfigured: {missing_str}. Remind the user to type /setup-mcps to set up credentials."
        }
    }
    print(json.dumps(output))
else:
    print(json.dumps({}))

sys.exit(0)
