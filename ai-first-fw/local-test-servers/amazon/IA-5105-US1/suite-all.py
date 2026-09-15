#!/usr/bin/env python3
"""IA-5105-US1 Master Suite: Complete Amazon Marketplace Taxonomy & Store Connect Verification.

Consolidates and executes all 44 test cases for User Story 1: Synchronize Amazon
Marketplace Taxonomy and Dynamic Product Schemas (IA-5105):
  1. Marketplace Taxonomy Sync (suite-taxonomy: 16 cases)
  2. US Store Connect & Taxonomy Sync (suite-connect-us: 14 cases)
  3. Non-US Multi-Marketplace Store Connect & Taxonomy Sync (suite-connect-non-us: 14 cases)

Runner contract: TESTING.md.
Publishes live status to amazon/test-results/IA-5105-US1-all/run-<stamp>/results.json.

Usage:
  python3 amazon/IA-5105-US1/suite-all.py
  python3 amazon/IA-5105-US1/suite-all.py --list
  python3 amazon/IA-5105-US1/suite-all.py TAX-CAT-1 US-CAT-1 NONUS-RBN-DE
  BASE_AMAZON=http://127.0.0.1:23123 BASE_OMS=http://127.0.0.1:23021 python3 amazon/IA-5105-US1/suite-all.py
"""

import datetime
import importlib
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
MOCK_DIR = os.path.dirname(HERE)
for _p in (HERE, MOCK_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

BASE_AMAZON = os.environ.get("BASE_AMAZON", os.environ.get("BASE", "http://127.0.0.1:23103")).rstrip("/")
BASE_OMS = os.environ.get("BASE_OMS", "http://127.0.0.1:23001").rstrip("/")

# Handle --port and --oms-port CLI flags
for idx, arg in enumerate(sys.argv):
    if arg == "--port" and idx + 1 < len(sys.argv):
        BASE_AMAZON = f"http://127.0.0.1:{sys.argv[idx + 1]}"
    elif arg.startswith("--port="):
        BASE_AMAZON = f"http://127.0.0.1:{arg.split('=', 1)[1]}"
    elif arg == "--oms-port" and idx + 1 < len(sys.argv):
        BASE_OMS = f"http://127.0.0.1:{sys.argv[idx + 1]}"
    elif arg.startswith("--oms-port="):
        BASE_OMS = f"http://127.0.0.1:{arg.split('=', 1)[1]}"

os.environ["BASE_AMAZON"] = BASE_AMAZON
os.environ["BASE"] = BASE_AMAZON
os.environ["BASE_OMS"] = BASE_OMS

SUITE = "IA-5105-US1-all"
SUITE_NAME = "IA-5105-US1: Master Suite -- Taxonomy & Store Connect Verification"
KEEP = "--keep-state" in sys.argv
LIST_ONLY = "--list" in sys.argv
WANTED_CASES = set(a for a in sys.argv[1:] if not a.startswith("-"))

STAMP = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
RUN_DIR = os.path.join(MOCK_DIR, "test-results", SUITE, "run-" + STAMP)

# Import the 3 constituent suites by module name
suite_tax = importlib.import_module("suite-taxonomy")
suite_us = importlib.import_module("suite-connect-us")
suite_non_us = importlib.import_module("suite-connect-non-us")

# Propagate runtime base URLs
for s in (suite_tax, suite_us, suite_non_us):
    s.BASE_AMAZON = BASE_AMAZON
    s.BASE_OMS = BASE_OMS
suite_tax.BASE = BASE_AMAZON

import requirements as R  # noqa: E402

tax_ids = set(c["id"] for c in suite_tax.CASES)
us_ids = set(c["id"] for c in suite_us.CASES)
non_us_ids = set(c["id"] for c in suite_non_us.CASES)

# Aggregate all test cases preserving order: 16 + 14 + 14 = 44 cases
ALL_CASES = suite_tax.CASES + suite_us.CASES + suite_non_us.CASES
RESULTS = {}
EVIDENCE = {
    "status": "running",
    "amazon mock": f"Amazon SP-API mock at {BASE_AMAZON}",
    "oms mock": f"Anchanto OMS mock at {BASE_OMS}",
    "authority": "IA-5105 deliverables override the Jira ticket; wiki plan/amazon-test-suites",
    "does_not_prove": [
        "Nothing about JPluger: there is no JPluger under test. transformer.py is a stand-in "
        "for the JPluger pipeline and its defects remain RED.",
        "Nothing about Amazon SP-API live behavior: the mock answers from captures.",
    ],
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
            "total": len(ALL_CASES),
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
        for idx, c in enumerate(ALL_CASES, 1):
            print(f"  {idx:2d}. [{c['id']}] {c['name']}")
        return 0

    print(f"=== Running {SUITE} (Master Suite: {len(ALL_CASES)} Cases) ===")
    print(f"  Amazon mock : {BASE_AMAZON}")
    print(f"  OMS mock    : {BASE_OMS}")
    print(f"  Run dir     : {RUN_DIR}")

    # Mock server probe -- never start an unowned ephemeral mock
    st_amz, _, _ = suite_us.call_amazon("POST", "/auth/o2/token", body={"grant_type": "client_credentials"})
    amz_up = (st_amz != 0)
    suite_us.AMAZON_UP = amz_up
    suite_non_us.AMAZON_UP = amz_up
    suite_tax.AMAZON_UP = amz_up
    print(f"  Mock probe  : {'online' if amz_up else 'DOWN (every case will be blocked)'} (status {st_amz})")
    EVIDENCE["amazon mock"] = f"online at {BASE_AMAZON}" if amz_up else "offline"

    st_oms, _, _ = suite_us.call_oms("GET", "/rest/v1/categories", query={"store_code": "SS0000US", "marketplace_code": "amazon_sp_us"})
    oms_up = (st_oms == 200)
    suite_us.OMS_UP = oms_up
    suite_non_us.OMS_UP = oms_up
    suite_tax.OMS_UP = oms_up
    print(f"  OMS probe   : {'online' if oms_up else 'DOWN (wire assertions will be blocked)'} (status {st_oms})")
    EVIDENCE["oms mock"] = f"online at {BASE_OMS}" if oms_up else "offline"

    if amz_up and not KEEP:
        st_amz_reset = R.oms_clear_log(BASE_AMAZON)
        print(f"  Amazon log  : reset (DELETE /log/data -> {st_amz_reset})")

    if oms_up and not KEEP:
        st_reset = R.oms_clear_log(BASE_OMS)
        print(f"  OMS log     : reset (DELETE /log/data -> {st_reset})")

    publish()

    passed, failed, blocked = 0, 0, 0
    cases_to_run = [c for c in ALL_CASES if not WANTED_CASES or c["id"] in WANTED_CASES]
    print(f"  Cases       : {len(cases_to_run)}{f' selected of {len(ALL_CASES)}' if WANTED_CASES else ''}\n")

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

        publish()
        r = RESULTS[cid]
        summary = r.get("summary", "")
        if v == "pass":
            passed += 1
            print(f"  \033[32mPASS\033[0m    {cid:<18} {c['name'][:50]:<50} {summary}")
        elif v == "blocked":
            blocked += 1
            print(f"  \033[33mBLOCKED\033[0m {cid:<18} {c['name'][:50]:<50} {summary}")
        else:
            failed += 1
            print(f"  \033[31mFAIL\033[0m    {cid:<18} {c['name'][:50]:<50} {summary}")
            for i in r.get("checks", []):
                if not i.get("ok"):
                    print(f"            - {i.get('label')}: expected {i.get('expected')!r}, got {i.get('actual')!r}")

    time.sleep(0.2)
    EVIDENCE["status"] = "complete"
    publish()

    total_checks = sum(len(RESULTS.get(c["id"], {}).get("checks", [])) for c in cases_to_run)
    print("\n=======================================================")
    print(f"Master Run Complete: {passed} passed, {failed} failed, {blocked} blocked, {total_checks} checks total (Total {len(cases_to_run)} cases)")
    print(f"Results written to {RUN_DIR}/results.json")
    print("=======================================================")
    return 1 if failed > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
