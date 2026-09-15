#!/usr/bin/env python3
"""Shared runner for the IA-5112 US5 suites: case registry, checks, mock preflight, results file.

Provides the shared test harness, HTTP utilities, and mock inspection machinery
following the testing contract in local-test-servers/TESTING.md and plan/amazon-test-suites#01-harness.
"""

import atexit
import datetime
import json
import os
import shutil
import sys
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
AMAZON_DIR = os.path.dirname(HERE)
SERVERS_DIR = os.path.dirname(AMAZON_DIR)
OMS_DIR = os.path.join(SERVERS_DIR, "anchanto-oms")

AMAZON_DATA_DIR = os.path.join(AMAZON_DIR, "mock-data")
OMS_DATA_DIR = os.path.join(OMS_DIR, "mock-data")
RESULTS_ROOT = os.path.join(AMAZON_DIR, "test-results")
LOG_FILE = "api-calls.har.json"

AMAZON_BASE = os.environ.get("BASE_AMAZON", os.environ.get("BASE", "http://127.0.0.1:23103")).rstrip("/")
OMS_BASE = os.environ.get("BASE_OMS", "http://127.0.0.1:23001").rstrip("/")

for _path in (HERE, SERVERS_DIR):
    if _path not in sys.path:
        sys.path.insert(0, _path)


# ===================================================================== Checks


class Checks:
    """One case's expected-against-actual list. A case passes when every check in it passed."""

    def __init__(self):
        self.items = []

    def add(self, label, what, expected, actual):
        ok = (str(expected) == str(actual)) if not isinstance(expected, bool) else (expected is (actual is True or actual == "True"))
        self.items.append({
            "label": label,
            "what": what,
            "expected": str(expected),
            "actual": str(actual),
            "ok": ok,
        })
        return ok

    def truthy(self, label, what, actual):
        got = "present" if actual not in (None, "", [], {}) else "missing"
        ok = (got == "present")
        self.items.append({
            "label": label,
            "what": what,
            "expected": "present",
            "actual": got,
            "ok": ok,
        })
        return ok

    def absent(self, label, what, actual):
        got = "absent" if actual in (None, "", [], {}) else f"present ({actual})"
        ok = (got == "absent")
        self.items.append({
            "label": label,
            "what": what,
            "expected": "absent",
            "actual": got,
            "ok": ok,
        })
        return ok

    def contains(self, label, what, item, collection):
        ok = item in collection if collection is not None else False
        self.items.append({
            "label": label,
            "what": what,
            "expected": f"contains {item!r}",
            "actual": f"size {len(collection)}" if isinstance(collection, (list, dict, set)) else str(collection),
            "ok": ok,
        })
        return ok

    @property
    def ok(self):
        return all(item["ok"] for item in self.items) and len(self.items) > 0


# ===================================================================== Suite


class Suite:
    """One runnable suite: its cases, its results folder, and its own main."""

    def __init__(self, suite_id, name, proves, does_not_prove, base_url=None):
        self.id = suite_id
        self.name = name
        self.proves = proves
        self.does_not_prove = does_not_prove
        self.base_url = base_url or AMAZON_BASE
        self.cases = []
        self.results = {}
        self.evidence = {
            "status": "running",
            "proves": self.proves,
            "does_not_prove": self.does_not_prove,
            "amazon mock": f"Amazon SP-API mock at {self.base_url}",
            "oms mock": f"Anchanto OMS mock at {OMS_BASE}",
        }
        self.stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        self.run_dir = os.path.join(RESULTS_ROOT, suite_id, "run-" + self.stamp)

    def case(self, case_id, name, given, then, note, fn):
        self.cases.append({
            "id": case_id,
            "name": name,
            "given": given,
            "then": then if isinstance(then, list) else [then],
            "note": note,
            "fn": fn,
        })

    def run_case(self, case):
        checks, calls, detail = Checks(), [], {}
        try:
            case["fn"](checks, calls, detail)
            verdict = "pass" if checks.ok else "fail"
        except Exception as error:  # noqa: BLE001
            checks.add("runner exception", "no unhandled exception", "none", f"error: {error}")
            detail["exception"] = str(error)
            verdict = "fail"
        passed = sum(1 for item in checks.items if item["ok"])
        self.results[case["id"]] = {
            "verdict": verdict,
            "checks": checks.items,
            "calls": calls,
            "detail": detail,
            "summary": f"{passed}/{len(checks.items)} checks passed",
        }
        return verdict

    def publish(self, wanted=None):
        cases_out = []
        for case in self.cases:
            entry = {k: case[k] for k in ("id", "name", "given", "then", "note")}
            result = self.results.get(case["id"])
            if result:
                entry.update(result)
            elif wanted and case["id"] not in wanted:
                entry.update({
                    "verdict": "skip",
                    "summary": "skipped (not selected)",
                    "checks": [],
                    "calls": [],
                    "detail": {},
                })
            else:
                entry.update({
                    "verdict": "pending",
                    "summary": "pending",
                    "checks": [],
                    "calls": [],
                    "detail": {},
                })
            cases_out.append(entry)

        done = [c for c in cases_out if c.get("verdict") in ("pass", "fail", "blocked", "skip")]
        document = {
            "name": self.name,
            "suite": self.id,
            "stamp": self.stamp,
            "at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "base_url": self.base_url,
            "summary": {
                verdict: sum(1 for c in done if c["verdict"] == verdict)
                for verdict in ("pass", "fail", "blocked", "skip")
            },
            "evidence": dict(self.evidence, status="complete"),
            "cases": cases_out,
        }
        os.makedirs(self.run_dir, exist_ok=True)
        with open(os.path.join(self.run_dir, "results.json"), "w", encoding="utf-8") as handle:
            json.dump(document, handle, indent=2)

    def main(self, argv=None, preflight=None, capture=None):
        argv = list(sys.argv[1:] if argv is None else argv)
        wanted = {arg for arg in argv if not arg.startswith("-")}

        if "--list" in argv:
            print(f"{self.name} -- {len(self.cases)} cases")
            for case in self.cases:
                print(f"  [{case['id']}] {case['name']}")
            return 0

        print(f"\n{self.name}")
        print(f"  proves        : {self.proves}")
        print(f"  does not prove: {self.does_not_prove}")
        print(f"  base amazon   : {self.base_url}")
        print(f"  base oms      : {OMS_BASE}")
        print(f"  run dir       : {self.run_dir}")

        if preflight:
            preflight()

        to_run = [c for c in self.cases if not wanted or c["id"] in wanted]
        print(f"\nRunning {len(to_run)} cases...\n")
        for case in to_run:
            self.run_case(case)
            result = self.results[case["id"]]
            mark = "✓" if result["verdict"] == "pass" else ("⚠" if result["verdict"] == "blocked" else "✗")
            print(f"  [{result['verdict'].upper():^7}] {mark} {case['id']}: {case['name']} -- {result['summary']}")

        self.evidence["status"] = "complete"
        if capture:
            capture()
        self.publish(wanted)

        passed = sum(1 for c in to_run if self.results[c["id"]]["verdict"] == "pass")
        failed = sum(1 for c in to_run if self.results[c["id"]]["verdict"] == "fail")
        blocked = sum(1 for c in to_run if self.results[c["id"]]["verdict"] == "blocked")
        skipped = sum(1 for c in to_run if self.results[c["id"]]["verdict"] == "skip")
        print(f"\n  {passed}/{len(to_run)} cases passed, {failed} failed, {blocked} blocked, {skipped} skipped.")
        print(f"  results: {os.path.join(self.run_dir, 'results.json')}\n")
        return 1 if failed else 0


# ===================================================================== HTTP & Mock Helpers


def http_json(method, url, body=None, token=None, timeout=10):
    """Sends a JSON HTTP request and returns `(status, parsed body, raw_bytes)`."""
    headers = {"Accept": "application/json"}
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = "Bearer " + token
        headers["x-amz-access-token"] = token
    req_obj = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req_obj, timeout=timeout) as resp:
            raw = resp.read()
            parsed = json.loads(raw.decode("utf-8")) if raw.strip() else {}
            return resp.status, parsed, raw
    except urllib.error.HTTPError as err:
        raw = err.read()
        try:
            parsed = json.loads(raw.decode("utf-8")) if raw.strip() else {}
        except Exception:
            parsed = {"raw": raw.decode("utf-8", errors="replace")}
        return err.code, parsed, raw
    except Exception as err:
        return 0, {"_transport_error": str(err)}, b""


def call_amazon(method, path, body=None, token="mock_sp_api_access_token"):
    """Dispatches an SP-API call against the configured Amazon mock base URL."""
    url = AMAZON_BASE + path
    return http_json(method, url, body=body, token=token)


def call_oms(method, path, body=None, query=None, token="f1a6c2d8e40b7935a1c6d2f8b04e7395"):
    """Dispatches an OMS call against the configured OMS mock base URL."""
    full_path = path + ("?" + urllib.parse.urlencode(query) if query else "")
    url = OMS_BASE + full_path
    return http_json(method, url, body=body, token=token)


def clear_oms_log():
    """Resets the OMS mock call log via DELETE /log/data."""
    try:
        st, body, _ = http_json("DELETE", OMS_BASE + "/log/data")
        return st == 200
    except Exception:
        return False


def read_oms_log():
    """Reads recorded requests/responses from OMS mock via GET /log/data."""
    try:
        st, body, _ = http_json("GET", OMS_BASE + "/log/data")
        if st == 200 and isinstance(body, dict):
            return body.get("entries", [])
    except Exception:
        pass
    return []


def read_oms_store(store_name):
    """Reads an OMS mock store directly from mock-data/."""
    path = os.path.join(OMS_DATA_DIR, store_name + ".json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return [] if store_name != "returns" else []


def read_amazon_store(store_name):
    """Reads an Amazon mock store directly from mock-data/."""
    path = os.path.join(AMAZON_DATA_DIR, store_name + ".json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []
