#!/usr/bin/env python3
"""Amazon SP-API to Anchanto OMS Taxonomy Transformer (IA-5105 User Story 1).

A local stand-in for the JPluger Amazon integration, which this harness cannot start. Every rule
below cites the requirement document it comes from, so a disagreement with a suite is an argument
about the requirement rather than a preference of this file:

  D-WIRE  the bulk_categories_attributes wire contract (sections 1.1-1.5)
  D-GAP   the decision log (decisions 2-8) and the request/row tables (sections 1.2-1.5)
  D-MATRIX the coverage matrix rows quoted against each rule
  C-OMS   anchanto-oms/anchanto-oms-swagger.json

Produces:
  1. POST /rest/v1/bulk_categories -- a flat category, with empty children and NO browse-node
     property of any kind (D-GAP section 2 REMOVE row, D-MATRIX N10).
  2. POST /rest/v1/bulk_categories_attributes -- the envelope, its `definition_status`, the verbatim
     raw_schema_json, Amazon's own schema_checksum passed through, and the flattened
     category_attributes.

WHAT THIS STAND-IN MODELS, as of T35. It is two layers, not one:

  the fetch layer   `build_definition_payload` -- the four gates of
                    `AmazonDefinitionsUtility.fetchDefinition`, in that method's own order: no
                    schema link, then a definition Amazon does not mark latest, then a failed
                    download, then bytes that do not match the stated checksum. Any of them answers
                    FETCH_FAILED with the reason production emits verbatim.
  the flatten layer `transform_schema_to_oms_attributes` -- everything below, unchanged.

WHAT IT DOES NOT MODEL, so a case asserting any of it is asserting nothing:
  * UNAVAILABLE. It belongs to the 404 on `getDefinitionsProductType`, which is the CALLER's call to
    make; no envelope exists to hand this file when Amazon served none.
  * The retry budget, the pacer, and every `[JP]`-side behaviour -- checkpoints, chaining, operator
    traces. There is no JPluger under test (REWRITE-PLAN §0.9.1).
  * The allOf merge, and therefore the `$ref` CYCLE that `mergeSubschema:966` raises PARSE_FAILED
    for. This file performs no merge, so it has no chain in which a reference could repeat.

T28 scoped the fetch layer OUT of this file on the ground that FETCH_FAILED belongs to a fetch that
never reached a schema. T35 reversed that deliberately: three contract states OMS must be able to
receive were otherwise unprovable in this harness, which is worse than the extra surface.

Absent keys are absent, not null: Gson drops nulls, so a key this file omits is a key that never
reaches the wire (D-MATRIX B6). `category_attributes` is therefore OMITTED -- never `[]` -- on
UNAVAILABLE, PARSE_FAILED and FETCH_FAILED, and `definition_status_reason` is omitted on AVAILABLE
save for the one exception the four-child cap creates.

NOT IMPLEMENTED, deliberately: D-GAP decision 8 names an unresolvable `$ref` as a second
PARSE_FAILED driver alongside the depth breach. Wiring it would make `fr-schema-SHOES.json` -- which
plants a top-level `orphan_ref` property pointing at `#/$defs/does_not_exist` -- a PARSE_FAILED
definition carrying no `category_attributes`, and TAX-ATTR-INV-1 drives that very capture to assert
that attribute rows ARE present. No suite drives the orphan-$ref branch at the wire, so the contract
and the fixture disagree with nothing to arbitrate between them. The row is skipped, the definition
stays parseable, and the collision is reported rather than decided here.
"""

import json


# D-WIRE section 1.2 / D-GAP section 1.4: the ten keys Amazon states as bounds, copied only when
# stated so an unstated bound is absent rather than zero (D-MATRIX B7). `multipleOf`, `item_maxLength`
# and `item_required` belonged to the superseded mapping spec and are NOT contract keys.
VALIDATION_KEYS = (
    "minLength", "maxLength", "maxUtf8ByteLength", "pattern", "minimum", "maximum",
    "minItems", "maxItems", "minUniqueItems", "maxUniqueItems",
)

# C-OMS, POST /rest/v1/categories_attributes -- the closed field_type enum on the single-row
# sibling. D-GAP section 1.4 reads the bulk endpoint's free string as missing validation rather than
# a licence, so only these three spellings are ever sent.
FIELD_TYPE_ATTRIBUTES = "attributes"     # data_type "array", no allowed values
FIELD_TYPE_OPTION_TYPE = "option_type"   # anything with allowed values
FIELD_TYPE_ATTRIBUTE = "attribute"       # everything else

# D-WIRE section 1.3 / D-GAP section 1.4.
CRITERIA_IS_PARENT = "is_parent"
CRITERIA_IS_CHILD = "is_child"
CRITERIA_INDEPENDENT = "independent"

# D-GAP decision 8 / D-WIRE section 1.1: six values exactly. FETCH_FAILED is never folded into
# UNAVAILABLE -- the first owes a retry and the second is terminal, and a caller that cannot tell
# them apart retries a 404 forever or abandons a transient fault.
STATUS_AVAILABLE = "AVAILABLE"
STATUS_UNAVAILABLE = "UNAVAILABLE"
STATUS_PARSE_FAILED = "PARSE_FAILED"
STATUS_SCHEMA_OMITTED = "SCHEMA_OMITTED"
STATUS_VALUES_OMITTED = "VALUES_OMITTED"
STATUS_FETCH_FAILED = "FETCH_FAILED"

# D-WIRE section 1.1: the statuses whose `category_attributes` key is absent rather than empty, and
# whose `raw_schema_json` never travels. PARSE_FAILED is the exception that keeps its raw document:
# the bytes are the only evidence of why the flattener refused them.
STATUSES_WITHOUT_ATTRIBUTES = (STATUS_UNAVAILABLE, STATUS_PARSE_FAILED, STATUS_FETCH_FAILED)

# The reason strings `AmazonDefinitionsUtility.fetchDefinition:241-264` emits VERBATIM. They are
# quoted, not composed: D-MATRIX A5, A6, C1, C7 and C8 each assert one of them character for
# character, so a reworded string fails the contract even when the status beside it is right.
REASON_CHECKSUM_MISMATCH = "downloaded schema does not match Amazon's checksum"
REASON_NOT_LATEST = "Amazon returned a definition it does not mark latest"
REASON_SCHEMA_DOWNLOAD_FAILED = "schema download failed"
REASON_NO_SCHEMA_LINK = "definition carries no schema link"
REASON_UNAVAILABLE_PREFIX = "Amazon defines no schema for "

# D-WIRE section 1.2 "Nesting limits" / D-GAP decision 4: the one AVAILABLE definition that still
# carries a reason, composed as "<node> states <n> children; 4 published" and joined by "; ".
WIDTH_REASON_TEMPLATE = "%s states %d children; %d published"
STATUS_REASON_JOIN = "; "

# The depth breach has no verbatim string in the deliverables -- the five quoted reasons all belong
# to the fetch failures -- so it states the measurement that refused the document.
DEPTH_REASON_TEMPLATE = "schema nests %d levels; the limit is %d"
SCHEMA_OMITTED_REASON = "serialized message exceeds %d bytes; raw_schema_json dropped"
VALUES_OMITTED_REASON = "still over %d bytes without the schema; every field_values emptied"

# D-GAP decision 3 / D-WIRE section 1.2. CODE: AmazonConstant:589.
DEFINITIONS_MAX_NESTING_DEPTH = 9

# D-GAP decision 4 / D-WIRE section 1.2. CODE: AmazonConstant:603.
DEFINITIONS_MAX_CHILDREN_PER_NODE = 4

# D-WIRE section 1.1 SCHEMA_OMITTED and section 2. CODE: AmazonConstant:575 (900 * 1024).
RAW_SCHEMA_MAX_BYTES = 900 * 1024

# D-MATRIX D6. CODE: AmazonConstant:662.
MAX_FIELD_VALUES_PER_ATTRIBUTE = 8000

# D-GAP section 1.4: free_text means the seller types the value, so a grouping row and a checkbox
# are never free text whatever else they state.
_NEVER_FREE_TEXT_TYPES = ("object", "array", "boolean")


def field_code_of(dotted_path):
    """Returns the OMS field code for a JSON-Schema property path, which IS the dotted path.

    D-GAP decision 2: nested codes carry the path, dot-separated -- `package_info.dimensions.length`.
    Amazon property names contain `_` and never `.`, so the dot is the only unambiguous join, and
    uniqueness becomes an invariant of the path rather than a de-duplication step. The underscored
    form this function used to produce is the defect IA-5105 removes (D-PLAN phase 1, D1/D3).

    @param dotted_path the property path already joined with `.`, non-empty
    @return the field code, character for character the path it was given
    """
    return dotted_path


def max_nesting_depth(schema):
    """Measures the deepest property nesting, counted the way the flattener descends.

    An `items` hop costs no depth: an array and its item level are one node to OMS, which is why a
    three-row measurement (parent, `.value`, `.unit`) reads as one level and not two.

    @param schema the schema document, or any node inside one
    @return the depth of the deepest `properties` chain, {@code 0} for a node that nests none
    """
    def walk(node, depth):
        if not isinstance(node, dict) or depth > 30:
            return depth
        best = depth
        properties = node.get("properties")
        if isinstance(properties, dict):
            for child in properties.values():
                best = max(best, walk(child, depth + 1))
        items = node.get("items")
        if isinstance(items, dict):
            best = max(best, walk(items, depth))
        return best

    return walk(schema, 0)


def build_bulk_category_payload(store_code, marketplace_code, product_type_code, display_name):
    """Builds the POST /rest/v1/bulk_categories body for one product type.

    Takes no browse-node argument on purpose. The 31-Aug revision asked for an envelope
    `browse_node_ids`; D-GAP section 2's REMOVE row withdraws it and D-MATRIX N10 forbids asserting
    it. BulkCategoryDTO in the connector's own oms-schema.json declares no browse-node property
    either -- classification travels as picker rows inside `category_attributes`.
    """
    return {
        "store_code": store_code,
        "category": {
            "name": display_name,
            "code": product_type_code,
            "marketplace_code": marketplace_code,
            "active": True,
            "children": [],
            "store_code": store_code,
            "position": 0,
            "variation": False,
        },
    }


def _resolve(spec, defs):
    """The `$ref` target, which describes a node that is nothing but a reference."""
    if isinstance(spec, dict) and "$ref" in spec:
        return defs.get(spec["$ref"].split("/")[-1], {}) or {}
    return {}


def extract_enums(prop, items_spec, resolved_ref):
    """Extracts allowed values and their display names from wherever Amazon states them.

    Amazon states one list in alternative places -- `enum`, an `anyOf`/`oneOf` branch, the item
    level of an array -- so the first hit wins; they are spellings of one list, not parts of one.

    `items_spec` is read for an array of primitives, whose values Amazon can only state at the item
    level. It is NOT read past its own `properties`: once the item level names properties they
    become their own rows, and each owns the values Amazon stated on it. Reading a child's enum onto
    its parent is the array-wrapper collapse D-MATRIX B8 rejects, wearing a different hat.
    """
    for spec in (prop, resolved_ref, items_spec):
        if not isinstance(spec, dict):
            continue
        if "enum" in spec:
            return spec["enum"], spec.get("enumNames", spec["enum"])
        for keyword in ("anyOf", "oneOf"):
            for branch in spec.get(keyword) or []:
                if isinstance(branch, dict) and "enum" in branch:
                    return branch["enum"], branch.get("enumNames", branch["enum"])
    return None, None


def extract_validation_constraints(prop, resolved_ref=None):
    """Collects the bounds Amazon states on one property, and nothing it leaves unstated.

    Reads the property itself, then lets its `$ref` target answer for keys the property omits.
    Never folds an array's item-level bounds up into the array row: D-MATRIX B8 rejects the fold,
    because the item level becomes its own sibling row instead.
    """
    validation = {k: prop[k] for k in VALIDATION_KEYS if k in prop}
    for key in VALIDATION_KEYS:
        if key not in validation and isinstance(resolved_ref, dict) and key in resolved_ref:
            validation[key] = resolved_ref[key]
    return validation or None


def compute_schema_checksum(schema_dict_or_str):
    """Computes an MD5 hex digest over a JSON Schema, for a caller with no stated checksum.

    Never used for `schema_checksum` on a real posting. D-WIRE section 1.1 makes that field a direct
    map of Amazon's `$.schema.checksum`, and it is the only change detector the refresh flow has --
    a locally recomputed digest is self-consistent whatever Amazon said, so it defeats the mechanism
    silently. Kept for callers that hold a schema and no envelope.
    """
    import hashlib
    raw = (schema_dict_or_str if isinstance(schema_dict_or_str, str)
           else json.dumps(schema_dict_or_str))
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def _serialised_bytes(payload):
    """The wire size of one message in BYTES, not characters.

    D-WIRE section 2 states the limit in bytes, so a multibyte definition (a JP capture, an accented
    FR label) must be measured after encoding or it passes a limit it actually breaches.
    """
    return len(json.dumps(payload, ensure_ascii=False).encode("utf-8"))


def transform_schema_to_oms_attributes(schema, store_code, marketplace_code, category_code,
                                       definition_version="UHqSqmb4FNUk=", latest_version=True,
                                       omit_raw_schema=False, browse_node_values=None,
                                       schema_checksum=None):
    """Flattens one Product Type Definition schema into a bulk_categories_attributes payload.

    Emits `definition_status` on every body and drives it from the document itself: a depth breach
    answers PARSE_FAILED before a single row is built, a node wider than the cap leaves the status
    AVAILABLE and names the breach in the reason, and an oversize message degrades SCHEMA_OMITTED
    then VALUES_OMITTED in that order. UNAVAILABLE and FETCH_FAILED belong to the fetch that never
    reached a schema, so they are not produced here.

    @param schema the Product Type Definition document as Amazon served it
    @param definition_version Amazon's `productTypeVersion.version`, opaque -- never parsed or ordered
    @param latest_version Amazon's `productTypeVersion.latest`
    @param omit_raw_schema forces the SCHEMA_OMITTED degradation whatever the message measures
    @param browse_node_values allowed values from GET_XML_BROWSE_TREE_DATA, keyed by field code; a
                              field code the schema omits adds no row
    @param schema_checksum Amazon's own `$.schema.checksum`, passed through verbatim; recomputed
                           locally only when the caller states none
    @return the request body, carrying no key whose contract value is absent

    @apiNote Pure: reads the schema and returns a body, touching no wire and no clock.
    """
    defs = schema.get("$defs", schema.get("definitions", {})) or {}
    raw_json_str = json.dumps(schema, ensure_ascii=False)
    supplied_values = dict(browse_node_values or {})

    payload = {
        "store_code": store_code,
        "category_code": category_code,
        "marketplace_code": marketplace_code,
        "definition_version": definition_version,
        "latest_version": latest_version,
        "schema_checksum": schema_checksum if schema_checksum is not None
                           else compute_schema_checksum(schema),
    }

    # D-GAP decision 3: a document nesting deeper than the cap is refused WHOLE -- the flattener
    # cannot express it, so a partial array would misrepresent the definition as complete. The raw
    # document still travels: it is the only evidence of what was refused (D-MATRIX A3).
    depth = max_nesting_depth(schema)
    if depth > DEFINITIONS_MAX_NESTING_DEPTH:
        payload["raw_schema_json"] = raw_json_str
        payload["definition_status"] = STATUS_PARSE_FAILED
        payload["definition_status_reason"] = DEPTH_REASON_TEMPLATE % (
            depth, DEFINITIONS_MAX_NESTING_DEPTH)
        return payload

    category_attributes = []
    truncations = []

    def walk(properties, required_codes, parent_path=None, depth=0):
        if depth > DEFINITIONS_MAX_NESTING_DEPTH or not properties:
            return

        # D-GAP decision 4: a node wider than the cap publishes its first four in AMAZON'S OWN
        # property order -- the order the document states, never a sorted or filtered one, because
        # the seller reads the first four as the ones Amazon leads with.
        #
        # The ROOT is exempt. The cap governs an attribute node, and D-PLAN phase 2 names the AU
        # capture's breaches as four nested nodes and no root -- a root cap would truncate every
        # real definition to four attributes and call it complete.
        publishable = list(properties.items())
        if parent_path and len(publishable) > DEFINITIONS_MAX_CHILDREN_PER_NODE:
            truncations.append((parent_path, len(publishable)))
            publishable = publishable[:DEFINITIONS_MAX_CHILDREN_PER_NODE]

        for code, prop in publishable:
            if not isinstance(prop, dict):
                continue

            dotted_path = "%s.%s" % (parent_path, code) if parent_path else code
            field_code = field_code_of(dotted_path)

            # A $ref is resolved first, because a referenced property's type, default and examples
            # live in the target. One that cannot be resolved leaves nothing to describe, and
            # C-OMS declares data_type required on every category_attributes[] row, so the row is
            # skipped rather than sent with an invented type. See the module docstring for why this
            # does not raise PARSE_FAILED here.
            if "$ref" in prop:
                resolved_ref = _resolve(prop, defs)
                if not resolved_ref:
                    continue
            else:
                resolved_ref = {}

            data_type = prop.get("type") or resolved_ref.get("type")
            items_spec = prop.get("items") or {}
            if "$ref" in items_spec:
                items_spec = _resolve(items_spec, defs)

            # D-MATRIX B8: an array's items.properties become sibling rows, never a fold into this
            # row's validation. The fold publishes 36 rows for DE against 147 expanded, with no
            # allowed values, no unit and no default anywhere.
            if data_type == "object":
                child_properties = prop.get("properties") or {}
                child_required = set(prop.get("required") or [])
            elif data_type == "array":
                child_properties = (items_spec.get("properties") or {}) if isinstance(items_spec, dict) else {}
                child_required = set(items_spec.get("required") or []) if isinstance(items_spec, dict) else set()
            else:
                child_properties, child_required = {}, set()

            has_children = bool(child_properties)

            enum_values, enum_names = extract_enums(
                prop, None if has_children else items_spec, resolved_ref)
            field_values = None
            if enum_values:
                field_values = [
                    {"name": str(enum_names[i]) if i < len(enum_names) else str(value),
                     "value": str(value)}
                    for i, value in enumerate(enum_values)
                ]
            elif not has_children and supplied_values.get(field_code):
                # The browse tree is the producer when the schema enumerates nothing. Keyed on field
                # code with no field-name special case anywhere, so the picker's dotted code is the
                # key the caller must supply (D-PLAN phase 4b states the coupling).
                field_values = list(supplied_values[field_code])
            if field_values:
                field_values = field_values[:MAX_FIELD_VALUES_PER_ATTRIBUTE]

            editable = prop.get("editable", resolved_ref.get("editable", True))
            hidden = prop.get("hidden", resolved_ref.get("hidden", False))

            # field_type, option_type and free_text all key off hasFieldValues, so filling the picker
            # flips all three with no extra branch.
            if field_values:
                field_type = FIELD_TYPE_OPTION_TYPE
            elif data_type == "array":
                field_type = FIELD_TYPE_ATTRIBUTES
            else:
                field_type = FIELD_TYPE_ATTRIBUTE

            row = {
                "field_code": field_code,
                "ss_field_code": field_code,
                "field_name": prop.get("title") or resolved_ref.get("title")
                              or code.replace("_", " ").title(),
                # D-WIRE section 1.4: Amazon's raw JSON-Schema type, verbatim. D-RECON section 1
                # settles the five additions -- OMS stores data_type as a free VARCHAR.
                "data_type": data_type,
                "field_type": field_type,
                # D-GAP section 1.4: the ENCLOSING object's required[], as a strict boolean
                "mandatory": code in (required_codes or set()),
                # D-WIRE section 1.1: an empty picker publishes an empty field_values and free text.
                # Amazon's editable flag is reported through smp_field instead.
                "free_text": not field_values and not has_children
                             and data_type not in _NEVER_FREE_TEXT_TYPES,
                "option_type": bool(field_values),
                # smp_field carries !editable, not a hardcoded false
                "smp_field": editable is False or hidden is True,
                "field_criteria": CRITERIA_IS_PARENT if has_children
                                  else (CRITERIA_IS_CHILD if parent_path else CRITERIA_INDEPENDENT),
                "marketplace_code": marketplace_code,
            }

            # D-WIRE section 1.3: field_parent_code is ABSENT at top level, not null. `id` and
            # `field_parent_id` stay unset on every Amazon row (D-MATRIX N16), so neither is set here.
            if parent_path:
                row["field_parent_code"] = field_code_of(parent_path)

            if field_values:
                row["field_values"] = field_values

            # Always present, empty when Amazon states no bound: an absent map and an empty one are
            # different answers to "what did Amazon constrain", and the second is the true one.
            # D-MATRIX B7 scopes "only when stated" to the keys INSIDE the map.
            row["validation"] = extract_validation_constraints(prop, resolved_ref) or {}

            default_value = prop.get("default", resolved_ref.get("default"))
            if default_value is not None:
                row["default"] = str(default_value)

            description = prop.get("description") or resolved_ref.get("description")
            if description:
                row["description"] = description

            category_attributes.append(row)

            walk(child_properties, child_required, parent_path=dotted_path, depth=depth + 1)

    walk(schema.get("properties") or {}, set(schema.get("required") or []))

    payload["category_attributes"] = category_attributes
    payload["raw_schema_json"] = raw_json_str

    # D-GAP decision 4: the truncation rides an AVAILABLE definition. It is the ONLY reason that ever
    # accompanies AVAILABLE, because the definition is complete and usable -- the seller is told
    # which node was cut rather than handed a failure.
    reasons = [WIDTH_REASON_TEMPLATE % (path, stated, DEFINITIONS_MAX_CHILDREN_PER_NODE)
               for path, stated in truncations]

    def restate(status):
        """Stamps the status and its reason onto the body, so what is measured is what is sent."""
        payload["definition_status"] = status
        if reasons:
            payload["definition_status_reason"] = STATUS_REASON_JOIN.join(reasons)
        else:
            payload.pop("definition_status_reason", None)

    restate(STATUS_AVAILABLE)

    # D-WIRE section 2: the degradation runs in one direction and stops at the first measurement
    # that fits. Dropping the schema is tried before emptying the values because the raw document is
    # re-fetchable and the values are not. Each measurement is taken on the WHOLE body, status and
    # reason included -- a limit checked against a partial message is not the limit the wire applies.
    if omit_raw_schema or _serialised_bytes(payload) > RAW_SCHEMA_MAX_BYTES:
        payload.pop("raw_schema_json", None)
        reasons.append(SCHEMA_OMITTED_REASON % RAW_SCHEMA_MAX_BYTES)
        restate(STATUS_SCHEMA_OMITTED)

        if _serialised_bytes(payload) > RAW_SCHEMA_MAX_BYTES:
            for row in category_attributes:
                if "field_values" in row:
                    row["field_values"] = []
            reasons.append(VALUES_OMITTED_REASON % RAW_SCHEMA_MAX_BYTES)
            restate(STATUS_VALUES_OMITTED)

    return payload


# ===================================================================== the fetch layer
#
# Added T35 by authority, reversing the T28 scoping recorded in the module docstring. Before this,
# the stand-in was a flattener only and FETCH_FAILED was unreachable, which left three contract
# states OMS must be able to receive permanently unprovable (TAX-LATEST-1, TAX-DL-FAIL-1,
# TAX-NO-LINK-1). This is the minimum that makes those verdicts real and nothing beyond it.


def checksum_matches(stated_checksum, schema_bytes):
    """Reports whether Amazon's stated checksum describes the bytes actually downloaded.

    Mirrors `AmazonDefinitionsUtility.checksumMatches:511-526` exactly, including its two tolerances:
    it FAILS OPEN on an empty or absent stated checksum, because Amazon omitting the field is not
    evidence the bytes are wrong, and it accepts the digest in either spelling Amazon uses --
    base64, or hex compared case-insensitively.

    @param stated_checksum Amazon's `$.schema.checksum`, may be {@code None} or empty
    @param schema_bytes the downloaded document, as bytes
    @return {@code True} when the checksum is absent, or when it matches in either spelling
    """
    if not stated_checksum:
        return True

    import base64
    import hashlib

    digest = hashlib.md5(schema_bytes).digest()

    return (stated_checksum == base64.b64encode(digest).decode()
            or stated_checksum.lower() == digest.hex())


def build_definition_payload(envelope, store_code, marketplace_code, category_code,
                             download, browse_node_values=None):
    """Applies the fetch gates to one definition envelope, then flattens what survives them.

    The gates and their order are `AmazonDefinitionsUtility.fetchDefinition:241-264`, reproduced
    because the ORDER is itself contractual: a definition with no schema link is refused before its
    version is read, and a non-latest definition is refused before its bytes are downloaded, so a
    non-latest definition that would also have failed its checksum reports the version, never the
    checksum. Each reason string is the one the production code emits verbatim.

    The 404 gate that produces UNAVAILABLE is NOT here: it belongs to the call that raised the 404,
    which is the caller's, and no envelope exists to pass when Amazon served none.

    @param envelope the `getDefinitionsProductType` body, as Amazon served it
    @param download callable taking the schema link and returning {@code (status, parsed, raw_bytes)};
                   INJECTED rather than defaulted because the mock hardcodes `127.0.0.1:23103` into
                   every `schema.link.resource`, so a producer that fetched the stated host directly
                   would read another process's mock (REWRITE-PLAN §0.9.4)
    @return a FETCH_FAILED body carrying neither `raw_schema_json` nor `category_attributes`, or the
            full flattened payload when every gate passes
    """
    version = (envelope.get("productTypeVersion") or {}) if isinstance(envelope, dict) else {}
    schema_link = (envelope.get("schema") or {}) if isinstance(envelope, dict) else {}
    resource = ((schema_link.get("link") or {}).get("resource")) if schema_link else None

    def refused(reason):
        """A FETCH_FAILED body. Keys whose value is unknown at this point are omitted, not nulled."""
        body = {
            "store_code": store_code,
            "category_code": category_code,
            "marketplace_code": marketplace_code,
            "definition_status": STATUS_FETCH_FAILED,
            "definition_status_reason": reason,
        }
        for key, value in (("definition_version", version.get("version")),
                           ("latest_version", version.get("latest")),
                           ("schema_checksum", schema_link.get("checksum"))):
            if value is not None:
                body[key] = value

        return body

    if not resource:
        return refused(REASON_NO_SCHEMA_LINK)

    # An unflagged version may be a release candidate, indistinguishable from the live schema at OMS.
    if version.get("latest") is not True:
        return refused(REASON_NOT_LATEST)

    try:
        status, schema, raw_bytes = download(resource)
    except Exception:
        return refused(REASON_SCHEMA_DOWNLOAD_FAILED)

    if status != 200 or not isinstance(schema, dict) or not schema:
        return refused(REASON_SCHEMA_DOWNLOAD_FAILED)

    if not checksum_matches(schema_link.get("checksum"), raw_bytes or b""):
        return refused(REASON_CHECKSUM_MISMATCH)

    return transform_schema_to_oms_attributes(
        schema, store_code, marketplace_code, category_code,
        definition_version=version.get("version"),
        latest_version=version.get("latest"),
        browse_node_values=browse_node_values,
        schema_checksum=schema_link.get("checksum"))
