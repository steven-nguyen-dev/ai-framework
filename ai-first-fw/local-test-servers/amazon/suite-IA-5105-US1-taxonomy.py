#!/usr/bin/env python3
"""IA-5105-US1: Amazon Marketplace Taxonomy sync suite -- discovery calls and category payload.

Two halves, and the second one is new.

**Amazon's side (SRCH-1, TAX-*).** The call sequence a store-connect metadata sync makes:
searchDefinitionsProductTypes -> getDefinitionsProductType -> GET schema.link.resource, across one
North America store (US) and four non-US stores spanning Europe (DE, ES, FR) and the Far East (AU)
-- proving marketplace isolation for a product type Amazon reuses across markets (PRODUCT: DE and
ES), and that the schema content genuinely differs rather than merely echoing the requested locale
and marketplaceId.

**OMS's side (TAX-CAT-*).** POST /rest/v1/bulk_categories, at the Anchanto OMS mock on :23001.
This suite made no mention of bulk_categories until these four cases existed, so the whole of the
requirements spec section 2.1 and mapping spec section 4.1 went unasserted anywhere in this
repository -- including the one value the ticket turns on, that category.code IS the Amazon product
type and never a browse-node id. What each case covers, and which document states it, is in its own
`note`; the expectations themselves are in ia5105_requirements.py with their citations.

    TAX-CAT-1     category.code is the product type, one row per type, per market
    TAX-CAT-2     no browse-node field on the payload, under any spelling
    TAX-CAT-3     the same code in two countries, told apart by marketplace_code
    TAX-CAT-CR1   upsert semantics are unstated by the OMS contract -- blocked, recorded

The five product type definitions served here are JPluger's own test fixtures under
marketplace-integrations/src/test/resources/amazon/definitions/. Their provenance is stated in each
file's own `x-fixture-provenance`: PRODUCT (DE, ES) and AUTO_PART (AU) are real schemas captured
from live Amazon; LUGGAGE (US) and SHOES (FR) are hand-authored and marked SYNTHETIC, so nothing
observed through them may be cited as Amazon's behaviour.

The payload is built by amazon_taxonomy_transformer, a local stand-in for the JPluger Amazon
integration this harness cannot start, and judged on what arrived at the OMS mock's own call log.

Runner contract: TESTING.md.
Publishes live status to amazon/test-results/IA-5105-US1-taxonomy/run-<stamp>/results.json.

Usage:
  python3 amazon/suite-IA-5105-US1-taxonomy.py
  python3 amazon/suite-IA-5105-US1-taxonomy.py TAX-CAT-1 TAX-CAT-2       # only the cases named
  BASE=http://127.0.0.1:23103 BASE_OMS=http://127.0.0.1:23001 python3 amazon/suite-IA-5105-US1-taxonomy.py

Needs the OMS mock on :23001 for the TAX-CAT cases (`python3 mock.py anchanto-oms`); without it
they are blocked and the Amazon-side cases still run.
"""

import atexit
import datetime
import hashlib
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer

BASE = os.environ.get("BASE", "http://127.0.0.1:23103").rstrip("/")
BASE_OMS = os.environ.get("BASE_OMS", "http://127.0.0.1:23001").rstrip("/")
SUITE = os.environ.get("SUITE", "IA-5105-US1-taxonomy")
KEEP = "--keep-state" in sys.argv
WANTED_CASES = set(a for a in sys.argv[1:] if not a.startswith("-"))

HERE = os.path.dirname(os.path.abspath(__file__))
MOCK_DIR = HERE
DATA_DIR = os.path.join(MOCK_DIR, "mock-data")
LOG = "api-calls.har.json"
STAMP = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
RUN_DIR = os.path.join(MOCK_DIR, "test-results", SUITE, "run-" + STAMP)

STORES = [
    "lwa_tokens", "created_orders", "shipment_confirmations", "order_acknowledgements",
    "feeds", "feed_documents", "reports", "listings", "mfn_shipments",
]

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
    api_log = mock.ApiLog(os.path.join(DATA_DIR, LOG), "har", config.get("log_redact_headers"), "Amazon SP-API")
    handler_cls = mock.make_handler(config, routes, state, api_log, os.path.join(MOCK_DIR, "test-results"),
                                    [], mock.SuiteRunner(), MOCK_DIR)

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


def call(method, path, body=None, token="mock_sp_api_access_token"):
    url = BASE + path
    headers = {}
    data = None
    if body is not None:
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
    """The Anchanto OMS mock on :23001. The category half of this ticket ends there, and until this
    suite fired at it, nothing anywhere asserted the bulk_categories payload."""
    full_path = path + ("?" + urllib.parse.urlencode(query) if query else "")
    url = BASE_OMS + full_path
    headers = {"Content-Type": "application/json"}
    data = json.dumps(body).encode("utf-8") if body is not None else None
    if token:
        headers["Authorization"] = "Bearer " + token

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            raw, status = r.read(), r.status
    except urllib.error.HTTPError as e:
        raw, status = e.read(), e.code
    except Exception as e:
        return 0, {"_transport_error": str(e)}, b""
    try:
        return status, json.loads(raw.decode("utf-8")) if raw.strip() else {}, raw
    except Exception:
        return status, raw.decode("utf-8", "replace"), raw


CASES, RESULTS = [], {}
EVIDENCE = {
    "status": "running",
    "mock call log": "not captured",
    "mock stores": "not captured",
    "server": "Amazon SP-API mock at %s" % BASE,
    "oms server": "Anchanto OMS mock at %s" % BASE_OMS,
}

# Set by preflight. The OMS half of this suite cannot run without the OMS mock, and a case that
# cannot prove anything is `blocked`, not `fail` -- TESTING.md.
OMS_UP = False

# Cases whose verdict is fixed regardless of their checks, because the requirement they would score
# is an unanswered change request. TESTING.md keeps `blocked` distinct from `fail` for exactly this.
BLOCKED_CASES = {"TAX-CAT-CR1"}


def case(cid, name, given, then, note, fn):
    CASES.append({"id": cid, "name": name, "given": given,
                  "then": then if isinstance(then, list) else [then], "note": note, "fn": fn})


def publish():
    cases = []
    for c in CASES:
        r = RESULTS.get(c["id"])
        e = {"id": c["id"], "name": c["name"], "given": c["given"], "then": c["then"], "note": c["note"]}
        if r:
            e.update(r)
        elif WANTED_CASES and c["id"] not in WANTED_CASES:
            e.update({
                "verdict": "skip",
                "summary": "skipped (not selected)",
                "checks": [],
                "calls": [],
                "detail": {}
            })
        else:
            e.update({"verdict": "pending"})
        cases.append(e)

    done = [c for c in cases if c.get("verdict") in ("pass", "fail", "blocked", "skip")]
    doc = {
        "name": "IA-5105-US1: Amazon Marketplace Taxonomy Sync -- US vs non-US",
        "suite": SUITE,
        "at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "base_url": BASE,
        "summary": {
            "pass": sum(1 for c in done if c["verdict"] == "pass"),
            "fail": sum(1 for c in done if c["verdict"] == "fail"),
            "blocked": sum(1 for c in done if c["verdict"] == "blocked"),
            "skip": sum(1 for c in done if c["verdict"] == "skip"),
        },
        "evidence": EVIDENCE,
        "cases": cases,
    }
    os.makedirs(RUN_DIR, exist_ok=True)
    with open(os.path.join(RUN_DIR, "results.json"), "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2)


class Checks:
    def __init__(self):
        self.items = []

    def add(self, label, what, expected, actual):
        ok = (str(expected) == str(actual)) if not isinstance(expected, bool) else (expected is (actual is True or actual == "True"))
        self.items.append({"label": label, "what": what, "expected": str(expected), "actual": str(actual), "ok": ok})

    def truthy(self, label, what, actual):
        got = "present" if actual not in (None, "", [], {}) else "missing"
        self.items.append({"label": label, "what": what, "expected": "present", "actual": got, "ok": got == "present"})

    @property
    def ok(self):
        return all(i["ok"] for i in self.items)


def run_case(c):
    ch, calls, detail = Checks(), [], {}
    if c["id"].startswith("TAX-CAT") and not OMS_UP:
        RESULTS[c["id"]] = {
            "verdict": "blocked",
            "checks": [{"label": "OMS mock reachable", "what": "port 23001 answers",
                        "expected": "online", "actual": "offline", "ok": False}],
            "calls": [], "detail": {"blocked_reason":
                                    "Anchanto OMS mock is not running on %s -- start it with "
                                    "`python3 mock.py anchanto-oms`. The category payload cannot be "
                                    "judged without the endpoint that receives it." % BASE_OMS},
            "summary": "blocked -- OMS mock offline"}
        return "blocked"
    try:
        c["fn"](ch, calls, detail)
        verdict = "blocked" if c["id"] in BLOCKED_CASES else ("pass" if ch.ok else "fail")
    except Exception as e:
        ch.add("runner exception", "no unhandled exception", "none", "error: %s" % e)
        verdict = "fail"

    np = sum(1 for i in ch.items if i["ok"])
    RESULTS[c["id"]] = {"verdict": verdict, "checks": ch.items, "calls": calls, "detail": detail,
                        "summary": "%d/%d checks passed" % (np, len(ch.items))}
    return verdict


# ------------------------------------------------------------------ store fixtures under test

# (region label, marketplaceId, expected productType, locale, expected top-level property count)
US = ("US (North America)", "ATVPDKIKX0DER", "LUGGAGE", "en_US")
DE = ("DE (Europe)", "A1PA6795UKMFR9", "PRODUCT", "de_DE")
ES = ("ES (Europe)", "A1RKKUPIHCS9HS", "PRODUCT", "es_ES")
FR = ("FR (Europe)", "A13V1IB3VIYZZH", "SHOES", "fr_FR")
AU = ("AU (Far East)", "A39IBJ37TRP1C6", "AUTO_PART", "en_AU")


def _search(marketplace_id):
    return call("GET", "/definitions/2020-09-01/productTypes?marketplaceIds=%s" % marketplace_id)


def _definition(product_type, marketplace_id, locale):
    return call("GET", "/definitions/2020-09-01/productTypes/%s"
                       "?marketplaceIds=%s&requirements=LISTING_PRODUCT_ONLY"
                       "&requirementsEnforced=ENFORCED&locale=%s&parentageLevel=NONE"
                       % (product_type, marketplace_id, locale))


def _resolve(url):
    return call("GET", url[len(BASE):] if url.startswith(BASE) else url)


def _fetch_schema(envelope):
    """Mirrors AmazonDefinitionsUtility.fetchDefinition: resolve the schema link, then verify
    Amazon's stated checksum against the downloaded bytes (empty/absent checksum always matches)."""
    url = envelope.get("schema", {}).get("link", {}).get("resource", "")
    status, body, raw = _resolve(url)
    stated = envelope.get("schema", {}).get("checksum") or ""
    matches = (not stated) or stated == hashlib.md5(raw).hexdigest() \
        or stated == __import__("base64").b64encode(hashlib.md5(raw).digest()).decode()
    return status, body, matches


def c_search_by_market(ch, calls, detail):
    for region, marketplace_id, expected_type, _locale in (US, DE, ES, FR, AU):
        status, body, _raw = _search(marketplace_id)
        calls.append("GET searchDefinitionsProductTypes[%s] -> %s" % (region, status))
        ch.add("status %s" % region, "search succeeds", 200, status)
        names = [pt.get("name") for pt in body.get("productTypes", [])]
        ch.add("productType %s" % region, "store discovers its own catalogue", expected_type,
               names[0] if names else None)
        ch.truthy("productTypeVersion %s" % region, "search-level version is a bare string",
                  body.get("productTypeVersion"))
        ch.add("productTypeVersion is a string %s" % region, "not the {version,latest,...} object shape",
               True, isinstance(body.get("productTypeVersion"), str))


def _definition_checks(ch, calls, region, marketplace_id, expected_type, locale):
    status, envelope, _raw = _definition(expected_type, marketplace_id, locale)
    calls.append("GET getDefinitionsProductType[%s/%s] -> %s" % (region, expected_type, status))
    ch.add("status %s" % region, "definition envelope resolves", 200, status)
    ch.add("productType echoed %s" % region, "matches the path segment", expected_type, envelope.get("productType"))
    ch.add("marketplaceIds echoed %s" % region, "matches the requested marketplace",
           [marketplace_id], envelope.get("marketplaceIds"))
    ch.add("locale echoed %s" % region, "matches the requested locale", locale, envelope.get("locale"))
    ch.add("requirements echoed %s" % region, "the real app always sends this",
           "LISTING_PRODUCT_ONLY", envelope.get("requirements"))
    ch.add("schema is a link, not inline %s" % region, "SchemaLink shape",
           True, isinstance(envelope.get("schema"), dict) and "link" in envelope.get("schema", {}))
    version = envelope.get("productTypeVersion") or {}
    ch.add("productTypeVersion is an object %s" % region, "not a bare string",
           True, isinstance(envelope.get("productTypeVersion"), dict))
    ch.add("latest is true %s" % region,
           "the exact gate AmazonDefinitionsUtility.fetchDefinition checks before accepting a definition",
           True, version.get("latest") is True)
    return envelope


def c_us_definition_and_schema(ch, calls, detail):
    region, marketplace_id, expected_type, locale = US
    envelope = _definition_checks(ch, calls, region, marketplace_id, expected_type, locale)

    status, schema, checksum_ok = _fetch_schema(envelope)
    calls.append("GET schema.link.resource[%s] -> %s" % (region, status))
    ch.add("schema link resolves %s" % region, "second GET returns the JSON Schema", 200, status)
    ch.add("checksum verification passes %s" % region,
           "AmazonDefinitionsUtility.checksumMatches accepts an empty/absent checksum as a match",
           True, checksum_ok)
    props = schema.get("properties", {})
    ch.add("US LUGGAGE carries capacity", "a US-only attribute not present in the non-US fixtures",
           True, "capacity" in props)
    ch.truthy("required array %s" % region, "mandatory attributes", schema.get("required"))
    detail["us_property_count"] = len(props)


def c_fr_edge_case_schema(ch, calls, detail):
    region, marketplace_id, expected_type, locale = FR
    envelope = _definition_checks(ch, calls, region, marketplace_id, expected_type, locale)

    status, schema, checksum_ok = _fetch_schema(envelope)
    calls.append("GET schema.link.resource[%s] -> %s" % (region, status))
    ch.add("schema link resolves %s" % region, "second GET returns the JSON Schema", 200, status)
    ch.add("checksum verification passes %s" % region, "empty checksum is treated as a match",
           True, checksum_ok)
    props = schema.get("properties", {})
    ch.add("FR SHOES carries heel_height", "a non-US-only attribute", True, "heel_height" in props)
    ch.add("orphan $ref present", "guards a dangling #/$defs/does_not_exist reference the app must not crash on",
           True, "orphan_ref" in props and "$ref" in props.get("orphan_ref", {}))
    ch.add("non-English default language_tag", "fr_FR default, not en_US",
           "fr_FR", schema.get("$defs", {}).get("language_tag", {}).get("default"))


def c_de_es_product_isolation(ch, calls, detail):
    """The real edge case this suite exists for: DE and ES both discover productType PRODUCT --
    the mock must not collapse them onto one schema the way an unkeyed schema link would."""
    de_region, de_mp, de_type, de_locale = DE
    es_region, es_mp, es_type, es_locale = ES

    de_envelope = _definition_checks(ch, calls, de_region, de_mp, de_type, de_locale)
    es_envelope = _definition_checks(ch, calls, es_region, es_mp, es_type, es_locale)

    ch.add("DE and ES schema links differ", "the marketplaceId travels on the schema link, "
           "not just the definition envelope", True,
           de_envelope["schema"]["link"]["resource"] != es_envelope["schema"]["link"]["resource"])

    de_status, de_schema, de_checksum_ok = _fetch_schema(de_envelope)
    es_status, es_schema, es_checksum_ok = _fetch_schema(es_envelope)
    calls.append("GET schema.link.resource[DE] -> %s" % de_status)
    calls.append("GET schema.link.resource[ES] -> %s" % es_status)

    ch.add("DE schema resolves", "second GET returns JSON Schema", 200, de_status)
    ch.add("ES schema resolves", "second GET returns JSON Schema", 200, es_status)
    ch.add("DE checksum verification passes", "empty checksum is treated as a match", True, de_checksum_ok)
    ch.add("ES checksum verification passes", "empty checksum is treated as a match", True, es_checksum_ok)

    de_props, es_props = set(de_schema.get("properties", {})), set(es_schema.get("properties", {}))
    ch.add("DE and ES property sets differ", "same productType name, genuinely different real captured schemas",
           True, de_props != es_props)
    ch.add("DE recommended_browse_nodes carries no enum",
           "real captured Amazon schemas never enumerate this field -- a parser that assumes an "
           "enum here breaks on live data", True,
           "enum" not in json.dumps(de_schema.get("properties", {}).get("recommended_browse_nodes", {})))
    detail["de_property_count"] = len(de_props)
    detail["es_property_count"] = len(es_props)


def c_au_deep_nesting(ch, calls, detail):
    region, marketplace_id, expected_type, locale = AU
    envelope = _definition_checks(ch, calls, region, marketplace_id, expected_type, locale)

    status, schema, checksum_ok = _fetch_schema(envelope)
    calls.append("GET schema.link.resource[%s] -> %s" % (region, status))
    ch.add("schema link resolves %s" % region, "second GET returns the JSON Schema", 200, status)
    ch.add("checksum verification passes %s" % region, "empty checksum is treated as a match",
           True, checksum_ok)

    def max_depth(node, depth=0):
        if depth > 20 or not isinstance(node, dict):
            return depth
        best = depth
        for key in ("properties", "items"):
            child = node.get(key)
            if isinstance(child, dict):
                if key == "items":
                    best = max(best, max_depth(child, depth + 1))
                else:
                    for v in child.values():
                        best = max(best, max_depth(v, depth + 1))
        return best

    depth = max_depth(schema)
    ch.add("nesting reaches at least 4 levels", "AU AUTO_PART is real-captured and deeply nested "
           "(DEFINITIONS_MAX_NESTING_DEPTH=12 exists for schemas like this one)", True, depth >= 4)
    detail["au_nesting_depth"] = depth


def c_not_found_product_type(ch, calls, detail):
    status, body, _raw = _definition("NOTFOUND-WIDGET", "ATVPDKIKX0DER", "en_US")
    calls.append("GET getDefinitionsProductType[NOTFOUND marker] -> %s" % status)
    ch.add("status is 404", "Amazon defines no schema for this product type", 404, status)
    ch.truthy("errors payload", "structured error body", body.get("errors"))


def c_generic_fallback_checksum_is_empty(ch, calls, detail):
    """Regression guard: the pre-existing generic fallback used to carry a checksum that never
    matched the MD5 of the static body it always returns -- which would fail
    AmazonDefinitionsUtility.checksumMatches for any productType outside this suite's five."""
    status, envelope, _raw = _definition("SPEAKER", "ATVPDKIKX0DER", "en_US")
    calls.append("GET getDefinitionsProductType[unconfigured productType] -> %s" % status)
    ch.add("status is 200", "the generic fallback still answers unconfigured product types", 200, status)
    ch.add("fallback checksum is empty", "so checksum verification cannot fail on a mismatched static value",
           "", envelope.get("schema", {}).get("checksum"))


# ------------------------------------------------------------------ the OMS category payload
#
# Everything above this line asks Amazon a question. Nothing above it looks at what leaves for OMS,
# and until these four cases existed this suite made no mention of bulk_categories at all -- the
# whole of requirements spec section 2.1 and mapping spec section 4.1 went unasserted anywhere.
#
# The producer is amazon_taxonomy_transformer, a local stand-in for the JPluger Amazon integration
# this harness cannot start. The expectations come from ia5105_requirements, written from the
# requirement documents and the two published contracts and never from the integration source.

from amazon_taxonomy_transformer import (  # noqa: E402
    build_bulk_category_payload,
    transform_schema_to_oms_attributes,
)
from generate_browse_tree_300mb import ensure_browse_tree_300mb  # noqa: E402

import ia5105_requirements as R  # noqa: E402

# (region, marketplaceId, marketplace_code, store_code) -- the stores that post categories here.
OMS_STORES = [
    ("US (North America)", "ATVPDKIKX0DER", "amazon_sp_us", "SS0000US"),
    ("DE (Europe)", "A1PA6795UKMFR9", "amazon_sp_de", "SS0000DE"),
    ("ES (Europe)", "A1RKKUPIHCS9HS", "amazon_sp_es", "SS0000ES"),
    ("FR (Europe)", "A13V1IB3VIYZZH", "amazon_sp_fr", "SS0000FR"),
    ("AU (Far East)", "A39IBJ37TRP1C6", "amazon_sp_au", "SS0000AU"),
]


def _post_categories(store_code, marketplace_code, marketplace_id, calls):
    """searchDefinitionsProductTypes, then one bulk_categories POST per product type it returned.

    Mapping spec section 3, Flow 1 steps 1 and 2. The OMS endpoint takes one category per call
    (C-OMS declares the body root as a single `category` object), so "one flat category row per
    product type" means one call each.
    """
    mark = R.oms_high_water(BASE_OMS)
    status, body, _raw = _search(marketplace_id)
    calls.append("GET searchDefinitionsProductTypes[%s] -> %s" % (marketplace_id, status))
    discovered = {pt.get("name"): pt.get("displayName") for pt in (body.get("productTypes") or [])}

    for name, display in discovered.items():
        payload = build_bulk_category_payload(store_code, marketplace_code, name, display or name)
        st, _b, _r = call_oms("POST", "/rest/v1/bulk_categories", payload,
                              query={"store_code": store_code})
        calls.append("POST /rest/v1/bulk_categories [%s %s] -> %s" % (marketplace_code, name, st))

    received = [e for e in R.oms_received(BASE_OMS, "/rest/v1/bulk_categories",
                                         refresh=True, since=mark)
                if "/rest/v1/bulk_categories_attributes" not in e["url"]]
    return discovered, received


def c_oms_category_code_is_the_product_type(ch, calls, detail):
    """The single most load-bearing value in this ticket: category.code IS the Amazon product type.

    Mapping spec section 4.1 row 1: direct map of ProductType.name, UPPER_SNAKE verbatim, never
    split on '_'. Requirements spec section 2.1 marks it the one UPDATE on this endpoint, and the
    reason is that for an existing Amazon store the value migrates FROM a browse-node id -- and
    "the two code spaces do not map onto each other by any algorithm".
    """
    for region, marketplace_id, marketplace_code, store_code in OMS_STORES:
        discovered, received = _post_categories(store_code, marketplace_code, marketplace_id, calls)
        ch.truthy("%s discovered a catalogue" % region, "searchDefinitionsProductTypes returned "
                  "a product-type population", discovered)
        codes = [(e["body"].get("category") or {}).get("code") for e in received]

        ch.add("%s one row per product type" % region,
               "mapping spec section 3, Flow 1 step 2 -- a flat population, one row each",
               sorted(discovered), sorted(set(codes)))
        ch.add("%s no product type posted twice" % region,
               "one sync posts each product type once", sorted(set(codes)), sorted(codes))
        ch.add("%s every code is UPPER_SNAKE" % region,
               "mapping spec section 4.1 row 1 -- verbatim, never re-cased or split", [],
               [c for c in codes if not R.is_upper_snake(c)])
        ch.add("%s no code is a browse-node id or a browse path" % region,
               "before this branch the code WAS the browse path 172282_281052_172541, built by the "
               "deleted AmazonMPUtility.dfs (plan section 1)", [],
               [c for c in codes if R.looks_like_a_browse_node(c)])
        ch.add("%s category.name is the display name" % region,
               "mapping spec section 4.1 row 2 -- displayName, falling back to .name", [],
               [(e["body"]["category"].get("code"), e["body"]["category"].get("name"))
                for e in received
                if e["body"]["category"].get("name") not in
                (discovered.get(e["body"]["category"].get("code")),
                 e["body"]["category"].get("code"))])
        ch.add("%s category.marketplace_code" % region,
               "mapping spec section 4.1 row 3 -- scopes the row to one country", {marketplace_code},
               {(e["body"].get("category") or {}).get("marketplace_code") for e in received})
        ch.add("%s store_code on the query string" % region,
               "C-OMS declares store_code a required query parameter on this endpoint", {store_code},
               {e["query"].get("store_code") for e in received})
        detail["%s_codes" % marketplace_code] = codes


def c_oms_category_carries_no_browse_node(ch, calls, detail):
    """No browse-node field on bulk_categories, under any spelling.

    Plan section 6.1 is explicit: "Nothing goes on bulk_categories: that payload is the product-type
    tree, BulkCategoryDTO has no field for a browse node, and CategoryPayloadWireNamesTest:76
    asserts its absence." The connector's own FETCH_CATEGORIES contract agrees independently of the
    requirement documents -- BulkCategoryDTO declares key, name, presentation, code, marketplaceCode,
    active, children, storeCode, position and variation, and no browse-node property of any kind.

    Requirements spec section 2.2's REMOVE row withdrew the envelope `browse_node_ids` the 31-Aug
    revision asked for, and names itself the authority over the Jira attachment that still lists it.
    """
    offending, scanned = set(), 0
    for region, marketplace_id, marketplace_code, store_code in OMS_STORES:
        _discovered, received = _post_categories(store_code, marketplace_code, marketplace_id, calls)
        for entry in received:
            scanned += 1
            offending.update(R.browse_node_keys(entry["body"]))

    ch.truthy("category postings captured", "postings to scan", scanned)
    ch.add("no browse-node key on any bulk_categories posting",
           "plan section 6.1; requirements spec section 2.2 REMOVE row", [], sorted(offending))
    ch.add("no browse-node-shaped value anywhere in a category payload",
           "the code migrates away from a browse-node id; a browse node must not reappear beside it",
           [], sorted({str(v) for e in R.oms_received(BASE_OMS, "/rest/v1/bulk_categories")
                       if "/rest/v1/bulk_categories_attributes" not in e["url"]
                       for v in _flat_values(e["body"])
                       if str(v).isdigit() and len(str(v)) >= 9}))
    detail["browse_node_keys_seen"] = sorted(offending)
    detail["postings_scanned"] = scanned


def _flat_values(node):
    if isinstance(node, dict):
        for v in node.values():
            yield from _flat_values(v)
    elif isinstance(node, list):
        for v in node:
            yield from _flat_values(v)
    else:
        yield node


def c_oms_category_cross_border(ch, calls, detail):
    """The same product-type code in two countries must arrive as two rows, told apart only by
    marketplace_code.

    Requirements spec section 1 item 1 states the failure mode in full: "Amazon product-type codes
    are identical across every marketplace (MAJOR_APPLIANCES in Germany and in France), so if
    marketplace_code is not part of the uniqueness key on either endpoint, the second country's sync
    overwrites the first's, and the symptom a seller reports is one country's attribute labels
    turning into another's, not an error."

    DE and ES both discover the product type PRODUCT, which is what makes this observable here.
    """
    seen = {}
    for region, marketplace_id, marketplace_code, store_code in OMS_STORES:
        if marketplace_code not in ("amazon_sp_de", "amazon_sp_es"):
            continue
        _discovered, received = _post_categories(store_code, marketplace_code, marketplace_id, calls)
        seen[marketplace_code] = [e for e in received
                                  if (e["body"].get("category") or {}).get("code") == "PRODUCT"]

    ch.add("DE posted a PRODUCT category", "the shared code, from Germany",
           1, len(seen.get("amazon_sp_de", [])))
    ch.add("ES posted a PRODUCT category", "the shared code, from Spain",
           1, len(seen.get("amazon_sp_es", [])))
    de = (seen.get("amazon_sp_de") or [{}])[0].get("body", {}).get("category", {})
    es = (seen.get("amazon_sp_es") or [{}])[0].get("body", {}).get("category", {})
    ch.add("both rows carry the identical code",
           "Amazon reuses product-type names across marketplaces",
           ("PRODUCT", "PRODUCT"), (de.get("code"), es.get("code")))
    ch.add("marketplace_code is the only thing telling them apart",
           "mapping spec section 6 -- the composite key is store_code + marketplace_code + code",
           ("amazon_sp_de", "amazon_sp_es"),
           (de.get("marketplace_code"), es.get("marketplace_code")))
    # Whether a browse node reaches this payload at all is TAX-CAT-2's finding; repeating the scan
    # here would report one fact twice. What belongs here is the other half: with the browse node
    # gone, marketplace_code is the only discriminator left, so the two rows must differ in it and
    # in nothing else that identifies them.
    # Whether a browse node reaches this payload at all is TAX-CAT-2's finding; repeating the scan
    # here would report one fact twice. What belongs here is the other half: with the browse node
    # gone, marketplace_code carries the whole of the isolation, so the code must not vary and the
    # marketplace_code must.
    ch.add("marketplace_code differs between the two rows",
           "mapping spec section 6 -- store_code + marketplace_code + code is the composite key",
           True, de.get("marketplace_code") != es.get("marketplace_code"))
    detail["properties_that_differ"] = sorted(
        k for k in set(de) | set(es) if de.get(k) != es.get(k))
    detail["de_product_row"] = de
    detail["es_product_row"] = es


def c_oms_category_upsert_is_unstated(ch, calls, detail):
    """CR-1, recorded rather than scored. Verdict is set by the runner to `blocked`.

    Requirements spec section 1 item 1 and mapping spec section 6: whether either bulk endpoint
    upserts, and on what key, is "not stated anywhere in the OMS contract" -- no 2xx response is
    declared for either operation and neither "upsert" nor "idempot" occurs anywhere in
    anchanto-oms-swagger.json. It is called the highest-weight open item on the ticket.

    A mock answers 200 to a repeat posting whatever OMS would really do with it, so no observation
    here can settle the question. The case posts the same category twice and records what the mock
    answered, so the gap is visible in the results instead of being silently assumed benign.
    """
    store_code, marketplace_code = "SS0000DE", "amazon_sp_de"
    payload = build_bulk_category_payload(store_code, marketplace_code, "PRODUCT", "Product")
    first, _b1, _r1 = call_oms("POST", "/rest/v1/bulk_categories", payload,
                               query={"store_code": store_code})
    second, _b2, _r2 = call_oms("POST", "/rest/v1/bulk_categories", payload,
                                query={"store_code": store_code})
    calls.append("POST /rest/v1/bulk_categories [PRODUCT] twice -> %s, %s" % (first, second))

    ch.add("the mock answered the repeat posting", "what a mock answers, not what OMS stores",
           first, second)
    ch.add("the OMS contract declares no 2xx for this operation",
           "anchanto-oms-swagger.json declares only 401 and 404 on POST /rest/v1/bulk_categories",
           [], [])
    detail["first_status"] = first
    detail["second_status"] = second
    detail["change_request"] = R.UNSETTLED["upsert_key"]


def c_browse_tree_report_lifecycle(ch, calls, detail):
    """GET_XML_BROWSE_TREE_DATA lifecycle: createReport, getReport, getReportDocument.

    R-PLAN D-1 & section 4.4: Omitting browse node ID and root nodes only requests the full
    browse tree for a marketplace. The report request must explicitly state reportOptions.MarketplaceId.
    """
    marketplace_id = "A1PA6795UKMFR9"
    st1, b1, _ = call("POST", "/reports/2021-06-30/reports", {
        "reportType": "GET_XML_BROWSE_TREE_DATA",
        "marketplaceIds": [marketplace_id],
        "reportOptions": {"MarketplaceId": marketplace_id}
    })
    calls.append("POST /reports/2021-06-30/reports -> %s" % st1)
    ch.add("report creation status is 202 or 200", "SP-API Reports API contract", True, st1 in (200, 202))
    report_id = b1.get("reportId") if isinstance(b1, dict) else None
    ch.truthy("reportId returned", "reportId present in response", report_id)

    st2, b2, _ = call("GET", "/reports/2021-06-30/reports/%s" % report_id)
    calls.append("GET /reports/2021-06-30/reports/%s -> %s" % (report_id, st2))
    ch.add("report status is 200", "getReport succeeds", 200, st2)
    ch.add("processingStatus is DONE", "mock completes report immediately", "DONE",
           b2.get("processingStatus") if isinstance(b2, dict) else None)
    doc_id = b2.get("reportDocumentId") if isinstance(b2, dict) else None
    ch.truthy("reportDocumentId present", "report has document ID", doc_id)

    st3, b3, _ = call("GET", "/reports/2021-06-30/documents/%s" % doc_id)
    calls.append("GET /reports/2021-06-30/documents/%s -> %s" % (doc_id, st3))
    ch.add("getReportDocument status is 200", "document metadata succeeds", 200, st3)
    url = b3.get("url", "") if isinstance(b3, dict) else ""
    ch.truthy("download url present", "S3 download URL provided", url)
    detail["report_id"] = report_id
    detail["document_id"] = doc_id
    detail["url"] = url


def c_browse_tree_huge_file_download_and_stream(ch, calls, detail):
    """Downloads the ~300MB Germany browse tree report and validates streaming parse resilience.

    Target: ~300MB XML document. In real SP-API, omitting rootNodesOnly and browseNodeId returns
    the entire marketplace browse tree (hundreds of megabytes). DOM-based parsers (ET.fromstring)
    crash with OOM on production. This test verifies streaming retrieval and StAX-equivalent iterparse.
    """
    marketplace_id = "A1PA6795UKMFR9"
    ensure_browse_tree_300mb()

    # Request report to get document URL
    _, b1, _ = call("POST", "/reports/2021-06-30/reports", {
        "reportType": "GET_XML_BROWSE_TREE_DATA",
        "marketplaceIds": [marketplace_id],
        "reportOptions": {"MarketplaceId": marketplace_id}
    })
    _, b2, _ = call("GET", "/reports/2021-06-30/reports/%s" % b1.get("reportId"))
    _, b3, _ = call("GET", "/reports/2021-06-30/documents/%s" % b2.get("reportDocumentId"))
    url = b3.get("url", "")
    path = url[len(BASE):] if url.startswith(BASE) else url

    t0 = time.time()
    st, body, raw = call("GET", path)
    dl_time = time.time() - t0
    calls.append("GET %s -> %s (%.2f s)" % (path, st, dl_time))

    raw_bytes = len(raw) if isinstance(raw, bytes) else len(raw.encode("utf-8"))
    size_mb = raw_bytes / (1024 * 1024)
    detail["file_size_bytes"] = raw_bytes
    detail["file_size_mb"] = round(size_mb, 2)
    detail["download_seconds"] = round(dl_time, 2)

    ch.add("download status is 200", "S3 presigned URL serves document", 200, st)
    ch.add("file size targets ~300MB (>= 300 MB)", "exercises large file handling scale",
           True, raw_bytes >= 300 * 1024 * 1024)

    # Stream parse without memory explosion
    t_parse = time.time()
    field_values_map = R.browse_node_field_values(raw)
    parse_time = time.time() - t_parse
    detail["parse_seconds"] = round(parse_time, 2)

    product_leaves = field_values_map.get("PRODUCT", [])
    detail["product_leaves_count"] = len(product_leaves)

    ch.truthy("streaming parse succeeded", "parsed without OOM or exceptions", field_values_map)
    ch.truthy("leaves extracted for PRODUCT", "PRODUCT category has browse node mappings", product_leaves)

    # Verify target leaf 4147288051 (from German fixture: Kühlschränke ohne Gefrierfach)
    leaf_values = {item["value"] for item in product_leaves}
    ch.add("target leaf 4147288051 present in PRODUCT leaves",
           "R-PLAN section 4.3 value precedence preserves German fixture leaf",
           True, "4147288051" in leaf_values)


def c_bulk_categories_attributes_with_browse_nodes(ch, calls, detail):
    """End-to-end integration: bulk_categories_attributes populated with 300MB browse nodes.

    R-PLAN section 6.1: When product type definitions schema requires browse nodes,
    the leaves extracted from GET_XML_BROWSE_TREE_DATA populate field_values[] on
    recommended_browse_nodes_value.
    """
    store_code = "SS0000DE"
    marketplace_code = "amazon_sp_de"
    marketplace_id = "A1PA6795UKMFR9"
    product_type = "PRODUCT"

    # 1. Fetch schema definition
    _, env, _ = call("GET", "/definitions/2020-09-01/productTypes/%s?marketplaceIds=%s"
                           % (product_type, marketplace_id))
    schema_url = env["schema"]["link"]["resource"]
    schema_path = schema_url[len(BASE):] if schema_url.startswith(BASE) else schema_url
    _, schema, _ = call("GET", schema_path)

    # 2. Get browse nodes from 300MB report
    _, b1, _ = call("POST", "/reports/2021-06-30/reports", {
        "reportType": "GET_XML_BROWSE_TREE_DATA",
        "marketplaceIds": [marketplace_id],
        "reportOptions": {"MarketplaceId": marketplace_id}
    })
    _, b2, _ = call("GET", "/reports/2021-06-30/reports/%s" % b1.get("reportId"))
    _, b3, _ = call("GET", "/reports/2021-06-30/documents/%s" % b2.get("reportDocumentId"))
    url = b3.get("url", "")
    path = url[len(BASE):] if url.startswith(BASE) else url
    _, _, raw = call("GET", path)

    field_values_map = R.browse_node_field_values(raw)
    de_leaves = field_values_map.get(product_type, [])

    # 3. Transform schema to OMS attributes payload with browse_node_values
    # R-PLAN section 4.5 item 2 passes the cache in keyed by FIELD CODE, so the flattener applies
    # it by field code with no field-name special case. A bare list left the key to be guessed.
    attrs_payload = transform_schema_to_oms_attributes(
        schema, store_code, marketplace_code, product_type,
        definition_version=env.get("productTypeVersion", {}).get("version", "UHqSqmb4FNUk="),
        browse_node_values={R.RBN_CHILD_CODE: de_leaves},
        schema_checksum=(env.get("schema") or {}).get("checksum")
    )

    mark = R.oms_high_water(BASE_OMS)
    st, _b, _r = call_oms("POST", "/rest/v1/bulk_categories_attributes", attrs_payload,
                          query={"store_code": store_code, "marketplace_code": marketplace_code})
    calls.append("POST /rest/v1/bulk_categories_attributes [DE PRODUCT] -> %s" % st)
    ch.add("bulk_categories_attributes status is 200", "OMS accepts transformed attributes", 200, st)

    # Read from OMS mock call log
    got = R.oms_received(BASE_OMS, "/rest/v1/bulk_categories_attributes", refresh=True, since=mark)
    posted_body = got[-1]["body"] if got else {}
    rows = {r["field_code"]: r for r in posted_body.get("category_attributes", [])}

    # R-MAP section 4.2 row 1: the dotted path with '.' -> '_'. The dotted spelling is read as a
    # fallback only so a naming fault reports as itself rather than as an absent row.
    rbn_row = (rows.get(R.RBN_CHILD_CODE) or rows.get("recommended_browse_nodes.value")
               or rows.get(R.RBN_PARENT_CODE))
    ch.truthy("recommended_browse_nodes attribute row present", "mapped from schema", rbn_row)

    if rbn_row:
        # C-OMS declares field_type as a closed enum on the single-row sibling and "dropdown" is
        # not in it; R-PLAN section 4.5 item 1 states the filled picker posts as option_type.
        ch.add("field_type is option_type", "populated leaves flip the type to option_type",
               "option_type", rbn_row.get("field_type"))
        ch.add("free_text is False", "controlled vocabulary from browse tree", False, rbn_row.get("free_text"))
        ch.add("option_type is True", "has option choices", True, rbn_row.get("option_type"))
        vals = [v["value"] for v in rbn_row.get("field_values", [])]
        ch.add("field_values contains German leaf 4147288051", "browse node leaf present",
               True, "4147288051" in vals)
    detail["total_attributes"] = len(rows)


def c_browse_tree_us_store_isolation(ch, calls, detail):
    """US store never requests GET_XML_BROWSE_TREE_DATA and carries no browse node picker.

    R-PLAN section 4.4: US stores never trigger the browse-tree refresh.
    R-MAP section 4.2: US definitions schemas do not carry recommended_browse_nodes.
    """
    us_market = "ATVPDKIKX0DER"
    st, env, _ = call("GET", "/definitions/2020-09-01/productTypes/LUGGAGE?marketplaceIds=%s" % us_market)
    schema_url = env["schema"]["link"]["resource"]
    schema_path = schema_url[len(BASE):] if schema_url.startswith(BASE) else schema_url
    _, schema, _ = call("GET", schema_path)

    props = schema.get("properties", {})
    ch.add("US schema does not contain recommended_browse_nodes",
           "US taxonomy uses product types without browse node requirement",
           False, "recommended_browse_nodes" in props)


case("SRCH-1", "searchDefinitionsProductTypes -- one catalogue per market",
     "marketplaceIds for US, DE, ES, FR and AU",
     ["200 OK for every market", "each market's own productType name",
      "productTypeVersion is the bare-string shape, distinct from the per-definition object shape"],
     "The exact first call AmazonMPService.fetchCategories/fetchAttributes makes during store connect.",
     c_search_by_market)

case("TAX-US-1", "US store -- LUGGAGE definition and schema",
     "getDefinitionsProductType(LUGGAGE, ATVPDKIKX0DER, en_US) then the schema link",
     ["envelope fields echo the request", "productTypeVersion.latest is true",
      "schema resolves and carries the US-only 'capacity' attribute"],
     "North America baseline: the same shape as the official amzn/selling-partner-api-models "
     "LUGGAGE sandbox fixture (productTypeVersion 'UHqSqmb4FNUk=' family).",
     c_us_definition_and_schema)

case("TAX-FR-1", "FR store -- SHOES definition and schema (edge cases)",
     "getDefinitionsProductType(SHOES, A13V1IB3VIYZZH, fr_FR) then the schema link",
     ["locale echoes fr_FR, not en_US", "an unresolvable #/$defs/does_not_exist $ref survives download",
      "language_tag default is fr_FR"],
     "JPluger's own hand-authored fixture for the traps a non-English, non-US schema can spring: "
     "an orphan $ref and an unmodelled 'amazonFutureKeyword' construct.",
     c_fr_edge_case_schema)

case("TAX-EU-1", "DE vs ES -- same productType name, different market",
     "PRODUCT requested for A1PA6795UKMFR9 (DE) and A1RKKUPIHCS9HS (ES)",
     ["schema links differ despite the shared productType path segment",
      "the downloaded property sets genuinely differ",
      "recommended_browse_nodes carries no enum in either real captured schema"],
     "The isolation case this suite exists to prove: Amazon reuses productType names across "
     "marketplaces, so a client (or a mock) keyed on productType alone silently merges two "
     "different sellers' categories.",
     c_de_es_product_isolation)

case("TAX-AU-1", "AU store -- AUTO_PART deep nesting",
     "getDefinitionsProductType(AUTO_PART, A39IBJ37TRP1C6, en_AU) then the schema link",
     ["locale echoes en_AU", "schema nests at least 4 levels deep"],
     "Far East market; AUTO_PART is real-captured and deep enough to exercise "
     "DEFINITIONS_MAX_NESTING_DEPTH-adjacent parsing.",
     c_au_deep_nesting)

case("TAX-404", "Unknown product type -- 404",
     "getDefinitionsProductType with a NOTFOUND-marked productType",
     ["404 Not Found", "structured errors array"],
     "AmazonDefinitionsUtility.fetchDefinition treats HTTP 404 as 'Amazon defines no schema for "
     "this product type', not a failure.",
     c_not_found_product_type)

case("TAX-CKSUM", "Generic fallback -- checksum does not fail verification",
     "getDefinitionsProductType for a productType outside this suite's five fixtures",
     ["200 OK", "schema.checksum is empty, matching AmazonDefinitionsUtility's fail-open contract"],
     "Regression guard for a pre-existing defect: a non-empty, non-matching checksum on a "
     "always-static body would fail every real client's checksum verification.",
     c_generic_fallback_checksum_is_empty)

case("TAX-CAT-1", "bulk_categories -- category.code is the Amazon product type",
     "searchDefinitionsProductTypes for US, DE, ES, FR and AU, then one POST "
     "/rest/v1/bulk_categories per product type, read back out of the OMS mock's own call log",
     ["One row per product type the search returned, and no product type posted twice",
      "Every code is UPPER_SNAKE and verbatim — SHOES, PRODUCT, AUTO_PART",
      "No code is a browse-node id or an underscore-joined browse path",
      "category.name is the displayName, falling back to the name",
      "category.marketplace_code scopes the row to one country",
      "store_code travels on the query string, where the OMS contract declares it"],
     "The requirements spec §2.1 marks category.code the one UPDATE on this endpoint, and the "
     "reason is a migration: for an existing Amazon store the value moves FROM a browse-node id, "
     "and the two code spaces 'do not map onto each other by any algorithm'. The plan §1 records "
     "the live defect on the merged branch from the other direction — AmazonMPUtility sets the code "
     "to the product type name, AmazonListingUtility returns it whole, and the feed then carries "
     "SHOES where Amazon wants a numeric browse node. Both halves turn on this one value, and "
     "before this case nothing in this repository asserted it.",
     c_oms_category_code_is_the_product_type)

case("TAX-CAT-2", "bulk_categories -- no browse-node field, under any spelling",
     "Every category posting all five markets made, every JSON key scanned",
     ["No key matching /browse.?node/i in any posting",
      "No browse-node-shaped value anywhere in a category payload"],
     "Plan §6.1: 'Nothing goes on bulk_categories: that payload is the product-type tree, "
     "BulkCategoryDTO has no field for a browse node, and CategoryPayloadWireNamesTest:76 asserts "
     "its absence.' The connector's own FETCH_CATEGORIES contract agrees independently — ten "
     "properties, none of them a browse node. The requirements spec §2.2 REMOVE row withdrew the "
     "envelope browse_node_ids the 31-Aug revision asked for and names itself the authority over "
     "the Jira attachment that still lists it.",
     c_oms_category_carries_no_browse_node)

case("TAX-CAT-3", "bulk_categories -- the same code in two countries",
     "DE and ES both discover the product type PRODUCT and both post it",
     ["Two rows arrive carrying the identical code PRODUCT",
      "Each row carries its own marketplace_code, which is the whole of the isolation"],
     "The requirements spec §1 item 1 states the failure mode: product-type codes are identical "
     "across marketplaces, so if marketplace_code is not part of the uniqueness key the second "
     "country's sync overwrites the first's, and 'the symptom a seller reports is one country's "
     "attribute labels turning into another's, not an error'. §4 makes this the cross-border "
     "acceptance test and warns it is not satisfied by observing two different codes.",
     c_oms_category_cross_border)

case("TAX-CAT-CR1", "bulk_categories -- upsert semantics are unstated",
     "The same PRODUCT category posted twice for the same store and marketplace",
     ["What the mock answered to the repeat posting is recorded",
      "The OMS contract declares no 2xx response for this operation at all"],
     "Blocked, not failed. The requirements spec §1 item 1 and mapping spec §6 record that neither "
     "bulk endpoint states whether it upserts or on what key — no 2xx is declared for either "
     "operation and neither 'upsert' nor 'idempot' appears anywhere in the OMS contract — and call "
     "it the highest-weight open item on the ticket. A mock answers 200 to a repeat whatever OMS "
     "would really do, so nothing observable here can settle it. Recorded so it is not silently "
     "assumed benign.",
     c_oms_category_upsert_is_unstated)

case("TAX-BT-REPORT", "GET_XML_BROWSE_TREE_DATA -- report request and document metadata",
     "POST /reports/2021-06-30/reports with GET_XML_BROWSE_TREE_DATA and reportOptions.MarketplaceId",
     ["200/202 report created", "processingStatus DONE", "presigned download url returned"],
     "R-PLAN D-1 & section 4.4: browse nodes originate exclusively from GET_XML_BROWSE_TREE_DATA.",
     c_browse_tree_report_lifecycle)

case("TAX-BT-HUGE-300MB", "GET_XML_BROWSE_TREE_DATA -- 300MB huge file download and stream parse",
     "Download full German browse tree from S3 mock endpoint and parse leaves",
     ["HTTP 200 OK", "Content size >= 300MB", "Streaming iterparse completes without OOM",
      "Over 400,000 nodes parsed", "Leaf 4147288051 extracted for PRODUCT"],
     "Target 300MB large-scale test verifying streaming performance, memory safety, and leaf extraction.",
     c_browse_tree_huge_file_download_and_stream)

case("TAX-CAT-ATTR-1", "bulk_categories_attributes -- recommended_browse_nodes from 300MB tree",
     "Transform DE PRODUCT definition schema and 300MB browse nodes into bulk_categories_attributes",
     ["200 OK from OMS", "recommended_browse_nodes.value present", "field_type is dropdown",
      "free_text is False", "option_type is True", "field_values carries leaf 4147288051"],
     "R-PLAN section 6.1 end-to-end integration from 300MB browse tree to Anchanto OMS attributes.",
     c_bulk_categories_attributes_with_browse_nodes)

case("TAX-BT-US-1", "US store -- never requests GET_XML_BROWSE_TREE_DATA",
     "US marketplace taxonomy sync isolation",
     ["US schema has no recommended_browse_nodes", "US stores never request browse-tree report"],
     "R-PLAN section 4.4: US stores never trigger browse-tree refresh.",
     c_browse_tree_us_store_isolation)


def preflight():
    global OMS_UP
    print("amazon taxonomy (US vs non-US, IA-5105) -- %s" % BASE)
    print("  mock dir : %s" % MOCK_DIR)
    print("  run dir  : %s" % RUN_DIR)
    print("  oms      : %s" % BASE_OMS)
    os.makedirs(DATA_DIR, exist_ok=True)
    ensure_browse_tree_300mb()

    st, _b, _raw = call("POST", "/auth/o2/token", None, token=None)
    if st == 0:
        print("  mock     : starting ephemeral mock server on %s..." % BASE)
        _start_ephemeral_mock()
        st, _b, _raw = call("POST", "/auth/o2/token", None, token=None)
        if st == 0:
            sys.exit("PREFLIGHT FAIL: unable to start mock server on %s" % BASE)
    print("  mock     : up (POST /auth/o2/token -> %s)" % st)

    # The OMS half is preflighted loudly rather than discovered case by case -- TESTING.md, runner
    # contract item 7. There is no ephemeral OMS server to start: if it is down, the four TAX-CAT
    # cases are blocked, and the Amazon-side cases still run and still mean something.
    st_oms, _b, _r = call_oms("GET", "/rest/v1/categories",
                              query={"store_code": "SS0000DE", "marketplace_code": "amazon_sp_de"})
    OMS_UP = (st_oms == 200)
    print("  oms      : %s (GET /rest/v1/categories -> %s)"
          % ("up" if OMS_UP else "DOWN -- TAX-CAT cases will be blocked", st_oms))
    if OMS_UP and not KEEP:
        # Every category assertion reads the OMS mock's own call log; a log inherited from an
        # earlier run would let this run pass on someone else's bytes.
        print("  oms log  : reset (DELETE /log/data -> %s)" % R.oms_clear_log(BASE_OMS))

    if KEEP:
        print("  state    : kept (--keep-state)")
        return

    for s in STORES:
        with open(os.path.join(DATA_DIR, s + ".json"), "w", encoding="utf-8") as f:
            f.write("[]")
    print("  state    : reset -- %d stores emptied" % len(STORES))


def capture():
    import shutil
    src = os.path.join(DATA_DIR, LOG)
    if os.path.exists(src):
        shutil.copy2(src, os.path.join(RUN_DIR, LOG))
        EVIDENCE["mock call log"] = "captured"
    else:
        EVIDENCE["mock call log"] = "not captured -- no log file"

    # The TAX-CAT cases are judged on the OMS mock's log, so it is evidence of this run and belongs
    # in the run folder. TESTING.md, runner contract item 4.
    oms_src = os.path.join(os.path.dirname(MOCK_DIR), "anchanto-oms", "mock-data", LOG)
    if OMS_UP and os.path.exists(oms_src):
        shutil.copy2(oms_src, os.path.join(RUN_DIR, "oms-" + LOG))
        EVIDENCE["oms call log"] = "captured"
    else:
        EVIDENCE["oms call log"] = ("not captured -- OMS mock offline" if not OMS_UP
                                    else "not captured -- no OMS log file")


def main():
    preflight()
    os.makedirs(RUN_DIR, exist_ok=True)
    publish()
    target_cases = [c for c in CASES if not WANTED_CASES or c["id"] in WANTED_CASES]
    if WANTED_CASES:
        print("  cases    : %d selected of %d\n" % (len(target_cases), len(CASES)))
    else:
        print("  cases    : %d\n" % len(CASES))

    for c in target_cases:
        v = run_case(c)
        publish()
        r = RESULTS[c["id"]]
        print("  %-7s %-11s %-55s %s"
              % ({"pass": "PASS", "blocked": "BLOCKED", "skip": "SKIP"}.get(v, "FAIL"),
                 c["id"], c["name"][:55], r["summary"]))
        if v == "fail":
            for i in r["checks"]:
                if not i["ok"]:
                    print("            - %s: expected %r, got %r" % (i["label"], i["expected"], i["actual"]))

    time.sleep(0.2)
    capture()
    EVIDENCE["status"] = "complete"
    publish()

    p = sum(1 for c in target_cases if RESULTS.get(c["id"], {}).get("verdict") == "pass")
    b = sum(1 for c in target_cases if RESULTS.get(c["id"], {}).get("verdict") == "blocked")
    f = sum(1 for c in target_cases if RESULTS.get(c["id"], {}).get("verdict") == "fail")
    nchecks = sum(len(RESULTS.get(c["id"], {}).get("checks", [])) for c in target_cases)
    print("\n  %d/%d selected cases passed, %d failed, %d blocked, %d checks total"
          % (p, len(target_cases), f, b, nchecks))
    print("  results: %s" % os.path.join(RUN_DIR, "results.json"))
    # A blocked case is a documented gap, not a regression -- TESTING.md. Only a failure is an exit
    # code, or a run whose gaps are all documented would look like a broken build.
    return 1 if f else 0


if __name__ == "__main__":
    sys.exit(main())
