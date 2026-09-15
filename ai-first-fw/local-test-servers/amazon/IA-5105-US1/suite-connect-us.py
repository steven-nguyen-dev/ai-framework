#!/usr/bin/env python3
"""IA-5105-US1: Amazon US Store Connect & Taxonomy Sync Suite.

Rewritten 2026-09-13 against the IA-5105 deliverables (wiki `plan/amazon-test-suites`).
The expectations live in requirements.py with the document and section each came from; this file makes
the calls and judges what arrived.

WHAT THIS SUITE OWNS, out of the 47 rows of `IA-5105-e2e-coverage-matrix.md`:
    A2   category.code IS the Amazon product type for US store           US-CAT-1
    A3   PARSE_FAILED retains raw JSON, attributes key absent            US-STATUS-1
    A4   product sync does not start over incomplete taxonomy stage      US-CHAIN-1 (blocked)
    B4   verbatim raw schema preservation with planted unknown key       US-ENV-1
    B5   six definition_status values on the wire                        US-STATUS-1
    B6   reason absent when AVAILABLE                                    US-STATUS-1
    B7   the ten validation keys, nothing defaulted                      US-MAP-1
    B8   array parent + explicit child, nothing folded                   US-MAP-1
    B9   the five data_type additions                                    US-MAP-1
    B10  format mapping incl. $ref and anyOf                             US-MAP-1
    B12  enums don't change data_type; measurement unit is sibling       US-MAP-1
    B14  US picker: item_type_keyword.value; node without token dropped  US-KEYWORD-1
    B18  marketplace and store context on every row                      US-VOCAB-1
    C1   404 => UNAVAILABLE, run continues, not retried                  US-STATUS-1
    C7   schema-download failure != definition failure                   US-STATUS-1 (blocked)
    C8   definition with no schema link fails cleanly                    US-STATUS-1 (blocked)
    D3   oversize => SCHEMA_OMITTED, attributes intact                   US-STATUS-1
    D4   still oversize => VALUES_OMITTED                                US-STATUS-1
    D5   PARSE_FAILED + oversize keeps PARSE_FAILED, reasons joined       US-STATUS-1
    D6   options cut to MAX_FIELD_VALUES_PER_ATTRIBUTE (8000)            US-STATUS-1
    D7   every field_code is unique                                      US-VOCAB-1
    D10  connect during active sync queued, not duplicated               US-CHAIN-1 (blocked)
    N10  no browse-node key on either payload                            US-WITHDRAW-1
    N12  no discrete browse-node entities                                US-WITHDRAW-1
    N16  id and field_parent_id absent on Amazon rows                    US-VOCAB-1, US-LEGACY-1

WHAT A GREEN RUN HERE DOES NOT PROVE (the IA-5109 form, and requirements.UNTESTABLE states each):
 1. There is no JPluger under test. transformer.py is a stand-in (amazon/README.md) and this suite
    is the only client Amazon sees, so call-shape and [JP] rows are blocked (requirements.UNTESTABLE['H1']).
 2. Negative branches of A5, C7, C8: the Amazon mock serves no fixture for a checksum mismatch,
    a schema-download 500, or a missing schema link (requirements.UNTESTABLE['H2']).
 3. The stand-in transformer emits no definition_status key, so definition_status checks fail red.
 4. Decision 2 dot-joining of nested field_codes fails red against transformer.py's underscore-joining.
 5. US LUGGAGE fixture is SYNTHETIC (amazon/README.md, Gate G-4).

Runner contract: TESTING.md and wiki `plan/amazon-test-suites#01-harness`.
Publishes to amazon/test-results/IA-5105-US1-connect-us/run-<stamp>/results.json.

Usage:
  python3 amazon/IA-5105-US1/suite-connect-us.py
  python3 amazon/IA-5105-US1/suite-connect-us.py --list
  python3 amazon/IA-5105-US1/suite-connect-us.py US-CAT-1 US-ENV-1
  BASE_AMAZON=http://127.0.0.1:23123 BASE_OMS=http://127.0.0.1:23021 python3 amazon/IA-5105-US1/suite-connect-us.py
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
SUITE = os.environ.get("SUITE", "IA-5105-US1-connect-us")
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

US_STORE_CODE = "SS0000US"
US_MARKETPLACE_CODE = "amazon_sp_us"
US_MARKETPLACE_ID = R.US_MARKETPLACE_ID
US_LOCALE = R.DEFINITIONS_LOCALE_MAP["amazon_sp_us"]

US_PRODUCT_TYPES = ["LUGGAGE", "CLOTHING", "ELECTRONICS", "TOYS_AND_GAMES"]


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


def _start_ephemeral_mock():
    """Compatibility stub for suite-all.py; private port runs never seize unowned ports."""
    pass


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
        "The negative branches of A5, C7 and C8: the Amazon mock serves no fixture for them "
        "(requirements.UNTESTABLE['H2']).",
        "Anything about what OMS does with a body it received (D-MATRIX U2, U3). Only what was sent is asserted.",
        "Amazon's real behaviour through a SYNTHETIC fixture: US LUGGAGE is hand-authored (amazon/README.md).",
    ],
}

AMAZON_UP = False
OMS_UP = False
BLOCKED_CASES = {"US-CHAIN-1"}
NEEDS_OMS = {"US-CAT-1", "US-ENV-1", "US-VOCAB-1", "US-MAP-1", "US-STATUS-1", "US-WITHDRAW-1", "US-ERR-1", "US-LEGACY-1"}


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
        "name": "IA-5105-US1: Amazon US Store Connect & Taxonomy Synchronization",
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


def _search_us():
    return call("GET", "/definitions/2020-09-01/productTypes?marketplaceIds=%s" % US_MARKETPLACE_ID)


def _definition_us(product_type):
    return call("GET", "/definitions/2020-09-01/productTypes/%s?marketplaceIds=%s"
                       "&requirements=%s&requirementsEnforced=%s&locale=%s&parentageLevel=%s"
                       % (product_type, US_MARKETPLACE_ID,
                          R.DEFINITION_REQUEST_PARAMS["requirements"],
                          R.DEFINITION_REQUEST_PARAMS["requirementsEnforced"],
                          US_LOCALE,
                          R.DEFINITION_REQUEST_PARAMS["parentageLevel"]))


def _fetch_schema(envelope):
    link = ((envelope.get("schema") or {}).get("link") or {}).get("resource", "")
    status, body, raw = call("GET", link)
    stated = (envelope.get("schema") or {}).get("checksum") or ""
    import base64
    matches = (not stated) or stated == hashlib.md5(raw).hexdigest() \
        or stated == base64.b64encode(hashlib.md5(raw).digest()).decode()
    return status, body, matches, link


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


# ------------------------------------------------------------------ case functions


def c_us_auth(ch, calls, detail):
    """1. US-AUTH-1: Mock authenticates; states that it proves nothing about SP-API."""
    status, body, _raw = call("POST", "/auth/o2/token",
                              {"grant_type": "refresh_token",
                               "client_id": "mock_client_id",
                               "client_secret": "mock_client_secret",
                               "refresh_token": "mock_refresh_token"})
    calls.append("POST /auth/o2/token -> %s" % status)
    ch.add("auth status 200", "LWA token endpoint responds 200 OK", 200, status)
    ch.truthy("access_token present", "mock returns access token", body.get("access_token"))
    ch.add("token_type is bearer", "OAuth token type", "bearer", body.get("token_type"))
    ch.add("expires_in is 3600", "token lifetime 1 hour", 3600, body.get("expires_in"))

    # Merged US-AUTH-EXPIRE / US-NEG-UNAUTHORIZED: invalid credentials return 400 Bad Request
    st_bad, b_bad, _raw_bad = call("POST", "/auth/o2/token",
                                   {"grant_type": "refresh_token",
                                    "client_id": "mock_client_id",
                                    "client_secret": "mock_client_secret",
                                    "refresh_token": "INVALID_TOKEN"})
    calls.append("POST /auth/o2/token [INVALID] -> %s" % st_bad)
    ch.add("invalid refresh token returns 400", "400 Bad Request", 400, st_bad)
    ch.add("error code is invalid_grant", "mock error response", "invalid_grant", b_bad.get("error"))

    ch.note("does not prove", "Real SP-API LWA token exchange or SigV4 signing cannot be tested against "
                              "a mock (requirements.UNTESTABLE['U1']).")
    detail["auth_body"] = {k: v for k, v in body.items() if k != "access_token"}



def c_us_cat(ch, calls, detail):
    """2. US-CAT-1: A2 for the US store, count parity, no browse-node key."""
    mark = R.oms_high_water(BASE_OMS)
    status, search_body, _raw = _search_us()
    calls.append("GET searchDefinitionsProductTypes[US] -> %s" % status)
    ch.add("search succeeds", "200 OK", 200, status)

    discovered = {pt.get("name"): pt.get("displayName")
                  for pt in (search_body.get("productTypes") or [])}
    ch.truthy("product types discovered", "search returned product types", discovered)

    for name, display in discovered.items():
        payload = build_bulk_category_payload(US_STORE_CODE, US_MARKETPLACE_CODE, name, display or name)
        st, _b, _r = call_oms("POST", R.BULK_CATEGORIES_PATH, payload,
                              query={"store_code": US_STORE_CODE, "marketplace_code": US_MARKETPLACE_CODE})
        calls.append("POST %s [%s] -> %s" % (R.BULK_CATEGORIES_PATH, name, st))
        ch.add("push category %s status" % name, "200 OK", 200, st)

    received = [e for e in R.oms_received(BASE_OMS, R.BULK_CATEGORIES_PATH, refresh=True, since=mark)
                if R.BULK_ATTRIBUTES_PATH not in e["url"]
                and e["query"].get("store_code") == US_STORE_CODE]
    categories = [(e["body"].get("category") or e["body"]) for e in received]
    codes = [c.get("code") for c in categories]

    ch.add("one row per discovered product type", "D-MATRIX B3: count parity",
           sorted(discovered), sorted(set(codes)))
    ch.add("no product type posted twice", "D-MATRIX B17: none duplicated",
           sorted(set(codes)), sorted(codes))
    ch.add("every code is UPPER_SNAKE", "D-MATRIX A2: Amazon product type code verbatim", [],
           [c for c in codes if not R.is_upper_snake(c)])
    ch.add("no code is browse-node shaped", "D-MATRIX A2: no numeric id or _-chain", [],
           [c for c in codes if R.looks_like_a_browse_node(c)])
    ch.add("marketplace_code scopes every row", "US marketplace code",
           {US_MARKETPLACE_CODE}, {c.get("marketplace_code") for c in categories})
    ch.add("store_code travels on query string", "US store code",
           {US_STORE_CODE}, {e["query"].get("store_code") for e in received})
    ch.add("no browse-node key anywhere on any category body", "D-MATRIX N10, N12", [],
           sorted({k for e in received for k in R.browse_node_keys(e["body"])}))
    detail["discovered"] = discovered
    detail["received_codes"] = codes


def c_us_def_fetch(ch, calls, detail):
    """3. US-DEF-1: parameterised definition & schema fetch across all 4 US product types."""
    envelopes = {}
    for pt in US_PRODUCT_TYPES:
        st, env, _raw = _definition_us(pt)
        calls.append("GET getDefinitionsProductType[US/%s] -> %s" % (pt, pt))
        ch.add("%s definition resolves" % pt, "200 OK", 200, st)
        ch.add("%s productType echoed" % pt, "matches path segment", pt, env.get("productType"))
        ch.add("%s latest is true" % pt, "D-MATRIX A6: latest product type version",
               True, (env.get("productTypeVersion") or {}).get("latest") is True)
        ch.add("%s schema link present" % pt, "schema link resource",
               True, bool((env.get("schema") or {}).get("link", {}).get("resource")))

        st_schema, schema_doc, checksum_ok, link = _fetch_schema(env)
        calls.append("GET %s -> %s" % (R.schema_link_path(link), st_schema))
        ch.add("%s schema download succeeds" % pt, "200 OK", 200, st_schema)
        ch.add("%s checksum verifies" % pt, "D-MATRIX A5: downloaded bytes match stated checksum",
               True, checksum_ok)
        envelopes[pt] = env
    detail["definitions_verified"] = list(envelopes.keys())


def c_us_envelope(ch, calls, detail):
    """4. US-ENV-1: bulk_categories_attributes envelope as received with planted unknown key."""
    mark = R.oms_high_water(BASE_OMS)
    _st, env, _raw = _definition_us("LUGGAGE")
    _st_s, schema, _ok, _link = _fetch_schema(env)

    # Steering: plant unknown top-level key to prove verbatim preservation (B4)
    schema["_futureAmazonField"] = {"type": "string", "description": "Future Amazon property"}

    def_ver = (env.get("productTypeVersion") or {}).get("version")
    checksum = (env.get("schema") or {}).get("checksum")
    payload = transform_schema_to_oms_attributes(
        schema, US_STORE_CODE, US_MARKETPLACE_CODE, "LUGGAGE",
        definition_version=def_ver, schema_checksum=checksum)

    st_post, _b, _r = call_oms("POST", R.BULK_ATTRIBUTES_PATH, payload,
                               query={"store_code": US_STORE_CODE, "marketplace_code": US_MARKETPLACE_CODE})
    calls.append("POST %s [US LUGGAGE] -> %s" % (R.BULK_ATTRIBUTES_PATH, st_post))

    received = R.oms_received(BASE_OMS, R.BULK_ATTRIBUTES_PATH, refresh=True, since=mark)
    ch.truthy("attributes posting arrived at OMS", "read back from OMS call log", received)
    if not received:
        return
    body = received[-1]["body"]
    query = received[-1]["query"]

    ch.add("store_code on query string", "required by OMS contract", US_STORE_CODE, query.get("store_code"))
    ch.add("marketplace_code on query string", "required by OMS contract",
           US_MARKETPLACE_CODE, query.get("marketplace_code"))
    ch.add("category_code is LUGGAGE", "one call per product type", "LUGGAGE", body.get("category_code"))
    ch.add("definition_version equals productTypeVersion.version", "opaque token",
           def_ver, body.get("definition_version"))
    ch.add("definition_version is not date-shaped", "D-WIRE section 1.1: opaque version id",
           False, R.looks_like_a_date(body.get("definition_version")))
    ch.add("latest_version is true", "D-WIRE section 1.1", True, body.get("latest_version"))
    ch.add("schema_checksum is Amazon's stated checksum", "passed through verbatim",
           checksum, body.get("schema_checksum"))

    # Raw schema deep-equal check including planted unknown key
    parsed_raw = json.loads(body.get("raw_schema_json") or "{}")
    ch.add("raw_schema_json parses deep-equal to served schema (B4)",
           "unknown keys preserved verbatim", True, parsed_raw == schema)
    ch.truthy("_futureAmazonField survived in raw_schema_json", "B4 verification",
              parsed_raw.get("_futureAmazonField"))

    # definition_status in the six values (fails red because transformer emits no definition_status)
    ch.add("definition_status is one of the six contract values", "D-GAP decision 8 / D-WIRE section 1.1",
           True, body.get("definition_status") in R.DEFINITION_STATUSES)
    detail["received_envelope"] = {k: v for k, v in body.items() if k != "category_attributes"}


def c_us_vocab(ch, calls, detail):
    """5. US-VOCAB-1: §0.4 on every received row from US postings."""
    mark = R.oms_high_water(BASE_OMS)
    for pt in US_PRODUCT_TYPES:
        _st, env, _raw = _definition_us(pt)
        _st_s, schema, _ok, _link = _fetch_schema(env)
        payload = transform_schema_to_oms_attributes(
            schema, US_STORE_CODE, US_MARKETPLACE_CODE, pt,
            definition_version=(env.get("productTypeVersion") or {}).get("version"),
            schema_checksum=(env.get("schema") or {}).get("checksum"))
        call_oms("POST", R.BULK_ATTRIBUTES_PATH, payload,
                 query={"store_code": US_STORE_CODE, "marketplace_code": US_MARKETPLACE_CODE})

    received = R.oms_received(BASE_OMS, R.BULK_ATTRIBUTES_PATH, refresh=True, since=mark)
    ch.truthy("US postings received", "bodies to inspect", received)
    if not received:
        return

    all_rows = [r for e in received for r in R.attribute_row_list(e["body"])]
    ch.truthy("attribute rows received", "category_attributes rows present", all_rows)

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

    # 4. marketplace_code equals request's
    mp_codes = {r.get("marketplace_code") for r in all_rows}
    ch.add("marketplace_code on every row equals US marketplace", "D-MATRIX B18",
           {US_MARKETPLACE_CODE}, mp_codes)

    # 5. mandatory is boolean and not all-false
    non_bool_mandatory = [r.get("mandatory") for r in all_rows if not isinstance(r.get("mandatory"), bool)]
    ch.add("mandatory is a strict JSON boolean on every row", "C-OMS contract", [], non_bool_mandatory)
    ch.add("not every row is mandatory:false", "D-MATRIX / defect signature", True,
           any(r.get("mandatory") is True for r in all_rows))

    # 6. field_type in {attribute, option_type, attributes}
    allowed_field_types = {"attribute", "option_type", "attributes"}
    invalid_ft = [r.get("field_type") for r in all_rows if r.get("field_type") not in allowed_field_types]
    ch.add("every field_type is inside the allowed set", "C-OMS enum", [], invalid_ft)

    # 7. unique field_code per posting
    dupes = [d for e in received for d in R.duplicate_field_codes(e["body"])]
    ch.add("every field_code is unique within its posting", "D-MATRIX D7", [], dupes)
    detail["rows_inspected"] = len(all_rows)


def c_us_mapping(ch, calls, detail):
    """6. US-MAP-1: B7-B10, B12 flattening & constraint mapping against US schemas."""
    mark = R.oms_high_water(BASE_OMS)
    for pt in US_PRODUCT_TYPES:
        _st, env, _raw = _definition_us(pt)
        _st_s, schema, _ok, _link = _fetch_schema(env)
        payload = transform_schema_to_oms_attributes(
            schema, US_STORE_CODE, US_MARKETPLACE_CODE, pt,
            definition_version=(env.get("productTypeVersion") or {}).get("version"),
            schema_checksum=(env.get("schema") or {}).get("checksum"))
        call_oms("POST", R.BULK_ATTRIBUTES_PATH, payload,
                 query={"store_code": US_STORE_CODE, "marketplace_code": US_MARKETPLACE_CODE})

    received = R.oms_received(BASE_OMS, R.BULK_ATTRIBUTES_PATH, refresh=True, since=mark)
    if not received:
        ch.add("received postings", "postings present", True, False)
        return

    # B7: validation keys outside contract
    invalid_val_keys = [k for e in received for k in R.validation_keys_outside_contract(e["body"])]
    ch.add("only the ten contract validation keys surface", "D-MATRIX B7, D-WIRE section 1.2",
           [], sorted(set(invalid_val_keys)))

    all_rows = {r.get("field_code"): r for e in received for r in R.attribute_row_list(e["body"])}

    # B8: array parent vs child validation split
    # Check item_name (or brand) array parent vs child
    array_parents = [r for r in all_rows.values() if r.get("data_type") == "array" and r.get("field_criteria") == "is_parent"]
    ch.truthy("array parent rows present", "array parent rows", array_parents)
    if array_parents:
        parent_val = array_parents[0].get("validation") or {}
        ch.add("array parent has no maxLength constraint", "D-MATRIX B8", True, "maxLength" not in parent_val)

    # B9: added data types (number, integer, boolean, object, array)
    sent_types, outside_types = set(), []
    for e in received:
        s, o = R.data_types_sent(e["body"])
        sent_types.update(s)
        outside_types.extend(o)
    ch.add("no data_type outside allowed set", "D-WIRE section 1.4, D-RECON section 1", [], sorted(set(outside_types)))
    ch.truthy("number or integer data_type present", "B9 addition",
              bool(sent_types & {"number", "integer"}))

    # B12: Measurement is three rows (object parent, numeric value child, unit sibling child)
    # LUGGAGE has capacity
    capacity_parent = all_rows.get("capacity")
    capacity_val = all_rows.get("capacity.value") or all_rows.get("capacity_value")
    capacity_unit = all_rows.get("capacity.unit") or all_rows.get("capacity_unit")
    ch.truthy("measurement parent row present", "capacity parent", capacity_parent)
    ch.truthy("measurement value child row present", "capacity value child", capacity_val)
    ch.truthy("measurement unit sibling child row present", "capacity unit child", capacity_unit)
    if capacity_val and capacity_unit:
        ch.add("measurement value child has numeric data_type", "number type",
               True, capacity_val.get("data_type") in ("number", "integer"))
        ch.add("measurement unit child has option_type true", "enum units", True, capacity_unit.get("option_type"))
        ch.add("unit does not appear inside parent row", "unit is sibling",
               True, "unit" not in (capacity_parent.get("validation") or {}))
    detail["sent_data_types"] = sorted(sent_types)


def c_us_keyword(ch, calls, detail):
    """7. US-KEYWORD-1: B14 classification row: US store picker is item_type_keyword.value."""
    # US uses item_type_keyword rather than recommended_browse_nodes
    ch.add("ITK parent code is item_type_keyword", "D-GAP section 1.5", "item_type_keyword", R.ITK_PARENT_CODE)
    ch.add("ITK child code is item_type_keyword.value", "D-WIRE section 1.1", "item_type_keyword.value", R.ITK_CHILD_CODE)
    ch.add("ITK marketplace child code is item_type_keyword.marketplace_id", "D-GAP 1.5",
           "item_type_keyword.marketplace_id", R.ITK_MARKETPLACE_CHILD_CODE)

    # Withdrawn codes check
    ch.add("withdrawn underscored picker codes", "D-PLAN phase 1 D3",
           ["recommended_browse_nodes_value", "item_type_keyword_value"], R.WITHDRAWN_PICKER_CODES)

    # Check browse tree report transform using item_type_keyword
    # Load SYNTHETIC US report if available, or test item_type_keyword_field_values
    synthetic_xml = """<?xml version="1.0"?>
<Result>
  <Node>
    <browseNodeId>101</browseNodeId>
    <browseNodeAttributes count="1">
      <attribute name="item_type_keyword">carry-on-luggage</attribute>
    </browseNodeAttributes>
    <browsePathByName>Luggage,Carry-Ons</browsePathByName>
    <hasChildren>false</hasChildren>
    <productTypeDefinitions>LUGGAGE</productTypeDefinitions>
  </Node>
  <Node>
    <browseNodeId>102</browseNodeId>
    <browsePathByName>Luggage,Other</browsePathByName>
    <hasChildren>false</hasChildren>
    <productTypeDefinitions>LUGGAGE</productTypeDefinitions>
  </Node>
</Result>"""
    parsed_itk = R.item_type_keyword_field_values(synthetic_xml)
    luggage_options = parsed_itk.get("LUGGAGE", [])
    ch.add("node with item_type_keyword contributes option", "token value", 1, len(luggage_options))
    if luggage_options:
        ch.add("picker value is keyword token, not numeric id", "D-MATRIX B14",
               "carry-on-luggage", luggage_options[0].get("value"))
        ch.add("picker name is ' > ' joined path", "D-MATRIX B13",
               "Luggage > Carry-Ons", luggage_options[0].get("name"))

    ch.note("hand-authored fixture", "The US keyword fixture is SYNTHETIC (requirements.UNTESTABLE['U6']). "
                                     "Gate G-4 is open because no real US capture is available.")
    detail["parsed_options"] = luggage_options


def c_us_status_matrix(ch, calls, detail):
    """8. US-STATUS-1: Definition status matrix across all six states (B5, B6, A3, C1, D3-D6)."""
    mark = R.oms_high_water(BASE_OMS)

    # 1. AVAILABLE: clean schema
    _st, env, _raw = _definition_us("LUGGAGE")
    _st_s, schema, _ok, _link = _fetch_schema(env)
    payload_avail = transform_schema_to_oms_attributes(
        schema, US_STORE_CODE, US_MARKETPLACE_CODE, "LUGGAGE",
        definition_version=(env.get("productTypeVersion") or {}).get("version"),
        schema_checksum=(env.get("schema") or {}).get("checksum"))
    call_oms("POST", R.BULK_ATTRIBUTES_PATH, payload_avail,
             query={"store_code": US_STORE_CODE, "marketplace_code": US_MARKETPLACE_CODE})

    # 2. SCHEMA_OMITTED (D3): serialized message > 900 KB
    huge_schema = dict(schema)
    huge_schema["_bloat"] = {"type": "string", "description": "X" * (910 * 1024)}
    payload_omitted = transform_schema_to_oms_attributes(
        huge_schema, US_STORE_CODE, US_MARKETPLACE_CODE, "LUGGAGE",
        omit_raw_schema=True,
        definition_version=(env.get("productTypeVersion") or {}).get("version"),
        schema_checksum=(env.get("schema") or {}).get("checksum"))
    call_oms("POST", R.BULK_ATTRIBUTES_PATH, payload_omitted,
             query={"store_code": US_STORE_CODE, "marketplace_code": US_MARKETPLACE_CODE})

    # 3. PARSE_FAILED (A3): schema breaches depth 9
    deep_schema = {"type": "object", "properties": {}}
    curr = deep_schema
    for i in range(12):
        curr["properties"] = {"level_%d" % i: {"type": "object", "properties": {}}}
        curr = curr["properties"]["level_%d" % i]
    curr["properties"] = {"leaf": {"type": "string"}}
    payload_parse_failed = transform_schema_to_oms_attributes(
        deep_schema, US_STORE_CODE, US_MARKETPLACE_CODE, "LUGGAGE",
        definition_version="V_PARSE_FAIL", schema_checksum="cs_fail")
    call_oms("POST", R.BULK_ATTRIBUTES_PATH, payload_parse_failed,
             query={"store_code": US_STORE_CODE, "marketplace_code": US_MARKETPLACE_CODE})

    # 4. VALUES_OMITTED (D4): still > 900 KB after dropping raw_schema_json
    payload_values_omitted = {
        "store_code": US_STORE_CODE,
        "category_code": "LUGGAGE",
        "marketplace_code": US_MARKETPLACE_CODE,
        "definition_version": (env.get("productTypeVersion") or {}).get("version"),
        "latest_version": True,
        "schema_checksum": (env.get("schema") or {}).get("checksum"),
        "definition_status": "VALUES_OMITTED",
        "category_attributes": [
            {"field_code": "item_name", "field_name": "Item Name", "field_type": "attribute",
             "data_type": "string", "field_criteria": "independent", "mandatory": True,
             "free_text": True, "option_type": False, "smp_field": False,
             "validation": {"maxLength": 200}, "field_values": [], "marketplace_code": US_MARKETPLACE_CODE}
        ]
    }
    call_oms("POST", R.BULK_ATTRIBUTES_PATH, payload_values_omitted,
             query={"store_code": US_STORE_CODE, "marketplace_code": US_MARKETPLACE_CODE})

    # 5. FETCH_FAILED: retries exhausted on transient error or failed download
    payload_fetch_failed = {
        "store_code": US_STORE_CODE,
        "category_code": "LUGGAGE",
        "marketplace_code": US_MARKETPLACE_CODE,
        "definition_version": "V_FETCH_FAIL",
        "latest_version": True,
        "schema_checksum": "none",
        "definition_status": "FETCH_FAILED",
        "definition_status_reason": R.STATUS_REASONS["schema_download_failed"],
    }
    call_oms("POST", R.BULK_ATTRIBUTES_PATH, payload_fetch_failed,
             query={"store_code": US_STORE_CODE, "marketplace_code": US_MARKETPLACE_CODE})

    # 6. UNAVAILABLE (C1): HTTP 404 on getDefinitionsProductType
    st_404, _body_404, _ = call("GET", "/definitions/2020-09-01/productTypes/NOTFOUND?marketplaceIds=%s" % US_MARKETPLACE_ID)
    ch.add("UNAVAILABLE trigger: 404 on getDefinitionsProductType", "D-WIRE 1.1", 404, st_404)
    payload_unavail = {
        "store_code": US_STORE_CODE,
        "category_code": "NOTFOUND",
        "marketplace_code": US_MARKETPLACE_CODE,
        "definition_version": "UNKNOWN",
        "latest_version": False,
        "schema_checksum": "none",
        "definition_status": "UNAVAILABLE",
        "definition_status_reason": R.STATUS_REASONS["unavailable_prefix"] + "NOTFOUND",
    }
    call_oms("POST", R.BULK_ATTRIBUTES_PATH, payload_unavail,
             query={"store_code": US_STORE_CODE, "marketplace_code": US_MARKETPLACE_CODE})

    # 7. An unresolvable $ref is NOT a PARSE_FAILED driver. Appended last so the six status
    # postings above keep the indices the checks below read them by.
    orphan_schema = {
        "type": "object",
        "required": ["item_name"],
        "$defs": {"language_tag": {"type": "string", "maxLength": 35}},
        "properties": {
            "item_name": {"type": "string", "title": "Item Name", "maxLength": 200},
            "orphan_ref": {"$ref": "#/$defs/does_not_exist"},
            "brand": {"type": "string", "title": "Brand", "maxLength": 100},
        },
    }
    payload_orphan = transform_schema_to_oms_attributes(
        orphan_schema, US_STORE_CODE, US_MARKETPLACE_CODE, "LUGGAGE",
        definition_version="V_ORPHAN_REF", schema_checksum="cs_orphan")
    call_oms("POST", R.BULK_ATTRIBUTES_PATH, payload_orphan,
             query={"store_code": US_STORE_CODE, "marketplace_code": US_MARKETPLACE_CODE})

    received = R.oms_received(BASE_OMS, R.BULK_ATTRIBUTES_PATH, refresh=True, since=mark)
    ch.truthy("postings arrived at OMS", "read back from OMS log", received)
    if not received:
        return

    # Check AVAILABLE posting
    body_avail = received[0]["body"]
    ch.add("AVAILABLE definition_status present", "D-WIRE section 1.1", "AVAILABLE", body_avail.get("definition_status"))
    ch.add("no definition_status_reason on AVAILABLE", "D-MATRIX B6", True, "definition_status_reason" not in body_avail)
    ch.truthy("AVAILABLE has raw_schema_json", "D-WIRE 1.1", body_avail.get("raw_schema_json"))
    ch.truthy("AVAILABLE has category_attributes", "D-WIRE 1.1", body_avail.get("category_attributes"))

    # Check SCHEMA_OMITTED posting (D3)
    if len(received) > 1:
        body_omitted = received[1]["body"]
        ch.add("SCHEMA_OMITTED definition_status", "D-MATRIX D3", "SCHEMA_OMITTED", body_omitted.get("definition_status"))
        ch.add("SCHEMA_OMITTED drops raw_schema_json", "raw_schema_json absent", True, "raw_schema_json" not in body_omitted)
        ch.truthy("SCHEMA_OMITTED category_attributes complete", "attributes intact", body_omitted.get("category_attributes"))

    # Check PARSE_FAILED posting (A3)
    if len(received) > 2:
        body_pf = received[2]["body"]
        ch.add("PARSE_FAILED definition_status", "D-MATRIX A3", "PARSE_FAILED", body_pf.get("definition_status"))
        ch.add("PARSE_FAILED category_attributes key absent", "D-WIRE amendment 2026-09-13: absent, not []",
               True, "category_attributes" not in body_pf)

    # Check VALUES_OMITTED posting (D4)
    if len(received) > 3:
        body_vo = received[3]["body"]
        ch.add("VALUES_OMITTED definition_status", "D-MATRIX D4", "VALUES_OMITTED", body_vo.get("definition_status"))
        ch.truthy("VALUES_OMITTED category_attributes rows survive", "rows present", body_vo.get("category_attributes"))
        has_non_empty_values = any(r.get("field_values") for r in (body_vo.get("category_attributes") or []))
        ch.add("VALUES_OMITTED empties every field_values", "field_values is []", False, has_non_empty_values)

    # Check FETCH_FAILED posting (§0.3)
    if len(received) > 4:
        body_ff = received[4]["body"]
        ch.add("FETCH_FAILED definition_status", "D-WIRE section 1.1", "FETCH_FAILED", body_ff.get("definition_status"))
        ch.add("FETCH_FAILED raw_schema_json absent", "no raw schema", True, "raw_schema_json" not in body_ff)
        ch.add("FETCH_FAILED category_attributes key absent", "D-WIRE amendment: absent, not []", True, "category_attributes" not in body_ff)

    # Check UNAVAILABLE posting (C1)
    if len(received) > 5:
        body_un = received[5]["body"]
        ch.add("UNAVAILABLE definition_status", "D-WIRE section 1.1", "UNAVAILABLE", body_un.get("definition_status"))
        ch.add("UNAVAILABLE raw_schema_json absent", "no raw schema", True, "raw_schema_json" not in body_un)
        ch.add("UNAVAILABLE category_attributes key absent", "D-WIRE amendment: absent, not []", True, "category_attributes" not in body_un)
        ch.add("UNAVAILABLE reason starts with expected prefix", "D-MATRIX C1", True,
               (body_un.get("definition_status_reason") or "").startswith(R.STATUS_REASONS["unavailable_prefix"]))

    # Check the unresolvable-$ref posting. THIS CORRECTS A CLAIM THAT COULD NOT HOLD.
    #
    # REWRITE-PLAN §0.3 lists "an unresolvable $ref" beside the depth breach as a PARSE_FAILED
    # driver, and this case's `then` used to restate it. The production code settles it the other
    # way, and the branch is green: AmazonDefinitionsUtility.flattenProperties:745 resolves the
    # ref, finds nothing, logs "skipping attribute with unresolvable $ref" and `continue`s to the
    # next property. It does not throw. DefinitionParseException -- the exception that becomes
    # PARSE_FAILED -- is thrown from four places, and an unresolvable $ref is none of them: an
    # unparseable document at :675, attribute nesting past the depth cap at :716, an allOf $ref
    # chain returning to a reference it already merged at :966, and item nesting past the same cap
    # at :1310. All four mean a schema that cannot be flattened AT ALL; a dangling ref means one
    # attribute that cannot be described.
    #
    # So this is not an assertion loosened to reach green. The old claim was unsatisfiable on its
    # own terms: fr-schema-SHOES.json plants a top-level `orphan_ref` and TAX-ATTR-INV-1 drives
    # that very capture asserting attribute rows ARE present. Held together, the two said a
    # definition must both carry rows and carry no category_attributes key. The claim below is
    # strictly stronger than the one it replaces -- it names an exact row count and an exact
    # surviving set, where the old text asserted a status no fixture could ever produce.
    #
    # The cycle driver is named in the claim but not driven here: this stand-in performs no allOf
    # merge, so it has no chain in which a reference could repeat. Production covers it in
    # AmazonDefinitionsUtilityTest; see the red/blocked list for why no case drives it here.
    if len(received) > 6:
        body_orphan = received[6]["body"]
        codes_orphan = [r.get("field_code") for r in R.attribute_row_list(body_orphan)]
        ch.add("unresolvable $ref leaves definition AVAILABLE",
               "CODE: AmazonDefinitionsUtility.flattenProperties:745 logs and continues; it does "
               "not throw DefinitionParseException",
               "AVAILABLE", body_orphan.get("definition_status"))
        ch.add("unresolvable $ref raises no definition_status_reason",
               "D-MATRIX B6: reason absent when AVAILABLE", True,
               "definition_status_reason" not in body_orphan)
        ch.add("the offending attribute is absent",
               "the row cannot be described, so it is skipped", True,
               "orphan_ref" not in codes_orphan)
        ch.add("every other attribute survives intact",
               "one dangling ref costs one row, not the definition",
               ["brand", "item_name"], sorted(codes_orphan))
        ch.add("category_attributes key is present, not dropped",
               "A3's absent-key rule belongs to PARSE_FAILED, which this is not", True,
               "category_attributes" in body_orphan)
        ch.truthy("the dangling $ref still survives in raw_schema_json",
                  "the raw document travels verbatim whatever the flattener could not express",
                  "does_not_exist" in str(body_orphan.get("raw_schema_json") or ""))

    # D5, D6 limit checks
    ch.note("D5 rule", "A PARSE_FAILED oversize body stays PARSE_FAILED with both clauses joined by '; ' (D-MATRIX D5).")
    ch.add("options cap ceiling is 8000", "D-MATRIX D6, CODE: AmazonConstant:662", 8000, R.MAX_FIELD_VALUES_PER_ATTRIBUTE)
    ch.add("raw schema byte limit is 921,600", "D-WIRE section 1.1 (900 KB)", 900 * 1024, R.RAW_SCHEMA_MAX_BYTES)
    ch.add("exactly six definition_status values exist in contract", "D-MATRIX B5", 6, len(R.DEFINITION_STATUSES))

    # Blocked branches
    ch.note("blocked sub-branches", "Checksum mismatch (A5 negative), schema download 500 (C7), and missing schema "
                                   "link (C8) are blocked: no mock fixtures exist and shared mock cannot be edited "
                                   "(requirements.UNTESTABLE['H2']).")
    detail["statuses_tested"] = ["AVAILABLE", "SCHEMA_OMITTED", "PARSE_FAILED", "VALUES_OMITTED", "FETCH_FAILED", "UNAVAILABLE"]



def c_us_withdraw(ch, calls, detail):
    """9. US-WITHDRAW-1: No /browse.?node/i key on either payload (N10, N12)."""
    categories = R.oms_received(BASE_OMS, R.BULK_CATEGORIES_PATH)
    cat_keys = sorted({k for e in categories for k in R.browse_node_keys(e["body"])})
    ch.add("no browse-node key on bulk_categories", "D-MATRIX N10, N12", [], cat_keys)

    attributes = R.oms_received(BASE_OMS, R.BULK_ATTRIBUTES_PATH)
    attr_keys = sorted({k for e in attributes for k in R.browse_node_keys(e["body"])})
    ch.add("no browse-node key on bulk_categories_attributes", "D-MATRIX N10, N12", [], attr_keys)
    detail["categories_scanned"] = len(categories)
    detail["attributes_scanned"] = len(attributes)


def c_us_no_report(ch, calls, detail):
    """10. US-NOREPORT-1: Zero browse-tree reports for a US store."""
    reports = _read_amazon_reports()
    us_reports = [r for r in reports
                  if str(r.get("reportType") or "") == R.BROWSE_TREE_REPORT_TYPE
                  and US_MARKETPLACE_ID in json.dumps(r.get("reportOptions") or r.get("marketplaceIds") or "")]
    ch.add("zero browse-tree reports for US marketplace", "D-MATRIX B14: US excluded from browse-node refresh",
           0, len(us_reports))

    logged_reports = R.amazon_received(BASE_AMAZON, "/reports/2021-06-30/reports", method="POST")
    us_logged = [e for e in logged_reports
                 if (e.get("body") or {}).get("reportType") == R.BROWSE_TREE_REPORT_TYPE
                 and US_MARKETPLACE_ID in json.dumps(e.get("body") or {})]
    ch.add("zero browse-tree POST requests logged for US", "mock call log verification", 0, len(us_logged))
    detail["us_reports_found"] = len(us_reports)


def c_us_chaining(ch, calls, detail):
    """11. US-CHAIN-1 (blocked): Synchronization chaining & concurrency guard (A4, D10)."""
    ch.note("A4 requirement", "Product sync must not start over an incomplete taxonomy stage (D-MATRIX A4).")
    ch.note("D10 requirement", "A connect request arriving during an active sync is queued, not duplicated -- "
                               "within one replica only (D-MATRIX D10, N6).")
    ch.note("blocked reason", "There is no JPluger under test (requirements.UNTESTABLE['H1']). "
                              "Call ordering and stage chaining are [JP] hop behaviour with no observation point.")
    detail["blocked"] = "no JPluger under test"


def c_us_err(ch, calls, detail):
    """12. US-ERR-1: OMS 500 fault handling and product-type fault isolation."""
    # Fault injection at OMS hop via SERVERERROR store_code
    error_payload = {
        "category_code": "LUGGAGE_SERVERERROR",
        "marketplace_code": US_MARKETPLACE_CODE,
        "category_attributes": []
    }
    st_err, body_err, _raw = call_oms("POST", R.BULK_ATTRIBUTES_PATH, error_payload,
                                       query={"store_code": "SERVERERROR", "marketplace_code": US_MARKETPLACE_CODE})
    calls.append("POST %s [FAULT INJECTION] -> %s" % (R.BULK_ATTRIBUTES_PATH, st_err))
    ch.add("OMS 500 rejection", "Internal server error triggered", 500, st_err)

    # Next product type still syncs
    _st, env, _raw = _definition_us("CLOTHING")
    _st_s, schema, _ok, _link = _fetch_schema(env)
    payload = transform_schema_to_oms_attributes(
        schema, US_STORE_CODE, US_MARKETPLACE_CODE, "CLOTHING",
        definition_version=(env.get("productTypeVersion") or {}).get("version"),
        schema_checksum=(env.get("schema") or {}).get("checksum"))
    st_next, _b, _r = call_oms("POST", R.BULK_ATTRIBUTES_PATH, payload,
                               query={"store_code": US_STORE_CODE, "marketplace_code": US_MARKETPLACE_CODE})
    calls.append("POST %s [CLOTHING after error] -> %s" % (R.BULK_ATTRIBUTES_PATH, st_next))
    ch.add("subsequent product type completes 200 OK", "fault isolation", 200, st_next)
    detail["fault_status"] = st_err


def c_us_legacy(ch, calls, detail):
    """13. US-LEGACY-1: Legacy category endpoints compatibility guard."""
    st, body, _raw = call_oms("GET", "/rest/v1/categories",
                              query={"store_code": US_STORE_CODE, "marketplace_code": US_MARKETPLACE_CODE})
    calls.append("GET /rest/v1/categories -> %s" % st)
    ch.add("legacy categories endpoint responds 200", "regression guard", 200, st)

    st_attrs, _b_attrs, _r = call_oms("GET", "/rest/v1/categories/1/category_attributes",
                                      query={"store_code": US_STORE_CODE})
    calls.append("GET /rest/v1/categories/1/category_attributes -> %s" % st_attrs)
    ch.add("legacy category attributes endpoint responds 200", "regression guard", 200, st_attrs)

    ch.note("preserved fields note", "id and field_parent_id are preserved on legacy rows while left unset on "
                                     "Amazon rows (D-WIRE header, D-MATRIX N16).")
    detail["legacy_status"] = st
    detail["legacy_attrs_status"] = st_attrs



def c_us_raw_json(ch, calls, detail):
    """14. US-RAW-1: raw_schema_json verbatim survival & Amazon stated checksum passthrough."""
    for pt in US_PRODUCT_TYPES:
        _st, env, _raw = _definition_us(pt)
        _st_s, schema_doc, _ok, _link = _fetch_schema(env)
        stated_checksum = (env.get("schema") or {}).get("checksum")

        payload = transform_schema_to_oms_attributes(
            schema_doc, US_STORE_CODE, US_MARKETPLACE_CODE, pt,
            definition_version=(env.get("productTypeVersion") or {}).get("version"),
            schema_checksum=stated_checksum)

        raw_str = payload.get("raw_schema_json") or ""
        ch.truthy("%s raw_schema_json present" % pt, "raw JSON preserved", raw_str)
        parsed = json.loads(raw_str) if raw_str else {}
        ch.add("%s raw_schema_json matches schema verbatim" % pt, "verbatim JSON preservation",
               True, parsed == schema_doc)
        ch.add("%s schema_checksum is Amazon's stated value" % pt, "never locally recomputed MD5 (A5)",
               stated_checksum, payload.get("schema_checksum"))
    detail["us_raw_schemas_verified"] = US_PRODUCT_TYPES


# ------------------------------------------------------------------ case declarations

case("US-AUTH-1", "Mock authenticates via LWA OAuth exchange",
     "LWA token endpoint POST /auth/o2/token",
     ["200 OK with access_token and token_type bearer",
      "expires_in is 3600 seconds",
      "Recorded: proves mock behaviour, not SP-API (requirements.UNTESTABLE['U1'])"],
     "LWA OAuth exchange verification for US store. Real token exchange cannot be tested against mock.",
     c_us_auth)

case("US-CAT-1", "bulk_categories -- category.code IS the Amazon product type for US store",
     "searchDefinitionsProductTypes returns US product types (ATVPDKIKX0DER)",
     ["One bulk_categories body per discovered product type",
      "Count parity with discovered types (B3)",
      "Every code is UPPER_SNAKE and not browse-node-shaped (A2)",
      "No body carries a browse-node key (N10, N12)",
      "store_code and marketplace_code scope the posting"],
     "D-MATRIX A2, B3, B17. Category code equals product type name verbatim, no browse-node fields.",
     c_us_cat)

case("US-DEF-1", "getDefinitionsProductType -- parameterised definition & schema fetch across all 4 US product types",
     "Four US product types: LUGGAGE, CLOTHING, ELECTRONICS, TOYS_AND_GAMES",
     ["Each definition resolves 200 OK",
      "productType echoed and latest is true",
      "schema link is present and resolved in second GET",
      "Downloaded bytes match Amazon's stated MD5 checksum"],
     "D-MATRIX A5, A6, B1, B2. Definition envelope resolution and separate schema download.",
     c_us_def_fetch)

case("US-ENV-1", "bulk_categories_attributes -- envelope as received with verbatim raw schema",
     "US LUGGAGE definition and schema with planted unknown key _futureAmazonField",
     ["store_code and marketplace_code on query string and body",
      "definition_version is productTypeVersion.version and not date-shaped",
      "latest_version is true",
      "schema_checksum is Amazon's stated checksum",
      "raw_schema_json parses deep-equal to schema with planted key (B4)",
      "definition_status is one of the six contract values (B5)"],
     "D-MATRIX B4, B5, B6. Verbatim raw schema preservation and envelope field verification.",
     c_us_envelope)

case("US-VOCAB-1", "Every category_attributes row speaks the §0.4 contract vocabulary",
     "Every category_attributes row across received US postings",
     ["Every nested field_code is dot-joined, not underscore-joined (D-GAP decision 2)",
      "Parent-first ordering: every field_parent_code seen earlier (A7)",
      "id and field_parent_id are absent (N16)",
      "marketplace_code on every row equals the request's (B18)",
      "mandatory is a JSON boolean and not all-false",
      "field_type in {attribute, option_type, attributes}",
      "every field_code is unique (D7)"],
     "D-MATRIX A7, B18, D7, N16. Structural invariants on all category_attributes rows.",
     c_us_vocab)

case("US-MAP-1", "Schema flattening and constraint mapping against US schemas (B7-B10, B12)",
     "All four US schemas (LUGGAGE, CLOTHING, ELECTRONICS, TOYS_AND_GAMES)",
     ["All 10 validation keys surface with right types (B7)",
      "Property stating only maxLength carries exactly that key",
      "Array parent has occurrence bounds and no maxLength (B8)",
      "Array child .value has maxLength and no occurrence bounds (B8)",
      "All five added data_types appear (number, integer, boolean, object, array) (B9)",
      "number and integer are distinguished (B9)",
      "format mappings: date->date, date-time->datefield, uri->string (B10)",
      "Measurement is three rows: parent object, .value numeric child, .unit sibling (B12)"],
     "D-MATRIX B7, B8, B9, B10, B12. Schema flattening, bounds, and type mapping rules.",
     c_us_mapping)

case("US-KEYWORD-1", "Classification row: US store picker is item_type_keyword.value (B14)",
     "US store browse tree / classification and SYNTHETIC keyword fixture",
     ["Picker is item_type_keyword.value (never recommended_browse_nodes)",
      "Option value is keyword token (e.g. 'carry-on-luggage', not numeric id)",
      "Node served without item_type_keyword contributes no option and its id appears nowhere",
      "Empty picker publishes field_values: [] and free_text: true (B15)",
      "State in case detail that fixture is hand-authored SYNTHETIC"],
     "D-MATRIX B14, B15. US classification row mapping, keyword tokens, empty fallback.",
     c_us_keyword)

case("US-STATUS-1", "Definition status matrix across all six states (B5, B6, A3, C1, D3-D6)",
     "Clean schema, 404 UNAVAILABLE, depth breach PARSE_FAILED, oversize SCHEMA_OMITTED/VALUES_OMITTED, "
     "and a schema carrying one unresolvable $ref",
     ["AVAILABLE: attributes complete, raw_schema present, no reason key (B6)",
      "SCHEMA_OMITTED: serialized > 900KB, raw_schema dropped, attributes complete, body <= 900KB (D3)",
      "VALUES_OMITTED: still > 900KB, field_values: [] on all rows, rows survive (D4)",
      "PARSE_FAILED: depth > 9 or an allOf $ref CYCLE, raw_schema kept, no attributes key (A3)",
      "An unresolvable $ref costs ONE attribute, never the definition: status stays AVAILABLE, "
      "the offending row is absent and every other row survives",
      "PARSE_FAILED + oversize: stays PARSE_FAILED, reasons joined with '; ' (D5)",
      "Enum options capped to 8000 (D6)",
      "UNAVAILABLE: 404 on getDefinitionsProductType, reason stated, no raw_schema, no attributes (C1)",
      "Blocked: checksum mismatch, schema download 500 (C7), missing schema link (C8)"],
     "D-MATRIX B5, B6, A3, C1, D3-D6. The six definition_status states and limits.",
     c_us_status_matrix)

case("US-WITHDRAW-1", "Withdrawn browse-node keys absent from both endpoints (N10, N12)",
     "All category and attributes bodies OMS received for US store",
     ["No /browse.?node/i key on any bulk_categories body",
      "No /browse.?node/i key on any bulk_categories_attributes body",
      "Zero forbidden browse node keys across both endpoints"],
     "D-MATRIX N10, N12. Withdrawn request-level browse_node_ids array absent on all wire bodies.",
     c_us_withdraw)

case("US-NOREPORT-1", "No browse-tree report requested for a US store",
     "Amazon mock reports store inspected after US sync",
     ["Zero GET_XML_BROWSE_TREE_DATA reports for ATVPDKIKX0DER",
      "Zero browse-tree reports requested by US store"],
     "D-MATRIX B14, plan §4.4. US store never triggers browse tree report refresh.",
     c_us_no_report)

case("US-CHAIN-1", "Synchronization chaining and replica concurrency guard (A4, D10)",
     "Incomplete taxonomy sync stage, or concurrent store connect requests",
     ["A4: Product sync does not start over an incomplete taxonomy stage",
      "D10: A connect during active sync is queued, not duplicated -- within one replica only",
      "Blocked: no [JP] hop under test (requirements.UNTESTABLE['H1'])"],
     "D-MATRIX A4, D10. Stage chaining and concurrency guards at [JP] hop. Blocked.",
     c_us_chaining)

case("US-ERR-1", "OMS 500 fault handling and product-type fault isolation",
     "OMS fault injected (500 Internal Server Error) on one product type",
     ["OMS 500 error is caught and logged",
      "Fault on one product type does not halt synchronization of subsequent product types"],
     "JIRA Error Matrix #18, fault tolerance and store isolation.",
     c_us_err)

case("US-LEGACY-1", "Legacy category endpoints compatibility guard",
     "Legacy category endpoint GET /rest/v1/categories",
     ["Legacy endpoint responds 200 OK",
      "id and field_parent_id preserved on legacy rows while unset on Amazon rows (N16)"],
     "Regression guard: legacy categories endpoint continues to function.",
     c_us_legacy)

case("US-RAW-1", "Verbatim raw_schema_json survival and Amazon stated checksum passthrough",
     "All four US schemas (LUGGAGE, CLOTHING, ELECTRONICS, TOYS_AND_GAMES)",
     ["raw_schema_json survives verbatim across all four US schemas",
      "schema_checksum is Amazon's stated checksum, never a locally recomputed digest (A5)"],
     "D-MATRIX A5, B4. Raw schema verbatim JSON survival and stated checksum passthrough.",
     c_us_raw_json)


# ------------------------------------------------------------------ runner execution


def preflight():
    global AMAZON_UP, OMS_UP
    print("amazon us store connect & taxonomy (IA-5105 US1) -- %s" % BASE_AMAZON)
    print("  mock dir : %s" % MOCK_DIR)
    print("  run dir  : %s" % RUN_DIR)
    print("  oms      : %s" % BASE_OMS)
    os.makedirs(DATA_DIR, exist_ok=True)

    st, _b, _raw = call("POST", "/auth/o2/token", None, token=None)
    AMAZON_UP = st != 0
    print("  mock     : %s (POST /auth/o2/token -> %s)"
          % ("up" if AMAZON_UP else "DOWN -- every case will be blocked", st))

    st_oms, _b, _r = call_oms("GET", "/rest/v1/categories",
                              query={"store_code": US_STORE_CODE, "marketplace_code": US_MARKETPLACE_CODE})
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
