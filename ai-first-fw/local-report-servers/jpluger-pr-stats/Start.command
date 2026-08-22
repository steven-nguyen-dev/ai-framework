#!/bin/bash
# ==============================================================================
# JPluger PR Stats - Double-Click Launcher for macOS Finder
# Double-clicking this file automatically opens Terminal and starts the server.
# ==============================================================================

cd -- "$(dirname "$0")"

# Grant permissions
chmod +x *.sh *.command *.py 2>/dev/null || true

# Run start script
bash ./start.sh "$@"
