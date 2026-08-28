#!/usr/bin/env python3
"""createOrder: Anchanto OMS publishes an order, JPluger creates it on Eton WMS.

The transport, not the pricing. What Eton answers and what the integration does about it: an
accepted create, a replay, a 5xx retried, a 4xx reported, a rejected pricing push, a payload that
cannot be mapped at all, and the shape of the body the mapping serialises to. None of these ten
cases is about one marketplace's mapping, which is why they are the ones left here.

createOrder used to be all 21 cases in this one file. The pricing cases now live one suite per
marketplace, because the three channels are three different mappings that happen to share this
wire, and each one is worth reading and failing on its own:

    eton/suite-create-order-shopee.py    7 cases   the adjustments{} hash, matched onto items by SKU
    eton/suite-create-order-lazada.py    2 cases   order_items[] with one detail row per unit
    eton/suite-create-order-tiktok.py    7 cases   order_items[] with an order-level discount to spread

Everything those four files share -- the base order, the intake loader, the five body checks and
the Suite itself -- is in `eton/create_order.py`.

Four of the ten cases here are built from masked production intakes in `eton/intakes/`, because a
replay, a rejected push and the property names of the body are all worth asserting against a real
payload rather than a hand-written one. They borrow a Shopee intake for that; what the Shopee
mapping does with it is asserted next door, not here.

    python3 eton/suite-create-order.py                 all 10 cases
    python3 eton/suite-create-order.py --fast          skips N10, the one retry case
    python3 eton/suite-create-order.py N10 N12 K4      only the cases named
    python3 eton/suite-create-order.py --judge eton/test-results/create-order/run-...

Requires the app on ${APP}, the mock on ${MOCK} (`python3 mock.py eton`), and the seed in the
database the app itself reads. Preflight names whichever is missing.

The engine, the check vocabulary and the runner contract: `suite/` and `TESTING.md`. What the mock
answers and why: `eton/README.md`.

Moved out, and where to -- the ids are not reused, so a run from before the split still lines up:
    P1 P2 P3 N1 N17     suite-create-order-shopee.py
    P4 P5               suite-create-order-lazada.py
    P6 P7 N5 N6         suite-create-order-tiktok.py

Retired, and why -- likewise:
    N2 N3 N4    "the carrier is found and mapped" for Shopee, Lazada and TikTok. The P cases prove
                the same thing against real payloads and state the resulting numbers.
    N15         asserted a per-unit adjustments amount multiplied out by quantity_purchased. Real
                Shopee data states the line total there, so the case asserted a fault; P1 pins the
                contract that replaced it.
    K1 K2 K3    kit explosion on Shopee and TikTok, and a kit beside a plain line. P1 is two kits
                and two plain lines in one production order; P2, P3, P5, P6, P7 and P9 carry kits
                too."""

import os
import sys

# create_order is a sibling module, and a suite file is started from wherever the caller happens to be.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from create_order import (BLOCKED_ON_RECOVER, DELETE, blank_marketplace_sku, case, flow_suite, item,
                      prod_case)


CASES = [
    # ---- the channel that is not mapped, and the state that is
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

    # ---- what Eton answers, and what the integration does about it
    prod_case("N9", "N9. Replay - Eton answers BESO05 already exists",
              "92000009", "SO-ETON-CO-N9-EXISTS", "shopee-shared-entry",
              expect={"create_status": 400, "create_mark": "BESO05",
                      "lines_sum_to_order": True, "promo_within_base": True},
              note="A replay must not be read as an error and must not duplicate the row. Proves "
                   "handleAlreadyExistsOnEton takes the replay branch, and that it still pushes "
                   "pricing — an order Eton already holds is exactly the case where the breakdown "
                   "may be the only thing missing.",
              given="The P2 intake under an order number containing EXISTS, so Eton answers 400 "
                    "with error code BESO05 — meaning it already holds this order.",
              then=["The create answers 400 carrying BESO05.",
                    "createOrder treats that as success, not failure.",
                    "The order is not re-saved — one row in orders, not two.",
                    "The price detail push still goes out, is accepted, and carries the same "
                    "breakdown P2 states."]),

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

    prod_case("N12", "N12. Pricing rejected - retried alone, then the order stands",
              "92009666", "SO-ETON-CO-N12-PRICING-REJECT", "shopee-shared-entry", wait=30,
              expect={"pricing_calls": 3, "pricing_status": 400,
                      "lines_sum_to_order": True, "promo_within_base": True},
              note="The most valuable case in the suite — the only one exercising 'the order "
                   "exists on Eton but its pricing does not'. It has stated three different "
                   "contracts. Originally 3 creates and 3 pricing pushes: pushCreatedOrderPricing "
                   "threw, so @Retryable replayed the whole run against a sale order Eton already "
                   "held. Commit 465e7a647c3 removed the throw, leaving 1 create and 1 push. "
                   "Commit 0b4508fc27d put the retry back where SRC-01 AC 3 asked for it — on the "
                   "priceDetail call alone — so the count is 1 create and 3 pushes, and the ratio "
                   "between those two numbers is the whole point of the case. Run "
                   "20260816-231529 is where the first expectation last failed.",
              given="The P2 intake under an order id containing 9666, so Eton accepts the create "
                    "but rejects the price detail with 400 on every attempt. The marker sits on "
                    "the id, not the number, because the pricing push is addressed by the code "
                    "Eton echoed back — and DataDTO.order_id is a Long, so it had to be numeric.",
              then=["1 create call and 3 pricing calls — only the rejected call is re-run, never "
                    "the sale-order creation, which is what SRC-01 AC 3 asks for.",
                    "The create answers 200 'New'; every pricing push answers 400.",
                    "Exactly one row in orders — the retry re-sends, it does not re-create.",
                    "Nothing is reported unsynchronized once the attempts are spent: createOrder "
                    "reports success, so the missing breakdown exists only as a logged error.",
                    "The three pushes are 3 to 6 seconds apart, which is why this case waits 30."]),

    # -------------------- payloads Eton or the mapper refuses
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

    case("K4", "K4. Kit with a component missing its SKU - validation 400",
         "92000104", "SO-ETON-CO-K4-KIT-NO-SKU",
         [item(9200205, sku=None, kit_details=[
             {"inventory_product_sku": "1025377-A", "quantity": 1, "price": 70000.0},
             {"inventory_product_sku": None, "quantity": 1, "price": 35000.0}])],
         shape="kit",
         expect={"create_calls": 1, "create_status": 400, "create_mark": "SKU' is required",
                 "pricing_calls": 0, "pricing_status": None, "db_rows": 0, "unsync": True},
         note="A shape-specific failure a plain item cannot produce, and the one kit case no "
              "production intake covers — OMS does not emit a component without a SKU. The index "
              "in Eton's error names the exploded line, which is what proves the component "
              "reached Eton as a line of its own.",
         given="A kit whose second component has no SKU, on a shopee_vn order carrying no pricing "
               "block.",
         then=["The create answers 400 naming 'ListSODetail[1].SKU' is required.",
               "1 create call — not retried.",
               "No row in orders.",
               "No price detail push."]),

    # --------------------------- the shape of the body itself
    prod_case("N14", "N14. Pricing payload - every property named once",
              "92000014", "SO-ETON-CO-N14-PAYLOAD-SHAPE", "shopee-qty2-entry",
              expect={"pricing_keys": 15, "lines_sum_to_order": True, "promo_within_base": True},
              note="P1 proves what the Shopee carrier maps to; this proves what the mapping "
                   "serialises to. Both price DTOs first named their fields for the wire, so "
                   "Jackson treated each field and its getter as two properties and sent all 15 "
                   "values twice — 30 keys, plus a doubled Items array with 8 doubled keys per "
                   "line. Eton accepted it because ASP.NET binding is case-insensitive and "
                   "last-wins, so nothing failed and nothing in the old suite could see it. Only "
                   "the wire shows it.",
              given="The same production intake as P1, judged on the property names of the pushed "
                    "body rather than on the amounts in it.",
              then=["Create accepted, one row in orders, one price detail push accepted.",
                    "The pushed body carries exactly 15 top-level properties — the count "
                    "PricingComponentModel declares in eton-swagger.json.",
                    "Not one lowercase-initial key: Items and never items, OrderBasePrice and "
                    "never orderBasePrice."]),

]


# ---------------------------------------------------------------------------------- suite

SUITE = flow_suite(
    suite_id="create-order",
    name="createOrder (Anchanto OMS -> Eton WMS)",
    description="Anchanto OMS -> JPluger -> Eton WMS, transport and failure: 10 cases "
                "(4 production intakes + 6 structural)",
    cases=CASES,
)


if __name__ == "__main__":
    from suite.run import main
    sys.exit(main(__file__, sys.argv[1:]))
