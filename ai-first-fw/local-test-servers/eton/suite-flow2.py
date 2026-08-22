#!/usr/bin/env python3
"""createOrder flow 2: Anchanto OMS publishes an order, JPluger creates it on Eton WMS.

Twenty-one cases fired at the JPluger controller and judged against the Eton mock's call log, the
`orders` table and the RabbitMQ queue JPluger reports unsynchronized orders on. Nothing is asserted
against JPluger's own response beyond the publish: the transport is asynchronous, so a 200 there
means published and never succeeded.

    python3 eton/suite-flow2.py                 all 21 cases, ~5 min
    python3 eton/suite-flow2.py --fast          skips N10, the one retry case
    python3 eton/suite-flow2.py N1 K1 K4        only the cases named
    python3 eton/suite-flow2.py --judge eton/test-results/flow2/run-…

Requires the app on ${APP}, the mock on ${MOCK} (`python3 mock.py eton`), and the
seed in the database the app itself reads. Preflight names whichever is missing.

The engine, the check vocabulary and the runner contract: `suite/` and
`TESTING.md`. What the mock answers and why: `eton/README.md`.
"""

import os
import sys

# The engine is a sibling package, and a suite file is started from wherever the caller happens to
# be -- the /test page starts it from the mock's own folder.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from suite import (Blocked, Calls, Case, ControllerStatus, Custom, DELETE, Group, Marker, MySql,
                   PostJson, QueueDelta, Queues, Rows, Sql, Status, Suite, merge, key_from)
from suite import AppResponds, DatabaseResponds, MockResponds, QueuesRespond, SeedRows

PACKAGE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ------------------------------------------------------------------------------------ settings

# Every one of these is overridden by an environment variable of the same name.
ENV = {
    "APP": "https://localhost",
    "MOCK": "http://127.0.0.1:23101",
    "RABBIT": "http://127.0.0.1:15672",
    "RABBIT_AUTH": "guest:guest",
    # Must match the running app's spring.datasource.url. application-local.properties says
    # ss_wms_integration, but an IDE run configuration can override it -- check the app's VM
    # options before believing this default.
    "DB_NAME": "wms_integrations_test",
    # recoverMethod compares event_name against "order_creation", in EtonWmsService and again in
    # the older wms-integration EtonOrders. No Java anywhere produces "order_created", yet that is
    # what the Postman fixtures send, so retry exhaustion reports nothing. Override to reproduce
    # that gap:  EVENT_NAME=order_created python3 eton/suite-flow2.py N10
    "EVENT_NAME": "order_creation",
    "CORE_JSON": os.path.join(PACKAGE, "core.json"),
}

RECOVER_EVENT_NAME = "order_creation"


def event_name_of(run):
    """The event_name a run was fired with, read from either shape of `meta.json`.

    Runs made before this engine existed recorded it at the top level; this one records it under
    `settings`. Both are still judgeable.
    """
    settings = run.meta.get("settings") or {}
    return settings.get("EVENT_NAME") or run.meta.get("event_name") or ""


BLOCKED_ON_RECOVER = Blocked(
    when=lambda run: event_name_of(run) != RECOVER_EVENT_NAME,
    reason=lambda run: ("recoverMethod compares event_name against '%s'; this run sent '%s', so "
                        "retry exhaustion reports nothing"
                        % (RECOVER_EVENT_NAME, event_name_of(run))))


def prepare(payload, env):
    """Applies the chosen event_name to the payload just before it is sent."""
    return merge(payload, {"event_parameters": {"event_name": env["EVENT_NAME"]}})


# ------------------------------------------------------------------------------------ payloads

# One order every case starts from. A case states only what it changes, so the difference between
# two cases is the whole of what distinguishes them.
ORDER = {
    "event_parameters": {
        "seller_code": "SSIN10000007004",
        "seller_id": "7004",
        "store_id": "16643",
        "warehouse_code": "eton",
        "store_code": "SS0000016643",
        "store_name": "Shopee Store",
        "zone_id": 1,
        "event_name": "order_creation",
        "marketplace_code": "shopee_vn",
    },
    "data": {
        "order_id": "92000001",
        "order_number": "SO-ETON-CO-N1",
        "market_place_order_number": "MP-428839066042874",
        "warehouse_code": "eton",
        "marketplace_code": "shopee_vn",
        "store_code": "SS0000016643",
        "seller_currency": "VND",
        "customer_first_name": "Nguyen",
        "customer_last_name": "Van A",
        "customer_email": "customer@example.com",
        "payment_method": "COD",
        "created_at": "2026-08-13T10:24:33.000Z",
        "shipping_address": {
            "first_name": "Nguyen", "last_name": "Van A", "address1": "123 Le Loi Street",
            "address2": "District 1", "city": "Ho Chi Minh City", "state_name": "Ho Chi Minh",
            "post_code": "700000", "country_code": "VN", "phone": "+84901234567",
        },
        "billing_address": {
            "first_name": "Nguyen", "last_name": "Van A", "address1": "123 Le Loi Street",
            "address2": "District 1", "city": "Ho Chi Minh City", "state_name": "Ho Chi Minh",
            "post_code": "700000", "country_code": "VN", "phone": "+84901234567",
        },
        "shipping_method": {"shipping_type": "Standard"},
        "order_items": [],
    },
}


def item(item_id, sku="SKU-ETON-001", price="105000.0", paid="92850.0", quantity=1,
         marketplace_sku="1025377_CB3", **extra):
    """One order line.

    `sku` is the inventory SKU, which is what reaches Eton as the line's SKU. `marketplace_sku` is
    the channel's own identifier, which is a different value and is what the Shopee adjustments
    block is joined on.
    """
    line = {"order_item_id": item_id, "name": "Combo Tra Oolong Cau Tre", "sku": marketplace_sku,
            "inventory_sku": sku, "item_price": price, "paid_price": paid, "quantity": quantity}
    line.update(extra)
    return line


def line_pricing(line_item_id, original, paid):
    """The per-line pricing carrier Lazada and TikTok send, in `order_items[].line_item_details`."""
    return [{"line_item_id": line_item_id, "item_original_price": original,
             "item_paid_price": paid, "seller_voucher_amount": 5000.0, "voucher_platform": "7000.0",
             "tax_amount": "1000.0", "shipping_fee_original": "20000.0",
             "shipping_fee_seller_discount": "3000.0", "shipping_fee_platform_discount": "12000.0",
             "platform_discount": "4000.0", "seller_discount": "2000.0"}]


# The order-level pricing carrier Shopee sends instead, in `data.order_adjustment`.
SHOPEE_PRICING = {
    "id": 90001, "marketplace_discount": 9000, "seller_discount": 3150, "marketplace_wallet": 0,
    "order_id": 90001,
    "adjustments": {
        "order_original_price": 105000, "seller_discount": 3150, "voucher_from_seller": 0,
        "shopee_discount": 0, "voucher_from_shopee": 9000, "coins": 0,
        "actual_shipping_fee": 16500, "seller_shipping_discount": 1500,
        "shopee_shipping_rebate": 15000, "service_fee": 8602, "buyer_total_amount": 92850,
        "escrow_tax": 0,
        "items": [{"item_sku": "", "model_sku": "1025377_CB3", "quantity_purchased": 1,
                   "original_price": 105000, "selling_price": 92850.0, "discounted_price": 92850.0,
                   "seller_discount": 3150, "discount_from_voucher_shopee": 9000,
                   "discount_from_voucher_seller": 0.0, "discount_from_coin": 0.0,
                   "is_main_item": True}],
    },
}

# The same block for a line of 2 units. Shopee states every adjustments amount per unit, so the
# order level is twice the entry and the pushed line total has to be too.
SHOPEE_PRICING_QTY2 = merge(SHOPEE_PRICING, {
    "adjustments": {
        "order_original_price": 210000, "buyer_total_amount": 185700,
        "items": [{"item_sku": "", "model_sku": "1025377_CB3", "quantity_purchased": 2,
                   "original_price": 105000, "selling_price": 92850.0, "discounted_price": 92850.0,
                   "seller_discount": 3150, "discount_from_voucher_shopee": 9000,
                   "discount_from_voucher_seller": 0.0, "discount_from_coin": 0.0,
                   "is_main_item": True}],
    },
})

# A kit of two components. Eton has no concept of a kit, so JPluger explodes it into one line per
# component and multiplies each component quantity by the kit quantity before building the payload.
KIT = [{"inventory_product_sku": "1025377-A", "quantity": 3, "price": 70000.0},
       {"inventory_product_sku": "1025377-B", "quantity": 1, "price": 35000.0}]


def order(order_id, number, items, marketplace=None, pricing=None, extra=None):
    """The payload for one case: the base order with its identity, its lines and its channel.

    `extra` is a fragment applied last, which is how a case removes a key the base order carries.
    """
    data = {"order_id": order_id, "order_number": number, "order_items": items}
    payload = {"data": data}
    if marketplace:
        # The channel is stated twice because both readers exist: the event parameters route the
        # message, and data.marketplace_code is what EtonPricingMapper resolves the carrier from.
        data["marketplace_code"] = marketplace
        payload["event_parameters"] = {"marketplace_code": marketplace}
    if pricing:
        data["order_adjustment"] = pricing
    merged = merge(ORDER, payload)
    # Applied against the merged order, not against `payload`: DELETE removes a key from the base
    # it is merged into, and `payload` never carries the base's keys in the first place.
    return merge(merged, extra) if extra else merged


def case(cid, name, order_id, number, items, expect, marketplace=None, pricing=None,
         shape="normal", wait=7, extra=None, **rest):
    """One case, keyed by the identifiers its evidence is recoverable from.

    The Eton calls carry the order id -- creation echoes it back as the sale order code, so the
    pricing push that follows is addressed by the same value -- and the `orders` rows carry the
    order number.
    """
    return Case(cid, name, payload=order(order_id, number, items, marketplace, pricing, extra),
                key=order_id, row_key=number, shape=shape, wait=wait, expect=expect,
                detail={"order_id": order_id, "order_number": number}, **rest)


# ------------------------------------------------------------------- what reached the wire

def pricing_payload(evidence):
    """The body of the first pricing push, or None when the case pushed nothing."""
    calls = evidence.calls.get("pricing", [])
    if not calls:
        return None
    body = calls[0].request_body
    return body if isinstance(body, dict) else None


def one_key_per_property(case, evidence):
    """Every pricing property named once, in Eton's PascalCase and nothing else.

    Jackson emits a field and its getter as two properties whenever their implicit names differ, so
    a DTO whose fields are named for the wire sends every value twice — once as `Items` and once as
    `items`. Eton accepted that only because ASP.NET model binding is case-insensitive and takes the
    last value, and Jackson contracts no property order. Counting the keys is what catches it.
    """
    want = case.expect.get("pricing_keys")
    body = pricing_payload(evidence)
    if want is None or body is None:
        return None
    doubled = sorted(key for key in body if key[:1].islower())
    return ("%d keys, none doubled" % want,
            "%d keys, doubled: %s" % (len(body), ", ".join(doubled) or "none"),
            len(body) == want and not doubled)


def item_base_prices(case, evidence):
    """`Items[].BasePrice` as sent, in order — the line total Eton reads, not a unit price."""
    want = case.expect.get("item_base_prices")
    body = pricing_payload(evidence)
    if want is None or body is None:
        return None
    got = [line.get("BasePrice") for line in (body.get("Items") or [])]
    return want, got, got == want


# -------------------------------------------------------------------------------------- cases

CASES = [
    case("N1", "N1. Plain item - happy path, no pricing carrier",
         "92000001", "SO-ETON-CO-N1", [item(9200101)],
         expect={"create_calls": 1, "create_status": 200, "create_mark": "New",
                 "pricing_calls": 0, "pricing_status": None, "db_rows": 1, "unsync": False},
         note="shopee_vn normally carries pricing. This is the case where it does not, so it "
              "proves buildShopeePayload returning empty skips the push rather than sending an "
              "empty or zeroed payload.",
         given="A shopee_vn order with one plain item and no data.order_adjustment block.",
         then=["Eton accepts the create and answers Status 'New'.",
               "One row is written to orders.",
               "No price detail is pushed — price_details.json must not grow."]),

    case("N2", "N2. Shopee - order_adjustment pricing",
         "92000002", "SO-ETON-CO-N2-SHOPEE", [item(9200102, sku="1025377")],
         pricing=SHOPEE_PRICING,
         expect={"create_calls": 1, "create_status": 200, "create_mark": "New",
                 "pricing_calls": 1, "pricing_status": 200, "db_rows": 1, "unsync": False},
         note="Shopee is the only channel carrying pricing at order level rather than per line. "
              "Proves that carrier is found and mapped.",
         given="A shopee_vn order carrying its pricing in data.order_adjustment.adjustments.",
         then=["Eton accepts the create, Status 'New'.",
               "One row in orders.",
               "One price detail push, accepted 200, with the order-level Shopee components "
               "populated."]),

    case("N3", "N3. Lazada - line_item_details",
         "92000003", "SO-ETON-CO-N3-LAZADA",
         [item(9200103, price="120000.0", paid="108000.0",
               line_item_details=line_pricing(1832015, "120000", "108000"))],
         marketplace="lazada_vn",
         expect={"create_calls": 1, "create_status": 200, "create_mark": "New",
                 "pricing_calls": 1, "pricing_status": 200, "db_rows": 1, "unsync": False},
         note="The per-line carrier is a different shape from Shopee's. Proves the mapper reads it.",
         given="A lazada_vn order carrying pricing per line, in order_items[].line_item_details.",
         then=["Create accepted, Status 'New'.",
               "One row in orders.",
               "One price detail push, accepted, carrying the per-line breakdown with "
               "Items[].SKU = SKU-ETON-001."]),

    case("N4", "N4. TikTok - line_item_details",
         "92000004", "SO-ETON-CO-N4-TIKTOK",
         [item(9200104, price="200000.0", paid="170000.0",
               line_item_details=line_pricing(1832016, "200000", "170000"))],
         marketplace="tiktok_vn",
         expect={"create_calls": 1, "create_status": 200, "create_mark": "New",
                 "pricing_calls": 1, "pricing_status": 200, "db_rows": 1, "unsync": False},
         note="Lazada and TikTok share one reader. Proves channel prefix resolution routes both to "
              "it, so a change made for one cannot silently break the other.",
         given="A tiktok_vn order carrying pricing per line — the same shape Lazada uses.",
         then=["Create accepted, Status 'New'.",
               "One row in orders.",
               "One price detail push, accepted, carrying the per-line breakdown."]),

    case("N5", "N5. TikTok - flat fallback (empty line_item_details)",
         "92000005", "SO-ETON-CO-N5-TIKTOK-FLAT",
         [item(9200105, price=200000.0, paid=170000.0, quantity=2, line_item_details=[],
               channel_discount=10000.0, seller_discount=5000.0, shipping_amount=15000.0,
               tax_amount=2000.0)],
         marketplace="tiktok_th",
         expect={"create_calls": 1, "create_status": 200, "create_mark": "New",
                 "pricing_calls": 1, "pricing_status": 200, "db_rows": 1, "unsync": False},
         note="hasLineItemPricing has to fall back to the flat fields rather than read an empty "
              "array as 'no pricing'. Proves the fallback fires.",
         given="A tiktok_vn order whose line_item_details is empty, but whose item_price and "
               "paid_price are non-zero.",
         then=["Create accepted, Status 'New'.",
               "One row in orders.",
               "One price detail push, accepted, mapped flat from item_price and paid_price with "
               "no line breakdown."]),

    case("N6", "N6. TikTok - zero prices, nothing to push (boundary)",
         "92000006", "SO-ETON-CO-N6-TIKTOK-ZERO",
         [item(9200106, price=0, paid=0, line_item_details=[])],
         marketplace="tiktok_vn",
         expect={"create_calls": 1, "create_status": 200, "create_mark": "New",
                 "pricing_calls": 0, "pricing_status": None, "db_rows": 1, "unsync": False},
         note="The boundary between 'flat fallback' and 'no data'. Zeros pushed to Eton would "
              "assert the order had no discount, tax or shipping — silent corruption, not a "
              "visible failure. Proves pushPricingIfMapped skips instead.",
         given="A tiktok_vn order whose line_item_details is empty AND whose item_price and "
               "paid_price are both zero.",
         then=["Create accepted, Status 'New'.",
               "One row in orders.",
               "No price detail call is made at all."]),

    case("N7", "N7. Haravan - out of scope channel",
         "92000007", "SO-ETON-CO-N7-HARAVAN",
         [item(9200107, price="80000.0", paid="80000.0")],
         marketplace="haravan_vn",
         expect={"create_calls": 1, "create_status": 200, "create_mark": "New",
                 "pricing_calls": 0, "pricing_status": None, "db_rows": 1, "unsync": False},
         note="The important negative. An out-of-scope channel must skip pricing rather than send "
              "zeros, for the same reason as N6.",
         given="A haravan_vn order. EtonUtils.getSalesChannel does a longest-prefix match over "
               "EtonConstants.SALES_CHANNEL_MAP and resolves this to 'Haravan', which is not one "
               "of the three channels build() maps pricing for, so it falls through to empty.",
         then=["Create accepted, Status 'New'.",
               "One row in orders.",
               "No price detail call is made at all."]),

    case("N8", "N8. Packed order",
         "92000008", "SO-ETON-CO-N8-PACKED", [item(9200108)],
         expect={"create_calls": 1, "create_status": 200, "create_mark": "Packed",
                 "pricing_calls": 0, "pricing_status": None, "db_rows": 1, "unsync": False},
         note="Cancellation behaviour later keys off packed state — cancelOrder reads any 400 as "
              "'Eton packed it'. Proves creation records that state in the first place.",
         given="An order whose number contains PACKED, which makes the mock answer as a warehouse "
               "that has already packed it.",
         then=["Create accepted with Status 'Packed' rather than 'New'.",
               "One row in orders.",
               "The code is appended to packed_orders.json.",
               "No price detail push."]),

    case("N9", "N9. Replay - Eton answers BESO05 already exists",
         "92000009", "SO-ETON-CO-N9-EXISTS", [item(9200109, sku="1025377")],
         pricing=SHOPEE_PRICING,
         expect={"create_calls": 1, "create_status": 400, "create_mark": "BESO05",
                 "pricing_calls": 1, "pricing_status": 200, "db_rows": 1, "unsync": False},
         note="A replay must not be read as an error and must not duplicate the row. Proves "
              "handleAlreadyExistsOnEton takes the replay branch.",
         given="An order whose number contains EXISTS, so Eton answers 400 with error code "
               "BESO05 — meaning it already holds this order.",
         then=["The create answers 400 carrying BESO05.",
               "createOrder treats that as success, not failure.",
               "The order is not re-saved — one row in orders, not two.",
               "The price detail push still goes out and is accepted."]),

    case("N10", "N10. Eton 500 - retry then recover",
         "92000010", "SO-ETON-CO-N10-SERVERERROR", [item(9200110)], wait=110,
         expect={"create_calls": 3, "create_status": 500, "create_mark": None,
                 "pricing_calls": 0, "pricing_status": None, "db_rows": 0, "unsync": False},
         blocked_when=BLOCKED_ON_RECOVER,
         note="Proves a 5xx is retried rather than swallowed, and that nothing is persisted for an "
              "order Eton never accepted. The unsynchronized report cannot be proven here unless "
              "event_name is order_creation — see the known gap.",
         given="An order whose number contains SERVERERROR, so Eton answers 500 to every create "
               "attempt.",
         then=["Exactly 3 create calls, 30 seconds apart — @Retryable's contract.",
               "No row is written to orders.",
               "No price detail push.",
               "After the third attempt @Recover runs."]),

    case("N11", "N11. Eton 400 generic - reported unsynchronized",
         "92000011", "SO-ETON-CO-N11-INVALID", [item(9200111)],
         expect={"create_calls": 1, "create_status": 400, "create_mark": "Validation failed",
                 "pricing_calls": 0, "pricing_status": None, "db_rows": 0, "unsync": True},
         note="A 4xx means the payload is wrong; retrying it three times would only delay the "
              "report. Proves the integration tells 4xx and 5xx apart.",
         given="An order whose number contains INVALID, so Eton answers a generic 400 rather than "
               "BESO05.",
         then=["Exactly 1 create call — a 400 is not retried.",
               "No row in orders.",
               "No price detail push.",
               "The order is reported unsynchronized to Anchanto OMS on the "
               "pushUnsynchronizedOrder queue."]),

    case("N12", "N12. Pricing rejected - retried alone, then the order stands",
         "92009666", "SO-ETON-CO-N12-PRICING-REJECT", [item(9200112, sku="1025377")],
         pricing=SHOPEE_PRICING, wait=30,
         expect={"create_calls": 1, "create_status": 200, "create_mark": "New",
                 "pricing_calls": 3, "pricing_status": 400, "db_rows": 1, "unsync": False},
         note="The most valuable case in the suite — the only one exercising 'the order exists on "
              "Eton but its pricing does not'. It has stated three different contracts. Originally "
              "3 creates and 3 pricing pushes: pushCreatedOrderPricing threw, so @Retryable "
              "replayed the whole run against a sale order Eton already held. Commit 465e7a647c3 "
              "removed the throw, leaving 1 create and 1 push. Commit 0b4508fc27d put the retry "
              "back where SRC-01 AC 3 asked for it — on the priceDetail call alone — so the count "
              "is 1 create and 3 pushes, and the ratio between those two numbers is the whole "
              "point of the case. Run 20260816-231529 is where the first expectation last failed.",
         given="An order whose id contains 9666, so Eton accepts the create but rejects the price "
               "detail with 400 on every attempt. The marker sits on the id, not the number, "
               "because the pricing push is addressed by the code Eton echoed back — and "
               "DataDTO.order_id is a Long, so it had to be numeric.",
         then=["1 create call and 3 pricing calls — only the rejected call is re-run, never the "
               "sale-order creation, which is what SRC-01 AC 3 asks for.",
               "The create answers 200 'New'; every pricing push answers 400.",
               "Exactly one row in orders — the retry re-sends, it does not re-create.",
               "Nothing is reported unsynchronized once the attempts are spent: createOrder "
               "reports success, so the missing breakdown exists only as a logged error.",
               "The three pushes are 3 to 6 seconds apart, which is why this case waits 30."]),

    case("N13", "N13. Empty order_items - mock validation 400",
         "92000013", "SO-ETON-CO-N13-NO-ITEMS", [],
         expect={"create_calls": 1, "create_status": 400, "create_mark": "must not be empty",
                 "pricing_calls": 0, "pricing_status": None, "db_rows": 0, "unsync": True},
         note="The array is sent empty rather than omitted on purpose: omitting the key NPEs "
              "inside buildCreateSaleOrderItems before any Eton call is made, which would test "
              "nothing.",
         given="An order with an empty order_items array, which produces an empty ListSODetail. "
               "Eton's schema forbids it.",
         then=["The create answers 400 naming 'ListSODetail' must not be empty.",
               "1 create call — not retried.",
               "No row in orders.",
               "No price detail push."]),

    case("N14", "N14. Pricing payload - every property named once",
         "92000014", "SO-ETON-CO-N14-PAYLOAD-SHAPE", [item(9200114, sku="1025377")],
         pricing=SHOPEE_PRICING,
         expect={"create_calls": 1, "create_status": 200, "create_mark": "New",
                 "pricing_calls": 1, "pricing_status": 200, "db_rows": 1, "unsync": False,
                 "pricing_keys": 15},
         note="N2 proves the Shopee carrier is found and mapped; this proves what the mapping "
              "serialises to. Both price DTOs first named their fields for the wire, so Jackson "
              "treated each field and its getter as two properties and sent all 15 values twice — "
              "30 keys, plus a doubled Items array with 8 doubled keys per line. Eton accepted it "
              "because ASP.NET binding is case-insensitive and last-wins, so nothing failed and "
              "nothing in the old suite could see it. Only the wire shows it.",
         given="The same shopee_vn order as N2, judged on the body of the pricing push rather "
               "than on whether the push happened.",
         then=["Create accepted, one row in orders, one price detail push accepted.",
               "The pushed body carries exactly 15 top-level properties — the count "
               "PricingComponentModel declares in eton-swagger.json.",
               "Not one lowercase-initial key: Items and never items, OrderBasePrice and never "
               "orderBasePrice."]),

    case("N15", "N15. Shopee quantity above one - per-unit amounts multiplied out",
         "92000015", "SO-ETON-CO-N15-QTY2", [item(9200115, sku="1025377", quantity=2)],
         pricing=SHOPEE_PRICING_QTY2,
         expect={"create_calls": 1, "create_status": 200, "create_mark": "New",
                 "pricing_calls": 1, "pricing_status": 200, "db_rows": 1, "unsync": False,
                 "item_base_prices": [210000.0]},
         note="Every other Shopee case orders one unit, where a per-unit price and a line total "
              "are the same number, so none of them can tell the two apart. Shopee states each "
              "adjustments.items[] amount per unit alongside quantity_purchased; Eton reads "
              "BasePrice as 'total number of the original price of the item'. Sending the unit "
              "price halves the line against an order level that is already correct.",
         given="A shopee_vn order for 2 units, whose adjustments entry carries "
               "quantity_purchased 2 and original_price 105000, and whose order-level "
               "order_original_price is the matching 210000.",
         then=["Create accepted, one row in orders, one price detail push accepted.",
               "Items[0].BasePrice is 210000 — 2 x 105000, not the 105000 unit price.",
               "It equals the order-level OrderBasePrice, so the two levels agree."]),

    case("N16", "N16. Unmappable payload - reported rather than escaping",
         "92000016", "SO-ETON-CO-N16-NO-ADDRESS", [item(9200116)],
         extra={"data": {"shipping_address": DELETE}},
         expect={"create_calls": 0, "create_status": None, "create_mark": None,
                 "pricing_calls": 0, "pricing_status": None, "db_rows": 0, "unsync": True},
         note="buildCreateSalesOrderDTO dereferences the shipping address for a log line. It was "
              "built outside createOrder's try block, so a missing address escaped past all three "
              "catch blocks — no seller-tagged log, no Slack alert, three silent @Retryable "
              "attempts and a minute of backoff before @Recover. It was moved back inside, which "
              "is what this case pins. A retry cannot fix a malformed payload.",
         given="An order with no shipping_address at all, which NPEs while the Eton payload is "
               "being mapped — before any Eton call is made.",
         then=["No create call reaches Eton, and no pricing call.",
               "No row in orders.",
               "The order is reported unsynchronized on the pushUnsynchronizedOrder queue, in "
               "this run rather than after three retries."]),

    case("N17", "N17. Blank item_sku - no line inherits another's prices",
         "92000017", "SO-ETON-CO-N17-BLANK-SKU",
         [item(9200117, sku="1025377"),
          item(9200118, sku="INV-UNPRICED", price="0.0", paid="0.0", marketplace_sku="")],
         pricing=SHOPEE_PRICING,
         expect={"create_calls": 1, "create_status": 200, "create_mark": "New",
                 "pricing_calls": 1, "pricing_status": 200, "db_rows": 1, "unsync": False,
                 "item_base_prices": [105000.0, 0.0]},
         note="Real Shopee payloads carry an empty item_sku on every adjustments entry — the "
              "fixture above does too. matchAdjustmentItem guarded only against null, so an OMS "
              "line whose own sku was blank matched the first such entry and inherited its prices, "
              "and the same entry was then counted once per blank line at order level. Silent "
              "over-statement, not a failure.",
         given="A shopee_vn order of two lines, the second carrying a blank marketplace sku, "
               "against an adjustments block whose single entry has item_sku ''.",
         then=["Create accepted, one row in orders, one price detail push accepted.",
               "Items[0].BasePrice is 105000, matched on model_sku as it should be.",
               "Items[1].BasePrice is 0 — the blank sku matches nothing rather than inheriting "
               "the first entry."]),

    case("K1", "K1. Shopee kit - explodes into components",
         "92000101", "SO-ETON-CO-K1-KIT-SHOPEE",
         [item(9200201, sku=None, quantity=2, kit_details=KIT)],
         pricing=SHOPEE_PRICING, shape="kit",
         expect={"create_calls": 1, "create_status": 200, "create_mark": "New",
                 "pricing_calls": 1, "pricing_status": 200, "db_rows": 1, "unsync": False},
         note="Eton has no concept of a kit. Proves the explosion happens before the payload is "
              "built, and that the quantity arithmetic multiplies through.",
         given="A shopee_vn order for a kit, quantity 2, made of two components.",
         then=["ListSODetail carries one line per component, not one line for the kit — "
               "1025377-A quantity 6, 1025377-B quantity 2, i.e. component quantity × kit "
               "quantity.",
               "Create accepted, Status 'New'.",
               "One row in orders.",
               "One price detail push with one Items[] entry per component."]),

    case("K2", "K2. TikTok kit - line_item_details carrier",
         "92000102", "SO-ETON-CO-K2-KIT-TIKTOK",
         [item(9200202, sku=None, price="300000.0", paid="255000.0", quantity=2, kit_details=KIT,
               line_item_details=line_pricing(1832017, "300000", "255000"))],
         marketplace="tiktok_vn", shape="kit",
         expect={"create_calls": 1, "create_status": 200, "create_mark": "New",
                 "pricing_calls": 1, "pricing_status": 200, "db_rows": 1, "unsync": False},
         note="Kit explosion and per-line pricing have to compose. Proves neither breaks the other.",
         given="The same kit, on a tiktok_vn order carrying its pricing per line.",
         then=["Components exploded exactly as in K1.",
               "Create accepted; one row in orders.",
               "One price detail push, mapped from line_item_details."]),

    case("K3", "K3. Kit and plain item in one order",
         "92000103", "SO-ETON-CO-K3-KIT-PLUS-PLAIN",
         [item(9200203, sku=None, quantity=2, kit_details=KIT),
          item(9200204, sku="INV-PLAIN", price="45000.0", paid="38650.0")],
         pricing=SHOPEE_PRICING, shape="kit",
         expect={"create_calls": 1, "create_status": 200, "create_mark": "New",
                 "pricing_calls": 1, "pricing_status": 200, "db_rows": 1, "unsync": False},
         note="Proves explosion is per line rather than per order: a plain line sitting beside a "
              "kit must survive untouched.",
         given="One order holding a kit of two components and a plain item.",
         then=["ListSODetail carries 3 lines — the 2 components and INV-PLAIN.",
               "Create accepted; one row in orders.",
               "One price detail push."]),

    case("K4", "K4. Kit with a component missing its SKU - validation 400",
         "92000104", "SO-ETON-CO-K4-KIT-NO-SKU",
         [item(9200205, sku=None, kit_details=[
             {"inventory_product_sku": "1025377-A", "quantity": 1, "price": 70000.0},
             {"inventory_product_sku": None, "quantity": 1, "price": 35000.0}])],
         pricing=SHOPEE_PRICING, shape="kit",
         expect={"create_calls": 1, "create_status": 400, "create_mark": "SKU' is required",
                 "pricing_calls": 0, "pricing_status": None, "db_rows": 0, "unsync": True},
         note="A shape-specific failure a plain item cannot produce. The index in Eton's error "
              "names the exploded line, which is what proves the component reached Eton as a line "
              "of its own.",
         given="A kit whose second component has no SKU.",
         then=["The create answers 400 naming 'ListSODetail[1].SKU' is required.",
               "1 create call — not retried.",
               "No row in orders.",
               "No price detail push."]),
]


# -------------------------------------------------------------------------------------- suite

SUITE = Suite(
    id="flow2",
    name="createOrder flow 2 (Anchanto OMS -> Eton WMS)",
    description="Anchanto OMS -> JPluger -> Eton WMS, 21 cases (normal + kit)",
    mock="eton",
    cases=CASES,
    env=ENV,
    prepare=prepare,

    # How a case reaches the app. The controller publishes and returns; every assertion below is
    # made against what the integration then did.
    fire=PostJson("${APP}/jpluger/wms/createOrders"),

    # The two calls this flow makes to Eton, named so a case can say how many it expects.
    groups=[Group("create", "POST", "/api/v0.2/saleorders/single"),
            Group("pricing", "POST", "/api/v0.2/saleorders/*/priceDetail", label="push")],

    # Creation echoes ClientSoCode back as the Eton code, so the pricing push that follows is
    # addressed by the same id -- which is what makes a case's whole traffic recoverable from the
    # log without relying on timing.
    call_key=key_from(url=r"/saleorders/([^/?]+)", skip=("single",), body=("ClientSoCode",)),

    # The checklist, in the order the flow happens: the publish, the create, its marker, the
    # `orders` insert -- which EtonWmsService does before pushing pricing -- then the pricing push
    # and its answer. Read top to bottom, it is the journey of one order.
    checks=[
        ControllerStatus("Send the order to JPluger",
                         "POST /jpluger/wms/createOrders (publish only)", value=200),
        Calls("create", "Send the order to Eton", "POST /api/v0.2/saleorders/single",
              expect="create_calls"),
        Status("create", "Eton answers the create", "HTTP status of the create response",
               expect="create_status"),
        Marker("create", "Read the marker in the reply",
               "Status / ErrorCode / ErrorMessages[0] in the body", expect="create_mark"),
        Rows("Write the order to the database", "rows in the `orders` table for this order",
             expect="db_rows"),
        Calls("pricing", "Send the price detail to Eton",
              "POST /api/v0.2/saleorders/{code}/priceDetail", expect="pricing_calls"),
        Status("pricing", "Eton answers the price detail",
               "HTTP status of every pricing response", expect="pricing_status", which="all"),
        # What the mapping serialised to, for the cases that state it. Every other check reads the
        # traffic; these two read the body inside it.
        Custom("Name every pricing property once",
               "top-level keys in the pushed body, and any lowercase-initial duplicate",
               one_key_per_property, expect="pricing_keys"),
        Custom("Send line totals, not unit prices", "Items[].BasePrice as pushed",
               item_base_prices, expect="item_base_prices"),
        # Reported, not judged: the depth is a run total and cannot be attributed to one case.
        QueueDelta("pushUnsynchronizedOrder", "unsynchronized report",
                   "messages added to the pushUnsynchronizedOrder queue", expect="unsync"),
    ],

    # Emptied before the run and captured into the run folder after every case.
    stores=["packed_orders", "price_details", "created_orders"],

    database=Sql(
        client=lambda env: MySql.from_json(env["CORE_JSON"], env["DB_NAME"]),
        dump="SELECT order_number, selluseller_order_id, wms_order_id, status, warehouse_code, "
             "created_date FROM orders WHERE order_number LIKE 'SO-ETON-CO-%' "
             "ORDER BY order_number",
        file="orders.tsv",
        key_column=0,
        reset="DELETE FROM orders WHERE order_number LIKE 'SO-ETON-CO-%'",
    ),

    queues=Queues(url="${RABBIT}", auth="${RABBIT_AUTH}", watch=["pushUnsynchronizedOrder"]),

    preflight=[
        AppResponds("${APP}/jpluger/wms/createOrders"),
        MockResponds(),
        DatabaseResponds(),
        # The seller and its Eton credentials must exist in the database the app reads, not merely
        # in some database. WmsIntegrationParamFactory looks them up before any Eton call is made,
        # so when they are absent every case dies with the same NullPointerException and nothing
        # reaches the mock -- which reads as "all tests failed" rather than "the app is pointed at
        # an empty schema".
        SeedRows("seller 7004",
                 "SELECT COUNT(*) FROM seller WHERE selluseller_seller_id=7004",
                 hint="load it:  mysql … ${DB_NAME} < eton/seed-data/"
                      "eton_local_seed_data.sql"),
        SeedRows("eton credentials",
                 "SELECT COUNT(*) FROM credential c JOIN seller s ON s.seller_id=c.seller_id "
                 "WHERE s.selluseller_seller_id=7004 AND c.wms_code='eton'",
                 at_least=4),
        QueuesRespond(),
    ],
)


if __name__ == "__main__":
    from suite.run import main
    sys.exit(main(__file__, sys.argv[1:]))
