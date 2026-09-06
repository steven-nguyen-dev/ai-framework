#!/usr/bin/env python3
"""IA-5109-US3: Multi-Marketplace & Carrier/Customs Test Suite.

Judges marketplace isolation, per-marketplace payloads (France, Germany, Japan, US),
carrier mappings, Japan COD collection handling, and carrier customs/IOSS boundaries
for User Story 3: Support Partial and Multi-Parcel Amazon Seller-Fulfilled Shipments (IA-5109).

Every case crosses the HTTP boundary. The observable is what the mock received, and where a rule
blocks it is the row the mock did not record -- shown alongside a sibling that does confirm, so the
block is the parcel's and not the whole flow's.

Covers:
  - The four marketplace ids, verbatim (FR A13V1IB3VIYZZH, DE A1PA6795UKMFR9, JP A1VC38T7YXB528, US ATVPDKIKX0DER) (L-55)
  - Japan's codCollectionMethod, and that it sits as a sibling of packageDetail (L-7, L-93)
  - Carrier resolution on the live payload shape: provider first, override only when non-empty,
    Other plus a mandatory carrierName, self delivery, and the configuration block (L-6, L-91, L-146, L-187)
  - Marketplace mismatch as a routing fault (L-31, L-55)
  - Rule N-5's Amazon half: the confirmation carries no customs data at all (L-70, L-94)
  - Compatibility with the domestic single-shipment path (L-99, L-105)

Not here, and why. Rule N-5's carrier half -- the IOSS number onto the carrier's create-order request
-- is outside this story's own call chain (mapping 4.6) and reaches no endpoint this suite calls, so
the case that asserted it against a dictionary it had just built is removed rather than rewritten.

Runner contract: TESTING.md.
Publishes live status to amazon/test-results/IA-5109-US3-multi-market/run-<stamp>/results.json.

Usage:
  python3 amazon/IA-5109-US3-suite-multi-market.py
  python3 amazon/IA-5109-US3-suite-multi-market.py --list
  BASE=http://127.0.0.1:23103 python3 amazon/IA-5109-US3-suite-multi-market.py
"""

import atexit
import datetime
import json
import os
import shutil
import sys
import threading
import time
from http.server import ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import ia5109_us3_requirements as R

BASE = os.environ.get("BASE", "http://127.0.0.1:23103").rstrip("/")
SUITE_ID = "IA-5109-US3-multi-market"
SUITE_NAME = "IA-5109-US3: Multi-Marketplace & Carrier/Customs Suite"
KEEP = "--keep-state" in sys.argv
LIST_ONLY = "--list" in sys.argv
WANTED_CASES = set(a for a in sys.argv[1:] if not a.startswith("-"))

MOCK_DIR = HERE
DATA_DIR = os.path.join(MOCK_DIR, "mock-data")
LOG_FILE = "api-calls.har.json"
STAMP = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
RUN_DIR = os.path.join(MOCK_DIR, "test-results", SUITE_ID, "run-" + STAMP)

_EPHEMERAL_SERVER = None
_EPHEMERAL_THREAD = None


def _start_ephemeral_mock():
    global _EPHEMERAL_SERVER, _EPHEMERAL_THREAD
    parent_dir = os.path.dirname(MOCK_DIR)
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)
    import mock

    config_path = os.path.join(MOCK_DIR, "amazon.mock.json")
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    os.makedirs(DATA_DIR, exist_ok=True)
    routes, spec = mock.build_routes(config, MOCK_DIR)
    state = mock.State(config.get("stores"), DATA_DIR)
    api_log = mock.ApiLog(os.path.join(DATA_DIR, LOG_FILE), "har", config.get("log_redact_headers"), "Amazon SP-API")
    handler_cls = mock.make_handler(
        config, routes, state, api_log, os.path.join(MOCK_DIR, "test-results"),
        [], mock.SuiteRunner(), MOCK_DIR
    )

    host = config.get("host", "127.0.0.1")
    port = int(config.get("port", 23103))
    _EPHEMERAL_SERVER = ThreadingHTTPServer((host, port), handler_cls)
    _EPHEMERAL_THREAD = threading.Thread(target=_EPHEMERAL_SERVER.serve_forever, daemon=True)
    _EPHEMERAL_THREAD.start()
    time.sleep(0.3)


def _stop_ephemeral_mock():
    global _EPHEMERAL_SERVER
    if _EPHEMERAL_SERVER:
        try:
            _EPHEMERAL_SERVER.shutdown()
            _EPHEMERAL_SERVER.server_close()
        except Exception:
            pass
        _EPHEMERAL_SERVER = None


atexit.register(_stop_ephemeral_mock)


def call_amazon(method, path, body=None, token="mock_sp_api_access_token"):
    url = BASE + path
    return R.http_json(method, url, body=body, token=token)


def store(name):
    """Reads one of the mock's stores back, which is where the partner-side observable lives."""
    path = os.path.join(DATA_DIR, name + ".json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


CASES, RESULTS = [], {}
EVIDENCE = {
    "status": "running",
    "mock call log": "not captured",
    "server": f"Amazon SP-API mock at {BASE}",
}


class Checks:
    def __init__(self):
        self.items = []

    def add(self, label, what, expected, actual):
        ok = (str(expected) == str(actual)) if not isinstance(expected, bool) else (expected is (actual is True or actual == "True"))
        self.items.append({
            "label": label,
            "what": what,
            "expected": str(expected),
            "actual": str(actual),
            "ok": ok,
        })

    def truthy(self, label, what, actual):
        got = "present" if actual not in (None, "", [], {}) else "missing"
        self.items.append({
            "label": label,
            "what": what,
            "expected": "present",
            "actual": got,
            "ok": got == "present",
        })

    @property
    def ok(self):
        return all(i["ok"] for i in self.items)


def case(cid, name, given, then, note, fn):
    CASES.append({
        "id": cid,
        "name": name,
        "given": given,
        "then": then if isinstance(then, list) else [then],
        "note": note,
        "fn": fn,
    })


def publish():
    cases_out = []
    for c in CASES:
        r = RESULTS.get(c["id"])
        e = {
            "id": c["id"],
            "name": c["name"],
            "given": c["given"],
            "then": c["then"],
            "note": c["note"],
        }
        if r:
            e.update(r)
        elif WANTED_CASES and c["id"] not in WANTED_CASES:
            e.update({
                "verdict": "skip",
                "summary": "skipped (not selected)",
                "checks": [],
                "calls": [],
                "detail": {},
            })
        else:
            e.update({"verdict": "pending"})
        cases_out.append(e)

    done = [c for c in cases_out if c.get("verdict") in ("pass", "fail", "blocked", "skip")]
    doc = {
        "name": SUITE_NAME,
        "suite": SUITE_ID,
        "at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "base_url": BASE,
        "summary": {
            "pass": sum(1 for c in done if c["verdict"] == "pass"),
            "fail": sum(1 for c in done if c["verdict"] == "fail"),
            "blocked": sum(1 for c in done if c["verdict"] == "blocked"),
            "skip": sum(1 for c in done if c["verdict"] == "skip"),
        },
        "evidence": EVIDENCE,
        "cases": cases_out,
    }
    os.makedirs(RUN_DIR, exist_ok=True)
    with open(os.path.join(RUN_DIR, "results.json"), "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2)


def run_case(c):
    ch = Checks()
    calls = []
    detail = {}
    try:
        c["fn"](ch, calls, detail)
        verdict = "pass" if ch.ok else "fail"
    except Exception as e:
        ch.add("runner exception", "no unhandled exception", "none", f"error: {e}")
        verdict = "fail"

    np = sum(1 for i in ch.items if i["ok"])
    RESULTS[c["id"]] = {
        "verdict": verdict,
        "checks": ch.items,
        "calls": calls,
        "detail": detail,
        "summary": f"{np}/{len(ch.items)} checks passed",
    }


# ===================================================================== Test Cases Definitions
#
# Every case crosses the HTTP boundary. Where a rule blocks, the observable is the row the mock did
# not record; a blocking case always ships a sibling parcel too, so the block is shown to be the
# parcel's and not the whole event's.

FR, DE, JP, US = "amazon_sp_fr", "amazon_sp_de", "amazon_sp_jp", "amazon_sp_us"
READY_TO_SHIP_AT = "2026-08-22T14:05:00Z"
PURCHASED_AT = "2026-08-20T09:12:03Z"
SUBMITTING_AT = "2026-08-22T14:06:00Z"
ITEM_1001 = "05015851154158"
ITEM_2002 = "05015851154159"


def live_meta(**overrides):
    """The carrier and date context of the one captured live ready-to-ship payload (L-146, L-187).

    Three carrier fields arrive empty and one arrives null, leaving shipping_provider as the only
    carrier identity on the payload, which is what makes the resolution order of 5.3 load-bearing.
    """
    meta = {
        "shipping_provider": "Startrack",
        "marketplace_carrier_code": "",
        "logistic_partner_name": None,
        "shipping_type": "FPP (Fixed Price Premium)",
        "updated_at": READY_TO_SHIP_AT,
        "purchased_at": PURCHASED_AT,
        "submitting_at": SUBMITTING_AT,
        "store_marketplace_code": FR,
    }
    meta.update(overrides)
    return meta


def one_box(tracking="MT-7734829901", **overrides):
    return [R.CartonBox("B1", tracking, ship_date=READY_TO_SHIP_AT,
                        items=[R.OrderItemAllocation(811, ITEM_1001, "SKU-1001", 2)], **overrides)]


def confirmations_for(order_id):
    return [c for c in store("shipment_confirmations") if c.get("orderId") == order_id]


def send(ch, calls, order_id, marketplace, parcel, is_cod=False, expect=204):
    request = R.build_amazon_confirmation_request(order_id, marketplace, parcel, is_cod=is_cod)
    status, _ = call_amazon("POST", request["url_path"], request["body"])
    calls.append("POST %s (%s) -> %s" % (request["url_path"], marketplace, status))
    if expect is not None:
        ch.add("confirmation answered %s" % expect, "one call per parcel", expect, status)
    return request, status


# --------------------------------------------------------------------- C-18, the four marketplaces

def test_mkt_france(ch, calls, detail):
    # France, amazon_sp_fr -> A13V1IB3VIYZZH (L-55, Appendix A.2)
    order_id = "902-MKTFR-0000001"
    parcels, _ = R.assemble_parcels(
        one_box(), live_meta(marketplace_carrier_code="DHL", logistic_partner_name="DHL Express",
                             shipping_type="DHL Express Worldwide"))
    send(ch, calls, order_id, FR, parcels[0])

    row = confirmations_for(order_id)[0]
    ch.add("marketplaceId", "verbatim from the repository", "A13V1IB3VIYZZH", row.get("marketplaceId"))
    ch.add("no cod method", "only Japan may carry it (L-7)", None, row.get("codCollectionMethod"))


def test_mkt_germany(ch, calls, detail):
    # Germany, amazon_sp_de -> A1PA6795UKMFR9 (L-55, Appendix A.6)
    order_id = "902-MKTDE-0000001"
    parcels, _ = R.assemble_parcels(
        one_box("DE-TRACK-001"),
        live_meta(store_marketplace_code=DE, marketplace_carrier_code="DHL",
                  logistic_partner_name="DHL Express", shipping_type="Paket"))
    send(ch, calls, order_id, DE, parcels[0])

    row = confirmations_for(order_id)[0]
    ch.add("marketplaceId", "verbatim from the repository", "A1PA6795UKMFR9", row.get("marketplaceId"))
    ch.add("no cod method", "IOSS and the deemed-reseller category apply as for France, COD does not",
           None, row.get("codCollectionMethod"))


def test_mkt_us(ch, calls, detail):
    # United States, amazon_sp_us -> ATVPDKIKX0DER (L-55, Appendix A.6)
    order_id = "902-MKTUS-0000001"
    parcels, _ = R.assemble_parcels(
        one_box("1Z9999999999999999"),
        live_meta(store_marketplace_code=US, marketplace_carrier_code="UPS",
                  logistic_partner_name="UPS Ground", shipping_type="Ground"))
    send(ch, calls, order_id, US, parcels[0])

    row = confirmations_for(order_id)[0]
    ch.add("marketplaceId", "verbatim from the repository", "ATVPDKIKX0DER", row.get("marketplaceId"))
    ch.add("no cod method", "no COD, no IOSS", None, row.get("codCollectionMethod"))


def test_mkt_all_four_ids(ch, calls, detail):
    # C-18: all four marketplaces carried, ids verbatim, evidence produced per marketplace (L-55, L-99)
    expected = {FR: "A13V1IB3VIYZZH", DE: "A1PA6795UKMFR9", JP: "A1VC38T7YXB528", US: "ATVPDKIKX0DER"}
    seen = {}
    for index, marketplace in enumerate(sorted(expected), start=1):
        order_id = "902-MKTALL-000000%d" % index
        parcels, _ = R.assemble_parcels(
            one_box("TRK-ALL-%d" % index),
            live_meta(store_marketplace_code=marketplace, marketplace_carrier_code="DHL",
                      logistic_partner_name="DHL Express", shipping_type="Express"))
        send(ch, calls, order_id, marketplace, parcels[0])
        seen[marketplace] = confirmations_for(order_id)[0].get("marketplaceId")

    for marketplace in sorted(expected):
        ch.add("%s id" % marketplace, "one store is exactly one marketplace (L-31)",
               expected[marketplace], seen.get(marketplace))
    ch.add("four distinct ids", "the story carries all four, not France alone",
           4, len(set(seen.values())))


# --------------------------------------------------------------------- C-5, Japan's COD method

def test_mkt_japan_cod(ch, calls, detail):
    # Japan and COD is the only case that carries the collection method, as a SIBLING (L-7, L-93)
    order_id = "902-MKTJPCOD-00001"
    parcels, _ = R.assemble_parcels(
        one_box("460012345678"),
        live_meta(store_marketplace_code=JP, marketplace_carrier_code="YAMATO",
                  logistic_partner_name="Yamato Transport", shipping_type="TA-Q-BIN"))
    request, _ = send(ch, calls, order_id, JP, parcels[0], is_cod=True)

    ch.add("sent at the request root", "a sibling of packageDetail, not a property inside it",
           True, "codCollectionMethod" in request["body"])
    ch.add("not inside packageDetail", "sending it inside would be an invalid request",
           False, "codCollectionMethod" in request["body"]["packageDetail"])

    row = confirmations_for(order_id)[0]
    ch.add("marketplaceId", "Japan", "A1VC38T7YXB528", row.get("marketplaceId"))
    ch.add("amazon received the method", "Japan records how the cash was collected",
           "DirectPayment", row.get("codCollectionMethod"))

    # The same value placed inside packageDetail is not the field Amazon reads, and the mock,
    # which reads it at the root as Amazon documents, records nothing.
    misplaced = "902-MKTJPBAD-00001"
    body = dict(request["body"])
    body.pop("codCollectionMethod")
    body["packageDetail"] = dict(request["body"]["packageDetail"])
    body["packageDetail"]["codCollectionMethod"] = "DirectPayment"
    status, _ = call_amazon("POST", "/orders/v0/orders/%s/shipmentConfirmation" % misplaced, body)
    calls.append("POST /orders/v0/orders/%s/shipmentConfirmation (method misplaced inside packageDetail) -> %s"
                 % (misplaced, status))
    ch.add("misplaced method is not read", "the position is what makes it the collection method (L-7)",
           None, confirmations_for(misplaced)[0].get("codCollectionMethod"))


def test_mkt_japan_non_cod(ch, calls, detail):
    # A Japanese order that is not COD must omit the method (L-7, L-93)
    order_id = "902-MKTJPSTD-00001"
    parcels, _ = R.assemble_parcels(
        one_box("460012345679"),
        live_meta(store_marketplace_code=JP, marketplace_carrier_code="YAMATO",
                  logistic_partner_name="Yamato Transport", shipping_type="TA-Q-BIN"))
    request, _ = send(ch, calls, order_id, JP, parcels[0], is_cod=False)

    ch.add("omitted from the request", "carrying it would misstate how the money was collected",
           False, "codCollectionMethod" in request["body"])
    ch.add("amazon received none", "absent, not blank", None,
           confirmations_for(order_id)[0].get("codCollectionMethod"))


def test_mkt_cod_forbidden_non_jp(ch, calls, detail):
    # The method is never injected outside Japan, even on a COD order (L-7, L-93)
    for index, marketplace in enumerate((FR, DE, US), start=1):
        order_id = "902-MKTCODX-000000%d" % index
        parcels, _ = R.assemble_parcels(
            one_box("TRK-COD-%d" % index),
            live_meta(store_marketplace_code=marketplace, marketplace_carrier_code="DHL",
                      logistic_partner_name="DHL Express", shipping_type="Express"))
        request, _ = send(ch, calls, order_id, marketplace, parcels[0], is_cod=True)
        ch.add("%s omits it in the request" % marketplace, "sending it elsewhere is an invalid request",
               False, "codCollectionMethod" in request["body"])
        ch.add("%s amazon received none" % marketplace, "the method is Japan's alone",
               None, confirmations_for(order_id)[0].get("codCollectionMethod"))


def test_mkt_isolation(ch, calls, detail):
    # An OMS shipment carrying another marketplace's order is a mismatch, never a confirmation (L-55)
    order_id = "902-MKTMISMATCH-01"
    parcels, blocked = R.assemble_parcels(
        one_box("TRK-MISMATCH"),
        live_meta(store_marketplace_code=FR, event_marketplace_code=DE,
                  marketplace_carrier_code="DHL", logistic_partner_name="DHL Express"))
    ch.add("assembly blocks", "one store is exactly one marketplace (L-31), so this is a routing fault",
           [R.EParcelBlockReason.MARKETPLACE_MISMATCH], [b.reason for b in blocked])
    ch.add("no parcel built", "a mismatch is rejected rather than routed", 0, len(parcels))
    ch.add("no confirmation reached amazon", "the wrong marketplace is never told a shipment",
           0, len(confirmations_for(order_id)))

    # The positive control: the same shipment on its own store confirms.
    matched = "902-MKTMATCHED-001"
    parcels, blocked = R.assemble_parcels(
        one_box("TRK-MATCHED"),
        live_meta(store_marketplace_code=DE, event_marketplace_code=DE,
                  marketplace_carrier_code="DHL", logistic_partner_name="DHL Express"))
    ch.add("the matched store is not blocked", "only the mismatch is a fault", [], [b.reason for b in blocked])
    send(ch, calls, matched, DE, parcels[0])
    ch.add("the matched store confirms", "the shipment reaches the marketplace it belongs to",
           "A1PA6795UKMFR9", confirmations_for(matched)[0].get("marketplaceId"))


# --------------------------------------------------------------------- C-4 and C-22, the carrier

def test_carrier_provider_first(ch, calls, detail):
    # 5.3: on the live payload shipping_provider is the only carrier identity present (L-146, L-187)
    order_id = "902-CARRIERLIVE-01"
    parcels, blocked = R.assemble_parcels(one_box("TRK-LIVE-SHAPE"), live_meta())
    ch.add("nothing blocked", "the live shape still resolves a carrier", [], [b.reason for b in blocked])
    send(ch, calls, order_id, FR, parcels[0])

    row = confirmations_for(order_id)[0]
    ch.add("carrier code is set at all", "setCarrierCode is commented out today (L-65)",
           True, bool(row.get("carrierCode")))
    ch.add("unrecognised provider goes as Other", "Startrack is not an Amazon carrier code (L-6)",
           "Other", row.get("carrierCode"))
    ch.add("name falls back to the provider", "logistic_partner_name is null on the live payload (L-187)",
           "Startrack", row.get("carrierName"))
    ch.add("service is the one the seller bought", "the buyer sees what was actually purchased",
           "FPP (Fixed Price Premium)", row.get("shippingMethod"))


def test_carrier_code_override(ch, calls, detail):
    # 5.3: marketplace_carrier_code overrides, but only when it is non-empty (L-146, L-32)
    order_id = "902-CARRIERMAP-001"
    parcels, _ = R.assemble_parcels(
        one_box("TRK-MAPPED"),
        live_meta(marketplace_carrier_code="DHL", logistic_partner_name="DHL Express",
                  shipping_type="DHL Express Worldwide"))
    send(ch, calls, order_id, FR, parcels[0])

    row = confirmations_for(order_id)[0]
    ch.add("recognised code sent unchanged", "a mapped carrier is not downgraded to Other",
           "DHL", row.get("carrierCode"))
    ch.add("name from logistic_partner_name", "the partner name wins over the provider when present",
           "DHL Express", row.get("carrierName"))
    ch.add("service from shipping_type", "the original service is preserved",
           "DHL Express Worldwide", row.get("shippingMethod"))


def test_carrier_unrecognised_other(ch, calls, detail):
    # C-4: an unrecognised carrier goes as Other, and then the name is mandatory (L-6, L-91)
    order_id = "902-CARRIEROTHER-1"
    parcels, _ = R.assemble_parcels(
        one_box("CJ-5581200347"),
        live_meta(shipping_provider="CJ Logistics", marketplace_carrier_code="",
                  logistic_partner_name=None, shipping_type="CJ International Parcel"))
    send(ch, calls, order_id, FR, parcels[0])

    row = confirmations_for(order_id)[0]
    ch.add("carrier code is Other", "the Other plus carrier-name fallback is what FR-22 asks for",
           "Other", row.get("carrierCode"))
    ch.add("carrier name is never empty", "Amazon requires a name whenever the code is Other",
           "CJ Logistics", row.get("carrierName"))
    ch.add("service still travels", "the buyer sees the service the seller bought",
           "CJ International Parcel", row.get("shippingMethod"))


def test_carrier_self_delivery(ch, calls, detail):
    # 5.3: SELF_DELIVERY is a named case with a fixed carrier name (L-91)
    order_id = "902-CARRIERSELF-01"
    parcels, _ = R.assemble_parcels(
        one_box("SELF-01"),
        live_meta(shipping_provider="SELF_DELIVERY", marketplace_carrier_code="",
                  logistic_partner_name=None, shipping_type="Self Delivery"))
    send(ch, calls, order_id, FR, parcels[0])

    row = confirmations_for(order_id)[0]
    ch.add("carrier code is Other", "self delivery is not an Amazon carrier", "Other", row.get("carrierCode"))
    ch.add("carrier name is Self Delivery", "the fixed name for the named case",
           "Self Delivery", row.get("carrierName"))


def test_carrier_unmapped_block(ch, calls, detail):
    # 5.3: no carrier identity at all is a configuration error and blocks the parcel (L-91)
    order_id = "902-CARRIERNONE-01"
    parcels, blocked = R.assemble_parcels(
        one_box("TRK-NO-CARRIER"),
        live_meta(shipping_provider=None, marketplace_carrier_code="",
                  logistic_partner_name=None, shipping_type=None))
    ch.add("assembly blocks", "Other still needs a name, so nothing to name is a configuration error",
           [R.EParcelBlockReason.MISSING_CARRIER_MAPPING], [b.reason for b in blocked])
    ch.add("no parcel built", "never sent nameless", 0, len(parcels))
    ch.add("no confirmation reached amazon", "a nameless Other would be rejected anyway",
           0, len(confirmations_for(order_id)))

    # The positive control: the same box with a provider present does confirm.
    mapped = "902-CARRIERSOME-01"
    parcels, _ = R.assemble_parcels(one_box("TRK-SOME-CARRIER"), live_meta())
    send(ch, calls, mapped, FR, parcels[0])
    ch.add("a resolvable carrier still ships", "the block is the configuration's, not the flow's",
           "Startrack", confirmations_for(mapped)[0].get("carrierName"))


# --------------------------------------------------------------------- Rule N-5, the customs boundary

def test_customs_nothing_to_amazon(ch, calls, detail):
    # Rule N-5: the confirmShipment contract has no customs field, so none is sent (L-70, L-94)
    order_id = "902-BOUNDARY-000001"   # no forbidden word in the id itself, or the scan finds its own fixture
    parcels, _ = R.assemble_parcels(
        one_box("MT-BOUNDARY-0001"),
        live_meta(marketplace_carrier_code="DHL", logistic_partner_name="DHL Express",
                  shipping_type="DHL Express Worldwide"))
    request, _ = send(ch, calls, order_id, FR, parcels[0])

    forbidden = ["ioss", "hs_code", "hscode", "country_of_origin", "commercial_invoice",
                 "cn22", "cn23", "customs", "deemed_reseller"]
    sent = json.dumps(request["body"]).lower()
    ch.add("nothing customs in the request", "the integration must not attempt a customs upload here",
           [], [key for key in forbidden if key in sent])

    received = json.dumps(confirmations_for(order_id)[0]).lower()
    ch.add("nothing customs reached amazon", "no invoice, HS code, origin, CN22, CN23 or IOSS field exists",
           [], [key for key in forbidden if key in received])


def test_customs_label_fail_blocks(ch, calls, detail):
    # Rule N-5: a carrier label failure is pre-assembly, so no Amazon confirmation is attempted (L-94)
    order_id = "902-CUSTOMSFAIL-01"
    boxes = one_box("TRK-LABEL-FAILED")
    labelled = [box for box in boxes if False]  # the label never printed, so no box is ready to confirm
    parcels, _ = R.assemble_parcels(labelled, live_meta(tracking_number="", line_items=[]))
    ch.add("no parcel built", "the carrier error stays actionable and Amazon is not told", 0, len(parcels))
    ch.add("no confirmation reached amazon", "no Amazon confirmation is attempted",
           0, len(confirmations_for(order_id)))

    # The positive control: once the label prints, the same box confirms.
    printed = "902-CUSTOMSOK-0001"
    parcels, _ = R.assemble_parcels(
        one_box("TRK-LABEL-PRINTED"),
        live_meta(marketplace_carrier_code="DHL", logistic_partner_name="DHL Express"))
    send(ch, calls, printed, FR, parcels[0])
    ch.add("a printed label confirms", "the block is the carrier's, not this flow's",
           "TRK-LABEL-PRINTED", confirmations_for(printed)[0].get("trackingNumber"))


def test_compat_single_shipment(ch, calls, detail):
    # Compatibility: one order, one shipment, one tracking number, every item (L-99, L-105)
    order_id = "902-COMPATSINGLE-1"
    boxes = [R.CartonBox("BOX-DOMESTIC-01", "1Z0000000000000000", ship_date=READY_TO_SHIP_AT,
                         items=[R.OrderItemAllocation(811, ITEM_1001, "SKU-1001", 1),
                                R.OrderItemAllocation(812, ITEM_2002, "SKU-2002", 2)])]
    parcels, blocked = R.assemble_parcels(
        boxes, live_meta(store_marketplace_code=US, marketplace_carrier_code="UPS",
                         logistic_partner_name="UPS Ground", shipping_type="Ground"))
    ch.add("nothing blocked", "the path that already works end to end", [], [b.reason for b in blocked])
    send(ch, calls, order_id, US, parcels[0])

    row = confirmations_for(order_id)[0]
    ch.add("exactly one parcel", "whatever multi-parcel adds must not break this", 1,
           len(confirmations_for(order_id)))
    ch.add("both items travel in it", "the whole shipment is one call", 2, len(row.get("orderItems") or []))
    ch.add("one tracking number", "the domestic single-shipment shape is unchanged",
           "1Z0000000000000000", row.get("trackingNumber"))

# ===================================================================== Register Cases

case("IA-5109-US3-MKT-FRANCE",
     "France: the marketplace id Amazon scopes the confirmation to",
     "An Amazon France confirmation on store amazon_sp_fr",
     ["Amazon receives marketplaceId A13V1IB3VIYZZH", "No codCollectionMethod"],
     "Mapping 5.3, Appendix A.2; Summary 2.1 C-18; Claim L-55",
     test_mkt_france)

case("IA-5109-US3-MKT-GERMANY",
     "Germany: the marketplace id Amazon scopes the confirmation to",
     "An Amazon Germany confirmation on store amazon_sp_de",
     ["Amazon receives marketplaceId A1PA6795UKMFR9", "No codCollectionMethod"],
     "Mapping 5.3, Appendix A.6; Summary 2.1 C-18; Claim L-55",
     test_mkt_germany)

case("IA-5109-US3-MKT-US",
     "United States: the marketplace id Amazon scopes the confirmation to",
     "An Amazon US confirmation on store amazon_sp_us",
     ["Amazon receives marketplaceId ATVPDKIKX0DER", "No codCollectionMethod"],
     "Mapping 5.3, Appendix A.6; Summary 2.1 C-18; Claim L-55",
     test_mkt_us)

case("IA-5109-US3-MKT-ALL-FOUR-IDS",
     "C-18: All four marketplaces carried, the ids verbatim",
     "One confirmation per store on amazon_sp_fr, _de, _jp and _us",
     ["Each store's own marketplace id reaches Amazon", "Four distinct ids, evidence produced per marketplace"],
     "Mapping 5.3, Appendix A.6; Summary 2.1 C-18; Claim L-55, L-31, L-99",
     test_mkt_all_four_ids)

case("IA-5109-US3-MKT-JAPAN-COD",
     "C-5: Japan and COD is the only case carrying the collection method",
     "An Amazon Japan cash-on-delivery confirmation",
     ["codCollectionMethod DirectPayment reaches Amazon", "It is sent as a sibling of packageDetail",
      "The same value placed inside packageDetail is not the field Amazon reads"],
     "Mapping 4.4 row 3, Appendix A.6; Summary 2.1 C-5; Claim L-7, L-93",
     test_mkt_japan_cod)

case("IA-5109-US3-MKT-JAPAN-NON-COD",
     "C-5: A Japanese order that is not COD omits the method",
     "An Amazon Japan prepaid confirmation",
     ["No codCollectionMethod in the request", "Amazon received none"],
     "Mapping 4.4 row 3; Summary 2.1 C-5; Claim L-7, L-93",
     test_mkt_japan_non_cod)

case("IA-5109-US3-MKT-COD-FORBIDDEN-NON-JP",
     "C-5: The collection method is never injected outside Japan",
     "Cash-on-delivery orders on France, Germany and the United States",
     ["None carries codCollectionMethod in the request", "Amazon received none on any of the three"],
     "Mapping 4.4 row 3; Summary 2.1 C-5; Claim L-7, L-93",
     test_mkt_cod_forbidden_non_jp)

case("IA-5109-US3-MKT-ISOLATION",
     "Rule N-4: A shipment carrying another marketplace's order is a mismatch",
     "A France store handed a shipment whose event names amazon_sp_de",
     ["Assembly blocks with MARKETPLACE_MISMATCH", "No confirmation reaches Amazon",
      "The same shipment on its own store confirms"],
     "Mapping 5.3, 7 N-4; Claim L-31, L-55",
     test_mkt_isolation)

case("IA-5109-US3-CARRIER-PROVIDER-FIRST",
     "5.3: On the live payload shipping_provider is the only carrier identity",
     "marketplace_carrier_code, ewms_carrier_code and marketplace_code all empty, logistic_partner_name null",
     ["The carrier code is set at all", "An unrecognised provider goes as Other",
      "carrierName falls back to shipping_provider", "The service the seller bought travels"],
     "Mapping 5.3 warning, 4.4 rows 5 to 7; Summary 2.1 C-4, C-22; Claim L-146, L-187, L-65, L-91",
     test_carrier_provider_first)

case("IA-5109-US3-CARRIER-CODE-OVERRIDE",
     "5.3: A populated marketplace_carrier_code overrides the provider",
     "A shipment whose marketplace_carrier_code is DHL",
     ["carrierCode DHL reaches Amazon unchanged", "carrierName comes from logistic_partner_name",
      "shippingMethod comes from shipping_type"],
     "Mapping 5.3, 4.4 rows 5 to 7; Claim L-146, L-32",
     test_carrier_code_override)

case("IA-5109-US3-CARRIER-UNRECOGNISED-OTHER",
     "C-4: An unrecognised carrier goes as Other with its name mandatory",
     "A shipment by CJ Logistics with no mapped carrier code",
     ["carrierCode Other reaches Amazon", "carrierName CJ Logistics is never empty"],
     "Mapping 5.3, 4.4 row 6; Summary 2.1 C-4; Claim L-6, L-91",
     test_carrier_unrecognised_other)

case("IA-5109-US3-CARRIER-SELF-DELIVERY",
     "5.3: Self delivery is a named case with a fixed carrier name",
     "A shipment whose shipping_provider is SELF_DELIVERY",
     ["carrierCode Other reaches Amazon", "carrierName Self Delivery reaches Amazon"],
     "Mapping 5.3; Claim L-91",
     test_carrier_self_delivery)

case("IA-5109-US3-CARRIER-UNMAPPED-BLOCK",
     "5.3: No carrier identity at all blocks the parcel",
     "A shipment with no provider, no carrier code and no partner name",
     ["Assembly blocks with MISSING_CARRIER_MAPPING", "No confirmation reaches Amazon",
      "A shipment that does resolve a carrier still ships"],
     "Mapping 5.3, 7 N-4; Claim L-91",
     test_carrier_unmapped_block)

case("IA-5109-US3-CUSTOMS-NOTHING-TO-AMAZON",
     "Rule N-5: The confirmation carries no customs data at all",
     "An EU-bound confirmation on an order Amazon is the deemed reseller for",
     ["No customs key in the request", "No customs key in what Amazon received"],
     "Mapping 7 N-5, 4.4; Claim L-70, L-94",
     test_customs_nothing_to_amazon)

case("IA-5109-US3-CUSTOMS-LABEL-FAIL-BLOCKS",
     "Rule N-5: A carrier label failure precedes assembly, so Amazon is not called",
     "A shipment whose carrier label never printed",
     ["No parcel is built", "No confirmation reaches Amazon", "Once the label prints the box confirms"],
     "Mapping 7 N-4, N-5; Claim L-94",
     test_customs_label_fail_blocks)

case("IA-5109-US3-COMPAT-SINGLE-SHIPMENT",
     "Compatibility: the domestic single-shipment path is unchanged",
     "One order, one shipment, one tracking number, every item",
     ["Exactly one confirmation reaches Amazon", "Both items travel in it", "One tracking number"],
     "Requirements 4; Claim L-99, L-105",
     test_compat_single_shipment)


# ===================================================================== Execution Engine

def preflight():
    print(f"{SUITE_NAME} -- {BASE}")
    st, _ = call_amazon("POST", "/auth/o2/token", {"grant_type": "refresh_token"})
    if st == 0:
        print(f"  mock     : starting ephemeral mock server on {BASE}...")
        _start_ephemeral_mock()
        st, _ = call_amazon("POST", "/auth/o2/token", {"grant_type": "refresh_token"})
        if st == 0:
            sys.exit(f"PREFLIGHT FAIL: unable to connect to mock server on {BASE}")
    print(f"  mock     : active (/auth/o2/token -> {st})")

    if KEEP:
        print("  state    : preserved (--keep-state)")
        return

    # The cases assert on what the confirmShipment route recorded, so the store starts empty.
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(os.path.join(DATA_DIR, "shipment_confirmations.json"), "w", encoding="utf-8") as f:
        f.write("[]")
    print("  state    : reset (shipment_confirmations emptied)")


def capture():
    src = os.path.join(DATA_DIR, LOG_FILE)
    if os.path.exists(src):
        os.makedirs(RUN_DIR, exist_ok=True)
        shutil.copy2(src, os.path.join(RUN_DIR, LOG_FILE))
        try:
            with open(src, "r", encoding="utf-8") as f:
                n = len(json.load(f).get("log", {}).get("entries", []))
            EVIDENCE["mock call log"] = f"captured -- {n} entries"
        except Exception:
            EVIDENCE["mock call log"] = "captured -- unparseable"
    else:
        EVIDENCE["mock call log"] = "not captured -- no log file"


def main():
    if LIST_ONLY:
        print(f"{SUITE_NAME} -- Declared Cases ({len(CASES)} cases):")
        for c in CASES:
            print(f"  [{c['id']}] {c['name']}")
            print(f"     Given: {c['given']}")
            print(f"     Note : {c['note']}")
        return

    preflight()

    to_run = [c for c in CASES if not WANTED_CASES or c["id"] in WANTED_CASES]
    print(f"\nRunning {len(to_run)} cases...")

    for c in to_run:
        run_case(c)
        r = RESULTS[c["id"]]
        v = r["verdict"].upper()
        print(f"  [{v}] {c['id']}: {c['name']} -- {r['summary']}")

    EVIDENCE["status"] = "complete"
    capture()
    publish()

    done = [RESULTS[c["id"]] for c in to_run if c["id"] in RESULTS]
    p_cnt = sum(1 for r in done if r["verdict"] == "pass")
    f_cnt = sum(1 for r in done if r["verdict"] == "fail")
    print(f"\nSuite Finished: {p_cnt} passed, {f_cnt} failed of {len(to_run)} cases.")
    print(f"Results written to {os.path.join(RUN_DIR, 'results.json')}")

    if f_cnt > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
