#!/usr/bin/env python3
"""Northern Ireland shipment: a warehouse posts an order, JPluger creates the shipment on DPD UK.

Thirty-seven cases fired at `POST /jpluger/carrier/orders` on the DPD UK integration app and judged
against the DPD mock's call log, the `corders` table and the app's own answer. The transport is
synchronous -- carrier-core's OrdersController calls DpdUKCarrierService and returns its response --
so what the app answers is evidence here, unlike an order published onto Kafka.

What the cases are for: IA-4752 / IA-5213 moved the customs invoice onto the Northern Ireland route.
Every mapping that ticket added is pinned here against the payload as it reaches DPD, and every
pre-submission refusal DpdUKUtility.validateShipment can raise has a case that provokes it.

    python3 dpd-uk/suite-ni-shipment.py                 all 37 cases, ~2 min
    python3 dpd-uk/suite-ni-shipment.py N1 R3           only the cases named
    python3 dpd-uk/suite-ni-shipment.py --list          the cases and what each expects
    python3 dpd-uk/suite-ni-shipment.py --judge dpd-uk/test-results/ni-shipment/run-…

Requires the app on ${APP}, the mock on ${MOCK} (`python3 mock.py dpd-uk`), and the seed in the
schema the app itself reads. Preflight names whichever is missing.

**The app has to be pointed at the mock.** `DPD_UK_BASE_URL` defaults to `https://api.dpd.co.uk/`
in application-local.properties, and nothing in this suite can override it -- start the app with
`-DDPD_UK_BASE_URL=http://127.0.0.1:23102/`. A run where every case reports "no shipment call" and
the mock's log is empty is that setting, not a mapping defect.

The engine, the check vocabulary and the runner contract: `suite/` and `TESTING.md`. What the mock
answers and why: `dpd-uk/README.md`. Where each field comes from:
`JPluger/.scratchpads/IA-4752-dpd/mapping-plan.md`.
"""

import os
import re
import shutil
import sys

# The engine is a sibling package, and a suite file is started from wherever the caller happens to
# be -- the /test page starts it from the mock's own folder.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from suite import (Blocked, Calls, Case, Custom, DELETE, Group, Marker, MySql, PostJson, Rows, Sql,
                   Status, Suite, merge)
from suite import AppResponds, DatabaseResponds, MockResponds, Probe, SeedRows

PACKAGE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ------------------------------------------------------------------------------------ settings

# Every one of these is overridden by an environment variable of the same name.
ENV = {
    # server.port in dpdUK-integration's application-local.properties, TLS from carrier-core's
    # ${user.dir}/../certs/Cert.p12. The HTTP connector is on 4001 if TLS is in the way.
    "APP": "https://localhost:3001",
    "MOCK": "http://127.0.0.1:23102",
    # carrier-core's application-core-local.properties datasource, with ddl-auto=none.
    "DB_NAME": "carrier_integrations_test",
    "CORE_JSON": os.path.join(PACKAGE, "core.json"),
    # Whether the label HTML can be turned into a PDF on this machine -- see LABEL_CONVERSION.
    "WKHTMLTOPDF": os.environ.get("WKHTMLTOPDF")
                   or ("present" if shutil.which("wkhtmltopdf") else "absent"),
}

SUCCESS_MESSAGE = "Order Created Successfully"          # GlobalConstant.GENERIC_SUCCESS_MESSAGE
FAILED_IN_APP = "Something went wrong"                  # GlobalConstant.GENERIC_ERROR_MESSAGE

# DpdUKCarrierService fetches both labels, converts the HTML one with wkhtmltopdf, splits the PDF
# per parcel and only then reports the shipment to the product and writes the `corders` row. Without
# the binary the conversion throws into the catch-all, so the last two assertions of every
# successful case cannot be made -- the shipment on DPD is unaffected and every mapping check still
# holds. Those cases are reported `blocked`, never `pass`, so a machine without it never reads as
# proof. Install it (`brew install --cask wkhtmltopdf`) to run them out.
LABEL_CONVERSION = ENV["WKHTMLTOPDF"] == "present"

ABSENT = "absent"                                       # what a field Gson dropped reads as
WEIGHT_TOLERANCE_KG = 0.001    # DpdUKConstants.WEIGHT_RECONCILIATION_TOLERANCE_KG


# ------------------------------------------------------------------------------------ payloads

# One order every case starts from: a Great Britain warehouse shipping two apparel lines in one
# package to a Belfast business that holds a UK Internal Market Scheme number. A case states only
# what it changes, so the difference between two cases is the whole of what distinguishes them.
ORDER = {
    "event_parameters": {
        "seller_code": "RPTH",
        "seller_id": 42,
        "zone_id": 0,
        "event_name": "logistics_partner_order_update",
        "logistics_partner_code": "dpd_uk",
    },
    "data": {
        "is_multi_parcel_not_supported": False,
        "order_id": 9001,
        "shipment_id": 4501,
        "order_number": "DPDUK-NI-B2B-NAR-01",
        "shipment_number": "DPDUK-NI-B2B-NAR-01",
        "customer_first_name": "Rukphong Thailand Ltd",
        "customer_last_name": None,
        "company_name": "Rukphong Thailand Ltd",
        "company_code": "RPTH",
        "tracking_number": "TRK123456789",
        "awb_number": "TRK123456789",
        "is_cod": False,
        "special_instruction": "Leave at reception",
        "shipping_amount": "2.0",
        "tax_amount": "0.0",
        "country_code": "GB",
        "items_count": 2,
        # DpdUKUtility.collectionDateMapping counts seconds from midnight to this instant and asks
        # the seller's dispatch slots for the one holding it. The seeded slot spans everything, so a
        # fixed date stays usable; see seed-data/dpd_uk_local_seed_data.sql.
        "order_date": "2026-08-10 09:12:00 UTC",
        "order_date_in_smp_timezone": "2026-08-13 11:41:02 +0100",
        "order_type": "b2b",
        "type_of_goods": "Apparel",
        "trade_terms": "DAP",
        "delivery_date": "2026-08-14",
        "total_packages": 1,
        "shipment_weight": 0.65,
        "total_declared_value": 42.0,

        # The Northern Ireland block IA-5213 added. `ukims_holder` is left unnamed: exactly one
        # party carries a number in the base order, which is what makes the holder unambiguous.
        "consumer_type": "business",
        "risk_status": "not_at_risk",
        "ukims_holder": None,
        "sender_ukims": None,
        "incoterm": "DAP",
        "carrier_incoterm": "DAP",
        "customs_currency": "GBP",
        "total_customs_value": 36.0,
        "invoice_number": None,
        "eori_no": "GB123456789000",
        "buyer_eori": "GB987654321000",
        "company_vat_no": "GB999888777",
        "sender_tax_id": "GB123456789",

        "shipping_address": {
            "first_name": "Aoife", "last_name": "Byrne",
            "address1": "14 Royal Avenue", "address2": "Suite 3", "address3": "",
            "city": "Belfast", "post_code": "BT1 1DA", "phone": "442890123456",
            "state_name": "Northern Ireland", "country": "United Kingdom", "country_code": "GB",
            "business_name": "Byrne Retail Ltd", "company_name": None,
            "customer_email": "buyer@customer.example.com",
            "receiver_tax_id": None,
            "receiver_ukims": "XIUKIM47700000000000000000001",
        },
        "billing_address": {
            "first_name": "Aoife", "last_name": "Byrne", "address1": "14 Royal Avenue",
            "address2": "Suite 3", "city": "Belfast", "post_code": "BT1 1DA",
            "phone": "442890123456", "state_name": "Northern Ireland",
            "country": "United Kingdom", "country_code": "GB",
            "customer_email": "buyer@customer.example.com",
        },
        "pickup_address": {
            "first_name": "Warehouse", "last_name": "Admin",
            "address1": "Unit 7, Trade Park", "address2": "Industrial Estate", "address3": "",
            "city": "Manchester", "post_code": "M1 2AB", "phone": "441612345678",
            "state_name": "England", "country": "United Kingdom", "country_code": "GB",
            "company_name": "Rukphong Thailand Ltd",
            "company_business_name": "Rukphong Thailand Ltd",
            "warehouse_name": "ABC Warehousing Company",
            "seller_email": "warehouse@rukphong.example.com",
        },
        # `<label>/<networkCode>`: DpdUKUtility.resolveNetworkCode reads what follows the slash.
        # 1^12 is a domestic next-day network, which is what a Northern Ireland shipment travels on
        # -- and why the invoice cannot be gated on the international network codes.
        "shipping_method": {
            "fulfilment_code": "DPD_UK/1^12",
            "logistics_partner_code": "dpd_uk",
            "country": "United Kingdom", "country_id": 78,
            "update_status": True, "is_self_service": False, "combined_with_invoice": False,
        },
        "order_items": [],
    },
    "headers": {"signature": "TEST_SIGNATURE"},
}


def item(order_item_id, name, sku, hs_code, unit_customs_value, product_cost, weight, quantity,
         item_price, **extra):
    """One order line, as the warehouse states it.

    `unit_customs_value` is the ex-VAT value of a single unit and is what DPD is told; `item_price`
    is the VAT-inclusive line total and is only the last resort. `product_cost` stands in for a free
    sample.
    """
    line = {
        "order_item_id": order_item_id, "name": name, "sku": sku, "inventory_sku": sku,
        "quantity": quantity, "item_price": item_price, "unit_price": item_price / quantity,
        "paid_price": item_price, "selling_price": item_price,
        "weight": weight, "currency": "GBP", "uom": "EA", "status": "packed",
        "country_origin_code": "GB", "hs_code": hs_code,
        "unit_customs_value": unit_customs_value, "product_cost": product_cost,
        "shipping_charges": 0.0, "tax_amount": "0.0",
        "item_description": None, "product_type": None, "composition": None, "product_url": None,
        "kit_details": [], "line_item_details": [], "discounts": [],
    }
    line.update(extra)
    return line


def packed(sku, name, hs_code, unit_customs_value, product_cost, weight, quantity, price):
    """One line inside a physical package -- what `CartonItems` carries."""
    return {
        "product_sku": sku, "product_name": name, "quantity": quantity, "price": price,
        "unit_price": price / quantity, "shipping_charges": 0.0,
        "origin_location_code": "GB", "origin_location_name": "United Kingdom",
        "hs_tariff_code": hs_code, "HsCode": hs_code, "source_hs_code": hs_code,
        "unit_customs_value": unit_customs_value, "product_cost": product_cost,
        "product_weight_in_kg": weight, "product_length_in_cm": 30, "product_height_in_cm": 2,
        "product_width_in_cm": 25, "uom": "EA", "status": "packed",
    }


def package(actual_weight, reference, carton_items):
    """One physical package -- a `WeightInfoList` entry, which becomes one DPD parcel."""
    return {"ActualWeight": actual_weight, "PackageReference": reference,
            "PackageHeight": 100, "PackageLength": 300, "PackageWidth": 200,
            "PackageVolume": 6000000, "Pkg": "Box - Medium", "CartonItems": carton_items,
            "Value": 42.0}


def packages(*groups):
    """`package_details` as the warehouse sends it: package groups, each holding its packages."""
    return {"ShipmentPackageList": [{"HawbNo": "TRK123456789", "WeightInfoList": list(group)}
                                    for group in groups]}


SHIRT = item(771, "Cotton T-Shirt", "SKU-001", "610910", 6.0, 4.0, 0.25, 2, 20.0,
             product_type="Apparel", composition="100% cotton")
SCARF = item(772, "Wool Scarf", "SKU-002", "621410", 24.0, 12.0, 0.15, 1, 30.0)

PACKED_SHIRT = packed("SKU-001", "Cotton T-Shirt", "610910", 6.0, 4.0, 0.25, 2, 20.0)
PACKED_SCARF = packed("SKU-002", "Wool Scarf", "621410", 24.0, 12.0, 0.15, 1, 30.0)

ONE_PACKAGE = packages([package(0.65, "CTN-0001", [PACKED_SHIRT, PACKED_SCARF])])


def order(number, items=None, packed_as=None, data=None):
    """The payload for one case: the base order with its identity, its lines and its packages."""
    override = {"data": {"order_number": number, "shipment_number": number,
                         "order_items": list(items if items is not None else [SHIRT, SCARF]),
                         "package_details": packed_as if packed_as is not None else ONE_PACKAGE}}
    merged = merge(ORDER, override)
    # Applied against the merged order, because a case removing a key the base carries has to be
    # merged into something that has it.
    return merge(merged, {"data": data}) if data else merged


def case(cid, name, number, expect, items=None, packed_as=None, data=None, shape="northern ireland",
         **rest):
    """One case, keyed by the order number.

    Every call of one case is recoverable from that number: DpdUKUtility sends it as
    `consignment[0].consignmentRef`, and the mock echoes it back inside the shipmentId the label
    calls then address. The `corders` rows carry it as well.
    """
    return Case(cid, name, payload=order(number, items, packed_as, data), key=number,
                row_key=number, shape=shape, wait=0, expect=expect,
                detail={"order_number": number}, **rest)


# ------------------------------------------------------------------- what reached the wire

def shipment_payload(evidence):
    """The body of the first shipment request, or None when the case sent none."""
    calls = evidence.calls.get("shipment", [])
    if not calls:
        return None
    body = calls[0].request_body
    return body if isinstance(body, dict) else None


def dig(document, path):
    """One value out of the payload by dotted path, or ABSENT.

    Gson drops a null, so "the field is not on the wire" and "the field was never set" are one
    observation -- which is exactly what a check on this integration has to state.
    """
    current = document
    for step in path.split("."):
        if isinstance(current, list) and step.lstrip("-").isdigit():
            index = int(step)
            if not -len(current) <= index < len(current):
                return ABSENT
            current = current[index]
        elif isinstance(current, dict) and step in current:
            current = current[step]
        else:
            return ABSENT
    return current


def item_lines(document):
    """Every parcelProduct of every parcel of the first consignment, in the order sent."""
    lines = []
    for parcel in dig(document, "consignment.0.parcel") or []:
        for line in (parcel.get("parcelProduct") if isinstance(parcel, dict) else None) or []:
            lines.append(line)
    return lines


def payload_check(label, what, path, expect):
    """A check on one value of the shipment payload as DPD received it."""
    def read(case, evidence):
        want = case.expect.get(expect)
        body = shipment_payload(evidence)
        if want is None or body is None:
            return None
        got = dig(body, path)
        return want, got, got == want
    return Custom(label, what, read, expect=expect)


def line_check(label, what, field, expect):
    """A check on one field of every customs line, in the order the lines were sent."""
    def read(case, evidence):
        want = case.expect.get(expect)
        body = shipment_payload(evidence)
        if want is None or body is None:
            return None
        got = [line.get(field, ABSENT) for line in item_lines(body)]
        return want, got, got == want
    return Custom(label, what, read, expect=expect)


def parcels_reconcile(case, evidence):
    """`numberOfParcels` against the parcels actually sent, and the weight against its lines.

    DPD refuses a count that disagrees with the array and a package lighter than what is in it, and
    both are numbers this integration computes rather than copies -- so they are the two that can
    drift without any field being obviously wrong.
    """
    want = case.expect.get("parcels")
    body = shipment_payload(evidence)
    if want is None or body is None:
        return None
    stated = dig(body, "consignment.0.numberOfParcels")
    sent = len(dig(body, "consignment.0.parcel") or [])
    weight = dig(body, "consignment.0.totalWeight")
    lines = sum(line.get("unitWeight", 0) * line.get("numberOfItems", 0)
                for line in item_lines(body))
    got = {"numberOfParcels": stated, "parcel[]": sent, "totalWeight": weight,
           "sum of unitWeight x numberOfItems": round(lines, 3)}
    # The same gram of tolerance DpdUKConstants.WEIGHT_RECONCILIATION_TOLERANCE_KG allows. Three
    # lines of 0.2 kg sum to 0.6000000000000001 in binary floating point, and a strict comparison
    # failed a shipment the integration -- and DPD -- consider balanced.
    ok = (stated == sent == want["parcel[]"] and weight == want["totalWeight"]
          and lines - weight <= WEIGHT_TOLERANCE_KG)
    return want, got, ok


def app_reply(case, evidence):
    """What the app told the product, read out of its own response body.

    A refusal is the message DpdUKUtility.validateShipment built, naming the field the product has
    to correct; a success is GlobalConstant.GENERIC_SUCCESS_MESSAGE. Note that carrier-core's
    GlobalUtility.renderResponse turns every status other than 200 and 401 into an HTTP 500, so the
    status alone cannot tell a refused payload from a failure inside the app -- the message can.
    """
    want = case.expect.get("app_says")
    if want is None or evidence.controller is None:
        return None
    # The success half of this assertion needs the label conversion, which is not on every machine.
    # Dropped rather than failed, and the case is `blocked` by BLOCKED_ON_LABEL_CONVERSION.
    if want == SUCCESS_MESSAGE and not LABEL_CONVERSION:
        return None
    body = evidence.controller.get("controller_body") or ""
    return want, body[:400] or "empty body", want.lower() in body.lower()


def status_sequence(case, evidence):
    """Every status the mock answered the shipment calls with, in order.

    The engine's Status check holds every answer to one expectation, which cannot state a first
    attempt that was refused and a second that was not -- the whole point of the GeoSession cases.
    """
    want = case.expect.get("shipment_statuses")
    calls = evidence.calls.get("shipment", [])
    if want is None or not calls:
        return None
    got = " ".join(str(call.status) for call in calls)
    return want, got, got == want


BLOCKED_ON_LABEL_CONVERSION = Blocked(
    when=lambda run: (run.meta.get("settings") or {}).get("WKHTMLTOPDF") != "present",
    reason="wkhtmltopdf is not on PATH, so the label HTML cannot be converted, the shipment is "
           "never reported to the product and no `corders` row is written. Everything DPD received "
           "is proven; the last leg is not. dpd-uk/tools holds a stand-in -- put it on the app's "
           "PATH and on this suite's, and the case runs out.")


# -------------------------------------------------------------------------------------- cases

# What a Northern Ireland shipment carries when nothing is wrong. Every other Northern Ireland case
# states only its own difference from this.
NI_MAPPED = {
    "shipment_calls": 1,
    "shipment_status": 200,
    "customs_flag": "Y",
    "terms": "DAP",
    "shipping_cost": "2.0",
    "invoice_reference": "DPDUK-NI-B2B-NAR-01",
    "customs_value": 36.0,
    "customs_currency": "GBP",
    "description": "Cotton T-Shirt|Wool Scarf",
    "delivery_street": "14 Royal Avenue",
    "delivery_locality": "Suite 3",
    "invoice_delivery_street": "14 Royal Avenue",
    "invoice_delivery_locality": "Suite 3",
    "consignment_collection_postcode": "M12AB",
    "consignment_delivery_postcode": "BT11DA",
    "skus": ["SKU-001", "SKU-002"],
    "shipper_county": "England",
    "delivery_county": "Northern Ireland",
    "delivery_organisation": "Byrne Retail Ltd",
    "shipper_postcode": "M12AB",
    "delivery_postcode": "BT11DA",
    "shipper_eori": "GB123456789000",
    "delivery_eori": "GB987654321000",
    "shipper_vat": "GB999888777",
    "is_business": True,
    "at_risk": False,
    "shipper_ukims": ABSENT,
    "delivery_ukims": "XIUKIM47700000000000000000001",
    "hs_codes": ["610910", "621410"],
    "unit_values": [6.0, 24.0],
    "unit_weights": [0.25, 0.15],
    "quantities": [2, 1],
    "origins": ["GB", "GB"],
    "descriptions": ["Cotton T-Shirt", "Wool Scarf"],
    "type_descriptions": ["Apparel", ABSENT],
    "fabrics": ["100% cotton", ABSENT],
    "parcels": {"parcel[]": 1, "totalWeight": 0.65},
    "label_calls": 2,
    "app_says": SUCCESS_MESSAGE,
    "db_rows": 1 if LABEL_CONVERSION else 0,
}


def refused(app_says, **rest):
    """A shipment the integration refuses before it is sent: nothing reaches DPD at all."""
    expect = {"shipment_calls": 0, "label_calls": 0, "app_says": app_says, "db_rows": 0}
    expect.update(rest)
    return expect


CASES = [
    case("N1", "N1. B2B receiver, goods not at risk - the whole mapping",
         "DPDUK-NI-B2B-NAR-01", expect=NI_MAPPED,
         note="The reference case for IA-4752. It is the one case that states every mapped field, "
              "so a regression anywhere in DpdUKUtility.createOrderOnDPDUK lands here first.",
         given="A Manchester warehouse shipping two apparel lines in one package to a Belfast "
               "business that holds a UKIMS number, with its own EORI number alongside it.",
         then=["generateCustomsData is Y even though the network code is the domestic 1^12.",
               "The invoice carries both parties, their EORI numbers and the sender's VAT number.",
               "The receiver is classified: isBusiness true, atRisk false, ukimsNumber sent.",
               "county comes from state_name, not from country, on both invoice addresses.",
               "The receiver's organisation is the business name, not the company name.",
               "customsValue is the stated total and customsCurrency is GBP.",
               "Both products are named in parcelDescription, pipe-separated.",
               "Each customs line carries its own commodity code, ex-VAT unit value and weight.",
               "The label is fetched twice - HTML for the PDF, Citizen CLP for the printer."]),

    case("N2", "N2. B2B receiver, goods at risk", "DPDUK-NI-B2B-AR-02",
         data={"risk_status": "at_risk"},
         expect=merge(NI_MAPPED, {"at_risk": True, "invoice_reference": "DPDUK-NI-B2B-AR-02"}),
         note="At risk is the flag that decides whether EU duty is due, and it is the only "
              "difference from N1 - so a mapping that ignores risk_status shows up as N1 passing "
              "and this failing.",
         given="The same shipment, with the goods declared at risk of moving into the EU.",
         then=["atRisk is true.",
               "No scheme number is required for the at-risk flow, but the one sent still stands."]),

    case("N3", "N3. Individual receiver", "DPDUK-NI-B2C-03",
         data={"consumer_type": "individual", "risk_status": None, "order_type": "b2c",
               "shipping_address": {"receiver_ukims": None, "business_name": None}},
         expect=merge(NI_MAPPED, {
             "is_business": False, "at_risk": ABSENT, "delivery_ukims": ABSENT,
             "delivery_organisation": ABSENT, "invoice_reference": "DPDUK-NI-B2C-03"}),
         note="A consumer has no risk status and no scheme number, and DPD rejects atRisk on a "
              "B2C invoice. Proves the two fields are omitted rather than sent false.",
         given="The same shipment to a private individual in Belfast.",
         then=["isBusiness is false.",
               "atRisk is absent from the wire, not false.",
               "No scheme number and no organisation are sent."]),

    case("N4", "N4. Delivered duty paid", "DPDUK-NI-DDP-04",
         data={"carrier_incoterm": None, "incoterm": "DDP", "trade_terms": "DDP"},
         expect=merge(NI_MAPPED, {"terms": "DT1", "invoice_reference": "DPDUK-NI-DDP-04"}),
         note="DPD names the duty-paid term DT1, not DDP. The translation is the whole of this "
              "case, and DAP - which every shipment carried before - is what a broken translation "
              "falls back to.",
         given="The same shipment, sold on DDP terms with no carrier term resolved upstream.",
         then=["invoiceTermsOfDelivery is DT1."]),

    case("N5", "N5. Two packages in two package groups", "DPDUK-NI-2PKG-05",
         packed_as=packages([package(0.5, "CTN-0001", [PACKED_SHIRT])],
                            [package(0.15, "CTN-0002", [PACKED_SCARF])]),
         data={"total_packages": 2, "shipment_weight": 0.65},
         expect=merge(NI_MAPPED, {
             "invoice_reference": "DPDUK-NI-2PKG-05",
             "parcels": {"parcel[]": 2, "totalWeight": 0.65},
             "unit_values": [6.0, 24.0], "unit_weights": [0.25, 0.15], "quantities": [2, 1],
             "hs_codes": ["610910", "621410"], "origins": ["GB", "GB"],
             "descriptions": ["Cotton T-Shirt", "Wool Scarf"],
             "type_descriptions": ["Apparel", ABSENT], "fabrics": ["100% cotton", ABSENT],
             "db_rows": 2 if LABEL_CONVERSION else 0}),
         note="A shipment can arrive as more than one package group, and the loop that gathers them "
              "used to let each group replace the last - one parcel travelled and the rest of the "
              "shipment was undeclared. Two groups of one package each is the shape that catches it.",
         given="The same two products, packed one per package, in two separate package groups.",
         then=["Two parcels are sent and numberOfParcels says two.",
               "Each parcel carries its own package's customs line.",
               "totalWeight is the sum of both packages and covers both lines."]),

    case("N6", "N6. Sender holds the scheme number", "DPDUK-NI-SENDER-UKIMS-6",
         data={"sender_ukims": "XIUKIM47700000000000000000009",
               "shipping_address": {"receiver_ukims": None}},
         expect=merge(NI_MAPPED, {
             "shipper_ukims": "XIUKIM47700000000000000000009", "delivery_ukims": ABSENT,
             "invoice_reference": "DPDUK-NI-SENDER-UKIMS-6"}),
         note="DPD accepts one party's scheme number and no more. With only the sender holding one "
              "it goes on the shipper, and the receiver's slot has to stay empty - the mirror of N1.",
         given="The same shipment, where the sender holds the scheme number and the receiver has none.",
         then=["ukimsNumber is on invoiceShipperDetails.",
               "invoiceDeliveryDetails carries no scheme number."]),

    case("D1", "D1. Great Britain domestic - no customs data at all",
         "DPDUK-GB-DOMESTIC-07", shape="domestic",
         data={"shipping_address": {"post_code": "M1 3CD", "city": "Manchester",
                                    "state_name": "England", "receiver_ukims": None},
               "consumer_type": None, "risk_status": None, "total_customs_value": None,
               "customs_currency": None},
         expect={"shipment_calls": 1, "shipment_status": 200, "customs_flag": ABSENT,
                 "invoice": ABSENT, "customs_value": ABSENT, "customs_currency": ABSENT,
                 "consignment_collection_postcode": "M12AB",
                 "consignment_delivery_postcode": "M13CD",
                 "parcels": {"parcel[]": 1, "totalWeight": 0.65},
                 "label_calls": 2, "app_says": SUCCESS_MESSAGE,
                 "db_rows": 1 if LABEL_CONVERSION else 0},
         note="The Windsor Framework data belongs to the Northern Ireland route only. A Manchester "
              "to Manchester shipment must be exactly what it was before IA-4752, and this is the "
              "case that says so - including that none of the new validation applies to it.",
         given="The same order, delivered inside Great Britain on the same domestic network code.",
         then=["No invoice and no generateCustomsData are sent.",
               "No customs value or currency is sent.",
               "The shipment is accepted with no classification data at all."]),

    case("D2", "D2. International network code - the invoice as it always was",
         "DPDUK-INTL-IE-08", shape="international",
         data={"shipping_method": {"fulfilment_code": "DPD_UK/1^19"},
               "shipping_address": {"country_code": "IE", "country": "Ireland",
                                    "post_code": "D02 AF30", "city": "Dublin",
                                    "state_name": "Leinster", "receiver_ukims": None},
               "consumer_type": None, "risk_status": None},
         expect={"shipment_calls": 1, "shipment_status": 200, "customs_flag": "Y",
                 "terms": "DAP", "shipping_cost": "0.0", "customs_value": 36.0,
                 "customs_currency": "GBP", "is_business": ABSENT, "at_risk": ABSENT,
                 "delivery_ukims": ABSENT, "shipper_ukims": ABSENT,
                 "consignment_collection_postcode": "M12AB",
                 "consignment_delivery_postcode": "D02AF30",
                 "parcels": {"parcel[]": 1, "totalWeight": 0.65},
                 "label_calls": 2, "app_says": SUCCESS_MESSAGE,
                 "db_rows": 1 if LABEL_CONVERSION else 0},
         note="One of the eight international network codes that carried a customs invoice before "
              "Northern Ireland existed. It must still get one, still with shippingCost 0 - the "
              "real carriage charge is stated on the Northern Ireland route alone, so no duty base "
              "moves for anyone else - and none of the Windsor Framework fields.",
         given="The same order to Dublin on network 1^19, with no Northern Ireland data.",
         then=["The invoice is built and generateCustomsData is Y.",
               "shippingCost stays 0, not the 2.00 the order carries.",
               "No isBusiness, atRisk or ukimsNumber is sent."]),

    case("R1", "R1. Consumer type unresolved", "DPDUK-NI-UNKNOWN-09", shape="refused",
         data={"consumer_type": "unknown"},
         expect=refused("consumer_type: must be resolved to business or individual"),
         note="DPD has no value for 'unknown' - the classification decides the whole customs "
              "treatment. The shipment has to be refused naming the field, not sent as a guess.",
         given="A Northern Ireland shipment whose receiver type the product could not resolve.",
         then=["No shipment call is made.",
               "The app names consumer_type in what it returns to the product."]),

    case("R2", "R2. Not at risk, no scheme number anywhere", "DPDUK-NI-NOUKIMS-10",
         shape="refused",
         data={"sender_ukims": None, "shipping_address": {"receiver_ukims": None}},
         expect=refused("sender_ukims or shipping_address.receiver_ukims"),
         note="A not-at-risk movement is what the scheme number buys. Without one from either "
               "party DPD rejects the shipment, and the field the product has to fill is the one "
               "the message has to name.",
         given="A business receiver, goods not at risk, and neither party holding a scheme number.",
         then=["No shipment call is made.",
               "Both key names appear in the refusal."]),

    case("R3", "R3. Commodity code missing on one line", "DPDUK-NI-NOHS-11", shape="refused",
         items=[SHIRT, merge(SCARF, {"hs_code": None})],
         packed_as=packages([package(0.65, "CTN-0001", [
             PACKED_SHIRT,
             merge(PACKED_SCARF, {"hs_tariff_code": None, "HsCode": None,
                                  "source_hs_code": None})])]),
         expect=refused("order_items.hs_code"),
         note="IA-5213 makes the commodity code mandatory on every Northern Ireland line. One line "
              "of two missing it is what proves the check is per line rather than per shipment.",
         given="The same shipment with no commodity code on the scarf, on the package line and the "
               "order line alike.",
         then=["No shipment call is made.",
               "The refusal names order_items.hs_code and the SKU that is missing it."]),

    case("R4", "R4. Stated customs total disagrees with the lines", "DPDUK-NI-VALUEGAP-12",
         shape="refused", data={"total_customs_value": 30.0},
         expect=refused("total_customs_value"),
         note="The customs total is computed upstream and the item values are sent alongside it. "
              "Where the two disagree one of them is wrong, and DPD would clear the goods against a "
              "figure the invoice lines do not support.",
         given="A stated total of 30.00 against lines that come to 36.00.",
         then=["No shipment call is made.",
               "The refusal states both figures."]),

    case("R5", "R5. Package lighter than what is in it", "DPDUK-NI-LIGHT-13", shape="refused",
         packed_as=packages([package(0.2, "CTN-0001", [PACKED_SHIRT, PACKED_SCARF])]),
         data={"shipment_weight": 0.2},
         expect=refused("shipment_weight"),
         note="DPD refuses a unit weight that outweighs the parcel holding it. 0.20 kg against "
              "0.65 kg of goods is the arithmetic the reconciliation exists for.",
         given="Both products packed in a package declared at 0.20 kg.",
         then=["No shipment call is made.",
               "The refusal names shipment_weight and states both weights."]),

    case("R6", "R6. Fulfilment code carries no network code", "DPDUK-NI-NOCODE-14",
         shape="refused", data={"shipping_method": {"fulfilment_code": "DPD_UK"}},
         expect=refused("shipping_method.fulfilment_code"),
         note="Without a network code DPD has no service to carry the shipment. The split on / used "
              "to throw into a catch-all that reported 'something went wrong' - the field is what "
              "the product needs to hear, and this refusal applies to every destination.",
         given="A fulfilment code with no network code after the separator.",
         then=["No shipment call is made.",
               "The refusal names shipping_method.fulfilment_code and echoes what arrived."]),

    case("R7", "R7. Customs currency DPD does not settle in", "DPDUK-NI-USD-15", shape="refused",
         items=[merge(SHIRT, {"currency": "USD"}), merge(SCARF, {"currency": "USD"})],
         data={"customs_currency": "USD"},
         expect=refused("customs_currency: must be GBP or EUR"),
         note="DPD settles customs in Sterling or Euro only. Relabelling a dollar value as GBP "
              "would clear the goods at the wrong amount, so an unsupported currency is refused "
              "rather than converted or dropped.",
         given="A shipment valued in US dollars, on the order and on its lines.",
         then=["No shipment call is made.",
               "The refusal names customs_currency."]),

    case("R8", "R8. Both parties hold a scheme number, neither is named",
         "DPDUK-NI-2UKIMS-16", shape="refused",
         data={"sender_ukims": "XIUKIM47700000000000000000009"},
         expect=refused("ukims_holder: must name sender or receiver"),
         note="DPD accepts one scheme number. With two present and no holder named, picking either "
              "would be a guess about who is liable, so the product is asked which - and "
              "ukims_holder is the key it answers with.",
         given="A shipment where the sender and the receiver both hold a scheme number and "
               "ukims_holder is not set to either party.",
         then=["No shipment call is made.",
               "The refusal names ukims_holder."]),

    case("E1", "E1. DPD rejects the postcode", "DPDUK-NI-BADPOSTCODE-17", shape="dpd error",
         expect={"shipment_calls": 1, "shipment_status": 200,
                 "dpd_error": "Invalid postcode value", "label_calls": 0,
                 "app_says": "Invalid postcode value", "db_rows": 0,
                 "customs_flag": "Y", "parcels": {"parcel[]": 1, "totalWeight": 0.65}},
         note="DPD answers 200 with a populated error array, which is the only thing separating a "
              "created shipment from a refused one. Proves the integration reads the array rather "
              "than the status, and passes DPD's own words back to the product.",
         given="A shipment DPD refuses on the delivery postcode.",
         then=["One shipment call, answered 200 with error 1009.",
               "No label is fetched and no row is written.",
               "The object, the error type and DPD's message reach the product."]),

    case("E2", "E2. GeoSession dropped, renewed, shipment sent again",
         "DPDUK-SESSIONEXPIRED-18", shape="geosession",
         expect=merge(NI_MAPPED, {"shipment_calls": 2, "shipment_status": None,
                                  "shipment_statuses": "401 200",
                                  "invoice_reference": "DPDUK-SESSIONEXPIRED-18"}),
         checks=[Custom("DPD answers the two attempts",
                        "the status of every POST /shipping/shipment, in order",
                        status_sequence, expect="shipment_statuses")],
         note="DPD can drop a GeoSession before its validity limit. The cached session is then "
              "renewed and the shipment sent once more; the second attempt must be the one that "
              "creates it, and the payload must be identical. Two calls is the ratio that "
              "distinguishes renewing the session from replaying the whole flow.",
         given="A shipment the mock refuses once with 401 and accepts on the retry.",
         then=["Two shipment calls: 401 then 200.",
               "The mapping on the accepted attempt is the same as N1's.",
               "The label is still fetched twice and one row is written."]),

    case("E3", "E3. GeoSession refused even after renewal", "DPDUK-SESSIONDEAD-19",
         shape="geosession",
         expect={"shipment_calls": 2, "shipment_status": 401, "label_calls": 0,
                 "app_says": "GEO SESSION is null", "db_rows": 0},
         note="One renewal and no more: a session DPD keeps refusing is a credential problem, and "
              "hammering it would lock the account. Proves the integration stops at two attempts "
              "and says which of its own conditions it stopped on.",
         given="A shipment the mock refuses with 401 every time.",
         then=["Exactly two shipment calls.",
               "No label is fetched and no row is written.",
               "The app reports the GeoSession as the reason."]),

    # ---- IA-4752 3.1 Northern Ireland identification

    case("P1", "P1. Destination postcode in lower case, with spaces", "DPDUK-NI-POSTCODE-20",
         data={"shipping_address": {"post_code": " bt1  1da "}},
         expect=merge(NI_MAPPED, {"invoice_reference": "DPDUK-NI-POSTCODE-20",
                                  "delivery_postcode": "bt11da",
                                  "consignment_delivery_postcode": "bt11da"}),
         note="IA-4752 3.1 requires the postcode match to ignore case and leading, trailing and "
              "internal spaces. A product that stores postcodes as the customer typed them would "
              "otherwise ship to Northern Ireland with no customs data at all.",
         given="The same shipment with the destination postcode as ' bt1  1da '.",
         then=["The shipment is still recognised as Northern Ireland: customs data and the invoice "
               "are sent.",
               "Every space is stripped on the invoice copy of the address.",
               "And on the address DPD delivers to, which is the one it validates."]),

    case("P2", "P2. Origin outside Great Britain", "DPDUK-IE-ORIGIN-21", shape="international",
         data={"pickup_address": {"country_code": "IE", "country": "Ireland",
                                  "post_code": "D02 AF30", "city": "Dublin",
                                  "state_name": "Leinster"}},
         expect={"shipment_calls": 1, "shipment_status": 200, "customs_flag": ABSENT,
                 "invoice": ABSENT, "customs_value": 36.0, "customs_currency": "GBP",
                 "consignment_collection_postcode": "D02AF30",
                 "consignment_delivery_postcode": "BT11DA",
                 "parcels": {"parcel[]": 1, "totalWeight": 0.65},
                 "label_calls": 2, "app_says": SUCCESS_MESSAGE,
                 "db_rows": 1 if LABEL_CONVERSION else 0},
         note="IA-4752 3.1: only a shipment that starts in Great Britain is a Windsor Framework "
              "movement. An Irish origin keeps the existing flow, which on a domestic network code "
              "means no invoice - while the customs value still goes, because ZD-471860 put it on "
              "every non-GB or BT destination.",
         given="The same Belfast delivery, collected from Dublin.",
         then=["No invoice and no generateCustomsData.",
               "The customs value and currency are still sent.",
               "None of the Northern Ireland validation applies."]),

    # ---- IA-4752 3.4 Risk status

    case("P3", "P3. Individual receiver with a risk status set", "DPDUK-NI-B2C-RISK-22",
         data={"consumer_type": "individual", "risk_status": "at_risk",
               "shipping_address": {"receiver_ukims": None, "business_name": None}},
         expect=merge(NI_MAPPED, {
             "is_business": False, "at_risk": ABSENT, "delivery_ukims": ABSENT,
             "delivery_organisation": ABSENT, "invoice_reference": "DPDUK-NI-B2C-RISK-22"}),
         note="IA-4752 3.4 makes risk status Not Applicable for an individual, whatever the product "
              "sent. A prefilled value left on the shipment must not reach DPD as an at-risk "
              "declaration - the receiver is not a business and cannot hold one.",
         given="An individual receiver on a shipment still carrying risk_status at_risk.",
         then=["isBusiness is false.",
               "atRisk is absent from the wire."]),

    case("P4", "P4. Business receiver with no risk status", "DPDUK-NI-NORISK-23", shape="refused",
         data={"risk_status": None},
         expect=refused("risk_status: is required for a business receiver"),
         note="IA-4752 3.4 makes At Risk or Not At Risk mandatory for a business. Neither DPD nor "
              "the integration may assume one: at risk decides whether EU duty is due.",
         given="A business receiver with no risk status resolved.",
         then=["No shipment call is made.",
               "The refusal names risk_status and both allowed values."]),

    # ---- IA-4752 3.5 UKIMS and the matching EORI

    case("P5", "P5. Both parties hold a scheme number, the receiver is named",
         "DPDUK-NI-HOLDER-RCV-24",
         data={"sender_ukims": "XIUKIM47700000000000000000009", "ukims_holder": "receiver"},
         expect=merge(NI_MAPPED, {"invoice_reference": "DPDUK-NI-HOLDER-RCV-24"}),
         note="IA-4752 3.5: the holder the product selected decides which number is sent. With both "
              "parties holding one, naming the receiver has to send the receiver's and drop the "
              "sender's - R8 is the same shipment with no holder named.",
         given="Sender and receiver both holding a scheme number, ukims_holder set to receiver.",
         then=["The receiver's scheme number is sent.",
               "The sender's is not, even though the sender holds one."]),

    case("P6", "P6. Receiver's scheme number without the receiver's EORI",
         "DPDUK-NI-NOBUYEREORI-25", shape="refused",
         data={"buyer_eori": None},
         expect=refused("buyer_eori: is required alongside shipping_address.receiver_ukims"),
         note="IA-4752 3.5 requires the selected holder's UKIMS and the corresponding EORI. DPD "
              "reads the pair together, so a scheme number sent without its owner's EORI number is "
              "a shipment DPD would reject at the border rather than at the API.",
         given="A not-at-risk business shipment where the receiver holds the scheme number and no "
               "buyer EORI was sent.",
         then=["No shipment call is made.",
               "The refusal names buyer_eori and the field it has to accompany."]),

    case("P7", "P7. No sender EORI number", "DPDUK-NI-NOEORI-26", shape="refused",
         data={"eori_no": None},
         expect=refused("eori_no: is required for a Northern Ireland shipment"),
         note="The sender's EORI number is mandatory on all three Northern Ireland flows in DPD's "
              "own field table - business or individual, at risk or not. Nothing else in the "
              "payload can stand in for it.",
         given="A Northern Ireland shipment with no sender EORI number.",
         then=["No shipment call is made.",
               "The refusal names eori_no."]),

    # ---- IA-4752 3.6 Incoterms

    case("P8", "P8. No Incoterm configured", "DPDUK-NI-NOTERM-27", shape="dpd error",
         data={"carrier_incoterm": None, "incoterm": None, "trade_terms": None},
         expect=merge(NI_MAPPED, {
             "invoice_reference": "DPDUK-NI-NOTERM-27", "terms": ABSENT,
             "dpd_error": "'invoice.invoiceTermsOfDelivery' is required",
             "app_says": "'invoice.invoiceTermsOfDelivery' is required",
             "label_calls": 0, "db_rows": 0}),
         note="The settled decision, and what it costs. IA-5213's mapping table says a blank "
              "Incoterm sends null or omits the field and IA-4752 3.6 forbids an internal default, "
              "so DpdUKUtility.resolveTermsOfDelivery returns null and Gson drops the key -- no DAP "
              "fallback, which commit b081e6ec996 had introduced and 087d5aafbb2 removed. DPD "
              "requires invoice.invoiceTermsOfDelivery once generateCustomsData is Y, so the very "
              "request that omits it is one DPD refuses: a Northern Ireland shipment whose carrier "
              "setup resolved no Incoterm cannot be created at all, and the product is told so in "
              "DPD's words rather than by a named field of its own payload.",
         given="A shipment whose carrier setup resolved no Incoterm at all.",
         then=["invoiceTermsOfDelivery is absent, not defaulted to DAP.",
               "One shipment call, answered 200 with error 1007.",
               "No label is fetched and no row is written.",
               "DPD's own words reach the product."]),

    # ---- IA-4752 3.7 Parcels, quantities and weights

    case("P9", "P9. No package allocation - one physical package", "DPDUK-NI-1PKG-28",
         data={"package_details": DELETE, "total_packages": 1},
         expect=merge(NI_MAPPED, {"invoice_reference": "DPDUK-NI-1PKG-28"}),
         note="IA-4752 3.7 permits one-package handling only where the shipment genuinely is one "
              "physical package, and that branch builds its customs lines from the order items "
              "rather than from the packed cartons. It is a second mapping of every product field, "
              "and it must agree with the packed one for the same goods.",
         given="The same two products with no package_details at all.",
         then=["One parcel carrying both customs lines.",
               "Every line field matches the packed shape: SKU, code, value, weight, quantity, "
               "origin, description, type and fabric.",
               "totalWeight is the summed line weights."]),

    # ---- IA-4752 3.8 Customs values

    case("P10", "P10. Free sample - product cost stands in for the price",
         "DPDUK-NI-FREESAMPLE-29",
         items=[SHIRT, merge(SCARF, {"unit_customs_value": None, "item_price": 0.0,
                                     "unit_price": 0.0, "paid_price": 0.0,
                                     "selling_price": 0.0})],
         packed_as=packages([package(0.65, "CTN-0001", [
             PACKED_SHIRT,
             merge(PACKED_SCARF, {"unit_customs_value": None, "price": 0.0,
                                  "unit_price": 0.0})])]),
         data={"total_customs_value": 24.0},
         expect=merge(NI_MAPPED, {"invoice_reference": "DPDUK-NI-FREESAMPLE-29",
                                  "customs_value": 24.0, "unit_values": [6.0, 12.0]}),
         note="IA-4752 3.8: a free sample has no selling price, and DPD refuses a zero unit value. "
              "The product cost is what stands in for it, and the consignment total has to follow "
              "the same arithmetic.",
         given="The scarf sent as a free sample: no customs value and a zero price, product cost "
               "12.00.",
         then=["The free line is valued at its product cost.",
               "customsValue is 6.00 x 2 + 12.00."]),

    case("P11", "P11. Free sample with no product cost", "DPDUK-NI-NOCOST-30", shape="refused",
         items=[SHIRT, merge(SCARF, {"unit_customs_value": None, "product_cost": None,
                                     "item_price": 0.0, "unit_price": 0.0, "paid_price": 0.0,
                                     "selling_price": 0.0})],
         packed_as=packages([package(0.65, "CTN-0001", [
             PACKED_SHIRT,
             merge(PACKED_SCARF, {"unit_customs_value": None, "product_cost": None, "price": 0.0,
                                  "unit_price": 0.0})])]),
         data={"total_customs_value": None},
         expect=refused("order_items.unit_customs_value"),
         note="IA-4752 3.8 blocks the shipment where a product cost is required and unavailable. "
              "Declaring the line at zero is the alternative, and DPD rejects a zero unit value - "
              "after the shipment has been created, which is the failure this ticket exists to "
              "stop.",
         given="The scarf as a free sample with neither a customs value nor a product cost.",
         then=["No shipment call is made.",
               "The refusal names the field and says product_cost is what fills it."]),

    case("P12", "P12. No customs total stated - summed from the lines",
         "DPDUK-NI-NOTOTAL-31",
         data={"total_customs_value": None},
         expect=merge(NI_MAPPED, {"invoice_reference": "DPDUK-NI-NOTOTAL-31"}),
         note="IA-5213 defines consignment.customsValue as the sum of unit value times quantity. "
              "Where the product states its own total the two are reconciled (R4); where it does "
              "not, the integration has to do the arithmetic itself rather than fall back to the "
              "declared value, which includes shipping and tax.",
         given="The same shipment with no total_customs_value.",
         then=["customsValue is 36.00, the summed lines, and not the 42.00 declared value."]),

    case("P13", "P13. Currency taken from the item lines", "DPDUK-NI-EUR-32",
         items=[merge(SHIRT, {"currency": "EUR"}), merge(SCARF, {"currency": "EUR"})],
         data={"customs_currency": None},
         expect=merge(NI_MAPPED, {"invoice_reference": "DPDUK-NI-EUR-32",
                                  "customs_currency": "EUR"}),
         note="IA-4752 3.8 values customs in the order's transaction currency, and DPD settles in "
              "Sterling or Euro only. A shipment whose currency the product states nowhere but on "
              "its items must still be declared in the currency the goods were sold in - R7 is the "
              "same case in a currency DPD does not take.",
         given="A shipment with no customs currency, whose items are priced in Euro.",
         then=["customsCurrency is EUR."]),

    case("P14", "P14. A package holding less than the order line ships",
         "DPDUK-NI-SHORTPACK-33", shape="refused",
         items=[SHIRT, SCARF],
         packed_as=packages([package(0.4, "CTN-0001", [
             merge(PACKED_SHIRT, {"quantity": 1, "price": 10.0}), PACKED_SCARF])]),
         data={"total_customs_value": None},
         expect=refused("order_items.quantity"),
         note="IA-4752 2.1 step 8 reconciles quantities before the DPD call. The order line ships "
              "two shirts and the only package declares one, so either the pack list or the order "
              "line is wrong - and a parcel that physically holds two units declared as one is "
              "under-declared goods crossing a customs border. Nothing catches it while the "
              "product also states a customs total, because then the value reconciliation fires "
              "instead; with no stated total the summed lines simply agree with themselves.",
         given="An order line for two shirts, packed as one, with no stated customs total.",
         then=["No shipment call is made.",
               "The refusal names order_items.quantity and the SKU that disagrees."]),

    # ---- IA-4752 3.9 Product customs information

    case("P15", "P15. The item's own description and origin win",
         "DPDUK-NI-ITEMDESC-34",
         items=[merge(SHIRT, {"item_description": "Organic cotton crew-neck tee",
                              "country_origin_code": "CN"}),
                merge(SCARF, {"country_origin_code": None})],
         packed_as=packages([package(0.65, "CTN-0001", [
             merge(PACKED_SHIRT, {"origin_location_code": None}),
             merge(PACKED_SCARF, {"origin_location_code": None})])]),
         expect=merge(NI_MAPPED, {
             "invoice_reference": "DPDUK-NI-ITEMDESC-34",
             "descriptions": ["Organic cotton crew-neck tee", "Wool Scarf"],
             "description": "Organic cotton crew-neck tee|Wool Scarf",
             "origins": ["CN", "GB"]}),
         note="IA-4752 3.9 orders both fallbacks: description before name, item origin before the "
              "collection country. Customs reads the description to classify the goods and the "
              "origin to rate the duty, so a name where a description exists and a warehouse "
              "country where the item states its own are both wrong answers.",
         given="A shirt made in China carrying its own description, and a scarf stating neither.",
         then=["The shirt's line and the parcel description use the item description.",
               "The shirt's origin is CN; the scarf falls back to the collection country."]),

    case("P16", "P16. Long descriptions, one product named twice",
         "DPDUK-NI-LONGDESC-35",
         items=[item(781, "Merino Wool Winter Scarf", "SKU-101", "621410", 6.0, 3.0, 0.2, 1, 6.0),
                item(782, "Merino Wool Winter Scarf", "SKU-102", "621410", 6.0, 3.0, 0.2, 1, 6.0),
                item(783, "Cotton Crew Neck T-Shirt", "SKU-103", "610910", 6.0, 3.0, 0.2, 1, 6.0)],
         packed_as=packages([package(0.6, "CTN-0001", [
             packed("SKU-101", "Merino Wool Winter Scarf", "621410", 6.0, 3.0, 0.2, 1, 6.0),
             packed("SKU-102", "Merino Wool Winter Scarf", "621410", 6.0, 3.0, 0.2, 1, 6.0),
             packed("SKU-103", "Cotton Crew Neck T-Shirt", "610910", 6.0, 3.0, 0.2, 1, 6.0)])]),
         data={"total_customs_value": 18.0, "shipment_weight": 0.6, "items_count": 3},
         expect=merge(NI_MAPPED, {
             "invoice_reference": "DPDUK-NI-LONGDESC-35",
             "customs_value": 18.0,
             "description": "Merino Wool Winter Scarf",
             "skus": ["SKU-101", "SKU-102", "SKU-103"],
             "hs_codes": ["621410", "621410", "610910"],
             "unit_values": [6.0, 6.0, 6.0],
             "unit_weights": [0.2, 0.2, 0.2],
             "quantities": [1, 1, 1],
             "origins": ["GB", "GB", "GB"],
             "descriptions": ["Merino Wool Winter Scarf", "Merino Wool Winter Scarf",
                              "Cotton Crew Neck T-Shirt"],
             "type_descriptions": [ABSENT, ABSENT, ABSENT],
             "fabrics": [ABSENT, ABSENT, ABSENT],
             "parcels": {"parcel[]": 1, "totalWeight": 0.6}}),
         note="IA-4752 3.9 has the parcel description concatenated with DPD's delimiter and "
              "truncated safely. Two products share a name, so naming each once is what stops the "
              "field being spent on repetition; and it stops on a delimiter, because a product name "
              "cut in half describes nothing. The 41-character limit is this codebase's own choice "
              "and IA-4752 3.9 asks engineering to confirm DPD's real maximum.",
         given="Three lines whose names come to 49 characters, two of them identical.",
         then=["Each name appears once.",
               "The description stops at the last name that fits whole - the second is dropped, "
               "not cut.",
               "Every customs line is still sent in full."]),

    # ---- IA-5213 locality and shipping cost

    case("P17", "P17. Street longer than the field", "DPDUK-NI-LOCALITY-36",
         data={"shipping_address": {"address1": "Flat 12b Ravenhill Business Park Annexe"}},
         expect=merge(NI_MAPPED, {
             "invoice_reference": "DPDUK-NI-LOCALITY-36",
             "delivery_street": "Flat 12b Ravenhill Business Park",
             "delivery_locality": "Annexe, Suite 3",
             "invoice_delivery_street": "Flat 12b Ravenhill Business Park",
             "invoice_delivery_locality": "Annexe, Suite 3"}),
         note="IA-5213 asks for the locality mapping to be verified. The invoice address used to be "
              "a second, separate mapping of the same street: the consignment copy broke it on a "
              "word and moved the rest in front of the second address line, while the invoice copy "
              "was the raw line cut mid-word at 35 characters by @Trim - and its locality lost the "
              "spilled words altogether. The customs invoice is the copy that clears the border, so "
              "it now carries the address the consignment carries.",
         given="A delivery street of 39 characters and a second address line of 7.",
         then=["The consignment street holds the words that fit.",
               "The locality is what did not fit, then the second address line.",
               "The invoice address states the same street and the same locality."]),

    case("P18", "P18. No shipping charge stated", "DPDUK-NI-NOSHIPCOST-37",
         data={"shipping_amount": None},
         expect=merge(NI_MAPPED, {"invoice_reference": "DPDUK-NI-NOSHIPCOST-37",
                                  "shipping_cost": ""}),
         note="DPD tells the two unknowns apart: a number is the carriage the customer paid, an "
              "empty string says it already sits inside the consignment value. Sending 0 declares "
              "free carriage and moves the duty base, which is why IA-5213 says blank when the cost "
              "is unavailable.",
         given="A Northern Ireland shipment with no shipping amount.",
         then=["shippingCost is an empty string, not 0."]),
]

# Every successful case is proven up to the label conversion, and no further, on a machine without
# wkhtmltopdf.
for _case in CASES:
    if _case.expect.get("app_says") == SUCCESS_MESSAGE:
        _case.blocked_when = BLOCKED_ON_LABEL_CONVERSION


def case_of(call):
    """Which case a logged call belongs to.

    The shipment request states the order number as `consignment[0].consignmentRef`. The label call
    knows only the shipmentId, and this mock answers with the order number inside it -- see
    `dpd-uk/README.md`, "What the mock does that DPD does not".
    """
    body = call.request_body if isinstance(call.request_body, dict) else {}
    consignments = body.get("consignment") or []
    if consignments and isinstance(consignments[0], dict):
        return str(consignments[0].get("consignmentRef") or "")
    found = re.search(r"/shipping/shipment/SHP-([^/?]+)/label", call.url)
    return found.group(1) if found else ""


class BinaryOnPath(Probe):
    """A command line tool the last leg of the flow shells out to.

    Not required: the cases that need it are reported `blocked` rather than failed, so its absence
    is stated once, here, instead of once per case.
    """

    required = False

    def __init__(self, binary, why):
        self.binary = binary
        self.why = why

    def check(self, run):
        found = shutil.which(self.binary)
        if found:
            return "ok", "%s on PATH (%s)" % (self.binary, found), []
        return "WARN", "%s not on PATH -- %s" % (self.binary, self.why), []


# -------------------------------------------------------------------------------------- suite

SUITE = Suite(
    id="ni-shipment",
    name="Northern Ireland shipment (warehouse -> JPluger -> DPD UK)",
    description="37 cases: every field the Northern Ireland mapping states, the rules of IA-4752 "
                "3.1 to 3.9, every pre-submission refusal, and the GeoSession retry",
    mock="dpd-uk",
    cases=CASES,
    env=ENV,

    # How a case reaches the app. carrier-core's OrdersController calls the integration in the
    # request thread, so this response is the app's own verdict on the shipment.
    fire=PostJson("${APP}/jpluger/carrier/orders"),

    # The two calls this flow makes to DPD once it holds a GeoSession. The login is a third, but it
    # carries nothing that names a case, so no group can attribute it: DpdUKGeoSessionCache issues
    # one per seller per 23 hours and one per session DPD refuses. Read those from the run's
    # mock-log.json -- E2 and E3 each show a login between their two shipment attempts.
    groups=[Group("shipment", "POST", "/shipping/shipment", label="shipment"),
            Group("label", "GET", "/shipping/shipment/*/label/", label="label fetch",
                  plural="label fetches")],

    # DpdUKUtility sends the order number as consignment[0].consignmentRef, and the mock echoes it
    # inside the shipmentId that the label calls are then addressed by -- so a case's whole traffic
    # is recoverable from the log without relying on timing.
    call_key=case_of,

    # DPD reports a refusal inside the error array, never in the status.
    marker_fields=("error[0]",),

    # The checklist, in the order the flow happens: the shipment call, what DPD made of it, then
    # every value the Northern Ireland mapping had to get right, then the label and what the product
    # was told. Read top to bottom, it is the journey of one shipment.
    checks=[
        Calls("shipment", "Send the shipment to DPD", "POST /shipping/shipment",
              expect="shipment_calls"),
        Status("shipment", "DPD answers the shipment", "HTTP status of every shipment response",
               expect="shipment_status", which="all"),
        Marker("shipment", "Read the error DPD returned", "error[0] of the shipment response",
               expect="dpd_error"),

        payload_check("Declare customs data", "generateCustomsData at the root of the request",
                      "generateCustomsData", "customs_flag"),
        payload_check("Build the invoice", "the invoice object", "invoice", "invoice"),
        payload_check("Name the duty term", "invoice.invoiceTermsOfDelivery",
                      "invoice.invoiceTermsOfDelivery", "terms"),
        payload_check("State the carriage paid", "invoice.shippingCost",
                      "invoice.shippingCost", "shipping_cost"),
        payload_check("Reference the invoice", "invoice.invoiceReference",
                      "invoice.invoiceReference", "invoice_reference"),

        payload_check("Name the sender's county", "invoice.invoiceShipperDetails.address.county",
                      "invoice.invoiceShipperDetails.address.county", "shipper_county"),
        payload_check("Strip the sender's postcode",
                      "invoice.invoiceShipperDetails.address.postcode",
                      "invoice.invoiceShipperDetails.address.postcode", "shipper_postcode"),
        payload_check("Send the sender's EORI number",
                      "invoice.invoiceShipperDetails.eoriNumber",
                      "invoice.invoiceShipperDetails.eoriNumber", "shipper_eori"),
        payload_check("Send the sender's VAT number",
                      "invoice.invoiceShipperDetails.valueAddedTaxNumber",
                      "invoice.invoiceShipperDetails.valueAddedTaxNumber", "shipper_vat"),
        payload_check("Send the sender's scheme number",
                      "invoice.invoiceShipperDetails.ukimsNumber",
                      "invoice.invoiceShipperDetails.ukimsNumber", "shipper_ukims"),

        payload_check("Name the receiver's county",
                      "invoice.invoiceDeliveryDetails.address.county",
                      "invoice.invoiceDeliveryDetails.address.county", "delivery_county"),
        payload_check("Strip the receiver's postcode",
                      "invoice.invoiceDeliveryDetails.address.postcode",
                      "invoice.invoiceDeliveryDetails.address.postcode", "delivery_postcode"),
        payload_check("Name the receiver's organisation",
                      "invoice.invoiceDeliveryDetails.address.organisation",
                      "invoice.invoiceDeliveryDetails.address.organisation",
                      "delivery_organisation"),
        payload_check("Send the receiver's EORI number",
                      "invoice.invoiceDeliveryDetails.eoriNumber",
                      "invoice.invoiceDeliveryDetails.eoriNumber", "delivery_eori"),
        payload_check("Send the receiver's scheme number",
                      "invoice.invoiceDeliveryDetails.ukimsNumber",
                      "invoice.invoiceDeliveryDetails.ukimsNumber", "delivery_ukims"),
        payload_check("Classify the receiver as a business",
                      "invoice.invoiceDeliveryDetails.isBusiness",
                      "invoice.invoiceDeliveryDetails.isBusiness", "is_business"),
        payload_check("Declare whether the goods are at risk",
                      "invoice.invoiceDeliveryDetails.atRisk",
                      "invoice.invoiceDeliveryDetails.atRisk", "at_risk"),

        payload_check("Value the consignment", "consignment[0].customsValue",
                      "consignment.0.customsValue", "customs_value"),
        payload_check("State the currency", "consignment[0].customsCurrency",
                      "consignment.0.customsCurrency", "customs_currency"),
        payload_check("Describe the goods", "consignment[0].parcelDescription",
                      "consignment.0.parcelDescription", "description"),
        payload_check("Split the delivery street on a word",
                      "consignment[0].deliveryDetails.address.street",
                      "consignment.0.deliveryDetails.address.street", "delivery_street"),
        payload_check("Spill what did not fit into the locality",
                      "consignment[0].deliveryDetails.address.locality",
                      "consignment.0.deliveryDetails.address.locality", "delivery_locality"),
        payload_check("Strip the postcode DPD collects from",
                      "consignment[0].collectionDetails.address.postcode",
                      "consignment.0.collectionDetails.address.postcode",
                      "consignment_collection_postcode"),
        payload_check("Strip the postcode DPD delivers to",
                      "consignment[0].deliveryDetails.address.postcode",
                      "consignment.0.deliveryDetails.address.postcode",
                      "consignment_delivery_postcode"),
        payload_check("The invoice's own copy of the street",
                      "invoice.invoiceDeliveryDetails.address.street",
                      "invoice.invoiceDeliveryDetails.address.street", "invoice_delivery_street"),
        payload_check("The invoice's own copy of the locality",
                      "invoice.invoiceDeliveryDetails.address.locality",
                      "invoice.invoiceDeliveryDetails.address.locality",
                      "invoice_delivery_locality"),
        Custom("Reconcile the parcels and the weight",
               "numberOfParcels, parcel[], totalWeight and the summed line weights",
               parcels_reconcile, expect="parcels"),

        line_check("Name each line's SKU", "productCode of every customs line", "productCode",
                   "skus"),
        line_check("Classify each line", "productHarmonisedCode of every customs line",
                   "productHarmonisedCode", "hs_codes"),
        line_check("Value each line", "unitValue of every customs line", "unitValue",
                   "unit_values"),
        line_check("Weigh each line", "unitWeight of every customs line", "unitWeight",
                   "unit_weights"),
        line_check("Count each line", "numberOfItems of every customs line", "numberOfItems",
                   "quantities"),
        line_check("Origin of each line", "countryOfOrigin of every customs line",
                   "countryOfOrigin", "origins"),
        line_check("Describe each line", "productItemsDescription of every customs line",
                   "productItemsDescription", "descriptions"),
        line_check("Type each line", "productTypeDescription of every customs line",
                   "productTypeDescription", "type_descriptions"),
        line_check("State the fabric of each line", "productFabricContent of every customs line",
                   "productFabricContent", "fabrics"),

        Calls("label", "Fetch the label", "GET /shipping/shipment/{shipmentId}/label/ , once as "
              "HTML and once as Citizen CLP", expect="label_calls"),
        Custom("Report back to the product", "the message on the app's own response",
               app_reply, expect="app_says"),
        Rows("Write the shipment to the database", "rows in `corders` for this order number",
             expect="db_rows"),
    ],

    # Emptied before the run and captured into the run folder after every case.
    stores=["logins", "shipments", "session_refused"],

    database=Sql(
        client=lambda env: MySql.from_json(env["CORE_JSON"], env["DB_NAME"]),
        dump="SELECT order_number, tracking_id, courier_code, courier_status, "
             "carrier_order_reference FROM corders WHERE order_number LIKE 'DPDUK-%' "
             "ORDER BY order_number",
        file="corders.tsv",
        key_column=0,
        reset="DELETE FROM corders WHERE order_number LIKE 'DPDUK-%'",
    ),

    preflight=[
        AppResponds("${APP}/jpluger/carrier/orders"),
        MockResponds(),
        DatabaseResponds(),
        # CarriersCustomORM.getSeller is called before any DPD call is made, and the credential
        # lookup, the GeoSession and the collection date all hang off the row it returns. Without
        # it every case fails identically, inside the app, with nothing in the mock's log.
        SeedRows("seller 42", "SELECT COUNT(*) FROM cseller WHERE selluseller_seller_id=42",
                 hint="load it:  mysql … ${DB_NAME} < dpd-uk/seed-data/"
                      "dpd_uk_local_seed_data.sql"),
        SeedRows("dpd_uk username and password",
                 "SELECT COUNT(*) FROM ccredential c JOIN cseller s ON s.seller_id=c.seller_id "
                 "WHERE s.selluseller_seller_id=42 AND c.carrier_code='dpd_uk' "
                 "AND c.key_name IN ('username','password')", at_least=2),
        SeedRows("dpd_uk dispatch slot",
                 "SELECT COUNT(*) FROM cdispatch_time_slots d JOIN cseller s "
                 "ON s.seller_id=d.seller_id WHERE s.selluseller_seller_id=42 "
                 "AND d.carrier_code='dpd_uk'"),
        BinaryOnPath("wkhtmltopdf",
                     "the label HTML cannot be converted, so every case that gets as far as a "
                     "created shipment is reported `blocked` at its last two assertions"),
    ],
)


if __name__ == "__main__":
    from suite.run import main
    sys.exit(main(__file__, sys.argv[1:]))
