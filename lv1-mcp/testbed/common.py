"""Shared errors, envelopes and secret masking for the testbed MCP server."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any


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


class Busy(ToolError):
    """A live run is active or another runner holds the portal lease."""

    code = "busy"


def ok(**fields: Any) -> dict[str, Any]:
    """Returns the success envelope carrying ``fields``."""
    result: dict[str, Any] = {"ok": True}
    result.update(fields)
    return result


def now_iso() -> str:
    """Returns the current UTC time as ISO-8601 with a ``Z`` suffix."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


_KEY_SEGMENT = re.compile(r"(\\?/)k(\\?/)[^/\\\s\"']+(\\?/)")
_KEY_ENCODED = re.compile(r"%2[Ff]k%2[Ff][^%/\s\"']+%2[Ff]")
_SECRET_HEADERS = r"x-testbed-gate|x-auth-token|x-testbed-lease"
# HAR header entries carry the secret as {"name": ..., "value": ...} in either key order; the
# session cookie appears the same way in HAR `cookies`.
_SECRET_NAMES = _SECRET_HEADERS + "|testbed_session"
_HEADER_NAME_VALUE = re.compile(
    r'("name"\s*:\s*"(?:%s)"\s*,\s*"value"\s*:\s*)"(?:[^"\\]|\\.)*"' % _SECRET_NAMES, re.I)
_HEADER_VALUE_NAME = re.compile(
    r'("value"\s*:\s*)"(?:[^"\\]|\\.)*"(\s*,\s*"name"\s*:\s*"(?:%s)")' % _SECRET_NAMES, re.I)
_HEADER_DICT = re.compile(r'("(?:%s)"\s*:\s*)"(?:[^"\\]|\\.)*"' % _SECRET_HEADERS, re.I)
_HEADER_LINE = re.compile(r"((?:%s)\s*:\s*)[^\s'\"\\,}]+" % _SECRET_HEADERS, re.I)
_SESSION_COOKIE = re.compile(r"(testbed_session=)[^;\s\"'\\]+")


def mask(text: str, secrets: tuple[str, ...] = ()) -> str:
    """Returns ``text`` with ``/k/<key>/`` segments, secret headers and the given literals replaced."""
    text = _KEY_SEGMENT.sub(lambda m: "%sk%s<redacted>%s" % m.groups(), text)
    text = _KEY_ENCODED.sub("%2Fk%2F<redacted>%2F", text)
    text = _HEADER_NAME_VALUE.sub(r'\1"<redacted>"', text)
    text = _HEADER_VALUE_NAME.sub(r'\1"<redacted>"\2', text)
    text = _HEADER_DICT.sub(r'\1"<redacted>"', text)
    text = _HEADER_LINE.sub(r"\1<redacted>", text)
    text = _SESSION_COOKIE.sub(r"\1<redacted>", text)
    for secret in sorted({s for s in secrets if s}, key=len, reverse=True):
        text = text.replace(secret, "<redacted>")
    return text


def mask_value(value: Any, secrets: tuple[str, ...] = ()) -> Any:
    """Returns ``value`` with :func:`mask` applied to every string inside it, keys included."""
    if isinstance(value, str):
        return mask(value, secrets)
    if isinstance(value, dict):
        return {mask_value(k, secrets): mask_value(v, secrets) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [mask_value(v, secrets) for v in value]
    return value
