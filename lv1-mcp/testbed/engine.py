"""Drives testbed-dev's suite engine (`suite/cli.py`) offline, and live runs in the background.

A live run is started through ``sh -c`` so its exit code is recorded even when this MCP server
restarts mid-run. The engine creates the run folder itself (``<results_root>/<mock>/<suite>/run-*``)
only after it starts, so a run's record sits beside it as three hidden files in the results root:
``.mcp-<run_id>.json`` (run_id, pid, target, args, start time), ``.mcp-<run_id>.log`` (engine output)
and ``.mcp-<run_id>.exit`` (exit code). The run folder is read from the engine's ``results:`` line.
"""

from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from .common import ConfigError, NotFoundError, ValidationError, mask, now_iso
from .config import Config

OFFLINE_TIMEOUT_S = 600
OUTPUT_LIMIT = 60_000
# The engine prints this line once the run folder exists (suite/flow.py).
_RUN_DIR_LINE = re.compile(r"^\s*results:\s*(\S.*?)\s*$", re.M)
# Keys stripped from the child's environment: this server's own names for the secrets. The engine
# gets them under the names it reads (ADMIN_PASSWORD, PATH_KEY), and only on a live run.
_MCP_SECRET_KEYS = ("TESTBED_API_TOKEN", "TESTBED_PATH_KEY", "TESTBED_HOST", "ADMIN_PASSWORD", "PATH_KEY")


def _engine(config: Config) -> tuple[Path, Path]:
    python, cli = config.engine_python, config.testbed_dev / "suite" / "cli.py"
    if not python.exists():
        raise ConfigError("engine venv missing: %s (run testbed-dev/setup.sh)" % python)
    if not cli.exists():
        raise ConfigError("engine missing: %s" % cli)
    return python, cli


def resolve(config: Config, item: str, contained: bool = True) -> str:
    """Returns ``item`` as an absolute path of an existing file or folder.

    Accepts a path relative to testbed-dev, relative to the lv1-servers root (``testbed-dev/...``) or absolute.
    With ``contained``, a path resolving outside testbed-dev (``..``, symlinks included) is rejected; run
    folders live in the data directory, so the judge's ``run_dir`` passes ``contained=False``.
    """
    path = Path(item).expanduser()
    if path.is_absolute():
        candidates = [path]
    else:
        candidates = [config.testbed_dev / path, config.servers_root / path]
    found = next((c for c in candidates if c.exists()), None)
    if found is None:
        raise NotFoundError("no such file or folder: %s" % item, path=str(candidates[0]))
    found = found.resolve()
    if contained and not found.is_relative_to(config.testbed_dev.resolve()):
        raise ValidationError("path resolves outside testbed-dev: %s" % item)
    return str(found)


def child_env(config: Config, live: bool) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k not in _MCP_SECRET_KEYS}
    env["TESTBED_URL"] = config.host
    env["JPLUGER_ROOT"] = str(config.jpluger_root)
    if live:
        env["ADMIN_PASSWORD"] = config.token
        env["PATH_KEY"] = config.path_key
    return env


def run_offline(config: Config, args: list[str]) -> dict[str, Any]:
    """Runs ``cli.py <args>`` to completion without secrets; returns exit code and masked output."""
    python, cli = _engine(config)
    try:
        done = subprocess.run([str(python), str(cli), *args], cwd=str(config.testbed_dev),
                              env=child_env(config, live=False), capture_output=True, text=True,
                              timeout=OFFLINE_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        raise ValidationError("engine did not finish in %d s" % OFFLINE_TIMEOUT_S) from None
    output = mask(done.stdout + done.stderr, config.secrets)
    truncated = len(output) > OUTPUT_LIMIT
    return {"exit_code": done.returncode, "output": output[-OUTPUT_LIMIT:], "truncated": truncated}


# ---- live runs ----

def _record_base(config: Config, run_id: str) -> str:
    """Returns the path prefix of a run's record files, ``<results_root>/.mcp-<run_id>``."""
    if not re.fullmatch(r"[A-Za-z0-9-]{1,64}", run_id):
        raise ValidationError("bad run_id: %r" % run_id)
    return str(config.results_root / (".mcp-" + run_id))


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    # A finished child of this server stays a zombie until reaped; reap it so it reads as gone.
    try:
        reaped, _ = os.waitpid(pid, os.WNOHANG)
        return reaped == 0
    except ChildProcessError:
        return True


def load_run(config: Config, run_id: str) -> dict[str, Any]:
    base = _record_base(config, run_id)
    try:
        record = json.loads(Path(base + ".json").read_text())
    except (OSError, ValueError):
        raise NotFoundError("no run %s under %s" % (run_id, config.results_root), run_id=run_id) from None
    try:
        exit_code = int(Path(base + ".exit").read_text().strip())
    except (OSError, ValueError):
        exit_code = None
    if not record.get("run_dir"):
        match = _RUN_DIR_LINE.search(_read_output(base))
        if match:
            record["run_dir"] = match.group(1)
    if exit_code is not None:
        record["state"], record["exit_code"] = "finished", exit_code
    elif _alive(record["pid"]):
        record["state"] = "running"
    else:
        record["state"] = "lost"  # killed without writing an exit code
    return record


def _read_output(base: str) -> str:
    try:
        return Path(base + ".log").read_text(errors="replace")
    except OSError:
        return ""


def output_tail(config: Config, run_id: str, lines: int = 40) -> str:
    text = _read_output(_record_base(config, run_id))
    return mask("\n".join(text.splitlines()[-lines:]), config.secrets)


def list_runs(config: Config) -> list[dict[str, Any]]:
    if not config.results_root.is_dir():
        return []
    runs = []
    for record in sorted(config.results_root.glob(".mcp-*.json"), reverse=True):
        try:
            runs.append(load_run(config, record.name[len(".mcp-"):-len(".json")]))
        except (NotFoundError, ValidationError):
            continue
    return runs


def active_run(config: Config) -> dict[str, Any] | None:
    return next((r for r in list_runs(config) if r["state"] == "running"), None)


def start_run(config: Config, args: list[str], target: str) -> dict[str, Any]:
    """Starts ``cli.py <args>`` detached with the secrets injected; returns the run record."""
    python, cli = _engine(config)
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
    base = _record_base(config, run_id)
    config.results_root.mkdir(parents=True, mode=0o700, exist_ok=True)
    argv = [str(python), str(cli), *args]
    # The shell outlives this server: it records the engine's exit code for run_status.
    script = '"$@" > "$0.log" 2>&1; echo $? > "$0.exit"'
    process = subprocess.Popen(["sh", "-c", script, base, *argv], cwd=str(config.testbed_dev),
                               env=child_env(config, live=True), stdin=subprocess.DEVNULL,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               start_new_session=True)
    record = {"run_id": run_id, "target": target, "args": args, "pid": process.pid,
              "started": now_iso(), "run_dir": None}
    Path(base + ".json").write_text(json.dumps(record, indent=2))
    return record


def stop_run(config: Config, run_id: str) -> None:
    """SIGTERMs the run's process group; the engine releases the lease on SIGTERM."""
    record = load_run(config, run_id)
    if record["state"] != "running":
        raise ValidationError("run %s is not running (%s)" % (run_id, record["state"]))
    os.killpg(record["pid"], signal.SIGTERM)


def read_results(run_dir: str) -> dict[str, Any]:
    """Returns the per-case verdict table and run.json of an engine run folder."""
    folder = Path(run_dir)
    out: dict[str, Any] = {"run_dir": str(folder)}
    try:
        results = json.loads((folder / "results.json").read_text())
    except (OSError, ValueError):
        results = None
    if results:
        out["name"] = results.get("name")
        out["summary"] = results.get("summary")
        out["evidence"] = results.get("evidence")
        out["cases"] = [{"id": c.get("id"), "verdict": c.get("verdict"), "name": c.get("name"),
                         "detail": c.get("detail")} for c in results.get("cases") or []]
    try:
        out["run"] = json.loads((folder / "run.json").read_text())
    except (OSError, ValueError):
        out["run"] = None
    return out
