"""The six coordinator tools as plain functions over a `TaskStore` - testable without MCP.

Each function is the tool boundary named in CONTRACT.md §3: it catches every `ToolError`
raised beneath it and returns `.to_dict()`, so the function's return value is always the JSON
envelope the tool promises, never a raised domain exception. A bug - anything that is not a
`ToolError` - still propagates, unchanged, per that same rule.
"""

from __future__ import annotations

import os
import re
from typing import Any

from .common import (
    NotFoundError,
    PromptFailed,
    ToolError,
    ValidationError,
    leader_name,
    now_iso,
    ok,
    session_id,
    strip_prefix,
)
from .config import Config

from .prompt import send_prompt
from .store import TaskStore, run_of

_STATUSES = ("done", "failed", "blocked")
_SCRATCH_NAME = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


def _prompt_failed_envelope(exc: PromptFailed, **identity: str) -> dict[str, Any]:
    """Builds the `prompt_failed` envelope with the write's identity repeated at the top level.

    CONTRACT §3 (amended): "On prompt_failed, identity travels at the top level too." `exc`
    already carries `identity` inside `.extra` (the caller built it that way), so `.to_dict()`
    puts it in `error` already; this only adds the same key(s) beside `ok: false`, so `r["id"]`
    (delegate) or `r["task_id"]` (complete) finds the id without reaching into `error` first.
    """
    envelope = exc.to_dict()
    envelope.update(identity)
    return envelope


def _seed_roster(store: TaskStore) -> None:
    """Seeds the roster from `SWARM_ROSTER` on the first tool call that finds it absent.

    Every tool calls this first (CONTRACT §1: "the coordinator seeds the ... hash from it on
    first tool call when the hash is absent" - no single tool is named as the one writer).
    """
    store.ensure_roster(os.environ.get("SWARM_ROSTER"))


def delegate(
    store: TaskStore,
    config: Config,
    target: str,
    brief: str,
    wiki_refs: list[str] | None = None,
) -> dict[str, Any]:
    """Writes `task:<id>`, logs it, then prompts `target`. See CONTRACT.md §4 and §4b.

    Write-then-prompt: the task is written and logged before the prompt runs, and a failed
    prompt does not undo either - the returned envelope names the written id regardless.

    Returns `{ok, id, prompted, delivery}` on success. `prompted` is always `True` here -
    it means only "the prompt command was dispatched", never "the pane received it" (that
    was the bug CONTRACT §4b fixes). `delivery` carries the confirmation: `"confirmed"` when
    Herdr's own JSON said the pane received it, `"unconfirmed"` when the process exited 0
    with nothing `send_prompt` could read as confirmation. A stalled or errored delivery
    never reaches this return - it raises `PromptFailed` and is caught below instead.

    @raises nothing - every ToolError is caught here and returned as the failure envelope.
    """
    try:
        _seed_roster(store)
        roster = store.roster()
        if roster and target not in roster:
            raise ValidationError(
                f"'{target}' is not in the roster. A prompt to an unknown pane is silent loss.",
                field="target",
                limit=sorted(roster),
                actual=target,
            )
        refs = list(wiki_refs) if wiki_refs else []
        task_id = store.next_task_id()
        store.write_task(task_id, target, brief, refs)
        first_line = brief.splitlines()[0] if brief else ""
        store.append_session_event(
            {
                "event": "delegate",
                "task": task_id,
                "target": target,
                "status": "",
                "summary": first_line[:200],
                "at": now_iso(),
            },
            run_of(task_id),
        )
        prompt_text = f'Task {task_id} — call swarm-coordinator.get("task:{task_id}")'
        try:
            delivery = send_prompt(config, target, prompt_text)
        except PromptFailed as exc:
            # The write already happened; carry the id so the envelope "says so" (CONTRACT §3).
            failure = PromptFailed(exc.message, id=task_id, **exc.extra)
            return _prompt_failed_envelope(failure, id=task_id)
        return ok(id=task_id, prompted=True, delivery=delivery.value)
    except ToolError as exc:
        return exc.to_dict()


def complete(
    store: TaskStore,
    config: Config,
    task_id: str,
    status: str,
    summary: str,
    result: str | None = None,
) -> dict[str, Any]:
    """Writes `result:<task_id>`, logs it, then prompts `$SWARM_LEADER`. See CONTRACT.md §4, §4b.

    Same write-then-prompt ordering as `delegate`: a failed prompt leaves the result written.
    Returns `{ok, task_id, prompted, delivery}` on success - see `delegate`'s docstring for
    what `prompted` and `delivery` each mean and do not mean.

    A repeat call for an already-completed `task_id` is never rejected - `result:<task_id>` is
    overwritten unconditionally, because a worker retrying `complete` after a `prompt_failed`
    must be able to resend the exact same arguments and succeed. But the session stream only
    gets a second `complete` entry when `(status, summary, result)` actually differs from what
    is already stored. A byte-identical repeat is that same retry, already logged once; a
    second identical entry would inflate the doc's §9 Test B completion count for one task that
    was, in truth, completed once. A *different* repeat - a worker correcting `blocked` to
    `done`, say - is new information and is logged as its own entry.
    """
    try:
        _seed_roster(store)
        if status not in _STATUSES:
            raise ValidationError(
                f"status must be one of {_STATUSES}.",
                field="status",
                limit=list(_STATUSES),
                actual=status,
            )
        line_count = len(summary.splitlines()) if summary else 0
        if line_count > config.limits.complete_summary_max_lines:
            raise ValidationError(
                "summary exceeds complete_summary_max_lines. Truncation is not the fix - "
                "use put() for anything longer.",
                field="summary",
                limit=config.limits.complete_summary_max_lines,
                actual=line_count,
            )
        if not store.task_exists(task_id):
            raise NotFoundError(f"No task '{task_id}' in this session.", what=f"task:{task_id}")

        previous = store.existing_result(task_id)
        is_identical_repeat = previous == (status, summary, result or "")

        store.write_result(task_id, status, summary, result)
        leader = leader_name()
        if not is_identical_repeat:
            store.append_session_event(
                {
                    "event": "complete",
                    "task": task_id,
                    "target": leader,
                    "status": status,
                    "summary": summary,
                    "at": now_iso(),
                },
                run_of(task_id),
            )
        # [ADD] CONTRACT §4: non-"done" statuses read "<status>", never "done", in the prompt.
        prompt_text = f'Task {task_id} {status} — call swarm-coordinator.get("result:{task_id}")'
        try:
            delivery = send_prompt(config, leader, prompt_text)
        except PromptFailed as exc:
            failure = PromptFailed(exc.message, task_id=task_id, **exc.extra)
            return _prompt_failed_envelope(failure, task_id=task_id)
        return ok(task_id=task_id, prompted=True, delivery=delivery.value)
    except ToolError as exc:
        return exc.to_dict()


def get(store: TaskStore, key: str) -> dict[str, Any]:
    """Reads any key in the session namespace by its short or fully qualified form.

    See CONTRACT.md §4: `value` is an object for a hash, a string for a string.

    CONTRACT §4 (amended): rejects `session` with `validation`, naming `session_log` as the
    tool to use. `session` is the one key with no bound on its length; a generic reader that
    returns the whole stream undoes the exact clamp `session_log` enforces.
    """
    try:
        _seed_roster(store)
        short = strip_prefix(key)
        if short == "session" or short.startswith("session:"):
            raise ValidationError(
                f'get("{short}") would return a whole stream, unbounded. Use session_log() '
                "instead - it clamps to 1..500 entries.",
                field="key",
                limit="session_log",
                actual=short,
            )
        redis_type, value = store.read(short)
        return ok(key=short, type=redis_type, value=value)
    except ToolError as exc:
        return exc.to_dict()


def put(store: TaskStore, config: Config, key: str, value: str) -> dict[str, Any]:
    """Writes `scratch:<name>`. `key` may be a bare name or a `scratch:`-prefixed one.

    See CONTRACT.md §4: `name` must match `[A-Za-z0-9._-]{1,128}`; the value is capped at
    `scratch_max_bytes` UTF-8 bytes.
    """
    try:
        _seed_roster(store)
        short = strip_prefix(key)
        name = short[len("scratch:") :] if short.startswith("scratch:") else short
        if not _SCRATCH_NAME.match(name):
            raise ValidationError(
                f"'{name}' is not a valid scratch name.",
                field="name",
                limit=_SCRATCH_NAME.pattern,
                actual=name,
            )
        byte_len = len(value.encode("utf-8"))
        if byte_len > config.limits.scratch_max_bytes:
            raise ValidationError(
                "value exceeds scratch_max_bytes.",
                field="value",
                limit=config.limits.scratch_max_bytes,
                actual=byte_len,
            )
        scratch_key, written_bytes = store.write_scratch(name, value)
        return ok(key=f"scratch:{name}", bytes=written_bytes)
    except ToolError as exc:
        return exc.to_dict()


def session_log(store: TaskStore, limit: int = 20, run: int | None = None) -> dict[str, Any]:
    """Returns the roster plus the last `limit` entries of one run, oldest-first.

    See CONTRACT.md §4: `limit` clamps to 1..500; an absent stream returns `entries: []`, not
    an error - a fresh session is not a failure. `run` defaults to the current run; pass an
    earlier number to reconcile a late completion from that run.
    """
    try:
        _seed_roster(store)
        clamped = min(max(int(limit), 1), 500)
        current = store.current_run()
        shown = current if run is None else int(run)
        if shown < 1 or shown > current:
            raise ValidationError(
                f"run must be between 1 and the current run, {current}.",
                field="run",
                limit=[1, current],
                actual=shown,
            )
        return ok(
            session_id=session_id(),
            leader=leader_name(),
            run=shown,
            current_run=current,
            roster=store.roster(),
            entries=store.session_entries(clamped, shown),
        )
    except ToolError as exc:
        return exc.to_dict()


def start_run(store: TaskStore) -> dict[str, Any]:
    """Opens a new run for a new objective: task ids restart at `R<run>-T1`.

    Returns `{ok, run, previous_run, open_tasks}`. `open_tasks` lists the previous run's
    delegates with no complete - a warning, never a refusal: those tasks keep their ids, and a
    late `complete` for one still lands on it. `previous_run` is `null` on a session's first run.
    """
    try:
        _seed_roster(store)
        run = store.start_run()
        previous = run - 1 if run > 1 else None
        open_tasks = store.open_tasks(previous) if previous else []
        return ok(run=run, previous_run=previous, open_tasks=open_tasks)
    except ToolError as exc:
        return exc.to_dict()
