#!/usr/bin/env python3
"""Smoke suite for the anchanto-wms mock — Anchanto WMS (Wareo3).

Proves the mock answers all 27 operations, steers on every marker, and records what it was sent.
It drives the mock alone — no app, no database, no Kafka — so a failure here is the mock or the
spec, never JPluger. Run it before blaming an integration.

Runner contract: TESTING.md. Writes
anchanto-wms/test-results/smoke/run-<stamp>/results.json, publishing every case
`pending` first and rewriting after each so /test tracks the live run.

  python3 anchanto-wms/suite-smoke.py
  BASE=http://127.0.0.1:23002 python3 anchanto-wms/suite-smoke.py --keep-state
"""

import json, os, sys, time, urllib.request, urllib.error, shutil, datetime

BASE = os.environ.get("BASE", "http://127.0.0.1:23002").rstrip("/")
SUITE = os.environ.get("SUITE", "smoke")
KEEP = "--keep-state" in sys.argv
CUST = "ANCHANTO"

HERE = os.path.dirname(os.path.abspath(__file__))
# This runner sits in the mock's own folder, beside the config it drives. The mock writes its
# stores and its call log into `mock-data/` there -- the `state_dir` the config declares -- and run
# folders sit beside that, under `test-results/`.
MOCK_DIR = HERE
DATA_DIR = os.path.join(MOCK_DIR, "mock-data")

STORES = ["token_grants", "created_orders", "order_pushes", "returns",
          "product_pushes", "party_pushes", "created_consignments", "consignment_pushes"]
LOG = "api-calls.har.json"
STAMP = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
RUN_DIR = os.path.join(MOCK_DIR, "test-results", SUITE, "run-" + STAMP)
V2 = "/rest/v2/customers/" + CUST


def call(method, path, body=None, wh="WH-KUL-01", token="mock_wms3_access_token"):
    url = BASE + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token: req.add_header("Authorization", "Bearer " + token)
    if wh:    req.add_header("warehouse-code", wh)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            raw, status = r.read().decode(), r.status
    except urllib.error.HTTPError as e:
        raw, status = e.read().decode(), e.code
    except Exception as e:
        return 0, {"_transport_error": str(e)}
    try:
        return status, json.loads(raw)
    except Exception:
        return status, raw


def store(name):
    try:
        with open(os.path.join(DATA_DIR, name + ".json")) as f:
            return json.load(f)
    except Exception:
        return []


CASES, RESULTS = [], {}
EVIDENCE = {"status": "running", "mock call log": "not captured", "mock stores": "not captured",
            "app": "not exercised -- mock only", "database": "not exercised -- mock only"}


def case(cid, name, given, then, note, fn):
    CASES.append({"id": cid, "name": name, "given": given, "then": then, "note": note, "fn": fn})


def publish():
    cases = []
    for c in CASES:
        r = RESULTS.get(c["id"])
        e = {"id": c["id"], "name": c["name"], "given": c["given"], "then": c["then"], "note": c["note"]}
        e.update(r if r else {"verdict": "pending"})
        cases.append(e)
    done = [c for c in cases if c["verdict"] in ("pass", "fail", "blocked")]
    doc = {"name": "Anchanto WMS (Wareo3) mock smoke -- 27 operations",
           "suite": SUITE,
           "at": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
           "base_url": BASE,
           "summary": {"pass": sum(1 for c in done if c["verdict"] == "pass"),
                       "fail": sum(1 for c in done if c["verdict"] == "fail"),
                       "blocked": sum(1 for c in done if c["verdict"] == "blocked")},
           "evidence": EVIDENCE, "cases": cases}
    os.makedirs(RUN_DIR, exist_ok=True)
    json.dump(doc, open(os.path.join(RUN_DIR, "results.json"), "w"), indent=2)


class Checks:
    def __init__(self): self.items = []
    def add(self, label, what, expected, actual):
        self.items.append({"label": label, "what": what, "expected": str(expected),
                           "actual": str(actual), "ok": str(expected) == str(actual)})
    def truthy(self, label, what, actual):
        got = "present" if actual not in (None, "", [], {}) else "missing"
        self.items.append({"label": label, "what": what, "expected": "present",
                           "actual": got, "ok": got == "present"})
    @property
    def ok(self): return all(i["ok"] for i in self.items)


def run_case(c):
    ch, calls, detail = Checks(), [], {}
    try:
        c["fn"](ch, calls, detail)
        verdict = "pass" if ch.ok else "fail"
    except Exception as e:
        ch.add("runner completed", "no exception from the case body", "yes", "no: %r" % (e,))
        verdict = "fail"
    np = sum(1 for i in ch.items if i["ok"])
    RESULTS[c["id"]] = {"verdict": verdict, "checks": ch.items, "calls": calls, "detail": detail,
                        "summary": "%d/%d checks passed" % (np, len(ch.items))}
    return verdict


# ------------------------------------------------------------------ cases

def c_token(ch, calls, detail):
    st, b = call("POST", "/oauth/token", None, wh=None, token=None)
    calls.append("POST /oauth/token (initial grant, no body) -> %s" % st)
    ch.add("status", "initial basic-auth grant", 200, st)
    ch.truthy("access_token", "the token every business call carries", b.get("access_token"))
    ch.truthy("refresh_token", "needed for the refresh grant", b.get("refresh_token"))
    ch.truthy("access_token_expire_in",
              "AuthenticateResponseDTO maps it through a private setter; absent means no expiry known",
              b.get("access_token_expire_in"))
    detail["token"] = b.get("access_token")


def c_token_refresh(ch, calls, detail):
    body = {"grant_type": "refresh_token", "refresh_token": "mock_wms3_refresh_token",
            "client_id": "jpluger-wms3", "client_secret": "s3cr3t"}
    st, b = call("POST", "/oauth/token", body, wh=None, token=None)
    calls.append("POST /oauth/token (refresh grant) -> %s" % st)
    ch.add("status", "refresh posts to the SAME url as the initial grant", 200, st)
    ch.truthy("access_token", "", b.get("access_token"))
    grants = store("token_grants")
    kinds = [g.get("grant_type") for g in grants]
    ch.add("both grants recorded and distinguishable",
           "token_grants keeps grant_type as sent; the initial grant has no body",
           True, "refresh_token" in kinds and "<basic auth, no body>" in kinds)


def c_token_reject(ch, calls, detail):
    st, b = call("POST", "/oauth/token", {"client_id": "NOAUTH-client"}, wh=None, token=None)
    calls.append("POST /oauth/token [NOAUTH] -> %s" % st)
    ch.add("status", "client credentials rejected", 401, st)
    ch.add("error code", "", "invalid_client", b.get("error"))


def c_create_b2c(ch, calls, detail):
    body = {"b2c_order": {"number": "SO-SMOKE-001", "company_code": "ANCHANTO",
                          "currency_code": "MYR", "shipping_type": "STANDARD",
                          "order_items_attributes": [
                              {"sku": "SKU-W3-001", "quantity": 2, "unit_price": 70000.0,
                               "selling_price": 63000.0}]}}
    st, b = call("POST", V2 + "/b2c_orders", body)
    calls.append("POST %s/b2c_orders -> %s" % (V2, st))
    ch.add("status", "create a b2c order", 200, st)
    ch.add("order_number echoed", "correlates the response to the submitted order",
           "SO-SMOKE-001", b.get("order_number"))
    ch.add("recorded in created_orders", "", True, "SO-SMOKE-001" in store("created_orders"))
    pushes = [p for p in store("order_pushes") if p.get("number") == "SO-SMOKE-001"]
    ch.add("warehouse-code HEADER received",
           "kebab-case header, not the snake_case body field -- a mock reading the body would miss it",
           "WH-KUL-01", pushes[0].get("warehouse_code_header") if pushes else None)
    ch.add("customer_code taken from the path",
           "scoped tenant, sourced from EHeaderKeys.CUSTOMER_CODE in real traffic",
           CUST, pushes[0].get("customer_code") if pushes else None)


def c_create_b2c_invalid(ch, calls, detail):
    st, b = call("POST", V2 + "/b2c_orders", {"b2c_order": {"order_items_attributes": []}})
    calls.append("POST %s/b2c_orders [no number, no items] -> %s" % (V2, st))
    ch.add("status is 422, not 400",
           "Wareo3 answers 422 for a malformed resource; a mock using 400 would test the wrong contract",
           422, st)
    ch.truthy("validation message", "", b.get("message"))


def c_cancel(ch, calls, detail):
    st, b = call("POST", V2 + "/b2c_orders/SO-SMOKE-001/cancel",
                 {"orderNumber": "SO-SMOKE-001", "remark": "Out of stock"})
    calls.append("POST %s/b2c_orders/SO-SMOKE-001/cancel -> %s" % (V2, st))
    ch.add("status", "cancel", 200, st)
    ch.add("response field", "writes answer {response, message}", "success", b.get("response"))
    rows = [p for p in store("order_pushes") if p.get("kind") == "b2c_cancel"]
    ch.add("camelCase orderNumber accepted",
           "the DTO has no @SerializedName, so Gson emits the Java name -- a mock demanding "
           "order_number would reject the real client",
           "Out of stock", rows[-1].get("remark") if rows else None)


def c_complete(ch, calls, detail):
    body = {"orderNumber": "SO-SMOKE-001",
            "deliveryDetails": {"deliveredTo": "Minh Nguyen", "deliveredRef": "REF-1",
                                "handoverTo": "Reception", "cashReceived": "true",
                                "receivedAmount": "148000", "comment": ""}}
    st, b = call("POST", V2 + "/b2c_orders/SO-SMOKE-001/complete", body)
    calls.append("POST %s/b2c_orders/SO-SMOKE-001/complete -> %s" % (V2, st))
    ch.add("status", "complete", 200, st)
    rows = [p for p in store("order_pushes") if p.get("kind") == "b2c_complete"]
    ch.add("nested camelCase deliveryDetails accepted", "",
           "Minh Nguyen", rows[-1].get("delivered_to") if rows else None)


def c_tracking(ch, calls, detail):
    body = {"tracking_number": "MYDHL0001234567", "orderNumber": "SO-SMOKE-001",
            "carrier": {"carrier_code": "DHL", "carrier_name": "DHL Express"}}
    st, _ = call("POST", V2 + "/b2c_orders/SO-SMOKE-001/tracking", body)
    calls.append("POST %s/b2c_orders/SO-SMOKE-001/tracking -> %s" % (V2, st))
    rows = [p for p in store("order_pushes") if p.get("kind") == "b2c_tracking"]
    ch.add("status", "push tracking", 200, st)
    ch.add("tracking number recorded", "", "MYDHL0001234567",
           rows[-1].get("tracking_number") if rows else None)
    ch.add("carrier code recorded", "", "DHL", rows[-1].get("carrier_code") if rows else None)


def c_shipping_docs(ch, calls, detail):
    body = {"url_type": "URL", "tracking_number": "MYDHL0001234567", "orderNumber": "SO-SMOKE-001"}
    st, _ = call("POST", V2 + "/b2c_orders/SO-SMOKE-001/shipping_docs", body)
    calls.append("POST %s/b2c_orders/SO-SMOKE-001/shipping_docs -> %s" % (V2, st))
    rows = [p for p in store("order_pushes") if p.get("kind") == "b2c_shipping_docs"]
    ch.add("status", "push shipping documents", 200, st)
    ch.add("url_type recorded", "", "URL", rows[-1].get("url_type") if rows else None)


def c_return(ch, calls, detail):
    body = {"orig_order_number": "SO-SMOKE-001", "externalReturnOrderNumber": "RET-EXT-001",
            "order": {"order_items": [{"sku": "SKU-W3-001", "quantity": 1}],
                      "pickup_date": "2026-08-22", "reason": "DAMAGED"}}
    st, b = call("POST", V2 + "/b2c_orders/SO-SMOKE-001/initiate_return", body)
    calls.append("POST %s/b2c_orders/SO-SMOKE-001/initiate_return -> %s" % (V2, st))
    ch.add("status", "path var is orig_order_number, not order_number", 200, st)
    ch.truthy("data.return_order_number returned",
              "the caller persists it; a mock omitting it strands the return",
              (b.get("data") or {}).get("return_order_number"))
    rows = store("returns")
    ch.add("reason recorded", "", "DAMAGED", rows[-1].get("reason") if rows else None)


def c_get_b2c(ch, calls, detail):
    st, b = call("GET", V2 + "/b2c_orders/SO-SMOKE-001/details")
    calls.append("GET %s/b2c_orders/SO-SMOKE-001/details -> %s" % (V2, st))
    ch.add("status", "read a b2c order", 200, st)
    ch.add("read envelope, not a payload array",
           "{summary, status_code, data:{id,type,attributes}} -- the OMS API's {\"payload\":[...]} "
           "appears nowhere in this API",
           True, isinstance(b, dict) and "summary" in b and "data" in b and "payload" not in b)
    ch.add("resource wrapper", "data carries id/type/attributes", True,
           all(k in (b.get("data") or {}) for k in ("id", "type", "attributes")))
    ch.add("order number echoed into attributes", "",
           "SO-SMOKE-001", ((b.get("data") or {}).get("attributes") or {}).get("number"))


def c_get_b2c_404(ch, calls, detail):
    st, _ = call("GET", V2 + "/b2c_orders/NOTFOUND-1/details")
    calls.append("GET %s/b2c_orders/NOTFOUND-1/details -> %s" % (V2, st))
    ch.add("status", "404 must be distinguishable from a 200 carrying an empty resource", 404, st)


def c_update_unassigned(ch, calls, detail):
    st, _ = call("POST", "/rest/v1/b2c/orders/SO-SMOKE-001/update_unassigned_order",
                 {"number": "SO-SMOKE-001"})
    calls.append("POST /rest/v1/b2c/orders/SO-SMOKE-001/update_unassigned_order -> %s" % st)
    ch.add("status", "a live v1 path with no v2 equivalent", 200, st)
    ch.add("recorded", "", True,
           any(p.get("kind") == "update_unassigned" for p in store("order_pushes")))


def c_create_b2b(ch, calls, detail):
    body = {"b2b_order": {"number": "PO-SMOKE-001", "supplier_code": "SUP-0001",
                          "company_code": "ANCHANTO", "currency_code": "MYR",
                          "is_stock_transfer": False,
                          "order_items_attributes": [{"sku": "SKU-W3-001", "quantity": 100,
                                                      "uom": "EA", "uom_quantity": 1}]}}
    st, b = call("POST", V2 + "/b2b_orders", body)
    calls.append("POST %s/b2b_orders -> %s" % (V2, st))
    ch.add("status", "create a b2b order", 200, st)
    ch.add("order_number echoed", "", "PO-SMOKE-001", b.get("order_number"))
    rows = [p for p in store("order_pushes") if p.get("kind") == "b2b_create"]
    ch.add("supplier_code recorded", "b2b-only field, absent from the b2c DTO",
           "SUP-0001", rows[-1].get("supplier_code") if rows else None)


def c_create_sto(ch, calls, detail):
    body = {"b2b_order": {"number": "STO-SMOKE-001", "company_code": "ANCHANTO",
                          "currency_code": "MYR", "is_stock_transfer": True,
                          "destination_store_code": "STORE-02",
                          "order_items_attributes": [{"sku": "SKU-W3-001", "quantity": 5}]}}
    st, b = call("POST", V2 + "/sto/orders", body)
    calls.append("POST %s/sto/orders -> %s" % (V2, st))
    rows = [p for p in store("order_pushes") if p.get("kind") == "sto_create"]
    ch.add("status", "create a stock-transfer order", 200, st)
    ch.add("order_number echoed", "", "STO-SMOKE-001", b.get("order_number"))
    ch.add("is_stock_transfer true", "what distinguishes an STO from a b2b order",
           "True", rows[-1].get("is_stock_transfer") if rows else None)
    ch.add("destination_store_code recorded", "", "STORE-02",
           rows[-1].get("destination_store_code") if rows else None)


def c_get_b2b(ch, calls, detail):
    st, b = call("GET", V2 + "/b2b_orders/PO-SMOKE-001/details")
    calls.append("GET %s/b2b_orders/PO-SMOKE-001/details -> %s" % (V2, st))
    ch.add("status", "read a b2b order", 200, st)
    ch.add("status_code is a NUMBER here",
           "WmsB2BGetOrderResponseDTO types it Integer while the b2c read types it String -- "
           "one field, two Java types, and the mock is faithful to both",
           "int", type(b.get("status_code")).__name__)


def c_get_b2b_items(ch, calls, detail):
    st, b = call("GET", V2 + "/b2b_orders/PO-SMOKE-001/order_items")
    calls.append("GET %s/b2b_orders/PO-SMOKE-001/order_items -> %s" % (V2, st))
    ch.add("status", "read b2b order items", 200, st)
    ch.add("data is a list", "the only read that returns one", "list", type(b.get("data")).__name__)
    ch.truthy("meta pagination", "the only read carrying it", b.get("meta"))
    ch.add("first item carries sku and warehouse", "", True,
           bool(b.get("data")) and "sku" in b["data"][0] and "warehouse" in b["data"][0])


def c_get_b2b_items_empty(ch, calls, detail):
    st, b = call("GET", V2 + "/b2b_orders/EMPTY-1/order_items")
    calls.append("GET %s/b2b_orders/EMPTY-1/order_items -> %s" % (V2, st))
    ch.add("status", "an order with no items is a 200, not a 404", 200, st)
    ch.add("empty data list", "", 0, len(b.get("data") or []))
    ch.add("meta.total zero", "", 0, (b.get("meta") or {}).get("total"))


def c_create_product(ch, calls, detail):
    body = {"product": {"sku": "SKU-SMOKE-001", "name": "Smoke Product",
                        "company_code": "ANCHANTO", "base_uom_code": "EA",
                        "country_of_origin_iso": "MY",
                        "product_dimensions_attributes": [
                            {"uom_code": "EA", "length_cm": 12.0, "width_cm": 8.0,
                             "height_cm": 10.0, "weight_gm": 400.0, "no_of_units": 1}],
                        "product_sales_informations_attributes": [
                            {"currency_code": "MYR", "selling_price": 63000.0,
                             "retail_price": 75000.0, "cost_price": 35000.0, "uom_code": "EA"}]}}
    st, b = call("POST", V2 + "/products", body)
    calls.append("POST %s/products -> %s" % (V2, st))
    rows = [p for p in store("product_pushes") if p.get("kind") == "create"]
    ch.add("status", "create a product", 200, st)
    ch.add("sku echoed", "", "SKU-SMOKE-001", b.get("sku"))
    ch.add("body carries its own status field",
           "Wms3ProductResponseDTO.status is a body field distinct from the HTTP status", 200, b.get("status"))
    ch.add("unit-suffixed dimensions arrived",
           "length_cm / weight_gm, not the bare height/weight the OMS API uses",
           "12.0", rows[-1].get("length_cm") if rows else None)


def c_update_product_put(ch, calls, detail):
    body = {"product": {"sku": "SKU-SMOKE-001", "name": "Smoke Product v2"}}
    st, b = call("PUT", V2 + "/products/SKU-SMOKE-001", body)
    calls.append("PUT %s/products/SKU-SMOKE-001 -> %s" % (V2, st))
    ch.add("PUT succeeds", "the ONLY PUT in the whole surface", 200, st)
    ch.add("sku echoed", "", "SKU-SMOKE-001", b.get("sku"))


def c_update_product_post_rejected(ch, calls, detail):
    st, _ = call("POST", V2 + "/products/SKU-SMOKE-001", {"product": {"sku": "SKU-SMOKE-001"}})
    calls.append("POST %s/products/SKU-SMOKE-001 (wrong verb) -> %s" % (V2, st))
    ch.add("POST on the update path 404s",
           "proves the route really is PUT-only. If this passed as 200 the mock would hide a "
           "wrong-verb bug that 404s in production",
           404, st)


def c_change_status(ch, calls, detail):
    st, _ = call("POST", V2 + "/products/change_status",
                 {"sku": "SKU-SMOKE-001", "state": "INACTIVE", "remark": "Discontinued"})
    calls.append("POST %s/products/change_status -> %s" % (V2, st))
    rows = [p for p in store("product_pushes") if p.get("kind") == "change_status"]
    ch.add("status", "change product status", 200, st)
    ch.add("state recorded", "", "INACTIVE", rows[-1].get("state") if rows else None)


def c_get_product(ch, calls, detail):
    st, b = call("GET", V2 + "/products/SKU-SMOKE-001")
    calls.append("GET %s/products/SKU-SMOKE-001 -> %s" % (V2, st))
    ch.add("status", "read a product", 200, st)
    ch.add("same read envelope as the order reads", "", True,
           isinstance(b, dict) and "summary" in b and "data" in b)


def c_supplier(ch, calls, detail):
    body = {"supplier": {"code": "SUP-SMOKE-1", "name": "Acme Supplies",
                         "email": "ops@acme.example", "active": True, "supplier_type": "VENDOR"}}
    st, b = call("POST", V2 + "/suppliers", body)
    calls.append("POST %s/suppliers -> %s" % (V2, st))
    ch.add("status", "create a supplier", 200, st)
    ch.truthy("data.id returned", "", (b.get("data") or {}).get("id"))
    st2, _ = call("POST", V2 + "/suppliers/update_supplier", body)
    calls.append("POST %s/suppliers/update_supplier -> %s" % (V2, st2))
    ch.add("update is a named sub-resource",
           "…/suppliers/update_supplier, not PUT …/suppliers/{code}", 200, st2)
    rows = [p for p in store("party_pushes") if p.get("party") == "supplier"]
    ch.add("both create and update recorded", "", 2, len(rows))


def c_buyer_shared_dto(ch, calls, detail):
    body = {"buyer": {"code": "BUY-SMOKE-1", "name": "Retail Co", "active": True,
                      "supplier_type": "VENDOR"}}
    st, b = call("POST", V2 + "/buyers", body)
    calls.append("POST %s/buyers -> %s" % (V2, st))
    st2, _ = call("POST", V2 + "/buyers/update_buyer", body)
    calls.append("POST %s/buyers/update_buyer -> %s" % (V2, st2))
    rows = [p for p in store("party_pushes") if p.get("party") == "buyer"]
    ch.add("create status", "", 200, st)
    ch.add("update status", "named sub-resource, as with suppliers", 200, st2)
    ch.add("supplier_type accepted on a BUYER payload",
           "suppliers and buyers share one Wms3PartyDataDTO, so a supplier-only field rides along",
           "VENDOR", rows[0].get("supplier_type_present") if rows else None)


def c_party_reads(ch, calls, detail):
    st1, b1 = call("GET", V2 + "/suppliers/SUP-SMOKE-1")
    calls.append("GET %s/suppliers/SUP-SMOKE-1 -> %s" % (V2, st1))
    st2, b2 = call("GET", V2 + "/buyers/BUY-SMOKE-1")
    calls.append("GET %s/buyers/BUY-SMOKE-1 -> %s" % (V2, st2))
    ch.add("supplier read", "path var supplier_code", 200, st1)
    ch.add("buyer read", "path var is `code`, not buyer_code -- inconsistent and faithful", 200, st2)
    ch.add("supplier resource type", "", "supplier", (b1.get("data") or {}).get("type"))
    ch.add("buyer resource type", "", "buyer", (b2.get("data") or {}).get("type"))


def c_consignment(ch, calls, detail):
    body = {"consignment": {"number": "CN-SMOKE-001", "supplier_code": "SUP-SMOKE-1",
                            "po_ref_number": "PO-REF-1", "order_type": "PURCHASE",
                            "ship_date": "2026-08-10", "receiving_date": "2026-08-14",
                            "consignment_items_attributes": [{"sku": "SKU-W3-001", "quantity": 100}],
                            "consignment_vas_attributes": [{"shrink_wrapping": True}]}}
    st, b = call("POST", V2 + "/consignments", body)
    calls.append("POST %s/consignments -> %s" % (V2, st))
    ch.add("status", "create a consignment", 200, st)
    ch.add("order_number returned",
           "the caller persists it -- a mock omitting it strands the consignment",
           "CN-SMOKE-001", b.get("order_number"))
    ch.add("recorded", "", True, "CN-SMOKE-001" in store("created_consignments"))
    st2, b2 = call("GET", V2 + "/consignments/CN-SMOKE-001/details")
    calls.append("GET %s/consignments/CN-SMOKE-001/details -> %s" % (V2, st2))
    ch.add("read status", "", 200, st2)
    ch.add("status_code is a number here too",
           "WmsB2BGetConsignmentResponseDTO types it int", "int", type(b2.get("status_code")).__name__)


def c_legacy_reads(ch, calls, detail):
    for path, label in [("/rest/v1/b2c/orders/SO-SMOKE-001/details", "b2c"),
                        ("/rest/v1/b2b/orders/PO-SMOKE-001/details", "b2b")]:
        st, b = call("GET", path)
        calls.append("GET %s -> %s" % (path, st))
        ch.add("%s v1 read status" % label,
               "declared with a %s placeholder and String.format -- the third placeholder style", 200, st)
        ch.add("%s v1 read envelope" % label, "", True,
               isinstance(b, dict) and "summary" in b and "data" in b)


def c_markers(ch, calls, detail):
    want = [("9990500", 500, "server error"),
            ("9990429", 429, "rate limited"),
            ("9990422", 422, "unprocessable -- Wareo3 uses 422, not 400"),
            ("9990401", 401, "token rejected")]
    for m, exp, why in want:
        st, _ = call("POST", V2 + "/b2c_orders",
                     {"b2c_order": {"number": m, "order_items_attributes": [{"sku": "S", "quantity": 1}]}})
        calls.append("POST %s/b2c_orders [%s] -> %s" % (V2, m, st))
        ch.add("%s -> %s" % (m, exp), why, exp, st)


def c_biz_error(ch, calls, detail):
    st, b = call("POST", V2 + "/b2c_orders",
                 {"b2c_order": {"number": "9990001", "order_items_attributes": [{"sku": "S", "quantity": 1}]}})
    calls.append("POST %s/b2c_orders [9990001] -> %s" % (V2, st))
    ch.add("status", "a 2xx that still failed", 200, st)
    ch.add("response says error",
           "writes carry their own response field; 200 alone does not mean success here",
           "error", b.get("response"))


def c_unmatched(ch, calls, detail):
    st, _ = call("GET", V2 + "/definitely-not-an-endpoint")
    calls.append("GET %s/definitely-not-an-endpoint -> %s" % (V2, st))
    ch.add("status", "a wrong URL must fail loudly, not be absorbed", 404, st)


# ------------------------------------------------------------------ registration

case("AUTH-1", "OAuth2 initial grant", "no body — client credentials go in the Authorization header",
     ["200", "access_token, refresh_token and access_token_expire_in all present"],
     "This is the live mechanism. /rest/v1/tokens/generate is legacy v1 and its token is never used "
     "for a v2 call, so it is deliberately absent from the mock.", c_token)
case("AUTH-2", "OAuth2 refresh grant", "grant_type refresh_token, posted to the same URL",
     ["200", "a token back", "both grants recorded and distinguishable"],
     "Wms3RequestHandler posts initial and refresh to one URL, so the store is the only way to prove "
     "which one happened.", c_token_refresh)
case("AUTH-3", "Rejected credentials", "client_id containing NOAUTH", ["401", "invalid_client"],
     "Lets a test exercise the failure path without breaking the token for every other case.", c_token_reject)
case("B2C-1", "Create a B2C order", "one order, one item, warehouse-code header set",
     ["200", "order_number echoed", "recorded", "the header arrived", "customer_code from the path"],
     "The header is the trap: warehouse-code is kebab-case and lives in the headers, while "
     "warehouse_code is a snake_case body field. Both constants exist side by side.", c_create_b2c)
case("B2C-2", "Malformed B2C order", "no number, empty items", ["422, not 400"],
     "Wareo3 answers 422 for a malformed resource. Mocking it as 400 would test a contract the real "
     "API does not have.", c_create_b2c_invalid)
case("B2C-3", "Cancel", "orderNumber in camelCase, as the client really sends it",
     ["200", "response success", "the camelCase field was accepted"],
     "Wms3SalesOrderCancelRequestDTO carries no @SerializedName, so Gson emits the Java name into an "
     "otherwise snake_case body.", c_cancel)
case("B2C-4", "Complete", "deliveryDetails with six camelCase members",
     ["200", "nested camelCase accepted"], "Same Gson fallback, one level deeper.", c_complete)
case("B2C-5", "Push tracking", "tracking number and carrier",
     ["200", "tracking number recorded", "carrier code recorded"], "", c_tracking)
case("B2C-6", "Push shipping documents", "url_type URL", ["200", "url_type recorded"], "", c_shipping_docs)
case("B2C-7", "Initiate a return", "orig_order_number path var, one returned item",
     ["200", "data.return_order_number returned", "reason recorded"],
     "The path variable is orig_order_number, not order_number, and the caller persists "
     "return_order_number — omit it and the return is stranded.", c_return)
case("B2C-8", "Read a B2C order", "an order number",
     ["200", "read envelope with no payload array", "data carries id/type/attributes", "number echoed"],
     "Every read answers {summary, status_code, data:{id,type,attributes}}. The OMS API's "
     "{\"payload\":[...]} appears nowhere in this API.", c_get_b2c)
case("B2C-9", "Read a missing order", "order number containing NOTFOUND", ["404"],
     "A 404 has to be distinguishable from a 200 carrying an empty resource.", c_get_b2c_404)
case("B2C-10", "Update an unassigned order", "the live v1 path", ["200", "recorded"],
     "A /rest/v1/ path with no v2 equivalent, still live. In scope despite the v2-only rule — "
     "excluding it on the version prefix alone would have been wrong.", c_update_unassigned)
case("B2B-1", "Create a B2B order", "supplier_code and uom fields",
     ["200", "order_number echoed", "supplier_code recorded"],
     "b2b/sto extend the b2c shape with supplier_code, is_stock_transfer and destination_store_code.",
     c_create_b2b)
case("B2B-2", "Create an STO order", "is_stock_transfer true, destination_store_code set",
     ["200", "order_number echoed", "both STO fields recorded"],
     "STO reuses the b2b envelope entirely; only those two fields distinguish it.", c_create_sto)
case("B2B-3", "Read a B2B order", "an order number",
     ["200", "status_code comes back as a JSON number"],
     "WmsB2BGetOrderResponseDTO types status_code Integer while WmsGetOrderResponseDTO types it "
     "String. One field, two Java types — the mock reproduces both rather than picking one.", c_get_b2b)
case("B2B-4", "Read B2B order items", "an order number",
     ["200", "data is a list", "meta present", "items carry sku and warehouse"],
     "The only read returning a list and the only one with pagination meta.", c_get_b2b_items)
case("B2B-5", "Read items for an empty order", "order number containing EMPTY",
     ["200", "empty list", "meta.total zero"],
     "An order with no items is a 200 with an empty list, not a 404 — the opposite of the OMS "
     "inventory_products endpoint, where 404 is the pagination terminator.", c_get_b2b_items_empty)
case("PROD-1", "Create a product", "dimensions and sales info",
     ["200", "sku echoed", "body status field", "length_cm arrived"],
     "Dimensions are unit-suffixed (length_cm, weight_gm), unlike the OMS API's bare height/weight. "
     "And Wms3ProductResponseDTO.status is a body field, not the HTTP status.", c_create_product)
case("PROD-2", "Update a product with PUT", "PUT …/products/{sku}", ["200", "sku echoed"],
     "The only PUT in 27 operations.", c_update_product_put)
case("PROD-3", "Update a product with POST", "the same path, wrong verb", ["404"],
     "The negative that gives PROD-2 its meaning. If POST also answered 200 the mock would hide a "
     "wrong-verb bug that 404s in production.", c_update_product_post_rejected)
case("PROD-4", "Change product status", "state INACTIVE", ["200", "state recorded"], "", c_change_status)
case("PROD-5", "Read a product", "a sku", ["200", "same read envelope"], "", c_get_product)
case("PARTY-1", "Create and update a supplier", "one supplier, then the update sub-resource",
     ["200 on both", "data.id returned", "both recorded"],
     "Update is a named sub-resource — …/suppliers/update_supplier — not a PUT on the identifier.",
     c_supplier)
case("PARTY-2", "Create and update a buyer", "a buyer payload carrying supplier_type",
     ["200 on both", "supplier_type accepted on a buyer"],
     "Suppliers and buyers share one Wms3PartyDataDTO, so a supplier-only field rides along on buyer "
     "payloads. A mock rejecting it would be stricter than the real API.", c_buyer_shared_dto)
case("PARTY-3", "Read a supplier and a buyer", "one of each",
     ["200 on both", "correct resource type on each"],
     "The supplier read uses {supplier_code} and the buyer read uses {code} — inconsistent, and "
     "reproduced rather than tidied.", c_party_reads)
case("CONS-1", "Create and read a consignment", "one consignment with items and VAS",
     ["200", "order_number returned", "recorded", "read returns a numeric status_code"],
     "order_number is persisted by the caller. WmsB2BGetConsignmentResponseDTO types status_code as "
     "a plain int — a third variant of that field.", c_consignment)
case("LEGACY-1", "The two WREO_DOMAIN v1 reads", "a b2c and a b2b order number",
     ["200 on both", "same read envelope"],
     "Declared with %s placeholders and String.format — the third placeholder style in this area. "
     "They live under wms3-core/utils/oip/, whose handler injects WREO_DOMAIN; `oip` means the OMS "
     "platform everywhere else in the repo, which is how they nearly got missed.", c_legacy_reads)
case("MRK-1", "All four steering markers", "each marker as the order number",
     ["9990500 → 500", "9990429 → 429", "9990422 → 422", "9990401 → 401"],
     "422 rather than 400 is the one to note: it is what Wareo3 actually answers for a malformed "
     "resource.", c_markers)
case("MRK-2", "In-band business failure", "order number 9990001",
     ["200", "response field says error"],
     "Writes carry their own response field, so a 200 alone does not mean success. A test asserting "
     "only on the HTTP status would pass here wrongly.", c_biz_error)
case("NEG-1", "Unknown path", "a path in neither the spec nor the config", ["404"],
     "A wrong base URL or a typo must fail loudly rather than being absorbed.", c_unmatched)


# ------------------------------------------------------------------ main

def preflight():
    print("anchanto-wms smoke (Anchanto WMS / Wareo3) -- %s" % BASE)
    print("  mock dir : %s" % MOCK_DIR)
    print("  data dir : %s" % DATA_DIR)
    print("  run dir  : %s" % RUN_DIR)
    if not os.path.isdir(MOCK_DIR):
        sys.exit("PREFLIGHT FAIL: %s does not exist" % MOCK_DIR)
    os.makedirs(DATA_DIR, exist_ok=True)
    st, _ = call("POST", "/oauth/token", None, wh=None, token=None)
    if st == 0:
        sys.exit("PREFLIGHT FAIL: nothing answering on %s.\n"
                 "  Start it with:  python3 mock.py anchanto-wms --reset" % BASE)
    print("  mock     : up (/oauth/token -> %s)" % st)
    if KEEP:
        print("  state    : kept (--keep-state)")
        return
    for s in STORES:
        open(os.path.join(DATA_DIR, s + ".json"), "w").write("[]")
    p = os.path.join(DATA_DIR, LOG)
    if os.path.exists(p):
        os.remove(p)
    print("  state    : reset -- %d stores emptied, call log removed" % len(STORES))


def capture():
    src = os.path.join(DATA_DIR, LOG)
    if os.path.exists(src):
        shutil.copy2(src, os.path.join(RUN_DIR, LOG))
        try:
            n = len(json.load(open(src)).get("log", {}).get("entries", []))
            EVIDENCE["mock call log"] = "captured -- %d entries" % n
        except Exception:
            EVIDENCE["mock call log"] = "captured -- unparseable"
    else:
        EVIDENCE["mock call log"] = "not captured -- no log file"
    json.dump({s: store(s) for s in STORES},
              open(os.path.join(RUN_DIR, "stores.json"), "w"), indent=2)
    EVIDENCE["mock stores"] = "captured -- %d files" % len(STORES)


def main():
    preflight()
    os.makedirs(RUN_DIR, exist_ok=True)
    publish()
    print("  cases    : %d\n" % len(CASES))
    for c in CASES:
        v = run_case(c)
        publish()
        r = RESULTS[c["id"]]
        print("  %-4s %-9s %-46s %s" % ("PASS" if v == "pass" else "FAIL", c["id"],
                                        c["name"][:46], r["summary"]))
        if v == "fail":
            for i in r["checks"]:
                if not i["ok"]:
                    print("            - %s: expected %r, got %r" % (i["label"], i["expected"], i["actual"]))
    time.sleep(0.3)
    capture()
    EVIDENCE["status"] = "complete"
    publish()
    p = sum(1 for c in CASES if RESULTS[c["id"]]["verdict"] == "pass")
    nchecks = sum(len(RESULTS[c["id"]]["checks"]) for c in CASES)
    print("\n  %d/%d cases passed, %d checks total" % (p, len(CASES), nchecks))
    print("  results: %s" % os.path.join(RUN_DIR, "results.json"))
    print("  /test  : %s/test" % BASE)
    return 1 if p != len(CASES) else 0


if __name__ == "__main__":
    sys.exit(main())
