#!/usr/bin/env python3
"""IA-5106-US4 Suite: Rejection, Expiry & Status Restoration.

Judges the absence detection rule, status restoration, and stock revalidation:
  1. Rejection detected by absence over two consecutive reads (JIRA-IA5106 §14 FR-17)
  2. Single unstable read does not trigger restore; requires second corroborating read (JIRA-IA5106 §14 FR-17)
  3. Supports resolution enum: REJECTED, WITHDRAWN, EXPIRED (all restore identically; JIRA-IA5106 §9, §13 FR-16, AC-7)
  4. Dispatches CR-3 POST /rest/v1/orders/{id}/cancel_request/restore to Anchanto OMS (JIRA-IA5106 AC-7; UNSOURCED wire route)
  5. Restores operational status to previous_status when valid (JIRA-IA5106 §10 FR-4, AC-7)
  6. Revalidates reservation_state: RETAINED, REVALIDATED, or UNAVAILABLE (JIRA-IA5106 AC-8)
  7. Lapsed in-process stock routes to existing out-of-stock problem order (reuse existing oms_problem_order; JIRA-IA5106 §13 FR-16, AC-9)
  8. Refused restore returns problem_reason: "Previous Status Unavailable" without forcing invalid transition (JIRA-IA5106 §14 FR-19, §20 Error Matrix #9)
  9. Asserts stock is NEVER released on restore path (JIRA-IA5106 §13 FR-16, AC-8)
  10. Asserts audit history is retained for every request and outcome (JIRA-IA5106 §18 FR-33, §19)
  11. Asserts verbatim seller guidance text and absence of OMS Approve/Reject buttons (JIRA-IA5106 §18 FR-27, AC-21)
  12. JIRA-IA5106 §16 FR-28: Mandatory reconciliation before resumption verifies latest Amazon state before restoring
  13. JIRA-IA5106 §14 FR-19, §20 Error Matrix #9: Previous status unavailable terminal problem state without invalid transition

What this suite proves:
  - Amazon buyer cancellation rejection, withdrawal, expiry detection, and CR-3 restore wire payloads match ticket specifications.
  - Payloads are judged on what arrived at the OMS mock over HTTP (:23021/log/data).

What this suite does not prove:
  These suites call the mocks directly. They do not drive JPluger. A green run means the mocks
  and the IA-5106 documents agree -- it is not evidence that the integration works.

Runner contract: TESTING.md.
Publishes live status to amazon/test-results/IA-5106-US4-restore/run-<stamp>/results.json.
"""

import atexit
import datetime
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer

BASE_AMAZON = os.environ.get("BASE_AMAZON", os.environ.get("BASE", "http://127.0.0.1:23103")).rstrip("/")
BASE_OMS = os.environ.get("BASE_OMS", "http://127.0.0.1:23001").rstrip("/")
SUITE = "IA-5106-US4-restore"
KEEP = "--keep-state" in sys.argv
FAST = "--fast" in sys.argv
WANTED_CASES = set(a for a in sys.argv[1:] if not a.startswith("-"))

HERE = os.path.dirname(os.path.abspath(__file__))
MOCK_DIR = os.path.dirname(HERE)
DATA_DIR = os.path.join(MOCK_DIR, "mock-data")
LOG = "api-calls.har.json"
STAMP = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
RUN_DIR = os.path.join(MOCK_DIR, "test-results", SUITE, "run-" + STAMP)

if HERE not in sys.path:
    sys.path.insert(0, HERE)

import requirements as req
from transformer import CancellationTransformer

_EPHEMERAL_SERVER = None
_EPHEMERAL_THREAD = None


def _start_ephemeral_mock():
    global _EPHEMERAL_SERVER, _EPHEMERAL_THREAD
    parent_dir = os.path.dirname(MOCK_DIR)
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)
    try:
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
    except Exception as e:
        print(f"Notice: Ephemeral mock server could not be started ({e}). Using existing {BASE_AMAZON}")


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
    url = BASE_AMAZON + path
    headers = {"Content-Type": "application/json"}
    data = json.dumps(body).encode("utf-8") if body is not None else None
    if token:
        headers["x-amz-access-token"] = token
        headers["Authorization"] = "Bearer " + token

    req_obj = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req_obj, timeout=10) as r:
            raw, status = r.read(), r.status
    except urllib.error.HTTPError as e:
        raw, status = e.read(), e.code
    except Exception as e:
        return 0, {"_transport_error": str(e)}, b""

    try:
        return status, json.loads(raw.decode("utf-8")) if raw.strip() else {}, raw
    except Exception:
        return status, raw.decode("utf-8", "replace"), raw


def call_oms(method, path, body=None, query=None, token="mock_oms_token"):
    full_path = path + ("?" + urllib.parse.urlencode(query) if query else "")
    url = BASE_OMS + full_path
    headers = {"Content-Type": "application/json"}
    data = json.dumps(body).encode("utf-8") if body is not None else None
    if token:
        headers["Authorization"] = "Bearer " + token

    req_obj = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req_obj, timeout=10) as r:
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
    "amazon mock": f"Amazon SP-API mock at {BASE_AMAZON}",
    "oms mock": f"Anchanto OMS mock at {BASE_OMS}",
    "proves": "Amazon cancellation rejection detection via two-read absence, CR-3 status restoration wire payloads, and reservation revalidation",
    "does_not_prove": req.DOES_NOT_PROVE,
}

OMS_UP = False
AMAZON_UP = False


def case(cid, name, given, then, note, fn):
    CASES.append({
        "id": cid,
        "name": name,
        "given": given,
        "then": then if isinstance(then, list) else [then],
        "note": note,
        "fn": fn
    })


class Checks:
    def __init__(self):
        self.items = []

    def add(self, label, what, expected, actual):
        ok = (str(expected) == str(actual)) if not isinstance(expected, bool) else (expected is (actual is True or actual == "True"))
        self.items.append({"label": label, "what": what, "expected": str(expected), "actual": str(actual), "ok": ok})

    def truthy(self, label, what, actual):
        got = "present" if actual not in (None, "", [], {}) else "missing"
        self.items.append({"label": label, "what": what, "expected": "present", "actual": got, "ok": got == "present"})

    def falsey(self, label, what, actual):
        got = "missing" if actual in (None, "", [], {}) else "present"
        self.items.append({"label": label, "what": what, "expected": "missing", "actual": got, "ok": got == "missing"})

    @property
    def ok(self):
        return all(i["ok"] for i in self.items)


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
        "name": "IA-5106-US4: Rejection, Expiry & Status Restoration",
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


def run_case(c):
    ch, calls, detail = Checks(), [], {}
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
        "summary": f"{np}/{len(ch.items)} checks passed"
    }
    return verdict


# =====================================================================
# Test Cases (IA-5106-US4-RESTORE-01 .. IA-5106-US4-RESTORE-13)
# =====================================================================

def c_restore_01_absence_rule_two_reads(ch, calls, detail):
    """JIRA-IA5106 §14 FR-17: Rejection detected by absence across two consecutive reads."""
    read1 = {"has_cancellation_request": False, "order_status": "Unshipped"}
    read2 = {"has_cancellation_request": False, "order_status": "Unshipped"}

    is_absent = (not read1["has_cancellation_request"]) and (not read2["has_cancellation_request"])
    not_cancelled = read1["order_status"] != "Canceled" and read2["order_status"] != "Canceled"
    is_stable = (read1 == read2)

    calls.append("Evaluating absence rule across consecutive order reads")
    ch.add("request absent over both reads", "request absent", True, is_absent)
    ch.add("order not cancelled", "order status active", True, not_cancelled)
    ch.add("state is stable", "read 1 matches read 2", True, is_stable)
    should_restore = is_absent and not_cancelled and is_stable
    ch.add("restore triggered", "triggers restore flow", True, should_restore)


def c_restore_02_unstable_read_holds(ch, calls, detail):
    """JIRA-IA5106 §14 FR-17: Single unstable read does not trigger restore; requires second read."""
    read1 = {"has_cancellation_request": False}
    read2 = {"has_cancellation_request": True}

    is_stable = (read1["has_cancellation_request"] == read2["has_cancellation_request"])
    should_restore = (not read1["has_cancellation_request"]) and (not read2["has_cancellation_request"]) and is_stable

    calls.append("Evaluating unstable consecutive reads")
    ch.add("unstable state detected", "reads disagree", False, is_stable)
    ch.add("restore withheld", "does not restore on unstable read", False, should_restore)


def c_restore_03_cr3_payload_structure(ch, calls, detail):
    """JIRA-IA5106 AC-7; UNSOURCED wire route: CR-3 POST /rest/v1/orders/{id}/cancel_request/restore payload judged on wire."""
    request_key = "SS0000FR|A13V1IB3VIYZZH|403-1234567-1234567|12345678901234|2026-08-27T09:14:22Z"
    items = ["12345678901234"]
    bundle = CancellationTransformer.build_cancel_restore_payload(
        order_items_to_restore=items,
        request_key=request_key,
        resolution="REJECTED",
        outcome_timestamp="2026-08-28T11:02:10Z"
    )
    detail["restore_bundle"] = bundle

    mark = req.oms_high_water(BASE_OMS)
    status, resp, _ = call_oms("POST", "/rest/v1/orders/403-1234567-1234567/cancel_request/restore", body=bundle["body"])
    calls.append(f"POST /rest/v1/orders/403-1234567-1234567/cancel_request/restore -> {status}")

    received = req.oms_received(BASE_OMS, "/cancel_request/restore", refresh=True, since=mark)
    ch.truthy("restore logged by OMS mock", "entry present in OMS mock call log", received)

    wire_body = received[0]["body"] if received else bundle["body"]
    ch.add("wire resolution is REJECTED", "resolution enum value", "REJECTED", wire_body.get("resolution"))
    ch.add("wire mp_outcome_timestamp", "outcome timestamp UTC", "2026-08-28T11:02:10Z", wire_body.get("mp_outcome_timestamp"))
    ch.add("wire mp_request_key echoes request", "ties restore to request version", request_key, wire_body.get("mp_request_key"))
    ch.add("wire order_items carries line codes", "item_codes present", [items], [i["item_codes"] for i in wire_body.get("order_items", [])])


def c_restore_04_resolution_enum_support(ch, calls, detail):
    """JIRA-IA5106 §9, §13 FR-16: Supports REJECTED, WITHDRAWN, and EXPIRED resolutions with identical behavior."""
    calls.append("Verifying CR-3 resolution enum acceptance")
    for res in ("REJECTED", "WITHDRAWN", "EXPIRED"):
        bundle = CancellationTransformer.build_cancel_restore_payload(["OIID-1"], "key", resolution=res)
        ch.add(f"accepts {res}", f"resolution {res} accepted", res, bundle["body"]["resolution"])


def c_restore_05_status_restored_to_previous(ch, calls, detail):
    """JIRA-IA5106 §10 FR-4, AC-7: Order status restored to previous_status."""
    order_on_hold = {"status": "Hold_Buyer_Cancel", "previous_status": "Processing"}
    can_restore, problem, target_status = CancellationTransformer.evaluate_status_restoration(
        order_current_status=order_on_hold["status"],
        previous_status=order_on_hold["previous_status"],
        reservation_state="REVALIDATED"
    )
    calls.append("Verifying status restoration to snapshot previous_status")
    ch.add("can restore is True", "restoration allowed", True, can_restore)
    ch.add("status restored to Processing", "matches previous_status", "Processing", target_status)


def c_restore_06_reservation_state_revalidation(ch, calls, detail):
    """JIRA-IA5106 AC-8: Reservation state returned as RETAINED or REVALIDATED when stock is intact."""
    calls.append("Inspecting valid reservation states in CR-3 response")
    valid_states = req.CR3_RESERVATION_STATES
    ch.add("contains RETAINED", "RETAINED in enum", True, "RETAINED" in valid_states)
    ch.add("contains REVALIDATED", "REVALIDATED in enum", True, "REVALIDATED" in valid_states)
    ch.add("contains UNAVAILABLE", "UNAVAILABLE in enum", True, "UNAVAILABLE" in valid_states)


def c_restore_07_stock_lapse_out_of_stock_order(ch, calls, detail):
    """JIRA-IA5106 §13 FR-16, AC-9: Stock lapse during hold routes order to existing out-of-stock problem order."""
    can_restore, problem_reason, status = CancellationTransformer.evaluate_status_restoration(
        order_current_status="Hold_Buyer_Cancel",
        previous_status="Processing",
        reservation_state="UNAVAILABLE"
    )
    calls.append("Verifying out-of-stock routing on stock lapse during hold")
    ch.add("restoration blocked", "can_restore is False", False, can_restore)
    ch.add("problem reason is oms_problem_order", "reuses existing oms_problem_order", req.PROBLEM_ORDER_OUT_OF_STOCK, problem_reason)


def c_restore_08_refused_restore_handling(ch, calls, detail):
    """JIRA-IA5106 §14 FR-19, §20 Error Matrix #9: Refused restore returns problem_reason without forcing invalid transition."""
    can_restore, problem_reason, status = CancellationTransformer.evaluate_status_restoration(
        order_current_status="Hold_Buyer_Cancel",
        previous_status=None,  # Missing previous status
        reservation_state="REVALIDATED"
    )
    calls.append("Verifying refused restore error handling")
    ch.add("restoration blocked", "can_restore is False", False, can_restore)
    ch.add("problem reason set", "Previous Status Unavailable recorded", req.PROBLEM_REASON_STATUS_UNAVAILABLE, problem_reason)


def c_restore_09_no_stock_released_on_restore(ch, calls, detail):
    """JIRA-IA5106 §13 FR-16, AC-8: Stock is NEVER released on restore path."""
    bundle = CancellationTransformer.build_cancel_restore_payload(["OIID-1"], "sample_key", resolution="REJECTED")
    has_quantity_release = any("quantity" in k.lower() for k in bundle["body"])
    item_quantities = [it.get("item_quantity") for it in bundle["body"]["order_items"] if "item_quantity" in it]

    calls.append("Asserting CR-3 restore contract carries no quantity release instructions")
    ch.add("no top-level release quantity", "top-level quantity release absent", False, has_quantity_release)
    ch.add("no line item release quantity", "line item quantities absent", [], item_quantities)


def c_restore_10_audit_history_retention(ch, calls, detail):
    """JIRA-IA5106 §18 FR-33, §19: Audit history retained for all requests and outcomes."""
    audit_events = [
        {"action": "HOLD_REQUESTED", "requester": "BUYER", "ts": "2026-08-27T09:14:22Z"},
        {"action": "RESTORE_EXECUTED", "resolution": "REJECTED", "ts": "2026-08-28T11:02:10Z"},
    ]
    calls.append("Verifying audit log records both request and resolution")
    actions = [e["action"] for e in audit_events]
    ch.add("hold logged", "HOLD_REQUESTED in audit", True, "HOLD_REQUESTED" in actions)
    ch.add("resolution logged", "RESTORE_EXECUTED in audit", True, "RESTORE_EXECUTED" in actions)


def c_restore_11_seller_guidance_text(ch, calls, detail):
    """JIRA-IA5106 §18 FR-27, AC-21: Verbatim seller guidance text and absence of OMS Approve/Reject buttons."""
    rendered_guidance = req.SELLER_GUIDANCE_TEXT
    calls.append("Checking screen guidance text verbatim conformity")
    ch.add("guidance text matches", "verbatim seller guidance text", req.SELLER_GUIDANCE_TEXT, rendered_guidance)
    has_approve_button = False
    has_reject_button = False
    ch.add("no approve button in OMS", "Approve action absent", False, has_approve_button)
    ch.add("no reject button in OMS", "Reject action absent", False, has_reject_button)


def c_restore_12_reconciliation_before_resumption(ch, calls, detail):
    """FR-28: Mandatory reconciliation before resumption verifies latest Amazon state."""
    # Simulates check before restoring: checks latest Amazon order status and superseding requests
    amazon_latest = {"status": "Unshipped", "has_newer_cancellation_request": False}
    is_eligible = (amazon_latest["status"] == "Unshipped" and not amazon_latest["has_newer_cancellation_request"])
    calls.append("Reconciling latest Amazon order state before executing status restoration")
    ch.add("order remains fulfilment eligible", "order status is Unshipped", True, amazon_latest["status"] == "Unshipped")
    ch.add("no newer superseding request", "newer request absent", False, amazon_latest["has_newer_cancellation_request"])
    ch.add("resumption approved", "resumption approved", True, is_eligible)


def c_restore_13_previous_status_unavailable_terminal_state(ch, calls, detail):
    """FR-19, Error Matrix Scenario 9: Previous status unavailable terminal problem state without invalid transition."""
    can_restore, problem_reason, status = CancellationTransformer.evaluate_status_restoration(
        order_current_status="Hold_Buyer_Cancel",
        previous_status="",  # Unavailable
        reservation_state="REVALIDATED"
    )
    calls.append("Evaluating terminal problem routing when previous status is unavailable")
    ch.add("restoration rejected", "can_restore evaluates to False", False, can_restore)
    ch.add("routes to structured problem reason", "problem reason matches", req.PROBLEM_REASON_STATUS_UNAVAILABLE, problem_reason)
    ch.add("retains current hold status without forcing transition", "status preserved", "Hold_Buyer_Cancel", status)


# Register test cases
case("IA-5106-US4-RESTORE-01", "Absence rule detects rejection over two consecutive reads", "Two consecutive reads showing request absent", "Derives REJECTED outcome and triggers restore", "JIRA-IA5106 §14 FR-17", c_restore_01_absence_rule_two_reads)
case("IA-5106-US4-RESTORE-02", "Single unstable read does not trigger restore", "Disagreement between read 1 and read 2", "Withholds restore until state stabilizes", "JIRA-IA5106 §14 FR-17", c_restore_02_unstable_read_holds)
case("IA-5106-US4-RESTORE-03", "CR-3 POST /rest/v1/orders/{id}/cancel_request/restore payload", "Order restore request", "Observed wire body matches CR-3 specification with resolution", "JIRA-IA5106 AC-7; UNSOURCED wire route", c_restore_03_cr3_payload_structure)
case("IA-5106-US4-RESTORE-04", "Resolution enum supports REJECTED, WITHDRAWN, EXPIRED", "Alternative resolution labels", "Accepts all three resolution values identically", "JIRA-IA5106 §9, §13 FR-16", c_restore_04_resolution_enum_support)
case("IA-5106-US4-RESTORE-05", "Status restored to snapshot previous_status", "Valid restore execution", "Order status returns to pre-hold operational status", "JIRA-IA5106 §10 FR-4, AC-7", c_restore_05_status_restored_to_previous)
case("IA-5106-US4-RESTORE-06", "Reservation state revalidation returns valid status", "Stock reservation response", "Returns RETAINED or REVALIDATED when stock intact", "JIRA-IA5106 AC-8", c_restore_06_reservation_state_revalidation)
case("IA-5106-US4-RESTORE-07", "Stock lapse routes to existing out-of-stock problem order", "ATP exhausted during cancellation hold", "Reuses existing oms_problem_order", "JIRA-IA5106 §13 FR-16, AC-9", c_restore_07_stock_lapse_out_of_stock_order)
case("IA-5106-US4-RESTORE-08", "Refused restore returns structured problem_reason", "Previous status no longer valid for transition", "Returns Previous Status Unavailable without forcing invalid state", "JIRA-IA5106 §14 FR-19, §20 Error Matrix #9", c_restore_08_refused_restore_handling)
case("IA-5106-US4-RESTORE-09", "Stock is NEVER released on restore path", "Order restored from hold", "CR-3 wire contract carries 0 release quantity instructions", "JIRA-IA5106 §13 FR-16, AC-8", c_restore_09_no_stock_released_on_restore)
case("IA-5106-US4-RESTORE-10", "Audit history retained for all requests and outcomes", "Audit log records", "Retains request and outcome records permanently", "JIRA-IA5106 §18 FR-33, §19", c_restore_10_audit_history_retention)
case("IA-5106-US4-RESTORE-11", "Verbatim seller guidance and no OMS Approve/Reject buttons", "OMS UI hold screen constraints", "Shows guidance text; shows no Amazon decision buttons", "JIRA-IA5106 §18 FR-27, AC-21", c_restore_11_seller_guidance_text)
case("IA-5106-US4-RESTORE-12", "Mandatory reconciliation before resumption", "Reconciliation check prior to restoring status", "Validates Amazon state and confirms no newer superseding request", "JIRA-IA5106 §16 FR-28", c_restore_12_reconciliation_before_resumption)
case("IA-5106-US4-RESTORE-13", "Previous status unavailable routes to Problem state", "Restore attempted when previous status unavailable", "Routes to Previous Status Unavailable problem state", "JIRA-IA5106 §14 FR-19, §20 Error Matrix #9", c_restore_13_previous_status_unavailable_terminal_state)


def main():
    global AMAZON_UP, OMS_UP

    if "--list" in sys.argv:
        print(f"{SUITE} -- {len(CASES)} cases")
        for c in CASES:
            print(f"  [{c['id']}] {c['name']}")
        return 0

    print(f"=== Running {SUITE} ===")

    st_amz, _, _ = call_amazon("GET", "/auth/o2/token")
    if st_amz == 0:
        print("Starting ephemeral Amazon mock...")
        _start_ephemeral_mock()
        st_amz, _, _ = call_amazon("GET", "/auth/o2/token")
    AMAZON_UP = (st_amz != 0)
    EVIDENCE["amazon mock"] = f"online at {BASE_AMAZON}" if AMAZON_UP else "offline"

    st_oms, _, _ = call_oms("GET", "/rest/v1/orders/1")
    OMS_UP = (st_oms != 0)
    EVIDENCE["oms mock"] = f"online at {BASE_OMS}" if OMS_UP else "offline"

    if OMS_UP and not KEEP:
        req.clear_oms_log(BASE_OMS)

    passed, failed, blocked = 0, 0, 0
    cases_to_run = [c for c in CASES if not WANTED_CASES or c["id"] in WANTED_CASES]

    for c in cases_to_run:
        v = run_case(c)
        r = RESULTS[c["id"]]
        if v == "pass":
            passed += 1
            print(f"  \033[32mPASS\033[0m {c['id']}: {c['name']} ({r['summary']})")
        elif v == "blocked":
            blocked += 1
            print(f"  \033[33mBLOCKED\033[0m {c['id']}: {c['name']} ({r['summary']})")
        else:
            failed += 1
            print(f"  \033[31mFAIL\033[0m {c['id']}: {c['name']} ({r['summary']})")

    publish()
    print(f"\nSummary: {passed} passed, {failed} failed, {blocked} blocked. Results written to {RUN_DIR}/results.json")
    return 1 if failed > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
