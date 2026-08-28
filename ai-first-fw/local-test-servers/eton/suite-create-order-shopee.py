#!/usr/bin/env python3
"""createOrder, Shopee: the adjustments{} hash matched onto order items by SKU.

Shopee is the only channel that prices from an order-level hash rather than from the order items,
so its whole mapping is a join: `data.order_adjustment.adjustments` states the order totals and one
entry per ordered line, and each entry has to find the line it belongs to. Every case here is
about that join or about what the entries say.

Five of the seven cases are masked production intakes from `eton/intakes/`, and each one states the
whole pushed body -- every order-level component and every line. Those numbers are not invented:
they are what the mapper produces from the payload OMS actually sent. Three are orders that were
pushed wrong in production:

    P1  an adjustments entry stating quantity_purchased 2 -- pushed as 408000, not 204000
    P2  a priced line and its zero-priced twin sharing an SKU -- 225000 pushed twice
    P8  the gift's discount read from the short field -- a 1000000 gift pushed at full list

    python3 eton/suite-create-order-shopee.py                 all 7 cases
    python3 eton/suite-create-order-shopee.py P8 N17          only the cases named
    python3 eton/suite-create-order-shopee.py --judge eton/test-results/create-order-shopee/run-...

Requires the app on ${APP}, the mock on ${MOCK} (`python3 mock.py eton`), and the seed in the
database the app itself reads. Preflight names whichever is missing.

Inherited from `suite-create-order.py` when the suite was split per marketplace, keeping the case
ids: P1, P2, P3, N1 and N17. P8 and P9 are new, which is why the P numbering is not contiguous per
channel -- an id is never reused or renumbered, so a run recorded before the split still lines
up."""

import os
import sys

# create_order is a sibling module, and a suite file is started from wherever the caller happens to be.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from create_order import (BLOCKED_ON_RECOVER, DELETE, blank_marketplace_sku, case, flow_suite, item,
                      prod_case)


CASES = [
    # ------------------------------------- production intakes
    prod_case("P1", "P1. Shopee - an adjustments entry for 2 units is a line total",
              "92000301", "SO-ETON-CO-P1-SHOPEE-QTY2", "shopee-qty2-entry",
              expect={
                  "order_totals": {
                      "OrderBasePrice": 457000,
                      "OrderSellerDiscount": 0,
                      "OrderSellerVoucher": 36560,
                      "OrderPlatformDiscount": 0,
                      "OrderPlatformVoucher": 67271,
                      "OrderCoinsOrCashback": 3600,
                      "ShippingFee": 0,
                      "ShippingDiscountSeller": 0,
                      "ShippingDiscountPlatform": 0,
                      "ServiceFee": 26124,
                      "Tax": 0,
                      "UnclassifiedDiscount": 0,
                      "UnclassifiedFee": 0,
                      "CurrencyCode": "VND",
                  },
                  "item_lines": [
                      ("1023146", 1, 78000, 0, 6240, 0, 11482, 700),
                      ("1023253", 4, 204000, 0, 16320, 0, 30030, 1700),
                      ("1023253", 2, 102000, 0, 8160, 0, 15015, 900),
                      ("1023210", 1, 73000, 0, 5840, 0, 10744, 300),
                  ],
                  "lines_sum_to_order": True, "promo_within_base": True},
              note="The order the double-count was found on. Its second entry states "
                   "quantity_purchased 2 and original_price 204000; the mapper scaled that amount "
                   "by the quantity and pushed 408000, against an order level of 457000 that was "
                   "already right. Eton accepted it -- its only per-line check is the promo "
                   "against that line's own base, and inflating the base keeps that legal -- so "
                   "the WMS held a figure 204000 too high and nothing failed. Also the one case "
                   "where an entry is matched on item_sku rather than model_sku.",
              given="A shopee_vn order of four lines, two of them kits, whose adjustments block "
                    "states one entry per ordered line -- amounts already totalled per line, not "
                    "per unit.",
              then=["Create accepted, Status 'New'; one row in orders; one push accepted.",
                    "Items[1].BasePrice is 204000 -- the entry's own figure, unscaled.",
                    "Both kit lines are priced under their component SKU 1023253, with the kit "
                    "quantity multiplied through: 4 units and 2.",
                    "The four line totals sum to OrderBasePrice 457000."]),

    prod_case("P2", "P2. Shopee - a shared entry is claimed by one line only",
              "92000311", "SO-ETON-CO-P2-SHOPEE-TWIN", "shopee-shared-entry",
              expect={
                  "order_totals": {
                      "OrderBasePrice": 225000,
                      "OrderSellerDiscount": 0,
                      "OrderSellerVoucher": 18000,
                      "OrderPlatformDiscount": 0,
                      "OrderPlatformVoucher": 37260,
                      "OrderCoinsOrCashback": 0,
                      "ShippingFee": 0,
                      "ShippingDiscountSeller": 0,
                      "ShippingDiscountPlatform": 0,
                      "ServiceFee": 14385,
                      "Tax": 0,
                      "UnclassifiedDiscount": 0,
                      "UnclassifiedFee": 0,
                      "CurrencyCode": "VND",
                  },
                  "item_lines": [
                      ("1027575", 15, 225000, 0, 18000, 0, 37260, 0),
                      ("1027575", 15, 0, 0, 0, 0, 0, 0),
                  ],
                  "lines_sum_to_order": True, "promo_within_base": True},
              note="The second way the same mapping over-reported. OMS emits a free gift as a "
                   "second line carrying the same marketplace SKU at a zero price, and matching "
                   "was stateless first-match, so both lines took the single adjustments entry in "
                   "full -- 225000 pushed twice against an order level of 225000. Entries are now "
                   "claimed by one line each, dearest first, so a contested entry lands on the "
                   "line that carries the money.",
              given="A shopee_vn order of two lines -- one priced, one a zero-priced gift -- both "
                    "carrying model SKU 1027575_CB15, against an adjustments block holding a "
                    "single entry.",
              then=["Create accepted, Status 'New'; one row in orders; one push accepted.",
                    "Items[0] takes the entry in full: BasePrice 225000.",
                    "Items[1] is the gift and takes nothing: every amount 0.",
                    "The lines sum to OrderBasePrice 225000, not to twice it."]),

    prod_case("P3", "P3. Shopee - the order discount is not the seller voucher",
              "92000321", "SO-ETON-CO-P3-SHOPEE-DISCOUNT", "shopee-order-discount",
              expect={
                  "order_totals": {
                      "OrderBasePrice": 130000,
                      "OrderSellerDiscount": 3900,
                      "OrderSellerVoucher": 6000,
                      "OrderPlatformDiscount": 0,
                      "OrderPlatformVoucher": 14412,
                      "OrderCoinsOrCashback": 0,
                      "ShippingFee": 0,
                      "ShippingDiscountSeller": 0,
                      "ShippingDiscountPlatform": 0,
                      "ServiceFee": 9606,
                      "Tax": 0,
                      "UnclassifiedDiscount": 0,
                      "UnclassifiedFee": 0,
                      "CurrencyCode": "VND",
                  },
                  "item_lines": [
                      ("1024505", 2, 130000, 3900, 6000, 0, 14412, 0),
                      ("1024505", 1, 0, 0, 0, 0, 0, 0),
                  ],
                  "lines_sum_to_order": True, "promo_within_base": True},
              note="The only Shopee intake here whose OrderSellerDiscount is not zero, and the "
                   "one that separates two figures carried under the same name at two different "
                   "depths: adjustments.seller_discount is 3900 and belongs to "
                   "OrderSellerDiscount, while order_adjustment.seller_discount is 6000 and is "
                   "the seller voucher -- the field the TikTok reader takes its order discount "
                   "from. Reading the outer one here would state 6000 twice and lose 3900.",
              given="A shopee_vn order carrying both a seller discount and a seller voucher, of "
                    "different amounts, plus the zero-priced gift beside its kit line.",
              then=["Create accepted, Status 'New'; one row in orders; one push accepted.",
                    "OrderSellerDiscount is 3900 and OrderSellerVoucher 6000 -- not the same "
                    "number twice.",
                    "Items[0] carries both, against a base of 130000 that covers them.",
                    "The lines sum to OrderBasePrice 130000."]),

    # ------------------------------------------------------- production intakes: Lazada

    prod_case("P8", "P8. Shopee - the gift's discount is only in the order-level field",
              "92000371", "SO-ETON-CO-P8-SHOPEE-GIFT", "shopee-gift-discount",
              expect={
                  "order_totals": {
                      "OrderBasePrice": 1612000,
                      "OrderSellerDiscount": 1000000,
                      "OrderSellerVoucher": 40000,
                      "OrderPlatformDiscount": 0,
                      "OrderPlatformVoucher": 91520,
                      "OrderCoinsOrCashback": 0,
                      "ShippingFee": 0,
                      "ShippingDiscountSeller": 0,
                      "ShippingDiscountPlatform": 0,
                      "ServiceFee": 34460,
                      "Tax": 0,
                      "UnclassifiedDiscount": 0,
                      "UnclassifiedFee": 0,
                      "CurrencyCode": "VND",
                  },
                  "item_lines": [
                      ("1023253", 12, 612000, 0, 40000, 0, 91520, 0),
                      ("HOPCOM", 1, 1000000, 1000000, 0, 0, 0, 0),
                  ],
                  "lines_sum_to_order": True, "promo_within_base": True},
              note="The reason OrderSellerDiscount is read from adjustments.order_seller_discount "
                   "and not from adjustments.seller_discount. The shorter field covers the ordered "
                   "lines only and states 0 here, while the gift's own entry in items[] states its "
                   "1000000 in full -- so reading it put the order level at 0 against lines "
                   "summing to 1000000, which is the disagreement Eton rejects. It also priced a "
                   "1000000 gift at full list with nothing against it. 38 orders in one month were "
                   "wrong this way, every one of them by exactly 1000000, and every one of them "
                   "also carried a bogus UnclassifiedDiscount of the same amount -- which is what "
                   "the 0 below pins.",
              given="A shopee_vn order of two lines: a kit of 12 units and a 1000000 add-on-deal "
                    "gift, against an adjustments block whose order_seller_discount is 1000000 and "
                    "whose seller_discount is 0.",
              then=["Create accepted, Status 'New'; one row in orders; one push accepted.",
                    "OrderSellerDiscount is 1000000 -- the order-level field, not the 0 beside it.",
                    "The gift line carries its own 1000000 discount against its own 1000000 base, "
                    "so it is given away rather than charged for.",
                    "UnclassifiedDiscount is 0: nothing is left over once the gift is accounted "
                    "for.",
                    "The two lines sum to OrderBasePrice 1612000."]),

    prod_case("P9", "P9. Shopee - a kit divides unevenly between three components",
              "92000381", "SO-ETON-CO-P9-SHOPEE-KIT3", "shopee-kit-three-components",
              expect={
                  "order_totals": {
                      "OrderBasePrice": 105000,
                      "OrderSellerDiscount": 0,
                      "OrderSellerVoucher": 0,
                      "OrderPlatformDiscount": 0,
                      "OrderPlatformVoucher": 5000,
                      "OrderCoinsOrCashback": 0,
                      "ShippingFee": 0,
                      "ShippingDiscountSeller": 0,
                      "ShippingDiscountPlatform": 0,
                      "ServiceFee": 8775,
                      "Tax": 0,
                      "UnclassifiedDiscount": 0,
                      "UnclassifiedFee": 0,
                      "CurrencyCode": "VND",
                  },
                  "item_lines": [
                      ("1023163", 1, 38640, 0, 0, 0, 1840, 0),
                      ("1023165", 1, 28560, 0, 0, 0, 1360, 0),
                      ("1023168", 1, 37800, 0, 0, 0, 1800, 0),
                  ],
                  "lines_sum_to_order": True, "promo_within_base": True},
              note="Every other kit in these intakes has one component, or components at equal "
                   "prices, so the share is 1 or a clean half and a proration bug would not show. "
                   "Here the components are priced 46000 / 34000 / 45000 against a parent of "
                   "105000, so all three shares are repeating fractions and the platform voucher "
                   "splits 1840 / 1360 / 1800. The one case where the kit shares are stated "
                   "against real component prices rather than round numbers.",
              given="A shopee_vn order of one kit line whose three components are priced "
                    "46000, 34000 and 45000 -- none of them a whole fraction of the 105000 parent.",
              then=["Create accepted, Status 'New'; one row in orders; one push accepted.",
                    "Three lines are pushed, one per component, under the component SKUs.",
                    "Each line's base is its own share of the parent: 38640, 28560 and 37800.",
                    "The platform voucher is prorated the same way: 1840, 1360 and 1800.",
                    "The three lines sum to OrderBasePrice 105000 exactly, despite every share "
                    "being a repeating fraction."]),

    # --------------- the join, and the channel without a hash
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

    prod_case("N17", "N17. Blank marketplace SKU - no line inherits another's prices",
              "92000017", "SO-ETON-CO-N17-BLANK-SKU", "shopee-qty2-entry",
              extra=blank_marketplace_sku("shopee-qty2-entry", 2),
              expect={
                  "item_lines": [
                      ("1023146", 1, 78000, 0, 6240, 0, 11482, 700),
                      ("1023253", 4, 204000, 0, 16320, 0, 30030, 1700),
                      ("1023253", 2, 0, 0, 0, 0, 0, 0),
                      ("1023210", 1, 73000, 0, 5840, 0, 10744, 300),
                  ],
                  "promo_within_base": True, "lines_sum_to_order": False},
              note="Every adjustments entry in a real Shopee payload carries an empty item_sku — "
                   "three of the four in this intake do. Matching guarded only against null, so "
                   "an OMS line whose own SKU was blank matched the first such entry and "
                   "inherited its prices. A blank SKU now matches nothing, which makes this the "
                   "one case where the two levels of the payload are meant to disagree: the order "
                   "level is read straight off the adjustments block and still states the whole "
                   "order, while the unmatched line contributes nothing to the line total. The "
                   "102000 gap is the point, not a fault.",
              given="The P1 intake with the third line's marketplace SKU emptied, against an "
                    "adjustments block whose entries carry item_sku ''.",
              then=["Create accepted, one row in orders, one price detail push accepted.",
                    "Items[1] still takes its own entry: 204000.",
                    "Items[2] is 0 — the blank SKU matches nothing rather than inheriting the "
                    "first entry that has a blank item_sku.",
                    "The lines sum to 355000 against an order level of 457000, and that "
                    "disagreement is what an unmatchable line is supposed to look like."]),

]


# ---------------------------------------------------------------------------------- suite

SUITE = flow_suite(
    suite_id="create-order-shopee",
    name="createOrder - Shopee pricing",
    description="Anchanto OMS -> JPluger -> Eton WMS, Shopee: 7 cases "
                "(5 production intakes + 2 structural)",
    cases=CASES,
)


if __name__ == "__main__":
    from suite.run import main
    sys.exit(main(__file__, sys.argv[1:]))
