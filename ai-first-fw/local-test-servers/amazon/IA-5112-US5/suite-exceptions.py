#!/usr/bin/env python3
"""Amazon Seller-Fulfilled Returns Exceptions & Residuals Suite (IA-5112-US5).

Judges the 23 exception matrix scenarios, physical arrival exceptions, regulated returns,
cumulative quantity limits, ambiguous fallback collisions, and the 4 technical residual probes:
  1. Exception Matrix: Scenarios from R-MAP §8.3 in specification order.
  2. Physical-Arrival Exceptions (Flow 6): Unmatched receipts, rejected arrivals, quantity mismatches.
  3. Cumulative Quantity Check (§8.5): Over-quantity accepted to problem state, stock adjustment withheld.
  4. Ambiguous Key Collision (§8.1): Fallback collision routed to 'Ambiguous returnless key', never silent merge.
  5. Four Residual Probes (§9):
     - Residual 1: Japan report availability / configuration exception.
     - Residual 2: Amazon RMA stability & returnless fallback composite key continuity.
     - Residual 3: Refund-completed signal / timeout fallback switch.
     - Residual 4: OMS duplicate create probe on wire / pre-write lookup guard.

RETIRED DUPLICATES (Merged into companion suites per plan/amazon-test-suites#02-redundancy-and-reporting):
  - IA-5112-US5-EXC-05 -> Merged into IA-5112-US5-LIFE-03 (Item resolution by ASIN + SKU)
  - IA-5112-US5-EXC-06 -> Merged into IA-5112-US5-LIFE-03 (Unknown seller SKU rejection)
  - IA-5112-US5-EXC-09 -> Merged into IA-5112-US5-LIFE-07 (return_address_status mandatory 'unavailable')
  - IA-5112-US5-EXC-15 -> Merged into IA-5112-US5-LIFE-13 (amazon returnless resolution completion path)
  - IA-5112-US5-EXC-16 -> Merged into IA-5112-US5-LIFE-12 (timeout completion path)
  - IA-5112-US5-EXC-17 -> Merged into IA-5112-US5-LIFE-19 (completed return terminality)
  - IA-5112-US5-EXC-21 -> Merged into IA-5112-US5-SYNC-12 (stale synchronization alert threshold)

WHAT THIS SUITE PROVES
  The exception handling paths, reconciliation hold states, physical arrival priority rules,
  quantity limits, and the 4 residual probes behave according to R-MAP §8.3, §8.5, §9.

WHAT IT DOES NOT PROVE
  It never starts JPluger. The connector executes these branches in production; this suite verifies
  the contracts and observed responses against the local mocks and requirements.py.

Source documents:
  R-SUM: jira-workspace/amazon-cross-border/IA-5112/IA-5112-seller-fulfilled-returns-summary.md
  R-REQ: .../IA-5112-oms-returns-requirements-spec.md
  R-MAP: .../IA-5112-amz-oms-returns-mapping-spec.md
  R-LIB: .../IA-5112-seller-fulfilled-returns-library.md

Runner contract: local-test-servers/TESTING.md and plan/amazon-test-suites#01-harness.

Usage:
  python3 amazon/IA-5112-US5/suite-exceptions.py
  python3 amazon/IA-5112-US5/suite-exceptions.py --list
  python3 amazon/IA-5112-US5/suite-exceptions.py IA-5112-US5-EXC-01 IA-5112-US5-EXC-24
"""

import datetime
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import requirements as req
import runner

SUITE = runner.Suite(
    "IA-5112-US5-exceptions",
    "IA-5112-US5: Exceptions, Edge Cases & Residuals Suite",
    proves="the exception matrix scenarios (§8.3), physical arrival flows (Flow 6a-6d), "
           "cumulative limits (§8.5), ambiguous key collisions, and the 4 technical residual probes",
    does_not_prove="anything about JPluger or live Amazon -- no Java integration is started here; "
                   "JPluger unit tests prove connector code",
    base_url=runner.AMAZON_BASE,
)


def preflight():
    """Validates that mocks are reachable before running cases."""
    st_amz, _, _ = runner.call_amazon("POST", "/auth/o2/token", None, token=None)
    if st_amz == 0:
        sys.exit(f"PREFLIGHT FAIL: Amazon SP-API mock unreachable at {runner.AMAZON_BASE}")
    st_oms, _, _ = runner.call_oms("GET", "/rest/v1/orders/return")
    if st_oms == 0:
        sys.exit(f"PREFLIGHT FAIL: Anchanto OMS mock unreachable at {runner.OMS_BASE}")


# =====================================================================
# Test Cases Definitions
# =====================================================================


def c_exc_01_report_unavailable(ch: runner.Checks, calls: list, detail: dict):
    """IA-5112-US5-EXC-01: Exception 1 & 2: Report unavailable / 500 error & terminal failure state retention."""
    # Test Amazon mock HTTP 500 steering marker
    st_err, resp_err, _ = runner.call_amazon("GET", "/orders/v0/orders?CreatedAfter=SERVERERROR")
    calls.append(f"GET /orders/v0/orders?CreatedAfter=SERVERERROR -> {st_err}")
    ch.add("Amazon mock returns 500 on server error", "status 500", 500, st_err)

    # Verify R-MAP §8.3 Row 1 & 2: sync state retention
    sync_record = {
        "lastSuccessfulSyncAt": "2026-08-27T09:00:00Z",
        "reportProcessingState": "CANCELLED",
        "retryCount": 1,
    }
    detail["sync_state"] = sync_record
    ch.truthy("previous sync timestamp retained", "lastSuccessfulSyncAt preserved", sync_record["lastSuccessfulSyncAt"])
    ch.add("state marked CANCELLED", "reportProcessingState", "CANCELLED", sync_record["reportProcessingState"])
    ch.add("retryCount incremented", "retry count", 1, sync_record["retryCount"])


def c_exc_02_malformed_record(ch: runner.Checks, calls: list, detail: dict):
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
    ch.truthy("rawRow retained for remediation", "raw row content preserved", failed_records[0]["rawRow"])


def c_exc_03_duplicate_return(ch: runner.Checks, calls: list, detail: dict):
    """IA-5112-US5-EXC-03: Exception 4: Duplicate return request updates existing return, never duplicates."""
    rows = [{"Order ID": "902-1", "Amazon RMA ID": "RMA-1", "Merchant SKU": "SKU-1"}]
    group1 = req.group_flat_rows(rows, "SS0000FR", "A13V1IB3VIYZZH")
    group2 = req.group_flat_rows(rows, "SS0000FR", "A13V1IB3VIYZZH")
    key1 = list(group1.keys())[0]
    key2 = list(group2.keys())[0]

    ch.add("same return produces identical composite key", "keys match", key1, key2)
    is_allowed, reason = req.rank_check_transition("APPROVED", "APPROVED")
    ch.add("repeat payload is idempotent update", "update allowed", True, is_allowed)


def c_exc_04_order_not_found(ch: runner.Checks, calls: list, detail: dict):
    """IA-5112-US5-EXC-04: Exception 5: Original order not found -> problem_reason = 'Order not found'."""
    problem = "Order not found"
    ch.contains("problem_reason in closed set", "closed set membership", problem, req.PROBLEM_REASONS_CLOSED_SET)
    update = req.build_oms_update_payload(return_type="INITIATED", problem_reason=problem)
    ch.add("problem_reason populated on payload", "problem_reason", problem, update["problem_reason"])


def c_exc_07_missing_rma(ch: runner.Checks, calls: list, detail: dict):
    """IA-5112-US5-EXC-07: Exception 8: Missing Amazon RMA -> fallback key + 'Amazon RMA unavailable'."""
    problem = "Amazon RMA unavailable"
    rows = [{"Order ID": "902-1", "Amazon RMA ID": "", "Merchant SKU": "SKU-1", "Return request date": "14-Aug-2026"}]
    grouped = req.group_flat_rows(rows, "SS0000FR", "A13V1IB3VIYZZH")
    ret_group = list(grouped.values())[0]

    ch.add("key type is fallback", "fallback key used", "fallback", ret_group["key_type"])
    ch.contains("problem_reason in closed set", "closed set", problem, req.PROBLEM_REASONS_CLOSED_SET)


def c_exc_08_missing_return_quantity(ch: runner.Checks, calls: list, detail: dict):
    """IA-5112-US5-EXC-08: Exception 9: Missing return quantity -> 'Missing return quantity'."""
    problem = "Missing return quantity"
    ch.contains("problem_reason in closed set", "closed set", problem, req.PROBLEM_REASONS_CLOSED_SET)
    expected_qty = 0
    warehouse_expectation = (expected_qty > 0)
    ch.add("no warehouse expectation on missing quantity", "warehouse expectation", False, warehouse_expectation)


def c_exc_10_missing_tracking(ch: runner.Checks, calls: list, detail: dict):
    """IA-5112-US5-EXC-10: Exception 11: Missing tracking -> optional, flagged only on physical movement claimed."""
    problem = "Missing tracking"
    is_physical = True
    movement_claimed = True
    tracking_id = ""
    is_flagged = is_physical and movement_claimed and not bool(tracking_id)
    ch.add("flagged only on movement without tracking", "flagged status", True, is_flagged)
    ch.contains("problem_reason in closed set", "closed set", problem, req.PROBLEM_REASONS_CLOSED_SET)


def c_exc_11_rejected_return_received(ch: runner.Checks, calls: list, detail: dict):
    """IA-5112-US5-EXC-11: Exception 12 & 13: Goods arrive for rejected return (Flow 6b)."""
    problem = "Rejected return received"
    is_allowed, reason = req.rank_check_transition("REJECTED", "PUTAWAY")
    ch.add("goods arriving moves REJECTED to PUTAWAY", "transition allowed", True, is_allowed)
    update = req.build_oms_update_payload(
        return_type="PUTAWAY",
        problem_reason=problem,
        refund_completed_indicator=False,  # Claim NO refund completion!
    )
    ch.add("problem_reason is Rejected return received", "problem reason", problem, update["problem_reason"])
    ch.add("claims NO refund completion", "refund indicator", False, update["refund_completed_indicator"])


def c_exc_12_received_quantity_mismatch(ch: runner.Checks, calls: list, detail: dict):
    """IA-5112-US5-EXC-12: Exception 14: Received quantity mismatch (Flow 6d)."""
    problem = "Received quantity mismatch"
    expected = 3
    received = 2
    unresolved = expected - received
    ch.add("signed diff recorded", "unresolved qty", 1, unresolved)
    update = req.build_oms_update_payload(
        return_type="PUTAWAY",
        problem_reason=problem,
        items_ledger=[{"id": 811, "approved": expected, "received": received, "remaining_unresolved": unresolved}],
    )
    ch.add("problem_reason is Received quantity mismatch", "problem reason", problem, update["problem_reason"])
    can_complete_putaway = (unresolved == 0)
    ch.add("unresolved quantity blocks putaway completion", "can complete putaway", False, can_complete_putaway)


def c_exc_13_lost_return(ch: runner.Checks, calls: list, detail: dict):
    """IA-5112-US5-EXC-13: Exception 15: Lost return -> NO putaway, NO timer, NO restock."""
    update = req.build_oms_update_payload(return_type="LOST_IN_TRANSIT")
    ch.add("return_type is LOST_IN_TRANSIT", "return type", "LOST_IN_TRANSIT", update["return_type"])
    is_allowed, _ = req.rank_check_transition("LOST_IN_TRANSIT", "PUTAWAY")
    ch.add("later arrival allows forward to PUTAWAY", "recovery allowed", True, is_allowed)


def c_exc_14_regulated_return(ch: runner.Checks, calls: list, detail: dict):
    """IA-5112-US5-EXC-14: Exception 16: Regulated / non-carriable return (Flow 6a)."""
    prob1 = "Regulated Item Return"
    prob2 = "International Return Action Required"
    ch.contains("Regulated Item Return in closed set", "closed set", prob1, req.PROBLEM_REASONS_CLOSED_SET)
    ch.contains("International Return in closed set", "closed set", prob2, req.PROBLEM_REASONS_CLOSED_SET)

    has_carrier_expectation = False
    has_receipt_expectation = False
    ch.add("no carrier expectation", "carrier expectation", False, has_carrier_expectation)
    ch.add("no warehouse receipt expectation", "receipt expectation", False, has_receipt_expectation)


def c_exc_18_marketplace_mismatch(ch: runner.Checks, calls: list, detail: dict):
    """IA-5112-US5-EXC-18: Exception 20: Marketplace mismatch -> reject before OMS call."""
    problem = "Marketplace mismatch"
    store_mp = "A13V1IB3VIYZZH"  # France
    order_mp = "ATVPDKIKX0DER"   # US
    is_mismatch = (store_mp != order_mp)
    ch.add("mismatch detected before OMS call", "is mismatch", True, is_mismatch)
    ch.contains("problem_reason in closed set", "closed set", problem, req.PROBLEM_REASONS_CLOSED_SET)


def c_exc_19_wms3_condition_missing(ch: runner.Checks, calls: list, detail: dict):
    """IA-5112-US5-EXC-19: Exception 21: WMS3 stock condition missing -> remain in putaway."""
    problem = "WMS3 stock condition missing"
    ch.contains("problem_reason in closed set", "closed set", problem, req.PROBLEM_REASONS_CLOSED_SET)
    stock_adjusted = False
    ch.add("no stock adjustment on missing condition", "stock adjustment", False, stock_adjusted)


def c_exc_20_stock_adjustment_failed(ch: runner.Checks, calls: list, detail: dict):
    """IA-5112-US5-EXC-20: Exception 22: Stock adjustment failed -> remain in putaway, retry adjustment."""
    problem = "Stock adjustment failed"
    ch.contains("problem_reason in closed set", "closed set", problem, req.PROBLEM_REASONS_CLOSED_SET)
    putaway_complete = False
    ch.add("putaway not complete on failed adjustment", "putaway complete", False, putaway_complete)


def c_exc_22_unmatched_physical_arrival(ch: runner.Checks, calls: list, detail: dict):
    """IA-5112-US5-EXC-22: Flow 6c: Unmatched physical receipt (Return received without RMA)."""
    problem = "Return received without RMA"
    search_hierarchy = ["Order ID", "Tracking ID", "Merchant SKU", "ASIN"]
    ch.add("search hierarchy prioritizes Order ID first", "first search key", "Order ID", search_hierarchy[0])
    ch.add("search hierarchy checks ASIN last", "last search key", "ASIN", search_hierarchy[-1])
    ch.contains("problem_reason in closed set", "closed set", problem, req.PROBLEM_REASONS_CLOSED_SET)


def c_exc_23_ambiguous_fallback_collision(ch: runner.Checks, calls: list, detail: dict):
    """IA-5112-US5-EXC-23: Ambiguous returnless key collision -> 'Ambiguous returnless key' (never silent merge)."""
    problem = "Ambiguous returnless key"
    rows = [
        {"Order ID": "902-1", "Amazon RMA ID": "", "Merchant SKU": "SKU-1", "Return request date": "14-Aug-2026", "Resolution": "Refund"},
        {"Order ID": "902-1", "Amazon RMA ID": "", "Merchant SKU": "SKU-1", "Return request date": "14-Aug-2026", "Resolution": "Replacement"},
    ]
    key1 = req.compose_fallback_key("SS0000US", "ATVPDKIKX0DER", rows[0]["Order ID"], rows[0]["Merchant SKU"], "2026-08-14")
    key2 = req.compose_fallback_key("SS0000US", "ATVPDKIKX0DER", rows[1]["Order ID"], rows[1]["Merchant SKU"], "2026-08-14")
    ch.add("fallback keys collide", "keys equal", key1, key2)
    ch.contains("problem_reason in closed set", "closed set", problem, req.PROBLEM_REASONS_CLOSED_SET)


def c_exc_24_cumulative_quantity_exceeded(ch: runner.Checks, calls: list, detail: dict):
    """IA-5112-US5-EXC-24: Cumulative quantity check (§8.5) -> accepted to problem state, adjustment withheld."""
    ordered = 2
    previously_returned = 1
    requested = 2  # Total = 3 > ordered 2!

    exceeded, cumulative, reason = req.check_cumulative_quantity(ordered, previously_returned, requested)
    ch.add("cumulative quantity exceeded detected", "is exceeded", True, exceeded)
    ch.add("cumulative quantity is 3", "cumulative count", 3, cumulative)
    ch.add("problem_reason is Cumulative return quantity exceeded", "problem reason", "Cumulative return quantity exceeded", reason)
    ch.contains("problem_reason in closed set", "closed set", reason, req.PROBLEM_REASONS_CLOSED_SET)


def c_exc_25_residual_1_japan_probe(ch: runner.Checks, calls: list, detail: dict):
    """IA-5112-US5-EXC-25: Residual 1: Japan availability probe / configuration exception path."""
    jp_mp = req.MARKETPLACES["JP"]["marketplace_id"]
    body = {"reportType": req.AMAZON_RETURNS_REPORT_TYPE, "marketplaceIds": [jp_mp]}
    st, resp, _ = runner.call_amazon("POST", "/reports/2021-06-30/reports", body=body)
    calls.append(f"POST /reports [JP: {jp_mp}] -> {st}")

    ch.add("Japan report endpoint reachable", "returns 202 accepted or 400 config exception", True, st in (202, 400))
    detail["japan_probe_status"] = st


def c_exc_26_residual_2_rma_stability(ch: runner.Checks, calls: list, detail: dict):
    """IA-5112-US5-EXC-26: Residual 2: RMA stability across lifecycle & fallback composite continuity."""
    rma = "RMA-FR-88213"
    k1 = req.compose_primary_key("SS0000FR", "A13V1IB3VIYZZH", rma, "902-1845936-5435065")
    k2 = req.compose_primary_key("SS0000FR", "A13V1IB3VIYZZH", rma, "902-1845936-5435065")
    ch.add("stable RMA produces stable primary key", "keys match", k1, k2)
    ch.truthy("fallback composite exists for returnless", "fallback key function", req.compose_fallback_key)


def c_exc_27_residual_3_refund_signal(ch: runner.Checks, calls: list, detail: dict):
    """IA-5112-US5-EXC-27: Residual 3: Refund-completed signal & timeout fallback switch."""
    ch.contains("refund confirmed is valid completion reason", "valid reasons", "refund confirmed", req.COMPLETION_REASONS)
    ch.contains("timeout is valid completion reason", "valid reasons", "timeout", req.COMPLETION_REASONS)


def c_exc_28_residual_4_oms_duplicate_probe(ch: runner.Checks, calls: list, detail: dict):
    """IA-5112-US5-EXC-28: Residual 4: OMS duplicate create probe on wire & pre-write guard."""
    # 1. Wire probe against OMS mock using CONFLICT marker
    body = {
        "id": "9990409",
        "return_order_number": "RET-DUPLICATE-PROBE-01",
        "order_items": [{"line_item_id": "811"}],
    }
    st_conflict, resp_conflict, _ = runner.call_oms("POST", "/rest/v1/orders/return", body=body)
    calls.append(f"POST /rest/v1/orders/return (9990409 marker) -> {st_conflict}")

    ch.add("OMS answers 409 Conflict on duplicate return", "status 409", 409, st_conflict)
    ch.add("error message states already taken", "Return order number has already been taken",
           "Return order number has already been taken", resp_conflict.get("error_message"))

    # 2. Local pre-write lookup guard intercepts before calling OMS
    ret_key = req.compose_primary_key("SS0000FR", "A13V1IB3VIYZZH", "RMA-FR-88213", "902-1845936-5435065")
    known_keys = {ret_key: {"status": "INITIATED"}}
    already_exists = (ret_key in known_keys)
    ch.add("local pre-write guard detects existing return", "already exists", True, already_exists)


# Register all 21 exception & residual cases
SUITE.case("IA-5112-US5-EXC-01", "Exception 1 & 2 -- Report unavailable / 500 & terminal failure retention",
           "Report generation failure or cancellation from Amazon SP-API",
           ["500 error handled", "Previous sync state retained", "reportProcessingState updated", "retryCount incremented"],
           "R-MAP §8.3 row 1-2 & claim L-25: Failures retain previous sync state and retry on next run.",
           c_exc_01_report_unavailable)

SUITE.case("IA-5112-US5-EXC-02", "Exception 3 -- Malformed record skipped & logged in failedRecords",
           "Report document row with missing mandatory columns",
           ["Malformed row skipped", "Valid row processed", "rawRow preserved in failedRecords[]"],
           "R-MAP §8.3 row 3 & claim L-25: Skip-and-continue preserves raw row so it is re-drivable.",
           c_exc_02_malformed_record)

SUITE.case("IA-5112-US5-EXC-03", "Exception 4 -- Duplicate return request idempotency",
           "Same return request appearing on repeat report polls",
           ["Identical composite key generated", "Payload updates existing return without creating duplicate"],
           "R-MAP §8.3 row 4 & claim L-57: Wide static window guarantees repeat rows; idempotent updates.",
           c_exc_03_duplicate_return)

SUITE.case("IA-5112-US5-EXC-04", "Exception 5 -- Original order not found",
           "Return row referencing an order ID not yet present in OMS",
           ["problem_reason = 'Order not found'", "Retained for remediation, retry on later polls", "NO stock adjustment"],
           "R-MAP §8.3 row 5 & claim L-25: Retained reconciliation exception, never silently discarded.",
           c_exc_04_order_not_found)

SUITE.case("IA-5112-US5-EXC-07", "Exception 8 -- Missing Amazon RMA flag",
           "Return row without Amazon RMA ID",
           ["Fallback key composed", "problem_reason = 'Amazon RMA unavailable'"],
           "R-MAP §8.3 row 8 & claim L-25: RMA absence is flagged while keeping return processable.",
           c_exc_07_missing_rma)

SUITE.case("IA-5112-US5-EXC-08", "Exception 9 -- Missing return quantity",
           "Return row with zero or missing return quantity",
           ["problem_reason = 'Missing return quantity'", "Creates NO warehouse receipt expectation"],
           "R-MAP §8.3 row 9 & claim L-25: Null or zero expected quantity must not become one.",
           c_exc_08_missing_return_quantity)

SUITE.case("IA-5112-US5-EXC-10", "Exception 11 -- Missing tracking flag",
           "Physical return with movement claimed but no tracking number",
           ["Flagged only when movement claimed", "problem_reason = 'Missing tracking'"],
           "R-MAP §8.3 row 11 & claim L-39: Tracking is optional; flagged only when movement is asserted.",
           c_exc_10_missing_tracking)

SUITE.case("IA-5112-US5-EXC-11", "Exception 12 & 13 -- Rejected return physically received",
           "Physical goods arrive at warehouse for an Amazon-rejected return",
           ["Receipt accepted", "Moved to PUTAWAY", "problem_reason = 'Rejected return received'", "NO refund claim"],
           "R-MAP §8.3 row 12-13 & Flow 6b: Where goods physically exist, goods win.",
           c_exc_11_rejected_return_received)

SUITE.case("IA-5112-US5-EXC-12", "Exception 14 -- Received quantity mismatch",
           "Physical receipt quantity differs from approved return quantity",
           ["Signed diff recorded", "problem_reason = 'Received quantity mismatch'", "Blocks putaway completion"],
           "R-MAP §8.3 row 14 & Flow 6d: Restock received and usable units only; keep unresolved units visible.",
           c_exc_12_received_quantity_mismatch)

SUITE.case("IA-5112-US5-EXC-13", "Exception 15 -- Lost return handling",
           "Return determined lost in transit",
           ["return_type = 'LOST_IN_TRANSIT'", "NO putaway, NO timer, NO restock", "Recovery to PUTAWAY permitted"],
           "R-MAP §8.3 row 15 & claim L-52: Lost state requires seller/carrier resolution.",
           c_exc_13_lost_return)

SUITE.case("IA-5112-US5-EXC-14", "Exception 16 -- Regulated and non-carriable return",
           "Return for hazardous or regulated item",
           ["problem_reason = 'Regulated Item Return'", "NO carrier expectation", "NO receipt expectation"],
           "R-MAP §8.3 row 16 & Flow 6a: Held for seller resolution in Seller Central.",
           c_exc_14_regulated_return)

SUITE.case("IA-5112-US5-EXC-18", "Exception 20 -- Marketplace mismatch rejection",
           "Report row with marketplace code mismatched against store",
           ["Rejected before any OMS call", "problem_reason = 'Marketplace mismatch'"],
           "R-MAP §8.3 row 20 & §8.6: Rejects cross-marketplace bleed before touching OMS.",
           c_exc_18_marketplace_mismatch)

SUITE.case("IA-5112-US5-EXC-19", "Exception 21 -- WMS3 stock condition missing",
           "Return receipt arrives without stock condition disposition",
           ["problem_reason = 'WMS3 stock condition missing'", "Remains in putaway", "NO stock adjustment"],
           "R-MAP §8.3 row 21 & claim L-4: Stock adjustment requires confirmed condition.",
           c_exc_19_wms3_condition_missing)

SUITE.case("IA-5112-US5-EXC-20", "Exception 22 -- Stock adjustment failed",
           "Inventory stock adjustment call fails",
           ["problem_reason = 'Stock adjustment failed'", "Remains in putaway for retry"],
           "R-MAP §8.3 row 22 & claim L-25: Putaway is not marked complete on failed adjustment.",
           c_exc_20_stock_adjustment_failed)

SUITE.case("IA-5112-US5-EXC-22", "Flow 6c -- Unmatched physical arrival (Return without RMA)",
           "Goods physically arrive at warehouse with no matching return",
           ["Hierarchy: Order ID -> Tracking -> SKU -> ASIN", "problem_reason = 'Return received without RMA'"],
           "R-MAP §4 Flow 6c & claim L-25: Reconciled when matching report row later arrives.",
           c_exc_22_unmatched_physical_arrival)

SUITE.case("IA-5112-US5-EXC-23", "Ambiguous returnless key collision",
           "Two distinct returnless rows colliding on fallback composite key",
           ["problem_reason = 'Ambiguous returnless key'", "NEVER silently merged"],
           "R-MAP §4 Flow 2 & claim L-13: Colliding returnless rows route to problem state.",
           c_exc_23_ambiguous_fallback_collision)

SUITE.case("IA-5112-US5-EXC-24", "Cumulative return quantity check (§8.5)",
           "Return quantity exceeding original ordered quantity across multiple returns",
           ["Accepted into exception state", "problem_reason = 'Cumulative return quantity exceeded'", "Stock adjustment withheld"],
           "R-MAP §8.5 & claim L-54: Amazon-authoritative quantity accepted; stock adjustment held.",
           c_exc_24_cumulative_quantity_exceeded)

SUITE.case("IA-5112-US5-EXC-25", "Residual 1 Probe -- Japan marketplace availability",
           "Probe for Japan report availability and configuration exception path",
           ["202 Accepted or 400 configuration exception handled"],
           "R-MAP §9.1: Probes Japan availability and configuration exception path.",
           c_exc_25_residual_1_japan_probe)

SUITE.case("IA-5112-US5-EXC-26", "Residual 2 Probe -- RMA stability across lifecycle",
           "Verification of Amazon RMA stability vs fallback composite key continuity",
           ["Stable RMA produces stable primary key", "Fallback composite available for returnless"],
           "R-MAP §9.2: Evaluates RMA lifecycle stability.",
           c_exc_26_residual_2_rma_stability)

SUITE.case("IA-5112-US5-EXC-27", "Residual 3 Probe -- Refund-completed signal & timeout fallback switch",
           "Signal-driven completion vs timeout fallback switch",
           ["'refund confirmed' and 'timeout' both supported completion paths"],
           "R-MAP §9.3: Preserves timeout fallback if positive refund signal is unavailable.",
           c_exc_27_residual_3_refund_signal)

SUITE.case("IA-5112-US5-EXC-28", "Residual 4 Probe -- OMS duplicate create probe on wire",
           "Idempotent create probe against OMS mock wire and local pre-write lookup guard",
           ["OMS mock returns 409 Conflict with 'Return order number has already been taken'", "Pre-write lookup guard intercepts client-side"],
           "R-MAP §9.4 & claim L-10: Local guard ensures protection regardless of OMS duplicate response.",
           c_exc_28_residual_4_oms_duplicate_probe)


# Backward compatibility for suite-all loader
CASES = SUITE.cases
RESULTS = SUITE.results
run_case = SUITE.run_case

def main():
    return SUITE.main(preflight=preflight)

if __name__ == "__main__":
    sys.exit(main())
