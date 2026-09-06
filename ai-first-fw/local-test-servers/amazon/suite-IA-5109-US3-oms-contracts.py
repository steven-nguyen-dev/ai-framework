#!/usr/bin/env python3
"""IA-5109-US3: OMS Schemas, DTOs & Contracts Test Suite.

Judges the Anchanto OMS contract modifications, webhook payloads, write-backs,
and internal storage models for User Story 3: Support Partial and Multi-Parcel
Amazon Seller-Fulfilled Shipments (IA-5109).

Every case crosses the HTTP boundary against the local Anchanto OMS mock, which the suite starts
itself when nothing is already listening. What OMS recorded is the observable.

Covers:
  - CR-0: the IA-5111 import fields on order create (L-20, L-134)
  - Mapping 4.5: the per-parcel write-back, row for row -- package_id, tracking_number, status,
    failure_reason, and the per-line id, quantity and item_codes[] (L-23, L-89, L-113, L-119)
  - Mapping 5.4 and 6: one message per parcel, and a rejection never reversing an acceptance (L-90)
  - C-17's second site: the order number never written back as a tracking number (L-66)
  - C-13: the SHIPPED item subset, which is how OMS reaches Partial (L-47, L-114, L-46)
  - Mapping 4.3: the OMS line read the quantity ledger is built from, and what happens when it fails

Not here, and why. The ready-to-ship event is a message we consume rather than an endpoint we call,
so C-8's quantity alias and CR-1's webhook diff have no HTTP surface in this harness; the alias is
pinned by RTSLineItemQuantityAliasTest and the box list by CartonDetailsWireShapeTest. awb_details is
not a configured route on the OMS mock. The order-level mp_fulfilment_state the prior revision
asserted is withdrawn by mapping 5.2 (L-138), and the database durability and unique-constraint cases
asserted Python literals against themselves; the behaviour they gestured at -- the same package
reference being an edit -- is now REF-TRACKING-CORRECTION against the Amazon mock.

Three of mapping 4.5's rows are absent from the OMS contract today (L-23). Under the working
principle they are a change to request and not a blocker: we agree the shape, build against it and
test against this mock, while the ask travels in parallel as CR-2 (L-39).

Runner contract: TESTING.md.
Publishes live status to amazon/test-results/IA-5109-US3-oms-contracts/run-<stamp>/results.json.

The suite starts its own Anchanto OMS mock on an OS-assigned port, against a run-scoped state
directory under the run folder. It never attaches to a server already holding the OMS port: that
server loaded its config at its own start, so a stale route would answer and the suite would report
on a contract that is not the one on disk.

Usage:
  python3 amazon/suite-IA-5109-US3-oms-contracts.py
  python3 amazon/suite-IA-5109-US3-oms-contracts.py --list
  python3 amazon/suite-IA-5109-US3-oms-contracts.py IA-5109-US3-CR2-WRITEBACK-ACCEPTED
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

# The suite always runs its own OMS mock, on an OS-assigned port and against a run-scoped state
# directory. Attaching to whatever already holds the OMS port would read a config that server loaded
# at its own start -- a stale route answers the call and the suite reports on the wrong contract --
# and would write into the state the portal's own server is keeping.
BASE_OMS = ""
SUITE_ID = "IA-5109-US3-oms-contracts"
SUITE_NAME = "IA-5109-US3: OMS Schemas, DTOs & Contracts Suite"
KEEP = "--keep-state" in sys.argv
LIST_ONLY = "--list" in sys.argv
WANTED_CASES = set(a for a in sys.argv[1:] if not a.startswith("-"))

MOCK_DIR = HERE
STAMP = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
RUN_DIR = os.path.join(MOCK_DIR, "test-results", SUITE_ID, "run-" + STAMP)

SERVERS_DIR = os.path.dirname(MOCK_DIR)
OMS_DIR = os.path.join(SERVERS_DIR, "anchanto-oms")
OMS_DATA_DIR = os.path.join(RUN_DIR, "oms-state")
OMS_LOG_FILE = "api-calls.har.json"

# The stores the write-back and the status update land in. Emptied per run so a case can assert on
# what this run recorded rather than on what some earlier run left behind.
OMS_STORES = ["created_orders", "order_pushes", "shipping_pushes"]

_EPHEMERAL_SERVER = None
_EPHEMERAL_THREAD = None


def _start_ephemeral_oms():
    """Starts the Anchanto OMS mock in-process on a free port, and returns its base URL."""
    global _EPHEMERAL_SERVER, _EPHEMERAL_THREAD
    if SERVERS_DIR not in sys.path:
        sys.path.insert(0, SERVERS_DIR)
    import mock

    with open(os.path.join(OMS_DIR, "anchanto-oms.mock.json"), "r", encoding="utf-8") as f:
        config = json.load(f)

    os.makedirs(OMS_DATA_DIR, exist_ok=True)
    routes, spec = mock.build_routes(config, OMS_DIR)
    state = mock.State(config.get("stores"), OMS_DATA_DIR)
    api_log = mock.ApiLog(os.path.join(OMS_DATA_DIR, OMS_LOG_FILE), "har",
                          config.get("log_redact_headers"), "Anchanto OMS")
    handler_cls = mock.make_handler(
        config, routes, state, api_log, os.path.join(OMS_DIR, "test-results"),
        [], mock.SuiteRunner(), OMS_DIR)

    host = config.get("host") or "127.0.0.1"
    _EPHEMERAL_SERVER = ThreadingHTTPServer((host, 0), handler_cls)
    _EPHEMERAL_THREAD = threading.Thread(target=_EPHEMERAL_SERVER.serve_forever, daemon=True)
    _EPHEMERAL_THREAD.start()
    time.sleep(0.3)
    return "http://%s:%d" % (host, _EPHEMERAL_SERVER.server_address[1])


def _stop_ephemeral_oms():
    global _EPHEMERAL_SERVER
    if _EPHEMERAL_SERVER:
        try:
            _EPHEMERAL_SERVER.shutdown()
            _EPHEMERAL_SERVER.server_close()
        except Exception:
            pass
        _EPHEMERAL_SERVER = None


atexit.register(_stop_ephemeral_oms)


def call_oms(method, path, body=None, token="mock_oms_access_token"):
    return R.http_json(method, BASE_OMS + path, body=body, token=token)


def store(name):
    """Reads one of the OMS mock's stores back, which is where the OMS-side observable lives."""
    path = os.path.join(OMS_DATA_DIR, name + ".json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

CASES, RESULTS = [], {}
EVIDENCE = {
    "status": "running",
    "oms mock": f"Anchanto OMS mock at {BASE_OMS}",
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
        "base_url": BASE_OMS,
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
# Every case crosses the HTTP boundary against the local Anchanto OMS mock. What OMS recorded is the
# observable; a case that asserted a literal dictionary against itself would pass whatever OMS did.
#
# Three of mapping 4.5's rows -- package_id, order_items[].quantity and order_items[].item_codes[] --
# are absent from the OMS contract today (L-23). Under the working principle that is a change to
# request and not a blocker: we agree the shape, build against it, and test against this mock, while
# the ask travels in parallel as CR-2 (L-39). The mock records them because we asked it to; that is
# the agreed shape under test, not evidence that OMS ships it.

OMS_ORDER_ID = 41277
OMS_ORDER_NUMBER = "AMZFR-902-1845936-5435065"
ITEM_1001 = "05015851154158"
ITEM_2002 = "05015851154159"
SECOND_TRACKING = "CJ-5581200347"
MASTER_TRACKING = "MT-7734829901"
READY_TO_SHIP_AT = "2026-08-22T14:05:00Z"


def shipping_pushes_for(tracking_number):
    return [p for p in store("shipping_pushes") if p.get("tracking_number") == tracking_number]


def order_pushes_of(kind, order_id):
    return [p for p in store("order_pushes")
            if p.get("kind") == kind and str(p.get("order_id")) == str(order_id)]


def parcel(reference, tracking, items):
    return R.Parcel(reference, tracking, carrier_code="DHL", carrier_name="DHL Express",
                    ship_date=READY_TO_SHIP_AT, order_items=items)


def post_writeback(ch, calls, payload, label, expect=200):
    status, body = call_oms("POST", "/rest/v1/orders/shipping_details", payload)
    calls.append("POST /rest/v1/orders/shipping_details (%s) -> %s" % (label, status))
    ch.add("OMS accepted the %s write-back" % label, "the connector posts it; we never call OMS directly (L-120)",
           expect, status)
    return body


# --------------------------------------------------------------------- CR-0, the import fields

def test_cr0_import_fields(ch, calls, detail):
    # CR-0: has_regulated_items and fulfillment_supply_source_id carried through from IA-5111 (L-20, L-134)
    order_number = "AMZFR-902-CR0-000001"
    payload = {"order": {
        "order_number": order_number,
        "store_code": "SS0000051211",
        "marketplace_code": "amazon_sp_fr",
        "order_total": "142.50",
        "has_regulated_items": False,
        "fulfillment_supply_source_id": "057d3fcc-b750-419f-bbcd-4d340c60c430",
        "order_items": [{"line_item_id": "0", "item_codes": [ITEM_1001], "sku": "SKU-1001", "quantity": 5}],
    }}
    status, _ = call_oms("POST", "/rest/v1/orders", payload)
    calls.append("POST /rest/v1/orders (%s) -> %s" % (order_number, status))
    ch.add("OMS accepted the order", "the import path OMS already serves", 200, status)

    rows = [p for p in store("order_pushes")
            if p.get("kind") == "order_create" and p.get("order_number") == order_number]
    ch.add("one order recorded", "the import landed", 1, len(rows))

    row = rows[0]
    ch.add("regulated flag carried", "a header-level flag, no amazon_ prefix, first-class column",
           False, row.get("has_regulated_items"))
    ch.add("supply source carried", "Amazon attributes the dispatch to the source it assigned",
           "057d3fcc-b750-419f-bbcd-4d340c60c430", row.get("fulfillment_supply_source_id"))
    ch.add("amazon id is on item_codes", "import moves it there and blanks line_item_id to \"0\" (L-119)",
           [ITEM_1001], (row.get("items") or [{}])[0].get("item_codes"))
    ch.add("line_item_id cannot serve", "blanked at six sites, deliberately",
           "0", (row.get("items") or [{}])[0].get("line_item_id"))


# --------------------------------------------------------------------- CR-2, the per-parcel write-back

def test_cr2_writeback_accepted(ch, calls, detail):
    # Mapping 4.5 rows 1, 2, 3, 5, 6 and 7 on an accepted parcel (L-23, L-88, L-89, L-113, L-119)
    accepted = parcel("1", MASTER_TRACKING,
                      [R.OrderItemAllocation(811, ITEM_1001, "SKU-1001", 2),
                       R.OrderItemAllocation(812, ITEM_2002, "SKU-2002", 1)])
    payload = R.build_oms_shipping_details_writeback(
        accepted, R.WRITEBACK_STATUS_SUCCESS, oms_order_id=OMS_ORDER_ID)
    post_writeback(ch, calls, payload, "accepted parcel 1")

    rows = shipping_pushes_for(MASTER_TRACKING)
    ch.add("one message recorded", "one message per parcel", 1, len(rows))

    row = rows[0]
    ch.add("row 1, status", "an accepted parcel is a success to OMS", "success", row.get("status"))
    ch.add("row 2, package_id", "reuse OMS's own name; without it a result cannot be attributed (L-113)",
           "1", row.get("package_id"))
    ch.add("row 3, tracking_number", "the number the box actually shipped under",
           MASTER_TRACKING, row.get("tracking_number"))

    items = row.get("order_items") or []
    ch.add("both lines closed", "the parcel drew on both lines", 2, len(items))
    ch.add("row 5, the OMS line id", "OMS closes the line the parcel drew from", 811, items[0].get("id"))
    ch.add("row 6, the quantity", "OMS cannot otherwise tell which quantity succeeded (L-89)",
           2, items[0].get("quantity"))
    ch.add("row 7, item_codes", "holds Amazon's id; line_item_id cannot serve (L-119)",
           [ITEM_1001], items[0].get("item_codes"))
    ch.add("no failure reason on a success", "failure_reason is the failure channel only",
           None, row.get("failure_reason"))


def test_cr2_writeback_rejected(ch, calls, detail):
    # Mapping 4.5 row 4 and 5.4, Appendix A.5: Amazon's own code and message reach OMS (L-38, L-127)
    rejected = parcel("2", SECOND_TRACKING, [R.OrderItemAllocation(811, ITEM_1001, "SKU-1001", 3)])
    payload = R.build_oms_shipping_details_writeback(
        rejected, R.WRITEBACK_STATUS_FAILURE, error_code="InvalidInput",
        error_message="Tracking number %s is not valid for carrier code Other." % SECOND_TRACKING,
        oms_order_id=OMS_ORDER_ID)
    post_writeback(ch, calls, payload, "rejected parcel 2")

    row = shipping_pushes_for(SECOND_TRACKING)[0]
    ch.add("row 1, status", "a rejected parcel is a failure to OMS", "failure", row.get("status"))
    ch.add("row 2, package_id", "which parcel failed", "2", row.get("package_id"))

    reason = row.get("failure_reason") or ""
    ch.add("row 4 carries the code", "the code operations searches on", True, "InvalidInput" in reason)
    ch.add("row 4 carries the message", "operations retries from this text alone", True,
           SECOND_TRACKING in reason)
    ch.add("row 4 carries the package reference", "failure_reason is the only channel a marketplace "
           "integration has (L-127)", True, "parcel 2" in reason)
    ch.add("row 6, the quantity that failed", "the quantity this parcel carried", 3,
           (row.get("order_items") or [{}])[0].get("quantity"))


def test_cr2_writeback_per_parcel(ch, calls, detail):
    # 5.4 and 6: one message per parcel, and a rejection never reverses an acceptance (L-90)
    good = parcel("1", "MT-PERPARCEL-OK", [R.OrderItemAllocation(811, ITEM_1001, "SKU-1001", 2)])
    bad = parcel("2", "CJ-PERPARCEL-BAD", [R.OrderItemAllocation(811, ITEM_1001, "SKU-1001", 3)])

    post_writeback(ch, calls, R.build_oms_shipping_details_writeback(
        good, R.WRITEBACK_STATUS_SUCCESS, oms_order_id=OMS_ORDER_ID), "parcel 1 success")
    post_writeback(ch, calls, R.build_oms_shipping_details_writeback(
        bad, R.WRITEBACK_STATUS_FAILURE, error_code="InvalidInput", error_message="rejected",
        oms_order_id=OMS_ORDER_ID), "parcel 2 failure")

    ok_rows = shipping_pushes_for("MT-PERPARCEL-OK")
    bad_rows = shipping_pushes_for("CJ-PERPARCEL-BAD")
    ch.add("two messages, not one", "collapsing them loses which parcel failed",
           [1, 1], [len(ok_rows), len(bad_rows)])
    ch.add("each attributable to its own parcel", "the package reference is what attributes it",
           ["1", "2"], [ok_rows[0].get("package_id"), bad_rows[0].get("package_id")])
    ch.add("the acceptance stands", "a rejected parcel never reverses an accepted one (L-90)",
           "success", ok_rows[0].get("status"))
    ch.add("the rejection is its own", "the order shows Partial with the failed parcel's state on its box row",
           "failure", bad_rows[0].get("status"))

    good.status = R.ParcelConfirmationStatus.ACCEPTED
    bad.status = R.ParcelConfirmationStatus.REJECTED
    ch.add("order-level row", "R-MAP 5.2; no marketplace-level status is set (L-130, L-138)",
           "some accepted some failed", R.order_level_outcome([good, bad]))


def test_cr2_failure_reason_width(ch, calls, detail):
    # Mapping 4.5 row 4: failure_reason must carry at least 500 characters (L-38, L-33)
    long_message = "Tracking number is not valid for carrier code Other. " * 12
    rejected = parcel("3", "TRK-LONGREASON-1", [R.OrderItemAllocation(811, ITEM_1001, "SKU-1001", 1)])
    payload = R.build_oms_shipping_details_writeback(
        rejected, R.WRITEBACK_STATUS_FAILURE, error_code="InvalidInput",
        error_message=long_message, oms_order_id=OMS_ORDER_ID)
    sent = payload["shipping_details"]["failure_reason"]
    ch.add("the reason sent is over 500 characters", "the width the row asks for",
           True, len(sent) >= R.MIN_FAILURE_REASON_LENGTH)

    post_writeback(ch, calls, payload, "long failure reason")

    row = shipping_pushes_for("TRK-LONGREASON-1")[0]
    held = row.get("failure_reason") or ""
    ch.add("OMS held it whole", "a truncated reason is a reason operations cannot act on",
           len(sent), len(held))
    ch.add("character for character", "the message survives the round trip unaltered", sent, held)


def test_cr2_blocked_never_order_number(ch, calls, detail):
    # C-17's second site: the order number is never written back as a tracking number (L-66)
    #
    # And what that costs, on the contract as it stands. shipping_details declares tracking_number
    # required (mapping 4.5 row 3, nullable No), so a parcel blocked for having no tracking number
    # cannot be reported through this endpoint at all -- and failure_reason is the only structured
    # failure channel a marketplace integration has (L-127). Substituting the order number would
    # make the call pass and is exactly the defect C-17 removes, so the call is left to fail.
    blocked = R.BlockedParcel(
        R.EParcelBlockReason.MISSING_TRACKING_NUMBER,
        "the carrier returned no tracking number for shipment SHP-41277-1",
        tracking_number=None)
    payload = R.build_oms_blocked_writeback(blocked, oms_order_id=OMS_ORDER_ID)
    sent = payload["shipping_details"]
    ch.add("no tracking number is sent", "publishRtsDetails falls back to getOrderNumber() today (L-66)",
           None, sent.get("tracking_number"))
    ch.add("the order number is not substituted", "the order number is not a tracking number",
           False, sent.get("tracking_number") == OMS_ORDER_NUMBER)

    post_writeback(ch, calls, payload, "blocked parcel with no tracking number", expect=422)
    ch.add("OMS holds no row under the order number", "recording a shipment under a number that is "
           "not a tracking number is the defect", 0, len(shipping_pushes_for(OMS_ORDER_NUMBER)))

    # The block that does have a number reaches OMS, which is where the reason can travel today.
    numbered = R.BlockedParcel(
        R.EParcelBlockReason.MISSING_CARRIER_MAPPING,
        "no carrier identity resolves for shipment SHP-41277-2",
        tracking_number="TRK-BLOCKED-CARRIER")
    post_writeback(ch, calls, R.build_oms_blocked_writeback(numbered, oms_order_id=OMS_ORDER_ID),
                   "blocked parcel carrying its tracking number")

    row = shipping_pushes_for("TRK-BLOCKED-CARRIER")[0]
    ch.add("it is a failure to OMS", "a blocked parcel never reads as a shipment", "failure", row.get("status"))
    ch.add("the block reason reached OMS", "the only structured failure channel a marketplace "
           "integration has (L-127)", True,
           R.EParcelBlockReason.MISSING_CARRIER_MAPPING in (row.get("failure_reason") or ""))


# --------------------------------------------------------------------- C-13, how OMS reaches Partial

def test_c13_update_status_item_subset(ch, calls, detail):
    # C-13: a SHIPPED update carrying fewer items than the order holds is how OMS reaches Partial (L-47, L-114)
    subset = [{"id": 811, "item_codes": [ITEM_1001], "quantity": 2}]
    status, _ = call_oms("POST", "/rest/v1/orders/%d/update_status?new_status=SHIPPED" % OMS_ORDER_ID,
                         {"order_items": subset, "tracking_number": MASTER_TRACKING})
    calls.append("POST /rest/v1/orders/%d/update_status?new_status=SHIPPED -> %s" % (OMS_ORDER_ID, status))
    ch.add("OMS accepted the update", "the marketplace path may now carry a body on SHIPPED", 200, status)

    rows = order_pushes_of("update_status", OMS_ORDER_ID)
    ch.add("one update recorded", "the status update landed", 1, len(rows))

    row = rows[0]
    ch.add("the status is SHIPPED", "requireBody holds RETURN, EXCHANGE, FAILED_DELIVERY and now SHIPPED (L-47)",
           "SHIPPED", row.get("new_status"))
    ch.add("the item subset reached OMS", "without it the subset is stripped and Partial is unreachable",
           1, len(row.get("order_items") or []))
    ch.add("the subset names the line", "OMS splits the excluded items into a separate shipment (L-114)",
           811, (row.get("order_items") or [{}])[0].get("id"))
    ch.add("and the quantity that shipped", "fewer items than the order holds is what triggers the split",
           2, (row.get("order_items") or [{}])[0].get("quantity"))


# --------------------------------------------------------------------- CR-4, the ledger read

def test_cr4_order_items_read(ch, calls, detail):
    # Mapping 4.3 and rule N-3: the OMS line read the quantity ledger is built from (L-89, L-99)
    status, body = call_oms("GET", "/rest/v1/orders/%d/order_items" % OMS_ORDER_ID)
    calls.append("GET /rest/v1/orders/%d/order_items -> %s" % (OMS_ORDER_ID, status))
    ch.add("OMS answered", "a configured route the ledger reads", 200, status)

    lines = body.get("payload") or []
    ch.add("lines returned", "the order's own items", True, len(lines) > 0)

    line = lines[0]
    ch.truthy("the OMS line id", "the id the write-back closes", line.get("order_item_id"))
    ch.truthy("the quantity", "the allocated half of the ledger", line.get("quantity"))
    ch.add("item_codes is an array", "Amazon's id lives here, never on line_item_id (L-119)",
           True, isinstance(line.get("item_codes"), list))

    # The remaining quantity is never computed from this read alone: Amazon's QuantityShipped, re-read
    # immediately before each submit, is the authority (L-9, L-10). This case pins the OMS half only.
    ch.add("no marketplace confirmed count here", "our own accepted count is never trusted over Amazon's",
           None, line.get("mp_confirmed_quantity"))


def test_cr4_order_items_unreachable(ch, calls, detail):
    # Rule N-4: an OMS read that fails is an outcome, not a licence to proceed on stale numbers (L-87)
    status, _ = call_oms("GET", "/rest/v1/orders/9990500/order_items")
    calls.append("GET /rest/v1/orders/9990500/order_items -> %s" % status)
    ch.add("OMS is unreachable", "the marker route that answers 500", 500, status)

    decision = R.gate_unreachable("GET /rest/v1/orders/9990500/order_items answered %s" % status)
    ch.add("the gate blocks", "never assume the quantities are still valid on a failed read",
           True, decision.blocked)
    ch.add("block reason", "marketplace validation unavailable",
           R.EGateBlockReason.MARKETPLACE_VALIDATION_UNAVAILABLE, decision.reason)
    ch.add("no write-back was published for it", "nothing is reported that was never attempted",
           0, len(shipping_pushes_for("9990500")))

# ===================================================================== Register Cases

case("IA-5109-US3-CR0-ORDER-IMPORT-FIELDS",
     "CR-0: The IA-5111 import fields reach OMS on order create",
     "An Amazon order carrying has_regulated_items and fulfillment_supply_source_id",
     ["OMS accepts the order", "Both fields are carried through, without an amazon_ prefix",
      "Amazon's order-item id is on item_codes[] and line_item_id is blanked"],
     "Requirements 1 CR-0; Summary 2.2 CR-0; Mapping 4.4 row 10; Claim L-20, L-119, L-134",
     test_cr0_import_fields)

case("IA-5109-US3-CR2-WRITEBACK-ACCEPTED",
     "Mapping 4.5: An accepted parcel's write-back, row for row",
     "Parcel 1 accepted by Amazon, drawing on two OMS lines",
     ["OMS accepts it", "package_id, tracking_number and status success are recorded",
      "Each line carries its id, its quantity and its item_codes[]", "No failure reason"],
     "Mapping 4.5 rows 1, 2, 3, 5, 6, 7, 5.4; Summary 2.1 C-23; Claim L-23, L-89, L-113, L-119",
     test_cr2_writeback_accepted)

case("IA-5109-US3-CR2-WRITEBACK-REJECTED",
     "Mapping 4.5 row 4: A rejection carries Amazon's own code and message",
     "Parcel 2 rejected with InvalidInput on the tracking number",
     ["Status is failure", "failure_reason carries the code, the message and the package reference",
      "The quantity that failed is recorded"],
     "Mapping 4.5 row 4, 5.4, Appendix A.5; Claim L-38, L-33, L-127",
     test_cr2_writeback_rejected)

case("IA-5109-US3-CR2-WRITEBACK-PER-PARCEL",
     "Mapping 6: One message per parcel, and a rejection never reverses an acceptance",
     "One order whose parcel 1 Amazon accepted and whose parcel 2 Amazon rejected",
     ["Two messages reach OMS, not one", "Each is attributable to its own package reference",
      "The acceptance stands", "The order lands on the Partial row of 5.2"],
     "Mapping 4.5, 5.2, 5.4, 6; Summary 2.1 C-23; Claim L-90, L-120, L-130",
     test_cr2_writeback_per_parcel)

case("IA-5109-US3-CR2-FAILURE-REASON-WIDTH",
     "Mapping 4.5 row 4: failure_reason carries at least 500 characters",
     "A rejection whose Amazon message runs past 500 characters",
     ["The reason sent exceeds 500 characters", "OMS holds it whole, with nothing lost from the end"],
     "Mapping 4.5 row 4; Summary 2.2 CR-2; Claim L-38, L-33",
     test_cr2_failure_reason_width)

case("IA-5109-US3-CR2-BLOCKED-NEVER-ORDER-NUMBER",
     "C-17: The order number is never written back as a tracking number",
     "A parcel blocked because the carrier returned no tracking number, and one blocked with a number",
     ["No tracking number is sent, and the order number is not substituted",
      "OMS answers 422 because tracking_number is required, so the block cannot be reported here",
      "OMS holds no row under the order number",
      "A block that does carry a tracking number reaches OMS with its reason"],
     "Mapping 4.5 row 3, 7 N-4, N-6; Summary 2.1 C-17; Claim L-66, L-127",
     test_cr2_blocked_never_order_number)

case("IA-5109-US3-C13-UPDATE-STATUS-ITEM-SUBSET",
     "C-13: A SHIPPED update carrying an item subset is how OMS reaches Partial",
     "A ready-to-ship update naming fewer items than the order holds",
     ["OMS accepts the update on new_status SHIPPED", "The item subset reaches OMS",
      "It names the line and the quantity that shipped"],
     "Mapping 5.2; Summary 2.1 C-13; Claim L-47, L-114, L-46",
     test_c13_update_status_item_subset)

case("IA-5109-US3-CR4-ORDER-ITEMS-READ",
     "Mapping 4.3: The OMS line read the quantity ledger is built from",
     "A GET of the order's items on the OMS mock",
     ["OMS answers with the order's lines", "item_codes[] is an array",
      "No marketplace confirmed count is read from here, because Amazon's is the authority"],
     "Mapping 4.3, 7 N-3; Summary 2.2 CR-4; Claim L-9, L-10, L-89, L-119",
     test_cr4_order_items_read)

case("IA-5109-US3-CR4-ORDER-ITEMS-UNREACHABLE",
     "Rule N-4: An OMS read that fails blocks rather than proceeding on stale numbers",
     "The OMS order-items read answers 500",
     ["The gate blocks with MARKETPLACE_VALIDATION_UNAVAILABLE",
      "No write-back is published for a call that was never attempted"],
     "Mapping 7 N-4; Claim L-87",
     test_cr4_order_items_unreachable)


# ===================================================================== Execution Engine

def preflight():
    global BASE_OMS

    print(f"{SUITE_NAME}")
    print(f"  oms dir  : {OMS_DIR}")
    print(f"  run dir  : {RUN_DIR}")

    os.makedirs(OMS_DATA_DIR, exist_ok=True)
    for name in OMS_STORES:
        with open(os.path.join(OMS_DATA_DIR, name + ".json"), "w", encoding="utf-8") as f:
            f.write("[]")

    BASE_OMS = _start_ephemeral_oms()
    EVIDENCE["oms mock"] = f"Anchanto OMS mock at {BASE_OMS}"
    print(f"  state    : run-scoped ({len(OMS_STORES)} stores, at {OMS_DATA_DIR})")

    st, _ = call_oms("POST", "/oauth/token", {"grant_type": "client_credentials"})
    if st == 0:
        sys.exit(f"PREFLIGHT FAIL: the OMS mock did not answer on {BASE_OMS}")
    print(f"  mock     : active on {BASE_OMS} (/oauth/token -> {st})")


def capture():
    src = os.path.join(OMS_DATA_DIR, OMS_LOG_FILE)
    os.makedirs(RUN_DIR, exist_ok=True)
    if os.path.exists(src) and os.path.abspath(src) != os.path.abspath(os.path.join(RUN_DIR, OMS_LOG_FILE)):
        shutil.copy2(src, os.path.join(RUN_DIR, OMS_LOG_FILE))
        try:
            with open(src, "r", encoding="utf-8") as f:
                entries = len(json.load(f).get("log", {}).get("entries", []))
            EVIDENCE["mock call log"] = f"captured -- {entries} entries"
        except Exception:
            EVIDENCE["mock call log"] = "captured -- unparseable"
    else:
        EVIDENCE["mock call log"] = "not captured -- no log file"

    stores_data = {name: store(name) for name in OMS_STORES}
    with open(os.path.join(RUN_DIR, "stores.json"), "w", encoding="utf-8") as f:
        json.dump(stores_data, f, indent=2)
    EVIDENCE["mock stores"] = f"captured -- {len(OMS_STORES)} files"


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
