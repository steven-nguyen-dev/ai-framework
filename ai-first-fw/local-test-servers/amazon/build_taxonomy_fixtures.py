#!/usr/bin/env python3
"""Wires official Amazon Product Type Definitions fixtures into amazon.mock.json.

Reads the 10 official and rich definition fixtures checked into:
  local-test-servers/amazon/schemas/product-types/

And automatically populates:
  1. GET /definitions/2020-09-01/productTypes (search) route, branching per marketplace
  2. GET /definitions/2020-09-01/productTypes/{productType} (definition envelopes)
  3. GET /s3/ptd-schema/{productType} (serving raw schemas verbatim per productType and marketplaceId)

100% self-contained in this repository.
"""
import base64
import hashlib
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SCHEMAS_DIR = os.path.join(HERE, "schemas", "product-types")
MOCK_JSON = os.path.join(HERE, "amazon.mock.json")
BASE = "http://127.0.0.1:23103"

GENERATED_TAG = "Amazon SP-API taxonomy fixture"


def load_schema(name):
    with open(os.path.join(SCHEMAS_DIR, name), encoding="utf-8") as f:
        return json.load(f)


def version_for(product_type, marketplace_id):
    """A stable, realistic-looking base64 version token, distinct per (productType, marketplaceId)."""
    digest = hashlib.md5((product_type + "|" + marketplace_id).encode()).digest()[:9]
    return base64.b64encode(digest).decode()


# ------------------------------------------------------------------ 10 Product Type Combinations across 6 Regions

COMBOS = [
    # US Marketplace (ATVPDKIKX0DER)
    dict(region="US (North America)", product_type="LUGGAGE", marketplace_id="ATVPDKIKX0DER",
         locale="en_US", display_name="Luggage", schema_file="us-schema-LUGGAGE.json"),
    dict(region="US (North America)", product_type="CLOTHING", marketplace_id="ATVPDKIKX0DER",
         locale="en_US", display_name="Clothing", schema_file="us-schema-CLOTHING.json"),
    dict(region="US (North America)", product_type="ELECTRONICS", marketplace_id="ATVPDKIKX0DER",
         locale="en_US", display_name="Electronics", schema_file="us-schema-ELECTRONICS.json"),
    dict(region="US (North America)", product_type="TOYS_AND_GAMES", marketplace_id="ATVPDKIKX0DER",
         locale="en_US", display_name="Toys and Games", schema_file="us-schema-TOYS_AND_GAMES.json"),

    # Europe - France (A13V1IB3VIYZZH)
    dict(region="FR (Europe)", product_type="SHOES", marketplace_id="A13V1IB3VIYZZH",
         locale="fr_FR", display_name="Shoes", schema_file="fr-schema-SHOES.json"),

    # Europe - Germany (A1PA6795UKMFR9)
    dict(region="DE (Europe)", product_type="PRODUCT", marketplace_id="A1PA6795UKMFR9",
         locale="de_DE", display_name="Product", schema_file="de-schema-PRODUCT.json"),

    # Europe - Spain (A1RKKUPIHCS9HS)
    dict(region="ES (Europe)", product_type="PRODUCT", marketplace_id="A1RKKUPIHCS9HS",
         locale="es_ES", display_name="Product", schema_file="es-schema-PRODUCT.json"),

    # Europe - UK / Great Britain (A1F83G8C2ARO7P)
    dict(region="UK (Europe)", product_type="FURNITURE", marketplace_id="A1F83G8C2ARO7P",
         locale="en_GB", display_name="Furniture", schema_file="gb-schema-FURNITURE.json"),

    # Far East - Japan (A1VC38T7YXB528)
    dict(region="JP (Far East)", product_type="BEAUTY", marketplace_id="A1VC38T7YXB528",
         locale="ja_JP", display_name="Beauty", schema_file="jp-schema-BEAUTY.json"),

    # Far East - Australia (A39IBJ37TRP1C6)
    dict(region="AU (Far East)", product_type="AUTO_PART", marketplace_id="A39IBJ37TRP1C6",
         locale="en_AU", display_name="Auto Part", schema_file="au-schema-AUTO_PART.json"),
]

for combo in COMBOS:
    schema = load_schema(combo["schema_file"])
    combo["schema"] = schema
    combo["version"] = version_for(combo["product_type"], combo["marketplace_id"])
    props = list((schema.get("properties") or {}).keys())
    combo["property_groups_names"] = props[:8] or ["item_name"]


def schema_link(product_type, marketplace_id):
    return "%s/s3/ptd-schema/%s?marketplaceId=%s" % (BASE, product_type, marketplace_id)


def envelope_for(combo):
    raw_str = json.dumps(combo["schema"])
    checksum = hashlib.md5(raw_str.encode("utf-8")).hexdigest()
    return {
        "metaSchema": {
            "link": {"resource": "%s/s3/ptd-schema/_meta" % BASE, "verb": "GET"},
            "checksum": "",
        },
        "schema": {
            "link": {"resource": schema_link(combo["product_type"], combo["marketplace_id"]), "verb": "GET"},
            "checksum": checksum,
        },
        "requirements": "${query.requirements|LISTING_PRODUCT_ONLY}",
        "requirementsEnforced": "${query.requirementsEnforced|ENFORCED}",
        "propertyGroups": {
            "product_identity": {
                "title": "Product Identity",
                "description": "Information to uniquely identify your product",
                "propertyNames": combo["property_groups_names"],
            }
        },
        "locale": "${query.locale|%s}" % combo["locale"],
        "marketplaceIds": ["${query.marketplaceIds|%s}" % combo["marketplace_id"]],
        "productType": combo["product_type"],
        "displayName": combo["display_name"],
        "productTypeVersion": {
            "version": combo["version"],
            "latest": True,
            "releaseCandidate": False,
        },
    }


def definition_rule(combo):
    return {
        "name": "%s -- %s %s (%s)" % (GENERATED_TAG, combo["region"], combo["product_type"], combo["marketplace_id"]),
        "when": {
            "path.productType": {"equals": combo["product_type"]},
            "query.marketplaceIds": {"contains": combo["marketplace_id"]},
        },
        "respond": {
            "status": 200,
            "body": envelope_for(combo),
        },
    }


def schema_rule(combo):
    return {
        "name": "%s -- %s %s schema" % (GENERATED_TAG, combo["region"], combo["product_type"]),
        "when": {
            "path.productType": {"equals": combo["product_type"]},
            "query.marketplaceId": {"equals": combo["marketplace_id"]},
        },
        "respond": {
            "status": 200,
            "body": combo["schema"],
        },
    }


# ------------------------------------------------------------------ Search route (GET /definitions/2020-09-01/productTypes)

by_marketplace = {}
for combo in COMBOS:
    mid = combo["marketplace_id"]
    by_marketplace.setdefault(mid, []).append(combo)


def search_rules():
    rules = []
    for mid, group in by_marketplace.items():
        first = group[0]
        pts = [
            {
                "name": c["product_type"],
                "displayName": c["display_name"],
                "marketplaceIds": [mid],
            }
            for c in group
        ]
        rules.append({
            "name": "%s -- search on %s (%s)" % (GENERATED_TAG, first["region"], mid),
            "when": {"query.marketplaceIds": {"contains": mid}},
            "respond": {
                "status": 200,
                "body": {
                    "productTypes": pts,
                    "productTypeVersion": first["version"],
                },
            },
        })
    return rules


def build_search_route():
    all_pts = [
        {
            "name": c["product_type"],
            "displayName": c["display_name"],
            "marketplaceIds": [c["marketplace_id"]],
        }
        for c in COMBOS
    ]
    return {
        "path": "/definitions/2020-09-01/productTypes",
        "method": "GET",
        "_comment": "Search and list available Amazon Product Types per marketplace.",
        "rules": search_rules(),
        "name": "no marker -- 200 list of product types",
        "respond": {
            "status": 200,
            "body": {
                "productTypes": all_pts,
                "productTypeVersion": "UHqSqmb4FNUk=",
            },
        },
    }


def update_mock_json():
    with open(MOCK_JSON, encoding="utf-8") as f:
        config = json.load(f)

    # 1. GET /definitions/2020-09-01/productTypes -- search route
    search_path = "/definitions/2020-09-01/productTypes"
    config["routes"] = [r for r in config["routes"] if r.get("path") != search_path]
    config["routes"].append(build_search_route())

    # 2. GET /definitions/2020-09-01/productTypes/{productType} -- definition envelopes
    def_path = "/definitions/2020-09-01/productTypes/{productType}"
    def_route = next((r for r in config["routes"] if r.get("path") == def_path), None)
    if not def_route:
        def_route = {"path": def_path, "method": "GET", "rules": []}
        config["routes"].append(def_route)

    existing_rules = [r for r in def_route.get("rules", []) if not r.get("name", "").startswith(GENERATED_TAG)]
    existing_rules.extend([definition_rule(c) for c in COMBOS])
    def_route["rules"] = existing_rules

    # 3. GET /s3/ptd-schema/{productType} -- schema serving
    schema_path = "/s3/ptd-schema/{productType}"
    schema_route = next((r for r in config["routes"] if r.get("path") == schema_path), None)
    if not schema_route:
        schema_route = {"path": schema_path, "method": "GET", "rules": []}
        config["routes"].append(schema_route)

    existing_schema_rules = [r for r in schema_route.get("rules", []) if not r.get("name", "").startswith(GENERATED_TAG)]
    existing_schema_rules.extend([schema_rule(c) for c in COMBOS])
    schema_route["rules"] = existing_schema_rules

    with open(MOCK_JSON, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

    print("Updated %s with %d product type definition fixtures across %d marketplaces." % (
        MOCK_JSON, len(COMBOS), len(by_marketplace)))


if __name__ == "__main__":
    update_mock_json()
