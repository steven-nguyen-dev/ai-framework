#!/usr/bin/env python3
"""Generates anchanto-oms/anchanto-oms.mock.json from the OMS swagger.

The config is generated rather than hand-written because it restates 74 operations' success
examples, and a hand-copied restatement drifts from the spec the first time the spec is
regenerated. Everything the generator cannot read out of the document -- which store a write
records into, which field a response echoes back, what the partner requires beyond the schema --
lives in TABLE below, keyed by "METHOD path", and is the only part a human edits.

    python3 anchanto-oms/build-config.py
    python3 mock.py anchanto-oms --check      # expect 74 routes, 74 configured

Config format: CONFIG.md.
"""

import copy
import json
import os

# This generator sits in the mock's own folder, beside the config it writes.
HERE = os.path.dirname(os.path.abspath(__file__))
PACKAGE = os.path.dirname(HERE)
MOCK_DIR = HERE
SPEC = os.path.join(MOCK_DIR, "anchanto-oms-swagger.json")
OUT = os.path.join(MOCK_DIR, "anchanto-oms.mock.json")

METHODS = ("get", "post", "put", "patch", "delete")

# --------------------------------------------------------------------------------------- markers

# Universal markers ride on every operation: a gateway 500, a rate limiter and an expired token can
# answer any call, whatever the document declares. The rest are semantic and are emitted only where
# the operation actually declares that status -- mocking a 409 on an endpoint that never conflicts
# would let a test prove something the real API cannot do.
UNIVERSAL = [("9990500", "SERVERERROR", 500), ("9990429", "RATELIMIT", 429),
             ("9990401", "NOAUTH", 401)]
DECLARED_ONLY = [("9990422", "INVALID", 422), ("9990404", "NOTFOUND", 404),
                 ("9990409", "CONFLICT", 409), ("9990400", "BADREQ", 400)]
BIZERR = "9990001"

TITLES = {400: "Bad Request", 401: "Unauthorized", 404: "Not Found", 409: "Conflict",
          422: "Unprocessable Entity", 429: "Too Many Requests", 500: "Internal Server Error"}


def error_family(op):
    """Which of the two error envelopes this operation uses.

    OMS answers errors in two shapes and they are not interchangeable: Orders and most writes use
    {error, error_message, status}, while Inventory and the catalogue reads use
    {errors: [{message, error_code}]}. An operation's undeclared statuses are answered in the shape
    its declared ones already use, so one endpoint never speaks both.
    """
    for code, response in (op.get("responses") or {}).items():
        if code.startswith("2"):
            continue
        example = json_example(response)
        if isinstance(example, dict) and "errors" in example:
            return "errors_array"
    return "error_object"


def canonical_error(status, family, why):
    if family == "errors_array":
        return {"errors": [{"message": why, "error_code": "1%d" % status}]}
    return {"error": TITLES[status], "error_message": why, "status": status}


# --------------------------------------------------------------------------------------- helpers

def json_example(response):
    media = ((response or {}).get("content") or {}).get("application/json") or {}
    return media.get("example")


def success(op):
    """The status and example body the document declares for the happy path."""
    for code in ("200", "201", "202", "204"):
        if code in (op.get("responses") or {}):
            return int(code), copy.deepcopy(json_example(op["responses"][code]))
    return 200, {}


def set_path(node, path, value):
    """Writes into a copied example by dotted path -- "order.order_number", "payload[0].sku"."""
    steps = []
    for raw in path.split("."):
        name, _, index = raw.partition("[")
        steps.append(name)
        if index:
            steps.append(int(index.rstrip("]")))
    for step in steps[:-1]:
        node = node[step]
    node[steps[-1]] = value


def echo(body, pairs):
    for path, template in (pairs or {}).items():
        try:
            set_path(body, path, template)
        except (KeyError, IndexError, TypeError):
            raise SystemExit("echo path %r is not in the success example" % path)
    return body


def marker_when(tokens, query_names):
    """A marker is found anywhere it could plausibly be written.

    Path parameters land in the URL, body fields land in the raw body, and the identifying query
    parameters are named one by one -- so a tester puts 9990404 in the order id, the sku or the
    store_code and gets the same answer without having to learn which one this endpoint reads.
    Both spellings of one marker, the numeric and the word, select the same rule.
    """
    branches = []
    for token in tokens:
        branches.append({"url": {"contains": token}})
        branches.append({"raw_body": {"contains": token}})
        branches += [{"query." + name: {"contains": token}} for name in query_names]
    return {"any": branches}


def bizerr_body(example):
    """The success example turned into the in-band failure the same endpoint can answer.

    Seventeen operations report failure inside a 200: `success` goes false, or `errors` fills up,
    or `error` stops being null. A test asserting only on the HTTP status passes wrongly against
    every one of them, which is the whole reason this marker exists.
    """
    body = copy.deepcopy(example)
    why = "mock marker %s/BIZERR: accepted with an in-band failure" % BIZERR
    if not isinstance(body, dict):
        return None
    touched = False
    if "success" in body:
        body["success"], touched = False, True
    if "status" in body and isinstance(body.get("status"), bool):
        body["status"], touched = False, True
    if "error" in body:
        body["error"], touched = why, True
    if isinstance(body.get("errors"), list):
        body["errors"], touched = [{"message": why, "error_code": "1001"}], True
    if "failed_count" in body and "created_count" in body:
        body["failed_count"], body["created_count"], touched = body["created_count"], 0, True
    if not touched:
        return None
    if "message" in body:
        body["message"] = why
    return body


def validation_response(op, family):
    """The status and body a `validate` block answers with.

    422 when the operation declares it, 400 when it declares that instead -- the endpoint's own
    contract rather than one code imposed on all 74. The declared example is reused so the shape is
    the partner's, with the collected violations written into whichever field carries the reason.
    """
    responses = op.get("responses") or {}
    status = 422 if "422" in responses else (400 if "400" in responses else 422)
    body = copy.deepcopy(json_example(responses.get(str(status)))) \
        or canonical_error(status, family, "")
    summary = "${validation.summary}"
    if isinstance(body, dict):
        # A declared error example often echoes the resource back -- the 400 on POST /rest/v1/orders
        # carries a whole order. That echo belongs to the case the example was written for
        # (a duplicate order number), not to a request that failed validation and created nothing,
        # so the resource is dropped and only the reason is kept.
        for key in [k for k, v in body.items()
                    if k != "errors" and (isinstance(v, dict) or (isinstance(v, list) and v))]:
            del body[key]
        carried = False
        if isinstance(body.get("errors"), list):
            body["errors"], carried = [{"message": summary, "error_code": "1%d" % status}], True
        for field in ("error_message", "error_description", "message"):
            if field in body:
                body[field], carried = summary, True
        if not carried:
            # Nowhere in the declared example says why, so the reason is added rather than moved.
            # Adding it where a field already carries the reason would leave two, disagreeing.
            if isinstance(body.get("error"), str):
                body["error"] = summary
            else:
                body["error_message"] = summary
        if "success" in body:
            body["success"] = False
    return status, body


# ----------------------------------------------------------------------------------------- stores

STORES = {
    "token_grants":               "every /oauth/token exchange, with the grant_type as sent",
    "created_orders":             "order numbers OMS accepted, single and async",
    "order_pushes":               "every order-lifecycle write, tagged by kind",
    "shipping_pushes":            "shipping details, async shipping details and manifests",
    "returns":                    "return orders created against an existing order",
    "created_inventory_products": "inventory_sku values accepted",
    "stock_pushes":               "every stock update -- v1 and v2, absolute, delta and async",
    "created_catalogues":         "catalogue skus accepted",
    "catalogue_pushes":           "catalogue writes, including price and listing-status changes",
    "taxonomy_pushes":            "brand, category and category-attribute writes",
    "store_pushes":               "store meta-data stamps",
    "shipping_method_pushes":     "shipping methods and their seller-marketplace mappings",
    "misc_pushes":                "payouts, reports, transactions and promotion failures",
    "async_feeds":                "every asynchronous feed queued, with the feed id handed back",
}


def record(store, value):
    return {"record": {"store": store, "values": [value]}}


def append(store, **entry):
    return {"append": {"store": store, "entry": entry}}


def push(kind, store="order_pushes", **fields):
    return append(store, kind=kind, **fields)


ORDER = "${path.id}"

# ------------------------------------------------------------------------------------------ table
#
# "METHOD path" -> what the generator cannot read out of the document.
#   note      one sentence naming what this route does that a bare spec route would not
#   echo      success-example field -> template, so two runs are distinguishable
#   then      actions run when the request is accepted (markers and validation answer first, so a
#             store only ever holds what the mock actually took)
#   validate  obligations the prose states and the schema does not
#   name      the fallback rule's name, which is what /log prints for the happy path

TABLE = {

    # -- Auth ------------------------------------------------------------------------------------
    "POST /oauth/token": {
        "note": "The one call with no bearer token. grant_type is authorization_code and the body "
                "is JSON, not form-urlencoded -- a mock reading query parameters would answer a "
                "call JPluger never makes.",
        "name": "no marker -- authorization_code exchanged, 200 with an access_token",
        "then": [push("oauth_token", store="token_grants",
                      grant_type="${body.grant_type|<absent>}",
                      client_id="${body.client_id|<absent>}",
                      code="${body.code|<absent>}",
                      redirect_uri="${body.redirect_uri|<absent>}")],
        "validate": {"required": ["client_id", "client_secret", "grant_type", "code"]},
    },
    "GET /rest/v1/users/me": {
        "note": "The identity probe fired straight after the token exchange; its seller_code and "
                "is_multiwarehousing populate the Seller row.",
        "name": "no marker -- 200, the seller behind the bearer token",
    },

    # -- Orders ----------------------------------------------------------------------------------
    "GET /rest/v1/orders": {"name": "no marker -- 200, one page of orders"},
    "POST /rest/v1/orders": {
        "note": "The order create. order_number is echoed so two runs are distinguishable, and "
                "recorded so a replay can be answered the way OMS answers one.",
        "name": "no marker -- order accepted, 200 with the submitted order_number",
        "echo": {"order_number": "${body.order.order_number}",
                 "store_code": "${body.order.store_code}",
                 "marketplace_code": "${body.order.marketplace_code}"},
        "then": [record("created_orders", "${body.order.order_number}"),
                 push("order_create", order_number="${body.order.order_number}",
                      store_code="${body.order.store_code}",
                      marketplace_code="${body.order.marketplace_code}",
                      order_total="${body.order.order_total}",
                      is_historical_order="${body.order.is_historical_order|<absent>}",
                      items="${body.order.order_items}")],
        "validate": {"required": ["order.order_number", "order.store_code",
                                  "order.order_items[*].sku"],
                     "non_empty": ["order.order_items"]},
    },
    "POST /rest/v1/orders/acknowledge_orders": {
        "note": "Answers 200 with error: null on the happy path -- the in-band failure field that "
                "makes 9990001 worth having.",
        "name": "no marker -- batch acknowledged, 200 with error null",
        "then": [push("acknowledge", order_number="${body.orders.0.order_number}",
                      order_id="${body.orders.0.order_id}",
                      status="${body.orders.0.status|<absent>}",
                      full_cancellation="${body.orders.0.full_cancellation|<absent>}")],
    },
    "POST /rest/v1/orders/async_create_orders": {
        "note": "Feed-based bulk create. store_code is a required query parameter, not a body "
                "field, and the response is a feed id rather than an order.",
        "name": "no marker -- feed queued, 200 with a feed id",
        "then": [record("created_orders", "${body.orders.0.order_number}"),
                 push("async_order_feed", store="async_feeds",
                      store_code="${query.store_code}",
                      first_order_number="${body.orders.0.order_number}")],
        "validate": {"required": ["query.store_code", "orders[*].order_number"],
                     "non_empty": ["orders"]},
    },
    "POST /rest/v1/orders/async_shipping_details": {
        "note": "The TikTok/Tokopedia asynchronous variant of shipping_details. Reports failure "
                "inside a 200 through success:false.",
        "name": "no marker -- shipping details queued, 200 with success true",
        "then": [push("async_shipping_details", store="shipping_pushes",
                      tracking_number="${body.shipping_details.tracking_number}",
                      status="${body.shipping_details.status}",
                      items="${body.shipping_details.order_items}")],
        "validate": {"required": ["shipping_details.tracking_number"]},
    },
    "POST /rest/v1/orders/push_unsynchronized_order": {
        "note": "Carries order_number and orderNumber side by side -- the Gson DTO emits the raw "
                "Java field name for one of them. Both are recorded so neither can be dropped "
                "silently.",
        "name": "no marker -- failure logged, 200 with success true",
        "then": [push("unsynchronized", order_number="${body.order_number|<absent>}",
                      order_number_camel="${body.orderNumber|<absent>}",
                      event_type="${body.event_type}",
                      error_message="${body.error_message}")],
    },
    "POST /rest/v1/orders/return": {
        "note": "return_order_number is persisted by the caller; omit it from the response and the "
                "return is stranded.",
        "name": "no marker -- return created, 200 with the submitted return_order_number",
        "echo": {"return_order_number": "${body.return_order_number}"},
        "then": [record("returns", "${body.return_order_number}"),
                 push("return_create", store="shipping_pushes",
                      return_order_number="${body.return_order_number}",
                      order_id="${body.id}",
                      items="${body.order_items}")],
        "validate": {"required": ["id", "return_order_number", "order_items[*].line_item_id"],
                     "non_empty": ["order_items"]},
    },
    "POST /rest/v1/orders/shipping_details": {
        "note": "shipping_lable is misspelled in the wire contract. Reproduced, not tidied -- a "
                "mock reading shipping_label would record nothing and still answer 200.",
        "name": "no marker -- shipping details accepted, 200 with success true",
        "then": [push("shipping_details", store="shipping_pushes",
                      order_id="${body.shipping_details.id}",
                      tracking_number="${body.shipping_details.tracking_number}",
                      status="${body.shipping_details.status}",
                      shipping_lable_source="${body.shipping_details.shipping_lable.document_source|<absent>}",
                      update_invoice_only="${body.shipping_details.update_invoice_only|<absent>}")],
        "validate": {"required": ["shipping_details.id", "shipping_details.tracking_number"]},
    },
    "POST /rest/v1/orders/update_cancelled_order_stock": {
        "note": "Splits returning units into sellable and damaged; both counts are recorded so a "
                "putaway test can prove which bucket each unit landed in.",
        "name": "no marker -- putaway accepted, 200 with the adjusted items",
        "then": [push("cancelled_order_stock", order_id="${body.id}",
                      putaway_method="${body.putaway_method}",
                      items="${body.items}")],
    },
    "GET /rest/v1/orders/{id}": {"name": "no marker -- 200, one order"},
    "PUT /rest/v1/orders/{id}": {
        "note": "The only PUT on an order. orderNumber arrives camelCase inside an otherwise "
                "snake_case body, because that DTO carries no @SerializedName.",
        "name": "no marker -- order updated, 200",
        "then": [push("order_update", order_id=ORDER,
                      order_number_camel="${body.order.orderNumber|<absent>}",
                      is_order_item_change="${body.order.isOrderItemChange|<absent>}",
                      order_total="${body.order.order_total}")],
    },
    "POST /rest/v1/orders/{id}/cancel": {
        "note": "Full and partial cancellation share this path; the item list is what separates "
                "them, so it is recorded rather than counted.",
        "name": "no marker -- cancellation accepted, 200",
        "then": [push("cancel", order_id=ORDER,
                      cancellation_reason="${body.cancellation_reason|<absent>}",
                      marketplace_code="${query.marketplace_code|<absent>}",
                      items="${body.order_items}")],
    },
    "POST /rest/v1/orders/{id}/confirm_payment": {
        "note": "constant-only: the path constant exists in ss-connector and selluseller-connector "
                "but no live call site was found, so the verb and body are inferred.",
        "name": "no marker -- payment confirmed, 200",
        "then": [push("confirm_payment", order_id=ORDER,
                      payment_method="${body.payment_method|<absent>}",
                      payment_total="${body.payment_total|<absent>}")],
    },
    "POST /rest/v1/orders/{id}/mark_approve_or_reject": {
        "name": "no marker -- approval recorded, 200",
        "then": [push("approve_or_reject", order_id=ORDER, status="${body.status}",
                      is_mp_unpaid="${body.is_mp_unpaid|<absent>}",
                      line_item_ids="${body.line_item_ids}")],
    },
    "POST /rest/v1/orders/{id}/mark_complete": {
        "note": "Completing an already-complete order is the 409 this endpoint declares, which is "
                "what 9990409 provokes.",
        "name": "no marker -- order completed, 200",
        "then": [push("mark_complete", order_id=ORDER,
                      marketplace_code="${body.marketplace_code|<absent>}",
                      line_item_ids="${body.line_item_ids}")],
    },
    "GET /rest/v1/orders/{id}/order_items": {"name": "no marker -- 200, the order's line items"},
    "POST /rest/v1/orders/{id}/revert_seller_cancellation": {
        "note": "Full and partial reverts both post here; line_items_status is the discriminator.",
        "name": "no marker -- cancellation reverted, 200",
        "then": [push("revert_cancellation", order_id=ORDER,
                      line_items_status="${body.line_items_status}")],
    },
    "POST /rest/v1/orders/{id}/serial_number_validation_response": {
        "note": "Reports WMS serial validation back to OMS, and answers 200 whether or not any "
                "serial failed -- failed_serial_numbers is where the failure lives.",
        "name": "no marker -- serial validation recorded, 200 with success true",
        "then": [push("serial_validation", order_id=ORDER,
                      shipment_number="${body.shipment_number}",
                      items="${body.order_items}")],
    },
    "POST /rest/v1/orders/{id}/update_delta_order": {
        "note": "Line-item delta. Like PUT /orders/{id} it carries camelCase orderNumber and "
                "isOrderItemChange inside a snake_case body.",
        "name": "no marker -- delta applied, 200",
        "then": [push("update_delta_order", order_id=ORDER,
                      order_number_camel="${body.order.orderNumber|<absent>}",
                      items="${body.order.order_items}")],
    },
    "POST /rest/v1/orders/{id}/update_status": {
        "note": "new_status is a required QUERY parameter, not a body field -- the body carries "
                "the reason, the items and the withhold object.",
        "name": "no marker -- status advanced, 200",
        "then": [push("update_status", order_id=ORDER, new_status="${query.new_status}",
                      wms_status="${body.wms_status|<absent>}",
                      tracking_number="${body.tracking_number|<absent>}",
                      return_type="${body.return_type|<absent>}")],
        "validate": {"required": ["query.new_status"]},
    },

    # -- Inventory -------------------------------------------------------------------------------
    "GET /rest/v1/inventory_products": {
        "note": "404 here means the page is past the end, not that the endpoint is broken -- it is "
                "how the paging loops terminate. 9990404 provokes exactly that.",
        "name": "no marker -- 200, one page of inventory products",
    },
    "POST /rest/v1/inventory_products": {
        "name": "no marker -- inventory product created, 200 with the submitted inventory_sku",
        "echo": {"inventory_sku": "${body.inventory_sku}"},
        "then": [record("created_inventory_products", "${body.inventory_sku}"),
                 push("inventory_create", store="stock_pushes",
                      inventory_sku="${body.inventory_sku}",
                      total_stock="${body.total_stock}",
                      sellable="${body.sellable}")],
        "validate": {"required": ["inventory_sku"]},
    },
    "POST /rest/v1/inventory_products/async_create_inventory_products": {
        "name": "no marker -- creation feed queued, 200 with a feed id",
        "then": [record("created_inventory_products", "${body.inventory_products.0.inventory_sku}"),
                 push("async_inventory_create", store="async_feeds",
                      first_inventory_sku="${body.inventory_products.0.inventory_sku}")],
        "validate": {"required": ["inventory_products[*].inventory_sku"],
                     "non_empty": ["inventory_products"]},
    },
    "PATCH /rest/v1/inventory_products/async_update_stocks": {
        "note": "PATCH, not POST. The v1 stock envelope is product.skus.sku[] -- three levels "
                "before the first seller_sku.",
        "name": "no marker -- stock feed queued, 200 with a feed id",
        "then": [push("async_update_stocks_v1", store="stock_pushes",
                      first_seller_sku="${body.product.skus.sku.0.seller_sku}",
                      skus="${body.product.skus.sku}")],
    },
    "POST /rest/v1/inventory_products/bulk_update_product": {
        "name": "no marker -- products updated, 200 with success true",
        "then": [push("bulk_update_product", store="stock_pushes",
                      payload_type="${body.payload_type}",
                      first_inventory_sku="${body.payload.0.inventory_sku}")],
    },
    "POST /rest/v1/inventory_products/sync_failed_status": {
        "note": "The one inventory write that reports marketplace-side failure back to OMS rather "
                "than pushing stock.",
        "name": "no marker -- failures recorded, 200",
        "then": [push("sync_failed_status", store="stock_pushes",
                      store_code="${body.store_code}", data="${body.data}")],
    },
    "PATCH /rest/v1/inventory_products/update_delta_stocks": {
        "note": "eventParametersDTO arrives camelCase inside a snake_case body, and its "
                "warehouseCode is what routes the movement.",
        "name": "no marker -- delta applied, 200 with an empty errors list",
        "then": [push("update_delta_stocks_v1", store="stock_pushes",
                      warehouse_code="${body.eventParametersDTO.warehouseCode|<absent>}",
                      seller_code="${body.eventParametersDTO.sellerCode|<absent>}",
                      skus="${body.product.skus.sku}")],
    },
    "PATCH /rest/v1/inventory_products/update_stocks": {
        "note": "PATCH and POST both exist on this path and are different operations. Keeping both "
                "is the point: a client sending the wrong verb must not be quietly answered.",
        "name": "no marker -- absolute stock applied (PATCH), 200 with status true",
        "then": [push("update_stocks_v1_patch", store="stock_pushes",
                      warehouse_code="${body.eventParametersDTO.warehouseCode|<absent>}",
                      skus="${body.product.skus.sku}")],
    },
    "POST /rest/v1/inventory_products/update_stocks": {
        "note": "The POST twin of the PATCH above, used only by wms-connector.",
        "name": "no marker -- absolute stock applied (POST), 200 with status true",
        "then": [push("update_stocks_v1_post", store="stock_pushes",
                      skus="${body.product.skus.sku}")],
    },
    "GET /rest/v1/inventory_products/{id}": {"name": "no marker -- 200, one inventory product"},
    "PATCH /rest/v1/inventory_products/{id}": {
        "note": "PATCH is the update verb on an inventory product, not PUT.",
        "name": "no marker -- inventory product updated, 200",
        "then": [push("inventory_update", store="stock_pushes", id=ORDER,
                      inventory_sku="${body.inventory_product.inventory_sku}",
                      total_stock="${body.inventory_product.total_stock}")],
    },
    "POST /rest/v1/inventory_products/{inventory_product_id}/stock_locations": {
        "note": "constant-only, and the one operation whose only declared success is 201.",
        "name": "no marker -- stock location created, 201",
        "then": [push("stock_location_create", store="stock_pushes",
                      inventory_product_id="${path.inventory_product_id}",
                      location_id="${body.stock_location.location_id}",
                      quantity="${body.stock_location.quantity}")],
    },
    "PATCH /rest/v1/inventory_products/{inventory_product_id}/stock_locations/{id}": {
        "note": "constant-only. Two path parameters, and version is an optimistic lock -- the 409 "
                "this endpoint declares is a stale version, which 9990409 provokes.",
        "name": "no marker -- stock location updated, 200",
        "then": [push("stock_location_update", store="stock_pushes",
                      inventory_product_id="${path.inventory_product_id}", id=ORDER,
                      version="${body.stock_location.version}",
                      quantity="${body.stock_location.quantity}")],
    },
    "GET /rest/v1/seller_marketplaces/get_all_stocks": {
        "note": "limit, offset and store_code are all required query parameters here, unlike the "
                "other paged reads where paging is optional.",
        "name": "no marker -- 200, one page of marketplace listings and their stock",
        "validate": {"required": ["query.limit", "query.offset", "query.store_code"]},
    },
    "PATCH /rest/v2/inventory_products/update_stocks": {
        "note": "The v2 envelope. SkuV2DTO carries @JsonProperty(\"sellerSku\") AND "
                "@SerializedName(\"seller_sku\"); the body is Gson-serialized, so the wire key is "
                "seller_sku. A mock keyed on sellerSku would never match.",
        "name": "no marker -- v2 absolute stock accepted, 200 with a feed id",
        "then": [push("update_stocks_v2", store="stock_pushes",
                      exclude_buffer_stock="${body.exclude_buffer_stock}",
                      first_seller_sku="${body.product.skus.sku.0.seller_sku}",
                      first_seller_sku_camel="${body.product.skus.sku.0.sellerSku|<absent>}",
                      skus="${body.product.skus.sku}")],
        "validate": {"required": ["product.skus.sku[*].seller_sku"],
                     "non_empty": ["product.skus.sku"]},
    },
    "PATCH /rest/v2/inventory_products/async_update_stocks": {
        "name": "no marker -- v2 stock feed queued, 200 with a feed id",
        "then": [push("async_update_stocks_v2", store="stock_pushes",
                      first_seller_sku="${body.product.skus.sku.0.seller_sku}",
                      skus="${body.product.skus.sku}")],
        "validate": {"required": ["product.skus.sku[*].seller_sku"]},
    },
    "PATCH /rest/v2/inventory_products/update_delta_stocks": {
        "name": "no marker -- v2 delta accepted, 200 with a feed id",
        "then": [push("update_delta_stocks_v2", store="stock_pushes",
                      first_seller_sku="${body.product.skus.sku.0.seller_sku}",
                      skus="${body.product.skus.sku}")],
        "validate": {"required": ["product.skus.sku[*].seller_sku"]},
    },

    # -- Catalogue -------------------------------------------------------------------------------
    "GET /rest/v1/catalogues": {
        "note": "store_code and sku are both required; this is the lookup every listing write "
                "checks against first.",
        "name": "no marker -- 200, the catalogue listing for that store and sku",
        "validate": {"required": ["query.store_code", "query.sku"]},
    },
    "POST /rest/v1/catalogues": {
        "name": "no marker -- listing created, 200 with the submitted sku",
        "echo": {"sku": "${body.product.sku}", "store_code": "${body.product.store_code}"},
        "then": [record("created_catalogues", "${body.product.sku}"),
                 push("catalogue_create", store="catalogue_pushes",
                      sku="${body.product.sku}", store_code="${body.store_code}",
                      price="${body.product.price}",
                      selling_price="${body.product.selling_price}")],
        "validate": {"required": ["store_code", "product.sku"]},
    },
    "POST /rest/v1/catalogues/async_create_catalogue": {
        "name": "no marker -- catalogue feed queued, 200 with a feed id",
        "then": [push("async_catalogue", store="async_feeds",
                      store_code="${query.store_code}",
                      first_sku="${body.products.0.sku}")],
        "validate": {"required": ["query.store_code"], "non_empty": ["products"]},
    },
    "POST /rest/v1/catalogues/update_price": {
        "note": "Price and the sale window travel together; a sale_start_date without an end is "
                "the shape that has caused trouble, so both are recorded.",
        "name": "no marker -- price updated, 200 with the submitted sku",
        "echo": {"sku": "${body.sku}"},
        "then": [push("catalogue_update_price", store="catalogue_pushes",
                      sku="${body.sku}", store_code="${body.store_code}",
                      price="${body.price}", selling_price="${body.selling_price}",
                      sale_start_date="${body.sale_start_date|<absent>}",
                      sale_end_date="${body.sale_end_date|<absent>}")],
        "validate": {"required": ["store_code", "sku"]},
    },
    "PATCH /rest/v1/catalogues/{sku}": {
        "name": "no marker -- listing updated, 200",
        "then": [push("catalogue_update", store="catalogue_pushes",
                      sku_path="${path.sku}", sku_body="${body.product.sku}",
                      state="${body.product.state|<absent>}")],
    },
    "PATCH /rest/v1/catalogues/{sku}/update_status": {
        "note": "OipPromotionsImpl sends the literal string {sku} in the path without substituting "
                "it. The template still matches, so the store records sku_path as {sku} and the "
                "bug is visible rather than absorbed.",
        "name": "no marker -- listing status changed, 200",
        "then": [push("catalogue_update_status", store="catalogue_pushes",
                      sku_path="${path.sku}", sku_body="${body.sku|<absent>}",
                      status="${body.status}", reason="${body.reason|<absent>}")],
    },

    # -- Catalogue Taxonomy ----------------------------------------------------------------------
    "POST /rest/v1/brands": {
        "name": "no marker -- brand created, 200 with the submitted code",
        "echo": {"code": "${body.brand.code}"},
        "then": [push("brand_create", store="taxonomy_pushes",
                      code="${body.brand.code}", name="${body.brand.name}",
                      store_code="${query.store_code}")],
        "validate": {"required": ["query.store_code", "brand.code", "brand.name"]},
    },
    "POST /rest/v1/brands/bulk_create": {
        "note": "storeCode camelCase in the body here, store_code snake_case in the query and in "
                "every sibling endpoint. Both are recorded so the difference stays visible.",
        "name": "no marker -- brands created, 200 with created_count",
        "then": [push("brand_bulk_create", store="taxonomy_pushes",
                      store_code_camel="${body.storeCode|<absent>}",
                      store_code_query="${query.store_code}",
                      first_code="${body.brands.0.code}")],
        "validate": {"required": ["query.store_code"], "non_empty": ["brands"]},
    },
    "PUT /rest/v1/brands/{id}": {
        "note": "constant-only, and one of three PUTs in the taxonomy -- everything else updates "
                "with PATCH or a named sub-resource.",
        "name": "no marker -- brand updated, 200",
        "then": [push("brand_update", store="taxonomy_pushes", id=ORDER,
                      code="${body.brand.code}")],
    },
    "POST /rest/v1/bulk_categories": {
        "note": "One call pushes a parent and its nested children; children ride inside "
                "category.children rather than arriving as separate calls.",
        "name": "no marker -- category tree created, 200 with created_count",
        "then": [push("bulk_categories", store="taxonomy_pushes",
                      code="${body.category.code}", name="${body.category.name}",
                      children="${body.category.children}",
                      store_code="${query.store_code}")],
        "validate": {"required": ["query.store_code", "category.code"]},
    },
    "POST /rest/v1/bulk_categories_attributes": {
        "name": "no marker -- category attributes created, 200 with created_count",
        "then": [push("bulk_category_attributes", store="taxonomy_pushes",
                      category_code="${body.category_code}",
                      marketplace_code="${body.marketplace_code}",
                      attributes="${body.category_attributes}")],
        "validate": {"required": ["query.store_code", "query.marketplace_code",
                                  "category_code"]},
    },
    "GET /rest/v1/categories": {
        "note": "constant-only.",
        "name": "no marker -- 200, the marketplace's categories",
        "validate": {"required": ["query.marketplace_code"]},
    },
    "POST /rest/v1/categories": {
        "note": "The single-category create is entirely camelCase -- storeCode, marketplaceCode, "
                "parentCode -- while its bulk sibling is snake_case.",
        "name": "no marker -- category created, 200 with the submitted code",
        "echo": {"code": "${body.category.code}"},
        "then": [push("category_create", store="taxonomy_pushes",
                      code="${body.category.code}",
                      store_code_camel="${body.storeCode|<absent>}",
                      marketplace_code_camel="${body.category.marketplaceCode|<absent>}",
                      parent_code_camel="${body.category.parentCode|<absent>}")],
        "validate": {"required": ["category.code", "category.name"]},
    },
    "GET /rest/v1/categories/{category_code}/category_attributes": {
        "note": "constant-only.",
        "name": "no marker -- 200, the category's attributes",
        "validate": {"required": ["query.marketplace_code"]},
    },
    "PUT /rest/v1/categories/{id}": {
        "note": "constant-only.",
        "name": "no marker -- category updated, 200",
        "then": [push("category_update", store="taxonomy_pushes", id=ORDER,
                      code="${body.category.code}")],
    },
    "POST /rest/v1/category_attributes": {
        "name": "no marker -- attributes created, 200",
        "then": [push("category_attributes_create", store="taxonomy_pushes",
                      category_code="${body.category_code}",
                      marketplace_code="${body.marketplace_code}",
                      attributes="${body.category_attributes}")],
        "validate": {"required": ["category_code", "marketplace_code"]},
    },
    "PUT /rest/v1/category_attributes/{id}": {
        "note": "constant-only, and camelCase throughout where its POST sibling is snake_case: "
                "fieldCode, dataType, ssFieldCode.",
        "name": "no marker -- attribute updated, 200",
        "then": [push("category_attribute_update", store="taxonomy_pushes", id=ORDER,
                      field_code_camel="${body.category_attributes.fieldCode|<absent>}",
                      data_type_camel="${body.category_attributes.dataType|<absent>}")],
    },

    # -- Stores ----------------------------------------------------------------------------------
    "GET /rest/v1/stores": {"name": "no marker -- 200, one page of stores"},
    "GET /rest/v1/stores/{id}": {"note": "constant-only.", "name": "no marker -- 200, one store"},
    "PATCH /rest/v1/stores/{id}": {
        "note": "The sync stamps land here. order_sync and inventory_sync are timestamps the "
                "connectors write back after a successful pull, so a stale value is a real symptom.",
        "name": "no marker -- store meta data stamped, 200",
        "then": [push("store_meta", store="store_pushes", id=ORDER,
                      ss_code="${body.store.ss_code}",
                      order_sync="${body.store.order_sync|<absent>}",
                      inventory_sync="${body.store.inventory_sync|<absent>}")],
    },
    "GET /rest/v1/stores/{id}/credentials": {
        "note": "constant-only. Answers marketplace credentials, which is why the call log redacts "
                "authorization headers but this response body is not redacted -- it is mock data.",
        "name": "no marker -- 200, the store's marketplace credentials",
    },

    # -- Warehouses ------------------------------------------------------------------------------
    "GET /rest/v1/warehouses": {"name": "no marker -- 200, the seller's warehouses"},
    "GET /rest/v1/warehouses/{id}": {"note": "constant-only.",
                                     "name": "no marker -- 200, one warehouse"},
    "GET /rest/v1/warehouses/{warehouse_id}/stock_locations": {
        "note": "constant-only.",
        "name": "no marker -- 200, the warehouse's stock locations",
    },

    # -- Shipping --------------------------------------------------------------------------------
    "GET /rest/v1/shipping_methods": {"name": "no marker -- 200, the configured carriers"},
    "POST /rest/v1/shipping_methods": {
        "note": "shipping_type, marketplace_code and country_name are required QUERY parameters "
                "while the carrier itself is the body -- an unusual split, and one a mock reading "
                "only the body would not catch.",
        "name": "no marker -- carrier created, 200 with the submitted name",
        "echo": {"name": "${body.name}"},
        "then": [push("shipping_method_create", store="shipping_method_pushes",
                      name="${body.name}",
                      logistics_partner_code="${body.logistics_partner_code}",
                      shipping_type="${query.shipping_type}",
                      marketplace_code="${query.marketplace_code}",
                      country_name="${query.country_name}")],
        "validate": {"required": ["query.shipping_type", "query.marketplace_code",
                                  "query.country_name", "name"]},
    },
    "GET /rest/v1/shipping_methods/{id}": {
        "note": "The legacy updateShippingCarrier stub issues GET here through "
                "restTemplate.getForEntity and never substitutes {id}, so the literal {id} reaches "
                "the wire. Mocked as the GET it actually is, not the update its constant is named "
                "after.",
        "name": "no marker -- 200, one shipping method",
    },
    "GET /rest/v1/smp_shipping_methods": {
        "note": "constant-only.",
        "name": "no marker -- 200, the seller-marketplace shipping mappings",
    },
    "POST /rest/v1/smp_shipping_methods": {
        "note": "Maps a created carrier onto the seller-marketplace. shipping_method_id in the "
                "body is the id the create above returned, so the two calls are ordered.",
        "name": "no marker -- mapping created, 200",
        "then": [push("smp_shipping_method_create", store="shipping_method_pushes",
                      shipping_method_id="${body.smp_shipping_method.shipping_method_id}",
                      marketplace_shipping_code="${body.smp_shipping_method.marketplace_shipping_code}",
                      ss_code="${query.ss_code}")],
        "validate": {"required": ["query.shipping_method", "query.logistics_partner_code",
                                  "query.ss_code"]},
    },
    "PUT /rest/v1/smp_shipping_methods/{id}": {
        "note": "constant-only.",
        "name": "no marker -- mapping updated, 200",
        "then": [push("smp_shipping_method_update", store="shipping_method_pushes", id=ORDER,
                      marketplace_shipping_code="${body.smp_shipping_method.marketplace_shipping_code}")],
    },

    # -- Misc ------------------------------------------------------------------------------------
    "POST /rest/v1/manifest/upload": {
        "note": "The manifest carries the document and the orders it covers in one body; "
                "order_numbers comes back as the acknowledgement.",
        "name": "no marker -- manifest accepted, 200 with the order numbers it covered",
        "then": [push("manifest_upload", store="shipping_pushes",
                      number="${body.number}", status="${body.status}",
                      orders="${body.orders}")],
        "validate": {"required": ["number"], "non_empty": ["orders"]},
    },
    "POST /rest/v1/payouts": {
        "name": "no marker -- payout created, 200 with the submitted payment_id",
        "echo": {"payment_id": "${body.payout.payment_id}"},
        "then": [push("payout", store="misc_pushes",
                      payment_id="${body.payout.payment_id}",
                      settlement_amount="${body.payout.settlement_amount}",
                      currency="${body.payout.currency}",
                      store_code="${body.payout.store_code}")],
        "validate": {"required": ["payout.payment_id", "payout.store_code"]},
    },
    "POST /rest/v1/promotions/update_failure_reasons": {
        "note": "constant-only.",
        "name": "no marker -- failure reasons recorded, 200",
        "then": [push("promotion_failures", store="misc_pushes",
                      store_code="${body.store_code}",
                      promotions="${body.promotions}")],
    },
    "POST /rest/v1/reports": {
        "note": "Hands OMS a URL rather than the report; the file itself never crosses this API.",
        "name": "no marker -- report url accepted, 200",
        "echo": {"url": "${body.url}"},
        "then": [push("report", store="misc_pushes",
                      report_history_id="${body.report_history_id}",
                      url="${body.url}", store_code="${body.store_code}")],
        "validate": {"required": ["url", "report_history_id"]},
    },
    "POST /rest/v1/transactions/async_create_transactions": {
        "name": "no marker -- transactions queued, 200",
        "then": [push("transactions", store="misc_pushes",
                      store_code="${body.store_code}",
                      first_transaction_number="${body.transactions.0.transaction_number}",
                      count="${body.transactions}")],
        "validate": {"required": ["store_code"], "non_empty": ["transactions"]},
    },
}


# -------------------------------------------------------------------------------------- generation

def query_names(op):
    """Query parameters a marker could plausibly be written into -- identifiers, not paging."""
    skip = {"limit", "offset", "sort_by", "sort_order", "sort_direction", "version",
            "extra_details", "filter_type", "updated_before", "updated_after", "created_after"}
    return [p["name"] for p in (op.get("parameters") or [])
            if p.get("in") == "query" and p["name"] not in skip]


def build_route(path, method, op, entry):
    family = error_family(op)
    status, body = success(op)
    queries = query_names(op)
    declared = set(op.get("responses") or {})
    rules = []

    for marker, word, code in UNIVERSAL + DECLARED_ONLY:
        if (marker, word, code) in DECLARED_ONLY and str(code) not in declared:
            continue
        example = json_example((op.get("responses") or {}).get(str(code)))
        why = "mock marker %s/%s: %s" % (marker, word, TITLES[code].lower())
        rules.append({
            "name": "%s / %s -- %d" % (marker, word, code),
            "when": marker_when([marker, word], queries),
            "respond": {"status": code,
                        "body": copy.deepcopy(example) if example is not None
                                else canonical_error(code, family, why)},
        })

    in_band = bizerr_body(body)
    if in_band is not None:
        rules.append({
            "_comment": "The 200 that is not a success. A test asserting only on the HTTP status "
                        "passes here wrongly, which is the failure this marker exists to catch.",
            "name": "%s / BIZERR -- %d with an in-band failure" % (BIZERR, status),
            "when": marker_when([BIZERR, "BIZERR"], queries),
            "respond": {"status": status, "body": in_band},
        })

    rule_validate = entry.get("validate")
    if rule_validate:
        code, failure = validation_response(op, family)
        rules.append({
            "_comment": "Answers only when something is actually wrong; a clean request falls "
                        "through to the fallback below.",
            "name": "validation failed -- %d" % code,
            "validate": rule_validate,
            "respond": {"status": code, "body": failure},
        })

    route = {"path": path, "method": method.upper(), "rules": rules,
             "name": entry.get("name", "no marker -- %d, the document's own example" % status),
             "respond": {"status": status, "body": echo(body, entry.get("echo"))}}
    if entry.get("note"):
        route = dict([("_comment", entry["note"])] + list(route.items()))
    if entry.get("then"):
        route["then"] = entry["then"]
    return route


def main():
    with open(SPEC) as handle:
        spec = json.load(handle)

    routes, unknown = [], []
    for path, operations in spec["paths"].items():
        for method, op in operations.items():
            if method not in METHODS:
                continue
            key = "%s %s" % (method.upper(), path)
            if key not in TABLE:
                unknown.append(key)
            routes.append(build_route(path, method, op, TABLE.get(key, {})))

    if unknown:
        print("  ! %d operation(s) absent from TABLE, generated with markers only:" % len(unknown))
        for key in unknown:
            print("      %s" % key)

    config = {
        "name": "Anchanto OMS (SelluSeller)",
        "port": 23001,
        "_comment": "GENERATED by anchanto-oms/build-config.py from "
                    "anchanto-oms-swagger.json -- edit the generator's TABLE, not this file. "
                    "74 operations, each with the document's own success example as the fallback, "
                    "steering markers above it, and stores recording what the mock accepted.",
        "spec": "anchanto-oms-swagger.json",
        "state_dir": "mock-data",
        "log_file": "api-calls.har.json",
        "log_format": "har",
        "test_results_dir": "test-results",
        "unmatched_status": 404,
        "_comment_suites": "The runner drives the mock alone -- no app, no database -- so a red "
                           "row is the mock or the spec and never an integration.",
        "test_suites": [
            {"id": "smoke",
             "name": "anchanto-oms smoke",
             "description": "All 74 operations, every marker, the store write contracts and the "
                            "serialization traps.",
             "estimate": "~10s",
             "command": ["python3", "anchanto-oms/suite-smoke.py"],
             "options": [{"flag": "--keep-state",
                          "label": "Keep state -- do not empty the stores or the call log first"}]},
        ],
        "stores": {name: {"file": name + ".json",
                          "type": "set" if name.startswith(("created_", "returns")) else "list",
                          "_comment": why}
                   for name, why in STORES.items()},
        "routes": routes,
    }

    with open(OUT, "w") as handle:
        json.dump(config, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    print("wrote %s -- %d routes, %d stores, %d bytes"
          % (os.path.relpath(OUT, PACKAGE), len(routes), len(STORES), os.path.getsize(OUT)))


if __name__ == "__main__":
    main()
