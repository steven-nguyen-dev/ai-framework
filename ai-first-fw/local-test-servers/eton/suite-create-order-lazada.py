#!/usr/bin/env python3
"""createOrder, Lazada: order_items[] with one detail row per unit.

Lazada carries its pricing on the order items themselves -- `line_item_details[]`, one row per unit
-- so there is no join to get wrong and no order-level hash to read the wrong field of. The mapping
is a sum, and what these cases pin is that it sums the right rows and explodes a kit correctly
while doing it.

The smallest of the four createOrder suites, and honestly so: both cases are masked production
intakes from `eton/intakes/`, and Lazada has no structural case of its own -- the failure and
transport cases are channel-agnostic and live in `suite-create-order.py`. Neither of these two is
an order that was pushed wrong; they are here because the seven-line order and the kit-plus-gift
order are the two shapes Lazada actually sends.

    python3 eton/suite-create-order-lazada.py                 both cases
    python3 eton/suite-create-order-lazada.py P5              only the case named
    python3 eton/suite-create-order-lazada.py --judge eton/test-results/create-order-lazada/run-...

Requires the app on ${APP}, the mock on ${MOCK} (`python3 mock.py eton`), and the seed in the
database the app itself reads. Preflight names whichever is missing.

Inherited from `suite-create-order.py` when the suite was split per marketplace, keeping the case
ids: P4 and P5."""

import os
import sys

# create_order is a sibling module, and a suite file is started from wherever the caller happens to be.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from create_order import (BLOCKED_ON_RECOVER, DELETE, blank_marketplace_sku, case, flow_suite, item,
                      prod_case)


CASES = [
    # ------------------------------------- production intakes
    prod_case("P4", "P4. Lazada - seven lines, one detail row per unit",
              "92000331", "SO-ETON-CO-P4-LAZADA-SEVEN", "lazada-seven-lines",
              expect={
                  "order_totals": {
                      "OrderBasePrice": 272400,
                      "OrderSellerDiscount": 0,
                      "OrderSellerVoucher": 13620,
                      "OrderPlatformDiscount": 0,
                      "OrderPlatformVoucher": 20702,
                      "OrderCoinsOrCashback": 0,
                      "ShippingFee": 31500,
                      "ShippingDiscountSeller": 0,
                      "ShippingDiscountPlatform": 0,
                      "ServiceFee": 0,
                      "Tax": 23975,
                      "UnclassifiedDiscount": 0,
                      "UnclassifiedFee": 0,
                      "CurrencyCode": "VND",
                  },
                  "item_lines": [
                      ("1024081", 2, 94000, 0, 4700, 0, 7144, 0),
                      ("1023222", 1, 26000, 0, 1300, 0, 1976, 0),
                      ("1023221", 1, 26000, 0, 1300, 0, 1976, 0),
                      ("1023786", 1, 26000, 0, 1300, 0, 1976, 0),
                      ("1023926", 1, 46000, 0, 2300, 0, 3496, 0),
                      ("1023025", 1, 23400, 0, 1170, 0, 1778, 0),
                      ("1023220", 1, 31000, 0, 1550, 0, 2356, 0),
                  ],
                  "lines_sum_to_order": True, "promo_within_base": True},
              note="The widest real order in the set, and the one that pins the per-unit detail "
                   "rows: its first line is 2 units and carries two rows of 2350 each, so the "
                   "reader has to sum them to 4700 rather than take the first. Lazada reports no "
                   "discount, coin or service fee at all, which is why five order-level "
                   "components are zero here and have to stay zero rather than be filled from a "
                   "neighbouring field.",
              given="A lazada_vn order of seven plain lines, each carrying its pricing in "
                    "order_items[].line_item_details, the first with one row per unit.",
              then=["Create accepted, Status 'New'; one row in orders; one push accepted.",
                    "Items[0].SellerVoucher is 4700 -- both detail rows, summed.",
                    "Tax 23975 and ShippingFee 31500 are summed across the seven lines; shipping "
                    "comes from each item's own shipping_amount, since shipping_fee_original is 0 "
                    "on every Lazada detail row.",
                    "The seven line totals sum to OrderBasePrice 272400."]),

    prod_case("P5", "P5. Lazada - a kit line and the gift beside it",
              "92000341", "SO-ETON-CO-P5-LAZADA-KIT", "lazada-kit-and-gift",
              expect={
                  "order_totals": {
                      "OrderBasePrice": 175000,
                      "OrderSellerDiscount": 0,
                      "OrderSellerVoucher": 0,
                      "OrderPlatformDiscount": 0,
                      "OrderPlatformVoucher": 14000,
                      "OrderCoinsOrCashback": 0,
                      "ShippingFee": 0,
                      "ShippingDiscountSeller": 0,
                      "ShippingDiscountPlatform": 0,
                      "ServiceFee": 0,
                      "Tax": 29272,
                      "UnclassifiedDiscount": 0,
                      "UnclassifiedFee": 0,
                      "CurrencyCode": "VND",
                  },
                  "item_lines": [
                      ("1025377", 5, 175000, 0, 0, 0, 14000, 0),
                      ("1025377", 1, 0, 0, 0, 0, 0, 0),
                  ],
                  "lines_sum_to_order": True, "promo_within_base": True},
              note="Lazada's own twin: the gift line carries no detail rows at all, so the "
                   "per-line reader has nothing to read there and must produce zeros rather than "
                   "fall back to the item's flat fields, which repeat the whole order's tax on "
                   "every line. Tax is the figure that shows it -- 29272 is the two lines' flat "
                   "copies summed, which is what the order level is built from, while the lines "
                   "themselves carry no tax at all.",
              given="A lazada_vn order of a five-component kit line with detail rows, and a "
                    "zero-priced gift line whose line_item_details is empty.",
              then=["Create accepted, Status 'New'; one row in orders; one push accepted.",
                    "Both lines are priced under the component SKU 1025377, 5 units and 1.",
                    "Items[1] carries nothing: base 0 and no voucher.",
                    "The lines sum to OrderBasePrice 175000."]),

    # ------------------------------------------------------- production intakes: TikTok

]


# ---------------------------------------------------------------------------------- suite

SUITE = flow_suite(
    suite_id="create-order-lazada",
    name="createOrder - Lazada pricing",
    description="Anchanto OMS -> JPluger -> Eton WMS, Lazada: 2 cases "
                "(2 production intakes)",
    cases=CASES,
)


if __name__ == "__main__":
    from suite.run import main
    sys.exit(main(__file__, sys.argv[1:]))
