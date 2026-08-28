#!/usr/bin/env python3
"""TEMPLATE -- copy to <mock>/suite-<name>.py and replace everything below.

One suite is one file: what it sends, what it expects, and why each case exists. The engine in
`suite/` does preflight, reset, firing, capture, judging and publishing, so a
requirement change or a defect is an edit here and nowhere else.

    python3 <mock>/suite-<name>.py                 every case
    python3 <mock>/suite-<name>.py --fast           skip the cases that only wait
    python3 <mock>/suite-<name>.py C1 C3            only the cases named
    python3 <mock>/suite-<name>.py --list           the cases and what each expects
    python3 <mock>/suite-<name>.py --judge <run>    re-score a folder, fire nothing

`--judge` is what an expectation change is checked with: edit the numbers here, re-score the runs
already on disk, and see which of them the new contract agrees with.

Three things to write, in this order.

1. **The payload.** One base your cases start from, and a helper per repeating fragment. A case
   states only what it changes, so the difference between two cases is the whole of what
   distinguishes them.
2. **The checklist.** Declared once, in the order the flow happens, naming each assertion in words.
   A check reads its expectation by name from the case's `expect` block, so all cases share one
   checklist and differ only in numbers. `None` drops the check for that case.
3. **The cases.** Identity, payload, `expect`, and `given` / `then` / `note` -- what the case is
   handed, what it has to prove, and which regression it catches. A reader arriving at a red row
   needs those three; the numbers alone are shorthand only their author can read.

A suite that drives a mock alone declares no `database` and no `queues`; those assertions are then
dropped with `not captured` against them rather than passing silently.

How to write one, the check vocabulary and what each escape hatch costs: `README.md` beside this
file. The runner contract, the results file and the traps this engine already handles:
`TESTING.md`. A worked example carrying all of it: `eton/suite-create-order.py`.
"""

import os
import sys

# The engine is a sibling package, and a suite file is started from wherever the caller happens to
# be -- the /test page starts it from the mock's own folder.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from suite import (Calls, Case, ControllerStatus, Group, Marker, MySql, PostJson, Queues, Rows,
                   Sql, Status, Suite, merge, key_from)
from suite import AppResponds, DatabaseResponds, MockResponds, QueuesRespond, SeedRows

PACKAGE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ------------------------------------------------------------------------------------ settings

# Each is overridden by an environment variable of the same name.
ENV = {
    "APP": "https://localhost",
    "MOCK": "http://127.0.0.1:23000",
    "DB_NAME": "example_test",
    "CORE_JSON": os.path.join(PACKAGE, "core.json"),
}


# ------------------------------------------------------------------------------------ payloads

REQUEST = {
    "event_parameters": {"seller_code": "SSIN10000007004", "event_name": "order_creation"},
    "data": {"order_id": "1", "order_number": "SO-EXAMPLE-1", "order_items": []},
}


def item(item_id, sku="SKU-1", quantity=1, **extra):
    line = {"order_item_id": item_id, "sku": sku, "quantity": quantity}
    line.update(extra)
    return line


def case(cid, name, order_id, number, items, expect, wait=7, **rest):
    """One case, keyed by the identifiers its evidence is recoverable from.

    `key` ties the partner's calls to this case and `row_key` its database rows. Prefer a value the
    client already sends over a correlation field invented for the test.
    """
    payload = merge(REQUEST, {"data": {"order_id": order_id, "order_number": number,
                                       "order_items": items}})
    return Case(cid, name, payload=payload, key=order_id, row_key=number, wait=wait, expect=expect,
                detail={"order_id": order_id, "order_number": number}, **rest)


# -------------------------------------------------------------------------------------- cases

CASES = [
    case("C1", "C1. Happy path", "1", "SO-EXAMPLE-1", [item(11)],
         expect={"create_calls": 1, "create_status": 200, "create_mark": "New", "db_rows": 1},
         note="Why this case exists -- the regression it catches.",
         given="What the case is handed.",
         then=["One acceptance criterion per entry.",
               "Stated as what has to be true, not as what the code does."]),

    case("C2", "C2. Partner rejects the payload", "2", "SO-EXAMPLE-2", [],
         expect={"create_calls": 1, "create_status": 400, "create_mark": "must not be empty",
                 "db_rows": 0},
         note="A 4xx is the partner saying the payload is wrong, so it must not be retried.",
         given="An order with no items, which the partner's schema forbids.",
         then=["Exactly 1 create call — a 400 is not retried.",
               "No row is written."]),
]


# -------------------------------------------------------------------------------------- suite

SUITE = Suite(
    id="example",                       # must match a test_suites[].id in the mock config
    name="Example flow (Anchanto OMS -> Example Partner)",
    description="what this suite covers, shown on the /test page",
    mock="example",                     # the integration folder name
    cases=CASES,
    env=ENV,

    fire=PostJson("${APP}/jpluger/wms/createOrders"),

    groups=[Group("create", "POST", "/api/v1/orders")],

    call_key=key_from(url=r"/orders/([^/?]+)", skip=(), body=("OrderCode",)),

    checks=[
        ControllerStatus("Send the order to JPluger", "POST /jpluger/wms/createOrders "
                         "(publish only)", value=200),
        Calls("create", "Send the order to the partner", "POST /api/v1/orders",
              expect="create_calls"),
        Status("create", "The partner answers", "HTTP status of the create response",
               expect="create_status"),
        Marker("create", "Read the marker in the reply", "Status / ErrorCode in the body",
               expect="create_mark"),
        Rows("Write the order to the database", "rows in `orders` for this order",
             expect="db_rows"),
    ],

    stores=["created_orders"],

    database=Sql(
        client=lambda env: MySql.from_json(env["CORE_JSON"], env["DB_NAME"]),
        dump="SELECT order_number, status FROM orders WHERE order_number LIKE 'SO-EXAMPLE-%' "
             "ORDER BY order_number",
        file="orders.tsv",
        key_column=0,
        reset="DELETE FROM orders WHERE order_number LIKE 'SO-EXAMPLE-%'",
    ),

    preflight=[
        AppResponds("${APP}/jpluger/wms/createOrders"),
        MockResponds(),
        DatabaseResponds(),
        SeedRows("seller 7004", "SELECT COUNT(*) FROM seller WHERE selluseller_seller_id=7004"),
    ],
)


if __name__ == "__main__":
    from suite.run import main
    sys.exit(main(__file__, sys.argv[1:]))
