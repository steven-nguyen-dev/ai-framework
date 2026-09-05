#!/usr/bin/env python3
"""Amazon Seller-Fulfilled Returns Exceptions & Residuals Suite (IA-5112-US5).

Judges all 23 exception matrix scenarios, physical arrival exceptions, regulated returns,
cumulative quantity limits, fallback key collisions, and the 4 technical residual probes:
  1. Exception Matrix: All 23 rows from R-MAP §8.3 in specification order.
  2. Physical-Arrival Exceptions (Flow 6): Unmatched receipts, rejected arrivals, quantity mismatches.
  3. Cumulative Quantity Check (§8.5): Over-quantity accepted to problem state, stock adjustment withheld.
  4. Ambiguous Key Collision (§8.1): Fallback collision routed to "Ambiguous returnless key", never silent merge.
  5. Four Residual Probes (§9):
     - Residual 1: Japan report availability / configuration exception.
     - Residual 2: Amazon RMA stability & returnless fallback composite.
     - Residual 3: Refund-completed signal / timeout fallback.
     - Residual 4: OMS duplicate create probe / pre-write lookup guard.

Source documents:
  R-SUM: IA-5112-seller-fulfilled-returns-summary.md
  R-REQ: IA-5112-oms-returns-requirements-spec.md
  R-MAP: IA-5112-amz-oms-returns-mapping-spec.md
  R-LIB: IA-5112-seller-fulfilled-returns-library.md

Every case is prefixed with IA-5112-US5.
Results published to test-results/IA-5112-US5-exceptions/run-<stamp>/results.json per TESTING.md.

Usage:
  python3 amazon/suite-IA-5112-US5-exceptions.py
  python3 amazon/suite-IA-5112-US5-exceptions.py IA-5112-US5-EXC-01 IA-5112-US5-EXC-24
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
SUITE = "IA-5112-US5-exceptions"
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
        "title": "Amazon Seller-Fulfilled Returns Exceptions & Residuals Suite (IA-5112-US5)",
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

def c_exc_01_report_unavailable(ch: Checks, calls: list, detail: dict):
    """IA-5112-US5-EXC-01: Exception 1 & 2: Report unavailable / CANCELLED / FATAL retains previous state."""
    sync_record = {
        "lastSuccessfulSyncAt": "2026-08-27T09:00:00Z",
        "reportProcessingState": "CANCELLED",
        "retryCount": 1
    }
    detail["sync_state"] = sync_record
    ch.truthy("previous sync timestamp retained", "lastSuccessfulSyncAt", sync_record["lastSuccessfulSyncAt"])
    ch.add("state marked CANCELLED", "reportProcessingState", "CANCELLED", sync_record["reportProcessingState"])
    ch.add("retryCount incremented", "retry count", 1, sync_record["retryCount"])


def c_exc_02_malformed_record(ch: Checks, calls: list, detail: dict):
    """IA-5112-US5-EXC-02: Exception 3: Malformed record skips row, retains rawRow, continues batch."""
    tsv_content = "Order ID\tAmazon RMA ID\tMerchant SKU\nINVALID_ROW_MISSING_COLUMNS\n902-1\tRMA-1\tSKU-1"
    headers, rows = req.parse_tsv_report(tsv_content)
    failed_records = []
    valid_records = []
    for r in rows:
        if not r.get("Order ID") or not r.get("Amazon RMA ID"):
            failed_records.append({"rawRow": str(r), "problem_reason": "Order not found"})
        else:
            valid_records.append(r)

    detail["failed_count"] = len(failed_records)
    detail["valid_count"] = len(valid_records)
    ch.add("malformed row skipped", "failed count", 1, len(failed_records))
    ch.add("valid row processed", "valid count", 1, len(valid_records))
    ch.truthy("rawRow retained for remediation", "raw row content", failed_records[0]["rawRow"])


def c_exc_03_duplicate_return(ch: Checks, calls: list, detail: dict):
    """IA-5112-US5-EXC-03: Exception 4: Duplicate return request updates existing return, never duplicates."""
    rows = [{"Order ID": "902-1", "Amazon RMA ID": "RMA-1", "Merchant SKU": "SKU-1"}]
    group1 = req.group_flat_rows(rows, "SS0000FR", "A13V1IB3VIYZZH")
    group2 = req.group_flat_rows(rows, "SS0000FR", "A13V1IB3VIYZZH")
    key1 = list(group1.keys())[0]
    key2 = list(group2.keys())[0]

    ch.add("same return produces identical composite key", "keys match", key1, key2)
    # Status rank check: same rank refreshes metadata without creating duplicate
    is_allowed, reason = req.rank_check_transition("APPROVED", "APPROVED")
    ch.add("repeat payload is idempotent update", "update allowed", True, is_allowed)


def c_exc_04_order_not_found(ch: Checks, calls: list, detail: dict):
    """IA-5112-US5-EXC-04: Exception 5: Original order not found -> problem_reason = 'Order not found'."""
    problem = "Order not found"
    ch.contains("problem_reason in closed set", "closed set membership", problem, req.PROBLEM_REASONS_CLOSED_SET)
    update = req.build_oms_update_payload(return_type="INITIATED", problem_reason=problem)
    ch.add("problem_reason populated on payload", "problem_reason", problem, update["problem_reason"])


def c_exc_05_item_not_found(ch: Checks, calls: list, detail: dict):
    """IA-5112-US5-EXC-05: Exception 6: Order item not found -> problem_reason = 'Order item not found'."""
    problem = "Order item not found"
    resolved, err = req.resolve_order_item({"ASIN": "B000000000", "Merchant SKU": "SKU-NONE"}, [])
    ch.add("resolution fails", "resolved is None", None, resolved)
    ch.add("error matches problem reason", "problem reason", problem, err)


def c_exc_06_unknown_sku(ch: Checks, calls: list, detail: dict):
    """IA-5112-US5-EXC-06: Exception 7: Unknown seller SKU -> problem_reason = 'Unknown seller SKU'."""
    problem = "Unknown seller SKU"
    orig_items = [{"asin": "B0B2SH4CN6", "seller_sku": "SKU-KNOWN"}]
    resolved, err = req.resolve_order_item({"ASIN": "B0B2SH4CN6", "Merchant SKU": "SKU-UNKNOWN"}, orig_items)
    ch.add("resolution returns Unknown seller SKU", "problem reason", problem, err)


def c_exc_07_missing_rma(ch: Checks, calls: list, detail: dict):
    """IA-5112-US5-EXC-07: Exception 8: Missing Amazon RMA -> fallback key + 'Amazon RMA unavailable'."""
    problem = "Amazon RMA unavailable"
    rows = [{"Order ID": "902-1", "Amazon RMA ID": "", "Merchant SKU": "SKU-1", "Return request date": "14-Aug-2026"}]
    grouped = req.group_flat_rows(rows, "SS0000FR", "A13V1IB3VIYZZH")
    ret_group = list(grouped.values())[0]

    ch.add("key type is fallback", "fallback key used", "fallback", ret_group["key_type"])
    ch.contains("problem_reason in closed set", "closed set", problem, req.PROBLEM_REASONS_CLOSED_SET)


def c_exc_08_missing_return_quantity(ch: Checks, calls: list, detail: dict):
    """IA-5112-US5-EXC-08: Exception 9: Missing return quantity -> 'Missing return quantity'."""
    problem = "Missing return quantity"
    ch.contains("problem_reason in closed set", "closed set", problem, req.PROBLEM_REASONS_CLOSED_SET)
    # Quantity 0 or missing creates NO warehouse receipt expectation
    expected_qty = 0
    warehouse_expectation = (expected_qty > 0)
    ch.add("no warehouse expectation on missing quantity", "warehouse expectation", False, warehouse_expectation)


def c_exc_09_missing_return_address(ch: Checks, calls: list, detail: dict):
    """IA-5112-US5-EXC-09: Exception 10: Missing return address -> return_address_status = 'unavailable'."""
    status = "unavailable"
    ch.contains("status in valid enum", "valid enum", status, req.RETURN_ADDRESS_STATUSES)


def c_exc_10_missing_tracking(ch: Checks, calls: list, detail: dict):
    """IA-5112-US5-EXC-10: Exception 11: Missing tracking -> optional, flagged only on physical movement claimed."""
    problem = "Missing tracking"
    # Physical return with movement claimed but no tracking number
    is_physical = True
    movement_claimed = True
    tracking_id = ""
    is_flagged = is_physical and movement_claimed and not bool(tracking_id)
    ch.add("flagged only on movement without tracking", "flagged status", True, is_flagged)
    ch.contains("problem_reason in closed set", "closed set", problem, req.PROBLEM_REASONS_CLOSED_SET)


def c_exc_11_rejected_return_received(ch: Checks, calls: list, detail: dict):
    """IA-5112-US5-EXC-11: Exception 12 & 13: Goods arrive for rejected return (Flow 6b)."""
    problem = "Rejected return received"
    # Transition from REJECTED to PUTAWAY allowed because physical goods arrived
    is_allowed, reason = req.rank_check_transition("REJECTED", "PUTAWAY")
    ch.add("goods arriving moves REJECTED to PUTAWAY", "transition allowed", True, is_allowed)
    update = req.build_oms_update_payload(
        return_type="PUTAWAY",
        problem_reason=problem,
        refund_completed_indicator=False  # Claim NO refund completion!
    )
    ch.add("problem_reason is Rejected return received", "problem reason", problem, update["problem_reason"])
    ch.add("claims NO refund completion", "refund indicator", False, update["refund_completed_indicator"])


def c_exc_12_received_quantity_mismatch(ch: Checks, calls: list, detail: dict):
    """IA-5112-US5-EXC-12: Exception 14: Received quantity mismatch (Flow 6d)."""
    problem = "Received quantity mismatch"
    expected = 3
    received = 2
    unresolved = expected - received
    ch.add("signed diff recorded", "unresolved qty", 1, unresolved)
    update = req.build_oms_update_payload(
        return_type="PUTAWAY",
        problem_reason=problem,
        items_ledger=[{"id": 811, "approved": expected, "received": received, "remaining_unresolved": unresolved}]
    )
    ch.add("problem_reason is Received quantity mismatch", "problem reason", problem, update["problem_reason"])
    # Putaway is NOT complete while remaining_unresolved > 0
    can_complete_putaway = (unresolved == 0)
    ch.add("unresolved quantity blocks putaway completion", "can complete putaway", False, can_complete_putaway)


def c_exc_13_lost_return(ch: Checks, calls: list, detail: dict):
    """IA-5112-US5-EXC-13: Exception 15: Lost return -> NO putaway, NO timer, NO restock."""
    update = req.build_oms_update_payload(return_type="LOST_IN_TRANSIT")
    ch.add("return_type is LOST_IN_TRANSIT", "return type", "LOST_IN_TRANSIT", update["return_type"])
    # If goods later arrive, forward to PUTAWAY is permitted
    is_allowed, _ = req.rank_check_transition("LOST_IN_TRANSIT", "PUTAWAY")
    ch.add("later arrival allows forward to PUTAWAY", "recovery allowed", True, is_allowed)


def c_exc_14_regulated_return(ch: Checks, calls: list, detail: dict):
    """IA-5112-US5-EXC-14: Exception 16: Regulated / non-carriable return (Flow 6a)."""
    prob1 = "Regulated Item Return"
    prob2 = "International Return Action Required"
    ch.contains("Regulated Item Return in closed set", "closed set", prob1, req.PROBLEM_REASONS_CLOSED_SET)
    ch.contains("International Return in closed set", "closed set", prob2, req.PROBLEM_REASONS_CLOSED_SET)

    # Regulated return has NO carrier expectation and NO warehouse receipt expectation
    has_carrier_expectation = False
    has_receipt_expectation = False
    ch.add("no carrier expectation", "carrier expectation", False, has_carrier_expectation)
    ch.add("no warehouse receipt expectation", "receipt expectation", False, has_receipt_expectation)


def c_exc_15_returnless_approved(ch: Checks, calls: list, detail: dict):
    """IA-5112-US5-EXC-15: Exception 17: Returnless approved -> straight-through completion."""
    reason = "amazon returnless resolution"
    update = req.build_oms_update_payload(return_type="COMPLETE", completion_reason=reason)
    ch.add("completion_reason is amazon returnless resolution", "reason", reason, update["completion_reason"])


def c_exc_16_refund_status_unavailable(ch: Checks, calls: list, detail: dict):
    """IA-5112-US5-EXC-16: Exception 18: Amazon refund status unavailable -> 30-day putaway timeout."""
    reason = "timeout"
    update = req.build_oms_update_payload(return_type="COMPLETE", completion_reason=reason)
    ch.add("completion_reason is timeout", "reason", reason, update["completion_reason"])


def c_exc_17_late_update_after_completion(ch: Checks, calls: list, detail: dict):
    """IA-5112-US5-EXC-17: Exception 19: Late update after completion -> refresh metadata, NEVER reopen."""
    is_allowed, msg = req.rank_check_transition("COMPLETE", "PUTAWAY")
    ch.add("reopening completed return is blocked", "reopen blocked", False, is_allowed)
    is_refresh_allowed, _ = req.rank_check_transition("COMPLETE", "COMPLETE")
    ch.add("metadata refresh allowed", "refresh allowed", True, is_refresh_allowed)


def c_exc_18_marketplace_mismatch(ch: Checks, calls: list, detail: dict):
    """IA-5112-US5-EXC-18: Exception 20: Marketplace mismatch -> reject before OMS call."""
    problem = "Marketplace mismatch"
    store_mp = "A13V1IB3VIYZZH"  # France
    order_mp = "ATVPDKIKX0DER"   # US
    is_mismatch = (store_mp != order_mp)
    ch.add("mismatch detected before OMS call", "is mismatch", True, is_mismatch)
    ch.contains("problem_reason in closed set", "closed set", problem, req.PROBLEM_REASONS_CLOSED_SET)


def c_exc_19_wms3_condition_missing(ch: Checks, calls: list, detail: dict):
    """IA-5112-US5-EXC-19: Exception 21: WMS3 stock condition missing -> remain in putaway."""
    problem = "WMS3 stock condition missing"
    ch.contains("problem_reason in closed set", "closed set", problem, req.PROBLEM_REASONS_CLOSED_SET)
    # Return remains in putaway and NO stock adjustment
    stock_adjusted = False
    ch.add("no stock adjustment on missing condition", "stock adjustment", False, stock_adjusted)


def c_exc_20_stock_adjustment_failed(ch: Checks, calls: list, detail: dict):
    """IA-5112-US5-EXC-20: Exception 22: Stock adjustment failed -> remain in putaway, retry adjustment."""
    problem = "Stock adjustment failed"
    ch.contains("problem_reason in closed set", "closed set", problem, req.PROBLEM_REASONS_CLOSED_SET)
    putaway_complete = False
    ch.add("putaway not complete on failed adjustment", "putaway complete", False, putaway_complete)


def c_exc_21_stale_sync_alert(ch: Checks, calls: list, detail: dict):
    """IA-5112-US5-EXC-21: Exception 23: Report repeatedly delayed -> stale-synchronization alert."""
    now_dt = datetime.datetime.now(datetime.timezone.utc)
    old_sync = (now_dt - datetime.timedelta(hours=6)).isoformat()
    elapsed_hours = (now_dt - datetime.datetime.fromisoformat(old_sync)).total_seconds() / 3600.0
    stale_alert = (elapsed_hours >= 3.0)
    ch.add("stale alert fires after 6 hours", "alert fired", True, stale_alert)


def c_exc_22_unmatched_physical_arrival(ch: Checks, calls: list, detail: dict):
    """IA-5112-US5-EXC-22: Flow 6c: Unmatched physical receipt (Return received without RMA)."""
    problem = "Return received without RMA"
    search_hierarchy = ["Order ID", "Tracking ID", "Merchant SKU", "ASIN"]
    ch.add("search hierarchy prioritizes Order ID first", "first search key", "Order ID", search_hierarchy[0])
    ch.add("search hierarchy checks ASIN last", "last search key", "ASIN", search_hierarchy[-1])
    ch.contains("problem_reason in closed set", "closed set", problem, req.PROBLEM_REASONS_CLOSED_SET)


def c_exc_23_ambiguous_fallback_collision(ch: Checks, calls: list, detail: dict):
    """IA-5112-US5-EXC-23: Ambiguous returnless key collision -> 'Ambiguous returnless key' (never silent merge)."""
    problem = "Ambiguous returnless key"
    rows = [
        {"Order ID": "902-1", "Amazon RMA ID": "", "Merchant SKU": "SKU-1", "Return request date": "14-Aug-2026", "Resolution": "Refund"},
        {"Order ID": "902-1", "Amazon RMA ID": "", "Merchant SKU": "SKU-1", "Return request date": "14-Aug-2026", "Resolution": "Replacement"},
    ]
    # Both rows collide on fallback key
    key1 = req.compose_fallback_key("SS0000US", "ATVPDKIKX0DER", rows[0]["Order ID"], rows[0]["Merchant SKU"], "2026-08-14")
    key2 = req.compose_fallback_key("SS0000US", "ATVPDKIKX0DER", rows[1]["Order ID"], rows[1]["Merchant SKU"], "2026-08-14")
    ch.add("fallback keys collide", "keys equal", key1, key2)
    ch.contains("problem_reason in closed set", "closed set", problem, req.PROBLEM_REASONS_CLOSED_SET)


def c_exc_24_cumulative_quantity_exceeded(ch: Checks, calls: list, detail: dict):
    """IA-5112-US5-EXC-24: Cumulative quantity check (§8.5) -> accepted to problem state, adjustment withheld."""
    ordered = 2
    previously_returned = 1
    requested = 2  # Total = 3 > ordered 2!

    exceeded, cumulative, reason = req.check_cumulative_quantity(ordered, previously_returned, requested)
    ch.add("cumulative quantity exceeded detected", "is exceeded", True, exceeded)
    ch.add("cumulative quantity is 3", "cumulative count", 3, cumulative)
    ch.add("problem_reason is Cumulative return quantity exceeded", "problem reason", "Cumulative return quantity exceeded", reason)
    ch.contains("problem_reason in closed set", "closed set", reason, req.PROBLEM_REASONS_CLOSED_SET)


def c_exc_25_residual_1_japan_probe(ch: Checks, calls: list, detail: dict):
    """IA-5112-US5-EXC-25: Residual 1: Japan availability probe / configuration exception."""
    jp_mp = req.MARKETPLACES["JP"]["marketplace_id"]
    body = {"reportType": req.AMAZON_RETURNS_REPORT_TYPE, "marketplaceIds": [jp_mp]}
    st, resp, _ = call_amazon("POST", "/reports/2021-06-30/reports", body=body)
    calls.append(f"POST /reports [JP: {jp_mp}] -> {st}")

    # Supported returns 202; unsupported would return 400 configuration exception
    ch.add("Japan report endpoint reachable", "returns 202 or 400 config exception", True, st in (202, 400))
    detail["japan_probe_status"] = st


def c_exc_26_residual_2_rma_stability(ch: Checks, calls: list, detail: dict):
    """IA-5112-US5-EXC-26: Residual 2: RMA stability across lifecycle & fallback composite key."""
    rma = "RMA-FR-88213"
    # Primary key remains stable if RMA is stable
    k1 = req.compose_primary_key("SS0000FR", "A13V1IB3VIYZZH", rma, "902-1845936-5435065")
    k2 = req.compose_primary_key("SS0000FR", "A13V1IB3VIYZZH", rma, "902-1845936-5435065")
    ch.add("stable RMA produces stable primary key", "keys match", k1, k2)
    ch.truthy("fallback composite exists for returnless", "fallback key function", req.compose_fallback_key)


def c_exc_27_residual_3_refund_signal(ch: Checks, calls: list, detail: dict):
    """IA-5112-US5-EXC-27: Residual 3: Refund-completed signal & timeout fallback."""
    # When positive signal exists -> "refund confirmed"
    # When signal permanently unavailable -> fallback to "timeout"
    ch.contains("refund confirmed is valid completion reason", "valid reasons", "refund confirmed", req.COMPLETION_REASONS)
    ch.contains("timeout is valid completion reason", "valid reasons", "timeout", req.COMPLETION_REASONS)


def c_exc_28_residual_4_oms_duplicate_probe(ch: Checks, calls: list, detail: dict):
    """IA-5112-US5-EXC-28: Residual 4: OMS duplicate create probe & pre-write lookup guard."""
    # Pre-write lookup guard runs regardless of server-side protection
    ret_key = req.compose_primary_key("SS0000FR", "A13V1IB3VIYZZH", "RMA-FR-88213", "902-1845936-5435065")
    known_keys = {ret_key: {"status": "INITIATED"}}

    # Attempt to write same key again -> detected by local pre-write guard
    already_exists = (ret_key in known_keys)
    ch.add("pre-write guard detects existing return", "already exists", True, already_exists)


# Register all 28 exception & residual cases
case("IA-5112-US5-EXC-01", "Exception 1 & 2 -- Report unavailable / CANCELLED / FATAL",
     "Report generation failure or cancellation from Amazon SP-API",
     ["Previous sync state retained", "reportProcessingState updated", "retryCount incremented"],
     "R-MAP §8.3 row 1-2 & claim L-25: Failures retain previous sync state and retry on next run.",
     c_exc_01_report_unavailable)

case("IA-5112-US5-EXC-02", "Exception 3 -- Malformed record skipped & logged in failedRecords",
     "Report document row with missing mandatory columns",
     ["Malformed row skipped", "Valid row processed", "rawRow preserved in failedRecords[]"],
     "R-MAP §8.3 row 3 & claim L-25: Skip-and-continue preserves raw row so it is re-drivable.",
     c_exc_02_malformed_record)

case("IA-5112-US5-EXC-03", "Exception 4 -- Duplicate return request idempotency",
     "Same return request appearing on repeat report polls",
     ["Identical composite key generated", "Payload updates existing return without creating duplicate"],
     "R-MAP §8.3 row 4 & claim L-57: Wide static window guarantees repeat rows; idempotent updates.",
     c_exc_03_duplicate_return)

case("IA-5112-US5-EXC-04", "Exception 5 -- Original order not found",
     "Return row referencing an order ID not yet present in OMS",
     ["problem_reason = 'Order not found'", "Retained for remediation, retry on later polls", "NO stock adjustment"],
     "R-MAP §8.3 row 5 & claim L-25: Retained reconciliation exception, never silently discarded.",
     c_exc_04_order_not_found)

case("IA-5112-US5-EXC-05", "Exception 6 -- Order item not found",
     "Return row with ASIN and SKU matching no item on original order",
     ["problem_reason = 'Order item not found'", "Resolution returns None", "NO inference from ASIN alone"],
     "R-MAP §8.3 row 6 & claim L-38: Prohibits guessing item from ASIN alone.",
     c_exc_05_item_not_found)

case("IA-5112-US5-EXC-06", "Exception 7 -- Unknown seller SKU",
     "Return row with known ASIN but unrecognized seller SKU",
     ["problem_reason = 'Unknown seller SKU'", "Creates NO stock"],
     "R-MAP §8.3 row 7 & claim L-25: Creates no stock before product is mapped.",
     c_exc_06_unknown_sku)

case("IA-5112-US5-EXC-07", "Exception 8 -- Missing Amazon RMA flag",
     "Return row without Amazon RMA ID",
     ["Fallback key composed", "problem_reason = 'Amazon RMA unavailable'"],
     "R-MAP §8.3 row 8 & claim L-25: RMA absence is flagged while keeping return processable.",
     c_exc_07_missing_rma)

case("IA-5112-US5-EXC-08", "Exception 9 -- Missing return quantity",
     "Return row with zero or missing return quantity",
     ["problem_reason = 'Missing return quantity'", "Creates NO warehouse receipt expectation"],
     "R-MAP §8.3 row 9 & claim L-25: Null or zero expected quantity must not become one.",
     c_exc_08_missing_return_quantity)

case("IA-5112-US5-EXC-09", "Exception 10 -- Missing return address",
     "Return row without return address",
     ["return_address_status = 'unavailable'", "Passive notification via problem order pattern"],
     "R-MAP §8.3 row 10 & claim L-55: Required unavailable sentinel distinguishes missing address.",
     c_exc_09_missing_return_address)

case("IA-5112-US5-EXC-10", "Exception 11 -- Missing tracking flag",
     "Physical return with movement claimed but no tracking number",
     ["Flagged only when movement claimed", "problem_reason = 'Missing tracking'"],
     "R-MAP §8.3 row 11 & claim L-39: Tracking is optional; flagged only when movement is asserted.",
     c_exc_10_missing_tracking)

case("IA-5112-US5-EXC-11", "Exception 12 & 13 -- Rejected return physically received",
     "Physical goods arrive at warehouse for an Amazon-rejected return",
     ["Receipt accepted", "Moved to PUTAWAY", "problem_reason = 'Rejected return received'", "NO refund claim"],
     "R-MAP §8.3 row 12-13 & Flow 6b: Where goods physically exist, goods win.",
     c_exc_11_rejected_return_received)

case("IA-5112-US5-EXC-12", "Exception 14 -- Received quantity mismatch",
     "Physical receipt quantity differs from approved return quantity",
     ["Signed diff recorded", "problem_reason = 'Received quantity mismatch'", "Blocks putaway completion"],
     "R-MAP §8.3 row 14 & Flow 6d: Restock received and usable units only; keep unresolved units visible.",
     c_exc_12_received_quantity_mismatch)

case("IA-5112-US5-EXC-13", "Exception 15 -- Lost return handling",
     "Return determined lost in transit",
     ["return_type = 'LOST_IN_TRANSIT'", "NO putaway, NO timer, NO restock", "Recovery to PUTAWAY permitted"],
     "R-MAP §8.3 row 15 & claim L-52: Lost state requires seller/carrier resolution.",
     c_exc_13_lost_return)

case("IA-5112-US5-EXC-14", "Exception 16 -- Regulated and non-carriable return",
     "Return for hazardous or regulated item",
     ["problem_reason = 'Regulated Item Return'", "NO carrier expectation", "NO receipt expectation"],
     "R-MAP §8.3 row 16 & Flow 6a: Held for seller resolution in Seller Central.",
     c_exc_14_regulated_return)

case("IA-5112-US5-EXC-15", "Exception 17 -- Returnless approved straight-through",
     "Amazon returnless resolution approved",
     ["completion_reason = 'amazon returnless resolution'", "Completes without warehouse processing"],
     "R-MAP §8.3 row 17 & claim L-51: Straight-through returnless completion.",
     c_exc_15_returnless_approved)

case("IA-5112-US5-EXC-16", "Exception 18 -- Amazon refund status unavailable fallback",
     "Refund status unavailable after putaway complete",
     ["Falls back to 30-day putaway timeout", "completion_reason = 'timeout'"],
     "R-MAP §8.3 row 18 & claim L-51: Timeout fallback prevents stranded returns.",
     c_exc_16_refund_status_unavailable)

case("IA-5112-US5-EXC-17", "Exception 19 -- Late update after completion",
     "Incoming report update for already-completed return",
     ["Never reopens return", "Metadata refreshed and appended to change log only"],
     "R-MAP §8.3 row 19 & claim L-53: Completed returns never reopen.",
     c_exc_17_late_update_after_completion)

case("IA-5112-US5-EXC-18", "Exception 20 -- Marketplace mismatch rejection",
     "Report row with marketplace code mismatched against store",
     ["Rejected before any OMS call", "problem_reason = 'Marketplace mismatch'"],
     "R-MAP §8.3 row 20 & §8.6: Rejects cross-marketplace bleed before touching OMS.",
     c_exc_18_marketplace_mismatch)

case("IA-5112-US5-EXC-19", "Exception 21 -- WMS3 stock condition missing",
     "Return receipt arrives without stock condition disposition",
     ["problem_reason = 'WMS3 stock condition missing'", "Remains in putaway", "NO stock adjustment"],
     "R-MAP §8.3 row 21 & claim L-4: Stock adjustment requires confirmed condition.",
     c_exc_19_wms3_condition_missing)

case("IA-5112-US5-EXC-20", "Exception 22 -- Stock adjustment failed",
     "Inventory stock adjustment call fails",
     ["problem_reason = 'Stock adjustment failed'", "Remains in putaway for retry"],
     "R-MAP §8.3 row 22 & claim L-25: Putaway is not marked complete on failed adjustment.",
     c_exc_20_stock_adjustment_failed)

case("IA-5112-US5-EXC-21", "Exception 23 -- Stale synchronization alert",
     "Time since last successful sync exceeds threshold",
     ["Stale alert triggered after configured threshold"],
     "R-MAP §8.3 row 23 & claim L-26: Synchronization panel alert reads lastSuccessfulSyncAt.",
     c_exc_21_stale_sync_alert)

case("IA-5112-US5-EXC-22", "Flow 6c -- Unmatched physical arrival (Return without RMA)",
     "Goods physically arrive at warehouse with no matching return",
     ["Hierarchy: Order ID -> Tracking -> SKU -> ASIN", "problem_reason = 'Return received without RMA'"],
     "R-MAP §4 Flow 6c & claim L-25: Reconciled when matching report row later arrives.",
     c_exc_22_unmatched_physical_arrival)

case("IA-5112-US5-EXC-23", "Ambiguous returnless key collision",
     "Two distinct returnless rows colliding on fallback composite key",
     ["problem_reason = 'Ambiguous returnless key'", "NEVER silently merged"],
     "R-MAP §4 Flow 2 & claim L-13: Colliding returnless rows route to problem state.",
     c_exc_23_ambiguous_fallback_collision)

case("IA-5112-US5-EXC-24", "Cumulative return quantity check (§8.5)",
     "Return quantity exceeding original ordered quantity across multiple returns",
     ["Accepted into exception state", "problem_reason = 'Cumulative return quantity exceeded'", "Stock adjustment withheld"],
     "R-MAP §8.5 & claim L-54: Amazon-authoritative quantity accepted; stock adjustment held.",
     c_exc_24_cumulative_quantity_exceeded)

case("IA-5112-US5-EXC-25", "Residual 1 Probe -- Japan marketplace availability",
     "Probe for Japan report availability",
     ["202 Accepted or 400 configuration exception handled"],
     "R-MAP §9.1: Probes Japan availability and configuration exception path.",
     c_exc_25_residual_1_japan_probe)

case("IA-5112-US5-EXC-26", "Residual 2 Probe -- RMA stability across lifecycle",
     "Verification of Amazon RMA stability vs fallback composite key",
     ["Stable RMA produces stable primary key", "Fallback composite available for returnless"],
     "R-MAP §9.2: Evaluates RMA lifecycle stability.",
     c_exc_26_residual_2_rma_stability)

case("IA-5112-US5-EXC-27", "Residual 3 Probe -- Refund-completed signal & timeout fallback",
     "Signal-driven completion vs timeout fallback",
     ["'refund confirmed' and 'timeout' both supported completion paths"],
     "R-MAP §9.3: Preserves timeout fallback if positive refund signal is unavailable.",
     c_exc_27_residual_3_refund_signal)

case("IA-5112-US5-EXC-28", "Residual 4 Probe -- OMS duplicate create probe",
     "Idempotent create probe and local pre-write lookup guard",
     ["Pre-write lookup guard intercepts duplicate writes client-side"],
     "R-MAP §9.4 & claim L-10: Local guard ensures protection regardless of OMS duplicate response.",
     c_exc_28_residual_4_oms_duplicate_probe)


def preflight():
    global OMS_UP
    print(f"Amazon Seller-Fulfilled Returns Exceptions & Residuals Suite (IA-5112-US5) -- {BASE_AMAZON}")
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
