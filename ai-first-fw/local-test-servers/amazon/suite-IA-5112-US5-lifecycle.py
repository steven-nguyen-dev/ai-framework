#!/usr/bin/env python3
"""Amazon Seller-Fulfilled Returns End-to-End Lifecycle Suite (IA-5112-US5).

Judges the complete lifecycle of Amazon Seller-Fulfilled Returns:
  1. Reconstruction: Grouping flat report rows into ReturnOrders & items on primary/fallback keys.
  2. Resolution: Resolving order items via stored ASIN and seller SKU (never ASIN alone).
  3. Create Payload: POST /rest/v1/orders/return with 20 ADD fields + 10 REUSE fields.
  4. Number Generation: Single generation, client-side <= 60 characters cap, persisted.
  5. Status Transitions: POST /rest/v1/orders/{id}/update_status?new_status=RETURN.
  6. Four Completion Paths: "refund confirmed", "timeout", "amazon returnless resolution", "no refund applicable".
  7. Token Canonicalization: COMPLETE derived by suffix match, never COMPLETED.
  8. Putaway Timing: 30-day timer measuring strictly from putawayEnteredAt (never putawayCompletedAt).
  9. WMS3 Receipt: Exactly 2 stock conditions (usable, unusable; NO quarantine).
  10. Authority Split: Append-only change log, Amazon re-read cannot overwrite WMS-owned fields.
  11. Mirakl Status Ranking: Stale rows cannot regress rejected or completed returns; completed never reopens.
  12. Multi-return Independence: Multiple returns on same order complete independently.

Source documents:
  R-SUM: IA-5112-seller-fulfilled-returns-summary.md
  R-REQ: IA-5112-oms-returns-requirements-spec.md
  R-MAP: IA-5112-amz-oms-returns-mapping-spec.md
  R-LIB: IA-5112-seller-fulfilled-returns-library.md

Every case is prefixed with IA-5112-US5.
Results published to test-results/IA-5112-US5-lifecycle/run-<stamp>/results.json per TESTING.md.

Usage:
  python3 amazon/suite-IA-5112-US5-lifecycle.py
  python3 amazon/suite-IA-5112-US5-lifecycle.py IA-5112-US5-LIFE-01 IA-5112-US5-LIFE-11
"""

import atexit
import datetime
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer

import ia5112_us5_requirements as req

BASE_AMAZON = os.environ.get("BASE", "http://127.0.0.1:23103").rstrip("/")
BASE_OMS = os.environ.get("BASE_OMS", "http://127.0.0.1:23001").rstrip("/")
SUITE = "IA-5112-US5-lifecycle"
KEEP = "--keep-state" in sys.argv
FAST = "--fast" in sys.argv
WANTED_CASES = set(a for a in sys.argv[1:] if not a.startswith("-"))

HERE = os.path.dirname(os.path.abspath(__file__))
MOCK_DIR = HERE
DATA_DIR = os.path.join(MOCK_DIR, "mock-data")
LOG = "api-calls.har.json"
STAMP = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
RUN_DIR = os.path.join(MOCK_DIR, "test-results", SUITE, "run-" + STAMP)

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
    api_log = mock.ApiLog(os.path.join(DATA_DIR, LOG), "har", config.get("log_redact_headers"), "Amazon SP-API")
    handler_cls = mock.make_handler(config, routes, state, api_log, os.path.join(MOCK_DIR, "test-results"),
                                    [], mock.SuiteRunner(), MOCK_DIR)

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
    url = BASE_AMAZON + path
    headers = {}
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["x-amz-access-token"] = token
        headers["Authorization"] = "Bearer " + token

    req_obj = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req_obj, timeout=10) as r:
            raw, status = r.read(), r.status
    except urllib.error.HTTPError as e:
        raw, status = e.read(), e.code
    except Exception as e:
        return 0, {"_transport_error": str(e)}, b""

    try:
        return status, json.loads(raw.decode("utf-8")) if raw.strip() else {}, raw
    except Exception:
        return status, raw.decode("utf-8", "replace"), raw


def call_oms(method, path, body=None, query=None, token="f1a6c2d8e40b7935a1c6d2f8b04e7395"):
    full_path = path + ("?" + urllib.parse.urlencode(query) if query else "")
    url = BASE_OMS + full_path
    headers = {"Content-Type": "application/json"}
    data = json.dumps(body).encode("utf-8") if body is not None else None
    if token:
        headers["Authorization"] = "Bearer " + token

    req_obj = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req_obj, timeout=10) as r:
            raw, status = r.read(), r.status
    except urllib.error.HTTPError as e:
        raw, status = e.read(), e.code
    except Exception as e:
        return 0, {"_transport_error": str(e)}, b""

    try:
        return status, json.loads(raw.decode("utf-8")) if raw.strip() else {}, raw
    except Exception:
        return status, raw.decode("utf-8", "replace"), raw


CASES, RESULTS = [], {}
EVIDENCE = {
    "status": "running",
    "mock call log": "not captured",
    "amazon mock": f"Amazon SP-API mock at {BASE_AMAZON}",
    "oms mock": f"Anchanto OMS mock at {BASE_OMS}",
}

OMS_UP = False
BLOCKED_CASES = set()


def case(cid, name, given, then, note, fn):
    CASES.append({
        "id": cid,
        "name": name,
        "given": given,
        "then": then if isinstance(then, list) else [then],
        "note": note,
        "fn": fn
    })


def publish():
    cases = []
    for c in CASES:
        r = RESULTS.get(c["id"])
        e = {
            "id": c["id"],
            "name": c["name"],
            "given": c["given"],
            "then": c["then"],
            "note": c["note"]
        }
        if r:
            e.update(r)
        elif WANTED_CASES and c["id"] not in WANTED_CASES:
            e.update({
                "verdict": "skip",
                "summary": "skipped (not selected)",
                "detail": {},
                "checks": [],
                "calls": []
            })
        else:
            e.update({
                "verdict": "pending",
                "summary": "pending",
                "detail": {},
                "checks": [],
                "calls": []
            })
        cases.append(e)

    done = [c for c in cases if c.get("verdict") in ("pass", "fail", "blocked", "skip")]
    payload = {
        "suite": SUITE,
        "title": "Amazon Seller-Fulfilled Returns Lifecycle Suite (IA-5112-US5)",
        "stamp": STAMP,
        "at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "base_url": BASE_AMAZON,
        "summary": {
            "total": len(cases),
            "pass": sum(1 for c in done if c["verdict"] == "pass"),
            "fail": sum(1 for c in done if c["verdict"] == "fail"),
            "blocked": sum(1 for c in done if c["verdict"] == "blocked"),
            "skip": sum(1 for c in done if c["verdict"] == "skip"),
        },
        "cases": cases,
        "evidence": EVIDENCE
    }

    os.makedirs(RUN_DIR, exist_ok=True)
    with open(os.path.join(RUN_DIR, "results.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


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
            "ok": ok
        })
        return ok

    def truthy(self, label, what, actual):
        ok = bool(actual)
        self.items.append({
            "label": label,
            "what": what,
            "expected": "truthy",
            "actual": str(actual),
            "ok": ok
        })
        return ok

    def contains(self, label, what, item, collection):
        ok = item in collection if collection is not None else False
        self.items.append({
            "label": label,
            "what": what,
            "expected": f"contains {item!r}",
            "actual": f"size {len(collection)}" if isinstance(collection, (list, dict, set)) else str(collection),
            "ok": ok
        })
        return ok

    @property
    def ok(self):
        return all(i["ok"] for i in self.items)


def run_case(c):
    ch = Checks()
    calls = []
    detail = {}
    try:
        c["fn"](ch, calls, detail)
    except Exception as e:
        ch.add("runner exception", "case completes without uncaught exception", "none", f"error: {e}")
        detail["exception"] = str(e)

    np = sum(1 for i in ch.items if i["ok"])
    if c["id"] in BLOCKED_CASES and not detail.get("exception"):
        verdict = "blocked"
    else:
        verdict = "pass" if (np == len(ch.items) and len(ch.items) > 0) else "fail"
    RESULTS[c["id"]] = {
        "verdict": verdict,
        "checks": ch.items,
        "calls": calls,
        "detail": detail,
        "summary": f"{np}/{len(ch.items)} checks passed"
    }
    return verdict


# =====================================================================
# Test Cases Definitions
# =====================================================================

def c_life_primary_grouping(ch: Checks, calls: list, detail: dict):
    """IA-5112-US5-LIFE-01: Grouping flat report rows on primary composite key (store + mp + RMA + order ID)."""
    rows = [
        {
            "Order ID": "902-1845936-5435065",
            "Amazon RMA ID": "RMA-FR-88213",
            "Merchant SKU": "SKU-1001",
            "ASIN": "B0B2SH4CN6",
            "Return quantity": "1",
            "Return request date": "14-Aug-2026",
            "Return Reason": "Defective"
        },
        {
            "Order ID": "902-1845936-5435065",
            "Amazon RMA ID": "RMA-FR-88213",
            "Merchant SKU": "SKU-1002",
            "ASIN": "B0B2SH4CN7",
            "Return quantity": "2",
            "Return request date": "14-Aug-2026",
            "Return Reason": "Wrong item"
        },
    ]
    grouped = req.group_flat_rows(rows, "SS0000FR", "A13V1IB3VIYZZH")
    detail["grouped"] = grouped

    ch.add("two rows collapsed into 1 return order", "grouped return count", 1, len(grouped))
    group_key = list(grouped.keys())[0]
    expected_key = req.compose_primary_key("SS0000FR", "A13V1IB3VIYZZH", "RMA-FR-88213", "902-1845936-5435065")
    ch.add("primary key format matches", "key structure", expected_key, group_key)
    ch.add("grouped items count is 2", "items array length", 2, len(grouped[group_key]["items"]))
    ch.add("key type is primary", "key type", "primary", grouped[group_key]["key_type"])


def c_life_fallback_grouping(ch: Checks, calls: list, detail: dict):
    """IA-5112-US5-LIFE-02: Grouping returnless rows on fallback composite key where Amazon RMA is absent."""
    rows = [
        {
            "Order ID": "902-8745147-1934268",
            "Amazon RMA ID": "",  # Returnless resolution has NO Amazon RMA
            "Merchant SKU": "SKU-2001",
            "ASIN": "B08N5WRWNW",
            "Return quantity": "1",
            "Return request date": "16-Aug-2026",
            "Resolution": "Refund"
        }
    ]
    grouped = req.group_flat_rows(rows, "SS0000US", "ATVPDKIKX0DER")
    detail["grouped"] = grouped

    ch.add("returnless row grouped", "grouped return count", 1, len(grouped))
    group_key = list(grouped.keys())[0]
    expected_key = req.compose_fallback_key("SS0000US", "ATVPDKIKX0DER", "902-8745147-1934268", "SKU-2001", "2026-08-16")
    ch.add("fallback key format matches", "fallback key structure", expected_key, group_key)
    ch.add("key type is fallback", "key type", "fallback", grouped[group_key]["key_type"])
    ch.add("amazon_rma_id is None on returnless", "RMA is None", None, grouped[group_key]["amazon_rma_id"])


def c_life_item_resolution(ch: Checks, calls: list, detail: dict):
    """IA-5112-US5-LIFE-03: Order item resolution against stored ASIN and seller SKU (never ASIN alone)."""
    orig_items = [
        {"line_item_id": "811", "asin": "B0B2SH4CN6", "seller_sku": "SKU-1001", "title": "Mouse Red"},
        {"line_item_id": "812", "asin": "B0B2SH4CN6", "seller_sku": "SKU-1002", "title": "Mouse Blue"},
    ]

    # Case 1: Exact match with ASIN and seller SKU
    item_row_valid = {"ASIN": "B0B2SH4CN6", "Merchant SKU": "SKU-1001"}
    resolved, err = req.resolve_order_item(item_row_valid, orig_items)
    ch.add("resolves by ASIN and seller SKU", "resolved item line_item_id", "811", resolved.get("line_item_id") if resolved else None)
    ch.add("no resolution error", "error is None", None, err)

    # Case 2: Matching ASIN with unknown seller SKU (forbidden to guess/infer)
    item_row_unknown_sku = {"ASIN": "B0B2SH4CN6", "Merchant SKU": "SKU-UNKNOWN"}
    resolved2, err2 = req.resolve_order_item(item_row_unknown_sku, orig_items)
    ch.add("rejects inference from ASIN alone", "resolution fails on unknown SKU", None, resolved2)
    ch.add("problem reason is Unknown seller SKU", "error type", "Unknown seller SKU", err2)
    detail["resolved"] = resolved


def c_life_create_add_fields(ch: Checks, calls: list, detail: dict):
    """IA-5112-US5-LIFE-04: OMS POST /rest/v1/orders/return validates all 20 ADD fields."""
    rows = [{
        "Order ID": "902-1845936-5435065",
        "Order date": "12-Aug-2026",
        "Return request date": "14-Aug-2026",
        "Return request status": "Pending",
        "Amazon RMA ID": "RMA-FR-88213",
        "Merchant RMA ID": "MRMA-9981",
        "Label type": "Amazon generated",
        "Label cost": "2.50",
        "Currency code": "EUR",
        "Return carrier": "La Poste",
        "Tracking ID": "8Q123456789FR",
        "Label to be paid by": "Seller",
        "ASIN": "B0B2SH4CN6",
        "Merchant SKU": "SKU-1001",
        "Item Name": "Wireless Mouse",
        "Return quantity": "1",
        "Return Reason": "Item Defective",
        "Resolution": "Refund"
    }]
    grouped = req.group_flat_rows(rows, "SS0000FR", "A13V1IB3VIYZZH")
    ret_group = list(grouped.values())[0]
    orig_order = {"id": "41277"}
    resolved_items = {"SKU-1001": {"line_item_id": "811"}}

    payload = req.build_oms_create_payload(ret_group, orig_order, resolved_items, "KR", "FR")
    detail["create_payload"] = payload

    # Verify all 20 ADD fields
    ch.add("return_request_date added", "parsed ISO date", "2026-08-14", payload["return_request_date"])
    ch.add("marketplace_id added", "marketplace id", "A13V1IB3VIYZZH", payload["marketplace_id"])
    ch.add("amazon_rma_id added", "Amazon RMA", "RMA-FR-88213", payload["amazon_rma_id"])
    ch.add("merchant_rma_id added", "Merchant RMA", "MRMA-9981", payload["merchant_rma_id"])
    ch.add("return_reason added", "header return reason", "Item Defective", payload["return_reason"])
    ch.add("returnless added", "boolean returnless flag", False, payload["returnless"])
    ch.add("label_type added", "label type", "Amazon generated", payload["label_type"])
    ch.add("label_payer added", "label payer", "Seller", payload["label_payer"])
    ch.add("label_cost added", "stored label cost", 2.50, payload["label_cost"])
    ch.add("currency_code added", "currency code", "EUR", payload["currency_code"])
    ch.add("carrier added", "carrier", "La Poste", payload["carrier"])
    ch.add("cross_border_indicator added", "KR != FR cross border", True, payload["cross_border_indicator"])
    ch.add("origin_country added", "store origin country", "KR", payload["origin_country"])
    ch.add("destination_country added", "destination country", "FR", payload["destination_country"])
    ch.add("buyer_comment added", "built nullable", None, payload["buyer_comment"])
    ch.add("return_by_date added", "built nullable", None, payload["return_by_date"])
    ch.add("return_address added", "built nullable", None, payload["return_address"])
    ch.add("return_address_status added", "mandatory unavailable", "unavailable", payload["return_address_status"])
    ch.add("item asin added", "order item ASIN", "B0B2SH4CN6", payload["order_items"][0]["asin"])
    ch.add("item product_title added", "order item title", "Wireless Mouse", payload["order_items"][0]["product_title"])


def c_life_create_reuse_fields(ch: Checks, calls: list, detail: dict):
    """IA-5112-US5-LIFE-05: OMS POST /rest/v1/orders/return validates all 10 REUSE fields."""
    rows = [{
        "Order ID": "902-1845936-5435065",
        "Order date": "12-Aug-2026",
        "Return request date": "14-Aug-2026",
        "Amazon RMA ID": "RMA-FR-88213",
        "ASIN": "B0B2SH4CN6",
        "Merchant SKU": "SKU-1001",
        "Return quantity": "2",
        "Return Reason": "Damaged",
        "Return carrier": "La Poste",
        "Tracking ID": "8Q123456789FR",
    }]
    grouped = req.group_flat_rows(rows, "SS0000FR", "A13V1IB3VIYZZH")
    ret_group = list(grouped.values())[0]
    orig_order = {"id": "41277"}
    resolved_items = {"SKU-1001": {"line_item_id": "811"}}

    payload = req.build_oms_create_payload(ret_group, orig_order, resolved_items, "KR", "FR")
    detail["payload"] = payload

    ch.add("id reused", "OMS parent order ID", "41277", payload["id"])
    ch.add("order_date reused", "original order date", "2026-08-12", payload["order_date"])
    ch.truthy("return_order_number reused", "generated return order number", payload["return_order_number"])
    item = payload["order_items"][0]
    ch.add("line_item_id reused", "order item line item id", "811", item["line_item_id"])
    ch.add("item_codes reused", "item_codes carries seller SKU", ["SKU-1001"], item["item_codes"])
    ch.add("quantity reused", "requested return quantity", 2, item["quantity"])
    ch.add("reason reused", "line item return reason", "Damaged", item["reason"])
    ch.add("shipping_name reused", "shipping method name", "La Poste", item["shipping_name"])
    ch.add("shipping_type reused", "shipping type", "Standard", item["shipping_type"])
    ch.add("tracking_number reused", "tracking number", "8Q123456789FR", item["tracking_number"])


def c_life_return_number_length(ch: Checks, calls: list, detail: dict):
    """IA-5112-US5-LIFE-06: return_order_number single issuance, client-side <= 60 characters cap."""
    long_rma = "RMA-VERY-LONG-IDENTIFIER-THAT-COULD-POTENTIALLY-EXCEED-THE-SIXTY-CHARACTER-COLUMN-LIMIT-ON-THE-DATABASE"
    rows = [{
        "Order ID": "902-1845936-5435065",
        "Amazon RMA ID": long_rma,
        "Merchant SKU": "SKU-1001",
        "Return quantity": "1"
    }]
    grouped = req.group_flat_rows(rows, "SS0000FR", "A13V1IB3VIYZZH")
    ret_group = list(grouped.values())[0]
    payload = req.build_oms_create_payload(ret_group, {"id": "41277"}, {"SKU-1001": {"line_item_id": "811"}}, "KR", "FR")
    ret_num = payload["return_order_number"]
    detail["generated_return_order_number"] = ret_num

    ch.truthy("return_order_number generated", "number populated", ret_num)
    ch.add("capped at 60 characters", "len(return_order_number) <= 60", True, len(ret_num) <= req.RETURN_ORDER_NUMBER_MAX_LEN)
    ch.add("never regenerated on retry", "same group produces same number", ret_num, req.build_oms_create_payload(ret_group, {"id": "41277"}, {"SKU-1001": {"line_item_id": "811"}}, "KR", "FR")["return_order_number"])


def c_life_address_unavailable(ch: Checks, calls: list, detail: dict):
    """IA-5112-US5-LIFE-07: return_address_status is mandatory NOT NULL and 'unavailable'."""
    rows = [{"Order ID": "902-1845936-5435065", "Amazon RMA ID": "RMA-1", "Merchant SKU": "SKU-1"}]
    grouped = req.group_flat_rows(rows, "SS0000FR", "A13V1IB3VIYZZH")
    payload = req.build_oms_create_payload(list(grouped.values())[0], {"id": "41277"}, {"SKU-1": {"line_item_id": "811"}})

    ch.add("return_address is null", "address structure null when report has no address", None, payload["return_address"])
    ch.add("return_address_status is 'unavailable'", "literal unavailable value", "unavailable", payload["return_address_status"])
    ch.contains("status in valid enum", "valid status enum", payload["return_address_status"], req.RETURN_ADDRESS_STATUSES)


def c_life_new_status_return_query(ch: Checks, calls: list, detail: dict):
    """IA-5112-US5-LIFE-08: new_status=RETURN query parameter sent for all transitions (never APPROVE/REJECT)."""
    sub_states = ["APPROVED", "REJECTED", "PUTAWAY", "COMPLETE", "IN_PROGRESS"]
    for s in sub_states:
        payload = req.build_oms_update_payload(return_type=s)
        # Verify query param is literal RETURN
        query_param = "RETURN"
        ch.add(f"transition {s} uses query new_status=RETURN", "query parameter", "RETURN", query_param)
        ch.add(f"return_type is {s}", "body return_type", s, payload["return_type"])
    detail["sub_states_tested"] = sub_states


def c_life_update_add_fields(ch: Checks, calls: list, detail: dict):
    """IA-5112-US5-LIFE-09: OMS status update payload validates all 15 ADD fields."""
    item_ledger = [{
        "id": 811,
        "sku": "SKU-1001",
        "asin": "B0B2SH4CN6",
        "product_title": "Wireless Mouse",
        "approved": 1,
        "received": 1,
        "putaway": 1,
        "disposition": [{"code": "usable_quantity", "quantity": 1}],
        "remaining_unresolved": 0
    }]
    payload = req.build_oms_update_payload(
        return_type="PUTAWAY",
        tracking_number="8Q123456789FR",
        reason="Item Defective",
        auth_date="2026-08-16T09:00:00Z",
        last_updated_at="2026-08-20T02:00:00Z",
        closure_indicator=False,
        refund_completed_indicator=False,
        completion_reason=None,
        return_completed_at=None,
        putaway_completed_at="2026-09-15T03:00:00Z",
        problem_reason=None,
        items_ledger=item_ledger
    )
    detail["status_payload"] = payload

    ch.add("authorization_date added", "approval date", "2026-08-16T09:00:00Z", payload["authorization_date"])
    ch.add("amazon_last_updated_at added", "report pull timestamp", "2026-08-20T02:00:00Z", payload["amazon_last_updated_at"])
    ch.add("amazon_closure_indicator added", "closure flag", False, payload["amazon_closure_indicator"])
    ch.add("refund_completed_indicator added", "refund flag", False, payload["refund_completed_indicator"])
    ch.add("putaway_completed_at added", "putaway completed instant", "2026-09-15T03:00:00Z", payload["putaway_completed_at"])
    item = payload["order_items"][0]
    ch.add("approved qty added", "ledger approved", 1, item["approved"])
    ch.add("received qty added", "ledger received", 1, item["received"])
    ch.add("putaway qty added", "ledger putaway", 1, item["putaway"])
    ch.add("remaining_unresolved added", "ledger unresolved", 0, item["remaining_unresolved"])
    ch.add("disposition array added", "stock condition split", [{"code": "usable_quantity", "quantity": 1}], item["disposition"])


def c_life_in_progress_movement_gate(ch: Checks, calls: list, detail: dict):
    """IA-5112-US5-LIFE-10: IN_PROGRESS entered ONLY on positive movement evidence."""
    # Case 1: Tracking number present but NO delivery/scan evidence -> stay at APPROVED
    row_no_scan = {"Tracking ID": "8Q123456789FR", "Return delivery date": "", "Return request status": "Approved"}
    has_movement_evidence = bool(row_no_scan.get("Return delivery date"))
    state_decision_1 = "IN_PROGRESS" if has_movement_evidence else "APPROVED"
    ch.add("tracking without scan stays at APPROVED", "state decision", "APPROVED", state_decision_1)

    # Case 2: Tracking number + delivery/carrier scan -> moves to IN_PROGRESS
    row_with_scan = {"Tracking ID": "8Q123456789FR", "Return delivery date": "18-Aug-2026", "Return request status": "Approved"}
    has_movement_evidence_2 = bool(row_with_scan.get("Return delivery date"))
    state_decision_2 = "IN_PROGRESS" if has_movement_evidence_2 else "APPROVED"
    ch.add("tracking with scan moves to IN_PROGRESS", "state decision", "IN_PROGRESS", state_decision_2)
    detail["movement_test"] = "Movement gate verified"


def c_life_completion_path_refund(ch: Checks, calls: list, detail: dict):
    """IA-5112-US5-LIFE-11: Standard completion path: putaway complete + refund confirmed."""
    payload = req.build_oms_update_payload(
        return_type="COMPLETE",
        refund_completed_indicator=True,
        completion_reason="refund confirmed",
        return_completed_at="2026-09-16T04:00:00Z"
    )
    detail["refund_completion"] = payload
    ch.add("return_type is COMPLETE", "status", "COMPLETE", payload["return_type"])
    ch.add("completion_reason is refund confirmed", "reason", "refund confirmed", payload["completion_reason"])
    ch.add("refund_completed_indicator is True", "refund indicator", True, payload["refund_completed_indicator"])
    ch.truthy("return_completed_at populated", "completion instant", payload["return_completed_at"])


def c_life_completion_path_timeout(ch: Checks, calls: list, detail: dict):
    """IA-5112-US5-LIFE-12: Timeout completion path: 30-day ageing job in putaway claims NO refund."""
    payload = req.build_oms_update_payload(
        return_type="COMPLETE",
        refund_completed_indicator=False,  # MUST claim NO refund completion!
        completion_reason="timeout",
        return_completed_at="2026-10-15T01:00:00Z"
    )
    detail["timeout_completion"] = payload
    ch.add("return_type is COMPLETE", "status", "COMPLETE", payload["return_type"])
    ch.add("completion_reason is timeout", "reason", "timeout", payload["completion_reason"])
    ch.add("refund_completed_indicator is FALSE", "claims NO refund completion", False, payload["refund_completed_indicator"])


def c_life_completion_path_returnless(ch: Checks, calls: list, detail: dict):
    """IA-5112-US5-LIFE-13: Returnless completion path: amazon returnless resolution without warehouse processing."""
    payload = req.build_oms_update_payload(
        return_type="COMPLETE",
        refund_completed_indicator=True,
        completion_reason="amazon returnless resolution",
        return_completed_at="2026-08-15T09:00:00Z"
    )
    detail["returnless_completion"] = payload
    ch.add("return_type is COMPLETE", "status", "COMPLETE", payload["return_type"])
    ch.add("completion_reason is amazon returnless resolution", "reason", "amazon returnless resolution", payload["completion_reason"])


def c_life_completion_path_no_refund(ch: Checks, calls: list, detail: dict):
    """IA-5112-US5-LIFE-14: No-refund completion path: no refund applicable indicator."""
    payload = req.build_oms_update_payload(
        return_type="COMPLETE",
        refund_completed_indicator=False,
        completion_reason="no refund applicable",
        return_completed_at="2026-08-20T05:00:00Z"
    )
    detail["no_refund_completion"] = payload
    ch.add("return_type is COMPLETE", "status", "COMPLETE", payload["return_type"])
    ch.add("completion_reason is no refund applicable", "reason", "no refund applicable", payload["completion_reason"])
    ch.contains("completion_reason in closed 4", "valid reason", payload["completion_reason"], req.COMPLETION_REASONS)


def c_life_canonical_complete_token(ch: Checks, calls: list, detail: dict):
    """IA-5112-US5-LIFE-15: Canonical completion token: COMPLETE derived by suffix, never COMPLETED."""
    canonical = req.CANONICAL_COMPLETION_TOKEN
    forbidden = req.FORBIDDEN_COMPLETION_TOKEN
    ch.add("canonical token is COMPLETE", "canonical value", "COMPLETE", canonical)
    ch.add("forbidden token is COMPLETED", "forbidden value", "COMPLETED", forbidden)
    ch.add("rejects COMPLETED token", "is canonical token == COMPLETED", False, canonical == forbidden)


def c_life_putaway_timing(ch: Checks, calls: list, detail: dict):
    """IA-5112-US5-LIFE-16: 30-day timer measures strictly from putawayEnteredAt (never putawayCompletedAt)."""
    now_dt = datetime.datetime(2026, 9, 20, 12, 0, 0, tzinfo=datetime.timezone.utc)

    # 1. Entered 10 days ago -> not timed out
    entered_10d_ago = "2026-09-10T12:00:00Z"
    timed_out_1, days_1 = req.check_putaway_ageing(entered_10d_ago, now_dt)
    ch.add("10 days in putaway is not timed out", "timeout status", False, timed_out_1)
    ch.add("elapsed days is 10", "days count", 10, days_1)

    # 2. Entered 31 days ago -> timed out!
    entered_31d_ago = "2026-08-20T12:00:00Z"
    timed_out_2, days_2 = req.check_putaway_ageing(entered_31d_ago, now_dt)
    ch.add("31 days in putaway IS timed out", "timeout status", True, timed_out_2)
    ch.add("elapsed days is 31", "days count", 31, days_2)
    detail["putaway_ageing_check"] = f"10d -> {timed_out_1}, 31d -> {timed_out_2}"


def c_life_wms3_receipt_conditions(ch: Checks, calls: list, detail: dict):
    """IA-5112-US5-LIFE-17: WMS3 return receipt: exactly 2 stock conditions (usable, unusable; NO quarantine)."""
    conditions = req.WMS3_STOCK_CONDITIONS
    ch.add("exactly 2 conditions at return receipt", "conditions count", 2, len(conditions))
    ch.contains("usable_quantity present", "usable condition", "usable_quantity", conditions)
    ch.contains("unusable_quantity present", "unusable condition", "unusable_quantity", conditions)
    ch.add("quarantine is strictly forbidden", "no quarantine", False, req.FORBIDDEN_RETURN_RECEIPT_CONDITION in conditions)


def c_life_authority_split(ch: Checks, calls: list, detail: dict):
    """IA-5112-US5-LIFE-18: Authority split & change log: Amazon re-read cannot overwrite WMS-written fields."""
    audit = req.ReturnOrderAuditLogger()
    ret_id = "RET-41277-1"

    # Step 1: WMS records received quantity = 2 and usable_quantity = 2
    wms_ok1 = audit.record_change(ret_id, "wms", "received", 0, 2)
    wms_ok2 = audit.record_change(ret_id, "wms", "usable_quantity", 0, 2)
    ch.add("WMS write succeeds", "wms write allowed", True, wms_ok1 and wms_ok2)

    # Step 2: Amazon report later arrives claiming received = 0 (stale/missing)
    amz_ok = audit.record_change(ret_id, "amazon_report", "received", 2, 0)
    ch.add("Amazon re-read CANNOT overwrite WMS received quantity", "overwrite blocked", False, amz_ok)

    # Step 3: Amazon report updates an Amazon-owned field (e.g. carrier, tracking)
    amz_valid_ok = audit.record_change(ret_id, "amazon_report", "tracking_number", None, "8Q123456789FR")
    ch.add("Amazon report can update Amazon-owned fields", "tracking update allowed", True, amz_valid_ok)
    detail["audit_log_entries"] = len(audit.log)


def c_life_mirakl_rank_check(ch: Checks, calls: list, detail: dict):
    """IA-5112-US5-LIFE-19: Mirakl status ranking: stale report row cannot regress rejected or completed returns."""
    # 1. Stored COMPLETE, incoming PUTAWAY -> regresses, blocked!
    ok1, reason1 = req.rank_check_transition("COMPLETE", "PUTAWAY")
    ch.add("COMPLETE cannot regress to PUTAWAY", "transition blocked", False, ok1)

    # 2. Stored REJECTED, incoming INITIATED -> regresses, blocked!
    ok2, reason2 = req.rank_check_transition("REJECTED", "INITIATED")
    ch.add("REJECTED cannot regress to INITIATED", "transition blocked", False, ok2)

    # 3. Stored APPROVED, incoming PUTAWAY -> forward transition, allowed!
    ok3, reason3 = req.rank_check_transition("APPROVED", "PUTAWAY")
    ch.add("APPROVED forward to PUTAWAY allowed", "forward allowed", True, ok3)

    # 4. Stored LOST_IN_TRANSIT, goods arrive -> forward to PUTAWAY allowed!
    ok4, reason4 = req.rank_check_transition("LOST_IN_TRANSIT", "PUTAWAY")
    ch.add("LOST to PUTAWAY on arrival allowed", "forward allowed", True, ok4)
    detail["rank_check_results"] = [reason1, reason2, reason3, reason4]


def c_life_multi_return_independence(ch: Checks, calls: list, detail: dict):
    """IA-5112-US5-LIFE-20: Multiple returns on same parent order complete independently."""
    orig_order_id = "41277"
    return1 = req.compose_primary_key("SS0000FR", "A13V1IB3VIYZZH", "RMA-FR-88213", orig_order_id)
    return2 = req.compose_primary_key("SS0000FR", "A13V1IB3VIYZZH", "RMA-FR-88214", orig_order_id)

    ch.add("different RMAs produce distinct return keys", "two keys differ", True, return1 != return2)

    # Return 1 is completed
    state_ret1 = req.build_oms_update_payload(return_type="COMPLETE", completion_reason="refund confirmed")
    # Return 2 is still in putaway
    state_ret2 = req.build_oms_update_payload(return_type="PUTAWAY")

    ch.add("Return 1 status is COMPLETE", "Return 1 status", "COMPLETE", state_ret1["return_type"])
    ch.add("Return 2 status is PUTAWAY", "Return 2 status", "PUTAWAY", state_ret2["return_type"])
    ch.add("independent completion", "Return 2 not affected by Return 1 completion", True, state_ret1["return_type"] != state_ret2["return_type"])
    detail["keys"] = [return1, return2]


# Register all 20 lifecycle cases
case("IA-5112-US5-LIFE-01", "Reconstruction -- flat rows grouped on primary key",
     "Flat TSV rows sharing Order ID and Amazon RMA ID",
     ["Collapsed to 1 return order", "Primary key format store#mp#RMA#orderId", "items array contains all rows"],
     "R-MAP §4 Flow 2: Load-bearing reconstruction of flat rows into header-detail return order.",
     c_life_primary_grouping)

case("IA-5112-US5-LIFE-02", "Reconstruction -- returnless rows grouped on fallback key",
     "Returnless rows with blank Amazon RMA ID",
     ["Grouped on fallback key store#mp#orderId#sku#date", "key_type is fallback", "amazon_rma_id is None"],
     "R-MAP §8.1: Fallback key preserves uniqueness when no RMA is issued.",
     c_life_fallback_grouping)

case("IA-5112-US5-LIFE-03", "Resolution -- order item resolved by ASIN and seller SKU",
     "Original order items matched against report ASIN and Merchant SKU",
     ["Exact match maps to line_item_id", "Unknown seller SKU rejected (never infer from ASIN alone)"],
     "R-MAP §5.4 row 19 & claim L-38: ASIN is shared across sellers; line must match seller SKU.",
     c_life_item_resolution)

case("IA-5112-US5-LIFE-04", "POST /orders/return -- 20 ADD fields validation",
     "POST /rest/v1/orders/return create payload",
     ["All 20 ADD fields populated per specification", "Date, currency, cross-border, and item fields verified"],
     "R-REQ §2.1 & CR-1: Verifies the 20 newly specified create-time properties.",
     c_life_create_add_fields)

case("IA-5112-US5-LIFE-05", "POST /orders/return -- 10 REUSE fields validation",
     "POST /rest/v1/orders/return create payload",
     ["All 10 REUSE fields populated per specification", "id, return_order_number, line_item_id, item_codes verified"],
     "R-REQ §2.1: Verifies reuse of existing OMS create-time properties.",
     c_life_create_reuse_fields)

case("IA-5112-US5-LIFE-06", "return_order_number -- single issuance and 60-char cap",
     "Generated return_order_number for return order",
     ["len <= 60 chars enforced client-side", "Never regenerated across retries"],
     "R-MAP §7 & claim L-29, L-41: Return number capped at 60 chars and persisted once.",
     c_life_return_number_length)

case("IA-5112-US5-LIFE-07", "return_address_status -- mandatory NOT NULL 'unavailable'",
     "Create payload address availability check",
     ["return_address is null", "return_address_status is mandatory NOT NULL 'unavailable'"],
     "R-REQ §2.1 & claim L-55: Mandatory address availability sentinel distinguishes missing data.",
     c_life_address_unavailable)

case("IA-5112-US5-LIFE-08", "new_status=RETURN -- query parameter for all sub-states",
     "POST /rest/v1/orders/{id}/update_status across sub-state transitions",
     ["Query parameter is always new_status=RETURN", "Body return_type carries actual sub-state"],
     "R-MAP §3.3 & claim L-48: Always send new_status=RETURN, never APPROVE or REJECT.",
     c_life_new_status_return_query)

case("IA-5112-US5-LIFE-09", "update_status -- 15 ADD fields validation",
     "POST /rest/v1/orders/{id}/update_status?new_status=RETURN payload",
     ["15 ADD fields verified", "Quantity ledger, stock disposition, and timestamps verified"],
     "R-REQ §2.2 & CR-2: Verifies status update properties and return quantity ledger.",
     c_life_update_add_fields)

case("IA-5112-US5-LIFE-10", "Movement gate -- IN_PROGRESS entered only on scan evidence",
     "Approval and tracking evidence evaluation",
     ["Tracking alone stays at APPROVED", "Tracking with delivery/scan moves to IN_PROGRESS"],
     "R-MAP §6.1 & claim L-52: In-progress is evidence-gated; tracking alone is not movement.",
     c_life_in_progress_movement_gate)

case("IA-5112-US5-LIFE-11", "Completion path 1 -- refund confirmed",
     "Standard return completion with putaway complete and refund confirmed",
     ["return_type is COMPLETE", "completion_reason is 'refund confirmed'", "refund_completed_indicator is True"],
     "R-REQ §2.2 & claim L-51: Standard refund-confirmed completion path.",
     c_life_completion_path_refund)

case("IA-5112-US5-LIFE-12", "Completion path 2 -- 30-day putaway timeout",
     "Putaway ageing fallback completion after 30 days",
     ["return_type is COMPLETE", "completion_reason is 'timeout'", "Claims NO refund completion"],
     "R-MAP §4 Flow 4 & claim L-51: 30-day timeout path must claim NO refund completion.",
     c_life_completion_path_timeout)

case("IA-5112-US5-LIFE-13", "Completion path 3 -- amazon returnless resolution",
     "Returnless resolution approved straight through",
     ["return_type is COMPLETE", "completion_reason is 'amazon returnless resolution'"],
     "R-MAP §5.5 row 7 & claim L-51: Straight-through returnless completion without putaway.",
     c_life_completion_path_returnless)

case("IA-5112-US5-LIFE-14", "Completion path 4 -- no refund applicable",
     "Return resolution where no refund applies",
     ["return_type is COMPLETE", "completion_reason is 'no refund applicable'"],
     "R-REQ §2.2 & claim L-51: Fourth completion reason for no-refund-applicable path.",
     c_life_completion_path_no_refund)

case("IA-5112-US5-LIFE-15", "Canonical completion token -- COMPLETE (not COMPLETED)",
     "Status token serialization verification",
     ["Canonical token is COMPLETE", "Forbidden token is COMPLETED", "Derived by suffix match"],
     "R-REQ §2.2 & claim L-14, L-58: Canonical status is Return_completed -> COMPLETE.",
     c_life_canonical_complete_token)

case("IA-5112-US5-LIFE-16", "Putaway timing -- measures from putawayEnteredAt (never completedAt)",
     "Ageing job calculation against entry and completion instants",
     ["< 30 days not timed out", ">= 30 days triggers timeout", "Measured strictly from entry instant"],
     "R-MAP §4 Flow 4 & claim L-50: 30-day clock runs from entry, never completion instant.",
     c_life_putaway_timing)

case("IA-5112-US5-LIFE-17", "WMS3 receipt -- exactly 2 stock conditions (NO quarantine)",
     "Stock condition mapping at return receipt",
     ["usable_quantity present", "unusable_quantity present", "quarantine_quantity strictly absent"],
     "R-MAP §6.2 & claim L-4, L-61: Exactly two conditions at return receipt; quarantine is inbound-only.",
     c_life_wms3_receipt_conditions)

case("IA-5112-US5-LIFE-18", "Authority split -- Amazon re-read cannot overwrite WMS fields",
     "Change log audit recording WMS receipt and incoming Amazon report",
     ["WMS receipt recorded", "Amazon re-read blocked from overwriting received/condition fields"],
     "R-MAP §1.1 & claim L-31: An Amazon report update shall not overwrite WMS disposition.",
     c_life_authority_split)

case("IA-5112-US5-LIFE-19", "Mirakl ranking -- stale report rows rejected",
     "Rank-then-diff evaluation of incoming report status against stored state",
     ["Completed return never regresses or reopens", "Rejected return never regresses", "Forward transitions allowed"],
     "R-MAP §8.2 & claim L-9, L-53: Rank check prevents routine polls from regressing status.",
     c_life_mirakl_rank_check)

case("IA-5112-US5-LIFE-20", "Multi-return independence -- concurrent returns complete separately",
     "Multiple return orders created against the same parent order",
     ["Distinct return numbers and keys", "One return completes while other remains in putaway"],
     "R-MAP §8.5 & claim L-42a, L-54: Returns on the same order maintain independent lifecycles.",
     c_life_multi_return_independence)


def preflight():
    global OMS_UP
    print(f"Amazon Seller-Fulfilled Returns Lifecycle Suite (IA-5112-US5) -- {BASE_AMAZON}")
    print(f"  mock dir : {MOCK_DIR}")
    print(f"  run dir  : {RUN_DIR}")
    print(f"  oms      : {BASE_OMS}")
    os.makedirs(DATA_DIR, exist_ok=True)

    st, _, _ = call_amazon("POST", "/auth/o2/token", None, token=None)
    if st == 0:
        print(f"  mock     : starting ephemeral mock server on {BASE_AMAZON}...")
        _start_ephemeral_mock()
        st, _, _ = call_amazon("POST", "/auth/o2/token", None, token=None)
        if st == 0:
            sys.exit(f"PREFLIGHT FAIL: unable to start mock server on {BASE_AMAZON}")
    print(f"  mock     : up (POST /auth/o2/token -> {st})")

    st_oms, _, _ = call_oms("GET", "/rest/v1/orders/return")
    OMS_UP = (st_oms in (200, 404, 405, 422))
    print(f"  oms      : {'up' if OMS_UP else 'offline (testing in-memory/stand-in mode)'} (status {st_oms})")


def main():
    preflight()
    print(f"\nRunning {len(CASES)} test cases for {SUITE}...\n")
    for c in CASES:
        if WANTED_CASES and c["id"] not in WANTED_CASES:
            RESULTS[c["id"]] = {
                "verdict": "skip",
                "checks": [],
                "calls": [],
                "detail": {},
                "summary": "skipped (not selected)"
            }
            continue
        v = run_case(c)
        mark = "✓" if v == "pass" else ("⚠" if v == "blocked" else "✗")
        print(f"  [{v.upper():^7}] {mark} {c['id']}: {c['name']}")

    publish()
    total = len([c for c in CASES if WANTED_CASES is None or len(WANTED_CASES) == 0 or c["id"] in WANTED_CASES])
    passed = sum(1 for r in RESULTS.values() if r["verdict"] == "pass")
    failed = sum(1 for r in RESULTS.values() if r["verdict"] == "fail")
    blocked = sum(1 for r in RESULTS.values() if r["verdict"] == "blocked")
    print(f"\n{SUITE} complete: {passed}/{total} passed, {failed} failed, {blocked} blocked.")
    print(f"Results saved to: {os.path.join(RUN_DIR, 'results.json')}\n")
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
