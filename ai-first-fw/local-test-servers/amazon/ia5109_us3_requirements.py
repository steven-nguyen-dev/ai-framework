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

# 5.2 Order-level state after a partial confirmation (R-MAP 5.2, L-130, L-138)
#
# There is no marketplace-level order status vocabulary. The prior revision's five-value
# mp_fulfilment_state -- processing, partial, complete, partial_with_exception, failed -- is
# WITHDRAWN: it is a third vocabulary beside the OMS order status and the parcel state, and FR-31
# asks for neither. Partial is reached by the item subset on update_status, which OMS splits into a
# separate shipment itself (L-114, L-46); the per-parcel state of 5.1 sits on the box row (L-129).
ORDER_LEVEL_ROWS = {
    "none accepted": "the existing processing status, unchanged",
    "some accepted": "Partial, reached by the item subset splitting the shipment",
    "all accepted": "the existing completion progression, unchanged",
    "some accepted some failed": "Partial, with the failed parcel's own state on its box row",
    "all failed": "the existing processing status, every parcel REJECTED",
}


# Assembly block reasons -- EParcelBlockReason on the Java side, R-MAP 7 N-4
class EParcelBlockReason:
    MISSING_TRACKING_NUMBER = "MISSING_TRACKING_NUMBER"
    MISSING_AMAZON_ORDER_ITEM_ID = "MISSING_AMAZON_ORDER_ITEM_ID"
    MISSING_AMAZON_ORDER_NUMBER = "MISSING_AMAZON_ORDER_NUMBER"
    QUANTITY_NOT_POSITIVE = "QUANTITY_NOT_POSITIVE"
    MISSING_CARRIER_MAPPING = "MISSING_CARRIER_MAPPING"
    MARKETPLACE_MISMATCH = "MARKETPLACE_MISMATCH"
    SHIP_DATE_TOO_FAR_AHEAD = "SHIP_DATE_TOO_FAR_AHEAD"
    SHIP_DATE_BEFORE_PURCHASE = "SHIP_DATE_BEFORE_PURCHASE"


# Pre-submit gate block reasons -- EGateBlockReason on the Java side, R-MAP 4.2 and 7 N-4
class EGateBlockReason:
    ORDER_CANCELLED = "ORDER_CANCELLED"
    REGULATED_ITEMS = "REGULATED_ITEMS"
    NOT_SELLER_FULFILLED = "NOT_SELLER_FULFILLED"
    BUYER_CANCELLATION_PENDING = "BUYER_CANCELLATION_PENDING"
    MARKETPLACE_VALIDATION_UNAVAILABLE = "MARKETPLACE_VALIDATION_UNAVAILABLE"
    QUANTITY_EXCEEDS_REMAINING = "QUANTITY_EXCEEDS_REMAINING"

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
    """One Amazon order item inside one parcel.

    The Amazon id comes from mp_item_codes[0] and never from line_item_id, which import blanks to
    the string "0" at six sites, nor from the seller SKU (L-119, L-134). An absent id and a
    non-positive quantity are both kept as they arrived so assembly can block on them rather than
    defaulting them into something sendable (L-14, L-81).
    """

    def __init__(self, line_item_id, order_item_id, sku, quantity, transparency_codes=None):
        self.line_item_id = int(line_item_id) if line_item_id is not None else None
        self.order_item_id = str(order_item_id) if order_item_id else None  # Amazon OrderItemId
        self.sku = str(sku) if sku else None
        self.quantity = quantity
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
    """One row of the ready-to-ship event's carton_details[] (C-14, L-111, L-175).

    package_id is OMS's own per-package identifier and is the package reference when it is present.
    It is null on 105,739 of 105,739 rows over seven days (L-173), so the counter path of rule N-2
    is the live one -- a null must stay null here rather than being defaulted into a reference OMS
    never allocated.
    """

    def __init__(self, carton_number, tracking_number, is_master_tracking=False,
                 ship_date=None, items=None, carrier_code=None, carrier_name=None,
                 shipping_method=None, package_id=None):
        self.carton_number = str(carton_number)
        self.tracking_number = str(tracking_number).strip() if tracking_number else ""
        self.is_master_tracking = bool(is_master_tracking)
        self.ship_date = ship_date
        self.items = items or []
        self.carrier_code = carrier_code
        self.carrier_name = carrier_name
        self.shipping_method = shipping_method
        self.package_id = package_id


class BlockedParcel:
    """A parcel assembly refused to build, carrying why -- BlockedParcel on the Java side.

    Blocking one parcel leaves its siblings alone: the good boxes of an event still reach Amazon
    (L-14, L-89).
    """

    def __init__(self, reason, detail, tracking_number=None):
        self.reason = reason
        self.detail = detail
        self.tracking_number = tracking_number

    def to_dict(self):
        return {"reason": self.reason, "detail": self.detail, "tracking_number": self.tracking_number}


class GateDecision:
    """The synchronous pre-submit gate's answer -- GateDecision on the Java side (C-7, C-25, C-26)."""

    def __init__(self, blocked, reason=None, detail=None, blocked_order_item_ids=None):
        self.blocked = bool(blocked)
        self.reason = reason
        self.detail = detail
        self.blocked_order_item_ids = blocked_order_item_ids or []


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


# ===================================================================== Carrier resolution (R-MAP 5.3)

def resolve_carrier(shipping_provider=None, marketplace_carrier_code=None,
                    logistic_partner_name=None, shipping_type=None):
    """Resolves carrierCode, carrierName and shippingMethod in the order R-MAP 5.3 requires.

    shipping_provider is read first and marketplace_carrier_code is an override that applies only
    when it is non-empty, because on the one captured live payload marketplace_carrier_code,
    ewms_carrier_code and shipping_method.marketplace_code all arrive empty and shipping_provider is
    the only carrier identity present (L-146). logistic_partner_name is null on that same payload,
    so the name falls back to shipping_provider (L-187). An unrecognised carrier goes as "Other"
    with its name mandatory (L-6, L-91); SELF_DELIVERY is the one named case; nothing at all is a
    configuration error and blocks the parcel (L-91).

    @return {@code (carrier_code, carrier_name, shipping_method)}, or {@code (None, None, None)}
            when no carrier identity resolves at all
    """
    provider = (shipping_provider or "").strip()
    override = (marketplace_carrier_code or "").strip()
    partner = (logistic_partner_name or "").strip()
    service = (shipping_type or "").strip()

    if override:
        return override, (partner or provider or override), (service or provider or None)

    if provider.upper() == "SELF_DELIVERY":
        return GENERIC_CARRIER_CODE, "Self Delivery", (service or None)

    if not provider:
        return None, None, None

    if provider.upper() in [c.upper() for c in STANDARD_CARRIERS]:
        return provider, (partner or provider), (service or provider)

    return GENERIC_CARRIER_CODE, (partner or provider), (service or provider)


# ===================================================================== Grouping Engine (Rule N-1)

def _parse_instant(value):
    if value is None or isinstance(value, datetime.datetime):
        return value
    return datetime.datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _as_iso(value):
    if value is None:
        return None
    if isinstance(value, datetime.datetime):
        return value.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return str(value)


def assemble_parcels(boxes, order_metadata, counter_start=1):
    """Assembles a ready-to-ship event into one Amazon parcel per distinct tracking number.

    Rule N-1: group by tracking number, sum the quantity per Amazon order item within a group, never
    merge distinct tracking numbers, never send a blank one (L-86, L-66). With no carton_details --
    which is every payload on the wire today (L-175) -- exactly one parcel is built from the line
    items and the shipment-level tracking number, by passing {@code boxes} empty and the line items
    on {@code order_metadata["line_items"]}.

    Rule N-2: the package reference is the box's own package_id serialised as digits when OMS sends
    one, and a per-order counter otherwise, which is the live path (L-163, L-173, L-5).

    Assembly is pure: it makes no Amazon call and reads no state. The over-confirmation guard of
    rule N-3 is not here -- it needs Amazon's own QuantityShipped and lives in {@code check_quantities}
    (L-9, L-10).

    @param boxes carton rows, empty or None for the no-box-list path
    @param order_metadata the event and store context; see the module docstring for the keys read
    @param counter_start first value of the allocated reference counter, must be > 0
    @return {@code (parcels, blocked)} -- a blocked parcel never suppresses its siblings
    """
    meta = order_metadata or {}
    blocked = []

    store_marketplace = meta.get("store_marketplace_code")
    event_marketplace = meta.get("event_marketplace_code")
    if store_marketplace and event_marketplace and store_marketplace != event_marketplace:
        return [], [BlockedParcel(
            EParcelBlockReason.MARKETPLACE_MISMATCH,
            "shipment carries %s, store is %s (L-31, L-55)" % (event_marketplace, store_marketplace))]

    if not meta.get("amazon_order_id", "sentinel"):
        return [], [BlockedParcel(
            EParcelBlockReason.MISSING_AMAZON_ORDER_NUMBER,
            "marketplace_order_number is absent; the OMS order number is never substituted (L-67)")]

    if not boxes:
        boxes = [CartonBox(
            carton_number=meta.get("shipment_number", "SHP-1"),
            tracking_number=meta.get("tracking_number") or "",
            ship_date=meta.get("ship_date") or meta.get("updated_at"),
            items=list(meta.get("line_items") or []),
            package_id=meta.get("package_id"),
        )]

    groups = {}
    order = []
    for box in boxes:
        trk = (box.tracking_number or "").strip()
        if not trk:
            blocked.append(BlockedParcel(
                EParcelBlockReason.MISSING_TRACKING_NUMBER,
                "box %s carries no tracking number; the order number is never substituted (L-66)" % box.carton_number,
                tracking_number=None))
            continue
        if trk not in groups:
            groups[trk] = []
            order.append(trk)
        groups[trk].append(box)

    purchased_at = _parse_instant(meta.get("purchased_at"))
    submitting_at = _parse_instant(meta.get("submitting_at"))
    skew_seconds = meta.get("skew_seconds", SHIP_DATE_FUTURE_TOLERANCE_SECONDS)

    parcels = []
    counter = counter_start

    for trk in order:
        box_list = groups[trk]
        head = box_list[0]

        carrier_code = head.carrier_code or meta.get("carrier_code")
        carrier_name = head.carrier_name or meta.get("carrier_name")
        shipping_method = head.shipping_method or meta.get("shipping_method")
        if not carrier_code:
            carrier_code, carrier_name, shipping_method = resolve_carrier(
                meta.get("shipping_provider"), meta.get("marketplace_carrier_code"),
                meta.get("logistic_partner_name"), meta.get("shipping_type"))
        if not carrier_code:
            blocked.append(BlockedParcel(
                EParcelBlockReason.MISSING_CARRIER_MAPPING,
                "no carrier identity resolves; \"Other\" still needs a name (L-91)", trk))
            continue
        if carrier_code == GENERIC_CARRIER_CODE and not carrier_name:
            blocked.append(BlockedParcel(
                EParcelBlockReason.MISSING_CARRIER_MAPPING,
                "carrierCode Other requires carrierName (L-6, L-91)", trk))
            continue

        ship_date = head.ship_date or meta.get("ship_date") or meta.get("updated_at")
        ship_instant = _parse_instant(ship_date)
        if ship_instant is not None and purchased_at is not None and ship_instant < purchased_at:
            blocked.append(BlockedParcel(
                EParcelBlockReason.SHIP_DATE_BEFORE_PURCHASE,
                "ship date %s precedes the purchase instant %s (L-8)" % (_as_iso(ship_instant), _as_iso(purchased_at)),
                trk))
            continue
        if ship_instant is not None and submitting_at is not None:
            skew = (ship_instant - submitting_at).total_seconds()
            if skew > skew_seconds:
                blocked.append(BlockedParcel(
                    EParcelBlockReason.SHIP_DATE_TOO_FAR_AHEAD,
                    "ship date is %ds ahead of the submit, past the %ds allowance; this bound is ours, "
                    "not Amazon's (L-45, L-52)" % (int(skew), int(skew_seconds)),
                    trk))
                continue

        item_map = {}
        item_order = []
        fault = None
        for box in box_list:
            for item in box.items:
                if not item.order_item_id:
                    fault = BlockedParcel(
                        EParcelBlockReason.MISSING_AMAZON_ORDER_ITEM_ID,
                        "no Amazon order-item id on %s; line_item_id is blanked to \"0\" at import "
                        "and the SKU is never a fallback (L-119, L-14)" % (item.sku or "an unnamed line"),
                        trk)
                    break
                if item.quantity is None or int(item.quantity) <= 0:
                    fault = BlockedParcel(
                        EParcelBlockReason.QUANTITY_NOT_POSITIVE,
                        "quantity %r on %s; Amazon deducts what we send, and zero deducts nothing "
                        "(L-81)" % (item.quantity, item.order_item_id),
                        trk)
                    break
                oid = item.order_item_id
                if oid not in item_map:
                    item_map[oid] = OrderItemAllocation(
                        line_item_id=item.line_item_id, order_item_id=oid, sku=item.sku,
                        quantity=int(item.quantity),
                        transparency_codes=list(item.transparency_codes))
                    item_order.append(oid)
                else:
                    item_map[oid].quantity += int(item.quantity)
                    for code in item.transparency_codes:
                        if code not in item_map[oid].transparency_codes:
                            item_map[oid].transparency_codes.append(code)
            if fault:
                break
        if fault:
            blocked.append(fault)
            continue

        if head.package_id is not None:
            reference = str(int(head.package_id))
        else:
            reference = str(counter)
            counter += 1

        parcels.append(Parcel(
            package_reference_id=reference,
            tracking_number=trk,
            carrier_code=carrier_code,
            carrier_name=carrier_name,
            shipping_method=shipping_method,
            ship_date=_as_iso(ship_instant) if ship_instant is not None else None,
            ship_from_supply_source_id=meta.get("ship_from_supply_source_id"),
            order_items=[item_map[o] for o in item_order],
            is_master_tracking=any(b.is_master_tracking for b in box_list),
            source_boxes=[b.carton_number for b in box_list]))

    return parcels, blocked


# ===================================================================== Pre-submit gate (R-MAP 4.2, 7 N-3, N-4)

def evaluate_gate(order_payload, order_items_payload=None):
    """Reads Amazon's own answer about the order immediately before we tell Amazon it shipped.

    The pre-ready-to-ship gate belongs to OMS (L-131); this is the second line of defence, the one
    that closes the FR-5 race OMS cannot -- an order cancelled between the OMS gate and our submit
    (L-87). Regulated blocks the whole order and never a line, because Amazon states the flag at
    header level only (L-20).

    @param order_payload the {@code payload} object of {@code GET /orders/v0/orders/{orderId}}
    @param order_items_payload the {@code payload} object of the {@code orderItems} read, optional
    @return a blocked decision carrying its reason, or an unblocked one
    """
    order = order_payload or {}

    if order.get("OrderStatus") in ("Canceled", "Cancelled"):
        return GateDecision(True, EGateBlockReason.ORDER_CANCELLED,
                            "Amazon reports the order %s; hand to IA-5106 (L-87)" % order.get("OrderStatus"))

    if order.get("HasRegulatedItems") is True:
        return GateDecision(True, EGateBlockReason.REGULATED_ITEMS,
                            "HasRegulatedItems is a header-level flag, so no line-level split is possible (L-20)")

    channel = order.get("FulfillmentChannel")
    if channel and channel != "MFN":
        return GateDecision(True, EGateBlockReason.NOT_SELLER_FULFILLED,
                            "FulfillmentChannel is %s; this story confirms seller-fulfilled shipments only (L-87)" % channel)

    pending = []
    for line in ((order_items_payload or {}).get("OrderItems") or []):
        cancel = line.get("BuyerRequestedCancel") or {}
        if str(cancel.get("IsBuyerRequestedCancel", "")).lower() == "true":
            pending.append(line.get("OrderItemId"))
    if pending:
        return GateDecision(True, EGateBlockReason.BUYER_CANCELLATION_PENDING,
                            "buyer cancellation pending; route to cancel-in-process (L-87)", pending)

    return GateDecision(False)


def gate_unreachable(detail):
    """Amazon unreachable is an outcome, never a licence to assume the order is still valid (L-87)."""
    return GateDecision(True, EGateBlockReason.MARKETPLACE_VALIDATION_UNAVAILABLE, detail)


def check_quantities(order_items_payload, parcel_quantities):
    """Asserts each parcel quantity against what Amazon itself says still remains.

    Amazon's QuantityShipped, re-read immediately before the submit, wins over anything we believe:
    ours is a belief and Amazon's is the fact (L-9, L-10, L-89).

    @param order_items_payload the {@code payload} object of the {@code orderItems} read
    @param parcel_quantities Amazon order-item id to the quantity this parcel carries
    @return a blocked decision naming the items that exceed, or an unblocked one
    """
    remaining = {}
    for line in ((order_items_payload or {}).get("OrderItems") or []):
        ordered = int(line.get("QuantityOrdered") or 0)
        shipped = int(line.get("QuantityShipped") or 0)
        remaining[line.get("OrderItemId")] = max(0, ordered - shipped)

    exceeded = [item for item, quantity in (parcel_quantities or {}).items()
                if quantity > remaining.get(item, 0)]
    if exceeded:
        return GateDecision(
            True, EGateBlockReason.QUANTITY_EXCEEDS_REMAINING,
            "; ".join("%s asks %d of %d remaining" % (i, parcel_quantities[i], remaining.get(i, 0))
                      for i in exceeded),
            exceeded)
    return GateDecision(False)


def reconcile_unknown_outcome(amazon_quantity_shipped, parcel_quantity):
    """Decides an unknown outcome from Amazon's count rather than resubmitting blind (C-25, L-90).

    @return {@code ACCEPTED} when Amazon's count covers the parcel, {@code RETRY_PENDING} otherwise --
            and a retry then reuses the same package reference (L-88)
    """
    if amazon_quantity_shipped >= parcel_quantity:
        return ParcelConfirmationStatus.ACCEPTED
    return ParcelConfirmationStatus.RETRY_PENDING


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

def build_oms_shipping_details_writeback(parcel, status, error_code=None, error_message=None,
                                         oms_order_id=None):
    """Builds one parcel's write-back for POST /rest/v1/orders/shipping_details, R-MAP 4.5 row for row.

    The names are OMS's own. Row 2 is {@code package_id}, which is what OMS already calls a package
    identifier on update_packages, and not a new name (L-113). Row 7 is {@code item_codes[]}, the
    array the order item already carries, because {@code line_item_id} cannot serve -- import blanks
    it to the string "0" (L-119). Rows 2, 6 and 7 are absent from the OMS contract today and travel
    in parallel as CR-2, which under the working principle is a change to request and not a blocker
    (L-23, L-39).

    @param status one of {@code success} or {@code failure}, R-MAP 5.4
    @return the request body, with failure_reason present only on a failure
    """
    failure_reason = None
    if status != WRITEBACK_STATUS_SUCCESS:
        code_str = "[%s]" % error_code if error_code else "[AmazonError]"
        msg_str = error_message or "Shipment confirmation rejected"
        failure_reason = "AMAZON_REJECTED %s parcel %s: %s" % (
            code_str, parcel.package_reference_id, msg_str)

    order_items = []
    for item in parcel.order_items:
        order_items.append({
            "id": item.line_item_id,
            "item_codes": [item.order_item_id] if item.order_item_id else [],
            "quantity": item.quantity,
        })

    details = {
        "package_id": parcel.package_reference_id,
        "tracking_number": parcel.tracking_number,
        "status": status,
        "order_items": order_items,
    }
    if oms_order_id is not None:
        details["id"] = oms_order_id
    if failure_reason:
        details["failure_reason"] = failure_reason

    return {"shipping_details": details}


def build_oms_blocked_writeback(blocked, oms_order_id=None):
    """Builds the write-back for a parcel assembly refused, R-MAP 4.5 and the second C-17 site.

    The tracking number stays whatever the carrier actually returned, which for a blocked parcel is
    nothing at all. publishRtsDetails falls back to getOrderNumber() today, recording a shipment
    that never had a tracking number under a number that is not one (L-66).
    """
    details = {
        "package_id": None,
        "tracking_number": blocked.tracking_number,
        "status": WRITEBACK_STATUS_FAILURE,
        "failure_reason": "AMAZON_BLOCKED [%s]: %s" % (blocked.reason, blocked.detail),
        "order_items": [],
    }
    if oms_order_id is not None:
        details["id"] = oms_order_id
    return {"shipping_details": details}


# ===================================================================== Order-level outcome (R-MAP 5.2)

def order_level_outcome(parcels):
    """Names which row of R-MAP 5.2 an order's parcels land on.

    It returns a description and never a status: there is no marketplace-level order status to set.
    Partial is reached by the item subset on update_status, which OMS splits into a separate
    shipment itself (L-114, L-46); the parcel state of 5.1 sits on the box row (L-129, L-130). The
    five-value mp_fulfilment_state the prior revision proposed is withdrawn (L-138).

    @return the key into {@code ORDER_LEVEL_ROWS} the parcels satisfy
    """
    if not parcels:
        return "none accepted"

    failed_states = (ParcelConfirmationStatus.REJECTED, ParcelConfirmationStatus.TERMINAL_FAILURE)
    accepted = [p for p in parcels if p.status == ParcelConfirmationStatus.ACCEPTED]
    failed = [p for p in parcels if p.status in failed_states]

    if len(accepted) == len(parcels):
        return "all accepted"
    if len(failed) == len(parcels):
        return "all failed"
    if accepted and failed:
        return "some accepted some failed"
    if accepted:
        return "some accepted"
    return "none accepted"


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
