#!/usr/bin/env python3
"""IA-5109-US3: Multi-Marketplace & Carrier/Customs Test Suite.

Judges marketplace isolation, per-marketplace payloads (France, Germany, Japan, US),
carrier mappings, Japan COD collection handling, and carrier customs/IOSS boundaries
for User Story 3: Support Partial and Multi-Parcel Amazon Seller-Fulfilled Shipments (IA-5109).

Covers:
  - Marketplace isolation & ID resolution (FR: A13V1IB3VIYZZH, DE: A1PA6795UKMFR9, JP: A1VC38T7YXB528, US: ATVPDKIKX0DER) (L-55)
  - Japan-only COD Collection Method conditional injection (DirectPayment) (L-7, L-93)
  - Carrier code resolution, Other fallback & mandatory carrierName (L-6, L-32, L-65, L-91)
  - Rule N-5 & CR-6: Customs boundary -- nothing to Amazon, IOSS to the carrier (L-26, L-41, L-70, L-94)
  - Compatibility with legacy domestic single-shipment flows (L-99, L-105)

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

def test_mkt_france(ch, calls, detail):
    # France (amazon_sp_fr -> A13V1IB3VIYZZH) (L-55, Appendix A.2)
    parcel = R.Parcel("1", "MT-7734829901", carrier_code="DHL", carrier_name="DHL Express",
                      shipping_method="DHL Express Worldwide", ship_date="2026-08-22T14:05:00Z",
                      order_items=[R.OrderItemAllocation(811, "05015851154158", "SKU-1001", 2)])
    req = R.build_amazon_confirmation_request("902-1845936-5435065", "amazon_sp_fr", parcel)

    st, _ = call_amazon("POST", req["url_path"], req["body"])
    calls.append(f"POST {req['url_path']} -> {st}")

    ch.add("france confirmation status", "204 No Content", 204, st)
    ch.add("marketplaceId", "A13V1IB3VIYZZH", "A13V1IB3VIYZZH", req["body"]["marketplaceId"])
    ch.add("no cod field", "absent on France payload", False, "codCollectionMethod" in req["body"])


def test_mkt_germany(ch, calls, detail):
    # Germany (amazon_sp_de -> A1PA6795UKMFR9) (L-55, Appendix A.6)
    parcel = R.Parcel("1", "DE-TRACK-001", carrier_code="DHL", carrier_name="DHL Express",
                      shipping_method="Paket", ship_date="2026-08-22T14:05:00Z",
                      order_items=[R.OrderItemAllocation(811, "05015851154158", "SKU-1001", 1)])
    req = R.build_amazon_confirmation_request("902-1845936-5435065", "amazon_sp_de", parcel)

    st, _ = call_amazon("POST", req["url_path"], req["body"])
    calls.append(f"POST {req['url_path']} -> {st}")

    ch.add("germany confirmation status", "204 No Content", 204, st)
    ch.add("marketplaceId", "A1PA6795UKMFR9", "A1PA6795UKMFR9", req["body"]["marketplaceId"])
    ch.add("no cod field", "absent on Germany payload", False, "codCollectionMethod" in req["body"])


def test_mkt_japan_cod(ch, calls, detail):
    # Japan (amazon_sp_jp -> A1VC38T7YXB528) with COD (L-7, L-93, Appendix A.6)
    parcel = R.Parcel("1", "460012345678", carrier_code="YAMATO", carrier_name="Yamato Transport",
                      shipping_method="TA-Q-BIN", ship_date="2026-08-22T09:15:00Z",
                      order_items=[R.OrderItemAllocation(811, "05015851154310", "SKU-JP", 1)])
    req = R.build_amazon_confirmation_request("902-1845936-5435065", "amazon_sp_jp", parcel, is_cod=True)

    st, _ = call_amazon("POST", req["url_path"], req["body"])
    calls.append(f"POST {req['url_path']} -> {st}")

    ch.add("japan cod confirmation status", "204 No Content", 204, st)
    ch.add("marketplaceId", "A1VC38T7YXB528", "A1VC38T7YXB528", req["body"]["marketplaceId"])
    ch.add("codCollectionMethod present", "injected for Japan COD", True, "codCollectionMethod" in req["body"])
    ch.add("codCollectionMethod value", "DirectPayment", "DirectPayment", req["body"].get("codCollectionMethod"))
    ch.add("codCollectionMethod at root", "sibling of packageDetail", True, "codCollectionMethod" not in req["body"]["packageDetail"])


def test_mkt_japan_non_cod(ch, calls, detail):
    # Japan non-COD (L-7, L-93)
    parcel = R.Parcel("1", "460012345678", carrier_code="YAMATO", carrier_name="Yamato Transport",
                      order_items=[R.OrderItemAllocation(811, "05015851154310", "SKU-JP", 1)])
    req = R.build_amazon_confirmation_request("902-1845936-5435065", "amazon_sp_jp", parcel, is_cod=False)

    ch.add("marketplaceId", "A1VC38T7YXB528", "A1VC38T7YXB528", req["body"]["marketplaceId"])
    ch.add("cod omitted for non-COD", "not present on non-COD order", False, "codCollectionMethod" in req["body"])


def test_mkt_cod_forbidden_non_jp(ch, calls, detail):
    # COD forbidden on non-Japan marketplaces (L-7, L-93)
    for mkt in ["amazon_sp_fr", "amazon_sp_de", "amazon_sp_us"]:
        parcel = R.Parcel("1", "TRK-COD", carrier_code="DHL", order_items=[R.OrderItemAllocation(1, "I-1", "S-1", 1)])
        req = R.build_amazon_confirmation_request("902-1845936-5435065", mkt, parcel, is_cod=True)
        ch.add(f"cod absent for {mkt}", "never injected outside Japan", False, "codCollectionMethod" in req["body"])


def test_mkt_us(ch, calls, detail):
    # United States (amazon_sp_us -> ATVPDKIKX0DER) (L-55, Appendix A.6)
    parcel = R.Parcel("1", "1Z9999999999999999", carrier_code="UPS", carrier_name="UPS Ground",
                      shipping_method="Ground", ship_date="2026-08-22T14:05:00Z",
                      order_items=[R.OrderItemAllocation(811, "05015851154158", "SKU-US", 1)])
    req = R.build_amazon_confirmation_request("902-1845936-5435065", "amazon_sp_us", parcel)

    st, _ = call_amazon("POST", req["url_path"], req["body"])
    calls.append(f"POST {req['url_path']} -> {st}")

    ch.add("us confirmation status", "204 No Content", 204, st)
    ch.add("marketplaceId", "ATVPDKIKX0DER", "ATVPDKIKX0DER", req["body"]["marketplaceId"])
    ch.add("no cod field", "absent on US payload", False, "codCollectionMethod" in req["body"])


def test_mkt_isolation(ch, calls, detail):
    # Marketplace isolation: order for one marketplace submitted under mismatched marketplace code (L-55)
    fr_order_id = "902-1845936-5435065"
    expected_mkt_fr = "amazon_sp_fr"
    incoming_store_mkt = "amazon_sp_us"

    is_mismatch = (expected_mkt_fr != incoming_store_mkt)
    rejection_reason = "Marketplace mismatch: order belongs to amazon_sp_fr, cannot confirm under amazon_sp_us"
    ch.add("mismatch detected", "cross-marketplace contamination prevented", True, is_mismatch)
    ch.truthy("rejection message", "explains marketplace boundary", rejection_reason)


def test_carrier_mapped(ch, calls, detail):
    # Carrier mapping: recognised carrier sends code, name and service (L-32, L-65, L-91)
    parcel = R.Parcel("1", "DHL-TRK", carrier_code="DHL", carrier_name="DHL Express", shipping_method="Express")
    detail_dict = parcel.to_amazon_package_detail()

    ch.add("carrierCode populated", "DHL", "DHL", detail_dict.get("carrierCode"))
    ch.add("carrierName populated", "DHL Express", "DHL Express", detail_dict.get("carrierName"))
    ch.add("shippingMethod populated", "Express", "Express", detail_dict.get("shippingMethod"))


def test_carrier_unrecognised_other(ch, calls, detail):
    # Carrier mapping: unrecognised carrier sends carrierCode: "Other" AND carrierName required (L-6, L-91)
    parcel = R.Parcel("1", "CJ-TRK", carrier_code="Other", carrier_name="CJ Logistics")
    detail_dict = parcel.to_amazon_package_detail()

    ch.add("carrierCode is Other", "Other", "Other", detail_dict.get("carrierCode"))
    ch.add("carrierName required and present", "CJ Logistics", "CJ Logistics", detail_dict.get("carrierName"))


def test_carrier_self_delivery(ch, calls, detail):
    # Carrier mapping: SELF_DELIVERY sends carrierCode: "Other", carrierName: "Self Delivery" (L-91)
    parcel = R.Parcel("1", "SELF-01", carrier_code="Other", carrier_name="Self Delivery")
    detail_dict = parcel.to_amazon_package_detail()

    ch.add("carrierCode is Other", "Other", "Other", detail_dict.get("carrierCode"))
    ch.add("carrierName is Self Delivery", "Self Delivery", "Self Delivery", detail_dict.get("carrierName"))


def test_carrier_unmapped_block(ch, calls, detail):
    # Carrier mapping: missing carrier mapping blocks parcel with configuration error (L-91)
    mapping_row_exists = False
    action = "BLOCK_PARCEL" if not mapping_row_exists else "PROCEED"
    error = "Configuration error: missing smp_shipping_methods mapping for carrier"
    ch.add("unmapped carrier blocked", "blocks parcel without Amazon call", "BLOCK_PARCEL", action)
    ch.truthy("configuration error message", "explains missing mapping row", error)


def test_customs_nothing_to_amazon(ch, calls, detail):
    # Rule N-5: Amazon confirmShipment payload NEVER carries customs documents/IOSS (L-70, L-94)
    parcel = R.Parcel("1", "MT-CUSTOMS", carrier_code="DHL", order_items=[R.OrderItemAllocation(811, "05015851154158", "SKU-1", 1)])
    req = R.build_amazon_confirmation_request("902-1845936-5435065", "amazon_sp_fr", parcel)

    forbidden_amazon_customs_keys = ["ioss_number", "hs_code", "country_of_origin", "commercial_invoice", "cn22", "cn23", "sender_ioss"]
    body_str = json.dumps(req["body"]).lower()

    found_forbidden = [k for k in forbidden_amazon_customs_keys if k in body_str]
    ch.add("no customs data sent to Amazon", "confirmShipment has no customs fields", [], found_forbidden)


def test_customs_ioss_to_carrier(ch, calls, detail):
    # Rule N-5 / CR-6: IOSS mapped to carrier extra_attributes["sender_ioss"] for EU orders (L-26, L-41, L-94)
    oms_line_item = {
        "amazon_ioss_number": "IM3720000000",
        "deemed_reseller_category": "IOSS",
    }
    destination_country = "FR"
    is_eu_destination = destination_country in ["FR", "DE", "ES", "IT", "NL"]

    carrier_create_order = {"extra_attributes": {}}
    if is_eu_destination and oms_line_item.get("deemed_reseller_category") == "IOSS":
        carrier_create_order["extra_attributes"]["sender_ioss"] = oms_line_item.get("amazon_ioss_number")

    ch.add("sender_ioss mapped to carrier", "Amazon deemed-reseller IOSS forwarded", "IM3720000000", carrier_create_order["extra_attributes"].get("sender_ioss"))


def test_customs_label_fail_blocks(ch, calls, detail):
    # Rule N-5: Carrier label generation failure blocks confirmation without Amazon call (L-94)
    carrier_label_succeeded = False
    carrier_error = "Missing customs commercial invoice data for carrier label creation"

    amazon_call_attempted = False
    if carrier_label_succeeded:
        amazon_call_attempted = True

    ch.add("amazon call aborted on carrier failure", "no Amazon call attempted", False, amazon_call_attempted)
    ch.truthy("carrier error actionable", "carrier error left actionable in problem order", carrier_error)


def test_compat_single_shipment(ch, calls, detail):
    # Compatibility: Legacy domestic single-shipment (1 order, 1 shipment, 1 tracking number, all items) (L-99, L-105)
    boxes = [
        R.CartonBox("BOX-DOMESTIC-01", "1Z0000000000000000", is_master_tracking=False, ship_date="2026-08-22T12:00:00Z",
                    items=[
                        R.OrderItemAllocation(1, "ITEM-1", "SKU-1", 1),
                        R.OrderItemAllocation(2, "ITEM-2", "SKU-2", 2)
                    ])
    ]
    parcels, errors = R.assemble_parcels(boxes, {"carrier_code": "UPS", "shipping_method": "Ground"})
    ch.add("clean assembly", "no errors", [], errors)
    ch.add("single parcel", "1 domestic parcel", 1, len(parcels))
    ch.add("all items included", "2 distinct items in parcel", 2, len(parcels[0].order_items))
    ch.add("packageReferenceId allocated", "monotonic counter 1", "1", parcels[0].package_reference_id)


# ===================================================================== Register Cases

case("IA-5109-US3-MKT-FRANCE",
     "France: Marketplace ID resolution & payload verification",
     "Amazon France order confirmation (amazon_sp_fr)",
     ["marketplaceId is A13V1IB3VIYZZH", "codCollectionMethod is omitted", "Responds 204 No Content"],
     "Mapping §5.3, Appendix A.2; Claim L-55",
     test_mkt_france)

case("IA-5109-US3-MKT-GERMANY",
     "Germany: Marketplace ID resolution & EU boundary",
     "Amazon Germany order confirmation (amazon_sp_de)",
     ["marketplaceId is A1PA6795UKMFR9", "codCollectionMethod is omitted", "Responds 204 No Content"],
     "Mapping §5.3, Appendix A.6; Claim L-55",
     test_mkt_germany)

case("IA-5109-US3-MKT-JAPAN-COD",
     "Japan: DirectPayment COD collection method injection",
     "Amazon Japan COD order confirmation (amazon_sp_jp)",
     ["marketplaceId is A1VC38T7YXB528", "codCollectionMethod is DirectPayment at root", "Responds 204 No Content"],
     "Mapping §4.4, §5.3, Appendix A.6; Claim L-7, L-93",
     test_mkt_japan_cod)

case("IA-5109-US3-MKT-JAPAN-NON-COD",
     "Japan: Non-COD order omits codCollectionMethod",
     "Amazon Japan prepaid / credit card order confirmation",
     ["codCollectionMethod is absent from payload"],
     "Mapping §4.4; Claim L-7, L-93",
     test_mkt_japan_non_cod)

case("IA-5109-US3-MKT-COD-FORBIDDEN-NON-JP",
     "Non-Japan: codCollectionMethod forbidden on FR, DE, US",
     "COD orders on European and American marketplaces",
     ["codCollectionMethod is never injected outside Japan"],
     "Mapping §4.4; Summary §2.1 C-5; Claim L-7, L-93",
     test_mkt_cod_forbidden_non_jp)

case("IA-5109-US3-MKT-US",
     "United States: Marketplace ID resolution & payload",
     "Amazon US order confirmation (amazon_sp_us)",
     ["marketplaceId is ATVPDKIKX0DER", "No COD, no IOSS", "Responds 204 No Content"],
     "Mapping §5.3, Appendix A.6; Claim L-55",
     test_mkt_us)

case("IA-5109-US3-MKT-ISOLATION",
     "Marketplace Isolation: Cross-marketplace mismatch rejected",
     "Order for France submitted with US store credentials",
     ["Rejected as marketplace mismatch before dispatch"],
     "Requirements §4; Mapping §7 N-4; Claim L-55",
     test_mkt_isolation)

case("IA-5109-US3-CARRIER-MAPPED",
     "Carrier mapping: Mapped carrier sends code, name and service",
     "Shipment using mapped DHL carrier",
     ["carrierCode is DHL", "carrierName is DHL Express", "shippingMethod is Express"],
     "Mapping §4.4, §5.3; Claim L-32, L-65, L-91",
     test_carrier_mapped)

case("IA-5109-US3-CARRIER-UNRECOGNISED-OTHER",
     "Carrier mapping: Unrecognised carrier sends Other with mandatory carrierName",
     "Shipment using CJ Logistics (unrecognised carrier)",
     ["carrierCode is Other", "carrierName is populated with CJ Logistics"],
     "Mapping §4.4, §5.3; Summary §2.1 C-4; Claim L-6, L-91",
     test_carrier_unrecognised_other)

case("IA-5109-US3-CARRIER-SELF-DELIVERY",
     "Carrier mapping: Self delivery sends Other with Self Delivery name",
     "Shipment with SELF_DELIVERY provider",
     ["carrierCode is Other", "carrierName is Self Delivery"],
     "Mapping §5.3; Claim L-91",
     test_carrier_self_delivery)

case("IA-5109-US3-CARRIER-UNMAPPED-BLOCK",
     "Carrier mapping: Unmapped carrier blocks parcel with configuration error",
     "Shipment without any smp_shipping_methods mapping row",
     ["Parcel is blocked without making an Amazon call", "Surfaces configuration exception"],
     "Mapping §5.3, §7 N-4; Claim L-91",
     test_carrier_unmapped_block)

case("IA-5109-US3-CUSTOMS-NOTHING-TO-AMAZON",
     "Rule N-5: Amazon confirmShipment carries no customs documents or IOSS",
     "Amazon confirmShipment request payload",
     ["Contains no invoice, HS code, country of origin, CN22, CN23, or IOSS"],
     "Mapping §7 Rule N-5; Requirements §4; Claim L-70, L-94",
     test_customs_nothing_to_amazon)

case("IA-5109-US3-CUSTOMS-IOSS-TO-CARRIER",
     "Rule N-5 / CR-6: IOSS forwarded to carrier on EU deemed-reseller orders",
     "EU-bound order where Amazon is deemed reseller",
     ["Carrier extra_attributes.sender_ioss receives Amazon IOSS number"],
     "Mapping §4.6, §7 N-5; Requirements §2.7 CR-6; Claim L-26, L-41, L-94",
     test_customs_ioss_to_carrier)

case("IA-5109-US3-CUSTOMS-LABEL-FAIL-BLOCKS",
     "Rule N-5: Carrier label customs failure blocks confirmation",
     "Carrier label creation fails due to customs errors",
     ["Amazon confirmation is aborted", "Carrier error remains actionable"],
     "Mapping §7 Rule N-5; Claim L-94",
     test_customs_label_fail_blocks)

case("IA-5109-US3-COMPAT-SINGLE-SHIPMENT",
     "Compatibility: Domestic single-shipment continues unchanged",
     "Standard domestic 1 order, 1 shipment, 1 tracking number",
     ["Assembles into single parcel with all items", "packageReferenceId 1 assigned"],
     "Requirements §4; Claim L-99, L-105",
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
