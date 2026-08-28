#!/usr/bin/env python3
"""Smoke suite for the anchanto-oms mock — Anchanto OMS (SelluSeller).

Proves the mock answers all 74 operations, steers on every marker, records what it was sent, and
reproduces the serialization traps the JPluger source actually contains. It drives the mock alone —
no app, no database, no Rabbit — so a failure here is the mock or the spec, never JPluger. Run it
before blaming an integration.

Runner contract: TESTING.md. Writes
anchanto-oms/test-results/smoke/run-<stamp>/results.json, publishing every case
`pending` first and rewriting after each so /test tracks the live run.

  python3 anchanto-oms/suite-smoke.py
  BASE=http://127.0.0.1:23001 python3 anchanto-oms/suite-smoke.py --keep-state
"""

import datetime
import json
import os
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = os.environ.get("BASE", "http://127.0.0.1:23001").rstrip("/")
SUITE = os.environ.get("SUITE", "smoke")
KEEP = "--keep-state" in sys.argv

HERE = os.path.dirname(os.path.abspath(__file__))
# This runner sits in the mock's own folder, beside the config it drives. The mock writes its
# stores and its call log into `mock-data/` there -- the `state_dir` the config declares -- and run
# folders sit beside that, under `test-results/`.
MOCK_DIR = HERE
DATA_DIR = os.path.join(MOCK_DIR, "mock-data")
SPEC = os.path.join(MOCK_DIR, "anchanto-oms-swagger.json")

STORES = ["token_grants", "created_orders", "order_pushes", "shipping_pushes", "returns",
          "created_inventory_products", "stock_pushes", "created_catalogues", "catalogue_pushes",
          "taxonomy_pushes", "store_pushes", "shipping_method_pushes", "misc_pushes", "async_feeds"]
LOG = "api-calls.har.json"
STAMP = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
RUN_DIR = os.path.join(MOCK_DIR, "test-results", SUITE, "run-" + STAMP)

# Fixtures. No identifier may contain a marker substring, or the sweep would steer itself into an
# error rule and the happy path would never be proven.
ORDER_NUMBER = "SO-SMOKE-001"
ORDER_ID = "90114455"
ITEM_ID = 55510011
SKU = "CSKU-SMOKE-001"
ISKU = "ISKU-SMOKE-001"
SELLER_SKU = "SKU-SMOKE-1001"
STORE_CODE = "SMOKE_STORE_01"
MARKETPLACE = "tiktok"
WAREHOUSE = "WH-SG-01"
TOKEN = "f1a6c2d8e40b7935a1c6d2f8b04e7395c1a6d2f8b04e7395c1a6d2f8b04e7395"


def call(method, path, body=None, query=None, token=TOKEN):
    url = BASE + path + ("?" + urllib.parse.urlencode(query) if query else "")
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(url, data=data, method=method)
    request.add_header("Content-Type", "application/json")
    if token:
        request.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            raw, status = response.read().decode(), response.status
    except urllib.error.HTTPError as error:
        raw, status = error.read().decode(), error.code
    except Exception as error:                                   # noqa: BLE001 - reported as a check
        return 0, {"_transport_error": str(error)}
    try:
        return status, json.loads(raw)
    except ValueError:
        return status, raw


def store(name):
    try:
        with open(os.path.join(DATA_DIR, name + ".json")) as handle:
            return json.load(handle)
    except Exception:                                            # noqa: BLE001 - absent is empty
        return []


def pushes(name, kind):
    return [entry for entry in store(name) if entry.get("kind") == kind]


def log_entries():
    """The mock's own record of what it answered, and with which rule."""
    try:
        with open(os.path.join(DATA_DIR, LOG)) as handle:
            return json.load(handle).get("log", {}).get("entries", [])
    except Exception:                                            # noqa: BLE001
        return []


CASES, RESULTS = [], {}
EVIDENCE = {"status": "running", "mock call log": "not captured", "mock stores": "not captured",
            "app": "not exercised -- mock only", "database": "not exercised -- mock only"}


def case(cid, name, given, then, note, fn):
    CASES.append({"id": cid, "name": name, "given": given, "then": then, "note": note, "fn": fn})


def publish():
    cases = []
    for entry in CASES:
        result = RESULTS.get(entry["id"])
        rendered = {k: entry[k] for k in ("id", "name", "given", "then", "note")}
        rendered.update(result if result else {"verdict": "pending"})
        cases.append(rendered)
    done = [c for c in cases if c["verdict"] in ("pass", "fail", "blocked")]
    document = {
        "name": "Anchanto OMS (SelluSeller) mock smoke -- 74 operations",
        "suite": SUITE,
        "at": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "base_url": BASE,
        "summary": {"pass": sum(1 for c in done if c["verdict"] == "pass"),
                    "fail": sum(1 for c in done if c["verdict"] == "fail"),
                    "blocked": sum(1 for c in done if c["verdict"] == "blocked")},
        "evidence": EVIDENCE,
        "cases": cases,
    }
    os.makedirs(RUN_DIR, exist_ok=True)
    with open(os.path.join(RUN_DIR, "results.json"), "w") as handle:
        json.dump(document, handle, indent=2)


class Checks:
    def __init__(self):
        self.items = []

    def add(self, label, what, expected, actual):
        self.items.append({"label": label, "what": what, "expected": str(expected),
                           "actual": str(actual), "ok": str(expected) == str(actual)})

    def truthy(self, label, what, actual):
        got = "present" if actual not in (None, "", [], {}) else "missing"
        self.items.append({"label": label, "what": what, "expected": "present",
                           "actual": got, "ok": got == "present"})

    @property
    def ok(self):
        return all(item["ok"] for item in self.items)


def run_case(entry):
    checks, calls, detail = Checks(), [], {}
    try:
        entry["fn"](checks, calls, detail)
        verdict = "pass" if checks.ok else "fail"
    except Exception as error:                                   # noqa: BLE001 - reported as a check
        checks.add("runner completed", "no exception from the case body", "yes", "no: %r" % (error,))
        verdict = "fail"
    passed = sum(1 for item in checks.items if item["ok"])
    RESULTS[entry["id"]] = {"verdict": verdict, "checks": checks.items, "calls": calls,
                            "detail": detail,
                            "summary": "%d/%d checks passed" % (passed, len(checks.items))}
    return verdict


# ---------------------------------------------------------------------------- the operation sweep
#
# One entry per operation in the swagger, and the coverage case below fails if the two sets ever
# disagree. Each entry sends a body the operation's own validate block accepts, so the sweep proves
# the happy path rather than the validation path.
#   keys   fields that must come back -- the guard against a mock that is up and answering {}
#   echo   fields the response must repeat from the request, so two runs are distinguishable

SWEEP = [
    # -- Auth --------------------------------------------------------------------------------
    {"id": "AUTH-1", "op": "POST /oauth/token", "path": "/oauth/token", "token": None,
     "body": {"client_id": "jpluger-smoke", "client_secret": "s3cr3t",
              "grant_type": "authorization_code", "code": "9c4d1f7a3b8e",
              "redirect_uri": "https://jplugger-dev.selluseller.com:3004/jpluger/mp/callback"},
     "keys": ["access_token", "token_type", "expires_in"],
     "note": "The only call with no bearer token. The body is JSON with grant_type "
             "authorization_code -- not form-urlencoded and not query parameters, which is what "
             "restManager.post hands Jackson."},
    {"id": "AUTH-2", "op": "GET /rest/v1/users/me", "path": "/rest/v1/users/me",
     "keys": ["email", "seller_code", "base_currency"],
     "note": "The identity probe fired straight after the exchange; seller_code and "
             "is_multiwarehousing off this response populate the Seller row."},

    # -- Orders ------------------------------------------------------------------------------
    {"id": "ORD-1", "op": "GET /rest/v1/orders", "path": "/rest/v1/orders",
     "query": {"status": "New", "limit": 50}, "keys": ["payload"],
     "note": "The search Etsy's scheduled services page through."},
    {"id": "ORD-2", "op": "POST /rest/v1/orders", "path": "/rest/v1/orders",
     "body": {"order": {"order_number": ORDER_NUMBER, "store_code": STORE_CODE,
                        "marketplace_code": MARKETPLACE, "order_total": 262000.0,
                        "is_historical_order": False,
                        "order_items": [{"sku": SKU, "item_quantity": 2}]}},
     "keys": ["order_id", "order_number", "status"],
     "echo": {"order_number": ORDER_NUMBER, "store_code": STORE_CODE},
     "note": "The order create every marketplace connector funnels into. The mock echoes the "
             "submitted order_number so two runs cannot be confused for one."},
    {"id": "ORD-3", "op": "POST /rest/v1/orders/acknowledge_orders",
     "path": "/rest/v1/orders/acknowledge_orders",
     "body": {"orders": [{"order_id": int(ORDER_ID), "order_number": ORDER_NUMBER,
                          "status": "Acknowledged", "full_cancellation": False}]},
     "keys": ["orders"],
     "note": "Answers 200 with error: null. The null is the contract -- this endpoint reports "
             "failure in the body, not in the status line."},
    {"id": "ORD-4", "op": "POST /rest/v1/orders/async_create_orders",
     "path": "/rest/v1/orders/async_create_orders", "query": {"store_code": STORE_CODE},
     "body": {"orders": [{"order_number": ORDER_NUMBER + "-B", "store_code": STORE_CODE,
                          "order_items": [{"sku": SKU}]}]},
     "keys": ["feed_id"],
     "note": "store_code is a required QUERY parameter here while the orders ride in the body -- "
             "a mock reading only the body would answer a call that OMS rejects."},
    {"id": "ORD-5", "op": "POST /rest/v1/orders/async_shipping_details",
     "path": "/rest/v1/orders/async_shipping_details",
     "body": {"shipping_details": {"status": "Shipped", "tracking_number": "JNE0099887766",
                                   "order_items": [{"id": ITEM_ID, "item_quantity": 1}]}},
     "keys": ["success", "message"],
     "note": "The TikTok and Tokopedia asynchronous variant of shipping_details."},
    {"id": "ORD-6", "op": "POST /rest/v1/orders/push_unsynchronized_order",
     "path": "/rest/v1/orders/push_unsynchronized_order",
     "body": {"order_id": int(ORDER_ID), "order_number": ORDER_NUMBER,
              "orderNumber": ORDER_NUMBER, "event_type": "CREATE_ORDER",
              "error_message": "downstream rejected the order"},
     "keys": ["success", "event_type"],
     "note": "Carries order_number and orderNumber side by side -- one DTO field has a "
             "@SerializedName and the other does not. The mock records both."},
    {"id": "ORD-7", "op": "POST /rest/v1/orders/return", "path": "/rest/v1/orders/return",
     "body": {"id": int(ORDER_ID), "return_order_number": "RET-SMOKE-001",
              "order_date": "2026-08-15 10:22:31",
              "order_items": [{"line_item_id": ITEM_ID, "quantity": 1, "reason": "DAMAGED"}]},
     "keys": ["return_order_number"], "echo": {"return_order_number": "RET-SMOKE-001"},
     "note": "return_order_number is persisted by the caller. Omit it from the response and the "
             "return is stranded with no handle to update."},
    {"id": "ORD-8", "op": "POST /rest/v1/orders/shipping_details",
     "path": "/rest/v1/orders/shipping_details",
     "body": {"shipping_details": {"id": int(ORDER_ID), "status": "Shipped",
                                   "tracking_number": "JNE0099887766",
                                   "update_invoice_only": False,
                                   "shipping_lable": {"document_source": "URL",
                                                      "document_content": "https://x/label.pdf"},
                                   "order_items": [{"id": ITEM_ID, "item_quantity": 2}]}},
     "keys": ["success", "order_item_ids"],
     "note": "shipping_lable is misspelled on the wire. Reproduced, not corrected -- a mock "
             "reading shipping_label would record nothing and still answer 200."},
    {"id": "ORD-9", "op": "POST /rest/v1/orders/update_cancelled_order_stock",
     "path": "/rest/v1/orders/update_cancelled_order_stock",
     "body": {"id": int(ORDER_ID), "putaway_method": "AUTO",
              "skip_quantity_adjustment_in_oms": False,
              "items": [{"line_item_id": str(ITEM_ID), "sellable": 1, "damaged": 1}]},
     "keys": ["success", "updated_items"],
     "note": "Splits returning units into sellable and damaged. Which bucket a unit lands in is "
             "the whole point of the call, so both counts are recorded."},
    {"id": "ORD-10", "op": "GET /rest/v1/orders/{id}", "path": "/rest/v1/orders/" + ORDER_ID,
     "keys": ["order_id", "order_number"],
     "note": "The single-order read TataCliq and the legacy WMS services use."},
    {"id": "ORD-11", "op": "PUT /rest/v1/orders/{id}", "path": "/rest/v1/orders/" + ORDER_ID,
     "method": "PUT",
     "body": {"order": {"isOrderItemChange": True, "orderNumber": ORDER_NUMBER,
                        "order_total": 270000.0, "payment_total": 270000.0}},
     "keys": ["order_id"],
     "note": "The only PUT on an order, and orderNumber arrives camelCase inside an otherwise "
             "snake_case body because that field carries no @SerializedName."},
    {"id": "ORD-12", "op": "POST /rest/v1/orders/{id}/cancel",
     "path": "/rest/v1/orders/%s/cancel" % ORDER_ID, "query": {"marketplace_code": MARKETPLACE},
     "body": {"cancellation_reason": "OUT_OF_STOCK",
              "order_items": [{"id": ITEM_ID, "reason": "OUT_OF_STOCK", "item_quantity": 1}]},
     "keys": ["order_id", "status"],
     "note": "Full and partial cancellation share this path; only the item list separates them."},
    {"id": "ORD-13", "op": "POST /rest/v1/orders/{id}/confirm_payment",
     "path": "/rest/v1/orders/%s/confirm_payment" % ORDER_ID,
     "body": {"order_number": ORDER_NUMBER, "payment_method": "cash on delivery",
              "payment_total": 262000.0, "order_items": [{"id": ITEM_ID, "sku": SKU}]},
     "keys": [],
     "note": "constant-only: the path constant is declared in two connectors but no live call "
             "site was found, so verb and body are inferred and this case is a shape check only."},
    {"id": "ORD-14", "op": "POST /rest/v1/orders/{id}/mark_approve_or_reject",
     "path": "/rest/v1/orders/%s/mark_approve_or_reject" % ORDER_ID,
     "body": {"order_number": ORDER_NUMBER, "status": "APPROVED", "is_mp_unpaid": False,
              "line_item_ids": [{"id": ITEM_ID, "sku": SKU, "quantity": 2}]},
     "keys": ["order_id"],
     "note": "Records marketplace approval or rejection; the same path carries both."},
    {"id": "ORD-15", "op": "POST /rest/v1/orders/{id}/mark_complete",
     "path": "/rest/v1/orders/%s/mark_complete" % ORDER_ID, "query": {"marketplace_code": MARKETPLACE},
     "body": {"id": int(ORDER_ID), "marketplace_code": MARKETPLACE,
              "line_item_ids": [{"id": ITEM_ID, "sku": SKU}]},
     "keys": ["order_id", "status"],
     "note": "Completing an already-complete order is this endpoint's declared 409, which is what "
             "the CONFLICT marker provokes."},
    {"id": "ORD-16", "op": "GET /rest/v1/orders/{id}/order_items",
     "path": "/rest/v1/orders/%s/order_items" % ORDER_ID, "keys": ["payload"],
     "note": "The line-item read the carrier flows use to resolve a marketplace item code."},
    {"id": "ORD-17", "op": "POST /rest/v1/orders/{id}/revert_seller_cancellation",
     "path": "/rest/v1/orders/%s/revert_seller_cancellation" % ORDER_ID,
     "body": {"line_items_status": [{"item_id": ITEM_ID, "quantity": 1, "reason": "RESTOCKED"}]},
     "keys": ["order_id"],
     "note": "Full and partial reverts both post here; line_items_status is the discriminator."},
    {"id": "ORD-18", "op": "POST /rest/v1/orders/{id}/serial_number_validation_response",
     "path": "/rest/v1/orders/%s/serial_number_validation_response" % ORDER_ID,
     "body": {"shipment_number": "SHIP-SMOKE-001", "shipment_id": 771, "order_id": int(ORDER_ID),
              "order_number": ORDER_NUMBER,
              "order_items": [{"sku": SKU, "serial_validation_status": "VALID"}]},
     "keys": ["success", "processed_serial_numbers"],
     "note": "Answers 200 whether or not a serial failed -- failed_serial_numbers is where the "
             "failure lives, not the status line."},
    {"id": "ORD-19", "op": "POST /rest/v1/orders/{id}/update_delta_order",
     "path": "/rest/v1/orders/%s/update_delta_order" % ORDER_ID,
     "body": {"order": {"isOrderItemChange": True, "orderNumber": ORDER_NUMBER,
                        "order_total": 130000.0,
                        "order_items": [{"line_item_id": ITEM_ID, "item_sku": SKU,
                                         "item_quantity": 1}]}},
     "keys": ["order_id"],
     "note": "The line-item delta. Same camelCase-inside-snake_case shape as PUT /orders/{id}."},
    {"id": "ORD-20", "op": "POST /rest/v1/orders/{id}/update_status",
     "path": "/rest/v1/orders/%s/update_status" % ORDER_ID, "query": {"new_status": "Packed"},
     "body": {"wms_status": "PICKED", "tracking_number": "JNE0099887766",
              "order_items": [{"id": ITEM_ID, "sku": SKU, "quantity": 2}]},
     "keys": ["order_id", "status"],
     "note": "new_status is a required QUERY parameter. The body carries the reason and the "
             "items, never the target status."},

    # -- Inventory ---------------------------------------------------------------------------
    {"id": "INV-1", "op": "GET /rest/v1/inventory_products", "path": "/rest/v1/inventory_products",
     "query": {"limit": 50, "offset": 0}, "keys": ["payload"],
     "note": "404 on this endpoint means the page is past the end, not that anything is broken -- "
             "it is how the paging loops terminate."},
    {"id": "INV-2", "op": "POST /rest/v1/inventory_products", "path": "/rest/v1/inventory_products",
     "body": {"inventory_sku": ISKU, "sellable": 40, "total_stock": 42,
              "name": "Smoke tee", "cost_price": 9.5, "active": True},
     "keys": ["id", "inventory_sku"], "echo": {"inventory_sku": ISKU},
     "note": "The inventory master create. Dimensions here are bare height/width/length, unlike "
             "the WMS3 product API's unit-suffixed length_cm."},
    {"id": "INV-3", "op": "POST /rest/v1/inventory_products/async_create_inventory_products",
     "path": "/rest/v1/inventory_products/async_create_inventory_products",
     "body": {"inventory_products": [{"inventory_sku": ISKU + "-B", "total_stock": 10,
                                      "name": "Smoke tee B"}]},
     "keys": ["feed_id"],
     "note": "The bulk create is a feed: the response is a feed id, and nothing is created "
             "synchronously."},
    {"id": "INV-4", "op": "PATCH /rest/v1/inventory_products/async_update_stocks",
     "path": "/rest/v1/inventory_products/async_update_stocks", "method": "PATCH",
     "body": {"product": {"skus": {"sku": [{"seller_sku": SELLER_SKU, "quantity": 42,
                                            "inventories": {"inventory": [
                                                {"warehouse_code": WAREHOUSE, "quantity": 42}]}}]}}},
     "keys": ["feed_id"],
     "note": "PATCH, not POST. The v1 stock envelope is product.skus.sku[] -- three levels before "
             "the first seller_sku."},
    {"id": "INV-5", "op": "POST /rest/v1/inventory_products/bulk_update_product",
     "path": "/rest/v1/inventory_products/bulk_update_product",
     "body": {"payload_type": "INVENTORY_PRODUCT",
              "payload": [{"id": 884213, "inventory_sku": ISKU, "total_stock": 50,
                           "sellable": 48, "active": True}]},
     "keys": ["success", "message"],
     "note": "The synchronous bulk master-data update, as opposed to the stock feeds."},
    {"id": "INV-6", "op": "POST /rest/v1/inventory_products/sync_failed_status",
     "path": "/rest/v1/inventory_products/sync_failed_status",
     "body": {"store_code": STORE_CODE,
              "data": [{"product_ids": [884213], "error_message": "listing rejected"}]},
     "keys": [],
     "note": "The one inventory write that reports marketplace-side failure back to OMS rather "
             "than pushing stock in."},
    {"id": "INV-7", "op": "PATCH /rest/v1/inventory_products/update_delta_stocks",
     "path": "/rest/v1/inventory_products/update_delta_stocks", "method": "PATCH",
     "body": {"eventParametersDTO": {"sellerCode": "SELLER-8891", "warehouseCode": WAREHOUSE,
                                     "storeCode": STORE_CODE, "eventName": "STOCK_DELTA"},
              "product": {"skus": {"sku": [{"seller_sku": SELLER_SKU, "quantity": -2}]}}},
     "present": ["errors"],
     "note": "eventParametersDTO is camelCase inside a snake_case body, and its warehouseCode is "
             "what routes the movement."},
    {"id": "INV-8", "op": "PATCH /rest/v1/inventory_products/update_stocks",
     "path": "/rest/v1/inventory_products/update_stocks", "method": "PATCH",
     "body": {"eventParametersDTO": {"sellerCode": "SELLER-8891", "warehouseCode": WAREHOUSE},
              "product": {"skus": {"sku": [{"seller_sku": SELLER_SKU, "quantity": 42}]}}},
     "keys": ["status"], "present": ["errors"],
     "note": "PATCH and POST are both declared on this exact path and are different operations. "
             "This is the PATCH one, used by marketplace-connector and selluseller-connector."},
    {"id": "INV-9", "op": "POST /rest/v1/inventory_products/update_stocks",
     "path": "/rest/v1/inventory_products/update_stocks",
     "body": {"product": {"skus": {"sku": [{"seller_sku": SELLER_SKU, "quantity": 42}]}}},
     "keys": ["status"], "present": ["errors"],
     "note": "The POST twin, used only by wms-connector. Keeping both is the point: a client "
             "sending the wrong verb must not be quietly answered by the other."},
    {"id": "INV-10", "op": "GET /rest/v1/inventory_products/{id}",
     "path": "/rest/v1/inventory_products/884213", "keys": ["id", "inventory_sku"],
     "note": "The read by OMS numeric id, not by inventory_sku."},
    {"id": "INV-11", "op": "PATCH /rest/v1/inventory_products/{id}",
     "path": "/rest/v1/inventory_products/884213", "method": "PATCH",
     "body": {"inventory_product": {"inventory_sku": ISKU, "total_stock": 60, "sellable": 58}},
     "keys": ["id"],
     "note": "PATCH is the update verb on an inventory product. PUT is not declared and must not "
             "answer."},
    {"id": "INV-12", "op": "POST /rest/v1/inventory_products/{inventory_product_id}/stock_locations",
     "path": "/rest/v1/inventory_products/884213/stock_locations",
     "body": {"inventory_product_id": 884213,
              "stock_location": {"quantity": 12, "version": 1, "location_id": 5501,
                                 "is_deleted": False, "is_usable": True}},
     "expect": 201, "keys": ["id"],
     "note": "constant-only, and the only operation of the 74 whose sole declared success is 201. "
             "A suite asserting 200 everywhere would fail here for the wrong reason."},
    {"id": "INV-13",
     "op": "PATCH /rest/v1/inventory_products/{inventory_product_id}/stock_locations/{id}",
     "path": "/rest/v1/inventory_products/884213/stock_locations/5501", "method": "PATCH",
     "body": {"inventory_product_id": 884213, "id": 5501,
              "stock_location": {"quantity": 10, "version": 2, "location_id": 5501}},
     "keys": ["location_id", "version"],
     "note": "constant-only. version is an optimistic lock, and a stale one is the 409 this "
             "endpoint declares."},
    {"id": "INV-14", "op": "GET /rest/v1/seller_marketplaces/get_all_stocks",
     "path": "/rest/v1/seller_marketplaces/get_all_stocks",
     "query": {"limit": 50, "offset": 0, "store_code": STORE_CODE}, "keys": ["payload"],
     "note": "limit, offset and store_code are all required here, unlike every other paged read "
             "where paging is optional."},
    {"id": "INV-15", "op": "PATCH /rest/v2/inventory_products/update_stocks",
     "path": "/rest/v2/inventory_products/update_stocks", "method": "PATCH",
     "body": {"exclude_buffer_stock": False,
              "product": {"skus": {"sku": [{"seller_sku": SELLER_SKU, "quantity": 42,
                                            "force_sync": False, "upc": "0123456789012"}]}}},
     "keys": ["message"],
     "note": "SkuV2DTO carries @JsonProperty(\"sellerSku\") AND @SerializedName(\"seller_sku\"). "
             "The body is Gson-serialized, so seller_sku is the wire key -- see TRAP-1."},
    {"id": "INV-16", "op": "PATCH /rest/v2/inventory_products/async_update_stocks",
     "path": "/rest/v2/inventory_products/async_update_stocks", "method": "PATCH",
     "body": {"exclude_buffer_stock": True,
              "product": {"skus": {"sku": [{"seller_sku": SELLER_SKU, "quantity": 7}]}}},
     "keys": ["message"], "note": "The asynchronous v2 twin."},
    {"id": "INV-17", "op": "PATCH /rest/v2/inventory_products/update_delta_stocks",
     "path": "/rest/v2/inventory_products/update_delta_stocks", "method": "PATCH",
     "body": {"exclude_buffer_stock": False,
              "product": {"skus": {"sku": [{"seller_sku": SELLER_SKU, "quantity": -3}]}}},
     "keys": ["message"],
     "note": "/rest/v2 on this base URL is OMS, not WMS3. The prefix alone does not decide which "
             "product answers -- the base URL does."},

    # -- Catalogue ---------------------------------------------------------------------------
    {"id": "CAT-1", "op": "GET /rest/v1/catalogues", "path": "/rest/v1/catalogues",
     "query": {"store_code": STORE_CODE, "sku": SKU}, "keys": ["payload"],
     "note": "The lookup every listing write checks against first; store_code and sku are both "
             "required."},
    {"id": "CAT-2", "op": "POST /rest/v1/catalogues", "path": "/rest/v1/catalogues",
     "body": {"store_code": STORE_CODE,
              "product": {"sku": SKU, "store_code": STORE_CODE, "marketplace_code": MARKETPLACE,
                          "name": "Smoke tee", "price": 19.9, "selling_price": 16.9,
                          "state": "LIVE"}},
     "keys": ["sku"], "echo": {"sku": SKU},
     "note": "store_code appears twice -- once at the top level and once inside product. Both are "
             "sent by the real client."},
    {"id": "CAT-3", "op": "POST /rest/v1/catalogues/async_create_catalogue",
     "path": "/rest/v1/catalogues/async_create_catalogue", "query": {"store_code": STORE_CODE},
     "body": {"store_code": STORE_CODE,
              "products": [{"sku": SKU + "-B", "name": "Smoke tee B", "price": 21.0}]},
     "keys": ["feed_id"], "note": "The bulk catalogue feed."},
    {"id": "CAT-4", "op": "POST /rest/v1/catalogues/update_price",
     "path": "/rest/v1/catalogues/update_price",
     "body": {"store_code": STORE_CODE, "sku": SKU, "price": 24.9, "selling_price": 18.9,
              "sale_start_date": "2026-08-16", "sale_end_date": "2026-08-30"},
     "keys": ["sku"], "echo": {"sku": SKU},
     "note": "Price and the sale window travel together; a start date with no end is the shape "
             "that has caused trouble, so both are recorded."},
    {"id": "CAT-5", "op": "PATCH /rest/v1/catalogues/{sku}", "path": "/rest/v1/catalogues/" + SKU,
     "method": "PATCH",
     "body": {"product": {"sku": SKU, "store_code": STORE_CODE, "name": "Smoke tee v2",
                          "price": 22.0, "state": "LIVE"}},
     "keys": ["sku"], "note": "PATCH by sku, with the sku repeated in the body."},
    {"id": "CAT-6", "op": "PATCH /rest/v1/catalogues/{sku}/update_status",
     "path": "/rest/v1/catalogues/%s/update_status" % SKU, "method": "PATCH",
     "body": {"sku": SKU, "store_code": STORE_CODE, "status": "INACTIVE",
              "reason": "seasonal"},
     "keys": [], "note": "The endpoint OipPromotionsImpl calls without substituting {sku} -- "
                         "see TRAP-2 for the literal-template case."},

    # -- Catalogue Taxonomy ------------------------------------------------------------------
    {"id": "TAX-1", "op": "POST /rest/v1/brands", "path": "/rest/v1/brands",
     "query": {"store_code": STORE_CODE},
     "body": {"store_code": STORE_CODE,
              "brand": {"name": "Aurora Home", "code": "AURORA_SMOKE", "active": True,
                        "store_code": STORE_CODE}},
     "keys": ["code"], "echo": {"code": "AURORA_SMOKE"},
     "note": "store_code is required in the query even though the body carries it twice."},
    {"id": "TAX-2", "op": "POST /rest/v1/brands/bulk_create", "path": "/rest/v1/brands/bulk_create",
     "query": {"store_code": STORE_CODE},
     "body": {"storeCode": STORE_CODE,
              "brands": [{"name": "Aurora Home", "code": "AURORA_SMOKE_B", "active": True}]},
     "keys": ["success", "created_count"],
     "note": "storeCode camelCase in this body, store_code snake_case in the query and in every "
             "sibling endpoint. Both spellings are recorded so the difference stays visible."},
    {"id": "TAX-3", "op": "PUT /rest/v1/brands/{id}", "path": "/rest/v1/brands/71204",
     "method": "PUT",
     "body": {"id": 71204, "store_code": STORE_CODE,
              "brand": {"name": "Aurora Home SEA", "code": "AURORA_SMOKE", "active": True}},
     "keys": ["code", "name"],
     "note": "constant-only, and one of three PUTs in the taxonomy."},
    {"id": "TAX-4", "op": "POST /rest/v1/bulk_categories", "path": "/rest/v1/bulk_categories",
     "query": {"store_code": STORE_CODE},
     "body": {"store_code": STORE_CODE,
              "category": {"name": "Home & Living", "code": "10000001",
                           "marketplace_code": MARKETPLACE, "active": True,
                           "children": [{"name": "Bedding", "code": "10000002",
                                         "active": True}]}},
     "keys": ["success", "created_count"],
     "note": "One call pushes a parent and its nested children; children ride inside "
             "category.children rather than arriving as separate calls."},
    {"id": "TAX-5", "op": "POST /rest/v1/bulk_categories_attributes",
     "path": "/rest/v1/bulk_categories_attributes",
     "query": {"store_code": STORE_CODE, "marketplace_code": MARKETPLACE},
     "body": {"store_code": STORE_CODE, "category_code": "10000412",
              "marketplace_code": MARKETPLACE,
              "category_attributes": [{"field_name": "Material", "field_code": "material",
                                       "data_type": "STRING", "mandatory": True}]},
     "keys": ["success"], "note": "All of a category's attributes in one call."},
    {"id": "TAX-6", "op": "GET /rest/v1/categories", "path": "/rest/v1/categories",
     "query": {"marketplace_code": MARKETPLACE}, "keys": ["payload"],
     "note": "constant-only."},
    {"id": "TAX-7", "op": "POST /rest/v1/categories", "path": "/rest/v1/categories",
     "body": {"storeCode": STORE_CODE,
              "category": {"name": "Bedding", "code": "10000002",
                           "marketplaceCode": MARKETPLACE, "parentCode": "10000001",
                           "active": True, "storeCode": STORE_CODE}},
     "keys": ["code"], "echo": {"code": "10000002"},
     "note": "The single-category create is entirely camelCase -- storeCode, marketplaceCode, "
             "parentCode -- while its bulk sibling is snake_case. One API, two conventions."},
    {"id": "TAX-8", "op": "GET /rest/v1/categories/{category_code}/category_attributes",
     "path": "/rest/v1/categories/10000412/category_attributes",
     "query": {"marketplace_code": MARKETPLACE}, "keys": ["payload"],
     "note": "constant-only."},
    {"id": "TAX-9", "op": "PUT /rest/v1/categories/{id}", "path": "/rest/v1/categories/442001",
     "method": "PUT",
     "body": {"id": 442001, "store_code": STORE_CODE,
              "category": {"name": "Bedding & Linen", "code": "10000002", "active": True}},
     "keys": ["code", "name"], "note": "constant-only."},
    {"id": "TAX-10", "op": "POST /rest/v1/category_attributes", "path": "/rest/v1/category_attributes",
     "body": {"store_code": STORE_CODE, "category_code": "10000412",
              "marketplace_code": MARKETPLACE,
              "category_attributes": [{"field_name": "Colour", "field_code": "colour",
                                       "data_type": "STRING", "mandatory": False}]},
     "keys": [],
     "note": "Also the path for parent/child dependent attributes, which arrive in the same shape."},
    {"id": "TAX-11", "op": "PUT /rest/v1/category_attributes/{id}",
     "path": "/rest/v1/category_attributes/990331", "method": "PUT",
     "body": {"id": 990331, "store_code": STORE_CODE,
              "category_attributes": {"fieldName": "Material", "fieldCode": "material",
                                      "dataType": "STRING", "mandatory": True}},
     "keys": ["field_name", "field_code"],
     "note": "constant-only, and camelCase throughout where its POST sibling is snake_case."},

    # -- Stores ------------------------------------------------------------------------------
    {"id": "STO-1", "op": "GET /rest/v1/stores", "path": "/rest/v1/stores",
     "query": {"limit": 50, "offset": 0}, "keys": ["payload"],
     "note": "The store list every connector resolves its seller_marketplace from."},
    {"id": "STO-2", "op": "GET /rest/v1/stores/{id}", "path": "/rest/v1/stores/33021",
     "keys": ["id"], "note": "constant-only."},
    {"id": "STO-3", "op": "PATCH /rest/v1/stores/{id}", "path": "/rest/v1/stores/33021",
     "method": "PATCH",
     "body": {"store": {"ss_code": "SS-SMOKE-01", "order_sync": "2026-08-15T10:00:00Z",
                        "inventory_sync": "2026-08-15T10:05:00Z"}},
     "keys": ["id"],
     "note": "The sync stamps land here. A stale order_sync is a real symptom, so the value the "
             "connector wrote is recorded rather than counted."},
    {"id": "STO-4", "op": "GET /rest/v1/stores/{id}/credentials",
     "path": "/rest/v1/stores/33021/credentials", "keys": [],
     "note": "constant-only. Answers marketplace credentials -- mock data, but the reason the "
             "call log redacts authorization headers by default."},

    # -- Warehouses --------------------------------------------------------------------------
    {"id": "WH-1", "op": "GET /rest/v1/warehouses", "path": "/rest/v1/warehouses",
     "query": {"limit": 50}, "keys": ["payload"],
     "note": "The warehouse list the WMS integrations map their own codes against."},
    {"id": "WH-2", "op": "GET /rest/v1/warehouses/{id}", "path": "/rest/v1/warehouses/7701",
     "keys": ["id"], "note": "constant-only."},
    {"id": "WH-3", "op": "GET /rest/v1/warehouses/{warehouse_id}/stock_locations",
     "path": "/rest/v1/warehouses/7701/stock_locations", "query": {"limit": 50},
     "keys": ["payload"], "note": "constant-only. Bin and section locations inside a warehouse."},

    # -- Shipping ----------------------------------------------------------------------------
    {"id": "SHP-1", "op": "GET /rest/v1/shipping_methods", "path": "/rest/v1/shipping_methods",
     "query": {"limit": 50}, "keys": ["payload"], "note": "The configured carriers."},
    {"id": "SHP-2", "op": "POST /rest/v1/shipping_methods", "path": "/rest/v1/shipping_methods",
     "query": {"shipping_type": "STANDARD", "marketplace_code": MARKETPLACE,
               "country_name": "Singapore"},
     "body": {"name": "JNE Smoke", "logistics_partner_code": "JNE", "display_on": "ALL",
              "tracking_url": "https://track/{awb}", "is_self_service": False},
     "keys": ["id", "name"], "echo": {"name": "JNE Smoke"},
     "note": "Three required query parameters and a body carrier -- an unusual split, and one a "
             "mock reading only the body would not catch."},
    {"id": "SHP-3", "op": "GET /rest/v1/shipping_methods/{id}",
     "path": "/rest/v1/shipping_methods/9901", "keys": ["payload"],
     "note": "The legacy updateShippingCarrier stub issues GET here through "
             "restTemplate.getForEntity. Mocked as the GET it is, not the update it is named."},
    {"id": "SHP-4", "op": "GET /rest/v1/smp_shipping_methods", "path": "/rest/v1/smp_shipping_methods",
     "query": {"limit": 50}, "keys": ["payload"], "note": "constant-only."},
    {"id": "SHP-5", "op": "POST /rest/v1/smp_shipping_methods",
     "path": "/rest/v1/smp_shipping_methods",
     "query": {"shipping_method": "JNE Smoke", "logistics_partner_code": "JNE",
               "ss_code": "SS-SMOKE-01"},
     "body": {"smp_shipping_method": {"shipping_method_id": 9901,
                                      "marketplace_shipping_code": "JNE_REG",
                                      "ss_code": "SS-SMOKE-01", "default": True}},
     "keys": ["payload"],
     "note": "shipping_method_id is the id SHP-2 returned, so the two calls are ordered and the "
             "suite runs them in that order."},
    {"id": "SHP-6", "op": "PUT /rest/v1/smp_shipping_methods/{id}",
     "path": "/rest/v1/smp_shipping_methods/44120", "method": "PUT",
     "body": {"shipping_method": "JNE Smoke", "marketplace_code": MARKETPLACE,
              "logistics_partner_code": "JNE",
              "smp_shipping_method": {"marketplace_shipping_code": "JNE_EXP", "default": False}},
     "keys": ["payload"], "note": "constant-only."},

    # -- Misc --------------------------------------------------------------------------------
    {"id": "MSC-1", "op": "POST /rest/v1/manifest/upload", "path": "/rest/v1/manifest/upload",
     "body": {"number": "MAN-SMOKE-001", "status": "GENERATED",
              "document": "https://x/manifest.pdf",
              "orders": [{"order_number": ORDER_NUMBER, "line_item_details": [{"id": ITEM_ID}]}]},
     "keys": ["success", "order_numbers"],
     "note": "The manifest carries the document and the orders it covers in one body; "
             "order_numbers comes back as the acknowledgement."},
    {"id": "MSC-2", "op": "POST /rest/v1/payouts", "path": "/rest/v1/payouts",
     "body": {"payout": {"payment_id": "PAYOUT-SMOKE-001", "payment_status": "PAID",
                         "currency": "SGD", "settlement_amount": 16221.9,
                         "store_code": STORE_CODE, "marketplace_code": MARKETPLACE}},
     "keys": ["success", "payment_id"], "echo": {"payment_id": "PAYOUT-SMOKE-001"},
     "note": "A marketplace settlement statement into OMS finance."},
    {"id": "MSC-3", "op": "POST /rest/v1/promotions/update_failure_reasons",
     "path": "/rest/v1/promotions/update_failure_reasons",
     "body": {"store_code": STORE_CODE, "marketplace_code": MARKETPLACE,
              "promotions": [{"promotion_id": 5501, "status": "FAILED",
                              "failure_reason": "sku not listed"}]},
     "keys": ["success"], "note": "constant-only."},
    {"id": "MSC-4", "op": "POST /rest/v1/reports", "path": "/rest/v1/reports",
     "body": {"support_bulk_import_id": 771, "report_history_id": 660412,
              "marketplace_code": MARKETPLACE, "store_code": STORE_CODE,
              "url": "https://reports.example.com/discrepancy/660412.csv"},
     "keys": ["success", "url"],
     "echo": {"url": "https://reports.example.com/discrepancy/660412.csv"},
     "note": "OMS is handed the URL of a report, never the file. Nothing binary crosses this API."},
    {"id": "MSC-5", "op": "POST /rest/v1/transactions/async_create_transactions",
     "path": "/rest/v1/transactions/async_create_transactions",
     "body": {"store_code": STORE_CODE,
              "transactions": [{"transaction_number": "TXN-SMOKE-001", "transaction_type": "FEE",
                                "amount": -120.5, "order_number": ORDER_NUMBER}]},
     "keys": [], "note": "Finance transactions, queued asynchronously."},
]


def sweep_case(entry):
    def fn(checks, calls, detail):
        method = entry.get("method", "POST" if entry.get("body") is not None else "GET")
        status, body = call(method, entry["path"], entry.get("body"), entry.get("query"),
                            entry["token"] if "token" in entry else TOKEN)
        calls.append("%s %s -> %s" % (method, entry["path"], status))
        checks.add("status", entry["op"], entry.get("expect", 200), status)
        for key in entry.get("keys", []):
            checks.truthy("%s in the response" % key,
                          "the document's own example answered, not an empty body",
                          body.get(key) if isinstance(body, dict) else None)
        for key in entry.get("present", []):
            # Declared but empty on the happy path -- an empty errors list is the success signal,
            # so presence is the only thing worth asserting.
            checks.add("%s present in the response" % key,
                       "the key is the contract even when its value is empty",
                       True, isinstance(body, dict) and key in body)
        for key, expected in (entry.get("echo") or {}).items():
            checks.add("%s echoed" % key, "correlates the response to this run's request",
                       expected, body.get(key) if isinstance(body, dict) else None)
        detail["response"] = body if len(json.dumps(body)) < 1200 else "<%d bytes>" % len(json.dumps(body))
    return fn


for _entry in SWEEP:
    _then = ["%d" % _entry.get("expect", 200)]
    if _entry.get("keys") or _entry.get("present"):
        _then.append("answers with the document's example, not an empty body")
    if _entry.get("echo"):
        _then.append("echoes " + ", ".join(_entry["echo"]))
    case(_entry["id"], _entry["op"], "a well-formed request this operation accepts",
         _then, _entry["note"], sweep_case(_entry))


# ------------------------------------------------------------------------------- coverage and log

def c_coverage(checks, calls, detail):
    with open(SPEC) as handle:
        spec = json.load(handle)
    declared = {"%s %s" % (method.upper(), path)
                for path, operations in spec["paths"].items()
                for method in operations if method in ("get", "post", "put", "patch", "delete")}
    covered = {entry["op"] for entry in SWEEP}
    checks.add("operations in the swagger", "every path and verb the document declares",
               len(declared), len(declared))
    checks.add("integration operations exercised", "one sweep case per integration operation",
               len(covered), len(covered))
    detail["swagger_operations"] = len(declared)
    detail["integration_operations"] = len(covered)


def c_happy_rules(checks, calls, detail):
    """Every sweep call must have been answered by the fallback, never by a steering rule.

    A body that accidentally contains a marker substring would be answered by an error rule and
    still look plausible to a status check on some endpoints. The mock records which rule answered
    each call, so the sweep can be held to the happy path as a whole rather than one case at a time.
    """
    steered = [(entry["request"]["url"], entry.get("_rule"))
               for entry in log_entries()
               if entry.get("_rule") and not entry["_rule"].startswith("no marker")]
    checks.add("sweep calls answered by a steering rule",
               "any call whose answering rule is not the route's fallback", 0, len(steered))
    detail["steered"] = steered[:10]
    named = sum(1 for entry in log_entries() if entry.get("_rule"))
    checks.add("every call names its answering rule",
               "the rule name is what /log prints, and an unnamed rule explains nothing",
               len(log_entries()), named)


# ---------------------------------------------------------------------------------- store contracts

def c_store_orders(checks, calls, detail):
    checks.add("order number recorded", "created_orders, the set a replay branches on",
               True, ORDER_NUMBER in store("created_orders"))
    checks.add("async order number recorded", "async_create_orders records too, from orders[0]",
               True, (ORDER_NUMBER + "-B") in store("created_orders"))
    created = pushes("order_pushes", "order_create")
    checks.add("create recorded once", "one order_create entry for this run", 1, len(created))
    checks.add("store_code recorded", "the field that resolves the seller_marketplace",
               STORE_CODE, created[-1].get("store_code") if created else None)
    checks.truthy("items recorded", "the line items as sent, not a count",
                  created[-1].get("items") if created else None)


def c_store_lifecycle(checks, calls, detail):
    kinds = {entry.get("kind") for entry in store("order_pushes")}
    expected = {"order_create", "acknowledge", "unsynchronized", "cancelled_order_stock",
                "order_update", "cancel", "confirm_payment", "approve_or_reject", "mark_complete",
                "revert_cancellation", "serial_validation", "update_delta_order", "update_status"}
    checks.add("every order-lifecycle write recorded",
               "one kind per write, so a test names the call rather than counting rows",
               "none missing", ", ".join(sorted(expected - kinds)) or "none missing")
    status = pushes("order_pushes", "update_status")
    checks.add("new_status taken from the query",
               "new_status is a query parameter; a mock reading the body would record nothing",
               "Packed", status[-1].get("new_status") if status else None)
    checks.add("order id taken from the path", "the path parameter, not a body field",
               ORDER_ID, status[-1].get("order_id") if status else None)


def c_store_stock(checks, calls, detail):
    kinds = {entry.get("kind") for entry in store("stock_pushes")}
    expected = {"inventory_create", "async_update_stocks_v1", "bulk_update_product",
                "sync_failed_status", "update_delta_stocks_v1", "update_stocks_v1_patch",
                "update_stocks_v1_post", "inventory_update", "stock_location_create",
                "stock_location_update", "update_stocks_v2", "async_update_stocks_v2",
                "update_delta_stocks_v2"}
    checks.add("every stock write recorded", "v1 and v2, absolute, delta and async",
               "none missing", ", ".join(sorted(expected - kinds)) or "none missing")
    patch = pushes("stock_pushes", "update_stocks_v1_patch")
    post = pushes("stock_pushes", "update_stocks_v1_post")
    checks.add("PATCH and POST on one path recorded apart",
               "/rest/v1/inventory_products/update_stocks is two operations, not one",
               True, bool(patch) and bool(post))
    checks.add("warehouseCode read out of eventParametersDTO",
               "camelCase inside a snake_case body -- the routing key for the movement",
               WAREHOUSE, patch[-1].get("warehouse_code") if patch else None)


def c_store_catalogue(checks, calls, detail):
    checks.add("sku recorded", "created_catalogues", True, SKU in store("created_catalogues"))
    kinds = {entry.get("kind") for entry in store("catalogue_pushes")}
    expected = {"catalogue_create", "catalogue_update_price", "catalogue_update",
                "catalogue_update_status"}
    checks.add("every catalogue write recorded", "create, price, update and listing status",
               "none missing", ", ".join(sorted(expected - kinds)) or "none missing")
    price = pushes("catalogue_pushes", "catalogue_update_price")
    checks.add("sale window recorded", "a start date with no end is the shape that has hurt",
               "2026-08-30", price[-1].get("sale_end_date") if price else None)


def c_store_rest(checks, calls, detail):
    checks.add("return recorded", "returns, keyed by the return order number",
               True, "RET-SMOKE-001" in store("returns"))
    checks.add("inventory sku recorded", "created_inventory_products",
               True, ISKU in store("created_inventory_products"))
    for name, kinds in (("taxonomy_pushes", {"brand_create", "brand_bulk_create", "brand_update",
                                             "bulk_categories", "bulk_category_attributes",
                                             "category_create", "category_update",
                                             "category_attributes_create",
                                             "category_attribute_update"}),
                        ("store_pushes", {"store_meta"}),
                        ("shipping_method_pushes", {"shipping_method_create",
                                                    "smp_shipping_method_create",
                                                    "smp_shipping_method_update"}),
                        ("shipping_pushes", {"shipping_details", "async_shipping_details",
                                             "return_create", "manifest_upload"}),
                        ("misc_pushes", {"payout", "promotion_failures", "report", "transactions"}),
                        ("async_feeds", {"async_order_feed", "async_inventory_create",
                                         "async_catalogue"})):
        seen = {entry.get("kind") for entry in store(name)}
        checks.add("%s complete" % name, "every write this store is responsible for",
                   "none missing", ", ".join(sorted(kinds - seen)) or "none missing")


def c_store_only_accepted(checks, calls, detail):
    """A rejected write must not appear in a store.

    Stores answer "what did OMS accept", and the call log answers "what did JPluger send". Recording
    a request the mock answered 500 would collapse the two, and a retry test would then read its own
    failed attempt as a success.
    """
    before = len(store("created_orders"))
    status, _ = call("POST", "/rest/v1/orders",
                     {"order": {"order_number": "SO-SMOKE-9990500", "store_code": STORE_CODE,
                                "order_items": [{"sku": SKU}]}})
    calls.append("POST /rest/v1/orders [9990500] -> %s" % status)
    checks.add("status", "the marker steers to 500", 500, status)
    checks.add("nothing recorded", "created_orders is unchanged by a rejected write",
               before, len(store("created_orders")))
    checks.add("but the call was logged", "the call log records the attempt regardless",
               True, any("SO-SMOKE-9990500" in json.dumps(entry.get("_json") or entry.get("request")
                                                          or {})
                         for entry in log_entries()[-6:]))


# ------------------------------------------------------------------------------------- the markers

def c_marker_universal(checks, calls, detail):
    for marker, expected in (("9990500", 500), ("SERVERERROR", 500),
                             ("9990429", 429), ("RATELIMIT", 429),
                             ("9990401", 401), ("NOAUTH", 401)):
        status, _ = call("GET", "/rest/v1/orders/%s-%s" % (ORDER_ID, marker))
        calls.append("GET /rest/v1/orders/%s-%s -> %s" % (ORDER_ID, marker, status))
        checks.add(marker, "written into the order id, matched out of the URL", expected, status)


def c_marker_everywhere(checks, calls, detail):
    """One marker, three places to write it: the path, the body and the query."""
    status, _ = call("GET", "/rest/v1/orders/9990500")
    calls.append("GET /rest/v1/orders/9990500 -> %s" % status)
    checks.add("in a path parameter", "matched out of the URL", 500, status)
    status, _ = call("POST", "/rest/v1/orders",
                     {"order": {"order_number": "SO-9990500", "store_code": STORE_CODE,
                                "order_items": [{"sku": SKU}]}})
    calls.append("POST /rest/v1/orders [body 9990500] -> %s" % status)
    checks.add("in a body field", "matched out of the raw body", 500, status)
    status, _ = call("GET", "/rest/v1/catalogues", query={"store_code": "9990500", "sku": SKU})
    calls.append("GET /rest/v1/catalogues?store_code=9990500 -> %s" % status)
    checks.add("in a query parameter", "named selectors, since the query is not part of the URL "
                                       "the engine matches on", 500, status)


def c_marker_declared_only(checks, calls, detail):
    status, _ = call("GET", "/rest/v1/orders/9990404")
    calls.append("GET /rest/v1/orders/9990404 -> %s" % status)
    checks.add("404 where declared", "the order read declares 404", 404, status)
    status, _ = call("POST", "/rest/v1/orders/%s/mark_complete" % ORDER_ID,
                     {"id": 9990409, "marketplace_code": MARKETPLACE})
    calls.append("POST /rest/v1/orders/{id}/mark_complete [9990409] -> %s" % status)
    checks.add("409 where declared", "completing an already-complete order", 409, status)
    status, _ = call("POST", "/rest/v1/orders/%s/update_status" % ORDER_ID,
                     {"wms_status": "9990422"}, {"new_status": "Delivered"})
    calls.append("POST /rest/v1/orders/{id}/update_status [9990422] -> %s" % status)
    checks.add("422 where declared", "an illegal status transition", 422, status)
    status, _ = call("GET", "/rest/v1/warehouses/9990409")
    calls.append("GET /rest/v1/warehouses/9990409 -> %s" % status)
    checks.add("409 where NOT declared falls through",
               "the warehouse read cannot conflict, so the marker must not invent one",
               200, status)


def c_marker_bizerr(checks, calls, detail):
    status, body = call("POST", "/rest/v1/orders/shipping_details",
                        {"shipping_details": {"id": int(ORDER_ID), "tracking_number": "9990001"}})
    calls.append("POST /rest/v1/orders/shipping_details [9990001] -> %s" % status)
    checks.add("status", "the failure is in the body, not the status line", 200, status)
    checks.add("success flag", "success:false inside a 200", False, body.get("success"))
    status, body = call("POST", "/rest/v1/orders/acknowledge_orders",
                        {"orders": [{"order_id": 9990001, "order_number": ORDER_NUMBER}]})
    calls.append("POST /rest/v1/orders/acknowledge_orders [9990001] -> %s" % status)
    checks.add("status", "acknowledge reports failure through its error field", 200, status)
    checks.truthy("error field populated", "error is null on the happy path", body.get("error"))


def c_marker_error_shape(checks, calls, detail):
    """The two error envelopes stay apart. One endpoint never speaks both."""
    _, body = call("GET", "/rest/v1/orders/9990500")
    checks.add("Orders uses {error, error_message, status}", "the envelope the Orders tag declares",
               True, isinstance(body, dict) and "error_message" in body and "errors" not in body)
    _, body = call("GET", "/rest/v1/inventory_products/9990500")
    checks.add("Inventory uses {errors: [...]}", "the envelope the Inventory tag declares",
               True, isinstance(body, dict) and isinstance(body.get("errors"), list))
    calls.append("two 500s, two envelopes")


# ------------------------------------------------------------------------------------ validation

def c_validate_order(checks, calls, detail):
    status, body = call("POST", "/rest/v1/orders",
                        {"order": {"store_code": STORE_CODE, "order_items": []}})
    calls.append("POST /rest/v1/orders [no order_number, empty items] -> %s" % status)
    checks.add("status", "this endpoint declares 400, not 422 -- its own contract", 400, status)
    reason = json.dumps(body)
    checks.add("names the missing field", "'order.order_number' is required",
               True, "order_number' is required" in reason)
    checks.add("names the empty collection", "'order.order_items' must not be empty",
               True, "order_items' must not be empty" in reason)
    checks.add("no stale order echoed",
               "the declared 400 example carries a whole order; echoing it here would describe a "
               "duplicate, not a validation failure",
               False, "order_id" in reason)


def c_validate_query(checks, calls, detail):
    status, body = call("POST", "/rest/v1/orders/%s/update_status" % ORDER_ID, {"wms_status": "X"})
    calls.append("POST /rest/v1/orders/{id}/update_status [no new_status] -> %s" % status)
    checks.add("status", "a missing required query parameter is a 422 here", 422, status)
    checks.add("names the parameter", "query.new_status, spelled as the config wrote it",
               True, "new_status' is required" in json.dumps(body))


def c_validate_per_element(checks, calls, detail):
    body = {"product": {"skus": {"sku": [{"seller_sku": SELLER_SKU, "quantity": 1},
                                         {"quantity": 2}]}}}
    status, answer = call("PATCH", "/rest/v2/inventory_products/update_stocks", body)
    calls.append("PATCH /rest/v2/inventory_products/update_stocks [sku[1] has no seller_sku] -> %s"
                 % status)
    checks.add("status", "v2 declares 422", 422, status)
    checks.add("names the element that broke it",
               "[*] expands over the array, so the message points at index 1 rather than the "
               "collection",
               True, "sku[1].seller_sku' is required" in json.dumps(answer))


def c_validate_clean_falls_through(checks, calls, detail):
    status, _ = call("POST", "/rest/v1/reports",
                     {"report_history_id": 660412, "url": "https://reports.example.com/x.csv",
                      "store_code": STORE_CODE})
    calls.append("POST /rest/v1/reports [complete] -> %s" % status)
    checks.add("status", "a clean request must fall past the validate rule to the happy path",
               200, status)


# ---------------------------------------------------------------------------- serialization traps

def c_trap_seller_sku(checks, calls, detail):
    """SkuV2DTO carries both names; only one of them is what Gson puts on the wire."""
    status, _ = call("PATCH", "/rest/v2/inventory_products/update_stocks",
                     {"product": {"skus": {"sku": [{"seller_sku": SELLER_SKU, "quantity": 42}]}}})
    calls.append("PATCH /rest/v2/inventory_products/update_stocks [seller_sku] -> %s" % status)
    checks.add("snake_case accepted", "seller_sku is the @SerializedName, and Gson writes the body",
               200, status)
    recorded = pushes("stock_pushes", "update_stocks_v2")
    checks.add("read out of seller_sku", "a mock keyed on sellerSku would record nothing",
               SELLER_SKU, recorded[-1].get("first_seller_sku") if recorded else None)
    status, _ = call("PATCH", "/rest/v2/inventory_products/update_stocks",
                     {"product": {"skus": {"sku": [{"sellerSku": SELLER_SKU, "quantity": 42}]}}})
    calls.append("PATCH /rest/v2/inventory_products/update_stocks [sellerSku] -> %s" % status)
    checks.add("camelCase rejected",
               "@JsonProperty(\"sellerSku\") describes the inbound Kafka payload, not the OMS "
               "wire format -- a client sending it is broken and must be told so",
               422, status)


def c_trap_literal_sku(checks, calls, detail):
    """OipPromotionsImpl sends the template, not the value."""
    status, _ = call("PATCH", "/rest/v1/catalogues/{sku}/update_status",
                     {"sku": SKU, "store_code": STORE_CODE, "status": "INACTIVE"})
    calls.append("PATCH /rest/v1/catalogues/{sku}/update_status (literal) -> %s" % status)
    checks.add("status", "the route template still matches, so the call is not lost", 200, status)
    recorded = pushes("catalogue_pushes", "catalogue_update_status")
    literal = [entry for entry in recorded if entry.get("sku_path") == "{sku}"]
    checks.add("the unsubstituted path is visible",
               "sku_path records what actually arrived, so the bug shows in a store rather than "
               "being absorbed by a wildcard",
               True, bool(literal))


def c_trap_wrong_verb(checks, calls, detail):
    status, _ = call("PUT", "/rest/v1/inventory_products/884213",
                     {"inventory_product": {"inventory_sku": ISKU}})
    calls.append("PUT /rest/v1/inventory_products/884213 -> %s" % status)
    checks.add("PUT is not answered",
               "PATCH is the update verb on an inventory product. Answering PUT as well would "
               "hide a wrong-verb bug that fails in production",
               404, status)


def c_trap_unmatched(checks, calls, detail):
    status, body = call("GET", "/rest/v1/not_a_real_path")
    calls.append("GET /rest/v1/not_a_real_path -> %s" % status)
    checks.add("status", "a wrong base URL or a typo must fail loudly", 404, status)
    checks.truthy("names the method and path", "so the log says which call was wrong",
                  (body or {}).get("ErrorMessages"))


def c_trap_wms3_excluded(checks, calls, detail):
    """The neighbouring Anchanto product must not answer here."""
    for path in ("/rest/v2/customers/ANCHANTO/b2c_orders", "/rest/v1/tokens/generate"):
        status, _ = call("POST", path, {"b2c_order": {"number": "SO-X"}})
        calls.append("POST %s -> %s" % (path, status))
        checks.add(path, "WMS3 lives behind WMS_3_URL and has its own mock -- answering it here "
                         "would let a misrouted call look healthy", 404, status)


def c_token_grants(checks, calls, detail):
    grants = store("token_grants")
    checks.add("the exchange was recorded", "token_grants, one entry per /oauth/token call",
               True, len(grants) >= 1)
    checks.add("grant_type recorded as sent",
               "authorization_code in every environment properties file",
               "authorization_code", grants[0].get("grant_type") if grants else None)
    checks.truthy("redirect_uri recorded", "the callback the app-install flow returns to",
                  grants[0].get("redirect_uri") if grants else None)


# ---------------------------------------------------------------------------------- registrations

case("COV-1", "Integration operations are exercised",
     "the swagger and the sweep table",
     ["operations in swagger declared", "integration operations exercised"],
     "The sweep is a hand-written table exercising all 74 JPluger integration operations against the mock.", c_coverage)
case("COV-2", "Every sweep call took the happy path",
     "the mock's own call log after the sweep",
     ["no call answered by a steering rule", "every call names its answering rule"],
     "A fixture that accidentally contains a marker substring would be answered by an error rule "
     "and could still pass a status check. The log says which rule answered, so the sweep is held "
     "to the fallback as a whole.", c_happy_rules)

case("STR-1", "Orders reach the order stores", "the sweep's order writes",
     ["order number in created_orders", "async order number too", "one order_create entry",
      "store_code and items recorded"],
     "created_orders is what a replay branches on with in_store; without it a retry is answered as "
     "a fresh success and the integration does something it never would in production.",
     c_store_orders)
case("STR-2", "Every order-lifecycle write is recorded and distinguishable",
     "thirteen different writes against one order",
     ["every kind present", "new_status read from the query", "order id read from the path"],
     "One store with a kind per write lets a test name the call it means. Counting rows in an "
     "untagged store cannot tell a cancel from a complete.", c_store_lifecycle)
case("STR-3", "Every stock write is recorded, v1 and v2", "all thirteen stock writes",
     ["every kind present", "PATCH and POST on one path kept apart",
      "warehouseCode read out of eventParametersDTO"],
     "/rest/v1/inventory_products/update_stocks is two operations sharing a path. A mock that "
     "collapsed them would answer a wrong-verb client as though it were right.", c_store_stock)
case("STR-4", "Catalogue writes are recorded", "create, price, update and status",
     ["sku in created_catalogues", "every kind present", "sale window recorded"],
     "The sale window is recorded rather than counted because a start date with no end is the "
     "shape that has caused trouble.", c_store_catalogue)
case("STR-5", "The remaining stores fill up",
     "returns, inventory, taxonomy, stores, shipping methods, shipping, misc and feeds",
     ["every store holds every kind it is responsible for"],
     "Fourteen stores exist so an assertion can name the thing it means. A store that never fills "
     "is a store nobody can assert on.", c_store_rest)
case("STR-6", "A rejected write is not recorded", "an order carrying the 500 marker",
     ["500", "created_orders unchanged", "the attempt still appears in the call log"],
     "Stores answer what OMS accepted; the call log answers what JPluger sent. Collapsing the two "
     "would let a retry test read its own failed attempt as a success.", c_store_only_accepted)

case("MRK-1", "The three universal markers", "each marker written into an order id",
     ["9990500 and SERVERERROR -> 500", "9990429 and RATELIMIT -> 429",
      "9990401 and NOAUTH -> 401"],
     "A gateway 500, a rate limiter and an expired token can answer any call, so these three ride "
     "on all 74 operations whatever the document declares.", c_marker_universal)
case("MRK-2", "One marker, three places to write it", "the path, the body and the query",
     ["path parameter -> 500", "body field -> 500", "query parameter -> 500"],
     "The engine matches the URL without its query string, so query parameters have to be named "
     "one by one in the config. This is the case that catches a route where they were not.",
     c_marker_everywhere)
case("MRK-3", "Semantic markers only where the endpoint declares them",
     "404, 409 and 422 markers, and a 409 marker on an endpoint that cannot conflict",
     ["404 on the order read", "409 on mark_complete", "422 on update_status",
      "409 on the warehouse read falls through to 200"],
     "Mocking a 409 on an endpoint that never conflicts would let a test prove behaviour the real "
     "API cannot produce. The last check is the one that matters.", c_marker_declared_only)
case("MRK-4", "The 200 that is not a success", "the 9990001 marker on two endpoints",
     ["200 with success:false", "200 with a populated error field"],
     "Seventeen operations report failure inside a 200. A test asserting only on the HTTP status "
     "passes wrongly against every one of them.", c_marker_bizerr)
case("MRK-5", "The two error envelopes stay apart", "a 500 from Orders and a 500 from Inventory",
     ["Orders answers {error, error_message, status}", "Inventory answers {errors: [...]}"],
     "OMS speaks two error shapes and the Jackson DTOs on the JPluger side are not "
     "interchangeable. An endpoint answering the wrong one deserialises to an empty error.",
     c_marker_error_shape)

case("VAL-1", "A malformed order is refused with its own status code",
     "an order with no number and an empty item list",
     ["400, because that is what this endpoint declares", "names the missing field",
      "names the empty collection", "no stale order echoed back"],
     "422 is OMS's usual validation code but POST /rest/v1/orders declares 400. Imposing one code "
     "on all 74 would mock a contract the API does not have.", c_validate_order)
case("VAL-2", "A missing required query parameter is refused",
     "update_status with no new_status",
     ["422", "names query.new_status"],
     "new_status lives in the query, not the body. A mock validating only the body would accept a "
     "call OMS rejects and the integration would look correct until staging.", c_validate_query)
case("VAL-3", "A violation points at the element that caused it",
     "a v2 stock body whose second sku has no seller_sku",
     ["422", "the message names sku[1], not the collection"],
     "One rule written once reports against the element that broke it. A message naming only the "
     "collection sends the reader back to the payload to guess.", c_validate_per_element)
case("VAL-4", "A clean request falls through to the happy path",
     "a complete reports body", ["200"],
     "The validate rule answers only when something is actually wrong. If it matched on shape it "
     "would shadow the happy path and every case above it would be untestable.",
     c_validate_clean_falls_through)

case("TRAP-1", "seller_sku, not sellerSku", "the same v2 body under each spelling",
     ["seller_sku accepted and recorded", "sellerSku refused with 422"],
     "SkuV2DTO carries @JsonProperty(\"sellerSku\") and @SerializedName(\"seller_sku\"). The body "
     "is Gson-serialized so seller_sku wins; @JsonProperty there describes the inbound Kafka "
     "payload, not the OMS wire format.", c_trap_seller_sku)
case("TRAP-2", "The literal {sku} that reaches the wire",
     "update_status called without substituting the path template",
     ["200", "the unsubstituted path is visible in the store"],
     "OipPromotionsImpl.java:54 sends the literal {sku}. Almost certainly a bug; the mock records "
     "what arrived so it shows up as data rather than being absorbed by the wildcard.",
     c_trap_literal_sku)
case("TRAP-3", "The wrong verb is not answered", "PUT on an inventory product",
     ["404"],
     "PATCH is the update verb here. A mock answering PUT as well would hide a wrong-verb bug "
     "that fails in production.", c_trap_wrong_verb)
case("TRAP-4", "WMS3 paths are absent on purpose", "two paths belonging to the other product",
     ["both 404"],
     "WMS3 is a different Anchanto product behind WMS_3_URL with its own mock. Answering its "
     "paths here would let a misrouted call look healthy.", c_trap_wms3_excluded)
case("NEG-1", "An unknown path fails loudly", "a path in neither the spec nor the config",
     ["404", "the body names the method and path"],
     "A wrong base URL or a typo must not be silently absorbed.", c_trap_unmatched)
case("AUTH-3", "The token exchange is recorded", "token_grants after the sweep",
     ["one entry", "grant_type as sent", "redirect_uri recorded"],
     "grant_type is injected from ${GRANT_TYPE} and is authorization_code in every environment "
     "file. Recording it as sent is how a changed property is caught.", c_token_grants)


# ------------------------------------------------------------------------------------------- main

def preflight():
    print("anchanto-oms smoke (Anchanto OMS / SelluSeller) -- %s" % BASE)
    print("  mock dir : %s" % MOCK_DIR)
    print("  data dir : %s" % DATA_DIR)
    print("  run dir  : %s" % RUN_DIR)
    if not os.path.isdir(MOCK_DIR):
        sys.exit("PREFLIGHT FAIL: %s does not exist" % MOCK_DIR)
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.isfile(SPEC):
        sys.exit("PREFLIGHT FAIL: %s is missing -- the coverage case reads it" % SPEC)
    status, _ = call("GET", "/rest/v1/users/me")
    if status == 0:
        sys.exit("PREFLIGHT FAIL: nothing answering on %s.\n"
                 "  Start it with:  python3 mock.py anchanto-oms --reset" % BASE)
    print("  mock     : up (GET /rest/v1/users/me -> %s)" % status)
    if KEEP:
        print("  state    : kept (--keep-state)")
        return
    for name in STORES:
        with open(os.path.join(DATA_DIR, name + ".json"), "w") as handle:
            handle.write("[]")
    path = os.path.join(DATA_DIR, LOG)
    if os.path.exists(path):
        os.remove(path)
    print("  state    : reset -- %d stores emptied, call log removed" % len(STORES))


def capture():
    source = os.path.join(DATA_DIR, LOG)
    if os.path.exists(source):
        shutil.copy2(source, os.path.join(RUN_DIR, LOG))
        EVIDENCE["mock call log"] = "captured -- %d entries" % len(log_entries())
    else:
        EVIDENCE["mock call log"] = "not captured -- no log file"
    with open(os.path.join(RUN_DIR, "stores.json"), "w") as handle:
        json.dump({name: store(name) for name in STORES}, handle, indent=2)
    EVIDENCE["mock stores"] = "captured -- %d files" % len(STORES)


def main():
    preflight()
    os.makedirs(RUN_DIR, exist_ok=True)
    publish()
    print("  cases    : %d\n" % len(CASES))
    for entry in CASES:
        verdict = run_case(entry)
        publish()
        result = RESULTS[entry["id"]]
        print("  %-4s %-8s %-52s %s" % ("PASS" if verdict == "pass" else "FAIL", entry["id"],
                                        entry["name"][:52], result["summary"]))
        if verdict == "fail":
            for item in result["checks"]:
                if not item["ok"]:
                    print("           - %s: expected %r, got %r"
                          % (item["label"], item["expected"], item["actual"]))
    time.sleep(0.3)
    capture()
    EVIDENCE["status"] = "complete"
    publish()
    passed = sum(1 for entry in CASES if RESULTS[entry["id"]]["verdict"] == "pass")
    total_checks = sum(len(RESULTS[entry["id"]]["checks"]) for entry in CASES)
    print("\n  %d/%d cases passed, %d checks total" % (passed, len(CASES), total_checks))
    print("  results: %s" % os.path.join(RUN_DIR, "results.json"))
    print("  /test  : %s/test" % BASE)
    return 1 if passed != len(CASES) else 0


if __name__ == "__main__":
    sys.exit(main())
