#!/usr/bin/env python3
"""Amazon Seller-Fulfilled Returns Master Test Suite (IA-5112-US5).

Consolidated runner for all 60 test cases across:
  - IA-5112-US5-SYNC (12 cases): Amazon SP-API report synchronization, polling, download, TSV parsing.
  - IA-5112-US5-LIFE (20 cases): Reconstruction, create/status payloads, 4 completion paths, 30-day ageing.
  - IA-5112-US5-EXC  (28 cases): 23 exception matrix scenarios, arrivals, cumulative check, and 4 residual probes.

Source documents:
  R-SUM: IA-5112-seller-fulfilled-returns-summary.md
  R-REQ: IA-5112-oms-returns-requirements-spec.md
  R-MAP: IA-5112-amz-oms-returns-mapping-spec.md
  R-LIB: IA-5112-seller-fulfilled-returns-library.md

Usage:
  python3 amazon/suite-IA-5112-US5.py                    # Run all 60 cases
  python3 amazon/suite-IA-5112-US5.py --sync             # Run sync cases only
  python3 amazon/suite-IA-5112-US5.py --lifecycle        # Run lifecycle cases only
  python3 amazon/suite-IA-5112-US5.py --exceptions       # Run exceptions cases only
  python3 amazon/suite-IA-5112-US5.py IA-5112-US5-LIFE-04 # Run specific case
"""

import atexit
import datetime
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer

import ia5112_us5_requirements as req

# Import case definitions from the three specialized suite modules
import importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))

def _load_module(mod_name, file_path):
    spec = importlib.util.spec_from_file_location(mod_name, file_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

mod_sync = _load_module("suite_sync", os.path.join(HERE, "suite-IA-5112-US5-sync.py"))
mod_life = _load_module("suite_life", os.path.join(HERE, "suite-IA-5112-US5-lifecycle.py"))
mod_exc = _load_module("suite_exc", os.path.join(HERE, "suite-IA-5112-US5-exceptions.py"))

BASE_AMAZON = os.environ.get("BASE", "http://127.0.0.1:23103").rstrip("/")
BASE_OMS = os.environ.get("BASE_OMS", "http://127.0.0.1:23001").rstrip("/")
SUITE = "IA-5112-US5"
STAMP = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
RUN_DIR = os.path.join(HERE, "test-results", SUITE, "run-" + STAMP)

# Combine cases
ALL_CASES = []
# Sync cases
for c in mod_sync.CASES:
    ALL_CASES.append(dict(c))
# Lifecycle cases
for c in mod_life.CASES:
    ALL_CASES.append(dict(c))
# Exceptions cases
for c in mod_exc.CASES:
    ALL_CASES.append(dict(c))

ARG_CASES = set(a for a in sys.argv[1:] if not a.startswith("-"))
RUN_SYNC = "--sync" in sys.argv
RUN_LIFE = "--lifecycle" in sys.argv
RUN_EXC = "--exceptions" in sys.argv

RESULTS = {}
EVIDENCE = {
    "status": "running",
    "mock call log": "not captured",
    "amazon mock": f"Amazon SP-API mock at {BASE_AMAZON}",
    "oms mock": f"Anchanto OMS mock at {BASE_OMS}",
}


def publish():
    cases = []
    for c in ALL_CASES:
        cid = c["id"]
        r = RESULTS.get(cid)
        e = {
            "id": cid,
            "name": c["name"],
            "given": c["given"],
            "then": c["then"],
            "note": c["note"]
        }
        if r:
            e.update(r)
        else:
            e.update({
                "verdict": "skip",
                "summary": "skipped (not selected)",
                "detail": {},
                "checks": [],
                "calls": []
            })
        cases.append(e)

    done = [c for c in cases if c.get("verdict") in ("pass", "fail", "blocked", "skip")]
    payload = {
        "suite": SUITE,
        "title": "Amazon Seller-Fulfilled Returns Master Suite (IA-5112-US5)",
        "stamp": STAMP,
        "at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "base_url": BASE_AMAZON,
        "summary": {
            "total": len(cases),
            "pass": sum(1 for c in done if c["verdict"] == "pass"),
            "fail": sum(1 for c in done if c["verdict"] == "fail"),
            "blocked": sum(1 for c in done if c["verdict"] == "blocked"),
            "skip": sum(1 for c in done if c["verdict"] == "skip"),
        },
        "cases": cases,
        "evidence": EVIDENCE
    }

    os.makedirs(RUN_DIR, exist_ok=True)
    with open(os.path.join(RUN_DIR, "results.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def main():
    print(f"Amazon Seller-Fulfilled Returns Master Suite (IA-5112-US5) -- {BASE_AMAZON}")
    print(f"  run dir  : {RUN_DIR}")
    print(f"  total cases registered: {len(ALL_CASES)}")

    # Preflight via sync module
    mod_sync.preflight()

    # Filter cases
    selected = []
    for c in ALL_CASES:
        cid = c["id"]
        if ARG_CASES:
            if cid in ARG_CASES:
                selected.append(c)
        elif RUN_SYNC or RUN_LIFE or RUN_EXC:
            if RUN_SYNC and cid.startswith("IA-5112-US5-SYNC"):
                selected.append(c)
            elif RUN_LIFE and cid.startswith("IA-5112-US5-LIFE"):
                selected.append(c)
            elif RUN_EXC and cid.startswith("IA-5112-US5-EXC"):
                selected.append(c)
        else:
            selected.append(c)

    print(f"\nExecuting {len(selected)} test cases across IA-5112-US5...\n")
    for c in selected:
        cid = c["id"]
        if cid.startswith("IA-5112-US5-SYNC"):
            v = mod_sync.run_case(c)
            RESULTS[cid] = mod_sync.RESULTS[cid]
        elif cid.startswith("IA-5112-US5-LIFE"):
            v = mod_life.run_case(c)
            RESULTS[cid] = mod_life.RESULTS[cid]
        elif cid.startswith("IA-5112-US5-EXC"):
            v = mod_exc.run_case(c)
            RESULTS[cid] = mod_exc.RESULTS[cid]

        mark = "✓" if v == "pass" else ("⚠" if v == "blocked" else "✗")
        print(f"  [{v.upper():^7}] {mark} {cid}: {c['name']}")

    publish()
    total = len(selected)
    passed = sum(1 for r in RESULTS.values() if r["verdict"] == "pass")
    failed = sum(1 for r in RESULTS.values() if r["verdict"] == "fail")
    blocked = sum(1 for r in RESULTS.values() if r["verdict"] == "blocked")
    print(f"\n{SUITE} master run complete: {passed}/{total} passed, {failed} failed, {blocked} blocked.")
    print(f"Results saved to: {os.path.join(RUN_DIR, 'results.json')}\n")
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
