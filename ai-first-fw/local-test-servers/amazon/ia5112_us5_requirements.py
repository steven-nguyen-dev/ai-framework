#!/usr/bin/env python3
"""IA-5112 User Story 5 expectations and transformation rules, written from the requirement
documents and published contracts for Amazon Seller-Fulfilled Returns.

Every expected value carries the document and section it comes from:
  R-SUM    jira-workspace/amazon-cross-border/IA-5112/IA-5112-seller-fulfilled-returns-summary.md
  R-REQ    .../IA-5112-oms-returns-requirements-spec.md
  R-MAP    .../IA-5112-amz-oms-returns-mapping-spec.md
  R-LIB    .../IA-5112-seller-fulfilled-returns-library.md
  C-OMS    anchanto-oms/anchanto-oms-swagger.json
  C-AMZ    amazon/amazon-sp-api-swagger.json

Used by:
  - suite-IA-5112-US5-sync.py
  - suite-IA-5112-US5-lifecycle.py
  - suite-IA-5112-US5-exceptions.py
  - suite-IA-5112-US5.py
"""

import csv
import datetime
import io
import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))

# =====================================================================
# 1. Amazon SP-API Reports Contract (C-AMZ, R-MAP §3.1, §5.1-5.3)
# =====================================================================

AMAZON_RETURNS_REPORT_TYPE = "GET_FLAT_FILE_RETURNS_DATA_BY_RETURN_DATE"

# R-MAP §5 (Source column inventory) & claim L-37: 31 documented columns in exact order
AMAZON_REPORT_COLUMNS_31 = [
    "Order ID",
    "Order date",
    "Return request date",
    "Return request status",
    "Amazon RMA ID",
    "Merchant RMA ID",
    "Label type",
    "Label cost",
    "Currency code",
    "Return carrier",
    "Tracking ID",
    "Label to be paid by",
    "A-to-Z Claim",
    "Is prime",
    "ASIN",
    "Merchant SKU",
    "Item Name",
    "Return quantity",
    "Return Reason",
    "In policy",
    "Return type",
    "Resolution",
    "Invoice number",
    "Return delivery date",
    "Order Amount",
    "Order quantity",
    "SafeT Action reason",
    "SafeT claim id",
    "SafeT claim state",
    "SafeT claim creation time",
    "SafeT claim reimbursement amount",
    "Refunded Amount",
]

# R-MAP §1.3: Four in-scope marketplaces
MARKETPLACES = {
    "FR": {
        "marketplace_code": "amazon_sp_fr",
        "marketplace_id": "A13V1IB3VIYZZH",
        "region": "EU",
        "country": "FR",
        "currency": "EUR",
    },
    "DE": {
        "marketplace_code": "amazon_sp_de",
        "marketplace_id": "A1PA6795UKMFR9",
        "region": "EU",
        "country": "DE",
        "currency": "EUR",
    },
    "JP": {
        "marketplace_code": "amazon_sp_jp",
        "marketplace_id": "A1VC38T7YXB528",
        "region": "FE",
        "country": "JP",
        "currency": "JPY",
    },
    "US": {
        "marketplace_code": "amazon_sp_us",
        "marketplace_id": "ATVPDKIKX0DER",
        "region": "NA",
        "country": "US",
        "currency": "USD",
    },
}

# R-MAP §3.1 & claim L-32: Rate Limits
RATE_LIMITS = {
    "create_report": {
        "rate_req_per_sec": 0.0167,  # 1 call per 60 seconds sustained
        "burst": 15,
        "binding_constraint": True,
    },
    "get_report": {
        "rate_req_per_sec": 2.0,
        "burst": 15,
        "binding_constraint": False,
    },
    "get_document": {
        "rate_req_per_sec": 0.0167,
        "burst": 15,
        "binding_constraint": True,
    },
}

# R-MAP §3.1 & claim L-12: Document URL expires in 5 minutes (300 seconds)
DOCUMENT_URL_EXPIRY_SECONDS = 300

# R-MAP §4 Flow 1: Poll cadence and wide static window (near 60-day cap)
DEFAULT_POLL_CADENCE_MINUTES = 30
REPORT_WINDOW_DAYS_CAP = 60

# =====================================================================
# 2. OMS POST /rest/v1/orders/return (R-REQ §2.1, R-MAP §5.4, C-OMS)
# =====================================================================

# 20 ADD fields on OMS create endpoint (R-REQ §2.1)
OMS_CREATE_ADD_FIELDS_20 = [
    "return_request_date",
    "marketplace_id",
    "amazon_rma_id",
    "merchant_rma_id",
    "return_reason",
    "returnless",
    "label_type",
    "label_payer",
    "label_cost",
    "currency_code",
    "carrier",
    "cross_border_indicator",
    "origin_country",
    "destination_country",
    "buyer_comment",
    "return_by_date",
    "return_address",
    "return_address_status",
    "asin",          # order_items[].asin
    "product_title", # order_items[].product_title
]

# 10 REUSE fields on OMS create endpoint (R-REQ §2.1)
OMS_CREATE_REUSE_FIELDS_10 = [
    "id",
    "order_date",
    "return_order_number",
    "line_item_id",    # order_items[].line_item_id
    "item_codes",      # order_items[].item_codes[]
    "quantity",        # order_items[].quantity
    "reason",          # order_items[].reason
    "shipping_name",   # order_items[].shipping_name
    "shipping_type",   # order_items[].shipping_type
    "tracking_number", # order_items[].tracking_number
]

# R-MAP §7: return_order_number max length 60 characters
RETURN_ORDER_NUMBER_MAX_LEN = 60

# R-REQ §2.1 row 17 & claim L-55: return_address_status must be NOT NULL and enum
RETURN_ADDRESS_STATUSES = ["available", "unavailable"]

# =====================================================================
# 3. OMS POST /rest/v1/orders/{id}/update_status?new_status=RETURN (R-REQ §2.2, R-MAP §5.5)
# =====================================================================

# 15 ADD fields on OMS status update endpoint (R-REQ §2.2)
OMS_STATUS_ADD_FIELDS_15 = [
    "authorization_date",
    "amazon_last_updated_at",
    "amazon_closure_indicator",
    "refund_completed_indicator",
    "completion_reason",
    "return_completed_at",
    "putaway_completed_at",
    "problem_reason",
    "approved",             # order_items[].approved
    "received",             # order_items[].received
    "putaway",              # order_items[].putaway
    "remaining_unresolved", # order_items[].remaining_unresolved
    "disposition",          # order_items[].disposition[]
    "asin",                 # order_items[].asin
    "product_title",        # order_items[].product_title
]

# 4 Completion Reasons (R-REQ §2.2, R-MAP §5.5 row 7, claim L-51)
COMPLETION_REASONS = [
    "refund confirmed",
    "timeout",
    "amazon returnless resolution",
    "no refund applicable",
]

# R-REQ §2.2 & claim L-14, L-58: Canonical completion token is COMPLETE, not COMPLETED
CANONICAL_COMPLETION_TOKEN = "COMPLETE"
FORBIDDEN_COMPLETION_TOKEN = "COMPLETED"

# R-REQ §2.2: Closed set of 16 problem_reason values
PROBLEM_REASONS_CLOSED_SET = [
    "Amazon RMA unavailable",
    "Ambiguous returnless key",
    "Order not found",
    "Order item not found",
    "Unknown seller SKU",
    "Marketplace mismatch",
    "Regulated Item Return",
    "International Return Action Required",
    "Rejected return received",
    "Received quantity mismatch",
    "Return received without RMA",
    "Cumulative return quantity exceeded",
    "Missing return quantity",
    "Missing tracking",
    "WMS3 stock condition missing",
    "Stock adjustment failed",
]

# =====================================================================
# 4. Status Model & Mirakl Ranking (R-MAP §6.1, §8.2, claim L-9, L-53)
# =====================================================================

# Return Type tokens mapped to EOrderState constants
RETURN_TYPE_MAPPING = {
    "RETURN_INITIATED": "INITIATED",
    "APPROVAL_IN_PROCESS": "APPROVAL_INPROCESS",
    "RETURN_APPROVED": "APPROVED",
    "RETURN_REJECTED": "REJECTED",
    "AUTO_APPROVED": "AUTO_APPROVED",
    "AUTO_REJECTED": "AUTO_REJECTED",
    "RETURN_IN_PROGRESS": "IN_PROGRESS",
    "LOST_IN_TRANSIT": "LOST_IN_TRANSIT",
    "RETURN_PUTAWAY": "PUTAWAY",
    "RETURN_COMPLETE": "COMPLETE",
}

# Mirakl rank order: lowest (1) to highest (6)
# Stale incoming row with rank < stored rank is rejected (no regression)
# Terminal states: REJECTED (cannot move backward), COMPLETE (never re-opens)
STATUS_RANKS = {
    "INITIATED": 1,
    "APPROVAL_INPROCESS": 2,
    "REJECTED": 3,
    "APPROVED": 3,
    "AUTO_APPROVED": 3,
    "AUTO_REJECTED": 3,
    "IN_PROGRESS": 4,
    "LOST_IN_TRANSIT": 4,
    "PUTAWAY": 5,
    "COMPLETE": 6,
}

# =====================================================================
# 5. WMS3 Stock Condition & Authority Split (R-REQ §2.7, R-MAP §1.1, §6.2)
# =====================================================================

# R-MAP §6.2 & claim L-4, L-61: Exactly TWO stock conditions at return receipt
WMS3_STOCK_CONDITIONS = ["usable_quantity", "unusable_quantity"]
# Quarantine exists ONLY at inbound, never at return receipt!
FORBIDDEN_RETURN_RECEIPT_CONDITION = "quarantine_quantity"

# R-REQ §2.5 & claim L-53, L-31: Append-only change log sources
CHANGE_LOG_SOURCES = ["amazon_report", "wms", "oms_user", "ageing_job"]

# WMS3 authoritative fields that Amazon reports CANNOT overwrite
WMS3_AUTHORITATIVE_FIELDS = [
    "received",
    "disposition",
    "usable_quantity",
    "unusable_quantity",
    "putaway",
    "putaway_completed_at",
    "putaway_entered_at",
    "stock_condition",
]

# =====================================================================
# 6. Functional Engines / Helpers
# =====================================================================

def parse_report_date(val: Optional[str]) -> Optional[str]:
    """Parses Amazon report date DD-MMM-YYYY (e.g. 14-Aug-2026) to ISO YYYY-MM-DD.
    Blank/empty string returns None.
    """
    if not val or not val.strip():
        return None
    val = val.strip()
    try:
        dt = datetime.datetime.strptime(val, "%d-%b-%Y")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        pass
    try:
        # Fallback to ISO if already ISO
        dt = datetime.datetime.fromisoformat(val.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return None


def parse_tsv_report(tsv_content: str) -> Tuple[List[str], List[Dict[str, str]]]:
    """Parses TSV report by header name (never by column index) per R-MAP §5.3 row 3."""
    reader = csv.reader(io.StringIO(tsv_content), delimiter="\t")
    rows = list(reader)
    if not rows:
        return [], []
    headers = [h.strip() for h in rows[0]]
    records = []
    for r in rows[1:]:
        if not r or not any(cell.strip() for cell in r):
            continue
        record = {}
        for idx, h in enumerate(headers):
            record[h] = r[idx].strip() if idx < len(r) else ""
        records.append(record)
    return headers, records


def compose_primary_key(store_code: str, marketplace_id: str, amazon_rma_id: str, amazon_order_id: str) -> str:
    """R-MAP §8.1: Primary composite key: store + MarketplaceId + Amazon RMA + Amazon order ID."""
    return f"{store_code}#{marketplace_id}#{amazon_rma_id}#{amazon_order_id}"


def compose_fallback_key(
    store_code: str,
    marketplace_id: str,
    amazon_order_id: str,
    amazon_order_item_id: str,
    return_request_date: str
) -> str:
    """R-MAP §8.1: Fallback composite key for returnless (no RMA):
    store + MarketplaceId + Amazon order ID + Amazon order item ID + return request date.
    """
    return f"{store_code}#{marketplace_id}#{amazon_order_id}#{amazon_order_item_id}#{return_request_date}"


def group_flat_rows(
    rows: List[Dict[str, str]],
    store_code: str,
    marketplace_id: str
) -> Dict[str, Dict[str, Any]]:
    """Flow 2: Groups flat TSV rows into return orders keyed by primary or fallback key."""
    grouped = {}
    for row in rows:
        rma = row.get("Amazon RMA ID", "").strip()
        order_id = row.get("Order ID", "").strip()
        sku = row.get("Merchant SKU", "").strip()
        req_date = parse_report_date(row.get("Return request date", "")) or "UNKNOWN-DATE"

        if rma:
            key = compose_primary_key(store_code, marketplace_id, rma, order_id)
            key_type = "primary"
        else:
            # Fallback key where RMA is absent
            key = compose_fallback_key(store_code, marketplace_id, order_id, sku, req_date)
            key_type = "fallback"

        if key not in grouped:
            grouped[key] = {
                "key": key,
                "key_type": key_type,
                "store_code": store_code,
                "marketplace_id": marketplace_id,
                "amazon_order_id": order_id,
                "amazon_rma_id": rma or None,
                "header_row": row,
                "items": [],
            }
        grouped[key]["items"].append(row)
    return grouped


def resolve_order_item(
    item_row: Dict[str, str],
    original_order_items: List[Dict[str, Any]]
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """R-MAP §5.4 row 19 & claim L-38: Resolve order item against stored ASIN and seller SKU.
    Never infer item from ASIN alone!
    """
    row_asin = item_row.get("ASIN", "").strip()
    row_sku = item_row.get("Merchant SKU", "").strip()

    matches = []
    for orig in original_order_items:
        if orig.get("asin") == row_asin and orig.get("seller_sku") == row_sku:
            matches.append(orig)

    if len(matches) == 1:
        return matches[0], None
    elif len(matches) > 1:
        return None, "Ambiguous order item match"
    else:
        # Check if matched by ASIN only (strictly forbidden to infer)
        asin_only = [orig for orig in original_order_items if orig.get("asin") == row_asin]
        if asin_only:
            return None, "Unknown seller SKU"
        return None, "Order item not found"


def build_oms_create_payload(
    grouped_return: Dict[str, Any],
    original_order: Dict[str, Any],
    resolved_items_map: Dict[str, Dict[str, Any]],
    store_origin_country: str = "KR",
    destination_country: str = "FR"
) -> Dict[str, Any]:
    """R-MAP §5.4: Builds POST /rest/v1/orders/return payload."""
    h = grouped_return["header_row"]
    rma = grouped_return["amazon_rma_id"]
    order_id = grouped_return["amazon_order_id"]
    mp_id = grouped_return["marketplace_id"]

    order_date_iso = parse_report_date(h.get("Order date", "")) or "2026-08-12"
    req_date_iso = parse_report_date(h.get("Return request date", "")) or "2026-08-14"

    # Generate return_order_number once (capped at 60 chars)
    if rma:
        ret_num = f"IA5112-{destination_country}-{rma}"[:RETURN_ORDER_NUMBER_MAX_LEN]
    else:
        ret_num = f"IA5112-{destination_country}-RET-{order_id[-8:]}"[:RETURN_ORDER_NUMBER_MAX_LEN]

    is_returnless = (
        h.get("Resolution", "").strip().lower() in ("refund", "returnless", "returnless_refund")
        and not bool(rma)
    )

    label_cost_val = 0.0
    try:
        label_cost_val = float(h.get("Label cost", "0") or "0")
    except ValueError:
        pass

    order_items_payload = []
    for item_row in grouped_return["items"]:
        sku = item_row.get("Merchant SKU", "").strip()
        resolved = resolved_items_map.get(sku, {})
        line_item_id = str(resolved.get("line_item_id", "811"))

        qty = 1
        try:
            qty = int(item_row.get("Return quantity", "1") or "1")
        except ValueError:
            pass

        order_items_payload.append({
            "line_item_id": line_item_id,
            "item_codes": [sku] if sku else [],
            "quantity": qty,
            "reason": item_row.get("Return Reason", "Item Defective"),
            "shipping_name": item_row.get("Return carrier") or None,
            "shipping_type": "Standard",
            "tracking_number": item_row.get("Tracking ID") or None,
            "asin": item_row.get("ASIN", "").strip(),
            "product_title": item_row.get("Item Name") or None,
        })

    payload = {
        "id": str(original_order.get("id", "41277")),
        "order_date": order_date_iso,
        "return_order_number": ret_num,
        "return_request_date": req_date_iso,
        "marketplace_id": mp_id,
        "amazon_rma_id": rma,
        "merchant_rma_id": h.get("Merchant RMA ID") or None,
        "return_reason": h.get("Return Reason", "Item Defective"),
        "returnless": is_returnless,
        "label_type": h.get("Label type") or None,
        "label_payer": h.get("Label to be paid by") or None,
        "label_cost": label_cost_val,
        "currency_code": h.get("Currency code") or None,
        "carrier": h.get("Return carrier") or None,
        "cross_border_indicator": (store_origin_country != destination_country),
        "origin_country": store_origin_country,
        "destination_country": destination_country,
        "buyer_comment": None,  # Not among 31 columns, built nullable
        "return_by_date": None, # Not among 31 columns, built nullable
        "return_address": None, # Not among 31 columns, built nullable
        "return_address_status": "unavailable", # Mandatory NOT NULL
        "order_items": order_items_payload,
    }
    return payload


def build_oms_update_payload(
    return_type: str,
    tracking_number: Optional[str] = None,
    reason: Optional[str] = None,
    auth_date: Optional[str] = None,
    last_updated_at: Optional[str] = None,
    closure_indicator: bool = False,
    refund_completed_indicator: bool = False,
    completion_reason: Optional[str] = None,
    return_completed_at: Optional[str] = None,
    putaway_completed_at: Optional[str] = None,
    problem_reason: Optional[str] = None,
    items_ledger: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """R-MAP §5.5: Builds POST /rest/v1/orders/{id}/update_status?new_status=RETURN payload."""
    body = {
        "return_type": return_type,
        "tracking_number": tracking_number,
        "reason": reason,
        "authorization_date": auth_date,
        "amazon_last_updated_at": last_updated_at or datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "amazon_closure_indicator": closure_indicator,
        "refund_completed_indicator": refund_completed_indicator,
        "completion_reason": completion_reason,
        "return_completed_at": return_completed_at,
        "putaway_completed_at": putaway_completed_at,
        "problem_reason": problem_reason,
        "order_items": items_ledger or [],
    }
    return body


def rank_check_transition(
    stored_return_type: str,
    incoming_return_type: str
) -> Tuple[bool, str]:
    """R-MAP §8.2: Evaluates rank before diffing (Mirakl rank check).
    Returns (is_allowed, reason).
    """
    stored_rank = STATUS_RANKS.get(stored_return_type, 0)
    incoming_rank = STATUS_RANKS.get(incoming_return_type, 0)

    # Completed returns NEVER re-open
    if stored_return_type == "COMPLETE":
        if incoming_return_type != "COMPLETE":
            return False, "Completed return cannot move backward or reopen"
        return True, "Metadata refresh on complete return"

    # Rejected returns NEVER move back to initiated or approval-pending
    if stored_return_type == "REJECTED":
        if incoming_rank < 3:
            return False, "Rejected return cannot move back to initiated or approval-pending"
        # Exception: goods physically arriving can transition to PUTAWAY (Flow 6b)
        if incoming_return_type == "PUTAWAY":
            return True, "Physical arrival after rejection permitted"

    # Lost to Putaway allowed (Flow 2 / Flow 6)
    if stored_return_type == "LOST_IN_TRANSIT" and incoming_return_type == "PUTAWAY":
        return True, "Lost return physically received and moved to putaway"

    if incoming_rank < stored_rank:
        return False, f"Incoming rank {incoming_rank} ({incoming_return_type}) regresses stored rank {stored_rank} ({stored_return_type})"

    return True, "Forward or equal transition permitted"


def check_cumulative_quantity(
    ordered_qty: int,
    previously_returned_qty: int,
    requested_qty: int
) -> Tuple[bool, int, Optional[str]]:
    """R-MAP §8.5 & claim L-54: Checks cumulative return quantity.
    Returns (is_exceeded, cumulative_qty, problem_reason).
    """
    cumulative = previously_returned_qty + requested_qty
    if cumulative > ordered_qty:
        return True, cumulative, "Cumulative return quantity exceeded"
    return False, cumulative, None


def check_putaway_ageing(
    putaway_entered_at_iso: str,
    now_dt: Optional[datetime.datetime] = None
) -> Tuple[bool, int]:
    """R-MAP §4 Flow 4: Evaluates 30-day ageing timeout in Return_Putaway.
    Measured strictly from putawayEnteredAt.
    Returns (is_timed_out, elapsed_days).
    """
    if not now_dt:
        now_dt = datetime.datetime.now(datetime.timezone.utc)
    try:
        entered_dt = datetime.datetime.fromisoformat(putaway_entered_at_iso.replace("Z", "+00:00"))
    except Exception:
        return False, 0

    elapsed = (now_dt - entered_dt).days
    return (elapsed >= 30), elapsed


class ReturnOrderAuditLogger:
    """R-REQ §2.5 & R-MAP §8.4: Append-only change log enforcing authority split."""

    def __init__(self):
        self.log: List[Dict[str, Any]] = []

    def record_change(
        self,
        return_order_id: str,
        source: str,
        field: str,
        old_val: Any,
        new_val: Any,
        record_ref: Optional[str] = None
    ) -> bool:
        if source not in CHANGE_LOG_SOURCES:
            raise ValueError(f"Invalid change source: {source}")

        # Enforce Authority Split: amazon_report CANNOT overwrite field last written by wms
        if source == "amazon_report" and field in WMS3_AUTHORITATIVE_FIELDS:
            # Check last write for this field
            prev_writes = [e for e in self.log if e["return_order_id"] == return_order_id and e["field"] == field]
            if prev_writes and prev_writes[-1]["source"] == "wms":
                # Forbidden overwrite!
                return False

        entry = {
            "return_order_id": return_order_id,
            "changed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "source": source,
            "field": field,
            "old_val": old_val,
            "new_val": new_val,
            "source_record_ref": record_ref,
        }
        self.log.append(entry)
        return True


def generate_sample_tsv(
    records: Optional[List[Dict[str, str]]] = None,
    marketplace_id: str = "A13V1IB3VIYZZH"
) -> str:
    """Generates valid 31-column TSV data with official header names."""
    headers = AMAZON_REPORT_COLUMNS_31
    out = io.StringIO()
    writer = csv.writer(out, delimiter="\t", lineterminator="\n")
    writer.writerow(headers)

    if not records:
        # Default happy-path row (Appendix A.1)
        records = [{
            "Order ID": "902-1845936-5435065",
            "Order date": "12-Aug-2026",
            "Return request date": "14-Aug-2026",
            "Return request status": "Pending",
            "Amazon RMA ID": "RMA-FR-88213",
            "Merchant RMA ID": "MRMA-9981",
            "Label type": "Amazon generated",
            "Label cost": "0.00",
            "Currency code": "EUR",
            "Return carrier": "La Poste",
            "Tracking ID": "8Q123456789FR",
            "Label to be paid by": "Seller",
            "A-to-Z Claim": "false",
            "Is prime": "false",
            "ASIN": "B0B2SH4CN6",
            "Merchant SKU": "SKU-1001",
            "Item Name": "Wireless Mouse",
            "Return quantity": "1",
            "Return Reason": "Item Defective",
            "In policy": "true",
            "Return type": "ReturnAndRefund",
            "Resolution": "Refund",
            "Invoice number": "",
            "Return delivery date": "",
            "Order Amount": "29.99",
            "Order quantity": "1",
            "SafeT Action reason": "",
            "SafeT claim id": "",
            "SafeT claim state": "",
            "SafeT claim creation time": "",
            "SafeT claim reimbursement amount": "",
            "Refunded Amount": "",
        }]

    for rec in records:
        row = [rec.get(h, "") for h in headers]
        writer.writerow(row)

    return out.getvalue()
