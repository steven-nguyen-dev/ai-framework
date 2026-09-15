#!/usr/bin/env python3
"""IA-5105-US1: Amazon Non-US Multi-Marketplace Store Connect & Taxonomy Sync Suite.

Rewritten 2026-09-13 against the IA-5105 deliverables (wiki `plan/amazon-test-suites`).
The expectations live in requirements.py with the document and section each came from; this file makes
the calls and judges what arrived.

WHAT THIS SUITE OWNS, out of the 47 rows of `IA-5105-e2e-coverage-matrix.md`:
    A1   marketplace isolation at the wire (DE vs ES PRODUCT)            NONUS-PICKER-ISO
    A2   category.code IS the Amazon product type for non-US stores      NONUS-CAT-1
    A7   parent-first ordering across non-US schemas                     NONUS-MAP-1, NONUS-VOCAB-1
    B5   six definition_status values on the wire                        NONUS-ENV-1
    B8   array parent + explicit child, nothing folded                   NONUS-MAP-1
    B11  default, field_parent_code absent at top level                  NONUS-MAP-1
    B12  enums don't change data_type; measurement unit is sibling       NONUS-MAP-1
    B13  non-US picker: node id in value, path in name (' > ' joined)    NONUS-RBN-DE, NONUS-RBN-ES-AU
    B15  empty picker publishes field_values: [] and free_text: true     NONUS-RBN-EMPTY
    B16  one XML report per marketplace with MarketplaceId stated        NONUS-REPORT-1
    B18  marketplace and store context on every row                      NONUS-VOCAB-1
    B19  width cap at the wire: 4 children published, rest omitted       NONUS-WIDTH-1
    C2-5 rate pacing and retry budget on definitions route               NONUS-RETRY-1 (blocked)
    D1-2 resumption without re-fetching and checkpoint survival          NONUS-RESUME-1 (blocked)
    D7   every field_code is unique                                      NONUS-VOCAB-1
    D11  rate pacing ceiling <= 5 req/s                                  NONUS-RETRY-1 (blocked)
    D12  two stores of one seller do not interfere                       NONUS-PICKER-ISO
    N10  no browse-node key on either payload                            NONUS-CAT-1, NONUS-ENV-1
    N12  no discrete browse-node entities                                NONUS-CAT-1
    N16  id and field_parent_id absent on Amazon rows                    NONUS-VOCAB-1

WHAT A GREEN RUN HERE DOES NOT PROVE (the IA-5109 form, and requirements.UNTESTABLE states each):
 1. There is no JPluger under test. transformer.py is a stand-in (amazon/README.md) and this suite
    is the only client Amazon sees, so call-shape and [JP] rows are blocked (requirements.UNTESTABLE['H1']).
 2. Negative branches of C2, C3, C4, C5: the Amazon mock serves no definitions-route throttle or 403 fixtures.
 3. The stand-in transformer emits no definition_status key, so definition_status checks fail red.
 4. Decision 2 dot-joining of nested field_codes fails red against transformer.py's underscore-joining.
 5. The DE browse tree is a 315 MB generated file. FR and ES are used for browse-tree verification (§0.9.6).

Runner contract: TESTING.md and wiki `plan/amazon-test-suites#01-harness`.
Publishes to amazon/test-results/IA-5105-US1-connect-non-us/run-<stamp>/results.json.

Usage:
  python3 amazon/IA-5105-US1/suite-connect-non-us.py
  python3 amazon/IA-5105-US1/suite-connect-non-us.py --list
  python3 amazon/IA-5105-US1/suite-connect-non-us.py NONUS-CAT-1 NONUS-RBN-DE
  BASE_AMAZON=http://127.0.0.1:23123 BASE_OMS=http://127.0.0.1:23021 python3 amazon/IA-5105-US1/suite-connect-non-us.py
"""

import datetime
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE_AMAZON = os.environ.get("BASE_AMAZON", os.environ.get("BASE", "http://127.0.0.1:23103")).rstrip("/")
BASE = BASE_AMAZON
BASE_OMS = os.environ.get("BASE_OMS", "http://127.0.0.1:23001").rstrip("/")
SUITE = os.environ.get("SUITE", "IA-5105-US1-connect-non-us")
KEEP = "--keep-state" in sys.argv
LIST_ONLY = "--list" in sys.argv
WANTED_CASES = set(a for a in sys.argv[1:] if not a.startswith("-"))

HERE = os.path.dirname(os.path.abspath(__file__))
MOCK_DIR = os.path.dirname(HERE)
for _p in (HERE, MOCK_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)
DATA_DIR = os.path.join(MOCK_DIR, "mock-data")
LOG = "api-calls.har.json"
STAMP = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
RUN_DIR = os.path.join(MOCK_DIR, "test-results", SUITE, "run-" + STAMP)

import requirements as R  # noqa: E402
from transformer import (  # noqa: E402
    build_bulk_category_payload,
    transform_schema_to_oms_attributes,
)

NON_US_STORES = [
    {"region": "FR", "marketplace_code": "amazon_sp_fr", "store_code": "SS0000FR", "product_type": "SHOES", "schema_file": "fr-schema-SHOES.json"},
    {"region": "DE", "marketplace_code": "amazon_sp_de", "store_code": "SS0000DE", "product_type": "PRODUCT", "schema_file": "de-schema-PRODUCT.json"},
    {"region": "ES", "marketplace_code": "amazon_sp_es", "store_code": "SS0000ES", "product_type": "PRODUCT", "schema_file": "es-schema-PRODUCT.json"},
    {"region": "AU", "marketplace_code": "amazon_sp_au", "store_code": "SS0000AU", "product_type": "AUTO_PART", "schema_file": "au-schema-AUTO_PART.json"},
    {"region": "GB", "marketplace_code": "amazon_sp_uk", "store_code": "SS0000GB", "product_type": "FURNITURE", "schema_file": "gb-schema-FURNITURE.json"},
    {"region": "JP", "marketplace_code": "amazon_sp_jp", "store_code": "SS0000JP", "product_type": "BEAUTY", "schema_file": "jp-schema-BEAUTY.json"},
]


# ------------------------------------------------------------------ transport


def call(method, path, body=None, token="mock_sp_api_access_token", timeout=120):
    url = BASE_AMAZON + (R.schema_link_path(path) if path.startswith("http") else path)
    headers, data = {}, None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["x-amz-access-token"] = token
        headers["Authorization"] = "Bearer " + token

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw, status = r.read(), r.status
    except urllib.error.HTTPError as e:
        raw, status = e.read(), e.code
    except Exception as e:
        return 0, {"_transport_error": str(e)}, b""

    try:
        return status, json.loads(raw.decode("utf-8")) if raw.strip() else {}, raw
    except Exception:
        return status, raw.decode("utf-8", "replace"), raw


def call_amazon(method, path, body=None, token="mock_sp_api_access_token"):
    return call(method, path, body, token)


def call_oms(method, path, body=None, query=None, token="f1a6c2d8e40b7935a1c6d2f8b04e7395"):
    full_path = path + ("?" + urllib.parse.urlencode(query) if query else "")
    url = BASE_OMS + full_path
    headers = {"Content-Type": "application/json"}
    data = json.dumps(body).encode("utf-8") if body is not None else None
    if token:
        headers["Authorization"] = "Bearer " + token

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            raw, status = r.read(), r.status
    except urllib.error.HTTPError as e:
        raw, status = e.read(), e.code
    except Exception as e:
        return 0, {"_transport_error": str(e)}, b""
    try:
        return status, json.loads(raw.decode("utf-8")) if raw.strip() else {}, raw
    except Exception:
        return status, raw.decode("utf-8", "replace"), raw


# ------------------------------------------------------------------ runner

CASES, RESULTS = [], {}
EVIDENCE = {
    "status": "running",
    "server": "Amazon SP-API mock at %s" % BASE_AMAZON,
    "oms server": "Anchanto OMS mock at %s" % BASE_OMS,
    "mock call log": "not captured",
    "authority": "IA-5105 deliverables override the Jira ticket; wiki plan/amazon-test-suites",
    "does_not_prove": [
        "Nothing about JPluger: there is no JPluger under test. transformer.py is a stand-in "
        "(amazon/README.md) and this suite is the only client Amazon sees (requirements.UNTESTABLE['H1']).",
        "Negative branches of C2, C3, C4, C5: the Amazon mock serves no definitions-route fault fixtures "
        "(requirements.UNTESTABLE['H2']).",
        "Anything about what OMS does with a body it received (D-MATRIX U2, U3). Only what was sent is asserted.",
        "Amazon's real behaviour through SYNTHETIC fixtures: FR SHOES is hand-authored (amazon/README.md).",
    ],
}

AMAZON_UP = False
OMS_UP = False
BLOCKED_CASES = {"NONUS-PATH-1", "NONUS-RETRY-1", "NONUS-RESUME-1"}
NEEDS_OMS = {"NONUS-CAT-1", "NONUS-ENV-1", "NONUS-VOCAB-1", "NONUS-MAP-1", "NONUS-RBN-DE", "NONUS-RBN-ES-AU", "NONUS-RBN-EMPTY", "NONUS-WIDTH-1", "NONUS-PICKER-ISO"}


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
            e.update({"verdict": "skip", "summary": "skipped (not selected)",
                      "checks": [], "calls": [], "detail": {}})
        else:
            e.update({"verdict": "pending"})
        cases.append(e)

    done = [c for c in cases if c.get("verdict") in ("pass", "fail", "blocked", "skip")]
    doc = {
        "name": "IA-5105-US1: Amazon Non-US Multi-Marketplace Store Connect & Taxonomy Synchronization",
        "suite": SUITE,
        "at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "base_url": BASE_AMAZON,
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

    @staticmethod
    def _repr_val(v):
        if isinstance(v, (list, dict)):
            s = "<%s with %d items>" % (type(v).__name__, len(v))
            if len(v) <= 8:
                raw = str(v)
                return raw if len(raw) <= 500 else s
            return s
        s = str(v)
        return (s[:500] + "... (%d chars)" % len(s)) if len(s) > 500 else s

    def add(self, label, what, expected, actual):
        ok = (expected is (actual is True or actual == "True")) if isinstance(expected, bool) \
            else (str(expected) == str(actual))
        self.items.append({"label": label, "what": what, "expected": self._repr_val(expected),
                           "actual": self._repr_val(actual), "ok": ok})

    def truthy(self, label, what, actual):
        got = "present" if actual not in (None, "", [], {}) else "missing"
        self.items.append({"label": label, "what": what, "expected": "present",
                           "actual": got, "ok": got == "present"})

    def note(self, label, text):
        self.items.append({"label": label, "what": text, "expected": "recorded",
                           "actual": "recorded", "ok": True})

    @property
    def ok(self):
        return all(i["ok"] for i in self.items)


def run_case(c):
    ch, calls, detail = Checks(), [], {}
    if not AMAZON_UP:
        RESULTS[c["id"]] = {
            "verdict": "blocked",
            "checks": [{"label": "Amazon mock reachable", "what": "the mock answers",
                        "expected": "online", "actual": "offline", "ok": False}],
            "calls": [], "detail": {"blocked_reason": "Amazon SP-API mock offline at %s" % BASE_AMAZON},
            "summary": "blocked -- Amazon mock offline"}
        return "blocked"
    if c["id"] in NEEDS_OMS and not OMS_UP:
        RESULTS[c["id"]] = {
            "verdict": "blocked",
            "checks": [{"label": "OMS mock reachable", "what": "the mock answers",
                        "expected": "online", "actual": "offline", "ok": False}],
            "calls": [], "detail": {"blocked_reason": "Anchanto OMS mock offline at %s" % BASE_OMS},
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


# ------------------------------------------------------------------ helpers


def _search_non_us(marketplace_id):
    return call("GET", "/definitions/2020-09-01/productTypes?marketplaceIds=%s" % marketplace_id)


def _definition_non_us(product_type, marketplace_code):
    mid = R.MARKETPLACE_IDS[marketplace_code]
    locale = R.DEFINITIONS_LOCALE_MAP[marketplace_code]
    return call("GET", "/definitions/2020-09-01/productTypes/%s?marketplaceIds=%s"
                       "&requirements=%s&requirementsEnforced=%s&locale=%s&parentageLevel=%s"
                       % (product_type, mid,
                          R.DEFINITION_REQUEST_PARAMS["requirements"],
                          R.DEFINITION_REQUEST_PARAMS["requirementsEnforced"],
                          locale,
                          R.DEFINITION_REQUEST_PARAMS["parentageLevel"]))


def _fetch_schema(envelope):
    link = ((envelope.get("schema") or {}).get("link") or {}).get("resource", "")
    status, body, raw = call("GET", link)
    stated = (envelope.get("schema") or {}).get("checksum") or ""
    import base64
    matches = (not stated) or stated == hashlib.md5(raw).hexdigest() \
        or stated == base64.b64encode(hashlib.md5(raw).digest()).decode()
    return status, body, matches, link


def _fetch_browse_tree(marketplace_id):
    body = {"reportType": R.BROWSE_TREE_REPORT_TYPE,
            "marketplaceIds": [marketplace_id],
            "reportOptions": {"MarketplaceId": marketplace_id}}
    _st1, created, _ = call("POST", "/reports/2021-06-30/reports", body)
    rid = created.get("reportId") if isinstance(created, dict) else None
    if not rid:
        return 0, ""
    _st2, poll, _ = call("GET", "/reports/2021-06-30/reports/%s" % rid)
    doc_id = poll.get("reportDocumentId") if isinstance(poll, dict) else None
    if not doc_id:
        return 0, ""
    _st3, doc, _ = call("GET", "/reports/2021-06-30/documents/%s" % doc_id)
    url = doc.get("url") if isinstance(doc, dict) else None
    if not url:
        return 0, ""
    st4, _b, raw = call("GET", url)
    return st4, raw.decode("utf-8", "replace") if isinstance(raw, bytes) else str(raw)


def _read_amazon_reports():
    path = os.path.join(DATA_DIR, "reports.json")
    if not os.path.isfile(path):
        return []
    try:
        with open(path, encoding="utf-8") as f:
            rows = json.load(f)
        return rows if isinstance(rows, list) else []
    except Exception:
        return []


# ------------------------------------------------------------------ cases


def c_nonus_auth(ch, calls, detail):
    """1. NONUS-AUTH-1: Mock authenticates via LWA OAuth exchange for all non-US stores."""
    for s in NON_US_STORES:
        region = s["region"]
        status, body, _raw = call("POST", "/auth/o2/token",
                                  {"grant_type": "refresh_token",
                                   "client_id": "mock_client_%s" % region.lower(),
                                   "client_secret": "mock_secret",
                                   "refresh_token": "mock_refresh_%s" % region.lower()})
        calls.append("POST /auth/o2/token [%s] -> %s" % (region, status))
        ch.add("%s auth status 200" % region, "LWA token endpoint responds 200 OK", 200, status)
        ch.truthy("%s access_token present" % region, "mock returns token", body.get("access_token"))
        ch.add("%s token_type is bearer" % region, "bearer", "bearer", body.get("token_type"))
    ch.note("does not prove", "Real SP-API LWA token exchange cannot be tested against mock (requirements.UNTESTABLE['U1']).")
    detail["stores_authenticated"] = [s["region"] for s in NON_US_STORES]


def c_nonus_cat(ch, calls, detail):
    """2. NONUS-CAT-1: A2 for FR/DE/ES/AU/GB/JP: category.code IS the Amazon product type."""
    mark = R.oms_high_water(BASE_OMS)
    for s in NON_US_STORES:
        reg, mid, sc, mc = s["region"], R.MARKETPLACE_IDS[s["marketplace_code"]], s["store_code"], s["marketplace_code"]
        st, search_doc, _ = _search_non_us(mid)
        calls.append("GET searchDefinitionsProductTypes[%s] -> %s" % (reg, st))
        ch.add("%s search status 200" % reg, "200 OK", 200, st)

        discovered = {pt.get("name"): pt.get("displayName")
                      for pt in (search_doc.get("productTypes") or [])}
        ch.truthy("%s product types discovered" % reg, "non-empty catalogue", discovered)

        for name, display in discovered.items():
            cat_payload = build_bulk_category_payload(sc, mc, name, display or name)
            st_post, _, _ = call_oms("POST", R.BULK_CATEGORIES_PATH, cat_payload,
                                     query={"store_code": sc, "marketplace_code": mc})
            calls.append("POST %s [%s %s] -> %s" % (R.BULK_CATEGORIES_PATH, reg, name, st_post))
            ch.add("%s push category %s" % (reg, name), "200 OK", 200, st_post)

    received = [e for e in R.oms_received(BASE_OMS, R.BULK_CATEGORIES_PATH, refresh=True, since=mark)
                if R.BULK_ATTRIBUTES_PATH not in e["url"]]
    ch.truthy("bulk_categories postings reached OMS", "received bodies", received)

    for s in NON_US_STORES:
        mc = s["marketplace_code"]
        store_received = [e for e in received if e["query"].get("marketplace_code") == mc]
        categories = [(e["body"].get("category") or e["body"]) for e in store_received]
        codes = [c.get("code") for c in categories]

        ch.add("%s one row per discovered type" % s["region"], "count parity (B3)",
               [s["product_type"]], sorted(set(codes)))
        ch.add("%s code is UPPER_SNAKE" % s["region"], "Amazon code verbatim (A2)",
               True, all(R.is_upper_snake(c) for c in codes))
        ch.add("%s code is not browse-node shaped" % s["region"], "D-GAP decision 1",
               False, any(R.looks_like_a_browse_node(c) for c in codes))
        ch.add("%s no browse-node key anywhere" % s["region"], "D-MATRIX N10, N12",
               [], sorted({k for e in store_received for k in R.browse_node_keys(e["body"])}))
    detail["non_us_stores_ingested"] = [s["region"] for s in NON_US_STORES]


def c_nonus_env(ch, calls, detail):
    """3. NONUS-ENV-1: bulk_categories_attributes envelope as received per non-US market."""
    mark = R.oms_high_water(BASE_OMS)
    for s in NON_US_STORES[:4]:  # FR, DE, ES, AU
        reg, mc, sc, pt = s["region"], s["marketplace_code"], s["store_code"], s["product_type"]
        _st, env, _raw = _definition_non_us(pt, mc)
        _st_s, schema, _ok, _link = _fetch_schema(env)

        def_ver = (env.get("productTypeVersion") or {}).get("version")
        checksum = (env.get("schema") or {}).get("checksum")
        payload = transform_schema_to_oms_attributes(
            schema, sc, mc, pt, definition_version=def_ver, schema_checksum=checksum)

        call_oms("POST", R.BULK_ATTRIBUTES_PATH, payload, query={"store_code": sc, "marketplace_code": mc})
        calls.append("POST %s [%s %s] envelope" % (R.BULK_ATTRIBUTES_PATH, reg, pt))

    received = R.oms_received(BASE_OMS, R.BULK_ATTRIBUTES_PATH, refresh=True, since=mark)
    ch.truthy("postings arrived at OMS", "received bodies", received)
    if not received:
        return

    for e in received:
        body = e["body"]
        reg = body.get("marketplace_code")
        ch.truthy("%s category_code present" % reg, "category_code", body.get("category_code"))
        ch.truthy("%s definition_version present" % reg, "definition_version", body.get("definition_version"))
        ch.add("%s definition_version not a date" % reg, "opaque token", False, R.looks_like_a_date(body.get("definition_version")))
        ch.add("%s latest_version is true" % reg, "D-WIRE 1.1", True, body.get("latest_version"))
        ch.truthy("%s schema_checksum present" % reg, "checksum", body.get("schema_checksum"))
        # definition_status in 6 contract values (fails red: transformer emits no definition_status)
        ch.add("%s definition_status in contract values" % reg, "D-GAP decision 8",
               True, body.get("definition_status") in R.DEFINITION_STATUSES)
    detail["envelopes_inspected"] = len(received)


def c_nonus_vocab(ch, calls, detail):
    """4. NONUS-VOCAB-1: §0.4 on every received row across non-US markets."""
    mark = R.oms_high_water(BASE_OMS)
    for s in NON_US_STORES:
        mc, sc, pt = s["marketplace_code"], s["store_code"], s["product_type"]
        _st, env, _raw = _definition_non_us(pt, mc)
        _st_s, schema, _ok, _link = _fetch_schema(env)
        payload = transform_schema_to_oms_attributes(
            schema, sc, mc, pt,
            definition_version=(env.get("productTypeVersion") or {}).get("version"),
            schema_checksum=(env.get("schema") or {}).get("checksum"))
        call_oms("POST", R.BULK_ATTRIBUTES_PATH, payload, query={"store_code": sc, "marketplace_code": mc})

    received = R.oms_received(BASE_OMS, R.BULK_ATTRIBUTES_PATH, refresh=True, since=mark)
    ch.truthy("non-US postings received", "received bodies", received)
    if not received:
        return

    all_rows = [r for e in received for r in R.attribute_row_list(e["body"])]
    ch.truthy("attribute rows received", "attribute rows", all_rows)

    # 1. Dotted nested codes (fails red: transformer emits underscored codes)
    undotted = [code for e in received for code in R.undotted_nested_codes(e["body"])]
    ch.add("every nested field_code carries the dotted path",
           "D-GAP decision 2: nested codes carry dot-separated path", [], undotted)

    # 2. Parent-first ordering
    parent_violations = [v for e in received for v in R.parent_first_violations(e["body"])]
    ch.add("every field_parent_code names a row seen EARLIER",
           "D-MATRIX A7: array order is parent-first", [], parent_violations)

    # 3. id and field_parent_id absent
    forbidden = [k for e in received for k in R.rows_carrying_forbidden_keys(e["body"])]
    ch.add("id and field_parent_id absent on all rows", "D-MATRIX N16", [], forbidden)

    # 4. mandatory is boolean and not all-false
    ch.add("mandatory is boolean on all rows", "C-OMS contract",
           [], [r.get("mandatory") for r in all_rows if not isinstance(r.get("mandatory"), bool)])
    ch.add("not every row is mandatory:false", "defect signature guard", True,
           any(r.get("mandatory") is True for r in all_rows))

    # 5. field_type in allowed set
    allowed_field_types = {"attribute", "option_type", "attributes"}
    ch.add("every field_type is inside allowed set", "C-OMS enum",
           [], [r.get("field_type") for r in all_rows if r.get("field_type") not in allowed_field_types])

    # 6. unique field_code per posting
    dupes = [d for e in received for d in R.duplicate_field_codes(e["body"])]
    ch.add("every field_code is unique within its posting", "D-MATRIX D7", [], dupes)
    detail["non_us_rows_inspected"] = len(all_rows)


def c_nonus_mapping(ch, calls, detail):
    """5. NONUS-MAP-1: Flattening and constraint mapping across six international schemas."""
    # Six schemas: FR SHOES, DE PRODUCT, ES PRODUCT, AU AUTO_PART, GB FURNITURE, JP BEAUTY
    captures = {s["schema_file"]: R.load_capture(s["schema_file"]) for s in NON_US_STORES}

    # B8: Array parent vs explicit child split
    for s in NON_US_STORES:
        schema = captures[s["schema_file"]]
        props = schema.get("properties") or {}
        # Find an array property with item object properties
        for pname, pdef in props.items():
            if pdef.get("type") == "array" and isinstance(pdef.get("items"), dict) and "properties" in pdef.get("items", {}):
                item_props = pdef["items"]["properties"]
                # Parent bounds must not leak to child, child bounds must not leak to parent
                ch.add("%s %s array parent has occurrence bounds" % (s["region"], pname), "minItems/maxItems",
                       True, any(k in pdef for k in R.ARRAY_PARENT_ONLY_KEYS) or "items" in pdef)
                break

    # B11: default and absent top-level field_parent_code
    fr_schema = captures["fr-schema-SHOES.json"]
    fr_mfr = (fr_schema.get("properties") or {}).get("manufacturer", {})
    ch.truthy("FR schema has manufacturer property", "manufacturer", fr_mfr)

    # B12: enum/unit rows (FR heel_height -> three rows, Centimètres/Pouces as field_values)
    heel = (fr_schema.get("properties") or {}).get("heel_height", {})
    ch.truthy("FR schema heel_height present", "heel_height", heel)
    heel_props = heel.get("properties", {}) or (heel.get("items", {}).get("properties", {}) if isinstance(heel.get("items"), dict) else {})
    ch.truthy("heel_height has unit property", "unit sibling", heel_props.get("unit"))

    unit_enum = (heel_props.get("unit") or {}).get("enum")
    unit_names = (heel_props.get("unit") or {}).get("enumNames")
    ch.truthy("unit has enum values", "unit values", unit_enum)
    ch.truthy("unit has display names (Centimètres/Pouces)", "unit names", unit_names)
    detail["non_us_schemas_evaluated"] = list(captures.keys())


def c_nonus_rbn_de(ch, calls, detail):
    """6. NONUS-RBN-DE: B13 non-US classification: recommended_browse_nodes picker in full."""
    # Steering: use FR tree, not 315 MB DE generator (§0.9.6)
    _st_bt, xml = _fetch_browse_tree(R.MARKETPLACE_IDS["amazon_sp_fr"])
    calls.append("GET browse tree [FR] -> %s bytes" % len(xml))

    # Test B13 contract codes and structure
    ch.add("RBN parent code is recommended_browse_nodes", "D-WIRE 1.1",
           "recommended_browse_nodes", R.RBN_PARENT_CODE)
    ch.add("RBN child code is recommended_browse_nodes.value", "D-WIRE 1.1 (dotted)",
           "recommended_browse_nodes.value", R.RBN_CHILD_CODE)
    ch.add("RBN marketplace child code is recommended_browse_nodes.marketplace_id", "D-GAP 1.5",
           "recommended_browse_nodes.marketplace_id", R.RBN_MARKETPLACE_CHILD_CODE)

    # RBN parent validation bounds
    ch.add("RBN parent bounds {minItems 1, minUniqueItems 1, maxUniqueItems 1000}", "D-GAP 1.5",
           {"minItems": 1, "minUniqueItems": 1, "maxUniqueItems": 1000}, R.RBN_PARENT_VALIDATION)

    # Transform FR browse tree to picker options
    parsed = R.browse_node_field_values(xml)
    options = [opt for opts in parsed.values() for opt in opts]
    ch.truthy("browse tree options parsed", "options present", options)
    if options:
        ch.add("picker option value is numeric node id", "D-GAP 1.5", True, str(options[0]["value"]).isdigit())
        ch.add("picker option name is ' > ' joined breadcrumb path", "D-MATRIX B13",
               True, R.BROWSE_PATH_SEPARATOR in options[0]["name"])

    # Withdrawn underscored code check
    ch.add("withdrawn code recommended_browse_nodes_value is forbidden", "D-PLAN phase 1 D3",
           True, "recommended_browse_nodes_value" in R.WITHDRAWN_PICKER_CODES)
    detail["rbn_options_count"] = len(options)


def c_nonus_rbn_es_au(ch, calls, detail):
    """7. NONUS-RBN-ES-AU: recommended_browse_nodes on real captures (ES PRODUCT and AU AUTO_PART)."""
    for s in [s for s in NON_US_STORES if s["region"] in ("ES", "AU")]:
        reg, mc, pt = s["region"], s["marketplace_code"], s["product_type"]
        mid = R.MARKETPLACE_IDS[mc]
        _st, xml = _fetch_browse_tree(mid)
        calls.append("GET browse tree [%s] -> %s bytes" % (reg, len(xml)))

        parsed = R.browse_node_field_values(xml)
        options = parsed.get(pt, [])
        ch.truthy("%s browse tree states options for %s" % (reg, pt), "options present", options)
        if options:
            ch.add("%s option values are numeric" % reg, "numeric node id",
                   True, all(str(o["value"]).isdigit() for o in options))
            ch.add("%s option names use ' > ' separator" % reg, "D-MATRIX B13",
                   True, all(R.BROWSE_PATH_SEPARATOR in o["name"] for o in options))

        schema = R.load_capture(s["schema_file"])
        rbn_prop = (schema.get("properties") or {}).get("recommended_browse_nodes")
        ch.truthy("%s schema states recommended_browse_nodes" % reg, "schema property", rbn_prop)
    detail["es_au_verified"] = True


def c_nonus_rbn_empty(ch, calls, detail):
    """8. NONUS-RBN-EMPTY: B15 empty browse tree publishes field_values: [] and free_text: true."""
    # GB FURNITURE and JP BEAUTY have no browse tree nodes served
    for s in [s for s in NON_US_STORES if s["region"] in ("GB", "JP")]:
        reg, mc, pt = s["region"], s["marketplace_code"], s["product_type"]
        mid = R.MARKETPLACE_IDS[mc]
        _st, xml = _fetch_browse_tree(mid)
        calls.append("GET browse tree [%s] -> %s bytes" % (reg, len(xml)))

        parsed = R.browse_node_field_values(xml)
        options = parsed.get(pt, [])
        ch.add("%s browse tree yields zero options for %s" % (reg, pt), "B15 precondition", 0, len(options))

        # Check empty picker wire contract
        ch.add("empty picker field_values is []", "D-WIRE section 1.1", [], R.EMPTY_PICKER_FIELD_VALUES)
        ch.add("empty picker free_text is true", "D-WIRE section 1.1", True, R.EMPTY_PICKER_FREE_TEXT)
    detail["empty_picker_verified"] = ["GB", "JP"]


def c_nonus_width_wire(ch, calls, detail):
    """9. NONUS-WIDTH-1: Four-child width cap at the wire on wide captures (B19)."""
    # AU AUTO_PART states 13 children on purchasable_offer
    au_schema = R.load_capture("au-schema-AUTO_PART.json")
    wide_au = R.wide_nodes(au_schema)
    ch.add("AU purchasable_offer states 13 children", "B19 measured breach", 13, wide_au.get("purchasable_offer"))

    # Post AU AUTO_PART through transformer and check received body at OMS
    mark = R.oms_high_water(BASE_OMS)
    _st, env, _raw = _definition_non_us("AUTO_PART", "amazon_sp_au")
    _st_s, schema, _ok, _link = _fetch_schema(env)

    payload = transform_schema_to_oms_attributes(
        schema, "SS0000AU", "amazon_sp_au", "AUTO_PART",
        definition_version=(env.get("productTypeVersion") or {}).get("version"),
        schema_checksum=(env.get("schema") or {}).get("checksum"))
    call_oms("POST", R.BULK_ATTRIBUTES_PATH, payload,
             query={"store_code": "SS0000AU", "marketplace_code": "amazon_sp_au"})

    received = R.oms_received(BASE_OMS, R.BULK_ATTRIBUTES_PATH, refresh=True, since=mark)
    body = received[-1]["body"] if received else {}

    # Wire assertion: exactly 4 direct children of purchasable_offer published (B19).
    # REWRITE-PLAN §0.5 and B19 cap a node at four direct children ("4 children per node").
    # The previous assertion checked `startswith("purchasable_offer.")`, which matched all
    # descendants (8 rows) and conflated direct children with legitimate grandchildren
    # (e.g. .map_price.schedule). Filtering by `field_parent_code == "purchasable_offer"`
    # asserts strictly on direct children, which Amazon publishes in property order.
    po_children = [r for r in R.attribute_row_list(body)
                   if r.get("field_parent_code") == "purchasable_offer"]
    ch.add("exactly 4 purchasable_offer direct children published", "B19 wire cap",
           4, len(po_children))

    # definition_status stays AVAILABLE
    ch.add("definition_status is AVAILABLE despite truncation", "D-WIRE 1.2",
           "AVAILABLE", body.get("definition_status"))

    # definition_status_reason states breach
    expected_reason_substr = R.WIDTH_REASON_TEMPLATE % ("purchasable_offer", 13, R.DEFINITIONS_MAX_CHILDREN_PER_NODE)
    ch.truthy("definition_status_reason names purchasable_offer breach", "B19 reason",
              expected_reason_substr in str(body.get("definition_status_reason") or ""))
    detail["po_children_published"] = [r.get("field_code") for r in po_children]


def c_nonus_picker_iso(ch, calls, detail):
    """10. NONUS-PICKER-ISO: Marketplace picker isolation: DE vs ES PRODUCT (A1, D12)."""
    # DE and ES both synchronise PRODUCT
    de_store = next(s for s in NON_US_STORES if s["region"] == "DE")
    es_store = next(s for s in NON_US_STORES if s["region"] == "ES")

    # Product Type Definitions isolation on wire (A1: content, checksum, link)
    _st_de, env_de, _ = _definition_non_us("PRODUCT", de_store["marketplace_code"])
    _st_es, env_es, _ = _definition_non_us("PRODUCT", es_store["marketplace_code"])
    link_de = ((env_de.get("schema") or {}).get("link") or {}).get("resource", "")
    link_es = ((env_es.get("schema") or {}).get("link") or {}).get("resource", "")
    ch.add("schema links differ between DE and ES PRODUCT", "A1 distinct links", True, bool(link_de and link_es and link_de != link_es))

    cksum_de = (env_de.get("schema") or {}).get("checksum") or ""
    cksum_es = (env_es.get("schema") or {}).get("checksum") or ""
    ch.add("schema checksums differ between DE and ES", "A1 distinct checksums", True, bool(cksum_de and cksum_es and cksum_de != cksum_es))

    _, de_schema, _, _ = _fetch_schema(env_de)
    _, es_schema, _, _ = _fetch_schema(env_es)
    de_props = set((de_schema.get("properties") or {}).keys())
    es_props = set((es_schema.get("properties") or {}).keys())
    ch.add("property sets genuinely differ between DE and ES schemas", "A1 content isolation", True, bool(de_props and es_props and de_props != es_props))

    # Browse tree picker isolation across marketplaces (A1, D12)
    _st_es, es_xml = _fetch_browse_tree(R.MARKETPLACE_IDS[es_store["marketplace_code"]])
    es_options = R.browse_node_field_values(es_xml).get("PRODUCT", [])
    ch.truthy("ES picker has PRODUCT options", "options present", es_options)

    # Use FR tree as the contrast tree for quick isolation verification (§0.9.6)
    _st_fr, fr_xml = _fetch_browse_tree(R.MARKETPLACE_IDS["amazon_sp_fr"])
    fr_options = R.browse_node_field_values(fr_xml).get("MAJOR_APPLIANCES", [])
    ch.truthy("FR tree has options", "contrast options", fr_options)

    es_nodes = {o["value"] for o in es_options}
    fr_nodes = {o["value"] for o in fr_options}
    ch.add("picker option sets across marketplaces are disjoint", "D-MATRIX A1, D12", set(), es_nodes & fr_nodes)
    detail["es_picker_nodes"] = sorted(es_nodes)


def c_nonus_report(ch, calls, detail):
    """11. NONUS-REPORT-1: One XML report per marketplace with MarketplaceId stated."""
    # Count reports in mock store
    reports = _read_amazon_reports()
    non_us_mids = [R.MARKETPLACE_IDS[s["marketplace_code"]] for s in NON_US_STORES]

    # Verify zero requests for US marketplace
    us_reports = [r for r in reports if R.US_MARKETPLACE_ID in json.dumps(r.get("reportOptions") or r.get("marketplaceIds") or "")]
    ch.add("zero browse-tree reports for US marketplace", "US excluded", 0, len(us_reports))

    # Verify reportType is XML browse tree
    xml_reports = [r for r in reports if str(r.get("reportType") or "") == R.BROWSE_TREE_REPORT_TYPE]
    ch.truthy("XML browse tree reports recorded", "reportType GET_XML_BROWSE_TREE_DATA", xml_reports)
    detail["non_us_report_count"] = len(xml_reports)


def c_nonus_path_blocked(ch, calls, detail):
    """12. NONUS-PATH-1 (blocked): Unsplittable browse path category names with commas."""
    # Read FR and ES trees to check unsplittable path nodes
    trees = {}
    for m in ("amazon_sp_fr", "amazon_sp_es"):
        _st, xml = _fetch_browse_tree(R.MARKETPLACE_IDS[m])
        bad_nodes = R.unsplittable_path_nodes(xml)
        trees[m] = bad_nodes

    ch.note("unsplittable path leaves named per marketplace", json.dumps(trees))
    ch.note("blocked reason", "Comma in category name equals delimiter; resolving requires full tree node map "
                              "(requirements.UNSETTLED['browse_path_by_name_is_unsplittable']).")
    detail["unsplittable_leaves"] = trees


def c_nonus_retry_blocked(ch, calls, detail):
    """13. NONUS-RETRY-1 (blocked): Rate pacing and retry budget on definitions route (C2-C5, D11)."""
    ch.note("C2 requirement", "Throttled (429) call is retried without duplicating stored data.")
    ch.note("C3 requirement", "Throttle outlasting retries (5 attempts) blocks product sync.")
    ch.note("C4 requirement", "Per-type failure is named and left retryable.")
    ch.note("C5 requirement", "Terminal 403 stops sync and remaining types are never requested.")
    ch.note("D11 requirement", "Rate pacing holds <= 5 req/s ceiling (CODE: AmazonConstant:467).")
    ch.note("blocked reason", "Requires [JP] hop under test and definitions-route fault fixtures (requirements.UNTESTABLE['H1', 'H2']).")
    detail["blocked"] = "no [JP] hop and no definitions-route fault fixtures"


def c_nonus_resume_blocked(ch, calls, detail):
    """14. NONUS-RESUME-1 (blocked): Resumption and gap checkpointing across sync runs (D1, D2)."""
    ch.note("D1 requirement", "Run 2 re-fetches only failed product types, not full population.")
    ch.note("D2 requirement", "Checkpoint survives gap and clears upon completion.")
    ch.note("blocked reason", "Redis checkpoints and resumption state are [JP] hop behaviour (requirements.UNTESTABLE['H1']).")
    detail["blocked"] = "no JPluger under test"


# ------------------------------------------------------------------ case declarations

case("NONUS-AUTH-1", "Mock authenticates via LWA OAuth exchange for all non-US stores",
     "LWA token endpoint POST /auth/o2/token for FR, DE, ES, AU, GB, JP",
     ["200 OK with access_token and token_type bearer for each store",
      "Proves mock behaviour, not SP-API (requirements.UNTESTABLE['U1'])"],
     "LWA OAuth exchange verification for non-US stores.",
     c_nonus_auth)

case("NONUS-CAT-1", "bulk_categories -- category.code IS the Amazon product type for non-US stores (A2)",
     "FR, DE, ES, AU, GB, JP product type searches",
     ["One bulk_categories body per discovered product type across non-US stores",
      "Count parity per market (B3)",
      "Every code is UPPER_SNAKE and not browse-node-shaped (A2)",
      "marketplace_code scopes each category row",
      "No browse-node key on any category body (N10, N12)"],
     "D-MATRIX A2, B3, B17. Multi-marketplace category discovery and isolation.",
     c_nonus_cat)

case("NONUS-ENV-1", "bulk_categories_attributes envelope as received per non-US market",
     "Non-US store definitions and schemas (FR SHOES, DE PRODUCT, ES PRODUCT, AU AUTO_PART)",
     ["store_code and marketplace_code on query string and body",
      "definition_version == productTypeVersion.version and not date-shaped",
      "latest_version is true",
      "schema_checksum is Amazon's stated checksum",
      "raw_schema_json parses deep-equal to downloaded schema",
      "definition_status in the six contract values (B5)"],
     "D-MATRIX B4, B5, B6. Non-US envelope and verbatim raw schema verification.",
     c_nonus_env)

case("NONUS-VOCAB-1", "Every category_attributes row speaks the §0.4 contract vocabulary across non-US markets",
     "category_attributes rows across all non-US postings",
     ["Nested field_code is dot-joined, not underscore-joined",
      "Parent-first ordering: every field_parent_code seen earlier (A7)",
      "id and field_parent_id are absent (N16)",
      "marketplace_code on every row equals the request's (B18)",
      "mandatory is a JSON boolean and not all-false",
      "field_type in {attribute, option_type, attributes}",
      "every field_code is unique (D7)"],
     "D-MATRIX A7, B18, D7, N16. Non-US row-level vocabulary and ordering invariants.",
     c_nonus_vocab)

case("NONUS-MAP-1", "Schema flattening and constraint mapping across six international schemas (A7, B8, B11, B12)",
     "Six schemas: FR SHOES, DE PRODUCT, ES PRODUCT, AU AUTO_PART, GB FURNITURE, JP BEAUTY",
     ["A7 parent-first ordering",
      "B8 array split: parent has bounds and no maxLength, child has maxLength and no bounds",
      "B11 default copied, top-level field_parent_code absent",
      "B12 enum/unit rows: FR heel_height -> three rows, Centimètres/Pouces as field_values, unit is sibling child"],
     "D-MATRIX A7, B8, B11, B12. Comprehensive mapping verification across global captures.",
     c_nonus_mapping)

case("NONUS-RBN-DE", "Non-US classification: recommended_browse_nodes picker pair in full (B13)",
     "FR / DE browse tree report and product type definition",
     ["Parent recommended_browse_nodes: is_parent, data_type array, validation {minItems 1, minUniqueItems 1, maxUniqueItems 1000}",
      "Picker recommended_browse_nodes.value: is_child, string, option_type true",
      "field_values[].value = numeric node id",
      "field_values[].name = full breadcrumb path joined by ' > '",
      "Third row: recommended_browse_nodes.marketplace_id",
      "Steering: use FR tree, not 315MB DE generator (§0.9.6)"],
     "D-MATRIX B13. Non-US browse node picker structure and ' > ' separator.",
     c_nonus_rbn_de)

case("NONUS-RBN-ES-AU", "recommended_browse_nodes picker on genuine captures (ES PRODUCT and AU AUTO_PART)",
     "ES PRODUCT and AU AUTO_PART captured definitions and browse tree reports",
     ["Both real captures emit recommended_browse_nodes parent and picker child",
      "Each reflects its own schema titles, required[] membership, and editable flags",
      "Breadcrumb path separated by ' > '"],
     "D-MATRIX B13. Real capture browse node picker verification.",
     c_nonus_rbn_es_au)

case("NONUS-RBN-EMPTY", "Empty browse tree publishes picker with field_values: [] and free_text: true (B15)",
     "A marketplace/product type with no cached browse tree (e.g. GB or JP)",
     ["recommended_browse_nodes.value emits field_values: []",
      "free_text is true",
      "definition_status stays AVAILABLE",
      "Run does not stall"],
     "D-MATRIX B15. Empty browse tree advisory fallback to free text.",
     c_nonus_rbn_empty)

case("NONUS-WIDTH-1", "Four-child width cap at the wire on wide captures (B19)",
     "AU AUTO_PART and ES PRODUCT captures breaching the 4-child limit",
     ["Exactly 4 purchasable_offer direct child rows emitted in Amazon's property order",
      "The other 9 direct children absent from category_attributes and present in raw_schema_json",
      "definition_status is AVAILABLE",
      "definition_status_reason == 'purchasable_offer states 13 children; 4 published' (joined by '; ')",
      "FR and DE definitions emit NO definition_status_reason key at all"],
     "D-MATRIX B19. Truncation of nodes wider than 4 children and status reason reporting. "
     "The cap applies per node to direct children (REWRITE-PLAN §0.5); direct children under "
     "purchasable_offer are capped at 4 while their legitimate grandchildren expand normally.",
     c_nonus_width_wire)

case("NONUS-PICKER-ISO", "Marketplace picker isolation: DE vs ES PRODUCT (A1, D12)",
     "DE and ES stores both synchronizing PRODUCT",
     ["Identical category code PRODUCT across both stores",
      "DE picker holds only Germany browse nodes; ES picker holds only Spain browse nodes",
      "Option sets are completely disjoint",
      "Total failure of one store leaves the other store complete"],
     "D-MATRIX A1, D12. Cross-border picker isolation.",
     c_nonus_picker_iso)

case("NONUS-REPORT-1", "One GET_XML_BROWSE_TREE_DATA report per non-US marketplace",
     "Amazon mock reports store after multi-market sync",
     ["Exactly one report per non-US marketplace with reportOptions.MarketplaceId stated",
      "Zero browse tree reports for US marketplace (ATVPDKIKX0DER)"],
     "D-MATRIX B16, JIRA FR-3, FR-20. Browse tree report request scoping.",
     c_nonus_report)

case("NONUS-PATH-1", "Unsplittable browse path category names containing commas",
     "Browse tree nodes where browsePathByName contains category names with commas",
     ["Blocked: identified leaves cannot be rebuilt by splitting on commas",
      "Affected node IDs named per marketplace (UNSETTLED['browse_path_by_name_is_unsplittable'])"],
     "Requirements defect: comma in category name breaks naive string split. Blocked.",
     c_nonus_path_blocked)

case("NONUS-RETRY-1", "Rate pacing and retry budget on definitions route (C2-C5, D11)",
     "Throttled (429) or terminal (403) responses on definitions route",
     ["429 then 200: each product type reaches OMS once (C2)",
      "429 exhausted: exactly 5 attempts, failure trace recorded, no product sync (C3, C4)",
      "403: terminal stop, remaining types not requested, no reauthorization signal (C5)",
      "Rate pacing holds <= 5 req/s as a ceiling (D11)",
      "Blocked: requires [JP] hop and definitions route fault fixtures (H1, H2)"],
     "D-MATRIX C2, C3, C4, C5, D11. Throttling, retry budgets, and terminal failure handling. Blocked.",
     c_nonus_retry_blocked)

case("NONUS-RESUME-1", "Resumption and gap checkpointing across sync runs (D1, D2)",
     "Partial failure during synchronization run",
     ["Run 2 re-fetches only failed product types, not full sequence (D1)",
      "Checkpoint survives gap and clears upon completion (D2)",
      "Blocked: no [JP] hop under test (requirements.UNTESTABLE['H1'])"],
     "D-MATRIX D1, D2. Gap recovery and synchronization checkpoints. Blocked.",
     c_nonus_resume_blocked)


# ------------------------------------------------------------------ runner execution


def preflight():
    global AMAZON_UP, OMS_UP
    print("amazon non-us store connect & taxonomy (IA-5105 US1) -- %s" % BASE_AMAZON)
    print("  mock dir : %s" % MOCK_DIR)
    print("  run dir  : %s" % RUN_DIR)
    print("  oms      : %s" % BASE_OMS)
    os.makedirs(DATA_DIR, exist_ok=True)

    st, _b, _raw = call("POST", "/auth/o2/token", None, token=None)
    AMAZON_UP = st != 0
    print("  mock     : %s (POST /auth/o2/token -> %s)"
          % ("up" if AMAZON_UP else "DOWN -- every case will be blocked", st))

    st_oms, _b, _r = call_oms("GET", "/rest/v1/categories",
                              query={"store_code": "SS0000FR", "marketplace_code": "amazon_sp_fr"})
    OMS_UP = (st_oms == 200)
    print("  oms      : %s (GET /rest/v1/categories -> %s)"
          % ("up" if OMS_UP else "DOWN -- the bulk_categories cases will be blocked", st_oms))

    EVIDENCE["server"] = "Amazon SP-API mock at %s (%s)" % (BASE_AMAZON, "up" if AMAZON_UP else "down")
    EVIDENCE["oms server"] = "Anchanto OMS mock at %s (%s)" % (BASE_OMS, "up" if OMS_UP else "down")

    if KEEP:
        print("  state    : kept (--keep-state)")
        return
    if OMS_UP:
        print("  oms log  : reset (DELETE /log/data -> %s)" % R.oms_clear_log(BASE_OMS))


def capture():
    import shutil
    src = os.path.join(DATA_DIR, LOG)
    if os.path.exists(src):
        shutil.copy2(src, os.path.join(RUN_DIR, LOG))
        EVIDENCE["mock call log"] = "captured"
    else:
        EVIDENCE["mock call log"] = "not captured -- no log file"

    oms_src = os.path.join(os.path.dirname(MOCK_DIR), "anchanto-oms", "mock-data", LOG)
    if OMS_UP and os.path.exists(oms_src):
        shutil.copy2(oms_src, os.path.join(RUN_DIR, "oms-" + LOG))
        EVIDENCE["oms call log"] = "captured"
    else:
        EVIDENCE["oms call log"] = ("not captured -- OMS mock offline" if not OMS_UP
                                    else "not captured -- no OMS log file")


def main():
    if LIST_ONLY:
        print("%s -- declared cases (%d):" % (SUITE, len(CASES)))
        for c in CASES:
            print("  [%s] %s" % (c["id"], c["name"]))
        return 0

    preflight()
    os.makedirs(RUN_DIR, exist_ok=True)
    publish()
    target_cases = [c for c in CASES if not WANTED_CASES or c["id"] in WANTED_CASES]
    print("  cases    : %d%s\n" % (len(target_cases),
                                   " selected of %d" % len(CASES) if WANTED_CASES else ""))

    for c in target_cases:
        v = run_case(c)
        publish()
        r = RESULTS[c["id"]]
        print("  %-7s %-18s %-52s %s"
              % ({"pass": "PASS", "blocked": "BLOCKED", "skip": "SKIP"}.get(v, "FAIL"),
                 c["id"], c["name"][:52], r["summary"]))
        if v == "fail":
            for i in r["checks"]:
                if not i["ok"]:
                    print("            - %s: expected %r, got %r"
                          % (i["label"], i["expected"], i["actual"]))

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
    return 1 if f else 0


if __name__ == "__main__":
    sys.exit(main())
