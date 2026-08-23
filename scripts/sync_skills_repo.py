#!/usr/bin/env python3
"""Dynamic User-Facing Skills & Marketplace Publisher.

Dynamically discovers all skills, utilities, plugins, report servers, and MCPs
from the monorepo, auto-generates manifests (marketplace.json, plugin.json) and
the user-facing README.md without any hardcoded skill lists or versions, and
publishes to the public skills repository (ai-first-framework-skills).

Usage:
    python3 scripts/sync_skills_repo.py [--dry-run] [--remote <git-url>]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
MONOREPO_ROOT = HERE.parent


@dataclass
class SkillMeta:
    dir_name: str
    name: str
    description: str
    version: str
    category: str
    disable_model_invocation: bool
    path: Path


def parse_yaml_frontmatter(text: str) -> dict[str, str]:
    m = re.match(r"^---\s*\n(.*?)\n---\s*(\n|$)", text, re.DOTALL)
    if not m:
        return {}
    res = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            res[k.strip()] = v.strip().strip("'\"")
    return res


def scan_skills_in_dir(parent_dir: Path) -> list[SkillMeta]:
    skills: list[SkillMeta] = []
    if not parent_dir.is_dir():
        return skills

    for child in sorted(parent_dir.iterdir()):
        if child.name.startswith(".") or not child.is_dir():
            continue
        skill_file = child / "SKILL.md"
        if skill_file.is_file():
            try:
                content = skill_file.read_text(encoding="utf-8")
                fm = parse_yaml_frontmatter(content)
                name = fm.get("name", child.name)
                desc = fm.get("description", "")
                ver = fm.get("version", "1.0.0")
                cat = fm.get("category", "General")
                disable_model = fm.get("disable-model-invocation", "false").lower() == "true"
                skills.append(
                    SkillMeta(
                        dir_name=child.name,
                        name=name,
                        description=desc,
                        version=ver,
                        category=cat,
                        disable_model_invocation=disable_model,
                        path=child,
                    )
                )
            except Exception as e:
                print(f"⚠️ Error reading {skill_file}: {e}", file=sys.stderr)
    return skills


def read_plugin_meta(plugin_dir: Path) -> dict[str, str]:
    """Reads plugin.json or .claude-plugin/plugin.json if present."""
    candidates = [
        plugin_dir / ".claude-plugin/plugin.json",
        plugin_dir / "plugin.json",
    ]
    for c in candidates:
        if c.is_file():
            try:
                return json.loads(c.read_text(encoding="utf-8"))
            except Exception:
                pass
    return {}


def generate_marketplace_json(skills: list[SkillMeta], utilities: list[SkillMeta], owner_name: str, owner_email: str) -> dict:
    skills_plugin_meta = read_plugin_meta(MONOREPO_ROOT / "ai-first-fw/skills")
    utils_plugin_meta = read_plugin_meta(MONOREPO_ROOT / "ai-first-fw/utilities")

    skills_desc = skills_plugin_meta.get("description") or f"Core AI-First Framework lifecycle skills: {', '.join(s.name for s in skills)}."
    utils_desc = utils_plugin_meta.get("description") or f"Standalone engineering utility skills: {', '.join(u.name for u in utilities)}."

    skills_ver = skills_plugin_meta.get("version", "1.0.0")
    utils_ver = utils_plugin_meta.get("version", "1.1.1")

    return {
        "$schema": "https://json.schemastore.org/claude-code-marketplace.json",
        "name": "ai-first-framework-skills",
        "description": "AI-First Software Engineering Framework: Core Lifecycle Skills, Standalone Utilities, and Local Engineering Dashboards",
        "owner": {
            "name": owner_name,
            "email": owner_email,
        },
        "plugins": [
            {
                "name": "ai-first-fw-skills",
                "description": skills_desc,
                "version": skills_ver,
                "source": "./skills",
            },
            {
                "name": "ai-first-fw-utilities",
                "description": utils_desc,
                "version": utils_ver,
                "source": "./utilities",
            },
        ],
    }


def generate_user_facing_readme(
    skills: list[SkillMeta],
    utilities: list[SkillMeta],
    owner_repo: str = "nguyennguyen-anchanto/ai-first-framework-skills",
) -> str:
    skills_table_rows = []
    for s in skills:
        skills_table_rows.append(f"| **`{s.name}`** | `{s.version}` | {s.description} |")

    skills_table_md = "\n".join(skills_table_rows)

    utils_list_items = []
    for u in utilities:
        utils_list_items.append(f"* **`{u.name}`** (`v{u.version}`): {u.description}")
    utils_list_md = "\n".join(utils_list_items)

    skills_npx_cmds = "\n".join(f"npx skills add {owner_repo}/skills/{s.dir_name}" for s in skills)
    utils_npx_cmds = "\n".join(f"npx skills add {owner_repo}/utilities/{u.dir_name}" for u in utilities)

    return f"""# 🧩 AI-First Framework: Skills, Dashboards & Local Servers

A production-ready toolkit of review-driven engineering skills, standalone utilities, and 1-click local engineering report servers for **Claude Code**, **Claude Cowork**, **Google Antigravity 2.0**, **Gemini**, and **Engineering Teams**.

---

## 📊 Local Report Servers & Standalone macOS Applications

Every report server comes pre-packaged with a **1-click macOS `.app` installer**, double-clickable terminal launchers, and distribution `.zip` archives.

| Server / Dashboard | Port | Distribution Package | Key Features |
| :--- | :--- | :--- | :--- |
| **Central Reports Portal** | `24000` | Run `python3 local-report-servers/portal.py` | Web-based management dashboard to monitor, start, and stop all local report servers |
| **[Daily Work Reports](local-report-servers/daily-report)** | `24001` | [`daily-report-1.0.0.zip`](local-report-servers/daily-report/daily-report-1.0.0.zip) | Daily engineering activity aggregator, timeline log viewer, and on-going matters tracker |
| **[JPluger PR Stats](local-report-servers/jpluger-pr-stats)** | `24002` | [`jpluger-pr-stats-1.0.0.zip`](local-report-servers/jpluger-pr-stats/jpluger-pr-stats-1.0.0.zip) | GitHub pull request triage, review coverage breakdown, aging analysis, and monthly velocity |
| **[AI Skills & Plugins](local-report-servers/ai-skills-report)** | `24003` | [`ai-skills-report-1.0.0.zip`](local-report-servers/ai-skills-report/ai-skills-report-1.0.0.zip) | Universal AI skills registry, marketplace manager, and multi-agent environment inspector |
| **[ELK AI Log Explorer](local-report-servers/elk-log-explorer)** | `24004` | [`elk-log-explorer-1.0.0.zip`](local-report-servers/elk-log-explorer/elk-log-explorer-1.0.0.zip) | Dark-themed Kibana log explorer with multi-agent AI natural language query translator |

---

### 🚀 1-Step Installation for Local Servers (macOS)

Download any server's `.zip` file into your **`~/Downloads`** folder, open **Terminal.app**, and copy & paste the single command:

#### Option 1: Install as a native macOS Application (`/Applications`)
```bash
# Daily Work Reports
unzip -o ~/Downloads/daily-report-1.0.0.zip -d ~/Downloads/daily-report && cd ~/Downloads/daily-report && chmod +x *.sh *.command *.py && ./setup.sh && ./install_app.sh

# JPluger PR Stats
unzip -o ~/Downloads/jpluger-pr-stats-1.0.0.zip -d ~/Downloads/jpluger-pr-stats && cd ~/Downloads/jpluger-pr-stats && chmod +x *.sh *.command *.py && ./setup.sh && ./install_app.sh

# AI Skills & Plugins Registry
unzip -o ~/Downloads/ai-skills-report-1.0.0.zip -d ~/Downloads/ai-skills-report && cd ~/Downloads/ai-skills-report && chmod +x *.sh *.command *.py && ./setup.sh && ./install_app.sh

# ELK AI Log Explorer
unzip -o ~/Downloads/elk-log-explorer-1.0.0.zip -d ~/Downloads/elk-log-explorer && cd ~/Downloads/elk-log-explorer && chmod +x *.sh *.command *.py && ./setup.sh && ./install_app.sh
```

#### Option 2: Launch via Central Reports Portal
```bash
python3 local-report-servers/portal.py
# Opens http://localhost:24000 to manage and start all servers with 1 click
```

---

## 🛠️ AI Skills & Utilities Installation

### Claude Code & Claude Cowork (Plugin Marketplace)

```bash
# 1. Register the marketplace
plugin marketplace add {owner_repo}

# 2. Install core lifecycle skills
plugin install ai-first-fw-skills@{owner_repo.split('/')[-1]}

# 3. Install standalone utilities
plugin install ai-first-fw-utilities@{owner_repo.split('/')[-1]}
```

---

### Direct Installation (`npx skills`)

```bash
# Core Lifecycle Skills
{skills_npx_cmds}

# Standalone Utility Skills
{utils_npx_cmds}
```

---

### Google Antigravity 2.0 & Gemini CLI Setup

Add the skill directory paths to your agent configuration (`~/.gemini/config/skills.json` or `.agents/skills.json`):

```json
{{
  "entries": [
    {{ "path": "skills" }},
    {{ "path": "utilities" }}
  ]
}}
```

---

## 🛡️ Core Lifecycle Skills (`skills/`)

| Skill | Version | Purpose |
| :--- | :--- | :--- |
{skills_table_md}

```
[ Input Requirements ]
         │
         ▼
 ┌─────────────────────────┐
 │    analysis-handoff     │ ──► .scratchpads/<feature>/analysis-handoff.md
 └───────────┬─────────────┘
             ▼
 ┌─────────────────────────┐
 │ implementation-planner  │ ──► Gate G1: Requirements & Acceptance Criteria Approved
 └───────────┬─────────────┘
             ▼
 ┌─────────────────────────┐     ┌─────────────────────┐
 │      specs-builder      │ ──► │   specs-reviewer    │ (Cold Diagnostic Spec Audit)
 └───────────┬─────────────┘     └─────────────────────┘
             ▼
 ┌─────────────────────────┐     ┌─────────────────────┐
 │ implementation-planner  │ ──► │    plan-reviewer    │ (Cold Plan & Evidence Audit)
 └───────────┬─────────────┘     └─────────────────────┘
             ▼                   └── Gate G2: Plan Approved (Unblocks Code Changes)
 ┌─────────────────────────┐     ┌─────────────────────┐
 │      Development        │ ──► │    code-reviewer    │ (Cold Diff & Quality Audit)
 └───────────┬─────────────┘     └─────────────────────┘
             ▼
 [ Verified Code & Pull Request ]
```

---

## ⚡ Standalone Utility Skills (`utilities/`)

{utils_list_md}

---

## 🔌 Local MCP Servers (`local-mcps/`)

* **`jira`**: FastMCP server for Jira issue metadata extraction, acceptance criteria parsing, and batch attachment analysis.
* **`kibana`**: FastMCP server for Kibana Observability & Logs with embedded KQL parser and session cookie auth.

---

## 📄 License & Maintainers

Maintained by **Nguyen Nguyen** (`nguyennguyen-anchanto`).  
Released under the MIT License.
"""


def get_git_remote_url(remote_name: str = "skills-upstream") -> str:
    try:
        res = subprocess.run(
            ["git", "-C", str(MONOREPO_ROOT), "remote", "get-url", remote_name],
            capture_output=True,
            text=True,
            check=True,
        )
        return res.stdout.strip()
    except Exception:
        return "https://github.com/nguyennguyen-anchanto/ai-first-framework-skills.git"


def sync_and_publish(target_remote: str | None = None, dry_run: bool = False) -> dict:
    if not target_remote:
        target_remote = os.getenv("SKILLS_REMOTE_URL") or get_git_remote_url("skills-upstream")

    skills = scan_skills_in_dir(MONOREPO_ROOT / "ai-first-fw/skills")
    utilities = scan_skills_in_dir(MONOREPO_ROOT / "ai-first-fw/utilities")

    print(f"🔍 Discovered {len(skills)} lifecycle skills and {len(utilities)} utility skills.")

    tmp_dir = Path(tempfile.mkdtemp(prefix="ai-skills-sync-"))
    try:
        print(f"📦 Staging sync payload in {tmp_dir}...")

        # Create base folders
        (tmp_dir / "skills").mkdir(parents=True, exist_ok=True)
        (tmp_dir / "utilities").mkdir(parents=True, exist_ok=True)
        (tmp_dir / "local-report-servers").mkdir(parents=True, exist_ok=True)
        (tmp_dir / "local-mcps").mkdir(parents=True, exist_ok=True)
        (tmp_dir / ".claude-plugin").mkdir(parents=True, exist_ok=True)

        # Copy trees
        for item in (MONOREPO_ROOT / "ai-first-fw/skills").iterdir():
            if item.name == ".DS_Store":
                continue
            dest = tmp_dir / "skills" / item.name
            if item.is_dir():
                shutil.copytree(item, dest, dirs_exist_ok=True)
            else:
                shutil.copy2(item, dest)

        for item in (MONOREPO_ROOT / "ai-first-fw/utilities").iterdir():
            if item.name == ".DS_Store":
                continue
            dest = tmp_dir / "utilities" / item.name
            if item.is_dir():
                shutil.copytree(item, dest, dirs_exist_ok=True)
            else:
                shutil.copy2(item, dest)

        for item in (MONOREPO_ROOT / "ai-first-fw/local-report-servers").iterdir():
            if item.name.startswith("."):
                continue
            dest = tmp_dir / "local-report-servers" / item.name
            if item.is_dir():
                shutil.copytree(item, dest, dirs_exist_ok=True)
            else:
                shutil.copy2(item, dest)

        for item in (MONOREPO_ROOT / "ai-first-fw/local-mcps").iterdir():
            if item.name.startswith("."):
                continue
            dest = tmp_dir / "local-mcps" / item.name
            if item.is_dir():
                shutil.copytree(item, dest, dirs_exist_ok=True)
            else:
                shutil.copy2(item, dest)

        # Generate marketplace.json
        mp_data = generate_marketplace_json(
            skills=skills,
            utilities=utilities,
            owner_name="Nguyen Nguyen",
            owner_email="nguyennguyen-anchanto@users.noreply.github.com",
        )
        (tmp_dir / ".claude-plugin/marketplace.json").write_text(json.dumps(mp_data, indent=2), encoding="utf-8")

        # Generate README.md
        readme_md = generate_user_facing_readme(skills, utilities)
        (tmp_dir / "README.md").write_text(readme_md, encoding="utf-8")

        # Generate .gitignore
        (tmp_dir / ".gitignore").write_text(".DS_Store\n*.pyc\n__pycache__/\n*.env\n.scratchpads/\n", encoding="utf-8")

        if dry_run:
            print("🧪 Dry run enabled - skipping git push.")
            return {
                "success": True,
                "dry_run": True,
                "skills_count": len(skills),
                "utilities_count": len(utilities),
                "staging_dir": str(tmp_dir),
            }

        # Initialize git repo and push
        subprocess.run(["git", "init", "-b", "main"], cwd=str(tmp_dir), check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Nguyen Nguyen"], cwd=str(tmp_dir), check=True)
        subprocess.run(["git", "config", "user.email", "nguyennguyen-anchanto@users.noreply.github.com"], cwd=str(tmp_dir), check=True)
        subprocess.run(["git", "remote", "add", "origin", target_remote], cwd=str(tmp_dir), check=True)

        subprocess.run(["git", "add", "-A"], cwd=str(tmp_dir), check=True)

        commit_msg = (
            f"feat(skills): sync {len(skills)} lifecycle skills & {len(utilities)} utilities dynamically\n\n"
            f"Skills: {', '.join(s.name for s in skills)}\n"
            f"Utilities: {', '.join(u.name for u in utilities)}"
        )
        subprocess.run(["git", "commit", "-m", commit_msg], cwd=str(tmp_dir), check=True)

        print(f"🚀 Pushing to {target_remote}...")
        push_res = subprocess.run(["git", "push", "origin", "main", "--force"], cwd=str(tmp_dir), capture_output=True, text=True)
        if push_res.returncode != 0:
            raise RuntimeError(f"Git push failed: {push_res.stderr}")

        print("✔ Successfully synced and pushed to user-facing skills repository!")
        return {
            "success": True,
            "skills_count": len(skills),
            "utilities_count": len(utilities),
            "target_remote": target_remote,
            "skills": [s.name for s in skills],
            "utilities": [u.name for u in utilities],
        }
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def main():
    parser = argparse.ArgumentParser(description="Sync and publish skills dynamically to public repository.")
    parser.add_argument("--remote", help="Target git remote URL")
    parser.add_argument("--dry-run", action="store_true", help="Perform staging without git push")
    args = parser.parse_args()

    res = sync_and_publish(target_remote=args.remote, dry_run=args.dry_run)
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
