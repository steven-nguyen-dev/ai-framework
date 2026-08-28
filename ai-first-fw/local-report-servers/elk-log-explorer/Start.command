#!/bin/bash
export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"
cd -- "$(dirname "$0")"
chmod +x *.sh *.command *.py 2>/dev/null || true
bash ./start.sh "$@"
