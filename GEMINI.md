# Installation & Configuration Rule

Before installing or configuring anything, always perform a web search to verify the exact official methods, paths, and requirements.

# Server Lifecycle Rule

Never start, spawn, or run daemon background server processes (e.g. `server.py`, `portal.py`) directly from agent background tasks. Instead, ask the user to start or manage servers through their respective launchers or scripts.

# Managed Repositories Rule

This workspace operates across and manages exactly two repositories:
1. `https://github.com/steven-nguyen-dev/ai-framework` — Primary monorepo.
2. `https://github.com/nguyennguyen-anchanto/ai-first-framework-skills` — Public skills marketplace upstream.

Never reference, search, or associate with external sibling repositories (such as `JPluger`).
Never use symlinks: all plugins and directories must remain physical and self-contained.

# Concise Writing & Make-It-Short Rule

Automatically invoke and apply the `make-it-short` skill whenever the user requests or demands brevity, conciseness, directness, compact documentation, or shortened text. Once requested in a session, all subsequent responses, documentation, and edits in that session must conform to `make-it-short` limits and wording rules.
