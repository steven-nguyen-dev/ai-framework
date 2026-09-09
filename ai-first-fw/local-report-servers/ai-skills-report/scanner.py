#!/usr/bin/env python3
"""Scanner and Extension Manager for AI Agent Skills & Plugins on macOS.

Discovers and inspects all skills, plugins, and extensions across:
1. Claude (CLI, Claude App Cowork, Claude App Code)
2. Antigravity (CLI, App, IDE)
3. Cursor (IDE, Skills, Rules, MCP)
4. Codex (CLI, Skills, Plugins, AGENTS.md, MCP)
5. Master Alphabetical Skills Registry & Installation Matrix

Provides install & uninstall management across target agent surfaces.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import tomllib
except ImportError:
    tomllib = None  # type: ignore

def find_workspace_root() -> Path:
    """Locates the ai-framework repository root dynamically across any machine."""
    env_root = os.getenv("AI_FRAMEWORK_ROOT") or os.getenv("WORKSPACE_ROOT")
    if env_root and Path(env_root).is_dir():
        return Path(env_root).resolve()

    candidate = Path(__file__).resolve().parent.parent.parent.parent
    if (candidate / "ai-first-fw").is_dir() or (candidate / "GEMINI.md").is_file():
        return candidate

    cwd = Path.cwd().resolve()
    for p in [cwd, *cwd.parents]:
        if (p / "ai-first-fw").is_dir() or (p / "GEMINI.md").is_file() or (p / "CLAUDE.md").is_file():
            return p

    return candidate


HOME = Path.home()
WORKSPACE = find_workspace_root()
BACKUPS = WORKSPACE / ".backups"
BACKUPS.mkdir(parents=True, exist_ok=True)


def _codex_home() -> Path:
    """Returns $CODEX_HOME, defaulting to ~/.codex."""
    env = os.getenv("CODEX_HOME")
    if env:
        return Path(env).expanduser().resolve()
    return HOME / ".codex"


@dataclass
class SkillItem:
    id: str
    name: str
    description: str
    section: str  # "claude" | "antigravity" | "cursor" | "codex"
    subsection: str  # "cli" | "app_cowork" | "app_code" | "app" | "ide" | "skills" | "rules"
    source_type: str  # "local_repo_symlink" | "local_workspace" | "local_user" | "marketplace_github" | "builtin" | "desktop_extension"
    source_label: str  # e.g. "Local (Repo Symlink)", "Marketplace (claude-plugins-official)"
    path: str
    resolved_path: str | None = None
    plugin_name: str | None = None
    version: str | None = None
    marketplace: str | None = None
    repo_url: str | None = None
    commit_sha: str | None = None
    category: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PluginItem:
    id: str
    name: str
    description: str
    section: str  # "claude" | "antigravity" | "cursor" | "codex"
    subsection: str  # "cli" | "app_cowork" | "app_code" | "app" | "ide" | "extensions" | "plugins" | "skills"
    source_type: str  # "marketplace_github" | "local" | "desktop_extension" | "builtin"
    source_label: str
    version: str | None
    marketplace: str | None
    repo_url: str | None
    commit_sha: str | None
    install_path: str
    skills_count: int = 0
    skills: list[SkillItem] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


def parse_yaml_frontmatter(text: str) -> dict[str, str]:
    """Extracts frontmatter key-values from markdown."""
    m = re.match(r"^---\s*\n(.*?)\n---\s*(\n|$)", text, re.DOTALL)
    if not m:
        return {}
    fm_text = m.group(1)
    result = {}
    for line in fm_text.splitlines():
        if ":" in line:
            key, val = line.split(":", 1)
            key = key.strip()
            val = val.strip().strip("'\"")
            if key and val and key not in result:
                result[key] = val
    if "description" not in result:
        desc_m = re.search(r"^description:\s*(?:>-\s*|>\s*|\|\s*)?\n?(.*?)(?=\n[a-z0-9_-]+:|\Z)", fm_text, re.DOTALL | re.MULTILINE)
        if desc_m:
            result["description"] = " ".join(l.strip() for l in desc_m.group(1).strip().splitlines() if l.strip())
    return result


def extract_skill_info_from_file(skill_file: Path) -> tuple[str, str, dict[str, str]]:
    """Returns (name, description, all_frontmatter) from a SKILL.md or flat .md file."""
    try:
        content = skill_file.read_text(encoding="utf-8", errors="replace")
        fm = parse_yaml_frontmatter(content)
        name = fm.get("name") or (skill_file.parent.name if skill_file.name == "SKILL.md" else skill_file.stem)
        desc = fm.get("description", "")
        if not desc:
            for line in content.splitlines():
                line = line.strip()
                if line and not line.startswith("#") and not line.startswith("---"):
                    desc = line
                    break
        return name, desc, fm
    except Exception:
        name = skill_file.parent.name if skill_file.name == "SKILL.md" else skill_file.stem
        return name, "", {}


def determine_local_source_label(path: Path) -> tuple[str, str, str | None]:
    """Returns (source_type, source_label, resolved_path) generically."""
    if str(WORKSPACE) in str(path) and WORKSPACE != HOME:
        return "local_workspace", "Workspace", str(path)
    else:
        return "local_user", "User / Personal", str(path)


# ==============================================================================
# 1. Claude Scanners
# ==============================================================================

def scan_claude_cli_skills() -> list[SkillItem]:
    """Scans ~/.claude/skills/ and project .claude/skills/."""
    skills: list[SkillItem] = []
    
    # 1. Personal skills: ~/.claude/skills/
    personal_dir = HOME / ".claude/skills"
    if personal_dir.is_dir():
        for item in sorted(personal_dir.iterdir()):
            if item.name.startswith("."):
                continue
            skill_md = item / "SKILL.md" if item.is_dir() else (item if item.suffix == ".md" else None)
            if skill_md and skill_md.is_file():
                name, desc, fm = extract_skill_info_from_file(skill_md)
                src_type, src_label, resolved = determine_local_source_label(item)
                skills.append(SkillItem(
                    id=f"claude:cli:personal:{item.name}",
                    name=name,
                    description=desc,
                    section="claude",
                    subsection="cli",
                    source_type=src_type,
                    source_label=src_label,
                    path=str(item),
                    resolved_path=resolved,
                    metadata={"scope": "personal", "target_key": "claude", "frontmatter": fm},
                ))

    # 2. Project workspace skills: <workspace>/.claude/skills/
    project_skills_dir = WORKSPACE / ".claude/skills"
    if project_skills_dir.is_dir():
        for item in sorted(project_skills_dir.iterdir()):
            if item.name.startswith("."):
                continue
            skill_md = item / "SKILL.md" if item.is_dir() else (item if item.suffix == ".md" else None)
            if skill_md and skill_md.is_file():
                name, desc, fm = extract_skill_info_from_file(skill_md)
                src_type, src_label, resolved = determine_local_source_label(item)
                skills.append(SkillItem(
                    id=f"claude:cli:workspace:{item.name}",
                    name=name,
                    description=desc,
                    section="claude",
                    subsection="cli",
                    source_type=src_type,
                    source_label=src_label,
                    path=str(item),
                    resolved_path=resolved,
                    metadata={"scope": "workspace", "frontmatter": fm},
                ))

    return skills


def scan_claude_cli_plugins() -> list[PluginItem]:
    """Scans installed Claude Code plugins from ~/.claude/plugins/."""
    plugins: list[PluginItem] = []
    
    marketplaces_info = {}
    known_mp_file = HOME / ".claude/plugins/known_marketplaces.json"
    if known_mp_file.is_file():
        try:
            marketplaces_info = json.loads(known_mp_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    installed_file = HOME / ".claude/plugins/installed_plugins.json"
    if installed_file.is_file():
        try:
            data = json.loads(installed_file.read_text(encoding="utf-8"))
            installed_plugins = data.get("plugins", {})
            for plugin_id, entries in installed_plugins.items():
                for entry in entries:
                    install_path_str = entry.get("installPath")
                    if not install_path_str:
                        continue
                    install_path = Path(install_path_str)
                    version = entry.get("version")
                    commit_sha = entry.get("gitCommitSha")
                    
                    mp_name = plugin_id.split("@")[-1] if "@" in plugin_id else None
                    pure_name = plugin_id.split("@")[0] if "@" in plugin_id else plugin_id
                    repo_url = None
                    if mp_name and mp_name in marketplaces_info:
                        src = marketplaces_info[mp_name].get("source", {})
                        if src.get("source") == "github":
                            repo_url = f"https://github.com/{src.get('repo')}"

                    contained_skills: list[SkillItem] = []
                    skills_root = install_path / "skills" if (install_path / "skills").is_dir() else install_path
                    for root, _, files in os.walk(skills_root):
                        if "SKILL.md" in files:
                            skill_file = Path(root) / "SKILL.md"
                            s_name, s_desc, fm = extract_skill_info_from_file(skill_file)
                            rel_category = str(Path(root).relative_to(skills_root).parent)
                            if rel_category in (".", ""):
                                rel_category = None
                            
                            contained_skills.append(SkillItem(
                                id=f"claude:plugin:{pure_name}:{s_name}",
                                name=s_name,
                                description=s_desc,
                                section="claude",
                                subsection="cli",
                                source_type="marketplace_github",
                                source_label=f"Marketplace ({mp_name})" if mp_name else "Marketplace / GitHub",
                                path=str(skill_file),
                                plugin_name=pure_name,
                                version=fm.get("version") or version,
                                marketplace=mp_name,
                                repo_url=repo_url,
                                commit_sha=commit_sha,
                                category=rel_category,
                                metadata={"scope": entry.get("scope", "user"), "frontmatter": fm},
                            ))

                    plugins.append(PluginItem(
                        id=f"claude:plugin:{plugin_id}",
                        name=pure_name,
                        description=f"Plugin {pure_name} installed from {mp_name or 'marketplace'}",
                        section="claude",
                        subsection="cli",
                        source_type="marketplace_github",
                        source_label=f"Marketplace ({mp_name})" if mp_name else "Marketplace / GitHub",
                        version=version,
                        marketplace=mp_name,
                        repo_url=repo_url,
                        commit_sha=commit_sha,
                        install_path=str(install_path),
                        skills_count=len(contained_skills),
                        skills=contained_skills,
                        metadata=entry,
                    ))
        except Exception:
            pass

    # Inspect cached plugins in ~/.claude/plugins/cache/
    cache_dir = HOME / ".claude/plugins/cache"
    if cache_dir.is_dir():
        for mp_dir in cache_dir.iterdir():
            if not mp_dir.is_dir() or mp_dir.name.startswith("."):
                continue
            for p_dir in mp_dir.iterdir():
                if not p_dir.is_dir() or p_dir.name.startswith("."):
                    continue
                plugin_name = p_dir.name
                if any(p.name == plugin_name for p in plugins):
                    continue
                
                for v_dir in p_dir.iterdir():
                    if not v_dir.is_dir():
                        continue
                    skills_root = v_dir / "skills"
                    contained_skills = []
                    if skills_root.is_dir():
                        for root, _, files in os.walk(skills_root):
                            if "SKILL.md" in files:
                                skill_file = Path(root) / "SKILL.md"
                                s_name, s_desc, fm = extract_skill_info_from_file(skill_file)
                                contained_skills.append(SkillItem(
                                    id=f"claude:cache:{plugin_name}:{s_name}",
                                    name=s_name,
                                    description=s_desc,
                                    section="claude",
                                    subsection="cli",
                                    source_type="marketplace_github",
                                    source_label=f"Marketplace Cache ({mp_dir.name})",
                                    path=str(skill_file),
                                    plugin_name=plugin_name,
                                    version=v_dir.name,
                                    marketplace=mp_dir.name,
                                    metadata={"frontmatter": fm},
                                ))
                    
                    if contained_skills:
                        plugins.append(PluginItem(
                            id=f"claude:cache:{plugin_name}",
                            name=plugin_name,
                            description=f"Cached plugin from {mp_dir.name}",
                            section="claude",
                            subsection="cli",
                            source_type="marketplace_github",
                            source_label=f"Marketplace Cache ({mp_dir.name})",
                            version=v_dir.name,
                            marketplace=mp_dir.name,
                            repo_url=f"https://github.com/anthropics/{mp_dir.name}" if "official" in mp_dir.name else None,
                            commit_sha=None,
                            install_path=str(v_dir),
                            skills_count=len(contained_skills),
                            skills=contained_skills,
                        ))

    return plugins


def scan_claude_app_cowork() -> tuple[list[PluginItem], list[SkillItem], dict[str, Any]]:
    """Scans Claude Desktop App Cowork extensions, files, and MCP configs."""
    plugins: list[PluginItem] = []
    skills: list[SkillItem] = []
    metadata: dict[str, Any] = {}
    
    app_supp = HOME / "Library/Application Support/Claude"
    if not app_supp.is_dir():
        return plugins, skills, metadata

    seen_plugin_names: set[str] = set()
    sessions_root = app_supp / "local-agent-mode-sessions"
    if sessions_root.is_dir():
        for manifest_file in sessions_root.rglob("rpm/manifest.json"):
            rpm_dir = manifest_file.parent
            try:
                m_data = json.loads(manifest_file.read_text(encoding="utf-8"))
                for p_meta in m_data.get("plugins", []):
                    p_id = p_meta.get("id")
                    p_name = p_meta.get("name", p_id)
                    if p_name in seen_plugin_names:
                        continue
                    seen_plugin_names.add(p_name)
                    p_display = p_meta.get("displayName", p_name)
                    mp_name = p_meta.get("marketplaceName", "Cowork Registry")
                    p_dir = rpm_dir / p_id if p_id else None
                    if not p_dir or not p_dir.is_dir():
                        continue

                    # Read plugin manifest
                    p_manifest = {}
                    p_json_file = p_dir / "plugin.json"
                    if not p_json_file.is_file():
                        p_json_file = p_dir / ".claude-plugin/plugin.json"
                    if p_json_file.is_file():
                        try:
                            p_manifest = json.loads(p_json_file.read_text(encoding="utf-8"))
                        except Exception:
                            pass

                    p_version = p_manifest.get("version", "1.0.0")
                    p_desc = p_manifest.get("description", p_display)

                    contained_skills: list[SkillItem] = []
                    for s_md in p_dir.rglob("SKILL.md"):
                        s_name, s_desc, fm = extract_skill_info_from_file(s_md)
                        contained_skills.append(SkillItem(
                            id=f"claude:cowork:{p_name}:{s_name}",
                            name=s_name,
                            description=s_desc,
                            section="claude",
                            subsection="app_cowork",
                            source_type="desktop_extension",
                            source_label=f"Cowork Plugin ({mp_name})",
                            path=str(s_md),
                            plugin_name=p_name,
                            version=fm.get("version") or p_version,
                            marketplace=mp_name,
                            metadata={"frontmatter": fm, "scope": "cowork"},
                        ))

                    plugins.append(PluginItem(
                        id=f"claude:cowork:rpm:{p_id}",
                        name=p_name,
                        description=p_desc,
                        section="claude",
                        subsection="app_cowork",
                        source_type="desktop_extension",
                        source_label=f"Cowork Plugin ({mp_name})",
                        version=p_version,
                        marketplace=mp_name,
                        repo_url=p_manifest.get("repository") or p_manifest.get("homepage"),
                        commit_sha=None,
                        install_path=str(p_dir),
                        skills_count=len(contained_skills),
                        skills=contained_skills,
                        metadata=p_meta,
                    ))
            except Exception:
                pass

    # 2. Legacy extensions if present
    ext_file = app_supp / "extensions-installations.json"
    if ext_file.is_file():
        try:
            data = json.loads(ext_file.read_text(encoding="utf-8"))
            for ext_id, info in data.get("extensions", {}).items():
                ext_dir = app_supp / "Claude Extensions" / ext_id
                if not ext_dir.is_dir():
                    continue

                manifest = info.get("manifest", {})
                ext_name = manifest.get("name", ext_id)
                ext_desc = manifest.get("description", "")
                version = info.get("version")
                hash_val = info.get("hash")

                if ext_id.startswith("ant.dir.ant"):
                    src_label = "Anthropic Directory (Official)"
                elif ext_id.startswith("ant.dir.gh"):
                    src_label = "GitHub Extension Directory"
                else:
                    src_label = "Desktop Extension"

                ext_item = PluginItem(
                    id=f"claude:cowork:ext:{ext_id}",
                    name=ext_name,
                    description=ext_desc,
                    section="claude",
                    subsection="app_cowork",
                    source_type="desktop_extension",
                    source_label=src_label,
                    version=version,
                    marketplace="Anthropic Extension Registry",
                    repo_url="https://github.com/anthropics" if "anthropic" in ext_id else None,
                    commit_sha=hash_val[:12] if hash_val else None,
                    install_path=str(ext_dir),
                    metadata=info,
                )
                plugins.append(ext_item)
        except Exception:
            pass

    cfg_file = app_supp / "claude_desktop_config.json"
    cowork_path = HOME / "Claude"
    if cfg_file.is_file():
        try:
            cfg_data = json.loads(cfg_file.read_text(encoding="utf-8"))
            cowork_path = Path(cfg_data.get("coworkUserFilesPath", str(HOME / "Claude")))
            metadata["coworkUserFilesPath"] = str(cowork_path)
            metadata["mcpServers"] = cfg_data.get("mcpServers", {})
            metadata["trustedFolders"] = cfg_data.get("preferences", {}).get("localAgentModeTrustedFolders", [])
        except Exception:
            pass

    # Scan plugins installed in Cowork folder
    cowork_plugins_root = cowork_path / "plugins"
    if cowork_plugins_root.is_dir():
        for item in sorted(cowork_plugins_root.iterdir()):
            if item.name.startswith("."):
                continue
            if not item.is_dir() and not (item.is_symlink() and item.resolve().is_dir()):
                continue

            manifest_file = item / "plugin.json"
            if not manifest_file.is_file() and (item / ".claude-plugin/plugin.json").is_file():
                manifest_file = item / ".claude-plugin/plugin.json"

            p_name = item.name
            p_desc = f"Cowork Plugin in {item.name}"
            manifest = {}
            if manifest_file.is_file():
                try:
                    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
                    p_name = manifest.get("name", p_name)
                    p_desc = manifest.get("description", p_desc)
                except Exception:
                    pass

            if p_name in seen_plugin_names:
                continue
            seen_plugin_names.add(p_name)

            contained_skills: list[SkillItem] = []
            for root, _, files in os.walk(item, followlinks=True):
                if "SKILL.md" in files:
                    skill_file = Path(root) / "SKILL.md"
                    s_name, s_desc, fm = extract_skill_info_from_file(skill_file)
                    contained_skills.append(SkillItem(
                        id=f"claude:cowork:plugin:{p_name}:{s_name}",
                        name=s_name,
                        description=s_desc,
                        section="claude",
                        subsection="app_cowork",
                        source_type="local",
                        source_label="Cowork Plugin",
                        path=str(skill_file),
                        plugin_name=p_name,
                        version=fm.get("version") or manifest.get("version"),
                        metadata={"frontmatter": fm},
                    ))

            plugins.append(PluginItem(
                id=f"claude:cowork:plugin:{item.name}",
                name=p_name,
                description=p_desc,
                section="claude",
                subsection="app_cowork",
                source_type="local",
                source_label="Cowork Plugin",
                version=manifest.get("version", "1.0.0"),
                marketplace=None,
                repo_url=None,
                commit_sha=None,
                install_path=str(item),
                skills_count=len(contained_skills),
                skills=contained_skills,
                metadata=manifest,
            ))

    return plugins, skills, metadata


def scan_claude_app_code() -> dict[str, Any]:
    """Scans Claude Desktop App Code integration and VM/worktrees."""
    app_supp = HOME / "Library/Application Support/Claude"
    result: dict[str, Any] = {
        "installed": (app_supp / "claude-code").is_dir(),
        "runtime_versions": [],
        "worktrees": [],
        "trusted_folders": [],
    }
    
    code_dir = app_supp / "claude-code"
    if code_dir.is_dir():
        result["runtime_versions"] = [d.name for d in code_dir.iterdir() if d.is_dir() and not d.name.startswith(".")]

    worktrees_file = app_supp / "git-worktrees.json"
    if worktrees_file.is_file():
        try:
            wt_data = json.loads(worktrees_file.read_text(encoding="utf-8"))
            cwds = wt_data.get("untrackedDirGc", {}).get("cwds", {})
            result["worktrees"] = list(cwds.keys())
        except Exception:
            pass

    cfg_file = app_supp / "claude_desktop_config.json"
    if cfg_file.is_file():
        try:
            cfg_data = json.loads(cfg_file.read_text(encoding="utf-8"))
            result["trusted_folders"] = cfg_data.get("preferences", {}).get("localAgentModeTrustedFolders", [])
        except Exception:
            pass

    return result


# ==============================================================================
# 2. Antigravity & Gemini Scanners
# ==============================================================================

def scan_antigravity_cli_skills() -> list[SkillItem]:
    """Scans Antigravity & Gemini CLI skills across ~/.gemini/ and ~/.antigravity/."""
    skills: list[SkillItem] = []
    seen_paths: set[str] = set()

    search_dirs = [
        HOME / ".gemini/antigravity-cli/skills",
        HOME / ".gemini/skills",
        HOME / ".gemini/commands",
        HOME / ".antigravity/skills",
        WORKSPACE / ".gemini/skills",
    ]

    for s_dir in search_dirs:
        if not s_dir.is_dir():
            continue
        for item in sorted(s_dir.iterdir()):
            if item.name.startswith("."):
                continue
            skill_md = item / "SKILL.md" if item.is_dir() else (item if item.suffix == ".md" else None)
            if skill_md and skill_md.is_file():
                path_str = str(item)
                if path_str in seen_paths:
                    continue
                seen_paths.add(path_str)
                name, desc, fm = extract_skill_info_from_file(skill_md)
                src_type, src_label, resolved = determine_local_source_label(item)
                skills.append(SkillItem(
                    id=f"antigravity:cli:{item.name}",
                    name=name,
                    description=desc,
                    section="antigravity",
                    subsection="cli",
                    source_type=src_type,
                    source_label=src_label,
                    version=fm.get("version"),
                    category=fm.get("category"),
                    path=path_str,
                    resolved_path=resolved,
                    metadata={"surface": "Antigravity / Gemini CLI", "target_key": "agy-cli", "frontmatter": fm},
                ))
    return skills


def scan_antigravity_cli_plugins() -> list[PluginItem]:
    """Scans Antigravity & Gemini plugins across ~/.gemini/ and ~/.antigravity/."""
    plugins: list[PluginItem] = []
    seen_plugins: set[str] = set()

    plugin_dirs = [
        HOME / ".gemini/antigravity/plugins",
        HOME / ".gemini/config/plugins",
        HOME / ".gemini/antigravity-cli/plugins",
        HOME / ".gemini/plugins",
        HOME / ".antigravity/plugins",
        WORKSPACE / ".gemini/plugins",
    ]

    for p_root in plugin_dirs:
        if not p_root.is_dir():
            continue
        for item in sorted(p_root.iterdir()):
            if item.name.startswith(".") or item.name in seen_plugins:
                continue
            if not item.is_dir() and not (item.is_symlink() and item.resolve().is_dir()):
                continue

            seen_plugins.add(item.name)
            manifest_file = item / "plugin.json"
            if not manifest_file.is_file() and (item / ".claude-plugin/plugin.json").is_file():
                manifest_file = item / ".claude-plugin/plugin.json"

            p_name = item.name
            p_desc = f"Antigravity Plugin in {item.name}"
            manifest = {}
            if manifest_file.is_file():
                try:
                    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
                    p_name = manifest.get("name", p_name)
                    p_desc = manifest.get("description", p_desc)
                except Exception:
                    pass

            contained_skills: list[SkillItem] = []
            for root, _, files in os.walk(item):
                if "SKILL.md" in files:
                    skill_file = Path(root) / "SKILL.md"
                    s_name, s_desc, fm = extract_skill_info_from_file(skill_file)
                    contained_skills.append(SkillItem(
                        id=f"antigravity:plugin:{p_name}:{s_name}",
                        name=s_name,
                        description=s_desc,
                        section="antigravity",
                        subsection="cli",
                        source_type="local",
                        source_label="Installed Plugin",
                        path=str(skill_file),
                        plugin_name=p_name,
                        version=fm.get("version") or manifest.get("version"),
                        category=fm.get("category"),
                        metadata={"frontmatter": fm},
                    ))

            plugins.append(PluginItem(
                id=f"antigravity:plugin:{item.name}",
                name=p_name,
                description=p_desc,
                section="antigravity",
                subsection="cli",
                source_type="local",
                source_label="Antigravity Plugin",
                version=manifest.get("version", "1.0.0"),
                marketplace=None,
                repo_url=None,
                commit_sha=None,
                install_path=str(item),
                skills_count=len(contained_skills),
                skills=contained_skills,
                metadata=manifest,
            ))
    return plugins


def scan_antigravity_app_skills() -> list[SkillItem]:
    """Scans Antigravity 2.0 (Desktop & Core) global, built-in, and workspace skills."""
    skills: list[SkillItem] = []
    seen_paths: set[str] = set()

    # 1. Global skills
    global_dirs = [
        HOME / ".gemini/config/skills",
        HOME / ".gemini/antigravity/skills",
        HOME / ".gemini/skills",
        HOME / ".antigravity/skills",
    ]
    for g_dir in global_dirs:
        if not g_dir.is_dir():
            continue
        for item in sorted(g_dir.iterdir()):
            if item.name.startswith("."):
                continue
            skill_md = item / "SKILL.md" if item.is_dir() else (item if item.suffix == ".md" else None)
            if skill_md and skill_md.is_file():
                path_str = str(item)
                if path_str in seen_paths:
                    continue
                seen_paths.add(path_str)
                name, desc, fm = extract_skill_info_from_file(skill_md)
                src_type, src_label, resolved = determine_local_source_label(item)
                skills.append(SkillItem(
                    id=f"antigravity:app:global:{item.name}",
                    name=name,
                    description=desc,
                    section="antigravity",
                    subsection="app",
                    source_type=src_type,
                    source_label=src_label,
                    version=fm.get("version"),
                    category=fm.get("category"),
                    path=path_str,
                    resolved_path=resolved,
                    metadata={"scope": "global", "target_key": "agy", "surface": "Antigravity 2.0 App", "frontmatter": fm},
                ))

    # 2. Built-in Core Antigravity / Gemini skills
    builtin_dirs = [
        HOME / ".gemini/antigravity/builtin/skills",
        HOME / ".antigravity/builtin/skills",
        HOME / "Library/Application Support/Antigravity/builtin/skills",
        HOME / "Library/Application Support/Google/Antigravity/builtin/skills",
    ]
    for b_dir in builtin_dirs:
        if not b_dir.is_dir():
            continue
        for item in sorted(b_dir.iterdir()):
            if item.name.startswith("."):
                continue
            skill_md = item / "SKILL.md" if item.is_dir() else (item if item.suffix == ".md" else None)
            if skill_md and skill_md.is_file():
                path_str = str(item)
                if path_str in seen_paths:
                    continue
                seen_paths.add(path_str)
                name, desc, fm = extract_skill_info_from_file(skill_md)
                skills.append(SkillItem(
                    id=f"antigravity:app:builtin:{item.name}",
                    name=name,
                    description=desc,
                    section="antigravity",
                    subsection="app",
                    source_type="builtin",
                    source_label="Built-in (Antigravity Core)",
                    version=fm.get("version", "1.0.0"),
                    category=fm.get("category", "Core Engine"),
                    path=path_str,
                    resolved_path=path_str,
                    metadata={"scope": "builtin", "surface": "Antigravity App Core", "frontmatter": fm},
                ))

    # 3. Workspace skills: .agents/skills and .gemini/skills
    ws_dirs = [
        WORKSPACE / ".agents/skills",
        WORKSPACE / ".gemini/skills",
    ]
    for w_dir in ws_dirs:
        if not w_dir.is_dir():
            continue
        for item in sorted(w_dir.iterdir()):
            if item.name.startswith("."):
                continue
            skill_md = item / "SKILL.md" if item.is_dir() else (item if item.suffix == ".md" else None)
            if skill_md and skill_md.is_file():
                path_str = str(item)
                if path_str in seen_paths:
                    continue
                seen_paths.add(path_str)
                name, desc, fm = extract_skill_info_from_file(skill_md)
                src_type, src_label, resolved = determine_local_source_label(item)
                skills.append(SkillItem(
                    id=f"antigravity:app:workspace:{item.name}",
                    name=name,
                    description=desc,
                    section="antigravity",
                    subsection="app",
                    source_type=src_type,
                    source_label=src_label,
                    version=fm.get("version"),
                    category=fm.get("category"),
                    path=path_str,
                    resolved_path=resolved,
                    metadata={"scope": "workspace", "surface": "Project Workspace", "frontmatter": fm},
                ))

    return skills


def scan_antigravity_ide_skills() -> list[SkillItem]:
    """Scans Antigravity IDE global and workspace skills."""
    skills: list[SkillItem] = []
    seen_paths: set[str] = set()

    ide_dirs = [
        HOME / ".gemini/antigravity/skills",
        HOME / ".gemini/skills",
        HOME / ".antigravity/skills",
    ]
    for i_dir in ide_dirs:
        if not i_dir.is_dir():
            continue
        for item in sorted(i_dir.iterdir()):
            if item.name.startswith("."):
                continue
            skill_md = item / "SKILL.md" if item.is_dir() else (item if item.suffix == ".md" else None)
            if skill_md and skill_md.is_file():
                path_str = str(item)
                if path_str in seen_paths:
                    continue
                seen_paths.add(path_str)
                name, desc, fm = extract_skill_info_from_file(skill_md)
                src_type, src_label, resolved = determine_local_source_label(item)
                skills.append(SkillItem(
                    id=f"antigravity:ide:global:{item.name}",
                    name=name,
                    description=desc,
                    section="antigravity",
                    subsection="ide",
                    source_type=src_type,
                    source_label=src_label,
                    version=fm.get("version"),
                    category=fm.get("category"),
                    path=path_str,
                    resolved_path=resolved,
                    metadata={"scope": "global", "target_key": "agy-ide", "surface": "Antigravity IDE", "frontmatter": fm},
                ))

    # Workspace skills
    ws_dirs = [
        WORKSPACE / ".agents/skills",
        WORKSPACE / ".gemini/skills",
    ]
    for w_dir in ws_dirs:
        if not w_dir.is_dir():
            continue
        for item in sorted(w_dir.iterdir()):
            if item.name.startswith("."):
                continue
            skill_md = item / "SKILL.md" if item.is_dir() else (item if item.suffix == ".md" else None)
            if skill_md and skill_md.is_file():
                path_str = str(item)
                if path_str in seen_paths:
                    continue
                seen_paths.add(path_str)
                name, desc, fm = extract_skill_info_from_file(skill_md)
                src_type, src_label, resolved = determine_local_source_label(item)
                skills.append(SkillItem(
                    id=f"antigravity:ide:workspace:{item.name}",
                    name=name,
                    description=desc,
                    section="antigravity",
                    subsection="ide",
                    source_type=src_type,
                    source_label=src_label,
                    version=fm.get("version"),
                    category=fm.get("category"),
                    path=path_str,
                    resolved_path=resolved,
                    metadata={"scope": "workspace", "surface": "Antigravity IDE Workspace", "frontmatter": fm},
                ))

    return skills


# ==============================================================================
# 2.5. Cursor Scanners
# ==============================================================================

def scan_cursor_skills() -> list[SkillItem]:
    """Scans Cursor skills across ~/.cursor/skills-cursor/, ~/.cursor/skills/, and workspace .cursor/skills/."""
    skills: list[SkillItem] = []
    seen_paths: set[str] = set()

    sync_manifest = {}
    manifest_file = HOME / ".cursor/skills-cursor/.sync-manifest.json"
    if manifest_file.is_file():
        try:
            sync_manifest = json.loads(manifest_file.read_text(encoding="utf-8")).get("skills", {})
        except Exception:
            pass

    search_dirs = [
        HOME / ".cursor/skills-cursor",
        HOME / ".cursor/skills",
        HOME / "Library/Application Support/Cursor/User/skills",
        WORKSPACE / ".cursor/skills",
    ]

    for s_dir in search_dirs:
        if not s_dir.is_dir():
            continue
        for item in sorted(s_dir.iterdir()):
            if item.name.startswith("."):
                continue
            skill_md = item / "SKILL.md" if item.is_dir() else (item if item.suffix == ".md" else None)
            if skill_md and skill_md.is_file():
                path_str = str(item)
                if path_str in seen_paths:
                    continue
                seen_paths.add(path_str)
                name, desc, fm = extract_skill_info_from_file(skill_md)
                
                # Identify parent plugin origin
                p_origin = sync_manifest.get(item.name, {}).get("plugin")
                src_type, src_label, resolved = determine_local_source_label(item)
                if p_origin:
                    src_label = f"Cursor Skill ({p_origin})"

                skills.append(SkillItem(
                    id=f"cursor:skill:{item.name}",
                    name=name,
                    description=desc,
                    section="cursor",
                    subsection="skills",
                    source_type=src_type,
                    source_label=src_label,
                    version=fm.get("version"),
                    category=fm.get("category", "Cursor Skill"),
                    path=path_str,
                    resolved_path=resolved,
                    plugin_name=p_origin,
                    metadata={"scope": "workspace" if str(WORKSPACE) in path_str else "global", "target_key": "cursor", "surface": "Cursor IDE", "plugin": p_origin, "frontmatter": fm},
                ))
    return skills


def scan_cursor_rules() -> list[SkillItem]:
    """Scans Cursor rules (.cursor/rules/*.mdc, .cursorrules) across workspace and user global config."""
    rules: list[SkillItem] = []
    seen_paths: set[str] = set()

    rule_candidates = [
        WORKSPACE / ".cursor/rules",
        HOME / ".cursor/rules",
    ]

    for r_dir in rule_candidates:
        if not r_dir.is_dir():
            continue
        for item in sorted(r_dir.iterdir()):
            if item.name.startswith("."):
                continue
            if item.suffix in (".mdc", ".md"):
                path_str = str(item)
                if path_str in seen_paths:
                    continue
                seen_paths.add(path_str)
                name, desc, fm = extract_skill_info_from_file(item)
                globs = fm.get("globs", "")
                always_apply = fm.get("alwaysApply", "")
                src_type, src_label, resolved = determine_local_source_label(item)
                rules.append(SkillItem(
                    id=f"cursor:rule:{item.stem}",
                    name=name or item.stem,
                    description=desc or f"Cursor rule for {globs or 'workspace'}",
                    section="cursor",
                    subsection="rules",
                    source_type=src_type,
                    source_label=src_label,
                    version=fm.get("version"),
                    category="Cursor Rule (.mdc)",
                    path=path_str,
                    resolved_path=resolved,
                    metadata={"scope": "workspace" if str(WORKSPACE) in path_str else "global", "target_key": "cursor", "globs": globs, "alwaysApply": always_apply, "frontmatter": fm},
                ))

    # Flat .cursorrules files
    for cr_file in [WORKSPACE / ".cursorrules", HOME / ".cursorrules"]:
        if cr_file.is_file():
            path_str = str(cr_file)
            if path_str not in seen_paths:
                seen_paths.add(path_str)
                try:
                    content = cr_file.read_text(encoding="utf-8", errors="replace")
                    first_line = next((l.strip().lstrip("#").strip() for l in content.splitlines() if l.strip()), "Workspace Cursor Rules")
                except Exception:
                    first_line = "Workspace Cursor Rules"
                src_type, src_label, resolved = determine_local_source_label(cr_file)
                rules.append(SkillItem(
                    id=f"cursor:rule:cursorrules:{'ws' if str(WORKSPACE) in path_str else 'global'}",
                    name=f".cursorrules ({'Workspace' if str(WORKSPACE) in path_str else 'Global'})",
                    description=first_line,
                    section="cursor",
                    subsection="rules",
                    source_type=src_type,
                    source_label=src_label,
                    category="Cursor Rules File",
                    path=path_str,
                    resolved_path=resolved,
                    metadata={"scope": "workspace" if str(WORKSPACE) in path_str else "global", "target_key": "cursor"},
                ))

    return rules


def scan_cursor_plugins() -> list[PluginItem]:
    """Cursor delegates package distribution to parent framework plugins and executes skills directly."""
    return []


# ==============================================================================
# 4. Codex Scanners
# ==============================================================================

def _version_sort_key(name: str):
    """Sorts version directory names so 0.1.14 ranks after 0.1.9."""
    parts = []
    for token in re.split(r"[^0-9A-Za-z]+", name):
        if not token:
            continue
        parts.append((0, int(token)) if token.isdigit() else (1, token.lower()))
    return parts


def _latest_version_dir(plugin_dir: Path) -> Path | None:
    v_dirs = [v for v in plugin_dir.iterdir() if v.is_dir() and not v.name.startswith(".")]
    if not v_dirs:
        return None
    return sorted(v_dirs, key=lambda d: _version_sort_key(d.name))[-1]


def _collect_skill_items_from_root(
    skills_root: Path,
    *,
    id_prefix: str,
    section: str,
    subsection: str,
    source_type: str,
    source_label: str,
    plugin_name: str | None = None,
    version: str | None = None,
    marketplace: str | None = None,
    repo_url: str | None = None,
    extra_meta: dict[str, Any] | None = None,
) -> list[SkillItem]:
    """Walks a directory tree and returns SkillItem for every SKILL.md found."""
    skills: list[SkillItem] = []
    if not skills_root.is_dir():
        return skills
    for root, _, files in os.walk(skills_root):
        if "SKILL.md" not in files:
            continue
        skill_file = Path(root) / "SKILL.md"
        s_name, s_desc, fm = extract_skill_info_from_file(skill_file)
        src_type, src_label, resolved = determine_local_source_label(skill_file)
        meta = {"frontmatter": fm}
        if extra_meta:
            meta.update(extra_meta)
        skills.append(SkillItem(
            id=f"{id_prefix}:{s_name}",
            name=s_name,
            description=s_desc,
            section=section,
            subsection=subsection,
            source_type=source_type or src_type,
            source_label=source_label or src_label,
            path=str(skill_file.parent),
            resolved_path=resolved,
            plugin_name=plugin_name,
            version=fm.get("version") or version,
            marketplace=marketplace,
            repo_url=repo_url,
            category=fm.get("category"),
            metadata=meta,
        ))
    return skills


def scan_codex_skills() -> list[SkillItem]:
    """Scans Codex skills from ~/.codex/skills, ~/.agents/skills, and workspace .agents/.codex skills."""
    skills: list[SkillItem] = []
    seen_paths: set[str] = set()
    seen_names: set[str] = set()
    codex_home = _codex_home()

    def add_from_dir(s_dir: Path, id_prefix: str, source_type: str, source_label: str, extra_meta: dict[str, Any]):
        if not s_dir.is_dir():
            return
        for item in sorted(s_dir.iterdir()):
            if item.name.startswith("."):
                continue
            skill_md = item / "SKILL.md" if item.is_dir() else (item if item.suffix == ".md" else None)
            if not (skill_md and skill_md.is_file()):
                continue
            path_str = str(item)
            if path_str in seen_paths or item.name in seen_names:
                continue
            seen_paths.add(path_str)
            seen_names.add(item.name)
            name, desc, fm = extract_skill_info_from_file(skill_md)
            src_type, src_label, resolved = determine_local_source_label(item)
            skills.append(SkillItem(
                id=f"{id_prefix}:{item.name}",
                name=name,
                description=desc,
                section="codex",
                subsection="skills",
                source_type=source_type or src_type,
                source_label=source_label or src_label,
                path=path_str,
                resolved_path=resolved,
                version=fm.get("version"),
                category=fm.get("category", "Codex Skill"),
                metadata={**extra_meta, "frontmatter": fm, "target_key": "codex", "surface": "Codex CLI"},
            ))

    add_from_dir(
        WORKSPACE / ".agents/skills",
        "codex:skill:workspace-agents",
        "local_workspace",
        "Workspace Agents Skills",
        {"scope": "workspace"},
    )
    add_from_dir(
        WORKSPACE / ".codex/skills",
        "codex:skill:workspace",
        "local_workspace",
        "Workspace Codex Skills",
        {"scope": "workspace"},
    )
    add_from_dir(
        codex_home / "skills",
        "codex:skill:user",
        "local_user",
        "Codex User Skills",
        {"scope": "global"},
    )
    add_from_dir(
        HOME / ".agents/skills",
        "codex:skill:agents",
        "local_user",
        "User Agents Skills",
        {"scope": "global", "root": "~/.agents/skills"},
    )

    system_dir = codex_home / "skills" / ".system"
    if system_dir.is_dir():
        for item in sorted(system_dir.iterdir()):
            if item.name.startswith(".") or not item.is_dir():
                continue
            skill_md = item / "SKILL.md"
            if not skill_md.is_file():
                continue
            path_str = str(item)
            if path_str in seen_paths:
                continue
            seen_paths.add(path_str)
            name, desc, fm = extract_skill_info_from_file(skill_md)
            skills.append(SkillItem(
                id=f"codex:skill:system:{item.name}",
                name=name,
                description=desc,
                section="codex",
                subsection="skills",
                source_type="builtin",
                source_label="Codex Built-in",
                path=path_str,
                resolved_path=path_str,
                version=fm.get("version"),
                category=fm.get("category", "Codex System Skill"),
                metadata={"scope": "system", "target_key": "codex", "surface": "Codex CLI", "frontmatter": fm},
            ))

    return skills


def scan_codex_agents_md() -> list[SkillItem]:
    """Scans AGENTS.md files Codex uses as always-on project/global instructions."""
    rules: list[SkillItem] = []
    candidates = [
        (WORKSPACE / "AGENTS.md", "workspace", "Workspace AGENTS.md"),
        (WORKSPACE / ".codex/AGENTS.md", "workspace", "Workspace Codex AGENTS.md"),
        (_codex_home() / "AGENTS.md", "global", "Global Codex AGENTS.md"),
    ]
    seen: set[str] = set()
    for path, scope, label in candidates:
        if not path.is_file():
            continue
        path_str = str(path)
        if path_str in seen:
            continue
        seen.add(path_str)
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
            first_line = next((l.strip().lstrip("#").strip() for l in content.splitlines() if l.strip()), label)
        except Exception:
            first_line = label
        src_type, src_label, resolved = determine_local_source_label(path)
        rules.append(SkillItem(
            id=f"codex:rule:agents-md:{scope}:{path.name}",
            name=label,
            description=first_line,
            section="codex",
            subsection="rules",
            source_type=src_type,
            source_label=src_label,
            category="AGENTS.md",
            path=path_str,
            resolved_path=resolved,
            metadata={"scope": scope, "target_key": "codex", "surface": "Codex CLI"},
        ))
    return rules


def scan_codex_plugins() -> list[PluginItem]:
    """Scans cached Codex plugins from ~/.codex/plugins/cache/<marketplace>/<plugin>/<version>/."""
    plugins: list[PluginItem] = []
    cache_dir = _codex_home() / "plugins" / "cache"
    if not cache_dir.is_dir():
        return plugins

    for mp_dir in sorted(cache_dir.iterdir()):
        if not mp_dir.is_dir() or mp_dir.name.startswith("."):
            continue
        for p_dir in sorted(mp_dir.iterdir()):
            if not p_dir.is_dir() or p_dir.name.startswith("."):
                continue
            latest = _latest_version_dir(p_dir)
            if latest is None:
                continue

            plugin_json = latest / ".codex-plugin" / "plugin.json"
            p_meta: dict[str, Any] = {}
            if plugin_json.is_file():
                try:
                    p_meta = json.loads(plugin_json.read_text(encoding="utf-8"))
                except Exception:
                    p_meta = {}

            plugin_name = p_meta.get("name") or p_dir.name
            version = p_meta.get("version") or latest.name
            description = (
                p_meta.get("description")
                or (p_meta.get("interface") or {}).get("shortDescription")
                or f"Codex plugin {plugin_name}"
            )
            repo_url = p_meta.get("repository") or p_meta.get("homepage")
            if isinstance(repo_url, dict):
                repo_url = repo_url.get("url")

            skills_rel = p_meta.get("skills") or "./skills/"
            skills_root = (latest / skills_rel).resolve() if skills_rel else latest / "skills"
            if not skills_root.is_dir():
                skills_root = latest / "skills"

            contained = _collect_skill_items_from_root(
                skills_root,
                id_prefix=f"codex:plugin:{plugin_name}",
                section="codex",
                subsection="plugins",
                source_type="marketplace_github",
                source_label=f"Codex Plugin Cache ({mp_dir.name})",
                plugin_name=plugin_name,
                version=version,
                marketplace=mp_dir.name,
                repo_url=repo_url,
                extra_meta={"scope": "user", "target_key": "codex", "surface": "Codex CLI"},
            )

            plugins.append(PluginItem(
                id=f"codex:plugin:{mp_dir.name}:{plugin_name}",
                name=plugin_name,
                description=description,
                section="codex",
                subsection="plugins",
                source_type="marketplace_github",
                source_label=f"Codex Plugin Cache ({mp_dir.name})",
                version=version,
                marketplace=mp_dir.name,
                repo_url=repo_url,
                commit_sha=None,
                install_path=str(latest),
                skills_count=len(contained),
                skills=contained,
                metadata=p_meta,
            ))

    return plugins


# ==============================================================================
# 5. Master Alphabetical Skills Registry & Installation Matrix
# ==============================================================================

def scan_all_skills_alphabetical() -> list[dict[str, Any]]:
    """Gathers all unique skills generically across installed plugins, registered marketplaces, built-ins, and local agents.
    
    Returns an alphabetically sorted list focused on repository links and plugin origins.
    """
    skills_map: dict[str, dict[str, Any]] = {}

    # Target keys for matrix: claude, agy, agy-ide, agy-cli, cursor, codex
    active_target_defs = [
        {"key": "claude", "label": "Claude CLI", "skills_dir": HOME / ".claude/skills"},
        {"key": "agy", "label": "Antigravity App", "skills_dir": HOME / ".gemini/config/skills"},
        {"key": "agy-ide", "label": "Antigravity IDE", "skills_dir": HOME / ".gemini/antigravity/skills"},
        {"key": "agy-cli", "label": "Antigravity CLI", "skills_dir": HOME / ".gemini/antigravity-cli/skills"},
        {"key": "cursor", "label": "Cursor IDE", "skills_dir": HOME / ".cursor/skills-cursor"},
        {"key": "codex", "label": "Codex CLI", "skills_dir": _codex_home() / "skills"},
    ]

    # 1. Discovered from Installed Plugins (Claude Code, Cowork, Antigravity/Gemini, Cursor, Codex)
    all_plugins = [
        *scan_claude_cli_plugins(),
        *scan_antigravity_cli_plugins(),
        *scan_cursor_plugins(),
        *scan_codex_plugins(),
    ]
    cowork_plugins, _, _ = scan_claude_app_cowork()
    all_plugins.extend(cowork_plugins)

    # Include standalone Cursor skills
    for s in scan_cursor_skills():
        if s.name not in skills_map:
            skills_map[s.name] = {
                "name": s.name,
                "description": s.description,
                "source_group": "Cursor IDE",
                "origin_path": s.path,
                "repo_url": None,
                "plugin_name": None,
                "version": s.version or "1.0.0",
                "can_install": False,
                "category": s.category or "Cursor",
                "targets": {},
            }

    # Include standalone Codex skills (user, workspace, built-in, AGENTS.md)
    for s in (*scan_codex_skills(), *scan_codex_agents_md()):
        if s.name not in skills_map:
            skills_map[s.name] = {
                "name": s.name,
                "description": s.description,
                "source_group": "Codex Built-in" if s.source_type == "builtin" else "Codex CLI",
                "origin_path": s.path,
                "repo_url": s.repo_url,
                "plugin_name": s.plugin_name,
                "version": s.version or "1.0.0",
                "can_install": False,
                "category": s.category or "Codex",
                "targets": {},
            }

    for p in all_plugins:
        repo_link = p.repo_url or (p.metadata.get("homepage") if p.metadata else None)
        for s in p.skills:
            if s.name not in skills_map:
                skills_map[s.name] = {
                    "name": s.name,
                    "description": s.description,
                    "source_group": f"Plugin: {p.name}",
                    "origin_path": s.path,
                    "repo_url": repo_link,
                    "plugin_name": p.name,
                    "version": s.version or p.version,
                    "can_install": False,
                    "category": s.category or p.name,
                    "targets": {},
                }

    # 2. Discovered from Registered Marketplace Catalogs
    marketplaces = scan_marketplaces()
    for mp in marketplaces:
        mp_repo = mp.get("repo")
        mp_name = mp.get("name", "Marketplace")
        for p_entry in mp.get("plugins", []):
            p_name = p_entry.get("name", "")
            p_desc = p_entry.get("description", "")
            p_repo = p_entry.get("repo_url") or mp_repo
            for s_item in p_entry.get("skills", []):
                s_name = s_item.get("name") if isinstance(s_item, dict) else s_item
                if s_name and s_name not in skills_map:
                    skills_map[s_name] = {
                        "name": s_name,
                        "description": s_item.get("description", p_desc) if isinstance(s_item, dict) else p_desc,
                        "source_group": f"Marketplace: {mp_name}",
                        "origin_path": p_repo or mp_name,
                        "repo_url": p_repo,
                        "plugin_name": p_name,
                        "version": p_entry.get("version"),
                        "can_install": False,
                        "category": p_name or "Marketplace",
                        "targets": {},
                    }

    # 3. Built-in Antigravity Core Skills
    builtin_skills = [s for s in scan_antigravity_app_skills() if s.source_type == "builtin"]
    for s in builtin_skills:
        if s.name not in skills_map:
            skills_map[s.name] = {
                "name": s.name,
                "description": s.description,
                "source_group": "Built-in Core",
                "origin_path": s.path,
                "repo_url": None,
                "plugin_name": None,
                "version": s.version or "1.0.0",
                "can_install": False,
                "category": s.category or "Core Engine",
                "targets": {},
            }

    # 4. Project Workspace Custom Skills (.agents/skills or .claude/skills if present in active workspace)
    ws_dirs = [
        WORKSPACE / ".agents/skills",
        WORKSPACE / ".claude/skills",
        WORKSPACE / ".gemini/skills",
        WORKSPACE / ".codex/skills",
    ]
    for ws_dir in ws_dirs:
        if ws_dir.is_dir():
            for item in ws_dir.iterdir():
                if item.name.startswith("."):
                    continue
                skill_md = item / "SKILL.md" if item.is_dir() else (item if item.suffix == ".md" else None)
                if skill_md and skill_md.is_file():
                    name, desc, fm = extract_skill_info_from_file(skill_md)
                    if name not in skills_map:
                        skills_map[name] = {
                            "name": name,
                            "description": desc,
                            "source_group": f"Workspace ({ws_dir.parent.name})",
                            "origin_path": str(item),
                            "repo_url": None,
                            "plugin_name": None,
                            "version": fm.get("version"),
                            "can_install": True,
                            "category": fm.get("category", "Project Custom"),
                            "targets": {},
                        }

    # Fill installation status for each target surface
    for name, skill_entry in skills_map.items():
        installed_count = 0
        total_targets = len(active_target_defs)
        for t in active_target_defs:
            t_key = t["key"]
            dest = t["skills_dir"] / name

            is_file = dest.is_file()
            is_dir = dest.is_dir()
            is_installed = is_file or is_dir
            if is_installed:
                installed_count += 1

            skill_entry["targets"][t_key] = {
                "target_name": t["label"],
                "installed": is_installed,
                "path": str(dest),
            }

        skill_entry["installed_count"] = installed_count
        skill_entry["total_targets"] = total_targets
        skill_entry["is_all_installed"] = (installed_count == total_targets)

    # Sort alphabetically by skill name
    return sorted(skills_map.values(), key=lambda x: x["name"].lower())


# ==============================================================================
# 4. Official Plugin & Marketplace Management (Zero Symlinks Standard)
# ==============================================================================

def clean_legacy_symlinks() -> list[str]:
    """Removes any obsolete manual symlinks to enforce the strict official plugin standard."""
    cleaned = []
    for d in [
        HOME / ".claude/skills",
        HOME / ".claude-clone/skills",
        HOME / ".gemini/config/skills",
        HOME / ".gemini/antigravity/skills",
        HOME / ".gemini/antigravity-cli/skills",
    ]:
        if d.is_dir():
            for item in d.iterdir():
                if item.is_symlink():
                    try:
                        item.unlink()
                        cleaned.append(str(item))
                    except Exception:
                        pass
    return cleaned


def uninstall_plugin_item(plugin_id: str, install_path_str: str) -> dict[str, Any]:
    """Uninstalls a plugin by backing up its directory and removing registration."""
    path = Path(install_path_str)
    if not path.exists():
        return {"success": False, "message": f"Plugin path {install_path_str} does not exist"}

    # Back up the plugin folder
    dest_dir = BACKUPS / "plugins"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{path.name}-{datetime.now():%Y%m%d-%H%M%S}"
    shutil.move(str(path), str(dest))

    # Also clean up installed_plugins.json if it was a registered Claude plugin
    for installed_file in [HOME / ".claude/plugins/installed_plugins.json", HOME / ".claude-clone/plugins/installed_plugins.json"]:
        if installed_file.is_file():
            try:
                data = json.loads(installed_file.read_text(encoding="utf-8"))
                plugins_dict = data.get("plugins", {})
                if plugin_id in plugins_dict:
                    del plugins_dict[plugin_id]
                    installed_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
            except Exception:
                pass

    # Also clean up extensions-installations.json if it was a Claude Desktop Extension
    for ext_file in [
        HOME / "Library/Application Support/Claude/extensions-installations.json",
        HOME / "Library/Application Support/Claude-Clone/extensions-installations.json",
        HOME / "Library/Application Support/Claude-One/extensions-installations.json",
    ]:
        if ext_file.is_file():
            try:
                data = json.loads(ext_file.read_text(encoding="utf-8"))
                ext_dict = data.get("extensions", {})
                ext_id = plugin_id.replace("claude:cowork:ext:", "")
                if ext_id in ext_dict:
                    del ext_dict[ext_id]
                    ext_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
            except Exception:
                pass

    # Also clean up Cowork rpm manifest.json across sessions in Claude, Claude-Clone, and Claude-One
    for app_supp in [
        HOME / "Library/Application Support/Claude",
        HOME / "Library/Application Support/Claude-Clone",
        HOME / "Library/Application Support/Claude-One",
    ]:
        sessions_root = app_supp / "local-agent-mode-sessions"
        if sessions_root.is_dir():
            for m_file in sessions_root.rglob("rpm/manifest.json"):
                try:
                    m_data = json.loads(m_file.read_text(encoding="utf-8"))
                    p_list = m_data.get("plugins", [])
                    p_id_cleaned = plugin_id.replace("claude:cowork:rpm:", "")
                    p_list = [p for p in p_list if p.get("id") != p_id_cleaned and p.get("name") != path.name]
                    m_data["plugins"] = p_list
                    m_file.write_text(json.dumps(m_data, indent=2), encoding="utf-8")
                except Exception:
                    pass

    return {"success": True, "plugin_id": plugin_id, "backup_path": str(dest)}


# ==============================================================================
# Marketplace Catalog Management
# ==============================================================================

def scan_marketplaces() -> list[dict[str, Any]]:
    """Discovers all registered marketplace catalogs and their offered plugins."""
    known_mp_file = HOME / ".claude/plugins/known_marketplaces.json"
    if not known_mp_file.is_file():
        return []

    try:
        known = json.loads(known_mp_file.read_text(encoding="utf-8"))
    except Exception:
        return []

    marketplaces = []
    for name, info in known.items():
        src = info.get("source", {})
        src_type = src.get("source", "unknown")
        repo = src.get("repo") or src.get("path")
        loc_str = info.get("installLocation", "")
        loc = Path(loc_str) if loc_str else None
        
        plugins_in_mp = []
        desc = ""
        
        # Check marketplace.json in loc / .claude-plugin
        if loc and loc.is_dir():
            manifest_candidates = [
                loc / ".claude-plugin/marketplace.json",
                loc / "marketplace.json",
            ]
            for cand in manifest_candidates:
                if cand.is_file():
                    try:
                        mp_data = json.loads(cand.read_text(encoding="utf-8"))
                        desc = mp_data.get("description", desc)
                        for p in mp_data.get("plugins", []):
                            plugins_in_mp.append({
                                "name": p.get("name"),
                                "description": p.get("description", ""),
                                "version": p.get("version", "1.0.0"),
                                "source": p.get("source", "")
                            })
                    except Exception:
                        pass
                    break

        marketplaces.append({
            "name": name,
            "source_type": src_type,
            "repo": repo,
            "installLocation": loc_str,
            "lastUpdated": info.get("lastUpdated"),
            "description": desc or f"Marketplace catalog for {name}",
            "plugins_count": len(plugins_in_mp),
            "plugins": plugins_in_mp,
            "is_removable": True
        })

    return sorted(marketplaces, key=lambda x: x["name"].lower())


def add_marketplace(source: str, repo: str | None = None, name: str | None = None) -> dict[str, Any]:
    """Registers a marketplace catalog in ~/.claude/plugins/known_marketplaces.json."""
    known_mp_file = HOME / ".claude/plugins/known_marketplaces.json"
    known_mp_file.parent.mkdir(parents=True, exist_ok=True)
    
    known = {}
    if known_mp_file.is_file():
        try:
            known = json.loads(known_mp_file.read_text(encoding="utf-8"))
        except Exception:
            known = {}

    source = source.strip()
    if "github.com/" in source:
        repo_part = source.split("github.com/")[-1].strip("/").replace(".git", "")
        repo_val = repo_part
        src_type = "github"
        mp_name = name or repo_part.split("/")[-1]
    elif "/" in source and not source.startswith("/") and not source.startswith("~") and not source.startswith("."):
        repo_val = source
        src_type = "github"
        mp_name = name or source.split("/")[-1]
    elif os.path.exists(os.path.expanduser(source)):
        dir_path = str(Path(os.path.expanduser(source)).resolve())
        src_type = "directory"
        repo_val = None
        mp_name = name or Path(dir_path).name
    else:
        if repo:
            src_type = "github"
            repo_val = repo
            mp_name = name or repo.split("/")[-1]
        else:
            return {"success": False, "message": f"Invalid marketplace source: {source}"}

    install_loc = HOME / f".claude/plugins/marketplaces/{mp_name}"
    
    if src_type == "github":
        install_loc.parent.mkdir(parents=True, exist_ok=True)
        if not install_loc.is_dir():
            cmd = f"git clone --depth 1 https://github.com/{repo_val}.git '{install_loc}'"
            ret = os.system(cmd)
            if ret != 0:
                return {"success": False, "message": f"Failed to clone repository https://github.com/{repo_val}.git"}
        else:
            os.system(f"git -C '{install_loc}' pull --ff-only 2>/dev/null || true")

        known[mp_name] = {
            "source": {
                "source": "github",
                "repo": repo_val
            },
            "installLocation": str(install_loc),
            "lastUpdated": datetime.utcnow().isoformat() + "Z"
        }
    else:
        known[mp_name] = {
            "source": {
                "source": "directory",
                "path": dir_path
            },
            "installLocation": dir_path,
            "lastUpdated": datetime.utcnow().isoformat() + "Z"
        }

    known_mp_file.write_text(json.dumps(known, indent=2), encoding="utf-8")
    return {"success": True, "marketplace": mp_name, "message": f"Marketplace '{mp_name}' registered successfully."}


def remove_marketplace(name: str) -> dict[str, Any]:
    """Removes a marketplace catalog from ~/.claude/plugins/known_marketplaces.json."""
    known_mp_file = HOME / ".claude/plugins/known_marketplaces.json"
    if not known_mp_file.is_file():
        return {"success": False, "message": "No registered marketplaces found."}

    try:
        known = json.loads(known_mp_file.read_text(encoding="utf-8"))
    except Exception as e:
        return {"success": False, "message": f"Error reading known marketplaces: {e}"}

    if name not in known:
        return {"success": False, "message": f"Marketplace '{name}' not found."}

    info = known.pop(name)
    known_mp_file.write_text(json.dumps(known, indent=2), encoding="utf-8")

    loc = Path(info.get("installLocation", ""))
    if loc.is_dir() and str(HOME / ".claude/plugins/marketplaces") in str(loc):
        try:
            shutil.rmtree(loc, ignore_errors=True)
        except Exception:
            pass

    return {"success": True, "marketplace": name, "message": f"Marketplace '{name}' removed successfully."}


def sync_cowork_plugins() -> list[str]:
    """Syncs ai-first-fw-skills, ai-first-fw-utilities, and installed marketplace plugins to Claude Desktop & Claude-Clone Cowork sessions."""
    synced = []
    app_supp_dirs = [
        HOME / "Library/Application Support/Claude",
        HOME / "Library/Application Support/Claude-Clone",
        HOME / "Library/Application Support/Claude-One",
    ]

    workspace = WORKSPACE
    now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    cache_root = HOME / ".claude/plugins/cache"

    for app_supp in app_supp_dirs:
        if not app_supp.is_dir() or (app_supp.is_symlink() and app_supp.name == "Claude-One"):
            continue
        sessions_root = app_supp / "local-agent-mode-sessions"
        if not sessions_root.is_dir():
            continue

        for manifest_file in sessions_root.rglob("rpm/manifest.json"):
            base_rpm = manifest_file.parent
            try:
                manifest_data = json.loads(manifest_file.read_text(encoding="utf-8"))
                plugins_list = manifest_data.get("plugins", [])

                # Identify official/installed IDs from manifest or directory
                skills_entry = next((p for p in plugins_list if p.get("name") == "ai-first-fw-skills" or p.get("id") == "plugin_01NcPbSGH4AdLAJUHBHejvNR"), None)
                utils_entry = next((p for p in plugins_list if p.get("name") == "ai-first-fw-utilities" or p.get("id") == "plugin_01Ek9Vap9MMJ3ZvpYBzNomna"), None)
                mcps_entry = next((p for p in plugins_list if p.get("name") == "ai-first-fw-mcps" or p.get("id") == "plugin_01AiFirstFwMcps0001"), None)

                # Preserve real ID if present; fallback to standard known installed ID
                skills_plugin_id = skills_entry.get("id") if (skills_entry and skills_entry.get("id") and not skills_entry.get("id").startswith("plugin_01AiFirstFwSkills001")) else "plugin_01NcPbSGH4AdLAJUHBHejvNR"
                utils_plugin_id = utils_entry.get("id") if (utils_entry and utils_entry.get("id") and not utils_entry.get("id").startswith("plugin_01AiFirstUtilities01")) else "plugin_01Ek9Vap9MMJ3ZvpYBzNomna"
                mcps_plugin_id = mcps_entry.get("id") if (mcps_entry and mcps_entry.get("id")) else "plugin_01AiFirstFwMcps0001"

                # 1. Sync ai-first-fw-skills directly to plugin root
                skills_src = workspace / "ai-first-fw/skills"
                if skills_src.is_dir():
                    skills_dest = base_rpm / skills_plugin_id
                    if skills_dest.exists():
                        shutil.rmtree(skills_dest)
                    shutil.copytree(skills_src, skills_dest, ignore=shutil.ignore_patterns(".DS_Store", "__pycache__"))
                    (skills_dest / ".claude-plugin").mkdir(exist_ok=True)
                    if (skills_src / "plugin.json").is_file():
                        shutil.copy2(skills_src / "plugin.json", skills_dest / ".claude-plugin/plugin.json")

                # 2. Sync ai-first-fw-utilities directly to plugin root
                utils_src = workspace / "ai-first-fw/utilities"
                if utils_src.is_dir():
                    utils_dest = base_rpm / utils_plugin_id
                    if utils_dest.exists():
                        shutil.rmtree(utils_dest)
                    shutil.copytree(utils_src, utils_dest, ignore=shutil.ignore_patterns(".DS_Store", "__pycache__"))
                    (utils_dest / ".claude-plugin").mkdir(exist_ok=True)
                    if (utils_src / "plugin.json").is_file():
                        shutil.copy2(utils_src / "plugin.json", utils_dest / ".claude-plugin/plugin.json")

                # 3. Sync ai-first-fw-mcps directly to plugin root
                mcps_src = workspace / "ai-first-fw/local-mcps"
                if mcps_src.is_dir():
                    mcps_dest = base_rpm / mcps_plugin_id
                    if mcps_dest.exists():
                        shutil.rmtree(mcps_dest)
                    shutil.copytree(mcps_src, mcps_dest, ignore=shutil.ignore_patterns(".DS_Store", "__pycache__", ".venv", "*.zip"))
                    (mcps_dest / ".claude-plugin").mkdir(exist_ok=True)
                    if (mcps_src / "plugin.json").is_file():
                        shutil.copy2(mcps_src / "plugin.json", mcps_dest / ".claude-plugin/plugin.json")

                # 4. Clean up any obsolete temporary/duplicate IDs
                for obsolete_id in ("plugin_01AiFirstFwSkills001", "plugin_01AiFirstUtilities01"):
                    if obsolete_id not in (skills_plugin_id, utils_plugin_id, mcps_plugin_id):
                        obsolete_path = base_rpm / obsolete_id
                        if obsolete_path.exists():
                            shutil.rmtree(obsolete_path, ignore_errors=True)

                # 5. Sync other installed marketplace plugins (e.g. mattpocock-skills)
                for p in plugins_list:
                    p_name = p.get("name")
                    p_id = p.get("id")
                    if not p_name or not p_id or p_name in ("ai-first-fw-skills", "ai-first-fw-utilities", "ai-first-fw-mcps"):
                        continue
                    if cache_root.is_dir():
                        matching_dirs = list(cache_root.glob(f"*/{p_name}/*"))
                        if matching_dirs:
                            latest_cached = sorted([d for d in matching_dirs if d.is_dir()], key=lambda d: d.name)[-1]
                            dest = base_rpm / p_id
                            if dest.exists():
                                shutil.rmtree(dest)
                            shutil.copytree(latest_cached, dest, ignore=shutil.ignore_patterns(".DS_Store", "__pycache__"))
                            (dest / ".claude-plugin").mkdir(exist_ok=True)
                            if (latest_cached / "plugin.json").is_file():
                                shutil.copy2(latest_cached / "plugin.json", dest / ".claude-plugin/plugin.json")
                    p["updatedAt"] = now_iso
                    p["updatedAtVerified"] = True

                # 6. Update manifest entries
                updated_plugins = [
                    p for p in plugins_list
                    if p.get("id") not in (skills_plugin_id, utils_plugin_id, mcps_plugin_id, "plugin_01AiFirstFwSkills001", "plugin_01AiFirstUtilities01")
                    and p.get("name") not in ("ai-first-fw-skills", "ai-first-fw-utilities", "ai-first-fw-mcps")
                ]

                skills_meta = skills_entry or {}
                updated_plugins.append({
                    "id": skills_plugin_id,
                    "name": "ai-first-fw-skills",
                    "displayName": skills_meta.get("displayName", "AI-First Framework Skills"),
                    "updatedAt": now_iso,
                    "updatedAtVerified": True,
                    "marketplaceId": skills_meta.get("marketplaceId", "marketplace_01JiAwPPGztsSf8qBEDumJwo"),
                    "marketplaceName": skills_meta.get("marketplaceName", "ai-framework"),
                    "installedBy": skills_meta.get("installedBy", "user"),
                    "installationPreference": skills_meta.get("installationPreference", "available")
                })

                utils_meta = utils_entry or {}
                updated_plugins.append({
                    "id": utils_plugin_id,
                    "name": "ai-first-fw-utilities",
                    "displayName": utils_meta.get("displayName", "AI-First Framework Utilities"),
                    "updatedAt": now_iso,
                    "updatedAtVerified": True,
                    "marketplaceId": utils_meta.get("marketplaceId", "marketplace_01JiAwPPGztsSf8qBEDumJwo"),
                    "marketplaceName": utils_meta.get("marketplaceName", "ai-framework"),
                    "installedBy": utils_meta.get("installedBy", "user"),
                    "installationPreference": utils_meta.get("installationPreference", "available")
                })

                mcps_meta = mcps_entry or {}
                updated_plugins.append({
                    "id": mcps_plugin_id,
                    "name": "ai-first-fw-mcps",
                    "displayName": mcps_meta.get("displayName", "AI-First Framework MCPs"),
                    "updatedAt": now_iso,
                    "updatedAtVerified": True,
                    "marketplaceId": mcps_meta.get("marketplaceId", "marketplace_01JiAwPPGztsSf8qBEDumJwo"),
                    "marketplaceName": mcps_meta.get("marketplaceName", "ai-framework"),
                    "installedBy": mcps_meta.get("installedBy", "user"),
                    "installationPreference": mcps_meta.get("installationPreference", "available")
                })

                manifest_data["plugins"] = updated_plugins
                manifest_data["lastUpdated"] = int(time.time() * 1000)
                manifest_file.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")
                synced.append(f"{app_supp.name}:{base_rpm.parent.name}")
            except Exception:
                pass

        # Sync skills-plugin built-in skills if in Claude-Clone / Claude-One from primary Claude app
        if app_supp.name in ("Claude-Clone", "Claude-One"):
            src_sp_dirs = list((HOME / "Library/Application Support/Claude/local-agent-mode-sessions/skills-plugin").glob("*/*")) if (HOME / "Library/Application Support/Claude/local-agent-mode-sessions/skills-plugin").is_dir() else []
            dst_sp_dirs = list((app_supp / "local-agent-mode-sessions/skills-plugin").glob("*/*")) if (app_supp / "local-agent-mode-sessions/skills-plugin").is_dir() else []
            if src_sp_dirs and dst_sp_dirs:
                src_sp = src_sp_dirs[0]
                for dst_sp in dst_sp_dirs:
                    try:
                        for item in dst_sp.iterdir():
                            if item.is_dir():
                                shutil.rmtree(item)
                            else:
                                item.unlink()
                        for item in src_sp.iterdir():
                            if item.is_dir():
                                shutil.copytree(item, dst_sp / item.name, symlinks=True)
                            else:
                                shutil.copy2(item, dst_sp / item.name)
                        synced.append(f"{app_supp.name}:skills-plugin")
                    except Exception:
                        pass

        # Also sync ~/Claude/plugins if present
        cfg_file = app_supp / "claude_desktop_config.json"
        cowork_path = HOME / "Claude"
        if cfg_file.is_file():
            try:
                cfg_data = json.loads(cfg_file.read_text(encoding="utf-8"))
                cowork_path = Path(cfg_data.get("coworkUserFilesPath", str(HOME / "Claude")))
            except Exception:
                pass
        cowork_plugins_dir = cowork_path / "plugins"
        if cowork_plugins_dir.is_dir():
            skills_link = cowork_plugins_dir / "ai-first-fw-skills"
            utils_link = cowork_plugins_dir / "ai-first-fw-utilities"
            if skills_link.is_symlink() or skills_link.exists():
                try:
                    skills_link.unlink(missing_ok=True)
                except Exception:
                    shutil.rmtree(skills_link, ignore_errors=True)
            try:
                skills_link.symlink_to(workspace / "ai-first-fw/skills", target_is_directory=True)
            except Exception:
                pass

            if utils_link.is_symlink() or utils_link.exists():
                try:
                    utils_link.unlink(missing_ok=True)
                except Exception:
                    shutil.rmtree(utils_link, ignore_errors=True)
            try:
                utils_link.symlink_to(workspace / "ai-first-fw/utilities", target_is_directory=True)
            except Exception:
                pass

    return synced


def sync_antigravity_plugins() -> list[str]:
    """Syncs marketplace plugins to Antigravity global plugins directory (~/.gemini/config/plugins/)."""
    synced = []
    agy_plugins_dir = HOME / ".gemini/config/plugins"
    agy_plugins_dir.mkdir(parents=True, exist_ok=True)
    workspace = WORKSPACE

    # 1. Sync ai-first-fw-skills
    skills_src = workspace / "ai-first-fw/skills"
    if skills_src.is_dir():
        tgt = agy_plugins_dir / "ai-first-fw-skills"
        if tgt.exists():
            shutil.rmtree(tgt)
        shutil.copytree(skills_src, tgt)
        synced.append("ai-first-fw-skills")

    # 2. Sync ai-first-fw-utilities
    utils_src = workspace / "ai-first-fw/utilities"
    if utils_src.is_dir():
        tgt = agy_plugins_dir / "ai-first-fw-utilities"
        if tgt.exists():
            shutil.rmtree(tgt)
        shutil.copytree(utils_src, tgt)
        synced.append("ai-first-fw-utilities")

    # 3. Sync cached marketplace plugins (e.g. mattpocock-skills)
    cache_root = HOME / ".claude/plugins/cache"
    if cache_root.is_dir():
        for mp_dir in cache_root.iterdir():
            if not mp_dir.is_dir():
                continue
            for p_dir in mp_dir.iterdir():
                if not p_dir.is_dir() or p_dir.name in ("ai-first-fw-skills", "ai-first-fw-utilities"):
                    continue
                v_dirs = [v for v in p_dir.iterdir() if v.is_dir()]
                if not v_dirs:
                    continue
                latest_v = sorted(v_dirs, key=lambda d: d.name)[-1]
                tgt = agy_plugins_dir / p_dir.name
                if tgt.exists():
                    shutil.rmtree(tgt)
                shutil.copytree(latest_v, tgt)
                synced.append(p_dir.name)

    return synced


def sync_cursor_plugins() -> list[str]:
    """Syncs ai-first-fw-skills, ai-first-fw-utilities, and cached marketplace plugins directly to Cursor global skills (~/.cursor/skills-cursor/).
    
    Filters:
      - ai-first-fw-skills: Excludes review-code (disabled for Cursor).
      - mattpocock-skills: Keeps only grill skills (grill-me, grill-with-docs, grilling) and wait-what/wait-wait; disables/removes all others.
    """
    synced = []
    cursor_skills_dir = HOME / ".cursor/skills-cursor"
    cursor_skills_dir.mkdir(parents=True, exist_ok=True)
    
    # Clean up legacy ~/.cursor/plugins directory if present to avoid duplication
    cursor_plugins_dir = HOME / ".cursor/plugins"
    if cursor_plugins_dir.is_dir():
        try:
            shutil.rmtree(cursor_plugins_dir)
        except Exception:
            pass

    workspace = WORKSPACE
    now_ms = int(time.time() * 1000)

    # Disabled skills filter rules for Cursor
    CURSOR_DISABLED_AI_FIRST_SKILLS = {"review-code"}
    # Known mattpocock skills that are disabled for Cursor (keep only grill* and wait-what/wait-wait)
    KNOWN_MATTPOCOCK_DISABLED = {
        "ask-matt", "claude-handoff", "code-review", "codebase-design", "diagnosing-bugs",
        "domain-modeling", "git-guardrails-claude-code", "handoff", "implement",
        "improve-codebase-architecture", "loop-me", "migrate-to-shoehorn", "prototype",
        "research", "resolving-merge-conflicts", "scaffold-exercises", "setup-matt-pocock-skills",
        "setup-pre-commit", "setup-ts-deep-modules", "tdd", "teach", "to-questionnaire",
        "to-spec", "to-tickets", "triage", "wayfinder", "wizard", "writing-beats",
        "writing-for-agents", "writing-fragments", "writing-shape"
    }

    # 1. Read or initialize .sync-manifest.json in ~/.cursor/skills-cursor/
    sync_manifest_file = cursor_skills_dir / ".sync-manifest.json"
    sync_manifest = {"version": 1, "skills": {}, "lastInventoryAt": now_ms}
    if sync_manifest_file.is_file():
        try:
            sync_manifest = json.loads(sync_manifest_file.read_text(encoding="utf-8"))
            if "skills" not in sync_manifest:
                sync_manifest["skills"] = {}
        except Exception:
            pass

    # 2. Sync individual skills from ai-first-fw/skills and ai-first-fw/utilities
    for p_name, src_group in [("ai-first-fw-skills", workspace / "ai-first-fw/skills"), ("ai-first-fw-utilities", workspace / "ai-first-fw/utilities")]:
        if src_group.is_dir():
            for item in src_group.iterdir():
                if item.is_dir() and (item / "SKILL.md").is_file():
                    # Exclude disabled ai-first skills for Cursor (e.g. review-code)
                    if p_name == "ai-first-fw-skills" and item.name in CURSOR_DISABLED_AI_FIRST_SKILLS:
                        dest_skill = cursor_skills_dir / item.name
                        if dest_skill.exists():
                            shutil.rmtree(dest_skill, ignore_errors=True)
                        sync_manifest["skills"].pop(item.name, None)
                        continue

                    dest_skill = cursor_skills_dir / item.name
                    if dest_skill.exists():
                        shutil.rmtree(dest_skill)
                    shutil.copytree(item, dest_skill, ignore=shutil.ignore_patterns(".DS_Store", "__pycache__"))
                    sync_manifest["skills"][item.name] = {
                        "lastSyncedAt": now_ms,
                        "plugin": p_name,
                    }
                    synced.append(f"skill:{item.name}")

    # 3. Sync cached marketplace plugins (e.g. mattpocock-skills)
    cache_root = HOME / ".claude/plugins/cache"
    if cache_root.is_dir():
        for mp_dir in cache_root.iterdir():
            if not mp_dir.is_dir():
                continue
            for p_dir in mp_dir.iterdir():
                if not p_dir.is_dir() or p_dir.name in ("ai-first-fw-skills", "ai-first-fw-utilities"):
                    continue
                v_dirs = [v for v in p_dir.iterdir() if v.is_dir()]
                if not v_dirs:
                    continue
                latest_v = sorted(v_dirs, key=lambda d: d.name)[-1]

                is_mattpocock = "mattpocock" in p_dir.name or "matt-pocock" in p_dir.name

                for root, _, files in os.walk(latest_v):
                    if "SKILL.md" in files:
                        s_folder = Path(root)
                        s_name = s_folder.name

                        # For matt-pocock skills, keep only grill skills and wait-what/wait-wait
                        if is_mattpocock:
                            is_grill = s_name.startswith("grill")
                            is_wait = s_name in ("wait-what", "wait-wait")
                            if not (is_grill or is_wait):
                                dest_s = cursor_skills_dir / s_name
                                if dest_s.exists():
                                    shutil.rmtree(dest_s, ignore_errors=True)
                                sync_manifest["skills"].pop(s_name, None)
                                continue

                        dest_s = cursor_skills_dir / s_name
                        if dest_s.exists():
                            shutil.rmtree(dest_s)
                        shutil.copytree(s_folder, dest_s, ignore=shutil.ignore_patterns(".DS_Store", "__pycache__"))
                        sync_manifest["skills"][s_name] = {
                            "lastSyncedAt": now_ms,
                            "plugin": p_dir.name,
                        }
                        synced.append(f"skill:{s_name}")

    # Ensure wait-wait alias is available alongside wait-what for Cursor
    wait_what_dir = cursor_skills_dir / "wait-what"
    if wait_what_dir.is_dir():
        wait_wait_dir = cursor_skills_dir / "wait-wait"
        if wait_wait_dir.exists():
            shutil.rmtree(wait_wait_dir)
        shutil.copytree(wait_what_dir, wait_wait_dir)
        wait_wait_md = wait_wait_dir / "SKILL.md"
        if wait_wait_md.is_file():
            content = wait_wait_md.read_text(encoding="utf-8")
            content = content.replace("name: wait-what", "name: wait-wait")
            wait_wait_md.write_text(content, encoding="utf-8")
        sync_manifest["skills"]["wait-wait"] = {
            "lastSyncedAt": now_ms,
            "plugin": "mattpocock-skills",
        }
        synced.append("skill:wait-wait")

    # 4. Clean up any remaining disabled skills from disk and sync manifest
    for s_item in list(cursor_skills_dir.iterdir()):
        if not s_item.is_dir() or s_item.name.startswith("."):
            continue
        s_name = s_item.name
        # Remove disabled ai-first skills
        if s_name in CURSOR_DISABLED_AI_FIRST_SKILLS:
            shutil.rmtree(s_item, ignore_errors=True)
            sync_manifest["skills"].pop(s_name, None)
            continue
        # Remove disabled matt-pocock skills
        p_origin = sync_manifest.get("skills", {}).get(s_name, {}).get("plugin", "")
        if "mattpocock" in p_origin or "matt-pocock" in p_origin or s_name in KNOWN_MATTPOCOCK_DISABLED:
            if not (s_name.startswith("grill") or s_name in ("wait-what", "wait-wait")):
                shutil.rmtree(s_item, ignore_errors=True)
                sync_manifest["skills"].pop(s_name, None)

    # 5. Write updated .sync-manifest.json
    sync_manifest["lastInventoryAt"] = now_ms
    sync_manifest_file.write_text(json.dumps(sync_manifest, indent=2) + "\n", encoding="utf-8")

    return synced


def sync_codex_plugins() -> list[str]:
    """Installs framework and marketplace plugins into Codex on Pull Updates.

    Installs once as Codex plugins (marketplace + cache + config.toml enable).
    Does not copy SKILL.md into ~/.codex/skills or ~/.agents/skills — those roots plus
    enabled plugins were producing 2–3 copies of each skill in the Codex `$` picker.

    Never writes into ~/.codex/skills/.system.
    Same skill filters as Cursor: skip review-code; keep only grill/wait mattpocock skills.
    """
    synced: list[str] = []
    now_ms = int(time.time() * 1000)
    mp_name = "ai-framework"
    disabled_ai_first = {"review-code"}
    mattpocock_disabled = {
        "ask-matt", "claude-handoff", "code-review", "codebase-design", "diagnosing-bugs",
        "domain-modeling", "git-guardrails-claude-code", "handoff", "implement",
        "improve-codebase-architecture", "loop-me", "migrate-to-shoehorn", "prototype",
        "research", "resolving-merge-conflicts", "scaffold-exercises", "setup-matt-pocock-skills",
        "setup-pre-commit", "setup-ts-deep-modules", "tdd", "teach", "to-questionnaire",
        "to-spec", "to-tickets", "triage", "wayfinder", "wizard", "writing-beats",
        "writing-for-agents", "writing-fragments", "writing-shape",
    }

    codex_home = _codex_home()
    user_skill_dirs = [codex_home / "skills", HOME / ".agents/skills"]
    for d in user_skill_dirs:
        d.mkdir(parents=True, exist_ok=True)

    mp_root = codex_home / "plugins" / "marketplaces" / mp_name
    cache_root = codex_home / "plugins" / "cache" / mp_name
    mp_plugins_dir = mp_root / "plugins"
    mp_plugins_dir.mkdir(parents=True, exist_ok=True)
    cache_root.mkdir(parents=True, exist_ok=True)

    sync_manifest: dict[str, Any] = {"version": 1, "skills": {}, "lastInventoryAt": now_ms}
    manifest_file = (codex_home / "skills") / ".sync-manifest.json"
    if manifest_file.is_file():
        try:
            loaded = json.loads(manifest_file.read_text(encoding="utf-8"))
            if isinstance(loaded, dict) and isinstance(loaded.get("skills"), dict):
                sync_manifest["skills"] = loaded["skills"]
        except Exception:
            pass

    def _copy_tree(src: Path, dest: Path) -> None:
        if dest.exists():
            shutil.rmtree(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src, dest, ignore=shutil.ignore_patterns(".DS_Store", "__pycache__"))

    def _read_plugin_meta(src: Path, fallback_name: str, fallback_ver: str) -> tuple[str, str, str]:
        for candidate in (src / ".codex-plugin/plugin.json", src / ".claude-plugin/plugin.json", src / "plugin.json"):
            if candidate.is_file():
                try:
                    data = json.loads(candidate.read_text(encoding="utf-8"))
                    return (
                        data.get("name") or fallback_name,
                        str(data.get("version") or fallback_ver),
                        data.get("description") or f"Codex plugin {fallback_name}",
                    )
                except Exception:
                    pass
        return fallback_name, fallback_ver, f"Codex plugin {fallback_name}"

    def _codex_manifest(name: str, version: str, description: str) -> dict[str, Any]:
        short = description.strip().splitlines()[0][:120] if description else name
        return {
            "name": name,
            "version": version,
            "description": description,
            "author": {"name": "Steven Nguyen"},
            "homepage": "https://github.com/steven-nguyen-dev/ai-framework",
            "repository": "https://github.com/steven-nguyen-dev/ai-framework",
            "skills": "./skills/",
            "interface": {
                "displayName": name,
                "shortDescription": short,
                "longDescription": description,
                "developerName": "Steven Nguyen",
                "category": "Developer Tools",
                "capabilities": ["Read", "Write"],
            },
        }

    def _install_plugin(plugin_name: str, version: str, description: str, skill_folders: list[Path]) -> None:
        if not skill_folders:
            return
        plugin_dir = mp_plugins_dir / plugin_name
        if plugin_dir.exists():
            shutil.rmtree(plugin_dir)
        skills_root = plugin_dir / "skills"
        skills_root.mkdir(parents=True, exist_ok=True)
        for folder in skill_folders:
            _copy_tree(folder, skills_root / folder.name)
        wait_what = skills_root / "wait-what"
        if wait_what.is_dir() and not (skills_root / "wait-wait").exists():
            _copy_tree(wait_what, skills_root / "wait-wait")
            wait_wait_md = skills_root / "wait-wait" / "SKILL.md"
            if wait_wait_md.is_file():
                content = wait_wait_md.read_text(encoding="utf-8")
                wait_wait_md.write_text(content.replace("name: wait-what", "name: wait-wait"), encoding="utf-8")
        manifest_dir = plugin_dir / ".codex-plugin"
        manifest_dir.mkdir(parents=True, exist_ok=True)
        (manifest_dir / "plugin.json").write_text(
            json.dumps(_codex_manifest(plugin_name, version, description), indent=2) + "\n",
            encoding="utf-8",
        )
        cache_dest = cache_root / plugin_name / version
        _copy_tree(plugin_dir, cache_dest)
        synced.append(f"plugin:{plugin_name}@{version}")

    installed_plugin_names: list[str] = []
    marketplace_entries: list[dict[str, Any]] = []

    workspace_plugins = [
        ("ai-first-fw-skills", WORKSPACE / "ai-first-fw/skills", disabled_ai_first),
        ("ai-first-fw-utilities", WORKSPACE / "ai-first-fw/utilities", set()),
    ]
    for p_name, src_group, skip in workspace_plugins:
        if not src_group.is_dir():
            continue
        folders = [
            item for item in sorted(src_group.iterdir())
            if item.is_dir() and (item / "SKILL.md").is_file() and item.name not in skip and not item.name.startswith(".")
        ]
        name, version, description = _read_plugin_meta(src_group, p_name, "1.0.0")
        _install_plugin(name, version, description, folders)
        installed_plugin_names.append(name)
        marketplace_entries.append({
            "name": name,
            "source": {"source": "local", "path": f"./plugins/{name}"},
            "policy": {"installation": "INSTALLED_BY_DEFAULT", "authentication": "ON_INSTALL"},
            "category": "Developer Tools",
        })

    cache_claude = HOME / ".claude/plugins/cache"
    if cache_claude.is_dir():
        for mp_dir in cache_claude.iterdir():
            if not mp_dir.is_dir():
                continue
            for p_dir in mp_dir.iterdir():
                if not p_dir.is_dir() or p_dir.name in ("ai-first-fw-skills", "ai-first-fw-utilities", "ai-first-fw-mcps"):
                    continue
                v_dirs = [v for v in p_dir.iterdir() if v.is_dir() and not v.name.startswith(".")]
                if not v_dirs:
                    continue
                latest_v = sorted(v_dirs, key=lambda d: _version_sort_key(d.name))[-1]
                is_mattpocock = "mattpocock" in p_dir.name or "matt-pocock" in p_dir.name
                skill_folders: list[Path] = []
                for root, _, files in os.walk(latest_v):
                    if "SKILL.md" not in files:
                        continue
                    s_folder = Path(root)
                    s_name = s_folder.name
                    if is_mattpocock:
                        if not (s_name.startswith("grill") or s_name in ("wait-what", "wait-wait")):
                            continue
                    skill_folders.append(s_folder)
                name, version, description = _read_plugin_meta(latest_v, p_dir.name, latest_v.name)
                _install_plugin(name, version, description, skill_folders)
                installed_plugin_names.append(name)
                marketplace_entries.append({
                    "name": name,
                    "source": {"source": "local", "path": f"./plugins/{name}"},
                    "policy": {"installation": "INSTALLED_BY_DEFAULT", "authentication": "ON_INSTALL"},
                    "category": "Developer Tools",
                })

    # Remove previously flattened copies so Codex `$` lists each skill once (plugin only).
    previously_flattened = list(sync_manifest.get("skills", {}).keys())
    for dest_root in user_skill_dirs:
        if not dest_root.is_dir():
            continue
        for s_name in previously_flattened:
            dest = dest_root / s_name
            if dest.is_dir() and not dest.name.startswith("."):
                shutil.rmtree(dest, ignore_errors=True)
        for s_item in list(dest_root.iterdir()):
            if not s_item.is_dir() or s_item.name.startswith("."):
                continue
            if s_item.name in disabled_ai_first:
                shutil.rmtree(s_item, ignore_errors=True)

    sync_manifest = {"version": 1, "skills": {}, "plugins": installed_plugin_names, "lastInventoryAt": now_ms}
    manifest_file.write_text(json.dumps(sync_manifest, indent=2) + "\n", encoding="utf-8")

    if marketplace_entries:
        agents_mp = mp_root / ".agents" / "plugins"
        agents_mp.mkdir(parents=True, exist_ok=True)
        (agents_mp / "marketplace.json").write_text(json.dumps({
            "name": mp_name,
            "interface": {"displayName": "AI Framework"},
            "plugins": marketplace_entries,
        }, indent=2) + "\n", encoding="utf-8")

        tables: list[tuple[str, dict[str, Any]]] = [
            ("marketplaces.ai-framework", {"source_type": "local", "source": str(mp_root)}),
        ]
        for p_name in installed_plugin_names:
            tables.append((f'plugins."{p_name}@{mp_name}"', {"enabled": True}))
        _upsert_codex_config_tables(tables)
        synced.append(f"marketplace:{mp_name}")

    return synced


def pull_updates_from_marketplaces() -> dict[str, Any]:
    """Pulls down the latest updates exclusively from registered public marketplaces and updates installed plugins across Claude, Claude-One, Claude Code clone, Antigravity, Cursor, and Codex."""
    known_mp_file = HOME / ".claude/plugins/known_marketplaces.json"
    installed_file = HOME / ".claude/plugins/installed_plugins.json"

    marketplaces_updated = []
    plugins_updated = []
    errors = []

    # 1. Update each registered marketplace repository using public git
    if known_mp_file.is_file():
        try:
            known = json.loads(known_mp_file.read_text(encoding="utf-8"))
            for mp_name, info in known.items():
                loc_str = info.get("installLocation")
                if not loc_str:
                    continue
                loc = Path(loc_str)
                src = info.get("source", {})
                if src.get("source") == "github":
                    repo_slug = src.get("repo")
                    if not repo_slug:
                        continue
                    public_git_url = f"https://github.com/{repo_slug}.git"
                    try:
                        if not (loc / ".git").is_dir():
                            loc.parent.mkdir(parents=True, exist_ok=True)
                            if loc.exists():
                                shutil.rmtree(loc)
                            subprocess.run(["git", "clone", "--depth", "1", public_git_url, str(loc)], capture_output=True, check=True)
                        else:
                            # Ensure public remote URL without private tokens
                            subprocess.run(["git", "-C", str(loc), "remote", "set-url", "origin", public_git_url], capture_output=True, check=True)
                            subprocess.run(["git", "-C", str(loc), "fetch", "origin"], capture_output=True, check=True)
                            branch_res = subprocess.run(["git", "-C", str(loc), "rev-parse", "--abbrev-ref", "origin/HEAD"], capture_output=True, text=True)
                            target_ref = branch_res.stdout.strip() if branch_res.returncode == 0 and branch_res.stdout.strip() else "origin/main"
                            subprocess.run(["git", "-C", str(loc), "reset", "--hard", target_ref], capture_output=True, check=True)
                        info["lastUpdated"] = datetime.utcnow().isoformat() + "Z"
                        marketplaces_updated.append(f"{mp_name} ({repo_slug})")
                    except Exception as err:
                        errors.append(f"Failed to pull public marketplace {mp_name} ({public_git_url}): {err}")
            known_mp_file.write_text(json.dumps(known, indent=2), encoding="utf-8")
        except Exception as e:
            errors.append(f"Failed reading known_marketplaces.json: {e}")

    # 2. Update installed plugins from the freshly updated marketplaces
    if installed_file.is_file() and known_mp_file.is_file():
        try:
            installed_data = json.loads(installed_file.read_text(encoding="utf-8"))
            plugins_dict = installed_data.get("plugins", {})
            known = json.loads(known_mp_file.read_text(encoding="utf-8"))

            for plugin_id, installs in list(plugins_dict.items()):
                if not installs or not isinstance(installs, list):
                    continue
                install_entry = installs[0]
                old_version = install_entry.get("version")

                if "@" not in plugin_id:
                    continue
                p_name, mp_name = plugin_id.split("@", 1)

                mp_info = known.get(mp_name)
                if not mp_info or not mp_info.get("installLocation"):
                    continue
                mp_loc = Path(mp_info["installLocation"])
                if not mp_loc.is_dir():
                    continue

                mp_manifest_candidates = [
                    mp_loc / ".claude-plugin/marketplace.json",
                    mp_loc / "marketplace.json",
                ]
                plugin_rel_source = None
                mp_plugin_version = None
                for cand in mp_manifest_candidates:
                    if cand.is_file():
                        try:
                            m_json = json.loads(cand.read_text(encoding="utf-8"))
                            for p in m_json.get("plugins", []):
                                if p.get("name") == p_name:
                                    plugin_rel_source = p.get("source", "")
                                    mp_plugin_version = p.get("version")
                                    break
                        except Exception:
                            pass
                        if plugin_rel_source:
                            break

                plugin_src_dir = None
                if isinstance(plugin_rel_source, str) and plugin_rel_source:
                    plugin_src_dir = (mp_loc / plugin_rel_source).resolve()
                elif isinstance(plugin_rel_source, dict):
                    p_path = plugin_rel_source.get("path") or plugin_rel_source.get("source")
                    if p_path and isinstance(p_path, str):
                        plugin_src_dir = (mp_loc / p_path).resolve()

                if not plugin_src_dir or not plugin_src_dir.is_dir():
                    for fallback in [
                        mp_loc / p_name,
                        mp_loc / "skills" / p_name,
                        mp_loc / "utilities" / p_name,
                        mp_loc / "ai-first-fw" / "skills",
                        mp_loc / "ai-first-fw" / "utilities",
                        mp_loc / "plugins" / p_name,
                    ]:
                        if fallback.is_dir():
                            plugin_src_dir = fallback
                            break
                    else:
                        continue

                new_ver = mp_plugin_version or "1.0.0"
                p_meta_candidates = [
                    plugin_src_dir / "plugin.json",
                    plugin_src_dir / ".claude-plugin/plugin.json",
                ]
                for p_cand in p_meta_candidates:
                    if p_cand.is_file():
                        try:
                            p_json = json.loads(p_cand.read_text(encoding="utf-8"))
                            cand_ver = p_json.get("version")
                            if cand_ver:
                                new_ver = cand_ver
                                break
                        except Exception:
                            pass

                git_sha = None
                if (mp_loc / ".git").is_dir():
                    sha_res = subprocess.run(["git", "-C", str(mp_loc), "rev-parse", "HEAD"], capture_output=True, text=True)
                    if sha_res.returncode == 0:
                        git_sha = sha_res.stdout.strip()

                dest_cache = HOME / f".claude/plugins/cache/{mp_name}/{p_name}/{new_ver}"
                dest_cache.parent.mkdir(parents=True, exist_ok=True)

                if dest_cache.exists():
                    shutil.rmtree(dest_cache)
                shutil.copytree(plugin_src_dir, dest_cache, symlinks=True)

                # Ensure destination cache has synchronized plugin manifests
                c_plugin_json = dest_cache / "plugin.json"
                c_dot_plugin_json = dest_cache / ".claude-plugin/plugin.json"
                if c_plugin_json.is_file() and not c_plugin_json.is_symlink():
                    try:
                        p_data = json.loads(c_plugin_json.read_text(encoding="utf-8"))
                        if p_data.get("version") != new_ver:
                            p_data["version"] = new_ver
                            c_plugin_json.write_text(json.dumps(p_data, indent=2), encoding="utf-8")
                    except Exception:
                        pass

                if c_dot_plugin_json.is_file() and not c_dot_plugin_json.is_symlink():
                    try:
                        p_data = json.loads(c_dot_plugin_json.read_text(encoding="utf-8"))
                        if p_data.get("version") != new_ver:
                            p_data["version"] = new_ver
                            c_dot_plugin_json.write_text(json.dumps(p_data, indent=2), encoding="utf-8")
                    except Exception:
                        pass
                elif not c_dot_plugin_json.exists() and c_plugin_json.is_file():
                    (dest_cache / ".claude-plugin").mkdir(parents=True, exist_ok=True)
                    try:
                        shutil.copy2(c_plugin_json, c_dot_plugin_json)
                    except Exception:
                        pass

                new_skills_list = []
                for s_dir in dest_cache.rglob("SKILL.md"):
                    new_skills_list.append(s_dir.parent.name)

                install_entry["version"] = new_ver
                install_entry["installPath"] = str(dest_cache)
                install_entry["lastUpdated"] = datetime.utcnow().isoformat() + "Z"
                if git_sha:
                    install_entry["gitCommitSha"] = git_sha

                plugins_updated.append({
                    "plugin_id": plugin_id,
                    "old_version": old_version,
                    "new_version": new_ver,
                    "skills_count": len(new_skills_list),
                    "skills": new_skills_list,
                })

            installed_file.write_text(json.dumps(installed_data, indent=2), encoding="utf-8")
        except Exception as e:
            errors.append(f"Failed updating installed plugins: {e}")

    # 3. Synchronize to .claude-clone environment if present
    clone_dir = HOME / ".claude-clone"
    if clone_dir.is_dir():
        try:
            # Sync cache
            src_cache = HOME / ".claude/plugins/cache"
            dst_cache = clone_dir / "plugins/cache"
            if src_cache.is_dir():
                dst_cache.mkdir(parents=True, exist_ok=True)
                for mp in src_cache.iterdir():
                    if not mp.is_dir() or mp.name.startswith("."):
                        continue
                    for p in mp.iterdir():
                        if not p.is_dir() or p.name.startswith("."):
                            continue
                        for v in p.iterdir():
                            if not v.is_dir() or v.name.startswith("."):
                                continue
                            target_v = dst_cache / mp.name / p.name / v.name
                            if not target_v.exists():
                                target_v.parent.mkdir(parents=True, exist_ok=True)
                                shutil.copytree(v, target_v, symlinks=True)

            # Sync installed_plugins.json
            if installed_file.is_file():
                inst_text = installed_file.read_text(encoding="utf-8")
                clone_inst_text = inst_text.replace("/.claude/", "/.claude-clone/")
                (clone_dir / "plugins/installed_plugins.json").write_text(clone_inst_text, encoding="utf-8")

            # Sync known_marketplaces.json
            if known_mp_file.is_file():
                known_text = known_mp_file.read_text(encoding="utf-8")
                clone_known_text = known_text.replace("/.claude/", "/.claude-clone/")
                (clone_dir / "plugins/known_marketplaces.json").write_text(clone_known_text, encoding="utf-8")

            # Sync marketplaces folder
            src_mp = HOME / ".claude/plugins/marketplaces"
            dst_mp = clone_dir / "plugins/marketplaces"
            if src_mp.is_dir():
                dst_mp.mkdir(parents=True, exist_ok=True)
                for mp_folder in src_mp.iterdir():
                    if not mp_folder.is_dir() or mp_folder.name.startswith("."):
                        continue
                    dst_mp_folder = dst_mp / mp_folder.name
                    if not dst_mp_folder.exists():
                        shutil.copytree(mp_folder, dst_mp_folder, symlinks=True)

            # Sync personal skills
            src_skills = HOME / ".claude/skills"
            dst_skills = clone_dir / "skills"
            if src_skills.is_dir():
                dst_skills.mkdir(parents=True, exist_ok=True)
                for s_item in src_skills.iterdir():
                    if s_item.name.startswith("."):
                        continue
                    dst_s_item = dst_skills / s_item.name
                    if dst_s_item.exists():
                        if dst_s_item.is_dir():
                            shutil.rmtree(dst_s_item)
                        else:
                            dst_s_item.unlink()
                    if s_item.is_dir():
                        shutil.copytree(s_item, dst_s_item, symlinks=True)
                    else:
                        shutil.copy2(s_item, dst_s_item)

            # Sync hooks
            src_hooks = HOME / ".claude/hooks"
            dst_hooks = clone_dir / "hooks"
            if src_hooks.is_dir():
                dst_hooks.mkdir(parents=True, exist_ok=True)
                for h_item in src_hooks.iterdir():
                    if h_item.name.startswith("."):
                        continue
                    dst_h_item = dst_hooks / h_item.name
                    if not dst_h_item.exists():
                        if h_item.is_dir():
                            shutil.copytree(h_item, dst_h_item, symlinks=True)
                        else:
                            shutil.copy2(h_item, dst_h_item)
        except Exception as e:
            errors.append(f"Failed syncing to .claude-clone: {e}")

    # 4. Clean any legacy symlinks to maintain zero symlink footprint
    cleaned_symlinks = clean_legacy_symlinks()
    cowork_synced = sync_cowork_plugins()
    antigravity_synced = sync_antigravity_plugins()
    cursor_synced = sync_cursor_plugins()
    try:
        codex_synced = sync_codex_plugins()
    except Exception as e:
        errors.append(f"Failed installing Codex plugins: {e}")
        codex_synced = []

    return {
        "success": True,
        "marketplaces_updated": marketplaces_updated,
        "plugins_updated": plugins_updated,
        "cleaned_legacy_symlinks": len(cleaned_symlinks),
        "cowork_sessions_synced": len(cowork_synced),
        "antigravity_plugins_synced": len(antigravity_synced),
        "cursor_items_synced": len(cursor_synced),
        "codex_items_synced": len(codex_synced),
        "errors": errors,
    }


# Backward-compatible alias
sync_and_update_all_marketplaces = pull_updates_from_marketplaces


# ==============================================================================
# ==============================================================================
# MCP Servers Scanner & Manager
# ==============================================================================

def _parse_toml_value(val: str):
    val = val.strip()
    if val.startswith("[") and val.endswith("]"):
        inner = val[1:-1].strip()
        if not inner:
            return []
        items = re.findall(r'"((?:\\.|[^"\\])*)"|\'((?:\\.|[^\'\\])*)\'|([^,\s]+)', inner)
        return [a or b or c for a, b, c in items]
    if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
        return bytes(val[1:-1], "utf-8").decode("unicode_escape") if "\\" in val[1:-1] else val[1:-1]
    if val.lower() in ("true", "false"):
        return val.lower() == "true"
    try:
        return int(val)
    except ValueError:
        pass
    try:
        return float(val)
    except ValueError:
        return val


def _parse_toml_mcp_fallback(text: str) -> dict[str, Any]:
    """Minimal parser for [mcp_servers.name] tables when tomllib is unavailable."""
    mcp: dict[str, dict[str, Any]] = {}
    current: dict[str, Any] | None = None
    env_mode = False
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        hm = re.match(r'^\[mcp_servers\.("?)([^"\]]+)\1(\.env)?\]$', line)
        if hm:
            name = hm.group(2)
            env_mode = bool(hm.group(3))
            current = mcp.setdefault(name, {})
            if env_mode:
                current.setdefault("env", {})
            continue
        if re.match(r"^\[", line):
            current = None
            env_mode = False
            continue
        if current is None or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        parsed = _parse_toml_value(val)
        if env_mode:
            current.setdefault("env", {})[key] = parsed
        else:
            current[key] = parsed
    return {"mcp_servers": mcp}


def _load_toml_file(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return {}
    if tomllib is not None:
        try:
            return tomllib.loads(text)
        except Exception:
            pass
    return _parse_toml_mcp_fallback(text)


def _load_codex_mcp_servers() -> dict[str, Any]:
    """Merges [mcp_servers] tables from global and workspace Codex config.toml files."""
    result: dict[str, Any] = {}
    for cfg_file in [_codex_home() / "config.toml", WORKSPACE / ".codex/config.toml"]:
        data = _load_toml_file(cfg_file)
        mcp = data.get("mcp_servers") or data.get("mcpServers") or {}
        if isinstance(mcp, dict):
            for name, cfg in mcp.items():
                if isinstance(cfg, dict):
                    result[name] = cfg
    return result


def _codex_mcp_lookup(name: str, mcps: dict[str, Any]) -> tuple[bool, Any]:
    """Returns (active, details). Codex tables with enabled=false count as inactive."""
    cfg = mcps.get(name) or mcps.get(f"{name}-local")
    if cfg is None:
        cfg = next((v for k, v in mcps.items() if name in k), None)
    if not isinstance(cfg, dict):
        return False, cfg
    if cfg.get("enabled") is False:
        return False, cfg
    return True, cfg


def _toml_quote(value: str) -> str:
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'


def _normalize_toml_header(header: str) -> str:
    return header.replace('"', "")


def _strip_toml_table(text: str, target_header: str) -> str:
    """Removes a TOML table and nested tables under the same header."""
    target = _normalize_toml_header(target_header)
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    skipping = False
    for line in lines:
        header_m = re.match(r"^\[+([^\]\n]+)\]+", line)
        if header_m:
            header = _normalize_toml_header(header_m.group(1).strip())
            skipping = header == target or header.startswith(target + ".")
        if not skipping:
            out.append(line)
    return "".join(out)


def _render_simple_toml_table(header: str, fields: dict[str, Any]) -> str:
    lines = [f"[{header}]"]
    for key, value in fields.items():
        if isinstance(value, bool):
            lines.append(f"{key} = {'true' if value else 'false'}")
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            lines.append(f"{key} = {value}")
        else:
            lines.append(f"{key} = {_toml_quote(str(value))}")
    return "\n".join(lines) + "\n"


def _upsert_codex_config_tables(tables: list[tuple[str, dict[str, Any]]]) -> None:
    """Inserts or replaces named tables in ~/.codex/config.toml without rewriting other keys."""
    cfg_file = _codex_home() / "config.toml"
    cfg_file.parent.mkdir(parents=True, exist_ok=True)
    text = cfg_file.read_text(encoding="utf-8") if cfg_file.is_file() else ""
    for header, fields in tables:
        text = _strip_toml_table(text, header)
        if text and not text.endswith("\n"):
            text += "\n"
        if text.strip():
            text += "\n"
        text += _render_simple_toml_table(header, fields)
    cfg_file.write_text(text, encoding="utf-8")


def _codex_mcp_table_header(server_id: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9_-]+", server_id):
        return f"mcp_servers.{server_id}"
    escaped = server_id.replace("\\", "\\\\").replace('"', '\\"')
    return f'mcp_servers."{escaped}"'


def _strip_toml_mcp_server(text: str, server_id: str) -> str:
    """Removes [mcp_servers.ID] and nested [mcp_servers.ID.*] tables from a TOML file."""
    unquoted_prefixes = {f"mcp_servers.{server_id}", f'mcp_servers."{server_id}"'}
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    skipping = False
    for line in lines:
        header_m = re.match(r"^\[+([^\]\n]+)\]+", line)
        if header_m:
            header = header_m.group(1).strip()
            header_unquoted = header.replace('"', "")
            skipping = False
            for prefix in (f"mcp_servers.{server_id}",):
                if header_unquoted == prefix or header_unquoted.startswith(prefix + "."):
                    skipping = True
                    break
            if not skipping:
                for prefix in unquoted_prefixes:
                    if header == prefix or header.startswith(prefix + "."):
                        skipping = True
                        break
        if not skipping:
            out.append(line)
    return "".join(out).rstrip() + ("\n" if text.endswith("\n") or out else "\n")


def _render_codex_mcp_block(server_id: str, cfg: dict[str, Any]) -> str:
    header = _codex_mcp_table_header(server_id)
    lines = [f"[{header}]"]
    if cfg.get("command"):
        lines.append(f"command = {_toml_quote(cfg['command'])}")
    if cfg.get("args"):
        args = ", ".join(_toml_quote(a) for a in cfg["args"])
        lines.append(f"args = [{args}]")
    if cfg.get("url"):
        lines.append(f"url = {_toml_quote(cfg['url'])}")
    if cfg.get("type"):
        lines.append(f"type = {_toml_quote(cfg['type'])}")
    env = cfg.get("env")
    if isinstance(env, dict) and env:
        lines.append("")
        lines.append(f"[{header}.env]")
        for k, v in env.items():
            lines.append(f"{k} = {_toml_quote(str(v))}")
    return "\n".join(lines) + "\n"


def _write_codex_mcp_toggle(server_id: str, enable: bool, cfg: dict[str, Any] | None) -> None:
    cfg_file = _codex_home() / "config.toml"
    cfg_file.parent.mkdir(parents=True, exist_ok=True)
    text = cfg_file.read_text(encoding="utf-8") if cfg_file.is_file() else ""
    text = _strip_toml_mcp_server(text, server_id)
    if enable and cfg:
        if text and not text.endswith("\n"):
            text += "\n"
        if text.strip():
            text += "\n"
        text += _render_codex_mcp_block(server_id, cfg)
    cfg_file.write_text(text, encoding="utf-8")


def scan_mcp_servers() -> list[dict[str, Any]]:
    """Scans local workspace MCP servers and inspects their configuration across Claude, Antigravity, and Cursor."""
    agy_global_file = HOME / ".gemini/config/mcp_config.json"
    claude_desktop_file = HOME / "Library/Application Support/Claude/claude_desktop_config.json"
    claude_code_file = HOME / ".claude.json"
    workspace_mcp_file = WORKSPACE / ".mcp.json"
    cursor_global_file = HOME / ".cursor/mcp.json"
    cursor_workspace_file = WORKSPACE / ".cursor/mcp.json"
    codex_global_file = _codex_home() / "config.toml"
    codex_workspace_file = WORKSPACE / ".codex/config.toml"

    agy_mcps = {}
    if agy_global_file.is_file():
        try:
            with open(agy_global_file) as f:
                agy_mcps = json.load(f).get("mcpServers", {})
        except Exception:
            pass

    claude_desktop_mcps = {}
    if claude_desktop_file.is_file():
        try:
            with open(claude_desktop_file) as f:
                claude_desktop_mcps = json.load(f).get("mcpServers", {})
        except Exception:
            pass

    claude_code_mcps = {}
    if claude_code_file.is_file():
        try:
            with open(claude_code_file) as f:
                claude_code_mcps = json.load(f).get("mcpServers", {})
        except Exception:
            pass

    workspace_mcps = {}
    if workspace_mcp_file.is_file():
        try:
            with open(workspace_mcp_file) as f:
                workspace_mcps = json.load(f).get("mcpServers", {})
        except Exception:
            pass

    cursor_mcps = {}
    if cursor_global_file.is_file():
        try:
            with open(cursor_global_file) as f:
                cursor_mcps.update(json.load(f).get("mcpServers", {}))
        except Exception:
            pass
    if cursor_workspace_file.is_file():
        try:
            with open(cursor_workspace_file) as f:
                cursor_mcps.update(json.load(f).get("mcpServers", {}))
        except Exception:
            pass

    codex_mcps = _load_codex_mcp_servers()

    mcps: dict[str, dict[str, Any]] = {}
    local_mcps_dir = WORKSPACE / "ai-first-fw/local-mcps"

    # 1. Scan Local Repository MCP Servers
    if local_mcps_dir.is_dir():
        for d in sorted(local_mcps_dir.iterdir()):
            if d.is_dir() and not d.name.startswith("."):
                server_py = d / "server.py"
                launch_sh = d / "launch.sh"
                env_file = d / ".env"
                env_sample_file = d / ".env.sample"
                venv_dir = d / ".venv"

                desc = ""
                tools = []
                if server_py.is_file():
                    try:
                        content = server_py.read_text(encoding="utf-8", errors="replace")
                        doc_m = re.search(r'\"\"\"(.*?)\"\"\"', content, re.DOTALL)
                        if doc_m:
                            desc = doc_m.group(1).strip().splitlines()[0]
                        tools = re.findall(r"@mcp\.tool\(\)\s*\ndef\s+([a-zA-Z0-9_]+)", content)
                        if not tools:
                            tools = re.findall(r'"name":\s*"(jira_[a-zA-Z0-9_]+|kibana_[a-zA-Z0-9_]+|[a-zA-Z0-9_]+)"', content)
                        if not tools:
                            tools = [fn for fn in re.findall(r"def\s+([a-zA-Z0-9_]+)\(", content) if not fn.startswith("_")]
                    except Exception:
                        pass

                # Preferred launcher strategy: launch.sh (self-healing) > .venv python > python3
                if launch_sh.is_file():
                    python_cmd = "bash"
                    exec_target = str(launch_sh)
                elif (venv_dir / "bin/python3").is_file():
                    python_cmd = str(venv_dir / "bin/python3")
                    exec_target = str(server_py)
                else:
                    python_cmd = "python3"
                    exec_target = str(server_py) if server_py.is_file() else None

                has_env = env_file.is_file()
                env_status = "missing"
                if has_env:
                    try:
                        env_text = env_file.read_text(encoding="utf-8", errors="replace")
                        if "your_" in env_text.lower() or "<placeholder>" in env_text.lower():
                            env_status = "sample_unconfigured"
                        else:
                            env_status = "configured"
                    except Exception:
                        env_status = "configured"
                elif env_sample_file.is_file():
                    env_status = "sample_available"

                mcps[d.name] = {
                    "id": d.name,
                    "name": d.name,
                    "title": f"{d.name.upper()} MCP Server",
                    "description": desc or f"Local {d.name} Model Context Protocol server",
                    "local_path": str(d),
                    "server_script": str(server_py) if server_py.is_file() else None,
                    "launcher_script": str(launch_sh) if launch_sh.is_file() else None,
                    "python_executable": python_cmd,
                    "exec_target": exec_target,
                    "is_local": True,
                    "has_venv": venv_dir.is_dir(),
                    "has_env": has_env,
                    "env_status": env_status,
                    "tools": tools,
                    "tools_count": len(tools),
                    "ecosystems": {
                        "antigravity": {
                            "configured": d.name in agy_mcps,
                            "config_path": str(agy_global_file),
                            "details": agy_mcps.get(d.name)
                        },
                        "claude_desktop": {
                            "configured": d.name in claude_desktop_mcps,
                            "config_path": str(claude_desktop_file),
                            "details": claude_desktop_mcps.get(d.name)
                        },
                        "claude_code": {
                            "configured": (d.name in claude_code_mcps) or (f"{d.name}-local" in claude_code_mcps) or (d.name in workspace_mcps),
                            "config_path": str(claude_code_file),
                            "details": claude_code_mcps.get(d.name) or claude_code_mcps.get(f"{d.name}-local") or workspace_mcps.get(d.name)
                        },
                        "cursor": {
                            "configured": (d.name in cursor_mcps) or (f"{d.name}-local" in cursor_mcps) or any(d.name in k for k in cursor_mcps),
                            "config_path": str(cursor_workspace_file if cursor_workspace_file.is_file() else cursor_global_file),
                            "details": cursor_mcps.get(d.name) or cursor_mcps.get(f"{d.name}-local") or next((v for k, v in cursor_mcps.items() if d.name in k), None)
                        },
                        "codex": {
                            "configured": _codex_mcp_lookup(d.name, codex_mcps)[0],
                            "config_path": str(codex_global_file if Path(codex_global_file).is_file() else codex_workspace_file),
                            "details": _codex_mcp_lookup(d.name, codex_mcps)[1]
                        },
                        "workspace": {
                            "configured": d.name in workspace_mcps,
                            "config_path": str(workspace_mcp_file),
                            "details": workspace_mcps.get(d.name)
                        }
                    }
                }

    # 2. Scan External / IDE MCP Servers
    all_external: dict[str, dict[str, Any]] = {}
    for name, cfg in agy_mcps.items():
        if name not in mcps:
            all_external.setdefault(name, {})["antigravity"] = cfg
    for name, cfg in claude_desktop_mcps.items():
        clean_name = name.replace("-local", "")
        if clean_name not in mcps:
            all_external.setdefault(clean_name, {})["claude_desktop"] = cfg
    for name, cfg in claude_code_mcps.items():
        clean_name = name.replace("-local", "")
        if clean_name not in mcps:
            all_external.setdefault(clean_name, {})["claude_code"] = cfg
    for name, cfg in workspace_mcps.items():
        clean_name = name.replace("-local", "")
        if clean_name not in mcps:
            all_external.setdefault(clean_name, {})["workspace"] = cfg
    for name, cfg in cursor_mcps.items():
        clean_name = name.replace("-local", "")
        if clean_name not in mcps:
            all_external.setdefault(clean_name, {})["cursor"] = cfg
    for name, cfg in codex_mcps.items():
        clean_name = name.replace("-local", "")
        if clean_name not in mcps:
            all_external.setdefault(clean_name, {})["codex"] = cfg

    for name, sources in all_external.items():
        if name.lower() == "idea":
            title = "IntelliJ IDEA MCP"
            desc = "JetBrains IntelliJ IDEA Model Context Protocol bridge for editor inspection, symbol navigation, and workspace actions."
        else:
            title = f"{name.title()} MCP"
            desc = f"External {name} Model Context Protocol integration bridge."

        mcps[name] = {
            "id": name,
            "name": name,
            "title": title,
            "description": desc,
            "local_path": None,
            "server_script": None,
            "launcher_script": None,
            "python_executable": None,
            "exec_target": None,
            "is_local": False,
            "has_venv": False,
            "has_env": False,
            "env_status": "not_applicable",
            "tools": [],
            "tools_count": 0,
            "ecosystems": {
                "antigravity": {
                    "configured": "antigravity" in sources,
                    "config_path": str(agy_global_file),
                    "details": sources.get("antigravity")
                },
                "claude_desktop": {
                    "configured": "claude_desktop" in sources,
                    "config_path": str(claude_desktop_file),
                    "details": sources.get("claude_desktop")
                },
                "claude_code": {
                    "configured": ("claude_code" in sources) or ("workspace" in sources),
                    "config_path": str(claude_code_file),
                    "details": sources.get("claude_code") or sources.get("workspace")
                },
                "cursor": {
                    "configured": "cursor" in sources,
                    "config_path": str(cursor_workspace_file if cursor_workspace_file.is_file() else cursor_global_file),
                    "details": sources.get("cursor")
                },
                "codex": {
                    "configured": ("codex" in sources) and not (
                        isinstance(sources.get("codex"), dict) and sources.get("codex", {}).get("enabled") is False
                    ),
                    "config_path": str(codex_global_file if Path(codex_global_file).is_file() else codex_workspace_file),
                    "details": sources.get("codex")
                },
                "workspace": {
                    "configured": "workspace" in sources,
                    "config_path": str(workspace_mcp_file),
                    "details": sources.get("workspace")
                }
            }
        }

    return list(mcps.values())


def toggle_mcp_target(server_id: str, target: str, enable: bool) -> dict[str, Any]:
    """Toggles configuration of a local or external MCP server in Antigravity, Claude Desktop, Claude Code, Cursor, or Codex."""
    local_mcps_dir = WORKSPACE / "ai-first-fw/local-mcps"
    server_dir = local_mcps_dir / server_id
    server_py = server_dir / "server.py"
    launch_sh = server_dir / "launch.sh"
    venv_python = server_dir / ".venv/bin/python3"
    workspace_mcp_file = WORKSPACE / ".mcp.json"

    is_local = server_py.is_file()

    # Determine optimal launcher: launch.sh self-heals virtualenv & requirements
    if launch_sh.is_file():
        cmd = "bash"
        args = [str(launch_sh)]
    elif venv_python.is_file():
        cmd = str(venv_python)
        args = [str(server_py)]
    else:
        cmd = "python3"
        args = [str(server_py)]

    # Known external server templates
    known_external = {
        "idea": {
            "antigravity": {"url": "http://127.0.0.1:64342/stream"},
            "claude_desktop": {"url": "http://127.0.0.1:64342/stream", "type": "http"},
            "claude_code": {"url": "http://127.0.0.1:64342/stream", "type": "http"},
            "cursor": {"url": "http://127.0.0.1:64342/stream"},
            "codex": {"url": "http://127.0.0.1:64342/stream"},
        }
    }

    if not is_local and server_id not in known_external and enable:
        raise FileNotFoundError(f"MCP server '{server_id}' is not a recognized local or external MCP server.")

    if target == "antigravity":
        cfg_file = HOME / ".gemini/config/mcp_config.json"
        cfg = {}
        if cfg_file.is_file():
            try:
                with open(cfg_file) as f:
                    cfg = json.load(f)
            except Exception:
                pass
        servers = cfg.setdefault("mcpServers", {})
        if enable:
            if is_local:
                servers[server_id] = {
                    "command": cmd,
                    "args": args
                }
            else:
                servers[server_id] = known_external.get(server_id, {}).get("antigravity", {"url": "http://127.0.0.1:64342/stream"})
        else:
            servers.pop(server_id, None)
            servers.pop(f"{server_id}-local", None)
        cfg_file.parent.mkdir(parents=True, exist_ok=True)
        cfg_file.write_text(json.dumps(cfg, indent=4), encoding="utf-8")

    elif target == "claude_desktop":
        desktop_cfg_files = [
            HOME / "Library/Application Support/Claude/claude_desktop_config.json",
            HOME / "Library/Application Support/Claude-Clone/claude_desktop_config.json",
            HOME / "Library/Application Support/Claude-One/claude_desktop_config.json",
        ]
        for cfg_file in desktop_cfg_files:
            if not cfg_file.parent.is_dir() and (cfg_file.name.startswith("Claude-Clone") or cfg_file.name.startswith("Claude-One")):
                continue
            cfg = {}
            if cfg_file.is_file():
                try:
                    with open(cfg_file) as f:
                        cfg = json.load(f)
                except Exception:
                    pass
            servers = cfg.setdefault("mcpServers", {})
            if enable:
                if is_local:
                    servers[server_id] = {
                        "command": cmd,
                        "args": args
                    }
                else:
                    servers[server_id] = known_external.get(server_id, {}).get("claude_desktop", {"url": "http://127.0.0.1:64342/stream", "type": "http"})
            else:
                servers.pop(server_id, None)
                servers.pop(f"{server_id}-local", None)
            cfg_file.parent.mkdir(parents=True, exist_ok=True)
            cfg_file.write_text(json.dumps(cfg, indent=2), encoding="utf-8")

    elif target == "claude_code":
        # 1. Update ~/.claude.json and ~/.claude-clone/.claude.json
        code_cfg_files = [HOME / ".claude.json", HOME / ".claude-clone/.claude.json"]
        for cfg_file in code_cfg_files:
            if not cfg_file.parent.is_dir() and ".claude-clone" in str(cfg_file):
                continue
            cfg = {}
            if cfg_file.is_file():
                try:
                    with open(cfg_file) as f:
                        cfg = json.load(f)
                except Exception:
                    pass
            servers = cfg.setdefault("mcpServers", {})
            if enable:
                if is_local:
                    servers[server_id] = {
                        "type": "stdio",
                        "command": cmd,
                        "args": args,
                        "env": {}
                    }
                else:
                    servers[server_id] = known_external.get(server_id, {}).get("claude_code", {"url": "http://127.0.0.1:64342/stream", "type": "http"})
            else:
                servers.pop(server_id, None)
                servers.pop(f"{server_id}-local", None)
            cfg_file.parent.mkdir(parents=True, exist_ok=True)
            cfg_file.write_text(json.dumps(cfg, indent=2), encoding="utf-8")

        # 2. Also keep workspace .mcp.json synchronized
        if is_local:
            ws_cfg = {}
            if workspace_mcp_file.is_file():
                try:
                    with open(workspace_mcp_file) as f:
                        ws_cfg = json.load(f)
                except Exception:
                    pass
            ws_servers = ws_cfg.setdefault("mcpServers", {})
            if enable:
                ws_servers[server_id] = {
                    "command": cmd,
                    "args": args
                }
            else:
                ws_servers.pop(server_id, None)
                ws_servers.pop(f"{server_id}-local", None)
            workspace_mcp_file.write_text(json.dumps(ws_cfg, indent=2) + "\n", encoding="utf-8")

    elif target == "cursor":
        cursor_cfg_files = [
            HOME / ".cursor/mcp.json",
            WORKSPACE / ".cursor/mcp.json",
        ]
        for cfg_file in cursor_cfg_files:
            cfg_file.parent.mkdir(parents=True, exist_ok=True)
            cfg = {}
            if cfg_file.is_file():
                try:
                    with open(cfg_file) as f:
                        cfg = json.load(f)
                except Exception:
                    pass
            servers = cfg.setdefault("mcpServers", {})
            if enable:
                if is_local:
                    servers[server_id] = {
                        "command": cmd,
                        "args": args
                    }
                else:
                    servers[server_id] = known_external.get(server_id, {}).get("cursor", {"url": "http://127.0.0.1:64342/stream"})
            else:
                servers.pop(server_id, None)
                servers.pop(f"{server_id}-local", None)
                for k in list(servers.keys()):
                    if k == server_id or k.startswith(f"{server_id}-"):
                        servers.pop(k, None)
            cfg_file.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")

    elif target == "codex":
        if enable:
            if is_local:
                mcp_cfg = {"command": cmd, "args": args}
            else:
                mcp_cfg = known_external.get(server_id, {}).get("codex", {"url": "http://127.0.0.1:64342/stream"})
            _write_codex_mcp_toggle(server_id, True, mcp_cfg)
        else:
            _write_codex_mcp_toggle(server_id, False, None)

    elif target == "workspace":
        if not is_local and enable:
            raise ValueError(f"External MCP server '{server_id}' cannot be added to workspace .mcp.json directly.")
        ws_cfg = {}
        if workspace_mcp_file.is_file():
            try:
                with open(workspace_mcp_file) as f:
                    ws_cfg = json.load(f)
            except Exception:
                pass
        ws_servers = ws_cfg.setdefault("mcpServers", {})
        if enable:
            ws_servers[server_id] = {
                "command": cmd,
                "args": args
            }
        else:
            ws_servers.pop(server_id, None)
            ws_servers.pop(f"{server_id}-local", None)
        workspace_mcp_file.write_text(json.dumps(ws_cfg, indent=2) + "\n", encoding="utf-8")

    else:
        raise ValueError(f"Unknown target ecosystem: {target}")

    return {
        "success": True,
        "server_id": server_id,
        "target": target,
        "enabled": enable,
        "message": f"MCP server '{server_id}' successfully {'added to' if enable else 'removed from'} {target}."
    }


# ==============================================================================
# Master Scanner
# ==============================================================================

def scan_all() -> dict[str, Any]:
    """Runs a full scan across Claude, Antigravity, Cursor, and Codex ecosystems, master registry, and MCP servers."""
    # 1. Claude
    claude_cli_skills = scan_claude_cli_skills()
    claude_cli_plugins = scan_claude_cli_plugins()
    claude_cowork_plugins, claude_cowork_skills, claude_cowork_meta = scan_claude_app_cowork()
    claude_code_meta = scan_claude_app_code()
    marketplaces = scan_marketplaces()

    # 2. Antigravity
    agy_cli_skills = scan_antigravity_cli_skills()
    agy_cli_plugins = scan_antigravity_cli_plugins()
    agy_app_skills = scan_antigravity_app_skills()
    agy_ide_skills = scan_antigravity_ide_skills()

    # 3. Cursor
    cursor_skills = scan_cursor_skills()
    cursor_rules = scan_cursor_rules()
    cursor_plugins = scan_cursor_plugins()

    # 4. Codex
    codex_skills = scan_codex_skills()
    codex_rules = scan_codex_agents_md()
    codex_plugins = scan_codex_plugins()

    # 5. Master Alphabetical Registry
    all_skills_alphabetical = scan_all_skills_alphabetical()

    # 6. MCP Servers
    mcp_servers = scan_mcp_servers()

    # Aggregate counts
    all_claude_skills = claude_cli_skills + claude_cowork_skills + [s for p in (claude_cli_plugins + claude_cowork_plugins) for s in p.skills]
    all_agy_skills = agy_cli_skills + agy_app_skills + agy_ide_skills + [s for p in agy_cli_plugins for s in p.skills]
    all_cursor_items = cursor_skills + cursor_rules + [s for p in cursor_plugins for s in p.skills]
    all_codex_items = codex_skills + codex_rules + [s for p in codex_plugins for s in p.skills]
    
    total_skills = len(all_claude_skills) + len(all_agy_skills) + len(all_cursor_items) + len(all_codex_items)
    total_plugins = len(claude_cli_plugins) + len(claude_cowork_plugins) + len(agy_cli_plugins) + len(cursor_plugins) + len(codex_plugins)

    local_count = 0
    marketplace_count = 0
    builtin_count = 0

    for s in (all_claude_skills + all_agy_skills + all_cursor_items + all_codex_items):
        if "marketplace" in s.source_type or "github" in s.source_type or "desktop_extension" in s.source_type:
            marketplace_count += 1
        elif "builtin" in s.source_type:
            builtin_count += 1
        else:
            local_count += 1

    for p in (claude_cli_plugins + claude_cowork_plugins + agy_cli_plugins + cursor_plugins + codex_plugins):
        if "marketplace" in p.source_type or "github" in p.source_type or "desktop_extension" in p.source_type:
            marketplace_count += 1
        elif "builtin" in p.source_type:
            builtin_count += 1
        else:
            local_count += 1

    codex_home = _codex_home()
    try:
        codex_cli_present = shutil.which("codex") is not None
    except Exception:
        codex_cli_present = False

    return {
        "scan_time": datetime.now().isoformat(),
        "summary": {
            "total_skills": total_skills,
            "total_plugins": total_plugins,
            "unique_skills_count": len(all_skills_alphabetical),
            "claude_skills_count": len(all_claude_skills),
            "claude_plugins_count": len(claude_cli_plugins) + len(claude_cowork_plugins),
            "antigravity_skills_count": len(all_agy_skills),
            "antigravity_plugins_count": len(agy_cli_plugins),
            "cursor_skills_count": len(cursor_skills),
            "cursor_rules_count": len(cursor_rules),
            "cursor_plugins_count": len(cursor_plugins),
            "codex_skills_count": len(codex_skills),
            "codex_rules_count": len(codex_rules),
            "codex_plugins_count": len(codex_plugins),
            "mcp_servers_count": len(mcp_servers),
            "local_count": local_count,
            "marketplace_count": marketplace_count,
            "builtin_count": builtin_count,
        },
        "all_skills_alphabetical": all_skills_alphabetical,
        "mcp_servers": mcp_servers,
        "claude": {
            "cli": {
                "skills": [asdict(s) for s in claude_cli_skills],
                "plugins": [asdict(p) for p in claude_cli_plugins],
            },
            "app_cowork": {
                "plugins": [asdict(p) for p in claude_cowork_plugins],
                "skills": [asdict(s) for s in claude_cowork_skills],
                "metadata": claude_cowork_meta,
            },
            "app_code": {
                "metadata": claude_code_meta,
            },
        },
        "antigravity": {
            "cli": {
                "skills": [asdict(s) for s in agy_cli_skills],
                "plugins": [asdict(p) for p in agy_cli_plugins],
            },
            "app": {
                "plugins": [asdict(p) for p in agy_cli_plugins],
                "skills": [asdict(s) for s in agy_app_skills],
            },
            "ide": {
                "plugins": [asdict(p) for p in agy_cli_plugins],
                "skills": [asdict(s) for s in agy_ide_skills],
            },
        },
        "cursor": {
            "skills": [asdict(s) for s in cursor_skills],
            "rules": [asdict(s) for s in cursor_rules],
            "plugins": [asdict(p) for p in cursor_plugins],
            "metadata": {
                "installed": os.path.isdir("/Applications/Cursor.app") or (HOME / ".cursor").is_dir(),
                "app_path": "/Applications/Cursor.app" if os.path.isdir("/Applications/Cursor.app") else None,
                "config_path": str(HOME / ".cursor"),
                "workspace_rules_path": str(WORKSPACE / ".cursor/rules") if (WORKSPACE / ".cursor/rules").is_dir() else None,
                "workspace_mcp_path": str(WORKSPACE / ".cursor/mcp.json") if (WORKSPACE / ".cursor/mcp.json").is_file() else None,
            }
        },
        "codex": {
            "skills": [asdict(s) for s in codex_skills],
            "rules": [asdict(s) for s in codex_rules],
            "plugins": [asdict(p) for p in codex_plugins],
            "metadata": {
                "installed": codex_home.is_dir() or codex_cli_present,
                "cli_present": codex_cli_present,
                "config_path": str(codex_home),
                "config_toml": str(codex_home / "config.toml") if (codex_home / "config.toml").is_file() else None,
                "skills_path": str(codex_home / "skills") if (codex_home / "skills").is_dir() else None,
                "plugins_path": str(codex_home / "plugins") if (codex_home / "plugins").is_dir() else None,
                "workspace_agents_md": str(WORKSPACE / "AGENTS.md") if (WORKSPACE / "AGENTS.md").is_file() else None,
            }
        },
        "marketplaces": marketplaces,
    }


if __name__ == "__main__":
    data = scan_all()
    print(f"Scanned {data['summary']['total_skills']} skills across surfaces.")
    print(f"Scanned {len(data['mcp_servers'])} MCP servers.")
    print(f"Found {len(data['all_skills_alphabetical'])} unique skills for Master Index.")
