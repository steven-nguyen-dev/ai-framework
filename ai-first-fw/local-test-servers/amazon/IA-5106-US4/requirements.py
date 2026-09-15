#!/usr/bin/env python3
"""IA-5106 User Story 4 expectations, re-sourced against verified authorities and published contracts.

Ticket: IA-5106 - Samsung CR | Amazon | User Story 4: Process Amazon Buyer Cancellation Requests
Commit: 57b2026814d (Merge PR #22482 for IA-5105; no feature/amazon-cross-border/IA-5106-US4 branch exists)

NOTE ON PHANTOM SOURCES:
  Earlier versions cited four local specification and claim files that do not exist in
  jpluger-shared, ai-framework, or JPluger git history. All citations in this file have
  been re-sourced to the real, openable authorities below.

The real authoritative sources:
  JIRA-IA5106 Jira Issue IA-5106 (FR-1..FR-32, AC-1..AC-25, §9 State Model, §18 UI, §19 Mapping, §20 Errors, §26 Discovery, §27 DoD)
  CTX-NOTE    jira-workspace/amazon-cross-border/IA-5106/investigation/notes/IA-5106-user-story-context.md
  C-OMS       anchanto-oms/anchanto-oms-swagger.json (Declared Anchanto OMS endpoints and schemas)
  C-AMZ       amazon/schemas/notifications/OrderChangeNotification.json & Amazon SP-API Orders specifications

Where a pinned value has no openable authority, it is marked with UNSOURCED and an explanatory note.
"""

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))

# =====================================================================
# Target Marketplaces & Store Configurations (JIRA-IA5106 §27 DoD, AC-23, FR-1, FR-32; C-AMZ)
# =====================================================================
# The ticket covers four marketplaces in three SP-API regions (DoD bullet 14, AC-23).
# Every call uses credentials of one store; marketplace isolation rests on credentials,
# NOT on marketplaceIds (which Amazon rejects for ORDER_CHANGE per C-AMZ).

TARGET_MARKETPLACES = {
    "FR": {
        "marketplace_code": "amazon_sp_fr",
        "country": "France",
        "region": "EU",
        "marketplace_id": "A13V1IB3VIYZZH",
        "default_store_code": "SS0000FR",
        "currency": "EUR",
    },
    "DE": {
        "marketplace_code": "amazon_sp_de",
        "country": "Germany",
        "region": "EU",
        "marketplace_id": "A1PA6795UKMFR9",
        "default_store_code": "SS0000DE",
        "currency": "EUR",
    },
    "JP": {
        "marketplace_code": "amazon_sp_jp",
        "country": "Japan",
        "region": "FE",
        "marketplace_id": "A1VC38T7YXB528",
        "default_store_code": "SS0000JP",
        "currency": "JPY",
    },
    "US": {
        "marketplace_code": "amazon_sp_us",
        "country": "United States",
        "region": "NA",
        "marketplace_id": "ATVPDKIKX0DER",
        "default_store_code": "SS0000US",
        "currency": "USD",
    },
}

# =====================================================================
# Amazon SP-API Constants & Enums (C-AMZ, JIRA-IA5106 FR-6, FR-7, FR-25, AC-5, AC-6, AC-22)
# =====================================================================

# Notification Type (JIRA-IA5106 FR-25, §26 Discovery Item 5, CTX-NOTE §4 Q1; C-AMZ)
NOTIFICATION_TYPE_ORDER_CHANGE = "ORDER_CHANGE"

# Permitted subscription change types (C-AMZ: OrderChangeNotification schema; JIRA-IA5106 FR-1, FR-25)
# The subscription filters strictly on these two types.
SUBSCRIPTION_CHANGE_TYPES = ["BuyerRequestedChange", "OrderStatusChange"]

# Forbidden filter for ORDER_CHANGE (C-AMZ: SP-API notifications documentation)
FORBIDDEN_SUBSCRIPTION_FILTER = "marketplaceIds"

# cancellationExecution.cancelledBy: all three values mean confirmed outcome
# Sourced from JIRA-IA5106 §2 Background, FR-6, FR-7, AC-5, AC-6, AC-22 & C-AMZ Orders 2026-01-01 schema:
# AMAZON = auto-approved under policy (skips seller action, FR-7, AC-5, AC-22)
# MERCHANT = seller approved in Seller Central (FR-6, AC-6)
# BUYER = buyer cancelled in Amazon self-service window (confirmed cancellation, NOT request!)
AMAZON_CANCELLED_BY_ENUM = ["AMAZON", "MERCHANT", "BUYER"]

# Fulfillment channels: process MFN only, skip AFN (FBA) (JIRA-IA5106 §6 Preconditions, §5.2 Out of Scope)
FULFILLMENT_CHANNEL_MFN = "MFN"
FULFILLMENT_CHANNEL_AFN = "AFN"

# =====================================================================
# OMS Contracts & Proposed Change Requests (JIRA-IA5106, C-OMS, CTX-NOTE)
# =====================================================================

# CR-1: POST /rest/v1/orders/{id}/cancel_request (the Hold)
# Business concept in JIRA-IA5106 FR-3 (Cancel_in_process hold), FR-14, AC-1, AC-3, AC-14.
# UNSOURCED: The route /rest/v1/orders/{id}/cancel_request is synthetic; not declared in C-OMS swagger. Requires OMS API contract.
CR1_ROUTE_TEMPLATE = "/rest/v1/orders/{id}/cancel_request"
# UNSOURCED: Wire query parameter for synthetic hold route; requires OMS API contract.
CR1_REQUIRED_QUERY = ["marketplace_code"]
# PARTIALLY SOURCED: Business concepts in JIRA-IA5106 FR-1, FR-32; UNSOURCED exact wire body field names require OMS API contract.
CR1_REQUIRED_BODY_FIELDS = ["requester", "mp_request_timestamp", "mp_request_key", "order_items"]
# Sourced from JIRA-IA5106 FR-1, §20 Error Matrix, AC-24 (nullable/optional cancellation reason handled gracefully)
CR1_OPTIONAL_BODY_FIELDS = ["request_reason"]  # nullable
# PARTIALLY SOURCED: Concepts in JIRA-IA5106 FR-1, FR-5; UNSOURCED exact wire item field names require OMS API contract.
CR1_ORDER_ITEM_REQUIRED = ["id", "item_codes", "reason"]
# Crucial prohibition: hold reduces no quantity (Sourced from JIRA-IA5106 FR-2, FR-14, AC-3)
CR1_FORBIDDEN_BODY_FIELDS = ["item_quantity"]

# CR-2: Previous status snapshot fields (write-once at DB level)
# Sourced from JIRA-IA5106 §10 FR-4 (Previous order status, allocation state, fulfilment stage, captured timestamp, actor, scope), AC-2.
CR2_SNAPSHOT_FIELDS = [
    "previous_status",
    "previous_allocation_state",
    "previous_fulfilment_stage",
    "previous_status_captured_at",
    "cancel_request_actor",
    "cancel_request_scope",
]

# CR-3: POST /rest/v1/orders/{id}/cancel_request/restore (the Restore)
# Business concept in JIRA-IA5106 §14 FR-17, FR-18, AC-7 (restoration of preserved operational status).
# UNSOURCED: The route /rest/v1/orders/{id}/cancel_request/restore is synthetic; not declared in C-OMS swagger. Requires OMS API contract.
CR3_ROUTE_TEMPLATE = "/rest/v1/orders/{id}/cancel_request/restore"
# UNSOURCED: Wire payload field names require OMS API contract.
CR3_REQUIRED_BODY_FIELDS = ["resolution", "mp_outcome_timestamp", "mp_request_key", "order_items"]
# Sourced from JIRA-IA5106 §9 State Model, §14 FR-17, §14 FR-18, §19 Mapping, AC-7
CR3_RESOLUTION_ENUM = ["REJECTED", "WITHDRAWN", "EXPIRED"]
# Sourced from JIRA-IA5106 §13 FR-16, AC-8, AC-9 (inventory reservation retention/revalidation states)
CR3_RESERVATION_STATES = ["RETAINED", "REVALIDATED", "UNAVAILABLE"]

# CR-4 & CR-5: GET /rest/v1/orders/{id} order-level reads
# Business attributes sourced from JIRA-IA5106 §18 Order-level UI display & §14 FR-19
CR4_ORDER_LEVEL_FIELDS = [
    "previous_status",
    "buyer_cancellation_requested",
    "buyer_cancellation_reason",
    "buyer_cancellation_requester",
    "mp_cancellation_outcome",
    "mp_cancellation_cancelled_by",
    "mp_outcome_timestamp",
    "mp_last_reconciled_at",
    "cancellation_scope",
    "problem_state",
    "problem_reason",
]

# Durable marketplace outcomes (Sourced from JIRA-IA5106 §9 State Model, FR-10, FR-17, FR-18, FR-27, §19 Mapping)
MP_CANCELLATION_OUTCOMES = ["PENDING", "CONFIRMED", "REJECTED", "WITHDRAWN", "EXPIRED"]

# CR-5: Structured problem reasons (JIRA-IA5106 §14 FR-19, §15 FR-22, §15 FR-23, §20 Error Matrix)
# Sourced from JIRA-IA5106 §9, §15 FR-23, §19, §20, §21 AC-17. Note: §26 discovery item 11 still lists the problem reason as pending confirmation.
PROBLEM_REASON_POST_RTS = "Cancellation After RFP"
# Concept in JIRA-IA5106 FR-19, §20; UNSOURCED exact string literal requires OMS enum specification
PROBLEM_REASON_STATUS_UNAVAILABLE = "Previous Status Unavailable"
# Concept in JIRA-IA5106 §20; UNSOURCED exact string literal requires OMS enum specification
PROBLEM_REASON_MAPPING_FAILURE = "Cancellation Mapping Failure"
# Sourced verbatim from JIRA-IA5106 §15 FR-22
PROBLEM_REASON_VALIDATION_PENDING = "Marketplace Validation Pending"
# Sourced from JIRA-IA5106 §13 FR-16, AC-9 (existing OMS out-of-stock problem order reuse)
PROBLEM_ORDER_OUT_OF_STOCK = "oms_problem_order"

NEW_PROBLEM_REASONS = [
    PROBLEM_REASON_POST_RTS,
    PROBLEM_REASON_STATUS_UNAVAILABLE,
    PROBLEM_REASON_MAPPING_FAILURE,
    PROBLEM_REASON_VALIDATION_PENDING,
]

# CR-6: GET /rest/v1/orders/{id}/order_items quantity ledger (Sourced from JIRA-IA5106 §12 FR-12, §18 Line-level UI)
CR6_LINE_LEDGER_FIELDS = [
    "buyer_cancellation_requested",
    "mp_cancellation_outcome",
    "line_hold_state",
    "mp_ordered_quantity",
    "mp_shipped_quantity",
    "mp_cancelled_quantity",
    "mp_remaining_quantity",
]

# CR-7: Screen seller guidance verbatim text (100% SOURCED VERBATIM from JIRA-IA5106 §18 User Guidance, FR-3, FR-6, AC-21)
SELLER_GUIDANCE_TEXT = (
    "The buyer has requested cancellation. Accept or reject the request in Amazon Seller Central. "
    "OMS will synchronize Amazon's final decision."
)

# CR-8 / Live Route: POST /rest/v1/orders/{id}/cancel (100% SOURCED from C-OMS /rest/v1/orders/{id}/cancel & JIRA-IA5106 FR-10, FR-15)
LIVE_CANCEL_ROUTE_TEMPLATE = "/rest/v1/orders/{id}/cancel"
LIVE_CANCEL_REQUIRED_QUERY = ["marketplace_code", "cancellation_reason"]
LIVE_CANCEL_ITEM_REQUIRED = ["id", "item_quantity", "reason", "item_codes"]

# Pre-ready-to-ship gate (JIRA-IA5106 §15 FR-20, FR-21; 100% SOURCED from C-OMS anchanto-oms-swagger.json)
# C-OMS declares /rest/v1/orders/bulk_cancellation_check with parameter order_ids description 'max 300'
BULK_CANCELLATION_CHECK_ROUTE = "/rest/v1/orders/bulk_cancellation_check"
BULK_CANCELLATION_CHECK_MAX_BATCH = 300
UPDATE_STATUS_ROUTE_TEMPLATE = "/rest/v1/orders/{id}/update_status"
STATUS_READY_TO_SHIP = "READY_TO_SHIP"

# Published connector operation (100% SOURCED from CTX-NOTE: IA-5106-user-story-context.md lines 22, 30)
CONNECTOR_OPERATION_FETCH_CANCELLED = "FETCH_CANCELLED_ORDERS"

# =====================================================================
# Status Translation Maps (Amazon Orders API v0 & 2026-01-01; JIRA-IA5106 §9, §19; CTX-NOTE)
# =====================================================================
# Orders v0 uses PascalCase; Orders 2026-01-01 uses UPPER_SNAKE_CASE.
# mapOrderStatus must handle BOTH spellings.

ORDER_STATUS_MAP = {
    # PascalCase (Orders v0)
    "Pending": "active",
    "Unshipped": "active",
    "PartiallyShipped": "active",
    "Canceled": "Cancel",
    # UPPER_SNAKE_CASE (Orders 2026-01-01)
    "PENDING": "active",
    "PENDING_AVAILABILITY": "active",
    "UNSHIPPED": "active",
    "PARTIALLY_SHIPPED": "active",
    "CANCELLED": "Cancel",
}

# =====================================================================
# Key Formats & Validation Rules (JIRA-IA5106 FR-1, FR-2, FR-32; C-AMZ)
# =====================================================================

def make_idempotency_key(store_code, marketplace_id, amazon_order_id, order_item_id, time_of_order_change):
    """Builds the 5-part composite idempotency key per JIRA-IA5106 §17 FR-32:
    OMS Store + Marketplace ID + Amazon Order ID + Amazon Order Item ID + Amazon Update Timestamp.
    Format: store_code|marketplace_id|AmazonOrderId|OrderItemId|TimeOfOrderChange
    """
    return f"{store_code}|{marketplace_id}|{amazon_order_id}|{order_item_id}|{time_of_order_change}"


def parse_is_buyer_requested_cancel(val):
    """Rule N-2 (C-AMZ Orders v0 & JIRA-IA5106 FR-1, FR-2, AC-14):
    IsBuyerRequestedCancel is typed string in Amazon's contract ('true'/'false').
    It MUST be parsed as text, never truthy-cast, so 'false' produces False.
    """
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.strip().lower() == "true"
    return False


# =====================================================================
# Unsettled, Blocked & Open Questions (JIRA-IA5106 AC-11, AC-13, DoD-14, §26 Discovery; CTX-NOTE Q3)
# =====================================================================

UNSETTLED = {
    "AC-11": (
        "AC-11 and FR-12 require partial line quantity cancellation, but Amazon reports no "
        "cancelled-quantity on the seller-fulfilled path in either v0, 2026-01-01, or notification. "
        "Whole-line cancellation only is built. AC-11 cannot pass as written and must be descoped."
    ),
    "AC-13": (
        "AC-13 requires forward state tracking for 'shipped in part, then cancelled the rest'. "
        "Blocked on IA-5109 landing mp_fulfilment_state."
    ),
    "CR-8": (
        "Whether POST /rest/v1/orders/{id}/cancel already returns in-process stock of a never-picked "
        "order to ATP. Assumed yes; confirmed as an open question to the OMS owner."
    ),
    "DOD-14-JP": (
        "DoD bullet 14 requires acceptance pass for Japan. Notification availability is documented "
        "per region (FE), but live account validation is required to sign off DoD-14."
    ),
}

# Cases whose verdict is fixed as `blocked` because the requirement is an unresolved open item
BLOCKED_CASES = {
    "IA-5106-US4-CANCEL-16",  # AC-11 sub-line partial quantity
    "IA-5106-US4-CANCEL-17",  # AC-13 forward state blocked on IA-5109
    "IA-5106-US4-GATE-16",    # DoD-14 Japan Far East live acceptance pass
}

# Retired cases registry (stable IDs, reason for retirement)
RETIRED_CASES = {
    "IA-5106-US4-HOLD-09": "Merged into IA-5106-US4-GATE-03 (pre-RTS gate evaluation belongs in suite-gate.py)",
}

# =====================================================================
# Error Matrix & Resilience Constants (JIRA-IA5106 §16 FR-26, §20 Error Matrix)
# =====================================================================

# Concept in JIRA-IA5106 §20 Error Matrix ('Amazon order not found in OMS'); UNSOURCED exact status string requires OMS enum specification
EXCEPTION_RECONCILIATION_PENDING = "ORDER_NOT_FOUND_RECONCILIATION_PENDING"
# Concept in JIRA-IA5106 §20 ('alert integration support'); UNSOURCED exact alert target string requires alerting specification
ALERT_INTEGRATION_DASHBOARD = "INTEGRATION_DASHBOARD"

# 100% SOURCED VERBATIM from JIRA-IA5106 §16 FR-26 (the 5 priority categories)
PRIORITY_SWEEP_CATEGORIES = [
    "HELD_ORDERS",
    "APPROACHING_READY_TO_SHIP",
    "CANCELLATION_AFTER_READY_TO_SHIP",
    "PARTIALLY_SHIPPED_WITH_REMAINING",
    "INCOMPLETE_CANCELLATION_DATA",
]

# Suite proof contract
DOES_NOT_PROVE = (
    "These suites call the mocks directly. They do not drive JPluger. "
    "A green run means the mocks and the IA-5106 documents agree -- it is not evidence that the "
    "integration works. Definition-of-done requirements are verified through the integration tests in JPluger."
)

# =====================================================================
# OMS Wire Helpers (Judging payloads on observed wire output)
# =====================================================================

_LOG_CACHE = {}


def _http(method, url, body=None, token=None):
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
        return 0, {"_transport_error": str(e)}
    try:
        return status, json.loads(raw.decode("utf-8")) if raw.strip() else {}
    except Exception:
        return status, raw.decode("utf-8", "replace")


def clear_oms_log(base_oms):
    """Clears the OMS mock call log via DELETE /log/data."""
    key = base_oms.rstrip("/")
    _LOG_CACHE.pop(key, None)
    status, _ = _http("DELETE", key + "/log/data")
    return status == 200


def oms_high_water(base_oms, token=None):
    """Returns newest sequence number in the OMS mock log."""
    key = base_oms.rstrip("/")
    status, doc = _http("GET", key + "/log/data", token=token)
    if status != 200 or not isinstance(doc, dict):
        return 0
    _LOG_CACHE[key] = doc.get("entries") or []
    seqs = [e.get("seq") or e.get("_seq") or 0 for e in _LOG_CACHE[key]]
    return max(seqs) if seqs else 0


def oms_received(base_oms, path, token=None, refresh=False, since=None):
    """Reads requests received by OMS mock for `path` since sequence `since`."""
    key = base_oms.rstrip("/")
    if refresh or key not in _LOG_CACHE:
        status, doc = _http("GET", key + "/log/data", token=token)
        _LOG_CACHE[key] = (doc.get("entries") or []) if (status == 200 and isinstance(doc, dict)) else []
    out = []
    for entry in _LOG_CACHE[key]:
        req_entry = entry.get("request") or {}
        url = req_entry.get("url") or ""
        if path not in url:
            continue
        seq = entry.get("seq") or entry.get("_seq") or 0
        if since is not None and seq <= since:
            continue
        body = req_entry.get("body")
        if not body and req_entry.get("bodyText"):
            try:
                body = json.loads(req_entry["bodyText"])
            except Exception:
                body = req_entry.get("bodyText")
        # Extract query dict
        query_dict = {}
        if "?" in url:
            parsed_q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
            query_dict = {k: v[0] if len(v) == 1 else v for k, v in parsed_q.items()}
        out.append({
            "seq": seq,
            "method": req_entry.get("method"),
            "url": url,
            "query": query_dict,
            "body": body if isinstance(body, (dict, list)) else {},
            "raw": req_entry.get("bodyText") or json.dumps(body) if body is not None else "",
            "status": (entry.get("response") or {}).get("status"),
        })
    return out

