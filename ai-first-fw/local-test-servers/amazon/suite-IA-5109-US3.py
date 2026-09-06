#!/usr/bin/env python3
"""Amazon Partial & Multi-Parcel Shipments Master Test Suite (IA-5109-US3).

Consolidated runner for all 52 test cases across:
  - IA-5109-US3-CONFIRM (23 cases): Amazon SP-API Orders v0 confirmShipment, grouping (Rule N-1),
                                   monotonic packageReferenceId (Rule N-2), quantity ledger (Rule N-3),
                                   and exception matrix (Rule N-4).
  - IA-5109-US3-OMS     (14 cases): Anchanto OMS contracts CR-0 to CR-5, RTS webhook diff,
                                   quantity alias, shipping_details write-back, and database durability.
  - IA-5109-US3-MKT     (15 cases): Multi-marketplace isolation (FR, DE, JP, US), Japan-only COD
                                   DirectPayment, carrier mapping, and customs/IOSS boundary.

Runner contract: TESTING.md.
Publishes live status to amazon/test-results/IA-5109-US3/run-<stamp>/results.json.

Usage:
  python3 amazon/suite-IA-5109-US3.py
  python3 amazon/suite-IA-5109-US3.py --list
  python3 amazon/suite-IA-5109-US3.py IA-5109-US3-FLOW1-HAPPY-PATH
  BASE=http://127.0.0.1:23103 python3 amazon/suite-IA-5109-US3.py
"""

import atexit
import datetime
import importlib.util
import json
import os
import shutil
import sys
import threading
import time
from http.server import ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import ia5109_us3_requirements as R

def _load_module(mod_name, file_path):
    spec = importlib.util.spec_from_file_location(mod_name, file_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

mod_confirm = _load_module("suite_confirm", os.path.join(HERE, "suite-IA-5109-US3-parcel-confirmation.py"))
mod_oms = _load_module("suite_oms", os.path.join(HERE, "suite-IA-5109-US3-oms-contracts.py"))
mod_mkt = _load_module("suite_mkt", os.path.join(HERE, "suite-IA-5109-US3-multi-market.py"))

BASE = os.environ.get("BASE", "http://127.0.0.1:23103").rstrip("/")
SUITE_ID = "IA-5109-US3"
SUITE_NAME = "IA-5109-US3: Master Test Suite (All 52 Cases)"
KEEP = "--keep-state" in sys.argv
LIST_ONLY = "--list" in sys.argv
WANTED_CASES = set(a for a in sys.argv[1:] if not a.startswith("-"))

MOCK_DIR = HERE
DATA_DIR = os.path.join(MOCK_DIR, "mock-data")
LOG_FILE = "api-calls.har.json"
STAMP = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
RUN_DIR = os.path.join(MOCK_DIR, "test-results", SUITE_ID, "run-" + STAMP)

# Aggregate all cases preserving order
ALL_CASES = mod_confirm.CASES + mod_oms.CASES + mod_mkt.CASES
RESULTS = {}
EVIDENCE = {
    "status": "running",
    "mock call log": "not captured",
    "server": f"Amazon SP-API mock at {BASE}",
}


def publish():
    cases_out = []
    for c in ALL_CASES:
        r = RESULTS.get(c["id"])
        e = {
            "id": c["id"],
            "name": c["name"],
            "given": c["given"],
            "then": c["then"],
            "note": c["note"],
        }
        if r:
            e.update(r)
        elif WANTED_CASES and c["id"] not in WANTED_CASES:
            e.update({
                "verdict": "skip",
                "summary": "skipped (not selected)",
                "checks": [],
                "calls": [],
                "detail": {},
            })
        else:
            e.update({"verdict": "pending"})
        cases_out.append(e)

    done = [c for c in cases_out if c.get("verdict") in ("pass", "fail", "blocked", "skip")]
    doc = {
        "name": SUITE_NAME,
        "suite": SUITE_ID,
        "at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "base_url": BASE,
        "summary": {
            "pass": sum(1 for c in done if c["verdict"] == "pass"),
            "fail": sum(1 for c in done if c["verdict"] == "fail"),
            "blocked": sum(1 for c in done if c["verdict"] == "blocked"),
            "skip": sum(1 for c in done if c["verdict"] == "skip"),
        },
        "evidence": EVIDENCE,
        "cases": cases_out,
    }
    os.makedirs(RUN_DIR, exist_ok=True)
    with open(os.path.join(RUN_DIR, "results.json"), "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2)


def run_case(c):
    ch = mod_confirm.Checks()
    calls = []
    detail = {}
    try:
        c["fn"](ch, calls, detail)
        verdict = "pass" if ch.ok else "fail"
    except Exception as e:
        ch.add("runner exception", "no unhandled exception", "none", f"error: {e}")
        verdict = "fail"

    np = sum(1 for i in ch.items if i["ok"])
    RESULTS[c["id"]] = {
        "verdict": verdict,
        "checks": ch.items,
        "calls": calls,
        "detail": detail,
        "summary": f"{np}/{len(ch.items)} checks passed",
    }


def main():
    if LIST_ONLY:
        print(f"{SUITE_NAME} -- Declared Cases ({len(ALL_CASES)} cases):")
        for c in ALL_CASES:
            print(f"  [{c['id']}] {c['name']}")
        return

    mod_confirm.preflight()

    to_run = [c for c in ALL_CASES if not WANTED_CASES or c["id"] in WANTED_CASES]
    print(f"\nRunning {len(to_run)} cases across all 3 suites...")

    for c in to_run:
        run_case(c)
        r = RESULTS[c["id"]]
        v = r["verdict"].upper()
        print(f"  [{v}] {c['id']}: {c['name']} -- {r['summary']}")

    EVIDENCE["status"] = "complete"
    mod_confirm.capture()
    publish()

    done = [RESULTS[c["id"]] for c in to_run if c["id"] in RESULTS]
    p_cnt = sum(1 for r in done if r["verdict"] == "pass")
    f_cnt = sum(1 for r in done if r["verdict"] == "fail")
    print(f"\n=======================================================")
    print(f"Master Suite Finished: {p_cnt} passed, {f_cnt} failed of {len(to_run)} cases.")
    print(f"Results written to {os.path.join(RUN_DIR, 'results.json')}")
    print(f"=======================================================")

    if f_cnt > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
