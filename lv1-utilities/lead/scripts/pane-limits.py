#!/usr/bin/env python3
"""
herdr-pane-limits.py

Optimized, token-efficient capacity checker and pane namer for herdr.
- Confined strictly to the current workspace ($HERDR_WORKSPACE_ID); spans every tab in it
- Explicit model token limits:
  - Big pool (Gemini, Claude, GPT): 700k tokens (<700K)
  - Default (all other models & unknown): 210k tokens (<210K)
- Auto-names worker panes in the current workspace as <space_tag>-<model>-<number>
- Supports checking a single target (1 line) or all panes in the workspace (compact table)

Usage:
  herdr-pane-limits.py          # compact summary of panes in current tab
  herdr-pane-limits.py <target> # single line check for one pane
"""

import json
import os
import re
import shlex
import subprocess
import sys
import time

# Explicit token limits in thousands (K)
BIG_POOL_LIMIT_K = 700.0
DEFAULT_LIMIT_K = 210.0

# Retained only so older callers importing these names keep working; the HIGH band no
# longer decides anything. Dispatch is decided by `current + predicted > limit`, and the
# figure the leader needs is the headroom (`limit - current`) printed on every row.
BIG_POOL_HIGH_K = BIG_POOL_LIMIT_K
DEFAULT_HIGH_K = DEFAULT_LIMIT_K

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

def get_model_target_limit(name, kind, tail_lines="", prefix=None):
    """
    Determines explicit token target limit based on model:
    - Big pool (Gemini, Claude, GPT): 700k tokens (<700K)
    - Default (all others / Grok / Unknown): 210k tokens (<210K)
    Returns: (limit_tokens_k, limit_str, high_tokens_k)
    """
    if prefix:
        p = prefix.lower()
        if p in ("grok", "agent"):
            return DEFAULT_LIMIT_K, "<210K>", DEFAULT_HIGH_K
        if p in ("opus", "gemini", "gpt"):
            return BIG_POOL_LIMIT_K, "<700K", BIG_POOL_HIGH_K

    combined = f"{name} {kind}".lower()
    if any(m in combined for m in ["grok", "cursor"]):
        return DEFAULT_LIMIT_K, "<210K>", DEFAULT_HIGH_K

    if any(m in combined for m in ["gemini", "agy", "claude", "opus", "sonnet", "gpt", "codex"]):
        return BIG_POOL_LIMIT_K, "<700K", BIG_POOL_HIGH_K

    # Clean tail_lines: ignore environment variables and startup command echoes
    clean_lines = [
        line for line in tail_lines.splitlines()
        if not any(k in line for k in ["SWARM_ROSTER", "SWARM_LEADER", "SWARM_SESSION_ID", "SWARM_PANE", "export "])
    ]
    tail = "\n".join(clean_lines).lower()

    if any(m in tail for m in ["grok", "cursor agent"]):
        return DEFAULT_LIMIT_K, "<210K>", DEFAULT_HIGH_K

    if any(m in tail for m in ["gemini", "antigravity", "claude", "opus", "sonnet", "codex", "gpt"]):
        return BIG_POOL_LIMIT_K, "<700K", BIG_POOL_HIGH_K

    return DEFAULT_LIMIT_K, "<210K>", DEFAULT_HIGH_K

def parse_usage(text, prefix=None):
    """
    Parses usage from agent pane output.
    Returns: (usage_display_str, pct_float, used_k_float)
    """
    is_256k = (prefix in ("grok", "agent"))

    # 1. Main format: Main: 166.3K/1.00M (17%), Main: 0/1.05M tok (0%), or Main: 73.6K/1.00M (…
    m = re.search(r'Main:\s*([0-9.]+[KkMm]?)\s*/\s*([0-9.]+[KkMm]?)(?:[^\n0-9]*([0-9.]+)%)?', text)
    if m:
        u_str, t_str = m.group(1), m.group(2)
        u_k, t_k = to_tokens_k(u_str), to_tokens_k(t_str)
        if is_256k:
            t_k = 256.0
            t_str = "256K"
        if m.group(3) and not is_256k:
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
        default_win = 256.0 if is_256k else 1000.0
        default_disp = "256K" if is_256k else "1.00M"
        t_k = to_tokens_k(m_win.group(1)) if m_win else default_win
        tot_disp = m_win.group(1) if m_win else default_disp
        u_k = (t_k * pct / 100.0) if t_k else None
        return f"{u_k:.1f}K/{tot_disp} ({pct:.0f}%)", pct, u_k

    # "Context left: 68%"
    m_codex_left = re.search(r'Context left:\s*([0-9.]+)%', text, re.IGNORECASE)
    if m_codex_left:
        left_pct = float(m_codex_left.group(1))
        pct = 100.0 - left_pct
        m_win = re.search(r'([0-9.]+[KkMm]?)\s*window', text, re.IGNORECASE)
        default_win = 256.0 if is_256k else 1000.0
        default_disp = "256K" if is_256k else "1.00M"
        t_k = to_tokens_k(m_win.group(1)) if m_win else default_win
        tot_disp = m_win.group(1) if m_win else default_disp
        u_k = (t_k * pct / 100.0) if t_k else None
        return f"{u_k:.1f}K/{tot_disp} ({pct:.0f}%)", pct, u_k

    # 3. Main format without total: Main: 150K (15%) or Main: (15%)
    m_pct = re.search(r'Main:[^(\n]+\(\s*([0-9.]+)%\s*\)', text)
    if m_pct:
        pct = float(m_pct.group(1))
        if is_256k:
            u_k = 256.0 * (pct / 100.0)
            return f"{u_k:.1f}K/256K ({pct:.0f}%)", pct, u_k
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
    if any(k in title for k in ["agp", "agr", "agg", "agy", "gemini"]):
        return "gemini", "Gemini"
    if any(k in title for k in ["cus", "cursor", "grok"]):
        return "grok", "Grok"
    if any(k in title for k in ["clan", "clone", "claude"]):
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
    Returns the worker category for a model prefix:
    - smart-agent: Opus (orchestration, decision advice)
    - power-worker: Sonnet (coding first, extends to general tasks)
    - general-worker: Gemini Flash (any task)
    - quick-worker: GPT, Grok and all others (fire & forget)
    """
    p = (prefix or "").lower()
    if "sonnet" in p:
        return "power-worker (Coding & general)"
    if "opus" in p or "claude" in p:
        return "smart-agent (Orchestrator & advisor)"
    if "gemini" in p or "agy" in p:
        return "general-worker (Any task)"
    return "quick-worker (Fire & forget)"

def in_workspace(item, workspace_id, pane_map=None):
    """True when a pane or agent record belongs to workspace_id (via workspace_id, tab_id prefix or pane_map)."""
    if not workspace_id:
        return True
    ws = item.get("workspace_id")
    if not ws and pane_map is not None:
        ws = (pane_map.get(item.get("pane_id"), {}) or {}).get("workspace_id")
    if not ws:
        tab = item.get("tab_id") or ""
        if not tab and pane_map is not None:
            tab = (pane_map.get(item.get("pane_id"), {}) or {}).get("tab_id") or ""
        ws = tab.split(":")[0] if ":" in tab else None
    return ws == workspace_id

def auto_name_panes(workspace_id=None, leader_pane_id=None):
    """
    Detects worker panes in the current workspace (every tab) and renames them to <space_tag>-<model>-<n>.
    Also renames the leader pane to <space_tag>-opus-leader.
    Numbering for each model prefix ALWAYS resets from 1 strictly within the workspace!
    Space tag is the first 3 letters of the space name (e.g. 'one', 'zer', 'two', 'aif').
    """
    space_tag = get_space_tag(ws_id=workspace_id)
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

    # Scoped strictly to the current workspace (all its tabs)
    target_panes = [p for p in all_panes if in_workspace(p, workspace_id)]

    leader_tab = None
    for p in all_panes:
        if p.get("pane_id") == caller_pane:
            leader_tab = p.get("tab_id")

    # Fetch geometry layout to sort the leader tab's workers top-to-bottom, left-to-right
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

    # Sort: leader's tab first (geometrically), then other tabs by tab id
    def worker_sort_key(p):
        rect = pane_rects.get(p.get("pane_id"), {})
        other_tab = 0 if p.get("tab_id") == leader_tab else 1
        return (other_tab, p.get("tab_id") or "", rect.get("y", 0), rect.get("x", 0), p.get("pane_id", ""))

    workers.sort(key=worker_sort_key)

    # Reset model counters from 1 strictly for this workspace
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

def get_current_workspace():
    """Resolves caller Herdr workspace ID: $HERDR_WORKSPACE_ID, the caller pane's record, or the tab id prefix."""
    ws_id = os.environ.get("HERDR_WORKSPACE_ID")
    if ws_id:
        return ws_id
    pane_id = os.environ.get("HERDR_PANE_ID")
    cmds = []
    if pane_id:
        cmds.append(["herdr", "pane", "get", pane_id])
    cmds.append(["herdr", "pane", "current", "--current"])
    for cmd in cmds:
        out, _, rc = run_cmd(cmd)
        if rc == 0:
            try:
                pane = json.loads(out).get("result", {}).get("pane", {})
                ws = pane.get("workspace_id")
                if not ws and ":" in (pane.get("tab_id") or ""):
                    ws = pane["tab_id"].split(":")[0]
                if ws:
                    return ws
            except Exception:
                pass
    tab_id = get_current_tab()
    if tab_id and ":" in tab_id:
        return tab_id.split(":")[0]
    return None

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
    skill_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    candidates = [
        os.path.join(skill_dir, "SKILL.md"),
        os.path.join(os.path.dirname(os.path.realpath(__file__)), "SKILL.md"),
        os.path.expanduser("~/.claude/skills/herdr-leader/SKILL.md"),
        os.path.expanduser("~/.claude-clone/skills/herdr-leader/SKILL.md"),
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

### Step 1 — Claim leadership and retrieve live capacity
Run `pane-limits --init-leader` to claim leadership, auto-name workers across every tab of `$HERDR_WORKSPACE_ID`, and retrieve capacity. Print the returned worker table and ask the user for the objective. Lead only worker panes in `$HERDR_WORKSPACE_ID`; leave panes in other workspaces to their own sessions. One leader per workspace.
On each new objective, call `swarm-coordinator.start_run()` before the first delegate: task ids restart at `R<run>-T1`. Report any `open_tasks` it returns from the previous run.

### Step 2 — Size and assign tasks by category
Break the objective into bounded, self-contained briefs. Assign each brief to a category:
- smart-agent — Opus: smart, top-tier work: orchestration, decision advice.
- power-worker — Sonnet: coding first; extends to general tasks.
- general-worker — Gemini Flash (agg, agp, agr): any task.
- quick-worker — GPT, Grok (gpt, cus): quick fire-and-forget tasks.
Treat categories as soft; when a target worker is busy, overflow to a capable idle worker.

The token limit is a pre-dispatch target: clear when `current + predicted > limit` (700K big pool: Claude/Gemini/GPT, 210K default for all others). Run `pane-limits <target>` immediately before every dispatch. Check headroom (`limit - current`).

### Step 3 — Delegate through the coordinator
Keep the swarm pane count fixed; allocate all briefs across existing panes.
Open every turn with `swarm-coordinator.session_log()`.
Consult the wiki for domain knowledge ahead of dispatch: use `wiki.search` to locate relevant specs, architecture, and traps.
Formulate the task for the coordinator:
- Standard brief: Pass directly in the `brief` argument of `swarm-coordinator.delegate(target, brief, wiki_refs)`.
- Large / multi-step plan: Write the plan into Redis scratch via `swarm-coordinator.put("plan:<step>", plan_markdown)` and reference the key in the brief text. Never write task plans into the wiki.
- `wiki_refs`: Pass only durable domain knowledge chunks the worker needs to consult, or `[]` if none.
Every brief ends with:
> When finished, call `swarm-coordinator.complete("<task-id>", "done", "<3-line summary>")`. Put anything longer in `swarm-coordinator.put()` and name the key in your summary.

### Step 4 — Let the completions come to you
Your turn ends after delegating. A worker's `complete` call prompts this pane and starts a new turn. Do not poll.
A new turn opens with `swarm-coordinator.session_log()`, then `swarm-coordinator.get("result:<id>")` for the task that woke you.
Reconcile every turn before reading results: pair delegates against completes in the log. If missing, check pane with `herdr agent get <pane>`.
A completion whose id carries an earlier run (`R3-T2` while the current run is 4) is a leftover: verify it, reconcile with `session_log(run=3)`, never fold it into the current objective unasked.

### Step 5 — Exchange payloads through Redis, not files
`swarm-coordinator.put(name, value)` writes a scratch payload and returns its key.
`swarm-coordinator.get(key)` reads it. Keys expire after 7 days.
Scratch payloads and task execution plans stay out of the wiki. No inter-agent payload touches the filesystem.

### Step 6 — Verify on disk, then clear or hand off
Zero blind trust. Verify with `git diff`, `ls -la`, `wc -l`, compilers and test suites before accepting anything.
Durable learning found along the way goes to the wiki's inbox via `wiki.note(slug, body, summary)`. Deliverables stay files in `jira-workspace/`.
Clearing context:
- Stateless: `herdr agent prompt <target> "/clear "` (trailing space), then delegate next brief.
- Stateful: delegate brief asking worker to `swarm-coordinator.put()` its handoff and report key; verify read back; `/clear `; delegate next brief referencing that key."""

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

def generate_leader_prompt(workspace_id=None, leader_pane_id=None):
    """
    Scans and auto-names all worker panes in the current workspace (every tab),
    reads their capacity, and formats a complete Leader Orchestrator prompt
    using directives loaded dynamically from lead SKILL.md.
    """
    if not workspace_id:
        workspace_id = get_current_workspace()
    if not leader_pane_id:
        leader_pane_id = get_current_pane()

    space_tag = get_space_tag(ws_id=workspace_id)

    # 1. Rename leader and auto-name workers in workspace
    auto_name_panes(workspace_id=workspace_id, leader_pane_id=leader_pane_id)

    # 2. Read live pane & agent info in this workspace
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

    agents = [a for a in agents if in_workspace(a, workspace_id, pane_map)]

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
        prefix, display_model = detect_model(p_info if p_info else {"pane_id": pane_id, "agent": kind, "label": name})
        role_str = get_model_role(prefix)

        limit_tokens_k, limit_str, _ = get_model_target_limit(name, kind, tail_lines, prefix=prefix)
        usage_str, pct, used_k = parse_usage(tail_lines, prefix=prefix)

        worker_rows.append((name, pane_id, display_model, role_str, limit_str, status, usage_str))

    if worker_rows:
        table_lines = [
            "| Target Name | Pane ID | Model | Category | Explicit Limit | Status | Current Usage |",
            "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |"
        ]
        for name, pane_id, model, role_str, limit_str, status, usage_str in worker_rows:
            table_lines.append(f"| `{name}` | `{pane_id}` | {model} | {role_str} | {limit_str} | {status} | {usage_str} |")
        roster_md = "\n".join(table_lines)
    else:
        roster_md = "*No worker panes detected in this workspace yet.*"

    leader_name = f"{space_tag}-opus-leader"
    directives = load_lead_skill_directives()

    prompt = f"""# Swarm Leader: {leader_name} [Workspace: {workspace_id or 'current'} | Space: {space_tag.upper()}]
You lead ONLY these worker panes in this workspace (all tabs):
{roster_md}

{directives}"""
    return prompt

def spawn_workers(agent_commands):
    """
    Dynamically partitions the tab and spawns worker panes.
    - Caller pane (leader) stays on the left half (50% width).
    - If any non-leader panes already exist in the leader's tab, they are closed first to ensure a clean layout.
      Panes in the workspace's other tabs are kept and join the roster.
    - Right half is dynamically split into N vertical slots for the N agent commands.
    - Executes each agent command in its assigned pane via `herdr pane run`.
    - Auto-names the leader (<space_tag>-opus-leader) and worker panes (<space_tag>-<model>-<n>).
    - Prints the live leader prompt with worker capacity table and orchestrator directives.
    """
    caller_pane = get_current_pane()
    current_tab = get_current_tab()
    current_ws = get_current_workspace()
    if not caller_pane or not current_tab:
        print("ERR: cannot determine current Herdr pane or tab. Ensure this is run inside a Herdr pane.", file=sys.stderr)
        sys.exit(1)

    space_tag = get_space_tag(tab_id=current_tab, ws_id=current_ws)

    # 1. Close any existing non-leader panes in the leader's tab for a clean slate (other tabs untouched)
    pane_out, _, rc = run_cmd(["herdr", "pane", "list"])
    if rc == 0:
        try:
            all_panes = json.loads(pane_out).get("result", {}).get("panes", [])
            for p in all_panes:
                pid = p.get("pane_id")
                if p.get("tab_id") == current_tab and pid and pid != caller_pane:
                    run_cmd(["herdr", "pane", "close", pid])
        except Exception:
            pass

    # Rename leader pane
    leader_name = f"{space_tag}-opus-leader"
    run_cmd(["herdr", "pane", "rename", caller_pane, leader_name])
    run_cmd(["herdr", "agent", "rename", caller_pane, leader_name])

    num_workers = len(agent_commands)
    if num_workers == 0:
        print("ERR: no worker commands provided to spawn.", file=sys.stderr)
        sys.exit(1)

    # 2. Split caller_pane right with ratio 0.5 (left half = leader, right half = workers)
    out, err, rc = run_cmd([
        "herdr", "pane", "split",
        "--pane", caller_pane,
        "--direction", "right",
        "--ratio", "0.5",
        "--no-focus",
    ])
    if rc != 0:
        print(f"ERR: failed to split right from leader: {err}", file=sys.stderr)
        sys.exit(1)

    try:
        first_worker = json.loads(out).get("result", {}).get("pane", {}).get("pane_id")
    except Exception:
        first_worker = None

    if not first_worker:
        print(f"ERR: failed to parse new pane ID from split output: {out}", file=sys.stderr)
        sys.exit(1)

    panes = [first_worker]
    current_to_split = first_worker

    # 3. Subdivide right half into num_workers vertical slots
    for i in range(num_workers - 1):
        remaining = num_workers - i
        ratio = 1.0 / remaining
        out, err, rc = run_cmd([
            "herdr", "pane", "split",
            "--pane", current_to_split,
            "--direction", "down",
            "--ratio", f"{ratio:.3f}",
            "--no-focus",
        ])
        if rc != 0:
            print(f"WARN: failed to split pane {current_to_split} down: {err}", file=sys.stderr)
            break
        try:
            new_pid = json.loads(out).get("result", {}).get("pane", {}).get("pane_id")
            if new_pid:
                panes.append(new_pid)
                current_to_split = new_pid
        except Exception:
            break

    # 4. Run each command in its target pane
    for pid, cmd in zip(panes, agent_commands):
        run_cmd(["herdr", "pane", "run", pid, cmd])

    # Allow a moment for processes to launch before scanning
    time.sleep(1.0)

    # 5. Generate and print the leader prompt
    prompt = generate_leader_prompt(workspace_id=current_ws, leader_pane_id=caller_pane)
    print(prompt)

def main():
    if "--space-tag" in sys.argv:
        print(get_space_tag())
        sys.exit(0)

    if "--spawn" in sys.argv:
        idx = sys.argv.index("--spawn")
        raw_items = sys.argv[idx + 1 :]
        cmd_items = []
        for it in raw_items:
            if it.startswith("--"):
                break
            cmd_items.append(it)
        combined = " ".join(cmd_items).replace(",", " ")
        commands = [c.strip() for c in combined.split() if c.strip()]
        if not commands:
            print("ERR: --spawn requires at least one command (e.g. --spawn clan,cus,agg,agr)", file=sys.stderr)
            sys.exit(1)
        spawn_workers(commands)
        sys.exit(0)

    if "--init-leader" in sys.argv or "--leader-prompt" in sys.argv:
        current_ws = get_current_workspace()
        current_pane = get_current_pane()
        prompt = generate_leader_prompt(workspace_id=current_ws, leader_pane_id=current_pane)
        print(prompt)
        sys.exit(0)

    target = sys.argv[1].strip() if len(sys.argv) > 1 else None

    current_pane = get_current_pane()
    current_ws = get_current_workspace()

    # Auto-name worker panes strictly within the current workspace (every tab)
    auto_name_panes(workspace_id=current_ws, leader_pane_id=current_pane)

    # Get pane labels for fallback display
    pane_out, _, _ = run_cmd(["herdr", "pane", "list"])
    pane_labels = {}
    pane_map = {}
    try:
        for p in json.loads(pane_out).get("result", {}).get("panes", []):
            if p.get("pane_id"):
                pane_labels[p["pane_id"]] = p.get("label")
                pane_map[p["pane_id"]] = p
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

    # Filter agents strictly to the current workspace only
    agents = [a for a in agents if in_workspace(a, current_ws, pane_map)]

    if target:
        agents = [a for a in agents if a.get("name") == target or a.get("pane_id") == target or pane_labels.get(a.get("pane_id")) == target]
        if not agents:
            ws_msg = f" in workspace '{current_ws}'. Leader can only lead panes within its own workspace." if current_ws else "."
            print(f"NOT_FOUND: target '{target}' not found{ws_msg}")
            sys.exit(1)

    space_tag = get_space_tag(ws_id=current_ws)

    if not target:
        header = f"PANES IN WORKSPACE [{current_ws}] (SPACE: {space_tag.upper()}):" if current_ws else f"PANES (SPACE: {space_tag.upper()}):"
        print(header)
        print(f"{'TARGET':<17} {'PANE':<6} {'ROLE':<14} {'STATUS':<8} {'USAGE':<21} {'LIMIT':<8} {'VERDICT'}")
        print("-" * 88)

    for ag in agents:
        pane_id = ag.get("pane_id", "")
        name = ag.get("name") or pane_labels.get(pane_id) or "unknown"
        kind = ag.get("agent", "unknown")
        status = ag.get("agent_status", "")

        pane_out, _, _ = run_cmd(["herdr", "pane", "read", pane_id, "--source", "visible"])
        tail_lines = "\n".join(pane_out.splitlines()[-15:])
        prefix, _ = detect_model({"pane_id": pane_id, "agent": kind, "label": name})
        role_desc = get_model_role(prefix)
        role_tag = role_desc.split("(")[0].strip()

        limit_tokens_k, limit_str, high_tokens_k = get_model_target_limit(name, kind, tail_lines, prefix=prefix)
        usage_str, pct, used_k = parse_usage(tail_lines, prefix=prefix)

        if used_k is not None:
            if used_k >= limit_tokens_k:
                verdict = f"BREACH ({used_k:.1f}K >= {limit_tokens_k:.0f}K) -> CLEAR BEFORE NEXT INSTRUCTION"
            else:
                verdict = f"OK  headroom {limit_tokens_k - used_k:.0f}K"
        elif pct is not None:
            equiv_limit_pct = 70.0 if limit_tokens_k == CLAUDE_GEMINI_LIMIT_K else 82.0
            if pct >= equiv_limit_pct:
                verdict = f"BREACH ({pct:.0f}% >= {equiv_limit_pct:.0f}%) -> CLEAR BEFORE NEXT INSTRUCTION"
            else:
                verdict = f"OK  headroom ~{equiv_limit_pct - pct:.0f}% of window"
        else:
            verdict = "UNKNOWN"

        if target:
            # Single-line ultra-compact format
            print(f"{name} ({pane_id}) [{role_desc}]: {usage_str} / {limit_str} [{verdict}] ({status})")
            return

        print(f"{name:<17} {pane_id:<6} {role_tag:<14} {status:<8} {usage_str:<21} {limit_str:<8} {verdict}")

if __name__ == "__main__":
    main()
