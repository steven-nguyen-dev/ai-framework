#!/usr/bin/env python3
"""IA-5105-US1 Master Suite: Complete Amazon Marketplace Taxonomy & Store Connect Verification.

Consolidates and executes all test suites for User Story 1: Synchronize Amazon
Marketplace Taxonomy and Dynamic Product Schemas (IA-5105):
  1. Marketplace Taxonomy Sync (IA-5105-US1-suite-taxonomy)
  2. US Store Connect & Taxonomy Sync (IA-5105-US1-suite-connect-us)
  3. Non-US Multi-Marketplace Store Connect & Taxonomy Sync (IA-5105-US1-suite-connect-non-us)

Runner contract: TESTING.md.
Publishes live status to amazon/test-results/IA-5105-US1-all/run-<stamp>/results.json.

Usage:
  python3 amazon/suite-IA-5105-US1.py
  python3 amazon/suite-IA-5105-US1.py --list
  python3 amazon/suite-IA-5105-US1.py TAX-CAT-1 US-CAT-1 NONUS-RBN-DE
  BASE=http://127.0.0.1:23103 BASE_OMS=http://127.0.0.1:23001 python3 amazon/suite-IA-5105-US1.py
"""

import atexit
import datetime
import importlib
import json
import os
import shutil
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

BASE_AMAZON = os.environ.get("BASE_AMAZON", os.environ.get("BASE", "http://127.0.0.1:23103")).rstrip("/")
BASE_OMS = os.environ.get("BASE_OMS", "http://127.0.0.1:23001").rstrip("/")
SUITE = "IA-5105-US1-all"
SUITE_NAME = "IA-5105-US1: Master Suite -- Taxonomy & Store Connect Verification"
KEEP = "--keep-state" in sys.argv
LIST_ONLY = "--list" in sys.argv
WANTED_CASES = set(a for a in sys.argv[1:] if not a.startswith("-"))

MOCK_DIR = HERE
DATA_DIR = os.path.join(MOCK_DIR, "mock-data")
LOG = "api-calls.har.json"
STAMP = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
RUN_DIR = os.path.join(MOCK_DIR, "test-results", SUITE, "run-" + STAMP)

# Import the 3 constituent suites by convention name
suite_tax = importlib.import_module("suite-IA-5105-US1-taxonomy")
suite_us = importlib.import_module("suite-IA-5105-US1-connect-us")
suite_non_us = importlib.import_module("suite-IA-5105-US1-connect-non-us")

tax_ids = set(c["id"] for c in suite_tax.CASES)
us_ids = set(c["id"] for c in suite_us.CASES)
non_us_ids = set(c["id"] for c in suite_non_us.CASES)

# Aggregate all test cases preserving order
ALL_CASES = suite_tax.CASES + suite_us.CASES + suite_non_us.CASES
RESULTS = {}
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
                "detail": {},
            })
        else:
            e.update({"verdict": "pending"})
        cases.append(e)

    done = [c for c in cases if c.get("verdict") in ("pass", "fail", "blocked", "skip")]
    doc = {
        "name": SUITE_NAME,
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
    if LIST_ONLY:
        print(f"{SUITE_NAME} -- Declared Cases ({len(ALL_CASES)} cases):")
        for c in ALL_CASES:
            print(f"  [{c['id']}] {c['name']}")
        return

    print(f"=== Running {SUITE} (Master Suite: {len(ALL_CASES)} Cases) ===")

    # Mock server probe
    st_amz, _, _ = suite_us.call_amazon("GET", "/auth/o2/token")
    if st_amz == 0:
        print("Starting ephemeral Amazon mock...")
        suite_us._start_ephemeral_mock()
        st_amz, _, _ = suite_us.call_amazon("GET", "/auth/o2/token")
    suite_us.AMAZON_UP = (st_amz != 0)
    suite_non_us.AMAZON_UP = (st_amz != 0)
    suite_tax.AMAZON_UP = (st_amz != 0)
    EVIDENCE["amazon mock"] = f"online at {BASE_AMAZON}" if (st_amz != 0) else "offline"

    st_oms, _, _ = suite_us.call_oms("GET", "/rest/v1/orders/1")
    suite_us.OMS_UP = (st_oms != 0)
    suite_non_us.OMS_UP = (st_oms != 0)
    suite_tax.OMS_UP = (st_oms != 0)
    EVIDENCE["oms mock"] = f"online at {BASE_OMS}" if (st_oms != 0) else "offline"

    passed, failed, blocked = 0, 0, 0
    cases_to_run = [c for c in ALL_CASES if not WANTED_CASES or c["id"] in WANTED_CASES]

    current_group = ""
    for c in cases_to_run:
        cid = c["id"]
        group = "TAXONOMY" if cid in tax_ids else ("CONNECT-US" if cid in us_ids else "CONNECT-NON-US")
        if group != current_group:
            current_group = group
            print(f"\n--- Domain {current_group} ---")

        if cid in tax_ids:
            v = suite_tax.run_case(c)
            RESULTS[cid] = suite_tax.RESULTS[cid]
        elif cid in us_ids:
            v = suite_us.run_case(c)
            RESULTS[cid] = suite_us.RESULTS[cid]
        elif cid in non_us_ids:
            v = suite_non_us.run_case(c)
            RESULTS[cid] = suite_non_us.RESULTS[cid]
        else:
            v = "fail"

        r = RESULTS[cid]
        summary = r.get("summary", "")
        if v == "pass":
            passed += 1
            print(f"  \033[32mPASS\033[0m {cid}: {c['name']} ({summary})")
        elif v == "blocked":
            blocked += 1
            print(f"  \033[33mBLOCKED\033[0m {cid}: {c['name']} ({summary})")
        else:
            failed += 1
            print(f"  \033[31mFAIL\033[0m {cid}: {c['name']} ({summary})")

    publish()
    print("\n=======================================================")
    print(f"Master Run Complete: {passed} passed, {failed} failed, {blocked} blocked (Total {len(cases_to_run)})")
    print(f"Results written to {RUN_DIR}/results.json")
    print("=======================================================")
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
