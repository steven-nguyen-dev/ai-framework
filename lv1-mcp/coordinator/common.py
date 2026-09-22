"""Shared errors, session identity and text utilities for swarm coordinator."""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from typing import Any

PREFIX = "swarm"


class ToolError(Exception):
    """Base for every expected domain failure. Serialises to the error envelope."""

    code = "error"

    def __init__(self, message: str, **extra: Any) -> None:
        super().__init__(message)
        self.message = message
        self.extra = extra

    def to_dict(self) -> dict[str, Any]:
        """Returns the failure envelope: ``{"ok": False, "error": {...}}``."""
        error: dict[str, Any] = {"code": self.code, "message": self.message}
        error.update(self.extra)
        return {"ok": False, "error": error}


class ConfigError(ToolError):
    code = "config"


class EnvError(ToolError):
    code = "env_missing"

    def __init__(self, variable: str) -> None:
        super().__init__(
            f"{variable} is not set. The launcher exports it before the pane starts.",
            variable=variable,
        )


class NamespaceError(ToolError):
    code = "namespace"


class ValidationError(ToolError):
    code = "validation"


class NotFoundError(ToolError):
    code = "not_found"


class VersionConflict(ToolError):
    code = "version_conflict"


class PromptFailed(ToolError):
    code = "prompt_failed"


class BackendError(ToolError):
    code = "backend"


def ok(**fields: Any) -> dict[str, Any]:
    """Returns the success envelope carrying ``fields``."""
    result: dict[str, Any] = {"ok": True}
    result.update(fields)
    return result


def count_words(text: str) -> int:
    """Counts whitespace-separated words."""
    return len(text.split())


def now_iso() -> str:
    """Returns the current UTC time as ISO-8601 with a ``Z`` suffix."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


_RESOLVED_HERDR_LEADERS: dict[str, str] = {}
_RESOLVED_HERDR_PANES: dict[str, str] = {}


def _resolve_herdr_leader(tab_id: str) -> str | None:
    if tab_id in _RESOLVED_HERDR_LEADERS:
        return _RESOLVED_HERDR_LEADERS[tab_id]
    try:
        res = subprocess.run(
            ["herdr", "pane", "list"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        if res.returncode == 0:
            panes = json.loads(res.stdout).get("result", {}).get("panes", [])
            for p in panes:
                if p.get("tab_id") == tab_id:
                    lbl = (p.get("label") or "").strip()
                    if "leader" in lbl.lower():
                        _RESOLVED_HERDR_LEADERS[tab_id] = lbl
                        return lbl
    except Exception:
        pass
    return None


def _resolve_herdr_pane_name(pane_id: str) -> str | None:
    if pane_id in _RESOLVED_HERDR_PANES:
        return _RESOLVED_HERDR_PANES[pane_id]
    try:
        res = subprocess.run(
            ["herdr", "pane", "get", pane_id],
            capture_output=True,
            text=True,
            timeout=3,
        )
        if res.returncode == 0:
            pane = json.loads(res.stdout).get("result", {}).get("pane", {})
            lbl = (pane.get("label") or "").strip()
            if lbl:
                _RESOLVED_HERDR_PANES[pane_id] = lbl
                return lbl
    except Exception:
        pass
    return None


def session_id() -> str:
    """Returns ``SWARM_SESSION_ID``, falling back to ``tab-<tab_id>`` from ``HERDR_TAB_ID``.

    @raises EnvError if neither variable is set.
    """
    value = os.environ.get("SWARM_SESSION_ID", "").strip()
    if value:
        return value
    tab_id = os.environ.get("HERDR_TAB_ID", "").strip()
    if tab_id:
        return f"tab-{tab_id.replace(':', '-')}"
    raise EnvError("SWARM_SESSION_ID")


def leader_name() -> str:
    """Returns ``SWARM_LEADER`` - the pane ``complete`` prompts.

    Falls back to resolving the leader pane in ``HERDR_TAB_ID`` if unset.
    @raises EnvError if neither is available.
    """
    value = os.environ.get("SWARM_LEADER", "").strip()
    if value:
        return value
    tab_id = os.environ.get("HERDR_TAB_ID", "").strip()
    if tab_id:
        resolved = _resolve_herdr_leader(tab_id)
        if resolved:
            return resolved
    raise EnvError("SWARM_LEADER")


def actor() -> str:
    """Returns this pane's name for ``updated_by`` / ``actor``, or ``'user'``. Never raises."""
    value = os.environ.get("SWARM_PANE", "").strip()
    if value:
        return value
    pane_id = os.environ.get("HERDR_PANE_ID", "").strip()
    if pane_id:
        resolved = _resolve_herdr_pane_name(pane_id)
        if resolved:
            return resolved
    return "user"


def namespace() -> str:
    """Returns this session's Redis key prefix, ``swarm:<session-id>:``."""
    return f"{PREFIX}:{session_id()}:"


def key(*parts: str) -> str:
    """Builds a fully qualified Redis key from short parts: ``key("task", "T7")``."""
    return namespace() + ":".join(parts)


def strip_prefix(candidate: str) -> str:
    """Normalises a key to its short form, rejecting another session's namespace.

    Accepts ``task:T7`` and ``swarm:<this-session>:task:T7`` alike.

    @raises NamespaceError if the key carries a different session's prefix.
    """
    cleaned = candidate.strip()
    if not cleaned:
        raise NamespaceError("An empty key names nothing.", key=candidate)
    if not cleaned.startswith(f"{PREFIX}:"):
        return cleaned
    own = namespace()
    if cleaned.startswith(own):
        return cleaned[len(own) :]
    raise NamespaceError(
        "That key belongs to another session. A cross-session read is never silent.",
        key=candidate,
    )
