#!/usr/bin/env python3
"""Everything the four createOrder suites share: the payloads, the checks and the Suite shape.

createOrder is Anchanto OMS publishing an order and JPluger creating it on Eton WMS. It used to be
one file of 21 cases; it is now one suite per marketplace plus one for the transport, because the
three channels are three different mappings that happen to share a wire:

    eton/suite-create-order-shopee.py    the adjustments{} hash, matched onto order items by SKU
    eton/suite-create-order-lazada.py    order_items[] with one detail row per unit
    eton/suite-create-order-tiktok.py    order_items[] with an order-level discount to spread
    eton/suite-create-order.py           create, replay, retry, failure and the payload's own shape

Splitting them buys two things. A channel's cases now fail together and read together -- a Shopee
mapping change is one suite, not seven cases scattered through twenty-one. And each suite is small
enough to run on its own, which is what makes it usable while working on one channel.

Case ids are never reused or renumbered, here or in the suites, so a run recorded before the split
still lines up case for case -- see each suite's own header for what it inherited.

Nothing in this module is a suite. It holds:

    settings and the payload every case starts from
    item()/order()/case()          hand-written cases, for shapes no production intake carries
    intake()/prod_case()           cases built from a masked production intake
    the five body checks           what the mapping serialised, judged on the pushed body
    flow_suite()                   the Suite every createOrder suite declares through

The engine, the check vocabulary and the runner contract: `suite/` and `TESTING.md`. What the mock
answers and why: `eton/README.md`.
"""

import copy
import json
import os
import sys

# The engine is a sibling package, and a suite file is started from wherever the caller happens to
# be -- the /test page starts it from the mock's own folder.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from suite import (Blocked, Calls, Case, ControllerStatus, Custom, DELETE, Group, Marker, MySql,
                   PostJson, QueueDelta, Queues, Rows, Sql, Status, Suite, merge, key_from)
from suite import AppResponds, DatabaseResponds, MockResponds, QueuesRespond, SeedRows

PACKAGE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))


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
    # that gap:  EVENT_NAME=order_created python3 eton/suite-create-order.py N10
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
# two cases is the whole of what distinguishes them. It carries the identity, the addresses and the
# customer -- a production intake carries none of those, and takes them from here.
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
    """One hand-written order line, for the cases a production intake cannot state.

    `sku` is the inventory SKU, which is what reaches Eton as the line's SKU. `marketplace_sku` is
    the channel's own identifier, which is a different value and is what the Shopee adjustments
    block is joined on. The per-line carrier Lazada and TikTok send is no longer written by hand --
    pass `line_item_details` from an intake in `eton/intakes/` if a case needs one.
    """
    line = {"order_item_id": item_id, "name": "Combo Tra Oolong Cau Tre", "sku": marketplace_sku,
            "inventory_sku": sku, "item_price": price, "paid_price": paid, "quantity": quantity}
    line.update(extra)
    return line


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


# ------------------------------------------------------------------- production intakes

INTAKES = os.path.join(HERE, "intakes")


def intake(name):
    """The `data` fragment of one masked production intake, from `eton/intakes/<name>.json`.

    Each file carries only the fields the create and pricing paths read, and says in its own header
    which sale order it was captured from and what it is worth testing. Every price, quantity and
    SKU in it is what OMS sent; the identity, the customer and the addresses are not in the file at
    all -- they come from ORDER above.
    """
    with open(os.path.join(INTAKES, name + ".json")) as handle:
        return json.load(handle)["data"]


def blank_marketplace_sku(name, index):
    """The same intake with one line's marketplace SKU emptied.

    That field is the join key the Shopee adjustments block is matched on, so emptying it is how a
    case asks what an unmatchable line is priced at.
    """
    items = copy.deepcopy(intake(name)["order_items"])
    items[index]["sku"] = ""
    return {"data": {"order_items": items}}


# The traffic a production intake produces when nothing goes wrong. A case states only where it
# differs, which for most of them is nowhere.
ACCEPTED = {"create_calls": 1, "create_status": 200, "create_mark": "New",
            "pricing_calls": 1, "pricing_status": 200, "db_rows": 1, "unsync": False}


def prod_case(cid, name, order_id, number, source, expect, extra=None, wait=7, **rest):
    """One case built from a production intake, judged on the whole body it pushes.

    `source` names a file in `eton/intakes/`. `expect` states what differs from ACCEPTED plus what
    the push has to carry: `order_totals` and `item_lines` together are every value in the body,
    and the property names those values arrive under are what N14 counts.
    """
    data = intake(source)
    payload = merge(ORDER, {"event_parameters": {"marketplace_code": data["marketplace_code"]},
                            "data": merge(data, {"order_id": order_id, "order_number": number})})
    return Case(cid, name, payload=merge(payload, extra) if extra else payload,
                key=order_id, row_key=number, shape="intake", wait=wait,
                expect=merge(ACCEPTED, expect),
                detail={"order_id": order_id, "order_number": number, "intake": source}, **rest)


# ------------------------------------------------------------------- what reached the wire

# Whole VND amounts, so the tolerance only has to absorb the float division a kit share and a
# TikTok discount spread introduce.
TOLERANCE = 0.01

ORDER_KEYS = ("OrderBasePrice", "OrderSellerDiscount", "OrderSellerVoucher",
              "OrderPlatformDiscount", "OrderPlatformVoucher", "OrderCoinsOrCashback",
              "ShippingFee", "ShippingDiscountSeller", "ShippingDiscountPlatform", "ServiceFee",
              "Tax", "UnclassifiedDiscount", "UnclassifiedFee", "CurrencyCode")

LINE_KEYS = ("SKU", "Quantity", "BasePrice", "SellerDiscount", "SellerVoucher",
             "PlatformDiscount", "PlatformVoucher", "CoinsOrCashback")


def pricing_payload(evidence):
    """The body of the first pricing push, or None when the case pushed nothing."""
    calls = evidence.calls.get("pricing", [])
    if not calls:
        return None
    body = calls[0].request_body
    return body if isinstance(body, dict) else None


def same(got, want):
    """One pushed value against one expected value: numbers within TOLERANCE, else equality."""
    if isinstance(want, bool) or not isinstance(want, (int, float)):
        return got == want
    try:
        return abs(float(got) - float(want)) <= TOLERANCE
    except (TypeError, ValueError):
        return False


def money(value):
    """A pushed amount as it reads in a results row: whole where it is whole."""
    return int(value) if isinstance(value, float) and value.is_integer() else value


def base_of(line):
    return float(line.get("BasePrice") or 0)


def promo_of(line):
    """Everything Eton counts as a promotion on one line: every discount and every voucher."""
    return sum(float(line.get(key) or 0) for key in
               ("SellerDiscount", "SellerVoucher", "PlatformDiscount", "PlatformVoucher",
                "CoinsOrCashback"))


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


def order_totals(case, evidence):
    """Every order-level component of the pushed body, against what the intake states.

    Stated in full rather than one figure at a time: a mapping that reads the right value out of
    the wrong field of the same payload is only visible when the whole set is compared at once.
    """
    want = case.expect.get("order_totals")
    body = pricing_payload(evidence)
    if want is None or body is None:
        return None
    stated = [key for key in ORDER_KEYS if key in want]
    wrong = [key for key in stated if not same(body.get(key), want[key])]
    expected = " ".join("%s=%s" % (key, want[key]) for key in stated)
    if not wrong:
        return (expected, "all %d components as stated" % len(stated), True)
    return (expected,
            " ".join("%s=%s" % (key, money(body.get(key))) for key in wrong) + " (wrong)", False)


def item_lines(case, evidence):
    """`Items[]` as sent, in order, every field of every line.

    Eton reads BasePrice as the line total rather than a unit price, and reads each promotion
    against that line alone -- so a line is only right when all eight values are.
    """
    want = case.expect.get("item_lines")
    body = pricing_payload(evidence)
    if want is None or body is None:
        return None
    got = [tuple(money(line.get(key)) for key in LINE_KEYS) for line in (body.get("Items") or [])]
    ok = len(got) == len(want) and all(
        all(same(value, wanted) for value, wanted in zip(line, expected))
        for line, expected in zip(got, want))
    return ([tuple(expected) for expected in want], got, ok)


def lines_sum_to_order(case, evidence):
    """Sum(Items[].BasePrice) against OrderBasePrice.

    The two levels are mapped from different places -- Shopee's order level is read straight off
    the adjustments block while its lines are matched entry by entry -- so they agree only when
    every line found the entry that belongs to it and no line took one twice. This is the check
    that would have failed in production while Eton was still answering 200.

    A case expecting False says the disagreement is the point: N17 empties a line's join key, so
    that line is priced at nothing while the order level still states the whole order.
    """
    want = case.expect.get("lines_sum_to_order")
    body = pricing_payload(evidence)
    if want is None or body is None:
        return None
    total = sum(base_of(line) for line in (body.get("Items") or []))
    order_base = float(body.get("OrderBasePrice") or 0)
    agree = abs(total - order_base) <= TOLERANCE
    return ("lines %s the order total" % ("sum to" if want else "do not sum to"),
            "lines %s, order %s" % (money(total), money(order_base)),
            agree == want)


def promo_within_base(case, evidence):
    """Every line's promotions inside that line's own base price.

    Eton checks this per line and answers 400 "Promo amount is over total." when it fails, which is
    exactly what a zero-priced gift line carrying the order's discount produces. Judged on the
    pushed body rather than on the answer, because the mock cannot enforce the rule -- its
    condition language has no arithmetic -- so a regression here is a 200 from the mock and a 400
    from Eton.
    """
    want = case.expect.get("promo_within_base")
    body = pricing_payload(evidence)
    if want is None or body is None:
        return None
    over = ["%s promo %s over base %s" % (line.get("SKU"), money(promo_of(line)),
                                          money(base_of(line)))
            for line in (body.get("Items") or []) if promo_of(line) > base_of(line) + TOLERANCE]
    return ("every line's promo within its own base" if want else "at least one line over base",
            "; ".join(over) if over else "every line within its base",
            (not over) == want)


# -------------------------------------------------------------------------------------- suite

def flow_suite(suite_id, name, description, cases):
    """The Suite every createOrder suite declares through: same wire, same checklist, its own cases.

    Only the cases differ between the four files, which is the point -- a Shopee mapping is judged
    by exactly the same evidence as a TikTok one, so a difference between two suites is a
    difference in the mapping and never in how it was measured.

    Each suite keeps its own run folder under `<test_results_dir>/<suite_id>/`, and its own reset
    of the `orders` table: every case in every createOrder suite numbers its order `SO-ETON-CO-…`, so
    the reset below is shared and two suites must not be run against one database at once.
    """
    return Suite(
        id=suite_id,
        name=name,
        description=description,
        mock="eton",
        cases=cases,
        env=ENV,
        prepare=prepare,

        # How a case reaches the app. The controller publishes and returns; every assertion below
        # is made against what the integration then did.
        fire=PostJson("${APP}/jpluger/wms/createOrders"),

        # The two calls this flow makes to Eton, named so a case can say how many it expects.
        groups=[Group("create", "POST", "/api/v0.2/saleorders/single"),
                Group("pricing", "POST", "/api/v0.2/saleorders/*/priceDetail", label="push")],

        # Creation echoes ClientSoCode back as the Eton code, so the pricing push that follows is
        # addressed by the same id -- which is what makes a case's whole traffic recoverable from
        # the log without relying on timing.
        call_key=key_from(url=r"/saleorders/([^/?]+)", skip=("single",), body=("ClientSoCode",)),

        # The checklist, in the order the flow happens: the publish, the create, its marker, the
        # `orders` insert -- which EtonWmsService does before pushing pricing -- then the pricing
        # push, its answer, and what the mapping put inside it. Read top to bottom, it is the
        # journey of one order.
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
            # What the mapping serialised to, for the cases that state it. Every check above reads
            # the traffic; these five read the body inside it.
            Custom("Name every pricing property once",
                   "top-level keys in the pushed body, and any lowercase-initial duplicate",
                   one_key_per_property, expect="pricing_keys"),
            Custom("Map every order-level component",
                   "the 14 order-level values in the pushed body", order_totals,
                   expect="order_totals"),
            Custom("Send line totals, not unit prices",
                   "Items[] as pushed: SKU, quantity and all six amounts, line by line", item_lines,
                   expect="item_lines"),
            Custom("Split the order total across the lines",
                   "Sum(Items[].BasePrice) against OrderBasePrice", lines_sum_to_order,
                   expect="lines_sum_to_order"),
            Custom("Keep each line's promo inside its own base",
                   "per line, its discounts and vouchers against its own BasePrice — the rule Eton "
                   "answers 'Promo amount is over total.' to", promo_within_base,
                   expect="promo_within_base"),
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
            # The seller and its Eton credentials must exist in the database the app reads, not
            # merely in some database. WmsIntegrationParamFactory looks them up before any Eton call
            # is made, so when they are absent every case dies with the same NullPointerException
            # and nothing reaches the mock -- which reads as "all tests failed" rather than "the app
            # is pointed at an empty schema".
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
