#!/usr/bin/env python3
"""Amazon SP-API to Anchanto OMS Cancellation Transformer (IA-5106 User Story 4).

A local stand-in for the JPluger Amazon integration, implementing the mappings,
defect fixes, and validations specified in Jira IA-5106, Anchanto OMS Swagger,
and Amazon Selling Partner API specifications.
"""

import copy
import datetime
import json
import re
import sys
import os

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

# Import requirements and constants
import requirements as req


class CancellationTransformer:
    """Implements all ingress and egress transformations for Amazon Buyer Cancellation."""

    # -----------------------------------------------------------------
    # Ingress 1: Subscription Setup (C-AMZ OrderChangeNotification; JIRA-IA5106 FR-25)
    # -----------------------------------------------------------------
    @staticmethod
    def build_subscription_payload(store_code, change_types=None, include_marketplace_ids=False):
        """Builds Amazon POST /notifications/v1/subscriptions payload.

        Enforces:
          - notificationType is 'ORDER_CHANGE' (JIRA-IA5106 FR-25; C-AMZ)
          - orderChangeTypes filter includes BuyerRequestedChange and OrderStatusChange (C-AMZ schema)
          - marketplaceIds filter is OMITTED (C-AMZ SP-API notifications contract)
        """
        if change_types is None:
            change_types = list(req.SUBSCRIPTION_CHANGE_TYPES)

        payload = {
            "payloadVersion": "1.0",
            "destinationId": f"dest-sqs-{store_code}",
            "processingDirective": {
                "eventFilter": {
                    "eventFilterType": "ORDER_CHANGE",
                    "orderChangeTypes": change_types,
                }
            }
        }
        if include_marketplace_ids:
            # Strictly forbidden by Amazon at runtime for ORDER_CHANGE (C-AMZ)
            payload["processingDirective"]["eventFilter"]["marketplaceIds"] = ["ATVPDKIKX0DER"]
        return payload

    # -----------------------------------------------------------------
    # Ingress 2: Notification Trigger Parser (JIRA-IA5106 FR-1, FR-25; C-AMZ)
    # -----------------------------------------------------------------
    @staticmethod
    def parse_notification_trigger(notification_doc):
        """Parses inbound ORDER_CHANGE notification doc into trigger context.

        Treated as a trigger, never as a source of record (JIRA-IA5106 §16 FR-25).
        Parses IsBuyerRequestedCancel as string per Rule N-2 (C-AMZ Orders v0 schema; JIRA-IA5106 FR-1, FR-2).
        """
        payload = notification_doc.get("Payload", {}).get("OrderChangeNotification", {})
        trigger = payload.get("OrderChangeTrigger", {})
        summary = payload.get("Summary", {})

        items = []
        for it in summary.get("OrderItems", []):
            items.append({
                "order_item_id": str(it.get("OrderItemId", "")),
                "seller_sku": it.get("SellerSKU", ""),
                "status": it.get("OrderItemStatus", ""),
                "quantity": it.get("Quantity", 0),
                "quantity_shipped": it.get("QuantityShipped", 0),
                # Rule N-2: parse string flag
                "is_buyer_requested_cancel": req.parse_is_buyer_requested_cancel(
                    it.get("IsBuyerRequestedCancel")
                ),
            })

        return {
            "amazon_order_id": payload.get("AmazonOrderId"),
            "order_change_type": payload.get("OrderChangeType"),
            "time_of_order_change": trigger.get("TimeOfOrderChange"),
            "change_reason": trigger.get("ChangeReason"),
            "marketplace_id": summary.get("MarketplaceId"),
            "order_status": summary.get("OrderStatus"),
            "fulfillment_type": summary.get("FulfillmentType"),
            "cancel_notify_date": summary.get("CancelNotifyDate"),
            "order_items": items,
        }

    # -----------------------------------------------------------------
    # Defect Fix C-15: Status Mapping (Amazon Orders v0 & 2026-01-01; JIRA-IA5106 §9, §19; CTX-NOTE)
    # -----------------------------------------------------------------
    @staticmethod
    def map_order_status(source_status):
        """Maps Amazon order status to OMS status.

        Replaces commented-out mapOrderStatus. Handles both PascalCase (v0)
        and UPPER_SNAKE_CASE (2026-01-01).
        """
        if not source_status:
            return "active"
        return req.ORDER_STATUS_MAP.get(source_status, "active")

    # -----------------------------------------------------------------
    # Defect Fixes C-13 & C-14: Line Cancellation Mapping (JIRA-IA5106 §12 FR-11, FR-12, AC-10; CTX-NOTE lines 27-29)
    # -----------------------------------------------------------------
    @staticmethod
    def map_cancelled_items(amazon_order_items, references, cancelled_item_ids):
        """Maps cancelled order items to OMS ItemReferences.

        Fixes:
          - C-13: Second loop removed. Only marks lines in cancelled_item_ids as cancelled!
          - C-14: Correlates by OrderItemId (ItemReference.getItemCodes()), not list position!
        """
        ref_map = {}
        for r in references:
            codes = r.get("item_codes", [])
            for c in codes:
                ref_map[str(c)] = r

        updated_refs = copy.deepcopy(references)
        cancelled_set = set(str(cid) for cid in cancelled_item_ids)

        for ref in updated_refs:
            # Match by order item code
            codes = ref.get("item_codes", [])
            is_cancelled = any(str(c) in cancelled_set for c in codes)
            if is_cancelled:
                ref["reference_id"] = "CANCELLED"
                ref["status"] = "Cancelled"
            else:
                # Non-cancelled lines remain active (C-13 fix: NO second loop marking all lines cancelled!)
                ref["reference_id"] = ref.get("reference_id", "ACTIVE")
                ref["status"] = ref.get("status", "Processing")

        return updated_refs

    # -----------------------------------------------------------------
    # Egress 1: CR-1 Hold Payload Builder (JIRA-IA5106 FR-1, FR-3, FR-32, AC-1)
    # -----------------------------------------------------------------
    @staticmethod
    def build_cancel_request_payload(order_number, store_code, marketplace_code, marketplace_id,
                                     detail_order_2026, time_of_order_change=None):
        """Builds POST /rest/v1/orders/{id}/cancel_request payload.

        Enforces:
          - requester is 'BUYER' (JIRA-IA5106 FR-1)
          - request_reason is nullable (JIRA-IA5106 FR-1, §20, AC-24)
          - mp_request_key is 5-part composite key (JIRA-IA5106 §17 FR-32)
          - item_quantity is OMITTED (JIRA-IA5106 FR-2, FR-14, AC-3)
        """
        order_items = []
        raw_items = detail_order_2026.get("orderItems", [])
        overall_reason = None
        first_item_id = ""

        timestamp = time_of_order_change or detail_order_2026.get("lastUpdateDate") or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        for idx, it in enumerate(raw_items):
            item_id = str(it.get("orderItemId", ""))
            if not first_item_id:
                first_item_id = item_id
            cancellation = it.get("cancellation", {})
            req_info = cancellation.get("cancellationRequest")
            if req_info:
                reason = req_info.get("cancelReason")
                if reason and not overall_reason:
                    overall_reason = reason
                order_items.append({
                    "id": it.get("oms_line_id", 1000 + idx),
                    "item_codes": [item_id],
                    "reason": reason,
                    # NO item_quantity!
                })

        key = req.make_idempotency_key(
            store_code=store_code,
            marketplace_id=marketplace_id,
            amazon_order_id=order_number,
            order_item_id=first_item_id or "ALL",
            time_of_order_change=timestamp
        )

        return {
            "query": {"marketplace_code": marketplace_code},
            "body": {
                "requester": "BUYER",
                "request_reason": overall_reason,
                "mp_request_timestamp": timestamp,
                "mp_request_key": key,
                "order_items": order_items,
            }
        }

    # -----------------------------------------------------------------
    # Egress 2: CR-3 Restore Payload Builder (JIRA-IA5106 §14 FR-17, FR-18, AC-7)
    # -----------------------------------------------------------------
    @staticmethod
    def build_cancel_restore_payload(order_items_to_restore, request_key, resolution="REJECTED",
                                    outcome_timestamp=None):
        """Builds POST /rest/v1/orders/{id}/cancel_request/restore payload.

        Enforces:
          - resolution in REJECTED, WITHDRAWN, EXPIRED (JIRA-IA5106 §9, FR-17, FR-18)
          - echoes mp_request_key
          - carries item_codes of lines to restore
        """
        if resolution not in req.CR3_RESOLUTION_ENUM:
            raise ValueError(f"Invalid resolution: {resolution}. Must be one of {req.CR3_RESOLUTION_ENUM}")

        ts = outcome_timestamp or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        items = []
        for it in order_items_to_restore:
            codes = it if isinstance(it, list) else [str(it)]
            items.append({"item_codes": codes})

        return {
            "body": {
                "resolution": resolution,
                "mp_outcome_timestamp": ts,
                "mp_request_key": request_key,
                "order_items": items,
            }
        }

    # -----------------------------------------------------------------
    # Egress 3: CR-8 / Live Confirmed Cancellation Builder (C-OMS /rest/v1/orders/{id}/cancel; JIRA-IA5106 FR-10, FR-15)
    # -----------------------------------------------------------------
    @staticmethod
    def build_confirmed_cancel_payload(order_number, store_code, marketplace_code,
                                      confirmed_items, ledger_items):
        """Builds POST /rest/v1/orders/{id}/cancel payload.

        Rule N-1 (JIRA-IA5106 FR-12): Only cancels full remaining quantity (mp_remaining_quantity).
        Never calculates or derives a partial sub-line quantity.
        """
        ledger_by_code = {}
        for line in ledger_items:
            for c in line.get("item_codes", []):
                ledger_by_code[str(c)] = line

        order_items = []
        overall_reason = "BuyerCanceled"

        for it in confirmed_items:
            code = str(it.get("order_item_id", ""))
            ledger_line = ledger_by_code.get(code)
            if not ledger_line:
                continue

            rem_qty = ledger_line.get("mp_remaining_quantity", 0)
            if rem_qty <= 0:
                # Line has no remaining quantity; already fully shipped or cancelled
                continue

            reason = it.get("cancel_reason") or overall_reason
            order_items.append({
                "id": ledger_line.get("id", 2866997),
                "item_codes": [code],
                "item_quantity": rem_qty,  # Send FULL remaining quantity (N-1)
                "reason": reason,
            })

        return {
            "query": {
                "marketplace_code": marketplace_code,
                "cancellation_reason": overall_reason,
            },
            "body": {
                "order_items": order_items,
            }
        }

    # -----------------------------------------------------------------
    # Flow 5: Pre-Ready-to-Ship Gate Evaluator (JIRA-IA5106 §15 FR-20, FR-21, FR-22, AC-15, AC-16)
    # -----------------------------------------------------------------
    @staticmethod
    def evaluate_pre_rts_gate(amazon_order_detail, bulk_check_result):
        """Evaluates whether an order can transition to READY_TO_SHIP.

        Returns (can_transition, action, problem_reason)
        """
        # 1. Check Amazon order detail for active cancellation request
        has_pending_request = False
        has_execution = False
        for it in amazon_order_detail.get("orderItems", []):
            cancellation = it.get("cancellation", {})
            if cancellation.get("cancellationRequest") and not cancellation.get("cancellationExecution"):
                has_pending_request = True
            if cancellation.get("cancellationExecution"):
                has_execution = True

        if has_pending_request:
            # Hold order, block RTS transition (AC-15, FR-20)
            return False, "HOLD", None

        if has_execution:
            # Confirmed cancellation discovered during pre-RTS check
            return False, "CANCEL", None

        # 2. Check bulk_cancellation_check result
        if not bulk_check_result or not bulk_check_result.get("success", True):
            # Unreachable or validation failure (AC-16, FR-22)
            return False, "RAISE_PROBLEM", req.PROBLEM_REASON_VALIDATION_PENDING

        status = str(bulk_check_result.get("status", "")).lower()
        if status in ("pending", "cancelled", "cancel_requested"):
            return False, "HOLD", None

        return True, "TRANSITION", None

    # -----------------------------------------------------------------
    # Exception & Boundary Validations (JIRA-IA5106 §20 Error Matrix)
    # -----------------------------------------------------------------
    @staticmethod
    def validate_cancellation_mapping(references, cancelled_item_ids):
        """Validates that all cancelled item IDs correlate to known OMS ItemReferences.

        If unresolvable, returns (False, missing_ids, PROBLEM_REASON_MAPPING_FAILURE).
        """
        known_codes = set()
        for r in references:
            for c in r.get("item_codes", []):
                known_codes.add(str(c))

        missing = [str(cid) for cid in cancelled_item_ids if str(cid) not in known_codes]
        if missing:
            return False, missing, req.PROBLEM_REASON_MAPPING_FAILURE
        return True, [], None

    @staticmethod
    def validate_store_marketplace(order_store_code, order_marketplace_code,
                                   update_store_code, update_marketplace_code):
        """Enforces store and marketplace isolation (JIRA-IA5106 §17 FR-32, §21 AC-23)."""
        is_match = (
            order_store_code == update_store_code
            and order_marketplace_code == update_marketplace_code
        )
        alert_target = req.ALERT_INTEGRATION_DASHBOARD if not is_match else None
        return is_match, alert_target

    @staticmethod
    def handle_order_not_found(amazon_order_id):
        """Error Matrix Scenario 3: Amazon order not found in OMS."""
        return {
            "amazon_order_id": amazon_order_id,
            "exception_status": req.EXCEPTION_RECONCILIATION_PENDING,
            "action": "STORE_FOR_RECONCILIATION",
        }

    @staticmethod
    def evaluate_status_restoration(order_current_status, previous_status, reservation_state):
        """Evaluates whether previous status can be restored or routes to Problem state (FR-19)."""
        if reservation_state == "UNAVAILABLE":
            return False, req.PROBLEM_ORDER_OUT_OF_STOCK, order_current_status
        if not previous_status:
            return False, req.PROBLEM_REASON_STATUS_UNAVAILABLE, order_current_status
        return True, None, previous_status

    @staticmethod
    def evaluate_state_transition(current_status, requested_transition):
        """Evaluates state transitions the gate must refuse (FR-20, FR-24)."""
        # Transitions from Cancel to anything else are refused
        if current_status == "Cancel":
            return False, "REFUSED_ALREADY_CANCELLED"
        # Transitions to Hold from Shipped are refused (handled by returns)
        if current_status == "Shipped" and requested_transition == "Cancel_in_process":
            return False, "REFUSED_ALREADY_SHIPPED"
        # Transitions to Ready_To_Ship when order is on hold are refused
        if current_status in ("Cancel_in_process", "Hold_Buyer_Cancel") and requested_transition == "READY_TO_SHIP":
            return False, "REFUSED_ON_HOLD"
        return True, "ALLOWED"

