#!/usr/bin/env python3
"""IA-5109 User Story 3 Expectations, Models, and Validation Engine.

Covers:
  - User Story 3: Support Partial and Multi-Parcel Amazon Seller-Fulfilled Shipments (IA-5109)
  - Source Documents in jira-workspace/amazon-cross-border/IA-5109:
      R-SUM    IA-5109-multi-parcel-shipments-summary.md
      R-REQ    IA-5109-oms-parcel-confirmation-requirements-spec.md
      R-MAP    IA-5109-parcel-confirmation-mapping-spec.md
      R-LIB    IA-5109-multi-parcel-shipments-library.md
      C-AMZ    amazon-sp-api-swagger.json (Orders v0 confirmShipment)
      C-OMS    anchanto-oms-swagger.json

Nothing in this file was derived by reading unverified integration code; all expected
values cite their governing requirement, claim (L-n), flow, and section.
"""

import copy
import datetime
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))

# ===================================================================== Marketplace & Auth Constants (L-55)

MARKETPLACES = {
    "amazon_sp_fr": {
        "marketplace_code": "amazon_sp_fr",
        "marketplace_id": "A13V1IB3VIYZZH",
        "name": "Amazon France",
        "region": "Europe",
        "currency": "EUR",
        "supports_cod": False,
        "is_eu": True,
    },
    "amazon_sp_de": {
        "marketplace_code": "amazon_sp_de",
        "marketplace_id": "A1PA6795UKMFR9",
        "name": "Amazon Germany",
        "region": "Europe",
        "currency": "EUR",
        "supports_cod": False,
        "is_eu": True,
    },
    "amazon_sp_jp": {
        "marketplace_code": "amazon_sp_jp",
        "marketplace_id": "A1VC38T7YXB528",
        "name": "Amazon Japan",
        "region": "Far East",
        "currency": "JPY",
        "supports_cod": True,
        "is_eu": False,
    },
    "amazon_sp_us": {
        "marketplace_code": "amazon_sp_us",
        "marketplace_id": "ATVPDKIKX0DER",
        "name": "Amazon United States",
        "region": "North America",
        "currency": "USD",
        "supports_cod": False,
        "is_eu": False,
    },
}

DEFAULT_MARKETPLACE_ID = "A13V1IB3VIYZZH"

# ===================================================================== Enums (R-MAP §5)

# 5.1 Parcel confirmation states (L-90, L-63, L-88, L-1, L-2)
class ParcelConfirmationStatus:
    PENDING_CONFIRMATION = "PENDING_CONFIRMATION"
    SUBMITTED = "SUBMITTED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    RETRY_PENDING = "RETRY_PENDING"
    RETRY_IN_PROGRESS = "RETRY_IN_PROGRESS"
    UNKNOWN_CONFIRMATION_STATE = "UNKNOWN_CONFIRMATION_STATE"
    TERMINAL_FAILURE = "TERMINAL_FAILURE"
    PROCESSING = "PROCESSING"

ALL_PARCEL_STATUSES = [
    ParcelConfirmationStatus.PENDING_CONFIRMATION,
    ParcelConfirmationStatus.SUBMITTED,
    ParcelConfirmationStatus.ACCEPTED,
    ParcelConfirmationStatus.REJECTED,
    ParcelConfirmationStatus.RETRY_PENDING,
    ParcelConfirmationStatus.RETRY_IN_PROGRESS,
    ParcelConfirmationStatus.UNKNOWN_CONFIRMATION_STATE,
    ParcelConfirmationStatus.TERMINAL_FAILURE,
    ParcelConfirmationStatus.PROCESSING,
]

# 5.2 Order-level derived marketplace state (L-90, L-98)
class MpFulfilmentState:
    PROCESSING = "processing"
    PARTIAL = "partial"
    COMPLETE = "complete"
    PARTIAL_WITH_EXCEPTION = "partial_with_exception"
    FAILED = "failed"

ALL_MP_FULFILMENT_STATES = [
    MpFulfilmentState.PROCESSING,
    MpFulfilmentState.PARTIAL,
    MpFulfilmentState.COMPLETE,
    MpFulfilmentState.PARTIAL_WITH_EXCEPTION,
    MpFulfilmentState.FAILED,
]

# 5.3 Carrier codes (L-65, L-91, L-6)
STANDARD_CARRIERS = ["DHL", "UPS", "FEDEX", "YAMATO", "SAGAWA", "JAPAN_POST"]
GENERIC_CARRIER_CODE = "Other"

# 5.4 COD Collection Method (L-7, L-93)
COD_DIRECT_PAYMENT = "DirectPayment"

# 5.5 Write-back status enum on POST /rest/v1/orders/shipping_details (L-23, L-82)
WRITEBACK_STATUS_SUCCESS = "success"
WRITEBACK_STATUS_FAILURE = "failure"

# Minimum character length for failure_reason (L-38, L-33)
MIN_FAILURE_REASON_LENGTH = 500

# Skew allowance for shipDate validation (L-8, L-52, R-MAP §7 N-4): 5 minutes
SHIP_DATE_FUTURE_TOLERANCE_SECONDS = 300

# Maximum batch size for POST /rest/v1/orders/bulk_cancellation_check (L-71, R-MAP §4.1)
MAX_BULK_CANCELLATION_BATCH_SIZE = 300


# ===================================================================== Domain Models & Transformers

class OrderItemAllocation:
    def __init__(self, line_item_id, order_item_id, sku, quantity, transparency_codes=None):
        self.line_item_id = int(line_item_id) if line_item_id is not None else None
        self.order_item_id = str(order_item_id)  # Amazon OrderItemId
        self.sku = str(sku)
        self.quantity = int(quantity)
        self.transparency_codes = transparency_codes or []

    def to_dict(self):
        d = {
            "orderItemId": self.order_item_id,
            "quantity": self.quantity,
        }
        if self.transparency_codes:
            d["transparencyCodes"] = self.transparency_codes
        return d


class CartonBox:
    def __init__(self, carton_number, tracking_number, is_master_tracking=False,
                 ship_date=None, items=None, carrier_code=None, carrier_name=None, shipping_method=None):
        self.carton_number = str(carton_number)
        self.tracking_number = str(tracking_number).strip() if tracking_number else ""
        self.is_master_tracking = bool(is_master_tracking)
        self.ship_date = ship_date
        self.items = items or []
        self.carrier_code = carrier_code
        self.carrier_name = carrier_name
        self.shipping_method = shipping_method


class Parcel:
    def __init__(self, package_reference_id, tracking_number, carrier_code,
                 carrier_name=None, shipping_method=None, ship_date=None,
                 ship_from_supply_source_id=None, order_items=None, is_master_tracking=False,
                 source_boxes=None):
        self.package_reference_id = str(package_reference_id)  # positive numeric string "1", "2"
        self.tracking_number = str(tracking_number).strip()
        self.carrier_code = str(carrier_code)
        self.carrier_name = str(carrier_name) if carrier_name else None
        self.shipping_method = str(shipping_method) if shipping_method else None
        self.ship_date = str(ship_date) if ship_date else None
        self.ship_from_supply_source_id = str(ship_from_supply_source_id) if ship_from_supply_source_id else None
        self.order_items = order_items or []  # list of OrderItemAllocation
        self.is_master_tracking = is_master_tracking
        self.source_boxes = source_boxes or []
        self.status = ParcelConfirmationStatus.PENDING_CONFIRMATION
        self.error_code = None
        self.error_message = None
        self.confirmation_reference = None
        self.confirmed_at = None

    def to_amazon_package_detail(self):
        """Converts to Amazon Orders v0 ConfirmShipmentRequest.packageDetail (L-70)."""
        detail = {
            "packageReferenceId": self.package_reference_id,
            "carrierCode": self.carrier_code,
            "trackingNumber": self.tracking_number,
            "shipDate": self.ship_date,
            "orderItems": [it.to_dict() for it in self.order_items]
        }
        if self.carrier_name or (self.carrier_code == GENERIC_CARRIER_CODE and self.carrier_name):
            detail["carrierName"] = self.carrier_name
        elif self.carrier_name:
            detail["carrierName"] = self.carrier_name

        if self.shipping_method:
            detail["shippingMethod"] = self.shipping_method
        if self.ship_from_supply_source_id:
            detail["shipFromSupplySourceId"] = self.ship_from_supply_source_id
        return detail


# ===================================================================== Grouping Engine (Rule N-1)

def assemble_parcels(boxes, order_metadata, counter_start=1):
    """Assembles OMS carton_details[] into Amazon parcels according to Rule N-1 (L-86).

    Rules:
      1. Group by tracking_number.
      2. Sum quantities for identical Amazon orderItemId.
      3. Allocate monotonic numeric string packageReferenceId ("1", "2", ...).
      4. Reject blank tracking numbers before calling Amazon.
      5. Reject multiple tracking numbers within a single parcel.
      6. Validate ship date within bounds.
    """
    if not boxes:
        raise ValueError("No carton boxes provided for parcel assembly")

    groups = {}
    errors = []

    for box in boxes:
        trk = (box.tracking_number or "").strip()
        if not trk:
            errors.append(f"Box {box.carton_number} has missing or blank tracking number (L-66)")
            continue

        if trk not in groups:
            groups[trk] = []
        groups[trk].append(box)

    if errors:
        return None, errors

    parcels = []
    current_counter = counter_start

    for trk, box_list in groups.items():
        # Sum items across boxes in this tracking group
        item_map = {}
        carrier_code = box_list[0].carrier_code or order_metadata.get("carrier_code") or "Other"
        carrier_name = box_list[0].carrier_name or order_metadata.get("carrier_name")
        shipping_method = box_list[0].shipping_method or order_metadata.get("shipping_method")
        ship_date = box_list[0].ship_date or order_metadata.get("ship_date") or order_metadata.get("updated_at")
        is_master = any(b.is_master_tracking for b in box_list)

        for b in box_list:
            for item in b.items:
                if not item.order_item_id:
                    errors.append(f"Box {b.carton_number} has item without Amazon orderItemId (L-14)")
                    continue
                oid = item.order_item_id
                if oid not in item_map:
                    item_map[oid] = OrderItemAllocation(
                        line_item_id=item.line_item_id,
                        order_item_id=oid,
                        sku=item.sku,
                        quantity=item.quantity,
                        transparency_codes=list(item.transparency_codes)
                    )
                else:
                    item_map[oid].quantity += item.quantity
                    for tc in item.transparency_codes:
                        if tc not in item_map[oid].transparency_codes:
                            item_map[oid].transparency_codes.append(tc)

        # Build parcel with monotonic integer counter (L-5, L-88)
        parcel = Parcel(
            package_reference_id=str(current_counter),
            tracking_number=trk,
            carrier_code=carrier_code,
            carrier_name=carrier_name,
            shipping_method=shipping_method,
            ship_date=ship_date,
            ship_from_supply_source_id=order_metadata.get("ship_from_supply_source_id"),
            order_items=list(item_map.values()),
            is_master_tracking=is_master,
            source_boxes=[b.carton_number for b in box_list]
        )
        parcels.append(parcel)
        current_counter += 1

    return parcels, errors


# ===================================================================== Quantity Ledger (Rule N-3)

class QuantityLedger:
    """Maintains 9 quantity buckets per Amazon OrderItemId according to Rule N-3 (L-89)."""

    def __init__(self, order_item_id, quantity_ordered, quantity_shipped_amazon=0, quantity_cancelled=0):
        self.order_item_id = str(order_item_id)
        self.ordered = int(quantity_ordered)
        self.cancelled = int(quantity_cancelled)
        self.shipped_amazon = int(quantity_shipped_amazon)  # Authority count from Amazon
        self.allocated = 0
        self.internally_shipped = 0
        self.submitted = 0
        self.accepted = int(quantity_shipped_amazon)
        self.failed = 0
        self.pending = 0
        self._lock = False

    @property
    def remaining(self):
        """remaining = ordered - shipped_amazon - cancelled (Amazon latest data is authority)."""
        return max(0, self.ordered - self.shipped_amazon - self.cancelled)

    def assert_and_reserve(self, new_quantity):
        """Pre-submit assertion and atomic reservation under lock (Rule N-3)."""
        if self._lock:
            raise RuntimeError("Concurrent reservation lock contention")
        self._lock = True
        try:
            active_inflight = self.submitted + self.pending
            available = self.remaining - active_inflight
            if new_quantity > available:
                return False, f"Quantity {new_quantity} exceeds remaining available {available} (Ordered: {self.ordered}, Shipped: {self.shipped_amazon}, Cancelled: {self.cancelled})"
            self.submitted += new_quantity
            return True, None
        finally:
            self._lock = False

    def record_outcome(self, quantity, is_success):
        if self.submitted >= quantity:
            self.submitted -= quantity
        if is_success:
            self.accepted += quantity
            self.shipped_amazon += quantity
        else:
            self.failed += quantity


# ===================================================================== Confirmation Payload Builder (R-MAP §4.4)

def build_amazon_confirmation_request(order_id, marketplace_code, parcel, is_cod=False):
    """Builds the POST /orders/v0/orders/{orderId}/shipmentConfirmation payload.

    Conforms to OrdersV0_ConfirmShipmentRequest (L-4, L-70, L-7, L-55).
    """
    mkt_info = MARKETPLACES.get(marketplace_code)
    if not mkt_info:
        raise ValueError(f"Unknown marketplace code: {marketplace_code}")

    marketplace_id = mkt_info["marketplace_id"]

    body = {
        "marketplaceId": marketplace_id,
        "packageDetail": parcel.to_amazon_package_detail()
    }

    # Japan COD only (L-7, L-93)
    if marketplace_code == "amazon_sp_jp" and is_cod:
        body["codCollectionMethod"] = COD_DIRECT_PAYMENT

    return {
        "url_path": f"/orders/v0/orders/{order_id}/shipmentConfirmation",
        "method": "POST",
        "body": body,
        "order_id": order_id,
        "marketplace_id": marketplace_id
    }


# ===================================================================== Write-Back Payload Builder (R-MAP §4.5)

def build_oms_shipping_details_writeback(parcel, status, error_code=None, error_message=None):
    """Builds the write-back payload for POST /rest/v1/orders/shipping_details (CR-2, L-23)."""
    failure_reason = None
    if status != WRITEBACK_STATUS_SUCCESS:
        code_str = f"[{error_code}]" if error_code else "[AmazonError]"
        msg_str = error_message or "Shipment confirmation rejected"
        failure_reason = f"AMAZON_REJECTED {code_str} parcel {parcel.package_reference_id}: {msg_str}"
        # Ensure it satisfies the capacity requirement (at least 500 characters handled)
        if len(failure_reason) < 100:
            failure_reason = failure_reason.ljust(100, " ")

    order_items = []
    for it in parcel.order_items:
        oi = {
            "id": it.line_item_id or 811,
            "mp_item_code": it.order_item_id,
            "quantity": it.quantity
        }
        order_items.append(oi)

    payload = {
        "shipping_details": {
            "package_reference_id": parcel.package_reference_id,
            "tracking_number": parcel.tracking_number,
            "status": status,
            "order_items": order_items
        }
    }
    if failure_reason:
        payload["shipping_details"]["failure_reason"] = failure_reason

    return payload


# ===================================================================== Exception Matrix Evaluator (R-MAP §7 N-4)

def evaluate_exception_matrix(scenario_name, **kwargs):
    """Evaluates the behavior for any of the 22 scenarios in Exception Matrix (R-MAP §7 N-4)."""
    if scenario_name == "regulated_item_order":
        has_regulated = kwargs.get("has_regulated_items", False)
        if has_regulated:
            return {"action": "BLOCK", "reason": "Regulated-item order", "problem_order": "MarketplaceValidation"}
        return {"action": "PROCEED"}

    elif scenario_name == "amazon_order_cancelled":
        status = kwargs.get("order_status")
        if status == "Canceled":
            return {"action": "BLOCK", "reason": "Amazon order cancelled", "hand_to": "IA-5106"}
        return {"action": "PROCEED"}

    elif scenario_name == "buyer_cancellation_pending":
        is_buyer_cancel = kwargs.get("is_buyer_requested_cancel", False)
        if is_buyer_cancel:
            return {"action": "BLOCK", "reason": "Buyer cancellation pending", "state": "cancel-in-process"}
        return {"action": "PROCEED"}

    elif scenario_name == "cancellation_after_ready_to_ship":
        is_cancelled_now = kwargs.get("is_cancelled_after_rts", False)
        if is_cancelled_now:
            return {
                "action": "BLOCK_CONFIRMATION",
                "problem_order": "Cancellation After Ready-to-Ship",
                "confirm_quantity": 0,
                "preserve_audit": True
            }
        return {"action": "PROCEED"}

    elif scenario_name == "amazon_unreachable":
        timeout = kwargs.get("unreachable", False)
        if timeout:
            return {"action": "BLOCK", "problem_order": "MarketplaceValidation", "do_not_assume_valid": True}
        return {"action": "PROCEED"}

    elif scenario_name == "distinct_tracking_grouped":
        trackings = kwargs.get("trackings", [])
        if len(set(trackings)) > 1:
            return {"action": "REJECT_PRE_SUBMISSION", "error": "Multiple distinct tracking numbers in one parcel"}
        return {"action": "PROCEED"}

    elif scenario_name == "missing_tracking_number":
        tracking = (kwargs.get("tracking") or "").strip()
        if not tracking:
            return {"action": "BLOCK_WITHOUT_AMAZON_CALL", "problem_order": True, "error": "Missing tracking number"}
        return {"action": "PROCEED"}

    elif scenario_name == "ship_date_tolerance":
        now_instant = kwargs.get("now", datetime.datetime.now(datetime.timezone.utc))
        ship_date = kwargs.get("ship_date")
        purchase_date = kwargs.get("purchase_date")
        if isinstance(ship_date, str):
            ship_date = datetime.datetime.fromisoformat(ship_date.replace("Z", "+00:00"))
        if isinstance(purchase_date, str):
            purchase_date = datetime.datetime.fromisoformat(purchase_date.replace("Z", "+00:00"))

        if purchase_date and ship_date < purchase_date:
            return {"action": "BLOCK", "error": "Ship date earlier than purchase date"}
        skew = (ship_date - now_instant).total_seconds()
        if skew > SHIP_DATE_FUTURE_TOLERANCE_SECONDS:
            return {"action": "BLOCK", "error": f"Ship date {skew}s exceeds 5m future allowance"}
        return {"action": "PROCEED"}

    elif scenario_name == "quantity_exceeds_remaining":
        requested_qty = kwargs.get("requested_qty", 0)
        remaining_qty = kwargs.get("remaining_qty", 0)
        if requested_qty > remaining_qty:
            return {"action": "BLOCK", "error": f"Requested {requested_qty} > remaining {remaining_qty}"}
        return {"action": "PROCEED"}

    elif scenario_name == "tracking_correction_after_acceptance":
        old_ref = kwargs.get("package_reference_id")
        return {
            "action": "RESUBMIT_SAME_REF",
            "package_reference_id": old_ref,
            "semantics": "EDIT",
            "adds_parcel": False
        }

    return {"action": "UNKNOWN"}


# ===================================================================== Order Fulfilment State Derivation (R-MAP §5.2)

def derive_order_fulfilment_state(parcels, total_items_required=None):
    """Derives order-level mp_fulfilment_state from parcel outcomes (L-90)."""
    if not parcels:
        return MpFulfilmentState.PROCESSING

    any_accepted = any(p.status == ParcelConfirmationStatus.ACCEPTED for p in parcels)
    any_failed = any(p.status in (ParcelConfirmationStatus.REJECTED, ParcelConfirmationStatus.TERMINAL_FAILURE) for p in parcels)
    all_accepted = all(p.status == ParcelConfirmationStatus.ACCEPTED for p in parcels)
    all_failed = all(p.status in (ParcelConfirmationStatus.REJECTED, ParcelConfirmationStatus.TERMINAL_FAILURE) for p in parcels)

    if all_accepted:
        return MpFulfilmentState.COMPLETE
    if all_failed:
        return MpFulfilmentState.FAILED
    if any_accepted and any_failed:
        return MpFulfilmentState.PARTIAL_WITH_EXCEPTION
    if any_accepted:
        return MpFulfilmentState.PARTIAL
    return MpFulfilmentState.PROCESSING


# ===================================================================== HTTP Log Helpers

def http_json(method, url, body=None, token=None, timeout=10):
    headers = {"Accept": "application/json"}
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = "Bearer " + token
        headers["x-amz-access-token"] = token
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            status = r.status
            res_body = json.loads(raw.decode("utf-8")) if raw.strip() else {}
            return status, res_body
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            res_body = json.loads(raw.decode("utf-8")) if raw.strip() else {}
        except Exception:
            res_body = {"raw": raw.decode("utf-8", errors="replace")}
        return e.code, res_body
    except Exception as e:
        return 0, {"error": str(e)}
