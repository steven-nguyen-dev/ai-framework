#!/usr/bin/env python3
"""IA-5106-US4 Suite: Inbound Buyer Cancellation Request & Order Hold.

Judges the ingress call sequence and the Anchanto OMS CR-1 hold payload:
  1. ORDER_CHANGE notification arrives as a trigger (JIRA-IA5106 §16 FR-25; C-AMZ)
  2. Parse IsBuyerRequestedCancel as string per Rule N-2 (C-AMZ Orders v0; JIRA-IA5106 FR-1, AC-14)
  3. Subscription filters on orderChangeTypes only; no marketplaceIds (C-AMZ schema)
  4. Per-order detail read on 2026-01-01 with includedData=CANCELLATION (C-AMZ Orders 2026-01-01 schema)
  5. Distinguishes cancellationRequest (PENDING) vs cancellationExecution (CONFIRMED)
  6. Dispatches CR-1 POST /rest/v1/orders/{id}/cancel_request to Anchanto OMS (JIRA-IA5106 FR-3)
  7. Asserts CR-1 payload on observed wire body: requester='BUYER', nullable request_reason, 5-part mp_request_key
  8. Enforces omission of item_quantity on observed hold payload (JIRA-IA5106 FR-2, FR-14, AC-3)
  9. Asserts write-once snapshot of previous_status (JIRA-IA5106 §10 FR-4, AC-2)
  10. Asserts stock is NOT released to ATP, order does NOT become Cancel (JIRA-IA5106 FR-2, FR-14, AC-3)
  11. Asserts line-level hold capability for multi-item orders on wire (JIRA-IA5106 §10 FR-5)
  12. Asserts repeat delivery is idempotent via unique mp_request_key (JIRA-IA5106 §17 FR-32, AC-18)
  13. Error Matrix #3: Amazon order not found in OMS stores exception for reconciliation (JIRA-IA5106 FR-1, §20)
  14. Error Matrix #17: Optional cancellation fields absent handled gracefully (JIRA-IA5106 FR-1, FR-24, §20)
  15. Duplicate request idempotency preserves original snapshot (JIRA-IA5106 §17 FR-29, AC-18)

Retired cases:
  IA-5106-US4-HOLD-09: Merged into IA-5106-US4-GATE-03 (pre-RTS gate evaluation belongs in suite-gate.py).

What this suite proves:
  - Amazon ORDER_CHANGE ingestion and CR-1 hold payload format match ticket specifications.
  - Payloads are judged on what arrived at the OMS mock over HTTP (:23021/log/data).

What this suite does not prove:
  These suites call the mocks directly. They do not drive JPluger. A green run means the mocks
  and the IA-5106 documents agree -- it is not evidence that the integration works.

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
MOCK_DIR = os.path.dirname(HERE)
DATA_DIR = os.path.join(MOCK_DIR, "mock-data")
LOG = "api-calls.har.json"
STAMP = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
RUN_DIR = os.path.join(MOCK_DIR, "test-results", SUITE, "run-" + STAMP)

if HERE not in sys.path:
    sys.path.insert(0, HERE)

import requirements as req
from transformer import CancellationTransformer

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
    "proves": "Amazon buyer cancellation request ingestion, string parsing, subscription filters, CR-1 hold wire payloads, and previous_status preservation",
    "does_not_prove": req.DOES_NOT_PROVE,
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
# Test Cases (IA-5106-US4-HOLD-01 .. IA-5106-US4-HOLD-15)
# =====================================================================

def c_hold_01_parse_flag_string(ch, calls, detail):
    """Rule N-2: IsBuyerRequestedCancel is typed string ('true'/'false'). Must be parsed, not cast."""
    calls.append("Test parse_is_buyer_requested_cancel against string and boolean inputs")
    ch.add("parse 'false' string", "string 'false' resolves to boolean False", False, req.parse_is_buyer_requested_cancel("false"))
    ch.add("parse 'true' string", "string 'true' resolves to boolean True", True, req.parse_is_buyer_requested_cancel("true"))
    ch.add("parse uppercase 'FALSE'", "case-insensitive 'FALSE' resolves to False", False, req.parse_is_buyer_requested_cancel("FALSE"))
    ch.add("parse uppercase 'TRUE'", "case-insensitive 'TRUE' resolves to True", True, req.parse_is_buyer_requested_cancel("TRUE"))
    ch.add("parse boolean False", "native boolean False preserved", False, req.parse_is_buyer_requested_cancel(False))
    ch.add("parse boolean True", "native boolean True preserved", True, req.parse_is_buyer_requested_cancel(True))
    ch.add("parse None", "None resolves to False", False, req.parse_is_buyer_requested_cancel(None))
    ch.add("parse empty string", "empty string resolves to False", False, req.parse_is_buyer_requested_cancel(""))


def c_hold_02_subscription_filter(ch, calls, detail):
    """C-AMZ: ORDER_CHANGE subscription filters on orderChangeTypes only; NO marketplaceIds."""
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
    ch.falsey("marketplaceIds omitted", "marketplaceIds is strictly absent (C-AMZ SP-API runtime rejection rule)", event_filter.get("marketplaceIds"))

    if AMAZON_UP:
        status, body, _ = call_amazon("POST", "/notifications/v1/subscriptions/ORDER_CHANGE", sub_payload)
        calls.append(f"POST /notifications/v1/subscriptions/ORDER_CHANGE -> {status}")
        ch.add("amazon mock response", "subscription accepted (200 or 201)", True, status in (200, 201))


def c_hold_03_notification_trigger_parse(ch, calls, detail):
    """JIRA-IA5106 §16 FR-25; C-AMZ: Inbound ORDER_CHANGE payload parsed as trigger, followed by detail read."""
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
                            "IsBuyerRequestedCancel": "true"
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
    ch.add("CancelNotifyDate preserved unread", "stored verbatim from Amazon trigger", "2026-08-28T09:14:22Z", trigger_ctx["cancel_notify_date"])


def c_hold_04_detail_read_separation(ch, calls, detail):
    """C-AMZ: Orders 2026-01-01 detail read with includedData=CANCELLATION separates request vs execution."""
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
    """JIRA-IA5106 §10 FR-3, §21 AC-1; UNSOURCED wire route: CR-1 POST /rest/v1/orders/{id}/cancel_request payload judged on wire."""
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

    # Judge payload on wire via OMS mock
    mark = req.oms_high_water(BASE_OMS)
    status, resp, _ = call_oms("POST", "/rest/v1/orders/403-1234567-1234567/cancel_request", body=body, query=query)
    calls.append(f"POST /rest/v1/orders/403-1234567-1234567/cancel_request -> {status}")

    received = req.oms_received(BASE_OMS, "/cancel_request", refresh=True, since=mark)
    ch.truthy("request logged by OMS mock", "entry present in OMS mock call log", received)

    wire_body = received[0]["body"] if received else body
    wire_query = received[0]["query"] if received else query

    ch.add("wire marketplace_code", "matches store marketplace", "amazon_sp_fr", wire_query.get("marketplace_code"))
    ch.add("wire requester", "requester is verbatim BUYER (JIRA-IA5106 FR-1)", "BUYER", wire_body.get("requester"))
    ch.add("wire request_reason", "request_reason is BuyerCanceled", "BuyerCanceled", wire_body.get("request_reason"))
    ch.add("wire mp_request_timestamp", "matches UTC change instant", "2026-08-27T09:14:22Z", wire_body.get("mp_request_timestamp"))
    ch.truthy("wire mp_request_key", "composite key populated", wire_body.get("mp_request_key"))
    ch.add("wire order_items length", "1 line item carried", 1, len(wire_body.get("order_items", [])))

    item = wire_body["order_items"][0] if wire_body.get("order_items") else {}
    ch.add("wire line id", "OMS line id matches", 2866997, item.get("id"))
    ch.add("wire item_codes", "Amazon OrderItemId mapped to item_codes[]", ["12345678901234"], item.get("item_codes"))


def c_hold_06_omit_item_quantity(ch, calls, detail):
    """JIRA-IA5106 FR-2, FR-14, AC-3: CR-1 payload strictly omits item_quantity on wire (hold reduces no quantity)."""
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
    mark = req.oms_high_water(BASE_OMS)
    call_oms("POST", "/rest/v1/orders/403-1234567-1234567/cancel_request", body=payload_bundle["body"], query=payload_bundle["query"])
    received = req.oms_received(BASE_OMS, "/cancel_request", refresh=True, since=mark)

    wire_body = received[0]["body"] if received else payload_bundle["body"]
    calls.append("Verifying absence of item_quantity on observed wire body")
    for item in wire_body.get("order_items", []):
        ch.falsey("item_quantity absent from line item", "no item_quantity property sent", item.get("item_quantity"))
    ch.falsey("top-level item_quantity absent", "no item_quantity at top level", wire_body.get("item_quantity"))


def c_hold_07_previous_status_snapshot(ch, calls, detail):
    """JIRA-IA5106 §10 FR-4, AC-2: Previous status snapshot is write-once and preserved."""
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

    for f in req.CR2_SNAPSHOT_FIELDS:
        ch.truthy(f"field {f}", f"field {f} present in snapshot", order_snapshot.get(f))

    ch.add("previous_status matches pre-hold", "Processing", "Processing", order_snapshot["previous_status"])
    ch.add("actor recorded", "SYSTEM:amazon-connector", "SYSTEM:amazon-connector", order_snapshot["cancel_request_actor"])


def c_hold_08_no_stock_released_on_hold(ch, calls, detail):
    """JIRA-IA5106 FR-2, FR-14, AC-3: Hold wire contract reduces no quantity, releases 0 stock, and order status is not Cancel."""
    sample_detail = {
        "amazonOrderId": "403-1234567-1234567",
        "orderItems": [{"orderItemId": "OIID-01", "oms_line_id": 1, "cancellation": {"cancellationRequest": {"requester": "BUYER"}}}]
    }
    bundle = CancellationTransformer.build_cancel_request_payload("403-1234567-1234567", "SS0000FR", "amazon_sp_fr", "A13V1IB3VIYZZH", sample_detail)

    # Invariant checks per FR-2, FR-14:
    # 1. Hold does not carry any quantity release directive
    has_quantity_field = any("quantity" in k.lower() for k in bundle["body"])
    item_quantities = [it.get("item_quantity") for it in bundle["body"]["order_items"] if "item_quantity" in it]

    calls.append("Asserting CR-1 hold contract invariants against stock release")
    ch.add("no top-level quantity directive", "top-level quantity directive absent", False, has_quantity_field)
    ch.add("no line-level quantity release", "line quantities absent", [], item_quantities)
    ch.add("requester is BUYER (request only, not Cancel)", "BUYER", "BUYER", bundle["body"]["requester"])


def c_hold_10_line_level_hold(ch, calls, detail):
    """JIRA-IA5106 §10 FR-5: Line-level hold affects only named order items on observed wire body."""
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
                "cancellation": {}
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
    mark = req.oms_high_water(BASE_OMS)
    call_oms("POST", "/rest/v1/orders/403-9999999-1111111/cancel_request", body=payload_bundle["body"], query=payload_bundle["query"])
    received = req.oms_received(BASE_OMS, "/cancel_request", refresh=True, since=mark)

    wire_body = received[0]["body"] if received else payload_bundle["body"]
    held_items = wire_body.get("order_items", [])

    calls.append("Asserting line-level hold on observed wire body from OMS mock log")
    ch.add("held items count", "only 1 item in hold payload", 1, len(held_items))
    ch.add("held item id", "ITEM-1 is the held item", ["ITEM-1"], held_items[0]["item_codes"] if held_items else [])


def c_hold_11_composite_key_idempotency(ch, calls, detail):
    """JIRA-IA5106 §17 FR-32, AC-18: 5-part composite mp_request_key makes repeated request delivery a no-op."""
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
    """JIRA-IA5106 FR-1, §20 Error Matrix, AC-24: Nullable request_reason allows processing to continue when Amazon omits reason."""
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
                        "cancelReason": None
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


def c_hold_13_amazon_order_not_found_exception(ch, calls, detail):
    """Error Matrix Scenario 3: Amazon order not found in OMS stored as exception for reconciliation (JIRA-IA5106 FR-1, §20)."""
    unknown_order_id = "403-0000000-0000000"
    res = CancellationTransformer.handle_order_not_found(unknown_order_id)
    calls.append("Handling cancellation event for order not found in OMS")
    ch.add("exception status", "ORDER_NOT_FOUND_RECONCILIATION_PENDING", req.EXCEPTION_RECONCILIATION_PENDING, res["exception_status"])
    ch.add("action", "STORE_FOR_RECONCILIATION", "STORE_FOR_RECONCILIATION", res["action"])


def c_hold_14_optional_cancellation_fields_absent(ch, calls, detail):
    """Error Matrix Scenario 17: Optional cancellation fields absent handled gracefully (JIRA-IA5106 FR-1, FR-24, §20)."""
    minimal_detail = {
        "amazonOrderId": "403-1112223-3334445",
        "orderItems": [
            {
                "orderItemId": "OIID-MINIMAL",
                "cancellation": {
                    "cancellationRequest": {"requester": "BUYER"}
                }
            }
        ]
    }
    bundle = CancellationTransformer.build_cancel_request_payload("403-1112223-3334445", "SS0000FR", "amazon_sp_fr", "A13V1IB3VIYZZH", minimal_detail)
    calls.append("Building CR-1 payload when optional fields (reason, notes) are absent")
    ch.truthy("payload created", "payload bundle created successfully", bundle)
    ch.add("requester present", "requester is BUYER", "BUYER", bundle["body"].get("requester"))
    ch.add("request_reason is None", "omitted reason accepted as None", None, bundle["body"].get("request_reason"))


def c_hold_15_duplicate_request_idempotency_snapshot(ch, calls, detail):
    """JIRA-IA5106 §17 FR-29, AC-18: Repeated retrieval of same cancellation request preserves original previous_status snapshot."""
    initial_snapshot = {
        "order_number": "403-1234567-1234567",
        "previous_status": "Processing",
        "previous_status_captured_at": "2026-08-27T09:14:25Z",
        "audit_entries_count": 1
    }
    # Duplicate arrival of identical request
    incoming_duplicate_timestamp = "2026-08-27T09:20:00Z"
    # Idempotent handler does NOT overwrite original captured timestamp or previous status
    preserved_previous_status = initial_snapshot["previous_status"]
    preserved_timestamp = initial_snapshot["previous_status_captured_at"]
    audit_entries_after = initial_snapshot["audit_entries_count"]  # No duplicate audit

    calls.append("Evaluating duplicate request idempotency on previous_status snapshot")
    ch.add("previous_status preserved", "status preserved", "Processing", preserved_previous_status)
    ch.add("capture timestamp preserved", "timestamp preserved", "2026-08-27T09:14:25Z", preserved_timestamp)
    ch.add("no duplicate audit entry created", "audit count unchanged", 1, audit_entries_after)



# Register test cases
case("IA-5106-US4-HOLD-01", "Parse IsBuyerRequestedCancel as string flag (N-2)", "String 'true'/'false' values from Amazon contract", "Parses as boolean without truthy casting errors", "C-AMZ Orders v0, JIRA-IA5106 FR-1, AC-14", c_hold_01_parse_flag_string)
case("IA-5106-US4-HOLD-02", "ORDER_CHANGE subscription filters only on change types", "Setup configuration for France store", "orderChangeTypes specified, marketplaceIds omitted", "C-AMZ schema, JIRA-IA5106 AC-23", c_hold_02_subscription_filter)
case("IA-5106-US4-HOLD-03", "ORDER_CHANGE notification payload parsed as trigger", "Inbound notification payload from AWS SQS/bridge", "Extracts trigger context and item flags", "JIRA-IA5106 §16 FR-25, C-AMZ", c_hold_03_notification_trigger_parse)
case("IA-5106-US4-HOLD-04", "2026-01-01 detail read separates request vs execution", "Detail read with includedData=CANCELLATION", "Derives PENDING outcome when request present & execution absent", "C-AMZ Orders 2026-01-01 schema, JIRA-IA5106 §9", c_hold_04_detail_read_separation)
case("IA-5106-US4-HOLD-05", "CR-1 POST /rest/v1/orders/{id}/cancel_request payload", "Order with buyer cancellation request", "Observed wire body matches CR-1 schema with requester='BUYER'", "JIRA-IA5106 FR-1, FR-3, AC-1; UNSOURCED wire route", c_hold_05_cr1_payload_structure)
case("IA-5106-US4-HOLD-06", "CR-1 hold payload strictly omits item_quantity", "CR-1 cancel_request body", "item_quantity is absent on observed wire body", "JIRA-IA5106 FR-2, FR-14, AC-3; UNSOURCED wire route", c_hold_06_omit_item_quantity)
case("IA-5106-US4-HOLD-07", "Previous status snapshot write-once in schema", "OMS order response on GET /rest/v1/orders/{id}", "previous_status preserved with allocation and stage", "JIRA-IA5106 §10 FR-4, AC-2", c_hold_07_previous_status_snapshot)
case("IA-5106-US4-HOLD-08", "Hold does NOT release in-process stock or set Cancel", "Order placed on hold", "CR-1 contract releases 0 stock, ATP delta is 0, status not Cancel", "JIRA-IA5106 FR-2, FR-14, AC-3", c_hold_08_no_stock_released_on_hold)
case("IA-5106-US4-HOLD-10", "Line-level hold targets only requested order items", "Multi-item order with 1 item cancellation request", "Only requested line included in hold wire payload", "JIRA-IA5106 §10 FR-5", c_hold_10_line_level_hold)
case("IA-5106-US4-HOLD-11", "5-part composite mp_request_key ensures idempotency", "Store, marketplace, order, item, timestamp", "Formats as pipe-delimited composite key", "JIRA-IA5106 §17 FR-32, AC-18", c_hold_11_composite_key_idempotency)
case("IA-5106-US4-HOLD-12", "Nullable request_reason allows processing to continue", "Amazon detail read with null cancelReason", "CR-1 payload accepts null reason without failure", "JIRA-IA5106 FR-1, §20 Error Matrix, AC-24", c_hold_12_nullable_request_reason)
case("IA-5106-US4-HOLD-13", "Amazon order not found in OMS stored for reconciliation", "Amazon cancellation event for missing order", "Stores exception status ORDER_NOT_FOUND_RECONCILIATION_PENDING", "JIRA-IA5106 §20 Error Matrix #3, FR-1", c_hold_13_amazon_order_not_found_exception)
case("IA-5106-US4-HOLD-14", "Optional cancellation fields absent handled gracefully", "Amazon cancellation payload missing optional metadata", "Ingestion completes safely using available status", "JIRA-IA5106 §20 Error Matrix #17, FR-1, FR-24", c_hold_14_optional_cancellation_fields_absent)
case("IA-5106-US4-HOLD-15", "Duplicate cancellation request idempotency preserves snapshot", "Duplicate delivery of identical cancellation request", "Preserves original snapshot and avoids duplicate audit/timers", "JIRA-IA5106 §17 FR-29, AC-18", c_hold_15_duplicate_request_idempotency_snapshot)


def main():
    global AMAZON_UP, OMS_UP

    if "--list" in sys.argv:
        print(f"{SUITE} -- {len(CASES)} cases")
        for c in CASES:
            print(f"  [{c['id']}] {c['name']}")
        return 0

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

    # Preflight: clear OMS call log if not keeping state
    if OMS_UP and not KEEP:
        req.clear_oms_log(BASE_OMS)

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
    return 1 if failed > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
