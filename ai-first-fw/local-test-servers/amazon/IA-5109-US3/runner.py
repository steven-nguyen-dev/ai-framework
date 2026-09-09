#!/usr/bin/env python3
"""Shared runner for the IA-5109 US3 suites: case registry, checks, mock preflight, results file.

Three suites and one master shared a copy of this machinery each before the rewrite. One copy, four
callers, so a change to the results contract lands in every suite at once.

Paths are resolved from this file: the suites live in `amazon/IA-5109-US3/` while the mock config,
the state directory and `test-results/` all belong to `amazon/`, so nothing here may be reached
relative to the working directory.

Runner contract: `local-test-servers/TESTING.md`.
"""

import atexit
import datetime
import json
import os
import socket
import sys
import threading
import time
from http.server import ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
AMAZON_DIR = os.path.dirname(HERE)
SERVERS_DIR = os.path.dirname(AMAZON_DIR)
OMS_DIR = os.path.join(SERVERS_DIR, "anchanto-oms")

AMAZON_DATA_DIR = os.path.join(AMAZON_DIR, "mock-data")
RESULTS_ROOT = os.path.join(AMAZON_DIR, "test-results")
LOG_FILE = "api-calls.har.json"

AMAZON_HOST = "127.0.0.1"
AMAZON_PORT = 23103
AMAZON_BASE = os.environ.get("BASE", "http://%s:%d" % (AMAZON_HOST, AMAZON_PORT)).rstrip("/")

for _path in (HERE, SERVERS_DIR):
    if _path not in sys.path:
        sys.path.insert(0, _path)


# ===================================================================== Checks


class Checks:
    """One case's expected-against-actual list. A case passes when every check in it passed."""

    def __init__(self):
        self.items = []

    def add(self, label, what, expected, actual):
        self.items.append({
            "label": label,
            "what": what,
            "expected": str(expected),
            "actual": str(actual),
            "ok": str(expected) == str(actual),
        })

    def truthy(self, label, what, actual):
        got = "present" if actual not in (None, "", [], {}) else "missing"
        self.items.append({
            "label": label, "what": what,
            "expected": "present", "actual": got, "ok": got == "present",
        })

    def absent(self, label, what, actual):
        got = "absent" if actual in (None, "", [], {}) else "present (%s)" % actual
        self.items.append({
            "label": label, "what": what,
            "expected": "absent", "actual": got, "ok": got == "absent",
        })

    @property
    def ok(self):
        return all(item["ok"] for item in self.items)


# ===================================================================== Suite


class Suite:
    """One runnable suite: its cases, its results folder, and its own `main`."""

    def __init__(self, suite_id, name, proves, does_not_prove, base_url=None):
        self.id = suite_id
        self.name = name
        # Both are printed and written into results.json. The second is not optional: a green run of
        # a suite that never starts JPluger must not read as evidence that the integration works.
        self.proves = proves
        self.does_not_prove = does_not_prove
        self.base_url = base_url or AMAZON_BASE
        self.cases = []
        self.results = {}
        self.evidence = {"status": "running"}
        self.run_dir = os.path.join(
            RESULTS_ROOT, suite_id,
            "run-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))

    def case(self, case_id, name, given, then, note, fn):
        self.cases.append({
            "id": case_id, "name": name, "given": given,
            "then": then if isinstance(then, list) else [then],
            "note": note, "fn": fn,
        })

    def run_case(self, case):
        checks, calls, detail = Checks(), [], {}
        try:
            case["fn"](checks, calls, detail)
            verdict = "pass" if checks.ok else "fail"
        except Exception as error:  # noqa: BLE001 -- a thrown case is a failed case, never a crash
            checks.add("runner exception", "no unhandled exception", "none", "error: %s" % error)
            verdict = "fail"
        passed = sum(1 for item in checks.items if item["ok"])
        self.results[case["id"]] = {
            "verdict": verdict, "checks": checks.items, "calls": calls, "detail": detail,
            "summary": "%d/%d checks passed" % (passed, len(checks.items)),
        }

    def publish(self, wanted=None):
        cases_out = []
        for case in self.cases:
            entry = {k: case[k] for k in ("id", "name", "given", "then", "note")}
            result = self.results.get(case["id"])
            if result:
                entry.update(result)
            elif wanted and case["id"] not in wanted:
                entry.update({"verdict": "skip", "summary": "skipped (not selected)",
                              "checks": [], "calls": [], "detail": {}})
            else:
                entry.update({"verdict": "pending"})
            cases_out.append(entry)

        done = [c for c in cases_out if c.get("verdict") in ("pass", "fail", "blocked", "skip")]
        document = {
            "name": self.name,
            "suite": self.id,
            "at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "base_url": self.base_url,
            "summary": {verdict: sum(1 for c in done if c["verdict"] == verdict)
                        for verdict in ("pass", "fail", "blocked", "skip")},
            "evidence": dict(self.evidence, proves=self.proves,
                             does_not_prove=self.does_not_prove),
            "cases": cases_out,
        }
        os.makedirs(self.run_dir, exist_ok=True)
        with open(os.path.join(self.run_dir, "results.json"), "w", encoding="utf-8") as handle:
            json.dump(document, handle, indent=2)

    def main(self, argv=None, preflight=None, capture=None):
        argv = list(sys.argv[1:] if argv is None else argv)
        wanted = {arg for arg in argv if not arg.startswith("-")}

        if "--list" in argv:
            print("%s -- %d cases" % (self.name, len(self.cases)))
            for case in self.cases:
                print("  [%s] %s" % (case["id"], case["name"]))
            return 0

        print("\n%s" % self.name)
        print("  proves        : %s" % self.proves)
        print("  does not prove: %s" % self.does_not_prove)

        if preflight:
            preflight()

        to_run = [c for c in self.cases if not wanted or c["id"] in wanted]
        print("\nRunning %d cases...\n" % len(to_run))
        for case in to_run:
            self.run_case(case)
            result = self.results[case["id"]]
            print("  [%s] %s: %s -- %s"
                  % (result["verdict"].upper(), case["id"], case["name"], result["summary"]))

        self.evidence["status"] = "complete"
        if capture:
            capture()
        self.publish(wanted)

        passed = sum(1 for c in to_run if self.results[c["id"]]["verdict"] == "pass")
        failed = len(to_run) - passed
        print("\n  %d/%d cases passed, %d failed" % (passed, len(to_run), failed))
        print("  results: %s" % os.path.join(self.run_dir, "results.json"))
        return 1 if failed else 0


# ===================================================================== The Amazon SP-API mock

_amazon_server = None


def amazon_listening():
    with socket.socket() as probe:
        probe.settimeout(0.4)
        return probe.connect_ex((AMAZON_HOST, AMAZON_PORT)) == 0


def start_amazon_mock_if_silent():
    """Attaches to the Amazon mock on its allocated port, starting one in-process if none answers.

    The port is never moved: `2310x` is a partner answering, and the port alone settles direction
    when a call log is read back.
    """
    global _amazon_server
    if amazon_listening():
        return AMAZON_BASE

    import mock

    with open(os.path.join(AMAZON_DIR, "amazon.mock.json"), "r", encoding="utf-8") as handle:
        config = json.load(handle)

    os.makedirs(AMAZON_DATA_DIR, exist_ok=True)
    routes, _spec = mock.build_routes(config, AMAZON_DIR)
    state = mock.State(config.get("stores"), AMAZON_DATA_DIR)
    api_log = mock.ApiLog(os.path.join(AMAZON_DATA_DIR, LOG_FILE), "har",
                          config.get("log_redact_headers"), "Amazon SP-API")
    handler = mock.make_handler(config, routes, state, api_log, RESULTS_ROOT,
                                [], mock.SuiteRunner(), AMAZON_DIR)

    _amazon_server = ThreadingHTTPServer((AMAZON_HOST, AMAZON_PORT), handler)
    threading.Thread(target=_amazon_server.serve_forever, daemon=True).start()
    time.sleep(0.3)
    return AMAZON_BASE


def amazon_store(name):
    """Reads one of the Amazon mock's stores back -- where the partner-side observable lives."""
    return _read_store(os.path.join(AMAZON_DATA_DIR, name + ".json"))


# ===================================================================== The Anchanto OMS mock

_oms_server = None
_oms_data_dir = None


def start_oms_mock(state_dir):
    """Starts the Anchanto OMS mock in-process on an OS-assigned port against a run-scoped state.

    It never attaches to a server already holding `23001`: that server loaded its config at its own
    start, so a stale route would answer and the suite would report on a contract that is not the one
    on disk -- and writing into the portal server's own state would corrupt what it is keeping.
    """
    global _oms_server, _oms_data_dir

    import mock

    with open(os.path.join(OMS_DIR, "anchanto-oms.mock.json"), "r", encoding="utf-8") as handle:
        config = json.load(handle)

    _oms_data_dir = state_dir
    os.makedirs(_oms_data_dir, exist_ok=True)
    routes, _spec = mock.build_routes(config, OMS_DIR)
    state = mock.State(config.get("stores"), _oms_data_dir)
    api_log = mock.ApiLog(os.path.join(_oms_data_dir, LOG_FILE), "har",
                          config.get("log_redact_headers"), "Anchanto OMS")
    handler = mock.make_handler(config, routes, state, api_log,
                                os.path.join(OMS_DIR, "test-results"),
                                [], mock.SuiteRunner(), OMS_DIR)

    host = config.get("host") or "127.0.0.1"
    _oms_server = ThreadingHTTPServer((host, 0), handler)
    threading.Thread(target=_oms_server.serve_forever, daemon=True).start()
    time.sleep(0.3)
    return "http://%s:%d" % (host, _oms_server.server_address[1])


def oms_store(name):
    return _read_store(os.path.join(_oms_data_dir or "", name + ".json"))


def _read_store(path):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:  # noqa: BLE001 -- an unwritten store is an empty one
        return []


def _stop_servers():
    for server in (_amazon_server, _oms_server):
        if server:
            try:
                server.shutdown()
                server.server_close()
            except Exception:  # noqa: BLE001
                pass


atexit.register(_stop_servers)


# ===================================================================== Evidence


def capture_har(run_dir, source_dir, label="mock call log"):
    """Copies a mock's HAR next to the run's results, so a verdict can be traced to its calls."""
    import shutil

    source = os.path.join(source_dir, LOG_FILE)
    if not os.path.exists(source):
        return "not captured"
    os.makedirs(run_dir, exist_ok=True)
    shutil.copy2(source, os.path.join(run_dir, LOG_FILE))
    return "captured"
