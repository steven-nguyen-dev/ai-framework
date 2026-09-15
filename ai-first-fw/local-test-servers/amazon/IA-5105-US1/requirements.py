#!/usr/bin/env python3
"""IA-5105-US1 expectations, pinned to the IA-5105 deliverables.

Ticket: IA-5105 - Samsung CR | Amazon | User Story 1: Synchronize Amazon Marketplace Taxonomy and
Dynamic Product Schemas.

Every expected value below carries the document and the section it came from. The authority order is
the one stated in wiki `plan/amazon-test-suites#00-authority`, highest first:

  D-MATRIX  jira-workspace/amazon-cross-border/IA-5105/deliverables/IA-5105-e2e-coverage-matrix.md
            the 47 target rows (A1-A7, B1-B19, C1-C9, D1-D12), plus section 2 "What must NOT be
            asserted" (N1-N17), section 3 "Genuinely untestable here" (U1-U11) and section 4
            "Fixture requirements a suite must satisfy"
  D-GAP     .../IA-5105-gap-report.md               the contract and decisions 1-14
  D-WIRE    .../IA-5105-oms-api-changes-v2.md       the field-level wire spec, sections 1.1-1.5
  D-RECON   .../oms-reconciliation.md               OMS's own answers, sections 1-6
  D-PLAN    .../IA-5105-implementation-plan.md      phases 0-6 and section 7, as implemented
  D-US2     .../us2-handover.md                     what US1 leaves behind
  D-OUT     .../out-of-scope.md                     what is not this ticket's work
  JIRA      IA-5105 itself: FR-1..FR-20, AC-1..AC-20, section 12 error matrix
  C-AMZ     amazon/IA-5105-US1/schemas/product-types/*.json  Amazon's own captured schemas
  MOCK      amazon/README.md and amazon.mock.json   what this harness serves

**The deliverables override the Jira ticket wherever they differ**, and where a deliverable and a
producer disagree, the deliverable is right and the producer is wrong: the constant states the
deliverable and the case fails red.

Constants whose only statement is in the branch's own source (a retry budget, a cap) are marked
`CODE:` with the file and member, because no requirement document states a number for them. They are
weaker than a document-pinned value, and a case reading one says so.

Read by suite-taxonomy.py, suite-connect-us.py, and suite-connect-non-us.py.
"""

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
# Amazon's captured schemas are under IA-5105-US1/schemas/product-types/.
SCHEMA_DIR = os.path.join(HERE, "schemas", "product-types")


# ===================================================================== marketplaces and identity
#
# D-GAP decision 11: "Marketplaces: France, Germany, Japan, United States. The live ticket names no
# others." ES, AU and GB appear only as fixtures: D-PLAN phase 2 uses the AU and ES captures for the
# width cap because they are the only captures that breach it, and D-MATRIX B19 asserts the cap is
# invisible on FR, DE and US.

MARKETPLACE_IDS = {
    "amazon_sp_us": "ATVPDKIKX0DER",      # D-MATRIX B14; MOCK README "Product type definitions"
    "amazon_sp_fr": "A13V1IB3VIYZZH",     # D-MATRIX A1
    "amazon_sp_de": "A1PA6795UKMFR9",     # D-MATRIX A1
    "amazon_sp_jp": "A1VC38T7YXB528",     # D-GAP decision 11; MOCK README
    "amazon_sp_es": "A1RKKUPIHCS9HS",     # fixture only - D-PLAN phase 2 width-cap capture
    "amazon_sp_au": "A39IBJ37TRP1C6",     # fixture only - D-PLAN phase 2 width-cap capture
    "amazon_sp_uk": "A1F83G8C2ARO7P",     # fixture only - no deliverable names GB
}

# D-MATRIX B14: the US marketplace is the one that emits item_type_keyword instead of
# recommended_browse_nodes.
US_MARKETPLACE_ID = MARKETPLACE_IDS["amazon_sp_us"]

# D-MATRIX B2, quoting `AMAZON_DEFINITIONS_LOCALE_MAP`: "amazon_sp_fr -> fr_FR, amazon_sp_us ->
# en_US, amazon_sp_de -> de_DE". The remaining entries are CODE: AmazonConstant:432-452, which is the
# only statement of them.
DEFINITIONS_LOCALE_MAP = {
    "amazon_sp_us": "en_US",
    "amazon_sp_fr": "fr_FR",
    "amazon_sp_de": "de_DE",
    "amazon_sp_jp": "ja_JP",
    "amazon_sp_es": "es_ES",
    "amazon_sp_au": "en_AU",
    "amazon_sp_uk": "en_GB",
}

# D-MATRIX B2: "Each definition request carries ... requirements=LISTING_PRODUCT_ONLY,
# requirementsEnforced=ENFORCED, ... productTypeVersion unset (LATEST), parentageLevel=NONE, and
# sellerId null."
DEFINITION_REQUEST_PARAMS = {
    "requirements": "LISTING_PRODUCT_ONLY",
    "requirementsEnforced": "ENFORCED",
    "parentageLevel": "NONE",
}

# D-MATRIX B2, recorded as "a deliberate current-state assertion, flagged against open question O1".
DEFINITION_REQUEST_ABSENT_PARAMS = ["sellerId", "productTypeVersion"]

# D-MATRIX B3: "The single search call carries marketplaceIds = exactly one id ... and keywords
# absent/null." D-MATRIX N15 closes pagination: `ProductTypeList` v2020-09-01 carries no page token.
SEARCH_REQUEST_ABSENT_PARAMS = ["keywords", "pageToken", "nextToken"]


# ===================================================================== the wire contract, D-WIRE
#
# D-WIRE header table: the endpoint is `POST /rest/v1/bulk_categories_attributes`, one call per
# product type, existing endpoint with a richer payload (D-GAP section 1.2 "No new endpoints").

BULK_CATEGORIES_PATH = "/rest/v1/bulk_categories"
BULK_ATTRIBUTES_PATH = "/rest/v1/bulk_categories_attributes"

# D-WIRE section 1.1, the six request-level additions.
ENVELOPE_ADDED = [
    "definition_version", "latest_version", "schema_checksum",
    "raw_schema_json", "definition_status", "definition_status_reason",
]

# D-GAP section 1.3 request-level table: what identifies the posting.
ENVELOPE_IDENTITY = ["store_code", "marketplace_code", "category_code"]

# D-GAP decision 8 and D-WIRE section 1.1: six values, FETCH_FAILED distinct from UNAVAILABLE.
# D-MATRIX B5: "Assert six exactly - a seventh value is a contract breach, not a feature."
DEFINITION_STATUSES = [
    "AVAILABLE", "UNAVAILABLE", "PARSE_FAILED",
    "SCHEMA_OMITTED", "VALUES_OMITTED", "FETCH_FAILED",
]

# D-MATRIX B5, the driver for each: what the mock must do for that status to arise.
DEFINITION_STATUS_DRIVER = {
    "AVAILABLE": "clean schema",
    "UNAVAILABLE": "404 on getDefinitionsProductType",
    "PARSE_FAILED": "a schema the flattener cannot express (depth > 9, unresolvable $ref)",
    "SCHEMA_OMITTED": "serialized message over 900 KB",
    "VALUES_OMITTED": "still over 900 KB after raw_schema_json was dropped",
    "FETCH_FAILED": "retries exhausted on a transient error, or a checksum mismatch",
}

# The exact reason strings the deliverables state. D-MATRIX A5, A6, C1, C7 and C8 quote each one, and
# `AmazonDefinitionsUtility.fetchDefinition:218-264` emits them verbatim.
STATUS_REASONS = {
    "checksum_mismatch": "downloaded schema does not match Amazon's checksum",   # D-MATRIX A5
    "not_latest": "Amazon returned a definition it does not mark latest",        # D-MATRIX A6
    "schema_download_failed": "schema download failed",                          # D-MATRIX C7
    "no_schema_link": "definition carries no schema link",                       # D-MATRIX C8
    "unavailable_prefix": "Amazon defines no schema for ",                       # D-MATRIX C1/B6
}

# D-WIRE section 1.2 "Nesting limits" / D-GAP decision 4: the one AVAILABLE definition that still
# carries a reason. The width note is composed as "<node> states <n> children; 4 published", several
# joined by "; " (D-PLAN phase 2, and `AmazonDefinitionsUtilityTest:709-712` states the four AU
# breaches in exactly this form).
WIDTH_REASON_TEMPLATE = "%s states %d children; %d published"
STATUS_REASON_JOIN = "; "

# D-MATRIX B6: "absent when AVAILABLE ... Gson drops nulls; no key is sent on the wire." D-WIRE
# amendment of 2026-09-13: an empty attribute set is an ABSENT KEY, not [], for UNAVAILABLE,
# PARSE_FAILED and FETCH_FAILED.
STATUSES_WITHOUT_ATTRIBUTES = ["UNAVAILABLE", "PARSE_FAILED", "FETCH_FAILED"]
STATUSES_WITHOUT_RAW_SCHEMA = ["UNAVAILABLE", "FETCH_FAILED", "SCHEMA_OMITTED", "VALUES_OMITTED"]

# D-GAP section 1.4 attribute-row table; D-WIRE section 1.5 worked example.
ATTRIBUTE_ROW_KEYS = [
    "field_code", "field_parent_code", "field_criteria", "field_name", "description",
    "data_type", "mandatory", "free_text", "option_type", "smp_field",
    "validation", "default", "field_values", "marketplace_code",
]

# D-WIRE section 1.3 / D-GAP section 1.4.
FIELD_CRITERIA = ["independent", "is_parent", "is_child"]

# D-WIRE section 1.4: the five additions on top of what OMS supported. D-RECON section 1 records
# OMS's answer - "data_type is a free VARCHAR; unknown values are stored".
DATA_TYPES_ADDED = ["number", "integer", "boolean", "object", "array"]
DATA_TYPES_SUPPORTED_BEFORE = [
    "string", "textField", "richText", "date", "datefield",
    "singleSelect", "multiSelect", "COMBO_BOX", "img", "treeSelect",
]
DATA_TYPES_ALLOWED = DATA_TYPES_SUPPORTED_BEFORE + DATA_TYPES_ADDED

# D-MATRIX B10: `format` maps onto OMS data types.
FORMAT_TO_DATA_TYPE = {
    "date": "date",
    "date-time": "datefield",
    "uri": "string",          # D-MATRIX B10: "uri and an unknown format -> string"
}

# D-WIRE section 1.2 and D-GAP section 1.4: the ten keys the code emits, and only these.
# "Only keys Amazon actually states; absent key = no constraint, not zero" (D-MATRIX B7).
# `multipleOf` is NOT one of them - it appeared in the superseded mapping spec and is listed here so
# a suite can assert its absence rather than silently accept it.
VALIDATION_KEYS = [
    "minLength", "maxLength", "maxUtf8ByteLength", "pattern", "minimum", "maximum",
    "minItems", "maxItems", "minUniqueItems", "maxUniqueItems",
]
VALIDATION_KEYS_WITHDRAWN = ["multipleOf", "item_maxLength", "item_required"]

# D-WIRE section 1.5, verbatim from the worked example: the array parent carries occurrence bounds
# and no maxLength; the child carries the item's own maxLength and no bounds (D-MATRIX B8).
ARRAY_PARENT_ONLY_KEYS = ["minItems", "maxItems", "minUniqueItems", "maxUniqueItems"]
ARRAY_CHILD_ONLY_KEYS = ["maxLength", "minLength", "maxUtf8ByteLength", "pattern"]


# ===================================================================== classification, D-GAP 1.5
#
# D-GAP section 1.5: both marketplaces produce the same three rows; only the attribute name and the
# meaning of `value` differ. D-WIRE section 1.1 states the codes.
#
# The dotted spelling is decision 2 (D-GAP section 2): "Nested codes carry the path, dot-separated".
# D-PLAN phase 1 D3 records that the branch shipped `recommended_browse_nodes_value` with an
# underscore and that closing it is the phase's own work - so the underscored spelling is the defect,
# not the expectation.

RBN_PARENT_CODE = "recommended_browse_nodes"
RBN_CHILD_CODE = "recommended_browse_nodes.value"
RBN_MARKETPLACE_CHILD_CODE = "recommended_browse_nodes.marketplace_id"

ITK_PARENT_CODE = "item_type_keyword"
ITK_CHILD_CODE = "item_type_keyword.value"
ITK_MARKETPLACE_CHILD_CODE = "item_type_keyword.marketplace_id"

# CODE: AmazonConstant.VALUE_CHILD_SUFFIX (`DOT + "value"`), the suffix that produces both picker
# codes. D-PLAN phase 4b states the coupling: the flattener's suffix is what produces the code the
# picker constants must match, so a drift publishes under one code and reads the answer back under
# another.
VALUE_CHILD_SUFFIX = ".value"

# The underscored spellings this ticket removes. A suite asserts these are ABSENT.
WITHDRAWN_PICKER_CODES = ["recommended_browse_nodes_value", "item_type_keyword_value"]

# D-MATRIX B13: "the path joined by ' > ' (AmazonConstant.BROWSE_PATH_SEPARATOR). Assert the
# separator exactly - a comma-joined or leaf-only name breaks seller disambiguation between two
# nodes both named Comics."
BROWSE_PATH_SEPARATOR = " > "

# D-GAP section 1.5 bounds table.
RBN_PARENT_VALIDATION = {"minItems": 1, "minUniqueItems": 1, "maxUniqueItems": 1000}
ITK_PARENT_VALIDATION = {"minItems": 1, "maxItems": 1}

# D-WIRE section 1.1: "Where no browse node or keyword applies ... the attribute row is emitted with
# an empty field_values: [] list and free_text: true." D-PLAN phase 3 is the phase that makes it so.
EMPTY_PICKER_FIELD_VALUES = []
EMPTY_PICKER_FREE_TEXT = True

# The browse-node attribute a node may state for itself, and the US keyword attribute.
# MOCK README "Browse tree reports": "One DE leaf states browseNodeAttributes/recommended_browse_nodes
# with a value that differs from its browseNodeId, so the value precedence ... is observable."
BROWSE_NODE_VALUE_ATTRIBUTE = "recommended_browse_nodes"
ITEM_TYPE_KEYWORD_ATTRIBUTE = "item_type_keyword"


# ===================================================================== limits, D-GAP decisions 3-5

# D-GAP decision 3 / D-WIRE section 1.2. CODE: AmazonConstant:589.
DEFINITIONS_MAX_NESTING_DEPTH = 9

# D-GAP decision 4 / D-WIRE section 1.2. CODE: AmazonConstant:603.
DEFINITIONS_MAX_CHILDREN_PER_NODE = 4

# D-WIRE section 1.1 SCHEMA_OMITTED and section 2. CODE: AmazonConstant:575 (900 * 1024).
RAW_SCHEMA_MAX_BYTES = 900 * 1024

# D-MATRIX D6 cites the ceiling but states no number. CODE: AmazonConstant:662.
MAX_FIELD_VALUES_PER_ATTRIBUTE = 8000

# D-MATRIX C2/C3: "bounded by DEFINITIONS_MAX_RETRIES = 4", so a run that exhausts them makes
# exactly 5 attempts. CODE: AmazonConstant:470.
DEFINITIONS_MAX_RETRIES = 4
DEFINITIONS_MAX_ATTEMPTS = DEFINITIONS_MAX_RETRIES + 1

# D-MATRIX D11: "DEFINITIONS_REQUESTS_PER_SECOND = 5 per selling partner ... assert as a ceiling,
# never as an exact cadence". CODE: AmazonConstant:467.
DEFINITIONS_REQUESTS_PER_SECOND = 5

# D-MATRIX C9: the hold-off inside which a second refresh must not be re-requested.
# CODE: AmazonConstant:673 (6 h).
BROWSE_NODE_REFRESH_HOLD_OFF_MILLIS = 6 * 60 * 60 * 1000

# D-MATRIX B16 / JIRA FR-3. D-MATRIX N11: GET_FLAT_FILE_BROWSE_TREE_DATA "does not exist in SP-API";
# assert its ABSENCE, never its use.
BROWSE_TREE_REPORT_TYPE = "GET_XML_BROWSE_TREE_DATA"
FORBIDDEN_REPORT_TYPE = "GET_FLAT_FILE_BROWSE_TREE_DATA"


# ===================================================================== what must NOT be asserted
#
# D-MATRIX section 2, N1-N17. A suite asserting any of these "would fail against correct code - or,
# worse, pressure someone into rebuilding what the ticket owner deliberately took out." Held as data
# so a case can name the row it would breach.

MUST_NOT_ASSERT = {
    "N1": "IS_LAST_REQUEST = true on any definition message (reverted; publishes lastRequest=false)",
    "N2": "definition messages routed to ETopic.MP_STORE_CONNECT (they publish to MP_COMMON_MODULE)",
    "N3": "a held-message buffer, a carriesTheChain flag, or a PendingDefinition type (deleted)",
    "N4": "StoreConnectImpl jumping FETCH_CATEGORY_ATTRIBUTES -> FETCH_PRODUCTS, or any amazon_sp "
          "constant in the shared connector (reverted)",
    "N5": "any distributed lock - Redis lock keys, TTLs, owner tokens, setIfAbsent (reverted)",
    "N6": "cross-replica duplicate-run prevention; AC-17 holds within one replica only (row D10)",
    "N7": "item_type_keyword reaching a flat-file listing column (out of scope, section 5.2)",
    "N8": "(withdrawn 2026-09-13 - the row was wrong; variant browse-node inheritance is assertable)",
    "N9": "any stage-progress event, percentage or completion signal delivered to OMS (FR-16 is "
          "OMS-side)",
    "N10": "a request-level browse_node_ids array on bulk_categories_attributes (withdrawn by "
           "D-WIRE section 1.1); classification is picker rows B13/B14",
    "N11": "a request for GET_FLAT_FILE_BROWSE_TREE_DATA - assert its absence (B16)",
    "N12": "discrete browse-node entities pushed to OMS - FR-4's eleven fields, parent ids, "
           "root/leaf indicators, source report id - or FR-5 reconciliation",
    "N13": "if/then/else or schema-root allOf parsed into attribute rows; assert their survival in "
           "raw_schema_json instead (B4)",
    "N14": "dependencies / dependentRequired handling (zero occurrences across every capture)",
    "N15": "product-type pagination - a page token, a second search page (AC-7 closed)",
    "N16": "field_parent_id or id populated on Amazon attribute rows; assert absence (B11)",
    "N17": "FR-13 product-side fields (amazon_primary_browse_node_id/_name/_path, "
           "amazon_marketplace_id) on any payload - deferred to US2",
}

# N10 and N12: the request-level browse-node array is withdrawn, so no browse-node KEY may appear on
# either payload. The string "recommended_browse_nodes" remains a legal field_code VALUE, and a
# numeric node id remains a legal field_values[].value - only keys are forbidden.
BROWSE_NODE_KEY_PATTERN = re.compile(r"browse[-_]?node", re.IGNORECASE)
FORBIDDEN_BROWSE_NODE_KEYS = [
    "browse_node_ids", "browseNodeIds", "browse-node-ids",
    "browse_node_id", "browseNodeId", "browsenodeids", "browse_nodes",
]

# N16: the two row-level keys Amazon rows leave unset. D-WIRE header: "id and field_parent_id stay
# exactly as they are ... Amazon just leaves them unset."
FORBIDDEN_ROW_KEYS = ["id", "field_parent_id"]


# ===================================================================== what cannot be proven here
#
# D-MATRIX section 3, U1-U11, plus the three this harness adds. "A row that cannot be proven should
# be named, not quietly converted into a weaker assertion that looks green."

UNTESTABLE = {
    "U1": "real SP-API behaviour - LWA token exchange, SigV4 signing, real throttle shapes, real "
          "Retry-After values. The mock proves JPluger's side; it cannot prove Amazon honours it.",
    "U2": "OMS storage semantics - idempotent upsert, no-duplicate guarantees, reparse without "
          "deleting product values (FR-19, AC-13), node update on change (AC-5), sync-record "
          "updating (AC-12). The OMS mock records bodies; it does not implement OMS's database. "
          "D-GAP decision 13 assigns all of it to OMS.",
    "U3": "what OMS does with a body once it arrives. What is SENT is settled and assertable: the "
          "category_attributes key is ABSENT for UNAVAILABLE, PARSE_FAILED and FETCH_FAILED.",
    "U4": "FR-16 stage board, AC-16, FR-14 / AC-19 Product Information page - OMS-side, and no wire "
          "message carries it (N9).",
    "U5": "FR-1 / AC-1 / AC-2 automatic versus manual sync - nothing Amazon-specific exists to "
          "assert; the connect-time trigger is platform behaviour in AuthenticationService.",
    "U6": "whether real Amazon returns enum + enumNames for recommended_browse_nodes and "
          "item_type_keyword when sellerId is supplied (O1), and whether recommended_browse_nodes "
          "is genuinely absent across the US catalogue (O2). The only keyword-enum fixture is "
          "hand-authored (us-schema-SYNTHETIC-item-type-keyword.json:4), so B14 proves JPluger's "
          "handling of a SYNTHETIC shape.",
    "U7": "FR-5 reconciliation - not implemented and not stored (N12); nothing to observe.",
    "U8": "a reauthorization signal to OMS on 401/403 (gap G9, knowingly open). C5 asserts the run "
          "stops; it must not assert a signal that is not sent.",
    "U9": "Retry-After in HTTP-date form - deliberately ignored by retryAfterMillis (gap G17).",
    "U10": "wall-clock bounds, 300 MB browse-tree memory behaviour, anything timing-dependent. Keep "
           "D11 a ceiling, and keep the 300 MB generator in a performance run, not in the "
           "correctness suite.",
    "U11": "the SendoUtilityTests timezone failure and any host-clock-dependent assertion.",

    # Added by this harness, not by D-MATRIX. These are why several matrix rows are recorded
    # `blocked` here rather than red.
    "H1": "There is no JPluger under test. amazon/README.md states it: transformer.py is 'a local "
          "stand-in for the JPluger Amazon integration, which this harness cannot start'. Every "
          "[JP]-hop row - call ordering, retry counts, Redis checkpoints, operator traces, rate "
          "pacing, queueing - has no observation point at all, and a suite that issues the Amazon "
          "calls itself and then asserts those calls were made proves only that its input is its "
          "input (wiki plan/amazon-test-suites#01-harness).",
    "H2": "The Amazon mock serves no fixture for a definition marked latest:false, for a checksum "
          "that mismatches the bytes served at the link, for a definition carrying no schema link, "
          "or for a 429/500/403 on the definitions routes - amazon.mock.json declares one rule per "
          "(productType, marketplaceId) plus a NOTFOUND marker, and nothing else. Driving A5, A6, "
          "C2, C3, C5, C7 and C8 needs fixtures this pane must not add: the mock is shared, and the "
          "authority rule forbids editing a mock so that a case can pass.",
    "H3": "The Amazon mock's schema links are absolute and hardcoded to 127.0.0.1:23103 "
          "(amazon.mock.json). A suite running against another port must rewrite the host before "
          "following the link, or it reads another process's mock and reports that process's "
          "fixtures as its own evidence. schema_link_path() does the rewrite and suites assert it.",
}

# Kept under their old names because the sibling suites read them. The question each names is now
# answered by the deliverables rather than open, and the text says which document answered it.
UNSETTLED = {
    "upsert_key": "ANSWERED, and no longer a suite's business. D-GAP decision 13: 'OMS owns upsert "
                  "and de-duplication.' D-MATRIX U2 scopes every such row to sent-payload "
                  "assertions: prove what JPluger sends per run, claim nothing about what OMS does "
                  "with it. The old TAX-CAT-CR1 case is retired on this ground.",
    "data_type_enum": "ANSWERED. D-RECON section 1: 'Are object and array accepted as data_type? "
                      "Yes. data_type is a free VARCHAR; unknown values are stored, not validated "
                      "at DB level.' D-WIRE section 1.4 adds number, integer, boolean, object and "
                      "array. The closed enum on the single-row sibling endpoint does not govern "
                      "the bulk endpoint, so sending an Amazon type verbatim is the contract, not a "
                      "breach.",
    "field_type_on_parent": "ANSWERED. D-WIRE section 1.5 shows field_type 'attributes' (plural) on "
                            "the array parent rows (bullet_point, recommended_browse_nodes) and "
                            "'attribute' (singular) on scalar child rows.",
    "field_values_source": "ANSWERED. D-WIRE section 1.1: classification travels as picker rows and "
                           "the options come from the browse tree; where none applies the row is "
                           "emitted with field_values: [] and free_text: true.",
    "browse_path_by_name_is_unsplittable": "STILL TRUE, and now a fixture property rather than a "
                                           "requirement defect. D-MATRIX B13 demands name = the "
                                           "path joined by ' > '. MOCK README states the trap: "
                                           "category names contain commas, and the naive split's "
                                           "token count often equals the id count, so a length "
                                           "assertion passes on corrupted data. Resolve the id "
                                           "chain through a node map instead.",
    "smp_field_on_a_mandatory_picker": "OPEN, and out of scope for US1. Amazon states "
                                       "editable:false on the picker in all three real captures, so "
                                       "smp_field is true on a row the seller must pick. What OMS "
                                       "then does with it is U3.",
}


# ===================================================================== the browse-tree transform
#
# D-MATRIX B13: the picker option is {name: the full breadcrumb path, value: the numeric node id}.
# D-GAP section 1.5: "value = numeric node id", "name = breadcrumb path, ' > ' joined".
#
# Run as the EXPECTATION, over the report the mock actually served, so a case compares a published
# payload against Amazon's own document rather than against another implementation.


def browse_node_field_values(report_xml, prefer_stated_attribute=True):
    """Returns {productType: [{"name": path, "value": node id}]} for one marketplace's report.

    A node is an option only if it is a leaf (`hasChildren` false) that states at least one
    `productTypeDefinitions` - a node with no product type has no picker to sit in.

    `prefer_stated_attribute` follows MOCK README: a node may state
    `browseNodeAttributes/recommended_browse_nodes` with a value that differs from its
    `browseNodeId`, and the stated attribute wins. No deliverable states this precedence - D-GAP
    section 1.5 says only "the numeric node id" - so a case that turns on it says which source it
    read. Pass False to read `browseNodeId` alone.

    Streams with iterparse: a real browse tree is hundreds of megabytes (MOCK README).
    """
    import io
    out = {}
    source = io.StringIO(report_xml) if isinstance(report_xml, str) else io.BytesIO(report_xml)
    for _event, node in ET.iterparse(source, events=("end",)):
        if node.tag != "Node":
            continue
        if (node.findtext("hasChildren") or "").strip().lower() == "true":
            node.clear()
            continue
        product_types = [t.strip() for t in _product_types(node) if t.strip()]
        if not product_types:
            node.clear()
            continue

        value = _stated_attribute(node, BROWSE_NODE_VALUE_ATTRIBUTE) if prefer_stated_attribute else None
        if not value:
            value = (node.findtext("browseNodeId") or "").strip()

        name = BROWSE_PATH_SEPARATOR.join(
            seg.strip() for seg in (node.findtext("browsePathByName") or "").split(","))

        for product_type in product_types:
            out.setdefault(product_type, []).append({"name": name, "value": value})
        node.clear()
    return out


def item_type_keyword_field_values(report_xml):
    """Returns {productType: [{"name", "value"}]} built from `item_type_keyword` only.

    D-MATRIX B14: for a US store the picker is `item_type_keyword.value`, its value is the
    standardized keyword token, and "a browse-tree node served WITHOUT
    <attribute name='item_type_keyword'> contributes NO option" - so a node stating none is skipped
    outright rather than falling back to its node id.
    """
    import io
    out = {}
    source = io.StringIO(report_xml) if isinstance(report_xml, str) else io.BytesIO(report_xml)
    for _event, node in ET.iterparse(source, events=("end",)):
        if node.tag != "Node":
            continue
        if (node.findtext("hasChildren") or "").strip().lower() == "true":
            node.clear()
            continue
        keyword = _stated_attribute(node, ITEM_TYPE_KEYWORD_ATTRIBUTE)
        product_types = [t.strip() for t in _product_types(node) if t.strip()]
        if not keyword or not product_types:
            node.clear()
            continue
        name = BROWSE_PATH_SEPARATOR.join(
            seg.strip() for seg in (node.findtext("browsePathByName") or "").split(","))
        for product_type in product_types:
            out.setdefault(product_type, []).append({"name": name, "value": keyword})
        node.clear()
    return out


def browse_node_ids(report_xml):
    """Every node's `browseNodeId`, in document order, duplicates included.

    JIRA section 12 states "Duplicate browse node -> upsert existing node", and MOCK README records
    the real collision the DE fixture carries from amzn/selling-partner-api-models issue #4742: id
    13528201031 appears twice, under two names, two parents and two depths. A picker keyed on node
    id alone silently collapses them.
    """
    import io
    ids = []
    source = io.StringIO(report_xml) if isinstance(report_xml, str) else io.BytesIO(report_xml)
    for _event, node in ET.iterparse(source, events=("end",)):
        if node.tag != "Node":
            continue
        node_id = (node.findtext("browseNodeId") or "").strip()
        if node_id:
            ids.append(node_id)
        node.clear()
    return ids


def root_node_ids(report_xml):
    """The tree's root ids, derived the way MOCK README says they must be.

    "Parentage is derived, not given. There is no isRoot and no parentNodeId. browsePathById carries
    an unnamed leading root id, so a top-level node has exactly two entries." The root sets are
    disjoint per marketplace, which is what makes a substituted tree (JIRA FR-20) observable.
    """
    import io
    roots = set()
    source = io.StringIO(report_xml) if isinstance(report_xml, str) else io.BytesIO(report_xml)
    for _event, node in ET.iterparse(source, events=("end",)):
        if node.tag != "Node":
            continue
        path = [p.strip() for p in (node.findtext("browsePathById") or "").split(",") if p.strip()]
        if path:
            roots.add(path[0])
        node.clear()
    return roots


def _stated_attribute(node, name):
    attrs = node.find("browseNodeAttributes")
    if attrs is None:
        return None
    for attr in attrs.findall("attribute"):
        if attr.get("name") == name:
            return (attr.text or "").strip()
    return None


def _product_types(node):
    """`productTypeDefinitions` is one element per definition in Amazon's published example, and the
    fixtures here carry one. Read every occurrence rather than assuming a count."""
    found = [e.text or "" for e in node.findall("productTypeDefinitions")]
    if len(found) == 1 and "," in found[0]:
        return found[0].split(",")
    return found


def unsplittable_path_nodes(report_xml):
    """Leaves whose breadcrumb cannot be rebuilt by splitting `browsePathByName` on commas.

    MOCK README: category names contain commas ('Kuche, Haushalt & Wohnen'), and the naive split's
    token count often EQUALS the id count, so a length assertion passes on corrupted data. Returns
    the affected `browseNodeId`s. See UNSETTLED["browse_path_by_name_is_unsplittable"].
    """
    import io
    bad = []
    source = io.StringIO(report_xml) if isinstance(report_xml, str) else io.BytesIO(report_xml)
    for _event, node in ET.iterparse(source, events=("end",)):
        if node.tag != "Node":
            continue
        if (node.findtext("hasChildren") or "").strip().lower() == "true":
            node.clear()
            continue
        by_name = (node.findtext("browsePathByName") or "")
        by_id = (node.findtext("browsePathById") or "")
        # browsePathById carries an unnamed leading root id, so a correct path has one fewer name.
        if len(by_name.split(",")) != max(len(by_id.split(",")) - 1, 1):
            bad.append((node.findtext("browseNodeId") or "").strip())
        node.clear()
    return bad


# ===================================================================== payload scans
#
# D-MATRIX assertions that are the same walk over any received body, held here so three suites make
# one walk rather than three that drift.


def attribute_rows(body):
    """category_attributes[] of one received body, keyed by field_code."""
    rows = {}
    for row in (body.get("category_attributes") or []):
        if isinstance(row, dict):
            rows[row.get("field_code")] = row
    return rows


def attribute_row_list(body):
    """category_attributes[] in the order it arrived.

    D-MATRIX A7 turns on the ORDER, not on set membership: "an implementation that emits children
    first would pass a naive containment check and break OMS's renderer".
    """
    return [r for r in (body.get("category_attributes") or []) if isinstance(r, dict)]


def parent_first_violations(body):
    """A7: every `field_parent_code` must name a row already seen EARLIER in the same array.

    Returns [(field_code, field_parent_code)] for the rows that break it - a child emitted before its
    parent, or one naming a parent that is not in the array at all.
    """
    seen, bad = set(), []
    for row in attribute_row_list(body):
        parent = row.get("field_parent_code")
        if parent is not None and parent not in seen:
            bad.append((row.get("field_code"), parent))
        seen.add(row.get("field_code"))
    return bad


def duplicate_field_codes(body):
    """D7: every `field_code` in a delivered array is unique.

    Under dotted paths a collision is impossible by construction, "so a failure here means the path
    is being built wrongly, not that de-duplication is missing".
    """
    seen, dupes = set(), []
    for row in attribute_row_list(body):
        code = row.get("field_code")
        if code in seen:
            dupes.append(code)
        seen.add(code)
    return dupes


def undotted_nested_codes(body):
    """Rows that name a parent but do not carry the dotted path.

    D-GAP decision 2: nested codes carry the path, dot-separated. D-PLAN phase 1 D1/D3 record the
    underscored form as the divergence this ticket closes, so an underscore-joined nested code is the
    defect and is reported by name.
    """
    bad = []
    for row in attribute_row_list(body):
        parent, code = row.get("field_parent_code"), str(row.get("field_code") or "")
        if not parent:
            continue
        if not code.startswith(str(parent) + "."):
            bad.append(code)
    return bad


def rows_carrying_forbidden_keys(body):
    """N16: `id` and `field_parent_id` stay unset on every Amazon row."""
    bad = []
    for row in attribute_row_list(body):
        for key in FORBIDDEN_ROW_KEYS:
            if key in row:
                bad.append((row.get("field_code"), key))
    return bad


def validation_keys_outside_contract(body):
    """Keys inside any `validation` object that D-WIRE section 1.2 does not list."""
    out = set()
    for row in attribute_row_list(body):
        for key in (row.get("validation") or {}):
            if key not in VALIDATION_KEYS:
                out.add(key)
    return sorted(out)


def browse_node_keys(payload):
    """Every JSON KEY anywhere in `payload` that names a browse node. Must always be empty.

    Keys only. "recommended_browse_nodes" is a legal `field_code` VALUE and a numeric node id is a
    legal `field_values[].value`; an envelope property or a column called `browse_node_ids` is the
    thing N10 and N12 forbid.
    """
    found = []

    def walk(node, trail):
        if isinstance(node, dict):
            for k, v in node.items():
                here = "%s.%s" % (trail, k) if trail else str(k)
                if BROWSE_NODE_KEY_PATTERN.search(str(k)):
                    found.append(here)
                walk(v, here)
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, "%s[%d]" % (trail, i))

    walk(payload, "")
    return found


def data_types_sent(body):
    """Distinct `data_type` values in one received body, and which fall outside the contract.

    D-WIRE section 1.4 plus D-RECON section 1 settle this: `object` and `array` are accepted and
    `data_type` is a free VARCHAR, so a value outside DATA_TYPES_ALLOWED is a genuine breach now, not
    an open change request.
    """
    sent = sorted({str(r.get("data_type")) for r in attribute_row_list(body)})
    outside = [d for d in sent if d not in DATA_TYPES_ALLOWED]
    return sent, outside


DATE_SHAPED = re.compile(r"^\d{4}-\d{2}-\d{2}|^\d{4}/\d{2}/\d{2}|^\d{8}$")


def looks_like_a_date(token):
    """D-WIRE section 1.1: `definition_version` is "Amazon's version id, opaque, do not parse/order".
    A date-shaped value there means `productTypeVersion` was read as something other than `.version`.
    """
    return bool(DATE_SHAPED.match(str(token or "")))


BROWSE_PATH_SHAPED = re.compile(r"^\d+(_\d+)+$")


def looks_like_a_browse_node(code):
    """D-MATRIX A2: no `code` may match ^[0-9]+$ and none may be a `_`-joined numeric chain - the
    legacy `parentCode_childBrowseNodeId` shape that D-GAP decision 1 abolishes."""
    text = str(code or "")
    return bool(BROWSE_PATH_SHAPED.match(text)) or text.isdigit()


UPPER_SNAKE = re.compile(r"^[A-Z0-9]+(_[A-Z0-9]+)*$")


def is_upper_snake(code):
    """An Amazon product type code, verbatim: `SHOES`, `LUGGAGE`, `NOTEBOOK_COMPUTER` (D-MATRIX A2)."""
    return bool(UPPER_SNAKE.match(str(code or "")))


def load_capture(name):
    with open(os.path.join(SCHEMA_DIR, name), encoding="utf-8") as f:
        return json.load(f)


def schema_link_path(url):
    """The path and query of a schema link, with the mock's hardcoded host dropped.

    UNTESTABLE["H3"]: amazon.mock.json spells `schema.link.resource` as an absolute
    `http://127.0.0.1:23103/...`. A suite on any other port must follow the link by PATH against its
    own base, or it reads a different process's mock.
    """
    parsed = urllib.parse.urlparse(str(url or ""))
    return parsed.path + (("?" + parsed.query) if parsed.query else "")


def schema_link_host(url):
    """The host:port a schema link names, so a case can state the rewrite it had to perform."""
    return urllib.parse.urlparse(str(url or "")).netloc


def wide_nodes(schema, limit=None, include_root=False):
    """Property paths whose node states more children than the cap, and their true child counts.

    D-MATRIX B19 and D-GAP decision 4: a node declaring more than four children publishes its first
    four in Amazon's own property order and names the breach in `definition_status_reason`. The
    return value is what the expected reason string is built from.

    The schema ROOT is excluded by default. D-PLAN phase 2 lists the AU capture's breaches as
    `fulfillment_availability`, `purchasable_offer`, `supplemental_condition_information` and
    `item_display_dimensions` and names no root, so the cap governs an attribute node rather than the
    count of top-level attributes - a root cap would truncate every real definition to four rows.
    """
    cap = DEFINITIONS_MAX_CHILDREN_PER_NODE if limit is None else limit
    found = {}

    def walk(node, path):
        if not isinstance(node, dict):
            return
        props = node.get("properties")
        if isinstance(props, dict):
            if len(props) > cap:
                found[path or "(root)"] = len(props)
            for name, child in props.items():
                walk(child, ("%s.%s" % (path, name)) if path else name)
        items = node.get("items")
        if isinstance(items, dict):
            walk(items, path)

    walk(schema, "")
    if not include_root:
        found.pop("(root)", None)
    return found


def max_nesting_depth(schema):
    """The deepest property nesting in a JSON Schema, counted the way the flattener descends.

    D-GAP decision 3 caps it at 9; D-RECON section 2.2 measures every real capture at 4 or less, so a
    capture reaching 9 here means the fixture changed, not that the cap is wrong.
    """
    def walk(node, depth):
        if not isinstance(node, dict) or depth > 30:
            return depth
        best = depth
        props = node.get("properties")
        if isinstance(props, dict):
            for child in props.values():
                best = max(best, walk(child, depth + 1))
        items = node.get("items")
        if isinstance(items, dict):
            best = max(best, walk(items, depth))
        return best

    return walk(schema, 0)


# ===================================================================== what arrived at the mocks
#
# wiki plan/amazon-test-suites#01-harness: "Payloads are judged on what arrived: clear the OMS mock
# call log in preflight, fire, then read bodies back from /log/data. Asserting on a dict still held
# in memory proves only that its input is its input."


_LOG_CACHE = {}


def oms_clear_log(base_oms, token=None):
    """DELETE /log/data - reset what the run owns, before firing."""
    _LOG_CACHE.pop(base_oms.rstrip("/"), None)
    return _http("DELETE", base_oms.rstrip("/") + "/log/data", token=token)[0]


def oms_high_water(base_oms, token=None):
    """The newest sequence number in a mock's log right now.

    Pass it back as `since` so a case reads only what it fired. A case that reads the whole log sees
    every earlier case's postings too, and "this product type was posted once" then fails on a later
    case having legitimately posted it again.
    """
    status, doc = _http("GET", base_oms.rstrip("/") + "/log/data", token=token)
    if status != 200 or not isinstance(doc, dict):
        return 0
    _LOG_CACHE[base_oms.rstrip("/")] = doc.get("entries") or []
    seqs = [e.get("seq") or e.get("_seq") or 0 for e in _LOG_CACHE[base_oms.rstrip("/")]]
    return max(seqs) if seqs else 0


def oms_received(base_oms, path, token=None, refresh=False, since=None, method="POST"):
    """Every request a mock logged for `path`, in the order it received them.

    Returns [{"seq", "method", "url", "query", "body", "raw", "status"}]. The log carries a verbatim
    `raw_schema_json` per posting - 147 KB for DE, 351 KB for AU - so it is fetched once and cached.
    Pass refresh=True after firing, never before reading. `method=None` reads every verb.
    """
    key = base_oms.rstrip("/")
    if refresh or key not in _LOG_CACHE:
        status, doc = _http("GET", key + "/log/data", token=token)
        _LOG_CACHE[key] = (doc.get("entries") or []) if (status == 200 and isinstance(doc, dict)) else []
    out = []
    for entry in _LOG_CACHE[key]:
        req = entry.get("request") or {}
        url = req.get("url") or ""
        if path not in url:
            continue
        if method and (req.get("method") or "").upper() != method.upper():
            continue
        seq = entry.get("seq") or entry.get("_seq") or 0
        if since is not None and seq <= since:
            continue
        body = _entry_body(req)
        out.append({
            "seq": seq,
            "method": req.get("method"),
            "url": url,
            "query": _query_of(url),
            "body": body if isinstance(body, dict) else {},
            "raw": json.dumps(body, ensure_ascii=False) if body is not None else "",
            "status": (entry.get("response") or {}).get("status"),
        })
    return out


def amazon_received(base_amazon, path, token=None, refresh=True, since=None, method="GET"):
    """The same read against the Amazon mock's own call log.

    Used for call-sequence and call-count rows (D-MATRIX B1, B3, B16). Those rows are about what
    JPluger asked Amazon for, and in this harness the suite is the only client - see
    UNTESTABLE["H1"]. A case reading this states that limitation rather than claiming the row.
    """
    return oms_received(base_amazon, path, token=token, refresh=refresh, since=since, method=method)


def _entry_body(req):
    """mock.read_log flattens the HAR to {body: postData._json, bodyText: postData.text}; a raw HAR
    read from the file keeps postData itself. Both shapes reach here."""
    for candidate in (req.get("body"), (req.get("postData") or {}).get("_json")
                      if isinstance(req.get("postData"), dict) else None):
        if isinstance(candidate, (dict, list)):
            return candidate
    for text in (req.get("bodyText"), req.get("body"),
                 (req.get("postData") or {}).get("text")
                 if isinstance(req.get("postData"), dict) else None):
        if isinstance(text, str) and text.strip():
            try:
                return json.loads(text)
            except Exception:
                continue
    return None


def _query_of(url):
    q = urllib.parse.urlparse(url).query
    return {k: v[0] for k, v in urllib.parse.parse_qs(q).items()}


def _http(method, url, token=None, timeout=60):
    headers = {}
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(url, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            status = r.status
    except urllib.error.HTTPError as e:
        raw, status = e.read(), e.code
    except Exception:
        return 0, {}
    try:
        return status, json.loads(raw.decode("utf-8")) if raw.strip() else {}
    except Exception:
        return status, {}
