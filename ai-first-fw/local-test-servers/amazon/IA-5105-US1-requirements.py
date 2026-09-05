#!/usr/bin/env python3
"""IA-5105-US1 expectations, written from the requirement documents and the two published contracts.

Ticket: IA-5105 - Samsung CR | Amazon | User Story 1: Synchronize Amazon Marketplace Taxonomy and Dynamic Product Schemas

Nothing in this file was derived by reading the JPluger Amazon integration. Every expected value
carries the document and section it comes from, so a failing check can be argued about against the
requirement rather than against the code. The four sources, and nothing else:

  R-PLAN   jira-workspace/amazon-cross-border/IA-5105/IA-5105-browse-node-and-listing-plan.md
           the current amendment -- D-1..D-3, section 4 (browse-node source), section 6 (payloads),
           section 7 (gates). Amends the mapping spec section 1.1 and the summary.
  R-REQ    .../IA-5105-oms-taxonomy-requirements-spec.md            the FRs, the ACs, section 2.1/2.2
  R-MAP    .../IA-5105-product-types-mapping-spec.md                the field mapping, section 4/5/6
  C-OMS    anchanto-oms/anchanto-oms-swagger.json                   what OMS actually declares
  C-AMZ    amazon/schemas/product-types/*.json                      Amazon's own captured schemas
           amazon/amazon-sp-api-swagger.json

Where the requirement is silent, or where two requirement documents disagree, the constant carries
an `UNSETTLED` note and the suite that reads it marks the case `blocked` rather than inventing a
verdict. Those notes are the report, not a TODO.

Read by IA-5105-US1-suite-taxonomy.py, IA-5105-US1-suite-connect-us.py, and IA-5105-US1-suite-connect-non-us.py.
"""

import json
import os
import re
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
SCHEMA_DIR = os.path.join(HERE, "schemas", "product-types")


# ===================================================================== the OMS contract, as declared
#
# C-OMS, POST /rest/v1/category_attributes -- the SINGLE-ROW sibling of the bulk endpoint. Its
# data_type is a closed enum; the bulk endpoint's is a free string with no enum. R-REQ section 1
# item 2 and section 2.2 (`data_type` UPDATE row) raise exactly this as CR-3, still unanswered:
# Amazon's raw JSON-Schema types are what this sync writes verbatim (R-MAP section 4.2, row 7) and
# most of them are not in the enum below.

OMS_SIBLING_DATA_TYPE_ENUM = [
    "string", "textField", "richText", "date", "datefield",
    "singleSelect", "multiSelect", "COMBO_BOX", "img", "treeSelect",
]

# C-OMS, same operation. field_type IS a closed enum on the sibling, and "attributes" (plural) --
# which R-PLAN section 6.1 puts on the recommended_browse_nodes parent row -- is a member of it.
OMS_SIBLING_FIELD_TYPE_ENUM = ["attribute", "option_type", "attributes", "attribute,option_type"]

# C-OMS, POST /rest/v1/bulk_categories -- query parameter, required. store_code is NOT a body
# property on this endpoint's declared schema.
BULK_CATEGORIES_QUERY = ["store_code"]

# C-OMS, POST /rest/v1/bulk_categories_attributes -- both query parameters, both required.
BULK_ATTRIBUTES_QUERY = ["store_code", "marketplace_code"]

# C-OMS, POST /rest/v1/bulk_categories_attributes, category_attributes[] items.required.
BULK_ATTRIBUTE_ROW_REQUIRED = ["field_code", "field_name", "field_type", "data_type"]

# R-REQ section 2.2, the six envelope ADD rows.
ENVELOPE_ADDED = [
    "definition_version", "latest_version", "schema_checksum",
    "raw_schema_json", "definition_status", "definition_status_reason",
]

# R-REQ section 2.2 / R-MAP section 4.2 envelope row 6. Four values, and SCHEMA_OMITTED is never
# bucketed with PARSE_FAILED.
DEFINITION_STATUSES = ["AVAILABLE", "UNAVAILABLE", "PARSE_FAILED", "SCHEMA_OMITTED"]


# ===================================================================== the browse-node prohibition
#
# R-REQ section 2.2, the REMOVE row: the 31-Aug revision asked for an envelope `browse_node_ids`;
# that ask is withdrawn and "This document is the authority; the Jira attachment lags it."
# R-MAP section 1.1 item 2 drops the field. R-PLAN section 4.2 refuses to restore it -- the
# productTypeDefinitions inversion returns "as a picker filter, never as an outbound value and never
# as a wire field". R-PLAN section 6.1: "Nothing goes on bulk_categories."
#
# Corroborated on the connector side, independently of the requirement documents: BulkCategoryDTO in
# connector/marketplace-connector/schema/oms-schema.json (FETCH_CATEGORIES) declares ten properties
# -- key, name, presentation, code, marketplaceCode, active, children, storeCode, position,
# variation -- and no browse-node property of any kind.
#
# Any JSON *key* matching this pattern is forbidden in either payload. Keys only: the string
# "recommended_browse_nodes" is a legal field_code *value* and must not be caught here.

BROWSE_NODE_KEY_PATTERN = re.compile(r"browse[-_]?node", re.IGNORECASE)

# Named for the report, so a failure says which spelling arrived.
FORBIDDEN_BROWSE_NODE_KEYS = [
    "browse_node_ids", "browseNodeIds", "browse-node-ids",
    "browse_node_id", "browseNodeId", "browsenodeids", "browse_nodes",
]


# ===================================================================== recommended_browse_nodes
#
# R-PLAN section 6.1. Two rows come out of flattening one array-of-object property. The field codes
# are fixed by R-MAP section 4.2 row 1 -- "the dotted property path, `.` -> `_`" -- so the child is
# recommended_browse_nodes_value with an underscore, never a dot.

RBN_PARENT_CODE = "recommended_browse_nodes"
RBN_CHILD_CODE = "recommended_browse_nodes_value"

# R-PLAN section 4.3. The value Amazon states per node, and the fallback.
RBN_NODE_ATTRIBUTE = "recommended_browse_nodes"

# R-PLAN section 4.3: "name must be the full path. Leaf names repeat across the tree, and the seller
# has to tell them apart in the picker." browsePathByName joined with " > ".
BROWSE_PATH_SEPARATOR = " > "

# R-MAP section 4.2 warning, last bullet: "us-schema-LUGGAGE.json yields neither a
# recommended_browse_nodes nor a recommended_browse_nodes_value row." R-PLAN section 4.4: US stores
# never trigger the browse-node refresh, because the US definition does not list the property.
# R-PLAN section 7, G-4 records this as unconfirmed against a real US capture.
US_MARKETPLACE_ID = "ATVPDKIKX0DER"

# R-PLAN section 4.1 / the mock's own browse-tree lifecycle: the report type that must never be
# requested for a US store, and must be requested once per marketplace for a non-US one.
BROWSE_TREE_REPORT_TYPE = "GET_XML_BROWSE_TREE_DATA"


UNSETTLED = {
    "field_type_on_parent": (
        "R-PLAN section 6.1 states field_type 'attributes' (plural) on the parent row and cites "
        "fieldType(array, false). R-REQ section 2.2's own payload example states 'attribute' "
        "(singular) for the same attribute. R-MAP section 5 resolves in the plan's favour -- "
        "data_type == 'array' with no enum maps to 'attributes' -- and C-OMS declares both spellings "
        "in the sibling enum, so both are accepted by OMS and only one can be right. The suites "
        "assert the plan, because it is the current amendment and it is the document that annotates "
        "this exact pair of rows."
    ),
    "field_values_source": (
        "R-MAP section 4.2's warning says field_values for this attribute is empty against every "
        "real capture, because Amazon states no enum -- and R-REQ section 2.2 shows the row with no "
        "field_values on purpose. R-PLAN D-1 supersedes both for the *source*: field_values is "
        "filled from GET_XML_BROWSE_TREE_DATA, not from the schema enum. The schema-derived reading "
        "and the browse-tree-derived reading are not in conflict; they are two different producers "
        "of the same array. The suites assert the plan's producer and keep the schema-derived "
        "emptiness as the documented fallback (R-PLAN section 4.4)."
    ),
    "browse_path_by_name_is_unsplittable": (
        "R-PLAN section 4.3 says name = browsePathByName joined with ' > ', and section 4.1 drops "
        "browseNodeName and browsePathById from the parse target. Amazon's document states "
        "browsePathByName as ONE comma-joined string, and category names contain commas "
        "('Kueche, Haushalt & Wohnen'), so the full path cannot be reconstructed from the only two "
        "elements the plan keeps. This is a defect in the requirement, not in any implementation."
    ),
    "smp_field_on_a_mandatory_picker": (
        "R-PLAN section 7, G-3 and CR-6. Amazon states editable:false on "
        "recommended_browse_nodes.value in all three real captures, so smp_field is true on a row "
        "the seller must pick. Whether OMS then hides it is unconfirmed. The suites assert what the "
        "requirement says to send and do not judge what OMS does with it."
    ),
    "data_type_enum": (
        "CR-3, R-REQ section 1 item 2. The bulk endpoint declares data_type as a free string; the "
        "single-row sibling declares a closed enum that excludes array, object, number, boolean and "
        "integer. The sync sends Amazon's raw JSON-Schema types verbatim. Unanswered by OMS."
    ),
    "upsert_key": (
        "CR-1, R-REQ section 1 item 1 and R-MAP section 6. Neither bulk endpoint declares a 2xx "
        "response or an upsert key anywhere in C-OMS. Whether marketplace_code is part of the "
        "uniqueness key is the highest-weight open item on the ticket, and no observation of a mock "
        "can settle it."
    ),
}


# ===================================================================== R-PLAN section 4.3, verbatim
#
#   for each <Node> streamed from the report:
#       skip if hasChildren == true                      only leaves are listable
#       skip if productTypeDefinitions is empty          no picker to place it in
#       value = browseNodeAttributes["recommended_browse_nodes"]  else browseNodeId
#       name  = browsePathByName joined with " > "
#       for each productType in productTypeDefinitions:
#           cache[marketplaceCode][productType] += FieldValueDTO(name, value)


def browse_node_field_values(report_xml):
    """The transform in R-PLAN section 4.3, run as the *expectation*.

    Returns {productType: [{"name": path, "value": id}, ...]} for one marketplace's report.
    Filter, map, bucket -- no recursion, exactly as the plan states it.
    Uses streaming iterparse so huge reports (e.g. 300MB) parse safely without heap exhaustion.
    """
    import io
    out = {}
    source = io.StringIO(report_xml) if isinstance(report_xml, str) else io.BytesIO(report_xml)
    for event, node in ET.iterparse(source, events=("end",)):
        if node.tag != "Node":
            continue
        if (node.findtext("hasChildren") or "").strip().lower() == "true":
            node.clear()
            continue
        product_types = [t.strip() for t in _product_types(node) if t.strip()]
        if not product_types:
            node.clear()
            continue

        value = None
        attrs = node.find("browseNodeAttributes")
        if attrs is not None:
            for attr in attrs.findall("attribute"):
                if attr.get("name") == RBN_NODE_ATTRIBUTE:
                    value = (attr.text or "").strip()
                    break
        if not value:
            value = (node.findtext("browseNodeId") or "").strip()

        name = BROWSE_PATH_SEPARATOR.join(
            seg.strip() for seg in (node.findtext("browsePathByName") or "").split(","))

        for product_type in product_types:
            out.setdefault(product_type, []).append({"name": name, "value": value})
        node.clear()
    return out


def _product_types(node):
    """`<productTypeDefinitions>` is one element per definition in Amazon's published example, and
    the fixtures here carry one. Read every occurrence rather than assuming a count."""
    found = [e.text or "" for e in node.findall("productTypeDefinitions")]
    if len(found) == 1 and "," in found[0]:
        return found[0].split(",")
    return found


def unsplittable_path_nodes(report_xml):
    """Nodes whose full path cannot be rebuilt from what R-PLAN section 4.1 keeps.

    A comma inside a browseNodeName makes browsePathByName unsplittable, and the naive split's token
    count often equals the id count, so a length check passes on corrupted data. Returns the
    browseNodeIds of the affected leaves. See UNSETTLED["browse_path_by_name_is_unsplittable"].
    Uses streaming iterparse for memory safety on huge files.
    """
    import io
    bad = []
    source = io.StringIO(report_xml) if isinstance(report_xml, str) else io.BytesIO(report_xml)
    for event, node in ET.iterparse(source, events=("end",)):
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


# ===================================================================== R-PLAN section 6.1, both rows


def expected_rbn_rows(schema, marketplace_code, field_values):
    """The two rows R-PLAN section 6.1 annotates, computed from Amazon's own schema.

    `schema` is the downloaded JSON Schema document -- C-AMZ, the published contract. `field_values`
    is what browse_node_field_values() produced for this product type; [] when the tree yields
    nothing for it. Returns (parent_row, child_row), or (None, None) when the definition does not
    carry the property at all -- which is the US case (R-MAP section 4.2, last bullet).

    Every value below cites the schema construct it reads, so the expectation is Amazon's statement
    plus the requirement's rule, and never an observation of an implementation.
    """
    parent = (schema.get("properties") or {}).get(RBN_PARENT_CODE)
    if not isinstance(parent, dict):
        return None, None

    items = parent.get("items") or {}
    value_spec = (items.get("properties") or {}).get("value") or {}
    top_required = schema.get("required") or []
    item_required = items.get("required") or []
    picked = list(field_values or [])

    parent_row = {
        "marketplace_code": marketplace_code,
        "field_code": RBN_PARENT_CODE,
        "ss_field_code": RBN_PARENT_CODE,
        "field_parent_code": None,
        # schema .title
        "field_name": parent.get("title"),
        # schema .type -- Amazon's raw JSON-Schema type, verbatim (R-MAP section 4.2, row 7)
        "data_type": parent.get("type"),
        # R-MAP section 5: data_type == "array" and no enum -> "attributes".
        # See UNSETTLED["field_type_on_parent"].
        "field_type": "attributes",
        # R-MAP section 5: has children -> is_parent
        "field_criteria": "is_parent",
        # R-REQ section 2.2: the ENCLOSING object's required[], strict boolean
        "mandatory": RBN_PARENT_CODE in top_required,
        "option_type": False,
        "free_text": False,
        # R-REQ section 2.2: smp_field carries !editable, not a hardcoded false
        "smp_field": parent.get("editable") is False,
        "validation": _validation(parent),
    }

    child_row = {
        "marketplace_code": marketplace_code,
        "field_code": RBN_CHILD_CODE,
        "ss_field_code": RBN_CHILD_CODE,
        "field_parent_code": RBN_PARENT_CODE,
        # schema items.properties.value.title
        "field_name": value_spec.get("title"),
        # schema ...value.type
        "data_type": value_spec.get("type"),
        # R-PLAN section 4.5 item 1: everything downstream keys off hasFieldValues, so field_type,
        # option_type and free_text all flip on their own when the picker is filled.
        "field_type": "option_type" if picked else "attribute",
        "field_criteria": "is_child",
        # R-REQ section 2.2: items.required[] contains "value"
        "mandatory": "value" in item_required,
        "option_type": bool(picked),
        # R-PLAN section 4.4: an empty cache publishes "with an empty field_values and free text"
        "free_text": not picked,
        # ...value.editable == false. R-PLAN section 7, G-3.
        "smp_field": value_spec.get("editable") is False,
        "validation": _validation(value_spec),
        "field_values": picked,
    }
    if value_spec.get("description"):
        child_row["description"] = value_spec["description"]

    return parent_row, child_row


# R-MAP section 4.2, row 9: "minLength, maxLength, pattern, minimum, maximum, minItems, maxItems, ..."
# keys present only when Amazon states them, a free-form map so an unrecognised key is stored rather
# than rejected. R-PLAN section 6.1 shows minItems/minUniqueItems/maxUniqueItems on the parent and
# maxLength on the child, which is exactly the subset those two constructs state.
VALIDATION_KEYS = [
    "minLength", "maxLength", "pattern", "minimum", "maximum", "multipleOf",
    "minItems", "maxItems", "minUniqueItems", "maxUniqueItems",
]


def _validation(spec):
    return {k: spec[k] for k in VALIDATION_KEYS if k in spec}


# ===================================================================== what arrived at the OMS mock
#
# The runner contract in TESTING.md, trap 3: live evidence is not the run's evidence. These read the
# mock's own call log, so a check is judged on the bytes that crossed the wire rather than on a dict
# the suite still holds in memory. A suite that asserts on its own input has proved nothing.


def oms_clear_log(base_oms, token=None):
    """DELETE /log/data. Runner contract item 5 -- reset what the run owns, before firing."""
    return _http("DELETE", base_oms.rstrip("/") + "/log/data", token=token)[0]


_LOG_CACHE = {}


def oms_high_water(base_oms, token=None):
    """The newest sequence number in the OMS mock's log right now.

    Pass it back as `since` to read only what one case fired. A case that reads the whole log sees
    every earlier case's postings too, and "this product type was posted once" then fails on a
    second case having legitimately posted it again.
    """
    status, doc = _http("GET", base_oms.rstrip("/") + "/log/data", token=token)
    if status != 200 or not isinstance(doc, dict):
        return 0
    _LOG_CACHE[base_oms.rstrip("/")] = doc.get("entries") or []
    seqs = [e.get("seq") or e.get("_seq") or 0 for e in _LOG_CACHE[base_oms.rstrip("/")]]
    return max(seqs) if seqs else 0


def oms_received(base_oms, path, token=None, refresh=False, since=None):
    """Every request the OMS mock logged for `path`, in the order it received them.

    Returns [{"seq", "method", "url", "query": {...}, "body": {...}, "status"}]. `body` is the parsed
    request body as the mock recorded it; `raw` is its JSON text, for a key scan.

    The log carries a verbatim raw_schema_json per posting -- 147 KB for DE, 351 KB for AU -- so it
    is fetched once and cached. Pass refresh=True after firing, never before reading.
    """
    key = base_oms.rstrip("/")
    if refresh or key not in _LOG_CACHE:
        status, doc = _http("GET", key + "/log/data", token=token)
        _LOG_CACHE[key] = (doc.get("entries") or []) if (status == 200 and isinstance(doc, dict)) else []
    out = []
    for entry in _LOG_CACHE[key]:
        req = entry.get("request") or {}
        url = req.get("url") or ""
        if path not in url or (req.get("method") or "").upper() != "POST":
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
    import urllib.parse
    q = urllib.parse.urlparse(url).query
    return {k: v[0] for k, v in urllib.parse.parse_qs(q).items()}


def _http(method, url, token=None, timeout=30):
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


# ===================================================================== payload scans


def browse_node_keys(payload):
    """Every JSON key anywhere in `payload` that names a browse node. Must always be empty.

    Keys only. "recommended_browse_nodes" is a legal field_code *value* and is not reported here;
    an envelope property or a column called browse_node_ids, browseNodeIds or any other spelling is.
    """
    found = []

    def walk(node, trail):
        if isinstance(node, dict):
            for k, v in node.items():
                if BROWSE_NODE_KEY_PATTERN.search(str(k)):
                    found.append("%s.%s" % (trail, k) if trail else str(k))
                walk(v, "%s.%s" % (trail, k) if trail else str(k))
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, "%s[%d]" % (trail, i))

    walk(payload, "")
    return found


def attribute_rows(body):
    """category_attributes[] of one received bulk_categories_attributes body, keyed by field_code."""
    rows = {}
    for row in (body.get("category_attributes") or []):
        if isinstance(row, dict):
            rows[row.get("field_code")] = row
    return rows


def data_types_sent(body):
    """Distinct data_type values in one received payload, and which are outside C-OMS's sibling enum.

    Requirement 5 of this task: pin what is sent so CR-3's mismatch stays visible rather than
    silently passing. See UNSETTLED["data_type_enum"].
    """
    sent = sorted({str(r.get("data_type")) for r in (body.get("category_attributes") or [])
                   if isinstance(r, dict)})
    outside = [d for d in sent if d not in OMS_SIBLING_DATA_TYPE_ENUM]
    return sent, outside


DATE_SHAPED = re.compile(r"^\d{4}-\d{2}-\d{2}|^\d{4}/\d{2}/\d{2}|^\d{8}$")


def looks_like_a_date(token):
    """R-PLAN section 6.1 annotates definition_version as "an opaque token". A date-shaped value
    there means productTypeVersion was read as something other than `.version`."""
    return bool(DATE_SHAPED.match(str(token or "")))


BROWSE_PATH_SHAPED = re.compile(r"^\d+(_\d+)+$")


def looks_like_a_browse_node(code):
    """R-REQ section 2.1, the `$.category.code` UPDATE row, and R-PLAN section 1: before the branch
    the category code WAS the browse path (172282_281052_172541) and getCategoryCode returned its
    last segment. A category code that is all digits, or a digit chain joined by underscores, is the
    pre-branch value and the defect this ticket exists to remove."""
    text = str(code or "")
    return bool(BROWSE_PATH_SHAPED.match(text)) or text.isdigit()


UPPER_SNAKE = re.compile(r"^[A-Z0-9]+(_[A-Z0-9]+)*$")


def is_upper_snake(code):
    """R-MAP section 4.1, row 1: "Direct map, UPPER_SNAKE verbatim", never split on `_`."""
    return bool(UPPER_SNAKE.match(str(code or "")))


def load_capture(name):
    with open(os.path.join(SCHEMA_DIR, name), encoding="utf-8") as f:
        return json.load(f)
