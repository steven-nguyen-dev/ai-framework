# MCP Credential Detection Rule

Whenever the user starts a session, asks about setup, or requests any task involving Jira (e.g. issues, tickets, attachments) or Kibana (e.g. logs, traces, errors, KQL):

1. Check if the credential files exist:
   - `~/.mcp/jira-reader.env`
   - `~/.mcp/kibana-explorer.env`

2. If either credential file is missing or contains placeholder values:
   - Inform the user politely and concisely:
     > ⚠️ **Jira Reader** and/or **Kibana Explorer** are not configured yet.
     > Type **/config** or paste your credentials here to configure them interactively in chat.
   - If the user was asking to perform a specific action (e.g. "fetch ticket JIRA-123"), offer to collect the credentials immediately so you can complete their request right away.
