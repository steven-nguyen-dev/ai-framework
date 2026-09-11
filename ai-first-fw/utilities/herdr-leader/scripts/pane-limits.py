#!/usr/bin/env python3
"""
herdr-pane-limits.py

Optimized, token-efficient capacity checker and pane namer for herdr.
- Confined strictly to the current tab ($HERDR_TAB_ID)
- Explicit model token limits:
  - Big pool (Gemini, Claude, GPT): 650k tokens (<650K)
  - Default (all other models & unknown): 210k tokens (<210K)
- Auto-names unnamed panes in the current tab as <model>-<number>
- Supports checking a single target (1 line) or all panes in the tab (compact table)

Usage:
  herdr-pane-limits.py          # compact summary of panes in current tab
  herdr-pane-limits.py <target> # single line check for one pane
"""

import json
import os
import re
import subprocess
import sys
import time

# Explicit token limits in thousands (K)
BIG_POOL_LIMIT_K = 650.0
BIG_POOL_HIGH_K = 550.0

DEFAULT_LIMIT_K = 210.0
DEFAULT_HIGH_K = 175.0

# Backwards compatibility aliases
CLAUDE_GEMINI_LIMIT_K = BIG_POOL_LIMIT_K
CLAUDE_GEMINI_HIGH_K = BIG_POOL_HIGH_K
GROK_UNKNOWN_LIMIT_K = DEFAULT_LIMIT_K
GROK_UNKNOWN_HIGH_K = DEFAULT_HIGH_K
GROK_GPT_UNKNOWN_LIMIT_K = DEFAULT_LIMIT_K
GROK_GPT_UNKNOWN_HIGH_K = DEFAULT_HIGH_K

def run_cmd(args):
    try:
        res = subprocess.run(args, capture_output=True, text=True, timeout=8)
        return res.stdout, res.stderr, res.returncode
    except Exception as e:
        return "", str(e), 1

def to_tokens_k(val_str):
    if not val_str:
        return None
    s = val_str.strip().upper()
    if s.endswith("M"):
        try:
            return float(s[:-1]) * 1000.0
        except ValueError:
            return None
    elif s.endswith("K"):
        try:
            return float(s[:-1])
        except ValueError:
            return None
    else:
        try:
            return float(s) / 1000.0
        except ValueError:
            return None

def get_space_tag(tab_id=None, ws_id=None):
    """
    Extracts the 3 beginning letters of the Herdr workspace (space) name.
    e.g. "One" -> "one", "Zero" -> "zer", "Two" -> "two", "ai-framework" -> "aif".
    """
    if not ws_id and tab_id and ":" in tab_id:
        ws_id = tab_id.split(":")[0]
    if not ws_id:
        ws_id = os.environ.get("HERDR_WORKSPACE_ID")
    if not tab_id:
        tab_id = os.environ.get("HERDR_TAB_ID")

    out, _, rc = run_cmd(["herdr", "workspace", "list"])
    workspaces = []
    if rc == 0:
        try:
            workspaces = json.loads(out).get("result", {}).get("workspaces", [])
        except Exception:
            pass

    label = None
    if ws_id:
        for w in workspaces:
            if w.get("workspace_id") == ws_id:
                label = w.get("label") or w.get("name")
                break
    if not label:
        for w in workspaces:
            if (tab_id and w.get("active_tab_id") == tab_id) or w.get("focused"):
                label = w.get("label") or w.get("name")
                break
    if not label and workspaces:
        label = workspaces[0].get("label") or workspaces[0].get("name")

    clean = re.sub(r"[^a-zA-Z0-9]", "", label or ws_id or "spc").lower()
    if not clean or not clean[0].isalpha():
        clean = "s" + clean
    return clean[:3]

def get_model_target_limit(name, kind, tail_lines=""):
    """
    Determines explicit token target limit based on model:
    - Big pool (Gemini, Claude, GPT): 650k tokens (<650K)
    - Default (all others / Grok / Unknown): 210k tokens (<210K)
    Returns: (limit_tokens_k, limit_str, high_tokens_k)
    """
    combined = f"{name} {kind}".lower()
    if any(m in combined for m in ["gemini", "agy", "claude", "opus", "sonnet", "gpt", "codex"]):
        return BIG_POOL_LIMIT_K, "<650K", BIG_POOL_HIGH_K

    tail = tail_lines.lower()
    if any(m in tail for m in ["gemini", "agy", "claude", "opus", "sonnet", "gpt", "codex"]):
        return BIG_POOL_LIMIT_K, "<650K", BIG_POOL_HIGH_K

    return DEFAULT_LIMIT_K, "<210K", DEFAULT_HIGH_K

def parse_usage(text):
    """
    Parses usage from agent pane output.
    Returns: (usage_display_str, pct_float, used_k_float)
    """
    # 1. Main format: Main: 166.3K/1.00M (17%), Main: 0/1.05M tok (0%), or Main: 73.6K/1.00M (…
    m = re.search(r'Main:\s*([0-9.]+[KkMm]?)\s*/\s*([0-9.]+[KkMm]?)(?:[^\n0-9]*([0-9.]+)%)?', text)
    if m:
        u_str, t_str = m.group(1), m.group(2)
        u_k, t_k = to_tokens_k(u_str), to_tokens_k(t_str)
        if m.group(3):
            pct = float(m.group(3))
        elif u_k is not None and t_k:
            pct = round(u_k / t_k * 100.0, 1)
        else:
            pct = None
        pct_disp = f" ({pct:.0f}%)" if pct is not None else ""
        return f"{u_str}/{t_str}{pct_disp}", pct, u_k

    # 2. Codex / GPT formats:
    # "Context 0% used" or "Context: 15% used"
    m_codex_used = re.search(r'Context[:\s]+([0-9.]+)%\s*used', text, re.IGNORECASE)
    if m_codex_used:
        pct = float(m_codex_used.group(1))
        m_win = re.search(r'([0-9.]+[KkMm]?)\s*window', text, re.IGNORECASE)
        t_k = to_tokens_k(m_win.group(1)) if m_win else 1000.0
        u_k = (t_k * pct / 100.0) if t_k else None
        tot_disp = m_win.group(1) if m_win else "1.00M"
        return f"{u_k:.1f}K/{tot_disp} ({pct:.0f}%)", pct, u_k

    # "Context left: 68%"
    m_codex_left = re.search(r'Context left:\s*([0-9.]+)%', text, re.IGNORECASE)
    if m_codex_left:
        left_pct = float(m_codex_left.group(1))
        pct = 100.0 - left_pct
        m_win = re.search(r'([0-9.]+[KkMm]?)\s*window', text, re.IGNORECASE)
        t_k = to_tokens_k(m_win.group(1)) if m_win else 1000.0
        u_k = (t_k * pct / 100.0) if t_k else None
        tot_disp = m_win.group(1) if m_win else "1.00M"
        return f"{u_k:.1f}K/{tot_disp} ({pct:.0f}%)", pct, u_k

    # 3. Main format without total: Main: 150K (15%) or Main: (15%)
    m_pct = re.search(r'Main:[^(\n]+\(\s*([0-9.]+)%\s*\)', text)
    if m_pct:
        pct = float(m_pct.group(1))
        return f"{pct:.0f}%", pct, None

    # 4. Fallback for Cursor/Grok format: Cursor Grok 4.6 High · 38.4%
    m = re.search(r'Cursor\s+[^\n·]+·\s*([0-9.]+)%', text)
    if m:
        pct = float(m.group(1))
        u_k = 256.0 * (pct / 100.0)
        return f"{u_k:.1f}K/256K ({pct:.0f}%)", pct, u_k
    m_pct = re.search(r'·\s*([0-9.]+)%\s*·', text)
    if m_pct:
        pct = float(m_pct.group(1))
        u_k = 256.0 * (pct / 100.0)
        return f"{u_k:.1f}K/256K ({pct:.0f}%)", pct, u_k

    return "?", None, None

def detect_model(pane_info):
    """
    Detects the model running in a pane using Herdr metadata, terminal titles,
    and terminal buffer inspection.
    Returns: (prefix, display_name)
    """
    pane_id = pane_info.get("pane_id")
    agent_kind = (pane_info.get("agent") or "").lower()
    label = (pane_info.get("label") or "").lower()
    title = (pane_info.get("terminal_title") or "").lower()

    # 1. Direct Herdr agent kind match
    if "claude" in agent_kind:
        return "opus", "Claude"
    if "agy" in agent_kind or "gemini" in agent_kind:
        return "gemini", "Gemini"
    if "cursor" in agent_kind or "grok" in agent_kind:
        return "grok", "Grok"
    if "codex" in agent_kind or "gpt" in agent_kind:
        return "gpt", "GPT"

    # 2. Match from existing model in label
    for m in ["opus", "grok", "gpt", "gemini"]:
        if m in label:
            disp = {"opus": "Claude", "grok": "Grok", "gpt": "GPT", "gemini": "Gemini"}[m]
            return m, disp

    # 3. Terminal title match
    if any(k in title for k in ["agp", "agy"]):
        return "gemini", "Gemini"
    if "cursor" in title:
        return "grok", "Grok"
    if "claude" in title:
        return "opus", "Claude"
    if any(k in title for k in ["codex", "gpt"]):
        return "gpt", "GPT"

    # 4. Terminal content inspection (last 15 lines of visible screen)
    if pane_id:
        out, _, _ = run_cmd(["herdr", "pane", "read", pane_id, "--source", "visible"])
        tail = "\n".join(out.splitlines()[-15:]).lower()
        if any(k in tail for k in ["claude", "opus 5", "sonnet"]):
            return "opus", "Claude"
        if any(k in tail for k in ["grok", "cursor agent"]):
            return "grok", "Grok"
        if any(k in tail for k in ["openai codex", "ask codex", "gpt-"]):
            return "gpt", "GPT"
        if any(k in tail for k in ["gemini", "antigravity", "3.8 flash", "google ai"]):
            return "gemini", "Gemini"

    return "agent", "Unknown"

def get_model_role(prefix):
    """
    Returns the recommended tier and role description for a model:
    - Opus: Top tier, smartest worker (High-complexity tasks)
    - Gemini: Core workhorse, smart worker (Normal complexity & below, bulk of work)
    - Default (all others: GPT, Grok, etc.): Simple worker (Fire & forget tasks)
    """
    p = (prefix or "").lower()
    if "opus" in p or "claude" in p:
        return "Top tier (High complexity)"
    if "gemini" in p or "agy" in p:
        return "Workhorse (Normal & bulk work)"
    return "Simple (Fire & forget)"

def auto_name_panes(tab_id=None, workspace_id=None, leader_pane_id=None):
    """
    Detects worker panes in current tab and renames them to <space_tag>-<model>-<n>.
    Also renames the leader pane to <space_tag>-opus-leader.
    Numbering for each model prefix ALWAYS resets from 1 strictly within the tab!
    Space tag is the first 3 letters of the space name (e.g. 'one', 'zer', 'two', 'aif').
    """
    space_tag = get_space_tag(tab_id=tab_id, ws_id=workspace_id)
    caller_pane = leader_pane_id or get_current_pane()

    if caller_pane:
        leader_name = f"{space_tag}-opus-leader"
        run_cmd(["herdr", "pane", "rename", caller_pane, leader_name])
        run_cmd(["herdr", "agent", "rename", caller_pane, leader_name])

    out, _, rc = run_cmd(["herdr", "pane", "list"])
    if rc != 0:
        return {}
    try:
        all_panes = json.loads(out).get("result", {}).get("panes", [])
    except Exception:
        return {}

    # Scoped strictly to the current tab
    if tab_id:
        target_panes = [p for p in all_panes if p.get("tab_id") == tab_id]
    elif workspace_id:
        target_panes = [p for p in all_panes if p.get("workspace_id") == workspace_id]
    else:
        target_panes = all_panes

    # Fetch geometry layout to sort workers top-to-bottom, left-to-right
    pane_rects = {}
    if caller_pane:
        layout_out, _, l_rc = run_cmd(["herdr", "pane", "layout", "--pane", caller_pane])
        if l_rc == 0:
            try:
                for lp in json.loads(layout_out).get("result", {}).get("layout", {}).get("panes", []):
                    pane_rects[lp.get("pane_id")] = lp.get("rect", {})
            except Exception:
                pass

    # Separate workers from leader
    workers = []
    for p in target_panes:
        pid = p.get("pane_id")
        lbl = (p.get("label") or "").lower()
        if pid == caller_pane or "leader" in lbl:
            continue
        workers.append(p)

    # Sort workers geometrically: top-to-bottom, then left-to-right
    def worker_sort_key(p):
        rect = pane_rects.get(p.get("pane_id"), {})
        return (rect.get("y", 0), rect.get("x", 0), p.get("pane_id", ""))

    workers.sort(key=worker_sort_key)

    # Reset model counters from 1 strictly for this tab
    model_counts = {"opus": 0, "gemini": 0, "grok": 0, "gpt": 0, "agent": 0}
    renamed = {}

    for p in workers:
        pane_id = p.get("pane_id")
        prefix, _ = detect_model(p)
        model_counts[prefix] = model_counts.get(prefix, 0) + 1
        new_name = f"{space_tag}-{prefix}-{model_counts[prefix]}"

        run_cmd(["herdr", "pane", "rename", pane_id, new_name])
        run_cmd(["herdr", "agent", "rename", pane_id, new_name])
        renamed[pane_id] = new_name

    return renamed

def get_current_tab():
    """Resolves caller Herdr tab ID from environment or Herdr CLI"""
    tab_id = os.environ.get("HERDR_TAB_ID")
    if tab_id:
        return tab_id
    pane_id = os.environ.get("HERDR_PANE_ID")
    if pane_id:
        out, _, rc = run_cmd(["herdr", "pane", "get", pane_id])
        if rc == 0:
            try:
                return json.loads(out).get("result", {}).get("pane", {}).get("tab_id")
            except Exception:
                pass
    out, _, rc = run_cmd(["herdr", "pane", "current", "--current"])
    if rc == 0:
        try:
            return json.loads(out).get("result", {}).get("pane", {}).get("tab_id")
        except Exception:
            pass
    return None

def get_current_pane():
    """Resolves caller Herdr pane ID from environment or Herdr CLI"""
    pane_id = os.environ.get("HERDR_PANE_ID")
    if pane_id:
        return pane_id
    out, _, rc = run_cmd(["herdr", "pane", "current", "--current"])
    if rc == 0:
        try:
            return json.loads(out).get("result", {}).get("pane", {}).get("pane_id")
        except Exception:
            pass
    return None

def load_lead_skill_directives():
    """
    Loads standing orchestrator directives dynamically from lead SKILL.md.
    Strips YAML frontmatter and initialization sections.
    Falls back to compact embedded directives if SKILL.md is missing.
    """
    skill_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    candidates = [
        os.path.join(skill_dir, "SKILL.md"),
        os.path.expanduser("~/Projects/ai-framework/ai-first-fw/utilities/herdr-leader/SKILL.md"),
        os.path.expanduser("~/.claude/skills/herdr-leader/SKILL.md"),
        os.path.expanduser("~/.claude-clone/skills/herdr-leader/SKILL.md"),
        os.path.expanduser("~/Projects/ai-framework/ai-first-fw/utilities/lead/SKILL.md"),
        os.path.expanduser("~/.claude/skills/lead/SKILL.md"),
        os.path.expanduser("~/.claude-clone/skills/lead/SKILL.md"),
    ]
    raw = None
    for p in candidates:
        if os.path.isfile(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    raw = f.read()
                break
            except Exception:
                pass

    if not raw:
        return """## Standing Orchestrator Directives
### 1. Team Scope & Authority
- Lead ONLY worker panes in your tab. Zero cross-tab authority.
### 2. Delegate, Track & Steer
- Never write code directly. Dispatch via `herdr agent prompt <target> "<brief>"`, track via `herdr agent wait <target>`, verify on disk.
### 3. Verify on Disk (Zero Blind Trust)
- Never trust terminal self-reports. Inspect `git diff`, `ls -la`, `wc -l`, and run tests.
### 4. Model Tiering, Recommended Roles & Capacity Sizing
- Opus: Top tier, smartest worker (High complexity).
- Gemini: Core workhorse, smart worker (Normal complexity & below, bulk of workload).
- Default (all others): Simple worker (Fire & forget).
- Soft guidance: Recommended, not rigid. Adapt flexibly if a tier is busy.
- Fixed panes & queueing: Keep pane count fixed; queue jobs via `herdr agent wait <target>` instead of creating new panes.
- Capacity: Big pool (Claude/Gemini/GPT) <650K, default for all others <210K. Run `pane-limits <target>` before dispatch. Split if HIGH.
### 5. Inter-Agent Communication & Scratchpads
- Use root repo '.scratchpads/' or agent tmp folder (/tmp) for inter-agent communication, drafts, payloads, and handoffs. Keep source tree clean.
### 6. Context Hygiene: Clear or Handoff
- Stateless: `/clear ` (trailing space). Stateful: handoff to '.scratchpads/<target>-handoff.md' -> verify -> `/clear ` -> read handoff.
### 7. Execution Mechanics
- Address by name (`<space>-<model>-<n>`). Interrupt via `herdr agent send-keys <target> ctrl+c`."""

    # Extract from '## Standing Orchestrator Directives' onward
    marker = "## Standing Orchestrator Directives"
    idx = raw.find(marker)
    if idx != -1:
        return raw[idx:].strip()

    # Fallback: strip frontmatter if marker not found
    if raw.startswith("---"):
        parts = raw.split("---", 2)
        if len(parts) >= 3:
            return parts[2].strip()
    return raw.strip()

def generate_leader_prompt(tab_id=None, leader_pane_id=None):
    """
    Scans and auto-names all worker panes in the current tab,
    reads their capacity, and formats a complete Leader Orchestrator prompt
    using directives loaded dynamically from lead SKILL.md.
    """
    if not tab_id:
        tab_id = get_current_tab()
    if not leader_pane_id:
        leader_pane_id = get_current_pane()

    space_tag = get_space_tag(tab_id=tab_id)

    # 1. Rename leader and auto-name workers in tab
    auto_name_panes(tab_id=tab_id, leader_pane_id=leader_pane_id)

    # 2. Read live pane & agent info in this tab
    pane_out, _, _ = run_cmd(["herdr", "pane", "list"])
    pane_map = {}
    try:
        for p in json.loads(pane_out).get("result", {}).get("panes", []):
            if p.get("pane_id"):
                pane_map[p["pane_id"]] = p
    except Exception:
        pass

    stdout, _, rc = run_cmd(["herdr", "agent", "list"])
    if rc != 0:
        return "ERR: herdr agent list failed"

    try:
        agents = json.loads(stdout).get("result", {}).get("agents", [])
    except Exception:
        return "ERR: failed parsing herdr agent list"

    if tab_id:
        agents = [a for a in agents if a.get("tab_id") == tab_id]

    caller_pane = leader_pane_id or os.environ.get("HERDR_PANE_ID")
    worker_rows = []

    for ag in agents:
        pane_id = ag.get("pane_id", "")
        p_info = pane_map.get(pane_id, {})
        name = ag.get("name") or p_info.get("label") or "unknown"
        kind = ag.get("agent", "unknown")
        status = ag.get("agent_status", "idle")

        if pane_id == caller_pane or "leader" in name.lower():
            continue

        pane_out, _, _ = run_cmd(["herdr", "pane", "read", pane_id, "--source", "visible"])
        tail_lines = "\n".join(pane_out.splitlines()[-15:])
        usage_str, pct, used_k = parse_usage(tail_lines)

        limit_tokens_k, limit_str, _ = get_model_target_limit(name, kind, tail_lines)
        prefix, display_model = detect_model(p_info if p_info else {"pane_id": pane_id, "agent": kind, "label": name})
        role_str = get_model_role(prefix)

        worker_rows.append((name, pane_id, display_model, role_str, limit_str, status, usage_str))

    if worker_rows:
        table_lines = [
            "| Target Name | Pane ID | Model | Recommended Role | Explicit Limit | Status | Current Usage |",
            "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |"
        ]
        for name, pane_id, model, role_str, limit_str, status, usage_str in worker_rows:
            table_lines.append(f"| `{name}` | `{pane_id}` | {model} | {role_str} | {limit_str} | {status} | {usage_str} |")
        roster_md = "\n".join(table_lines)
    else:
        roster_md = "*No worker panes detected in this tab yet.*"

    leader_name = f"{space_tag}-opus-leader"
    directives = load_lead_skill_directives()

    prompt = f"""# Swarm Leader: {leader_name} [Tab: {tab_id or 'current'} | Space: {space_tag.upper()}]
You lead ONLY these worker panes in this tab:
{roster_md}

{directives}"""
    return prompt

def split_pane(parent_id, direction="right", cwd=None, ratio="0.5"):
    """
    Splits parent_id in the given direction ('right' or 'down') with an explicit ratio.
    Returns the newly created pane_id, or None on failure.
    """
    args = [
        "herdr", "pane", "split",
        "--pane", parent_id,
        "--direction", direction,
        "--ratio", str(ratio),
        "--no-focus"
    ]
    if cwd:
        args.extend(["--cwd", cwd])
    out, err, rc = run_cmd(args)
    if rc != 0:
        args_alt = [
            "herdr", "pane", "split",
            parent_id,
            "--direction", direction,
            "--ratio", str(ratio),
            "--no-focus"
        ]
        if cwd:
            args_alt.extend(["--cwd", cwd])
        out, err, rc = run_cmd(args_alt)
        if rc != 0:
            print(f"ERR: failed splitting pane {parent_id}: {err}", file=sys.stderr)
            return None
    try:
        data = json.loads(out)
        return data.get("result", {}).get("pane", {}).get("pane_id")
    except Exception as e:
        print(f"ERR: failed parsing split response: {e}", file=sys.stderr)
        return None

def close_other_panes_in_tab(tab_id, keep_pane_id):
    """Closes all panes in tab_id except keep_pane_id."""
    out, _, rc = run_cmd(["herdr", "pane", "list"])
    if rc != 0:
        return 0
    try:
        panes = json.loads(out).get("result", {}).get("panes", [])
    except Exception:
        return 0

    closed = 0
    for p in panes:
        pid = p.get("pane_id")
        tid = p.get("tab_id")
        if tid == tab_id and pid and pid != keep_pane_id:
            run_cmd(["herdr", "pane", "close", pid])
            closed += 1
    return closed

def get_pane_cwd(pane_id):
    """Fetches working directory of a pane from Herdr."""
    if pane_id:
        out, _, rc = run_cmd(["herdr", "pane", "get", pane_id])
        if rc == 0:
            try:
                pane = json.loads(out).get("result", {}).get("pane", {})
                return pane.get("foreground_cwd") or pane.get("cwd")
            except Exception:
                pass
    return os.environ.get("PWD") or os.getcwd()

def spawn_swarm(option_num, tab_id=None, leader_pane_id=None):
    """
    Closes other panes in current tab, spawns worker panes for option (3, 4, or 5),
    runs the agent commands, and auto-names all panes.
    Enforces:
    - Leader occupies the entire LEFT half (100% height, 50% width).
    - ALL worker panes are confined strictly to the RIGHT half (x >= 50%).

    Option 3: clan, agp, agr
    Option 4: clan, agp, agr, agg
    Option 5: clan, agp, agr, cus, gpt
    """
    try:
        opt = int(option_num)
    except ValueError:
        print(f"ERR: Invalid spawn option '{option_num}'. Choose 3, 4, or 5.", file=sys.stderr)
        return False

    if opt not in (3, 4, 5):
        print(f"ERR: Unsupported spawn option '{opt}'. Choose 3, 4, or 5.", file=sys.stderr)
        return False

    if not tab_id:
        tab_id = get_current_tab()
    if not leader_pane_id:
        leader_pane_id = get_current_pane()

    if not tab_id or not leader_pane_id:
        print("ERR: Could not resolve current Herdr tab or pane ID.", file=sys.stderr)
        return False

    space_tag = get_space_tag(tab_id=tab_id)
    cwd = get_pane_cwd(leader_pane_id)

    print(f"🧹 Closing other panes in tab [{tab_id}] (Space: {space_tag.upper()})...")
    closed = close_other_panes_in_tab(tab_id, leader_pane_id)
    if closed > 0:
        time.sleep(0.5)

    # Ensure leader pane is not zoomed
    run_cmd(["herdr", "pane", "zoom", "--pane", leader_pane_id, "--off"])
    time.sleep(0.1)

    # Rename leader pane
    leader_name = f"{space_tag}-opus-leader"
    run_cmd(["herdr", "pane", "rename", leader_pane_id, leader_name])
    run_cmd(["herdr", "agent", "rename", leader_pane_id, leader_name])

    print(f"🌱 Spawning {opt} worker panes (Leader on Left Half, All Workers on Right Half)...")

    # Step 1: Divide the tab cleanly 50/50 vertically.
    # Leader stays in left half; p1 becomes the root of the right half.
    p1 = split_pane(leader_pane_id, direction="right", cwd=cwd, ratio="0.5")
    if not p1:
        print("ERR: Failed to split right from leader pane.", file=sys.stderr)
        return False

    time.sleep(0.2)
    workers = []  # list of (pane_id, command, assigned_name)

    # Step 2: Subdivide ONLY within the right half (never touching leader_pane_id again)
    if opt == 3:
        # 3 workers in right half:
        # p1 (top-right, 50% height)
        # p2 (bottom-left of right half, 50% height)
        # p3 (bottom-right of right half, 50% height)
        p2 = split_pane(p1, direction="down", cwd=cwd, ratio="0.5")
        time.sleep(0.15)
        p3 = split_pane(p2, direction="right", cwd=cwd, ratio="0.5") if p2 else None

        workers = [
            (p1, "clan", f"{space_tag}-opus-1"),
            (p2, "agp", f"{space_tag}-gemini-1"),
            (p3, "agr", f"{space_tag}-gemini-2"),
        ]

    elif opt == 4:
        # 4 workers in right half (2x2 grid):
        # Top row: p1 (top-left), p3 (top-right)
        # Bottom row: p2 (bottom-left), p4 (bottom-right)
        p2 = split_pane(p1, direction="down", cwd=cwd, ratio="0.5")
        time.sleep(0.15)
        p3 = split_pane(p1, direction="right", cwd=cwd, ratio="0.5")
        time.sleep(0.15)
        p4 = split_pane(p2, direction="right", cwd=cwd, ratio="0.5") if p2 else None

        workers = [
            (p1, "clan", f"{space_tag}-opus-1"),
            (p3, "agp", f"{space_tag}-gemini-1"),
            (p2, "agr", f"{space_tag}-gemini-2"),
            (p4, "agg", f"{space_tag}-gemini-3"),
        ]

    elif opt == 5:
        # 5 workers in right half:
        # Top row (2 workers): p1, p3
        # Bottom row (3 workers): p2, p4, p5
        p2 = split_pane(p1, direction="down", cwd=cwd, ratio="0.5")
        time.sleep(0.15)
        p3 = split_pane(p1, direction="right", cwd=cwd, ratio="0.5")
        time.sleep(0.15)
        p4 = split_pane(p2, direction="right", cwd=cwd, ratio="0.5") if p2 else None
        time.sleep(0.15)
        p5 = split_pane(p4, direction="right", cwd=cwd, ratio="0.5") if p4 else None

        workers = [
            (p1, "clan", f"{space_tag}-opus-1"),
            (p3, "agp", f"{space_tag}-gemini-1"),
            (p2, "agr", f"{space_tag}-gemini-2"),
            (p4, "cus", f"{space_tag}-grok-1"),
            (p5, "gpt", f"{space_tag}-gpt-1"),
        ]

    valid_workers = [w for w in workers if w[0]]
    time.sleep(0.8)  # allow shells in newly spawned panes to finish loading

    print("🚀 Launching worker agents...")
    for pid, cmd, name in valid_workers:
        run_cmd(["herdr", "pane", "rename", pid, name])
        run_cmd(["herdr", "agent", "rename", pid, name])
        run_cmd(["herdr", "pane", "run", pid, cmd])
        print(f"  ↳ [{pid}] {name} (Right Half) -> `{cmd}`")

    print("⏳ Waiting for agents to initialize...")
    time.sleep(2.5)

    auto_name_panes(tab_id=tab_id, leader_pane_id=leader_pane_id)
    return True


def main():
    if "--init-leader" in sys.argv or "--leader-prompt" in sys.argv:
        current_tab = get_current_tab()
        current_pane = get_current_pane()
        prompt = generate_leader_prompt(tab_id=current_tab, leader_pane_id=current_pane)
        print(prompt)
        sys.exit(0)

    spawn_opt = None
    if "--spawn" in sys.argv:
        idx = sys.argv.index("--spawn")
        if idx + 1 < len(sys.argv):
            spawn_opt = sys.argv[idx + 1]
    elif len(sys.argv) > 1 and sys.argv[1] in ("3", "4", "5"):
        spawn_opt = sys.argv[1]

    if spawn_opt:
        current_tab = get_current_tab()
        current_pane = get_current_pane()
        success = spawn_swarm(spawn_opt, tab_id=current_tab, leader_pane_id=current_pane)
        if not success:
            sys.exit(1)
        target = None
    else:
        target = sys.argv[1].strip() if len(sys.argv) > 1 else None
    
    current_tab = get_current_tab()
    current_pane = get_current_pane()
    current_ws = os.environ.get("HERDR_WORKSPACE_ID")

    # Auto-name any unnamed panes strictly within the current tab
    auto_name_panes(tab_id=current_tab, workspace_id=(current_ws if not current_tab else None), leader_pane_id=current_pane)

    # Get pane labels for fallback display
    pane_out, _, _ = run_cmd(["herdr", "pane", "list"])
    pane_labels = {}
    try:
        for p in json.loads(pane_out).get("result", {}).get("panes", []):
            if p.get("pane_id"):
                pane_labels[p["pane_id"]] = p.get("label")
    except Exception:
        pass

    # Fetch live agents
    stdout, _, rc = run_cmd(["herdr", "agent", "list"])
    if rc != 0:
        print("ERR: herdr agent list failed", file=sys.stderr)
        sys.exit(1)

    try:
        agents = json.loads(stdout).get("result", {}).get("agents", [])
    except Exception:
        print("ERR: failed parsing json", file=sys.stderr)
        sys.exit(1)

    # Filter agents strictly to the current tab only
    if current_tab:
        agents = [a for a in agents if a.get("tab_id") == current_tab]
    elif current_ws:
        agents = [a for a in agents if a.get("workspace_id") == current_ws]

    if target:
        agents = [a for a in agents if a.get("name") == target or a.get("pane_id") == target or pane_labels.get(a.get("pane_id")) == target]
        if not agents:
            tab_msg = f" in tab '{current_tab}'. Leader can only lead panes within its own tab." if current_tab else "."
            print(f"NOT_FOUND: target '{target}' not found{tab_msg}")
            sys.exit(1)

    space_tag = get_space_tag(tab_id=current_tab, ws_id=current_ws)

    if not target:
        header = f"PANES IN TAB [{current_tab}] (SPACE: {space_tag.upper()}):" if current_tab else f"PANES (SPACE: {space_tag.upper()}):"
        print(header)
        print(f"{'TARGET':<17} {'PANE':<6} {'ROLE':<11} {'STATUS':<8} {'USAGE':<21} {'LIMIT':<8} {'VERDICT'}")
        print("-" * 88)

    for ag in agents:
        pane_id = ag.get("pane_id", "")
        name = ag.get("name") or pane_labels.get(pane_id) or "unknown"
        kind = ag.get("agent", "unknown")
        status = ag.get("agent_status", "")

        pane_out, _, _ = run_cmd(["herdr", "pane", "read", pane_id, "--source", "visible"])
        tail_lines = "\n".join(pane_out.splitlines()[-15:])
        usage_str, pct, used_k = parse_usage(tail_lines)

        limit_tokens_k, limit_str, high_tokens_k = get_model_target_limit(name, kind, tail_lines)
        prefix, _ = detect_model({"pane_id": pane_id, "agent": kind, "label": name})
        role_desc = get_model_role(prefix)
        role_tag = role_desc.split("(")[0].strip()

        if used_k is not None:
            if used_k >= limit_tokens_k:
                verdict = f"BREACH ({used_k:.1f}K >= {limit_tokens_k:.0f}K) -> CLEAR/HANDOFF"
            elif used_k >= high_tokens_k:
                verdict = f"HIGH ({used_k:.1f}K) -> SPLIT UNIT"
            else:
                verdict = "OK"
        elif pct is not None:
            equiv_limit_pct = 65.0 if limit_tokens_k == CLAUDE_GEMINI_LIMIT_K else 82.0
            equiv_high_pct = 55.0 if limit_tokens_k == CLAUDE_GEMINI_LIMIT_K else 68.0
            if pct >= equiv_limit_pct:
                verdict = f"BREACH ({pct:.0f}% >= {equiv_limit_pct:.0f}%) -> CLEAR/HANDOFF"
            elif pct >= equiv_high_pct:
                verdict = f"HIGH ({pct:.0f}%) -> SPLIT UNIT"
            else:
                verdict = "OK"
        else:
            verdict = "UNKNOWN"

        if target:
            # Single-line ultra-compact format
            print(f"{name} ({pane_id}) [{role_desc}]: {usage_str} / {limit_str} [{verdict}] ({status})")
            return

        print(f"{name:<17} {pane_id:<6} {role_tag:<11} {status:<8} {usage_str:<21} {limit_str:<8} {verdict}")

if __name__ == "__main__":
    main()
