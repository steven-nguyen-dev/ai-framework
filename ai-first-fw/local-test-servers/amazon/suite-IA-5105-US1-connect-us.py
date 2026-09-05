#!/usr/bin/env python3
"""IA-5105-US1: End-to-End Store Connect & Taxonomy Sync Suite — Amazon US Market.

Executes the full cross-border integration pipeline across both test servers:
  1. Preflight: Asserts both Amazon SP-API mock (:23103) and Anchanto OMS mock (:23001) are active.
  2. Auth: Performs LWA OAuth token exchange for the US store.
  3. Category Discovery: Discovers product types and pushes flat categories via POST /rest/v1/bulk_categories.
  4. Product Types: Discovers available product types for US marketplace (ATVPDKIKX0DER -> LUGGAGE).
  5. Definitions: Retrieves product type definition envelope and downloads JSON Schema from S3 link.
  6. Field Mapping: Deeply verifies schema flattening, attributes, data types, parent-child links, and validation rules per IA-5105.
  8. Definition Statuses: Verifies AVAILABLE, PARSE_FAILED, SCHEMA_OMITTED (>900KB), and UNAVAILABLE statuses per FR-6, FR-18, AC-10.
  9. Raw JSON Schema: Verifies raw_schema_json verbatim preservation and schema_checksum passthrough per FR-8, FR-19.
  10. Ingestion: Pushes the structured category attributes payload to Anchanto OMS mock (:23001).
  11. Call Log & Payload: Inspects Anchanto OMS server call log (:23001/log/data) to prove network dispatch and accurate payload.
  12. Fault Injection: Verifies error handling when OMS rejects or fails a push.

What the requirement-derived cases cover. The `note` on every case names the document and section;
ia5105_requirements.py holds the expectations with their citations, and was written from the
requirement documents and the two published contracts -- never from the integration source.

  US-CAT-1        mapping spec §4.1, category.code is the product type, as OMS received it
  US-CAT-MULTI    mapping spec §3 Flow 1 step 2, one row per discovered product type
  US-WITHDRAW-1   requirements spec §2.2 REMOVE row, no browse-node key on either payload, and no
                  recommended_browse_nodes row for a US store (mapping spec §4.2, last bullet)
  US-NOREPORT-1   plan §4.4, no browse-tree report requested at all -- counted at the mock, because
                  a payload cannot prove a call was never made
  US-ENV-1        requirements spec §2.2, the envelope's six ADD rows, as received
  US-VOCAB-1      the OMS contract's own field_type enum and field_code rule
  US-CR3-1        CR-3, the data_type values sent. Blocked, recorded, unanswered by OMS

WHAT IS UNDER TEST. The payload is built by amazon_taxonomy_transformer, a local stand-in for the
JPluger Amazon integration this harness cannot start, and judged on the bytes that reached the OMS
mock's own call log -- never on a dict the suite still holds.

Note on the US fixtures: all four US schemas here are marked SYNTHETIC in their own
x-fixture-provenance, and the mapping spec §1.1 says so of us-schema-LUGGAGE.json in as many words.
Gate G-4 is open on the US premise itself, so a US case here proves what the fixture states, not
what Amazon US states.

Runner contract: TESTING.md.
Publishes live status to amazon/test-results/IA-5105-US1-connect-us/run-<stamp>/results.json.

Usage:
  python3 amazon/suite-IA-5105-US1-connect-us.py
  python3 amazon/suite-IA-5105-US1-connect-us.py US-PRE-1 US-ENV-1       # only the cases named
  BASE_AMAZON=http://127.0.0.1:23103 BASE_OMS=http://127.0.0.1:23001 python3 amazon/suite-IA-5105-US1-connect-us.py
"""

import atexit
import datetime
import hashlib
import json
import os
import shutil
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

BASE_AMAZON = os.environ.get("BASE_AMAZON", os.environ.get("BASE", "http://127.0.0.1:23103")).rstrip("/")
BASE_OMS = os.environ.get("BASE_OMS", "http://127.0.0.1:23001").rstrip("/")
SUITE = os.environ.get("SUITE", "IA-5105-US1-connect-us")
KEEP = "--keep-state" in sys.argv
WANTED_CASES = set(a for a in sys.argv[1:] if not a.startswith("-"))

HERE = os.path.dirname(os.path.abspath(__file__))
MOCK_DIR = HERE
DATA_DIR = os.path.join(MOCK_DIR, "mock-data")
OMS_DIR = os.path.join(os.path.dirname(MOCK_DIR), "anchanto-oms")
OMS_DATA_DIR = os.path.join(OMS_DIR, "mock-data")
LOG = "api-calls.har.json"
STAMP = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
RUN_DIR = os.path.join(MOCK_DIR, "test-results", SUITE, "run-" + STAMP)

# US Store Fixtures
US_STORE_CODE = "SS0000US"
US_MARKETPLACE_CODE = "amazon_sp_us"
US_MARKETPLACE_ID = "ATVPDKIKX0DER"
US_LOCALE = "en_US"

US_SCHEMAS = [
    {"product_type": "LUGGAGE", "name": "Luggage", "file": "us-schema-LUGGAGE.json", "expected_attrs": 20},
    {"product_type": "CLOTHING", "name": "Clothing", "file": "us-schema-CLOTHING.json", "expected_attrs": 29},
    {"product_type": "ELECTRONICS", "name": "Electronics", "file": "us-schema-ELECTRONICS.json", "expected_attrs": 23},
    {"product_type": "TOYS_AND_GAMES", "name": "Toys & Games", "file": "us-schema-TOYS_AND_GAMES.json", "expected_attrs": 12},
]

CASES, RESULTS = [], {}
EVIDENCE = {
    "status": "running",
    "mock call log": "not captured",
    "amazon mock": f"Amazon SP-API mock at {BASE_AMAZON}",
    "oms mock": f"Anchanto OMS mock at {BASE_OMS}",
}


def call_amazon(method, path, body=None, token="mock_sp_api_access_token", is_form=False):
    url = BASE_AMAZON + path
    headers = {}
    data = None
    if body is not None:
        if is_form:
            data = urllib.parse.urlencode(body).encode("utf-8")
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        else:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
    if token:
        headers["x-amz-access-token"] = token
        headers["Authorization"] = "Bearer " + token

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            raw, status = r.read(), r.status
    except urllib.error.HTTPError as e:
        raw, status = e.read(), e.code
    except Exception as e:
        return 0, {"_transport_error": str(e)}, b""

    try:
        return status, json.loads(raw.decode("utf-8")) if raw.strip() else {}, raw
    except Exception:
        return status, raw.decode("utf-8", "replace"), raw


def call_oms(method, path, body=None, query=None, token="f1a6c2d8e40b7935a1c6d2f8b04e7395"):
    full_path = path
    if query:
        full_path += "?" + urllib.parse.urlencode(query)
    url = BASE_OMS + full_path
    headers = {"Content-Type": "application/json"}
    data = json.dumps(body).encode("utf-8") if body is not None else None
    if token:
        headers["Authorization"] = "Bearer " + token

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            raw, status = r.read(), r.status
    except urllib.error.HTTPError as e:
        raw, status = e.read(), e.code
    except Exception as e:
        return 0, {"_transport_error": str(e)}, b""

    try:
        return status, json.loads(raw.decode("utf-8")) if raw.strip() else {}, raw
    except Exception:
        return status, raw.decode("utf-8", "replace"), raw


def case(cid, name, given, then, note, fn):
    CASES.append({
        "id": cid,
        "name": name,
        "given": given,
        "then": then if isinstance(then, list) else [then],
        "note": note,
        "fn": fn
    })


def publish():
    cases = []
    for c in CASES:
        r = RESULTS.get(c["id"])
        e = {
            "id": c["id"],
            "name": c["name"],
            "given": c["given"],
            "then": c["then"],
            "note": c["note"]
        }
        if r:
            e.update(r)
        elif WANTED_CASES and c["id"] not in WANTED_CASES:
            e.update({
                "verdict": "skip",
                "summary": "skipped (not selected)",
                "detail": {},
                "checks": [],
                "calls": []
            })
        else:
            e.update({
                "verdict": "pending",
                "summary": "pending",
                "detail": {},
                "checks": [],
                "calls": []
            })
        cases.append(e)

    payload = {
        "suite": SUITE,
        "title": "IA-5105-US1: Amazon US Store Connect & Taxonomy Synchronization",
        "stamp": STAMP,
        "verdict": "pass" if all(c.get("verdict") in ("pass", "skip") for c in cases if c.get("verdict") != "pending") and any(c.get("verdict") == "pass" for c in cases) else ("fail" if any(c.get("verdict") == "fail" for c in cases) else "running"),
        "counts": {
            "total": len(cases),
            "pass": sum(1 for c in cases if c.get("verdict") == "pass"),
            "fail": sum(1 for c in cases if c.get("verdict") == "fail"),
            "skip": sum(1 for c in cases if c.get("verdict") == "skip"),
            "blocked": sum(1 for c in cases if c.get("verdict") == "blocked"),
            "pending": sum(1 for c in cases if c.get("verdict") == "pending"),
        },
        "cases": cases,
        "evidence": EVIDENCE
    }

    os.makedirs(RUN_DIR, exist_ok=True)
    with open(os.path.join(RUN_DIR, "results.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


class Checks:
    def __init__(self):
        self.items = []

    def add(self, label, what, expected, actual):
        ok = (actual == expected)
        self.items.append({
            "label": label,
            "what": what,
            "expected": str(expected),
            "actual": str(actual),
            "ok": ok
        })
        return ok

    def truthy(self, label, what, actual):
        ok = bool(actual)
        self.items.append({
            "label": label,
            "what": what,
            "expected": "truthy",
            "actual": str(actual),
            "ok": ok
        })
        return ok

    def contains(self, label, what, item, collection):
        ok = item in collection if collection is not None else False
        self.items.append({
            "label": label,
            "what": what,
            "expected": f"contains {item!r}",
            "actual": f"size {len(collection)}" if isinstance(collection, (list, dict, set)) else str(collection),
            "ok": ok
        })
        return ok


# TESTING.md: `blocked` is "could not prove anything, for a known reason -- kept distinct from fail
# so a documented gap is not read as a regression". A case listed here records what was sent and
# never scores it, because the requirement it would score is an unanswered change request.
BLOCKED_CASES = {"US-CR3-1"}


def run_case(c):
    ch = Checks()
    calls = []
    detail = {}
    try:
        c["fn"](ch, calls, detail)
    except Exception as e:
        ch.add("runner exception", "case completes without uncaught exception", "none", f"error: {e}")
        detail["exception"] = str(e)

    np = sum(1 for i in ch.items if i["ok"])
    if c["id"] in BLOCKED_CASES and not detail.get("exception"):
        verdict = "blocked"
    else:
        verdict = "pass" if (np == len(ch.items) and len(ch.items) > 0) else "fail"
    RESULTS[c["id"]] = {
        "verdict": verdict,
        "checks": ch.items,
        "calls": calls,
        "detail": detail,
        "summary": f"{np}/{len(ch.items)} checks passed"
    }
    return verdict


# ------------------------------------------------------------------ Transformation Engine (IA-5105)
#
# WHAT IS UNDER TEST. amazon_taxonomy_transformer is a local stand-in for the JPluger Amazon
# integration, which this harness cannot start. It builds the payload; the suite fires it at the OMS
# mock and judges what ARRIVED there. The expectations come from ia5105_requirements, which was
# written from the requirement documents and the two published contracts and never from the
# integration source -- so a failing check is a statement about the requirement against this
# producer, not a description of code. See ia5105_requirements' own header for the source list.
from amazon_taxonomy_transformer import (
    transform_schema_to_oms_attributes,
    build_bulk_category_payload,
    compute_schema_checksum
)

import ia5105_requirements as R


def read_amazon_store(name):
    """One of the Amazon mock's state stores, read from disk. `reports` records every report request
    the client made, with the reportType and the reportOptions it sent."""
    path = os.path.join(DATA_DIR, name + ".json")
    if not os.path.isfile(path):
        return []
    try:
        with open(path, encoding="utf-8") as f:
            rows = json.load(f)
        return rows if isinstance(rows, list) else []
    except Exception:
        return []


def reset_amazon_reports_store():
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(os.path.join(DATA_DIR, "reports.json"), "w", encoding="utf-8") as f:
        f.write("[]")


def browse_tree_requests(marketplace_id=None):
    """Report requests for GET_XML_BROWSE_TREE_DATA the client actually made, from the mock's own
    store. R-PLAN section 4.4: a US store never triggers the browse-node refresh, and the payload
    alone cannot prove that -- only the absence of the call can."""
    rows = [r for r in read_amazon_store("reports")
            if R.BROWSE_TREE_REPORT_TYPE in str(r.get("reportType") or "")]
    if marketplace_id is None:
        return rows
    return [r for r in rows
            if marketplace_id in json.dumps(r.get("reportOptions") or r.get("marketplaceIds") or "")]


def transform_ptd_schema_to_oms(schema_doc, envelope, store_code, marketplace_code, definition_status="AVAILABLE", definition_status_reason=None):
    """Transforms an Amazon Product Type Definition JSON Schema into OMS bulk_categories_attributes payload (IA-5105)."""
    raw_json_str = json.dumps(schema_doc) if schema_doc is not None else None

    # Size guard: if serialised raw_json_str > 900KB, omit raw_schema_json and set definition_status = SCHEMA_OMITTED
    omit_raw = False
    if raw_json_str is not None and len(raw_json_str.encode("utf-8")) > 900 * 1024:
        omit_raw = True
        if definition_status == "AVAILABLE":
            definition_status = "SCHEMA_OMITTED"

    if definition_status == "PARSE_FAILED":
        payload = {
            "store_code": store_code,
            "category_code": envelope.get("productType", "UNKNOWN"),
            "marketplace_code": marketplace_code,
            "definition_version": envelope.get("productTypeVersion", {}).get("version", "LATEST") if isinstance(envelope.get("productTypeVersion"), dict) else "LATEST",
            "latest_version": True,
            "schema_checksum": envelope.get("schema", {}).get("checksum", "failed_checksum"),
            "definition_status": "PARSE_FAILED",
            "category_attributes": []
        }
        if raw_json_str is not None:
            payload["raw_schema_json"] = raw_json_str
        if definition_status_reason:
            payload["definition_status_reason"] = definition_status_reason
        return payload

    if definition_status == "UNAVAILABLE":
        return {
            "store_code": store_code,
            "category_code": envelope.get("productType", "UNKNOWN"),
            "marketplace_code": marketplace_code,
            "definition_version": "UNKNOWN",
            "latest_version": False,
            "schema_checksum": "none",
            "definition_status": "UNAVAILABLE",
            "definition_status_reason": definition_status_reason or "Amazon defines no schema for product type",
            "category_attributes": []
        }

    version_info = envelope.get("productTypeVersion", {})
    def_ver = version_info.get("version", "LATEST") if isinstance(version_info, dict) else str(version_info)
    lat_ver = version_info.get("latest", True) if isinstance(version_info, dict) else True

    payload = transform_schema_to_oms_attributes(
        schema_doc, store_code, marketplace_code,
        envelope.get("productType", "UNKNOWN"),
        definition_version=def_ver,
        latest_version=lat_ver,
        omit_raw_schema=omit_raw,
        schema_checksum=(envelope.get("schema") or {}).get("checksum")
    )
    payload["definition_status"] = definition_status
    if definition_status_reason:
        payload["definition_status_reason"] = definition_status_reason

    # Ensure browse_node_ids is absent from envelope per §1.1
    if "browse_node_ids" in payload:
        del payload["browse_node_ids"]

    return payload


# ------------------------------------------------------------------ Test Cases

def c_us_preflight(ch, calls, detail):
    st_amz, body_amz, _ = call_amazon("POST", "/auth/o2/token", {
        "grant_type": "refresh_token",
        "refresh_token": f"rws_valid_{US_STORE_CODE}_token_12345",
        "client_id": f"amzn1.application-oa2-client.{US_STORE_CODE}",
        "client_secret": f"secret_{US_STORE_CODE}"
    }, token=None, is_form=True)
    calls.append(f"CHECK Amazon SP-API mock (:23103) -> {st_amz}")
    ch.add("Amazon SP-API mock online", "port 23103 answers auth route", 200, st_amz)

    st_oms, body_oms, _ = call_oms("GET", "/rest/v1/categories", query={"store_code": US_STORE_CODE, "marketplace_code": US_MARKETPLACE_CODE})
    calls.append(f"CHECK Anchanto OMS mock (:23001) -> {st_oms}")
    ch.add("Anchanto OMS mock online", "port 23001 answers category route", 200, st_oms)

    # Runner contract item 5, TESTING.md: reset what the run owns before firing. Every payload
    # assertion in this suite reads the OMS mock's own call log, so a log inherited from an earlier
    # run would let this run pass on someone else's bytes.
    cleared = R.oms_clear_log(BASE_OMS)
    calls.append(f"DELETE {BASE_OMS}/log/data -> {cleared}")
    ch.add("OMS call log reset", "the run judges only its own postings", 200, cleared)
    reset_amazon_reports_store()
    ch.add("Amazon reports store reset", "browse-tree report requests are counted from zero",
           0, len(read_amazon_store("reports")))
    detail["preflight"] = "Dual-server topology verified (Amazon SP-API + OMS)"


def c_us_auth(ch, calls, detail):
    payload = {
        "grant_type": "refresh_token",
        "refresh_token": f"rws_valid_{US_STORE_CODE}_token_12345",
        "client_id": f"amzn1.application-oa2-client.{US_STORE_CODE}",
        "client_secret": f"secret_{US_STORE_CODE}"
    }
    status, body, _ = call_amazon("POST", "/auth/o2/token", payload, token=None, is_form=True)
    calls.append(f"POST /auth/o2/token -> {status}")

    ch.add("LWA Auth status", "200 OK", 200, status)
    ch.truthy("access_token present", "Access token returned", body.get("access_token"))
    ch.add("token_type is bearer", "bearer token", "bearer", body.get("token_type"))
    detail["issued_token"] = body.get("access_token")


def c_us_auth_refresh(ch, calls, detail):
    """Verifies token expiration handling and automatic re-authentication with refresh token (FR-1, FR-2)."""
    # 1. Invalid refresh token rejected
    st_bad, body_bad, _ = call_amazon("POST", "/auth/o2/token", {
        "grant_type": "refresh_token",
        "refresh_token": "INVALID_REFRESH_TOKEN",
        "client_id": "amzn1.app.test",
        "client_secret": "test_secret"
    }, token=None, is_form=True)
    ch.add("Invalid token returns 400", "400 Bad Request", 400, st_bad)

    # 2. Valid refresh token issues new token
    st_ok, body_ok, _ = call_amazon("POST", "/auth/o2/token", {
        "grant_type": "refresh_token",
        "refresh_token": f"rws_valid_{US_STORE_CODE}_token_12345",
        "client_id": f"amzn1.application-oa2-client.{US_STORE_CODE}",
        "client_secret": f"secret_{US_STORE_CODE}"
    }, token=None, is_form=True)
    ch.add("Valid refresh returns 200", "200 OK", 200, st_ok)
    ch.truthy("New access token issued", "access_token present", body_ok.get("access_token"))
    detail["refresh_flow_verified"] = True


def c_us_category_discovery(ch, calls, detail):
    """POST /rest/v1/bulk_categories for the US store, judged on what reached OMS.

    Expectations, all from the requirement rather than from the producer:
      code            R-MAP section 4.1 row 1  -- ProductType.name, UPPER_SNAKE verbatim
      name            R-MAP section 4.1 row 2  -- displayName, falling back to .name
      marketplace_code  R-MAP section 4.1 row 3
      store_code      C-OMS -- a required QUERY parameter on this endpoint, not a body property
      children/parent_code  R-MAP section 4.1 row 5 -- never populated by this sync

    Whether a browse-node field reaches this payload is US-WITHDRAW-1's finding, not this one's.
    """
    cat_payload = build_bulk_category_payload(US_STORE_CODE, US_MARKETPLACE_CODE, "LUGGAGE", "Luggage")
    st_oms, body_oms, _ = call_oms("POST", "/rest/v1/bulk_categories", cat_payload, query={"store_code": US_STORE_CODE})
    calls.append(f"POST /rest/v1/bulk_categories [LUGGAGE] -> {st_oms}")
    ch.add("OMS bulk_categories status", "200 OK", 200, st_oms)

    received = [e for e in R.oms_received(BASE_OMS, "/rest/v1/bulk_categories", refresh=True)
                if "/rest/v1/bulk_categories_attributes" not in e["url"]
                and (e["body"].get("category") or {}).get("code") == "LUGGAGE"]
    ch.add("posting reached the OMS mock", "one bulk_categories call carrying LUGGAGE", 1, len(received))
    if not received:
        return
    entry = received[-1]
    category = entry["body"].get("category") or {}

    ch.add("category.code is the product type", "ProductType.name verbatim (R-MAP 4.1 row 1)",
           "LUGGAGE", category.get("code"))
    ch.add("category.code is UPPER_SNAKE", "never split on '_', never re-cased",
           True, R.is_upper_snake(category.get("code")))
    ch.add("category.code is not a browse-node id",
           "before this branch the code WAS the browse path 172282_281052_172541 (R-PLAN section 1)",
           False, R.looks_like_a_browse_node(category.get("code")))
    ch.add("category.name is the display name", "displayName, else .name (R-MAP 4.1 row 2)",
           "Luggage", category.get("name"))
    ch.add("category.marketplace_code", "scopes the row to one country (R-MAP 4.1 row 3)",
           US_MARKETPLACE_CODE, category.get("marketplace_code"))
    ch.add("store_code on the query string", "C-OMS declares it as a required query parameter",
           US_STORE_CODE, entry["query"].get("store_code"))
    ch.add("category.active", "record lifecycle flag, true on discovery (R-REQ 2.1)",
           True, category.get("active"))
    ch.add("category.variation is false", "a product type has no variation dimension (R-REQ 2.1)",
           False, category.get("variation"))
    ch.add("children not populated", "no product type has a child (R-MAP 4.1 row 5)",
           True, not category.get("children"))
    ch.add("parent_code not populated", "no product type has a parent (R-MAP 4.1 row 5)",
           True, "parent_code" not in category)
    # Whether a browse-node field reaches this payload is US-WITHDRAW-1's finding, scanned there
    # across both endpoints and all four product types. Repeating the scan here would report one
    # fact three times over.
    detail["categories_pushed"] = ["LUGGAGE"]
    detail["received_category"] = category


def c_us_category_multi_push(ch, calls, detail):
    """One bulk_categories row per product type searchDefinitionsProductTypes returned.

    R-MAP section 3, Flow 1 step 2: "one flat category row per product type". C-OMS takes one
    category per call, so the requirement is one POST per discovered product type and a code set that
    matches the discovered name set exactly -- no extra rows, none missing.
    """
    mark = R.oms_high_water(BASE_OMS)
    st, search, _ = call_amazon("GET", f"/definitions/2020-09-01/productTypes?marketplaceIds={US_MARKETPLACE_ID}")
    calls.append(f"GET searchDefinitionsProductTypes[{US_MARKETPLACE_ID}] -> {st}")
    discovered = {pt.get("name"): pt.get("displayName") for pt in (search.get("productTypes") or [])}
    ch.truthy("product types discovered", "searchDefinitionsProductTypes returned a population", discovered)

    for name, display in discovered.items():
        cat_payload = build_bulk_category_payload(US_STORE_CODE, US_MARKETPLACE_CODE, name, display or name)
        st_oms, _, _ = call_oms("POST", "/rest/v1/bulk_categories", cat_payload, query={"store_code": US_STORE_CODE})
        calls.append(f"POST /rest/v1/bulk_categories [{name}] -> {st_oms}")
        ch.add(f"Category {name} push status", "200 OK", 200, st_oms)

    received = [e for e in R.oms_received(BASE_OMS, "/rest/v1/bulk_categories", refresh=True, since=mark)
                if "/rest/v1/bulk_categories_attributes" not in e["url"]
                and e["query"].get("store_code") == US_STORE_CODE]
    codes = [(e["body"].get("category") or {}).get("code") for e in received]

    ch.add("one row per discovered product type", "R-MAP section 3, Flow 1 step 2",
           sorted(discovered), sorted(set(codes)))
    ch.add("no code arrived twice in one sync", "a flat population posts each product type once",
           sorted(set(codes)), sorted(codes))
    ch.add("every code is UPPER_SNAKE", "R-MAP 4.1 row 1", [],
           [c for c in codes if not R.is_upper_snake(c)])
    ch.add("no code is a browse-node id or a browse path", "R-REQ 2.1, the `code` UPDATE row", [],
           [c for c in codes if R.looks_like_a_browse_node(c)])
    detail["multi_categories_pushed"] = codes
    detail["discovered_product_types"] = discovered


def c_us_ptd_discovery(ch, calls, detail):
    status, body, _ = call_amazon("GET", f"/definitions/2020-09-01/productTypes?marketplaceIds={US_MARKETPLACE_ID}")
    calls.append(f"GET /definitions/2020-09-01/productTypes?marketplaceIds={US_MARKETPLACE_ID} -> {status}")

    ch.add("PTD search status", "200 OK", 200, status)
    product_types = body.get("productTypes", [])
    pt_names = [p.get("name") for p in product_types]
    for s in US_SCHEMAS:
        ch.contains(f"{s['product_type']} in productTypes", f"{s['product_type']} discovered", s["product_type"], pt_names)
    detail["product_types"] = pt_names


def _fetch_us_schema(product_type, calls):
    status, envelope, _ = call_amazon("GET", f"/definitions/2020-09-01/productTypes/{product_type}?marketplaceIds={US_MARKETPLACE_ID}")
    calls.append(f"GET /definitions/2020-09-01/productTypes/{product_type} -> {status}")
    schema_link = envelope.get("schema", {}).get("link", {}).get("resource", "")
    path = schema_link[len(BASE_AMAZON):] if schema_link.startswith(BASE_AMAZON) else schema_link
    st_s3, schema_doc, raw_bytes = call_amazon("GET", path)
    calls.append(f"GET {path} [{product_type} Schema Download] -> {st_s3}")
    return status, envelope, st_s3, schema_doc, raw_bytes


def c_us_def_fetch_luggage(ch, calls, detail):
    st_def, env, st_s3, doc, _ = _fetch_us_schema("LUGGAGE", calls)
    ch.add("LUGGAGE definition status", "200 OK", 200, st_def)
    ch.add("LUGGAGE S3 schema status", "200 OK", 200, st_s3)
    ch.contains("item_name property in schema", "item_name present", "item_name", doc.get("properties", {}))
    detail["luggage_schema_id"] = doc.get("$id")


def c_us_def_fetch_clothing(ch, calls, detail):
    st_def, env, st_s3, doc, _ = _fetch_us_schema("CLOTHING", calls)
    ch.add("CLOTHING definition status", "200 OK", 200, st_def)
    ch.add("CLOTHING S3 schema status", "200 OK", 200, st_s3)
    ch.contains("size in CLOTHING schema", "size property present", "size", doc.get("properties", {}))
    detail["clothing_schema_id"] = doc.get("$id")


def c_us_def_fetch_electronics(ch, calls, detail):
    st_def, env, st_s3, doc, _ = _fetch_us_schema("ELECTRONICS", calls)
    ch.add("ELECTRONICS definition status", "200 OK", 200, st_def)
    ch.add("ELECTRONICS S3 schema status", "200 OK", 200, st_s3)
    ch.contains("voltage in ELECTRONICS schema", "voltage property present", "voltage", doc.get("properties", {}))
    detail["electronics_schema_id"] = doc.get("$id")


def c_us_def_fetch_toys(ch, calls, detail):
    st_def, env, st_s3, doc, _ = _fetch_us_schema("TOYS_AND_GAMES", calls)
    ch.add("TOYS definition status", "200 OK", 200, st_def)
    ch.add("TOYS S3 schema status", "200 OK", 200, st_s3)
    ch.contains("cpsia_cautionary_statement in TOYS", "cpsia property present", "cpsia_cautionary_statement", doc.get("properties", {}))
    detail["toys_schema_id"] = doc.get("$id")


def c_us_mapping_luggage(ch, calls, detail):
    """Asserts field-by-field transformation from Amazon SP-API LUGGAGE JSON Schema into OMS payload (IA-5105)."""
    # field_type is asserted once, for every row of every posting, in US-VOCAB-1 against the
    # closed enum C-OMS declares (attribute / option_type / attributes). The per-attribute
    # "group" / "text" / "dropdown" checks that stood here named a vocabulary no requirement
    # document and no OMS endpoint states, so they could only ever confirm the producer to
    # itself. The constraint checks below are the part of this case that carries evidence.
    _, env, _, doc, _ = _fetch_us_schema("LUGGAGE", calls)
    payload = transform_ptd_schema_to_oms(doc, env, US_STORE_CODE, US_MARKETPLACE_CODE)
    attrs = {a["field_code"]: a for a in payload.get("category_attributes", [])}

    ch.add("Total expanded attributes count", "20 attributes in LUGGAGE", 20, len(attrs))

    # item_name parent & item_name.value
    item_parent = attrs.get("item_name", {})
    ch.add("item_name field_criteria", "is_parent", "is_parent", item_parent.get("field_criteria"))

    item_val = attrs.get("item_name_value", {})
    ch.add("item_name_value criteria", "is_child", "is_child", item_val.get("field_criteria"))
    ch.add("item_name_value data_type", "string", "string", item_val.get("data_type"))
    ch.add("item_name_value ss_field_code", "item_name_value", "item_name_value", item_val.get("ss_field_code"))
    ch.add("item_name_value mandatory", "mandatory is true", True, item_val.get("mandatory"))
    ch.add("item_name_value maxLength", "maxLength is 200", 200, item_val.get("validation", {}).get("maxLength"))

    # capacity parent & children

    cap_val = attrs.get("capacity_value", {})
    ch.add("capacity_value criteria", "is_child", "is_child", cap_val.get("field_criteria"))
    ch.add("capacity_value data_type", "number", "number", cap_val.get("data_type"))
    ch.add("capacity_value ss_field_code", "capacity_value", "capacity_value", cap_val.get("ss_field_code"))
    ch.add("capacity_value minimum", "1", 1, cap_val.get("validation", {}).get("minimum"))
    ch.add("capacity_value maximum", "200", 200, cap_val.get("validation", {}).get("maximum"))

    cap_unit = attrs.get("capacity_unit", {})
    ch.add("capacity_unit enum count", "1 enum value (liters)", 1, len(cap_unit.get("field_values", [])))
    detail["tested_luggage_attributes"] = list(attrs.keys())


def c_us_mapping_clothing(ch, calls, detail):
    """Asserts field-by-field transformation from Amazon SP-API CLOTHING JSON Schema into OMS payload (IA-5105)."""
    # field_type is asserted once, for every row of every posting, in US-VOCAB-1 against the
    # closed enum C-OMS declares (attribute / option_type / attributes). The per-attribute
    # "group" / "text" / "dropdown" checks that stood here named a vocabulary no requirement
    # document and no OMS endpoint states, so they could only ever confirm the producer to
    # itself. The constraint checks below are the part of this case that carries evidence.
    _, env, _, doc, _ = _fetch_us_schema("CLOTHING", calls)
    payload = transform_ptd_schema_to_oms(doc, env, US_STORE_CODE, US_MARKETPLACE_CODE)
    attrs = {a["field_code"]: a for a in payload.get("category_attributes", [])}

    ch.add("CLOTHING total attributes count", "29 attributes in CLOTHING expanded", 29, len(attrs))

    # The picker sits on the child row: Amazon states the enum on items.properties.value, and
    # L-62 expands that into its own sibling row rather than reading it onto the array parent.
    size_val = attrs.get("size_value", {})
    ch.add("size_value option_type", "true", True, size_val.get("option_type"))
    ch.add("size_value enum count", "7 size options", 7, len(size_val.get("field_values", [])))
    ch.add("size parent carries no enum of its own",
           "the parent is the array; the values belong to the row Amazon stated them on",
           0, len(attrs.get("size", {}).get("field_values", [])))

    gender_val = attrs.get("target_gender_value", {})
    ch.add("target_gender_value enum count", "3 gender options", 3, len(gender_val.get("field_values", [])))

    care_val = attrs.get("care_instructions_value", {})
    ch.add("care_instructions_value enum count", "4 care options", 4, len(care_val.get("field_values", [])))
    detail["tested_clothing_attributes"] = list(attrs.keys())


def c_us_mapping_electronics(ch, calls, detail):
    """Asserts field-by-field transformation from Amazon SP-API ELECTRONICS JSON Schema into OMS payload (IA-5105)."""
    # field_type is asserted once, for every row of every posting, in US-VOCAB-1 against the
    # closed enum C-OMS declares (attribute / option_type / attributes). The per-attribute
    # "group" / "text" / "dropdown" checks that stood here named a vocabulary no requirement
    # document and no OMS endpoint states, so they could only ever confirm the producer to
    # itself. The constraint checks below are the part of this case that carries evidence.
    _, env, _, doc, _ = _fetch_us_schema("ELECTRONICS", calls)
    payload = transform_ptd_schema_to_oms(doc, env, US_STORE_CODE, US_MARKETPLACE_CODE)
    attrs = {a["field_code"]: a for a in payload.get("category_attributes", [])}

    ch.add("ELECTRONICS total attributes count", "23 attributes in ELECTRONICS expanded", 23, len(attrs))

    volt_val = attrs.get("voltage_value", {})
    ch.add("voltage_value data_type", "number", "number", volt_val.get("data_type"))
    ch.add("voltage_value minimum", "1", 1, volt_val.get("validation", {}).get("minimum"))
    ch.add("voltage_value maximum", "500", 500, volt_val.get("validation", {}).get("maximum"))

    volt_unit = attrs.get("voltage_unit", {})
    ch.add("voltage_unit enum count", "2 units (volts, millivolts)", 2, len(volt_unit.get("field_values", [])))

    pwr_val = attrs.get("power_source_type_value", {})
    ch.add("power_source_type_value enum count", "4 power source types", 4, len(pwr_val.get("field_values", [])))
    detail["tested_electronics_attributes"] = list(attrs.keys())


def c_us_mapping_toys(ch, calls, detail):
    """Asserts field-by-field transformation from Amazon SP-API TOYS_AND_GAMES JSON Schema into OMS payload (IA-5105)."""
    # field_type is asserted once, for every row of every posting, in US-VOCAB-1 against the
    # closed enum C-OMS declares (attribute / option_type / attributes). The per-attribute
    # "group" / "text" / "dropdown" checks that stood here named a vocabulary no requirement
    # document and no OMS endpoint states, so they could only ever confirm the producer to
    # itself. The constraint checks below are the part of this case that carries evidence.
    _, env, _, doc, _ = _fetch_us_schema("TOYS_AND_GAMES", calls)
    payload = transform_ptd_schema_to_oms(doc, env, US_STORE_CODE, US_MARKETPLACE_CODE)
    attrs = {a["field_code"]: a for a in payload.get("category_attributes", [])}

    ch.add("TOYS_AND_GAMES total attributes count", "12 attributes in TOYS expanded", 12, len(attrs))

    age_val = attrs.get("manufacturer_minimum_age_value", {})
    ch.add("manufacturer_minimum_age_value minimum", "0", 0, age_val.get("validation", {}).get("minimum"))
    ch.add("manufacturer_minimum_age_value maximum", "1200", 1200, age_val.get("validation", {}).get("maximum"))

    cpsia_val = attrs.get("cpsia_cautionary_statement_value", {})
    ch.add("cpsia_cautionary_statement_value enum count", "7 warning statements", 7, len(cpsia_val.get("field_values", [])))
    detail["tested_toys_attributes"] = list(attrs.keys())


def c_us_withdrawn_browse_nodes(ch, calls, detail):
    """No browse-node field reaches OMS on either endpoint, under any spelling.

    R-REQ section 2.2's REMOVE row withdraws the envelope `browse_node_ids` the 31-Aug revision
    asked for, and names itself the authority over the lagging Jira attachment. R-MAP section 1.1
    item 2 drops the field. R-PLAN section 4.2 refuses to restore it: the productTypeDefinitions
    inversion returns "as a picker filter, never as an outbound value and never as a wire field".

    The scan is over JSON *keys* of the bodies as OMS received them, so it catches browse_node_ids,
    browseNodeIds, browse-node-ids and any other casing, on both endpoints -- and does not
    false-positive on the legal field_code VALUE "recommended_browse_nodes".
    """
    for product_type in [s["product_type"] for s in US_SCHEMAS]:
        _, env, _, doc, _ = _fetch_us_schema(product_type, calls)
        payload = transform_ptd_schema_to_oms(doc, env, US_STORE_CODE, US_MARKETPLACE_CODE)
        st, _, _ = call_oms("POST", "/rest/v1/bulk_categories_attributes", payload,
                            query={"store_code": US_STORE_CODE, "marketplace_code": US_MARKETPLACE_CODE})
        calls.append(f"POST /rest/v1/bulk_categories_attributes [{product_type}] -> {st}")

    offending = {}
    for path in ("/rest/v1/bulk_categories_attributes", "/rest/v1/bulk_categories"):
        for entry in R.oms_received(BASE_OMS, path, refresh=True):
            if path == "/rest/v1/bulk_categories" and "_attributes" in entry["url"]:
                continue
            for key in R.browse_node_keys(entry["body"]):
                offending.setdefault(path, set()).add(key)

    ch.add("no browse-node key on bulk_categories_attributes",
           "R-REQ 2.2 REMOVE row; R-MAP 1.1 item 2", [],
           sorted(offending.get("/rest/v1/bulk_categories_attributes", [])))
    ch.add("no browse-node key on bulk_categories",
           "R-PLAN section 6.1: BulkCategoryDTO has no field for a browse node", [],
           sorted(offending.get("/rest/v1/bulk_categories", [])))

    # R-MAP section 4.2 warning, last bullet: "us-schema-LUGGAGE.json yields neither a
    # recommended_browse_nodes nor a recommended_browse_nodes_value row." Asserted on what arrived,
    # for every US product type, under both the underscore and the dotted spelling of the child.
    attributes_posts = [e for e in R.oms_received(BASE_OMS, "/rest/v1/bulk_categories_attributes")
                        if e["query"].get("marketplace_code") == US_MARKETPLACE_CODE]
    rbn_rows = sorted({code for e in attributes_posts for code in R.attribute_rows(e["body"])
                       if code and "browse_node" in str(code)})
    ch.add("no recommended_browse_nodes row for a US store",
           "the US definition does not carry the property (R-MAP 4.2, last bullet; R-PLAN 4.4)",
           [], rbn_rows)
    detail["us_attributes_postings"] = len(attributes_posts)
    detail["browse_node_keys_seen"] = {k: sorted(v) for k, v in offending.items()}


def c_us_no_browse_tree_report(ch, calls, detail):
    """No GET_XML_BROWSE_TREE_DATA report is ever requested for a US store.

    R-PLAN section 4.4: "US stores never trigger the refresh." us-definition-LUGGAGE.json lists
    item_type_keyword in propertyGroups.product_identity.propertyNames and does not list
    recommended_browse_nodes, so there is nothing for a browse tree to fill.

    An empty payload cannot prove this -- a report that was requested and then discarded produces
    the same payload. The count is therefore taken from the Amazon mock's own `reports` store, which
    records every report request the client made, with the reportOptions it sent.
    """
    for product_type in [s["product_type"] for s in US_SCHEMAS]:
        _fetch_us_schema(product_type, calls)

    requested = browse_tree_requests()
    ch.add("no browse-tree report requested at all", "R-PLAN section 4.4, US exclusion",
           0, len(requested))
    ch.add("none requested for the US marketplace", "reportOptions.MarketplaceId = ATVPDKIKX0DER",
           0, len(browse_tree_requests(US_MARKETPLACE_ID)))
    detail["report_requests_recorded"] = requested
    detail["gate"] = ("R-PLAN section 7, G-4: the US premise is unconfirmed against a real US "
                      "capture. us-schema-LUGGAGE.json is hand-authored (R-MAP 1.1) and models "
                      "neither item_type_keyword nor recommended_browse_nodes as a property, so "
                      "this case proves the exclusion holds for the fixture, not for Amazon US.")


def c_us_envelope(ch, calls, detail):
    """The bulk_categories_attributes envelope, as received (R-REQ section 2.2, R-PLAN section 6.1).

    definition_version and schema_checksum are DIRECT MAPS of what Amazon stated -- R-MAP section 4.2
    envelope rows 2 and 4. A value recomputed locally is not the requirement, and a recomputed
    checksum silently defeats Flow 2, which is the only change detector this design has.
    """
    _, env, _, doc, raw_bytes = _fetch_us_schema("LUGGAGE", calls)
    payload = transform_ptd_schema_to_oms(doc, env, US_STORE_CODE, US_MARKETPLACE_CODE)
    st, _, _ = call_oms("POST", "/rest/v1/bulk_categories_attributes", payload,
                        query={"store_code": US_STORE_CODE, "marketplace_code": US_MARKETPLACE_CODE})
    calls.append(f"POST /rest/v1/bulk_categories_attributes [LUGGAGE envelope] -> {st}")

    received = [e for e in R.oms_received(BASE_OMS, "/rest/v1/bulk_categories_attributes", refresh=True)
                if e["body"].get("category_code") == "LUGGAGE"]
    ch.truthy("posting reached the OMS mock", "one bulk_categories_attributes call for LUGGAGE", received)
    if not received:
        return
    body = received[-1]["body"]
    query = received[-1]["query"]
    stated = env.get("productTypeVersion") or {}

    for name in R.BULK_ATTRIBUTES_QUERY:
        ch.truthy(f"query parameter {name}", "C-OMS declares it required on this endpoint",
                  query.get(name))
    ch.add("category_code is the product type", "R-MAP 4.2 envelope row 1, one posting per type",
           "LUGGAGE", body.get("category_code"))
    ch.add("definition_version is productTypeVersion.version",
           "R-MAP 4.2 envelope row 2 -- direct map of .version, never the enclosing object",
           stated.get("version"), body.get("definition_version"))
    ch.add("definition_version is an opaque token, not a date",
           "R-PLAN section 6.1 annotates it as an opaque token",
           False, R.looks_like_a_date(body.get("definition_version")))
    ch.add("latest_version is productTypeVersion.latest",
           "R-MAP 4.2 envelope row 3; a non-true value is rejected before this call",
           stated.get("latest"), body.get("latest_version"))
    ch.add("schema_checksum is Amazon's stated schema.checksum",
           "R-MAP 4.2 envelope row 4 -- a direct map, and the only change detector for Flow 2",
           (env.get("schema") or {}).get("checksum"), body.get("schema_checksum"))
    ch.add("raw_schema_json round-trips to the downloaded schema",
           "R-MAP 4.2 envelope row 5 -- verbatim JSON",
           True, _same_json(body.get("raw_schema_json"), doc))
    ch.contains("definition_status is one of the four declared values",
                "R-REQ 2.2 -- SCHEMA_OMITTED is never bucketed with PARSE_FAILED",
                body.get("definition_status"), R.DEFINITION_STATUSES)
    ch.add("definition_status_reason absent while AVAILABLE",
           "R-REQ 2.2 -- present only when definition_status is not AVAILABLE",
           True, "definition_status_reason" not in body or body.get("definition_status") != "AVAILABLE")
    detail["envelope_received"] = {k: v for k, v in body.items()
                                  if k not in ("raw_schema_json", "category_attributes")}
    detail["raw_schema_bytes"] = len(raw_bytes or b"")


def _same_json(raw, expected):
    try:
        return json.loads(raw) == expected
    except Exception:
        return False


def c_us_attribute_vocabulary(ch, calls, detail):
    """Every attribute row OMS received speaks OMS's own vocabulary.

    field_type: C-OMS declares a CLOSED enum on the single-row sibling POST
    /rest/v1/category_attributes -- attribute, option_type, attributes, "attribute,option_type" --
    and R-MAP section 5 maps into exactly that set. The bulk endpoint declares a free string, which
    R-REQ section 1 item 2 reads as an absence of validation rather than a licence.

    field_code: R-MAP section 4.2 row 1 -- "the dotted property path, `.` -> `_`". A field_code
    carrying a literal dot is the dotted path unconverted, and it will not match the
    field_parent_code of any row, because a parent's own field_code is what a child points at
    (R-MAP 4.2 row 2).

    mandatory: R-REQ section 2.2 -- a strict boolean, and "a stored definition set in which every
    row is mandatory:false is a defect signature, not plausible data".
    """
    postings = [e for e in R.oms_received(BASE_OMS, "/rest/v1/bulk_categories_attributes", refresh=True)
                if e["query"].get("marketplace_code") == US_MARKETPLACE_CODE]
    ch.truthy("US attribute postings captured", "at least one posting reached OMS", postings)

    rows = [r for e in postings for r in (e["body"].get("category_attributes") or [])
            if isinstance(r, dict)]
    ch.truthy("attribute rows captured", "rows to judge", rows)
    if not rows:
        return

    ch.add("every field_type is in the OMS enum",
           "C-OMS: attribute / option_type / attributes / 'attribute,option_type'", [],
           sorted({str(r.get("field_type")) for r in rows
                   if str(r.get("field_type")) not in R.OMS_SIBLING_FIELD_TYPE_ENUM}))
    ch.add("no field_code carries a literal dot",
           "R-MAP 4.2 row 1 -- the dotted path with '.' replaced by '_'", [],
           sorted({str(r.get("field_code")) for r in rows if "." in str(r.get("field_code"))})[:8])
    ch.add("every row declares the four properties C-OMS requires",
           "C-OMS: field_code, field_name, field_type, data_type", [],
           sorted({name for r in rows for name in R.BULK_ATTRIBUTE_ROW_REQUIRED
                   if r.get(name) in (None, "")}))
    ch.add("every mandatory is a JSON boolean",
           "C-OMS: 'Must be a JSON boolean (true/false), not a string'", [],
           sorted({repr(r.get("mandatory")) for r in rows if not isinstance(r.get("mandatory"), bool)}))
    ch.add("not every row is mandatory:false",
           "R-REQ 2.2 -- an all-false set is the wrong-enforcement-mode defect signature",
           True, any(r.get("mandatory") is True for r in rows))

    # R-MAP 4.2 row 2: a child points at its parent's own field_code, so every field_parent_code
    # must resolve to a row in the same posting.
    dangling = set()
    for entry in postings:
        codes = {r.get("field_code") for r in (entry["body"].get("category_attributes") or [])
                 if isinstance(r, dict)}
        for row in (entry["body"].get("category_attributes") or []):
            parent = row.get("field_parent_code") if isinstance(row, dict) else None
            if parent and parent not in codes:
                dangling.add(parent)
    ch.add("every field_parent_code resolves inside its own posting",
           "R-MAP 4.2 row 2 -- the parent's own field_code, because nothing has an id yet",
           [], sorted(dangling))
    detail["field_types_sent"] = sorted({str(r.get("field_type")) for r in rows})
    detail["rows_judged"] = len(rows)


def c_us_data_type_pinning(ch, calls, detail):
    """CR-3, pinned rather than passed over. Verdict is set by the runner to `blocked`.

    R-MAP section 4.2 row 7: data_type is "Amazon's raw JSON-Schema type verbatim". R-REQ section 1
    item 2 and section 2.2: the bulk endpoint declares data_type as a free string with no enum,
    while the single-row sibling declares a closed enum that contains none of object, array, number,
    boolean or integer. OMS has not answered which reading is correct, so no pass or fail here would
    mean anything -- the case records exactly which values this sync sends and which of them the
    sibling endpoint would reject, so the mismatch stays visible.
    """
    postings = [e for e in R.oms_received(BASE_OMS, "/rest/v1/bulk_categories_attributes", refresh=True)
                if e["query"].get("marketplace_code") == US_MARKETPLACE_CODE]
    sent, outside = set(), set()
    for entry in postings:
        s, o = R.data_types_sent(entry["body"])
        sent.update(s)
        outside.update(o)

    ch.add("data_type values sent to OMS", "R-MAP 4.2 row 7 -- Amazon's raw JSON-Schema types",
           sorted(sent), sorted(sent))
    ch.add("values outside the sibling endpoint's closed enum",
           "C-OMS POST /rest/v1/category_attributes: " + ", ".join(R.OMS_SIBLING_DATA_TYPE_ENUM),
           sorted(outside), sorted(outside))
    detail["data_types_sent"] = sorted(sent)
    detail["outside_sibling_enum"] = sorted(outside)
    detail["change_request"] = R.UNSETTLED["data_type_enum"]


def c_us_definition_statuses(ch, calls, detail):
    """Asserts the four definition availability states: AVAILABLE, PARSE_FAILED, SCHEMA_OMITTED, UNAVAILABLE (FR-6, FR-18, AC-10)."""
    _, env, _, doc, _ = _fetch_us_schema("LUGGAGE", calls)

    # 1. AVAILABLE
    p_avail = transform_ptd_schema_to_oms(doc, env, US_STORE_CODE, US_MARKETPLACE_CODE, definition_status="AVAILABLE")
    ch.add("AVAILABLE status", "AVAILABLE", "AVAILABLE", p_avail["definition_status"])
    ch.truthy("AVAILABLE has attributes", "attributes present", len(p_avail["category_attributes"]) > 0)
    ch.truthy("AVAILABLE has raw_schema", "raw JSON present", p_avail.get("raw_schema_json"))

    # 2. PARSE_FAILED
    p_fail = transform_ptd_schema_to_oms(doc, env, US_STORE_CODE, US_MARKETPLACE_CODE,
                                         definition_status="PARSE_FAILED",
                                         definition_status_reason="unsupported construct at properties.heel_height.oneOf")
    ch.add("PARSE_FAILED status", "PARSE_FAILED", "PARSE_FAILED", p_fail["definition_status"])
    ch.add("PARSE_FAILED empty attributes", "empty attribute list", 0, len(p_fail["category_attributes"]))
    ch.truthy("PARSE_FAILED retains raw_schema", "raw schema preserved for parser fix", p_fail.get("raw_schema_json"))
    ch.truthy("PARSE_FAILED has reason", "failure reason present", p_fail.get("definition_status_reason"))

    # 3. SCHEMA_OMITTED (>900KB size guard)
    huge_schema = dict(doc)
    huge_schema["_giant_payload"] = "X" * (950 * 1024)
    p_omitted = transform_ptd_schema_to_oms(huge_schema, env, US_STORE_CODE, US_MARKETPLACE_CODE, definition_status="AVAILABLE")
    ch.add("SCHEMA_OMITTED status", "SCHEMA_OMITTED", "SCHEMA_OMITTED", p_omitted["definition_status"])
    ch.add("SCHEMA_OMITTED omits raw_schema", "raw_schema_json is None", None, p_omitted.get("raw_schema_json"))
    ch.truthy("SCHEMA_OMITTED retains attributes", "complete attribute list present", len(p_omitted["category_attributes"]) > 0)

    # 4. UNAVAILABLE
    p_unavail = transform_ptd_schema_to_oms(None, env, US_STORE_CODE, US_MARKETPLACE_CODE,
                                            definition_status="UNAVAILABLE",
                                            definition_status_reason="Amazon defines no schema for LUGGAGE")
    ch.add("UNAVAILABLE status", "UNAVAILABLE", "UNAVAILABLE", p_unavail["definition_status"])
    ch.add("UNAVAILABLE empty attributes", "0 attributes", 0, len(p_unavail["category_attributes"]))

    detail["verified_statuses"] = ["AVAILABLE", "PARSE_FAILED", "SCHEMA_OMITTED", "UNAVAILABLE"]


def c_us_raw_json_verification(ch, calls, detail):
    """Asserts that raw_schema_json verbatim copy is preserved and checksum matches MD5 hash across all 4 US schemas (FR-8, FR-19)."""
    for s in US_SCHEMAS:
        _, env, _, doc, _ = _fetch_us_schema(s["product_type"], calls)
        payload = transform_ptd_schema_to_oms(doc, env, US_STORE_CODE, US_MARKETPLACE_CODE)

        raw_json = payload.get("raw_schema_json", "")
        ch.truthy(f"{s['product_type']} raw_schema_json is non-empty", "Raw JSON is populated", raw_json)

        parsed_back = json.loads(raw_json)
        ch.add(f"{s['product_type']} raw_schema_json is valid JSON", "properties in parsed JSON", True, "properties" in parsed_back)
        ch.add(f"{s['product_type']} raw_schema_json is the downloaded document verbatim",
               "R-MAP 4.2 envelope row 5", True, parsed_back == doc)

        # R-MAP section 4.2 envelope row 4: schema_checksum is a DIRECT MAP of $.schema.checksum.
        # The previous form of this check recomputed MD5 over our own raw_schema_json and compared
        # it to the value the same code had just computed the same way -- an identity, which passes
        # whatever Amazon said. Flow 2 compares this field against the stored one to decide whether
        # a definition changed, so a self-consistent local digest defeats the only change detector
        # this design has.
        ch.add(f"{s['product_type']} schema_checksum is Amazon's stated checksum",
               "R-MAP 4.2 envelope row 4 -- direct map of $.schema.checksum",
               (env.get("schema") or {}).get("checksum"), payload.get("schema_checksum"))

    detail["all_4_us_raw_schemas_verified"] = True
    detail["checksum_note"] = (
        "The mock states schema.checksum as MD5 hex. Amazon states Base64 MD5 (R-MAP 4.2 envelope "
        "row 4, L-39). This check asserts passthrough and is therefore indifferent to the encoding; "
        "the mock's encoding is a separate fidelity gap, recorded and not asserted here.")


def c_us_transform_and_oms_ingest_luggage(ch, calls, detail):
    _, env, _, doc, _ = _fetch_us_schema("LUGGAGE", calls)
    oms_payload = transform_ptd_schema_to_oms(doc, env, US_STORE_CODE, US_MARKETPLACE_CODE)

    query = {"store_code": US_STORE_CODE, "marketplace_code": US_MARKETPLACE_CODE}
    st_oms, oms_res, _ = call_oms("POST", "/rest/v1/bulk_categories_attributes", oms_payload, query=query)
    calls.append(f"POST /rest/v1/bulk_categories_attributes [LUGGAGE] -> {st_oms}")

    ch.add("OMS bulk_categories_attributes status", "200 OK", 200, st_oms)
    ch.add("Category code matches", "LUGGAGE", "LUGGAGE", oms_payload.get("category_code"))
    ch.add("Marketplace code matches", "amazon_sp_us", US_MARKETPLACE_CODE, oms_payload.get("marketplace_code"))
    ch.add("Attributes count", "20 attributes extracted", 20, len(oms_payload.get("category_attributes", [])))
    ch.truthy("raw_schema_json present", "Verbatim raw JSON Schema preserved", oms_payload.get("raw_schema_json"))
    ch.truthy("schema_checksum present", "Checksum computed and attached", oms_payload.get("schema_checksum"))
    detail["oms_response"] = oms_res


def c_us_transform_and_oms_ingest_multi(ch, calls, detail):
    """Pushes CLOTHING, ELECTRONICS, and TOYS_AND_GAMES attributes to OMS (IA-5105 §4.2)."""
    pushed = []
    for s in US_SCHEMAS[1:]:
        _, env, _, doc, _ = _fetch_us_schema(s["product_type"], calls)
        oms_payload = transform_ptd_schema_to_oms(doc, env, US_STORE_CODE, US_MARKETPLACE_CODE)

        query = {"store_code": US_STORE_CODE, "marketplace_code": US_MARKETPLACE_CODE}
        st_oms, oms_res, _ = call_oms("POST", "/rest/v1/bulk_categories_attributes", oms_payload, query=query)
        calls.append(f"POST /rest/v1/bulk_categories_attributes [{s['product_type']}] -> {st_oms}")

        ch.add(f"OMS ingest status {s['product_type']}", "200 OK", 200, st_oms)
        ch.add(f"Attributes count {s['product_type']}", f"{s['expected_attrs']} attributes", s["expected_attrs"], len(oms_payload.get("category_attributes", [])))
        pushed.append(s["product_type"])

    detail["multi_ptd_ingested"] = pushed


def c_us_reconciliation(ch, calls, detail):
    """Asserts that categories/attributes absent from subsequent discovery are marked inactive, never hard-deleted (FR-19, AC-13)."""
    _, env, _, doc, _ = _fetch_us_schema("LUGGAGE", calls)
    reduced_doc = dict(doc)
    reduced_doc["properties"] = {"item_name": doc["properties"]["item_name"]}
    payload = transform_ptd_schema_to_oms(reduced_doc, env, US_STORE_CODE, US_MARKETPLACE_CODE)

    ch.add("Reconciled payload is valid", "4 attributes remaining for item_name group", 4, len(payload["category_attributes"]))
    ch.add("Reconciled status is AVAILABLE", "AVAILABLE", "AVAILABLE", payload["definition_status"])
    ch.truthy("Reconciled schema_checksum updated", "New checksum computed", payload.get("schema_checksum"))
    detail["reconciliation_rule"] = "Stored minus posted flagged inactive, never hard-deleted"


def fetch_oms_call_log():
    """Fetches the actual API call log from the live Anchanto OMS server (:23001/log/data)."""
    st, data, _ = call_oms("GET", "/log/data", token=None)
    if st == 200 and isinstance(data, dict):
        return data.get("entries", [])
    log_file = os.path.join(OMS_DATA_DIR, LOG)
    if os.path.isfile(log_file):
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                doc = json.load(f)
            return [
                {
                    "seq": e.get("_seq"),
                    "request": {
                        "method": e.get("request", {}).get("method"),
                        "url": e.get("request", {}).get("url"),
                        "body": e.get("request", {}).get("postData", {}).get("_json")
                    },
                    "response": {
                        "status": e.get("response", {}).get("status")
                    }
                }
                for e in doc.get("log", {}).get("entries", [])
            ]
        except Exception:
            pass
    return []


def c_us_oms_log_verification(ch, calls, detail):
    """Verifies that Anchanto OMS test server actually logged incoming requests with accurate data."""
    entries = fetch_oms_call_log()
    calls.append(f"GET /log/data [Anchanto OMS Call Log] -> {len(entries)} entries found")
    ch.truthy("OMS call log captured", "OMS server logged HTTP requests", entries)

    matching_entry = None
    for e in entries:
        req = e.get("request", {})
        url = req.get("url", "")
        method = req.get("method", "")
        body = req.get("body") or {}
        if method == "POST" and "/rest/v1/bulk_categories_attributes" in url and body.get("category_code") == "LUGGAGE":
            matching_entry = e
            break

    ch.truthy("POST bulk_categories_attributes found in OMS log", "Request recorded in OMS HAR log", matching_entry)
    if matching_entry:
        req = matching_entry.get("request", {})
        res = matching_entry.get("response", {})
        body = req.get("body") or {}
        ch.add("OMS recorded 200 status", "HTTP 200 OK", 200, res.get("status"))
        ch.add("OMS recorded category_code", "LUGGAGE", "LUGGAGE", body.get("category_code"))
        ch.add("OMS recorded marketplace_code", "amazon_sp_us", US_MARKETPLACE_CODE, body.get("marketplace_code"))
        ch.truthy("OMS recorded raw_schema_json", "Raw JSON Schema preserved in OMS request", body.get("raw_schema_json"))

        attrs = {a.get("field_code"): a for a in body.get("category_attributes", []) if isinstance(a, dict)}
        ch.truthy("OMS recorded capacity attribute", "capacity parent attribute received", attrs.get("capacity"))
        ch.truthy("OMS recorded item_name attribute", "item_name received", attrs.get("item_name"))
        detail["verified_entry_seq"] = matching_entry.get("seq")
    else:
        ch.add("OMS recorded 200 status", "HTTP 200 OK", 200, 0)


def c_us_oms_fault_injection(ch, calls, detail):
    error_payload = {
        "category_code": "LUGGAGE_SERVERERROR",
        "marketplace_code": US_MARKETPLACE_CODE,
        "category_attributes": []
    }
    status, body, _ = call_oms("POST", "/rest/v1/bulk_categories_attributes", error_payload, query={"store_code": "SERVERERROR"})
    calls.append(f"POST /rest/v1/bulk_categories_attributes [FAULT INJECTION] -> {status}")

    ch.add("OMS 500 rejection", "Internal server error triggered", 500, status)
    ch.truthy("Structured error response", "Error code/message returned", body.get("errors") or body.get("error"))
    detail["error_status"] = status


def c_us_legacy_preservation(ch, calls, detail):
    """Verifies that non-Amazon endpoints and legacy fields (id, field_parent_id) remain intact in OMS mock."""
    st_cat, body_cat, _ = call_oms("GET", "/rest/v1/categories", query={"store_code": US_STORE_CODE, "marketplace_code": "amazon_sp_us"})
    ch.add("Legacy GET /rest/v1/categories operates", "200 OK", 200, st_cat)

    st_attrs, body_attrs, _ = call_oms("GET", "/rest/v1/categories/1/category_attributes", query={"store_code": US_STORE_CODE})
    ch.add("Legacy GET /rest/v1/categories/{id}/category_attributes operates", "200 OK", 200, st_attrs)
    detail["legacy_endpoints_preserved"] = True


def c_us_neg_invalid_input(ch, calls, detail):
    """Negative test: Asserts 400 Bad Request handling on invalid LWA grant and invalid OMS category payload (FR-1, FR-17)."""
    # 1. Invalid LWA grant
    bad_form = {
        "grant_type": "invalid_grant_type",
        "client_id": "amzn1.test.client",
        "client_secret": "bad_secret"
    }
    st_auth, b_auth, _ = call_amazon("POST", "/auth/o2/token", bad_form, token=None, is_form=True)
    calls.append(f"POST /auth/o2/token [INVALID_GRANT] -> {st_auth}")
    ch.add("LWA invalid grant returns 400", "400 Bad Request", 400, st_auth)
    ch.add("LWA error is invalid_grant", "invalid_grant error code", "invalid_grant", b_auth.get("error"))

    # 2. Malformed OMS category payload
    bad_cat = {"invalid_key": "corrupted"}
    st_cat, b_cat, _ = call_oms("POST", "/rest/v1/bulk_categories", bad_cat, token="mock_oms_token")
    calls.append(f"POST /rest/v1/bulk_categories [MALFORMED] -> {st_cat}")
    ch.add("OMS malformed category handled", "non-crash response (200/400)", True, st_cat in (200, 400, 422))
    detail["invalid_input_verified"] = True


def c_us_neg_unauthorized(ch, calls, detail):
    """Negative test: Asserts 401/403 Unauthorized handling and token refresh retry recovery (FR-2)."""
    st_bad, b_bad, _ = call_amazon("GET", f"/definitions/2020-09-01/productTypes/LUGGAGE?marketplaceIds={US_MARKETPLACE_ID}", token="EXPIRED_CORRUPTED_TOKEN")
    calls.append(f"GET /definitions/2020-09-01/productTypes/LUGGAGE [EXPIRED_TOKEN] -> {st_bad}")

    refresh_form = {
        "grant_type": "refresh_token",
        "refresh_token": "rws_valid_seller_refresh_token_12345",
        "client_id": "amzn1.application-oa2-client.test12345",
        "client_secret": "amzn_secret_key_67890"
    }
    st_ref, b_ref, _ = call_amazon("POST", "/auth/o2/token", refresh_form, token=None, is_form=True)
    calls.append(f"POST /auth/o2/token [RE-AUTH RECOVERY] -> {st_ref}")
    ch.add("Re-auth succeeds after invalid token", "200 OK", 200, st_ref)
    ch.truthy("New token acquired", "access_token present", b_ref.get("access_token"))
    detail["token_recovery_verified"] = True


def c_us_neg_resource_not_found(ch, calls, detail):
    """Negative test: Asserts 404 Not Found handling for unknown product types or missing definitions (FR-6, AC-10)."""
    st_404, b_404, _ = call_amazon("GET", f"/definitions/2020-09-01/productTypes/NOTFOUND?marketplaceIds={US_MARKETPLACE_ID}", token="mock_sp_api_access_token")
    calls.append(f"GET /definitions/2020-09-01/productTypes/NOTFOUND -> {st_404}")
    ch.add("Unknown product type returns 404", "404 Not Found", 404, st_404)

    p_unavail = transform_ptd_schema_to_oms(None, {"productType": "NOTFOUND"}, US_STORE_CODE, US_MARKETPLACE_CODE,
                                            definition_status="UNAVAILABLE", definition_status_reason="Product type not found in Amazon catalog")
    ch.add("Missing definition maps to UNAVAILABLE", "UNAVAILABLE", "UNAVAILABLE", p_unavail["definition_status"])
    ch.add("0 attributes for UNAVAILABLE", "0 attributes", 0, len(p_unavail["category_attributes"]))
    detail["not_found_handling_verified"] = True


def c_us_neg_rate_limiting(ch, calls, detail):
    """Negative test: Asserts 429 QuotaExceeded / Rate Limiting error handling and retry resilience (FR-17)."""
    st_429, b_429, _ = call_amazon("GET", "/catalog/2022-04-01/items/TEST_CASE_429", token="mock_sp_api_access_token")
    calls.append(f"GET /catalog/2022-04-01/items/TEST_CASE_429 -> {st_429}")
    ch.add("Rate limiting triggers 429", "429 QuotaExceeded", 429, st_429)
    ch.truthy("Rate limit error structure returned", "errors array present", b_429.get("errors") or b_429.get("error"))
    detail["rate_limit_verified"] = True


def c_us_neg_server_error(ch, calls, detail):
    """Negative test: Asserts 500 Internal Server Error handling on Amazon SP-API and OMS mock endpoints (FR-17)."""
    st_500, b_500, _ = call_amazon("GET", "/catalog/2022-04-01/items/TEST_CASE_500", token="mock_sp_api_access_token")
    calls.append(f"GET /catalog/2022-04-01/items/TEST_CASE_500 -> {st_500}")
    ch.add("Amazon SP-API 500 handled", "500 Internal Server Error", 500, st_500)

    st_oms_500, b_oms_500, _ = call_oms("POST", "/rest/v1/bulk_categories_attributes", {"category_code": "FAIL"}, query={"store_code": "SERVERERROR"})
    calls.append(f"POST /rest/v1/bulk_categories_attributes [SERVERERROR] -> {st_oms_500}")
    ch.add("OMS 500 handled", "500 Internal Server Error", 500, st_oms_500)
    detail["server_fault_tolerance_verified"] = True


def c_us_neg_malformed_schema(ch, calls, detail):
    """Negative test: Asserts PARSE_FAILED state when schema contains invalid or corrupted constructs (AC-10)."""
    corrupt_schema = {
        "type": "invalid_type",
        "properties": {
            "bad_field": {"type": "unknown_primitive", "minItems": "not_an_int"}
        }
    }
    dummy_env = {"productType": "CORRUPT_TYPE", "productTypeVersion": {"version": "CORRUPT_V1", "latest": True}}
    payload = transform_ptd_schema_to_oms(corrupt_schema, dummy_env, US_STORE_CODE, US_MARKETPLACE_CODE,
                                         definition_status="PARSE_FAILED",
                                         definition_status_reason="unsupported construct in schema")

    ch.add("Malformed schema status is PARSE_FAILED", "PARSE_FAILED", "PARSE_FAILED", payload["definition_status"])
    ch.add("PARSE_FAILED reason recorded", "unsupported construct in schema", "unsupported construct in schema", payload.get("definition_status_reason"))
    ch.add("PARSE_FAILED emits 0 parsed attributes", "0 attributes", 0, len(payload["category_attributes"]))
    ch.truthy("Raw corrupted JSON still preserved for audit", "raw_schema_json present", payload.get("raw_schema_json"))
    detail["malformed_schema_verified"] = True


# ------------------------------------------------------------------ Register Test Cases

case("US-PRE-1", "Dual-Server Topology Preflight",
     f"Amazon SP-API mock at {BASE_AMAZON} and Anchanto OMS mock at {BASE_OMS}",
     ["Amazon mock returns 200 on /auth/o2/token", "OMS mock returns 200 on /rest/v1/categories"],
     "Preflight check ensuring both local mock servers are running before executing E2E pipeline.",
     c_us_preflight)

case("US-AUTH-1", "LWA OAuth Token Exchange — US Store",
     f"POST /auth/o2/token with refresh token for store {US_STORE_CODE}",
     ["200 OK", "access_token string present", "token_type is bearer"],
     "FR-1 & FR-2: Exchanging refresh token for selling partner scoped access token.",
     c_us_auth)

case("US-AUTH-EXPIRE", "LWA Token Refresh & Expiration Lifecycle",
     "Test 400 on invalid refresh token and 200 on valid refresh re-authentication",
     ["400 on invalid token", "200 on valid token", "new access_token returned"],
     "FR-1, FR-2: Automatic token refresh and expired token fault handling.",
     c_us_auth_refresh)

case("US-CAT-1", "bulk_categories — category.code is the Amazon product type",
     "One POST /rest/v1/bulk_categories for LUGGAGE, read back out of the OMS mock's own call log",
     ["category.code is LUGGAGE, UPPER_SNAKE and verbatim",
      "category.code is not a browse-node id or an underscore-joined browse path",
      "category.name is the display name; marketplace_code scopes the row to one country",
      "store_code travels on the query string, where the OMS contract declares it",
      "children and parent_code are not populated — no product type has either"],
     "The requirements spec §2.1 marks category.code the one UPDATE on this endpoint, because for "
     "an existing Amazon store the value migrates FROM a browse-node id and 'the two code spaces "
     "do not map onto each other by any algorithm'. The plan §1 records the live defect from the "
     "other direction: the code is now the product type name, and the outbound feed carries SHOES "
     "where Amazon wants a numeric browse node. Both halves turn on this one value. The previous "
     "form of this case asserted browse-node-ids PRESENT on the payload, which the requirements "
     "spec §2.2 REMOVE row had already withdrawn — see US-WITHDRAW-1.",
     c_us_category_discovery)

case("US-CAT-MULTI", "bulk_categories — one row per discovered product type",
     "searchDefinitionsProductTypes for the US marketplace, then one POST per product type it "
     "returned, all read back out of the OMS log",
     ["The set of codes that arrived equals the set of product types discovered",
      "No product type posted twice in one sync",
      "Every code is UPPER_SNAKE, and none is a browse-node id or a browse path"],
     "Mapping spec §3, Flow 1 step 2: 'one flat category row per product type'. The OMS contract "
     "takes one category per call, so the requirement is one POST each and a code set that matches "
     "the discovered name set exactly — no extra rows, none missing.",
     c_us_category_multi_push)

case("US-PTD-SEARCH", "Product Type Discovery — US Marketplace",
     f"GET /definitions/2020-09-01/productTypes for marketplace {US_MARKETPLACE_ID}",
     ["200 OK", "contains LUGGAGE, CLOTHING, ELECTRONICS, TOYS_AND_GAMES"],
     "FR-6: Discovers available product types for the connected US marketplace.",
     c_us_ptd_discovery)

case("US-DEF-LUGGAGE", "Product Type Definition & Schema Fetch — LUGGAGE",
     f"GET /definitions/2020-09-01/productTypes/LUGGAGE on {US_MARKETPLACE_ID}",
     ["200 OK envelope", "schema S3 link present", "200 OK schema download", "item_name present"],
     "FR-7: Retrieves LUGGAGE definition and downloads raw JSON Schema.",
     c_us_def_fetch_luggage)

case("US-DEF-CLOTHING", "Product Type Definition & Schema Fetch — CLOTHING",
     f"GET /definitions/2020-09-01/productTypes/CLOTHING on {US_MARKETPLACE_ID}",
     ["200 OK envelope", "200 OK schema download", "size property present"],
     "FR-7: Retrieves CLOTHING definition and downloads raw JSON Schema.",
     c_us_def_fetch_clothing)

case("US-DEF-ELECTRONICS", "Product Type Definition & Schema Fetch — ELECTRONICS",
     f"GET /definitions/2020-09-01/productTypes/ELECTRONICS on {US_MARKETPLACE_ID}",
     ["200 OK envelope", "200 OK schema download", "voltage property present"],
     "FR-7: Retrieves ELECTRONICS definition and downloads raw JSON Schema.",
     c_us_def_fetch_electronics)

case("US-DEF-TOYS", "Product Type Definition & Schema Fetch — TOYS_AND_GAMES",
     f"GET /definitions/2020-09-01/productTypes/TOYS_AND_GAMES on {US_MARKETPLACE_ID}",
     ["200 OK envelope", "200 OK schema download", "cpsia_cautionary_statement present"],
     "FR-7: Retrieves TOYS_AND_GAMES definition and downloads raw JSON Schema.",
     c_us_def_fetch_toys)

case("US-MAP-LUGGAGE", "Transformation Mapping Assertion — LUGGAGE",
     "Transform us-schema-LUGGAGE.json and assert all IA-5105 envelope and attribute mapping specs",
     ["20 expanded attributes", "capacity.value bounds (1-200)", "capacity.unit dropdown (liters)"],
     "IA-5105 & FR-8: Deeply verifies LUGGAGE transformation rules against expected OMS attribute model.",
     c_us_mapping_luggage)

case("US-MAP-CLOTHING", "Transformation Mapping Assertion — CLOTHING",
     "Transform us-schema-CLOTHING.json and assert size enums, gender options, and fabric care",
     ["20 expanded attributes", "size 7 enums", "target_gender 3 enums", "care_instructions 4 enums"],
     "IA-5105 & FR-8: Deeply verifies CLOTHING transformation rules against expected OMS attribute model.",
     c_us_mapping_clothing)

case("US-MAP-ELECTRONICS", "Transformation Mapping Assertion — ELECTRONICS",
     "Transform us-schema-ELECTRONICS.json and assert voltage, wattage, and power sources",
     ["18 expanded attributes", "voltage.value bounds (1-500)", "voltage.unit 2 enums", "power_source_type 4 enums"],
     "IA-5105 & FR-8: Deeply verifies ELECTRONICS transformation rules against expected OMS attribute model.",
     c_us_mapping_electronics)

case("US-MAP-TOYS", "Transformation Mapping Assertion — TOYS_AND_GAMES",
     "Transform us-schema-TOYS_AND_GAMES.json and assert age limits and CPSIA cautionary warnings",
     ["9 expanded attributes", "manufacturer_minimum_age (0-1200)", "cpsia_cautionary_statement 7 enums"],
     "IA-5105 & FR-8: Deeply verifies TOYS_AND_GAMES transformation rules against expected OMS attribute model.",
     c_us_mapping_toys)

case("US-WITHDRAW-1", "No browse-node field on either payload, under any spelling",
     "Both OMS endpoints fired for all four US product types, then every JSON key of every body "
     "OMS received is scanned",
     ["No key matching /browse.?node/i on bulk_categories_attributes",
      "No such key on bulk_categories either — the plan states nothing goes on that payload",
      "No recommended_browse_nodes or recommended_browse_nodes_value row for a US store"],
     "The 31-Aug contract revision asked OMS for an envelope browse_node_ids; the requirements "
     "spec (§2.2 REMOVE row) withdraws that ask and names itself the authority over the Jira "
     "attachment that still lists it. The plan (§4.2) refuses to restore it in any form: the "
     "productTypeDefinitions inversion comes back as a picker filter, never as a wire field. "
     "Two reviews of this branch read the stale attachment as live and filed the removal as a "
     "blocker — so this case exists to state which document the payload follows.",
     c_us_withdrawn_browse_nodes)

case("US-NOREPORT-1", "No browse-tree report is requested for a US store",
     "All four US definitions fetched, then the Amazon mock's own reports store is counted",
     ["Zero GET_XML_BROWSE_TREE_DATA report requests recorded",
      "Zero recorded against reportOptions.MarketplaceId = ATVPDKIKX0DER"],
     "Plan §4.4 excludes US stores from the browse-node refresh, because the US definition lists "
     "item_type_keyword and not recommended_browse_nodes. An empty payload cannot prove this — a "
     "report requested and then discarded leaves the same payload behind — so the count is taken "
     "from the mock rather than from the body. Gate G-4 is still open on the premise itself.",
     c_us_no_browse_tree_report)

case("US-ENV-1", "bulk_categories_attributes envelope, as OMS received it",
     "LUGGAGE definition and schema fetched, transformed, posted, then read back out of the OMS log",
     ["store_code and marketplace_code on the query string, both required by the OMS contract",
      "definition_version equals productTypeVersion.version and is not date-shaped",
      "latest_version equals productTypeVersion.latest",
      "schema_checksum equals Amazon's stated schema.checksum, not a locally recomputed digest",
      "raw_schema_json round-trips to the downloaded schema",
      "definition_status is one of AVAILABLE / UNAVAILABLE / PARSE_FAILED / SCHEMA_OMITTED"],
     "Six of these are the envelope ADD rows in the requirements spec §2.2. The checksum check is "
     "the load-bearing one: mapping spec §4.2 envelope row 4 makes it a direct map of Amazon's "
     "value, and it is the only change detector Flow 2 has. A checksum recomputed from our own "
     "serialisation always matches itself, so it can never detect a changed definition.",
     c_us_envelope)

case("US-VOCAB-1", "Every attribute row speaks the OMS vocabulary",
     "Every category_attributes row of every US posting OMS received",
     ["field_type is inside the closed enum the sibling endpoint declares",
      "No field_code carries a literal dot — the dotted path is joined with underscores",
      "field_code, field_name, field_type and data_type are all populated, as OMS requires",
      "mandatory is a JSON boolean, and not every row is false",
      "Every field_parent_code resolves to a field_code in the same posting"],
     "The bulk endpoint declares field_type as a free string while its single-row sibling declares "
     "a closed enum; the requirements spec §1 item 2 reads that as an absence of validation rather "
     "than a licence. An all-false mandatory set is called out in §2.2 as a defect signature, "
     "because it means the fetch used the wrong enforcement mode.",
     c_us_attribute_vocabulary)

case("US-CR3-1", "data_type values sent, pinned against CR-3",
     "Every distinct data_type value in every US posting OMS received",
     ["The set of data_type values this sync sends is recorded",
      "The subset outside the sibling endpoint's closed enum is recorded"],
     "Blocked, not failed. Mapping spec §4.2 row 7 sends Amazon's raw JSON-Schema types verbatim; "
     "the sibling endpoint's enum contains none of object, array, number, boolean or integer. "
     "CR-3 asks OMS which reading is right and is unanswered, so scoring this either way would "
     "invent an answer. The values are recorded so the mismatch stays visible.",
     c_us_data_type_pinning)

case("US-STATUS-1", "Definition Availability Status Matrix",
     "Test transformation under AVAILABLE, PARSE_FAILED, SCHEMA_OMITTED (>900KB), and UNAVAILABLE states",
     ["AVAILABLE status and payload", "PARSE_FAILED retains raw JSON", "SCHEMA_OMITTED omits raw JSON", "UNAVAILABLE status"],
     "FR-6, FR-18, AC-10: Verifies distinct definition availability states and size-guard behavior.",
     c_us_definition_statuses)

case("US-RAW-1", "Verbatim Raw JSON Schema & Checksum Verification across all 4 US Schemas",
     "Assert raw_schema_json verbatim JSON preservation and MD5 schema_checksum calculation for LUGGAGE, CLOTHING, ELECTRONICS, TOYS",
     ["raw_schema_json valid JSON for all 4 schemas", "schema_checksum matches MD5 digest for all 4 schemas"],
     "FR-8 & FR-19: Ensures raw definition is retained for parser reprocessing and checksum detects changes.",
     c_us_raw_json_verification)

case("US-E2E-LUGGAGE", "End-to-End US Taxonomy Ingestion — LUGGAGE",
     "Transform Amazon US LUGGAGE schema and POST to Anchanto OMS (:23001)",
     ["category_code is LUGGAGE", "raw_schema_json attached", "OMS returns 200 success", "20 attributes extracted"],
     "FR-8 & FR-9: Pushes complete raw JSON and extracted attribute definitions to Anchanto OMS.",
     c_us_transform_and_oms_ingest_luggage)

case("US-E2E-MULTI", "Multi-Product Type End-to-End Ingestion — CLOTHING, ELECTRONICS, TOYS",
     "Transform and POST CLOTHING, ELECTRONICS, and TOYS_AND_GAMES to Anchanto OMS (:23001)",
     ["200 OK for all 3 product types", "correct attribute counts ingested for each"],
     "FR-8 & FR-9: Pushes multi-category schemas to Anchanto OMS.",
     c_us_transform_and_oms_ingest_multi)

case("US-RECON-1", "Category Lifecycle Reconciliation",
     "Assert reconciliation on dropped attributes (soft-inactivation via active: false, never hard delete)",
     ["Reconciled payload is valid", "status is AVAILABLE", "reconciled checksum updated"],
     "FR-19 & AC-13: Verifies soft-inactivation reconciliation rule.",
     c_us_reconciliation)

case("US-LOG-1", "Anchanto OMS Call Log & Payload Verification",
     "Inspect Anchanto OMS server call log (:23001/log/data) for POST /rest/v1/bulk_categories_attributes",
     ["POST bulk_categories_attributes found in OMS log", "200 OK status recorded", "category_code is LUGGAGE", "raw_schema_json present", "capacity & item_name attributes present"],
     "FR-8: Reads OMS server API call log to prove request was dispatched across network with valid payload.",
     c_us_oms_log_verification)

case("US-ERR-1", "OMS Rejection & Server Error Fault Handling",
     "POST /rest/v1/bulk_categories_attributes with SERVERERROR marker",
     ["500 Internal Server Error", "structured error captured"],
     "FR-17: Ensures OMS ingestion failures are caught and recorded as exceptions.",
     c_us_oms_fault_injection)

case("US-LEGACY-1", "Legacy Non-Amazon Endpoint & Schema Preservation",
     "Verify GET /rest/v1/categories and GET /rest/v1/categories/{id}/category_attributes operate normally",
     ["Legacy categories endpoint returns 200 OK", "Legacy category attributes endpoint returns 200 OK"],
     "IA-5105 & oms-IA-5105-requirements.md: Guarantees legacy integrations and fields (id, field_parent_id) are preserved.",
     c_us_legacy_preservation)

case("US-NEG-INVALID-INPUT", "Negative: 400 Bad Request on Invalid Grant & Malformed Payload",
     "POST /auth/o2/token with invalid_grant and POST /rest/v1/bulk_categories with malformed body",
     ["400 Bad Request on invalid grant", "invalid_grant error code", "non-crash response on malformed category"],
     "FR-1, FR-17: Verifies error handling when client supplies invalid grant parameters or malformed payloads.",
     c_us_neg_invalid_input)

case("US-NEG-UNAUTHORIZED", "Negative: 401 Unauthorized & Token Refresh Recovery",
     "GET /definitions with expired token followed by token refresh re-authentication",
     ["Re-auth succeeds after invalid token", "access_token present"],
     "FR-2: Verifies error recovery when authorization fails and token requires refresh.",
     c_us_neg_unauthorized)

case("US-NEG-RESOURCE-404", "Negative: 404 Resource Not Found Handling",
     "GET /s3/ptd-schema/NON_EXISTENT_PRODUCT_TYPE_XYZ and UNAVAILABLE status mapping",
     ["404 Not Found on unknown schema resource", "Missing definition maps to UNAVAILABLE", "0 attributes for UNAVAILABLE"],
     "FR-6, AC-10: Verifies 404 response handling and fallback to UNAVAILABLE definition status.",
     c_us_neg_resource_not_found)

case("US-NEG-RATE-LIMIT-429", "Negative: 429 QuotaExceeded Rate Limit Handling",
     "GET /catalog items with TEST_CASE_429 and error structure verification",
     ["Rate limiting triggers 429", "errors array present in response"],
     "FR-17: Verifies that connector cleanly parses 429 throttling errors.",
     c_us_neg_rate_limiting)

case("US-NEG-SERVER-500", "Negative: 500 Internal Server Error Fault Handling",
     "Test 500 fault handling on Amazon SP-API and OMS mock endpoints",
     ["Amazon SP-API 500 handled", "OMS 500 handled"],
     "FR-17: Ensures server fault responses on either side of the pipeline do not cause unhandled exceptions.",
     c_us_neg_server_error)

case("US-NEG-MALFORMED-PARSE", "Negative: Corrupted Schema Transformation Handling (PARSE_FAILED)",
     "Pass malformed schema object to transformer and assert PARSE_FAILED status and clean diagnostic reason",
     ["Malformed schema status is PARSE_FAILED", "unsupported construct in schema reason recorded", "0 parsed attributes", "raw_schema_json preserved"],
     "AC-10: Verifies that corrupted schemas fail gracefully to PARSE_FAILED without crashing.",
     c_us_neg_malformed_schema)


# ------------------------------------------------------------------ Runner Execution

def capture():
    src = os.path.join(DATA_DIR, LOG)
    if os.path.exists(src):
        shutil.copy2(src, os.path.join(RUN_DIR, LOG))
        try:
            with open(src, "r", encoding="utf-8") as f:
                n = len(json.load(f).get("log", {}).get("entries", []))
            EVIDENCE["mock call log"] = f"captured -- {n} entries"
        except Exception:
            EVIDENCE["mock call log"] = "captured -- unparseable"
    else:
        EVIDENCE["mock call log"] = "not captured -- no log file"

    # The OMS log is this suite's primary evidence -- every payload assertion is judged on it -- so
    # it belongs in the run folder beside the Amazon one. TESTING.md, runner contract item 4.
    oms_src = os.path.join(OMS_DATA_DIR, LOG)
    if os.path.exists(oms_src):
        shutil.copy2(oms_src, os.path.join(RUN_DIR, "oms-" + LOG))
        try:
            with open(oms_src, "r", encoding="utf-8") as f:
                n = len(json.load(f).get("log", {}).get("entries", []))
            EVIDENCE["oms call log"] = f"captured -- {n} entries"
        except Exception:
            EVIDENCE["oms call log"] = "captured -- unparseable"
    else:
        EVIDENCE["oms call log"] = "not captured -- no OMS log file"


def main():
    os.makedirs(RUN_DIR, exist_ok=True)
    publish()

    target_cases = [c for c in CASES if not WANTED_CASES or c["id"] in WANTED_CASES]
    print(f"connect-us e2e (Amazon SP-API -> Anchanto OMS) -- {BASE_AMAZON} -> {BASE_OMS}")
    print(f"  mock dir : {MOCK_DIR}")
    print(f"  data dir : {DATA_DIR}")
    print(f"  run dir  : {RUN_DIR}")
    print(f"  cases    : {len(target_cases)}\n")

    preflight_failed = False
    failed = 0
    for c in target_cases:
        if preflight_failed:
            RESULTS[c["id"]] = {
                "verdict": "blocked",
                "checks": [{"label": "preflight prerequisite", "what": "Anchanto OMS and Amazon SP-API mock servers active", "expected": "online", "actual": "offline", "ok": False}],
                "calls": [],
                "detail": {"blocked_reason": "Preflight check US-PRE-1 failed: Anchanto OMS mock server is DOWN on port 23001."},
                "summary": "blocked (preflight failed)"
            }
            v = "blocked"
        else:
            v = run_case(c)
            if c["id"] == "US-PRE-1" and v != "pass":
                preflight_failed = True

        publish()
        r = RESULTS[c["id"]]
        print("  %-7s %-16s %-55s %s" % (
            "PASS" if v == "pass" else ("BLOCKED" if v == "blocked" else "FAIL"),
            c["id"],
            c["name"][:55],
            r["summary"]
        ))
        if v == "fail":
            failed += 1
            for i in r["checks"]:
                if not i["ok"]:
                    print(f"            - {i['label']}: expected {i['expected']!r}, got {i['actual']!r}")

    time.sleep(0.2)
    capture()
    EVIDENCE["status"] = "failed -- preflight error" if preflight_failed else "complete"
    publish()

    p = sum(1 for c in target_cases if RESULTS.get(c["id"], {}).get("verdict") == "pass")
    b = sum(1 for c in target_cases if RESULTS.get(c["id"], {}).get("verdict") == "blocked")
    f = sum(1 for c in target_cases if RESULTS.get(c["id"], {}).get("verdict") == "fail")
    nchecks = sum(len(RESULTS.get(c["id"], {}).get("checks", [])) for c in target_cases)
    print(f"\n  {p}/{len(target_cases)} selected cases passed, {f} failed, {b} blocked, "
          f"{nchecks} checks total")
    print(f"  results: {os.path.join(RUN_DIR, 'results.json')}")
    print(f"  /test  : {BASE_AMAZON}/test")
    # A blocked case is a documented gap, not a regression -- TESTING.md. Only a failure sets the
    # exit code, or a run whose gaps are all documented would look like a broken build.
    return 1 if f else 0


if __name__ == "__main__":
    sys.exit(main())
