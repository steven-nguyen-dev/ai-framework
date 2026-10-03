"""The testbed tools as plain functions over a `Config` and a `TestbedClient`, testable without MCP.

Every function returns the JSON envelope: ``{"ok": true, ...}`` or ``{"ok": false, "error": {...}}``.
Expected failures (`ToolError`, `TestbedError`) become the failure envelope; every string in either
envelope is masked, so the token and path key never leave this process.
"""

from __future__ import annotations

import functools
from typing import Any, Callable

from . import engine, sync
from .client import TestbedClient, TestbedError
from .common import Busy, ToolError, ValidationError, mask_value, ok
from .config import Config

_STORE_MODES = ("replace", "append", "merge")
CALL_LOG_LIMIT = 50


def _envelope(fn: Callable[..., dict[str, Any]]) -> Callable[..., dict[str, Any]]:
    @functools.wraps(fn)
    def wrapper(config: Config, *args: Any, **kwargs: Any) -> dict[str, Any]:
        try:
            result = fn(config, *args, **kwargs)
        except ToolError as error:
            result = error.to_dict()
        except TestbedError as error:
            result = {"ok": False, "error": {"code": error.code, "status": error.status,
                                             "message": error.message, "details": error.details}}
        return mask_value(result, config.secrets)

    return wrapper


def client_for(config: Config) -> TestbedClient:
    return TestbedClient(config.host, config.token)


def _lease(config: Config) -> dict[str, Any]:
    return client_for(config).lease_state() or {"held": False}


def _refuse_if_busy(config: Config, action: str) -> None:
    """Raises Busy when a registry run is active or anyone holds the portal lease."""
    active = engine.active_run(config)
    if active:
        raise Busy("%s refused: run %s is active (%s)" % (action, active["run_id"], active["target"]),
                   run_id=active["run_id"])
    state = _lease(config)
    if state.get("held"):
        lease = state.get("lease") or {}
        raise Busy("%s refused: the testbed lease is held by %s (%s) until %s"
                   % (action, lease.get("owner"), lease.get("purpose"), lease.get("expires_at")),
                   lease=lease)


def _plan(config: Config, mock: str) -> sync.MockPlan:
    return sync.MockPlan(config.mocks_root, config.suites_root, mock)


# ---- mock content ----

@_envelope
def mocks_diff(config: Config, mock: str) -> dict[str, Any]:
    return ok(**sync.mocks_diff(client_for(config), _plan(config, mock)))


@_envelope
def mocks_push(config: Config, mock: str, dry_run: bool = False) -> dict[str, Any]:
    plan = _plan(config, mock)
    if not dry_run:
        # A push restarts the mock under a running suite.
        _refuse_if_busy(config, "mocks_push")
    return ok(**sync.mocks_push(client_for(config), plan, dry_run=dry_run))


@_envelope
def mocks_rollback(config: Config, mock: str) -> dict[str, Any]:
    _refuse_if_busy(config, "mocks_rollback")
    client = client_for(config)
    with client.hold_lease(sync.lease_owner(), "mcp mocks rollback %s" % mock):
        result = client.rollback(mock)
    return ok(result=result)


@_envelope
def mocks_status(config: Config, mock: str | None = None) -> dict[str, Any]:
    client = client_for(config)
    servers = client.servers() or []
    if mock is None:
        return ok(mocks=[{k: s.get(k) for k in ("key", "content_path", "status", "pushed")} for s in servers])
    server = sync.known_mock(client, mock)
    if server is None:
        raise ToolError("unknown mock %r" % mock, known=[s.get("key") for s in servers])
    try:
        health = client.health(server["key"])
    except TestbedError as error:
        health = {"ok": False, "error": error.code}
    return ok(mock=server, health=health)


# ---- mock runtime ----

@_envelope
def lease_status(config: Config) -> dict[str, Any]:
    return ok(lease=_lease(config), active_run=(engine.active_run(config) or {}).get("run_id"))


@_envelope
def stores_get(config: Config, mock: str, name: str | None = None) -> dict[str, Any]:
    client = client_for(config)
    if name:
        return ok(store=name, value=client.get_store(mock, name))
    return ok(stores=client.list_stores(mock))


@_envelope
def stores_put(config: Config, mock: str, name: str, value: Any, mode: str = "replace") -> dict[str, Any]:
    if mode not in _STORE_MODES:
        raise ValidationError("mode must be one of %s" % ", ".join(_STORE_MODES))
    client_for(config).put_store(mock, name, value, mode)
    return ok(store=name, mode=mode)


@_envelope
def reset(config: Config, mock: str, stores: list[str] | None = None, log: bool = False,
          files: bool = False) -> dict[str, Any]:
    return ok(result=client_for(config).reset(mock, stores=stores, log=log, files=files))


@_envelope
def call_log(config: Config, mock: str, after_seq: int | None = None, since: str | None = None,
             limit: int = CALL_LOG_LIMIT) -> dict[str, Any]:
    log = client_for(config).log_data(mock, after_seq=after_seq, since=since) or {}
    entries = log.get("entries") or []
    limit = max(1, min(int(limit), 500))
    return ok(mock=mock, last_seq=log.get("last_seq"), server_time=log.get("server_time"),
              total=len(entries), entries=entries[-limit:])


# ---- engine, offline ----

def _items(config: Config, items: list[str] | str) -> list[str]:
    values = [items] if isinstance(items, str) else list(items or [])
    if not values:
        raise ValidationError("give at least one case file or suite folder")
    return [engine.resolve(config, item) for item in values]


def _offline(config: Config, args: list[str]) -> dict[str, Any]:
    result = engine.run_offline(config, args)
    return ok(passed=result["exit_code"] == 0, **result)


@_envelope
def suite_validate(config: Config, items: list[str] | str) -> dict[str, Any]:
    return _offline(config, [*_items(config, items), "--validate"])


@_envelope
def suite_lint(config: Config, suite_dirs: list[str] | str) -> dict[str, Any]:
    return _offline(config, ["--lint", *_items(config, suite_dirs)])


@_envelope
def suite_list(config: Config, items: list[str] | str, markers: str | None = None) -> dict[str, Any]:
    args = [*_items(config, items), "--list"]
    if markers:
        args += ["-m", markers]
    return _offline(config, args)


@_envelope
def suite_judge(config: Config, case_file: str, run_dir: str, cases: list[str] | None = None) -> dict[str, Any]:
    args = [engine.resolve(config, case_file), *(cases or []), "--judge", engine.resolve(config, run_dir)]
    return _offline(config, args)


# ---- engine, live ----

@_envelope
def run_start(config: Config, target: str, cases: list[str] | None = None, markers: str | None = None,
              fast: bool = False) -> dict[str, Any]:
    if not config.token:
        raise ToolError("TESTBED_API_TOKEN is not set (~/.mcp/.testbed.env)")
    resolved = engine.resolve(config, target)
    _refuse_if_busy(config, "run_start")
    args = [resolved, *(cases or [])]
    if markers:
        args += ["-m", markers]
    if fast:
        args.append("--fast")
    record = engine.start_run(config, args, target)
    return ok(run_id=record["run_id"], pid=record["pid"], target=target,
              hint="poll run_status(run_id); the engine exits 3 when blocked (lease or preflight)")


@_envelope
def run_status(config: Config, run_id: str, tail: int = 40) -> dict[str, Any]:
    record = engine.load_run(config, run_id)
    status = {k: record.get(k) for k in ("run_id", "target", "state", "exit_code", "started", "run_dir")}
    if record.get("run_dir"):
        results = engine.read_results(record["run_dir"])
        status["summary"] = results.get("summary")
        status["finished"] = (results.get("run") or {}).get("finished")
    status["output_tail"] = engine.output_tail(config, run_id, max(0, min(int(tail), 400)))
    return ok(**status)


@_envelope
def run_result(config: Config, run_id: str) -> dict[str, Any]:
    record = engine.load_run(config, run_id)
    if not record.get("run_dir"):
        raise ToolError("run %s has no run folder (%s); see run_status output" % (run_id, record["state"]),
                        state=record["state"], exit_code=record.get("exit_code"))
    return ok(run_id=run_id, state=record["state"], exit_code=record.get("exit_code"),
              **engine.read_results(record["run_dir"]))


@_envelope
def run_list(config: Config, limit: int = 20) -> dict[str, Any]:
    runs = engine.list_runs(config)[: max(1, int(limit))]
    return ok(runs=[{k: r.get(k) for k in ("run_id", "target", "state", "exit_code", "started", "run_dir")}
                    for r in runs])


@_envelope
def run_stop(config: Config, run_id: str) -> dict[str, Any]:
    engine.stop_run(config, run_id)
    return ok(run_id=run_id, signalled="SIGTERM")

