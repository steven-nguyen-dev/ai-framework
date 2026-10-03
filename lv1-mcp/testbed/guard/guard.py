#!/usr/bin/env python3
"""PreToolUse guard keeping agents off the testbed mock server and engine.

The `testbed` MCP is the only route to the mock server, the testbed engine
(suite/cli.py) and the MCP secrets under ~/.mcp/ and ~/.config/lv1-testbed/.
This hook reads the Claude Code hook payload on stdin and denies any Bash
command that reaches for them, naming the MCP tool to use instead.

It is a pattern guard, not a sandbox: see README.md for what it cannot catch.
"""

import base64
import binascii
import json
import os
import re
import shlex
import sys

HOME = os.path.expanduser("~")
PROJECTS = os.path.join(HOME, "Projects")
SECRET_DIRS = (os.path.join(HOME, ".mcp"), os.path.join(HOME, ".config", "lv1-testbed"),
               os.path.join(HOME, ".local", "share", "lv1-testbed"))
MAX_SCRIPT_BYTES = 512 * 1024
SCRIPT_DEPTH = 2

MCP = "the `testbed` MCP tool"
SECRET_HINT = (
    "Only the `testbed` MCP reads ~/.mcp/.testbed.env and it never returns the values; "
    "`run_start` injects them into a live run. Do not read, grep, source or print MCP secrets."
)
ENGINE_HINT = (
    f"Use {MCP}s instead: `suite_validate`, `suite_lint`, `suite_list`, `suite_judge` (offline), "
    "`run_start` / `run_status` / `run_result` / `run_list` (live), `mocks_diff` / `mocks_push` (mock content)."
)
SERVER_HINT = (
    f"Use {MCP}s instead: `mocks_diff`, `mocks_push`, `mocks_rollback`, `mocks_status` (mock content), "
    "`stores_get`, `stores_put`, `reset`, `call_log`, `lease_status` (mock runtime), "
    "`run_start` (live runs)."
)
DATA_HINT = (
    "~/.local/share/lv1-testbed is the local mock server's data; writing it bypasses the API. "
    f"Change mock content with {MCP} `mocks_push` and runtime state with `stores_put` / `reset`."
)
EDIT_HINT = "Edit suite and mock files with the Edit/Write tools, then push them with `mocks_push`."

INTERPRETERS = {
    "python", "python3", "python2", "bash", "sh", "zsh", "dash", "ksh", "fish", "source", ".",
    "node", "deno", "bun", "ruby", "perl", "php", "osascript", "xargs", "eval", "exec", "env",
    "uv", "uvx", "pipx", "make", "npx", "tclsh", "lua", "pwsh",
}
GIT_SAFE = {
    "status", "add", "commit", "log", "diff", "show", "rev-parse", "branch", "restore",
    "reset", "mv", "rm", "ls-files", "blame", "grep", "stash", "tag", "switch", "checkout",
    "fetch", "pull", "merge", "rebase", "cherry-pick", "revert", "shortlog", "describe",
}
CONTROL = {"|", "||", "&&", ";", "&", ";;", "(", ")", "|&", "<(", ">(", "<<", "<<<"}


class Rule:
    """A blocking pattern, the views it applies to, and the hint it gives."""

    def __init__(self, name, pattern, hint, compact=False):
        self.name = name
        self.regex = re.compile(pattern, re.IGNORECASE)
        self.hint = hint
        self.compact = compact


def _server_hint(text):
    t = text.lower()
    if "rollback" in t:
        return f"Use {MCP} `mocks_rollback`."
    if "lease" in t:
        return f"Use {MCP} `lease_status`."
    if "stores" in t:
        return f"Use {MCP}s `stores_get` / `stores_put`."
    if "reset" in t:
        return f"Use {MCP} `reset`."
    if "/log" in t or "files" in t and "__testbed" in t:
        return f"Use {MCP} `call_log`."
    if "/api/content" in t or "uploads" in t or "apply" in t:
        return f"Use {MCP}s `mocks_diff` / `mocks_push` / `mocks_status`. {EDIT_HINT}"
    return SERVER_HINT


def _engine_hint(text):
    t = text.lower()
    for flag, tool in (("--validate", "suite_validate"), ("--lint", "suite_lint"),
                       ("--list", "suite_list"), ("--judge", "suite_judge")):
        if flag in t:
            return f"Use {MCP} `{tool}`."
    if re.search(r"mocks\s+push", t):
        return f"Use {MCP} `mocks_push`. {EDIT_HINT}"
    if re.search(r"mocks\s+diff", t):
        return f"Use {MCP} `mocks_diff`."
    if re.search(r"\brun\b", t):
        return f"Use {MCP}s `run_start`, then `run_status` and `run_result`."
    return ENGINE_HINT + " Read engine source with the Read tool."


RULES = [
    Rule("mock server host", r"concavoi", SERVER_HINT, compact=True),
    Rule("mock server port", r"(?<![\w-])23[01]0\d(?!\d)", SERVER_HINT),
    Rule("mock admin API", r"/api/(content|mocks|lease|servers)\b", None, compact=True),
    Rule("mock runtime API", r"__testbed", None, compact=True),
    Rule("mock call log", r"/log/data\b", f"Use {MCP} `call_log`."),
    Rule("testbed secret", r"x-auth-token|admin_password|path_key|testbed_api_token", SECRET_HINT,
         compact=True),
    Rule("mock server data", r"\.local/share/lv1[-_]?testbed", DATA_HINT, compact=True),
    Rule("testbed secret file", r"lv1[-_]?testbed|testbed\.env", SECRET_HINT, compact=True),
    Rule("MCP secrets dir", r"\.mcp(?![\w.-])", SECRET_HINT),
    Rule("environment dump", r"(^|[|;&(]\s*|\s)(printenv|env|set|export\s+-p|declare\s+-[px]+|compgen\s+-[ve])\s*($|[|;&>)])",
         SECRET_HINT),
    Rule("process environment", r"\bps\b[^|;&]*\s-?[a-zA-Z]*[eE][a-zA-Z]*\b|\blaunchctl\s+(getenv|print)", SECRET_HINT),
    Rule("testbed engine", r"\bcli\.py\b|\bsuite\.cli\b|-m\s+cli\b|testbed_client|commands[./]sync\b",
         None),
]


def _decode_escapes(text):
    """Expands \\xNN, \\uNNNN and \\NNN escapes as printf, $'...' and Python would."""
    def hex_sub(m):
        return chr(int(m.group(1), 16))

    out = re.sub(r"\\x([0-9a-fA-F]{2})", hex_sub, text)
    out = re.sub(r"\\u([0-9a-fA-F]{4})", hex_sub, out)
    return re.sub(r"\\0?([0-7]{3})", lambda m: chr(int(m.group(1), 8) & 0xFF), out)


def _printable(data):
    try:
        s = data.decode("utf-8")
    except UnicodeDecodeError:
        return None
    if not s or sum(c.isprintable() or c in "\n\t" for c in s) < 0.9 * len(s):
        return None
    return s


def _decoded_blobs(text):
    """Yields base64 and hex payloads hidden in the text, decoded."""
    for tok in re.findall(r"[A-Za-z0-9+/_-]{8,}={0,2}", text):
        for alt in (tok, tok.replace("-", "+").replace("_", "/")):
            try:
                s = _printable(base64.b64decode(alt + "=" * (-len(alt) % 4), validate=True))
            except (binascii.Error, ValueError):
                continue
            if s:
                yield s
                break
    for tok in re.findall(r"(?:[0-9a-fA-F]{2}){6,}", text):
        s = _printable(bytes.fromhex(tok))
        if s:
            yield s


def _views(text):
    """Returns (text, compact) pairs: the raw text and spellings an evasion would hide behind."""
    escaped = _decode_escapes(text)
    unquoted = re.sub(r"""['"\\`]""", "", escaped)
    unquoted = re.sub(r"\$\{?(?=['\"])", "", unquoted)
    compact = re.sub(r"[\s+,()\[\]{}$]", "", unquoted)
    views = [(text, False), (escaped, False), (unquoted, False), (compact, True)]
    for v, _ in list(views):
        views.append((v[::-1], True))
    for blob in list(_decoded_blobs(text)) + list(_decoded_blobs(unquoted)):
        views.append((blob, False))
        views.extend((b, False) for b in _decoded_blobs(blob))
    return views


# Parent dirs of a testbed dir: (pattern, child names that may follow it without a match).
_PARENTS = (
    (r"\.config", ()),
    (r"\.local/share", ()),
    (r"\.local", ("bin", "lib", "state", "share")),
)


def _config_violation(text):
    """Flags ~/.config, ~/.local and ~/.local/share paths aimed at lv1-testbed, or globbed so they could be."""
    for parent, free in _PARENTS:
        pattern = r"(?<![\w-])" + parent + r"(?=[/\s'\";|&)]|$)(/[^\s'\";|&)]*)?"
        for m in re.finditer(pattern, text):
            seg = (m.group(1) or "/").lstrip("/").split("/")[0]
            if seg in free:
                continue
            if not seg or seg.lower().startswith("lv1") or re.search(r"[*?\[{$]", seg):
                return True
    return bool(re.search(r"(~|\$\{?HOME\}?|/Users/[^/\s]+)/\.[^/\s]*[*?\[]", text))


def _scan_text(text, skip=()):
    """Returns (rule name, hint) for the first rule the text breaks, else None."""
    for view, compact in _views(text):
        for rule in RULES:
            if rule.name in skip or compact and not rule.compact:
                continue
            if rule.regex.search(view):
                hint = rule.hint
                if hint is None:
                    hint = _engine_hint(view) if rule.name == "testbed engine" else _server_hint(view)
                return rule.name, hint
        if not compact and _config_violation(view):
            return "testbed secret or data dir", SECRET_HINT + " " + DATA_HINT
    return None


def _tokens(command):
    try:
        lex = shlex.shlex(command, posix=True, punctuation_chars=True)
        lex.whitespace_split = True
        return list(lex)
    except ValueError:
        return command.split()


def _resolve(token, cwd):
    tok = token.replace("${HOME}", HOME).replace("$HOME", HOME)
    tok = os.path.expanduser(tok)
    return os.path.normpath(tok if os.path.isabs(tok) else os.path.join(cwd, tok))


def _read_script(path):
    try:
        if os.path.isfile(path) and os.path.getsize(path) <= MAX_SCRIPT_BYTES:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                return fh.read()
    except OSError:
        pass
    return None


def _is_unittest(tokens):
    return any(t == "-m" and i + 1 < len(tokens) and tokens[i + 1] == "unittest"
               for i, t in enumerate(tokens)) and not any(
        t in INTERPRETERS - {"python", "python3"} for t in tokens)


def _scripts(command, cwd, depth=SCRIPT_DEPTH, seen=None):
    """Yields (path, content) of files the command would execute, following scripts they name."""
    seen = set() if seen is None else seen
    tokens = _tokens(command)
    if _is_unittest(tokens):
        return
    runs_code = any(os.path.basename(t) in INTERPRETERS for t in tokens)
    for tok in tokens:
        if tok in CONTROL or tok.startswith("-"):
            continue
        path = _resolve(tok, cwd)
        if path in seen:
            continue
        executable = os.path.isfile(path) and os.access(path, os.X_OK)
        if not (runs_code or executable):
            continue
        content = _read_script(path)
        if content is None:
            continue
        seen.add(path)
        yield path, content
        if depth > 1:
            names = re.findall(r"[\w./~${}-]+\.(?:py|sh|bash|zsh|js|mjs|rb|pl|php)\b", content)
            yield from _scripts(" ".join(["bash"] + names), os.path.dirname(path), depth - 1, seen)


class ReachesSecrets(Exception):
    """Raised when a search command's path covers an MCP secrets directory."""


def _strip_free_text(command, cwd):
    """Drops commit messages and search patterns from a single git or grep command.

    Those arguments are text, not actions, so a commit message or a grep pattern
    naming the mock host must not block the command. Any other shape returns the
    command unchanged so every part of it is scanned.

    @return the text to scan and the rule names that do not apply to it
    @throws ReachesSecrets if {@code a grep path is, or contains, an MCP secrets directory}
    """
    cmd = re.sub(r"\"\$\(cat <<-?'?(\w+)'?\n.*?\n\1\n?\s*\)\"", '"MSG"', command, flags=re.S)
    if "$(" in cmd or "`" in cmd:
        return command, set()
    tokens = _tokens(cmd)
    prefix = []
    if len(tokens) >= 3 and tokens[0] == "cd" and tokens[2] == "&&":
        prefix, tokens = tokens[:3], tokens[3:]
    if not tokens or any(t in CONTROL or t in {">", ">>", "<", "&>"} for t in tokens):
        return command, set()
    program = os.path.basename(tokens[0])
    if program == "git":
        args = tokens[1:]
        while args and args[0] in {"-C", "--no-pager"}:
            args = args[2:] if args[0] == "-C" else args[1:]
        if not args or args[0] not in GIT_SAFE:
            return command, set()
        kept, skip = [], False
        text_opts = {"-m", "--message", "-S", "-G", "--grep", "-e"}
        for t in args:
            if skip:
                skip = False
                continue
            if t in text_opts:
                skip = True
                continue
            if any(t.startswith(o + "=") for o in ("--message", "--grep")):
                continue
            kept.append(t)
        if args[0] == "grep":
            kept = _drop_pattern(kept[1:], cwd)
            if kept is None:
                raise ReachesSecrets()
            kept = ["grep"] + kept
        # Git takes file names, not programs, so naming cli.py there runs nothing.
        return " ".join(shlex.quote(t) for t in prefix + ["git"] + kept), {"testbed engine"}
    if program in {"grep", "egrep", "fgrep", "rg"}:
        if any(t.startswith("--pre") for t in tokens):
            return command, set()
        kept = _drop_pattern(tokens[1:], cwd)
        if kept is None:
            raise ReachesSecrets()
        return " ".join(shlex.quote(t) for t in prefix + [tokens[0]] + kept), set()
    return command, set()


VALUE_OPTS = {"-A", "-B", "-C", "-m", "-g", "-t", "-T", "--glob", "--type", "--type-not",
              "--max-count", "--context", "--before-context", "--after-context", "-d", "-D"}


def _drop_pattern(args, cwd):
    """Removes the pattern argument of a grep-like call; None if a path would reach the secrets."""
    kept, pattern_seen, skip, value = [], False, False, False
    for t in args:
        if skip:
            skip = False
            continue
        if value:
            value = False
            kept.append(t)
            continue
        if t in VALUE_OPTS:
            value = True
            kept.append(t)
            continue
        if t in {"-e", "--regexp"}:
            skip, pattern_seen = True, True
            continue
        if t.startswith("-"):
            kept.append(t)
            continue
        if not pattern_seen:
            pattern_seen = True
            continue
        kept.append(t)
    for t in kept:
        if t.startswith("-"):
            continue
        path = os.path.realpath(_resolve(t, cwd))
        if any(s == path or s.startswith(path.rstrip("/") + "/") for s in SECRET_DIRS):
            return None
    if not any(not t.startswith("-") for t in kept):
        if any(s.startswith(os.path.realpath(cwd).rstrip("/") + "/") for s in SECRET_DIRS):
            return None
    return kept


def check(command, cwd=None):
    """Returns a deny reason for a Bash command, or None when it may run.

    @apiNote Pure apart from reading the script files the command would execute.
    """
    cwd = cwd or os.getcwd()
    where = "the command"
    try:
        hit = _scan_text(*_strip_free_text(command, cwd))
    except ReachesSecrets:
        hit = "testbed secret dir", "Search inside the repository instead. " + SECRET_HINT
    if hit is None:
        for path, content in _scripts(command, cwd):
            hit = _scan_text(content)
            if hit:
                where = f"the script {path}"
                break
    if hit is None:
        return None
    name, hint = hit
    return (f"Blocked by the testbed guard: {where} touches the {name}. "
            f"Agents reach the mock server, the testbed engine and MCP secrets only through the "
            f"`testbed` MCP. {hint}")


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
