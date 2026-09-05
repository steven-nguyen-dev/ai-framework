#!/usr/bin/env python3
"""suite-IA-5106-US4: Complete Buyer Cancellation Verification Master Suite.

Runs the entire test matrix (56 cases) across all four functional domains:
  1. Hold & Ingress (suite-IA-5106-US4-hold: IA-5106-US4-HOLD-01..12)
  2. Confirmed Cancellation & Release (suite-IA-5106-US4-cancel: IA-5106-US4-CANCEL-01..17)
  3. Rejection & Restoration (suite-IA-5106-US4-restore: IA-5106-US4-RESTORE-01..11)
  4. Pre-RTS Gate, Race Conditions & Resilience (suite-IA-5106-US4-gate: IA-5106-US4-GATE-01..16)

Runner contract: TESTING.md.
Publishes live status to amazon/test-results/IA-5106-US4-all/run-<stamp>/results.json.

Usage:
  python3 amazon/suite-IA-5106-US4.py
  python3 amazon/suite-IA-5106-US4.py IA-5106-US4-HOLD-01
"""

import atexit
import datetime
import importlib
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer

BASE_AMAZON = os.environ.get("BASE_AMAZON", os.environ.get("BASE", "http://127.0.0.1:23103")).rstrip("/")
BASE_OMS = os.environ.get("BASE_OMS", "http://127.0.0.1:23001").rstrip("/")
SUITE = "IA-5106-US4-all"
KEEP = "--keep-state" in sys.argv
FAST = "--fast" in sys.argv
WANTED_CASES = set(a for a in sys.argv[1:] if not a.startswith("-"))

HERE = os.path.dirname(os.path.abspath(__file__))
MOCK_DIR = HERE
DATA_DIR = os.path.join(MOCK_DIR, "mock-data")
LOG = "api-calls.har.json"
STAMP = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
RUN_DIR = os.path.join(MOCK_DIR, "test-results", SUITE, "run-" + STAMP)

if HERE not in sys.path:
    sys.path.insert(0, HERE)

import ia5106_requirements as req
from amazon_cancellation_transformer import CancellationTransformer

# Dynamically import the 4 individual suites by convention name
suite_hold = importlib.import_module("suite-IA-5106-US4-hold")
suite_cancel = importlib.import_module("suite-IA-5106-US4-cancel")
suite_restore = importlib.import_module("suite-IA-5106-US4-restore")
suite_gate = importlib.import_module("suite-IA-5106-US4-gate")

# Aggregate all test cases
ALL_CASES = suite_hold.CASES + suite_cancel.CASES + suite_restore.CASES + suite_gate.CASES

CASES, RESULTS = [], {}
EVIDENCE = {
    "status": "running",
    "amazon mock": f"Amazon SP-API mock at {BASE_AMAZON}",
    "oms mock": f"Anchanto OMS mock at {BASE_OMS}",
}


def publish():
    cases = []
    for c in ALL_CASES:
        r = RESULTS.get(c["id"])
        e = {"id": c["id"], "name": c["name"], "given": c["given"], "then": c["then"], "note": c["note"]}
        if r:
            e.update(r)
        elif WANTED_CASES and c["id"] not in WANTED_CASES:
            e.update({
                "verdict": "skip",
                "summary": "skipped (not selected)",
                "checks": [],
                "calls": [],
                "detail": {}
            })
        else:
            e.update({"verdict": "pending"})
        cases.append(e)

    done = [c for c in cases if c.get("verdict") in ("pass", "fail", "blocked", "skip")]
    doc = {
        "name": "IA-5106-US4: Master Suite — Full Buyer Cancellation Verification",
        "suite": SUITE,
        "at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "base_url": BASE_AMAZON,
        "summary": {
            "pass": sum(1 for c in done if c["verdict"] == "pass"),
            "fail": sum(1 for c in done if c["verdict"] == "fail"),
            "blocked": sum(1 for c in done if c["verdict"] == "blocked"),
            "skip": sum(1 for c in done if c["verdict"] == "skip"),
        },
        "evidence": EVIDENCE,
        "cases": cases,
    }
    os.makedirs(RUN_DIR, exist_ok=True)
    with open(os.path.join(RUN_DIR, "results.json"), "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2)


def main():
    print(f"=== Running {SUITE} (Master Suite: 56 Cases) ===")

    # Probe mocks via suite_hold
    st_amz, _, _ = suite_hold.call_amazon("GET", "/auth/o2/token")
    if st_amz == 0:
        print("Starting ephemeral Amazon mock...")
        suite_hold._start_ephemeral_mock()
        st_amz, _, _ = suite_hold.call_amazon("GET", "/auth/o2/token")
    suite_hold.AMAZON_UP = (st_amz != 0)
    suite_cancel.AMAZON_UP = (st_amz != 0)
    suite_restore.AMAZON_UP = (st_amz != 0)
    suite_gate.AMAZON_UP = (st_amz != 0)
    EVIDENCE["amazon mock"] = f"online at {BASE_AMAZON}" if (st_amz != 0) else "offline"

    st_oms, _, _ = suite_hold.call_oms("GET", "/rest/v1/orders/1")
    suite_hold.OMS_UP = (st_oms != 0)
    suite_cancel.OMS_UP = (st_oms != 0)
    suite_restore.OMS_UP = (st_oms != 0)
    suite_gate.OMS_UP = (st_oms != 0)
    EVIDENCE["oms mock"] = f"online at {BASE_OMS}" if (st_oms != 0) else "offline"

    passed, failed, blocked = 0, 0, 0
    cases_to_run = [c for c in ALL_CASES if not WANTED_CASES or c["id"] in WANTED_CASES]

    current_group = ""
    for c in cases_to_run:
        group = c["id"].split("-")[3] if len(c["id"].split("-")) > 3 else "OTHER"
        if group != current_group:
            current_group = group
            print(f"\n--- Group {current_group} ---")

        # Pick appropriate run_case function based on case origin
        if c["id"].startswith("IA-5106-US4-HOLD"):
            v = suite_hold.run_case(c)
            RESULTS[c["id"]] = suite_hold.RESULTS[c["id"]]
        elif c["id"].startswith("IA-5106-US4-CANCEL"):
            v = suite_cancel.run_case(c)
            RESULTS[c["id"]] = suite_cancel.RESULTS[c["id"]]
        elif c["id"].startswith("IA-5106-US4-RESTORE"):
            v = suite_restore.run_case(c)
            RESULTS[c["id"]] = suite_restore.RESULTS[c["id"]]
        elif c["id"].startswith("IA-5106-US4-GATE"):
            v = suite_gate.run_case(c)
            RESULTS[c["id"]] = suite_gate.RESULTS[c["id"]]
        else:
            v = "fail"

        r = RESULTS[c["id"]]
        if v == "pass":
            passed += 1
            print(f"  \033[32mPASS\033[0m {c['id']}: {c['name']} ({r['summary']})")
        elif v == "blocked":
            blocked += 1
            print(f"  \033[33mBLOCKED\033[0m {c['id']}: {c['name']} ({r['summary']})")
        else:
            failed += 1
            print(f"  \033[31mFAIL\033[0m {c['id']}: {c['name']} ({r['summary']})")

    publish()
    print(f"\n=======================================================")
    print(f"Master Run Complete: {passed} passed, {failed} failed, {blocked} blocked (Total {len(cases_to_run)})")
    print(f"Results written to {RUN_DIR}/results.json")
    print(f"=======================================================")
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
