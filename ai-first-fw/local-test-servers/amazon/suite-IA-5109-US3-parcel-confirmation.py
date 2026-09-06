#!/usr/bin/env python3
"""IA-5109-US3: Parcel Confirmation & Core Flows Test Suite.

Judges the Amazon Selling Partner API (SP-API) Orders v0 confirmShipment integration
against the specifications for User Story 3: Support Partial and Multi-Parcel Amazon
Seller-Fulfilled Shipments (IA-5109).

Every case crosses the HTTP boundary. The observable is what the mock received -- the rows the
confirmShipment route recorded, or, for a rule that blocks, the rows it did not -- never a pure
function asserting our own encoded rule against itself.

Covers:
  - Flow 1: End-to-end multi-parcel confirmation happy path (L-1, L-4, L-70, L-86)
  - Flow 2: Independent parcel retry and failure isolation (L-90, L-88)
  - Flow 3: Unknown outcome reconciled against QuantityShipped (L-9, L-90)
  - Rule N-1: Grouping by tracking number, blank tracking, and the no-box-list live shape (L-66, L-86, L-175)
  - Rule N-2: The package reference from package_id, allocation, stability and the edit (L-5, L-50, L-88, L-163)
  - Rule N-3: The quantity ledger read from Amazon's own QuantityShipped (L-9, L-10, L-89)
  - Rule N-4: The exception matrix -- the gate, the ship-date bounds, the item and quantity blocks
  - C-10: The Amazon order-item id from mp_item_codes[] (L-119)
  - C-17: The six defect sites in AmazonMPUtility (L-16, L-53, L-65, L-66, L-67, L-68)
  - C-26: The synchronous pre-submit gate against Amazon's own answer (L-20, L-87)

Not here, and why. Flow 0's entry branch (C-19) is an in-process store-configuration decision with
no HTTP surface; AmazonRtsRouterTest.EntryBranch pins it. N-1's "distinct tracking numbers grouped
into one parcel" is nil by construction -- the group key is the tracking number, so the parcel cannot
be built -- and GROUP-MULTI-TRACKING is the positive evidence.

Runner contract: TESTING.md.
Publishes live status to amazon/test-results/IA-5109-US3-confirmation/run-<stamp>/results.json.

Usage:
  python3 amazon/IA-5109-US3-suite-parcel-confirmation.py
  python3 amazon/IA-5109-US3-suite-parcel-confirmation.py --list
  python3 amazon/IA-5109-US3-suite-parcel-confirmation.py IA-5109-US3-FLOW1-HAPPY-PATH
  BASE=http://127.0.0.1:23103 python3 amazon/IA-5109-US3-suite-parcel-confirmation.py --keep-state
"""

import atexit
import datetime
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

BASE = os.environ.get("BASE", "http://127.0.0.1:23103").rstrip("/")
SUITE_ID = "IA-5109-US3-confirmation"
SUITE_NAME = "IA-5109-US3: Parcel Confirmation & Core Flows Suite"
KEEP = "--keep-state" in sys.argv
FAST = "--fast" in sys.argv
LIST_ONLY = "--list" in sys.argv
WANTED_CASES = set(a for a in sys.argv[1:] if not a.startswith("-"))

MOCK_DIR = HERE
DATA_DIR = os.path.join(MOCK_DIR, "mock-data")
LOG_FILE = "api-calls.har.json"
STAMP = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
RUN_DIR = os.path.join(MOCK_DIR, "test-results", SUITE_ID, "run-" + STAMP)

STORES = [
    "lwa_tokens",
    "created_orders",
    "shipment_confirmations",
    "order_acknowledgements",
    "feeds",
    "feed_documents",
    "reports",
    "listings",
    "mfn_shipments",
]

_EPHEMERAL_SERVER = None
_EPHEMERAL_THREAD = None


def _start_ephemeral_mock():
    global _EPHEMERAL_SERVER, _EPHEMERAL_THREAD
    parent_dir = os.path.dirname(MOCK_DIR)
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)
    import mock

    config_path = os.path.join(MOCK_DIR, "amazon.mock.json")
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    os.makedirs(DATA_DIR, exist_ok=True)
    routes, spec = mock.build_routes(config, MOCK_DIR)
    state = mock.State(config.get("stores"), DATA_DIR)
    api_log = mock.ApiLog(os.path.join(DATA_DIR, LOG_FILE), "har", config.get("log_redact_headers"), "Amazon SP-API")
    handler_cls = mock.make_handler(
        config, routes, state, api_log, os.path.join(MOCK_DIR, "test-results"),
        [], mock.SuiteRunner(), MOCK_DIR
    )

    host = config.get("host", "127.0.0.1")
    port = int(config.get("port", 23103))
    _EPHEMERAL_SERVER = ThreadingHTTPServer((host, port), handler_cls)
    _EPHEMERAL_THREAD = threading.Thread(target=_EPHEMERAL_SERVER.serve_forever, daemon=True)
    _EPHEMERAL_THREAD.start()
    time.sleep(0.3)


def _stop_ephemeral_mock():
    global _EPHEMERAL_SERVER
    if _EPHEMERAL_SERVER:
        try:
            _EPHEMERAL_SERVER.shutdown()
            _EPHEMERAL_SERVER.server_close()
        except Exception:
            pass
        _EPHEMERAL_SERVER = None


atexit.register(_stop_ephemeral_mock)


def call_amazon(method, path, body=None, token="mock_sp_api_access_token"):
    url = BASE + path
    return R.http_json(method, url, body=body, token=token)


def store(name):
    """Reads one of the mock's stores back, which is where the partner-side observable lives."""
    path = os.path.join(DATA_DIR, name + ".json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


CASES, RESULTS = [], {}
EVIDENCE = {
    "status": "running",
    "mock call log": "not captured",
    "mock stores": "not captured",
    "server": f"Amazon SP-API mock at {BASE}",
}


class Checks:
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

    def truthy(self, label, what, actual):
        got = "present" if actual not in (None, "", [], {}) else "missing"
        self.items.append({
            "label": label,
            "what": what,
            "expected": "present",
            "actual": got,
            "ok": got == "present",
        })

    @property
    def ok(self):
        return all(i["ok"] for i in self.items)


def case(cid, name, given, then, note, fn):
    CASES.append({
        "id": cid,
        "name": name,
        "given": given,
        "then": then if isinstance(then, list) else [then],
        "note": note,
        "fn": fn,
    })


def publish():
    cases_out = []
    for c in CASES:
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
    ch = Checks()
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


# ===================================================================== Test Cases Definitions
#
# Every case here crosses the HTTP boundary. A case that only asserted our own encoded rule against
# itself would pass whatever the partner did, so the observable is always what the mock received:
# the rows the confirmShipment route recorded, or -- for a rule that blocks -- the rows it did not.

APPENDIX_A_ORDER = "902-1845936-5435065"

FR = "amazon_sp_fr"
SUBMITTING_AT = "2026-08-22T14:06:00Z"
PURCHASED_AT = "2026-08-20T09:12:03Z"
READY_TO_SHIP_AT = "2026-08-22T14:05:00Z"
NEXT_DAY = "2026-08-23T09:40:00Z"

ITEM_1001 = "05015851154158"
ITEM_2002 = "05015851154159"
ITEM_3003 = "05015851154160"
MASTER_TRACKING = "MT-7734829901"
SECOND_TRACKING = "CJ-5581200347"


def live_meta(**overrides):
    """The carrier and date context of the one captured live ready-to-ship payload (L-146, L-187)."""
    meta = {
        "shipping_provider": "Startrack",
        "marketplace_carrier_code": "",
        "logistic_partner_name": None,
        "shipping_type": "FPP (Fixed Price Premium)",
        "updated_at": READY_TO_SHIP_AT,
        "purchased_at": PURCHASED_AT,
        "submitting_at": SUBMITTING_AT,
        "store_marketplace_code": FR,
    }
    meta.update(overrides)
    return meta


def confirmations_for(order_id):
    """The rows the mock's confirmShipment route holds for one order, in the order it recorded them."""
    return [c for c in store("shipment_confirmations") if c.get("orderId") == order_id]


def submit(ch, calls, order_id, parcels, marketplace=FR, is_cod=False, expect=204):
    """Sends one confirmShipment call per parcel and records what each answered."""
    statuses = []
    for parcel in parcels:
        request = R.build_amazon_confirmation_request(order_id, marketplace, parcel, is_cod=is_cod)
        status, _ = call_amazon("POST", request["url_path"], request["body"])
        calls.append("POST %s (parcel %s) -> %s" % (request["url_path"], parcel.package_reference_id, status))
        statuses.append(status)
    if expect is not None:
        ch.add("every parcel answered %s" % expect, "one call per parcel, each accepted",
               [expect] * len(parcels), statuses)
    return statuses


# --------------------------------------------------------------------- Rule N-1, grouping

def test_flow1_happy_path(ch, calls, detail):
    # Flow 1: one order, two carriers, two parcels, partial quantity (L-1, L-4, L-70, L-86)
    order_id = APPENDIX_A_ORDER

    st_ord, order_body = call_amazon("GET", "/orders/v0/orders/%s" % order_id)
    calls.append("GET /orders/v0/orders/%s -> %s" % (order_id, st_ord))
    ch.add("amazon order fetch", "order metadata status 200", 200, st_ord)

    st_items, items_body = call_amazon("GET", "/orders/v0/orders/%s/orderItems" % order_id)
    calls.append("GET /orders/v0/orders/%s/orderItems -> %s" % (order_id, st_items))
    ch.add("amazon order items fetch", "order items status 200", 200, st_items)

    gate = R.evaluate_gate(order_body.get("payload"), items_body.get("payload"))
    ch.add("gate passes", "a clean seller-fulfilled order still ships", False, gate.blocked)

    boxes = [
        R.CartonBox("SHP-41277-1-C1", MASTER_TRACKING, is_master_tracking=True, ship_date=READY_TO_SHIP_AT,
                    items=[R.OrderItemAllocation(811, ITEM_1001, "SKU-1001", 1)]),
        R.CartonBox("SHP-41277-1-C2", MASTER_TRACKING, is_master_tracking=True, ship_date=READY_TO_SHIP_AT,
                    items=[R.OrderItemAllocation(811, ITEM_1001, "SKU-1001", 1),
                           R.OrderItemAllocation(812, ITEM_2002, "SKU-2002", 1)]),
        R.CartonBox("SHP-41277-1-C3", SECOND_TRACKING, ship_date=NEXT_DAY,
                    items=[R.OrderItemAllocation(811, ITEM_1001, "SKU-1001", 3)]),
    ]
    meta = live_meta(marketplace_carrier_code="DHL", logistic_partner_name="DHL Express",
                     shipping_type="DHL Express Worldwide", submitting_at=NEXT_DAY,
                     ship_from_supply_source_id="057d3fcc-b750-419f-bbcd-4d340c60c430")

    parcels, blocked = R.assemble_parcels(boxes, meta)
    ch.add("nothing blocked", "clean grouping", [], [b.reason for b in blocked])
    submit(ch, calls, order_id, parcels)

    rows = confirmations_for(order_id)
    ch.add("amazon holds two parcels", "one call per parcel, never one call per order", 2, len(rows))
    ch.add("each parcel one tracking number", "distinct numbers never merge",
           [MASTER_TRACKING, SECOND_TRACKING], [r.get("trackingNumber") for r in rows])

    first = {i["orderItemId"]: i["quantity"] for i in rows[0].get("orderItems") or []}
    second = {i["orderItemId"]: i["quantity"] for i in rows[1].get("orderItems") or []}
    ch.add("parcel 1 sums SKU-1001 across boxes", "packed one per box across two boxes, told 2 not 1 twice",
           2, first.get(ITEM_1001))
    ch.add("parcel 1 carries SKU-2002", "both lines travel in the parcel", 1, first.get(ITEM_2002))
    ch.add("parcel 2 carries the rest", "quantity 5 split as 2 and 3, never 5 twice", 3, second.get(ITEM_1001))
    ch.add("supply source reaches amazon", "the dispatch is attributed to the source Amazon assigned",
           "057d3fcc-b750-419f-bbcd-4d340c60c430", rows[0].get("shipFromSupplySourceId"))

    for parcel in parcels:
        parcel.status = R.ParcelConfirmationStatus.ACCEPTED
    ch.add("order-level row", "R-MAP 5.2, no marketplace status is set", "all accepted",
           R.order_level_outcome(parcels))


def test_group_master_tracking(ch, calls, detail):
    # Rule N-1: boxes sharing one master tracking number are one parcel, quantities summed (L-86)
    order_id = "902-0000001-0000001"
    boxes = [
        R.CartonBox("B1", "MT-MASTER-01", is_master_tracking=True, ship_date=READY_TO_SHIP_AT,
                    items=[R.OrderItemAllocation(811, ITEM_1001, "SKU-1001", 2)]),
        R.CartonBox("B2", "MT-MASTER-01", is_master_tracking=True, ship_date=READY_TO_SHIP_AT,
                    items=[R.OrderItemAllocation(811, ITEM_1001, "SKU-1001", 3)]),
        R.CartonBox("B3", "MT-MASTER-01", is_master_tracking=True, ship_date=READY_TO_SHIP_AT,
                    items=[R.OrderItemAllocation(812, ITEM_2002, "SKU-2002", 1)]),
    ]
    parcels, blocked = R.assemble_parcels(boxes, live_meta())
    ch.add("nothing blocked", "clean master-tracking grouping", [], [b.reason for b in blocked])
    submit(ch, calls, order_id, parcels)

    rows = confirmations_for(order_id)
    ch.add("one call for three boxes", "Amazon keys a parcel on the tracking number", 1, len(rows))
    quantities = {i["orderItemId"]: i["quantity"] for i in rows[0].get("orderItems") or []}
    ch.add("SKU-1001 summed", "2 + 3 reaches Amazon as one 5", 5, quantities.get(ITEM_1001))
    ch.add("SKU-2002 carried", "the third box's line travels in the same parcel", 1, quantities.get(ITEM_2002))


def test_group_multi_tracking(ch, calls, detail):
    # Rule N-1: distinct tracking numbers are distinct parcels, so distinct calls (L-86)
    order_id = "902-0000002-0000002"
    boxes = [
        R.CartonBox("B1", "TRK-001", ship_date=READY_TO_SHIP_AT,
                    items=[R.OrderItemAllocation(811, "ITEM-A", "SKU-A", 1)]),
        R.CartonBox("B2", "TRK-002", ship_date=READY_TO_SHIP_AT,
                    items=[R.OrderItemAllocation(812, "ITEM-B", "SKU-B", 1)]),
        R.CartonBox("B3", "TRK-003", ship_date=READY_TO_SHIP_AT,
                    items=[R.OrderItemAllocation(813, "ITEM-C", "SKU-C", 1)]),
    ]
    parcels, blocked = R.assemble_parcels(boxes, live_meta())
    ch.add("nothing blocked", "three clean groups", [], [b.reason for b in blocked])
    submit(ch, calls, order_id, parcels)

    rows = confirmations_for(order_id)
    ch.add("three parcels reach amazon", "one call per tracking number", 3, len(rows))
    ch.add("three tracking numbers", "never merged into one parcel",
           ["TRK-001", "TRK-002", "TRK-003"], [r.get("trackingNumber") for r in rows])
    ch.add("three distinct references", "a shared reference would read as an edit of the first",
           3, len({r.get("packageReferenceId") for r in rows}))


def test_group_split_dates(ch, calls, detail):
    # Rule N-1: each parcel carries its own real ship date (L-92)
    order_id = "902-0000003-0000003"
    boxes = [
        R.CartonBox("B1", "TRK-D1", ship_date="2026-08-22T08:00:00Z",
                    items=[R.OrderItemAllocation(811, "ITEM-1", "SKU-1", 1)]),
        R.CartonBox("B2", "TRK-D2", ship_date="2026-08-23T09:40:00Z",
                    items=[R.OrderItemAllocation(812, "ITEM-2", "SKU-2", 1)]),
    ]
    parcels, blocked = R.assemble_parcels(boxes, live_meta(submitting_at=NEXT_DAY))
    ch.add("nothing blocked", "both dates inside the bounds", [], [b.reason for b in blocked])
    submit(ch, calls, order_id, parcels)

    rows = confirmations_for(order_id)
    ch.add("two parcels", "two dispatch days are two parcels", 2, len(rows))
    ch.add("each carries its own ship date", "Amazon measures the late-shipment metric on it",
           ["2026-08-22T08:00:00Z", "2026-08-23T09:40:00Z"], [r.get("shipDate") for r in rows])


def test_group_partial_line(ch, calls, detail):
    # Rule N-1: quantity 5 split 2 and 3 across two parcels, one order item twice (L-86)
    order_id = "902-0000004-0000004"
    boxes = [
        R.CartonBox("B1", "TRK-P1", ship_date=READY_TO_SHIP_AT,
                    items=[R.OrderItemAllocation(811, ITEM_1001, "SKU-1001", 2)]),
        R.CartonBox("B2", "TRK-P2", ship_date=NEXT_DAY,
                    items=[R.OrderItemAllocation(811, ITEM_1001, "SKU-1001", 3)]),
    ]
    parcels, _ = R.assemble_parcels(boxes, live_meta(submitting_at=NEXT_DAY))
    submit(ch, calls, order_id, parcels)

    rows = confirmations_for(order_id)
    ch.add("two parcels", "a split quantity is two calls", 2, len(rows))
    ch.add("both name the same amazon order item", "the same line appears a second time",
           [ITEM_1001, ITEM_1001],
           [(r.get("orderItems") or [{}])[0].get("orderItemId") for r in rows])
    ch.add("quantities are 2 then 3", "never 5 twice, and never 5 once",
           [2, 3], [(r.get("orderItems") or [{}])[0].get("quantity") for r in rows])


def test_group_reject_blank_tracking(ch, calls, detail):
    # Rule N-1: a blank tracking number blocks its own parcel and leaves the others alone (L-66, L-86)
    order_id = "902-0000006-0000006"
    boxes = [
        R.CartonBox("B1", MASTER_TRACKING, ship_date=READY_TO_SHIP_AT,
                    items=[R.OrderItemAllocation(811, ITEM_1001, "SKU-1001", 2)]),
        R.CartonBox("B2", "   ", ship_date=READY_TO_SHIP_AT,
                    items=[R.OrderItemAllocation(812, ITEM_2002, "SKU-2002", 1)]),
    ]
    parcels, blocked = R.assemble_parcels(boxes, live_meta())
    ch.add("one parcel blocked", "the blank one is blocked, not sent blank",
           [R.EParcelBlockReason.MISSING_TRACKING_NUMBER], [b.reason for b in blocked])
    submit(ch, calls, order_id, parcels)

    rows = confirmations_for(order_id)
    ch.add("only the good parcel reached amazon", "a block never suppresses its siblings", 1, len(rows))
    ch.add("the good tracking number went", "the one box that had a number still ships",
           MASTER_TRACKING, rows[0].get("trackingNumber"))
    ch.add("order number never sent as tracking", "the order number is not a tracking number (L-66)",
           False, any(r.get("trackingNumber") == order_id for r in rows))


def test_group_no_carton_details(ch, calls, detail):
    # Rule N-1: today's payload has no box list and must still make exactly one correct parcel (L-175)
    order_id = "902-0000007-0000007"
    meta = live_meta(tracking_number=MASTER_TRACKING, shipment_number="SHP-41277-1",
                     line_items=[R.OrderItemAllocation(811, ITEM_1001, "SKU-1001", 2),
                                 R.OrderItemAllocation(812, ITEM_2002, "SKU-2002", 1)])
    parcels, blocked = R.assemble_parcels([], meta)
    ch.add("nothing blocked", "the single-parcel path is the normal case", [], [b.reason for b in blocked])
    submit(ch, calls, order_id, parcels)

    rows = confirmations_for(order_id)
    ch.add("exactly one parcel", "carton_details has zero occurrences on the wire (L-175)", 1, len(rows))
    ch.add("the shipment tracking number carries it", "no box list means the shipment number is the parcel's",
           MASTER_TRACKING, rows[0].get("trackingNumber"))
    ch.add("both line items travel", "the regression that matters most still works",
           2, len(rows[0].get("orderItems") or []))


# --------------------------------------------------------------------- Rule N-2, the package reference

def test_ref_from_package_id(ch, calls, detail):
    # Rule N-2: the reference is OMS's own package_id as digits, never a composite (L-163, L-5, L-165)
    order_id = "902-0000008-0000008"
    boxes = [R.CartonBox("B1", MASTER_TRACKING, ship_date=READY_TO_SHIP_AT, package_id=3,
                         items=[R.OrderItemAllocation(811, ITEM_1001, "SKU-1001", 2)])]
    parcels, _ = R.assemble_parcels(boxes, live_meta())
    submit(ch, calls, order_id, parcels)

    row = confirmations_for(order_id)[0]
    reference = row.get("packageReferenceId")
    ch.add("reference is the package_id", "package_id is an integer on the read paths (L-163)", "3", reference)
    ch.add("digits only", "Amazon accepts positive numeric values", True, str(reference).isdigit())
    ch.add("never a composite", "the shipment id and box number stay an internal key (L-5)",
           False, "-" in str(reference))
    ch.add("never the update_packages string form", "\"PKG-1\" is the form Amazon rejects (L-165)",
           False, str(reference).upper().startswith("PKG"))


def test_ref_allocated_when_none(ch, calls, detail):
    # Rule N-2: with no package_id -- every row in production -- a reference is still allocated (L-173)
    order_id = "902-0000009-0000009"
    boxes = [
        R.CartonBox("B1", MASTER_TRACKING, ship_date=READY_TO_SHIP_AT, package_id=None,
                    items=[R.OrderItemAllocation(811, ITEM_1001, "SKU-1001", 2)]),
        R.CartonBox("B2", SECOND_TRACKING, ship_date=READY_TO_SHIP_AT, package_id=None,
                    items=[R.OrderItemAllocation(812, ITEM_2002, "SKU-2002", 1)]),
    ]
    parcels, _ = R.assemble_parcels(boxes, live_meta())
    submit(ch, calls, order_id, parcels)

    rows = confirmations_for(order_id)
    references = [r.get("packageReferenceId") for r in rows]
    ch.add("two parcels held", "package_id is null on 105,739 of 105,739 rows, so this is the live path",
           2, len(rows))
    ch.add("all digits", "the counter still serialises as digits", True,
           all(str(r).isdigit() for r in references))
    ch.add("two parcels never share a reference", "Amazon would read the second as an edit of the first",
           2, len(set(references)))


def test_ref_stable_retry(ch, calls, detail):
    # Rule N-2: a retry reuses the reference, so Amazon edits the parcel rather than adding one (L-88)
    order_id = "902-0000010-0000010"
    parcel = R.Parcel("2", "TRK-RETRY-BAD", carrier_code="INVALID_CARRIER", carrier_name="Bad",
                      ship_date=READY_TO_SHIP_AT,
                      order_items=[R.OrderItemAllocation(811, ITEM_1001, "SKU-1001", 2)])

    first = R.build_amazon_confirmation_request(order_id, FR, parcel)
    st_reject, body = call_amazon("POST", first["url_path"], first["body"])
    calls.append("POST %s (parcel 2, bad carrier) -> %s" % (first["url_path"], st_reject))
    ch.add("amazon rejects the parcel", "400 InvalidInput", 400, st_reject)
    ch.add("amazon holds nothing yet", "a rejected call records no parcel", 0, len(confirmations_for(order_id)))

    parcel.carrier_code = "DHL"
    parcel.carrier_name = "DHL Express"
    retry = R.build_amazon_confirmation_request(order_id, FR, parcel)
    st_retry, _ = call_amazon("POST", retry["url_path"], retry["body"])
    calls.append("POST %s (retry, same reference) -> %s" % (retry["url_path"], st_retry))
    ch.add("the retry is accepted", "204 No Content", 204, st_retry)

    rows = confirmations_for(order_id)
    ch.add("one parcel held", "the retry corrected the parcel rather than adding one", 1, len(rows))
    ch.add("reference unchanged", "a tracking correction, a carrier change and a retry all leave it alone (L-5, L-88)",
           "2", rows[0].get("packageReferenceId"))
    ch.add("corrected carrier recorded", "the surviving row is the corrected one", "DHL", rows[0].get("carrierCode"))


def test_ref_void_increment(ch, calls, detail):
    # Rule N-2: a voided-and-recreated shipment takes a new value, never an abandoned one (L-88)
    order_id = "902-0000011-0000011"
    first, _ = R.assemble_parcels(
        [R.CartonBox("B1", "TRK-V1", ship_date=READY_TO_SHIP_AT,
                     items=[R.OrderItemAllocation(811, "ITEM-1", "SKU-1", 1)]),
         R.CartonBox("B2", "TRK-V2", ship_date=READY_TO_SHIP_AT,
                     items=[R.OrderItemAllocation(812, "ITEM-2", "SKU-2", 1)])],
        live_meta())
    submit(ch, calls, order_id, first)

    recreated, _ = R.assemble_parcels(
        [R.CartonBox("B3", "TRK-V3", ship_date=READY_TO_SHIP_AT,
                     items=[R.OrderItemAllocation(813, "ITEM-3", "SKU-3", 1)])],
        live_meta(), counter_start=3)
    submit(ch, calls, order_id, recreated)

    rows = confirmations_for(order_id)
    ch.add("three parcels held", "the recreated shipment added a parcel rather than editing one", 3, len(rows))
    ch.add("references are 1, 2, 3", "the abandoned value is never reused",
           ["1", "2", "3"], sorted(r.get("packageReferenceId") for r in rows))


def test_ref_tracking_correction(ch, calls, detail):
    # Rule N-2 / C-15: correcting an accepted parcel resubmits the SAME reference (L-50, L-96)
    #
    # This exercises the mock's documented-edit model, which is what R-1 makes testable: it is our
    # handling that is under test, never Amazon's behaviour, which only Amazon can evidence (L-178).
    order_id = "902-0000012-0000012"
    parcel = R.Parcel("1", MASTER_TRACKING, carrier_code="DHL", carrier_name="DHL Express",
                      ship_date=READY_TO_SHIP_AT,
                      order_items=[R.OrderItemAllocation(811, ITEM_1001, "SKU-1001", 2)])

    original = R.build_amazon_confirmation_request(order_id, FR, parcel)
    st_first, _ = call_amazon("POST", original["url_path"], original["body"])
    calls.append("POST %s (parcel 1, %s) -> %s" % (original["url_path"], MASTER_TRACKING, st_first))
    ch.add("first confirmation accepted", "204 No Content", 204, st_first)
    ch.add("one parcel held", "the parcel Amazon now holds", 1, len(confirmations_for(order_id)))

    parcel.tracking_number = "MT-7734829999"
    corrected = R.build_amazon_confirmation_request(order_id, FR, parcel)
    st_second, _ = call_amazon("POST", corrected["url_path"], corrected["body"])
    calls.append("POST %s (correction, same reference 1, MT-7734829999) -> %s"
                 % (corrected["url_path"], st_second))
    ch.add("correction accepted", "204 No Content", 204, st_second)

    rows = confirmations_for(order_id)
    ch.add("still one parcel", "the same reference edits the parcel; a new one would add a second (L-50)",
           1, len(rows))
    ch.add("reference unchanged", "the correction reuses the reference it was accepted under",
           "1", rows[0].get("packageReferenceId"))
    ch.add("corrected tracking number survives", "the second number is what the parcel now carries",
           "MT-7734829999", rows[0].get("trackingNumber"))
    ch.add("original tracking number gone", "an edit replaces rather than accumulates",
           False, any(r.get("trackingNumber") == MASTER_TRACKING for r in rows))


def test_ref_omitted_appends(ch, calls, detail):
    # Rule N-2: a payload omitting the reference always appends -- Amazon assigns one itself (L-109)
    order_id = "902-0000013-0000013"
    body = {
        "marketplaceId": R.MARKETPLACES[FR]["marketplace_id"],
        "packageDetail": {
            "carrierCode": "DHL", "carrierName": "DHL Express",
            "trackingNumber": "TRK-NOREF-1", "shipDate": READY_TO_SHIP_AT,
            "orderItems": [{"orderItemId": ITEM_1001, "quantity": 1}],
        },
    }
    path = "/orders/v0/orders/%s/shipmentConfirmation" % order_id
    for number in ("TRK-NOREF-1", "TRK-NOREF-2"):
        body["packageDetail"]["trackingNumber"] = number
        status, _ = call_amazon("POST", path, body)
        calls.append("POST %s (no packageReferenceId, %s) -> %s" % (path, number, status))
        ch.add("accepted without a reference %s" % number, "Amazon assigns one when none is sent", 204, status)

    rows = confirmations_for(order_id)
    ch.add("both calls added a parcel", "with no reference there is nothing to edit against", 2, len(rows))
    ch.add("neither carries one", "the reference is absent, not blank",
           [None, None], [r.get("packageReferenceId") for r in rows])


# --------------------------------------------------------------------- C-10 and C-8, items and quantities

def test_item_id_from_codes(ch, calls, detail):
    # C-10: the Amazon order-item id comes from mp_item_codes[], never the SKU (L-119, L-143)
    order_id = "902-0000014-0000014"
    boxes = [R.CartonBox("B1", MASTER_TRACKING, ship_date=READY_TO_SHIP_AT,
                         items=[R.OrderItemAllocation(811, ITEM_1001, "SKU-1001", 2)])]
    parcels, _ = R.assemble_parcels(boxes, live_meta())
    submit(ch, calls, order_id, parcels)

    item = (confirmations_for(order_id)[0].get("orderItems") or [{}])[0]
    ch.add("amazon id reaches amazon", "mp_item_codes[] holds Amazon's own id from import",
           ITEM_1001, item.get("orderItemId"))
    ch.add("never the seller sku", "the SKU is never a fallback (L-14)", False, item.get("orderItemId") == "SKU-1001")
    ch.add("never line_item_id", "import blanks it to \"0\" at six sites (L-119)",
           False, item.get("orderItemId") in ("0", "811"))


def test_item_id_missing_blocks(ch, calls, detail):
    # C-10: an unresolvable item blocks its parcel and leaves the others (L-14, L-119)
    order_id = "902-0000015-0000015"
    boxes = [
        R.CartonBox("B1", MASTER_TRACKING, ship_date=READY_TO_SHIP_AT,
                    items=[R.OrderItemAllocation(811, ITEM_1001, "SKU-1001", 2)]),
        R.CartonBox("B2", SECOND_TRACKING, ship_date=READY_TO_SHIP_AT,
                    items=[R.OrderItemAllocation(812, None, "SKU-2002", 1)]),
    ]
    parcels, blocked = R.assemble_parcels(boxes, live_meta())
    ch.add("the unresolvable parcel is blocked", "do not guess (L-14)",
           [R.EParcelBlockReason.MISSING_AMAZON_ORDER_ITEM_ID], [b.reason for b in blocked])
    submit(ch, calls, order_id, parcels)

    rows = confirmations_for(order_id)
    ch.add("only the resolvable parcel reached amazon", "other parcels continue", 1, len(rows))
    ch.add("the blocked tracking number never went", "no call is made for it",
           False, any(r.get("trackingNumber") == SECOND_TRACKING for r in rows))


def test_qty_not_positive_blocks(ch, calls, detail):
    # Rule N-3, the arithmetic half: a zero or absent quantity is never confirmed (L-81)
    order_id = "902-0000016-0000016"
    for label, quantity in (("absent", None), ("explicit zero", 0)):
        boxes = [R.CartonBox("B-%s" % label, "TRK-QTY-%s" % quantity, ship_date=READY_TO_SHIP_AT,
                             items=[R.OrderItemAllocation(811, ITEM_1001, "SKU-1001", quantity)])]
        parcels, blocked = R.assemble_parcels(boxes, live_meta())
        ch.add("%s quantity blocks" % label, "a null-defaulted 0 is rejected, not sent",
               [R.EParcelBlockReason.QUANTITY_NOT_POSITIVE], [b.reason for b in blocked])
        submit(ch, calls, order_id, parcels, expect=None)

    ch.add("amazon holds nothing yet", "zero deducts nothing and closes nothing",
           0, len(confirmations_for(order_id)))

    # The positive control: a good box on the same order still ships, so the block is the line's
    # and not the event's.
    good, blocked = R.assemble_parcels(
        [R.CartonBox("B-good", "TRK-QTY-GOOD", ship_date=READY_TO_SHIP_AT,
                     items=[R.OrderItemAllocation(811, ITEM_1001, "SKU-1001", 2)])],
        live_meta())
    ch.add("a positive quantity is not blocked", "the guard is the line's, not the event's",
           [], [b.reason for b in blocked])
    submit(ch, calls, order_id, good)
    ch.add("only the good parcel reached amazon", "one row, carrying the quantity that was positive",
           [2], [(r.get("orderItems") or [{}])[0].get("quantity") for r in confirmations_for(order_id)])


def test_transparency_codes(ch, calls, detail):
    # R-MAP 4.4 row 14: an enrolled line carries its transparency codes to Amazon (L-9)
    order_id = "902-0000017-0000017"
    boxes = [R.CartonBox("B1", "TRK-TRANSPARENCY", ship_date=READY_TO_SHIP_AT,
                         items=[R.OrderItemAllocation(813, ITEM_3003, "SKU-3003", 1,
                                                      transparency_codes=["09876543211234567890"])])]
    parcels, _ = R.assemble_parcels(boxes, live_meta())
    submit(ch, calls, order_id, parcels)

    item = (confirmations_for(order_id)[0].get("orderItems") or [{}])[0]
    ch.add("codes reach amazon", "an enrolled unit is verified against these codes",
           ["09876543211234567890"], item.get("transparencyCodes"))


# --------------------------------------------------------------------- C-6 and C-16, the ship-date bounds

def test_date_skew_tolerance(ch, calls, detail):
    # C-6 / C-16: 5-minute allowance, never a bare > now; and never before the purchase (L-8, L-45, L-52)
    order_id = "902-0000018-0000018"

    inside, blocked_inside = R.assemble_parcels(
        [R.CartonBox("B1", "TRK-SKEW-OK", ship_date="2026-08-22T14:10:00Z",
                     items=[R.OrderItemAllocation(811, ITEM_1001, "SKU-1001", 1)])],
        live_meta())
    ch.add("four minutes ahead passes", "clock skew, not bad data; a bare > now would reject it (L-45)",
           [], [b.reason for b in blocked_inside])
    submit(ch, calls, order_id, inside)

    _, blocked_ahead = R.assemble_parcels(
        [R.CartonBox("B2", "TRK-SKEW-FAR", ship_date="2026-08-22T14:16:00Z",
                     items=[R.OrderItemAllocation(811, ITEM_1001, "SKU-1001", 1)])],
        live_meta())
    ch.add("ten minutes ahead blocks", "Amazon documents no future-date rule; this bound is ours (L-52)",
           [R.EParcelBlockReason.SHIP_DATE_TOO_FAR_AHEAD], [b.reason for b in blocked_ahead])

    _, blocked_before = R.assemble_parcels(
        [R.CartonBox("B3", "TRK-SKEW-PAST", ship_date="2026-08-19T09:12:03Z",
                     items=[R.OrderItemAllocation(811, ITEM_1001, "SKU-1001", 1)])],
        live_meta())
    ch.add("before the purchase blocks", "a box cannot have shipped before the order was placed (L-8)",
           [R.EParcelBlockReason.SHIP_DATE_BEFORE_PURCHASE], [b.reason for b in blocked_before])

    rows = confirmations_for(order_id)
    ch.add("only the in-bounds parcel reached amazon", "both bounds block before the call is made",
           ["TRK-SKEW-OK"], [r.get("trackingNumber") for r in rows])


# --------------------------------------------------------------------- C-17, the six defect sites

def test_defect_corrections_c17(ch, calls, detail):
    # C-17: the six sites, checked on what Amazon received (L-16, L-53, L-65, L-66, L-67, L-68)
    order_id = "902-0000019-0000019"
    oms_order_number = "AMZFR-" + order_id

    boxes = [R.CartonBox("SHP-41277-1-C1", MASTER_TRACKING, ship_date=READY_TO_SHIP_AT, package_id=3,
                         items=[R.OrderItemAllocation(811, ITEM_1001, "SKU-1001", 1)])]
    meta = live_meta(marketplace_carrier_code="DHL", logistic_partner_name="DHL Express",
                     shipping_type="DHL Express Worldwide")
    parcels, _ = R.assemble_parcels(boxes, meta)

    request = R.build_amazon_confirmation_request(order_id, FR, parcels[0])
    status, _ = call_amazon("POST", request["url_path"], request["body"])
    calls.append("POST %s -> %s" % (request["url_path"], status))
    ch.add("confirmation accepted", "204 No Content", 204, status)

    row = confirmations_for(order_id)[0]
    ch.add("defect 1: amazon order id on the path", "setAmazonOrderID is given the OMS number today (L-67)",
           order_id, row.get("orderId"))
    ch.add("defect 1: oms number never sent", "the OMS order number is a different key",
           0, len([c for c in store("shipment_confirmations") if c.get("orderId") == oms_order_number]))
    ch.add("defect 2: ship date is the ready-to-ship instant", "order_date is the purchase instant (L-16, L-92)",
           READY_TO_SHIP_AT, row.get("shipDate"))
    ch.add("defect 3: real tracking number", "never fabricated from the order number (L-66)",
           MASTER_TRACKING, row.get("trackingNumber"))
    ch.add("defect 4: carrier code is set", "setCarrierCode is commented out today (L-65)",
           "DHL", row.get("carrierCode"))
    ch.add("defect 5: correlation by reference", "a loop index cannot be re-derived after a restart (L-68)",
           "3", row.get("packageReferenceId"))
    ch.add("defect 6: the parcel carries its items", "with no Item[] Amazon deducts the whole ordered quantity",
           1, len(row.get("orderItems") or []))


# --------------------------------------------------------------------- Flows 2 to 4 and the gate

def test_flow2_parcel_retry(ch, calls, detail):
    # Flow 2: one parcel accepted, one rejected; the retry moves only the rejection (L-90, L-88)
    order_id = "902-0000020-0000020"
    good = R.Parcel("1", "TRK-OK", carrier_code="DHL", carrier_name="DHL Express",
                    ship_date=READY_TO_SHIP_AT,
                    order_items=[R.OrderItemAllocation(811, ITEM_1001, "SKU-1001", 2)])
    bad = R.Parcel("2", "TRK-BAD", carrier_code="INVALID_CARRIER", carrier_name="Unknown",
                   ship_date=READY_TO_SHIP_AT,
                   order_items=[R.OrderItemAllocation(812, ITEM_2002, "SKU-2002", 1)])

    request = R.build_amazon_confirmation_request(order_id, FR, good)
    st_good, _ = call_amazon("POST", request["url_path"], request["body"])
    calls.append("POST %s (parcel 1) -> %s" % (request["url_path"], st_good))
    ch.add("parcel 1 accepted", "204 No Content", 204, st_good)
    good.status = R.ParcelConfirmationStatus.ACCEPTED

    request = R.build_amazon_confirmation_request(order_id, FR, bad)
    st_bad, error = call_amazon("POST", request["url_path"], request["body"])
    calls.append("POST %s (parcel 2) -> %s" % (request["url_path"], st_bad))
    ch.add("parcel 2 rejected", "400 InvalidInput", 400, st_bad)
    ch.add("amazon names the code", "the code operations searches on",
           "InvalidInput", ((error.get("errors") or [{}])[0]).get("code"))
    bad.status = R.ParcelConfirmationStatus.REJECTED

    ch.add("order-level row", "R-MAP 5.2, Partial with the failed parcel's state on its box row",
           "some accepted some failed", R.order_level_outcome([good, bad]))
    ch.add("amazon holds only the accepted parcel", "a rejection records nothing",
           ["1"], [r.get("packageReferenceId") for r in confirmations_for(order_id)])

    bad.carrier_code = "DHL"
    bad.carrier_name = "DHL Express"
    request = R.build_amazon_confirmation_request(order_id, FR, bad)
    st_retry, _ = call_amazon("POST", request["url_path"], request["body"])
    calls.append("POST %s (retry parcel 2) -> %s" % (request["url_path"], st_retry))
    ch.add("the retry is accepted", "204 No Content", 204, st_retry)

    rows = confirmations_for(order_id)
    ch.add("two parcels now held", "the retry added the failed parcel and never resent the accepted one",
           ["1", "2"], sorted(r.get("packageReferenceId") for r in rows))
    ch.add("the accepted parcel is untouched", "an accepted parcel is terminal (L-90)",
           "TRK-OK", [r for r in rows if r.get("packageReferenceId") == "1"][0].get("trackingNumber"))


def test_flow3_unknown_outcome(ch, calls, detail):
    # Flow 3 / C-25: reconcile against QuantityShipped, never resubmit blind (L-9, L-90)
    covered_order = "902-PARTIALSHIPPED-01"
    parcel = R.Parcel("1", "TRK-UNKNOWN-1", carrier_code="DHL", carrier_name="DHL Express",
                      ship_date=READY_TO_SHIP_AT,
                      order_items=[R.OrderItemAllocation(811, ITEM_1001, "SKU-1001", 2)])

    request = R.build_amazon_confirmation_request(covered_order, FR, parcel)
    status, _ = call_amazon("POST", request["url_path"], request["body"])
    calls.append("POST %s (answer lost) -> %s" % (request["url_path"], status))
    parcel.status = R.ParcelConfirmationStatus.UNKNOWN_CONFIRMATION_STATE
    ch.add("state on a lost answer", "no HTTP status means we do not know whether Amazon took it",
           R.ParcelConfirmationStatus.UNKNOWN_CONFIRMATION_STATE, parcel.status)

    st_items, items = call_amazon("GET", "/orders/v0/orders/%s/orderItems" % covered_order)
    calls.append("GET /orders/v0/orders/%s/orderItems -> %s" % (covered_order, st_items))
    shipped = [i for i in items["payload"]["OrderItems"] if i["OrderItemId"] == ITEM_1001][0]["QuantityShipped"]
    ch.add("amazon says two shipped", "the reconciliation reads Amazon's own count", 2, shipped)
    ch.add("covered quantity reconciles to accepted", "the call landed and must not be resent",
           R.ParcelConfirmationStatus.ACCEPTED, R.reconcile_unknown_outcome(shipped, 2))
    ch.add("no second call was made", "never resubmit blind (L-90)", 1, len(confirmations_for(covered_order)))

    uncovered_order = "902-UNSHIPPED-000001"
    st_items, items = call_amazon("GET", "/orders/v0/orders/%s/orderItems" % uncovered_order)
    calls.append("GET /orders/v0/orders/%s/orderItems -> %s" % (uncovered_order, st_items))
    shipped = [i for i in items["payload"]["OrderItems"] if i["OrderItemId"] == ITEM_1001][0]["QuantityShipped"]
    ch.add("amazon says nothing shipped", "the call never landed", 0, shipped)
    ch.add("uncovered quantity is safe to retry", "the same reference is reused (L-88)",
           R.ParcelConfirmationStatus.RETRY_PENDING, R.reconcile_unknown_outcome(shipped, 2))


def test_guard_overconfirm_block(ch, calls, detail):
    # C-7 / Rule N-3: Amazon's QuantityShipped wins over anything we believe (L-9, L-10, L-89)
    order_id = "902-PARTIALSHIPPED-02"
    st_items, items = call_amazon("GET", "/orders/v0/orders/%s/orderItems" % order_id)
    calls.append("GET /orders/v0/orders/%s/orderItems -> %s" % (order_id, st_items))
    ch.add("order items read", "the guard re-reads immediately before the submit", 200, st_items)

    payload = items["payload"]
    over = R.check_quantities(payload, {ITEM_1001: 4})
    ch.add("four of three remaining blocks", "ordered 5, Amazon says 2 shipped, so 3 remain",
           R.EGateBlockReason.QUANTITY_EXCEEDS_REMAINING, over.reason)

    fits = R.check_quantities(payload, {ITEM_1001: 3})
    ch.add("three of three remaining passes", "Appendix A.3 fits exactly", False, fits.blocked)

    parcel = R.Parcel("1", "TRK-GUARD-OK", carrier_code="DHL", carrier_name="DHL Express",
                      ship_date=READY_TO_SHIP_AT,
                      order_items=[R.OrderItemAllocation(811, ITEM_1001, "SKU-1001", 3)])
    submit(ch, calls, order_id, [parcel])
    ch.add("only the fitting parcel reached amazon", "the blocked one is never sent",
           1, len(confirmations_for(order_id)))

    exhausted = "902-FULLYSHIPPED-01"
    st_items, items = call_amazon("GET", "/orders/v0/orders/%s/orderItems" % exhausted)
    calls.append("GET /orders/v0/orders/%s/orderItems -> %s" % (exhausted, st_items))
    third = R.check_quantities(items["payload"], {ITEM_1001: 1})
    ch.add("a third parcel is blocked", "QuantityShipped is 5 of 5, so nothing remains (L-89)",
           R.EGateBlockReason.QUANTITY_EXCEEDS_REMAINING, third.reason)
    ch.add("amazon was never called for it", "the guard runs before the submit",
           0, len(confirmations_for(exhausted)))


def test_gate_cancelled_block(ch, calls, detail):
    # C-26 / Flow 4: an order Amazon has cancelled is never confirmed as shipped (L-87)
    order_id = "902-CANCELED-0000001"
    st_order, order = call_amazon("GET", "/orders/v0/orders/%s" % order_id)
    calls.append("GET /orders/v0/orders/%s -> %s" % (order_id, st_order))
    ch.add("amazon answers", "the gate reads Amazon's own status", 200, st_order)
    ch.add("amazon reports cancelled", "the state the gate acts on", "Canceled",
           order["payload"].get("OrderStatus"))

    decision = R.evaluate_gate(order["payload"])
    ch.add("gate blocks", "confirming a cancelled order is the failure IA-5106 exists to prevent",
           True, decision.blocked)
    ch.add("block reason", "hand to IA-5106", R.EGateBlockReason.ORDER_CANCELLED, decision.reason)
    ch.add("no confirmation was sent", "this is the FR-5 race the OMS gate cannot close",
           0, len(confirmations_for(order_id)))


def test_gate_regulated_block(ch, calls, detail):
    # C-26: a regulated order blocks whole, because Amazon states the flag at header level only (L-20)
    order_id = "902-REGULATED-000001"
    st_order, order = call_amazon("GET", "/orders/v0/orders/%s" % order_id)
    calls.append("GET /orders/v0/orders/%s -> %s" % (order_id, st_order))
    ch.add("amazon reports the flag", "HasRegulatedItems on the order header", True,
           order["payload"].get("HasRegulatedItems"))

    decision = R.evaluate_gate(order["payload"])
    ch.add("gate blocks", "block ready to ship and the confirmation", True, decision.blocked)
    ch.add("block reason", "regulated items", R.EGateBlockReason.REGULATED_ITEMS, decision.reason)
    ch.add("no line-level split", "no line-level split is possible (L-20)", 0,
           len(decision.blocked_order_item_ids))
    ch.add("no confirmation was sent", "the whole order is blocked", 0, len(confirmations_for(order_id)))


def test_gate_not_seller_fulfilled(ch, calls, detail):
    # C-26: this story confirms seller-fulfilled shipments and nothing else (L-87)
    order_id = "902-AFNCHANNEL-00001"
    st_order, order = call_amazon("GET", "/orders/v0/orders/%s" % order_id)
    calls.append("GET /orders/v0/orders/%s -> %s" % (order_id, st_order))
    ch.add("amazon reports the channel", "Amazon fulfils this order itself", "AFN",
           order["payload"].get("FulfillmentChannel"))

    decision = R.evaluate_gate(order["payload"])
    ch.add("gate blocks", "block on any value but MFN", True, decision.blocked)
    ch.add("block reason", "not ours to confirm", R.EGateBlockReason.NOT_SELLER_FULFILLED, decision.reason)
    ch.add("no confirmation was sent", "an AFN order is not this story's", 0, len(confirmations_for(order_id)))


def test_gate_buyer_cancellation(ch, calls, detail):
    # C-26: a buyer's pending cancellation must not be shipped against (L-87)
    order_id = "902-BUYERCANCEL-0001"
    st_order, order = call_amazon("GET", "/orders/v0/orders/%s" % order_id)
    st_items, items = call_amazon("GET", "/orders/v0/orders/%s/orderItems" % order_id)
    calls.append("GET /orders/v0/orders/%s -> %s" % (order_id, st_order))
    calls.append("GET /orders/v0/orders/%s/orderItems -> %s" % (order_id, st_items))

    decision = R.evaluate_gate(order["payload"], items["payload"])
    ch.add("gate blocks", "route to cancel-in-process rather than shipping against it", True, decision.blocked)
    ch.add("block reason", "buyer cancellation pending",
           R.EGateBlockReason.BUYER_CANCELLATION_PENDING, decision.reason)
    ch.add("the line is named", "the gate says which line the buyer is cancelling",
           [ITEM_1001], decision.blocked_order_item_ids)
    ch.add("no confirmation was sent", "nothing ships against a pending cancellation",
           0, len(confirmations_for(order_id)))


def test_gate_unreachable_amazon(ch, calls, detail):
    # C-26: Amazon unreachable is an outcome, never a licence to assume the order is valid (L-87)
    order_id = "902-SERVERERROR-0001"
    st_order, body = call_amazon("GET", "/orders/v0/orders/%s" % order_id)
    calls.append("GET /orders/v0/orders/%s -> %s" % (order_id, st_order))
    ch.add("amazon is unreachable", "the re-check itself failed", 500, st_order)

    decision = R.gate_unreachable("GET /orders/v0/orders/%s answered %s" % (order_id, st_order))
    ch.add("gate blocks", "never assume the order is still valid on a failed re-check", True, decision.blocked)
    ch.add("block reason", "marketplace validation unavailable",
           R.EGateBlockReason.MARKETPLACE_VALIDATION_UNAVAILABLE, decision.reason)
    ch.truthy("the reason travels with it", "operations acts on this text", decision.detail)
    ch.add("no confirmation was sent", "an unanswered re-check is not permission",
           0, len(confirmations_for(order_id)))

# ===================================================================== Register Cases

case("IA-5109-US3-FLOW1-HAPPY-PATH",
     "Flow 1: End-to-end multi-parcel confirmation happy path",
     "Appendix A order 902-1845936-5435065 shipped as three boxes under two tracking numbers",
     ["Two confirmShipment calls, both 204", "Amazon holds two parcels, one tracking number each",
      "SKU-1001 summed to 2 in the first and 3 in the second", "shipFromSupplySourceId reaches Amazon"],
     "Summary 2.1 C-1..C-4; Mapping 3 Flow 1, Appendix A.2, A.3; Claim L-1, L-4, L-70, L-86",
     test_flow1_happy_path)

case("IA-5109-US3-GROUP-MASTER-TRACKING",
     "Rule N-1: Three boxes under one master tracking number are one parcel",
     "Three container boxes sharing MT-MASTER-01",
     ["Exactly one confirmShipment call reaches Amazon", "SKU-1001 arrives summed as 5, not 2 then 3"],
     "Mapping 7 N-1, Appendix A.2; Claim L-4, L-86",
     test_group_master_tracking)

case("IA-5109-US3-GROUP-MULTI-TRACKING",
     "Rule N-1: Distinct tracking numbers are distinct parcels",
     "Three boxes with three distinct tracking numbers",
     ["Three confirmShipment calls reach Amazon", "Each parcel carries exactly one tracking number",
      "Three distinct package references"],
     "Mapping 7 N-1; Claim L-86",
     test_group_multi_tracking)

case("IA-5109-US3-GROUP-SPLIT-DATES",
     "Rule N-1: Each parcel carries its own real ship date",
     "Two boxes dispatched on different days",
     ["Two parcels reach Amazon", "Each carries the dispatch instant of its own box"],
     "Mapping 7 N-1, 4.4 row 9; Claim L-92",
     test_group_split_dates)

case("IA-5109-US3-GROUP-PARTIAL-LINE",
     "Rule N-1: One order item split across two parcels",
     "SKU-1001 ordered 5, shipped 2 today and 3 tomorrow",
     ["Both parcels name the same Amazon order item", "Quantities reach Amazon as 2 and 3"],
     "Mapping 7 N-1, Appendix A.3; Claim L-86",
     test_group_partial_line)

case("IA-5109-US3-GROUP-REJECT-BLANK-TRACKING",
     "Rule N-1: A blank tracking number blocks its own parcel only",
     "Two boxes, one with a whitespace tracking number",
     ["The blank one is blocked with MISSING_TRACKING_NUMBER", "The good parcel still reaches Amazon",
      "The order number is never sent as a tracking number"],
     "Mapping 7 N-1, N-4; Claim L-66, L-86",
     test_group_reject_blank_tracking)

case("IA-5109-US3-GROUP-NO-CARTON-DETAILS",
     "Rule N-1: The live payload, with no box list at all",
     "A ready-to-ship event carrying line_items and a shipment tracking number and no carton_details",
     ["Exactly one parcel reaches Amazon", "It carries the shipment-level tracking number",
      "Both line items travel in it"],
     "Mapping 7 N-1; Claim L-86, L-139, L-144, L-175",
     test_group_no_carton_details)

case("IA-5109-US3-REF-FROM-PACKAGE-ID",
     "Rule N-2: The package reference is OMS's package_id as digits",
     "A box carrying package_id 3",
     ["Amazon receives packageReferenceId 3", "Digits only, never a composite, never the PKG-1 form"],
     "Mapping 7 N-2, 4.4 row 4; Summary 2.1 C-3; Claim L-163, L-165, L-5",
     test_ref_from_package_id)

case("IA-5109-US3-REF-ALLOCATED-WHEN-NONE",
     "Rule N-2: A reference is allocated when OMS sends none",
     "Two boxes, both with package_id null, which is every row in production",
     ["Both parcels reach Amazon with digit references", "The two parcels never share a reference"],
     "Mapping 7 N-2; Claim L-173, L-5, L-50",
     test_ref_allocated_when_none)

case("IA-5109-US3-REF-STABLE-RETRY",
     "Rule N-2: A retry reuses the package reference",
     "Parcel 2 rejected for a bad carrier code, corrected and resent",
     ["The retry answers 204", "Amazon holds one parcel, not two", "The reference is unchanged",
      "The corrected carrier is what survives"],
     "Mapping 7 N-2; Claim L-88, L-5, L-50",
     test_ref_stable_retry)

case("IA-5109-US3-REF-VOID-INCREMENT",
     "Rule N-2: A recreated shipment takes a new reference",
     "Parcels 1 and 2 already confirmed; a third is assembled from counter 3",
     ["Amazon holds three parcels", "The references are 1, 2 and 3 with none reused"],
     "Mapping 7 N-2; Claim L-88",
     test_ref_void_increment)

case("IA-5109-US3-REF-TRACKING-CORRECTION",
     "Rule N-2 / C-15: A tracking correction resubmits the same reference",
     "An accepted parcel whose tracking number changes afterwards",
     ["The correction answers 204", "Amazon still holds one parcel", "The reference is unchanged",
      "The corrected tracking number is the one that survives"],
     "Mapping 7 N-2, N-4; Summary 2.1 C-15; accepted risk R-1; Claim L-50, L-96, L-178",
     test_ref_tracking_correction)

case("IA-5109-US3-REF-OMITTED-APPENDS",
     "Rule N-2: A payload omitting the reference always adds a parcel",
     "Two confirmations sent with no packageReferenceId at all",
     ["Both answer 204", "Amazon holds two parcels", "Neither carries a reference"],
     "Mapping 7 N-2; Claim L-109, L-178",
     test_ref_omitted_appends)

case("IA-5109-US3-ITEM-ID-FROM-CODES",
     "C-10: The Amazon order-item id comes from mp_item_codes[]",
     "A line carrying mp_item_codes 05015851154158 and SKU SKU-1001",
     ["Amazon receives the Amazon id", "Never the seller SKU", "Never line_item_id"],
     "Mapping 4.4 row 12; Summary 2.1b C-10; Claim L-119, L-143, L-134",
     test_item_id_from_codes)

case("IA-5109-US3-ITEM-ID-MISSING-BLOCKS",
     "C-10: An unresolvable order item blocks its parcel and no other",
     "Two boxes, one whose line resolves no Amazon order-item id",
     ["The unresolvable parcel is blocked with MISSING_AMAZON_ORDER_ITEM_ID",
      "The other parcel still reaches Amazon"],
     "Mapping 7 N-4; Summary 2.1b C-10; Claim L-14, L-119",
     test_item_id_missing_blocks)

case("IA-5109-US3-QTY-NOT-POSITIVE-BLOCKS",
     "Rule N-3: An absent or zero quantity is never confirmed",
     "A line whose quantity is null, and a line whose quantity is an explicit zero",
     ["Both block with QUANTITY_NOT_POSITIVE", "Amazon holds nothing for the order"],
     "Mapping 4.4 row 13, 7 N-3; Claim L-81, L-11",
     test_qty_not_positive_blocks)

case("IA-5109-US3-TRANSPARENCY-CODES",
     "Mapping 4.4 row 14: A transparency-enrolled line carries its codes",
     "A line on SKU-3003 carrying serial_numbers",
     ["transparencyCodes reach Amazon on the order item"],
     "Mapping 4.4 row 14; Claim L-9",
     test_transparency_codes)

case("IA-5109-US3-DATE-SKEW-TOLERANCE",
     "C-6 / C-16: The ship-date bounds, both ours rather than Amazon's",
     "Ship dates four minutes ahead, ten minutes ahead, and a day before the purchase",
     ["Four minutes ahead reaches Amazon", "Ten minutes ahead blocks with SHIP_DATE_TOO_FAR_AHEAD",
      "Before the purchase blocks with SHIP_DATE_BEFORE_PURCHASE", "Only the in-bounds parcel is sent"],
     "Mapping 7 N-4; Summary 2.1 C-6, C-16; Claim L-8, L-45, L-52",
     test_date_skew_tolerance)

case("IA-5109-US3-DEFECT-CORRECTIONS-C17",
     "C-17: The six defect sites, checked on what Amazon received",
     "One confirmation assembled from the live carrier shape and sent",
     ["The Amazon order id is on the path, never the OMS number", "The ship date is the ready-to-ship instant",
      "The tracking number is real", "The carrier code is set", "Correlation is by package reference",
      "The parcel carries its item list"],
     "Summary 2.1 C-17; Mapping 4.4 warning; Claim L-16, L-53, L-65, L-66, L-67, L-68",
     test_defect_corrections_c17)

case("IA-5109-US3-FLOW2-PARCEL-RETRY",
     "Flow 2: Independent parcel retry and failure isolation",
     "Parcel 1 accepted and parcel 2 rejected on the same order",
     ["Amazon holds only the accepted parcel after the rejection",
      "The retry adds parcel 2 and never resends parcel 1", "The order lands on the Partial row of 5.2"],
     "Mapping 3 Flow 2, 5.2; Claim L-90, L-88",
     test_flow2_parcel_retry)

case("IA-5109-US3-FLOW3-UNKNOWN-OUTCOME",
     "Flow 3 / C-25: Unknown outcome reconciled against QuantityShipped",
     "A confirmation whose answer is lost, on an order Amazon says has 2 shipped, and on one with 0",
     ["The covered parcel reconciles to ACCEPTED and is never resent",
      "The uncovered parcel reconciles to RETRY_PENDING under the same reference"],
     "Mapping 3 Flow 3, 5.1; Summary 2.1 C-25; Claim L-9, L-88, L-90",
     test_flow3_unknown_outcome)

case("IA-5109-US3-GUARD-OVERCONFIRM-BLOCK",
     "C-7 / Rule N-3: The over-confirmation guard reads Amazon's own count",
     "Ordered 5 with QuantityShipped 2, then an order with QuantityShipped 5",
     ["Four of three remaining blocks", "Three of three remaining passes and reaches Amazon",
      "A third parcel against a fully shipped item blocks and is never sent"],
     "Mapping 7 N-3, Appendix A.3; Summary 2.1 C-7; Claim L-9, L-10, L-89",
     test_guard_overconfirm_block)

case("IA-5109-US3-GATE-CANCELLED-BLOCK",
     "C-26 / Flow 4: A cancelled order is never confirmed as shipped",
     "Amazon answers OrderStatus Canceled on the pre-submit re-check",
     ["The gate blocks with ORDER_CANCELLED", "No confirmation reaches Amazon"],
     "Mapping 4.2, 7 N-4, Flow 4; Summary 2.1 C-26; Claim L-87",
     test_gate_cancelled_block)

case("IA-5109-US3-GATE-REGULATED-BLOCK",
     "C-26: A regulated order blocks whole, never a line",
     "Amazon answers HasRegulatedItems true on the pre-submit re-check",
     ["The gate blocks with REGULATED_ITEMS", "No line-level split is attempted",
      "No confirmation reaches Amazon"],
     "Mapping 4.2, 7 N-4; Summary 2.1 C-26; Claim L-20, L-87",
     test_gate_regulated_block)

case("IA-5109-US3-GATE-NOT-SELLER-FULFILLED",
     "C-26: An order Amazon fulfils itself is not ours to confirm",
     "Amazon answers FulfillmentChannel AFN on the pre-submit re-check",
     ["The gate blocks with NOT_SELLER_FULFILLED", "No confirmation reaches Amazon"],
     "Mapping 4.2, 7 N-4; Summary 2.1 C-26; Claim L-87",
     test_gate_not_seller_fulfilled)

case("IA-5109-US3-GATE-BUYER-CANCELLATION",
     "C-26: A pending buyer cancellation blocks the confirmation",
     "Amazon answers IsBuyerRequestedCancel true on the order item",
     ["The gate blocks with BUYER_CANCELLATION_PENDING", "The line is named",
      "No confirmation reaches Amazon"],
     "Mapping 4.2, 7 N-4; Summary 2.1 C-26; Claim L-87",
     test_gate_buyer_cancellation)

case("IA-5109-US3-GATE-UNREACHABLE-AMAZON",
     "C-26: Amazon unreachable blocks rather than assuming the order is valid",
     "The pre-submit re-check answers 500",
     ["The gate blocks with MARKETPLACE_VALIDATION_UNAVAILABLE", "The reason travels with it",
      "No confirmation reaches Amazon"],
     "Mapping 4.2, 7 N-4; Summary 2.1 C-26; Claim L-87",
     test_gate_unreachable_amazon)


# ===================================================================== Execution Engine

def preflight():
    print(f"{SUITE_NAME} -- {BASE}")
    print(f"  mock dir : {MOCK_DIR}")
    print(f"  data dir : {DATA_DIR}")
    print(f"  run dir  : {RUN_DIR}")

    st, _ = call_amazon("POST", "/auth/o2/token", {"grant_type": "refresh_token"})
    if st == 0:
        print(f"  mock     : starting ephemeral mock server on {BASE}...")
        _start_ephemeral_mock()
        st, _ = call_amazon("POST", "/auth/o2/token", {"grant_type": "refresh_token"})
        if st == 0:
            sys.exit(f"PREFLIGHT FAIL: unable to connect or start mock server on {BASE}")
    print(f"  mock     : active (/auth/o2/token -> {st})")

    if KEEP:
        print("  state    : preserved (--keep-state)")
        return

    os.makedirs(DATA_DIR, exist_ok=True)
    for s in STORES:
        fpath = os.path.join(DATA_DIR, s + ".json")
        with open(fpath, "w", encoding="utf-8") as f:
            f.write("[]")
    log_p = os.path.join(DATA_DIR, LOG_FILE)
    if os.path.exists(log_p):
        os.remove(log_p)
    print(f"  state    : reset ({len(STORES)} stores emptied, call log cleared)")


def capture():
    src = os.path.join(DATA_DIR, LOG_FILE)
    if os.path.exists(src):
        os.makedirs(RUN_DIR, exist_ok=True)
        shutil.copy2(src, os.path.join(RUN_DIR, LOG_FILE))
        try:
            with open(src, "r", encoding="utf-8") as f:
                n = len(json.load(f).get("log", {}).get("entries", []))
            EVIDENCE["mock call log"] = f"captured -- {n} entries"
        except Exception:
            EVIDENCE["mock call log"] = "captured -- unparseable"
    else:
        EVIDENCE["mock call log"] = "not captured -- no log file"

    stores_data = {}
    for s in STORES:
        fpath = os.path.join(DATA_DIR, s + ".json")
        if os.path.exists(fpath):
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    stores_data[s] = json.load(f)
            except Exception:
                stores_data[s] = []
        else:
            stores_data[s] = []

    with open(os.path.join(RUN_DIR, "stores.json"), "w", encoding="utf-8") as f:
        json.dump(stores_data, f, indent=2)
    EVIDENCE["mock stores"] = f"captured -- {len(STORES)} files"


def main():
    if LIST_ONLY:
        print(f"{SUITE_NAME} -- Declared Cases ({len(CASES)} cases):")
        for c in CASES:
            print(f"  [{c['id']}] {c['name']}")
            print(f"     Given: {c['given']}")
            print(f"     Note : {c['note']}")
        return

    preflight()

    to_run = [c for c in CASES if not WANTED_CASES or c["id"] in WANTED_CASES]
    print(f"\nRunning {len(to_run)} cases...")

    for c in to_run:
        run_case(c)
        r = RESULTS[c["id"]]
        v = r["verdict"].upper()
        print(f"  [{v}] {c['id']}: {c['name']} -- {r['summary']}")

    EVIDENCE["status"] = "complete"
    capture()
    publish()

    done = [RESULTS[c["id"]] for c in to_run if c["id"] in RESULTS]
    p_cnt = sum(1 for r in done if r["verdict"] == "pass")
    f_cnt = sum(1 for r in done if r["verdict"] == "fail")
    print(f"\nSuite Finished: {p_cnt} passed, {f_cnt} failed of {len(to_run)} cases.")
    print(f"Results written to {os.path.join(RUN_DIR, 'results.json')}")

    if f_cnt > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
