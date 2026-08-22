#!/usr/bin/env python3
"""Proves the engine itself, against a run folder written here rather than against a live mock.

Every suite's verdicts rest on this code, so it is checked without an app, a mock, a database or a
queue: a folder holding the evidence a run would have produced is judged, and the verdicts are
compared with what the checks are supposed to say. Run it after touching anything under
`suite/`.

    python3 suite/selftest.py
"""

import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from suite import (Calls, Case, ControllerStatus, Group, Marker, Rows, Status, Suite, DELETE,
                   merge, key_from)
from suite import engine

FAILURES = []


def check(claim, ok):
    print("  %-5s %s" % ("ok" if ok else "FAIL", claim))
    if not ok:
        FAILURES.append(claim)


# ---------------------------------------------------------------------------------- payloads

def test_merge():
    base = {"a": 1, "nested": {"keep": 1, "replace": 2}, "list": [1, 2]}
    merged = merge(base, {"nested": {"replace": 3, "added": 4}, "list": [9]})
    check("merge keeps what the override does not mention", merged["nested"]["keep"] == 1)
    check("merge replaces a stated value", merged["nested"]["replace"] == 3)
    check("merge adds a new key", merged["nested"]["added"] == 4)
    check("merge replaces a list rather than extending it", merged["list"] == [9])
    check("merge leaves the base untouched", base["nested"]["replace"] == 2)
    check("DELETE removes a key the base carries", "a" not in merge(base, {"a": DELETE}))


# ------------------------------------------------------------------------------------ judging

def call(at, method, url, status, body=None, request_body=None):
    return {"at": at, "request": {"method": method, "url": url, "body": request_body},
            "response": {"status": status, "body": body or {}}}


def build_suite():
    return Suite(
        id="selftest", name="engine selftest", mock="none",
        fire=None,
        cases=[
            Case("A", "A. accepted", key="1", row_key="SO-1", shape="normal",
                 expect={"create_calls": 1, "create_status": 200, "create_mark": "New",
                         "pricing_calls": 1, "pricing_status": 200, "db_rows": 1}),
            Case("B", "B. rejected", key="2", row_key="SO-2", shape="normal",
                 expect={"create_calls": 1, "create_status": 400, "create_mark": "BESO05",
                         "pricing_calls": 0, "pricing_status": None, "db_rows": 0}),
            Case("C", "C. never fired", key="3", row_key="SO-3", shape="normal",
                 expect={"create_calls": 1, "create_status": 200, "create_mark": None,
                         "pricing_calls": 0, "pricing_status": None, "db_rows": 0}),
        ],
        groups=[Group("create", "POST", "/api/v0.2/saleorders/single"),
                Group("pricing", "POST", "/api/v0.2/saleorders/*/priceDetail", label="push")],
        call_key=key_from(url=r"/saleorders/([^/?]+)", skip=("single",), body=("ClientSoCode",)),
        checks=[
            ControllerStatus("Publish", "POST to the app", value=200),
            Calls("create", "Create calls", "POST …/saleorders/single", expect="create_calls"),
            Status("create", "Create answer", "status", expect="create_status"),
            Marker("create", "Marker", "Status / ErrorCode", expect="create_mark"),
            Rows("Rows written", "rows in `orders`", expect="db_rows"),
            Calls("pricing", "Pricing calls", "POST …/priceDetail", expect="pricing_calls"),
            Status("pricing", "Pricing answer", "status", expect="pricing_status", which="all"),
        ],
        database=None,
    )


def write_run(folder, with_rows=True):
    host = "http://127.0.0.1:23101"
    entries = [
        call("2026-01-01T00:00:01Z", "POST", host + "/api/v0.2/saleorders/single", 200,
             {"Code": "1", "Status": "New"}, {"ClientSoCode": "1"}),
        call("2026-01-01T00:00:02Z", "POST", host + "/api/v0.2/saleorders/1/priceDetail", 200, {}),
        call("2026-01-01T00:00:03Z", "POST", host + "/api/v0.2/saleorders/single", 400,
             {"ErrorCode": "BESO05"}, {"ClientSoCode": "2"}),
    ]
    with open(os.path.join(folder, "mock-log.json"), "w") as handle:
        json.dump({"name": "selftest", "host": host, "entries": entries}, handle)
    with open(os.path.join(folder, "controller-responses.json"), "w") as handle:
        json.dump([{"id": "A", "controller_status": 200, "fired_at": "2026-01-01T00:00:00Z"},
                   {"id": "B", "controller_status": 200, "fired_at": "2026-01-01T00:00:03Z"}],
                  handle)
    with open(os.path.join(folder, "meta.json"), "w") as handle:
        json.dump({"suite": "selftest", "settings": {"EVENT_NAME": "order_creation"}}, handle)
    if with_rows:
        with open(os.path.join(folder, "rows.tsv"), "w") as handle:
            handle.write("order_number\tstatus\nSO-1\tNEW\n")


def test_judging():
    from suite import Sql
    folder = tempfile.mkdtemp()
    try:
        suite = build_suite()
        write_run(folder)
        document = engine.judge(suite, folder)
        by_id = {case["id"]: case for case in document["cases"]}

        check("a case whose calls match every expectation passes", by_id["A"]["verdict"] == "pass")
        check("a case reading a marker inside a 400 passes", by_id["B"]["verdict"] == "pass")
        check("a case that was never fired is skipped, not failed",
              by_id["C"]["verdict"] == "skip")
        check("a case not yet fired is pending while the run is partial",
              engine.judge(suite, folder, partial=True)["cases"][2]["verdict"] == "pending")
        check("the summary line names the groups it counted",
              by_id["A"]["summary"] == "1 create → 200 New · 1 push → 200")
        check("a check about calls that were never made is dropped rather than passed",
              all(c["label"] != "Pricing answer" for c in by_id["B"]["checks"]))
        check("database checks are dropped when no database was declared",
              all(c["label"] != "Rows written" for c in by_id["A"]["checks"]))

        # With a database declared, the same folder judges its rows and says so when it cannot.
        suite.database = Sql(dump="", file="rows.tsv", key_column=0)
        document = engine.judge(suite, folder)
        by_id = {case["id"]: case for case in document["cases"]}
        check("rows are counted per case", by_id["A"]["verdict"] == "pass")
        check("a case expecting no rows passes when it wrote none", by_id["B"]["verdict"] == "pass")

        os.remove(os.path.join(folder, "rows.tsv"))
        document = engine.judge(suite, folder)
        by_id = {case["id"]: case for case in document["cases"]}
        check("an uncaptured database is stated, never passed",
              by_id["A"]["detail"].get("database rows", "").startswith("not captured"))

        # A wrong expectation has to fail, or none of the above means anything.
        suite.cases[0].expect["create_calls"] = 2
        document = engine.judge(suite, folder)
        by_id = {case["id"]: case for case in document["cases"]}
        check("a missed expectation fails and names itself",
              by_id["A"]["verdict"] == "fail" and "Create calls" in by_id["A"]["actual"])
    finally:
        shutil.rmtree(folder, ignore_errors=True)


def test_selection():
    suite = build_suite()
    suite.cases[2].wait = 110
    check("--fast drops a case by its own wait, never by its name",
          [c.id for c in engine.select(suite, fast=True)] == ["A", "B"])
    check("named ids select exactly those cases",
          [c.id for c in engine.select(suite, ids=["B"])] == ["B"])


if __name__ == "__main__":
    print("payloads")
    test_merge()
    print("judging")
    test_judging()
    print("selection")
    test_selection()
    print("")
    if FAILURES:
        print("%d check(s) failed" % len(FAILURES))
        sys.exit(1)
    print("engine selftest passed")
