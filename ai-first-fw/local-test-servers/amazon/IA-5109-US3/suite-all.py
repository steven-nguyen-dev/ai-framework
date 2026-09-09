#!/usr/bin/env python3
"""IA-5109 US3 -- master suite: Flow 1 send, poll and write-back in one run.

**Flow 1 is the `POST_ORDER_FULFILLMENT_DATA` order fulfilment feed**, the mechanism `D1` / `P-2`
selects. No suite in this folder calls `confirmShipment`: that is Flow 2, and `D1` defers it until
the multi-package phase begins.

WHAT THIS SUITE PROVES
  Everything its three children prove, in one run: that the local mocks serve Flow 1's whole shape --
  the send chain, both processing-report variants, every steered feed status, and the three-outcome
  write-back -- and that a feed document and a write-back built to the mapping survive them.

WHAT IT DOES NOT PROVE
  **None of these suites starts JPluger.** They post at the mocks directly, against
  `requirements.py`, this folder's reference implementation of the documents. A green run means the
  mocks and the documents agree. It is not evidence that the integration works, and it is not
  `D-25`: that row is met by the JPluger JUnit tests -- `AmazonMPUtilityTest`,
  `AmazonMPScheduledServiceTest`, `AmazonRtsWriteBackAndDuplicateTest` -- built and run through
  `marketplace-integrations/pom-legacy.xml`, because the aggregator `pom.xml` compiles none of that
  module's `src` tree.

Each child also writes its own results folder, so a master run leaves four readable runs.

Runner contract: `local-test-servers/TESTING.md`.

Usage:
  python3 amazon/IA-5109-US3/suite-all.py
  python3 amazon/IA-5109-US3/suite-all.py --list
  python3 amazon/IA-5109-US3/suite-all.py IA-5109-US3-POLL-FATAL
"""

import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import runner

SUITE = runner.Suite(
    "IA-5109-US3",
    "IA-5109-US3: Flow 1 master suite -- send, poll and write-back",
    proves="the local mocks serve Flow 1 end to end, and mapping-shaped payloads survive them",
    does_not_prove="anything about JPluger -- no suite here starts it; D-25 is the JUnit tests",
)

CHILDREN = [
    ("send", "suite-feed-submission.py"),
    ("poll", "suite-feed-poll.py"),
    ("write-back", "suite-oms-writeback.py"),
]


def load(label, filename):
    """Loads a sibling suite as a module. The children are scripts, so they cannot simply be imported."""
    path = os.path.join(HERE, filename)
    spec = importlib.util.spec_from_file_location("ia5109_us3_" + label.replace("-", "_"), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MODULES = [(label, load(label, filename)) for label, filename in CHILDREN]

# Cases keep their child's identity: each is run by the suite object that owns its module state, so
# a case reads the same mock base url and stores it would in a solo run.
OWNER_OF = {}
for _label, _module in MODULES:
    for _case in _module.SUITE.cases:
        SUITE.cases.append(_case)
        OWNER_OF[_case["id"]] = (_label, _module)


def main():
    argv = sys.argv[1:]
    wanted = {arg for arg in argv if not arg.startswith("-")}

    if "--list" in argv:
        print("%s -- %d cases" % (SUITE.name, len(SUITE.cases)))
        for label, module in MODULES:
            print("\n  %s -- %s (%d cases)" % (label, module.SUITE.name, len(module.SUITE.cases)))
            for case in module.SUITE.cases:
                print("    [%s] %s" % (case["id"], case["name"]))
        return 0

    print("\n%s" % SUITE.name)
    print("  proves        : %s" % SUITE.proves)
    print("  does not prove: %s" % SUITE.does_not_prove)

    for _label, module in MODULES:
        module.preflight()
        SUITE.evidence.update(module.SUITE.evidence)

    to_run = [c for c in SUITE.cases if not wanted or c["id"] in wanted]
    print("\nRunning %d cases across %d suites...\n" % (len(to_run), len(MODULES)))

    for case in to_run:
        label, module = OWNER_OF[case["id"]]
        module.SUITE.run_case(case)
        result = module.SUITE.results[case["id"]]
        SUITE.results[case["id"]] = result
        print("  [%s] %-6s %s: %s -- %s"
              % (result["verdict"].upper(), label, case["id"], case["name"], result["summary"]))

    for _label, module in MODULES:
        module.capture()
        module.SUITE.evidence["status"] = "complete"
        module.SUITE.publish(wanted)
        SUITE.evidence.update(module.SUITE.evidence)

    # After the update loop, never before it: a child's evidence still says "running" and would
    # overwrite the master's own status.
    SUITE.evidence["status"] = "complete"
    SUITE.publish(wanted)

    passed = sum(1 for c in to_run if SUITE.results[c["id"]]["verdict"] == "pass")
    failed = len(to_run) - passed
    print("\n=======================================================")
    print("  %d/%d cases passed, %d failed" % (passed, len(to_run), failed))
    print("  results: %s" % os.path.join(SUITE.run_dir, "results.json"))
    print("=======================================================")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
