#!/bin/bash
cd -- "$(dirname "$0")"
chmod +x *.sh *.command *.py 2>/dev/null || true
bash ./setup.sh
echo ""
bash ./install_app.sh
