#!/usr/bin/env python3
"""IA-5105-US1: Amazon taxonomy discovery, the category payload, and the browse-tree report.

Rewritten 2026-09-13 against the IA-5105 deliverables (wiki `plan/amazon-test-suites`). The
expectations live in requirements.py with the document and section each came from; this file makes
the calls and judges what arrived.

WHAT THIS SUITE OWNS, out of the 47 rows of `IA-5105-e2e-coverage-matrix.md`:
    A2   category.code IS the Amazon product type                        TAX-CAT-1
    A5   a definition failing Amazon's checksum is not published         TAX-CKSUM   (both halves;
                                                                                     wire half below)
    A6   a definition Amazon does not mark latest is refused             TAX-LATEST-1
    B1   search -> definition -> schema link, once each, in order        TAX-SEQ-1
    B2   the getDefinitionsProductType request parameters                DEF-PARAMS-1
    B3   search is scoped to one marketplace and asks for everything     SRCH-1
    B16  the browse tree uses the XML report and the full report flow    TAX-BT-REPORT
    B17  every product type reaches OMS as a category before attributes  TAX-CAT-ORDER-1
    B19  a node wider than four children truncates and says so           TAX-AU-1 (the precondition)
    C1   a 404 definition is UNAVAILABLE and the run continues           TAX-404 (the Amazon half)
    C6   an empty product-type catalogue is an answer, not a failure     SRCH-EMPTY-1
    C7   a schema-download failure is distinguished from definition fail TAX-DL-FAIL-1
    C8   a definition carrying no schema link fails cleanly              TAX-NO-LINK-1
    C9   a failed browse-tree report leaves definitions untouched        TAX-BT-FATAL-1
    A1   marketplace isolation                                           TAX-EU-1, TAX-CAT-3
    FR-3 / N11  the flat-file browse report is never requested           TAX-BT-REPORT
    FR-20       a failed report must not substitute another marketplace  TAX-BT-ISO-1
    JIRA section 12, "Duplicate browse node -> upsert existing node"     TAX-BT-DUP-1

WHAT A GREEN RUN HERE DOES NOT PROVE (the IA-5109 form, and requirements.UNTESTABLE states each):

 1. **It does not prove anything about JPluger.** There is no JPluger under test - amazon/README.md
    says so: transformer.py is "a local stand-in for the JPluger Amazon integration, which this
    harness cannot start". This suite is the only client Amazon sees, so every [JP] row (retry
    budgets, Redis checkpoints, operator traces, rate pacing, queueing) has no observation point at
    all, and the call-shape rows (B1, B2, B3) are proven only of the mock: that it records the
    distinction, so the row becomes provable the day a real client points at it. Each such case
    carries `does_not_prove` in its own detail.
 2. **It does not prove the negative branches of C2, C3 and C5.** The Amazon mock
    serves no 429/500/403 on the definitions routes. Those fixtures do not exist and this pane must not
    add them: the mock is shared, and the authority rule forbids editing a mock so that a case can
    pass. The negative branches of A6, C6, C7, and C8 are now steered via safe marker-keyed rules in
    amazon.mock.json, while A5's mismatch branch is induced from two mock-served bodies at one link
    (TAX-CKSUM) and C9 is driven on CANCELLED (TAX-BT-FATAL-1). None changes a route or response for
    another suite.
 3. **It does not prove the six `definition_status` values reach OMS.** The stand-in transformer
    emits no `definition_status` key at all, so B5, B6, A3, D3, D4 and D5 fail red wherever they are
    asserted. That is the collision, reported as such.
 4. **The dotted `field_code` collision is deliberate.** Decision 2 of the gap report makes nested
    codes dot-joined; transformer.py still joins them with an underscore
    (`field_code_of: dotted_path.replace(".", "_")`). Every case that reads a nested code fails red
    until the producer is corrected. Softening it would hide the one change the ticket turns on.
 5. **Three fixtures are SYNTHETIC** (amazon/README.md): US `LUGGAGE`, FR `SHOES` and everything
    outside DE `PRODUCT`, ES `PRODUCT` and AU `AUTO_PART`. Nothing observed through them may be
    cited as Amazon's behaviour.

Runner contract: TESTING.md and wiki `plan/amazon-test-suites#01-harness`.
Publishes to amazon/test-results/IA-5105-US1-taxonomy/run-<stamp>/results.json.

Usage:
  python3 amazon/IA-5105-US1/suite-taxonomy.py
  python3 amazon/IA-5105-US1/suite-taxonomy.py --list
  python3 amazon/IA-5105-US1/suite-taxonomy.py TAX-CAT-1 SRCH-1        # only the cases named
  BASE_AMAZON=http://127.0.0.1:23103 BASE_OMS=http://127.0.0.1:23001 \
      python3 amazon/IA-5105-US1/suite-taxonomy.py

Needs the Amazon mock (`python3 mock.py amazon`) and, for the cases that post, the Anchanto OMS mock
(`python3 mock.py anchanto-oms`). A mock that is down makes its cases `blocked`, never `pass`.
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

# BASE_AMAZON is the name the sibling suites use; BASE stays readable for the older invocation.
BASE_AMAZON = os.environ.get("BASE_AMAZON", os.environ.get("BASE", "http://127.0.0.1:23103")).rstrip("/")
BASE = BASE_AMAZON
BASE_OMS = os.environ.get("BASE_OMS", "http://127.0.0.1:23001").rstrip("/")
SUITE = os.environ.get("SUITE", "IA-5105-US1-taxonomy")
KEEP = "--keep-state" in sys.argv
LIST_ONLY = "--list" in sys.argv
WANTED_CASES = set(a for a in sys.argv[1:] if not a.startswith("-"))

HERE = os.path.dirname(os.path.abspath(__file__))
MOCK_DIR = os.path.dirname(HERE)  # amazon/ -- mock config, state and test-results live one level up
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
    build_definition_payload,
    transform_schema_to_oms_attributes,
)

# The stores this suite connects. D-GAP decision 11 names FR, DE, JP and US as the ticket's
# marketplaces; ES and AU ride along because D-PLAN phase 2 measured the width cap on their captures.
STORES_UNDER_TEST = [
    ("US", "amazon_sp_us", "SS0000US", "LUGGAGE"),
    ("FR", "amazon_sp_fr", "SS0000FR", "SHOES"),
    ("DE", "amazon_sp_de", "SS0000DE", "PRODUCT"),
    ("ES", "amazon_sp_es", "SS0000ES", "PRODUCT"),
    ("AU", "amazon_sp_au", "SS0000AU", "AUTO_PART"),
]

# The four marketplaces the ticket actually names, for the rows that must hold on all of them.
TICKET_STORES = [s for s in STORES_UNDER_TEST if s[1] in
                 ("amazon_sp_us", "amazon_sp_fr", "amazon_sp_de", "amazon_sp_jp")]


# ------------------------------------------------------------------ transport


def call(method, path, body=None, token="mock_sp_api_access_token", timeout=120):
    """One call at the Amazon mock. `path` may be an absolute URL: its host is dropped.

    requirements.UNTESTABLE["H3"] - amazon.mock.json hardcodes `127.0.0.1:23103` into every schema
    and report link, so a suite on another port that followed the link verbatim would read another
    process's mock and report its fixtures as this run's evidence.
    """
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
    """The name suite-all.py reaches for when it probes this suite's mock."""
    return call(method, path, body, token)


def call_oms(method, path, body=None, query=None, token="f1a6c2d8e40b7935a1c6d2f8b04e7395"):
    """One call at the Anchanto OMS mock, where the category half of this ticket ends."""
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
        "(amazon/README.md) and this suite is the only client Amazon sees, so B1/B2/B3 are proven "
        "of the mock only and every [JP] row is blocked (requirements.UNTESTABLE['H1']).",
        "The negative branches of C2, C3 and C5: the Amazon mock serves no 429/500/403 fixture "
        "on definitions routes and this pane must not add one to a shared mock "
        "(requirements.UNTESTABLE['H2']).",
        "Anything about what OMS does with a body it received (D-MATRIX U2, U3). Only what was sent "
        "is asserted.",
        "Amazon's real behaviour through a SYNTHETIC fixture: US LUGGAGE and FR SHOES are "
        "hand-authored (amazon/README.md).",
    ],
}

# Set by preflight; suite-all.py sets them directly when it drives these cases.
AMAZON_UP = False
OMS_UP = False

# Cases whose verdict is fixed regardless of their checks, because what they would score cannot be
# driven here. TESTING.md keeps `blocked` distinct from `fail` for exactly this.
BLOCKED_CASES = set()

# Cases that cannot be judged without the OMS mock.
NEEDS_OMS = {
    "TAX-CAT-1", "TAX-CAT-3", "TAX-CAT-ORDER-1", "TAX-ATTR-INV-1",
    "TAX-BT-FATAL-1", "TAX-LATEST-1", "TAX-DL-FAIL-1", "TAX-NO-LINK-1",
}


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
        "name": "IA-5105-US1: Amazon taxonomy discovery, categories and the browse-tree report",
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
        """Records a fact that is not scored - a fixture gap, a limitation, a measured number."""
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
            "calls": [], "detail": {"blocked_reason":
                                    "the Amazon SP-API mock is not answering at %s -- start it with "
                                    "`python3 mock.py amazon`. A suite that cannot run is reported "
                                    "as such, never claimed green." % BASE_AMAZON},
            "summary": "blocked -- Amazon mock offline"}
        return "blocked"
    if c["id"] in NEEDS_OMS and not OMS_UP:
        RESULTS[c["id"]] = {
            "verdict": "blocked",
            "checks": [{"label": "OMS mock reachable", "what": "the mock answers",
                        "expected": "online", "actual": "offline", "ok": False}],
            "calls": [], "detail": {"blocked_reason":
                                    "the Anchanto OMS mock is not answering at %s -- start it with "
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


# ------------------------------------------------------------------ Amazon calls


def _search(marketplace_id):
    return call("GET", "/definitions/2020-09-01/productTypes?marketplaceIds=%s" % marketplace_id)


def _definition(product_type, marketplace_id, locale):
    """The request D-MATRIX B2 states, parameter for parameter. `sellerId` and `productTypeVersion`
    are deliberately absent: B2 records `sellerId=null` as the current state, flagged against O1, and
    an absent `productTypeVersion` is how LATEST is requested."""
    return call("GET", "/definitions/2020-09-01/productTypes/%s?marketplaceIds=%s"
                       "&requirements=%s&requirementsEnforced=%s&locale=%s&parentageLevel=%s"
                       % (product_type, marketplace_id,
                          R.DEFINITION_REQUEST_PARAMS["requirements"],
                          R.DEFINITION_REQUEST_PARAMS["requirementsEnforced"], locale,
                          R.DEFINITION_REQUEST_PARAMS["parentageLevel"]))


def _fetch_schema(envelope):
    """Resolves the schema link and verifies Amazon's stated checksum against the bytes served.

    The two gates D-MATRIX A5 and A6 name, in the order `AmazonDefinitionsUtility.fetchDefinition`
    applies them: a definition Amazon does not mark latest is refused before its bytes are read, and
    bytes that fail the stated checksum are never published.
    """
    link = ((envelope.get("schema") or {}).get("link") or {}).get("resource", "")
    status, body, raw = call("GET", link)
    stated = (envelope.get("schema") or {}).get("checksum") or ""
    import base64
    matches = (not stated) or stated == hashlib.md5(raw).hexdigest() \
        or stated == base64.b64encode(hashlib.md5(raw).digest()).decode()
    return status, body, matches, link


def _schema_downloader(resource):
    """The downloader `transformer.build_definition_payload` fetches the schema link through.

    Injected rather than left to the producer because the mock hardcodes `127.0.0.1:23103` into
    every `schema.link.resource`; `R.schema_link_path` strips that host so the bytes come from THIS
    run's mock rather than whichever process happens to hold 23103 (REWRITE-PLAN §0.9.4).
    """
    status, body, raw = call("GET", R.schema_link_path(resource))

    return status, body, raw


def _browse_tree(marketplace_id, with_report_options=True, report_type=None):
    """The whole Reports flow D-MATRIX B16 states: createReport -> poll -> document -> download.

    `with_report_options=False` reproduces the trap amazon/README.md records: omitting
    `reportOptions.MarketplaceId` makes Amazon serve the seller's DEFAULT store's tree to every
    store, which is how JIRA FR-20's "do not substitute another marketplace's browse tree" fails
    silently.
    """
    body = {"reportType": report_type or R.BROWSE_TREE_REPORT_TYPE,
            "marketplaceIds": [marketplace_id]}
    if with_report_options:
        body["reportOptions"] = {"MarketplaceId": marketplace_id}
    st1, created, _ = call("POST", "/reports/2021-06-30/reports", body)
    report_id = created.get("reportId") if isinstance(created, dict) else None
    if not report_id:
        return {"create_status": st1, "report_id": None}
    st2, status_body, _ = call("GET", "/reports/2021-06-30/reports/%s" % report_id)
    doc_id = status_body.get("reportDocumentId") if isinstance(status_body, dict) else None
    out = {"create_status": st1, "report_id": report_id, "poll_status": st2,
           "processing_status": (status_body or {}).get("processingStatus"),
           "document_id": doc_id, "xml": b"", "download_status": None, "url": None}
    if not doc_id:
        return out
    st3, doc, _ = call("GET", "/reports/2021-06-30/documents/%s" % doc_id)
    url = doc.get("url") if isinstance(doc, dict) else None
    out["url"] = url
    if url:
        st4, _b, raw = call("GET", url)
        out["download_status"], out["xml"] = st4, raw
    out["doc_status"] = st3
    return out


def _categories_received(since=None, refresh=True):
    """bulk_categories postings only. `/rest/v1/bulk_categories` is a prefix of
    `/rest/v1/bulk_categories_attributes`, so a substring read returns both."""
    return [e for e in R.oms_received(BASE_OMS, R.BULK_CATEGORIES_PATH, refresh=refresh, since=since)
            if R.BULK_ATTRIBUTES_PATH not in e["url"]]


def _post_categories(store_code, marketplace_code, calls):
    """searchDefinitionsProductTypes, then one bulk_categories POST per product type it returned.

    One call per product type: D-GAP section 1.2 keeps the existing endpoint, whose body root is a
    single category object, so "one flat category row per product type" is one POST each.
    """
    marketplace_id = R.MARKETPLACE_IDS[marketplace_code]
    mark = R.oms_high_water(BASE_OMS)
    status, body, _raw = _search(marketplace_id)
    calls.append("GET searchDefinitionsProductTypes[%s] -> %s" % (marketplace_code, status))
    discovered = {pt.get("name"): pt.get("displayName")
                  for pt in (body.get("productTypes") or [])}

    for name, display in discovered.items():
        payload = build_bulk_category_payload(store_code, marketplace_code, name, display or name)
        st, _b, _r = call_oms("POST", R.BULK_CATEGORIES_PATH, payload,
                              query={"store_code": store_code})
        calls.append("POST %s [%s %s] -> %s" % (R.BULK_CATEGORIES_PATH, marketplace_code, name, st))

    return discovered, _categories_received(since=mark)


def _category_of(entry):
    """The category object of a received bulk_categories body.

    D-MATRIX A2 asserts on `code`; the OMS contract nests it under `category`, so the read states
    which shape it found rather than assuming one.
    """
    body = entry.get("body") or {}
    return body.get("category") if isinstance(body.get("category"), dict) else body


# ------------------------------------------------------------------ cases


def c_search_by_market(ch, calls, detail):
    """B3. The search is scoped to one marketplace and asks for the complete set."""
    # The Amazon mock's log persists across runs (mock-data/api-calls.har.json), so a read without a
    # high-water mark judges this case on calls some earlier run fired.
    mark = R.oms_high_water(BASE_AMAZON)
    for region, marketplace_code, _store, expected_type in STORES_UNDER_TEST:
        marketplace_id = R.MARKETPLACE_IDS[marketplace_code]
        status, body, _raw = _search(marketplace_id)
        calls.append("GET searchDefinitionsProductTypes[%s] -> %s" % (region, status))
        ch.add("%s status" % region, "the search succeeds", 200, status)

        names = [pt.get("name") for pt in (body.get("productTypes") or [])]
        ch.add("%s discovers its own catalogue" % region,
               "the store's own product type, not another marketplace's",
               True, expected_type in names)
        ch.add("%s every entry is scoped to the requested marketplace" % region,
               "D-MATRIX B3: the search is scoped to the store's marketplace id", [],
               [pt.get("name") for pt in (body.get("productTypes") or [])
                if marketplace_id not in (pt.get("marketplaceIds") or [])])
        ch.add("%s search-level productTypeVersion is a bare string" % region,
               "distinct from the {version, latest, releaseCandidate} object the definition "
               "returns under the same field name", True,
               isinstance(body.get("productTypeVersion"), str))

    logged = R.amazon_received(BASE_AMAZON, "/definitions/2020-09-01/productTypes?", since=mark)
    ch.add("every search carried exactly one marketplaceIds",
           "D-MATRIX B3: marketplaceIds = exactly one id, that of the store's marketplace", [],
           [e["url"] for e in logged if len(e["query"].get("marketplaceIds", "").split(",")) != 1])
    ch.add("no search carried keywords or a page token",
           "D-MATRIX B3 asks for the complete set without keywords; N15 closes pagination - "
           "ProductTypeList v2020-09-01 carries no page token", [],
           sorted({p for e in logged for p in R.SEARCH_REQUEST_ABSENT_PARAMS if p in e["query"]}))
    ch.note("does not prove", "The request is this suite's own. What is proven is that the mock "
                              "records the distinction, so the row becomes provable the day a real "
                              "client points at it (requirements.UNTESTABLE['H1']).")
    detail["searches_logged"] = len(logged)


def c_definition_request_parameters(ch, calls, detail):
    """B2. Every definition request carries the parameters the matrix states, and no others."""
    # Scoped to this case's own calls: the mock's log outlives the run that wrote it.
    mark = R.oms_high_water(BASE_AMAZON)
    for region, marketplace_code, _store, product_type in STORES_UNDER_TEST:
        marketplace_id = R.MARKETPLACE_IDS[marketplace_code]
        locale = R.DEFINITIONS_LOCALE_MAP[marketplace_code]
        status, envelope, _raw = _definition(product_type, marketplace_id, locale)
        calls.append("GET getDefinitionsProductType[%s/%s] -> %s" % (region, product_type, status))
        ch.add("%s status" % region, "the definition envelope resolves", 200, status)
        ch.add("%s productType echoed" % region, "matches the path segment",
               product_type, envelope.get("productType"))
        ch.add("%s marketplaceIds echoed" % region, "exactly the one id for the store's marketplace",
               [marketplace_id], envelope.get("marketplaceIds"))
        ch.add("%s locale echoed" % region,
               "D-MATRIX B2: locale per AMAZON_DEFINITIONS_LOCALE_MAP", locale, envelope.get("locale"))
        ch.add("%s requirements echoed" % region, "D-MATRIX B2: LISTING_PRODUCT_ONLY",
               R.DEFINITION_REQUEST_PARAMS["requirements"], envelope.get("requirements"))
        ch.add("%s requirementsEnforced echoed" % region, "D-MATRIX B2: ENFORCED",
               R.DEFINITION_REQUEST_PARAMS["requirementsEnforced"],
               envelope.get("requirementsEnforced"))
        ch.add("%s schema is a link, not inline" % region,
               "D-MATRIX B1: the schema fetch is a second, separate call to the link's resource",
               True, "link" in (envelope.get("schema") or {}))
        version = envelope.get("productTypeVersion") or {}
        ch.add("%s productTypeVersion is an object" % region,
               "the per-definition shape {version, latest, releaseCandidate}",
               True, isinstance(version, dict))
        ch.add("%s latest is true" % region,
               "D-MATRIX A6: a definition Amazon does not mark latest is refused",
               True, version.get("latest") is True)

    logged = R.amazon_received(BASE_AMAZON, "/definitions/2020-09-01/productTypes/", since=mark)
    ch.add("parentageLevel=NONE on every definition request", "D-MATRIX B2", [],
           [e["url"] for e in logged
            if e["query"].get("parentageLevel") != R.DEFINITION_REQUEST_PARAMS["parentageLevel"]])
    ch.add("sellerId and productTypeVersion absent on every request",
           "D-MATRIX B2: sellerId null (flagged against O1) and productTypeVersion unset = LATEST",
           [], sorted({p for e in logged for p in R.DEFINITION_REQUEST_ABSENT_PARAMS
                       if p in e["query"]}))
    ch.note("does not prove", "The request is this suite's own - see "
                              "requirements.UNTESTABLE['H1']. O1 is open: whether supplying sellerId "
                              "would change what Amazon returns for the classification attributes "
                              "is untestable here (D-MATRIX U6).")
    detail["definition_requests_logged"] = len(logged)


def c_call_sequence(ch, calls, detail):
    """B1. search once, then one definition per product type, then one schema fetch per definition."""
    marketplace_code, region = "amazon_sp_fr", "FR"
    marketplace_id = R.MARKETPLACE_IDS[marketplace_code]
    locale = R.DEFINITIONS_LOCALE_MAP[marketplace_code]
    mark = R.oms_high_water(BASE_AMAZON)

    status, body, _raw = _search(marketplace_id)
    calls.append("GET searchDefinitionsProductTypes[%s] -> %s" % (region, status))
    discovered = [pt.get("name") for pt in (body.get("productTypes") or [])]

    for product_type in discovered:
        _st, envelope, _raw = _definition(product_type, marketplace_id, locale)
        calls.append("GET getDefinitionsProductType[%s] -> %s" % (product_type, _st))
        st_schema, _schema, _ok, link = _fetch_schema(envelope)
        calls.append("GET %s -> %s" % (R.schema_link_path(link), st_schema))

    searches = R.amazon_received(BASE_AMAZON, "/definitions/2020-09-01/productTypes?", since=mark)
    definitions = R.amazon_received(BASE_AMAZON, "/definitions/2020-09-01/productTypes/", since=mark)
    schemas = R.amazon_received(BASE_AMAZON, "/s3/ptd-schema/", since=mark)

    ch.add("exactly one search", "D-MATRIX B1: searchDefinitionsProductTypes once", 1, len(searches))
    ch.add("one definition call per product type", "N per distinct code",
           len(discovered), len(definitions))
    ch.add("definitions follow the search's order", "D-MATRIX B1: in the search's order",
           discovered, [urllib.parse.urlparse(e["url"]).path.rsplit("/", 1)[-1] for e in definitions])
    ch.add("one schema-document fetch per definition", "a second, separate call to the link",
           len(discovered), len(schemas))
    ch.add("the search precedes every definition call", "D-MATRIX B1 ordering", True,
           all(s["seq"] > searches[0]["seq"] for s in definitions) if searches and definitions else False)
    ch.add("each schema fetch follows its own definition call", "per product type ordering", True,
           all(schemas[i]["seq"] > definitions[i]["seq"] for i in range(min(len(schemas), len(definitions))))
           and len(schemas) == len(definitions))
    ch.add("the schema is fetched from the link's own resource",
           "not inlined in the definition response", [],
           [e["url"] for e in schemas if "/s3/ptd-schema/" not in e["url"]])
    ch.note("does not prove", "This suite made these calls. The row is proven of the mock's log, "
                              "not of JPluger (requirements.UNTESTABLE['H1']).")
    detail["discovered"] = discovered


def c_de_es_isolation(ch, calls, detail):
    """A1, at the Amazon hop. The same product type code, two marketplaces, two definitions."""
    envelopes, schemas = {}, {}
    for marketplace_code in ("amazon_sp_de", "amazon_sp_es"):
        marketplace_id = R.MARKETPLACE_IDS[marketplace_code]
        locale = R.DEFINITIONS_LOCALE_MAP[marketplace_code]
        st, envelope, _raw = _definition("PRODUCT", marketplace_id, locale)
        calls.append("GET getDefinitionsProductType[%s/PRODUCT] -> %s" % (marketplace_code, st))
        ch.add("%s definition resolves" % marketplace_code, "200 OK", 200, st)
        envelopes[marketplace_code] = envelope
        st_schema, schema, checksum_ok, link = _fetch_schema(envelope)
        calls.append("GET %s -> %s" % (R.schema_link_path(link), st_schema))
        ch.add("%s schema resolves" % marketplace_code, "the second GET returns the JSON Schema",
               200, st_schema)
        ch.add("%s checksum verifies" % marketplace_code,
               "D-MATRIX A5: the downloaded bytes match Amazon's stated checksum",
               True, checksum_ok)
        schemas[marketplace_code] = schema

    de, es = envelopes["amazon_sp_de"], envelopes["amazon_sp_es"]
    ch.add("the schema links differ", "the marketplaceId travels on the link, so a client keyed on "
           "productType alone collapses two sellers' categories", True,
           de["schema"]["link"]["resource"] != es["schema"]["link"]["resource"])
    ch.add("definition_version differs", "D-MATRIX A1: distinct definition_version per marketplace",
           True, de["productTypeVersion"]["version"] != es["productTypeVersion"]["version"])
    ch.add("schema_checksum differs", "D-MATRIX A1: distinct schema_checksum per marketplace",
           True, de["schema"]["checksum"] != es["schema"]["checksum"])
    ch.add("the locales differ", "each store asks in its own language",
           ("de_DE", "es_ES"), (de.get("locale"), es.get("locale")))

    de_props = set((schemas["amazon_sp_de"].get("properties") or {}))
    es_props = set((schemas["amazon_sp_es"].get("properties") or {}))
    ch.add("the property sets genuinely differ",
           "D-MATRIX A1: assert on the CONTENT, never on an echoed marketplaceId alone - an "
           "implementation that fetched one twice and stamped the second must fail this row",
           True, de_props != es_props)
    detail["de_only"] = sorted(de_props - es_props)[:10]
    detail["es_only"] = sorted(es_props - de_props)[:10]


def c_width_cap_preconditions(ch, calls, detail):
    """B19's precondition: which captures breach the four-child cap, and which must not."""
    wide_by_market = {}
    for region, marketplace_code, _store, product_type in STORES_UNDER_TEST:
        marketplace_id = R.MARKETPLACE_IDS[marketplace_code]
        st, envelope, _raw = _definition(product_type, marketplace_id,
                                         R.DEFINITIONS_LOCALE_MAP[marketplace_code])
        st_schema, schema, _ok, link = _fetch_schema(envelope)
        calls.append("GET %s -> %s" % (R.schema_link_path(link), st_schema))
        wide = R.wide_nodes(schema)
        wide_by_market[marketplace_code] = wide
        ch.add("%s nesting stays inside the depth cap" % region,
               "D-GAP decision 3: maximum nesting depth %d; D-RECON section 2.2 measures every real "
               "capture at 4 or less" % R.DEFINITIONS_MAX_NESTING_DEPTH,
               True, R.max_nesting_depth(schema) <= R.DEFINITIONS_MAX_NESTING_DEPTH)
        detail["%s_depth" % marketplace_code] = R.max_nesting_depth(schema)
        detail["%s_wide_nodes" % marketplace_code] = wide

    au = wide_by_market.get("amazon_sp_au", {})
    ch.add("AU purchasable_offer states 13 children",
           "D-MATRIX B19 and D-PLAN phase 2 measured this number on this capture",
           13, au.get("purchasable_offer"))
    ch.add("AU breaches the cap at the four nodes the plan names",
           "D-PLAN phase 2: fulfillment_availability, purchasable_offer, "
           "supplemental_condition_information and item_display_dimensions. Its fifth wide node, "
           "purchasable_offer.variable_weight_based_price, reports nothing because capping its "
           "parent means the flattener never descends to it",
           ["fulfillment_availability", "item_display_dimensions", "purchasable_offer",
            "supplemental_condition_information"],
           sorted(k for k in au if "." not in k))
    ch.add("the ticket's own marketplaces breach nothing",
           "D-MATRIX B19's regression guard: the cap must be invisible on FR, DE and US, whose "
           "widest captured node is exactly %d" % R.DEFINITIONS_MAX_CHILDREN_PER_NODE, [],
           sorted(k for m in ("amazon_sp_fr", "amazon_sp_de", "amazon_sp_us")
                  for k in wide_by_market.get(m, {})))
    ch.note("expected reason string",
            "A definition that truncates publishes AVAILABLE and names the node: %r. Several are "
            "joined by %r (D-WIRE section 1.2, D-GAP decision 4)."
            % (R.WIDTH_REASON_TEMPLATE % ("purchasable_offer", 13,
                                          R.DEFINITIONS_MAX_CHILDREN_PER_NODE),
               R.STATUS_REASON_JOIN))
    ch.note("does not prove", "Whether the producer truncates, and whether it names the node in "
                              "definition_status_reason, is asserted at the wire by the connect "
                              "suites. This case proves only that the fixtures B19 needs are the "
                              "ones the plan measured.")


def c_definition_not_found(ch, calls, detail):
    """C1, the Amazon half: Amazon serves no definition for this product type."""
    status, body, _raw = _definition("NOTFOUND-WIDGET", R.US_MARKETPLACE_ID, "en_US")
    calls.append("GET getDefinitionsProductType[NOTFOUND marker] -> %s" % status)
    ch.add("status is 404", "D-WIRE section 1.1: UNAVAILABLE is HTTP 404 on "
           "getDefinitionsProductType", 404, status)
    ch.truthy("structured errors payload", "an error body support can read", body.get("errors"))
    ch.note("the wire consequence", "That 404 must arrive at OMS as definition_status %r with a "
                                    "reason naming the product type (%r...), no raw_schema_json and "
                                    "NO category_attributes key at all - and it must not be folded "
                                    "into %r, which means a retry is owed. Asserted at the wire by "
                                    "the connect suites (D-MATRIX C1, B5, B6)."
            % ("UNAVAILABLE", R.STATUS_REASONS["unavailable_prefix"], "FETCH_FAILED"))
    ch.note("does not prove", "That the 404 is NOT retried. D-MATRIX C1 asks for the retry count at "
                              "the [JP] hop and there is no JPluger under test "
                              "(requirements.UNTESTABLE['H1']).")
    ch.note("nor is the scenario realistic", "D-MATRIX section 4: Amazon documents "
                                             "searchDefinitionsProductTypes as returning only "
                                             "product types that HAVE definitions, so a 404 for a "
                                             "type the search just returned indicates a malformed "
                                             "request rather than a schema-less product type. The "
                                             "row proves the handling, not the scenario.")


def c_checksum_verification(ch, calls, detail):
    """A5. Amazon's stated checksum is verified against the bytes served at the link."""
    st, envelope, _raw = _definition("LUGGAGE", R.US_MARKETPLACE_ID, "en_US")
    calls.append("GET getDefinitionsProductType[US/LUGGAGE] -> %s" % st)
    stated = (envelope.get("schema") or {}).get("checksum")
    ch.truthy("US LUGGAGE states a checksum", "a fixture with a real MD5 to verify against", stated)

    st_schema, _schema, matches, link = _fetch_schema(envelope)
    calls.append("GET %s -> %s" % (R.schema_link_path(link), st_schema))
    ch.add("the downloaded bytes match the stated checksum",
           "D-MATRIX A5: unverified bytes never reach OMS", True, matches)

    st_fb, fallback, _raw = _definition("SPEAKER", R.US_MARKETPLACE_ID, "en_US")
    calls.append("GET getDefinitionsProductType[unconfigured productType] -> %s" % st_fb)
    ch.add("the generic fallback still answers", "an unconfigured product type resolves", 200, st_fb)
    ch.add("the fallback states no checksum",
           "amazon/README.md: a static body can never hash to a fixed checksum computed ahead of "
           "time, so empty is the documented 'Amazon stated none' pass-through and checksum "
           "verification fails open", "", (fallback.get("schema") or {}).get("checksum"))

    # The negative half, induced rather than fixtured. The mock keys the schema route on
    # (productType, marketplaceId), so the SAME path served without the query answers the generic
    # fallback document instead of the LUGGAGE capture: two mock-served bodies at one link, and the
    # stated checksum can only match one of them. No rule and no response changes for anyone.
    bare_link = link.split("?")[0]
    _st_full, _body_full, raw_full = call("GET", link)
    st_bare, _body_bare, raw_bare = call("GET", bare_link)
    calls.append("GET %s [stated link, marketplaceId dropped] -> %s"
                 % (R.schema_link_path(bare_link), st_bare))
    bare_digest = hashlib.md5(raw_bare).hexdigest()
    ch.add("the two bodies at that path are genuinely different documents",
           "an induced mismatch is worth nothing if both reads return the same bytes", True,
           hashlib.md5(raw_full).hexdigest() != bare_digest)
    ch.add("bytes that do not hash to the stated checksum are rejected",
           "D-MATRIX A5: verification is the gate that keeps unverified bytes out of OMS, so the "
           "comparator must answer False when the document changes under a checksum that did not",
           False, stated == bare_digest)

    ch.note("what the induced mismatch does and does not prove",
            "It proves the comparator rejects a document that does not hash to the stated value: "
            "both bodies came from the mock, and the mismatch was induced by following the stated "
            "link without its marketplaceId query (%r vs the stated %r). It does NOT simulate "
            "Amazon serving bytes that disagree with its own checksum - no fixture does that - and "
            "the comparator under test is this suite's, not JPluger's "
            "(requirements.UNTESTABLE['H1'])." % (bare_digest, stated))
    ch.note("the wire consequence, still unprovable here",
            "Bytes that fail the checksum must arrive as definition_status 'FETCH_FAILED' with "
            "reason %r and NO raw_schema_json (D-MATRIX A5). No producer in this harness emits a "
            "definition_status at all, so the wire half stays blocked in US-STATUS-1 whether or "
            "not a mismatching fixture exists." % R.STATUS_REASONS["checksum_mismatch"])
    detail["stated_checksum"] = stated
    detail["induced_mismatch_digest"] = bare_digest


def c_definition_not_latest(ch, calls, detail):
    """A6. A definition Amazon does not mark latest is refused."""
    marketplace_code, store_code, product_type = "amazon_sp_us", "SS0000US", "LUGGAGE-NOTLATEST"
    marketplace_id = R.MARKETPLACE_IDS[marketplace_code]
    locale = R.DEFINITIONS_LOCALE_MAP[marketplace_code]

    mark = R.oms_high_water(BASE_OMS)
    status, envelope, _raw = _definition(product_type, marketplace_id, locale)
    calls.append("GET getDefinitionsProductType[%s] -> %s" % (product_type, status))
    ch.add("status is 200", "the definition envelope resolves", 200, status)

    pt_version = envelope.get("productTypeVersion") or {}
    ch.add("fixture productTypeVersion.latest is false",
           "steered on NOTLATEST marker to return latest: false", False, pt_version.get("latest"))

    # When latest is false, the definition is refused before its bytes are read.
    # It must arrive at OMS as FETCH_FAILED with reason "Amazon returned a definition it does not mark latest",
    # and no body with latest_version: false may ever be sent.
    # The refusal is the PRODUCER's to make, so the whole envelope goes to the fetch layer and the
    # case asserts what came back. Handing it a pre-fetched schema would have made this case assert
    # a decision the suite had already taken for itself.
    payload = build_definition_payload(
        envelope, store_code, marketplace_code, product_type, _schema_downloader)
    calls.append("build_definition_payload[%s] -> %s" % (product_type, payload.get("definition_status")))
    st_pub, _b, _r = call_oms("POST", R.BULK_ATTRIBUTES_PATH, payload,
                              query={"store_code": store_code, "marketplace_code": marketplace_code})
    calls.append("POST %s [%s] -> %s" % (R.BULK_ATTRIBUTES_PATH, product_type, st_pub))

    received = R.oms_received(BASE_OMS, R.BULK_ATTRIBUTES_PATH, refresh=True, since=mark)
    ch.truthy("posting arrived at OMS", "read back from OMS log", received)
    body = received[-1]["body"] if received else {}

    ch.add("definition_status is FETCH_FAILED",
           "D-MATRIX A6 / D-WIRE 1.1: a non-latest definition must arrive as FETCH_FAILED",
           "FETCH_FAILED", body.get("definition_status"))
    ch.add("reason states definition is not marked latest",
           "D-MATRIX A6 exact reason string",
           R.STATUS_REASONS["not_latest"], body.get("definition_status_reason"))
    ch.add("category_attributes key is absent on FETCH_FAILED",
           "D-WIRE section 1.1: category_attributes is absent for FETCH_FAILED",
           True, "category_attributes" not in body)
    ch.add("raw_schema_json is absent on FETCH_FAILED",
           "D-WIRE section 1.1: raw_schema_json dropped on FETCH_FAILED",
           True, "raw_schema_json" not in body)
    detail["envelope_latest"] = pt_version.get("latest")
    detail["received_status"] = body.get("definition_status")


def c_search_empty_catalogue(ch, calls, detail):
    """C6. An empty product-type list is an answer, not a failure."""
    mark_amz = R.oms_high_water(BASE_AMAZON)
    mark_oms = R.oms_high_water(BASE_OMS)
    empty_marketplace_id = "A1PA6795UKMFR9-EMPTY"

    status, body, _raw = _search(empty_marketplace_id)
    calls.append("GET searchDefinitionsProductTypes[%s] -> %s" % (empty_marketplace_id, status))
    ch.add("search status is 200", "an empty marketplace search succeeds cleanly", 200, status)

    product_types = body.get("productTypes") if isinstance(body, dict) else None
    ch.add("productTypes list is empty",
           "D-MATRIX C6: mock returns empty product-type list", [], product_types)

    logged_defs = R.amazon_received(BASE_AMAZON, "/definitions/2020-09-01/productTypes/", since=mark_amz)
    ch.add("zero getDefinitionsProductType calls dispatched",
           "D-MATRIX C6: zero definition calls when catalogue is empty",
           0, len(logged_defs))

    received_attrs = R.oms_received(BASE_OMS, R.BULK_ATTRIBUTES_PATH, refresh=True, since=mark_oms)
    ch.add("zero bulk_categories_attributes bodies posted to OMS",
           "D-MATRIX C6: nothing to push for an empty catalogue",
           0, len(received_attrs))
    detail["empty_search_body"] = body


def c_schema_download_failure(ch, calls, detail):
    """C7. A schema-download failure is distinguished from a definition failure."""
    marketplace_code, store_code, product_type = "amazon_sp_us", "SS0000US", "LUGGAGE-SCHEMADLFAIL"
    marketplace_id = R.MARKETPLACE_IDS[marketplace_code]
    locale = R.DEFINITIONS_LOCALE_MAP[marketplace_code]

    mark = R.oms_high_water(BASE_OMS)
    status, envelope, _raw = _definition(product_type, marketplace_id, locale)
    calls.append("GET getDefinitionsProductType[%s] -> %s" % (product_type, status))
    ch.add("definition status is 200", "the definition envelope itself resolves", 200, status)

    st_schema, schema, _ok, link = _fetch_schema(envelope)
    calls.append("GET %s -> %s" % (R.schema_link_path(link), st_schema))
    ch.add("schema link download fails with 404",
           "steered to unrouted path; schema download fails", 404, st_schema)

    # The producer follows the link itself and answers FETCH_FAILED "schema download failed".
    payload = build_definition_payload(
        envelope, store_code, marketplace_code, product_type, _schema_downloader)
    st_pub, _b, _r = call_oms("POST", R.BULK_ATTRIBUTES_PATH, payload,
                              query={"store_code": store_code, "marketplace_code": marketplace_code})
    calls.append("POST %s [%s] -> %s" % (R.BULK_ATTRIBUTES_PATH, product_type, st_pub))

    received = R.oms_received(BASE_OMS, R.BULK_ATTRIBUTES_PATH, refresh=True, since=mark)
    ch.truthy("posting arrived at OMS", "read back from OMS log", received)
    body = received[-1]["body"] if received else {}

    ch.add("definition_status is FETCH_FAILED",
           "D-MATRIX C7: schema download failure results in FETCH_FAILED",
           "FETCH_FAILED", body.get("definition_status"))
    ch.add("reason states schema download failed",
           "D-MATRIX C7 exact reason string",
           R.STATUS_REASONS["schema_download_failed"], body.get("definition_status_reason"))
    ch.add("raw_schema_json is absent on FETCH_FAILED",
           "D-MATRIX C7 / D-WIRE 1.1: no raw JSON pushed on download failure",
           True, "raw_schema_json" not in body)
    ch.add("category_attributes key is absent on FETCH_FAILED",
           "D-WIRE section 1.1: category_attributes is absent for FETCH_FAILED",
           True, "category_attributes" not in body)
    detail["schema_status"] = st_schema
    detail["received_status"] = body.get("definition_status")


def c_definition_no_schema_link(ch, calls, detail):
    """C8. A definition carrying no schema link fails cleanly."""
    marketplace_code, store_code, product_type = "amazon_sp_us", "SS0000US", "LUGGAGE-NOSCHEMA"
    marketplace_id = R.MARKETPLACE_IDS[marketplace_code]
    locale = R.DEFINITIONS_LOCALE_MAP[marketplace_code]

    mark = R.oms_high_water(BASE_OMS)
    status, envelope, _raw = _definition(product_type, marketplace_id, locale)
    calls.append("GET getDefinitionsProductType[%s] -> %s" % (product_type, status))
    ch.add("definition status is 200", "the definition envelope resolves", 200, status)
    ch.add("envelope omits schema key",
           "D-MATRIX C8: definition carries no schema link",
           False, "schema" in envelope)

    # The producer sees the envelope has no schema link and refuses before reading any bytes.
    payload = build_definition_payload(
        envelope, store_code, marketplace_code, product_type, _schema_downloader)
    st_pub, _b, _r = call_oms("POST", R.BULK_ATTRIBUTES_PATH, payload,
                              query={"store_code": store_code, "marketplace_code": marketplace_code})
    calls.append("POST %s [%s] -> %s" % (R.BULK_ATTRIBUTES_PATH, product_type, st_pub))

    received = R.oms_received(BASE_OMS, R.BULK_ATTRIBUTES_PATH, refresh=True, since=mark)
    ch.truthy("posting arrived at OMS", "read back from OMS log", received)
    body = received[-1]["body"] if received else {}

    ch.add("definition_status is FETCH_FAILED",
           "D-MATRIX C8: missing schema link results in FETCH_FAILED",
           "FETCH_FAILED", body.get("definition_status"))
    ch.add("reason states definition carries no schema link",
           "D-MATRIX C8 exact reason string",
           R.STATUS_REASONS["no_schema_link"], body.get("definition_status_reason"))
    ch.add("raw_schema_json is absent on FETCH_FAILED",
           "D-WIRE section 1.1: raw_schema_json dropped on FETCH_FAILED",
           True, "raw_schema_json" not in body)
    ch.add("category_attributes key is absent on FETCH_FAILED",
           "D-WIRE section 1.1: category_attributes is absent for FETCH_FAILED",
           True, "category_attributes" not in body)
    detail["envelope_keys"] = sorted(envelope.keys()) if isinstance(envelope, dict) else []
    detail["received_status"] = body.get("definition_status")


def c_category_code_is_the_product_type(ch, calls, detail):
    """A2. The single most load-bearing value in this ticket."""
    for region, marketplace_code, store_code, _product_type in STORES_UNDER_TEST:
        discovered, received = _post_categories(store_code, marketplace_code, calls)
        ch.truthy("%s discovered a catalogue" % region,
                  "the search returned a product-type population", discovered)

        categories = [_category_of(e) for e in received]
        codes = [c.get("code") for c in categories]

        ch.add("%s one row per product type" % region,
               "D-MATRIX B3: count parity between the search response and the bodies OMS received",
               sorted(discovered), sorted(set(codes)))
        ch.add("%s no product type posted twice" % region,
               "D-MATRIX B17: one bulk_categories body per discovered product type, none duplicated",
               sorted(set(codes)), sorted(codes))
        ch.add("%s every code is an Amazon product type, verbatim" % region,
               "D-MATRIX A2: code equals a productType.name returned by the search - SHOES, "
               "LUGGAGE, NOTEBOOK_COMPUTER", [],
               [c for c in codes if not R.is_upper_snake(c)])
        ch.add("%s no code is a browse-node id or a browse path" % region,
               "D-MATRIX A2: no body's code matches ^[0-9]+$ and none is the legacy "
               "parentCode_childBrowseNodeId shape that D-GAP decision 1 abolishes", [],
               [c for c in codes if R.looks_like_a_browse_node(c)])
        ch.add("%s name falls back to code when displayName is absent" % region,
               "D-MATRIX A2: name falls back to code when the mock omits displayName", [],
               [(c.get("code"), c.get("name")) for c in categories
                if c.get("name") not in (discovered.get(c.get("code")), c.get("code"))])
        ch.add("%s marketplace_code scopes the row" % region,
               "D-MATRIX B18 / JIRA FR-11: stored with marketplace context",
               {marketplace_code}, {c.get("marketplace_code") for c in categories})
        ch.add("%s store_code travels on the query string" % region,
               "where the OMS contract declares it", {store_code},
               {e["query"].get("store_code") for e in received})
        ch.add("%s no browse-node key on any category body" % region,
               "D-MATRIX N10 and N12: the request-level browse-node array is withdrawn and no "
               "browse-node entity is stored; classification travels as picker rows", [],
               sorted({k for e in received for k in R.browse_node_keys(e["body"])}))
        detail["%s_codes" % marketplace_code] = codes


def c_category_cross_border(ch, calls, detail):
    """A1 at the category level: the same code in two countries is two rows."""
    seen = {}
    for region, marketplace_code, store_code, _pt in STORES_UNDER_TEST:
        if marketplace_code not in ("amazon_sp_de", "amazon_sp_es"):
            continue
        _discovered, received = _post_categories(store_code, marketplace_code, calls)
        seen[marketplace_code] = [e for e in received if _category_of(e).get("code") == "PRODUCT"]

    ch.add("DE posted a PRODUCT category", "the shared code, from Germany",
           1, len(seen.get("amazon_sp_de", [])))
    ch.add("ES posted a PRODUCT category", "the shared code, from Spain",
           1, len(seen.get("amazon_sp_es", [])))

    de = _category_of((seen.get("amazon_sp_de") or [{}])[0]) or {}
    es = _category_of((seen.get("amazon_sp_es") or [{}])[0]) or {}
    ch.add("both rows carry the identical code",
           "Amazon reuses product-type names across marketplaces",
           ("PRODUCT", "PRODUCT"), (de.get("code"), es.get("code")))
    ch.add("marketplace_code is what tells them apart",
           "JIRA FR-11 / AC-20: a France definition must not overwrite DE, JP or US even with an "
           "identical product-type code",
           ("amazon_sp_de", "amazon_sp_es"), (de.get("marketplace_code"), es.get("marketplace_code")))
    ch.note("does not prove", "Whether OMS's own uniqueness key includes marketplace_code. D-GAP "
                              "decision 13 gives upsert and de-duplication to OMS and D-MATRIX U2 "
                              "scopes this row to what JPluger sends.")
    detail["de_row"], detail["es_row"] = de, es


def c_categories_precede_attributes(ch, calls, detail):
    """B17. Every product type reaches OMS as a category before its attributes do."""
    region, marketplace_code, store_code = "FR", "amazon_sp_fr", "SS0000FR"
    marketplace_id = R.MARKETPLACE_IDS[marketplace_code]
    mark = R.oms_high_water(BASE_OMS)

    discovered, _received = _post_categories(store_code, marketplace_code, calls)
    for product_type in discovered:
        _st, envelope, _raw = _definition(product_type, marketplace_id,
                                          R.DEFINITIONS_LOCALE_MAP[marketplace_code])
        st_schema, schema, _ok, link = _fetch_schema(envelope)
        calls.append("GET %s -> %s" % (R.schema_link_path(link), st_schema))
        payload = transform_schema_to_oms_attributes(
            schema, store_code, marketplace_code, product_type,
            definition_version=(envelope.get("productTypeVersion") or {}).get("version"),
            schema_checksum=(envelope.get("schema") or {}).get("checksum"))
        st, _b, _r = call_oms("POST", R.BULK_ATTRIBUTES_PATH, payload,
                              query={"store_code": store_code, "marketplace_code": marketplace_code})
        calls.append("POST %s [%s] -> %s" % (R.BULK_ATTRIBUTES_PATH, product_type, st))

    categories = [e for e in _categories_received(since=mark)]
    attributes = R.oms_received(BASE_OMS, R.BULK_ATTRIBUTES_PATH, refresh=False, since=mark)

    ch.truthy("categories arrived", "bulk_categories bodies to order", categories)
    ch.truthy("attributes arrived", "bulk_categories_attributes bodies to order", attributes)
    ch.add("every category precedes the first attribute posting",
           "D-MATRIX B17 / JIRA FR-2 sequence: 2 product types, 3 PTDs, 4 raw JSON and parsed "
           "attributes", True,
           bool(categories) and bool(attributes)
           and max(e["seq"] for e in categories) < min(e["seq"] for e in attributes))
    ch.add("one category body per discovered product type, none duplicated",
           "D-MATRIX B17", sorted(discovered),
           sorted(_category_of(e).get("code") for e in categories))
    ch.add("one attribute body per product type",
           "D-GAP section 1.2: one call per product type",
           len(discovered), len(attributes))
    detail["category_seqs"] = [e["seq"] for e in categories]
    detail["attribute_seqs"] = [e["seq"] for e in attributes]


def c_attribute_payload_invariants(ch, calls, detail):
    """A7, D7, N16 and B7's key set: the invariants that hold on EVERY attributes body.

    The per-market content of `category_attributes` belongs to the connect suites, which have the
    captures and the pickers. What belongs here is the handful of properties that must hold on every
    posting whatever marketplace produced it, asserted once rather than once per market.
    """
    marketplace_code, store_code = "amazon_sp_fr", "SS0000FR"
    marketplace_id = R.MARKETPLACE_IDS[marketplace_code]
    mark = R.oms_high_water(BASE_OMS)

    _st, envelope, _raw = _definition("SHOES", marketplace_id,
                                      R.DEFINITIONS_LOCALE_MAP[marketplace_code])
    st_schema, schema, _ok, link = _fetch_schema(envelope)
    calls.append("GET %s -> %s" % (R.schema_link_path(link), st_schema))
    payload = transform_schema_to_oms_attributes(
        schema, store_code, marketplace_code, "SHOES",
        definition_version=(envelope.get("productTypeVersion") or {}).get("version"),
        schema_checksum=(envelope.get("schema") or {}).get("checksum"))
    st, _b, _r = call_oms("POST", R.BULK_ATTRIBUTES_PATH, payload,
                          query={"store_code": store_code, "marketplace_code": marketplace_code})
    calls.append("POST %s [FR SHOES] -> %s" % (R.BULK_ATTRIBUTES_PATH, st))

    received = R.oms_received(BASE_OMS, R.BULK_ATTRIBUTES_PATH, refresh=True, since=mark)
    ch.truthy("the posting arrived at OMS", "a body to judge, read back from the mock's log", received)
    body = received[-1]["body"] if received else {}
    rows = R.attribute_row_list(body)
    ch.truthy("the body carries attribute rows", "category_attributes", rows)

    ch.add("every field_parent_code names a row already seen EARLIER",
           "D-MATRIX A7: walk the array in order keeping a set of field_code seen. Assert on array "
           "ORDER, not on set membership - an implementation that emits children first would pass a "
           "naive containment check and break OMS's renderer", [],
           R.parent_first_violations(body))
    ch.add("every field_code is unique",
           "D-MATRIX D7 / D-WIRE section 1.3: field_code is the dot-joined property path and Amazon "
           "property names never contain a dot, so two distinct paths cannot produce the same code", [],
           R.duplicate_field_codes(body))
    ch.add("every nested field_code carries the dotted path",
           "D-GAP decision 2: nested codes carry the path, dot-separated - package_info.dimensions."
           "length. An underscore-joined path is ambiguous because Amazon property names contain "
           "underscores, and D-PLAN phase 1 closes it", [],
           R.undotted_nested_codes(body))
    ch.add("no row carries id or field_parent_id",
           "D-MATRIX N16 / D-WIRE header: 'id and field_parent_id stay exactly as they are ... "
           "Amazon just leaves them unset'", [],
           R.rows_carrying_forbidden_keys(body))
    ch.add("every validation key is one the contract states",
           "D-WIRE section 1.2 lists ten keys and only ten; multipleOf belonged to the superseded "
           "mapping spec", [],
           R.validation_keys_outside_contract(body))
    ch.add("every field_criteria is one of the three",
           "D-WIRE section 1.3 / D-GAP section 1.4", [],
           sorted({str(r.get("field_criteria")) for r in rows
                   if r.get("field_criteria") not in R.FIELD_CRITERIA}))
    ch.add("every data_type is one the contract allows",
           "D-WIRE section 1.4 adds number, integer, boolean, object and array to what OMS already "
           "supported; D-RECON section 1 confirms OMS stores them", [],
           R.data_types_sent(body)[1])
    ch.add("no withdrawn picker code appears",
           "D-PLAN phase 1 D3: recommended_browse_nodes_value and item_type_keyword_value are the "
           "underscored spellings this ticket removes", [],
           [c for c in R.WITHDRAWN_PICKER_CODES if c in R.attribute_rows(body)])
    ch.add("no browse-node key on the body",
           "D-MATRIX N10: the request-level browse_node_ids array is withdrawn; classification "
           "travels as picker rows", [],
           R.browse_node_keys(body))
    ch.add("definition_status is present and is one of the six",
           "D-GAP decision 8 / D-WIRE section 1.1: AVAILABLE, UNAVAILABLE, PARSE_FAILED, "
           "SCHEMA_OMITTED, VALUES_OMITTED, FETCH_FAILED - six exactly, and a seventh value is a "
           "contract breach, not a feature", True,
           body.get("definition_status") in R.DEFINITION_STATUSES)
    ch.add("an AVAILABLE body carries no definition_status_reason",
           "D-MATRIX B6: absent when AVAILABLE - not null, not an empty string - with the single "
           "exception of a node truncated at the four-child limit (D-GAP decision 4), which this "
           "capture does not reach", True,
           not (body.get("definition_status") == "AVAILABLE"
                and "definition_status_reason" in body))
    detail["row_count"] = len(rows)
    detail["nested_codes_sample"] = R.undotted_nested_codes(body)[:8]
    detail["envelope_keys"] = sorted(k for k in body if k != "category_attributes")


def c_browse_tree_report(ch, calls, detail):
    """B16 and JIRA FR-3. The XML report, the whole flow, and never the flat file."""
    marketplace_code = "amazon_sp_fr"
    marketplace_id = R.MARKETPLACE_IDS[marketplace_code]
    mark = R.oms_high_water(BASE_AMAZON)
    flow = _browse_tree(marketplace_id)
    calls.append("POST /reports/2021-06-30/reports [%s] -> %s"
                 % (R.BROWSE_TREE_REPORT_TYPE, flow.get("create_status")))
    calls.append("GET /reports/2021-06-30/reports/%s -> %s"
                 % (flow.get("report_id"), flow.get("poll_status")))
    calls.append("GET /s3/report-download/%s -> %s"
                 % (flow.get("document_id"), flow.get("download_status")))

    ch.add("the report is created", "createReport answers 200 or 202",
           True, flow.get("create_status") in (200, 202))
    ch.truthy("a reportId comes back", "the report lifecycle starts", flow.get("report_id"))
    ch.add("the status poll succeeds", "getReport", 200, flow.get("poll_status"))
    ch.add("processing completes", "DONE, so a document id exists",
           "DONE", flow.get("processing_status"))
    ch.truthy("a reportDocumentId comes back", "getReport names the document", flow.get("document_id"))
    ch.add("the document downloads", "getReportDocument's url serves the body",
           200, flow.get("download_status"))

    xml = flow.get("xml") or b""
    ch.truthy("the body is XML", "a browse tree to parse", xml[:5])
    options = R.browse_node_field_values(xml)
    ch.truthy("leaves parse into picker options", "the transform D-MATRIX B13 states", options)

    flat = [{"name": o["name"], "value": o["value"]} for opts in options.values() for o in opts]
    ch.add("every option's value is a numeric node id",
           "D-MATRIX B13: value is the numeric node id, e.g. 2028940032", [],
           [o["value"] for o in flat if not str(o["value"]).isdigit()])
    ch.add("every option's name is the breadcrumb path, %r joined" % R.BROWSE_PATH_SEPARATOR,
           "D-MATRIX B13: assert the separator exactly - a comma-joined or leaf-only name breaks "
           "seller disambiguation between two nodes both named Comics", [],
           [o["name"] for o in flat if R.BROWSE_PATH_SEPARATOR not in o["name"]])

    requests = R.amazon_received(BASE_AMAZON, "/reports/2021-06-30/reports",
                                 since=mark, method="POST")
    types = [(e["body"] or {}).get("reportType") for e in requests]
    ch.add("only the XML browse report was requested",
           "JIRA FR-3: use ONE supported format and do not request both for the same sync", [],
           [t for t in types if t != R.BROWSE_TREE_REPORT_TYPE])
    ch.add("zero requests name the flat-file report",
           "D-MATRIX N11: GET_FLAT_FILE_BROWSE_TREE_DATA does not exist in SP-API - FR-3 asked for "
           "validation of both, and the answer is that one of them is not real. Assert its absence, "
           "never its use", 0,
           sum(1 for t in types if t == R.FORBIDDEN_REPORT_TYPE))
    ch.note("does not prove", "That JPluger requests the report, or requests it once per "
                              "marketplace: this suite issued it (requirements.UNTESTABLE['H1']).")
    detail["product_types_with_options"] = {k: len(v) for k, v in options.items()}
    detail["report_bytes"] = len(xml)


def c_browse_tree_failed_report(ch, calls, detail):
    """C9. A browse-tree report that fails leaves the definitions already published untouched.

    Driven on the CANCELLED marker rather than FATAL. JIRA section 12 names both terminal statuses
    in one breath -- "Report returns FATAL or CANCELLED -> record failure and allow retry" -- and
    the mock implements CANCELLED, so the row's own wording is satisfied without a mock change. The
    marker rides in `reportOptions.MarketplaceId`, which is what the mock keys the reportId on
    (amazon/README.md), so the id the mock hands back is the id this case then polls: a real
    create -> poll flow, not a fabricated id. FATAL is recorded below as the documented-but-absent
    marker it is.
    """
    marketplace_code, store_code, product_type = "amazon_sp_de", "SS0000DE", "PRODUCT"
    marketplace_id = R.MARKETPLACE_IDS[marketplace_code]

    # 1. Publish the definition BEFORE the report fails -- C9's subject is what survives the failure.
    mark_before = R.oms_high_water(BASE_OMS)
    _st, envelope, _raw = _definition(product_type, marketplace_id,
                                      R.DEFINITIONS_LOCALE_MAP[marketplace_code])
    st_schema, schema, _ok, link = _fetch_schema(envelope)
    calls.append("GET %s -> %s" % (R.schema_link_path(link), st_schema))
    payload = transform_schema_to_oms_attributes(
        schema, store_code, marketplace_code, product_type,
        definition_version=(envelope.get("productTypeVersion") or {}).get("version"),
        schema_checksum=(envelope.get("schema") or {}).get("checksum"))
    st_pub, _b, _r = call_oms("POST", R.BULK_ATTRIBUTES_PATH, payload,
                              query={"store_code": store_code,
                                     "marketplace_code": marketplace_code})
    calls.append("POST %s [DE PRODUCT, before the report] -> %s" % (R.BULK_ATTRIBUTES_PATH, st_pub))
    before = R.oms_received(BASE_OMS, R.BULK_ATTRIBUTES_PATH, refresh=True, since=mark_before)
    rows_before = R.attribute_row_list(before[-1]["body"] if before else {})
    codes_before = [r.get("field_code") for r in rows_before]
    ch.truthy("a definition is published before the report runs",
              "the body C9 says must survive the failure", rows_before)

    # 2. The browse-tree report for that same marketplace, steered to a terminal failure.
    mark_failure = R.oms_high_water(BASE_OMS)
    failing = _browse_tree("%s-CANCELLED" % marketplace_id)
    calls.append("POST /reports/2021-06-30/reports [browse tree, CANCELLED marker] -> %s, id %s"
                 % (failing.get("create_status"), failing.get("report_id")))
    calls.append("GET /reports/2021-06-30/reports/%s -> %s"
                 % (failing.get("report_id"), failing.get("processing_status")))

    ch.add("the report is accepted, then reaches a terminal status that is not DONE",
           "JIRA section 12: 'Report returns FATAL or CANCELLED -> record failure and allow "
           "retry'. A report that fails is the precondition of the row, so it is driven rather "
           "than assumed", "CANCELLED", failing.get("processing_status"))
    ch.add("a failed report names no document",
           "there is nothing to download and nothing to parse: a client that reads a document id "
           "off a failed report is reading a field Amazon did not send", None,
           failing.get("document_id"))
    ch.add("nothing was downloaded",
           "no document id means no download attempt; a browse tree that was never served cannot "
           "have supplied a single option", 0, len(failing.get("xml") or b""))

    # 3. Republish after the failure. The producer has no browse values to offer, and the row's
    #    demand is that the definition still publishes complete rather than empty or retracted.
    payload_after = transform_schema_to_oms_attributes(
        schema, store_code, marketplace_code, product_type,
        definition_version=(envelope.get("productTypeVersion") or {}).get("version"),
        schema_checksum=(envelope.get("schema") or {}).get("checksum"))
    st_after, _b2, _r2 = call_oms("POST", R.BULK_ATTRIBUTES_PATH, payload_after,
                                  query={"store_code": store_code,
                                         "marketplace_code": marketplace_code})
    calls.append("POST %s [DE PRODUCT, after the failure] -> %s"
                 % (R.BULK_ATTRIBUTES_PATH, st_after))
    after = R.oms_received(BASE_OMS, R.BULK_ATTRIBUTES_PATH, refresh=True, since=mark_failure)
    body_after = after[-1]["body"] if after else {}
    rows_after = R.attribute_row_list(body_after)
    codes_after = [r.get("field_code") for r in rows_after]

    ch.add("exactly one body follows the failure, and it is not an empty one",
           "the retraction this row guards against would show up here as a second body, or as a "
           "body whose category_attributes arrived empty", [1, True],
           [len(after), bool(rows_after)])
    ch.add("the definition still publishes its complete attribute set after the failure",
           "D-MATRIX C9: a failed report must not empty or retract a definition that already "
           "published. Asserted on the bodies OMS received, before and after", codes_before,
           codes_after)
    ch.add("no row carries a browse-node option the failed report could not have supplied",
           "the failure mode this row exists for is a picker filled from somewhere else -- the "
           "seller's default store, another marketplace, a stale cache. With no tree served, every "
           "option on the body must come from the schema's own enums", [],
           sorted({str(v.get("value")) for r in rows_after
                   for v in (r.get("field_values") or [])
                   if str(v.get("value")).isdigit() and len(str(v.get("value"))) >= 8}))

    # 4. The FATAL marker, still documented and still absent. Reported, not repaired.
    fatal_id = "rep-browsetree-FATAL-%s" % marketplace_id
    st_f, body_f, _raw_f = call("GET", "/reports/2021-06-30/reports/%s" % fatal_id)
    calls.append("GET /reports/2021-06-30/reports/%s -> %s" % (fatal_id, st_f))
    ch.note("FATAL is documented and not implemented on this route",
            "amazon/README.md's steering-marker table lists `FATAL` for `feedId, reportId`, and the "
            "feeds route honours it. This route does not: %r answers processingStatus %r with "
            "reportDocumentId %r -- a failed report handing back a document id, which is the one "
            "shape a client must never see. The same table overstates `SERVERERROR` and "
            "`RATELIMIT` as 'Query, Path, or Body' markers; neither definitions route declares "
            "either rule. README.md's own route description (line 300) already lists this route as "
            "DONE / IN_PROGRESS / CANCELLED, so the table is the half that is wrong. Reported, not "
            "repaired: the mock is shared."
            % (fatal_id, (body_f or {}).get("processingStatus"),
               (body_f or {}).get("reportDocumentId")))
    ch.note("what stays out of reach",
            "The 6 h hold-off (%d h), the retry after a recorded failure, and the fact that "
            "JPluger rather than this suite republished are [JP]-hop behaviour with no observation "
            "point (requirements.UNTESTABLE['H1']). The empty-picker SHAPE the row also implies -- "
            "field_values: [] with free_text: true -- belongs to B15 / NONUS-RBN-EMPTY in "
            "suite-connect-non-us.py and is not re-asserted here."
            % (R.BROWSE_NODE_REFRESH_HOLD_OFF_MILLIS // 3600000))
    detail["failed_report"] = {k: failing.get(k) for k in
                               ("report_id", "processing_status", "document_id")}
    detail["fatal_marker_answer"] = {"reportId": fatal_id,
                                     "processingStatus": (body_f or {}).get("processingStatus"),
                                     "reportDocumentId": (body_f or {}).get("reportDocumentId")}
    detail["rows_published"] = len(rows_after)


def c_browse_tree_not_substituted(ch, calls, detail):
    """JIRA FR-20: a browse tree must never be substituted from another marketplace."""
    marketplace_id = R.MARKETPLACE_IDS["amazon_sp_fr"]
    scoped = _browse_tree(marketplace_id, with_report_options=True)
    calls.append("POST /reports [with reportOptions.MarketplaceId] -> %s" % scoped.get("report_id"))
    substituted = _browse_tree(marketplace_id, with_report_options=False)
    calls.append("POST /reports [reportOptions omitted] -> %s" % substituted.get("report_id"))

    scoped_roots = R.root_node_ids(scoped.get("xml") or b"")
    other_roots = R.root_node_ids(substituted.get("xml") or b"")

    ch.truthy("the scoped report served a tree", "a tree for the requested marketplace", scoped_roots)
    ch.truthy("the unscoped report served a tree", "Amazon answers either way", other_roots)
    ch.add("the scoped report is keyed on the marketplace",
           "amazon/README.md: reportId becomes rep-browsetree-<reportOptions.MarketplaceId>",
           "rep-browsetree-%s" % marketplace_id, scoped.get("report_id"))
    ch.add("omitting reportOptions serves the seller's DEFAULT store's tree",
           "amazon/README.md: 'omit reportOptions and every store receives the same tree. That is "
           "what the real API does, and it makes the marketplace-isolation failure reproducible "
           "offline'", "rep-browsetree-DEFAULTSTORE", substituted.get("report_id"))
    ch.add("the two trees are genuinely different taxonomies",
           "JIRA FR-20: do NOT substitute another marketplace's browse tree. The root sets are "
           "disjoint by construction, so a substituted tree is observable rather than inferred",
           set(), scoped_roots & other_roots)
    ch.note("does not prove", "That JPluger states reportOptions. This case proves the trap is live "
                              "in the mock, so a client that omits it fails here rather than in "
                              "production, where the wrong country's taxonomy arrives with no "
                              "error at all.")
    detail["scoped_roots"] = sorted(scoped_roots)
    detail["default_store_roots"] = sorted(other_roots)


def c_browse_tree_duplicate_node(ch, calls, detail):
    """JIRA section 12, "Duplicate browse node -> upsert existing node"."""
    trees = {}
    for marketplace_code in ("amazon_sp_fr", "amazon_sp_de"):
        flow = _browse_tree(R.MARKETPLACE_IDS[marketplace_code])
        calls.append("GET browse tree [%s] -> %s bytes"
                     % (marketplace_code, len(flow.get("xml") or b"")))
        trees[marketplace_code] = flow.get("xml") or b""

    import collections
    duplicates = {}
    for marketplace_code, xml in trees.items():
        ids = R.browse_node_ids(xml)
        duplicates[marketplace_code] = sorted(
            {i for i, n in collections.Counter(ids).items() if n > 1})

    ch.truthy("a tree carrying a duplicate node id is served",
              "amazon/README.md records the real amazon.de pair from "
              "amzn/selling-partner-api-models issue #4742: id 13528201031 under two names, two "
              "parents and two depths",
              [d for ds in duplicates.values() for d in ds])
    ch.add("the duplicate is inside one marketplace, not across two",
           "JIRA FR-4: browse nodes must be unique within the connected marketplace context, and "
           "'the same browse-node ID must not be assumed to have identical meaning across all "
           "marketplaces without validation'",
           True, any(duplicates.values()))
    ch.note("what an upsert keyed on node id would lose",
            "JIRA section 12 answers a duplicate with 'upsert existing node', which collapses the "
            "pair. The picker model of D-GAP section 1.5 does not: the option is {name: the "
            "breadcrumb path, value: the node id}, so two nodes sharing an id stay two options "
            "whenever their paths differ. That is the behaviour to preserve.")
    ch.note("the unsplittable-path trap travels with it",
            "Nodes whose browsePathByName cannot be rebuilt by splitting on commas, per "
            "marketplace: %s. Category names contain commas, and the naive split's token count "
            "often equals the id count, so a length assertion passes on corrupted data - see "
            "requirements.UNSETTLED['browse_path_by_name_is_unsplittable']."
            % json.dumps({m: R.unsplittable_path_nodes(x) for m, x in trees.items()}))
    detail["duplicate_node_ids"] = duplicates


# ------------------------------------------------------------------ case declarations

case("SRCH-1", "searchDefinitionsProductTypes -- one catalogue per marketplace, no keywords",
     "marketplaceIds for the US, FR, DE, ES and AU stores",
     ["200 OK for every marketplace, each discovering its own catalogue",
      "Every product type the search returns is scoped to the requested marketplace id",
      "Exactly one marketplaceIds per request, and no keywords or page token",
      "The search-level productTypeVersion is the bare-string shape, not the definition's object"],
     "D-MATRIX B3. The complete set is retrieved without keywords, and N15 closes pagination with "
     "nothing to write: ProductTypeList v2020-09-01 carries no page token, so AC-7 is answered by "
     "the absence of the field rather than by a second page. The request is this suite's own, so "
     "what is proven is that the mock records the distinction (requirements.UNTESTABLE['H1']).",
     c_search_by_market)

case("DEF-PARAMS-1", "getDefinitionsProductType -- the request parameters, per marketplace",
     "A definition requested for each store with its own marketplace id and locale",
     ["marketplaceIds is exactly the one id for the store's marketplace",
      "requirements=LISTING_PRODUCT_ONLY and requirementsEnforced=ENFORCED",
      "locale is the store's own, per AMAZON_DEFINITIONS_LOCALE_MAP",
      "parentageLevel=NONE, and sellerId and productTypeVersion are both absent",
      "productTypeVersion comes back as an object whose latest is true",
      "schema is a link, so the document takes a second, separate GET"],
     "D-MATRIX B2, parameter for parameter, merged from the three per-market cases this suite used "
     "to carry (TAX-US-1, TAX-FR-1 and the envelope half of TAX-AU-1), which asserted the same "
     "echo three times. sellerId=null is recorded as a deliberate current-state assertion against "
     "open question O1: whether supplying it changes what Amazon returns for the classification "
     "attributes is untestable here (D-MATRIX U6).",
     c_definition_request_parameters)

case("TAX-SEQ-1", "The call sequence: search once, then a definition and a schema fetch per type",
     "An FR store connect, with every Amazon call read back out of the Amazon mock's own log",
     ["Exactly one hit on /definitions/2020-09-01/productTypes",
      "Exactly N hits on /definitions/2020-09-01/productTypes/{productType}, in the search's order",
      "Exactly N GETs on the schema-document URLs those responses named",
      "The search precedes every definition call, and each schema fetch follows its own definition"],
     "D-MATRIX B1 and JIRA FR-2's sequence. The schema fetch being a SECOND call to the link's "
     "resource is the load-bearing half: a client that read an inlined schema would never verify "
     "the checksum (A5) and would never notice a broken link (C7, C8). This suite is the only "
     "client the mock sees, so the row is proven of the log rather than of JPluger "
     "(requirements.UNTESTABLE['H1']).",
     c_call_sequence)

case("TAX-EU-1", "Marketplace isolation -- the same product type code, two marketplaces",
     "PRODUCT requested for A1PA6795UKMFR9 (DE) and A1RKKUPIHCS9HS (ES), both schemas downloaded",
     ["The schema links differ, so the marketplaceId travels on the link",
      "definition_version and schema_checksum both differ between the two",
      "The downloaded property sets genuinely differ -- content, not an echoed marketplaceId"],
     "D-MATRIX A1 at the Amazon hop, and the row states the trap: 'assert on the CONTENT, never on "
     "an echoed marketplaceId alone - an implementation that fetched FR twice and stamped the "
     "second with amazon_sp_de must fail this row'. DE and ES are the pair that makes it "
     "observable, because Amazon reuses the code PRODUCT across both. JIRA FR-11 and AC-20 are "
     "what it protects.",
     c_de_es_isolation)

case("TAX-AU-1", "The four-child cap -- which captures breach it, and which must not",
     "Every capture downloaded and walked for nodes wider than the cap and deeper than the limit",
     ["AU purchasable_offer states 13 children, as the plan measured",
      "AU breaches at exactly the four nodes D-PLAN phase 2 names",
      "FR, DE and US breach nothing -- the cap is invisible on the ticket's own marketplaces",
      "No capture reaches the depth limit of 9"],
     "The precondition D-MATRIX B19 needs. B19 asserts at the wire that a wide node publishes its "
     "first four children in Amazon's own property order, keeps definition_status AVAILABLE and "
     "names the node and its true count in definition_status_reason - the one case where a reason "
     "rides an AVAILABLE definition (D-GAP decision 4). This case proves the fixtures that row "
     "runs on are the ones the plan measured, so a fixture change is caught here rather than read "
     "as a producer regression there.",
     c_width_cap_preconditions)

case("TAX-404", "A product type Amazon serves no definition for",
     "getDefinitionsProductType with a NOTFOUND-marked product type",
     ["404 Not Found", "A structured errors array support can read"],
     "D-MATRIX C1, the Amazon half. The wire half - definition_status UNAVAILABLE, a reason naming "
     "the product type, no raw_schema_json and no category_attributes key at all - belongs to the "
     "connect suites, and the retry half belongs to a [JP] hop this harness does not have. "
     "D-MATRIX section 4 is honest that the scenario is not realistic: Amazon documents "
     "searchDefinitionsProductTypes as returning only product types that have definitions, so this "
     "proves the handling and not the scenario.",
     c_definition_not_found)

case("TAX-CKSUM", "Amazon's stated checksum is verified against the bytes served at the link",
     "US LUGGAGE, which states a real MD5, and an unconfigured product type, which states none",
     ["The downloaded bytes match the stated checksum",
      "The generic fallback states an empty checksum, so verification fails open"],
     "D-MATRIX A5. Verification is the gate that keeps unverified bytes out of OMS: bytes failing "
     "it must arrive as FETCH_FAILED with the reason the matrix quotes, and with no "
     "raw_schema_json. The empty-checksum fallback is a regression guard amazon/README.md "
     "explains - a static body can never hash to a fixed checksum computed ahead of time, so a "
     "non-empty fake would fail every real client's verification. The mismatch branch itself has no "
     "fixture and is recorded, not faked (requirements.UNTESTABLE['H2']).",
     c_checksum_verification)

case("TAX-LATEST-1", "A definition Amazon does not mark latest is refused",
     "LUGGAGE-NOTLATEST requested from the mock, returning productTypeVersion.latest = false",
     ["The definition envelope resolves and marks productTypeVersion.latest = false",
      "definition_status is FETCH_FAILED",
      "Reason states 'Amazon returned a definition it does not mark latest'",
      "category_attributes and raw_schema_json keys are absent"],
     "D-MATRIX A6: a non-latest definition is refused before its bytes are read. Driven via "
     "the NOTLATEST marker on productType. Assert definition_status 'FETCH_FAILED' with reason "
     "'Amazon returned a definition it does not mark latest', no raw_schema_json, and no "
     "category_attributes key (D-WIRE section 1.1).",
     c_definition_not_latest)

case("TAX-CAT-1", "bulk_categories -- category.code IS the Amazon product type",
     "A search per store, one POST /rest/v1/bulk_categories per product type, every body read back "
     "out of the OMS mock's own call log",
     ["One body per product type the search returned, and no product type posted twice",
      "Every code is an Amazon product type verbatim -- SHOES, LUGGAGE, AUTO_PART",
      "No code is a browse-node id or an underscore-joined numeric browse path",
      "name falls back to code where the mock states no displayName",
      "marketplace_code scopes the row and store_code travels on the query string",
      "No browse-node key on any body, under any spelling"],
     "D-MATRIX A2, the one concept change of the whole ticket: 'an OMS category is now an Amazon "
     "product type (SHOES), not a browse node' (D-WIRE header, D-GAP decision 1). The negative "
     "half matters as much as the positive one - before this branch the code WAS the browse path "
     "(172282_281052_172541), and the two code spaces do not map onto each other by any algorithm. "
     "The browse-node key scan folded in from the retired TAX-CAT-2, which scanned the same bodies "
     "a second time; its other half, a scan for browse-node-shaped VALUES, is withdrawn, because "
     "under D-GAP section 1.5 a numeric node id is a legal field_values entry.",
     c_category_code_is_the_product_type)

case("TAX-CAT-3", "bulk_categories -- the same product type code in two countries",
     "DE and ES both discover PRODUCT and both post it",
     ["Two bodies arrive carrying the identical code PRODUCT",
      "Each carries its own marketplace_code, which is the whole of the isolation"],
     "JIRA FR-11 and AC-20, at the category level: 'a France definition must not overwrite a "
     "Germany, Japan or US definition, even when the product-type code is identical'. What OMS's "
     "uniqueness key does with the pair is D-GAP decision 13's - OMS owns upsert and "
     "de-duplication - and D-MATRIX U2 scopes this row to what JPluger sends.",
     c_category_cross_border)

case("TAX-CAT-ORDER-1", "Every product type reaches OMS as a category before its attributes do",
     "An FR store connect posting categories then attributes, ordered by the OMS mock's own "
     "sequence numbers",
     ["Every bulk_categories body precedes the first bulk_categories_attributes body",
      "One category body per discovered product type, none duplicated",
      "One attribute body per product type"],
     "D-MATRIX B17 and JIRA FR-2's sequence: product types, then definitions, then raw JSON and "
     "parsed attributes. The order is what OMS's own two-pass field creation depends on "
     "(D-RECON section 1: BulkUpsertFieldWorker resolves code -> parent_id within marketplace + "
     "taxon scope), so attributes arriving first would resolve against a category that does not "
     "exist yet.",
     c_categories_precede_attributes)

case("TAX-ATTR-INV-1", "bulk_categories_attributes -- the invariants every body must hold",
     "One FR SHOES definition transformed and posted, read back out of the OMS mock's own log",
     ["Every field_parent_code names a row emitted EARLIER in the same array",
      "Every field_code is unique, and every nested one carries the dotted path",
      "No row carries id or field_parent_id; no validation key outside the contract's ten",
      "definition_status is present and one of the six; an AVAILABLE body carries no reason"],
     "The cross-cutting half of the wire contract, asserted once rather than once per market: "
     "D-MATRIX A7 (parent-first ORDER, not set membership), D7 (unique dotted codes), N16 (id and "
     "field_parent_id unset), B5 and B6 (six statuses, no reason when AVAILABLE) and the ten "
     "validation keys of D-WIRE section 1.2. The per-market CONTENT of category_attributes - the "
     "pickers, the measurement rows, the row counts - belongs to the connect suites, which hold the "
     "captures. This case is expected to fail against the current stand-in on two counts, and both "
     "are the report: transformer.field_code_of still joins nested paths with an underscore "
     "(D-GAP decision 2 makes them dotted), and the stand-in emits no definition_status at all.",
     c_attribute_payload_invariants)

case("TAX-BT-REPORT", "The browse tree comes from the XML report, through the whole report flow",
     "createReport -> poll -> document id -> download -> parse, for the FR marketplace",
     ["The full lifecycle answers, ending in a downloadable document",
      "Leaves parse into picker options whose value is the numeric node id",
      "Every option name is the breadcrumb path joined by ' > '",
      "Zero requests name GET_FLAT_FILE_BROWSE_TREE_DATA"],
     "D-MATRIX B16 and JIRA FR-3, which asked for both report formats to be validated. The answer "
     "is in D-MATRIX N11: the flat-file browse report does not exist in SP-API, EReportType "
     "declares only the XML one, so the requirement is satisfied by asserting its ABSENCE. The "
     "' > ' separator is asserted exactly, because a comma-joined or leaf-only name breaks seller "
     "disambiguation between two nodes with the same leaf name (D-MATRIX B13).",
     c_browse_tree_report)

case("TAX-BT-FATAL-1", "A failed browse-tree report leaves published definitions untouched",
     "DE PRODUCT published to OMS, then a browse-tree report for DE steered to CANCELLED",
     ["The report is accepted and reaches a terminal status that is not DONE",
      "It names no document, so nothing is downloaded and no option can come from it",
      "The definition republishes its complete attribute set, and no row carries a browse-node "
      "option the failed report could not have supplied",
      "Recorded: FATAL is documented on this route and not implemented; the hold-off and the "
      "retry are [JP]"],
     "D-MATRIX C9 and JIRA section 12 ('Report returns FATAL or CANCELLED -> record failure and "
     "allow retry'). The dangerous failure is not the report failing; it is a failed report "
     "emptying or retracting definitions that already published, or another marketplace's tree "
     "being substituted for the missing one (FR-20, covered by TAX-BT-ISO-1). Driven on CANCELLED, "
     "the terminal status the row names alongside FATAL and the one the mock implements, so the "
     "row is proven without editing a shared mock. The 6 h hold-off and the retry stay [JP].",
     c_browse_tree_failed_report)

case("TAX-BT-ISO-1", "A browse tree is never substituted from another marketplace",
     "The same marketplace's report requested with, and then without, reportOptions.MarketplaceId",
     ["The scoped report is keyed on the requested marketplace",
      "Omitting reportOptions serves the seller's DEFAULT store's tree instead",
      "The two trees' root sets are disjoint, so the substitution is observable"],
     "JIRA FR-20: 'do NOT substitute another marketplace's browse tree'. amazon/README.md builds "
     "the trap deliberately - five trees with disjoint root sets, and a default that answers "
     "whenever reportOptions is omitted - because in production the substituted taxonomy arrives "
     "with no error at all, and the first symptom is a seller seeing another country's categories. "
     "Nothing in the coverage matrix covers the substitution directly; C9 covers the failure that "
     "precedes it.",
     c_browse_tree_not_substituted)

case("TAX-BT-DUP-1", "A browse node id that repeats inside one marketplace",
     "Every non-US tree the mock serves, counted by browseNodeId",
     ["A tree carrying a duplicate node id is served",
      "The duplicate is inside one marketplace, not across two",
      "Recorded: what an upsert keyed on node id would lose, and which leaves have unsplittable "
      "paths"],
     "JIRA section 12, 'Duplicate browse node -> upsert existing node', against JIRA FR-4, 'browse "
     "nodes must be unique within the connected marketplace context'. The pair is real: "
     "amazon/README.md carries the amazon.de collision from amzn/selling-partner-api-models issue "
     "#4742, id 13528201031 under two names, two parents and two depths. The picker model of "
     "D-GAP section 1.5 survives it where a node-id-keyed upsert does not, and that is the "
     "property worth guarding.",
     c_browse_tree_duplicate_node)

case("SRCH-EMPTY-1", "An empty product-type catalogue is an answer, not a failure",
     "searchDefinitionsProductTypes called with marketplaceIds containing EMPTY",
     ["Search status is 200 and productTypes list is empty",
      "Zero getDefinitionsProductType calls dispatched",
      "Zero bulk_categories_attributes bodies posted to OMS"],
     "D-MATRIX C6: an empty product-type list is an answer, not a failure. Driven with "
     "marketplaceIds containing EMPTY; asserts 200 with empty productTypes list, exactly 1 "
     "search call, zero definition calls, and zero attributes posted.",
     c_search_empty_catalogue)

case("TAX-DL-FAIL-1", "A schema-download failure is distinguished from a definition failure",
     "LUGGAGE-SCHEMADLFAIL requested, whose schema link points to an unrouted path (mock 404s)",
     ["Definition envelope resolves with status 200",
      "Schema link download fails with 404",
      "definition_status is FETCH_FAILED",
      "Reason states 'schema download failed'",
      "category_attributes and raw_schema_json keys are absent"],
     "D-MATRIX C7: a schema-download failure is distinguished from a definition failure. "
     "Driven via the SCHEMADLFAIL marker whose schema.link.resource points to an unrouted "
     "path (mock 404s); asserts definition_status FETCH_FAILED with reason 'schema download failed', "
     "raw schema absent, attributes absent.",
     c_schema_download_failure)

case("TAX-NO-LINK-1", "A definition carrying no schema link fails cleanly",
     "LUGGAGE-NOSCHEMA requested, returning an envelope with no schema key",
     ["Definition envelope resolves with status 200 and omits schema key",
      "definition_status is FETCH_FAILED",
      "Reason states 'definition carries no schema link'",
      "category_attributes and raw_schema_json keys are absent"],
     "D-MATRIX C8: a definition carrying no schema link fails cleanly. Driven via the "
     "NOSCHEMA marker returning an envelope with no schema key; asserts definition_status "
     "FETCH_FAILED with reason 'definition carries no schema link', raw schema absent, "
     "attributes absent.",
     c_definition_no_schema_link)


# ------------------------------------------------------------------ runner execution


def preflight():
    global AMAZON_UP, OMS_UP
    print("amazon taxonomy, categories and browse tree (IA-5105 US1) -- %s" % BASE_AMAZON)
    print("  mock dir : %s" % MOCK_DIR)
    print("  run dir  : %s" % RUN_DIR)
    print("  oms      : %s" % BASE_OMS)
    os.makedirs(DATA_DIR, exist_ok=True)

    st, _b, _raw = call("POST", "/auth/o2/token", None, token=None)
    AMAZON_UP = st != 0
    print("  mock     : %s (POST /auth/o2/token -> %s)"
          % ("up" if AMAZON_UP else "DOWN -- every case will be blocked", st))
    # No ephemeral server is started. amazon.mock.json binds port 23103, and seizing a port this run
    # does not own would take it from another run; a suite that cannot reach its mock is reported as
    # blocked rather than made to pass (wiki plan/amazon-test-suites#02-redundancy-and-reporting).

    st_oms, _b, _r = call_oms("GET", "/rest/v1/categories",
                              query={"store_code": "SS0000DE", "marketplace_code": "amazon_sp_de"})
    OMS_UP = (st_oms == 200)
    print("  oms      : %s (GET /rest/v1/categories -> %s)"
          % ("up" if OMS_UP else "DOWN -- the bulk_categories cases will be blocked", st_oms))

    EVIDENCE["server"] = "Amazon SP-API mock at %s (%s)" % (BASE_AMAZON, "up" if AMAZON_UP else "down")
    EVIDENCE["oms server"] = "Anchanto OMS mock at %s (%s)" % (BASE_OMS, "up" if OMS_UP else "down")

    if KEEP:
        print("  state    : kept (--keep-state)")
        return
    if OMS_UP:
        # Every payload assertion reads the OMS mock's own call log; a log inherited from an earlier
        # run would let this run pass on someone else's bytes.
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
    # A blocked case is a documented gap, not a regression -- TESTING.md. Only a failure is an exit
    # code, or a run whose gaps are all documented would look like a broken build.
    return 1 if f else 0


if __name__ == "__main__":
    sys.exit(main())
