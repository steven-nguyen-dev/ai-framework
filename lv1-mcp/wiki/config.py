"""Independent configuration loader for the Wiki MCP server."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11 fallback
    import tomli as tomllib  # type: ignore[no-redef]

from .common import ConfigError

DEFAULT_CONFIG_PATH = Path.home() / ".config" / "wiki-mcp" / "config.toml"
FALLBACK_CONFIG_PATH = Path.home() / ".config" / "swarm" / "config.toml"


@dataclass(frozen=True)
class Limits:
    body_max_words: int = 200
    summary_max_words: int = 120


@dataclass(frozen=True)
class EmbedderConfig:
    enabled: bool = True
    url: str = "http://127.0.0.1:11434"
    model: str = "embeddinggemma"
    dimensions: int = 768
    timeout_s: float = 30.0
    batch_size: int = 32


@dataclass(frozen=True)
class WikiConfig:
    inbox_prefix: str = "inbox/"


@dataclass(frozen=True)
class Config:
    postgres_dsn: str = "postgresql://wiki:wiki@127.0.0.1:25432/wiki"
    wiki: WikiConfig = field(default_factory=WikiConfig)
    embedder: EmbedderConfig = field(default_factory=EmbedderConfig)
    limits: Limits = field(default_factory=Limits)


def config_path(path: str | os.PathLike[str] | None = None) -> Path:
    """Returns the config path: explicit path, else WIKI_CONFIG, else default."""
    if path is not None:
        return Path(path)
    env = os.environ.get("WIKI_CONFIG") or os.environ.get("SWARM_CONFIG")
    if env:
        return Path(env)
    if DEFAULT_CONFIG_PATH.exists():
        return DEFAULT_CONFIG_PATH
    if FALLBACK_CONFIG_PATH.exists():
        return FALLBACK_CONFIG_PATH
    return DEFAULT_CONFIG_PATH


def _section(raw: dict[str, Any], name: str, path: Path) -> dict[str, Any]:
    value = raw.get(name, {})
    if not isinstance(value, dict):
        raise ConfigError(f"{path}: [{name}] must be a table", field=name)
    return value


def _str(section: dict[str, Any], key: str, default: str, path: Path) -> str:
    if key not in section:
        return default
    val = section[key]
    if not isinstance(val, str):
        raise ConfigError(f"{path}: {key} must be a string", field=key)
    return val


def _int(section: dict[str, Any], key: str, default: int, path: Path) -> int:
    if key not in section:
        return default
    val = section[key]
    if not isinstance(val, int) or isinstance(val, bool):
        raise ConfigError(f"{path}: {key} must be an integer", field=key)
    return val


def _bool(section: dict[str, Any], key: str, default: bool, path: Path) -> bool:
    if key not in section:
        return default
    val = section[key]
    if not isinstance(val, bool):
        raise ConfigError(f"{path}: {key} must be a boolean", field=key)
    return val


def _number(section: dict[str, Any], key: str, default: float, path: Path) -> float:
    if key not in section:
        return default
    val = section[key]
    if not isinstance(val, (int, float)) or isinstance(val, bool):
        raise ConfigError(f"{path}: {key} must be a number", field=key)
    return float(val)


def load_config(path: str | os.PathLike[str] | None = None) -> Config:
    """Reads the Wiki TOML config, falling back to defaults for anything absent."""
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
    postgres_section = _section(raw, "postgres", target)
    wiki_section = _section(raw, "wiki", target)
    embedder_section = _section(raw, "embedder", target)
    limits_section = _section(raw, "limits", target)

    embedder = EmbedderConfig(
        enabled=_bool(embedder_section, "enabled", defaults.embedder.enabled, target),
        url=_str(embedder_section, "url", defaults.embedder.url, target),
        model=_str(embedder_section, "model", defaults.embedder.model, target),
        dimensions=_int(embedder_section, "dimensions", defaults.embedder.dimensions, target),
        timeout_s=_number(embedder_section, "timeout_s", defaults.embedder.timeout_s, target),
        batch_size=_int(embedder_section, "batch_size", defaults.embedder.batch_size, target),
    )

    wiki = WikiConfig(
        inbox_prefix=_str(wiki_section, "inbox_prefix", defaults.wiki.inbox_prefix, target),
    )

    limits = Limits(
        body_max_words=_int(limits_section, "body_max_words", defaults.limits.body_max_words, target),
        summary_max_words=_int(limits_section, "summary_max_words", defaults.limits.summary_max_words, target),
    )

    return Config(
        postgres_dsn=_str(postgres_section, "dsn", defaults.postgres_dsn, target),
        wiki=wiki,
        embedder=embedder,
        limits=limits,
    )
