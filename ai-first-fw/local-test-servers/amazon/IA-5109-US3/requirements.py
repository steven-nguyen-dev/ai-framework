#!/usr/bin/env python3
"""IA-5109 US3 -- Flow 1 reference builder and processing-report reader.

**Flow 1 is the `POST_ORDER_FULFILLMENT_DATA` order fulfilment feed**, the mechanism `D1` / `P-2`
selects. `confirmShipment` is Flow 2 and is deferred; nothing in this folder builds it.

What this module is: a reference implementation of the *wire shapes* IA-5109 Flow 1 uses -- the feed
document of mapping 4.2, the processing report of harness-map 4.4, and the write-back of mapping
4.4. The suites in this folder send those shapes at the local mocks and read back what the mocks
recorded.

What this module is **not**: the integration. It does not call JPluger, and JPluger does not call it.
A behaviour agreeing with this file is a behaviour agreeing with the documents; whether the Java
agrees is settled by the JPluger JUnit tests (`AmazonMPUtilityTest`, `AmazonMPScheduledServiceTest`,
`AmazonRtsWriteBackAndDuplicateTest`), which is where `D-25` is proved.

Sources, all under `jpluger-shared/jira-workspace/amazon-cross-border/IA-5109/`:
  MAP   IA-5109-multi-package-confirmation-mapping.md -- 4.1 source, 4.2 feed, 4.4 write-back, 5 enums
  SPEC  IA-5109-multi-package-confirmation-specs.md   -- 2 scope, 4 C-n, 5 definition of done, 6 notes
  HMAP  rebuild-notes/harness-map.md                   -- 3 what the mock serves, 4 the routes and ids
  CODE  JPluger 103a9e6ac5d, 27863f91d29               -- the behaviour these shapes mirror
"""

import datetime
import hashlib
import json
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

# ===================================================================== Feed constants (MAP 4.2)

FEED_TYPE = "POST_ORDER_FULFILLMENT_DATA"

# What the application sends on the feed it uploads. Amazon's own processing report carries 1.02;
# the two are different documents and the versions are not interchangeable (HMAP 4.4).
DOCUMENT_VERSION = "1.01"
REPORT_DOCUMENT_VERSION = "1.02"

MESSAGE_TYPE = "OrderFulfillment"
OPERATION_TYPE = "Update"

# The offset is carried because the value is a machine instant: the format the feed used before this
# work carried none, so the same shipment rendered differently on every host timezone (MAP 4.2, C-13).
FULFILMENT_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"

# Eight digest bytes keep the derived identifier inside IDNumber's twenty digits (C-5, L-56).
MERCHANT_FULFILMENT_ID_BYTES = 8

# ===================================================================== Marketplaces (MAP 4.2, L-40)
#
# createFeed scopes the feed to one Amazon store through marketplaceIds[0], injected from the auth
# map and keyed by marketplace_code. These are the four cross-border markets of epic IA-5085.

MARKETPLACES = {
    "amazon_sp_fr": {"marketplace_id": "A13V1IB3VIYZZH", "name": "Amazon France"},
    "amazon_sp_de": {"marketplace_id": "A1PA6795UKMFR9", "name": "Amazon Germany"},
    "amazon_sp_jp": {"marketplace_id": "A1VC38T7YXB528", "name": "Amazon Japan"},
    "amazon_sp_us": {"marketplace_id": "ATVPDKIKX0DER", "name": "Amazon United States"},
}

# ===================================================================== Carrier enumeration (MAP 5)

OTHER = "Other"
SELF_DELIVERY = "Self Delivery"

# A **subset** of Amazon's closed 594-member CarrierCode enumeration, carrying only the members these
# suites resolve against. The enumeration's single source of truth is `amzn-base.xsd` release 4.1,
# transcribed in full into JPluger's `AmazonCarrierCode`; this file is deliberately not its second
# home, because two transcriptions drift and the shorter one silently wins.
ENUMERATION_SUBSET = [
    "17FEIA", "Amazon Shipping", "Aramex", "Australia Post", "Blue Package", "Canada Post",
    "Chronopost", "Colissimo", "DHL", "DHL eCommerce", "DHL Express", "DPD", "Delhivery",
    "Deutsche Post", "Evri", "FedEx", "GLS", "Hermes", "InPost", "Japan Post", "La Poste",
    "Ninjavan", "OnTrac", OTHER, "Royal Mail", SELF_DELIVERY, "Startrack", "UPS", "USPS",
    "Yodel", "YAMATO",
]

_ENUMERATION_BY_LOWER_CASE = {}
for _member in ENUMERATION_SUBSET:
    _ENUMERATION_BY_LOWER_CASE.setdefault(_member.lower(), _member)


def resolve_carrier_code(*carrier_identities):
    """Resolves the first carrier identity naming an enumeration member, else `Other`.

    Mirrors `AmazonCarrierCode.resolveOrOther`: identities are tried in preference order, blanks are
    skipped, and matching is case-insensitive with the earliest member in schema order winning a key.
    A carrier with no member goes as `Other` with its name in `CarrierName` (MAP 5), which keeps the
    confirmation valid and loses Amazon-side tracking (L-61).
    """
    for carrier_identity in carrier_identities:
        if not carrier_identity or not str(carrier_identity).strip():
            continue
        member = _ENUMERATION_BY_LOWER_CASE.get(str(carrier_identity).strip().lower())
        if member:
            return member
    return OTHER


def carrier_name_of(shipment):
    """Names the carrier the way the feed builder does, before the code is resolved.

    `Self Delivery` short-circuits and drops any logistic partner name beside it -- that precedence
    is on the tree and pinned by no mapping row, which is note `N-14`. Otherwise the logistic partner
    name is preferred and `shipping_provider` is the fallback (MAP 4.1, L-30).
    """
    if shipment.shipping_provider == SELF_DELIVERY:
        return SELF_DELIVERY
    if shipment.logistic_partner_name:
        return shipment.logistic_partner_name
    return shipment.shipping_provider


# ===================================================================== The shipment (MAP 4.1)


class LineItem:
    """One `line_items[*]` entry of the OMS `CREATE_ORDER_SHIPMENT` payload.

    `quanity` is the wire key and its misspelling is the contract, not a typo to tidy (L-45).
    """

    def __init__(self, line_id, mp_item_codes=None, quantity=1):
        self.id = line_id
        self.mp_item_codes = list(mp_item_codes) if mp_item_codes else []
        self.quantity = quantity

    @property
    def amazon_order_item_code(self):
        """The first code OMS sent, or None when it sent none -- never a substituted one (C-2)."""
        for code in self.mp_item_codes:
            if code and str(code).strip():
                return str(code).strip()
        return None


class Shipment:
    """One OMS shipment notification, at the grain `RTSDataDTO` carries (MAP 4.1)."""

    def __init__(self, order_number, tracking_number=None, shipment_number=None,
                 shipping_provider=None, logistic_partner_name=None, shipping_type=None,
                 line_items=None, order_date=None):
        self.order_number = order_number
        self.tracking_number = tracking_number
        self.shipment_number = shipment_number
        self.shipping_provider = shipping_provider
        self.logistic_partner_name = logistic_partner_name
        self.shipping_type = shipping_type
        self.line_items = list(line_items) if line_items else []
        # The buyer's purchase instant. Read here only so a case can prove it is NOT what reaches
        # Amazon as the fulfilment date (C-13, L-28).
        self.order_date = order_date

    @property
    def has_tracking_number(self):
        return bool(self.tracking_number and str(self.tracking_number).strip())


def with_tracking_number(shipments):
    """Selects the shipments Amazon may be told about (C-1).

    A shipment with no tracking number is refused before the first Amazon call and never confirmed
    under a substituted identifier: Amazon requires the tracking number on a seller-fulfilled
    confirmation and offers no fabricated-value case, and a package confirmed under the order number
    corrupts the tracking the buyer is shown (L-26, L-33, L-83).
    """
    return [shipment for shipment in shipments if shipment.has_tracking_number]


# ===================================================================== Derived feed values


def merchant_fulfilment_id(shipment):
    """Derives the stable positive identifier a package is confirmed under (C-5).

    Mirrors `AmazonMPUtility.merchantFulfillmentId`: SHA-256 over order number, shipment number and
    tracking number; the first eight bytes read unsigned; the top bit dropped and zero stepped over,
    because Amazon types the element as a positive integer (L-56). Derived, never stored -- a rebuild
    of the same shipment carries the value its first submission carried (L-181).
    """
    identity = "%s|%s|%s" % (shipment.order_number,
                             shipment.shipment_number if shipment.shipment_number is not None else None,
                             shipment.tracking_number)
    digest = hashlib.sha256(identity.encode("utf-8")).digest()[:MERCHANT_FULFILMENT_ID_BYTES]
    return (int.from_bytes(digest, "big") >> 1) + 1


def receipt_instant(now=None):
    """This codebase's own receipt instant, ISO 8601 in UTC with the offset spelled out.

    `D9`'s clearly labelled interim proxy, sent as the fulfilment date until `CR-3` lands: not the
    buyer's purchase instant, not silence. Amazon rates late shipment on this field, and the
    notification carries no fulfilment instant at all (L-100, L-125, L-126).
    """
    moment = now or datetime.datetime.now(datetime.timezone.utc)
    return moment.strftime(FULFILMENT_DATE_FORMAT) + "+00:00"


# ===================================================================== The feed document (MAP 4.2)


def build_order_fulfilment_feed(shipments, selling_partner_id, now=None):
    """Builds the `OrderFulfillment` envelope uploaded as the feed document.

    Every caller must have removed the shipments carrying no tracking number first: this list is also
    the list the poll correlates results against by `MessageID` position, so nothing may be dropped
    from it here (L-34, L-63).

    Omissions are deliberate and each is a mapping row:
      - `CarrierName` is emitted only where the code is `Other` (MAP 5).
      - `Quantity` is omitted when non-positive -- the element is optional and Amazon types it as a
        positive integer, so a zero fails the schema (L-45, L-55).
      - a line with no `mp_item_codes` value is left out rather than given a substituted code. Which
        is correct -- skip the line or refuse the confirmation -- is open question `N-13`.
    """
    envelope = ET.Element("AmazonEnvelope")
    header = ET.SubElement(envelope, "Header")
    ET.SubElement(header, "DocumentVersion").text = DOCUMENT_VERSION
    ET.SubElement(header, "MerchantIdentifier").text = selling_partner_id
    ET.SubElement(envelope, "MessageType").text = MESSAGE_TYPE

    for position, shipment in enumerate(shipments, start=1):
        message = ET.SubElement(envelope, "Message")
        ET.SubElement(message, "MessageID").text = str(position)
        ET.SubElement(message, "OperationType").text = OPERATION_TYPE

        fulfilment = ET.SubElement(message, "OrderFulfillment")
        ET.SubElement(fulfilment, "AmazonOrderID").text = shipment.order_number
        ET.SubElement(fulfilment, "MerchantFulfillmentID").text = str(merchant_fulfilment_id(shipment))
        ET.SubElement(fulfilment, "FulfillmentDate").text = receipt_instant(now)

        carrier_name = carrier_name_of(shipment)
        carrier_code = resolve_carrier_code(carrier_name, shipment.shipping_provider)

        data = ET.SubElement(fulfilment, "FulfillmentData")
        ET.SubElement(data, "CarrierCode").text = carrier_code
        if carrier_code == OTHER:
            ET.SubElement(data, "CarrierName").text = carrier_name
        ET.SubElement(data, "ShippingMethod").text = shipment.shipping_type or shipment.shipping_provider
        # Never the order number: with_tracking_number has already turned away every shipment
        # carrying none, so the value on the wire is the carrier's own (C-1, L-26).
        ET.SubElement(data, "ShipperTrackingNumber").text = shipment.tracking_number

        for line_item in shipment.line_items:
            code = line_item.amazon_order_item_code
            if code is None:
                continue
            item = ET.SubElement(fulfilment, "Item")
            ET.SubElement(item, "AmazonOrderItemCode").text = code
            if line_item.quantity and int(line_item.quantity) > 0:
                ET.SubElement(item, "Quantity").text = str(int(line_item.quantity))

    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(envelope, encoding="unicode")


def feed_messages(feed_xml):
    """Reads an uploaded feed document back as one dict per `Message`, keyed by wire element name.

    The observable the suites assert on: what the mock recorded, parsed, never the builder's own
    intermediate values.
    """
    root = ET.fromstring(feed_xml)
    messages = []
    for message in root.findall("Message"):
        fulfilment = message.find("OrderFulfillment")
        data = fulfilment.find("FulfillmentData") if fulfilment is not None else None
        items = []
        if fulfilment is not None:
            for item in fulfilment.findall("Item"):
                items.append({
                    "AmazonOrderItemCode": _text(item, "AmazonOrderItemCode"),
                    "Quantity": _text(item, "Quantity"),
                })
        messages.append({
            "MessageID": _text(message, "MessageID"),
            "OperationType": _text(message, "OperationType"),
            "AmazonOrderID": _text(fulfilment, "AmazonOrderID"),
            "MerchantFulfillmentID": _text(fulfilment, "MerchantFulfillmentID"),
            "FulfillmentDate": _text(fulfilment, "FulfillmentDate"),
            "CarrierCode": _text(data, "CarrierCode"),
            "CarrierName": _text(data, "CarrierName"),
            "ShippingMethod": _text(data, "ShippingMethod"),
            "ShipperTrackingNumber": _text(data, "ShipperTrackingNumber"),
            "Item": items,
        })
    return messages


def feed_header(feed_xml):
    root = ET.fromstring(feed_xml)
    header = root.find("Header")
    return {
        "DocumentVersion": _text(header, "DocumentVersion"),
        "MerchantIdentifier": _text(header, "MerchantIdentifier"),
        "MessageType": _text(root, "MessageType"),
    }


def _text(parent, tag):
    if parent is None:
        return None
    found = parent.find(tag)
    return found.text if found is not None else None


# ===================================================================== The processing report

RESULT_CODE_ERROR = "Error"


def parse_processing_report(report_xml):
    """Reads Amazon's processing report into its summary and its rejections (HMAP 4.4).

    Element shape is the one the application's JAXB models unmarshal into: `AmazonEnvelope` >
    `Message` > `ProcessingReport` > `StatusCode`, `ProcessingSummary`, `Result*`.
    """
    root = ET.fromstring(report_xml)
    reports = []
    for message in root.findall("Message"):
        report = message.find("ProcessingReport")
        if report is None:
            continue
        summary = report.find("ProcessingSummary")
        results = []
        for result in report.findall("Result"):
            results.append({
                "MessageID": _text(result, "MessageID"),
                "ResultCode": _text(result, "ResultCode"),
                "ResultMessageCode": _text(result, "ResultMessageCode"),
                "ResultDescription": _text(result, "ResultDescription"),
            })
        reports.append({
            "StatusCode": _text(report, "StatusCode"),
            "MessagesProcessed": _text(summary, "MessagesProcessed"),
            "MessagesSuccessful": _text(summary, "MessagesSuccessful"),
            "MessagesWithError": _text(summary, "MessagesWithError"),
            "MessagesWithWarning": _text(summary, "MessagesWithWarning"),
            "Result": results,
        })
    return reports


# ===================================================================== Outcomes (SPEC D-20a)
#
# The contract's own three-outcome vocabulary. **Acceptance is not among them:** a feed reaching DONE
# is completion and not acceptance (L-76), and a report with no errors and no warnings names no order
# (L-138). Whether Amazon accepted is read back under P-6, which is not built.

SUBMITTED_NOT_REJECTED = "submitted-and-not-rejected"
REJECTED = "rejected"
UNKNOWN = "unknown"

# The two terminal statuses that carry no processing report. Both are recorded as unknown and
# reconciled rather than resubmitted: the feed may already have applied the message, so a second
# submission risks a second confirmation at Amazon (C-7, FR-33). What CANCELLED means for a
# submission Amazon may already hold is covered by no claim -- note `N-16` -- and unknown never
# misreports, so the treatment is safe on no evidence.
TERMINAL_WITHOUT_REPORT = ("FATAL", "CANCELLED")


def reports_messages_with_error(report):
    """Answers whether a report counts a rejection, unreadably-absent counting as one (C-6)."""
    raw = report.get("MessagesWithError")
    if raw is None:
        return True
    try:
        return int(str(raw).strip()) > 0
    except ValueError:
        return True


def submitted_index(message_id):
    """Turns Amazon's 1-based MessageID into a 0-based position in the submitted list, else -1."""
    if message_id is None:
        return -1
    try:
        return int(str(message_id).strip()) - 1
    except ValueError:
        return -1


def collect_rejections(report, submitted_message_count):
    """Collects the rejections a report attributes to submitted messages.

    Keys are canonical 1-based ids rather than Amazon's own spelling, so a padded or spaced id
    cannot publish one shipment as rejected and as not-rejected at once.

    @return `(rejections, attributable)` -- attributable is False when the report rejects a message
            no submitted message answers to, in which case no shipment in the feed can be told from
            another and none may be published as not-rejected (C-12).
    """
    rejections = {}
    attributable = True
    for result in report.get("Result") or []:
        if str(result.get("ResultCode") or "").lower() != RESULT_CODE_ERROR.lower():
            continue
        index = submitted_index(result.get("MessageID"))
        if index < 0 or index >= submitted_message_count:
            attributable = False
            continue
        rejections.setdefault(str(index + 1), result.get("ResultDescription"))
    return rejections, attributable


def outcomes_from_report(report_xml, submitted_message_count):
    """Names the outcome of every submitted message from the processing report alone (C-6, D-20b).

    @return a list of `(outcome, reason)` in submitted order, or None when the report states no
            outcome for the submitted messages -- which is itself an unknown outcome, not a success.
    """
    reports = parse_processing_report(report_xml)
    if not reports or submitted_message_count <= 0:
        return None

    rejections = {}
    error_reported = False
    attributable = True
    for report in reports:
        error_reported = error_reported or reports_messages_with_error(report)
        report_rejections, report_attributable = collect_rejections(report, submitted_message_count)
        rejections.update(report_rejections)
        attributable = attributable and report_attributable

    # A report counting an error it attributes to nothing leaves every message indistinguishable.
    if not attributable or (error_reported and not rejections):
        return None

    outcomes = []
    for position in range(1, submitted_message_count + 1):
        key = str(position)
        if key in rejections:
            outcomes.append((REJECTED, rejections[key]))
        else:
            outcomes.append((SUBMITTED_NOT_REJECTED, None))
    return outcomes


# ===================================================================== Write-back (MAP 4.4)

WRITEBACK_SUCCESS = "success"
WRITEBACK_FAILURE = "failure"
WRITEBACK_UNKNOWN = "unknown"

WRITEBACK_STATUS_OF = {
    SUBMITTED_NOT_REJECTED: WRITEBACK_SUCCESS,
    REJECTED: WRITEBACK_FAILURE,
    UNKNOWN: WRITEBACK_UNKNOWN,
}


def build_writeback(shipment, outcome, reason=None, oms_order_id=None):
    """Builds one shipment's `CREATE_ORDER_SHIPMENT` write-back to Anchanto OMS (MAP 4.4).

    Carries the tracking number OMS sent, or none at all -- never the order number standing in for a
    missing one. OMS shows this field to the seller as the buyer's tracking, so a substituted value
    is a fabricated tracking number rather than an absent one (C-11, L-42).

    `unknown` is the third status `CR-5` asks OMS to accept. It is not a failure: telling OMS the
    confirmation did not happen sends the seller to re-confirm a package Amazon may already hold
    (C-12, L-77). Whether OMS reads a populated `failure_reason` as evidence of failure regardless of
    the status is note `N-15`, and OMS must answer it.
    """
    details = {
        "tracking_number": shipment.tracking_number,
        "status": WRITEBACK_STATUS_OF[outcome],
        "order_items": [
            {"id": str(line_item.id), "itemQuantity": line_item.quantity}
            for line_item in shipment.line_items
        ],
    }
    if oms_order_id is not None:
        details["id"] = oms_order_id
    if reason is not None:
        details["failure_reason"] = reason
    return {"shipping_details": details}


# ===================================================================== HTTP


def http_json(method, url, body=None, token=None, timeout=10):
    """Sends a JSON request and returns `(status, parsed body)`; status 0 means it never landed."""
    headers = {"Accept": "application/json"}
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = "Bearer " + token
        headers["x-amz-access-token"] = token
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
            return response.status, (json.loads(raw.decode("utf-8")) if raw.strip() else {})
    except urllib.error.HTTPError as error:
        raw = error.read()
        try:
            return error.code, (json.loads(raw.decode("utf-8")) if raw.strip() else {})
        except ValueError:
            return error.code, {"raw": raw.decode("utf-8", errors="replace")}
    except Exception as error:  # noqa: BLE001 -- a suite reports the failure, it never raises
        return 0, {"error": str(error)}


def http_text(method, url, body=None, content_type="text/xml", token=None, timeout=10):
    """Sends or fetches a non-JSON body and returns `(status, text)`.

    The feed document upload and the processing-report download are both XML over the mock's `/s3/`
    stand-ins, so neither can go through `http_json`.
    """
    headers = {}
    data = None
    if body is not None:
        data = body.encode("utf-8")
        headers["Content-Type"] = content_type
    if token:
        headers["Authorization"] = "Bearer " + token
        headers["x-amz-access-token"] = token
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode("utf-8", errors="replace")
    except Exception as error:  # noqa: BLE001
        return 0, str(error)
