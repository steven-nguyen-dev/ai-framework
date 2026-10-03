"""Environment-only configuration. `launch.sh` sources ``~/.mcp/.testbed.env`` before the server starts."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_HOST = "https://test.concavoi.com"
DEFAULT_SERVERS_ROOT = Path.home() / "Projects" / "lv1-servers"
DEFAULT_JPLUGER_ROOT = Path.home() / "Projects" / "jpluger-family" / "one" / "JPluger"
DEFAULT_RESULTS = Path.home() / ".local" / "share" / "lv1-testbed-dev" / "results"


@dataclass(frozen=True)
class Config:
    host: str
    # Never returned by any tool; masked in every string a tool returns.
    token: str
    path_key: str
    servers_root: Path
    jpluger_root: Path
    results_root: Path

    @property
    def testbed_dev(self) -> Path:
        return self.servers_root / "testbed-dev"

    @property
    def mocks_root(self) -> Path:
        return self.servers_root / "cloud-servers" / "mock-api" / "mocks"

    @property
    def suites_root(self) -> Path:
        return self.testbed_dev / "suites"

    @property
    def engine_python(self) -> Path:
        return self.testbed_dev / ".venv" / "bin" / "python"

    @property
    def secrets(self) -> tuple[str, ...]:
        return tuple(s for s in (self.token, self.path_key) if s)

    def describe(self) -> dict[str, object]:
        """Returns the config without its secrets: only whether each is set."""
        return {
            "host": self.host,
            "token_set": bool(self.token),
            "path_key_set": bool(self.path_key),
            "servers_root": str(self.servers_root),
            "jpluger_root": str(self.jpluger_root),
            "results_root": str(self.results_root),
        }


def load_config(env: dict[str, str] | None = None) -> Config:
    """Reads ``TESTBED_HOST``, ``TESTBED_API_TOKEN``, ``TESTBED_PATH_KEY`` and the path overrides."""
    env = os.environ if env is None else env

    def path(name: str, default: Path) -> Path:
        value = env.get(name, "").strip()
        return Path(value).expanduser() if value else default

    # Same resolution as the engine (suite/runfolder/runinfo.py results_root).
    if env.get("TESTBED_RESULTS", "").strip():
        results = Path(env["TESTBED_RESULTS"].strip()).expanduser()
    elif env.get("TESTBED_DEV_DATA", "").strip():
        results = Path(env["TESTBED_DEV_DATA"].strip()).expanduser() / "results"
    else:
        results = DEFAULT_RESULTS

    return Config(
        host=(env.get("TESTBED_HOST", "").strip() or DEFAULT_HOST).rstrip("/"),
        token=env.get("TESTBED_API_TOKEN", ""),
        path_key=env.get("TESTBED_PATH_KEY", ""),
        servers_root=path("LV1_SERVERS_ROOT", DEFAULT_SERVERS_ROOT),
        jpluger_root=path("JPLUGER_ROOT", DEFAULT_JPLUGER_ROOT),
        results_root=results.absolute(),
    )
