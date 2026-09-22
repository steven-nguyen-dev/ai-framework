"""Configuration loader for the Swarm Coordinator MCP server."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore[no-redef]

from .common import ConfigError

DEFAULT_CONFIG_PATH = Path.home() / ".config" / "swarm" / "config.toml"


@dataclass(frozen=True)
class Limits:
    ttl_seconds: int = 604_800
    body_max_words: int = 200
    summary_max_words: int = 120
    complete_summary_max_lines: int = 3
    scratch_max_bytes: int = 16_777_216


@dataclass(frozen=True)
class Config:
    redis_url: str = "redis://127.0.0.1:26379/0"
    prompt_argv: tuple[str, ...] = (
        "herdr",
        "agent",
        "prompt",
        "{pane}",
        "{text}",
        "--wait",
        "--until",
        "working",
        "--timeout",
        "6000",
    )
    prompt_timeout_s: float = 10.0
    limits: Limits = field(default_factory=Limits)


def config_path(path: str | os.PathLike[str] | None = None) -> Path:
    """Returns the config path: explicit path, else SWARM_CONFIG, else default."""
    if path is not None:
        return Path(path)
    env = os.environ.get("SWARM_CONFIG")
    return Path(env) if env else DEFAULT_CONFIG_PATH


def _section(raw: dict[str, Any], name: str, source: Path) -> dict[str, Any]:
    value = raw.get(name, {})
    if not isinstance(value, dict):
        raise ConfigError(f"{source}: [{name}] must be a table", field=name)
    return value


def _str(table: dict[str, Any], key: str, default: str, source: Path) -> str:
    value = table.get(key, default)
    if not isinstance(value, str):
        raise ConfigError(f"{source}: {key} must be a string", field=key)
    return value


def _int(table: dict[str, Any], key: str, default: int, source: Path) -> int:
    value = table.get(key, default)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ConfigError(f"{source}: {key} must be an integer", field=key)
    return value


def _number(table: dict[str, Any], key: str, default: float, source: Path) -> float:
    value = table.get(key, default)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ConfigError(f"{source}: {key} must be numeric", field=key)
    return float(value)


def load_config(path: str | os.PathLike[str] | None = None) -> Config:
    """Reads the TOML config, falling back to defaults for anything absent."""
    target = config_path(path)
    if not target.exists():
        return Config()

    try:
        with target.open("rb") as handle:
            raw: dict[str, Any] = tomllib.load(handle)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"{target} is not valid TOML: {exc}") from exc
    except OSError as exc:
        raise ConfigError(f"{target} could not be read: {exc}") from exc

    defaults = Config()
    redis_section = _section(raw, "redis", target)
    herdr_section = _section(raw, "herdr", target)
    limits_section = _section(raw, "limits", target)

    argv = herdr_section.get("prompt_argv", list(defaults.prompt_argv))
    if not isinstance(argv, list) or not argv or not all(isinstance(part, str) for part in argv):
        raise ConfigError(
            f"{target}: herdr.prompt_argv must be a non-empty list of strings",
            field="herdr.prompt_argv",
        )

    limit_defaults = defaults.limits
    limits = Limits(
        ttl_seconds=_int(limits_section, "ttl_seconds", limit_defaults.ttl_seconds, target),
        body_max_words=_int(
            limits_section, "body_max_words", limit_defaults.body_max_words, target
        ),
        summary_max_words=_int(
            limits_section, "summary_max_words", limit_defaults.summary_max_words, target
        ),
        complete_summary_max_lines=_int(
            limits_section,
            "complete_summary_max_lines",
            limit_defaults.complete_summary_max_lines,
            target,
        ),
        scratch_max_bytes=_int(
            limits_section, "scratch_max_bytes", limit_defaults.scratch_max_bytes, target
        ),
    )

    return Config(
        redis_url=_str(redis_section, "url", defaults.redis_url, target),
        prompt_argv=tuple(argv),
        prompt_timeout_s=_number(
            herdr_section, "prompt_timeout_s", defaults.prompt_timeout_s, target
        ),
        limits=limits,
    )
