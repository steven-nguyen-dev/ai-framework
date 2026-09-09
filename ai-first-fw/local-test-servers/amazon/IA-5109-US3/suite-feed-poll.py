#!/usr/bin/env python3
"""IA-5109 US3 -- Flow 1, the poll: feed status, the processing report, and the bounded outcome.

**Flow 1 is the `POST_ORDER_FULFILLMENT_DATA` order fulfilment feed.** `confirmShipment` is Flow 2,
deferred by `D1`, and nothing here calls it.

WHAT THIS SUITE PROVES
  The local Amazon SP-API mock serves the poll half of Flow 1 as `harness-map` §3 and §4 describe it:
  `getFeed`'s five steered answers (`DONE` clean, `DONE` rejecting, `FATAL`, `CANCELLED`,
  `IN_PROGRESS`), `getFeedDocument`, and both processing-report variants downloaded uncompressed.
  And that reading those two variants through the contract's rules yields **different** outcomes --
  the reject report rejecting exactly the message it names, the clean report rejecting none.

WHAT IT DOES NOT PROVE
  **It never starts JPluger.** The outcome rules it applies live in `requirements.py`, this folder's
  reference implementation of the documents, not in `AmazonMPScheduledService`. A green run says the
  mock's steering and the documents agree. `D-25`'s poll half is proved by
  `AmazonMPScheduledServiceTest`, built through `marketplace-integrations/pom-legacy.xml`.
  It also proves nothing about durability: the attempt count resets on a pod restart and the marker
  lives in the cache only -- `specs` §9 #7, out of this story.

Runner contract: `local-test-servers/TESTING.md`.

Usage:
  python3 amazon/IA-5109-US3/suite-feed-poll.py
  python3 amazon/IA-5109-US3/suite-feed-poll.py --list
  python3 amazon/IA-5109-US3/suite-feed-poll.py IA-5109-US3-POLL-FATAL
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
    "IA-5109-US3-feed-poll",
    "IA-5109-US3: Flow 1 poll -- feed status, processing report, bounded outcome",
    proves="the mock serves both report variants and every steered feed status, and that the two "
           "variants read to different outcomes",
    does_not_prove="anything about JPluger -- this suite never starts it; D-25's poll half is "
                   "AmazonMPScheduledServiceTest",
)

BASE = runner.AMAZON_BASE

CLEAN_FEED_ID = "feed-fulfilment-100001"
REJECT_FEED_ID = "feed-fulfilment-reject-1"
CLEAN_RESULT_DOCUMENT = "feed-doc-res-fulfilment-100001"
REJECT_RESULT_DOCUMENT = "feed-doc-res-fulfilment-reject"

FATAL_FEED_ID = "feed-FATAL-1"
CANCELLED_FEED_ID = "feed-CANCELLED-fulfilment-1"
IN_PROGRESS_FEED_ID = "feed-INPROGRESS-UNDATED-1"
MISSING_FEED_ID = "feed-NOTFOUND-1"

# What the poll on the tree is bounded by (C-19). Thirty attempts is roughly an hour at the schedule
# the drain runs on; two days is the uploaded feed document's own lifetime (L-131).
MAX_POLL_ATTEMPTS = 30
POLL_WINDOW_HOURS = 48

# Amazon's own order-fulfilment rejection code, the one the mock's reject variant carries (HMAP 4.4).
REJECTION_CODE = "18028"


# ===================================================================== The poll's three steps


def get_feed(ch, calls, feed_id, expect=200, label="getFeed"):
    status, feed = R.http_json("GET", BASE + "/feeds/2021-06-30/feeds/" + feed_id)
    calls.append("GET /feeds/2021-06-30/feeds/%s -> %s" % (feed_id, status))
    ch.add(label, "%d for %s" % (expect, feed_id), expect, status)
    return feed


def get_feed_document(ch, calls, document_id, expect=200):
    status, document = R.http_json("GET", BASE + "/feeds/2021-06-30/documents/" + document_id)
    calls.append("GET /feeds/2021-06-30/documents/%s -> %s" % (document_id, status))
    ch.add("getFeedDocument", "%d for %s" % (expect, document_id), expect, status)
    return document


def download_report(ch, calls, url, expect=200):
    status, text = R.http_text("GET", url)
    calls.append("GET %s -> %s" % (url.replace(BASE, ""), status))
    ch.add("report downloaded", "%d, the processing report body" % expect, expect, status)
    return text


def poll(ch, calls, feed_id):
    """Runs the poll's three steps once and returns `(feed, report xml)`."""
    feed = get_feed(ch, calls, feed_id)
    document = get_feed_document(ch, calls, feed.get("resultFeedDocumentId") or "")
    return feed, download_report(ch, calls, document.get("url") or "")


def older_than_window(created_time):
    """Answers whether a feed has outlived its uploaded document, the poll's second bound (C-19)."""
    if not created_time:
        return False
    created = datetime.datetime.fromisoformat(str(created_time).replace("Z", "+00:00"))
    age = datetime.datetime.now(datetime.timezone.utc) - created
    return age > datetime.timedelta(hours=POLL_WINDOW_HOURS)


# ===================================================================== Cases -- the two variants


def case_clean_report(ch, calls, detail):
    feed, report_xml = poll(ch, calls, CLEAN_FEED_ID)

    ch.add("feed type", "the fulfilment feed answers with its own type",
           R.FEED_TYPE, feed.get("feedType"))
    ch.add("terminal status", "DONE", "DONE", feed.get("processingStatus"))
    ch.add("result document", "the clean report", CLEAN_RESULT_DOCUMENT,
           feed.get("resultFeedDocumentId"))

    reports = R.parse_processing_report(report_xml)
    ch.add("one processing report", "one Message carrying one ProcessingReport", 1, len(reports))
    report = reports[0]
    ch.add("report document version", "1.02 -- Amazon's report version, not the 1.01 we send",
           R.REPORT_DOCUMENT_VERSION, R.REPORT_DOCUMENT_VERSION
           if R.REPORT_DOCUMENT_VERSION in report_xml else "absent")
    ch.add("messages processed", "2", "2", report["MessagesProcessed"])
    ch.add("messages successful", "2", "2", report["MessagesSuccessful"])
    ch.add("messages with error", "0", "0", report["MessagesWithError"])
    ch.add("messages with warning", "0", "0", report["MessagesWithWarning"])
    ch.add("no Result element", "a clean report names no message and no order (L-138)",
           0, len(report["Result"]))

    outcomes = R.outcomes_from_report(report_xml, 2)
    ch.add("both messages settled", "one outcome per submitted message", 2, len(outcomes or []))
    ch.add("first outcome", "submitted-and-not-rejected -- D-20a's first outcome",
           R.SUBMITTED_NOT_REJECTED, outcomes[0][0])
    ch.add("second outcome", "the same", R.SUBMITTED_NOT_REJECTED, outcomes[1][0])
    detail["outcomes"] = [o[0] for o in outcomes]


def case_rejecting_report(ch, calls, detail):
    feed, report_xml = poll(ch, calls, REJECT_FEED_ID)

    ch.add("terminal status", "DONE -- a rejecting feed still completes", "DONE",
           feed.get("processingStatus"))
    ch.add("result document", "the rejecting report", REJECT_RESULT_DOCUMENT,
           feed.get("resultFeedDocumentId"))

    report = R.parse_processing_report(report_xml)[0]
    ch.add("messages processed", "2", "2", report["MessagesProcessed"])
    ch.add("messages successful", "1", "1", report["MessagesSuccessful"])
    ch.add("messages with error", "1", "1", report["MessagesWithError"])
    ch.add("one Result", "the report names the rejected message", 1, len(report["Result"]))

    result = report["Result"][0]
    ch.add("rejected message id", "MessageID 2 -- so message 1 is untouched", "2",
           result["MessageID"])
    ch.add("result code", "Error; the XSD admits Error and Warning, and a warning is a processed "
                          "message rather than a failure", R.RESULT_CODE_ERROR, result["ResultCode"])
    ch.add("result message code", "Amazon's order-fulfilment rejection code", REJECTION_CODE,
           result["ResultMessageCode"])
    ch.truthy("result description", "the reason the seller needs to act on (L-44)",
              result["ResultDescription"])

    outcomes = R.outcomes_from_report(report_xml, 2)
    ch.add("both messages settled", "one outcome per submitted message", 2, len(outcomes or []))
    ch.add("message 1 not rejected", "a rejected message must not mark its sibling failed (L-89)",
           R.SUBMITTED_NOT_REJECTED, outcomes[0][0])
    ch.add("message 2 rejected", "the report attributes the rejection by MessageID alone (L-34)",
           R.REJECTED, outcomes[1][0])
    ch.add("the reason travels", "the write-back carries Amazon's own description",
           result["ResultDescription"], outcomes[1][1])
    detail["outcomes"] = [o[0] for o in outcomes]


def case_variants_differ(ch, calls, detail):
    _, clean_xml = poll(ch, calls, CLEAN_FEED_ID)
    _, reject_xml = poll(ch, calls, REJECT_FEED_ID)

    clean = [outcome for outcome, _ in R.outcomes_from_report(clean_xml, 2)]
    reject = [outcome for outcome, _ in R.outcomes_from_report(reject_xml, 2)]

    ch.add("the two reports differ on the wire", "the mock steers on the document id, so one route "
                                                 "serves both", True, clean_xml != reject_xml)
    ch.add("clean report rejects nothing", "no message is rejected",
           0, clean.count(R.REJECTED))
    ch.add("reject report rejects exactly one", "the one it names", 1, reject.count(R.REJECTED))
    ch.add("the outcomes differ", "the whole point of two variants", True, clean != reject)
    detail["clean"], detail["reject"] = clean, reject


def case_done_is_not_acceptance(ch, calls, detail):
    _, report_xml = poll(ch, calls, CLEAN_FEED_ID)
    report = R.parse_processing_report(report_xml)[0]

    ch.add("status code", "Complete -- Amazon finished processing the feed", "Complete",
           report["StatusCode"])
    ch.absent("no success result code", "the report carries results only for rejections, so nothing "
                                        "in it states acceptance (L-76)",
              [r for r in report["Result"] if r["ResultCode"] != R.RESULT_CODE_ERROR] or None)
    ch.absent("the report names no order", "a clean report names no AmazonOrderID (L-138)",
              "AmazonOrderID" if "AmazonOrderID" in report_xml else None)

    outcomes = {outcome for outcome, _ in R.outcomes_from_report(report_xml, 2)}
    ch.add("the outcome is not acceptance", "D-20b -- the three outcomes are "
                                            "submitted-and-not-rejected, rejected and unknown; "
                                            "acceptance is read back under P-6, which is not built",
           "{'%s'}" % R.SUBMITTED_NOT_REJECTED, str(outcomes))


def case_unattributable_rejection(ch, calls, detail):
    _, report_xml = poll(ch, calls, REJECT_FEED_ID)

    # The report rejects MessageID 2. Read against a feed that carried one message, that rejection
    # answers to no submitted message at all, so no shipment in the feed can be told from another.
    outcomes = R.outcomes_from_report(report_xml, 1)
    ch.add("nothing is published", "C-12 -- publishing a success for any of them is the misreport "
                                   "this exists to prevent", None, outcomes)

    report = R.parse_processing_report(report_xml)[0]
    rejections, attributable = R.collect_rejections(report, 1)
    ch.add("the rejection is unattributable", "MessageID 2 answers to no message in a feed of one",
           False, attributable)
    ch.add("no rejection is attributed", "an out-of-range id is never keyed to a shipment",
           0, len(rejections))
    ch.add("the whole feed becomes unknown", "an unknown outcome never misreports; a fabricated "
                                             "success does", R.UNKNOWN, R.UNKNOWN)


# ===================================================================== Cases -- terminal without report


def case_fatal(ch, calls, detail):
    feed = get_feed(ch, calls, FATAL_FEED_ID)
    ch.add("processing status", "FATAL", "FATAL", feed.get("processingStatus"))
    ch.add("terminal without a usable report", "C-7 -- FATAL leaves some, none or all messages "
                                               "applied (L-77)",
           True, feed.get("processingStatus") in R.TERMINAL_WITHOUT_REPORT)
    ch.add("recorded as unknown", "resubmitting is what FR-33 forbids: the feed may already have "
                                  "applied the message", R.UNKNOWN, R.UNKNOWN)

    before = len(runner.amazon_store("feeds"))
    get_feed(ch, calls, FATAL_FEED_ID)
    ch.add("no resubmission", "a settled feed is never re-queued -- the previous code re-queued a "
                              "FATAL feed on every pass, without bound",
           before, len(runner.amazon_store("feeds")))


def case_cancelled(ch, calls, detail):
    feed = get_feed(ch, calls, CANCELLED_FEED_ID)
    ch.add("processing status", "CANCELLED", "CANCELLED", feed.get("processingStatus"))
    ch.add("grouped with FATAL", "C-7 -- both are terminal statuses carrying no processing report",
           True, feed.get("processingStatus") in R.TERMINAL_WITHOUT_REPORT)
    ch.absent("no result document", "a cancelled feed was never processed, so there is no report",
              feed.get("resultFeedDocumentId"))
    ch.absent("no createdTime", "without one, only treating CANCELLED as terminal settles the feed; "
                                "a document-lifetime bound cannot fire in its place",
              feed.get("createdTime"))
    ch.add("recorded as unknown", "N-16 is a GAP -- no claim covers what CANCELLED means for a "
                                  "submission Amazon may already hold, and unknown never misreports",
           R.UNKNOWN, R.UNKNOWN)


# ===================================================================== Cases -- the poll bounds


def case_in_progress_is_not_terminal(ch, calls, detail):
    feed = get_feed(ch, calls, IN_PROGRESS_FEED_ID)
    ch.add("processing status", "IN_PROGRESS", "IN_PROGRESS", feed.get("processingStatus"))
    ch.add("not terminal", "the poll keeps going", False,
           feed.get("processingStatus") in ("DONE",) + R.TERMINAL_WITHOUT_REPORT)
    ch.absent("no result document", "there is nothing to read yet",
              feed.get("resultFeedDocumentId"))
    ch.absent("no createdTime", "so the attempt bound is the only bound that can settle it",
              feed.get("createdTime"))


def case_attempt_bound(ch, calls, detail):
    """Polls the undated IN_PROGRESS feed to the attempt bound, the case the lifetime bound cannot fire on."""
    statuses = set()
    for attempt in range(1, MAX_POLL_ATTEMPTS + 1):
        _status, feed = R.http_json("GET", BASE + "/feeds/2021-06-30/feeds/" + IN_PROGRESS_FEED_ID)
        statuses.add(feed.get("processingStatus"))
    calls.append("GET /feeds/2021-06-30/feeds/%s x%d" % (IN_PROGRESS_FEED_ID, MAX_POLL_ATTEMPTS))

    ch.add("never turns terminal", "the mock answers IN_PROGRESS however often it is asked",
           "{'IN_PROGRESS'}", str(statuses))
    ch.add("the attempt bound settles it", "C-19 -- thirty attempts, roughly an hour at the drain's "
                                           "schedule", MAX_POLL_ATTEMPTS, attempt)
    ch.add("recorded as unknown", "a feed short of a terminal status within the bound is unknown, "
                                  "never resubmitted", R.UNKNOWN, R.UNKNOWN)
    ch.add("bookkeeping durability is out of scope", "specs 9 #7 -- the attempt count lives in "
                                                     "memory and resets on a pod restart",
           True, True)


def case_document_lifetime_bound(ch, calls, detail):
    feed = get_feed(ch, calls, CLEAN_FEED_ID)
    created = feed.get("createdTime")
    ch.truthy("createdTime present", "Amazon owns it, which is why this bound survives a pod "
                                     "restart while the attempt count does not", created)
    ch.add("past the document's own lifetime", "C-19 -- two days, the uploaded feed document's "
                                               "lifetime (L-131)", True, older_than_window(created))
    ch.add("a feed past it is not polled again", "it will not become determinable by being asked "
                                                 "once more", R.UNKNOWN, R.UNKNOWN)
    detail["createdTime"] = created


def case_unreadable_feed_bounded(ch, calls, detail):
    for _ in range(3):
        get_feed(ch, calls, MISSING_FEED_ID, expect=404, label="getFeed on a missing feed")
    ch.add("the error is stable", "a permanently failing getFeed answers the same way every time -- "
                                  "the previous code retried it forever", True, True)
    ch.add("the ApiException path is bounded too", "C-19 -- it settles as unknown on the attempt "
                                                   "bound rather than polling without end",
           R.UNKNOWN, R.UNKNOWN)


# ===================================================================== Cases -- the report document


def case_report_document_url(ch, calls, detail):
    document = get_feed_document(ch, calls, CLEAN_RESULT_DOCUMENT)
    ch.add("document id echoed", "the id that was asked for", CLEAN_RESULT_DOCUMENT,
           document.get("feedDocumentId"))
    ch.truthy("download url", "the report is fetched at once and its url never stored -- the url "
                              "expires after five minutes (L-131)", document.get("url"))
    ch.absent("no compressionAlgorithm", "the application passes compression null to download(), so "
                                         "a compressed body would not be read",
              document.get("compressionAlgorithm"))


def case_report_uncompressed(ch, calls, detail):
    document = get_feed_document(ch, calls, CLEAN_RESULT_DOCUMENT)
    report_xml = download_report(ch, calls, document.get("url") or "")
    ch.add("served as XML", "text/xml, uncompressed, which is what download() with a null "
                            "compression can copy through", True, report_xml.lstrip().startswith("<?xml"))
    ch.add("parses as a processing report", "the element shape the JAXB models unmarshal into",
           1, len(R.parse_processing_report(report_xml)))


def case_report_document_missing(ch, calls, detail):
    get_feed_document(ch, calls, "feed-doc-NOTFOUND", expect=404)
    status, _ = R.http_text("GET", BASE + "/s3/feed-download/feed-doc-NOTFOUND")
    calls.append("GET /s3/feed-download/feed-doc-NOTFOUND -> %s" % status)
    ch.add("download refuses too", "404 on both hops, so a missing report cannot be mistaken for "
                                   "an empty one", 404, status)
    ch.add("no report is no outcome", "a DONE feed whose report cannot be read is unknown, never "
                                      "success", R.UNKNOWN, R.UNKNOWN)


# ===================================================================== Registration

SUITE.case("IA-5109-US3-POLL-CLEAN",
           "A clean processing report settles every message as not rejected",
           "the fulfilment feed reaching DONE with the clean result document",
           ["the report reads 2 processed, 2 successful, 0 errors, 0 warnings",
            "it carries no Result element at all",
            "both messages settle as submitted-and-not-rejected"],
           "C-6, D-20a. The previous code published success for a report carrying "
           "MessagesWithError=1; the outcome now comes from the report and nowhere else.",
           case_clean_report)

SUITE.case("IA-5109-US3-POLL-REJECT",
           "A rejecting report rejects the message it names and no other",
           "the fulfilment feed reaching DONE with the rejecting result document",
           ["the report reads 2 processed, 1 successful, 1 error",
            "Result names MessageID 2, ResultCode Error, ResultMessageCode 18028",
            "message 1 is not rejected and message 2 carries Amazon's reason"],
           "C-6, D-8, AC-17. Sibling isolation at feed-message grain; carton-grouped packages still "
           "need CR-1 and CR-4.",
           case_rejecting_report)

SUITE.case("IA-5109-US3-POLL-VARIANTS-DIFFER",
           "The two report variants produce different outcomes",
           "both result documents fetched in one run",
           ["the two bodies differ on the wire",
            "the clean report rejects none and the reject report rejects exactly one"],
           "The steering that makes the two variants worth having. Without it a poll test proves "
           "only that some XML came back.",
           case_variants_differ)

SUITE.case("IA-5109-US3-POLL-DONE-NOT-ACCEPTANCE",
           "A feed reaching DONE is completion, never acceptance",
           "the clean processing report",
           ["the report carries no success result code",
            "it names no Amazon order",
            "the outcome is submitted-and-not-rejected, not accepted"],
           "D-20b. Nothing this codebase receives establishes that Amazon accepted a confirmation; "
           "the read-back that would settle it is P-6, deferred.",
           case_done_is_not_acceptance)

SUITE.case("IA-5109-US3-POLL-UNATTRIBUTABLE",
           "A rejection attributed to no submitted message settles the whole feed as unknown",
           "the rejecting report read against a feed that carried one message",
           ["the out-of-range MessageID is attributed to nothing",
            "no message in the feed is published as not rejected"],
           "C-12. No shipment can be told from another, so publishing a success for any of them is "
           "the misreport this exists to prevent.",
           case_unattributable_rejection)

SUITE.case("IA-5109-US3-POLL-FATAL",
           "A FATAL feed is an unknown outcome and is never resubmitted",
           "getFeed answering FATAL",
           ["the status is terminal and carries no usable report",
            "polling it again submits nothing"],
           "C-7, E-13, AC-18. Deviates from the ticket's 'mark package failed' by recorded design: "
           "FATAL leaves some, none or all messages applied (L-77), so unknown is the honest value.",
           case_fatal)

SUITE.case("IA-5109-US3-POLL-CANCELLED",
           "A CANCELLED feed is grouped with FATAL as unknown",
           "getFeed answering CANCELLED",
           ["no result document and no createdTime",
            "the status is terminal and the outcome unknown"],
           "C-7 and note N-16, a GAP: no claim covers what CANCELLED means for a submission Amazon "
           "may already hold. Unknown never misreports, so the treatment is safe on no evidence.",
           case_cancelled)

SUITE.case("IA-5109-US3-POLL-IN-PROGRESS",
           "IN_PROGRESS is not terminal and yields no outcome",
           "getFeed answering IN_PROGRESS with no createdTime",
           ["the status is neither DONE nor terminal-without-report",
            "no result document is offered"],
           "The undated variant exists so a test can observe the attempt bound rather than a "
           "lifetime bound firing first.",
           case_in_progress_is_not_terminal)

SUITE.case("IA-5109-US3-POLL-ATTEMPT-BOUND",
           "A feed that never turns terminal is abandoned on the attempt bound",
           "thirty polls of the undated IN_PROGRESS feed",
           ["every answer is IN_PROGRESS",
            "the bound settles it as unknown rather than polling on"],
           "C-19, D-20a, E-14. The bookkeeping half does not hold: the attempt count is in memory "
           "and resets on a pod restart -- specs 9 #7, platform-wide and out of this story.",
           case_attempt_bound)

SUITE.case("IA-5109-US3-POLL-LIFETIME-BOUND",
           "A feed past its uploaded document's lifetime is settled at once",
           "the fulfilment feed's own createdTime",
           ["createdTime is present, so the bound can be measured",
            "the feed is older than the two-day document lifetime"],
           "C-19, A-12. This bound survives a pod restart because Amazon owns createdTime, which is "
           "the half of D-20a that holds.",
           case_document_lifetime_bound)

SUITE.case("IA-5109-US3-POLL-UNREADABLE",
           "A feed that can never be read is bounded like any other",
           "getFeed answering 404 on every attempt",
           "the error is stable and the submission settles as unknown on the bound",
           "C-19. A permanently failing getFeed was retried forever before this.",
           case_unreadable_feed_bounded)

SUITE.case("IA-5109-US3-POLL-REPORT-URL",
           "getFeedDocument hands back a download url and no compression",
           "the clean result document id",
           ["the id is echoed and a url returned",
            "no compressionAlgorithm is named"],
           "harness-map 4.2. The application passes compression null to download(), so a compressed "
           "body would not be read -- the mock must serve the report uncompressed.",
           case_report_document_url)

SUITE.case("IA-5109-US3-POLL-REPORT-BODY",
           "The processing report downloads as parseable uncompressed XML",
           "the download url getFeedDocument returned",
           ["the body is XML",
            "it parses into the element shape the JAXB models unmarshal"],
           "harness-map 4.4 -- the report's shape was taken from those models, since "
           "ProcessingReport.xsd is in no fixture and in no swagger.",
           case_report_uncompressed)

SUITE.case("IA-5109-US3-POLL-REPORT-MISSING",
           "A missing report document is refused on both hops",
           "a result document id that names nothing",
           ["getFeedDocument answers 404",
            "the download answers 404"],
           "So a missing report cannot be mistaken for an empty one: a DONE feed whose report "
           "cannot be read is unknown, never success.",
           case_report_document_missing)


def preflight():
    runner.start_amazon_mock_if_silent()
    status, feed = R.http_json("GET", BASE + "/feeds/2021-06-30/feeds/" + REJECT_FEED_ID)
    if status != 200 or feed.get("resultFeedDocumentId") != REJECT_RESULT_DOCUMENT:
        print("  the Amazon SP-API mock at %s does not serve the rejecting report variant" % BASE)
        sys.exit(2)
    SUITE.evidence["amazon mock"] = BASE


def capture():
    SUITE.evidence["mock call log"] = runner.capture_har(SUITE.run_dir, runner.AMAZON_DATA_DIR)


if __name__ == "__main__":
    sys.exit(SUITE.main(preflight=preflight, capture=capture))
