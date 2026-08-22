#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

python3 -m venv "$DIR/.venv"
"$DIR/.venv/bin/pip" install --quiet --upgrade pip
"$DIR/.venv/bin/pip" install --quiet -r "$DIR/requirements.txt"

# Create .env from .env.sample if not present
if [ ! -f "$DIR/.env" ] && [ -f "$DIR/.env.sample" ]; then
    cp "$DIR/.env.sample" "$DIR/.env"
    echo "✔ Created $DIR/.env from .env.sample (fill in your Jira credentials)"
fi

echo "✔ Dependencies installed into $DIR/.venv"
echo "✔ Setup complete."
