#!/usr/bin/env python3
"""PreToolUse guard closing the shell gap around the `testbed` MCP.

Denies Bash commands that read the testbed key files, reach the mock server, run the
testbed engine or touch the local mock data. The key isolation is the real protection;
this hook only covers what the Read/Edit deny rules leave open. See README.md.
"""

import json
import os
import re
import shlex
import sys

HOME = os.path.expanduser("~")
MAX_SCRIPT_BYTES = 512 * 1024
# A path segment ends at a slash, a quote, whitespace or the end of the text, so
# lv1-testbed-dev and lv1-testbed-mcp stay allowed.
END = r"(?=/|['\"\s]|$)"
INTERPRETERS = {"python", "python3", "bash", "sh", "zsh", "source", ".", "node", "ruby", "perl",
                "xargs", "eval", "env"}

# (name, pattern, hint)
RULES = [
    # Key files: the secrets the MCP alone holds.
    ("key file", r"\.testbed\.env|\.config/lv1-testbed" + END,
     "Only the `testbed` MCP reads the testbed keys."),
    # Mock server: a direct call skips the MCP's lease and audit.
    ("mock server host", r"test\.concavoi\.com",
     "Use the `testbed` MCP tools (`mocks_*`, `stores_*`, `reset`, `call_log`, `run_start`)."),
    ("mock admin API", r"/api/(?:content|mocks|lease|servers)\b|__testbed",
     "Use the `testbed` MCP tools (`mocks_*`, `stores_*`, `reset`, `call_log`, `lease_status`)."),
    ("mock server port", r"(?<![\w-])23(?:0\d\d|10[0-3])(?!\d)",
     "Use the `testbed` MCP tools (`mocks_*`, `stores_*`, `reset`, `call_log`)."),
    # Engine: runs suites with the keys; the MCP runs it for agents.
    ("testbed engine",
     r"(?:python[\d.]*|uv\s+run|bash|sh|\./)\s*(?:-\S+\s+)*\S*cli\.py\b|-m\s+suite\.cli\b|\btestbed_client\b",
     "Use `suite_validate`, `suite_lint`, `suite_list`, `suite_judge`, `run_start`, `run_status`, `run_result`."),
    # Mock data: writing it bypasses the API.
    ("mock data folder", r"\.local/share/lv1-testbed" + END,
     "Change mock content with `mocks_push` and runtime state with `stores_put` / `reset`."),
]
COMPILED = [(name, re.compile(pattern, re.IGNORECASE), hint) for name, pattern, hint in RULES]


def _views(text):
    """Returns the raw text, with escapes decoded, and with quotes and backslashes removed."""
    def char(m, base):
        return chr(int(m.group(1), base) & 0xFF if base == 8 else int(m.group(1), base))

    escaped = re.sub(r"\\x([0-9a-fA-F]{2})|\\u([0-9a-fA-F]{4})",
                     lambda m: chr(int(m.group(1) or m.group(2), 16)), text)
    escaped = re.sub(r"\\0?([0-7]{3})", lambda m: char(m, 8), escaped)
    unquoted = re.sub(r"['\"\\`]", "", escaped)
    return [text, escaped, unquoted]


def _scan(text):
    """Returns (rule name, hint) for the first rule the text breaks, else None."""
    for view in _views(text):
        for name, regex, hint in COMPILED:
            if regex.search(view):
                return name, hint
    return None


def _scripts(command, cwd):
    """Yields (path, content) of existing files the command executes."""
    try:
        tokens = shlex.split(command)
    except ValueError:
        tokens = command.split()
    # Test files hold fixture text, so a unittest run is not scanned through its files.
    if "unittest" in tokens:
        return
    runs_code = any(os.path.basename(t) in INTERPRETERS for t in tokens)
    for tok in tokens:
        path = os.path.expanduser(tok.replace("${HOME}", HOME).replace("$HOME", HOME))
        path = os.path.normpath(path if os.path.isabs(path) else os.path.join(cwd, path))
        try:
            if not os.path.isfile(path) or os.path.getsize(path) > MAX_SCRIPT_BYTES:
                continue
            if not (runs_code or os.access(path, os.X_OK)):
                continue
            with open(path, encoding="utf-8", errors="replace") as fh:
                yield path, fh.read()
        except OSError:
            continue


def check(command, cwd=None):
    """Returns a deny reason for a Bash command, or None when it may run.

    @apiNote Pure apart from reading the script files the command executes.
    """
    cwd = cwd or os.getcwd()
    where, hit = "the command", _scan(command)
    if hit is None:
        for path, content in _scripts(command, cwd):
            hit = _scan(content)
            if hit:
                where = f"the script {path}"
                break
    if hit is None:
        return None
    name, hint = hit
    return f"Blocked by the testbed guard: {where} touches the {name}. {hint}"


def main():
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        return 0
    if payload.get("tool_name") != "Bash":
        return 0
    command = (payload.get("tool_input") or {}).get("command") or ""
    try:
        reason = check(command, payload.get("cwd"))
    except Exception as exc:  # noqa: BLE001 — a guard bug must not open the gate
        reason = f"Blocked by the testbed guard: it failed to analyse the command ({exc!r})."
    if reason:
        json.dump({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }}, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
