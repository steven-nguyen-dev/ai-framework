# Installation & Configuration Rule

Before installing or configuring anything, always perform a web search to verify the exact official methods, paths, and requirements.

# Report Pages & Shared Theme Rule

Every dashboard, viewer, and report page across the repository (e.g. under `ai-first-fw/local-report-servers/` and `local-test-servers/`) MUST use the shared dark theme tokens, styles, and components from `ai-first-fw/local-theme/` (`theme.css`, `theme.js`, `theme.json`).

# Server Lifecycle Rule

Never start, spawn, or run daemon background server processes (e.g. `server.py`, `portal.py`) directly from agent background tasks. Instead, ask the user to start or manage servers through the Central Reports Portal (`python3 portal.py` on port 24000) or their respective `.command` scripts.

