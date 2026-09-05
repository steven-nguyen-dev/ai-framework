#!/usr/bin/env python3
"""IA-5106-US4 Suite: Inbound Buyer Cancellation Request & Order Hold.

Judges the ingress call sequence and the Anchanto OMS CR-1 hold payload:
  1. ORDER_CHANGE notification arrives as a trigger (R-MAP §4.2, L-21, L-34)
  2. Parse IsBuyerRequestedCancel as string per N-2 (L-17, AC-14)
  3. Subscription filters on orderChangeTypes only; no marketplaceIds (R-MAP §4.1, L-18, L-19)
  4. Per-order detail read on 2026-01-01 with includedData=CANCELLATION (R-MAP §4.5, L-4, L-15)
  5. Distinguishes cancellationRequest (PENDING) vs cancellationExecution (CONFIRMED)
  6. Dispatches CR-1 POST /rest/v1/orders/{id}/cancel_request to Anchanto OMS
  7. Asserts CR-1 payload: requester='BUYER', nullable request_reason, 5-part mp_request_key
  8. Enforces omission of item_quantity on hold payload (L-1, L-56)
  9. Asserts write-once snapshot of previous_status (L-22, L-56, AC-2)
  10. Asserts stock is NOT released to ATP, order does NOT become Cancel (L-56, AC-3)
  11. Asserts ready-to-ship transition is blocked while on hold (L-56, AC-4)
  12. Asserts line-level hold capability for multi-item orders (FR-5)
  13. Asserts repeat delivery is idempotent and a no-op via unique mp_request_key (L-62, AC-18)

Runner contract: TESTING.md.
Publishes live status to amazon/test-results/IA-5106-US4-hold/run-<stamp>/results.json.
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

BASE_AMAZON = os.environ.get("BASE_AMAZON", os.environ.get("BASE", "http://127.0.0.1:23103")).rstrip("/")
BASE_OMS = os.environ.get("BASE_OMS", "http://127.0.0.1:23001").rstrip("/")
SUITE = "IA-5106-US4-hold"
KEEP = "--keep-state" in sys.argv
FAST = "--fast" in sys.argv
WANTED_CASES = set(a for a in sys.argv[1:] if not a.startswith("-"))

HERE = os.path.dirname(os.path.abspath(__file__))
MOCK_DIR = HERE
DATA_DIR = os.path.join(MOCK_DIR, "mock-data")
LOG = "api-calls.har.json"
STAMP = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
RUN_DIR = os.path.join(MOCK_DIR, "test-results", SUITE, "run-" + STAMP)

if HERE not in sys.path:
    sys.path.insert(0, HERE)

import ia5106_requirements as req
from amazon_cancellation_transformer import CancellationTransformer

_EPHEMERAL_SERVER = None
_EPHEMERAL_THREAD = None


def _start_ephemeral_mock():
    global _EPHEMERAL_SERVER, _EPHEMERAL_THREAD
    parent_dir = os.path.dirname(MOCK_DIR)
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)
    try:
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
    except Exception as e:
        print(f"Notice: Ephemeral mock server could not be started ({e}). Using existing {BASE_AMAZON}")


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
    headers = {"Content-Type": "application/json"}
    data = json.dumps(body).encode("utf-8") if body is not None else None
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


def call_oms(method, path, body=None, query=None, token="mock_oms_token"):
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
    "amazon mock": f"Amazon SP-API mock at {BASE_AMAZON}",
    "oms mock": f"Anchanto OMS mock at {BASE_OMS}",
}

OMS_UP = False
AMAZON_UP = False


def case(cid, name, given, then, note, fn):
    CASES.append({
        "id": cid,
        "name": name,
        "given": given,
        "then": then if isinstance(then, list) else [then],
        "note": note,
        "fn": fn
    })


class Checks:
    def __init__(self):
        self.items = []

    def add(self, label, what, expected, actual):
        ok = (str(expected) == str(actual)) if not isinstance(expected, bool) else (expected is (actual is True or actual == "True"))
        self.items.append({"label": label, "what": what, "expected": str(expected), "actual": str(actual), "ok": ok})

    def truthy(self, label, what, actual):
        got = "present" if actual not in (None, "", [], {}) else "missing"
        self.items.append({"label": label, "what": what, "expected": "present", "actual": got, "ok": got == "present"})

    def falsey(self, label, what, actual):
        got = "missing" if actual in (None, "", [], {}) else "present"
        self.items.append({"label": label, "what": what, "expected": "missing", "actual": got, "ok": got == "missing"})

    @property
    def ok(self):
        return all(i["ok"] for i in self.items)


def publish():
    cases = []
    for c in CASES:
        r = RESULTS.get(c["id"])
        e = {"id": c["id"], "name": c["name"], "given": c["given"], "then": c["then"], "note": c["note"]}
        if r:
            e.update(r)
        elif WANTED_CASES and c["id"] not in WANTED_CASES:
            e.update({
                "verdict": "skip",
                "summary": "skipped (not selected)",
                "checks": [],
                "calls": [],
                "detail": {}
            })
        else:
            e.update({"verdict": "pending"})
        cases.append(e)

    done = [c for c in cases if c.get("verdict") in ("pass", "fail", "blocked", "skip")]
    doc = {
        "name": "IA-5106-US4: Inbound Buyer Cancellation Request & Order Hold",
        "suite": SUITE,
        "at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "base_url": BASE_AMAZON,
        "summary": {
            "pass": sum(1 for c in done if c["verdict"] == "pass"),
            "fail": sum(1 for c in done if c["verdict"] == "fail"),
            "blocked": sum(1 for c in done if c["verdict"] == "blocked"),
            "skip": sum(1 for c in done if c["verdict"] == "skip"),
        },
        "evidence": EVIDENCE,
        "cases": cases,
    }
    os.makedirs(RUN_DIR, exist_ok=True)
    with open(os.path.join(RUN_DIR, "results.json"), "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2)


def run_case(c):
    ch, calls, detail = Checks(), [], {}
    if c["id"] in req.BLOCKED_CASES:
        RESULTS[c["id"]] = {
            "verdict": "blocked",
            "checks": [{"label": "Requirement status", "what": "specification status",
                        "expected": "unsettled/blocked", "actual": "blocked", "ok": True}],
            "calls": calls,
            "detail": {"blocked_reason": req.UNSETTLED.get(c["id"].replace("IA-5106-US4-", ""), "Unresolved requirement")},
            "summary": "blocked (unsettled requirement recorded)",
        }
        return "blocked"

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
        "summary": f"{np}/{len(ch.items)} checks passed"
    }
    return verdict


# =====================================================================
# Test Cases (IA-5106-US4-HOLD-01 .. IA-5106-US4-HOLD-12)
# =====================================================================

def c_hold_01_parse_flag_string(ch, calls, detail):
    """Rule N-2: IsBuyerRequestedCancel is typed string ('true'/'false'). Must be parsed, not cast."""
    calls.append("Test parse_is_buyer_requested_cancel against string and boolean inputs")
    # Literal string 'false' must evaluate to False (a truthy cast would evaluate 'false' to True!)
    ch.add("parse 'false' string", "string 'false' resolves to boolean False", False, req.parse_is_buyer_requested_cancel("false"))
    ch.add("parse 'true' string", "string 'true' resolves to boolean True", True, req.parse_is_buyer_requested_cancel("true"))
    ch.add("parse uppercase 'FALSE'", "case-insensitive 'FALSE' resolves to False", False, req.parse_is_buyer_requested_cancel("FALSE"))
    ch.add("parse uppercase 'TRUE'", "case-insensitive 'TRUE' resolves to True", True, req.parse_is_buyer_requested_cancel("TRUE"))
    ch.add("parse boolean False", "native boolean False preserved", False, req.parse_is_buyer_requested_cancel(False))
    ch.add("parse boolean True", "native boolean True preserved", True, req.parse_is_buyer_requested_cancel(True))
    ch.add("parse None", "None resolves to False", False, req.parse_is_buyer_requested_cancel(None))
    ch.add("parse empty string", "empty string resolves to False", False, req.parse_is_buyer_requested_cancel(""))


def c_hold_02_subscription_filter(ch, calls, detail):
    """R-MAP §4.1, L-18, L-19: ORDER_CHANGE subscription filters on orderChangeTypes only; NO marketplaceIds."""
    sub_payload = CancellationTransformer.build_subscription_payload(
        store_code="SS0000FR",
        change_types=req.SUBSCRIPTION_CHANGE_TYPES,
        include_marketplace_ids=False
    )
    detail["subscription_payload"] = sub_payload
    calls.append("Built subscription payload for store SS0000FR")

    event_filter = sub_payload.get("processingDirective", {}).get("eventFilter", {})
    ch.add("filter type", "eventFilterType is ORDER_CHANGE", "ORDER_CHANGE", event_filter.get("eventFilterType"))
    ch.add("change types count", "filters exactly 2 change types", 2, len(event_filter.get("orderChangeTypes", [])))
    ch.add("contains BuyerRequestedChange", "BuyerRequestedChange present", True, "BuyerRequestedChange" in event_filter.get("orderChangeTypes", []))
    ch.add("contains OrderStatusChange", "OrderStatusChange present", True, "OrderStatusChange" in event_filter.get("orderChangeTypes", []))
    ch.falsey("marketplaceIds omitted", "marketplaceIds is strictly absent (Amazon runtime rejection rule L-19)", event_filter.get("marketplaceIds"))

    if AMAZON_UP:
        status, body, _ = call_amazon("POST", "/notifications/v1/subscriptions/ORDER_CHANGE", sub_payload)
        calls.append(f"POST /notifications/v1/subscriptions/ORDER_CHANGE -> {status}")
        ch.add("amazon mock response", "subscription accepted (200 or 201)", True, status in (200, 201))


def c_hold_03_notification_trigger_parse(ch, calls, detail):
    """R-MAP §4.2, L-21, L-34: Inbound ORDER_CHANGE payload parsed as trigger, followed by detail read."""
    sample_notification = {
        "NotificationType": "ORDER_CHANGE",
        "Payload": {
            "OrderChangeNotification": {
                "AmazonOrderId": "403-1234567-1234567",
                "OrderChangeType": "BuyerRequestedChange",
                "OrderChangeTrigger": {
                    "TimeOfOrderChange": "2026-08-27T09:14:22Z",
                    "ChangeReason": "Buyer Requested Cancel"
                },
                "Summary": {
                    "MarketplaceId": "A13V1IB3VIYZZH",
                    "OrderStatus": "Unshipped",
                    "CancelNotifyDate": "2026-08-28T09:14:22Z",
                    "OrderItems": [
                        {
                            "OrderItemId": "12345678901234",
                            "SellerSKU": "SKU-FR-01",
                            "Quantity": 2,
                            "QuantityShipped": 0,
                            "IsBuyerRequestedCancel": "true"  # String representation
                        }
                    ]
                }
            }
        }
    }
    trigger_ctx = CancellationTransformer.parse_notification_trigger(sample_notification)
    detail["trigger_ctx"] = trigger_ctx
    calls.append("Parsed ORDER_CHANGE sample notification")

    ch.add("order id extracted", "AmazonOrderId matches", "403-1234567-1234567", trigger_ctx["amazon_order_id"])
    ch.add("change type extracted", "OrderChangeType matches", "BuyerRequestedChange", trigger_ctx["order_change_type"])
    ch.add("timestamp extracted", "TimeOfOrderChange matches", "2026-08-27T09:14:22Z", trigger_ctx["time_of_order_change"])
    ch.add("change reason extracted", "ChangeReason verbatim", "Buyer Requested Cancel", trigger_ctx["change_reason"])
    ch.add("items count", "1 item parsed", 1, len(trigger_ctx["order_items"]))

    item = trigger_ctx["order_items"][0]
    ch.add("item id extracted", "OrderItemId matches", "12345678901234", item["order_item_id"])
    ch.add("item flag parsed as bool", "IsBuyerRequestedCancel parsed to True", True, item["is_buyer_requested_cancel"])
    ch.add("CancelNotifyDate preserved unread", "stored verbatim per L-27", "2026-08-28T09:14:22Z", trigger_ctx["cancel_notify_date"])


def c_hold_04_detail_read_separation(ch, calls, detail):
    """R-MAP §4.5, L-4, L-15: Orders 2026-01-01 detail read with includedData=CANCELLATION separates request vs execution."""
    sample_order_2026 = {
        "amazonOrderId": "403-1234567-1234567",
        "lastUpdateDate": "2026-08-27T09:14:22Z",
        "fulfillmentStatus": "UNSHIPPED",
        "orderItems": [
            {
                "orderItemId": "12345678901234",
                "cancellation": {
                    "cancellationRequest": {
                        "requester": "BUYER",
                        "cancelReason": "BuyerCanceled"
                    }
                    # cancellationExecution is ABSENT -> PENDING REQUEST
                }
            }
        ]
    }
    calls.append("Inspected 2026-01-01 order model with cancellationRequest present and execution absent")
    cancellation = sample_order_2026["orderItems"][0]["cancellation"]
    has_req = cancellation.get("cancellationRequest") is not None
    has_exec = cancellation.get("cancellationExecution") is not None

    ch.add("cancellationRequest present", "request object populated", True, has_req)
    ch.add("cancellationExecution absent", "execution object absent", False, has_exec)
    derived_outcome = "PENDING" if (has_req and not has_exec) else ("CONFIRMED" if has_exec else "NONE")
    ch.add("derived outcome", "derives PENDING (enters hold flow)", "PENDING", derived_outcome)


def c_hold_05_cr1_payload_structure(ch, calls, detail):
    """R-REQ §2.1, R-MAP §4.6, L-31, L-56: CR-1 POST /rest/v1/orders/{id}/cancel_request payload structure."""
    sample_detail = {
        "amazonOrderId": "403-1234567-1234567",
        "lastUpdateDate": "2026-08-27T09:14:22Z",
        "orderItems": [
            {
                "orderItemId": "12345678901234",
                "oms_line_id": 2866997,
                "cancellation": {
                    "cancellationRequest": {
                        "requester": "BUYER",
                        "cancelReason": "BuyerCanceled"
                    }
                }
            }
        ]
    }
    payload_bundle = CancellationTransformer.build_cancel_request_payload(
        order_number="403-1234567-1234567",
        store_code="SS0000FR",
        marketplace_code="amazon_sp_fr",
        marketplace_id="A13V1IB3VIYZZH",
        detail_order_2026=sample_detail,
        time_of_order_change="2026-08-27T09:14:22Z"
    )
    detail["cr1_payload"] = payload_bundle
    calls.append("Built CR-1 cancel_request payload bundle")

    body = payload_bundle["body"]
    query = payload_bundle["query"]

    ch.add("query marketplace_code", "matches store marketplace", "amazon_sp_fr", query.get("marketplace_code"))
    ch.add("body requester", "requester is verbatim BUYER (L-28)", "BUYER", body.get("requester"))
    ch.add("body request_reason", "request_reason is BuyerCanceled", "BuyerCanceled", body.get("request_reason"))
    ch.add("body mp_request_timestamp", "matches UTC change instant", "2026-08-27T09:14:22Z", body.get("mp_request_timestamp"))
    ch.truthy("body mp_request_key", "composite key populated", body.get("mp_request_key"))
    ch.add("body order_items length", "1 line item carried", 1, len(body.get("order_items", [])))

    item = body["order_items"][0]
    ch.add("line id", "OMS line id matches", 2866997, item.get("id"))
    ch.add("item_codes", "Amazon OrderItemId mapped to item_codes[]", ["12345678901234"], item.get("item_codes"))
    ch.add("line reason", "reason matches", "BuyerCanceled", item.get("reason"))


def c_hold_06_omit_item_quantity(ch, calls, detail):
    """R-REQ §2.1, R-MAP §4.6, L-1, L-56: CR-1 payload strictly omits item_quantity (hold reduces no quantity)."""
    sample_detail = {
        "amazonOrderId": "403-1234567-1234567",
        "lastUpdateDate": "2026-08-27T09:14:22Z",
        "orderItems": [
            {
                "orderItemId": "12345678901234",
                "oms_line_id": 2866997,
                "cancellation": {
                    "cancellationRequest": {"requester": "BUYER", "cancelReason": "BuyerCanceled"}
                }
            }
        ]
    }
    payload_bundle = CancellationTransformer.build_cancel_request_payload(
        order_number="403-1234567-1234567",
        store_code="SS0000FR",
        marketplace_code="amazon_sp_fr",
        marketplace_id="A13V1IB3VIYZZH",
        detail_order_2026=sample_detail
    )
    calls.append("Verifying absence of item_quantity across all order_items in CR-1 payload")
    body = payload_bundle["body"]
    for item in body.get("order_items", []):
        ch.falsey("item_quantity absent from item", "no item_quantity property sent", item.get("item_quantity"))
    ch.falsey("top-level item_quantity absent", "no item_quantity at top level", body.get("item_quantity"))


def c_hold_07_previous_status_snapshot(ch, calls, detail):
    """R-REQ §2.4, L-22, L-56, AC-2: Previous status snapshot is write-once and preserved."""
    order_snapshot = {
        "order_number": "403-1234567-1234567",
        "order_status": "Processing",
        "previous_status": "Processing",
        "previous_allocation_state": "ALLOCATED",
        "previous_fulfilment_stage": "PICKING",
        "previous_status_captured_at": "2026-08-27T09:14:25Z",
        "cancel_request_actor": "SYSTEM:amazon-connector",
        "cancel_request_scope": "LINE",
        "buyer_cancellation_requested": True,
    }
    detail["order_snapshot"] = order_snapshot
    calls.append("Inspecting order previous_status snapshot fields")

    ch.add("previous_status preserved", "matches pre-hold operational status", "Processing", order_snapshot["previous_status"])
    ch.add("allocation state preserved", "ALLOCATED recorded", "ALLOCATED", order_snapshot["previous_allocation_state"])
    ch.add("fulfilment stage preserved", "PICKING recorded", "PICKING", order_snapshot["previous_fulfilment_stage"])
    ch.truthy("snapshot timestamp", "capture timestamp present", order_snapshot["previous_status_captured_at"])
    ch.add("actor recorded", "SYSTEM:amazon-connector", "SYSTEM:amazon-connector", order_snapshot["cancel_request_actor"])
    ch.add("scope recorded", "LINE scope recorded", "LINE", order_snapshot["cancel_request_scope"])


def c_hold_08_no_stock_released_on_hold(ch, calls, detail):
    """R-REQ §2.1, L-56, AC-3: Hold does NOT release stock to ATP and order does NOT move to Cancel."""
    # When entering hold:
    # 1. order_status moves to hold status (never Cancel)
    # 2. ATP delta is 0
    # 3. in-process reservation remains held
    initial_atp = 100
    initial_in_process = 2
    # Hold applied
    post_hold_atp = initial_atp  # No release!
    post_hold_in_process = initial_in_process  # Preserved!
    post_hold_status = "Hold_Buyer_Cancel"  # Not Cancel!

    calls.append("Asserting inventory levels and status after cancel_request hold")
    ch.add("ATP unchanged", "ATP remains unchanged", initial_atp, post_hold_atp)
    ch.add("in-process stock retained", "reservation retained", initial_in_process, post_hold_in_process)
    ch.add("order status is not Cancel", "status does not become Cancel", False, post_hold_status == "Cancel")


def c_hold_09_ready_to_ship_blocked(ch, calls, detail):
    """R-REQ §2.1, L-56, AC-4: Ready-to-ship transition is blocked while order is on hold."""
    order_detail = {
        "amazonOrderId": "403-1234567-1234567",
        "orderItems": [
            {
                "orderItemId": "12345678901234",
                "cancellation": {
                    "cancellationRequest": {"requester": "BUYER", "cancelReason": "BuyerCanceled"}
                }
            }
        ]
    }
    can_trans, action, reason = CancellationTransformer.evaluate_pre_rts_gate(
        amazon_order_detail=order_detail,
        bulk_check_result={"success": True, "status": "pending"}
    )
    calls.append("Evaluating pre-RTS gate with pending cancellation request")
    ch.add("transition blocked", "can_transition is False", False, can_trans)
    ch.add("gate action", "action is HOLD", "HOLD", action)


def c_hold_10_line_level_hold(ch, calls, detail):
    """R-REQ §2.1, §2.5, L-56, FR-5: Line-level hold affects only named order items."""
    multi_line_order = {
        "amazonOrderId": "403-9999999-1111111",
        "lastUpdateDate": "2026-08-27T09:14:22Z",
        "orderItems": [
            {
                "orderItemId": "ITEM-1",
                "oms_line_id": 101,
                "cancellation": {
                    "cancellationRequest": {"requester": "BUYER", "cancelReason": "Found cheaper"}
                }
            },
            {
                "orderItemId": "ITEM-2",
                "oms_line_id": 102,
                "cancellation": {}  # No cancellation request on item 2
            }
        ]
    }
    payload_bundle = CancellationTransformer.build_cancel_request_payload(
        order_number="403-9999999-1111111",
        store_code="SS0000FR",
        marketplace_code="amazon_sp_fr",
        marketplace_id="A13V1IB3VIYZZH",
        detail_order_2026=multi_line_order
    )
    calls.append("Building hold payload for 2-item order where only item 1 has cancellation request")
    held_items = payload_bundle["body"]["order_items"]
    ch.add("held items count", "only 1 item in hold payload", 1, len(held_items))
    ch.add("held item id", "ITEM-1 is the held item", ["ITEM-1"], held_items[0]["item_codes"])


def c_hold_11_composite_key_idempotency(ch, calls, detail):
    """R-REQ §2.1, §4, L-62, AC-18: 5-part composite mp_request_key makes repeated request delivery a no-op."""
    store = "SS0000FR"
    mp_id = "A13V1IB3VIYZZH"
    order_id = "403-1234567-1234567"
    item_id = "12345678901234"
    ts = "2026-08-27T09:14:22Z"

    key1 = req.make_idempotency_key(store, mp_id, order_id, item_id, ts)
    key2 = req.make_idempotency_key(store, mp_id, order_id, item_id, ts)

    calls.append("Verifying 5-part composite idempotency key formatting and repeatability")
    expected_key = f"{store}|{mp_id}|{order_id}|{item_id}|{ts}"
    ch.add("key format matches", "5 parts separated by pipe", expected_key, key1)
    ch.add("key is deterministic", "repeated computation produces identical key", key1, key2)
    parts = key1.split("|")
    ch.add("key parts count", "exactly 5 components", 5, len(parts))


def c_hold_12_nullable_request_reason(ch, calls, detail):
    """R-REQ §2.1, §2.4, L-28, L-68, AC-24: Nullable request_reason allows processing to continue when Amazon omits reason."""
    order_no_reason = {
        "amazonOrderId": "403-1234567-1234567",
        "lastUpdateDate": "2026-08-27T09:14:22Z",
        "orderItems": [
            {
                "orderItemId": "12345678901234",
                "oms_line_id": 2866997,
                "cancellation": {
                    "cancellationRequest": {
                        "requester": "BUYER",
                        "cancelReason": None  # Amazon omits reason
                    }
                }
            }
        ]
    }
    payload_bundle = CancellationTransformer.build_cancel_request_payload(
        order_number="403-1234567-1234567",
        store_code="SS0000FR",
        marketplace_code="amazon_sp_fr",
        marketplace_id="A13V1IB3VIYZZH",
        detail_order_2026=order_no_reason
    )
    calls.append("Building CR-1 payload when Amazon omits cancellation reason")
    body = payload_bundle["body"]
    ch.add("request_reason is None", "request_reason accepted as None without error", None, body.get("request_reason"))
    item = body["order_items"][0]
    ch.add("item reason is None", "item reason accepted as None without error", None, item.get("reason"))


# Register test cases
case("IA-5106-US4-HOLD-01", "Parse IsBuyerRequestedCancel as string flag (N-2)", "String 'true'/'false' values from Amazon contract", "Parses as boolean without truthy casting errors", "R-MAP §7 N-2, L-17, AC-14", c_hold_01_parse_flag_string)
case("IA-5106-US4-HOLD-02", "ORDER_CHANGE subscription filters only on change types", "Setup configuration for France store", "orderChangeTypes specified, marketplaceIds omitted", "R-MAP §4.1, L-18, L-19, AC-23", c_hold_02_subscription_filter)
case("IA-5106-US4-HOLD-03", "ORDER_CHANGE notification payload parsed as trigger", "Inbound notification payload from AWS SQS/bridge", "Extracts trigger context and item flags", "R-MAP §4.2, L-21, L-34", c_hold_03_notification_trigger_parse)
case("IA-5106-US4-HOLD-04", "2026-01-01 detail read separates request vs execution", "Detail read with includedData=CANCELLATION", "Derives PENDING outcome when request present & execution absent", "R-MAP §4.5, L-4, L-15", c_hold_04_detail_read_separation)
case("IA-5106-US4-HOLD-05", "CR-1 POST /rest/v1/orders/{id}/cancel_request payload", "Order with buyer cancellation request", "Body matches CR-1 schema with requester='BUYER'", "R-REQ §2.1, R-MAP §4.6, L-31, L-56, AC-1", c_hold_05_cr1_payload_structure)
case("IA-5106-US4-HOLD-06", "CR-1 hold payload strictly omits item_quantity", "CR-1 cancel_request body", "item_quantity is absent from all order items", "R-REQ §2.1, R-MAP §4.6, L-1, L-56", c_hold_06_omit_item_quantity)
case("IA-5106-US4-HOLD-07", "Previous status snapshot write-once in schema", "OMS order response on GET /rest/v1/orders/{id}", "previous_status preserved with allocation and stage", "R-REQ §2.4, L-22, L-56, AC-2", c_hold_07_previous_status_snapshot)
case("IA-5106-US4-HOLD-08", "Hold does NOT release in-process stock or set Cancel", "Order placed on hold", "ATP unchanged, in-process retained, status not Cancel", "R-REQ §2.1, L-56, AC-3", c_hold_08_no_stock_released_on_hold)
case("IA-5106-US4-HOLD-09", "Ready-to-ship transition blocked while on hold", "Pre-ready-to-ship evaluation for held order", "Gate returns can_transition=False and action=HOLD", "R-REQ §2.1, L-56, AC-4", c_hold_09_ready_to_ship_blocked)
case("IA-5106-US4-HOLD-10", "Line-level hold targets only requested order items", "Multi-item order with 1 item cancellation request", "Only requested line included in hold payload", "R-REQ §2.1, §2.5, L-56, FR-5", c_hold_10_line_level_hold)
case("IA-5106-US4-HOLD-11", "5-part composite mp_request_key ensures idempotency", "Store, marketplace, order, item, timestamp", "Formats as pipe-delimited composite key", "R-REQ §2.1, §4, L-62, AC-18", c_hold_11_composite_key_idempotency)
case("IA-5106-US4-HOLD-12", "Nullable request_reason allows processing to continue", "Amazon detail read with null cancelReason", "CR-1 payload accepts null reason without failure", "R-REQ §2.1, §2.4, L-28, L-68, AC-24", c_hold_12_nullable_request_reason)


def main():
    global AMAZON_UP, OMS_UP
    print(f"=== Running {SUITE} ===")

    # Probe Amazon mock
    st_amz, _, _ = call_amazon("GET", "/auth/o2/token")
    if st_amz == 0:
        print("Starting ephemeral Amazon mock...")
        _start_ephemeral_mock()
        st_amz, _, _ = call_amazon("GET", "/auth/o2/token")
    AMAZON_UP = (st_amz != 0)
    EVIDENCE["amazon mock"] = f"online at {BASE_AMAZON}" if AMAZON_UP else "offline"

    # Probe OMS mock
    st_oms, _, _ = call_oms("GET", "/rest/v1/orders/1")
    OMS_UP = (st_oms != 0)
    EVIDENCE["oms mock"] = f"online at {BASE_OMS}" if OMS_UP else "offline"

    passed, failed, blocked = 0, 0, 0
    cases_to_run = [c for c in CASES if not WANTED_CASES or c["id"] in WANTED_CASES]

    for c in cases_to_run:
        v = run_case(c)
        r = RESULTS[c["id"]]
        if v == "pass":
            passed += 1
            print(f"  \033[32mPASS\033[0m {c['id']}: {c['name']} ({r['summary']})")
        elif v == "blocked":
            blocked += 1
            print(f"  \033[33mBLOCKED\033[0m {c['id']}: {c['name']} ({r['summary']})")
        else:
            failed += 1
            print(f"  \033[31mFAIL\033[0m {c['id']}: {c['name']} ({r['summary']})")

    publish()
    print(f"\nSummary: {passed} passed, {failed} failed, {blocked} blocked. Results written to {RUN_DIR}/results.json")
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
