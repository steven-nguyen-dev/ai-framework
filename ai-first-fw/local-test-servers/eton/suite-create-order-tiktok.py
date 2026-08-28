#!/usr/bin/env python3
"""createOrder, TikTok: order_items[] with one order-level discount to spread.

TikTok reads its lines like Lazada does, from `line_item_details[]`, but states its discounts once
for the whole order. So the mapping has two jobs Lazada's does not: pick which of the three
carriers is reporting the discount, and spread that one figure across the lines without breaking
either invariant -- the lines must sum to the order total, and no line may carry more promo than
its own base.

Gift lines are what makes that hard, and they are why three of these seven cases exist. Five are
masked production intakes from `eton/intakes/` and state the whole pushed body: every order-level
component and every line, exactly as the mapper produces it from the payload OMS actually sent. Two
are orders that were pushed wrong in production:

    P6   the promo put on the zero-priced gift line -- "Promo amount is over total."
    P10  the gift priced like the purchase it came free with -- base price doubled

    python3 eton/suite-create-order-tiktok.py                 all 7 cases
    python3 eton/suite-create-order-tiktok.py P10 P11         only the cases named
    python3 eton/suite-create-order-tiktok.py --judge eton/test-results/create-order-tiktok/run-...

Requires the app on ${APP}, the mock on ${MOCK} (`python3 mock.py eton`), and the seed in the
database the app itself reads. Preflight names whichever is missing.

Inherited from `suite-create-order.py` when the suite was split per marketplace, keeping the case
ids: P6, P7, N5 and N6. P10, P11 and P12 are new, which is why the P numbering is not contiguous
per channel -- an id is never reused or renumbered, so a run recorded before the split still lines
up."""

import os
import sys

# create_order is a sibling module, and a suite file is started from wherever the caller happens to be.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from create_order import (BLOCKED_ON_RECOVER, DELETE, blank_marketplace_sku, case, flow_suite, item,
                      prod_case)


CASES = [
    # ------------------------------------- production intakes
    prod_case("P6", "P6. TikTok - the promo lands on the line that can carry it",
              "92000351", "SO-ETON-CO-P6-TIKTOK-GIFT", "tiktok-gift-line",
              expect={
                  "order_totals": {
                      "OrderBasePrice": 148000,
                      "OrderSellerDiscount": 13400,
                      "OrderSellerVoucher": 0,
                      "OrderPlatformDiscount": 0,
                      "OrderPlatformVoucher": 0,
                      "OrderCoinsOrCashback": 0,
                      "ShippingFee": 28300,
                      "ShippingDiscountSeller": 0,
                      "ShippingDiscountPlatform": 28300,
                      "ServiceFee": 0,
                      "Tax": 0,
                      "UnclassifiedDiscount": 0,
                      "UnclassifiedFee": 0,
                      "CurrencyCode": "VND",
                  },
                  "item_lines": [
                      ("1022281", 2, 148000, 13400, 0, 0, 0, 0),
                      ("1024681", 2, 0, 0, 0, 0, 0, 0),
                  ],
                  "lines_sum_to_order": True, "promo_within_base": True},
              note="The one production order in this set Eton rejected outright, three attempts "
                   "in a row: the 13400 seller discount was put on the zero-priced gift line, "
                   "whose own base could not carry it, and Eton answered 400 'Promo amount is "
                   "over total.'. The discount is now spread across the lines in proportion to "
                   "their base, so a zero-priced line takes none of it. The mock cannot answer "
                   "the way Eton did -- its conditions have no arithmetic -- so the rule is "
                   "judged on the pushed body instead.",
              given="A tiktok_vn order of a priced kit line and a zero-priced gift line, with the "
                    "order's seller discount carried on order_adjustment.",
              then=["Create accepted, Status 'New'; one row in orders; one push accepted.",
                    "Items[0] carries the whole 13400 against its base of 148000.",
                    "Items[1] carries none of it -- base 0, promo 0.",
                    "Every line's promo is inside its own base, which is the rule Eton enforces "
                    "and the mock does not.",
                    "ShippingFee 28300 comes from shipping_fee_original and is cancelled by an "
                    "equal ShippingDiscountPlatform."]),

    prod_case("P7", "P7. TikTok - both discounts read from order_adjustment",
              "92000361", "SO-ETON-CO-P7-TIKTOK-CARRIED", "tiktok-carried-discounts",
              expect={
                  "order_totals": {
                      "OrderBasePrice": 175000,
                      "OrderSellerDiscount": 15001,
                      "OrderSellerVoucher": 0,
                      "OrderPlatformDiscount": 16000,
                      "OrderPlatformVoucher": 0,
                      "OrderCoinsOrCashback": 0,
                      "ShippingFee": 52200,
                      "ShippingDiscountSeller": 0,
                      "ShippingDiscountPlatform": 52200,
                      "ServiceFee": 0,
                      "Tax": 0,
                      "UnclassifiedDiscount": 0,
                      "UnclassifiedFee": 0,
                      "CurrencyCode": "VND",
                  },
                  "item_lines": [
                      ("1025377", 5, 175000, 15001, 0, 16000, 0, 0),
                      ("1025377", 1, 0, 0, 0, 0, 0, 0),
                  ],
                  "lines_sum_to_order": True, "promo_within_base": True},
              note="Proves the first step of the TikTok order-discount precedence, and proves the "
                   "figures are read once rather than summed: OMS repeats both on every item, so "
                   "summing the flat copies would double them. The odd 15001 is deliberate -- it "
                   "is the real amount, and a rounded 15000 would not show a spread that lost a "
                   "unit. Those two order-level discounts are also what UnclassifiedDiscount is "
                   "derived from, and it reconciles to 0 against what the buyer paid.",
              given="A tiktok_vn order carrying seller_discount 15001 and marketplace_discount "
                    "16000 on order_adjustment, with a kit line and its zero-priced twin.",
              then=["Create accepted, Status 'New'; one row in orders; one push accepted.",
                    "OrderSellerDiscount 15001 and OrderPlatformDiscount 16000, each read once.",
                    "Items[0] carries both in full; Items[1], priced at 0, carries neither.",
                    "UnclassifiedDiscount is 0: the base less both discounts is exactly the paid "
                    "total.",
                    "The lines sum to OrderBasePrice 175000."]),

    # ------------------------------------------------- structure, boundaries and failures

    prod_case("P10", "P10. TikTok - a gift priced like the purchase is still given away",
              "92000391", "SO-ETON-CO-P10-TIKTOK-GWP", "tiktok-mispriced-gift",
              expect={
                  "order_totals": {
                      "OrderBasePrice": 120000,
                      "OrderSellerDiscount": 3602,
                      "OrderSellerVoucher": 0,
                      "OrderPlatformDiscount": 45396,
                      "OrderPlatformVoucher": 0,
                      "OrderCoinsOrCashback": 0,
                      "ShippingFee": 82300,
                      "ShippingDiscountSeller": 0,
                      "ShippingDiscountPlatform": 82300,
                      "ServiceFee": 0,
                      "Tax": 0,
                      "UnclassifiedDiscount": 0,
                      "UnclassifiedFee": 0,
                      "CurrencyCode": "VND",
                  },
                  "item_lines": [
                      ("1027575", 2, 30000, 900.5, 0, 11349, 0, 0),
                      ("1027573", 2, 30000, 900.5, 0, 11349, 0, 0),
                      ("1027576", 2, 30000, 900.5, 0, 11349, 0, 0),
                      ("1027574", 2, 30000, 900.5, 0, 11349, 0, 0),
                      ("1027575", 1, 0, 0, 0, 0, 0, 0),
                      ("1027573", 1, 0, 0, 0, 0, 0, 0),
                      ("1027576", 1, 0, 0, 0, 0, 0, 0),
                      ("1027574", 1, 0, 0, 0, 0, 0, 0),
                      ("1027575", 2, 0, 0, 0, 0, 0, 0),
                      ("1027573", 2, 0, 0, 0, 0, 0, 0),
                      ("1027576", 2, 0, 0, 0, 0, 0, 0),
                      ("1027574", 2, 0, 0, 0, 0, 0, 0),
                  ],
                  "lines_sum_to_order": True, "promo_within_base": True},
              note="P6 is a gift line priced at zero, which is what OMS sends 7851 times out of "
                   "7859. This is one of the 8 it does not: on the '4 MIX TANG 4 MIX' promotion it "
                   "copied the purchased line's item_price and paid_price onto the is_gwp_item "
                   "line beside it, so the order base price came out at 240000 -- twice the 120000 "
                   "OMS states in its own item_total. is_gwp_item is read as 'this line is given "
                   "away' rather than trusting the price on it, which is the treatment "
                   "OrderItemsUtility already applies to a gift line on an e-invoice: the line "
                   "stays, its money goes to zero. Not a mapping bug on our side -- an OMS data "
                   "defect the mapper defends against.",
              given="A tiktok_vn order of three order items -- one bought, two flagged "
                    "is_gwp_item, one of which carries the bought line's prices -- each exploding "
                    "into four kit components, so twelve lines are pushed.",
              then=["Create accepted, Status 'New'; one row in orders; one push accepted.",
                    "OrderBasePrice is 120000, matching OMS's own item_total, not the 240000 the "
                    "copied prices would produce.",
                    "All twelve lines are still pushed -- the gift lines are kept so the payload "
                    "still matches the sale order, they are just worth nothing.",
                    "Only the four bought components carry base and promo; the eight gift lines "
                    "are zero throughout.",
                    "The lines sum to OrderBasePrice 120000."]),

    prod_case("P11", "P11. TikTok - four identical gifts under one SKU",
              "92000401", "SO-ETON-CO-P11-TIKTOK-GIFTS4", "tiktok-repeated-gifts",
              expect={
                  "order_totals": {
                      "OrderBasePrice": 936000,
                      "OrderSellerDiscount": 276000,
                      "OrderSellerVoucher": 0,
                      "OrderPlatformDiscount": 99000,
                      "OrderPlatformVoucher": 0,
                      "OrderCoinsOrCashback": 0,
                      "ShippingFee": 356800,
                      "ShippingDiscountSeller": 0,
                      "ShippingDiscountPlatform": 356800,
                      "ServiceFee": 0,
                      "Tax": 0,
                      "UnclassifiedDiscount": 0,
                      "UnclassifiedFee": 0,
                      "CurrencyCode": "VND",
                  },
                  "item_lines": [
                      ("1024506", 24, 936000, 276000, 0, 99000, 0, 0),
                      ("1024506", 3, 0, 0, 0, 0, 0, 0),
                      ("1024506", 3, 0, 0, 0, 0, 0, 0),
                      ("1024506", 3, 0, 0, 0, 0, 0, 0),
                      ("1024506", 3, 0, 0, 0, 0, 0, 0),
                  ],
                  "lines_sum_to_order": True, "promo_within_base": True},
              note="Five lines under one SKU, four of them identical in every field. Any mapping "
                   "that keyed a line on its SKU, or deduplicated lines that look alike, would "
                   "collapse these four into one and send Eton a sale order short of three gifts "
                   "-- and a gift is real stock that has to be picked. The whole 276000 seller "
                   "discount also has to land on the single priced line, because none of the four "
                   "zero-priced lines can carry any of it.",
              given="A tiktok_vn order of five lines all carrying SKU 1024506: one priced at "
                    "936000 for 24 units, and four gifts of 3 units each at zero.",
              then=["Create accepted, Status 'New'; one row in orders; one push accepted.",
                    "Five lines are pushed, not one -- identical gift lines are kept apart.",
                    "The priced line takes the whole 276000 seller discount and the whole 99000 "
                    "platform discount.",
                    "Each of the four gift lines is zero in all six amounts, so none of them "
                    "breaches its own base.",
                    "The lines sum to OrderBasePrice 936000."]),

    prod_case("P12", "P12. TikTok - an order discount that does not divide evenly",
              "92000411", "SO-ETON-CO-P12-TIKTOK-SPLIT", "tiktok-uneven-split",
              expect={
                  "order_totals": {
                      "OrderBasePrice": 91000,
                      "OrderSellerDiscount": 1352,
                      "OrderSellerVoucher": 0,
                      "OrderPlatformDiscount": 48410,
                      "OrderPlatformVoucher": 0,
                      "OrderCoinsOrCashback": 0,
                      "ShippingFee": 29800,
                      "ShippingDiscountSeller": 0,
                      "ShippingDiscountPlatform": 29800,
                      "ServiceFee": 0,
                      "Tax": 0,
                      "UnclassifiedDiscount": 0,
                      "UnclassifiedFee": 0,
                      "CurrencyCode": "VND",
                  },
                  "item_lines": [
                      ("1025607", 1, 27000, 401.142857, 0, 14363.406593, 0, 0),
                      ("1025703", 1, 64000, 950.857143, 0, 34046.593407, 0, 0),
                  ],
                  "lines_sum_to_order": True, "promo_within_base": True},
              note="TikTok states one discount for the whole order, so the mapper has to spread it "
                   "across the lines by base-price share and the shares here are all repeating: "
                   "1352 over 27000 and 64000 of a 91000 order. The last priced line takes the "
                   "remainder rather than its own share, so Sum(Items[].SellerDiscount) is 1352 "
                   "exactly and not 1351.9999999. The amounts below are the only fractional "
                   "figures any case in these suites expects, which is why TOLERANCE exists.",
              given="A tiktok_vn order of two differently priced lines, 27000 and 64000, carrying "
                    "an order-level seller discount of 1352 and a platform discount of 48410.",
              then=["Create accepted, Status 'New'; one row in orders; one push accepted.",
                    "The seller discount splits 401.142857 / 950.857143 by base-price share.",
                    "The platform discount splits 14363.406593 / 34046.593407 the same way.",
                    "Both lines stay inside their own base, and the lines sum to OrderBasePrice "
                    "91000."]),

    #  the carriers, and the boundary where there is nothing to push
    case("N5", "N5. TikTok - flat fallback (empty line_item_details)",
         "92000005", "SO-ETON-CO-N5-TIKTOK-FLAT",
         [item(9200105, price=200000.0, paid=170000.0, quantity=2, line_item_details=[],
               channel_discount=10000.0, seller_discount=5000.0, shipping_amount=15000.0,
               tax_amount=2000.0)],
         marketplace="tiktok_th",
         expect={"create_calls": 1, "create_status": 200, "create_mark": "New",
                 "pricing_calls": 1, "pricing_status": 200, "db_rows": 1, "unsync": False,
                 "item_lines": [("SKU-ETON-001", 2, 200000, 5000, 0, 10000, 0, 0)],
                 "lines_sum_to_order": True, "promo_within_base": True},
         note="hasLineItemPricing has to fall back to the flat fields rather than read an empty "
              "array as 'no pricing'. Hand-written on purpose: no production intake here has an "
              "empty line_item_details on its only line, so the last step of the discount "
              "precedence -- the flat per-item copies, read as a max because OMS repeats them on "
              "every line -- has nothing real to stand on.",
         given="A tiktok_th order whose line_item_details is empty, but whose item_price and "
               "paid_price are non-zero.",
         then=["Create accepted, Status 'New'.",
               "One row in orders.",
               "One price detail push, accepted, mapped flat from the item's own fields: base "
               "200000, seller discount 5000, platform discount 10000."]),

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

]


# ---------------------------------------------------------------------------------- suite

SUITE = flow_suite(
    suite_id="create-order-tiktok",
    name="createOrder - TikTok pricing",
    description="Anchanto OMS -> JPluger -> Eton WMS, TikTok: 7 cases "
                "(5 production intakes + 2 structural)",
    cases=CASES,
)


if __name__ == "__main__":
    from suite.run import main
    sys.exit(main(__file__, sys.argv[1:]))
