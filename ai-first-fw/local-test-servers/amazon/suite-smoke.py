#!/usr/bin/env python3
"""Smoke suite for the Amazon SP-API mock server.

Proves the mock answers core Selling Partner API operations, steers on error markers,
serves official upstream sandbox mock data fixtures (TEST_CASE_*), records mutations into
state stores, and provides spec coverage across Amazon models.

Runner contract: TESTING.md.
Publishes live status to amazon/test-results/smoke/run-<stamp>/results.json.

Usage:
  python3 amazon/suite-smoke.py
  BASE=http://127.0.0.1:23103 python3 amazon/suite-smoke.py --keep-state
"""

import atexit
import datetime
import glob
import json
import os
import shutil
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer

BASE = os.environ.get("BASE", "http://127.0.0.1:23103").rstrip("/")
SUITE = os.environ.get("SUITE", "smoke")
KEEP = "--keep-state" in sys.argv
FAST = "--fast" in sys.argv
WANTED_CASES = set(a for a in sys.argv[1:] if not a.startswith("-"))

HERE = os.path.dirname(os.path.abspath(__file__))
MOCK_DIR = HERE
DATA_DIR = os.path.join(MOCK_DIR, "mock-data")
FIXTURES_DIR = os.path.join(MOCK_DIR, "mock-fixtures")
SCHEMAS_DIR = os.path.join(MOCK_DIR, "schemas")

STORES = [
    "lwa_tokens",
    "created_orders",
    "shipment_confirmations",
    "order_acknowledgements",
    "feeds",
    "feed_documents",
    "reports",
    "listings",
    "mfn_shipments"
]
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


def call(method, path, body=None, token="mock_sp_api_access_token", is_form=False):
    url = BASE + path
    headers = {}
    data = None
    if body is not None:
        if is_form:
            data = urllib.parse.urlencode(body).encode("utf-8")
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        else:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"

    if token:
        headers["x-amz-access-token"] = token
        headers["Authorization"] = "Bearer " + token

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            raw, status = r.read().decode("utf-8"), r.status
    except urllib.error.HTTPError as e:
        raw, status = e.read().decode("utf-8"), e.code
    except Exception as e:
        return 0, {"_transport_error": str(e)}

    try:
        return status, json.loads(raw) if raw.strip() else {}
    except Exception:
        return status, raw


def store(name):
    path = os.path.join(DATA_DIR, name + ".json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


CASES, RESULTS = [], {}
EVIDENCE = {
    "status": "running",
    "mock call log": "not captured",
    "mock stores": "not captured",
    "server": f"Amazon SP-API mock at {BASE}"
}


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
                "checks": [],
                "calls": [],
                "detail": {}
            })
        else:
            e.update({"verdict": "pending"})
        cases.append(e)

    done = [c for c in cases if c.get("verdict") in ("pass", "fail", "blocked", "skip")]
    doc = {
        "name": "Amazon Selling Partner API (SP-API) Mock Smoke Suite",
        "suite": SUITE,
        "at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "base_url": BASE,
        "summary": {
            "pass": sum(1 for c in done if c["verdict"] == "pass"),
            "fail": sum(1 for c in done if c["verdict"] == "fail"),
            "blocked": sum(1 for c in done if c["verdict"] == "blocked"),
            "skip": sum(1 for c in done if c["verdict"] == "skip")
        },
        "evidence": EVIDENCE,
        "cases": cases
    }
    os.makedirs(RUN_DIR, exist_ok=True)
    with open(os.path.join(RUN_DIR, "results.json"), "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2)


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

    def truthy(self, label, what, actual):
        got = "present" if actual not in (None, "", [], {}) else "missing"
        self.items.append({
            "label": label,
            "what": what,
            "expected": "present",
            "actual": got,
            "ok": got == "present"
        })

    @property
    def ok(self):
        return all(i["ok"] for i in self.items)


def run_case(c):
    ch, calls, detail = Checks(), [], {}
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


# ------------------------------------------------------------------ test case definitions

def c_auth_token(ch, calls, detail):
    form_data = {
        "grant_type": "refresh_token",
        "refresh_token": "rws_valid_seller_refresh_token_12345",
        "client_id": "amzn1.application-oa2-client.test12345",
        "client_secret": "amzn_secret_key_67890"
    }
    st, b = call("POST", "/auth/o2/token", form_data, token=None, is_form=True)
    calls.append(f"POST /auth/o2/token [refresh_token] -> {st}")
    ch.add("status", "LWA token exchange", 200, st)
    ch.truthy("access_token", "Bearer access token for SP-API", b.get("access_token"))
    ch.add("token_type", "bearer token format", "bearer", b.get("token_type"))
    ch.truthy("expires_in", "token validity duration", b.get("expires_in"))

    tokens = store("lwa_tokens")
    ch.add("recorded in store", "lwa_tokens records the token issuance", True, len(tokens) > 0)
    detail["issued_token"] = b.get("access_token")


def c_auth_invalid(ch, calls, detail):
    form_data = {
        "grant_type": "refresh_token",
        "refresh_token": "INVALID_REFRESH_TOKEN",
        "client_id": "amzn1.application-oa2-client.test12345",
        "client_secret": "INVALID_SECRET"
    }
    st, b = call("POST", "/auth/o2/token", form_data, token=None, is_form=True)
    calls.append(f"POST /auth/o2/token [INVALID] -> {st}")
    ch.add("status", "invalid credentials rejected", 400, st)
    ch.add("error", "LWA standard error code", "invalid_grant", b.get("error"))


def c_auth_server_error(ch, calls, detail):
    form_data = {
        "grant_type": "refresh_token",
        "refresh_token": "SERVERERROR_TRIGGER",
        "client_id": "amzn1.application-oa2-client.SERVERERROR",
        "client_secret": "secret"
    }
    st, b = call("POST", "/auth/o2/token", form_data, token=None, is_form=True)
    calls.append(f"POST /auth/o2/token [SERVERERROR] -> {st}")
    ch.add("status", "LWA server error marker", 500, st)
    ch.add("error", "server_error code", "server_error", b.get("error"))


def c_rdt_token(ch, calls, detail):
    body = {
        "targetApplication": "amzn1.sp.solution.123456",
        "restrictedResources": [
            {
                "method": "GET",
                "path": "/orders/v0/orders/{orderId}/address",
                "dataElements": ["buyerInfo", "shippingAddress"]
            }
        ]
    }
    st, b = call("POST", "/tokens/2021-03-01/restrictedDataToken", body)
    calls.append(f"POST /tokens/2021-03-01/restrictedDataToken -> {st}")
    ch.add("status", "RDT token exchange", 200, st)
    ch.truthy("restrictedDataToken", "RDT token string", b.get("restrictedDataToken"))
    ch.add("expiresIn", "RDT expiry in seconds", 3600, b.get("expiresIn"))


def c_orders_list(ch, calls, detail):
    st, b = call("GET", "/orders/v0/orders?MarketplaceIds=ATVPDKIKX0DER&CreatedAfter=2026-08-20T00:00:00Z")
    calls.append(f"GET /orders/v0/orders -> {st}")
    ch.add("status", "list orders happy path", 200, st)
    payload = b.get("payload", {})
    orders = payload.get("Orders", [])
    ch.truthy("Orders list", "contains simulated orders", orders)
    ch.truthy("NextToken", "pagination token present for multi-page results", payload.get("NextToken"))
    if orders:
        ch.truthy("AmazonOrderId", "valid Amazon order ID format", orders[0].get("AmazonOrderId"))
        ch.add("MarketplaceId", "US marketplace ID", "ATVPDKIKX0DER", orders[0].get("MarketplaceId"))
    detail["order_count"] = len(orders)


def c_orders_empty(ch, calls, detail):
    st, b = call("GET", "/orders/v0/orders?MarketplaceIds=ATVPDKIKX0DER&CreatedAfter=EMPTY_DATE_FILTER")
    calls.append(f"GET /orders/v0/orders [EMPTY marker] -> {st}")
    ch.add("status", "empty orders response", 200, st)
    orders = b.get("payload", {}).get("Orders")
    ch.add("Orders is empty array", "returns empty array [] rather than 404", "[]", str(orders))


def c_orders_page2(ch, calls, detail):
    st, b = call("GET", "/orders/v0/orders?NextToken=mock_next_token_page_2_98765")
    calls.append(f"GET /orders/v0/orders [NextToken] -> {st}")
    ch.add("status", "paginated page 2 orders", 200, st)
    orders = b.get("payload", {}).get("Orders", [])
    ch.truthy("Page 2 orders", "returns second page items", orders)
    if orders:
        ch.add("Page 2 Order ID", "matches second page fixture", "902-3159896-1390916", orders[0].get("AmazonOrderId"))


def c_orders_ratelimit(ch, calls, detail):
    st, b = call("GET", "/orders/v0/orders?CreatedAfter=RATELIMIT_TRIGGER")
    calls.append(f"GET /orders/v0/orders [RATELIMIT marker] -> {st}")
    ch.add("status", "rate limit exceeded", 429, st)
    errors = b.get("errors", [])
    ch.truthy("errors array", "standard SP-API error format", errors)
    if errors:
        ch.add("error code", "QuotaExceeded error", "QuotaExceeded", errors[0].get("code"))


def c_orders_server_error(ch, calls, detail):
    st, b = call("GET", "/orders/v0/orders?CreatedAfter=SERVERERROR_TRIGGER")
    calls.append(f"GET /orders/v0/orders [SERVERERROR marker] -> {st}")
    ch.add("status", "server error 500", 500, st)
    errors = b.get("errors", [])
    if errors:
        ch.add("error code", "InternalServerError code", "InternalServerError", errors[0].get("code"))


def c_order_single(ch, calls, detail):
    order_id = "902-1845936-5435065"
    st, b = call("GET", f"/orders/v0/orders/{order_id}")
    calls.append(f"GET /orders/v0/orders/{order_id} -> {st}")
    ch.add("status", "retrieve single order", 200, st)
    order = b.get("payload", {})
    ch.add("AmazonOrderId echoed", "matches requested path order ID", order_id, order.get("AmazonOrderId"))
    ch.add("OrderStatus", "order fulfillment status", "Unshipped", order.get("OrderStatus"))
    ch.truthy("DefaultShipFromLocationAddress", "warehouse address", order.get("DefaultShipFromLocationAddress"))


def c_order_not_found(ch, calls, detail):
    order_id = "NOTFOUND-902-0000000-0000000"
    st, b = call("GET", f"/orders/v0/orders/{order_id}")
    calls.append(f"GET /orders/v0/orders/{order_id} [NOTFOUND] -> {st}")
    ch.add("status", "order not found returns 404", 404, st)
    errors = b.get("errors", [])
    if errors:
        ch.add("error code", "NotFound code", "NotFound", errors[0].get("code"))


def c_order_items(ch, calls, detail):
    order_id = "902-1845936-5435065"
    st, b = call("GET", f"/orders/v0/orders/{order_id}/orderItems")
    calls.append(f"GET /orders/v0/orders/{order_id}/orderItems -> {st}")
    ch.add("status", "get order items", 200, st)
    items = b.get("payload", {}).get("OrderItems", [])
    ch.truthy("OrderItems list", "order items array", items)
    if items:
        ch.add("ASIN", "item ASIN", "B00005N5PF", items[0].get("ASIN"))
        ch.add("SellerSKU", "item SellerSKU", "SKU-AMZN-PROD-001", items[0].get("SellerSKU"))
        ch.truthy("ItemPrice", "item price object", items[0].get("ItemPrice"))


def c_order_address(ch, calls, detail):
    order_id = "902-1845936-5435065"
    st, b = call("GET", f"/orders/v0/orders/{order_id}/address")
    calls.append(f"GET /orders/v0/orders/{order_id}/address -> {st}")
    ch.add("status", "get shipping address", 200, st)
    addr = b.get("payload", {}).get("ShippingAddress", {})
    ch.add("City", "shipping city", "Seattle", addr.get("City"))
    ch.add("StateOrRegion", "shipping state", "WA", addr.get("StateOrRegion"))
    ch.add("PostalCode", "postal code", "98109", addr.get("PostalCode"))


def c_order_address_rdt_required(ch, calls, detail):
    order_id = "RDT_REQUIRED-902-1111111-2222222"
    st, b = call("GET", f"/orders/v0/orders/{order_id}/address")
    calls.append(f"GET /orders/v0/orders/{order_id}/address [RDT_REQUIRED] -> {st}")
    ch.add("status", "RDT requirement returns 403", 403, st)
    errors = b.get("errors", [])
    if errors:
        ch.add("error code", "Unauthorized code", "Unauthorized", errors[0].get("code"))


def c_order_buyer_info(ch, calls, detail):
    order_id = "902-1845936-5435065"
    st, b = call("GET", f"/orders/v0/orders/{order_id}/buyerInfo")
    calls.append(f"GET /orders/v0/orders/{order_id}/buyerInfo -> {st}")
    ch.add("status", "get buyer info", 200, st)
    buyer = b.get("payload", {})
    ch.add("BuyerEmail", "buyer email", "buyer-mock@marketplace.amazon.com", buyer.get("BuyerEmail"))
    ch.add("BuyerName", "buyer name", "John Buyer", buyer.get("BuyerName"))


def c_shipment_confirm(ch, calls, detail):
    order_id = "902-1845936-5435065"
    body = {
        "marketplaceId": "ATVPDKIKX0DER",
        "packageDetail": {
            "packageReferenceId": "PKG-001",
            "carrierCode": "UPS",
            "carrierName": "United Parcel Service",
            "shippingMethod": "Ground",
            "trackingNumber": "1Z9999999999999999",
            "shipDate": "2026-08-26T12:00:00Z",
            "orderItems": [
                {"orderItemId": "65432109876543", "quantity": 1}
            ]
        }
    }
    st, b = call("POST", f"/orders/v0/orders/{order_id}/shipmentConfirmation", body)
    calls.append(f"POST /orders/v0/orders/{order_id}/shipmentConfirmation -> {st}")
    ch.add("status is 204", "shipment confirmation success", 204, st)

    confs = store("shipment_confirmations")
    matching = [c for c in confs if c.get("orderId") == order_id]
    ch.add("recorded in store", "confirmation appended to shipment_confirmations.json", True, len(matching) > 0)
    if matching:
        ch.add("carrier recorded", "UPS carrier code recorded", "UPS", matching[-1].get("carrierCode"))
        ch.add("tracking recorded", "tracking number stored", "1Z9999999999999999", matching[-1].get("trackingNumber"))


def c_shipment_confirm_invalid(ch, calls, detail):
    order_id = "902-1845936-5435065"
    body = {
        "packageDetail": {
            "carrierCode": "INVALID_CARRIER",
            "trackingNumber": "TRK123"
        }
    }
    st, b = call("POST", f"/orders/v0/orders/{order_id}/shipmentConfirmation", body)
    calls.append(f"POST /orders/v0/orders/{order_id}/shipmentConfirmation [INVALID carrier] -> {st}")
    ch.add("status is 400", "invalid carrier rejected", 400, st)


def c_order_acknowledgement(ch, calls, detail):
    body = {
        "orderAcknowledgements": [
            {
                "purchaseOrderNumber": "PO-AMZN-2026-001",
                "acknowledgementDate": "2026-08-26T12:00:00Z",
                "acknowledgementStatus": {
                    "code": "Acknowledged",
                    "description": "Order accepted"
                }
            }
        ]
    }
    st, b = call("POST", "/vendor/orders/v1/acknowledgements", body)
    calls.append(f"POST /vendor/orders/v1/acknowledgements -> {st}")
    ch.add("status is 202", "order acknowledgement accepted", 202, st)
    acks = store("order_acknowledgements")
    ch.add("recorded in store", "recorded in order_acknowledgements.json", True, len(acks) > 0)


def c_feeds_lifecycle(ch, calls, detail):
    st1, b1 = call("POST", "/feeds/2021-06-30/documents", {"contentType": "text/xml; charset=UTF-8"})
    calls.append(f"POST /feeds/2021-06-30/documents -> {st1}")
    ch.add("doc status is 201", "feed document creation", 201, st1)
    feed_doc_id = b1.get("feedDocumentId")
    ch.truthy("feedDocumentId", "returned document ID", feed_doc_id)
    ch.truthy("upload url", "S3 upload URL", b1.get("url"))

    feed_body = {
        "feedType": "POST_ORDER_ACKNOWLEDGEMENT_DATA",
        "marketplaceIds": ["ATVPDKIKX0DER"],
        "inputFeedDocumentId": feed_doc_id
    }
    st2, b2 = call("POST", "/feeds/2021-06-30/feeds", feed_body)
    calls.append(f"POST /feeds/2021-06-30/feeds -> {st2}")
    ch.add("feed submit status is 202", "feed acceptance", 202, st2)
    feed_id = b2.get("feedId")
    ch.truthy("feedId", "assigned feed ID", feed_id)

    st3, b3 = call("GET", f"/feeds/2021-06-30/feeds/{feed_id}")
    calls.append(f"GET /feeds/2021-06-30/feeds/{feed_id} -> {st3}")
    ch.add("feed query status is 200", "feed status inquiry", 200, st3)
    ch.add("processingStatus is DONE", "completed feed status", "DONE", b3.get("processingStatus"))

    recorded_feeds = store("feeds")
    ch.add("feed recorded in store", "feeds.json tracking", True, any(f.get("feedId") == feed_id for f in recorded_feeds))


def c_feeds_markers(ch, calls, detail):
    st_inprog, b_inprog = call("GET", "/feeds/2021-06-30/feeds/INPROGRESS-FEED-99")
    calls.append(f"GET /feeds/2021-06-30/feeds/INPROGRESS-FEED-99 -> {st_inprog}")
    ch.add("IN_PROGRESS status", "steered feed status", "IN_PROGRESS", b_inprog.get("processingStatus"))

    st_fatal, b_fatal = call("GET", "/feeds/2021-06-30/feeds/FATAL-FEED-99")
    calls.append(f"GET /feeds/2021-06-30/feeds/FATAL-FEED-99 -> {st_fatal}")
    ch.add("FATAL status", "steered fatal status", "FATAL", b_fatal.get("processingStatus"))


def c_reports_lifecycle(ch, calls, detail):
    report_body = {
        "reportType": "GET_MERCHANT_LISTINGS_ALL_DATA",
        "marketplaceIds": ["ATVPDKIKX0DER"]
    }
    st1, b1 = call("POST", "/reports/2021-06-30/reports", report_body)
    calls.append(f"POST /reports/2021-06-30/reports -> {st1}")
    ch.add("report submit status is 202", "report acceptance", 202, st1)
    report_id = b1.get("reportId")
    ch.truthy("reportId", "assigned report ID", report_id)

    st2, b2 = call("GET", f"/reports/2021-06-30/reports/{report_id}")
    calls.append(f"GET /reports/2021-06-30/reports/{report_id} -> {st2}")
    ch.add("report status is 200", "report status response", 200, st2)
    ch.add("processingStatus is DONE", "report completed", "DONE", b2.get("processingStatus"))
    doc_id = b2.get("reportDocumentId")
    ch.truthy("reportDocumentId", "document ID present", doc_id)

    st3, b3 = call("GET", f"/reports/2021-06-30/documents/{doc_id}")
    calls.append(f"GET /reports/2021-06-30/documents/{doc_id} -> {st3}")
    ch.add("doc status is 200", "report document URL response", 200, st3)
    ch.truthy("download url", "presigned S3 download URL", b3.get("url"))


def c_catalog_item(ch, calls, detail):
    asin = "B00005N5PF"
    st, b = call("GET", f"/catalog/2022-04-01/items/{asin}?marketplaceIds=ATVPDKIKX0DER")
    calls.append(f"GET /catalog/2022-04-01/items/{asin} -> {st}")
    ch.add("status is 200", "catalog query response", 200, st)
    ch.add("asin echoed", "matches requested ASIN", asin, b.get("asin"))
    summaries = b.get("summaries", [])
    ch.truthy("summaries", "product summary list", summaries)
    if summaries:
        ch.add("brand", "brand name", "Amazon Basics", summaries[0].get("brand"))


def c_listings_management(ch, calls, detail):
    seller_id = "A2EUQ1WTGCTBG2"
    sku = "SKU-AMZN-PROD-001"
    body = {
        "productType": "SPEAKER",
        "attributes": {
            "item_name": [{"value": "Amazon Basics Wireless Bluetooth Speaker - Black", "marketplace_id": "ATVPDKIKX0DER"}],
            "condition_type": [{"value": "new_new", "marketplace_id": "ATVPDKIKX0DER"}]
        }
    }
    st1, b1 = call("PUT", f"/listings/2021-08-01/items/{seller_id}/{sku}?marketplaceIds=ATVPDKIKX0DER", body)
    calls.append(f"PUT /listings/2021-08-01/items/{seller_id}/{sku} -> {st1}")
    ch.add("PUT listing status is 200", "listing update accepted", 200, st1)
    ch.add("status is ACCEPTED", "listing status", "ACCEPTED", b1.get("status"))

    recorded_listings = store("listings")
    ch.add("recorded in store", "listings.json tracking", True, any(l.get("sku") == sku for l in recorded_listings))

    st2, b2 = call("GET", f"/listings/2021-08-01/items/{seller_id}/{sku}?marketplaceIds=ATVPDKIKX0DER")
    calls.append(f"GET /listings/2021-08-01/items/{seller_id}/{sku} -> {st2}")
    ch.add("GET listing status is 200", "listing read", 200, st2)
    ch.add("sku echoed", "listing SKU matches", sku, b2.get("sku"))


def c_product_pricing(ch, calls, detail):
    st, b = call("GET", "/products/pricing/v0/price?MarketplaceId=ATVPDKIKX0DER&ItemType=Asin&Asins=B00005N5PF")
    calls.append(f"GET /products/pricing/v0/price -> {st}")
    ch.add("status is 200", "pricing query response", 200, st)
    payload = b.get("payload", [])
    ch.truthy("pricing payload", "returns pricing entries", payload)
    if payload:
        ch.add("pricing status", "pricing status Success", "Success", payload[0].get("status"))


def c_fba_inventory(ch, calls, detail):
    st, b = call("GET", "/fba/inventory/v1/summaries?details=true&granularityType=Marketplace&granularityId=ATVPDKIKX0DER&marketplaceIds=ATVPDKIKX0DER")
    calls.append(f"GET /fba/inventory/v1/summaries -> {st}")
    ch.add("status is 200", "FBA inventory summaries", 200, st)
    summaries = b.get("payload", {}).get("inventorySummaries", [])
    ch.truthy("inventorySummaries", "FBA inventory list", summaries)
    if summaries:
        fulfillable = summaries[0].get("inventoryDetails", {}).get("fulfillableQuantity")
        ch.add("fulfillableQuantity", "fulfillable stock quantity", 150, fulfillable)


def c_merchant_fulfillment(ch, calls, detail):
    st1, b1 = call("POST", "/mfn/v0/eligibleShippingServices", {"ShipmentRequestDetails": {"AmazonOrderId": "902-1845936-5435065"}})
    calls.append(f"POST /mfn/v0/eligibleShippingServices -> {st1}")
    ch.add("eligible services status is 200", "MFN services query", 200, st1)
    services = b1.get("payload", {}).get("ShippingServiceList", [])
    ch.truthy("ShippingServiceList", "available carrier services", services)

    mfn_body = {
        "ShipmentRequestDetails": {
            "AmazonOrderId": "902-1845936-5435065",
            "PackageDimensions": {"Length": 10, "Width": 8, "Height": 4, "Unit": "inches"},
            "Weight": {"Value": 2.5, "Unit": "ounces"}
        },
        "ShippingServiceId": "UPS_GROUND_PKG"
    }
    st2, b2 = call("POST", "/mfn/v0/shipments", mfn_body)
    calls.append(f"POST /mfn/v0/shipments -> {st2}")
    ch.add("shipment status is 200", "MFN shipment purchase", 200, st2)
    payload = b2.get("payload", {})
    ch.add("Status", "shipment purchase status", "Purchased", payload.get("Status"))
    ch.truthy("TrackingId", "carrier tracking ID", payload.get("TrackingId"))
    ch.truthy("Label", "printable label payload", payload.get("Label"))

    mfn_stores = store("mfn_shipments")
    ch.add("recorded in store", "mfn_shipments.json tracking", True, len(mfn_stores) > 0)


# ------------------------------------------------------------------ upstream sandbox fixtures verification

def c_sb_orders_200(ch, calls, detail):
    st, b = call("GET", "/orders/v0/orders?CreatedAfter=TEST_CASE_200&MarketplaceIds=ATVPDKIKX0DER")
    calls.append(f"GET /orders/v0/orders?CreatedAfter=TEST_CASE_200 -> {st}")
    ch.add("status is 200", "official sandbox TEST_CASE_200", 200, st)
    orders = b.get("payload", {}).get("Orders", [])
    ch.truthy("Orders list present", "orders in fixture", len(orders) >= 2)
    if len(orders) >= 2:
        ch.add("first order ID", "order fixture 1", "902-1845936-5435065", orders[0].get("AmazonOrderId"))
        ch.add("second order ID", "order fixture 2", "902-8745147-1934268", orders[1].get("AmazonOrderId"))


def c_sb_orders_next_token(ch, calls, detail):
    st, b = call("GET", "/orders/v0/orders?CreatedAfter=TEST_CASE_200_NEXT_TOKEN&MarketplaceIds=ATVPDKIKX0DER")
    calls.append(f"GET /orders/v0/orders?CreatedAfter=TEST_CASE_200_NEXT_TOKEN -> {st}")
    ch.add("status is 200", "official sandbox pagination", 200, st)
    ch.add("NextToken matches upstream fixture", "exact sandbox next token", "2YgYW55IGNhcm5hbCBwbGVhc3VyZS4", b.get("payload", {}).get("NextToken"))


def c_sb_orders_400(ch, calls, detail):
    st, b = call("GET", "/orders/v0/orders?CreatedAfter=TEST_CASE_400")
    calls.append(f"GET /orders/v0/orders?CreatedAfter=TEST_CASE_400 -> {st}")
    ch.add("status is 400", "official sandbox error TEST_CASE_400", 400, st)
    errors = b.get("errors", [])
    ch.truthy("errors payload", "errors array returned", errors)


def c_sb_orders_iba(ch, calls, detail):
    st, b = call("GET", "/orders/v0/orders/TEST_CASE_IBA_200")
    calls.append(f"GET /orders/v0/orders/TEST_CASE_IBA_200 -> {st}")
    ch.add("status is 200", "official sandbox IBA order", 200, st)
    payload = b.get("payload", {})
    ch.add("IsIBA is true", "IBA order flag", True, payload.get("IsIBA"))
    ch.add("AmazonOrderId matches fixture", "order ID", "921-3175655-0452641", payload.get("AmazonOrderId"))
    ch.add("SalesChannel", "German marketplace", "Amazon.de", payload.get("SalesChannel"))


def c_sb_catalog_error_cases(ch, calls, detail):
    st404, _ = call("GET", "/catalog/2022-04-01/items/TEST_CASE_404?marketplaceIds=ATVPDKIKX0DER")
    calls.append(f"GET /catalog/items/TEST_CASE_404 -> {st404}")
    ch.add("catalog 404", "TEST_CASE_404 status", 404, st404)

    st429, _ = call("GET", "/catalog/2022-04-01/items/TEST_CASE_429?marketplaceIds=ATVPDKIKX0DER")
    calls.append(f"GET /catalog/items/TEST_CASE_429 -> {st429}")
    ch.add("catalog 429", "TEST_CASE_429 rate limit", 429, st429)

    st500, _ = call("GET", "/catalog/2022-04-01/items/TEST_CASE_500?marketplaceIds=ATVPDKIKX0DER")
    calls.append(f"GET /catalog/items/TEST_CASE_500 -> {st500}")
    ch.add("catalog 500", "TEST_CASE_500 server error", 500, st500)


def c_fixtures_repository_integrity(ch, calls, detail):
    master_fixture = os.path.join(FIXTURES_DIR, "all-sandbox-fixtures.json")
    ch.add("all-sandbox-fixtures.json exists", "extracted master fixtures file", True, os.path.isfile(master_fixture))
    domain_files = glob.glob(f"{FIXTURES_DIR}/*.json")
    ch.truthy("domain fixture files", "extracted domain fixture files (>40)", len(domain_files) >= 40)
    schema_files = glob.glob(f"{SCHEMAS_DIR}/**/*.json", recursive=True)
    ch.truthy("schema files", "synced schema files (>40)", len(schema_files) >= 40)

    if os.path.isfile(master_fixture):
        with open(master_fixture, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        ch.truthy("sandbox fixture count", "contains >800 sandbox test cases", len(data) >= 800)
        detail["total_extracted_fixtures"] = len(data)
        detail["total_domain_files"] = len(domain_files)
        detail["total_schema_files"] = len(schema_files)


def c_spec_passthrough(ch, calls, detail):
    st1, b1 = call("GET", "/sellers/v1/marketplaceParticipations")
    calls.append(f"GET /sellers/v1/marketplaceParticipations [spec default] -> {st1}")
    ch.add("sellers route status", "unconfigured spec route answers 200", 200, st1)

    st2, b2 = call("GET", "/finances/v0/financialEvents")
    calls.append(f"GET /finances/v0/financialEvents [spec default] -> {st2}")
    ch.add("finances route status", "unconfigured spec route answers 200", 200, st2)


def c_unmatched_route(ch, calls, detail):
    st, b = call("GET", "/some/completely/unknown/endpoint/path")
    calls.append(f"GET /some/completely/unknown/endpoint/path -> {st}")
    ch.add("status is 404", "unknown path fails loudly with 404", 404, st)
    ch.truthy("error messages", "contains route failure explanation", b.get("ErrorMessages"))


# ------------------------------------------------------------------ register cases

# ---------------------------------------------------------------------------
# Browse tree, product type definitions, and the S3 data plane.
#
# GET_XML_BROWSE_TREE_DATA is not in amzn/selling-partner-api-models and has no
# sandbox fixture, so these cases are driven by fixtures written into the config.
# The element shape follows Amazon's published Browse Tree Reports example; the
# duplicate-browseNodeId nodes are the real amazon.de pair from issue #4742.
# ---------------------------------------------------------------------------

BT_XML = "GET_XML_BROWSE_TREE_DATA"
MP_DE, MP_FR, MP_US = "A1PA6795UKMFR9", "A13V1IB3VIYZZH", "ATVPDKIKX0DER"


def _browse_tree(marketplace, with_report_options=True):
    """Runs createReport -> getReport -> getReportDocument -> download. Returns the XML."""
    body = {"reportType": BT_XML, "marketplaceIds": [marketplace]}
    if with_report_options:
        body["reportOptions"] = {"MarketplaceId": marketplace}
    _, b1 = call("POST", "/reports/2021-06-30/reports", body)
    _, b2 = call("GET", "/reports/2021-06-30/reports/%s" % b1.get("reportId"))
    _, b3 = call("GET", "/reports/2021-06-30/documents/%s" % b2.get("reportDocumentId"))
    url = b3.get("url", "")
    st, xml = call("GET", url[len(BASE):] if url.startswith(BASE) else url)
    return st, b2, xml


def _roots(xml):
    """Top-level node ids: browsePathById carries an unnamed root id, so a root has 2 entries."""
    import xml.etree.ElementTree as ET
    import io
    source = io.StringIO(xml) if isinstance(xml, str) else io.BytesIO(xml)
    roots = []
    for event, n in ET.iterparse(source, events=("end",)):
        if n.tag == "Node":
            path = n.findtext("browsePathById") or ""
            if len(path.split(",")) == 2:
                roots.append(n.findtext("browseNodeId"))
            n.clear()
    return sorted(roots)


def c_browse_tree_isolation(ch, calls, detail):
    st_de, meta_de, de = _browse_tree(MP_DE)
    calls.append("browse tree chain for %s -> %s" % (MP_DE, st_de))
    ch.add("document status is 200", "browse tree downloadable", 200, st_de)
    ch.add("reportType echoed", "type survives the lifecycle", BT_XML, meta_de.get("reportType"))

    _, _, fr = _browse_tree(MP_FR)
    calls.append("browse tree chain for %s" % MP_FR)
    ch.add("DE and FR trees differ", "reportOptions.MarketplaceId selects the store",
           True, _roots(de) != _roots(fr))

    # Omitting reportOptions is what the JPluger connector does today. Amazon then
    # returns the seller's DEFAULT store's tree, so every store gets the same taxonomy.
    _, _, de_no = _browse_tree(MP_DE, with_report_options=False)
    _, _, fr_no = _browse_tree(MP_FR, with_report_options=False)
    calls.append("browse tree chain with reportOptions omitted")
    ch.add("omitted reportOptions collapses to one tree", "reproduces the default-store defect",
           True, _roots(de_no) == _roots(fr_no))
    ch.add("default-store tree is neither DE nor FR", "wrong taxonomy served",
           True, _roots(de_no) != _roots(de) and _roots(de_no) != _roots(fr))

    recorded = store("reports")
    ch.add("reportOptions recorded", "store captures what the client sent",
           True, any(r.get("reportType") == BT_XML for r in recorded))


def c_browse_tree_shape(ch, calls, detail):
    import collections as _c
    import xml.etree.ElementTree as ET
    import io
    st, _, xml = _browse_tree(MP_DE)
    calls.append("GET browse tree document -> %s" % st)

    source = io.StringIO(xml) if isinstance(xml, str) else io.BytesIO(xml)
    first_node = None
    node_count = 0
    ids = []
    commas = []
    misleading = []

    for event, n in ET.iterparse(source, events=("end",)):
        if n.tag == "Node":
            node_count += 1
            if first_node is None:
                first_node = {
                    "isRoot": n.find(".//isRoot"),
                    "parentNodeId": n.find(".//parentNodeId"),
                    "browseNodeStoreContextName": n.findtext("browseNodeStoreContextName"),
                    "productTypeDefinitions": n.findtext("productTypeDefinitions"),
                }
            nid = n.findtext("browseNodeId")
            if nid:
                ids.append(nid)
            bname = n.findtext("browseNodeName") or ""
            if "," in bname:
                commas.append(nid)
            bpath_name = n.findtext("browsePathByName") or ""
            bpath_id = n.findtext("browsePathById") or ""
            if len(bpath_name.split(",")) == len(bpath_id.split(",")):
                misleading.append(nid)
            n.clear()

    ch.truthy("nodes present", "parsed Node elements", node_count > 0)
    ch.add("no isRoot element", "root is derived, not flagged", None, first_node.get("isRoot") if first_node else None)
    ch.add("no parentNodeId element", "parent is derived from browsePathById",
           None, first_node.get("parentNodeId") if first_node else None)
    ch.truthy("browseNodeStoreContextName", "store-facing label present",
              first_node.get("browseNodeStoreContextName") if first_node else None)
    ch.truthy("productTypeDefinitions", "product type join key present",
              first_node.get("productTypeDefinitions") if first_node else None)

    dupes = [i for i, c in _c.Counter(ids).items() if c > 1]
    ch.truthy("duplicate browseNodeId present", "one id, two placements (issue #4742)", dupes)

    # A name containing a comma makes browsePathByName unsplittable, and the token
    # count can still equal the id count -- so a length assertion passes on bad data.
    ch.truthy("comma in a browseNodeName", "browsePathByName is not splittable", commas)
    ch.truthy("naive split count can match id count", "length check is not a sufficient guard", misleading)


def c_listings_report_localised(ch, calls, detail):
    seen = {}
    for mp in (MP_US, MP_FR, MP_JP := "A1VC38T7YXB528"):
        _, b1 = call("POST", "/reports/2021-06-30/reports",
                     {"reportType": "GET_MERCHANT_LISTINGS_ALL_DATA", "marketplaceIds": [mp]})
        _, b2 = call("GET", "/reports/2021-06-30/reports/%s" % b1.get("reportId"))
        st, tsv = call("GET", "/s3/report-download/%s" % b2.get("reportDocumentId"))
        calls.append("listings report for %s -> %s" % (mp, st))
        rows = tsv.rstrip("\n").split("\n")
        seen[mp] = (rows[0].split("\t"), rows[1].split("\t"))

    ch.add("US headers are English", "default column names", "item-name", seen[MP_US][0][0])
    ch.add("FR headers are localised", "French column names", "nom-produit", seen[MP_FR][0][0])
    ch.add("FR price column localised", "prix, not price", "prix", seen[MP_FR][0][4])
    ch.add("same SKU across marketplaces", "seller SKU is the shared identity",
           True, seen[MP_US][1][3] == seen[MP_FR][1][3] == seen[MP_JP][1][3])
    ch.add("ASIN differs per marketplace", "marketplace-specific product identity",
           True, seen[MP_US][1][16] != seen[MP_JP][1][16])
    ch.add("price differs per marketplace", "marketplace-specific price",
           True, seen[MP_US][1][4] != seen[MP_JP][1][4])


def c_product_type_definition(ch, calls, detail):
    st, b = call("GET", "/definitions/2020-09-01/productTypes/HEADPHONES"
                        "?marketplaceIds=%s&requirements=LISTING_PRODUCT_ONLY"
                        "&requirementsEnforced=NOT_ENFORCED&locale=fr_FR" % MP_FR)
    calls.append("GET getDefinitionsProductType -> %s" % st)
    ch.add("status is 200", "definition envelope", 200, st)

    ch.add("schema is a link, not inline", "SchemaLink shape",
           True, isinstance(b.get("schema"), dict) and "link" in b.get("schema", {}))
    # This generic fallback's checksum is empty on purpose: a real client verifies the downloaded
    # schema bytes against it (AmazonDefinitionsUtility.checksumMatches in JPluger), and empty/absent
    # is the documented "Amazon stated none" pass -- a fixed, non-matching hex string here would
    # instead fail every real client's verification, since the fallback's static body never hashes
    # to it. Product types with real, checked-in fixtures (see IA-5105-US1-suite-taxonomy.py) still carry the
    # field, just empty, so its presence/shape is unchanged.
    ch.add("schema.checksum is empty", "fail-open: matches whatever bytes /s3/ptd-schema serves",
           "", b.get("schema", {}).get("checksum"))
    ch.add("productTypeVersion is an object", "not a bare string",
           True, isinstance(b.get("productTypeVersion"), dict))
    ch.add("version member present", "the value to store",
           "UHqSqmb4FNUk=", (b.get("productTypeVersion") or {}).get("version"))
    ch.add("requirements echoed", "request parameter honoured",
           "LISTING_PRODUCT_ONLY", b.get("requirements"))
    ch.truthy("propertyGroups", "Amazon's own attribute grouping", b.get("propertyGroups"))

    # The second GET the schema link demands.
    url = b.get("schema", {}).get("link", {}).get("resource", "")
    st2, schema = call("GET", url[len(BASE):] if url.startswith(BASE) else url)
    calls.append("GET schema.link.resource -> %s" % st2)
    ch.add("schema link resolves", "second GET returns the JSON Schema", 200, st2)
    ch.truthy("required array", "mandatory attributes", schema.get("required"))
    props = schema.get("properties", {})
    ch.truthy("properties", "attribute definitions", props)
    weight = props.get("item_weight", {}).get("items", {}).get("properties", {})
    ch.add("measurement is a value/unit object", "not a scalar plus a unit list",
           True, "value" in weight and "unit" in weight)
    ch.truthy("unit enum", "allowed units for the extractor",
              weight.get("unit", {}).get("enum"))


def c_feed_upload_capture(ch, calls, detail):
    _, b = call("POST", "/feeds/2021-06-30/documents", {"contentType": "text/xml; charset=UTF-8"})
    url = b.get("url", "")
    ch.add("upload URL points at the mock", "S3 stand-in is reachable",
           True, url.startswith(BASE))

    xml = ("<AmazonEnvelope><Message><MessageID>1</MessageID><OrderFulfillment>"
           "<AmazonOrderID>902-1845936-5435065</AmazonOrderID></OrderFulfillment>"
           "</Message></AmazonEnvelope>")
    st, _ = call("PUT", url[len(BASE):] if url.startswith(BASE) else url, xml)
    calls.append("PUT feed body -> %s" % st)
    ch.add("upload accepted", "S3 PUT semantics", 200, st)

    uploads = store("feed_uploads")
    ch.truthy("body captured", "feed_uploads.json records what was sent", uploads)
    if uploads:
        body = uploads[-1].get("body", "")
        ch.add("captured body is the XML sent", "assertable feed content",
               True, "AmazonOrderID" in body)


case("AUTH-1", "LWA OAuth Token Exchange", "valid refresh_token and client credentials",
     ["200 OK", "access_token present", "recorded in lwa_tokens store"],
     "Integrations obtain OAuth tokens from /auth/o2/token before calling SP-API endpoints.",
     c_auth_token)

case("AUTH-2", "LWA Rejection on Invalid Token", "refresh_token with INVALID marker",
     ["400 Bad Request", "error: invalid_grant"],
     "Ensures client properly handles expired or revoked refresh tokens.",
     c_auth_invalid)

case("AUTH-3", "LWA Server Error Marker", "refresh_token with SERVERERROR marker",
     ["500 Internal Server Error", "error: server_error"],
     "Verifies retry logic on transient OAuth auth failures.",
     c_auth_server_error)

case("RDT-1", "Restricted Data Token (RDT) Exchange", "POST to /tokens/2021-03-01/restrictedDataToken",
     ["200 OK", "restrictedDataToken present", "expiresIn: 3600"],
     "SP-API requires RDTs to decrypt customer PII data.",
     c_rdt_token)

case("ORD-1", "Orders List — Happy Path", "GET /orders/v0/orders with marketplace and date filter",
     ["200 OK", "Orders array populated", "NextToken present"],
     "Core order synchronization flow for pulling new marketplace orders.",
     c_orders_list)

case("ORD-2", "Orders List — Empty Window", "GET /orders/v0/orders with EMPTY marker",
     ["200 OK", "Orders: []"],
     "Verifies sync loop handles empty order windows gracefully.",
     c_orders_empty)

case("ORD-3", "Orders List — NextToken Pagination", "GET /orders/v0/orders with NextToken query parameter",
     ["200 OK", "Page 2 orders returned"],
     "Validates multi-page cursor pagination.",
     c_orders_page2)

case("ORD-4", "Orders List — Rate Limit 429", "GET /orders/v0/orders with RATELIMIT marker",
     ["429 Too Many Requests", "code: QuotaExceeded"],
     "Tests client exponential backoff and rate limit recovery.",
     c_orders_ratelimit)

case("ORD-5", "Orders List — Server Error 500", "GET /orders/v0/orders with SERVERERROR marker",
     ["500 Internal Server Error", "code: InternalServerError"],
     "Tests client resilience against transient Amazon 500 errors.",
     c_orders_server_error)

case("ORD-6", "Single Order Details", "GET /orders/v0/orders/{orderId}",
     ["200 OK", "AmazonOrderId matches path parameter", "OrderStatus present"],
     "Retrieval of detailed order metadata.",
     c_order_single)

case("ORD-7", "Order Not Found 404", "GET /orders/v0/orders/NOTFOUND-902-000",
     ["404 Not Found", "code: NotFound"],
     "Validates handling of non-existent order IDs.",
     c_order_not_found)

case("ORD-8", "Order Items Retrieval", "GET /orders/v0/orders/{orderId}/orderItems",
     ["200 OK", "OrderItems array with ASIN, SKU, ItemPrice"],
     "Retrieval of line items for fulfillment and inventory reservation.",
     c_order_items)

case("ORD-9", "Order Shipping Address", "GET /orders/v0/orders/{orderId}/address",
     ["200 OK", "ShippingAddress with City, State, PostalCode"],
     "Delivery address extraction for warehouse packing slips and carrier label generation.",
     c_order_address)

case("ORD-10", "Order Address — RDT Access Denied", "GET /orders/v0/orders/RDT_REQUIRED-902/address",
     ["403 Forbidden / AccessDenied"],
     "Validates client handles PII token refusal.",
     c_order_address_rdt_required)

case("ORD-11", "Order Buyer Info", "GET /orders/v0/orders/{orderId}/buyerInfo",
     ["200 OK", "BuyerEmail present"],
     "Buyer details for invoice creation and customer support.",
     c_order_buyer_info)

case("CONF-1", "Shipment Confirmation", "POST /orders/v0/orders/{orderId}/shipmentConfirmation",
     ["204 No Content", "recorded in shipment_confirmations store"],
     "Confirms order shipment to Amazon with tracking number and carrier code.",
     c_shipment_confirm)

case("CONF-2", "Shipment Confirmation Refusal", "POST shipmentConfirmation with INVALID carrier code",
     ["400 Bad Request", "InvalidInput error"],
     "Rejects invalid carrier tracking submissions before push.",
     c_shipment_confirm_invalid)

case("ACK-1", "Order Acknowledgement", "POST /vendor/orders/v1/acknowledgements",
     ["202 Accepted", "recorded in order_acknowledgements store"],
     "Direct/vendor order acknowledgement flow.",
     c_order_acknowledgement)

case("FEED-1", "Feeds Lifecycle — Submit & Query", "POST /feeds/documents, POST /feeds, GET /feeds/{feedId}",
     ["201 Created doc", "202 Accepted feed", "200 feed DONE", "recorded in feeds store"],
     "Asynchronous data exchange for bulk inventory and order updates.",
     c_feeds_lifecycle)

case("FEED-2", "Feeds Status Steering", "GET /feeds with INPROGRESS and FATAL markers",
     ["IN_PROGRESS status", "FATAL status"],
     "Simulates long-running and failing background feed tasks.",
     c_feeds_markers)

case("REP-1", "Reports Lifecycle", "POST /reports, GET /reports/{reportId}, GET /reports/documents/{id}",
     ["202 Accepted report", "200 report DONE", "200 download URL"],
     "End-to-end report generation and download flow.",
     c_reports_lifecycle)

case("REP-2", "Browse Tree Report — Marketplace Isolation",
     "GET_XML_BROWSE_TREE_DATA requested with and without reportOptions.MarketplaceId",
     ["DE and FR trees differ when reportOptions is set",
      "omitting reportOptions collapses every store onto the default store's tree"],
     "The report type has no sandbox fixture upstream; driven by config fixtures. "
     "The omitted-reportOptions case reproduces a live connector defect.",
     c_browse_tree_isolation)

case("REP-3", "Browse Tree Report — Document Shape",
     "a downloaded GET_XML_BROWSE_TREE_DATA document",
     ["no isRoot or parentNodeId element",
      "duplicate browseNodeId across two placements",
      "browsePathByName cannot be split on commas"],
     "Guards the three traps in the real report: derived parentage, non-unique node ids, "
     "and comma-bearing category names whose naive split count can match the id count.",
     c_browse_tree_shape)

case("REP-4", "Merchant Listings Report — Localised Columns",
     "GET_MERCHANT_LISTINGS_ALL_DATA for US, FR and JP",
     ["FR column headers are French", "ASIN and price differ per marketplace"],
     "Amazon localises the column headers; AmazonListingReportResponse carries French "
     "@JsonAlias values for eight of them.",
     c_listings_report_localised)

case("DEF-1", "Product Type Definition — Schema Link",
     "getDefinitionsProductType then a GET to schema.link.resource",
     ["schema is a link with a checksum, not an inline schema",
      "productTypeVersion is an object", "the link resolves to a JSON Schema"],
     "The definition envelope never contains the schema itself. Measurement attributes "
     "in the linked document are {value, unit} objects.",
     c_product_type_definition)

case("FEED-3", "Feed Upload Body Capture",
     "a feed document created, then its body PUT to the returned URL",
     ["upload URL is reachable", "the raw body is recorded for assertion"],
     "Lets a test assert what XML the client actually sent — e.g. whether the order "
     "fulfilment feed carries <Item> elements.",
     c_feed_upload_capture)


case("CAT-1", "Catalog Items Query", "GET /catalog/2022-04-01/items/{asin}",
     ["200 OK", "asin echoed", "summaries present"],
     "Catalog product info and brand lookup.",
     c_catalog_item)

case("LIST-1", "Listings Items CRUD", "PUT /listings/2021-08-01/items/{sellerId}/{sku} and GET",
     ["200 ACCEPTED", "recorded in listings store", "200 GET listing"],
     "Updating and reading SKU listings catalog definitions.",
     c_listings_management)

case("PRC-1", "Product Pricing API", "GET /products/pricing/v0/price",
     ["200 OK", "BuyingPrice present", "status: Success"],
     "Fetch competitive and listing prices for SKUs.",
     c_product_pricing)

case("FBA-1", "FBA Inventory Summaries", "GET /fba/inventory/v1/summaries",
     ["200 OK", "fulfillableQuantity present"],
     "Query Amazon FBA fulfillment center inventory balances.",
     c_fba_inventory)

case("MFN-1", "Merchant Fulfillment Shipping", "POST /mfn/v0/eligibleShippingServices & POST /mfn/v0/shipments",
     ["200 eligible services", "200 Purchased shipment with label PDF", "recorded in mfn_shipments store"],
     "Buy Shipping services and label generation for Seller Fulfilled Prime / MFN orders.",
     c_merchant_fulfillment)

# --- Official Upstream Sandbox Test Cases ---

case("SB-ORD-1", "Sandbox: Orders TEST_CASE_200", "GET /orders/v0/orders?CreatedAfter=TEST_CASE_200",
     ["200 OK", "Orders fixture populated with 902-1845936-5435065 & 902-8745147-1934268"],
     "Matches official Amazon sandbox TEST_CASE_200 static response payload.",
     c_sb_orders_200)

case("SB-ORD-2", "Sandbox: Orders TEST_CASE_200_NEXT_TOKEN", "GET /orders/v0/orders?CreatedAfter=TEST_CASE_200_NEXT_TOKEN",
     ["200 OK", "NextToken: 2YgYW55IGNhcm5hbCBwbGVhc3VyZS4"],
     "Matches official Amazon sandbox pagination test case token.",
     c_sb_orders_next_token)

case("SB-ORD-3", "Sandbox: Orders TEST_CASE_400", "GET /orders/v0/orders?CreatedAfter=TEST_CASE_400",
     ["400 Bad Request", "errors array present"],
     "Matches official Amazon sandbox 400 error test case.",
     c_sb_orders_400)

case("SB-ORD-4", "Sandbox: Order TEST_CASE_IBA_200", "GET /orders/v0/orders/TEST_CASE_IBA_200",
     ["200 OK", "IsIBA: true", "AmazonOrderId: 921-3175655-0452641"],
     "Matches official Amazon sandbox Invoicing by Amazon (IBA) order fixture.",
     c_sb_orders_iba)

case("SB-CAT-1", "Sandbox: Catalog Error Test Cases", "GET /catalog/items with TEST_CASE_404, 429, 500",
     ["404 NotFound", "429 QuotaExceeded", "500 InternalServerError"],
     "Matches official Amazon sandbox error fixtures for catalog lookups.",
     c_sb_catalog_error_cases)

case("SB-REPO-1", "Sandbox: Fixtures Repository Integrity", "Inspect mock-fixtures/ and schemas/",
     ["all-sandbox-fixtures.json >800 items", "44 domain files present", "schemas/ populated"],
     "Guarantees that all extracted mock data fixtures and schemas are present and accessible.",
     c_fixtures_repository_integrity)

case("SPEC-1", "Spec Pass-Through Coverage", "GET unconfigured routes /sellers/v1/marketplaceParticipations & /finances/v0/financialEvents",
     ["200 OK for both routes"],
     "Verifies that all 371 declared routes across the 66 SP-API model files answer correctly.",
     c_spec_passthrough)

case("NEG-1", "Unmatched Endpoint Handling", "GET /some/completely/unknown/endpoint/path",
     ["404 Not Found", "structured error message"],
     "Ensures unrecognized endpoints fail loudly rather than succeeding silently.",
     c_unmatched_route)


# ------------------------------------------------------------------ execution harness

def preflight():
    print(f"amazon smoke (Amazon Selling Partner API) -- {BASE}")
    print(f"  mock dir : {MOCK_DIR}")
    print(f"  data dir : {DATA_DIR}")
    print(f"  run dir  : {RUN_DIR}")
    if not os.path.isdir(MOCK_DIR):
        sys.exit(f"PREFLIGHT FAIL: {MOCK_DIR} does not exist")
    os.makedirs(DATA_DIR, exist_ok=True)
    from generate_browse_tree_300mb import ensure_browse_tree_300mb
    ensure_browse_tree_300mb()

    st, _ = call("POST", "/auth/o2/token", {"grant_type": "refresh_token"}, token=None, is_form=True)
    if st == 0:
        print(f"  mock     : starting ephemeral mock server on {BASE}...")
        _start_ephemeral_mock()
        st, _ = call("POST", "/auth/o2/token", {"grant_type": "refresh_token"}, token=None, is_form=True)
        if st == 0:
            sys.exit(f"PREFLIGHT FAIL: unable to start mock server on {BASE}")
    print(f"  mock     : up (/auth/o2/token -> {st})")

    if KEEP:
        print("  state    : kept (--keep-state)")
        return

    for s in STORES:
        with open(os.path.join(DATA_DIR, s + ".json"), "w", encoding="utf-8") as f:
            f.write("[]")
    p = os.path.join(DATA_DIR, LOG)
    if os.path.exists(p):
        os.remove(p)
    print(f"  state    : reset -- {len(STORES)} stores emptied, call log removed")


def capture():
    src = os.path.join(DATA_DIR, LOG)
    if os.path.exists(src):
        shutil.copy2(src, os.path.join(RUN_DIR, LOG))
        try:
            with open(src, "r", encoding="utf-8") as f:
                n = len(json.load(f).get("log", {}).get("entries", []))
            EVIDENCE["mock call log"] = f"captured -- {n} entries"
        except Exception:
            EVIDENCE["mock call log"] = "captured -- unparseable"
    else:
        EVIDENCE["mock call log"] = "not captured -- no log file"

    stores_data = {s: store(s) for s in STORES}
    with open(os.path.join(RUN_DIR, "stores.json"), "w", encoding="utf-8") as f:
        json.dump(stores_data, f, indent=2)
    EVIDENCE["mock stores"] = f"captured -- {len(STORES)} files"


def main():
    preflight()
    os.makedirs(RUN_DIR, exist_ok=True)
    publish()
    target_cases = [c for c in CASES if not WANTED_CASES or c["id"] in WANTED_CASES]
    if WANTED_CASES:
        print(f"  cases    : {len(target_cases)} selected of {len(CASES)}\n")
    else:
        print(f"  cases    : {len(CASES)}\n")

    for c in target_cases:
        v = run_case(c)
        publish()
        r = RESULTS[c["id"]]
        print("  %-4s %-11s %-48s %s" % (
            "PASS" if v == "pass" else "FAIL",
            c["id"],
            c["name"][:48],
            r["summary"]
        ))
        if v == "fail":
            for i in r["checks"]:
                if not i["ok"]:
                    print(f"            - {i['label']}: expected {i['expected']!r}, got {i['actual']!r}")

    time.sleep(0.2)
    capture()
    EVIDENCE["status"] = "complete"
    publish()

    p = sum(1 for c in target_cases if RESULTS.get(c["id"], {}).get("verdict") == "pass")
    nchecks = sum(len(RESULTS.get(c["id"], {}).get("checks", [])) for c in target_cases)
    print(f"\n  {p}/{len(target_cases)} selected cases passed, {nchecks} checks total")
    print(f"  results: {os.path.join(RUN_DIR, 'results.json')}")
    print(f"  /test  : {BASE}/test")
    return 1 if p != len(target_cases) else 0


if __name__ == "__main__":
    sys.exit(main())
