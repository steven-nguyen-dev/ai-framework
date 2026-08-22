#!/usr/bin/env python3
"""Scanner and Extension Manager for AI Agent Skills & Plugins on macOS.

Discovers and inspects all skills, plugins, and extensions across:
1. Claude (CLI, Claude App Cowork, Claude App Code)
2. Antigravity (CLI, App, IDE)
3. Master Alphabetical Skills Registry & Installation Matrix

Provides install & uninstall management across target agent surfaces.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

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


@dataclass
class SkillItem:
    id: str
    name: str
    description: str
    section: str  # "claude" | "antigravity"
    subsection: str  # "cli" | "app_cowork" | "app_code" | "app" | "ide"
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
    section: str  # "claude" | "antigravity"
    subsection: str  # "cli" | "app_cowork" | "app_code" | "app" | "ide"
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
    if path.is_symlink():
        try:
            resolved = str(path.resolve())
            return "local_symlink", "Local (Symlink)", resolved
        except Exception:
            return "local_symlink", "Local (Broken Symlink)", None
    elif str(WORKSPACE) in str(path) and WORKSPACE != HOME:
        return "local_workspace", "Local (Workspace)", str(path)
    else:
        return "local_user", "Local (User / Personal)", str(path)


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
# 3. Master Alphabetical Skills Registry & Installation Matrix
# ==============================================================================

def scan_all_skills_alphabetical() -> list[dict[str, Any]]:
    """Gathers all unique skills generically across installed plugins, registered marketplaces, built-ins, and local agents.
    
    Returns an alphabetically sorted list focused on repository links and plugin origins.
    """
    skills_map: dict[str, dict[str, Any]] = {}

    # Target keys for matrix: claude, agy, agy-ide, agy-cli
    active_target_defs = [
        {"key": "claude", "label": "Claude CLI", "skills_dir": HOME / ".claude/skills"},
        {"key": "agy", "label": "Antigravity App", "skills_dir": HOME / ".gemini/config/skills"},
        {"key": "agy-ide", "label": "Antigravity IDE", "skills_dir": HOME / ".gemini/antigravity/skills"},
        {"key": "agy-cli", "label": "Antigravity CLI", "skills_dir": HOME / ".gemini/antigravity-cli/skills"},
    ]

    # 1. Discovered from Installed Plugins (Claude Code, Cowork, Antigravity/Gemini)
    all_plugins = [
        *scan_claude_cli_plugins(),
        *scan_antigravity_cli_plugins(),
    ]
    cowork_plugins, _, _ = scan_claude_app_cowork()
    all_plugins.extend(cowork_plugins)

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

            is_symlink = dest.is_symlink()
            is_file = dest.is_file()
            is_dir = dest.is_dir()
            target_link = str(dest.resolve()) if is_symlink else None

            is_installed = is_symlink or is_file or is_dir
            if is_installed:
                installed_count += 1

            skill_entry["targets"][t_key] = {
                "target_name": t["label"],
                "installed": is_installed,
                "is_symlink": is_symlink,
                "link_dest": target_link,
                "path": str(dest),
            }

        skill_entry["installed_count"] = installed_count
        skill_entry["total_targets"] = total_targets
        skill_entry["is_all_installed"] = (installed_count == total_targets)

    # Sort alphabetically by skill name
    return sorted(skills_map.values(), key=lambda x: x["name"].lower())


# ==============================================================================
# 4. Install & Uninstall Management Engine
# ==============================================================================

def install_skill_to_targets(skill_name: str, target_keys: list[str] | None = None, force: bool = True) -> dict[str, Any]:
    """Installs/symlinks a skill from known plugin/workspace sources to target agent directories."""
    src: Path | None = None

    # Search in all discovered plugins
    for p in [*scan_claude_cli_plugins(), *scan_antigravity_cli_plugins()]:
        for s in p.skills:
            if s.name == skill_name:
                cand = Path(s.path)
                src = cand.parent if cand.is_file() else cand
                break
        if src:
            break

    # Search in workspace
    if not src:
        for ws_dir in [WORKSPACE / ".agents/skills" / skill_name, WORKSPACE / ".claude/skills" / skill_name, WORKSPACE / ".gemini/skills" / skill_name]:
            if ws_dir.is_dir() and (ws_dir / "SKILL.md").is_file():
                src = ws_dir
                break

    if not src:
        return {"success": False, "message": f"Skill source folder for '{skill_name}' not found."}

    results = []
    target_list = [t for t in TARGETS if (not target_keys or t.key in target_keys or "all" in target_keys)]
    
    for t in target_list:
        if not t.skills_dir.parent.is_dir() and not t.creatable:
            continue
        t.skills_dir.mkdir(parents=True, exist_ok=True)
        dest = t.skills_dir / skill_name
        
        # If dest exists
        if dest.is_symlink() or dest.exists():
            if dest.is_symlink():
                dest.unlink()
            elif force:
                back_up(dest, t.key)
            else:
                results.append({"target": t.key, "status": "skipped", "message": "Real file exists (use force)"})
                continue
                
        # Create atomic symlink
        tmp = dest.with_name(f".{skill_name}.installing-{os.getpid()}")
        if tmp.is_symlink() or tmp.exists():
            tmp.unlink()
        tmp.symlink_to(src, target_is_directory=True)
        os.replace(tmp, dest)
        results.append({"target": t.key, "status": "installed", "path": str(dest)})

    return {"success": True, "skill": skill_name, "results": results}


def uninstall_skill_from_targets(skill_name: str, target_keys: list[str] | None = None, force: bool = True) -> dict[str, Any]:
    """Uninstalls a skill from target agent directories (unlinks symlinks, backups real dirs)."""
    results = []
    target_list = [t for t in TARGETS if (not target_keys or t.key in target_keys or "all" in target_keys)]

    for t in target_list:
        dest = t.skills_dir / skill_name
        if not dest.is_symlink() and not dest.exists():
            continue

        if dest.is_symlink():
            dest.unlink()
            results.append({"target": t.key, "status": "removed", "path": str(dest)})
        elif force:
            moved = back_up(dest, t.key)
            results.append({"target": t.key, "status": "backed_up", "path": str(moved)})
        else:
            results.append({"target": t.key, "status": "skipped", "message": "Real directory (pass force)"})

    return {"success": True, "skill": skill_name, "results": results}


def install_all_canonical_skills() -> dict[str, Any]:
    """Installs all AI-First FW & Utility skills to all available agent surfaces."""
    installed = []
    for source in SOURCES:
        for skill_dir in source.skills():
            res = install_skill_to_targets(skill_dir.name, target_keys=["all"], force=True)
            installed.append(res)
    return {"success": True, "count": len(installed), "details": installed}


def uninstall_all_canonical_skills() -> dict[str, Any]:
    """Uninstalls all AI-First FW & Utility skills from all surfaces."""
    uninstalled = []
    for source in SOURCES:
        for skill_dir in source.skills():
            res = uninstall_skill_from_targets(skill_dir.name, target_keys=["all"], force=True)
            uninstalled.append(res)
    return {"success": True, "count": len(uninstalled), "details": uninstalled}


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
    installed_file = HOME / ".claude/plugins/installed_plugins.json"
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
    ext_file = HOME / "Library/Application Support/Claude/extensions-installations.json"
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


# ==============================================================================
# MCP Servers Scanner & Manager
# ==============================================================================

def scan_mcp_servers() -> list[dict[str, Any]]:
    """Scans local workspace MCP servers and inspects their configuration across Claude & Antigravity."""
    agy_global_file = HOME / ".gemini/config/mcp_config.json"
    claude_desktop_file = HOME / "Library/Application Support/Claude/claude_desktop_config.json"
    claude_code_file = HOME / ".claude.json"

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

    mcps: dict[str, dict[str, Any]] = {}
    local_mcps_dir = WORKSPACE / "ai-first-fw/local-mcps"

    # 1. Scan Local Repository MCP Servers
    if local_mcps_dir.is_dir():
        for d in sorted(local_mcps_dir.iterdir()):
            if d.is_dir() and not d.name.startswith("."):
                server_py = d / "server.py"
                env_file = d / ".env"
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
                            tools = re.findall(r"def\s+([a-zA-Z0-9_]+)\(", content)
                    except Exception:
                        pass

                python_cmd = str(venv_dir / "bin/python3") if (venv_dir / "bin/python3").is_file() else "/Users/nguyennguyen.anchanto/Projects/ai-framework/ai-first-fw/local-mcps/jira/.venv/bin/python3"

                mcps[d.name] = {
                    "id": d.name,
                    "name": d.name,
                    "title": f"{d.name.upper()} MCP Server",
                    "description": desc or f"Local {d.name} Model Context Protocol server",
                    "local_path": str(d),
                    "server_script": str(server_py) if server_py.is_file() else None,
                    "python_executable": python_cmd,
                    "is_local": True,
                    "has_venv": venv_dir.is_dir(),
                    "has_env": env_file.is_file(),
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
                            "configured": (d.name in claude_code_mcps) or (f"{d.name}-local" in claude_code_mcps),
                            "config_path": str(claude_code_file),
                            "details": claude_code_mcps.get(d.name) or claude_code_mcps.get(f"{d.name}-local")
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
            "python_executable": None,
            "is_local": False,
            "has_venv": False,
            "has_env": False,
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
                    "configured": "claude_code" in sources,
                    "config_path": str(claude_code_file),
                    "details": sources.get("claude_code")
                }
            }
        }

    return list(mcps.values())


def toggle_mcp_target(server_id: str, target: str, enable: bool) -> dict[str, Any]:
    """Toggles configuration of a local or external MCP server in Antigravity, Claude Desktop, or Claude Code."""
    local_mcps_dir = WORKSPACE / "ai-first-fw/local-mcps"
    server_dir = local_mcps_dir / server_id
    server_py = server_dir / "server.py"
    venv_python = server_dir / ".venv/bin/python3"
    python_cmd = str(venv_python) if venv_python.is_file() else "/Users/nguyennguyen.anchanto/Projects/ai-framework/ai-first-fw/local-mcps/jira/.venv/bin/python3"

    is_local = server_py.is_file()

    # Known external server templates
    known_external = {
        "idea": {
            "antigravity": {"url": "http://127.0.0.1:64342/stream"},
            "claude_desktop": {"url": "http://127.0.0.1:64342/stream", "type": "http"},
            "claude_code": {"url": "http://127.0.0.1:64342/stream", "type": "http"},
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
                    "command": python_cmd,
                    "args": [str(server_py)]
                }
            else:
                servers[server_id] = known_external.get(server_id, {}).get("antigravity", {"url": "http://127.0.0.1:64342/stream"})
        else:
            servers.pop(server_id, None)
            servers.pop(f"{server_id}-local", None)
        cfg_file.parent.mkdir(parents=True, exist_ok=True)
        cfg_file.write_text(json.dumps(cfg, indent=4), encoding="utf-8")

    elif target == "claude_desktop":
        cfg_file = HOME / "Library/Application Support/Claude/claude_desktop_config.json"
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
                    "command": python_cmd,
                    "args": [str(server_py)]
                }
            else:
                servers[server_id] = known_external.get(server_id, {}).get("claude_desktop", {"url": "http://127.0.0.1:64342/stream", "type": "http"})
        else:
            servers.pop(server_id, None)
            servers.pop(f"{server_id}-local", None)
        cfg_file.parent.mkdir(parents=True, exist_ok=True)
        cfg_file.write_text(json.dumps(cfg, indent=2), encoding="utf-8")

    elif target == "claude_code":
        cfg_file = HOME / ".claude.json"
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
                    "command": python_cmd,
                    "args": [str(server_py)],
                    "env": {}
                }
            else:
                servers[server_id] = known_external.get(server_id, {}).get("claude_code", {"url": "http://127.0.0.1:64342/stream", "type": "http"})
        else:
            servers.pop(server_id, None)
            servers.pop(f"{server_id}-local", None)
        cfg_file.parent.mkdir(parents=True, exist_ok=True)
        cfg_file.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
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
    """Runs a full scan across Claude and Antigravity ecosystems, master registry, and MCP servers."""
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

    # 3. Master Alphabetical Registry
    all_skills_alphabetical = scan_all_skills_alphabetical()

    # 4. MCP Servers
    mcp_servers = scan_mcp_servers()

    # Aggregate counts
    all_claude_skills = claude_cli_skills + claude_cowork_skills + [s for p in claude_cli_plugins for s in p.skills]
    all_agy_skills = agy_cli_skills + agy_app_skills + agy_ide_skills + [s for p in agy_cli_plugins for s in p.skills]
    
    total_skills = len(all_claude_skills) + len(all_agy_skills)
    total_plugins = len(claude_cli_plugins) + len(claude_cowork_plugins) + len(agy_cli_plugins)

    local_count = 0
    marketplace_count = 0
    builtin_count = 0

    for s in (all_claude_skills + all_agy_skills):
        if "marketplace" in s.source_type or "github" in s.source_type or "desktop_extension" in s.source_type:
            marketplace_count += 1
        elif "builtin" in s.source_type:
            builtin_count += 1
        else:
            local_count += 1

    for p in (claude_cli_plugins + claude_cowork_plugins + agy_cli_plugins):
        if "marketplace" in p.source_type or "github" in p.source_type or "desktop_extension" in p.source_type:
            marketplace_count += 1
        elif "builtin" in p.source_type:
            builtin_count += 1
        else:
            local_count += 1

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
        "marketplaces": marketplaces,
    }


if __name__ == "__main__":
    data = scan_all()
    print(f"Scanned {data['summary']['total_skills']} skills across surfaces.")
    print(f"Scanned {len(data['mcp_servers'])} MCP servers.")
    print(f"Found {len(data['all_skills_alphabetical'])} unique skills for Master Index.")
