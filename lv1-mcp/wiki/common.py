"""Standalone shared utilities and errors for the Wiki MCP server."""

from __future__ import annotations

import os
import re
import unicodedata
from typing import Any

_NON_SLUG = re.compile(r"[^\w　-鿿가-힯]+", re.UNICODE)
_DASHES = re.compile(r"-{2,}")


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


class ValidationError(ToolError):
    code = "validation"


class NotFoundError(ToolError):
    code = "not_found"


class VersionConflict(ToolError):
    code = "version_conflict"


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


def slugify(heading: str) -> str:
    """Converts a heading to a section slug: lowercase, hyphenated, CJK preserved."""
    normalised = unicodedata.normalize("NFKC", heading).strip().lower()
    slug = _NON_SLUG.sub("-", normalised)
    slug = _DASHES.sub("-", slug).strip("-")
    return slug or "section"


def first_paragraph(text: str) -> str:
    """Returns the first blank-line-delimited paragraph, whitespace collapsed."""
    for block in re.split(r"\n\s*\n", text.strip()):
        collapsed = " ".join(block.split())
        if collapsed:
            return collapsed
    return ""


def trim_words(text: str, limit: int) -> str:
    """Truncates to at most ``limit`` words, preserving order."""
    words = text.split()
    return " ".join(words[:limit])


def now_iso() -> str:
    """Returns current UTC time formatted as ISO-8601 with Z suffix."""
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def actor() -> str:
    """Returns current actor identity, falling back cleanly to system user."""
    return os.environ.get("WIKI_ACTOR") or os.environ.get("USER") or "user"
