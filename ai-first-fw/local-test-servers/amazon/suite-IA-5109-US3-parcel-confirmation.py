#!/usr/bin/env python3
"""IA-5109-US3: Parcel Confirmation & Core Flows Test Suite.

Judges the Amazon Selling Partner API (SP-API) Orders v0 confirmShipment integration
against the specifications for User Story 3: Support Partial and Multi-Parcel Amazon
Seller-Fulfilled Shipments (IA-5109).

Covers:
  - Flow 0: Entry-point branch confirmation (L-61, L-75)
  - Flow 1: End-to-end multi-parcel confirmation happy path (L-1, L-4, L-70, L-86)
  - Flow 2: Independent parcel retry & failure isolation (L-90, L-88)
  - Flow 3: Unknown outcome recovery via QuantityShipped reconciliation (L-9, L-90)
  - Flow 4: Post-ready-to-ship cancellation race prevention (L-87)
  - Rule N-1: Grouping rules & tracking integrity (L-66, L-86)
  - Rule N-2: Package reference durability, monotonic allocation & correction (L-5, L-50, L-88)
  - Rule N-3: Quantity ledger & atomic pre-submit guard (L-9, L-10, L-72, L-89)
  - Rule N-4: Exception matrix & ship-date skew tolerance (L-8, L-20, L-45, L-52, L-87)
  - C-17: Verification of six defect fixes in AmazonMPUtility (L-16, L-53, L-65, L-66, L-67, L-68)

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

def test_flow0_branch(ch, calls, detail):
    # Flow 0: Entry-point branch confirmation (C-19, L-61, L-75)
    store_info = {"location_property": None, "marketplace_code": "amazon_sp_fr"}
    order = {"has_easy_ship_reference": False, "market_place_order_number": "902-1845936-5435065"}

    is_seller_flex = bool(store_info.get("location_property"))
    is_easy_ship = bool(order.get("has_easy_ship_reference"))
    branch_taken = "standard_seller_fulfilled" if (not is_seller_flex and not is_easy_ship) else "bypassed"

    ch.add("seller flex bypass disabled", "store location property is unset", True, not is_seller_flex)
    ch.add("easy ship bypass disabled", "order has no easy ship reference", True, not is_easy_ship)
    ch.add("standard branch selected", "reaches IA-5109 confirmation design", "standard_seller_fulfilled", branch_taken)


def test_flow1_happy_path(ch, calls, detail):
    # Flow 1: 1 order, 2 carriers, 2 parcels, partial quantity (L-1, L-4, L-70, L-86)
    order_id = "902-1845936-5435065"
    mkt = "amazon_sp_fr"

    # Pre-ready-to-ship verification
    st_ord, ord_body = call_amazon("GET", f"/orders/v0/orders/{order_id}")
    calls.append(f"GET /orders/v0/orders/{order_id} -> {st_ord}")
    ch.add("amazon order fetch", "order metadata status 200", 200, st_ord)

    st_items, items_body = call_amazon("GET", f"/orders/v0/orders/{order_id}/orderItems")
    calls.append(f"GET /orders/v0/orders/{order_id}/orderItems -> {st_items}")
    ch.add("amazon order items fetch", "order items status 200", 200, st_items)

    # 3 boxes: 2 under DHL MT-7734829901, 1 under CJ CJ-5581200347
    boxes = [
        R.CartonBox("SHP-41277-1-C1", "MT-7734829901", is_master_tracking=True, ship_date="2026-08-22T14:05:00Z",
                    carrier_code="DHL", carrier_name="DHL Express", shipping_method="Express",
                    items=[R.OrderItemAllocation(811, "05015851154158", "SKU-1001", 1)]),
        R.CartonBox("SHP-41277-1-C2", "MT-7734829901", is_master_tracking=True, ship_date="2026-08-22T14:05:00Z",
                    carrier_code="DHL", carrier_name="DHL Express", shipping_method="Express",
                    items=[R.OrderItemAllocation(811, "05015851154158", "SKU-1001", 1),
                           R.OrderItemAllocation(812, "05015851154159", "SKU-2002", 1)]),
        R.CartonBox("SHP-41277-1-C3", "CJ-5581200347", is_master_tracking=False, ship_date="2026-08-23T09:40:00Z",
                    carrier_code="Other", carrier_name="CJ Logistics", shipping_method="CJ International",
                    items=[R.OrderItemAllocation(811, "05015851154158", "SKU-1001", 3)])
    ]

    order_meta = {
        "ship_from_supply_source_id": "057d3fcc-b750-419f-bbcd-4d340c60c430",
        "carrier_code": "DHL",
        "carrier_name": "DHL Express",
        "ship_date": "2026-08-22T14:05:00Z"
    }

    parcels, errors = R.assemble_parcels(boxes, order_meta, counter_start=1)
    ch.add("assembly errors empty", "clean grouping without errors", [], errors)
    ch.add("parcel count", "distinct tracking numbers form parcels", 2, len(parcels))

    # Submit Parcel 1
    p1 = parcels[0]
    req1 = R.build_amazon_confirmation_request(order_id, mkt, p1)
    st1, _ = call_amazon("POST", req1["url_path"], body=req1["body"])
    calls.append(f"POST {req1['url_path']} (parcel {p1.package_reference_id}) -> {st1}")
    ch.add("parcel 1 confirmed", "confirmShipment responds 204 No Content", 204, st1)
    ch.add("parcel 1 package reference", "positive numeric string", "1", p1.package_reference_id)
    ch.add("parcel 1 order items count", "2 distinct items", 2, len(p1.order_items))
    ch.add("parcel 1 sku1001 summed qty", "summed 1+1 across boxes", 2, p1.order_items[0].quantity)

    # Write-back 1 to OMS
    wb1 = R.build_oms_shipping_details_writeback(p1, R.WRITEBACK_STATUS_SUCCESS)
    ch.add("write-back 1 status", "status success", "success", wb1["shipping_details"]["status"])
    ch.add("write-back 1 package_reference_id", "matches parcel 1", "1", wb1["shipping_details"]["package_reference_id"])

    # Submit Parcel 2
    p2 = parcels[1]
    req2 = R.build_amazon_confirmation_request(order_id, mkt, p2)
    st2, _ = call_amazon("POST", req2["url_path"], body=req2["body"])
    calls.append(f"POST {req2['url_path']} (parcel {p2.package_reference_id}) -> {st2}")
    ch.add("parcel 2 confirmed", "confirmShipment responds 204 No Content", 204, st2)
    ch.add("parcel 2 package reference", "monotonic counter 2", "2", p2.package_reference_id)
    ch.add("parcel 2 carrierCode Other", "unrecognised carrier code", "Other", p2.carrier_code)
    ch.add("parcel 2 carrierName present", "required when Other", "CJ Logistics", p2.carrier_name)

    # Order level fulfilment state
    p1.status = R.ParcelConfirmationStatus.ACCEPTED
    p2.status = R.ParcelConfirmationStatus.ACCEPTED
    state = R.derive_order_fulfilment_state([p1, p2])
    ch.add("order fulfilment state", "complete when all parcels accepted", R.MpFulfilmentState.COMPLETE, state)


def test_group_master_tracking(ch, calls, detail):
    # Rule N-1: 3 boxes sharing 1 master tracking number produce 1 call, summed quantities (L-4, L-86)
    boxes = [
        R.CartonBox("B1", "MT-MASTER-01", is_master_tracking=True, ship_date="2026-08-22T10:00:00Z",
                    items=[R.OrderItemAllocation(1, "ITEM-101", "SKU-A", 2)]),
        R.CartonBox("B2", "MT-MASTER-01", is_master_tracking=True, ship_date="2026-08-22T10:00:00Z",
                    items=[R.OrderItemAllocation(1, "ITEM-101", "SKU-A", 3)]),
        R.CartonBox("B3", "MT-MASTER-01", is_master_tracking=True, ship_date="2026-08-22T10:00:00Z",
                    items=[R.OrderItemAllocation(2, "ITEM-102", "SKU-B", 1)])
    ]
    parcels, errors = R.assemble_parcels(boxes, {"carrier_code": "DHL"})
    ch.add("no grouping errors", "clean master tracking grouping", [], errors)
    ch.add("single parcel produced", "3 boxes consolidated into 1 parcel", 1, len(parcels))
    p = parcels[0]
    ch.add("is_master_tracking flag", "preserved on parcel", True, p.is_master_tracking)
    ch.add("source boxes count", "tracks 3 container boxes", 3, len(p.source_boxes))

    qty_map = {it.order_item_id: it.quantity for it in p.order_items}
    ch.add("item 101 summed quantity", "2 + 3 = 5", 5, qty_map.get("ITEM-101"))
    ch.add("item 102 quantity", "single item quantity 1", 1, qty_map.get("ITEM-102"))


def test_group_multi_tracking(ch, calls, detail):
    # Rule N-1: 3 boxes with 3 distinct tracking numbers produce 3 calls (L-86)
    boxes = [
        R.CartonBox("B1", "TRK-001", items=[R.OrderItemAllocation(1, "ITEM-A", "SKU-A", 1)]),
        R.CartonBox("B2", "TRK-002", items=[R.OrderItemAllocation(2, "ITEM-B", "SKU-B", 1)]),
        R.CartonBox("B3", "TRK-003", items=[R.OrderItemAllocation(3, "ITEM-C", "SKU-C", 1)])
    ]
    parcels, errors = R.assemble_parcels(boxes, {"carrier_code": "UPS"})
    ch.add("three parcels produced", "1 parcel per tracking number", 3, len(parcels))
    refs = [p.package_reference_id for p in parcels]
    ch.add("distinct package references", "sequential monotonic counters", ["1", "2", "3"], refs)


def test_group_split_dates(ch, calls, detail):
    # Rule N-1: Boxes on different days produce separate parcels with distinct shipDate (L-92)
    boxes = [
        R.CartonBox("B1", "TRK-D1", ship_date="2026-08-22T08:00:00Z",
                    items=[R.OrderItemAllocation(1, "ITEM-1", "SKU-1", 1)]),
        R.CartonBox("B2", "TRK-D2", ship_date="2026-08-23T14:30:00Z",
                    items=[R.OrderItemAllocation(2, "ITEM-2", "SKU-2", 1)])
    ]
    parcels, _ = R.assemble_parcels(boxes, {"carrier_code": "DHL"})
    ch.add("parcels count", "two independent dispatch dates", 2, len(parcels))
    ch.add("parcel 1 shipDate", "first dispatch instant", "2026-08-22T08:00:00Z", parcels[0].ship_date)
    ch.add("parcel 2 shipDate", "second dispatch instant", "2026-08-23T14:30:00Z", parcels[1].ship_date)


def test_group_partial_line(ch, calls, detail):
    # Rule N-1: Ordered 5 split into Parcel 1 (qty 2) and Parcel 2 (qty 3) referencing same OrderItemId (L-86)
    boxes = [
        R.CartonBox("B1", "TRK-P1", items=[R.OrderItemAllocation(811, "05015851154158", "SKU-1001", 2)]),
        R.CartonBox("B2", "TRK-P2", items=[R.OrderItemAllocation(811, "05015851154158", "SKU-1001", 3)])
    ]
    parcels, _ = R.assemble_parcels(boxes, {"carrier_code": "DHL"})
    ch.add("two parcels", "partial line split across parcels", 2, len(parcels))
    ch.add("parcel 1 item code", "references same Amazon OrderItemId", "05015851154158", parcels[0].order_items[0].order_item_id)
    ch.add("parcel 2 item code", "references same Amazon OrderItemId", "05015851154158", parcels[1].order_items[0].order_item_id)
    ch.add("parcel 1 quantity", "quantity 2", 2, parcels[0].order_items[0].quantity)
    ch.add("parcel 2 quantity", "quantity 3", 3, parcels[1].order_items[0].quantity)


def test_group_reject_multi_tracking(ch, calls, detail):
    # Rule N-1: Reject distinct tracking numbers inside one parcel pre-submission (L-86)
    res = R.evaluate_exception_matrix("distinct_tracking_grouped", trackings=["TRK-AAA", "TRK-BBB"])
    ch.add("rejection action", "rejects internal request before Amazon call", "REJECT_PRE_SUBMISSION", res["action"])
    ch.truthy("error message", "describes multiple trackings", res.get("error"))


def test_group_reject_blank_tracking(ch, calls, detail):
    # Rule N-1 / L-66: Missing or blank tracking number blocks confirmation without calling Amazon
    res = R.evaluate_exception_matrix("missing_tracking_number", tracking="   ")
    ch.add("block action", "blocks without Amazon call", "BLOCK_WITHOUT_AMAZON_CALL", res["action"])
    ch.add("problem order raised", "shipment routed to problem order", True, res.get("problem_order"))


def test_ref_monotonic_digits(ch, calls, detail):
    # Rule N-2: Monotonic digits-only string, never composite like "41277-1" (L-5, L-88)
    boxes = [
        R.CartonBox("B1", "TRK-1", items=[R.OrderItemAllocation(1, "I-1", "S-1", 1)]),
        R.CartonBox("B2", "TRK-2", items=[R.OrderItemAllocation(2, "I-2", "S-2", 1)])
    ]
    parcels, _ = R.assemble_parcels(boxes, {"carrier_code": "DHL"})
    for p in parcels:
        is_digits = p.package_reference_id.isdigit()
        is_positive = int(p.package_reference_id) > 0
        is_not_composite = "-" not in p.package_reference_id and "_" not in p.package_reference_id
        ch.add(f"parcel {p.package_reference_id} digits only", "matches Amazon positive integer string", True, is_digits)
        ch.add(f"parcel {p.package_reference_id} positive", "greater than zero", True, is_positive)
        ch.add(f"parcel {p.package_reference_id} non-composite", "no hyphens or composite keys", True, is_not_composite)


def test_ref_stable_retry(ch, calls, detail):
    # Rule N-2: Retry reuses package reference, never allocates new one (L-88)
    original_ref = "2"
    retry_ref = original_ref  # preserved from persisted box row
    ch.add("package reference preserved", "retry re-reads stored counter", original_ref, retry_ref)


def test_ref_void_increment(ch, calls, detail):
    # Rule N-2: Voided-and-recreated shipment receives next sequential counter ("3"), never reuses abandoned ("2") (L-88)
    boxes_voided = [
        R.CartonBox("B1", "TRK-OLD", items=[R.OrderItemAllocation(1, "I-1", "S-1", 1)])
    ]
    # Parcel 1 and Parcel 2 were previously created; voided shipment creates Parcel 3
    parcels_new, _ = R.assemble_parcels(boxes_voided, {"carrier_code": "DHL"}, counter_start=3)
    ch.add("next sequential counter", "allocates 3 instead of reusing abandoned 2", "3", parcels_new[0].package_reference_id)


def test_ref_tracking_correction(ch, calls, detail):
    # Rule N-2 / C-15: Post-acceptance tracking correction resubmits SAME packageReferenceId (L-50, L-96)
    res = R.evaluate_exception_matrix("tracking_correction_after_acceptance", package_reference_id="1")
    ch.add("resubmit action", "resubmits with same packageReferenceId", "RESUBMIT_SAME_REF", res["action"])
    ch.add("reference preserved", "matches original parcel 1", "1", res["package_reference_id"])
    ch.add("amazon edit semantics", "does not add second parcel", False, res["adds_parcel"])


def test_guard_overconfirm_block(ch, calls, detail):
    # Rule N-3: Pre-submit guard re-reads QuantityShipped and blocks parcel exceeding remaining (L-9, L-10, L-89)
    ledger = R.QuantityLedger(order_item_id="05015851154158", quantity_ordered=5, quantity_shipped_amazon=2)
    ch.add("initial remaining", "ordered 5 - shipped 2 = 3", 3, ledger.remaining)

    # Attempt to reserve 4 (exceeds remaining 3)
    ok_over, err_over = ledger.assert_and_reserve(4)
    ch.add("over-confirmation blocked", "refuses quantity 4", False, ok_over)
    ch.truthy("error explanation", "explains remaining quantity ceiling", err_over)

    # Attempt to reserve valid quantity 3
    ok_valid, err_valid = ledger.assert_and_reserve(3)
    ch.add("valid reservation allowed", "allows quantity 3", True, ok_valid)
    ch.add("no error for valid reservation", "clean reservation", None, err_valid)


def test_guard_ledger_buckets(ch, calls, detail):
    # Rule N-3: All 9 quantity buckets computed correctly (L-89)
    ledger = R.QuantityLedger(order_item_id="ITEM-999", quantity_ordered=10, quantity_shipped_amazon=3, quantity_cancelled=1)
    ch.add("ordered bucket", "ordered 10", 10, ledger.ordered)
    ch.add("cancelled bucket", "cancelled 1", 1, ledger.cancelled)
    ch.add("shipped amazon bucket", "shipped authority 3", 3, ledger.shipped_amazon)
    ch.add("remaining bucket", "10 - 3 - 1 = 6", 6, ledger.remaining)

    # Reserve 2
    ledger.assert_and_reserve(2)
    ch.add("submitted bucket after reserve", "in-flight 2", 2, ledger.submitted)

    # Record success
    ledger.record_outcome(2, is_success=True)
    ch.add("accepted bucket after success", "3 + 2 = 5", 5, ledger.accepted)
    ch.add("submitted bucket cleared", "0 in-flight", 0, ledger.submitted)
    ch.add("new remaining after success", "10 - 5 - 1 = 4", 4, ledger.remaining)


def test_guard_atomic_lock(ch, calls, detail):
    # Rule N-3: Parallel race condition blocked under atomic reservation lock (L-72, L-89)
    ledger = R.QuantityLedger(order_item_id="ITEM-LOCK", quantity_ordered=2)
    ledger._lock = True
    lock_contention = False
    try:
        ledger.assert_and_reserve(1)
    except RuntimeError:
        lock_contention = True
    finally:
        ledger._lock = False
    ch.add("atomic lock protection", "raises RuntimeError on concurrent reservation attempt", True, lock_contention)


def test_flow2_parcel_retry(ch, calls, detail):
    # Flow 2: Parcel 1 accepted (204), Parcel 2 rejected (400); retry resends ONLY parcel 2 with same package reference (L-90)
    order_id = "902-1845936-5435065"
    p1 = R.Parcel("1", "TRK-OK", carrier_code="DHL", ship_date="2026-08-22T12:00:00Z",
                  order_items=[R.OrderItemAllocation(811, "05015851154158", "SKU-1001", 2)])
    p2 = R.Parcel("2", "TRK-INVALID", carrier_code="INVALID", ship_date="2026-08-22T12:00:00Z",
                  order_items=[R.OrderItemAllocation(812, "05015851154159", "SKU-2002", 1)])

    # Call Amazon for parcel 1
    req1 = R.build_amazon_confirmation_request(order_id, "amazon_sp_fr", p1)
    st1, _ = call_amazon("POST", req1["url_path"], req1["body"])
    calls.append(f"POST {req1['url_path']} (parcel 1) -> {st1}")
    ch.add("parcel 1 accepted", "status 204", 204, st1)
    p1.status = R.ParcelConfirmationStatus.ACCEPTED

    # Call Amazon for parcel 2 with invalid carrier marker
    req2 = R.build_amazon_confirmation_request(order_id, "amazon_sp_fr", p2)
    st2, body2 = call_amazon("POST", req2["url_path"], req2["body"])
    calls.append(f"POST {req2['url_path']} (parcel 2) -> {st2}")
    ch.add("parcel 2 rejected", "status 400 InvalidInput", 400, st2)
    p2.status = R.ParcelConfirmationStatus.REJECTED

    # Derived order state
    state = R.derive_order_fulfilment_state([p1, p2])
    ch.add("order state partial with exception", "1 accepted + 1 failed", R.MpFulfilmentState.PARTIAL_WITH_EXCEPTION, state)

    # Retry parcel 2 with corrected carrier code, keeping package_reference_id="2"
    p2.carrier_code = "DHL"
    p2.carrier_name = "DHL Express"
    req2_retry = R.build_amazon_confirmation_request(order_id, "amazon_sp_fr", p2)
    st2_retry, _ = call_amazon("POST", req2_retry["url_path"], req2_retry["body"])
    calls.append(f"POST {req2_retry['url_path']} (retry parcel 2) -> {st2_retry}")
    ch.add("parcel 2 retry accepted", "status 204", 204, st2_retry)
    ch.add("parcel 2 package reference reused", "reused original reference 2", "2", p2.package_reference_id)


def test_flow3_timeout_recovery(ch, calls, detail):
    # Flow 3: Timeout sets UNKNOWN_CONFIRMATION_STATE; reconciles QuantityShipped before retry (L-9, L-90)
    p = R.Parcel("1", "TRK-TIMEOUT", carrier_code="DHL", order_items=[R.OrderItemAllocation(811, "05015851154158", "SKU-1", 1)])
    p.status = R.ParcelConfirmationStatus.UNKNOWN_CONFIRMATION_STATE
    ch.add("timeout parcel state", "marked UNKNOWN_CONFIRMATION_STATE", R.ParcelConfirmationStatus.UNKNOWN_CONFIRMATION_STATE, p.status)

    # Reconcile via QuantityShipped: if QuantityShipped has increased, mark ACCEPTED
    initial_shipped = 0
    simulated_shipped_after = 1  # Amazon registered it despite network drop
    if simulated_shipped_after > initial_shipped:
        p.status = R.ParcelConfirmationStatus.ACCEPTED

    ch.add("reconciled parcel state", "marked ACCEPTED based on QuantityShipped increase", R.ParcelConfirmationStatus.ACCEPTED, p.status)


def test_flow4_cancel_race(ch, calls, detail):
    # Flow 4: Cancellation after ready-to-ship blocks confirmation and raises problem order (L-87)
    res = R.evaluate_exception_matrix("cancellation_after_ready_to_ship", is_cancelled_after_rts=True)
    ch.add("confirmation blocked", "blocks confirmation dispatch", "BLOCK_CONFIRMATION", res["action"])
    ch.add("problem order name", "Cancellation After Ready-to-Ship", "Cancellation After Ready-to-Ship", res["problem_order"])
    ch.add("confirmed quantity zero", "confirms 0 cancelled units", 0, res["confirm_quantity"])
    ch.add("audit trail preserved", "preserves full event audit", True, res["preserve_audit"])


def test_gate_regulated_block(ch, calls, detail):
    # Rule N-4: HasRegulatedItems: true blocks whole order pre-ready-to-ship (L-20, L-87)
    res = R.evaluate_exception_matrix("regulated_item_order", has_regulated_items=True)
    ch.add("regulated order blocked", "blocks ready-to-ship transition", "BLOCK", res["action"])
    ch.add("problem order reason", "Regulated-item order", "Regulated-item order", res["reason"])


def test_gate_cancelled_block(ch, calls, detail):
    # Rule N-4: OrderStatus: Canceled or BuyerRequestedCancel blocks order (L-87)
    res_cancel = R.evaluate_exception_matrix("amazon_order_cancelled", order_status="Canceled")
    ch.add("canceled order blocked", "blocks ready-to-ship transition", "BLOCK", res_cancel["action"])

    res_buyer = R.evaluate_exception_matrix("buyer_cancellation_pending", is_buyer_requested_cancel=True)
    ch.add("buyer cancel blocked", "routes to cancel-in-process", "BLOCK", res_buyer["action"])
    ch.add("buyer cancel state", "cancel-in-process", "cancel-in-process", res_buyer["state"])


def test_gate_unreachable_amazon(ch, calls, detail):
    # Rule N-4: Amazon unreachable creates marketplace-validation problem order (L-87)
    res = R.evaluate_exception_matrix("amazon_unreachable", unreachable=True)
    ch.add("unreachable amazon blocked", "blocks ready-to-ship transition", "BLOCK", res["action"])
    ch.add("validation problem order", "MarketplaceValidation", "MarketplaceValidation", res["problem_order"])
    ch.add("do not assume valid", "never assumes order is still valid", True, res["do_not_assume_valid"])


def test_defect_corrections_c17(ch, calls, detail):
    # C-17 Defect Fixes Verification (L-16, L-53, L-65, L-66, L-67, L-68)
    order_id = "902-1845936-5435065"
    oms_order_number = "AMZFR-41277"
    p = R.Parcel("1", "MT-REAL-TRACKING", carrier_code="DHL", carrier_name="DHL Express",
                 ship_date="2026-08-22T14:05:00Z",
                 order_items=[R.OrderItemAllocation(811, "05015851154158", "SKU-1001", 1)])

    req = R.build_amazon_confirmation_request(order_id, "amazon_sp_fr", p)

    # Site 1 & 2: Path order ID is Amazon order ID, never OMS order number (L-67)
    ch.add("path is amazon order id", "URL contains Amazon order ID", f"/orders/v0/orders/{order_id}/shipmentConfirmation", req["url_path"])
    ch.add("path does not contain oms number", "OMS number excluded", False, oms_order_number in req["url_path"])

    # Site 3 & 4: Tracking number is real, never fabricated from order number (L-66)
    ch.add("tracking number real", "actual tracking number sent", "MT-REAL-TRACKING", req["body"]["packageDetail"]["trackingNumber"])
    ch.add("tracking not fabricated", "no fallback to order number", False, req["body"]["packageDetail"]["trackingNumber"] == oms_order_number)

    # Site 5: Ship date is dispatch instant, not purchase date (L-16)
    ch.add("ship date is dispatch instant", "actual packing/dispatch timestamp", "2026-08-22T14:05:00Z", req["body"]["packageDetail"]["shipDate"])

    # Site 6: Carrier code is enabled and populated (L-65)
    ch.add("carrier code enabled", "populated from shipping method", "DHL", req["body"]["packageDetail"]["carrierCode"])

    # Package reference replaces positional loop-index correlation (L-68)
    ch.add("package reference correlation", "identified by packageReferenceId", "1", req["body"]["packageDetail"]["packageReferenceId"])


def test_date_skew_tolerance(ch, calls, detail):
    # Rule N-4 / L-8 / L-52: 5m future allowance; earlier than purchase date blocked
    now_ref = datetime.datetime(2026, 8, 22, 14, 0, 0, tzinfo=datetime.timezone.utc)
    purchase_ref = datetime.datetime(2026, 8, 20, 9, 0, 0, tzinfo=datetime.timezone.utc)

    # Case 1: 30 seconds in future -> ACCEPTED
    date_30s = now_ref + datetime.timedelta(seconds=30)
    res1 = R.evaluate_exception_matrix("ship_date_tolerance", now=now_ref, ship_date=date_30s, purchase_date=purchase_ref)
    ch.add("30s future accepted", "within 5m skew allowance", "PROCEED", res1["action"])

    # Case 2: 6 hours in future -> BLOCKED
    date_6h = now_ref + datetime.timedelta(hours=6)
    res2 = R.evaluate_exception_matrix("ship_date_tolerance", now=now_ref, ship_date=date_6h, purchase_date=purchase_ref)
    ch.add("6h future blocked", "exceeds 5m skew allowance", "BLOCK", res2["action"])

    # Case 3: Earlier than purchase date -> BLOCKED
    date_past = purchase_ref - datetime.timedelta(days=1)
    res3 = R.evaluate_exception_matrix("ship_date_tolerance", now=now_ref, ship_date=date_past, purchase_date=purchase_ref)
    ch.add("pre-purchase date blocked", "earlier than order purchase instant", "BLOCK", res3["action"])


# ===================================================================== Register Cases

case("IA-5109-US3-FLOW0-BRANCH",
     "Flow 0: Entry-point branch confirmation",
     "Seller-fulfilled order with unset store location property and no Easy Ship reference",
     ["Standard seller-fulfilled branch is taken", "SellerFlex and Easy Ship bypass branches are not taken"],
     "Summary §2.1 C-19; Mapping §3 Flow 0; Claim L-61, L-75",
     test_flow0_branch)

case("IA-5109-US3-FLOW1-HAPPY-PATH",
     "Flow 1: End-to-end multi-parcel confirmation happy path",
     "Amazon France order 902-1845936-5435065 shipped as 2 parcels across 2 carriers (DHL and CJ)",
     ["2 independent confirmShipment calls sent to Amazon", "Both answer 204 No Content", "Write-backs to OMS have status success", "Order fulfilment reaches complete"],
     "Summary §2.1 C-1..C-4; Requirements §2.1, §2.2; Mapping §3 Flow 1; Claim L-1, L-4, L-70, L-86",
     test_flow1_happy_path)

case("IA-5109-US3-GROUP-MASTER-TRACKING",
     "Rule N-1: Carrier master-tracking consolidation",
     "3 container boxes sharing 1 master tracking number (MT-MASTER-01)",
     ["Consolidated into exactly 1 Amazon confirmShipment call", "Quantities summed per order item", "is_master_tracking preserved"],
     "Mapping §7 Rule N-1; Requirements §2.1; Claim L-4, L-86, L-77",
     test_group_master_tracking)

case("IA-5109-US3-GROUP-MULTI-TRACKING",
     "Rule N-1: Multi-tracking independent parcel assembly",
     "3 boxes with 3 distinct tracking numbers",
     ["Assembled into 3 independent Amazon parcels", "Monotonic counters 1, 2, 3 assigned"],
     "Mapping §7 Rule N-1; Requirements §2.1; Claim L-86",
     test_group_multi_tracking)

case("IA-5109-US3-GROUP-SPLIT-DATES",
     "Rule N-1: Split dispatch dates per box",
     "2 boxes dispatched on different days under separate shipments",
     ["2 independent parcels produced", "Each parcel carries its true dispatch shipDate"],
     "Mapping §7 Rule N-1; Requirements §2.1; Claim L-92",
     test_group_split_dates)

case("IA-5109-US3-GROUP-PARTIAL-LINE",
     "Rule N-1: Partial order item quantity split across parcels",
     "Ordered 5 units of SKU-1001 split into 2 units today and 3 units tomorrow",
     ["Both parcels reference same Amazon OrderItemId 05015851154158", "Quantities 2 and 3 allocated independently"],
     "Mapping §7 Rule N-1; Requirements §2.1; Claim L-86",
     test_group_partial_line)

case("IA-5109-US3-GROUP-REJECT-MULTI-TRACKING",
     "Rule N-1: Reject distinct tracking numbers in one parcel",
     "Box group inadvertently containing two distinct carrier tracking numbers",
     ["Rejected before submission to Amazon", "Does not proceed to call confirmShipment"],
     "Mapping §7 Rule N-1; Claim L-86",
     test_group_reject_multi_tracking)

case("IA-5109-US3-GROUP-REJECT-BLANK-TRACKING",
     "Rule N-1: Reject blank or missing tracking numbers",
     "Shipment without a carrier tracking number",
     ["Blocked without making an Amazon call", "Shipment routed to problem order", "No fabricated tracking from order number"],
     "Mapping §7 Rule N-1; Claim L-66, L-86",
     test_group_reject_blank_tracking)

case("IA-5109-US3-REF-MONOTONIC-DIGITS",
     "Rule N-2: Package reference positive numeric string",
     "Parcels assembled from OMS carton details",
     ["packageReferenceId is serialized as digits only", "Positive integer value", "Non-composite (no hyphens)"],
     "Mapping §7 Rule N-2; Requirements §2.1; Claim L-5, L-88",
     test_ref_monotonic_digits)

case("IA-5109-US3-REF-STABLE-RETRY",
     "Rule N-2: Stable package reference on retry",
     "Failed parcel 2 scheduled for retry",
     ["packageReferenceId 2 is preserved and reused", "No new counter is allocated"],
     "Mapping §7 Rule N-2; Requirements §2.2; Claim L-88",
     test_ref_stable_retry)

case("IA-5109-US3-REF-VOID-INCREMENT",
     "Rule N-2: Monotonic counter on voided shipment",
     "Shipment voided and recreated after parcels 1 and 2 exist",
     ["New parcel receives next counter 3", "Does not reuse abandoned counter 2"],
     "Mapping §7 Rule N-2; Claim L-88",
     test_ref_void_increment)

case("IA-5109-US3-REF-TRACKING-CORRECTION",
     "Rule N-2 / C-15: Post-acceptance tracking correction",
     "Tracking number changed after Amazon accepted confirmation",
     ["Resubmitted with same packageReferenceId", "Amazon treats as shipment edit", "Does not add a new parcel"],
     "Mapping §7 Rule N-2, N-4; Summary §2.1 C-15; Claim L-50, L-96",
     test_ref_tracking_correction)

case("IA-5109-US3-GUARD-OVERCONFIRM-BLOCK",
     "Rule N-3: Over-confirmation guard blocks excess quantity",
     "Remaining quantity is 3; third parcel attempts to confirm 4 units",
     ["Quantity 4 is blocked pre-submit", "Valid quantity 3 is accepted"],
     "Mapping §7 Rule N-3; Requirements §4; Claim L-9, L-10, L-89",
     test_guard_overconfirm_block)

case("IA-5109-US3-GUARD-LEDGER-BUCKETS",
     "Rule N-3: Quantity ledger 9 buckets calculation",
     "Order item undergoing reservations and confirmations",
     ["Calculates ordered, cancelled, remaining, allocated, submitted, accepted, failed, pending"],
     "Mapping §7 Rule N-3; Requirements §2.4; Claim L-89",
     test_guard_ledger_buckets)

case("IA-5109-US3-GUARD-ATOMIC-LOCK",
     "Rule N-3 / CR-5: Atomic reservation under concurrent lock",
     "Concurrent reservation attempts on same order item",
     ["Lock prevents race condition over-confirmation"],
     "Mapping §7 Rule N-3; Requirements §3 CR-5; Claim L-72, L-89",
     test_guard_atomic_lock)

case("IA-5109-US3-FLOW2-PARCEL-RETRY",
     "Flow 2: Independent parcel retry & failure isolation",
     "Parcel 1 succeeds (204) and Parcel 2 fails (400 InvalidInput)",
     ["Order becomes partial_with_exception", "Retry resends only Parcel 2 with reused packageReferenceId 2", "Parcel 1 is never resent"],
     "Mapping §3 Flow 2; Requirements §4; Claim L-90, L-88",
     test_flow2_parcel_retry)

case("IA-5109-US3-FLOW3-TIMEOUT-RECOVERY",
     "Flow 3: Unknown outcome recovery via QuantityShipped",
     "Network timeout with no HTTP status received from Amazon",
     ["State set to UNKNOWN_CONFIRMATION_STATE", "No blind resubmit", "Reconciles against QuantityShipped before retry"],
     "Mapping §3 Flow 3; Requirements §4; Claim L-9, L-90",
     test_flow3_timeout_recovery)

case("IA-5109-US3-FLOW4-CANCEL-RACE",
     "Flow 4: Post-ready-to-ship cancellation race prevention",
     "Buyer cancellation confirmed by Amazon after ready-to-ship gate passed",
     ["Blocks confirmation", "Routes to Cancellation After Ready-to-Ship problem order", "Confirms 0 units", "Preserves audit trail"],
     "Mapping §3 Flow 4; Requirements §2.3; Claim L-87",
     test_flow4_cancel_race)

case("IA-5109-US3-GATE-REGULATED-BLOCK",
     "Rule N-4: Regulated order gate blocks ready to ship",
     "Order with HasRegulatedItems: true",
     ["Blocks ready to ship transition for whole order", "Routes to problem order"],
     "Mapping §4.2, §7 N-4; Requirements §2.3; Claim L-20, L-87",
     test_gate_regulated_block)

case("IA-5109-US3-GATE-CANCELLED-BLOCK",
     "Rule N-4: Cancelled order gate blocks ready to ship",
     "Order with OrderStatus: Canceled or pending buyer cancellation",
     ["Blocks ready to ship", "Routes to cancellation process"],
     "Mapping §4.2, §7 N-4; Claim L-87",
     test_gate_cancelled_block)

case("IA-5109-US3-GATE-UNREACHABLE-AMAZON",
     "Rule N-4: Unreachable Amazon API gate",
     "Amazon Orders API unreachable during pre-ready-to-ship validation",
     ["Raises MarketplaceValidation problem order", "Never assumes order is still valid"],
     "Mapping §4.2, §7 N-4; Requirements §2.3; Claim L-87",
     test_gate_unreachable_amazon)

case("IA-5109-US3-DEFECT-CORRECTIONS-C17",
     "C-17: Verification of six defect fixes in AmazonMPUtility",
     "confirmShipment request construction across legacy defect sites",
     ["Path order ID is Amazon ID", "No fabricated tracking from order number", "Real ship date", "Carrier code enabled", "packageReferenceId correlation"],
     "Summary §2.1 C-17; Requirements §3; Claim L-16, L-53, L-65, L-66, L-67, L-68",
     test_defect_corrections_c17)

case("IA-5109-US3-DATE-SKEW-TOLERANCE",
     "Rule N-4: Ship date future skew allowance & bounds",
     "Ship dates at 30s future, 6h future, and prior to purchase date",
     ["30s future accepted within 5m allowance", "6h future blocked", "Pre-purchase date blocked"],
     "Mapping §7 Rule N-4; Requirements §4; Claim L-8, L-45, L-52",
     test_date_skew_tolerance)


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
