#!/usr/bin/env python3
import json
import sys
from pathlib import Path

jira_env = Path.home() / ".mcp" / ".jira-reader.env"
jira_env_legacy = Path.home() / ".mcp" / "jira-reader.env"
kibana_env = Path.home() / ".mcp" / ".kibana-explorer.env"
kibana_env_legacy = Path.home() / ".mcp" / "kibana-explorer.env"

missing = []
if not jira_env.exists() and not jira_env_legacy.exists():
    missing.append("Jira Reader")
if not kibana_env.exists() and not kibana_env_legacy.exists():
    missing.append("Kibana Explorer")

if missing:
    missing_str = ", ".join(missing)
    output = {
        "systemMessage": f"\n⚠️ [AI-First Framework] {missing_str} MCP credentials are not configured yet.\n",
        "hookSpecificOutput": {
            "additionalContext": (
                f"CRITICAL ONBOARDING: The user has the AI-First Framework MCP plugin installed, but {missing_str} are not configured yet (missing credentials in ~/.mcp/). "
                "You MUST inform the user and ask them directly for their credentials step-by-step in your response:\n"
                "1. If Jira is missing: Ask for Jira Host URL (e.g. https://anchantoplan.atlassian.net), Atlassian Email, and API Token (https://id.atlassian.com/manage-profile/security/api-tokens).\n"
                "2. If Kibana is missing: Ask for Kibana URL (e.g. https://apac-elk.anchanto.com:5601), Username, and Password.\n"
                "When the user provides the credentials in chat, write them directly to ~/.mcp/.jira-reader.env and/or ~/.mcp/.kibana-explorer.env with permissions 0600."
            )
        }
    }
    print(json.dumps(output))
else:
    print(json.dumps({}))

sys.exit(0)
