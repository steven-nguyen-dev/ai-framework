#!/usr/bin/env python3
"""IA-5106 User Story 4 expectations, written from the requirement documents and published contracts.

Ticket: IA-5106 - Samsung CR | Amazon | User Story 4: Process Amazon Buyer Cancellation Requests
Repository: JPluger @ feature/amazon-cross-border/IA-5106-US4 (commit 57b2026814d)

Nothing in this file was derived by reading implementation quirks in the integration code.
Every expected value carries the document and section it comes from, so a failing check can
be argued against the specification rather than against the code.

The authoritative sources:
  R-REQ    jira-workspace/amazon-cross-border/IA-5106/IA-5106-oms-buyer-cancellation-requirements-spec.md
           the FRs (FR-1..FR-32), the ACs (AC-1..AC-25), §2.1..§2.6, §3, Appendix A, B, C
  R-MAP    .../IA-5106-buyer-cancellation-mapping-spec.md
           Flows 1..6, field mappings §4.1..§4.10, enums §5, uniqueness §6, rules §7 N-1..N-5
  R-SUM    .../IA-5106-buyer-cancellation-summary.md
           Context, Scope, Changes C-1..C-24, CR-1..CR-8, Open Questions 1..18, Notes
  R-LIB    .../IA-5106-buyer-cancellation-library.md
           Claim library L-1..L-80 with provenance and locators
  C-OMS    anchanto-oms/anchanto-oms-swagger.json
           What Anchanto OMS actually declares on the wire
  C-AMZ    amazon/amazon-sp-api-swagger.json
           amazon/schemas/notifications/OrderChangeNotification.json
           Amazon Selling Partner API contracts for Orders v0, Orders 2026-01-01, Notifications v1

Where a requirement is impossible or unresolved, the constant carries an UNSETTLED / BLOCKED note
and the suite records it as `blocked` rather than inventing a false verdict.
"""

import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))

# =====================================================================
# Target Marketplaces & Store Configurations (R-MAP §1, R-REQ §1, L-19)
# =====================================================================
# The ticket covers four marketplaces in three SP-API regions.
# Every call uses credentials of one store; marketplace isolation rests on credentials,
# NOT on marketplaceIds (which Amazon rejects for ORDER_CHANGE).

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
# Amazon SP-API Constants & Enums (C-AMZ, R-MAP §5, L-2, L-16, L-18)
# =====================================================================

# Notification Type (R-MAP §4.1, L-18)
NOTIFICATION_TYPE_ORDER_CHANGE = "ORDER_CHANGE"

# Permitted subscription change types (R-MAP §4.1, L-18, L-34)
# The subscription filters strictly on these two types.
SUBSCRIPTION_CHANGE_TYPES = ["BuyerRequestedChange", "OrderStatusChange"]

# Forbidden filter for ORDER_CHANGE (R-MAP §4.1, L-19)
FORBIDDEN_SUBSCRIPTION_FILTER = "marketplaceIds"

# cancellationExecution.cancelledBy: all three values mean confirmed outcome (R-MAP §5.2, L-16)
# AMAZON = auto-approved under policy (skips seller action, FR-7, AC-5, AC-22)
# MERCHANT = seller approved in Seller Central (FR-6, AC-6)
# BUYER = buyer cancelled in Amazon self-service window (confirmed cancellation, NOT request!)
AMAZON_CANCELLED_BY_ENUM = ["AMAZON", "MERCHANT", "BUYER"]

# Fulfillment channels: process MFN only, skip AFN (FBA) (R-MAP §4.3, L-63)
FULFILLMENT_CHANNEL_MFN = "MFN"
FULFILLMENT_CHANNEL_AFN = "AFN"

# =====================================================================
# OMS Contracts & Change Requests (C-OMS, R-REQ §2, R-MAP §4)
# =====================================================================

# CR-1: POST /rest/v1/orders/{id}/cancel_request (the Hold) (R-REQ §2.1, L-56)
CR1_ROUTE_TEMPLATE = "/rest/v1/orders/{id}/cancel_request"
CR1_REQUIRED_QUERY = ["marketplace_code"]
CR1_REQUIRED_BODY_FIELDS = ["requester", "mp_request_timestamp", "mp_request_key", "order_items"]
CR1_OPTIONAL_BODY_FIELDS = ["request_reason"]  # nullable (L-68)
CR1_ORDER_ITEM_REQUIRED = ["id", "item_codes", "reason"]
# Crucial prohibition: hold reduces no quantity (R-REQ §2.1, R-MAP §4.6, L-1, L-56)
CR1_FORBIDDEN_BODY_FIELDS = ["item_quantity"]

# CR-2: Previous status snapshot fields (write-once at DB level) (R-REQ §2.4, L-56)
CR2_SNAPSHOT_FIELDS = [
    "previous_status",
    "previous_allocation_state",
    "previous_fulfilment_stage",
    "previous_status_captured_at",
    "cancel_request_actor",
    "cancel_request_scope",
]

# CR-3: POST /rest/v1/orders/{id}/cancel_request/restore (the Restore) (R-REQ §2.2, L-59)
CR3_ROUTE_TEMPLATE = "/rest/v1/orders/{id}/cancel_request/restore"
CR3_REQUIRED_BODY_FIELDS = ["resolution", "mp_outcome_timestamp", "mp_request_key", "order_items"]
CR3_RESOLUTION_ENUM = ["REJECTED", "WITHDRAWN", "EXPIRED"]
CR3_RESERVATION_STATES = ["RETAINED", "REVALIDATED", "UNAVAILABLE"]

# CR-4 & CR-5: GET /rest/v1/orders/{id} order-level reads (R-REQ §2.4)
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

# Durable marketplace outcomes (R-REQ §2.4, R-MAP §5.3, L-59, L-66)
MP_CANCELLATION_OUTCOMES = ["PENDING", "CONFIRMED", "REJECTED", "WITHDRAWN", "EXPIRED"]

# CR-5: Structured problem reasons (R-REQ §2.4, §3, L-42, L-59, L-60, L-66)
PROBLEM_REASON_POST_RTS = "Cancellation After Ready To Ship"
PROBLEM_REASON_STATUS_UNAVAILABLE = "Previous Status Unavailable"
PROBLEM_REASON_MAPPING_FAILURE = "Cancellation Mapping Failure"
PROBLEM_REASON_VALIDATION_PENDING = "Marketplace Validation Pending"
# The 5th is the existing out-of-stock problem order (REUSE, L-42)
PROBLEM_ORDER_OUT_OF_STOCK = "oms_problem_order"

NEW_PROBLEM_REASONS = [
    PROBLEM_REASON_POST_RTS,
    PROBLEM_REASON_STATUS_UNAVAILABLE,
    PROBLEM_REASON_MAPPING_FAILURE,
    PROBLEM_REASON_VALIDATION_PENDING,
]

# CR-6: GET /rest/v1/orders/{id}/order_items quantity ledger (R-REQ §2.5, L-32, L-75)
CR6_LINE_LEDGER_FIELDS = [
    "buyer_cancellation_requested",
    "mp_cancellation_outcome",
    "line_hold_state",
    "mp_ordered_quantity",
    "mp_shipped_quantity",
    "mp_cancelled_quantity",
    "mp_remaining_quantity",
]

# CR-7: Screen seller guidance verbatim text (R-REQ §3, L-57, L-63, L-68)
SELLER_GUIDANCE_TEXT = (
    "The buyer has requested cancellation. Accept or reject the request in Amazon Seller Central. "
    "OMS will synchronize Amazon's final decision."
)

# CR-8 / Live Route: POST /rest/v1/orders/{id}/cancel (R-REQ §2.3, R-MAP §4.8, L-5, L-31)
LIVE_CANCEL_ROUTE_TEMPLATE = "/rest/v1/orders/{id}/cancel"
LIVE_CANCEL_REQUIRED_QUERY = ["marketplace_code", "cancellation_reason"]
LIVE_CANCEL_ITEM_REQUIRED = ["id", "item_quantity", "reason", "item_codes"]

# Pre-ready-to-ship gate (R-REQ §2.6, R-MAP §4.9, L-20, L-60)
BULK_CANCELLATION_CHECK_ROUTE = "/rest/v1/orders/bulk_cancellation_check"
BULK_CANCELLATION_CHECK_MAX_BATCH = 300
UPDATE_STATUS_ROUTE_TEMPLATE = "/rest/v1/orders/{id}/update_status"
STATUS_READY_TO_SHIP = "READY_TO_SHIP"

# Published connector operation (R-MAP §4.8, L-5, L-10)
CONNECTOR_OPERATION_FETCH_CANCELLED = "FETCH_CANCELLED_ORDERS"

# =====================================================================
# Status Translation Maps (R-MAP §5.1, §7 N-3, L-7, L-23)
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
# Key Formats & Validation Rules (R-MAP §6, §7)
# =====================================================================

def make_idempotency_key(store_code, marketplace_id, amazon_order_id, order_item_id, time_of_order_change):
    """Builds the 5-part composite idempotency key per R-MAP §6 and claim L-62:
    store_code|marketplace_id|AmazonOrderId|OrderItemId|TimeOfOrderChange
    """
    return f"{store_code}|{marketplace_id}|{amazon_order_id}|{order_item_id}|{time_of_order_change}"


def parse_is_buyer_requested_cancel(val):
    """Rule N-2: IsBuyerRequestedCancel is typed string in Amazon's contract ('true'/'false').
    It MUST be parsed as text, never truthy-cast, so 'false' produces False.
    """
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.strip().lower() == "true"
    return False


# =====================================================================
# Unsettled, Blocked & Open Questions (R-SUM §3, R-REQ §1, Appendix B)
# =====================================================================

UNSETTLED = {
    "AC-11": (
        "AC-11 and FR-12 require partial line quantity cancellation, but Amazon reports no "
        "cancelled-quantity on the seller-fulfilled path in either v0, 2026-01-01, or notification (L-1). "
        "Whole-line cancellation only is built (N-1). AC-11 cannot pass as written and must be descoped (L-58)."
    ),
    "AC-13": (
        "AC-13 requires forward state tracking for 'shipped in part, then cancelled the rest'. "
        "Blocked on IA-5109 landing mp_fulfilment_state (L-32)."
    ),
    "CR-8": (
        "Whether POST /rest/v1/orders/{id}/cancel already returns in-process stock of a never-picked "
        "order to ATP. Assumed yes; confirmed as an open question to the OMS owner (L-48)."
    ),
    "DOD-14-JP": (
        "DoD bullet 14 requires acceptance pass for Japan. Notification availability is documented "
        "per region (FE), but live account validation is required to sign off DoD-14 (L-67)."
    ),
}

# Cases whose verdict is fixed as `blocked` because the requirement is an unresolved open item
BLOCKED_CASES = {
    "IA-5106-US4-CANCEL-16",  # AC-11 sub-line partial quantity
    "IA-5106-US4-CANCEL-17",  # AC-13 forward state blocked on IA-5109
    "IA-5106-US4-GATE-16",    # DoD-14 Japan Far East live acceptance pass
}
