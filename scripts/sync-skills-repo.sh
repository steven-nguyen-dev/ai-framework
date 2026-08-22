#!/usr/bin/env bash
# ==============================================================================
# Sync User-Facing Skills Repository (ai-first-framework-skills)
# Dynamically discovers skills, utilities, plugins, report servers, and MCPs.
# Zero hardcoding - generates all manifests, tables, and README automatically.
# ==============================================================================
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
python3 "$DIR/sync_skills_repo.py" "$@"

