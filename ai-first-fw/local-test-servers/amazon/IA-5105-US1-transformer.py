#!/usr/bin/env python3
"""Amazon SP-API to Anchanto OMS Taxonomy Transformer (IA-5105 User Story 1).

A local stand-in for the JPluger Amazon integration, which this harness cannot start. Every rule
below cites the requirement document it comes from, so a disagreement with a suite is an argument
about the requirement rather than a preference of this file:

  R-PLAN  the IA-5105 browse-node and listing plan (the current amendment)
  R-REQ   the OMS taxonomy requirements spec
  R-MAP   the product-types mapping spec
  C-OMS   anchanto-oms/anchanto-oms-swagger.json

Produces:
  1. POST /rest/v1/bulk_categories -- a flat category, with empty children and NO browse-node
     property of any kind (R-REQ section 2.2 REMOVE row, R-MAP section 1.1 item 2,
     R-PLAN section 6.1 "Nothing goes on bulk_categories").
  2. POST /rest/v1/bulk_categories_attributes -- the envelope, the verbatim raw_schema_json,
     Amazon's own schema_checksum passed through, and the flattened category_attributes.
"""

import json


# R-MAP section 4.2, row 9 / R-PLAN section 6.1: the keys Amazon states as bounds, copied only when
# stated so an unstated bound is absent rather than null.
VALIDATION_KEYS = (
    "minLength", "maxLength", "pattern", "minimum", "maximum", "multipleOf",
    "minItems", "maxItems", "minUniqueItems", "maxUniqueItems",
)

# C-OMS, POST /rest/v1/categories_attributes -- the closed field_type enum on the single-row
# sibling. R-REQ section 1 item 2 reads the bulk endpoint's free string as missing validation
# rather than a licence, so only these three spellings are ever sent.
FIELD_TYPE_ATTRIBUTES = "attributes"     # R-MAP section 5: data_type "array", no allowed values
FIELD_TYPE_OPTION_TYPE = "option_type"   # anything with allowed values
FIELD_TYPE_ATTRIBUTE = "attribute"       # everything else

# R-MAP section 5.
CRITERIA_IS_PARENT = "is_parent"
CRITERIA_IS_CHILD = "is_child"
CRITERIA_INDEPENDENT = "independent"

# R-PLAN section 6.1 / R-MAP section 4.2 row 1: free_text means the seller types the value, so a
# grouping row and a checkbox are never free text whatever else they state.
_NEVER_FREE_TEXT_TYPES = ("object", "array", "boolean")


def field_code_of(dotted_path):
    """Converts a dotted JSON-Schema property path into an OMS field code.

    R-MAP section 4.2, row 1: "the dotted property path, `.` -> `_`". The dot is OMS's own
    parent/child separator, so a literal dot in a field_code is the defect this replaces.
    """
    return dotted_path.replace(".", "_")


def build_bulk_category_payload(store_code, marketplace_code, product_type_code, display_name):
    """Builds the POST /rest/v1/bulk_categories body for one product type.

    Takes no browse-node argument on purpose. The 31-Aug revision asked for an envelope
    `browse_node_ids`; R-REQ section 2.2's REMOVE row withdraws it, R-MAP section 1.1 item 2 drops
    the field, and R-PLAN section 6.1 states "Nothing goes on bulk_categories". BulkCategoryDTO in
    the connector's own oms-schema.json declares no browse-node property either.
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
    its parent is the array-wrapper collapse R-MAP section 4.2 claim L-62 rejects, wearing a
    different hat.
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
    Never folds an array's item-level bounds up into the array row: R-MAP section 4.2 claim L-62
    rejects the fold, because the item level becomes its own sibling row instead.
    """
    validation = {k: prop[k] for k in VALIDATION_KEYS if k in prop}
    for key in VALIDATION_KEYS:
        if key not in validation and isinstance(resolved_ref, dict) and key in resolved_ref:
            validation[key] = resolved_ref[key]
    return validation or None


def compute_schema_checksum(schema_dict_or_str):
    """Computes an MD5 hex digest over a JSON Schema, for a caller with no stated checksum.

    Never used for `schema_checksum` on a real posting. R-MAP section 4.2 envelope row 4 makes that
    field a DIRECT MAP of Amazon's `$.schema.checksum`, and R-MAP section 6 / R-REQ section 2.3
    make it the only change detector Flow 2 has -- a locally recomputed digest is self-consistent
    whatever Amazon said, so it defeats the mechanism silently. Kept for callers that hold a schema
    and no envelope.
    """
    import hashlib
    raw = (schema_dict_or_str if isinstance(schema_dict_or_str, str)
           else json.dumps(schema_dict_or_str))
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def transform_schema_to_oms_attributes(schema, store_code, marketplace_code, category_code,
                                       definition_version="UHqSqmb4FNUk=", latest_version=True,
                                       omit_raw_schema=False, browse_node_values=None,
                                       schema_checksum=None):
    """Flattens one Product Type Definition schema into a bulk_categories_attributes payload.

    @param browse_node_values allowed values from GET_XML_BROWSE_TREE_DATA, keyed by field code
                              (R-PLAN section 4.5 item 2); a field code the schema omits adds no row
    @param schema_checksum Amazon's own `$.schema.checksum`, passed through verbatim; recomputed
                           locally only when the caller states none
    """
    defs = schema.get("$defs", schema.get("definitions", {})) or {}
    raw_json_str = json.dumps(schema, ensure_ascii=False)
    supplied_values = dict(browse_node_values or {})

    category_attributes = []

    def walk(properties, required_codes, parent_path=None, depth=0):
        if depth > 10 or not properties:
            return

        for code, prop in properties.items():
            if not isinstance(prop, dict):
                continue

            dotted_path = "%s.%s" % (parent_path, code) if parent_path else code
            field_code = field_code_of(dotted_path)

            # A $ref is resolved first, because a referenced property's type, default and examples
            # live in the target. One that cannot be resolved leaves nothing to describe, and
            # C-OMS declares data_type required on every category_attributes[] row, so the row is
            # skipped rather than sent with an invented type.
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

            # R-MAP section 4.2, L-62: an array's items.properties become sibling rows, never a fold
            # into this row's validation. The fold publishes 36 rows for DE against 147 expanded,
            # with no allowed values, no unit and no default anywhere.
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
                # R-PLAN D-1: the browse tree is the producer when the schema enumerates nothing.
                # Keyed on field code with no field-name special case anywhere.
                field_values = list(supplied_values[field_code])

            editable = prop.get("editable", resolved_ref.get("editable", True))
            hidden = prop.get("hidden", resolved_ref.get("hidden", False))

            # R-PLAN section 4.5 item 1: field_type, option_type and free_text all key off
            # hasFieldValues, so filling the picker flips all three with no extra branch.
            if field_values:
                field_type = FIELD_TYPE_OPTION_TYPE
            elif data_type == "array":
                field_type = FIELD_TYPE_ATTRIBUTES
            else:
                field_type = FIELD_TYPE_ATTRIBUTE

            row = {
                "field_code": field_code,
                "ss_field_code": field_code,
                "field_parent_code": field_code_of(parent_path) if parent_path else None,
                "field_name": prop.get("title") or resolved_ref.get("title")
                              or code.replace("_", " ").title(),
                # R-MAP section 4.2, row 7: Amazon's raw JSON-Schema type, verbatim. Most of these
                # are outside C-OMS's sibling enum, which is CR-3 and unanswered.
                "data_type": data_type,
                "field_type": field_type,
                # R-REQ section 2.2: the ENCLOSING object's required[], as a strict boolean
                "mandatory": code in (required_codes or set()),
                # R-PLAN section 4.4: an empty picker publishes "with an empty field_values and free
                # text". Amazon's editable flag is reported through smp_field instead -- G-3/CR-6
                # records that OMS's handling of a non-editable mandatory picker is unconfirmed.
                "free_text": not field_values and not has_children
                             and data_type not in _NEVER_FREE_TEXT_TYPES,
                "option_type": bool(field_values),
                # R-REQ section 2.2: smp_field carries !editable, not a hardcoded false
                "smp_field": editable is False or hidden is True,
                "field_criteria": CRITERIA_IS_PARENT if has_children
                                  else (CRITERIA_IS_CHILD if parent_path else CRITERIA_INDEPENDENT),
                "marketplace_code": marketplace_code,
            }

            if field_values:
                row["field_values"] = field_values

            # Always present, empty when Amazon states no bound: R-PLAN section 6.1 shows the map
            # on both rows, and R-MAP section 4.2 row 9 scopes "only when stated" to the keys
            # inside it. An absent map and an empty one are different answers to "what did Amazon
            # constrain", and the second is the true one.
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

    payload = {
        "store_code": store_code,
        "category_code": category_code,
        "marketplace_code": marketplace_code,
        "definition_version": definition_version,
        "latest_version": latest_version,
        "schema_checksum": schema_checksum if schema_checksum is not None
                           else compute_schema_checksum(schema),
        "category_attributes": category_attributes,
    }

    if not omit_raw_schema:
        payload["raw_schema_json"] = raw_json_str

    return payload
