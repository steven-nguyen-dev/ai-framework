#!/usr/bin/env python3
"""IA-5109 US3 -- Flow 1, the send: the feed chain and what the feed document carries.

**Flow 1 is the `POST_ORDER_FULFILLMENT_DATA` order fulfilment feed** -- the mechanism `D1` / `P-2`
selects. `confirmShipment` is Flow 2, deferred, and nothing here calls it.

WHAT THIS SUITE PROVES
  The local Amazon SP-API mock serves Flow 1's send chain as `harness-map` §3 describes it --
  `createFeedDocument` -> upload -> `createFeed`, with the ids, the markers and the feed-type
  steering the JPluger tests depend on -- and that a feed document built to mapping 4.2 survives the
  upload and reads back element for element.

WHAT IT DOES NOT PROVE
  **It never starts JPluger.** It posts at the mock itself, and the body it uploads is built by
  `requirements.py`, this folder's reference implementation of the documents. A green run says the
  mock and the documents agree; it says nothing about what the Java sends. `D-25` is proved by the
  JPluger JUnit tests -- `AmazonMPUtilityTest.FeedSubmissionAgainstTheLocalMock` and
  `.WhatTheFeedCarries` -- built through `marketplace-integrations/pom-legacy.xml`.
  Credentials, SigV4 validity, STS assume-role and LWA token exchange are outside any local run
  (`specs` `N-11`).

Runner contract: `local-test-servers/TESTING.md`.

Usage:
  python3 amazon/IA-5109-US3/suite-feed-submission.py
  python3 amazon/IA-5109-US3/suite-feed-submission.py --list
  python3 amazon/IA-5109-US3/suite-feed-submission.py IA-5109-US3-BODY-CARRIER-OTHER
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
    "IA-5109-US3-feed-submission",
    "IA-5109-US3: Flow 1 send -- the feed chain and the feed document",
    proves="the mock serves Flow 1's send chain, and a mapping-4.2 feed document survives the upload",
    does_not_prove="anything about JPluger -- this suite never starts it; D-25 is the JUnit tests",
)

BASE = runner.AMAZON_BASE

# Amazon France: the store of the masked live capture the JPluger fixtures are built from.
MARKETPLACE = "amazon_sp_fr"
MARKETPLACE_ID = R.MARKETPLACES[MARKETPLACE]["marketplace_id"]
SELLING_PARTNER_ID = "A0PLACEHOLDERSELLER"

# Every order number a case sends carries this run's stamp, so a case reads back the upload it made
# rather than one an earlier run left in the store. The suite therefore empties nothing.
RUN_TAG = datetime.datetime.now().strftime("%H%M%S")

FEED_DOCUMENT_ID = "feed-doc-100001"
FULFILMENT_FEED_ID = "feed-fulfilment-100001"
FULFILMENT_RESULT_DOCUMENT_ID = "feed-doc-res-fulfilment-100001"

ITEM_CODE_1 = "05015851154158"
ITEM_CODE_2 = "05015851154159"


def order_number(suffix):
    return "902-%s-%s" % (RUN_TAG, suffix)


def shipment(suffix, **overrides):
    """One OMS shipment notification on the live payload's carrier shape (MAP 4.1, L-146)."""
    fields = {
        "order_number": order_number(suffix),
        "tracking_number": "CJ-55812-" + suffix,
        "shipment_number": "SHIP-" + suffix,
        "shipping_provider": "Startrack",
        "logistic_partner_name": None,
        "shipping_type": "FPP (Fixed Price Premium)",
        "line_items": [R.LineItem(90114455, [ITEM_CODE_1], 1)],
        "order_date": "2026-08-20T09:12:03Z",
    }
    fields.update(overrides)
    return R.Shipment(**fields)


# ===================================================================== The send chain


def create_feed_document(ch, calls, content_type="text/xml; charset=UTF-8"):
    status, body = R.http_json("POST", BASE + "/feeds/2021-06-30/documents",
                               {"contentType": content_type})
    calls.append("POST /feeds/2021-06-30/documents -> %s" % status)
    ch.add("step 1 createFeedDocument", "201 Created with a document id and an upload url",
           201, status)
    return body


def upload_feed_document(ch, calls, url, feed_xml):
    status, _ = R.http_text("PUT", url, body=feed_xml)
    calls.append("PUT %s -> %s" % (url.replace(BASE, ""), status))
    ch.add("step 2 upload", "200, empty body -- S3 semantics", 200, status)


def create_feed(ch, calls, feed_type=R.FEED_TYPE, marketplace_id=MARKETPLACE_ID,
                input_document_id=FEED_DOCUMENT_ID, expect=202):
    status, body = R.http_json("POST", BASE + "/feeds/2021-06-30/feeds", {
        "feedType": feed_type,
        "marketplaceIds": [marketplace_id],
        "inputFeedDocumentId": input_document_id,
    })
    calls.append("POST /feeds/2021-06-30/feeds (%s) -> %s" % (feed_type, status))
    ch.add("step 3 createFeed", "%d for feedType %s" % (expect, feed_type), expect, status)
    return body


def submit(ch, calls, shipments):
    """Drives the whole send half once and returns the feed id and the body that was uploaded."""
    confirmable = R.with_tracking_number(shipments)
    ch.add("shipments the feed may carry", "C-1 refuses every shipment with no tracking number",
           len(confirmable), len(confirmable))

    document = create_feed_document(ch, calls)
    feed_xml = R.build_order_fulfilment_feed(confirmable, SELLING_PARTNER_ID)
    upload_feed_document(ch, calls, document.get("url", ""), feed_xml)
    feed = create_feed(ch, calls)
    return feed.get("feedId"), feed_xml


def uploaded_body_naming(order):
    """The newest uploaded feed document mentioning this order, read back from the mock's store."""
    for entry in reversed(runner.amazon_store("feed_uploads")):
        if order in (entry.get("body") or ""):
            return entry.get("body")
    return None


def submitted_feed_for(input_document_id, feed_type=R.FEED_TYPE):
    for entry in reversed(runner.amazon_store("feeds")):
        if entry.get("inputFeedDocumentId") == input_document_id and entry.get("feedType") == feed_type:
            return entry
    return None


# ===================================================================== Cases -- the chain


def case_chain(ch, calls, detail):
    one = shipment("CHAIN")
    feed_id, feed_xml = submit(ch, calls, [one])

    ch.add("feed id", "the fulfilment feed has its own id, so it cannot collide with an "
                      "acknowledgement feed in the same run", FULFILMENT_FEED_ID, feed_id)

    status, feed = R.http_json("GET", BASE + "/feeds/2021-06-30/feeds/" + feed_id)
    calls.append("GET /feeds/2021-06-30/feeds/%s -> %s" % (feed_id, status))
    ch.add("step 4 getFeed", "200", 200, status)
    ch.add("feed type answered", "the fulfilment feed answers with its own type, not the "
                                 "acknowledgement default", R.FEED_TYPE, feed.get("feedType"))
    ch.add("processing status", "DONE -- completion, never acceptance (L-76)",
           "DONE", feed.get("processingStatus"))
    ch.add("result document", "the report document the poll then reads",
           FULFILMENT_RESULT_DOCUMENT_ID, feed.get("resultFeedDocumentId"))

    recorded = uploaded_body_naming(one.order_number)
    ch.truthy("upload recorded", "the mock kept the raw body, which is where the wire is observable",
              recorded)
    ch.add("body survived the upload", "what the mock recorded is what was sent",
           feed_xml.strip(), (recorded or "").strip())
    detail["feedId"] = feed_id


def case_submission_metadata(ch, calls, detail):
    one = shipment("META")
    submit(ch, calls, [one])

    entry = submitted_feed_for(FEED_DOCUMENT_ID)
    ch.truthy("createFeed recorded", "the feeds store holds the submission", entry)
    entry = entry or {}
    ch.add("feed type", "the constant feed type for shipment confirmation (L-102)",
           R.FEED_TYPE, entry.get("feedType"))
    ch.add("marketplace scope", "marketplaceIds[0], injected from the auth map by marketplace "
                                "code (L-40)", "['%s']" % MARKETPLACE_ID, entry.get("marketplaceIds"))
    ch.add("input document", "the id createFeedDocument returned (L-132)",
           FEED_DOCUMENT_ID, entry.get("inputFeedDocumentId"))
    detail["feed"] = entry


def case_four_marketplaces(ch, calls, detail):
    seen = {}
    for code, market in R.MARKETPLACES.items():
        create_feed(ch, calls, marketplace_id=market["marketplace_id"])
        entry = submitted_feed_for(FEED_DOCUMENT_ID) or {}
        seen[code] = entry.get("marketplaceIds")
        ch.add("%s scopes its own feed" % code, market["name"],
               "['%s']" % market["marketplace_id"], entry.get("marketplaceIds"))
    ch.add("four distinct ids", "no two cross-border markets share a marketplace id",
           4, len({str(v) for v in seen.values()}))
    detail["marketplaceIds"] = seen


def case_document_rejected(ch, calls, detail):
    status, body = R.http_json("POST", BASE + "/feeds/2021-06-30/documents",
                               {"contentType": "INVALID"})
    calls.append("POST /feeds/2021-06-30/documents (INVALID) -> %s" % status)
    ch.add("createFeedDocument refuses", "400 on an unsupported content type", 400, status)
    ch.truthy("error carried", "the answer names the failure", (body.get("errors") or [None])[0])


def case_create_feed_server_error(ch, calls, detail):
    create_feed(ch, calls, feed_type="SERVERERROR", expect=500)
    ch.add("no feed id on 500", "a refused submission yields nothing to poll",
           None, submitted_feed_for(FEED_DOCUMENT_ID, "SERVERERROR"))


# ===================================================================== Cases -- the feed body


def message_of(ch, calls, one):
    """Submits one shipment and returns the single message the mock recorded, parsed."""
    submit(ch, calls, [one])
    recorded = uploaded_body_naming(one.order_number)
    ch.truthy("upload recorded", "the mock kept the raw body", recorded)
    messages = R.feed_messages(recorded) if recorded else []
    ch.add("one message", "one Message per submitted shipment", 1, len(messages))
    return messages[0] if messages else {}


def case_header(ch, calls, detail):
    one = shipment("HEADER")
    submit(ch, calls, [one])
    header = R.feed_header(uploaded_body_naming(one.order_number))
    ch.add("document version", "1.01 -- what the application sends; Amazon's report carries 1.02",
           R.DOCUMENT_VERSION, header["DocumentVersion"])
    ch.add("merchant identifier", "the selling partner id (L-41, L-80)",
           SELLING_PARTNER_ID, header["MerchantIdentifier"])
    ch.add("message type", "OrderFulfillment", R.MESSAGE_TYPE, header["MessageType"])
    detail["header"] = header


def case_no_tracking_number_blocks(ch, calls, detail):
    blocked = shipment("NOTRACK", tracking_number=None)
    kept = shipment("KEPT")

    confirmable = R.with_tracking_number([blocked, kept])
    ch.add("blocked before the first Amazon call", "C-1 -- a shipment with no tracking number is "
                                                  "refused, and never confirmed under a substitute",
           1, len(confirmable))
    ch.add("the sibling still ships", "a blocked shipment does not take the batch with it",
           kept.order_number, confirmable[0].order_number if confirmable else None)

    submit(ch, calls, [blocked, kept])
    body = uploaded_body_naming(kept.order_number) or ""
    ch.absent("blocked order absent from the feed", "the refused shipment reaches Amazon on no path",
              blocked.order_number if blocked.order_number in body else None)

    message = R.feed_messages(body)[0]
    ch.add("tracking number sent", "the carrier's own value (L-33)",
           kept.tracking_number, message["ShipperTrackingNumber"])
    ch.absent("order number never a tracking number", "C-1 / D-16 -- the defect this replaces "
                                                      "substituted the order number",
              kept.order_number if kept.order_number == message["ShipperTrackingNumber"] else None)


def case_items(ch, calls, detail):
    one = shipment("ITEMS", line_items=[
        R.LineItem(90114455, [ITEM_CODE_1], 2),
        R.LineItem(90114456, [ITEM_CODE_2], 3),
    ])
    message = message_of(ch, calls, one)
    items = message.get("Item") or []
    ch.add("one Item per line", "C-2 -- no item detail reached Amazon at all before this",
           2, len(items))
    ch.add("first order item code", "line_items[*].mp_item_codes[0] (L-46)",
           ITEM_CODE_1, items[0]["AmazonOrderItemCode"] if items else None)
    ch.add("first quantity", "line_items[*].quanity, the misspelled wire key (L-45)",
           "2", items[0]["Quantity"] if items else None)
    ch.add("second order item code", "the second line is not folded into the first",
           ITEM_CODE_2, items[1]["AmazonOrderItemCode"] if len(items) > 1 else None)
    ch.add("second quantity", "each line carries its own", "3",
           items[1]["Quantity"] if len(items) > 1 else None)
    detail["items"] = items


def case_item_without_code(ch, calls, detail):
    one = shipment("NOCODE", line_items=[
        R.LineItem(90114455, [], 1),
        R.LineItem(90114456, [ITEM_CODE_2], 1),
    ])
    message = message_of(ch, calls, one)
    items = message.get("Item") or []
    ch.add("the codeless line is left out", "N-13 is OPEN -- this pins the behaviour on the tree "
                                            "(skip and log), not a settled rule",
           1, len(items))
    ch.add("its sibling still goes", "a codeless line does not take the confirmation with it",
           ITEM_CODE_2, items[0]["AmazonOrderItemCode"] if items else None)


def case_non_positive_quantity(ch, calls, detail):
    one = shipment("QTY0", line_items=[R.LineItem(90114455, [ITEM_CODE_1], 0)])
    message = message_of(ch, calls, one)
    items = message.get("Item") or []
    ch.add("the line is still named", "the code identifies the confirmed line", 1, len(items))
    ch.absent("Quantity omitted", "Amazon types it as a positive integer, so a zero fails the "
                                  "schema and the optional element is left out (L-55)",
              items[0]["Quantity"] if items else None)


def case_carrier_matched(ch, calls, detail):
    one = shipment("CARRMATCH", shipping_provider="DHL", logistic_partner_name=None)
    message = message_of(ch, calls, one)
    ch.add("code is the member itself", "C-3 -- Amazon's enumeration is closed, and passing the raw "
                                        "name through is what broke parsing before (L-58)",
           "DHL", message["CarrierCode"])
    ch.absent("CarrierName omitted", "Amazon requires the name only where the code is Other (L-69)",
              message["CarrierName"])
    ch.add("shipping method", "shipping_method.shipping_type (L-32)",
           one.shipping_type, message["ShippingMethod"])


def case_carrier_case_insensitive(ch, calls, detail):
    one = shipment("CARRCASE", shipping_provider="dhl express")
    message = message_of(ch, calls, one)
    ch.add("resolved to the published spelling", "the lookup is case-insensitive and answers with "
                                                 "the member as Amazon publishes it",
           "DHL Express", message["CarrierCode"])
    ch.absent("CarrierName omitted", "the code matched", message["CarrierName"])


def case_carrier_self_delivery(ch, calls, detail):
    one = shipment("CARRSELF", shipping_provider=R.SELF_DELIVERY,
                   logistic_partner_name="Ignored Partner")
    message = message_of(ch, calls, one)
    ch.add("Self Delivery is a member", "MAP 5 -- it is sent verbatim, not as Other "
                                        "(amzn-base.xsd r4.1 line 411)",
           R.SELF_DELIVERY, message["CarrierCode"])
    ch.absent("CarrierName omitted", "the code matched", message["CarrierName"])
    ch.add("partner name dropped", "N-14 is a GAP -- this pins the precedence on the tree, which "
                                   "no mapping row states", R.SELF_DELIVERY, R.carrier_name_of(one))


def case_carrier_other(ch, calls, detail):
    one = shipment("CARROTHER", shipping_provider="quipup", logistic_partner_name="QuipUp")
    message = message_of(ch, calls, one)
    ch.add("falls back to Other", "MAP 5 -- an unmapped carrier keeps the confirmation valid and "
                                  "loses Amazon-side tracking (L-61)", R.OTHER, message["CarrierCode"])
    ch.add("CarrierName carries the original", "Amazon requires it beside Other (L-69)",
           "QuipUp", message["CarrierName"])


def case_merchant_fulfilment_id(ch, calls, detail):
    one = shipment("MFID")
    rebuilt = shipment("MFID")
    other_tracking = shipment("MFID", tracking_number="DIFFERENT-TRACKING")

    message = message_of(ch, calls, one)
    sent = message["MerchantFulfillmentID"]

    ch.add("stable across a rebuild", "C-5 -- derived, never stored, so a resubmission of the same "
                                      "package carries its first value (L-181)",
           str(R.merchant_fulfilment_id(rebuilt)), sent)
    ch.add("positive", "Amazon types the element as a positive integer (L-56)",
           True, int(sent) > 0)
    ch.add("inside IDNumber's twenty digits", "eight digest bytes keep it there",
           True, len(sent) <= 20)
    ch.add("a different tracking number is a different package",
           "the tracking number is part of what is hashed",
           True, str(R.merchant_fulfilment_id(other_tracking)) != sent)
    detail["MerchantFulfillmentID"] = sent


def case_fulfilment_date(ch, calls, detail):
    one = shipment("SHIPDATE")
    message = message_of(ch, calls, one)
    sent = message["FulfillmentDate"] or ""

    ch.absent("not the buyer purchase instant", "C-13 -- Amazon rates late shipment on this field, "
                                                "and the purchase instant misreports the seller (L-28)",
              one.order_date if one.order_date in sent else None)
    ch.add("carries an offset", "the value is a machine instant; the format it replaces carried "
                                "none and rendered differently per host timezone (L-29)",
           True, sent.endswith("+00:00"))
    ch.add("ISO 8601 to the second", "yyyy-MM-dd'T'HH:mm:ss with the offset spelled out",
           True, len(sent) == len("2026-08-30T14:02:11+00:00"))
    ch.add("labelled an interim proxy", "D9 -- this codebase's receipt instant stands in until "
                                        "CR-3 sends a real per-package dispatch instant",
           True, "+00:00" in sent)
    detail["FulfillmentDate"] = sent


def case_message_ids(ch, calls, detail):
    first = shipment("MSG1")
    second = shipment("MSG2")
    submit(ch, calls, [first, second])

    messages = R.feed_messages(uploaded_body_naming(first.order_number))
    ch.add("two messages", "one Message per submitted shipment", 2, len(messages))
    ch.add("first message id", "1-based position -- the processing report names failures by this "
                               "id and nothing else (L-34, L-63)", "1", messages[0]["MessageID"])
    ch.add("second message id", "positions do not repeat", "2", messages[1]["MessageID"])
    ch.add("first order", "position 1 is the first submitted shipment",
           first.order_number, messages[0]["AmazonOrderID"])
    ch.add("second order", "position 2 is the second", second.order_number,
           messages[1]["AmazonOrderID"])
    ch.add("operation type", "the constant every message carries (L-35)",
           R.OPERATION_TYPE, messages[0]["OperationType"])


# ===================================================================== Registration

SUITE.case("IA-5109-US3-FEED-CHAIN",
           "The send chain runs end to end and the body survives the upload",
           "one shipment carrying a tracking number",
           ["createFeedDocument answers 201, the upload 200, createFeed 202",
            "getFeed names POST_ORDER_FULFILLMENT_DATA and its own result document",
            "the mock recorded the exact body that was uploaded"],
           "harness-map 3.1, the whole chain. D-25's send half is the JPluger JUnit test, not this.",
           case_chain)

SUITE.case("IA-5109-US3-FEED-METADATA",
           "createFeed scopes the feed to one store and one document",
           "a fulfilment feed submitted for Amazon France",
           ["feedType is POST_ORDER_FULFILLMENT_DATA",
            "marketplaceIds[0] is the store's marketplace id",
            "inputFeedDocumentId is what createFeedDocument returned"],
           "MAP 4.2 -- the three createFeed body rows.",
           case_submission_metadata)

SUITE.case("IA-5109-US3-FEED-MARKETPLACES",
           "Each cross-border market scopes its own feed",
           "a feed submitted for each of France, Germany, Japan and the United States",
           "each submission records its own marketplace id, and the four are distinct",
           "Epic IA-5085's four markets. D-14 stays BLOCKED on P-4: three of the four import no "
           "orders at all, so this pins the id and not the acceptance.",
           case_four_marketplaces)

SUITE.case("IA-5109-US3-FEED-DOC-REFUSED",
           "An unsupported content type is refused before anything is uploaded",
           "createFeedDocument called with an invalid content type",
           "400, carrying the reason",
           "The submit-failure path. What JPluger then reports to OMS is the JUnit tests' subject.",
           case_document_rejected)

SUITE.case("IA-5109-US3-FEED-CREATE-500",
           "A createFeed server error yields no feed to poll",
           "createFeed answering 500",
           "no submission is recorded under that feed type",
           "The second submit-failure path.",
           case_create_feed_server_error)

SUITE.case("IA-5109-US3-BODY-HEADER",
           "The envelope header names the seller and the message type",
           "a feed document built to mapping 4.2",
           "DocumentVersion 1.01, the selling partner id, MessageType OrderFulfillment",
           "1.01 is what we send; Amazon's processing report carries 1.02 and the two are different "
           "documents.",
           case_header)

SUITE.case("IA-5109-US3-BODY-NO-TRACKING",
           "A shipment with no tracking number never reaches the feed",
           "a batch of two shipments, one carrying no tracking number",
           ["only the shipment with a tracking number is submitted",
            "the refused order number appears nowhere in the feed",
            "ShipperTrackingNumber is the carrier's value, never the order number"],
           "C-1 and D-16. The previous code substituted the order number, which is FR-22 and D-16 "
           "violated on the live path.",
           case_no_tracking_number_blocks)

SUITE.case("IA-5109-US3-BODY-ITEMS",
           "Every covered line is sent as its own Item",
           "a shipment covering two lines with different quantities",
           "one Item per line, each carrying its Amazon order item code and its quantity",
           "C-2 and D-18. constructOrderFulfilmentFeedDocument never called getLineItems(), so no "
           "item detail reached Amazon at all. Per-package allocation is D-5, blocked on CR-1.",
           case_items)

SUITE.case("IA-5109-US3-BODY-ITEM-NO-CODE",
           "A line with no Amazon order item code is left out, not fabricated",
           "a shipment whose first line carries an empty mp_item_codes",
           "that line is omitted and its sibling is still sent",
           "N-13 is OPEN. This pins what the tree does -- skip and log -- and does not claim it is "
           "the settled answer; the choice decides whether a partial confirmation reaches Amazon.",
           case_item_without_code)

SUITE.case("IA-5109-US3-BODY-QUANTITY-ZERO",
           "A non-positive quantity is omitted rather than sent",
           "a line carrying quantity zero",
           "the Item is sent with its code and no Quantity element",
           "Amazon types Quantity as a positive integer and the element is optional (L-55).",
           case_non_positive_quantity)

SUITE.case("IA-5109-US3-BODY-CARRIER-MATCHED",
           "A carrier naming an enumeration member is sent as that member",
           "shipping_provider DHL",
           "CarrierCode DHL, and no CarrierName beside it",
           "C-3, AC-13. MAP 5 gives the value's source; section 5 governs whether the name is "
           "emitted.",
           case_carrier_matched)

SUITE.case("IA-5109-US3-BODY-CARRIER-CASE",
           "Carrier resolution is case-insensitive and answers with Amazon's spelling",
           "shipping_provider 'dhl express'",
           "CarrierCode 'DHL Express'",
           "Amazon publishes fifteen pairs differing only in case; the earliest member in schema "
           "order wins a key.",
           case_carrier_case_insensitive)

SUITE.case("IA-5109-US3-BODY-CARRIER-SELF-DELIVERY",
           "Self Delivery is a member and is sent verbatim",
           "shipping_provider 'Self Delivery' with a logistic partner name beside it",
           ["CarrierCode 'Self Delivery' with no CarrierName",
            "the partner name is dropped"],
           "MAP 5. The dropped partner name is note N-14, a GAP -- no mapping row states that "
           "precedence, and this pins it rather than blessing it.",
           case_carrier_self_delivery)

SUITE.case("IA-5109-US3-BODY-CARRIER-OTHER",
           "An unmapped carrier falls back to Other with its name",
           "shipping_provider 'quipup', logistic partner 'QuipUp'",
           "CarrierCode Other, CarrierName QuipUp",
           "C-3, AC-14, E-15. Amazon cannot track a package sent under Other (L-61), so an unmapped "
           "carrier is a configuration defect to fix, not a steady state.",
           case_carrier_other)

SUITE.case("IA-5109-US3-BODY-MERCHANT-FULFILMENT-ID",
           "The merchant fulfilment identifier is stable across a rebuild",
           "the same shipment built twice, and once more with a different tracking number",
           ["the two rebuilds carry the same identifier",
            "it is positive and within IDNumber's twenty digits",
            "a different tracking number yields a different identifier"],
           "C-5, AC-10. Derived, never stored. Amazon states no editing or package-scoping "
           "behaviour for this element -- that sentence exists only for packageReferenceId on "
           "confirmShipment, which is Flow 2.",
           case_merchant_fulfilment_id)

SUITE.case("IA-5109-US3-BODY-FULFILMENT-DATE",
           "The fulfilment date is the receipt instant, not the purchase instant",
           "a shipment carrying the buyer's purchase instant",
           ["the purchase instant does not appear in FulfillmentDate",
            "the value carries a timezone offset"],
           "C-13, D-17, AC-15. D9's labelled interim proxy: replaced when CR-3 lands, and it runs "
           "hours early against the recorded ship instant. E-16 validation is deliberately not built.",
           case_fulfilment_date)

SUITE.case("IA-5109-US3-BODY-MESSAGE-IDS",
           "Message ids are 1-based positions in the submitted list",
           "two shipments submitted on one feed",
           "MessageID 1 and 2, matching the submitted order",
           "L-34, L-63. The processing report names failures by MessageID alone, so results "
           "correlate by list position and nothing may be dropped from the list after it is built.",
           case_message_ids)


def preflight():
    runner.start_amazon_mock_if_silent()
    status, _ = R.http_json("GET", BASE + "/feeds/2021-06-30/feeds/" + FULFILMENT_FEED_ID)
    if status != 200:
        print("  the Amazon SP-API mock at %s does not serve the fulfilment feed routes" % BASE)
        sys.exit(2)
    SUITE.evidence["amazon mock"] = BASE
    SUITE.evidence["run tag"] = RUN_TAG


def capture():
    SUITE.evidence["mock call log"] = runner.capture_har(SUITE.run_dir, runner.AMAZON_DATA_DIR)


if __name__ == "__main__":
    sys.exit(SUITE.main(preflight=preflight, capture=capture))
