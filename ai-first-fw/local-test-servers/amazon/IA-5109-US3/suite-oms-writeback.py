#!/usr/bin/env python3
"""IA-5109 US3 -- Flow 1, the write-back: what Anchanto OMS is told about each outcome.

**Flow 1 is the `POST_ORDER_FULFILLMENT_DATA` order fulfilment feed.** The outcomes written back
here are the feed's three -- `submitted-and-not-rejected`, `rejected`, `unknown` -- and not
`confirmShipment`'s, which is Flow 2 and deferred by `D1`.

WHAT THIS SUITE PROVES
  The local Anchanto OMS mock accepts the `CREATE_ORDER_SHIPMENT` write-back of mapping 4.4 and
  records it, so the three outcomes are distinguishable on the wire and none of them can reach OMS
  carrying an order number where a tracking number belongs.

WHAT IT DOES NOT PROVE
  **It never starts JPluger.** The connector posts this payload in production; this suite posts it
  itself, built by `requirements.py` from the documents. `C-11`, `C-12` and `C-14` are proved by
  `AmazonRtsWriteBackAndDuplicateTest` and `AmazonMPScheduledServiceTest` in JPluger.
  Nor does it prove OMS accepts `unknown`: that is `CR-5`, an ask in flight. The mock records the
  value because we asked it to, which is the agreed shape under test and not evidence OMS ships it.
  Note `N-15` is open beside it -- whether OMS reads a populated `failure_reason` as failure
  regardless of the status is NOT ESTABLISHED, and OMS must answer it.

  Per-package outcomes are out of reach entirely: the notification carries one scalar tracking
  number, so `CR-1` and `CR-4` block `D-3` through `D-7` and `D-13`. Nothing here pretends otherwise.

Runner contract: `local-test-servers/TESTING.md`.

Usage:
  python3 amazon/IA-5109-US3/suite-oms-writeback.py
  python3 amazon/IA-5109-US3/suite-oms-writeback.py --list
  python3 amazon/IA-5109-US3/suite-oms-writeback.py IA-5109-US3-WB-UNKNOWN
"""

import datetime
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import requirements as R
import runner

SUITE = runner.Suite(
    "IA-5109-US3-oms-writeback",
    "IA-5109-US3: Flow 1 write-back -- the three outcomes Anchanto OMS is told",
    proves="the OMS mock records the mapping-4.4 write-back, and the three outcomes are "
           "distinguishable on the wire",
    does_not_prove="anything about JPluger, and nothing about OMS accepting 'unknown' -- that is "
                   "CR-5, still an ask",
    base_url="",
)

BASE_OMS = ""
RUN_TAG = datetime.datetime.now().strftime("%H%M%S")

OMS_ORDER_ID = 41277
ITEM_CODE_1 = "05015851154158"

# The reason the poll records against an unknown outcome. It is the cause, because CR-5 requires the
# submission be reconciled rather than retried, and reconciliation needs to know why.
UNKNOWN_REASON = "feed reached a terminal status carrying no processing report"
BLOCKED_REASON = "no tracking number on the shipment, so the confirmation is not sent to Amazon"


def order_number(suffix):
    return "902-%s-%s" % (RUN_TAG, suffix)


def shipment(suffix, tracking=True, lines=None):
    return R.Shipment(
        order_number=order_number(suffix),
        tracking_number=("CJ-55812-" + suffix) if tracking else None,
        shipment_number="SHIP-" + suffix,
        shipping_provider="Startrack",
        shipping_type="FPP (Fixed Price Premium)",
        line_items=lines if lines is not None else [R.LineItem(90114455, [ITEM_CODE_1], 1)],
    )


def post_writeback(ch, calls, payload, label, expect=200):
    status, body = R.http_json("POST", BASE_OMS + "/rest/v1/orders/shipping_details", payload)
    calls.append("POST /rest/v1/orders/shipping_details (%s) -> %s" % (label, status))
    ch.add("OMS accepted the %s write-back" % label,
           "%d -- the connector posts this in production; we post it directly here" % expect,
           expect, status)
    return body


def recorded_for(tracking_number):
    """The rows the OMS mock holds for one tracking number, in the order it recorded them."""
    return [row for row in runner.oms_store("shipping_pushes")
            if row.get("tracking_number") == tracking_number]


def write_back(ch, calls, one, outcome, reason=None, label=None, expect=200):
    payload = R.build_writeback(one, outcome, reason=reason, oms_order_id=OMS_ORDER_ID)
    post_writeback(ch, calls, payload, label or outcome, expect=expect)
    rows = recorded_for(one.tracking_number)
    ch.add("one row recorded", "the mock kept what was posted", 1, len(rows))
    return rows[-1] if rows else {}


# ===================================================================== Cases -- the three outcomes


def case_not_rejected(ch, calls, detail):
    one = shipment("OK")
    row = write_back(ch, calls, one, R.SUBMITTED_NOT_REJECTED)

    ch.add("status", "success -- OMS's status field admits two values today (L-44), so "
                     "submitted-and-not-rejected rides the existing one",
           R.WRITEBACK_SUCCESS, row.get("status"))
    ch.add("tracking number", "exactly what OMS sent (C-11, L-42)",
           one.tracking_number, row.get("tracking_number"))
    ch.absent("no failure reason", "nothing went wrong, so there is nothing to reconcile",
              row.get("failure_reason"))
    ch.add("order id", "identifies the OMS shipment the outcome belongs to",
           str(OMS_ORDER_ID), str(row.get("order_id")))
    detail["row"] = row


def case_rejected(ch, calls, detail):
    one = shipment("REJ")
    reason = "Invalid tracking id for carrier Other"
    row = write_back(ch, calls, one, R.REJECTED, reason=reason)

    ch.add("status", "failure -- Amazon rejected the message", R.WRITEBACK_FAILURE, row.get("status"))
    ch.add("failure reason", "Amazon's own ResultDescription; the seller needs it to act (L-44)",
           reason, row.get("failure_reason"))
    ch.add("tracking number still carried", "a rejection does not blank the tracking number",
           one.tracking_number, row.get("tracking_number"))


def case_unknown(ch, calls, detail):
    one = shipment("UNK")
    row = write_back(ch, calls, one, R.UNKNOWN, reason=UNKNOWN_REASON)

    ch.add("status", "unknown -- its own value, distinct from failure (C-12)",
           R.WRITEBACK_UNKNOWN, row.get("status"))
    ch.add("not reported as a failure", "telling OMS the confirmation did not happen sends the "
                                        "seller to re-confirm a package Amazon may already hold",
           True, row.get("status") != R.WRITEBACK_FAILURE)
    ch.add("the cause travels", "CR-5 requires reconciliation, not retry, and reconciliation needs "
                                "the cause; failure_reason is the only free-text slot OMS reads",
           UNKNOWN_REASON, row.get("failure_reason"))
    ch.add("tracking number carried", "so the package can be found again", one.tracking_number,
           row.get("tracking_number"))


def case_three_statuses_distinct(ch, calls, detail):
    rows = {}
    for suffix, outcome, reason in (("D1", R.SUBMITTED_NOT_REJECTED, None),
                                    ("D2", R.REJECTED, "Invalid CarrierCode"),
                                    ("D3", R.UNKNOWN, UNKNOWN_REASON)):
        one = shipment(suffix)
        rows[outcome] = write_back(ch, calls, one, outcome, reason=reason, label=outcome)

    statuses = [row.get("status") for row in rows.values()]
    ch.add("three distinct statuses", "D-20a's three outcomes are distinguishable at OMS",
           3, len(set(statuses)))
    ch.add("statuses", "success, failure, unknown", "['success', 'failure', 'unknown']",
           str(statuses))
    ch.add("unknown is not failure", "the misreport C-12 exists to prevent",
           True, rows[R.UNKNOWN].get("status") != rows[R.REJECTED].get("status"))
    detail["statuses"] = statuses


# ===================================================================== Cases -- the tracking number


def case_never_the_order_number(ch, calls, detail):
    one = shipment("NOTRACK", tracking=False)
    payload = R.build_writeback(one, R.REJECTED, reason=BLOCKED_REASON, oms_order_id=OMS_ORDER_ID)

    ch.absent("tracking number absent", "C-11 -- a shipment that never had one is written back with "
                                        "none, not with a stand-in",
              payload["shipping_details"]["tracking_number"])
    ch.add("the order number is not it", "the previous code substituted getOrderNumber(); OMS shows "
                                         "this field to the seller as the buyer's tracking (L-42)",
           True, payload["shipping_details"]["tracking_number"] != one.order_number)
    ch.add("no order number anywhere in the payload", "D-16 on the write-back half",
           False, one.order_number in str(payload))

    # FINDING, not a passing behaviour. The OMS mock declares shipping_details.tracking_number
    # REQUIRED, so the very write-back C-11 mandates -- a refused shipment reported with no
    # tracking number -- is refused 422 by the contract on disk. Asserted as observed rather than
    # worked around: if OMS relaxes the field, this case fails and someone reads the collision.
    post_writeback(ch, calls, payload, "refused shipment", expect=422)
    ch.add("nothing recorded", "a 422 leaves no row, so the refusal never reached OMS at all",
           0, len([row for row in runner.oms_store("shipping_pushes")
                   if row.get("failure_reason") == BLOCKED_REASON]))
    detail["finding"] = ("anchanto-oms.mock.json requires shipping_details.tracking_number, which "
                         "collides with C-11's 'send the real tracking number or none'")


def case_refused_is_reported(ch, calls, detail):
    """A shipment refused before submission is told to OMS -- and the OMS contract turns it away."""
    blocked = shipment("BLOCKED", tracking=False)
    kept = shipment("KEPT")

    confirmable = R.with_tracking_number([blocked, kept])
    ch.add("the refused shipment never reaches Amazon", "C-1", 1, len(confirmable))
    ch.add("it is still reported rather than only logged", "C-11 -- a refusal OMS is never told "
                                                           "about leaves the seller with nothing",
           R.WRITEBACK_FAILURE,
           R.build_writeback(blocked, R.REJECTED)["shipping_details"]["status"])
    ch.add("as a definite failure", "the confirmation was never submitted, so this outcome is "
                                    "determined -- not the unknown a feed of undecidable fate earns",
           True, R.WRITEBACK_FAILURE != R.WRITEBACK_UNKNOWN)

    post_writeback(ch, calls,
                   R.build_writeback(blocked, R.REJECTED, reason=BLOCKED_REASON,
                                     oms_order_id=OMS_ORDER_ID),
                   "blocked", expect=422)
    post_writeback(ch, calls,
                   R.build_writeback(kept, R.SUBMITTED_NOT_REJECTED, oms_order_id=OMS_ORDER_ID),
                   "submitted")

    ch.add("the sibling still reports its own outcome", "a blocked shipment does not take the "
                                                        "batch with it",
           R.WRITEBACK_SUCCESS,
           (recorded_for(kept.tracking_number) or [{}])[-1].get("status"))
    ch.add("the refusal did not land", "same finding as WB-NEVER-ORDER-NUMBER: the OMS contract "
                                       "requires the field C-11 leaves empty",
           0, len([row for row in runner.oms_store("shipping_pushes")
                   if row.get("failure_reason") == BLOCKED_REASON]))


# ===================================================================== Cases -- lines and isolation


def case_line_items(ch, calls, detail):
    one = shipment("LINES", lines=[
        R.LineItem(90114455, [ITEM_CODE_1], 2),
        R.LineItem(90114456, ["05015851154159"], 3),
    ])
    row = write_back(ch, calls, one, R.SUBMITTED_NOT_REJECTED)
    items = row.get("order_items") or []

    ch.add("one entry per line", "the outcome names every line it covers", 2, len(items))
    ch.add("line id is a string", "cast to string on the write-back (L-43)", "90114455",
           items[0].get("id") if items else None)
    ch.add("first quantity", "line_items[*].quanity carried through (L-43)", 2,
           items[0].get("itemQuantity") if items else None)
    ch.add("second line id", "the second line is not folded into the first", "90114456",
           items[1].get("id") if len(items) > 1 else None)
    detail["order_items"] = items


def case_sibling_isolation(ch, calls, detail):
    """The rejecting report's two messages write back independently."""
    first = shipment("SIB1")
    second = shipment("SIB2")

    # Message 1 is not rejected; message 2 is, with Amazon's own reason.
    reason = "Invalid tracking id for carrier Other"
    first_row = write_back(ch, calls, first, R.SUBMITTED_NOT_REJECTED, label="message 1")
    second_row = write_back(ch, calls, second, R.REJECTED, reason=reason, label="message 2")

    ch.add("message 1 succeeds", "D-8 -- a rejected message must not mark its sibling failed (L-89)",
           R.WRITEBACK_SUCCESS, first_row.get("status"))
    ch.add("message 2 fails", "and carries its own reason", R.WRITEBACK_FAILURE,
           second_row.get("status"))
    ch.absent("no reason on the sibling", "the failure does not leak across",
              first_row.get("failure_reason"))
    ch.add("two rows, two tracking numbers", "each outcome is addressed to its own package",
           True, first_row.get("tracking_number") != second_row.get("tracking_number"))


def case_oms_unavailable(ch, calls, detail):
    """OMS refusing the write-back is visible rather than swallowed."""
    one = shipment("OMS500")
    payload = R.build_writeback(one, R.REJECTED, reason="SERVERERROR while reconciling",
                                oms_order_id=OMS_ORDER_ID)
    post_writeback(ch, calls, payload, "OMS 500", expect=500)
    ch.add("nothing recorded on a refusal", "a write-back OMS refused left no row, so it cannot be "
                                            "mistaken for one that landed",
           0, len(recorded_for(one.tracking_number)))
    ch.add("what happens next is not this suite's", "re-driving a refused write-back is Cluster A, "
                                                    "and nothing on the tree does it", True, True)


# ===================================================================== Registration

SUITE.case("IA-5109-US3-WB-NOT-REJECTED",
           "A message the report did not reject writes back as success",
           "the first of D-20a's three outcomes",
           ["status success, carrying no failure reason",
            "the tracking number is exactly what OMS sent"],
           "C-11. Not acceptance: nothing this codebase receives establishes Amazon accepted, and "
           "OMS's status field admits two values today (L-44), so this outcome rides the existing "
           "one and the third is reserved for unknown.",
           case_not_rejected)

SUITE.case("IA-5109-US3-WB-REJECTED",
           "A rejected message writes back as failure with Amazon's reason",
           "the processing report's ResultDescription",
           ["status failure",
            "failure_reason is Amazon's own description"],
           "AC-17's first half. The 'allow correction' half is Cluster A -- nothing on the tree "
           "re-drives a rejected confirmation, and C-4's pre-rejection was dropped by D6.",
           case_rejected)

SUITE.case("IA-5109-US3-WB-UNKNOWN",
           "An undetermined outcome writes back as unknown, never as failure",
           "a feed that reached a terminal status carrying no processing report",
           ["status unknown, distinct from failure",
            "the cause travels in failure_reason so the submission can be reconciled"],
           "C-12, CR-5, AC-18. Blocked on CR-5: OMS is asked to accept the value and has not yet. "
           "N-15 is open beside it -- whether OMS reads a populated failure_reason as failure "
           "regardless of the status is NOT ESTABLISHED.",
           case_unknown)

SUITE.case("IA-5109-US3-WB-THREE-DISTINCT",
           "The three outcomes are distinguishable at OMS",
           "one write-back of each outcome",
           ["three distinct status values reach OMS",
            "unknown is not failure"],
           "D-20a. Every submission reaches one of exactly three terminal outcomes; collapsing two "
           "of them is the misreport the third exists to prevent.",
           case_three_statuses_distinct)

SUITE.case("IA-5109-US3-WB-NEVER-ORDER-NUMBER",
           "A shipment with no tracking number is written back with none, and OMS refuses it",
           "a shipment OMS sent carrying no tracking number",
           ["tracking_number is absent, not substituted, and the order number appears nowhere",
            "the OMS mock answers 422 and records nothing"],
           "C-11, D-16 -- and a FINDING. anchanto-oms.mock.json declares "
           "shipping_details.tracking_number REQUIRED, so the very write-back C-11 mandates is "
           "refused by the contract on disk. Asserted as observed rather than worked around: if OMS "
           "relaxes the field this case fails and someone reads the collision. Neither mock was "
           "edited to make it pass.",
           case_never_the_order_number)

SUITE.case("IA-5109-US3-WB-REFUSED-REPORTED",
           "A refused shipment is reported as a definite failure, and its sibling is unaffected",
           "a batch of two, one refused for having no tracking number",
           ["the refusal is built as a failure carrying its reason, not left to a log",
            "the sibling's own outcome still lands at OMS",
            "the refusal itself is turned away 422 by the OMS contract"],
           "C-11 and C-1. The refusal is a determined outcome -- the confirmation was never "
           "submitted -- so it is a failure, not the unknown an undecidable feed earns. The 422 is "
           "the same finding as WB-NEVER-ORDER-NUMBER.",
           case_refused_is_reported)

SUITE.case("IA-5109-US3-WB-LINE-ITEMS",
           "The write-back names every line the outcome covers",
           "a shipment covering two lines",
           ["one order_items entry per line",
            "the OMS line id as a string, and its quantity"],
           "MAP 4.4. Per-package allocation is D-5, blocked on CR-1; this is per order.",
           case_line_items)

SUITE.case("IA-5109-US3-WB-SIBLING-ISOLATION",
           "A rejected message does not mark its sibling failed",
           "one feed whose report rejects the second message only",
           ["message 1 writes back success with no reason",
            "message 2 writes back failure with its own"],
           "D-8, E-11 at feed-message grain. Carton-grouped packages still need CR-1 and CR-4.",
           case_sibling_isolation)

SUITE.case("IA-5109-US3-WB-OMS-REFUSES",
           "A write-back OMS refuses leaves no row",
           "the OMS mock's SERVERERROR marker",
           ["OMS answers 500",
            "nothing is recorded, so a refused write-back cannot be read as one that landed"],
           "What happens next is Cluster A and is not built: nothing on the tree re-drives a "
           "refused write-back.",
           case_oms_unavailable)


def preflight():
    global BASE_OMS
    BASE_OMS = runner.start_oms_mock(os.path.join(SUITE.run_dir, "oms-state"))
    SUITE.base_url = BASE_OMS
    SUITE.evidence["oms mock"] = "%s (started by this suite, run-scoped state)" % BASE_OMS
    status, _ = R.http_json("POST", BASE_OMS + "/rest/v1/orders/shipping_details",
                            {"shipping_details": {"id": 0, "tracking_number": "PREFLIGHT",
                                                  "status": "success"}})
    if status != 200:
        print("  the Anchanto OMS mock did not answer shipping_details (%s)" % status)
        sys.exit(2)


def capture():
    SUITE.evidence["oms call log"] = runner.capture_har(
        SUITE.run_dir, os.path.join(SUITE.run_dir, "oms-state"), "oms call log")


if __name__ == "__main__":
    sys.exit(SUITE.main(preflight=preflight, capture=capture))
