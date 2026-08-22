#!/usr/bin/env python3
"""Copying the mock's live evidence into a run folder, and reading it back to judge a case.

The call log and the state stores are global and stay mutable for as long as the mock is up: the
Clear button on `/log` deletes the log outright, and any second runner's reset empties the stores.
A run that re-fetched them into its own folder on every case mirrored that loss -- run
`20260814-140740` captured its first ten cases correctly, overwrote its own copy with a log someone
had just cleared, and scored ten passing cases `fail`.

So the run folder is append-only. Each capture unions the live evidence with what is already
persisted, and a live file that has shrunk is recorded as an anomaly instead of being allowed to
erase the record. Judge from the run folder, never from the live file.
"""

import collections
import datetime
import json
import os

from .model import Call


# ------------------------------------------------------------------------------ file helpers

def load(path, default=None):
    try:
        with open(path, "r") as handle:
            return json.load(handle)
    except Exception:
        return default


def write_json(path, document):
    """Writes through a temporary file, so a capture interrupted halfway cannot leave truncated
    JSON where the run's only copy of the evidence used to be."""
    temporary = path + ".tmp"
    with open(temporary, "w") as handle:
        json.dump(document, handle, indent=2)
    os.replace(temporary, path)


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _first(run_dir, names, default=None):
    """First of these file names that the run folder actually holds.

    Names change; runs already on disk do not. Reading through a list keeps an older folder
    judgeable after a rename instead of silently reading as `not captured`.
    """
    for name in names:
        document = load(os.path.join(run_dir, name))
        if document is not None:
            return document
    return default


# --------------------------------------------------------------------------------- capturing

def log_key(entry):
    """Identity of one logged call, chosen to survive a log reset.

    `seq` cannot be used: the mock derives it from the file's length, so a cleared log restarts at 1
    and every new entry collides with one already captured. The start timestamp carries
    milliseconds, so it separates even the retry replays of one URL 30 seconds apart.
    """
    request = entry.get("request") or {}
    return (entry.get("at") or entry.get("startedDateTime"),
            request.get("method"), request.get("url"))


def merge_entries(persisted, live, seq_field):
    """Union of both lists in start-time order, renumbered so the persisted file stays consistent."""
    merged, seen = [], set()
    for entry in list(persisted) + list(live):
        key = log_key(entry)
        if key in seen:
            continue
        seen.add(key)
        merged.append(entry)
    merged.sort(key=lambda entry: (entry.get("at") or entry.get("startedDateTime") or ""))
    for index, entry in enumerate(merged, 1):
        entry[seq_field] = index
    return merged


def capture(run_dir, mock, stores=()):
    """Unions the mock's log, its HAR archive and its stores into the run folder.

    Returns the ledger entry for this capture, including whether the live log has shrunk since the
    last one -- which means someone cleared it under the run.
    """
    path = os.path.join(run_dir, "mock-log.json")
    persisted = load(path, {}) or {}
    live = mock.log()

    if live is None:
        record = {"at": now(), "live_entries": None,
                  "accumulated": len(persisted.get("entries") or [])}
    else:
        entries = merge_entries(persisted.get("entries") or [], live.get("entries") or [], "seq")
        write_json(path, {"name": live.get("name") or persisted.get("name"),
                          "host": live.get("host") or persisted.get("host"),
                          "entries": entries})
        record = {"at": now(), "live_entries": len(live.get("entries") or []),
                  "accumulated": len(entries)}

    _capture_har(run_dir, mock)
    _capture_stores(run_dir, mock, stores)

    ledger_path = os.path.join(run_dir, "log-capture.json")
    ledger = load(ledger_path, {}) or {}
    captures = ledger.get("captures") or []
    seen = [c["live_entries"] for c in captures if c.get("live_entries") is not None]
    record["reset_detected"] = bool(seen and record.get("live_entries") is not None
                                    and record["live_entries"] < seen[-1])
    captures.append(record)
    recovered = 0
    if record.get("live_entries") is not None:
        recovered = max(0, record["accumulated"] - record["live_entries"])
    write_json(ledger_path, {"captures": captures,
                             "live_log_cleared_mid_run": any(c.get("reset_detected")
                                                             for c in captures),
                             "entries_only_in_run_folder": recovered})
    return record


def _capture_har(run_dir, mock):
    """The HAR is the same calls in the format DevTools and Postman import, so it is merged the same
    way rather than copied -- a plain copy after a clear would hand someone an empty archive."""
    source = os.path.join(mock.directory, mock.log_file)
    if not os.path.exists(source):
        return
    path = os.path.join(run_dir, mock.log_file)
    persisted = load(path, {}) or {}
    live = load(source, {}) or {}
    entries = merge_entries((persisted.get("log") or {}).get("entries") or [],
                            (live.get("log") or {}).get("entries") or [], "_seq")
    shell = live.get("log") or persisted.get("log") or {}
    write_json(path, {"log": {"version": shell.get("version", "1.2"),
                              "creator": shell.get("creator", {"name": "mock_server",
                                                               "version": "1.0"}),
                              "entries": entries}})


def _store_key(item):
    return json.dumps(item, sort_keys=True) if isinstance(item, (dict, list)) else str(item)


def _capture_stores(run_dir, mock, stores):
    """Stores only grow inside a run, so their union is the whole history -- and a store the mock
    emptied mid-run cannot take the run's record of it down."""
    for name in stores:
        source = os.path.join(mock.directory, name + ".json")
        if not os.path.exists(source):
            continue
        path = os.path.join(run_dir, name + ".json")
        merged, seen = [], set()
        for item in (load(path, []) or []) + (load(source, []) or []):
            key = _store_key(item)
            if key in seen:
                continue
            seen.add(key)
            merged.append(item)
        write_json(path, merged)


# ----------------------------------------------------------------------------------- reading

class CaseEvidence(object):
    """Everything one case produced, in the shape the checks read."""

    def __init__(self, controller, calls, rows, queue_delta, marker_fields):
        self.controller = controller
        self.calls = calls
        self.rows = rows
        self.queue_delta = queue_delta
        self.marker_fields = marker_fields


class RunEvidence(object):
    """A run folder read back: its calls, what the app answered, its rows and its queue depths.

    Read from the folder rather than from the mock, so a suite can be re-judged long after the run
    -- which is what makes an expectation change re-scorable against runs already on disk.
    """

    def __init__(self, run_dir, suite):
        self.run_dir = run_dir
        self.suite = suite
        self.meta = load(os.path.join(run_dir, "meta.json"), {}) or {}
        self.log = load(os.path.join(run_dir, "mock-log.json"), {}) or {}
        self.capture_ledger = load(os.path.join(run_dir, "log-capture.json"), {}) or {}
        self.fired = _first(run_dir, ("controller-responses.json",), []) or []
        self.fired_by_id = {entry["id"]: entry for entry in self.fired}

        self.calls_by_key = collections.defaultdict(list)
        for entry in self.log.get("entries") or []:
            call = Call(entry)
            self.calls_by_key[suite.call_key(call)].append(call)

        self.rows = self._read_rows()
        self.queue_delta = self._read_queue_delta()

    def _read_rows(self):
        """Rows per case key, or None when the database was never captured."""
        if not self.suite.database:
            return None
        path = os.path.join(self.run_dir, self.suite.database.file)
        if not os.path.exists(path):
            return None
        counted = collections.Counter()
        with open(path) as handle:
            for line in list(handle)[1:]:                        # the dump carries a header row
                if line.strip():
                    columns = line.rstrip("\n").split("\t")
                    if len(columns) > self.suite.database.key_column:
                        counted[columns[self.suite.database.key_column]] += 1
        return counted

    def _read_queue_delta(self):
        """Growth per watched queue across the run, or an empty mapping when not captured."""
        if not self.suite.queues:
            return {}
        # `rabbit-*.json` is what runs made before this engine existed are holding, and an
        # expectation change has to be re-scorable against them.
        before = _first(self.run_dir, ("queues-before.json", "rabbit-before.json"))
        after = _first(self.run_dir, ("queues-after.json", "rabbit-after.json"))
        if before is None or after is None:
            return {}
        deltas = {}
        for name in self.suite.queues.watch:
            start = self.suite.queues.depth(before, name)
            end = self.suite.queues.depth(after, name)
            if start is None or end is None:
                continue
            deltas[name] = end - start
        return deltas

    def for_case(self, case):
        calls = collections.defaultdict(list)
        for call in self.calls_by_key.get(case.key, []):
            for group in self.suite.groups:
                if group.matches(call):
                    calls[group.name].append(call)
                    break
        rows = None if self.rows is None else self.rows.get(case.row_key, 0)
        return CaseEvidence(self.fired_by_id.get(case.id), calls, rows, self.queue_delta,
                            self.suite.marker_fields)

    def describe_log(self):
        """States plainly whether the log a verdict rests on is complete.

        A cleared live log used to be invisible: the calls were simply not there and every case that
        made them read as "got 0". It is said here instead, so a run whose evidence was disturbed
        says so on the page rather than looking like a regression.
        """
        entries = len(self.log.get("entries") or [])
        if not entries:
            return "missing"
        if self.capture_ledger.get("live_log_cleared_mid_run"):
            return ("captured, %d call(s) -- the mock's live log was cleared mid-run; %d of these "
                    "survive only in this run folder"
                    % (entries, self.capture_ledger.get("entries_only_in_run_folder", 0)))
        return "captured, %d call(s)" % entries
