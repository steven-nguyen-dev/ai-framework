---
description: Interactive configuration and diagnostics wizard for Jira Reader and Kibana Explorer MCP servers.
---

Guide the developer through configuring and verifying the local MCP servers (`jira-reader` and `kibana-explorer`):

1. **Check Existing Configuration**:
   - Check if `~/.jira.env` or `${CLAUDE_PLUGIN_ROOT}/jira-reader/.env` exists.
   - Check if `${CLAUDE_PLUGIN_ROOT}/kibana-explorer/.env` exists.

2. **Run Configuration**:
   - Ask the user if they want you to run the interactive setup wizard via `bash ${CLAUDE_PLUGIN_ROOT}/setup.sh`, or if they prefer to provide credentials directly in chat.
   - If providing in chat:
     - **Jira**: Collect `JIRA_HOST`, `JIRA_EMAIL`, and `JIRA_API_TOKEN` (or `JIRA_PAT`), and save to `~/.jira.env` with `chmod 600`.
     - **Kibana**: Collect `KIBANA_URL`, `KIBANA_USERNAME`, `KIBANA_PASSWORD`, and default index pattern, and save to `${CLAUDE_PLUGIN_ROOT}/kibana-explorer/.env`.

3. **Verify Connectivity**:
   - Run `python3 ${CLAUDE_PLUGIN_ROOT}/jira-reader/server.py --test`
   - Run `bash ${CLAUDE_PLUGIN_ROOT}/kibana-explorer/launch.sh --selftest`

4. **Activation**:
   - Remind the user to run `/reload-plugins` and check `/mcp`.
