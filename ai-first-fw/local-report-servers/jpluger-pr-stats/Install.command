#!/bin/bash
# ==============================================================================
# JPluger PR Stats - Double-Click Installer for macOS Finder
# Double-clicking this file automatically opens Terminal and installs the application.
# ==============================================================================

cd -- "$(dirname "$0")"

# Grant permissions
chmod +x *.sh *.command *.py 2>/dev/null || true

# 1. Run dependency check & GitHub auth setup
bash ./setup.sh

echo ""
# 2. Install as macOS Application in /Applications
bash ./install_app.sh
