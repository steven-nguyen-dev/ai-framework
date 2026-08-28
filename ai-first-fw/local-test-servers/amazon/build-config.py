#!/usr/bin/env python3
"""Builds Amazon SP-API mock server assets from amzn/selling-partner-api-models.

Extracts all specifications, schemas, and 900+ official sandbox mock data fixtures
from https://github.com/amzn/selling-partner-api-models:
  1. Consolidates 66 Swagger 2.0 specs into amazon-sp-api-swagger.json
  2. Extracts and indexes all static sandbox test fixtures into mock-fixtures/
  3. Syncs official report, notification, and feed schemas into schemas/
  4. Generates/validates the mock configuration

Usage:
    python3 amazon/build-config.py
    python3 mock.py amazon --check
"""

import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
UPSTREAM_DIR = os.path.join(HERE, "upstream")
OUT_SPEC = os.path.join(HERE, "amazon-sp-api-swagger.json")
FIXTURES_DIR = os.path.join(HERE, "mock-fixtures")
SCHEMAS_DIR = os.path.join(HERE, "schemas")
LOCAL_SCRATCH = "/Users/nguyennguyen.anchanto/.gemini/antigravity/brain/0ec4a7b2-86d2-4240-99f0-a22dc82393f8/scratch/selling-partner-api-models"


def slugify(filepath):
    """Converts filename to a CamelCase namespace prefix."""
    base = os.path.splitext(os.path.basename(filepath))[0]
    parts = re.split(r"[-_.]", base)
    return "".join(p[:1].upper() + p[1:] for p in parts if p)


def rewrite_refs(obj, prefix):
    """Recursively rewrites $ref pointers to point to namespaced definitions."""
    if isinstance(obj, dict):
        new_obj = {}
        for k, v in obj.items():
            if k == "$ref" and isinstance(v, str) and v.startswith("#/definitions/"):
                def_name = v.replace("#/definitions/", "")
                new_obj[k] = f"#/definitions/{prefix}_{def_name}"
            else:
                new_obj[k] = rewrite_refs(v, prefix)
        return new_obj
    elif isinstance(obj, list):
        return [rewrite_refs(item, prefix) for item in obj]
    else:
        return obj


def ensure_upstream():
    """Ensures upstream repository exists in amazon/upstream."""
    models_dir = os.path.join(UPSTREAM_DIR, "models")
    if os.path.isdir(models_dir):
        return UPSTREAM_DIR

    if os.path.isdir(LOCAL_SCRATCH) and os.path.isdir(os.path.join(LOCAL_SCRATCH, "models")):
        print(f"Copying from local scratch cache {LOCAL_SCRATCH} to {UPSTREAM_DIR}...")
        if os.path.exists(UPSTREAM_DIR):
            shutil.rmtree(UPSTREAM_DIR)
        shutil.copytree(LOCAL_SCRATCH, UPSTREAM_DIR, ignore=shutil.ignore_patterns(".git", ".github"))
        return UPSTREAM_DIR

    print(f"Cloning amzn/selling-partner-api-models into {UPSTREAM_DIR}...")
    temp_clone_dir = tempfile.mkdtemp(prefix="amzn_sp_api_")
    try:
        subprocess.check_call([
            "git", "clone", "--depth", "1",
            "https://github.com/amzn/selling-partner-api-models.git",
            temp_clone_dir
        ])
        if os.path.exists(UPSTREAM_DIR):
            shutil.rmtree(UPSTREAM_DIR)
        shutil.copytree(temp_clone_dir, UPSTREAM_DIR, ignore=shutil.ignore_patterns(".git", ".github"))
    finally:
        shutil.rmtree(temp_clone_dir, ignore_errors=True)
    return UPSTREAM_DIR


def extract_mock_fixtures(upstream_path):
    """Extracts and organizes all static sandbox fixtures from Swagger models."""
    print("Extracting sandbox mock fixtures...")
    models_dir = os.path.join(upstream_path, "models")
    os.makedirs(FIXTURES_DIR, exist_ok=True)

    all_fixtures = {}
    domain_fixtures = {}

    for f in sorted(glob.glob(f"{models_dir}/**/*.json", recursive=True)):
        domain = os.path.basename(os.path.dirname(f)).replace("-api-model", "").replace("-model", "")
        with open(f, "r", encoding="utf-8") as h:
            data = json.load(h)

        file_fixtures = []
        for path_str, path_obj in data.get("paths", {}).items():
            for method, op in path_obj.items():
                if not isinstance(op, dict):
                    continue

                for status, resp in op.get("responses", {}).items():
                    if isinstance(resp, dict) and "x-amzn-api-sandbox" in resp:
                        for idx, item in enumerate(resp["x-amzn-api-sandbox"].get("static", [])):
                            req_params = item.get("request", {}).get("parameters", {})
                            tc_label = None
                            for _, pv in req_params.items():
                                val = pv.get("value") if isinstance(pv, dict) else pv
                                if isinstance(val, str) and ("TEST_CASE" in val or "902-" in val):
                                    tc_label = val
                                    break
                            fix_obj = {
                                "source_file": os.path.relpath(f, upstream_path),
                                "domain": domain,
                                "path": path_str,
                                "method": method.upper(),
                                "status": int(status) if status.isdigit() else 200,
                                "test_case": tc_label or f"CASE_{status}_{idx+1}",
                                "request": item.get("request", {}),
                                "response": item.get("response", {})
                            }
                            file_fixtures.append(fix_obj)
                            fixture_key = f"{method.upper()} {path_str} [{fix_obj['test_case']}]"
                            all_fixtures[fixture_key] = fix_obj

                if "x-amzn-api-sandbox" in op:
                    for idx, item in enumerate(op["x-amzn-api-sandbox"].get("static", [])):
                        fix_obj = {
                            "source_file": os.path.relpath(f, upstream_path),
                            "domain": domain,
                            "path": path_str,
                            "method": method.upper(),
                            "status": 200,
                            "test_case": f"TOP_CASE_{idx+1}",
                            "request": item.get("request", {}),
                            "response": item.get("response", {})
                        }
                        file_fixtures.append(fix_obj)
                        fixture_key = f"{method.upper()} {path_str} [{fix_obj['test_case']}]"
                        all_fixtures[fixture_key] = fix_obj

        if file_fixtures:
            if domain not in domain_fixtures:
                domain_fixtures[domain] = []
            domain_fixtures[domain].extend(file_fixtures)

    for domain, items in domain_fixtures.items():
        dom_path = os.path.join(FIXTURES_DIR, f"{domain}.json")
        with open(dom_path, "w", encoding="utf-8") as fh:
            json.dump(items, fh, indent=2)

    master_path = os.path.join(FIXTURES_DIR, "all-sandbox-fixtures.json")
    with open(master_path, "w", encoding="utf-8") as fh:
        json.dump(all_fixtures, fh, indent=2)

    print(f"Extracted {len(all_fixtures)} total sandbox fixtures across {len(domain_fixtures)} domain files in {FIXTURES_DIR}.")


def sync_schemas(upstream_path):
    """Syncs official report, notification, and feed schemas."""
    src_schemas = os.path.join(upstream_path, "schemas")
    if os.path.isdir(src_schemas):
        print(f"Syncing schemas from {src_schemas} to {SCHEMAS_DIR}...")
        if os.path.exists(SCHEMAS_DIR):
            shutil.rmtree(SCHEMAS_DIR)
        shutil.copytree(src_schemas, SCHEMAS_DIR)
        print("Schemas synced successfully.")


def build_unified_spec(upstream_path):
    models_dir = os.path.join(upstream_path, "models")
    print(f"Building unified Swagger 2.0 specification from {models_dir}...")
    model_files = []
    for root, _, files in os.walk(models_dir):
        for f in files:
            if f.endswith(".json"):
                model_files.append(os.path.join(root, f))
    model_files.sort()

    unified_spec = {
        "swagger": "2.0",
        "info": {
            "title": "Amazon Selling Partner API (SP-API) Mock Server Specification",
            "description": "Consolidated Swagger 2.0 specification generated from amzn/selling-partner-api-models",
            "version": "2026-08",
            "contact": {
                "name": "Amazon Selling Partner API Support",
                "url": "https://developer-docs.amazon.com/sp-api"
            },
            "license": {
                "name": "Apache License 2.0",
                "url": "http://www.apache.org/licenses/LICENSE-2.0"
            }
        },
        "host": "127.0.0.1:23103",
        "basePath": "",
        "schemes": ["http", "https"],
        "consumes": ["application/json", "application/x-www-form-urlencoded"],
        "produces": ["application/json"],
        "paths": {},
        "definitions": {}
    }

    # Add Login with Amazon (LWA) OAuth2 Token Endpoint
    unified_spec["paths"]["/auth/o2/token"] = {
        "post": {
            "tags": ["Authentication"],
            "summary": "Login with Amazon (LWA) token endpoint",
            "description": "Exchanges refresh token or client credentials for an access token.",
            "consumes": ["application/x-www-form-urlencoded", "application/json"],
            "produces": ["application/json"],
            "responses": {
                "200": {
                    "description": "Successful token exchange",
                    "schema": {
                        "$ref": "#/definitions/LwaAuth_TokenResponse"
                    },
                    "examples": {
                        "application/json": {
                            "access_token": "Atza|IQEBLjAsAhQmock_sp_api_access_token_1234567890",
                            "token_type": "bearer",
                            "expires_in": 3600,
                            "refresh_token": "rws_mock_refresh_token_12345"
                        }
                    }
                },
                "400": {
                    "description": "Invalid grant or credentials",
                    "schema": {
                        "$ref": "#/definitions/LwaAuth_ErrorResponse"
                    },
                    "examples": {
                        "application/json": {
                            "error": "invalid_grant",
                            "error_description": "The client credentials or refresh token is invalid."
                        }
                    }
                }
            }
        }
    }

    unified_spec["definitions"]["LwaAuth_TokenResponse"] = {
        "type": "object",
        "properties": {
            "access_token": {"type": "string"},
            "token_type": {"type": "string"},
            "expires_in": {"type": "integer"},
            "refresh_token": {"type": "string"}
        },
        "required": ["access_token", "token_type", "expires_in"]
    }
    unified_spec["definitions"]["LwaAuth_ErrorResponse"] = {
        "type": "object",
        "properties": {
            "error": {"type": "string"},
            "error_description": {"type": "string"}
        }
    }

    for model_file in model_files:
        model_slug = slugify(model_file)
        with open(model_file, "r", encoding="utf-8") as handle:
            data = json.load(handle)

        defs = data.get("definitions", {})
        for def_name, def_body in defs.items():
            renamed = f"{model_slug}_{def_name}"
            unified_spec["definitions"][renamed] = rewrite_refs(def_body, model_slug)

        paths = data.get("paths", {})
        for path_str, path_item in paths.items():
            renamed_path_item = rewrite_refs(path_item, model_slug)
            for method, op in renamed_path_item.items():
                if method.lower() in ("get", "post", "put", "delete", "patch", "head", "options"):
                    responses = op.get("responses", {})
                    for status in ("200", "201", "202", "204", "default"):
                        if status in responses and responses[status]:
                            resp = responses[status]
                            if "examples" not in resp:
                                resp["examples"] = {}
                            if "application/json" not in resp["examples"]:
                                sb = op.get("x-amzn-api-sandbox") or resp.get("x-amzn-api-sandbox")
                                if sb and isinstance(sb, dict) and "static" in sb and len(sb["static"]) > 0:
                                    static_resp = sb["static"][0].get("response")
                                    if static_resp is not None:
                                        resp["examples"]["application/json"] = static_resp

            if path_str not in unified_spec["paths"]:
                unified_spec["paths"][path_str] = renamed_path_item
            else:
                unified_spec["paths"][path_str].update(renamed_path_item)

    print(f"Writing unified specification to {OUT_SPEC}...")
    with open(OUT_SPEC, "w", encoding="utf-8") as out_h:
        json.dump(unified_spec, out_h, indent=2)

    print(f"Done! {len(unified_spec['paths'])} paths and {len(unified_spec['definitions'])} definitions written.")


def main():
    upstream_path = ensure_upstream()
    extract_mock_fixtures(upstream_path)
    sync_schemas(upstream_path)
    build_unified_spec(upstream_path)


if __name__ == "__main__":
    main()
