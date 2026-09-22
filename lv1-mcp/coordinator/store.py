"""Redis access for the coordinator: keys, TTLs, the task sequence and the session stream.

Every key name, every TTL and every stream shape lives here, in one place, so ``tools.py``
never touches a redis client directly and stays testable against a plain dict-backed fake if
``fakeredis`` is ever unavailable.
"""

from __future__ import annotations

import functools
import json
from typing import Any

from .common import BackendError, NotFoundError, ValidationError, now_iso
from .common import key as qualify
from .config import Config

# CONTRACT §4's key table has exactly one stream, `session`. `store.read`'s stream branch is
# therefore unreachable from `tools.get` once it rejects the `session` key (CONTRACT §4 [ADD]),
# but the branch stays, bounded, for a caller that reaches `TaskStore.read` directly - the same
# 500-entry ceiling `session_log` clamps to, so nothing that calls this method can pull an
# unbounded stream into memory.
_STREAM_READ_MAX = 500


def make_redis_client(config: Config) -> Any:
    """Builds the redis client the server uses, from ``config.redis_url``.

    Imports ``redis`` lazily so ``store.py`` still imports with ``redis`` absent - only the
    server path (or a caller that actually wants a live connection) needs the dependency
    installed. A test builds a ``TaskStore`` directly around ``fakeredis.FakeRedis`` instead
    of calling this.

    Sets both ``socket_connect_timeout`` and ``socket_timeout`` to 5 seconds. This is a
    loopback-only, single-user deployment (CONTRACT §1: Redis lives on 127.0.0.1), so 5s is
    generous for any real round trip; it is also short enough that a backend which accepts the
    TCP connection and never answers surfaces as a ``backend`` envelope well inside one MCP
    call instead of wedging the stdio server (CONTRACT §3, §5's adapter rule).
    """
    import redis

    return redis.Redis.from_url(
        config.redis_url,
        decode_responses=True,
        socket_connect_timeout=5.0,
        socket_timeout=5.0,
    )


def _reraise_as_backend(method: Any) -> Any:
    """Wraps a `TaskStore` method so any `redis.RedisError` it raises becomes `BackendError`.

    CONTRACT §3 (amended): "a dead backend is an envelope, not an exception." Every method that
    touches `self._r` goes through this decorator, so `tools.py`'s existing `except ToolError`
    boundary catches a dropped connection exactly like any other domain failure, with no
    special-casing at the call site. Imports `redis` lazily, matching `make_redis_client`, so a
    `TaskStore` built directly around `fakeredis.FakeRedis` never requires the real package
    merely to be imported - only to be raised, which only a real `redis.RedisError` does.
    """

    @functools.wraps(method)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        """Calls the wrapped method; converts `redis.RedisError` to `BackendError`."""
        import redis

        try:
            return method(*args, **kwargs)
        except redis.RedisError as exc:
            raise BackendError(str(exc), backend="redis") from exc

    return wrapper


class TaskStore:
    """Redis-backed storage for one coordinator session, prefix ``swarm:<session-id>:``.

    @param client a redis client with ``decode_responses=True``; constructor-injected so a
        test passes ``fakeredis.FakeRedis`` and the store never constructs its own connection.
    @param config supplies ``limits.ttl_seconds``; the store reads no other field.
    """

    def __init__(self, client: Any, config: Config) -> None:
        """Stores the client and config for later calls; opens no connection of its own."""
        self._r = client
        self._config = config

    def full(self, short: str) -> str:
        """Qualifies a short key (``task:T7``) with this session's ``swarm:<sid>:`` prefix."""
        return qualify(short)

    # -- roster ----------------------------------------------------------------

    @_reraise_as_backend
    def ensure_roster(self, roster_json: str | None) -> None:
        """Seeds the ``roster`` hash from ``SWARM_ROSTER`` the first time it is absent.

        A no-op once the hash exists, even if ``SWARM_ROSTER`` later changes - the doc names
        the roster "written once at swarm start" and this is that writer (CONTRACT §1). Also
        a no-op when the variable is unset: an empty roster is valid and means every tool
        skips target validation.

        @raises ValidationError if ``SWARM_ROSTER`` is set but is not a JSON object - a bad
            launcher config must surface, not crash the first tool call.
        """
        roster_key = self.full("roster")
        if self._r.exists(roster_key):
            return
        if not roster_json:
            return
        try:
            parsed = json.loads(roster_json)
        except json.JSONDecodeError as exc:
            raise ValidationError(
                "SWARM_ROSTER is not valid JSON.",
                field="SWARM_ROSTER",
                limit="JSON object",
                actual=roster_json,
            ) from exc
        if not isinstance(parsed, dict):
            raise ValidationError(
                "SWARM_ROSTER must be a JSON object: pane name -> {model, tier}.",
                field="SWARM_ROSTER",
                limit="JSON object",
                actual=type(parsed).__name__,
            )
        if not parsed:
            return
        mapping = {pane: json.dumps(entry) for pane, entry in parsed.items()}
        self._r.hset(roster_key, mapping=mapping)
        self.touch_ttls(roster_key)

    @_reraise_as_backend
    def roster(self) -> dict[str, Any]:
        """Returns the roster: pane name -> parsed ``{model, tier, token_limit}``.

        Empty when the hash is absent or ``SWARM_ROSTER`` was never set - callers treat an
        empty roster as "no roster to validate against", never as a fetch failure.
        """
        raw = self._r.hgetall(self.full("roster"))
        parsed: dict[str, Any] = {}
        for pane, value in raw.items():
            try:
                parsed[pane] = json.loads(value)
            except json.JSONDecodeError:
                parsed[pane] = value
        return parsed

    # -- ttl ---------------------------------------------------------------

    @_reraise_as_backend
    def touch_ttls(self, *keys: str) -> None:
        """Refreshes the TTL clock: the given keys, plus ``session``, ``roster``, ``taskseq``.

        ``EXPIRE`` on an absent key is a no-op in Redis, so calling this before those three
        keys exist is harmless. One clock, 7 days, no exceptions, on every write regardless of
        which key it touched (CONTRACT §4).
        """
        ttl = self._config.limits.ttl_seconds
        targets = set(keys) | {self.full("session"), self.full("roster"), self.full("taskseq")}
        for target in targets:
            self._r.expire(target, ttl)

    # -- tasks and results ---------------------------------------------------------------

    @_reraise_as_backend
    def next_task_id(self) -> str:
        """Allocates the next id via ``INCR taskseq``. Ids run ``T1``, ``T2``, ... per session."""
        seq_key = self.full("taskseq")
        n = self._r.incr(seq_key)
        self._r.expire(seq_key, self._config.limits.ttl_seconds)
        return f"T{n}"

    @_reraise_as_backend
    def task_exists(self, task_id: str) -> bool:
        """Reports whether ``task:<task_id>`` exists in this session."""
        return bool(self._r.exists(self.full(f"task:{task_id}")))

    @_reraise_as_backend
    def write_task(self, task_id: str, target: str, brief: str, wiki_refs: list[str]) -> str:
        """Writes ``task:<task_id>`` and refreshes its TTL. Returns the qualified key written."""
        task_key = self.full(f"task:{task_id}")
        self._r.hset(
            task_key,
            mapping={
                "target": target,
                "brief": brief,
                "wiki_refs": json.dumps(wiki_refs),
                "created": now_iso(),
            },
        )
        self.touch_ttls(task_key)
        return task_key

    @_reraise_as_backend
    def write_result(self, task_id: str, status: str, summary: str, result: str | None) -> str:
        """Writes ``result:<task_id>`` and refreshes its TTL. Returns the qualified key written.

        Overwrites unconditionally, including over an already-completed task - `complete` in
        `tools.py` relies on that: a worker retrying after `prompt_failed` must be able to call
        this again with the exact same arguments and land the same result, never a rejection.

        @param result stored as ``""`` when absent - a Redis hash field cannot hold ``None``.
        """
        result_key = self.full(f"result:{task_id}")
        self._r.hset(
            result_key,
            mapping={
                "status": status,
                "summary": summary,
                "result": result or "",
                "finished": now_iso(),
            },
        )
        self.touch_ttls(result_key)
        return result_key

    @_reraise_as_backend
    def existing_result(self, task_id: str) -> tuple[str, str, str] | None:
        """Returns the stored ``(status, summary, result)`` for ``task_id``, or ``None`` if absent.

        `complete` reads this before overwriting, to tell a worker's byte-identical retry
        (after a `prompt_failed`) apart from a genuine correction of an earlier completion -
        see `tools.complete`'s docstring for what that distinction decides.
        """
        raw = self._r.hgetall(self.full(f"result:{task_id}"))
        if not raw:
            return None
        return raw.get("status", ""), raw.get("summary", ""), raw.get("result", "")

    # -- session stream ---------------------------------------------------------------

    @_reraise_as_backend
    def append_session_event(self, fields: dict[str, str]) -> str:
        """Appends one entry to the session stream and refreshes its TTL. Returns its key."""
        session_key = self.full("session")
        self._r.xadd(session_key, fields)
        self.touch_ttls(session_key)
        return session_key

    @_reraise_as_backend
    def session_entries(self, limit: int) -> list[dict[str, Any]]:
        """Returns up to ``limit`` session entries, oldest-first.

        Reads with ``XREVRANGE ... COUNT limit`` - newest-first, bounded without scanning the
        whole stream - then reverses in Python, because ``session_log``'s contract is
        oldest-first (CONTRACT §4). An absent stream returns ``[]``, not an error.
        """
        raw = self._r.xrevrange(self.full("session"), "+", "-", count=limit)
        entries = [{"id": entry_id, **fields} for entry_id, fields in raw]
        entries.reverse()
        return entries

    # -- generic get/put ---------------------------------------------------------------

    @_reraise_as_backend
    def read(self, short_key: str) -> tuple[str, Any]:
        """Reads any key in this session's namespace by its short form.

        Reads ``TYPE`` once and dispatches on it, instead of ``EXISTS`` then ``TYPE`` then the
        value read: fewer round trips, and a narrower TOCTOU window against a key that expires
        mid-call. Whatever residual window remains is closed by treating an empty/missing
        result for a type that ``TYPE`` reported as live - the key expired between calls - as
        ``not_found`` rather than as an empty value.

        @return ``(redis_type, value)``: ``value`` is a ``dict`` for a hash, a ``str`` for a
            string, a list of ``dict`` (oldest-first, ``id`` included, capped at
            `_STREAM_READ_MAX` entries) for a stream.
        @raises NotFoundError if the key does not exist, or expires during the read.
        @raises ValidationError if the key holds a redis type this store does not expose
            (list, set, zset, ...) - a key that demonstrably exists must never be reported as
            missing.
        """
        full_key = self.full(short_key)
        redis_type = self._r.type(full_key)
        if redis_type in (None, "none"):
            raise NotFoundError(f"No key '{short_key}' in this session.", what=short_key)
        if redis_type == "hash":
            value = self._r.hgetall(full_key)
            if not value:
                raise NotFoundError(f"No key '{short_key}' in this session.", what=short_key)
            return "hash", value
        if redis_type == "string":
            value = self._r.get(full_key)
            if value is None:
                raise NotFoundError(f"No key '{short_key}' in this session.", what=short_key)
            return "string", value
        if redis_type == "stream":
            raw = self._r.xrange(full_key, "-", "+", count=_STREAM_READ_MAX)
            if not raw:
                raise NotFoundError(f"No key '{short_key}' in this session.", what=short_key)
            return "stream", [{"id": entry_id, **fields} for entry_id, fields in raw]
        raise ValidationError(
            f"'{short_key}' is a redis {redis_type}, which get() does not expose.",
            field="key",
            limit=["hash", "string", "stream"],
            actual=redis_type,
        )

    @_reraise_as_backend
    def write_scratch(self, name: str, value: str) -> tuple[str, int]:
        """Writes ``scratch:<name>`` and refreshes its TTL. Returns ``(key, byte length)``."""
        scratch_key = self.full(f"scratch:{name}")
        byte_len = len(value.encode("utf-8"))
        self._r.set(scratch_key, value)
        self.touch_ttls(scratch_key)
        return scratch_key, byte_len
