#!/usr/bin/env python3
"""Amazon Seller-Fulfilled Returns Master Test Suite (IA-5112-US5).

Consolidated master suite executing all 55 test cases across:
  - IA-5112-US5-sync       (14 cases): SP-API report synchronization, polling, download, TSV parsing, rate limits, 4-marketplace isolation.
  - IA-5112-US5-lifecycle  (20 cases): Reconstruction, create/status wire payloads on OMS mock, 4 completion paths, 30-day clock edges.
  - IA-5112-US5-exceptions (21 cases): Exception matrix scenarios (§8.3), physical arrivals, cumulative limits, and 4 residual probes.

WHAT THIS SUITE PROVES
  The consolidated behavior of the Amazon SP-API mock and Anchanto OMS mock across the full
  Seller-Fulfilled Returns specification: report synchronization, end-to-end lifecycle progression,
  exception branches, and technical residual probes.

WHAT IT DOES NOT PROVE
  It never starts JPluger. The connector issues these calls in production; these suites post directly
  at the local mocks against requirements.py, this folder's reference implementation. JPluger JUnit
  tests prove the connector code.

Source documents:
  R-SUM: jira-workspace/amazon-cross-border/IA-5112/IA-5112-seller-fulfilled-returns-summary.md
  R-REQ: .../IA-5112-oms-returns-requirements-spec.md
  R-MAP: .../IA-5112-amz-oms-returns-mapping-spec.md
  R-LIB: .../IA-5112-seller-fulfilled-returns-library.md

Runner contract: local-test-servers/TESTING.md and plan/amazon-test-suites#01-harness.

Usage:
  python3 amazon/IA-5112-US5/suite-all.py                    # Run all 55 cases
  python3 amazon/IA-5112-US5/suite-all.py --list             # List all cases across the three suites
  python3 amazon/IA-5112-US5/suite-all.py --sync             # Run sync cases only
  python3 amazon/IA-5112-US5/suite-all.py --lifecycle        # Run lifecycle cases only
  python3 amazon/IA-5112-US5/suite-all.py --exceptions       # Run exceptions cases only
  python3 amazon/IA-5112-US5/suite-all.py IA-5112-US5-LIFE-04 # Run specific case
"""

import datetime
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import runner

CHILDREN = [
    ("sync", "suite-sync.py"),
    ("lifecycle", "suite-lifecycle.py"),
    ("exceptions", "suite-exceptions.py"),
]


def _load_module(label, filename):
    path = os.path.join(HERE, filename)
    spec = importlib.util.spec_from_file_location("ia5112_us5_" + label, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MODULES = [(label, _load_module(label, filename)) for label, filename in CHILDREN]

SUITE = runner.Suite(
    "IA-5112-US5-all",
    "IA-5112-US5: Master Test Suite (Consolidated 55 Cases)",
    proves="the Amazon SP-API mock and Anchanto OMS mock serve the full Seller-Fulfilled Returns "
           "contract end-to-end: report sync, lifecycle wire updates, 4 completion paths, and exceptions",
    does_not_prove="anything about JPluger -- no Java application is started here; JPluger JUnit tests prove connector code",
    base_url=runner.AMAZON_BASE,
)

OWNER_OF = {}
for _label, _module in MODULES:
    for _case in _module.SUITE.cases:
        SUITE.cases.append(_case)
        OWNER_OF[_case["id"]] = (_label, _module)


def main():
    argv = list(sys.argv[1:])
    wanted = {arg for arg in argv if not arg.startswith("-")}
    run_sync_only = "--sync" in argv
    run_life_only = "--lifecycle" in argv
    run_exc_only = "--exceptions" in argv

    if "--list" in argv:
        print(f"{SUITE.name} -- {len(SUITE.cases)} cases")
        for label, module in MODULES:
            print(f"\n  {label.upper()} -- {module.SUITE.name} ({len(module.SUITE.cases)} cases)")
            for case in module.SUITE.cases:
                print(f"    [{case['id']}] {case['name']}")
        return 0

    print(f"\n{SUITE.name}")
    print(f"  proves        : {SUITE.proves}")
    print(f"  does not prove: {SUITE.does_not_prove}")
    print(f"  base amazon   : {runner.AMAZON_BASE}")
    print(f"  base oms      : {runner.OMS_BASE}")
    print(f"  run dir       : {SUITE.run_dir}")

    # Run preflight across all child modules
    for _label, module in MODULES:
        module.preflight()
        SUITE.evidence.update(module.SUITE.evidence)

    # Filter target cases
    to_run = []
    for case in SUITE.cases:
        cid = case["id"]
        if wanted:
            if cid in wanted:
                to_run.append(case)
        elif run_sync_only or run_life_only or run_exc_only:
            if run_sync_only and cid.startswith("IA-5112-US5-SYNC"):
                to_run.append(case)
            elif run_life_only and cid.startswith("IA-5112-US5-LIFE"):
                to_run.append(case)
            elif run_exc_only and cid.startswith("IA-5112-US5-EXC"):
                to_run.append(case)
        else:
            to_run.append(case)

    print(f"\nExecuting {len(to_run)} cases across {len(MODULES)} suites...\n")
    for case in to_run:
        _label, module = OWNER_OF[case["id"]]
        verdict = module.SUITE.run_case(case)
        result = module.SUITE.results[case["id"]]
        SUITE.results[case["id"]] = result
        mark = "✓" if verdict == "pass" else ("⚠" if verdict == "blocked" else "✗")
        print(f"  [{verdict.upper():^7}] {mark} {case['id']}: {case['name']} -- {result['summary']}")

    # Publish master results
    SUITE.evidence["status"] = "complete"
    SUITE.publish(wanted)

    # Also publish child suites
    for _label, module in MODULES:
        child_wanted = {c["id"] for c in to_run if c["id"] in module.SUITE.results}
        if child_wanted:
            module.SUITE.evidence["status"] = "complete"
            module.SUITE.publish(child_wanted)

    passed = sum(1 for c in to_run if SUITE.results[c["id"]]["verdict"] == "pass")
    failed = sum(1 for c in to_run if SUITE.results[c["id"]]["verdict"] == "fail")
    blocked = sum(1 for c in to_run if SUITE.results[c["id"]]["verdict"] == "blocked")
    skipped = sum(1 for c in to_run if SUITE.results[c["id"]]["verdict"] == "skip")
    print(f"\n{SUITE.name} master run complete:")
    print(f"  {passed}/{len(to_run)} cases passed, {failed} failed, {blocked} blocked, {skipped} skipped.")
    print(f"  master results: {os.path.join(SUITE.run_dir, 'results.json')}\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
