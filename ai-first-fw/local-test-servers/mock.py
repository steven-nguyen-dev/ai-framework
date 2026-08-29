#!/usr/bin/env python3
"""Spec-driven mock HTTP server.

Point it at a Swagger/OpenAPI document and it will answer every operation in that document with
the example response the document declares. Point it additionally at a rules config and it will
answer chosen operations conditionally -- a marker in the request selects the status code and body,
and requests can be recorded into small JSON stores that later requests can branch on.

    python3 mock.py eton              # by integration folder, from anywhere
    python3 mock.py                   # lists the integrations that exist
    python3 mock.py eton --check      # print the route table and exit

An explicit path to a config file still works, for a config kept outside this folder.

Authentication is not simulated: tokens are never validated. An auth endpoint that a client must
call before it will talk to the server is declared as an ordinary route in the config.

See CONFIG.md for the config format, README.md for the CLI.
"""

import argparse
import collections
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer

try:
    from http.server import ThreadingHTTPServer as _Server
except ImportError:  # Python < 3.7
    _Server = HTTPServer

from urllib.parse import unquote, urlparse, parse_qs

HERE = os.path.dirname(os.path.abspath(__file__))
METHODS = ("get", "put", "post", "delete", "patch", "head", "options")

# Comparisons that exist to spot a marker inside an identifier ("EXISTS" in "EXISTS1003") default to
# case-insensitive; the config opts out per-operator with "case_sensitive": true.
_LOOSE_BY_DEFAULT = ("contains", "not_contains", "starts_with", "ends_with")

# Stores and the call log are read-modify-write against a file, and the server is threaded.
_FILE_LOCK = threading.RLock()


def write_json(path, data):
    """Writes via a temporary file and one rename.

    The server is normally killed rather than shut down, and a kill landing inside a plain write
    leaves truncated JSON that the next run cannot parse -- which, for an append-only log, means
    silently starting over and losing every call recorded so far. os.replace is atomic, so the file
    on disk is only ever the last complete write.
    """
    temporary = path + ".tmp"
    with open(temporary, "w") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


# --------------------------------------------------------------------------------------- selectors

_MISSING = object()


def select(selector, ctx):
    """Reads one value out of the request.

    Understood roots: body, validation, path, query, header, method, url, raw_body. Everything after
    the root is a dotted walk into the parsed JSON body ("body.InvoiceInfo.TaxCode"), where a numeric
    step indexes a list. A bare "body" yields the whole parsed body. Returns _MISSING when any step
    is absent, which every operator other than "exists" treats as no-match. A JSON null reads as
    missing, so "absent" and "sent as null" are one case.
    """
    root, _, rest = selector.partition(".")

    if root == "method":
        return ctx["method"]
    if root == "url":
        return ctx["path"]
    if root == "raw_body":
        return ctx["raw_body"]
    if root == "path":
        return ctx["path_params"].get(rest, _MISSING)
    if root == "query":
        values = ctx["query"].get(rest)
        return values[0] if values else _MISSING
    if root == "header":
        return ctx["headers"].get(rest.lower(), _MISSING)
    if root == "body":
        current = ctx["body"]
    elif root == "validation":
        current = ctx.get("validation")
    else:
        return _MISSING

    if not rest:
        return current if current is not None else _MISSING

    for step in rest.split("."):
        if isinstance(current, dict):
            if step not in current:
                return _MISSING
            current = current[step]
        elif isinstance(current, list) and step.lstrip("-").isdigit():
            index = int(step)
            if not -len(current) <= index < len(current):
                return _MISSING
            current = current[index]
        else:
            return _MISSING
    return current if current is not None else _MISSING


# -------------------------------------------------------------------------------------- validation

_ROOTS = ("body", "validation", "path", "query", "header", "method", "url", "raw_body")


def _normalize(path):
    return path if path.split(".")[0].split("[")[0] in _ROOTS else "body." + path


def _label(path):
    """Reports the field the way the config wrote it -- ListSODetail[1].SKU, not ListSODetail.1.SKU."""
    return re.sub(r"\.(\d+)(?=\.|$)", r"[\1]", path[5:] if path.startswith("body.") else path)


def expand(path, ctx):
    """Turns one path into the concrete paths it names.

    "ListSODetail[*].SKU" becomes one path per element, so a rule written once reports
    "ListSODetail[2].SKU is required" against the element that actually broke it. An absent or
    non-list collection expands to nothing -- the collection's own requirement reports that.

    A path may carry more than one [*]: DPD nests its customs lines as
    "consignment[*].parcel[*].productHarmonisedCode", and each wildcard is expanded against the
    list the wildcards before it selected. Expanding only the first left the rest of the path
    literal, and a literal "[*]" step matches nothing -- so every element reported as missing.
    """
    path = _normalize(path)
    if "[*]" not in path:
        return [path]
    head, _, tail = path.partition("[*]")
    items = select(head, ctx)
    if items is _MISSING or not isinstance(items, list):
        return []
    concrete = ["%s.%d%s" % (head, index, tail) for index in range(len(items))]
    if "[*]" not in tail:
        return concrete
    return [nested for one in concrete for nested in expand(one, ctx)]


def validate(spec_obj, ctx, state):
    """Collects every violation of a rule's `validate` block, in the order declared.

    Exists because a Swagger document states only part of what an API will actually reject: the
    conditional obligations ("required if scheme is ADM4") live in prose no generator reads. This is
    where a config writes them down so the mock refuses the same calls the partner would.
    """
    errors = []

    for path in spec_obj.get("required", []):
        for concrete in expand(path, ctx):
            if select(concrete, ctx) is _MISSING:
                errors.append("'%s' is required" % _label(concrete))

    for clause in spec_obj.get("required_when", []):
        if not evaluate(clause.get("when"), ctx, state):
            continue
        for path in clause.get("fields", []):
            for concrete in expand(path, ctx):
                if select(concrete, ctx) is _MISSING:
                    because = clause.get("because")
                    errors.append("'%s' is required%s"
                                  % (_label(concrete), " -- " + because if because else ""))

    for path in spec_obj.get("non_empty", []):
        for concrete in expand(path, ctx):
            value = select(concrete, ctx)
            if value is not _MISSING and len(value) == 0:
                errors.append("'%s' must not be empty" % _label(concrete))

    for path, limit in (spec_obj.get("max_length") or {}).items():
        for concrete in expand(path, ctx):
            value = select(concrete, ctx)
            if value is not _MISSING and len(str(value)) > limit:
                errors.append("'%s' exceeds maxLength %d" % (_label(concrete), limit))

    return errors


# -------------------------------------------------------------------------------------- conditions

def _as_text(value):
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _test_operator(op, expected, actual, spec_obj, state):
    if op == "exists":
        return (actual is not _MISSING) == bool(expected)
    if actual is _MISSING:
        return False

    loose = not spec_obj.get("case_sensitive", op not in _LOOSE_BY_DEFAULT)
    text = _as_text(actual)
    needle = _as_text(expected) if not isinstance(expected, list) else None
    if loose:
        text_cmp = text.lower()
        needle_cmp = needle.lower() if needle is not None else None
    else:
        text_cmp, needle_cmp = text, needle

    if op == "equals":
        return actual == expected if type(actual) is type(expected) else text_cmp == needle_cmp
    if op == "not_equals":
        return not (actual == expected if type(actual) is type(expected) else text_cmp == needle_cmp)
    if op == "contains":
        return needle_cmp in text_cmp
    if op == "not_contains":
        return needle_cmp not in text_cmp
    if op == "starts_with":
        return text_cmp.startswith(needle_cmp)
    if op == "ends_with":
        return text_cmp.endswith(needle_cmp)
    if op == "matches":
        flags = 0 if spec_obj.get("case_sensitive") else re.IGNORECASE
        return re.search(str(expected), text, flags) is not None
    if op == "one_of":
        candidates = [_as_text(v) for v in expected]
        return text_cmp in ([c.lower() for c in candidates] if loose else candidates)
    if op == "in_store":
        return state.contains(str(expected), text)
    if op == "not_in_store":
        return not state.contains(str(expected), text)

    raise ValueError("unknown operator: %s" % op)


def evaluate(condition, ctx, state):
    """A condition object. Sibling keys are ANDed; all/any/not combine nested conditions.

    A key that is not a combinator is a selector, and its value is either an operator object
    ({"contains": "X"}) or a bare value, which is shorthand for {"equals": <value>}.
    """
    if condition is None:
        return True
    if isinstance(condition, bool):
        return condition
    if not isinstance(condition, dict):
        raise ValueError("condition must be an object, got %r" % (condition,))

    for key, value in condition.items():
        if key == "_comment":
            continue
        if key in ("all", "and"):
            if not all(evaluate(c, ctx, state) for c in value):
                return False
        elif key in ("any", "or"):
            if not any(evaluate(c, ctx, state) for c in value):
                return False
        elif key == "not":
            if evaluate(value, ctx, state):
                return False
        else:
            actual = select(key, ctx)
            if not isinstance(value, dict):
                value = {"equals": value}
            for op, expected in value.items():
                if op in ("case_sensitive", "_comment"):
                    continue
                if not _test_operator(op, expected, actual, value, state):
                    return False
    return True


# --------------------------------------------------------------------------------------- templates

_TEMPLATE = re.compile(r"\$\{([^}]+)\}")


def render(value, ctx):
    """Substitutes ${selector} in strings, recursing through dicts and lists.

    A string that is exactly one placeholder is replaced by the selected value with its type intact,
    so ${body.Qty} stays a number. Anywhere else the value is interpolated as text. A trailing
    |fallback supplies the value to use when the selector is missing; without one, a missing
    selector renders as null (whole-string) or an empty string (interpolated).
    """
    if isinstance(value, dict):
        return {k: render(v, ctx) for k, v in value.items() if k != "_comment"}
    if isinstance(value, list):
        return [render(v, ctx) for v in value]
    if not isinstance(value, str):
        return value

    def resolve(expression):
        selector, sep, fallback = expression.partition("|")
        found = select(selector.strip(), ctx)
        if found is _MISSING:
            return fallback if sep else _MISSING
        return found

    whole = _TEMPLATE.fullmatch(value)
    if whole:
        resolved = resolve(whole.group(1))
        return None if resolved is _MISSING else resolved

    def replace(match):
        resolved = resolve(match.group(1))
        return "" if resolved is _MISSING else _as_text(resolved)

    return _TEMPLATE.sub(replace, value)


# ------------------------------------------------------------------------------------------- state

class State:
    """The named JSON stores a config can record into and branch on.

    Each store is one file on disk, re-read per access so it can be inspected or reset mid-run, and
    so a test can assert against it afterwards. A "set" store holds distinct strings; a "list" store
    appends every entry in order.
    """

    def __init__(self, stores, base_dir):
        self.definitions = stores or {}
        self.base_dir = base_dir

    def _path(self, name):
        definition = self.definitions.get(name)
        if definition is None:
            raise KeyError("undeclared store: %s" % name)
        return os.path.join(self.base_dir, definition.get("file", name + ".json"))

    def _load(self, name):
        path = self._path(name)
        if os.path.exists(path):
            try:
                with open(path, "r") as handle:
                    return json.load(handle)
            except Exception:
                pass
        return []

    def _save(self, name, data):
        try:
            write_json(self._path(name), data)
        except Exception as error:
            print("  ! could not write store %s: %s" % (name, error), flush=True)

    def contains(self, name, value):
        return str(value) in {str(v) for v in self._load(name)}

    def record(self, name, values):
        with _FILE_LOCK:
            existing = self._load(name)
            known = {str(v) for v in existing}
            for value in values:
                if value is None or value == "":
                    continue
                if str(value) not in known:
                    existing.append(str(value))
                    known.add(str(value))
            self._save(name, existing)

    def append(self, name, entry):
        with _FILE_LOCK:
            existing = self._load(name)
            existing.append(entry)
            self._save(name, existing)

    def reset(self, name):
        with _FILE_LOCK:
            self._save(name, [])


def run_actions(actions, ctx, state):
    for action in actions or []:
        if "record" in action:
            spec_obj = action["record"]
            values = spec_obj.get("values", [spec_obj.get("value")])
            state.record(spec_obj["store"], [render(v, ctx) for v in values])
        elif "append" in action:
            spec_obj = action["append"]
            state.append(spec_obj["store"], render(spec_obj.get("entry"), ctx))
        elif "log" in action:
            print("  · %s" % render(action["log"], ctx), flush=True)


# ----------------------------------------------------------------------------------------- api log

_REDACTED = "***redacted***"

# Redacted by default so the log stays safe to hand to someone else. Auth is not simulated, so
# nothing here is needed to replay a call against the mock.
_DEFAULT_REDACT = ("authorization", "proxy-authorization", "cookie", "set-cookie",
                   "x-api-key", "api-key", "x-eton-hmac-sha256")

# Headers curl sets by itself; repeating them in the generated command is noise.
_CURL_SKIP = ("host", "content-length", "user-agent", "accept", "accept-encoding", "connection")


def _shell_quote(value):
    return "'" + str(value).replace("'", "'\\''") + "'"


def build_curl(method, url, headers, body):
    parts = ["curl", "-i", "-X", method, _shell_quote(url)]
    for name, value in headers.items():
        if name.lower() in _CURL_SKIP:
            continue
        parts += ["-H", _shell_quote("%s: %s" % (name, value))]
    if body:
        parts += ["--data-raw", _shell_quote(body)]
    return " ".join(parts)


class ApiLog:
    """Appends every call to one file, in a shape other people can replay.

    "har" writes a HAR 1.2 archive -- the interchange format Chrome DevTools, Postman, Insomnia and
    the k6/Playwright converters all import -- carrying a ready-to-paste "_curl" on each entry.
    HAR's spec reserves underscore-prefixed names for custom fields, so the extras below travel
    with the archive without making it invalid.

    "simple" writes the same calls as a flat JSON array with parsed bodies, which is easier to
    assert against directly from a unit test.
    """

    def __init__(self, path, fmt="har", redact=None, creator="mock_server"):
        self.path = path
        self.format = fmt
        self.redact = {h.lower() for h in (redact if redact is not None else _DEFAULT_REDACT)}
        self.creator = creator
        self.count = 0

    def _headers_out(self, headers):
        return {k: (_REDACTED if k.lower() in self.redact else v) for k, v in headers.items()}

    def _empty(self):
        if self.format == "har":
            return {"log": {"version": "1.2",
                            "creator": {"name": self.creator, "version": "1.0"},
                            "entries": []}}
        return []

    def _read(self):
        """An unreadable log is moved aside rather than overwritten -- starting a fresh log on top
        of one that failed to parse would throw away every call already recorded in it."""
        if not os.path.exists(self.path):
            return self._empty()
        try:
            with open(self.path, "r") as handle:
                document = json.load(handle)
            if self.format == "har":
                document["log"]["entries"]
            elif not isinstance(document, list):
                raise ValueError("expected a JSON array")
            return document
        except Exception as error:
            salvage = self.path + ".corrupt"
            try:
                os.replace(self.path, salvage)
                print("  ! call log unreadable (%s); moved to %s, starting a new one"
                      % (error, salvage), flush=True)
            except Exception:
                pass
            return self._empty()

    def record(self, call):
        with _FILE_LOCK:
            document = self._read()
            entries = document["log"]["entries"] if self.format == "har" else document
            self.count = len(entries) + 1
            entries.append(self._har_entry(call) if self.format == "har"
                           else self._simple_entry(call))
            try:
                write_json(self.path, document)
            except Exception as error:
                print("  ! could not write call log: %s" % error, flush=True)

    def _common(self, call):
        headers = self._headers_out(call["request_headers"])
        curl = build_curl(call["method"], call["url"], headers, call["request_body_text"])
        status_text = call.get("status_text") or ""
        return headers, curl, status_text

    def _simple_entry(self, call):
        headers, curl, status_text = self._common(call)
        return {
            "seq": self.count,
            "at": call["started"],
            "durationMs": call["duration_ms"],
            "rule": call.get("rule"),
            "curl": curl,
            "request": {
                "method": call["method"],
                "url": call["url"],
                "path": call["path"],
                "query": call["query"],
                "headers": headers,
                "body": call["request_body_json"],
                "bodyText": call["request_body_text"] or None,
            },
            "response": {
                "status": call["status"],
                "statusText": status_text,
                "headers": call["response_headers"],
                "body": call["response_body_json"],
                "bodyText": call["response_body_text"] or None,
            },
        }

    def _har_entry(self, call):
        headers, curl, status_text = self._common(call)
        request_text = call["request_body_text"] or ""
        response_text = call["response_body_text"] or ""

        post_data = {}
        if request_text:
            post_data = {"mimeType": call["request_headers"].get("Content-Type", "application/json"),
                         "text": request_text,
                         "_json": call["request_body_json"]}

        return {
            "startedDateTime": call["started"],
            "time": call["duration_ms"],
            "_seq": self.count,
            "_rule": call.get("rule"),
            "_curl": curl,
            "request": {
                "method": call["method"],
                "url": call["url"],
                "httpVersion": "HTTP/1.1",
                "cookies": [],
                "headers": [{"name": k, "value": v} for k, v in headers.items()],
                "queryString": [{"name": k, "value": v}
                                for k, values in call["query"].items() for v in values],
                "postData": post_data,
                "headersSize": -1,
                "bodySize": len(request_text.encode("utf-8")),
            },
            "response": {
                "status": call["status"],
                "statusText": status_text,
                "httpVersion": "HTTP/1.1",
                "cookies": [],
                "headers": [{"name": k, "value": v} for k, v in call["response_headers"].items()],
                "content": {
                    "size": len(response_text.encode("utf-8")),
                    "mimeType": call["response_headers"].get("Content-Type", "application/json"),
                    "text": response_text,
                    "_json": call["response_body_json"],
                },
                "redirectURL": "",
                "headersSize": -1,
                "bodySize": len(response_text.encode("utf-8")),
            },
            "cache": {},
            "timings": {"send": 0, "wait": call["duration_ms"], "receive": 0},
        }


# -------------------------------------------------------------------------------- spec -> defaults

def _resolve_ref(ref, spec):
    node = spec
    for part in ref.lstrip("#/").split("/"):
        node = node.get(part, {})
        if not isinstance(node, dict):
            return {}
    return node


def synthesize(schema, spec, depth=0, seen=None):
    """Builds a plausible response body from a JSON schema, for operations the config says nothing
    about. Prefers whatever the document already spells out -- an example on the definition, then a
    default, then a zero value for the declared type."""
    if not isinstance(schema, dict) or depth > 6:
        return None
    seen = seen or set()

    ref = schema.get("$ref")
    if ref:
        if ref in seen:
            return None
        return synthesize(_resolve_ref(ref, spec), spec, depth + 1, seen | {ref})

    for key in ("example", "default"):
        if key in schema:
            return schema[key]

    schema_type = schema.get("type")
    if schema_type == "object" or "properties" in schema:
        return {name: synthesize(sub, spec, depth + 1, seen)
                for name, sub in (schema.get("properties") or {}).items()}
    if schema_type == "array":
        item = synthesize(schema.get("items", {}), spec, depth + 1, seen)
        return [item] if item is not None else []
    if schema_type in ("integer", "number"):
        return 0
    if schema_type == "boolean":
        return False
    if schema_type == "string":
        return ""
    return None


def _json_media(response):
    """The JSON example and schema a response declares, in either document version.

    Swagger 2.0 hangs them off the response itself -- examples keyed by content type, one schema.
    OpenAPI 3 moves both under content/<media type>, and renames "examples" to "example", keeping
    "examples" for a map of named {"value": ...} objects. Reading only the 2.0 shape answers every
    operation of a 3.x document with an empty body, which looks like a mock that is up and healthy.
    """
    content = response.get("content")
    if isinstance(content, dict):
        for media_type, media in content.items():
            if "json" not in media_type or not isinstance(media, dict):
                continue
            if "example" in media:
                return media["example"], media.get("schema")
            for named in (media.get("examples") or {}).values():
                if isinstance(named, dict) and "value" in named:
                    return named["value"], media.get("schema")
            return _MISSING, media.get("schema")

    for content_type, example in (response.get("examples") or {}).items():
        if "json" in content_type:
            return example, response.get("schema")
    return _MISSING, response.get("schema")


def spec_response(operation, spec):
    """The success response the document declares for one operation: its example if it has one,
    otherwise a body synthesized from the response schema."""
    responses = operation.get("responses") or {}
    for status in ("200", "201", "202", "204", "default"):
        if status not in responses:
            continue
        code = int(status) if status.isdigit() else 200
        example, schema = _json_media(responses[status] or {})
        if example is not _MISSING:
            return {"status": code, "body": example}
        return {"status": code, "body": synthesize(schema, spec) if schema else {}}
    return {"status": 200, "body": {}}


# --------------------------------------------------------------------------------------- log view

def read_log(path, fmt):
    """Flattens either log format into the one shape the viewer renders."""
    if not path or not os.path.exists(path):
        return []
    try:
        with open(path, "r") as handle:
            document = json.load(handle)
    except Exception:
        return []

    if fmt != "har":
        return document if isinstance(document, list) else []

    out = []
    for entry in document.get("log", {}).get("entries", []):
        request, response = entry.get("request", {}), entry.get("response", {})
        post = request.get("postData") or {}
        content = response.get("content") or {}
        out.append({
            "seq": entry.get("_seq"),
            "at": entry.get("startedDateTime"),
            "durationMs": entry.get("time"),
            "rule": entry.get("_rule"),
            "curl": entry.get("_curl"),
            "request": {
                "method": request.get("method"),
                "url": request.get("url"),
                "headers": {h["name"]: h["value"] for h in request.get("headers", [])},
                "body": post.get("_json"),
                "bodyText": post.get("text"),
            },
            "response": {
                "status": response.get("status"),
                "statusText": response.get("statusText"),
                "headers": {h["name"]: h["value"] for h in response.get("headers", [])},
                "body": content.get("_json"),
                "bodyText": content.get("text"),
            },
        })
    return out


# Tokens and the primitives both pages are built from. One block, included by each template, so
# /log and /test cannot drift apart -- they were already duplicating a palette and had begun to.
#
# Tinted surface + dark text everywhere a status is shown, rather than white on a saturated fill:
# every pair below clears WCAG AA at 4.5:1, which the old #49cc90 and #f93e3e badges did not.
# ------------------------------------------------------------------------------------------- theme
#
# Every colour, radius and shadow the two pages use, as one token map. Nothing below this point
# names a colour: the stylesheets read `var(--token)` and the tokens come from here, so retheming
# is a data change and the two pages cannot drift apart while it happens.
#
# The defaults are the fallback, not the source of truth -- `theme.json` next to this script wins
# over them, and a `"theme"` block in an individual `<name>.mock.json` wins over that, so one mock
# can be recoloured without touching the others.
#
# Why these values: Swagger UI's own defaults are the ceiling, measured rather than eyeballed. Its
# neutral border #d9dde3 sits 0.280 in luminance below a card and its loudest method fill runs 0.99
# saturation; these stay under both, at 0.234 and 0.82. Badge legibility runs 5.2:1 and up against
# Swagger's own 2.03:1 for white-on-green, because the depth comes from deeper tints and stronger
# rules rather than from saturation. Surfaces step apart by ~0.1 luminance each, and `--muted` is
# dark enough to clear WCAG AA on the darkest of them, so one token stays safe everywhere.
THEME_DEFAULT = collections.OrderedDict([
    ("canvas", "#020617"), ("panel", "#0b0f19"), ("surface", "#0f172a"), ("surface-2", "#1e293b"),
    ("ink", "#f8fafc"), ("ink-2", "#cbd5e1"), ("muted", "#94a3b8"),
    ("line", "#1e293b"), ("line-2", "#334155"),
    ("pass-bg", "rgba(16, 185, 129, 0.15)"), ("pass-fg", "#34d399"),
    ("fail-bg", "rgba(239, 68, 68, 0.15)"), ("fail-fg", "#f87171"),
    ("run-bg", "rgba(59, 130, 246, 0.15)"), ("run-fg", "#60a5fa"),
    ("warn-bg", "rgba(245, 158, 11, 0.15)"), ("warn-fg", "#fbbf24"),
    ("mute-bg", "rgba(51, 65, 85, 0.4)"), ("mute-fg", "#cbd5e1"),
    ("teal-bg", "rgba(20, 184, 166, 0.15)"), ("teal-fg", "#2dd4bf"),
    ("violet-bg", "rgba(168, 85, 247, 0.15)"), ("violet-fg", "#c084fc"),
    ("slate-bg", "rgba(51, 65, 85, 0.4)"), ("slate-fg", "#cbd5e1"),
    ("code-bg", "#020617"), ("hover", "#1e293b"), ("selected", "#334155"),
    ("pass-bg-2", "rgba(16, 185, 129, 0.25)"), ("fail-bg-2", "rgba(239, 68, 68, 0.25)"),
    ("header-mute", "#94a3b8"), ("dot", "#34d399"), ("dim", "#64748b"),
    ("radius", "8px"),
    ("shadow", "0 1px 3px rgba(0, 0, 0, 0.4), 0 6px 20px -4px rgba(0, 0, 0, 0.6)"),
])


def load_theme(config, config_dir):
    """Defaults, then `theme.json` beside this script, then the config's own `theme` block.

    Later wins, and an unknown key is kept rather than dropped -- a page-specific token added to
    the file should reach the stylesheet without the engine needing to know about it first.
    """
    theme = collections.OrderedDict(THEME_DEFAULT)
    candidate_paths = (
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "local-theme", "theme.json"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "theme.json"),
    )
    for path in candidate_paths:
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as handle:
                    loaded = json.load(handle)
                theme.update({k: v for k, v in loaded.items() if not k.startswith("_")})
                break
            except Exception as error:
                print("  ! theme.json unreadable (%s); using the built-in defaults" % error, flush=True)
    theme.update({k: v for k, v in (config.get("theme") or {}).items() if not k.startswith("_")})
    return theme


def theme_css(theme):
    return ":root{%s}" % "".join("--%s:%s;" % (k, v) for k, v in theme.items())


BASE_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;600;700&display=swap');
/*THEME*/
*{box-sizing:border-box}
body{margin:0;font:14px/1.6 'Inter',-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
color:var(--ink);background:var(--canvas)}
code,pre{font-family:'JetBrains Mono',"SF Mono",Menlo,Consolas,"Liberation Mono",monospace}
header{background:rgba(15,23,42,.92);backdrop-filter:blur(10px);border-bottom:1px solid var(--line-2);color:var(--ink);padding:14px 20px;display:flex;align-items:center;gap:12px;position:sticky;top:0;z-index:20}
header h1{margin:0;font-size:16px;font-weight:700;letter-spacing:0.02em}
header .host{color:var(--header-mute);font-size:11.5px;font-family:'JetBrains Mono',monospace}
header a{color:var(--header-mute);font-size:12px;margin-left:auto;text-decoration:none;font-family:'JetBrains Mono',monospace}
header a:hover{color:var(--ink)}
input[type=search],select{padding:7px 10px;border:1px solid var(--line-2);
border-radius:var(--radius);font-size:13px;background:var(--surface-2);color:var(--ink)}
.btn{display:inline-flex;align-items:center;justify-content:center;min-width:76px;padding:6px 12px;
border:1px solid var(--line-2);background:var(--surface);border-radius:var(--radius);cursor:pointer;
font-size:12px;font-family:'JetBrains Mono',monospace;font-weight:600;color:var(--ink-2);text-align:center;box-sizing:border-box;transition:all .12s}
.btn:hover{background:var(--hover);border-color:var(--run-fg);color:var(--ink)}
/* Sleek, dark bordered code surfaces */
pre{background:var(--code-bg);color:var(--ink);border:1px solid var(--line);padding:12px 14px;
border-radius:var(--radius);overflow:auto;margin:0 0 14px;font-size:12.5px;line-height:1.55}
.empty{padding:56px 20px;text-align:center;color:var(--muted)}
.empty code{background:var(--surface-2);padding:2px 6px;border-radius:4px}
"""


# Favicon: Paper with Text (for /log Call Log)
LOG_FAVICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect width="32" height="32" rx="7" fill="#1e293b"/><path d="M7 5H19L25 11V27H7V5Z" fill="#f8fafc"/><path d="M19 5V11H25" fill="#cbd5e1"/><rect x="9.5" y="13" width="7" height="2.2" rx="1" fill="#38bdf8"/><rect x="18" y="13" width="4.5" height="2.2" rx="1" fill="#4ade80"/><line x1="9.5" y1="18.5" x2="22.5" y2="18.5" stroke="#475569" stroke-width="2" stroke-linecap="round"/><line x1="9.5" y1="22.5" x2="19.5" y2="22.5" stroke="#64748b" stroke-width="2" stroke-linecap="round"/></svg>"""

LOG_FAVICON_DATA_URI = "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAzMiAzMiI+PHJlY3Qgd2lkdGg9IjMyIiBoZWlnaHQ9IjMyIiByeD0iNyIgZmlsbD0iIzFlMjkzYiIvPjxwYXRoIGQ9Ik03IDVIMTlMMjUgMTFWMjdIN1Y1WiIgZmlsbD0iI2Y4ZmFmYyIvPjxwYXRoIGQ9Ik0xOSA1VjExSDI1IiBmaWxsPSIjY2JkNWUxIi8+PHJlY3QgeD0iOS41IiB5PSIxMyIgd2lkdGg9IjciIGhlaWdodD0iMi4yIiByeD0iMSIgZmlsbD0iIzM4YmRmOCIvPjxyZWN0IHg9IjE4IiB5PSIxMyIgd2lkdGg9IjQuNSIgaGVpZ2h0PSIyLjIiIHJ4PSIxIiBmaWxsPSIjNGFkZTgwIi8+PGxpbmUgeDE9IjkuNSIgeTE9IjE4LjUiIHgyPSIyMi41IiB5Mj0iMTguNSIgc3Ryb2tlPSIjNDc1NTY5IiBzdHJva2Utd2lkdGg9IjIiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIvPjxsaW5lIHgxPSI5LjUiIHkxPSIyMi41IiB4Mj0iMTkuNSIgeTI9IjIyLjUiIHN0cm9rZT0iIzY0NzQ4YiIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiLz48L3N2Zz4="

# Favicon: Radar Screen (for Test Server)
TEST_FAVICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect width="32" height="32" rx="7" fill="#1e293b"/><circle cx="16" cy="16" r="11" fill="#0f172a" stroke="#4ade80" stroke-width="1.8"/><circle cx="16" cy="16" r="6" fill="none" stroke="#22c55e" stroke-width="1" stroke-opacity="0.5"/><line x1="16" y1="5" x2="16" y2="27" stroke="#22c55e" stroke-width="1" stroke-opacity="0.5"/><line x1="5" y1="16" x2="27" y2="16" stroke="#22c55e" stroke-width="1" stroke-opacity="0.5"/><line x1="16" y1="16" x2="24" y2="8" stroke="#4ade80" stroke-width="1.8" stroke-linecap="round"/><circle cx="21" cy="11" r="1.5" fill="#4ade80"/><circle cx="11" cy="20" r="1.2" fill="#38bdf8"/></svg>"""

TEST_FAVICON_DATA_URI = "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAzMiAzMiI+PHJlY3Qgd2lkdGg9IjMyIiBoZWlnaHQ9IjMyIiByeD0iNyIgZmlsbD0iIzFlMjkzYiIvPjxjaXJjbGUgY3g9IjE2IiBjeT0iMTYiIHI9IjExIiBmaWxsPSIjMGYxNzJhIiBzdHJva2U9IiM0YWRlODAiIHN0cm9rZS13aWR0aD0iMS44Ii8+PGNpcmNsZSBjeD0iMTYiIGN5PSIxNiIgcj0iNiIgZmlsbD0ibm9uZSIgc3Ryb2tlPSIjMjJjNTVlIiBzdHJva2Utd2lkdGg9IjEiIHN0cm9rZS1vcGFjaXR5PSIwLjUiLz48bGluZSB4MT0iMTYiIHkxPSI1IiB4Mj0iMTYiIHkyPSIyNyIgc3Ryb2tlPSIjMjJjNTVlIiBzdHJva2Utd2lkdGg9IjEiIHN0cm9rZS1vcGFjaXR5PSIwLjUiLz48bGluZSB4MT0iNSIgeTE9IjE2IiB4Mj0iMjciIHkyPSIxNiIgc3Ryb2tlPSIjMjJjNTVlIiBzdHJva2Utd2lkdGg9IjEiIHN0cm9rZS1vcGFjaXR5PSIwLjUiLz48bGluZSB4MT0iMTYiIHkxPSIxNiIgeDI9IjI0IiB5Mj0iOCIgc3Ryb2tlPSIjNGFkZTgwIiBzdHJva2Utd2lkdGg9IjEuOCIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIi8+PGNpcmNsZSBjeD0iMjEiIGN5PSIxMSIgcj0iMS41IiBmaWxsPSIjNGFkZTgwIi8+PGNpcmNsZSBjeD0iMTEiIGN5PSIyMCIgcj0iMS4yIiBmaWxsPSIjMzhiZGY4Ii8+PC9zdmc+"

LOG_UI_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Mock server log</title>
<link rel="icon" type="image/svg+xml" href=\"""" + LOG_FAVICON_DATA_URI + """\">
<link rel="shortcut icon" type="image/svg+xml" href=\"""" + LOG_FAVICON_DATA_URI + """\">
<style>
/*BASE_CSS*/
:root{--get-bg:var(--run-bg);--get-fg:var(--run-fg);
--post-bg:var(--pass-bg);--post-fg:var(--pass-fg);
--put-bg:var(--warn-bg);--put-fg:var(--warn-fg);
--delete-bg:var(--fail-bg);--delete-fg:var(--fail-fg);
--patch-bg:var(--teal-bg);--patch-fg:var(--teal-fg);
--head-bg:var(--violet-bg);--head-fg:var(--violet-fg);
--options-bg:var(--slate-bg);--options-fg:var(--slate-fg)}
.dot{display:inline-block;width:7px;height:7px;border-radius:50%;background:var(--dot)}
main{max-width:76rem;margin:0 auto;padding:1.6vh 1.1vw;min-width:0}
.bar{display:flex;gap:10px;align-items:center;margin-bottom:1.2vh;flex-wrap:wrap}
.bar input[type=search]{flex:1;min-width:180px}
.bar label{font-size:12px;color:var(--ink-2);display:flex;align-items:center;gap:5px;cursor:pointer}
.count{font-size:12px;color:var(--muted)}
.op{border:1px solid var(--line);border-radius:var(--radius);margin-bottom:7px;overflow:hidden;
background:var(--surface);box-shadow:var(--shadow)}
.op>summary{display:flex;align-items:center;gap:11px;padding:7px 10px;cursor:pointer;
list-style:none;user-select:none}
.op[open]>summary{background:var(--surface-2)}
.op>summary::-webkit-details-marker{display:none}
.verb{flex:none;width:76px;text-align:center;padding:4px 0;border-radius:999px;
font-size:11px;font-weight:600;letter-spacing:.03em}
.u{flex:1;font-family:"SF Mono",Menlo,monospace;font-size:13px;word-break:break-all}
.st{flex:none;font-size:12px;font-weight:600;font-family:"SF Mono",Menlo,monospace}
.st.s2{color:var(--pass-fg)}.st.s4{color:var(--warn-fg)}.st.s5{color:var(--fail-fg)}
.when{flex:none;font-size:11px;color:var(--muted);font-variant-numeric:tabular-nums}
.body{border-top:1px solid var(--line);padding:13px 15px}
.rule{font-size:12px;color:var(--ink-2);margin:0 0 13px;padding:7px 10px;
background:var(--surface-2);border-radius:6px}
h3{font-size:12px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);
margin:0 0 7px;display:flex;align-items:center;gap:9px;font-weight:600}
pre{max-height:30vh}
pre.curl{white-space:pre-wrap;word-break:break-all}
/* A response body is the thing you actually came to read, so it gets half the window. */
pre.resp{max-height:50vh;resize:vertical}
table.h{border-collapse:collapse;margin:0 0 14px;font-size:12.5px}
table.h td{padding:3px 0;border:0;vertical-align:top}
table.h td:first-child{color:var(--muted);padding-right:16px;white-space:nowrap}
.copy{display:inline-block;width:60px;min-width:60px;text-align:center;padding:2px 0;
border:1px solid var(--line-2);background:var(--surface);font-size:11px;border-radius:999px;
cursor:pointer;color:var(--ink-2);box-sizing:border-box}
.copy:hover{background:var(--surface-2)}
</style></head><body>
<header><svg style="vertical-align:-3px;margin-right:8px;flex:none" width="18" height="18" viewBox="0 0 32 32"><rect width="32" height="32" rx="7" fill="#1e293b"/><path d="M7 5H19L25 11V27H7V5Z" fill="#f8fafc"/><path d="M19 5V11H25" fill="#cbd5e1"/><rect x="9.5" y="13" width="7" height="2.2" rx="1" fill="#38bdf8"/><rect x="18" y="13" width="4.5" height="2.2" rx="1" fill="#4ade80"/><line x1="9.5" y1="18.5" x2="22.5" y2="18.5" stroke="#475569" stroke-width="2" stroke-linecap="round"/><line x1="9.5" y1="22.5" x2="19.5" y2="22.5" stroke="#64748b" stroke-width="2" stroke-linecap="round"/></svg><h1 id="title">Mock server log</h1>
<span class="host" id="host"></span>
<a href="TEST_URL">Test Results &rarr;</a></header>
<main>
  <div class="bar">
    <input type="search" id="q" placeholder="Filter by URL, method, status, rule…">
    <select id="sort"><option value="new">Newest first</option><option value="old">Oldest first</option></select>
    <label><input type="checkbox" id="auto" checked> Auto-refresh</label>
    <button class="btn" id="reload">Reload</button>
    <button class="btn" id="clear">Clear</button>
    <a class="btn" href="TEST_URL" style="text-decoration:none">Test Results &rarr;</a>
    <span class="count" id="count"></span>
  </div>
  <div id="list"></div>
</main>
<script>
var METHODS={GET:'get',POST:'post',PUT:'put',DELETE:'delete',PATCH:'patch',
HEAD:'head',OPTIONS:'options'};
var entries=[], open={};

// The chip carries the method's colour as a tint; the entry's own border stays neutral. A coloured
// rule around every row competes with the status for attention and wins, which is backwards.
function tint(m,part){var v=getComputedStyle(document.documentElement)
  .getPropertyValue('--'+(METHODS[m]||'options')+'-'+part).trim();
  return v||'var(--slate-'+part+')';}
function esc(s){return String(s==null?'':s).replace(/[&<>]/g,function(c){
  return {'&':'&amp;','<':'&lt;','>':'&gt;'}[c];});}
function pretty(e,which){var b=e[which].body;
  if(b!==undefined&&b!==null)return JSON.stringify(b,null,2);
  return e[which].bodyText||'(no body)';}
function short(iso){if(!iso)return'';var d=new Date(iso);
  return isNaN(d)?iso:d.toLocaleTimeString(undefined,{hour12:false})+'.'+
    String(d.getMilliseconds()).padStart(3,'0');}
function pathOf(u){try{return new URL(u).pathname+new URL(u).search;}catch(_){return u;}}

function draw(){
  var q=document.getElementById('q').value.toLowerCase();
  var rows=entries.filter(function(e){
    if(!q)return true;
    return (e.request.method+' '+e.request.url+' '+e.response.status+' '+(e.rule||''))
      .toLowerCase().indexOf(q)>-1;});
  if(document.getElementById('sort').value==='new')rows=rows.slice().reverse();
  document.getElementById('count').textContent=
    rows.length+' of '+entries.length+' call'+(entries.length===1?'':'s');
  var list=document.getElementById('list');
  if(!rows.length){list.innerHTML='<div class="empty">'+(entries.length?
    'Nothing matches that filter.':'No calls recorded yet — send a request to this mock.')+
    '</div>';return;}
  list.innerHTML=rows.map(function(e){
    var m=e.request.method||'GET', s=e.response.status||0;
    var cls=s>=500?'s5':s>=400?'s4':'s2';
    return '<details class="op" data-k="'+e.seq+'"'+(open[e.seq]?' open':'')+'>'+
      '<summary>'+
      '<span class="verb" style="background:'+tint(m,'bg')+';color:'+tint(m,'fg')+'">'+esc(m)+'</span>'+
      '<span class="u">'+esc(pathOf(e.request.url))+'</span>'+
      '<span class="st '+cls+'">'+esc(s)+'</span>'+
      '<span class="when">'+esc(short(e.at))+' · '+esc(e.durationMs)+'ms</span>'+
      '</summary><div class="body">'+
      (e.rule?'<div class="rule"><b>Matched rule:</b> '+esc(e.rule)+'</div>':
        '<div class="rule">Answered from the spec\\'s example response.</div>')+
      '<h3>Curl request <button class="copy" data-c="'+encodeURIComponent(e.curl||'')+
        '">Copy</button></h3>'+
      '<pre class="curl">'+esc(e.curl)+'</pre>'+
      '<h3>Server response <span class="st '+cls+'">'+esc(s)+' '+
        esc(e.response.statusText||'')+'</span></h3>'+
      '<table class="h">'+Object.keys(e.response.headers||{}).map(function(k){
        return '<tr><td>'+esc(k)+'</td><td>'+esc(e.response.headers[k])+'</td></tr>';}).join('')+
      '</table><pre class="resp">'+esc(pretty(e,'response'))+'</pre>'+
      '</div></details>';}).join('');
  [].forEach.call(list.querySelectorAll('details'),function(d){
    d.ontoggle=function(){open[d.dataset.k]=d.open;};});
  [].forEach.call(list.querySelectorAll('.copy'),function(b){
    b.onclick=function(ev){ev.preventDefault();
      navigator.clipboard.writeText(decodeURIComponent(b.dataset.c));
      b.textContent='Copied';setTimeout(function(){b.textContent='Copy';},1200);};});
}

function load(){
  fetch('DATA_URL').then(function(r){return r.json();})
    .then(function(d){entries=d.entries;
      document.title=d.name+' — mock log';
      document.getElementById('title').textContent=d.name+' log';
      document.getElementById('host').textContent=d.host;
      draw();})
    .catch(function(){});
}
document.getElementById('q').oninput=draw;
document.getElementById('sort').onchange=draw;
document.getElementById('reload').onclick=load;
document.getElementById('clear').onclick=function(){
  if(!confirm('Clear this log?'))return;
  fetch('DATA_URL',{method:'DELETE'}).then(load);};
setInterval(function(){if(document.getElementById('auto').checked)load();},3000);
load();
</script></body></html>
""".replace("/*BASE_CSS*/", BASE_CSS)


# -------------------------------------------------------------------------------------- test view

def read_test_runs(directory, prefix=""):
    """Every `<dir>/*/results.json`, newest first.

    A run is just a folder holding a results.json; whatever produced it is none of the server's
    business. The raw evidence a runner drops alongside it is left alone and simply listed. `prefix`
    is folded into each id so a run stays addressable once suites nest their runs a level down.
    """
    runs = []
    if not directory or not os.path.isdir(directory):
        return runs
    for name in sorted(os.listdir(directory), reverse=True):
        path = os.path.join(directory, name, "results.json")
        if not os.path.isfile(path):
            continue
        try:
            with open(path, "r") as handle:
                result = json.load(handle)
        except Exception as error:
            runs.append({"id": prefix + name, "name": name, "error": str(error), "cases": []})
            continue
        cases = result.get("cases") or []
        tally = collections.Counter((c.get("verdict") or "unknown").lower() for c in cases)
        runs.append({
            "id": prefix + name,
            "stamp": name,
            "name": result.get("name") or name,
            "at": result.get("at"),
            "total": len(cases),
            "tally": dict(tally),
            "_result": result,
            "_files": sorted(f for f in os.listdir(os.path.join(directory, name))
                             if f != "results.json"),
        })
    return runs


def group_test_runs(results_dir, suites):
    """The declared suites, each carrying the runs in its own folder — `<results>/<suite>/run-*/`.

    Anything that does not sit under a declared suite is still returned, gathered under `unfiled`.
    A run whose suite was renamed, removed from the config, or written before suites had folders is
    exactly when someone needs to see it, and the engine's job is to render what it finds.
    """
    groups, claimed = [], set()
    for suite in suites:
        folder = os.path.join(results_dir, suite["id"]) if results_dir else None
        claimed.add(suite["id"])
        entry = {k: v for k, v in suite.items() if k != "command"}
        entry["runs"] = read_test_runs(folder, prefix=suite["id"] + "/")
        groups.append(entry)

    unfiled = []
    if results_dir and os.path.isdir(results_dir):
        # A results.json directly inside the results dir is a run from the flat layout that came
        # before suites had folders of their own.
        unfiled.extend(r for r in read_test_runs(results_dir) if r["stamp"] not in claimed)
        for name in sorted(os.listdir(results_dir), reverse=True):
            path = os.path.join(results_dir, name)
            if (name in claimed or not os.path.isdir(path)
                    or os.path.isfile(os.path.join(path, "results.json"))):
                continue
            unfiled.extend(read_test_runs(path, prefix=name + "/"))
    if unfiled:
        unfiled.sort(key=lambda r: r.get("stamp") or r["id"], reverse=True)
        groups.append({"id": "unfiled", "name": "Unfiled runs", "orphan": True,
                       "description": "not produced by any suite declared in this config",
                       "runs": unfiled})
    return groups


def all_runs(groups):
    return [run for group in groups for run in group["runs"]]


class SuiteRunner:
    """Runs one config-declared suite at a time, streaming its output into a ring buffer.

    Only suites written in the config file can be started, and only with flags that suite declares:
    the browser sends a suite id and a set of flag strings, never a command. That keeps a page
    served on loopback from being a way to run arbitrary shell.
    """

    def __init__(self):
        self.lock = threading.Lock()
        self.process = None
        self.lines = collections.deque(maxlen=500)
        self.meta = {}

    def _pump(self, process):
        for raw in iter(process.stdout.readline, b""):
            self.lines.append(raw.decode("utf-8", "replace").rstrip("\n"))
        process.wait()
        self.meta["finished"] = time.time()
        self.meta["exit_code"] = process.returncode

    def start(self, suite, flags, cases=None, cwd=None):
        with self.lock:
            if self.process and self.process.poll() is None:
                return False, "a run is already in progress"

            allowed = {o["flag"] for o in suite.get("options", [])}
            chosen = [f for f in flags if f in allowed]
            valid_cases = [c for c in (cases or []) if isinstance(c, str) and re.match(r"^[A-Za-z0-9_.-]+$", c)]
            command = list(suite["command"]) + chosen + valid_cases

            self.lines.clear()
            self.lines.append("$ " + " ".join(command))
            try:
                process = subprocess.Popen(command, cwd=cwd, stdout=subprocess.PIPE,
                                           stderr=subprocess.STDOUT, bufsize=1)
            except Exception as error:
                self.lines.append("failed to start: %s" % error)
                self.meta = {"suite": suite["id"], "started": time.time(),
                             "finished": time.time(), "exit_code": -1, "flags": chosen, "cases": valid_cases}
                return False, str(error)

            self.process = process
            self.meta = {"suite": suite["id"], "name": suite.get("name", suite["id"]),
                         "started": time.time(), "finished": None,
                         "exit_code": None, "flags": chosen, "cases": valid_cases}
            threading.Thread(target=self._pump, args=(process,), daemon=True).start()
            return True, None

    def stop(self):
        with self.lock:
            if self.process and self.process.poll() is None:
                self.process.terminate()
                return True
            return False

    def status(self):
        running = bool(self.process and self.process.poll() is None)
        out = dict(self.meta)
        out["running"] = running
        # poll() reports the exit as soon as the process goes, while _pump may still be draining
        # its output and has not recorded the code yet -- read it off the process meanwhile, so the
        # page never shows "exit null" for a run that has clearly finished.
        if not running and out.get("exit_code") is None and self.process is not None:
            out["exit_code"] = self.process.returncode
        out["output"] = list(self.lines)
        if out.get("started"):
            end = out.get("finished") or time.time()
            out["elapsed"] = int(end - out["started"])
        return out


def resolve_suites(config, config_dir, root_dir=HERE):
    """Suite commands and CLI references are resolved relative to root_dir (local-test-servers)."""
    suites = []
    for suite in config.get("test_suites") or []:
        entry = dict(suite)
        raw_cmd = list(entry.get("command") or [])
        resolved_cmd = []
        for part in raw_cmd:
            candidate_config = os.path.normpath(os.path.join(config_dir, part))
            candidate_root = os.path.normpath(os.path.join(root_dir, part))
            if os.path.exists(candidate_config):
                resolved_cmd.append(os.path.relpath(candidate_config, root_dir))
            elif os.path.exists(candidate_root):
                resolved_cmd.append(os.path.relpath(candidate_root, root_dir))
            else:
                resolved_cmd.append(part)
        entry["command"] = resolved_cmd
        entry["cli"] = " ".join(resolved_cmd)
        suites.append(entry)
    return suites


TEST_UI_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Test Results & Living Specs</title>
<link rel="icon" type="image/svg+xml" href=\"""" + TEST_FAVICON_DATA_URI + """\">
<link rel="shortcut icon" type="image/svg+xml" href=\"""" + TEST_FAVICON_DATA_URI + """\">
<style>
/*BASE_CSS*/
html, body{height:100vh;width:100vw;margin:0;padding:0;overflow:hidden}
body{display:flex;flex-direction:column}
header{flex:none;height:48px;max-height:48px;padding:0 20px;display:flex;align-items:center;box-sizing:border-box}
.wrap{display:flex;flex:1;min-height:0;height:auto;overflow:hidden;width:100%;box-sizing:border-box}
aside{width:22vw;min-width:270px;max-width:360px;flex:none;background:var(--panel);
border-right:1px solid var(--line-2);padding:1.4vh 10px;overflow-y:auto;height:100%;box-sizing:border-box}
.aside-hd{display:flex;align-items:center;justify-content:space-between;gap:8px;margin:0 0 8px;padding:0 3px}
.aside-hd h2{font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin:0;font-weight:600}
.batch-run-btn{padding:3px 9px;border:0;border-radius:var(--radius);background:var(--pass-bg);color:var(--pass-fg);font-size:11px;font-weight:600;cursor:pointer;transition:all .15s ease;display:inline-flex;align-items:center;gap:4px;white-space:nowrap}
.batch-run-btn:hover{background:var(--pass-bg-2)}
.batch-run-btn[disabled]{background:var(--mute-bg);color:var(--muted);cursor:not-allowed}
.batch-run-btn.running{background:var(--run-bg);color:var(--run-fg);animation:pulse 1.1s ease-in-out infinite}
.aside-subbar{display:flex;align-items:center;justify-content:space-between;padding:2px 4px 6px;font-size:11px;color:var(--muted);border-bottom:1px solid var(--line);margin-bottom:8px}
.aside-sel-all-label{display:inline-flex;align-items:center;gap:6px;cursor:pointer;user-select:none;font-size:11px;color:var(--ink-2);font-weight:500}
.aside-sel-all-label input{margin:0;cursor:pointer}
.aside-queue-indicator{font-size:10.5px;color:var(--run-fg);font-weight:600}
.suite-chk-label{display:inline-flex;align-items:center;margin-right:2px;cursor:pointer;flex:none}
.suite-chk-label input{margin:0;cursor:pointer}
.run{display:flex;align-items:center;gap:6px;width:100%;text-align:left;background:none;border:0;cursor:pointer;
padding:4px 6px 4px 8px;font-size:12px;color:var(--ink-2);border-radius:6px;transition:background .1s;flex:none;box-sizing:border-box}
.run:hover{background:var(--hover)}
.run.on{background:var(--selected);color:var(--ink);font-weight:600}
.run-main{display:flex;align-items:flex-start;gap:8px;flex:1;min-width:0;background:none;border:0;cursor:pointer;text-align:left;padding:0;color:inherit;font:inherit}
.run-dot{width:8px;height:8px;border-radius:50%;margin-top:4px;flex:none}
.run-dot.pass{background:var(--pass-fg)}
.run-dot.fail{background:var(--fail-fg)}
.run-dot.blocked{background:var(--warn-fg)}
.run-body{flex:1;min-width:0}
.run-time-text{font-size:12px;font-weight:600;display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.run-tally{font-size:11px;color:var(--muted);font-weight:400;margin-top:2px}
.run-del-btn{display:inline-flex;align-items:center;justify-content:center;width:20px;height:20px;border-radius:4px;border:none;background:transparent;color:var(--muted);cursor:pointer;font-size:12px;opacity:0.35;transition:all .15s;flex:none;padding:0;margin-left:auto}
.run:hover .run-del-btn{opacity:0.75}
.run-del-btn:hover{opacity:1;background:var(--fail-bg);color:var(--fail-fg)}

main{flex:1;display:flex;flex-direction:column;min-width:0;height:100%;overflow-y:auto;overflow-x:hidden;padding:1.4vh 1.4vw 2.5vh;box-sizing:border-box}
.pinned-header{width:100%;box-sizing:border-box}
.scroll-area{width:100%;box-sizing:border-box}

/* Mode Switcher & Top Header Bar */
.top-header-bar{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:1.2vh;flex-wrap:wrap}
.mode-switch{display:inline-flex;background:var(--surface-2);border:1px solid var(--line-2);border-radius:var(--radius);padding:3px;gap:3px;box-shadow:var(--shadow)}
.mode-btn{border:0;background:transparent;padding:6px 14px;font-size:12px;font-weight:500;color:var(--ink-2);cursor:pointer;border-radius:calc(var(--radius) - 2px);transition:all .15s ease;display:inline-flex;align-items:center;gap:6px}
.mode-btn:hover{color:var(--ink);background:rgba(255,255,255,.04)}
.mode-btn.active{background:var(--surface);color:var(--ink);font-weight:600;box-shadow:0 1px 3px rgba(0,0,0,.4)}
.global-actions{display:flex;align-items:center;gap:8px}

/* Executive Summary Card */
.exec-card{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);box-shadow:var(--shadow);padding:12px 16px;margin-bottom:1.2vh}
.exec-hd{display:flex;align-items:flex-start;justify-content:space-between;gap:14px;margin-bottom:8px;flex-wrap:wrap}
.exec-title h2{margin:0 0 3px;font-size:15px;font-weight:700;color:var(--ink);display:flex;align-items:center;gap:8px}
.exec-title .sub{font-size:11.5px;color:var(--muted)}
.health-container{margin:8px 0}
.health-label{display:flex;justify-content:space-between;align-items:center;font-size:11.5px;font-weight:600;color:var(--ink-2);margin-bottom:4px}
.health-bar-bg{height:8px;border-radius:999px;background:var(--surface-2);border:1px solid var(--line);overflow:hidden;display:flex}
.health-bar-fill{height:100%;transition:width .3s ease}
.health-bar-pass{background:var(--pass-fg)}
.health-bar-fail{background:var(--fail-fg)}
.health-bar-blocked{background:var(--warn-fg)}

.chips{display:flex;gap:7px;margin-top:8px;flex-wrap:wrap;align-items:center}
.chip{padding:3px 10px;border-radius:999px;font-size:11.5px;font-weight:600;cursor:pointer;border:1px solid transparent;background:var(--surface-2);color:var(--ink-2);transition:all .1s}
.chip:hover{opacity:.85}
.chip.is-active{box-shadow:0 0 0 2px var(--ink)}
.chip.pass{background:var(--pass-bg);color:var(--pass-fg)}
.chip.fail{background:var(--fail-bg);color:var(--fail-fg)}
.chip.skip,.chip.pending{background:var(--mute-bg);color:var(--mute-fg)}
.chip.blocked{background:var(--warn-bg);color:var(--warn-fg)}
.chip.total{background:var(--surface-2);color:var(--ink);border-color:var(--line)}
.run-time-badge{font-size:11.5px;color:var(--muted);margin-left:auto}

.fail-alert{background:#fef2f2;border:1px solid #fecaca;border-radius:var(--radius);padding:8px 12px;margin-top:8px;color:#991b1b;font-size:11.5px}
.fail-alert-hd{font-weight:700;display:flex;align-items:center;gap:6px;margin-bottom:4px}
.fail-item{margin:3px 0;display:flex;align-items:center;gap:8px;font-size:11.5px}
.jump-btn{padding:1px 7px;border-radius:4px;background:#fee2e2;border:1px solid #fca5a5;color:#991b1b;font-size:10.5px;cursor:pointer;font-weight:600}
.jump-btn:hover{background:#fecaca}

.resume-btn{background:var(--pass-bg);color:var(--pass-fg);border:1px solid var(--pass-fg);font-weight:600;cursor:pointer;display:inline-flex;align-items:center;gap:5px;padding:3px 10px;border-radius:var(--radius);font-size:11.5px;transition:all .15s ease}
.resume-btn:hover{background:var(--pass-bg-2)}
.pending-alert{background:#eff6ff;border:1px solid #bfdbfe;border-radius:var(--radius);padding:8px 12px;margin-top:8px;color:#1e40af;font-size:12px;display:flex;align-items:center;justify-content:space-between;gap:10px}

/* Filter bar */
.bar{display:flex;gap:10px;align-items:center;margin-bottom:1.2vh;flex-wrap:wrap}
.bar input[type=search]{flex:1;min-width:180px}

/* Terminal Drawer */
.term-drawer{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);box-shadow:var(--shadow);margin-bottom:1.2vh;overflow:hidden}
.term-summary{display:flex;align-items:center;gap:8px;padding:7px 12px;cursor:pointer;background:var(--surface);font-size:12px;color:var(--ink-2);user-select:none;list-style:none;transition:background .15s}
.term-summary:hover{background:var(--surface-2)}
.term-summary::-webkit-details-marker{display:none}
.term-summary .s-arrow{font-size:9px;color:var(--dim);flex:none;transition:transform .15s ease;display:inline-block}
.term-drawer[open] > .term-summary .s-arrow{transform:rotate(90deg)}
.term-drawer pre{margin:0;border:0;border-radius:0;background:#182232;color:#e2e8f0;padding:10px 12px;font-size:11.5px;line-height:1.55;max-height:25vh;overflow:auto;white-space:pre-wrap;border-top:1px solid var(--line)}

/* Suite Box in Sidebar */
.grp{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);box-shadow:var(--shadow);overflow:hidden;margin-bottom:8px}
.ghd{display:flex;align-items:center;gap:8px;padding:7px 9px;cursor:pointer;user-select:none;list-style:none;transition:background .12s ease}
.ghd:hover{background:var(--surface-2)}
.ghd::-webkit-details-marker{display:none}
.ghd .s-arrow{font-size:9px;color:var(--dim);flex:none;transition:transform .15s ease;display:inline-block}
.grp[open] > .ghd .s-arrow{transform:rotate(90deg)}
.ghd .nm{font-size:12.5px;font-weight:600;flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.grp-body{border-top:1px solid var(--line);padding:5px 0 4px;background:var(--surface)}
.go{padding:4px 9px;border:0;border-radius:999px;background:var(--pass-bg);color:var(--pass-fg);font-size:11px;font-weight:600;cursor:pointer;flex:none}
.go:hover{background:var(--pass-bg-2)}
.go[disabled]{background:var(--mute-bg);color:var(--muted);cursor:not-allowed}
.stop{background:var(--fail-bg);color:var(--fail-fg)}
.stop:hover{background:var(--fail-bg-2)}

.s-info{margin:3px 0 0;font-size:11px}
.s-sum{display:flex;align-items:center;gap:6px;padding:3px 9px;cursor:pointer;color:var(--muted);user-select:none;list-style:none;border-radius:4px;transition:background .1s}
.s-sum:hover{background:var(--surface-2);color:var(--ink)}
.s-sum::-webkit-details-marker{display:none}
.s-arrow{font-size:9px;color:var(--dim);flex:none;transition:transform .15s ease;display:inline-block}
.s-info[open] .s-arrow{transform:rotate(90deg)}
.s-brief{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:11px}
.s-est{flex:none;font-size:10px;color:var(--dim);padding:1px 4px;background:var(--code-bg);border-radius:4px;border:1px solid var(--line)}
.s-detail{padding:6px 9px 7px;background:var(--surface-2);border-top:1px solid var(--line);border-bottom:1px solid var(--line);margin-top:3px}
.s-desc{font-size:11px;color:var(--ink-2);line-height:1.45;margin:0 0 5px}
.s-meta{display:flex;gap:5px;flex-wrap:wrap;align-items:center}
.s-tag{font-size:10px;color:var(--muted);background:var(--surface);padding:1px 5px;border-radius:4px;border:1px solid var(--line)}
.s-tag code{font-family:"SF Mono",Menlo,monospace;font-size:9.5px;color:var(--ink)}
.grp label.flag-opt{display:flex;align-items:center;gap:7px;font-size:11px;color:var(--ink-2);padding:3px 9px;cursor:pointer}
.grp label.flag-opt input{margin:0;cursor:pointer;flex:none}

/* Granular Case Selection in Sidebar */
.case-picker{margin:6px 6px 4px;background:var(--surface-2);border:1px solid var(--line);border-radius:6px;padding:6px}
.case-picker-hd{display:flex;align-items:center;justify-content:space-between;font-size:11px;font-weight:600;color:var(--muted);margin-bottom:5px;cursor:pointer;user-select:none}
.case-picker-hd::-webkit-details-marker{display:none}
.case-picker-btns{display:flex;gap:4px}
.tiny-btn{padding:2px 6px;font-size:10px;border:1px solid var(--line-2);border-radius:3px;background:var(--surface);cursor:pointer;color:var(--ink-2)}
.tiny-btn:hover{background:var(--surface-2);color:var(--ink)}
.case-list{max-height:150px;overflow-y:auto;display:flex;flex-direction:column;gap:2px;padding-right:2px}
.case-opt{display:flex;align-items:flex-start;font-size:11px;color:var(--ink-2);cursor:pointer;padding:3px 4px;border-radius:3px;line-height:1.4}
.case-opt:hover{background:var(--surface)}
.case-opt input{margin:2px 8px 0 2px;cursor:pointer;flex:none}
.case-opt b{font-family:"SF Mono",Menlo,monospace;font-size:10.5px;margin-right:5px;color:var(--ink);flex:none}
.case-opt span{flex:1;word-break:break-word}

/* Scrollable Suite Run History (5 items visible) */
.runs{margin:6px 4px 4px;padding:4px 0 2px;border-top:1px solid var(--line);max-height:246px;overflow-y:auto;display:flex;flex-direction:column;gap:2px}
.runs .none{padding:6px 9px;font-size:11px;color:var(--muted)}

/* Card & Table Results */
.card{width:100%;background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);box-shadow:var(--shadow);margin-bottom:1.4vh;overflow:hidden}
.cardhd{display:flex;align-items:baseline;gap:9px;padding:8px 12px;background:var(--surface-2);border-bottom:1px solid var(--line)}
.cardhd b{font-size:12px;font-weight:600}
.cardhd span{font-size:11px;color:var(--muted)}

table.t{width:100%;border-collapse:collapse;background:var(--surface)}
table.t th{text-align:left;font-size:11px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);padding:8px 12px;background:var(--surface-2);border-bottom:1px solid var(--line);font-weight:600;position:sticky;top:0;z-index:2;box-shadow:0 1px 0 var(--line)}
table.t td{padding:8px 12px;border-bottom:1px solid var(--line);vertical-align:top;font-size:13px}
table.t th.c-id{width:45px}
table.t th.c-case{width:32%}
table.t th.c-v{width:120px}
tr.case{cursor:pointer}
tr.case:hover td{background:var(--hover)}
tr.case.open td{background:var(--selected)}
table.t tbody tr:last-child td{border-bottom:0}
td.id{font-family:"SF Mono",Menlo,monospace;font-weight:700;font-size:12.5px}

.v span{padding:3px 9px;border-radius:999px;font-size:11px;font-weight:600;letter-spacing:.02em}
.v .pass{background:var(--pass-bg);color:var(--pass-fg)}
.v .fail{background:var(--fail-bg);color:var(--fail-fg)}
.v .skip,.v .pending{background:var(--mute-bg);color:var(--mute-fg)}
.v .blocked{background:var(--warn-bg);color:var(--warn-fg)}
.v .running{background:var(--run-bg);color:var(--run-fg);animation:pulse 1.1s ease-in-out infinite}
@keyframes pulse{50%{opacity:.55}}
.cnt{color:var(--muted);font-size:11px;margin-left:6px;font-variant-numeric:tabular-nums}
tr.case.bad td{background:var(--fail-bg)}
tr.case.bad:hover td,tr.case.bad.open td{background:var(--fail-bg-2)}

.run-single-btn{padding:2px 7px;border-radius:4px;background:var(--surface);border:1px solid var(--line-2);color:var(--ink-2);font-size:11px;font-weight:600;cursor:pointer;margin-left:6px;transition:all .1s}
.run-single-btn:hover{background:var(--pass-bg);color:var(--pass-fg);border-color:var(--pass-fg)}

/* Detail Accordion */
tr.detail td{background:var(--canvas);padding:0}
.dwrap{padding:14px 18px}

/* Business Spec Elements */
.spec-box{background:var(--surface);border:1px solid var(--line);border-radius:6px;padding:12px 14px;margin-bottom:10px}
.spec-sec-title{font-size:11px;text-transform:uppercase;letter-spacing:.06em;font-weight:700;color:var(--muted);margin:0 0 6px;display:flex;align-items:center;gap:6px}
.spec-given{font-size:12.5px;color:var(--ink);line-height:1.55;margin:0;background:var(--surface-2);padding:7px 11px;border-radius:5px;border-left:3px solid #3b82f6}
.spec-ac-list{list-style:none;padding:0;margin:0;display:flex;flex-direction:column;gap:5px}
.spec-ac-item{display:flex;align-items:flex-start;gap:8px;font-size:12.5px;color:var(--ink);line-height:1.5;background:var(--surface-2);padding:6px 10px;border-radius:5px}
.spec-ac-icon{flex:none;font-size:12px;font-weight:700}
.spec-ac-icon.ok{color:#16a34a}
.spec-ac-icon.fail{color:#dc2626}
.spec-why{background:#fffbeb;border:1px solid #fef3c7;border-left:3px solid #f59e0b;border-radius:5px;padding:8px 12px;color:#92400e;font-size:12px;line-height:1.55;margin:0}

/* Technical Mode Tables & Micro Assertions */
table.ck{width:100%;border-collapse:collapse}
table.ck td,table.ck th{padding:2px 10px 2px 0;border:0;font-size:12px;vertical-align:top}
table.ck th{text-align:left;font-size:10px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);font-weight:600;padding-bottom:4px}
table.ck td.cl{width:17em;color:var(--ink-2);white-space:nowrap}
table.ck td.cw{width:46ch;color:var(--muted);font-family:"SF Mono",Menlo,monospace;font-size:11px;white-space:nowrap}
table.ck td.ce,table.ck td.ca{font-family:"SF Mono",Menlo,monospace;white-space:nowrap}
table.ck td.ce{width:8ch;color:var(--muted)}
table.ck td.ca{width:18ch}
table.ck td.st{width:5em;font-size:10px;font-weight:600;letter-spacing:.05em;color:var(--pass-fg)}
table.ck td.gap{width:auto}
table.ck tr.no td.ca{color:var(--fail-fg);font-weight:600}
table.ck tr.no td.st{color:var(--fail-fg)}
table.ck tr.no td.cl,table.ck tr.no td.ce{color:var(--ink)}
.rest{font-size:11px;color:var(--muted);margin-top:4px}
.mono{font-family:"SF Mono",Menlo,monospace;font-size:12px;color:var(--ink-2)}
.sum{color:var(--ink-2)}
.sum .sep{color:var(--dim);padding:0 2px}
.kv{border-collapse:collapse;margin-bottom:10px}
.kv td{padding:2px 0;border:0;font-size:12px}
.kv td:first-child{color:var(--muted);padding-right:16px;white-space:nowrap}
.kv td.mono{font-size:12px;color:var(--ink)}

.copy-cli-btn{padding:3px 9px;border-radius:4px;background:var(--surface);border:1px solid var(--line-2);color:var(--ink-2);font-size:11px;cursor:pointer;display:inline-flex;align-items:center;gap:4px;margin-bottom:8px}
.copy-cli-btn:hover{background:var(--surface-2);color:var(--ink)}
.files{font-size:11px;color:var(--muted);margin-top:10px;width:100%;line-height:1.5}
.spin{width:11px;height:11px;border:2px solid rgba(0,0,0,.15);border-top-color:currentColor;border-radius:50%;animation:sp .7s linear infinite;display:inline-block}
@keyframes sp{to{transform:rotate(360deg)}}
</style></head><body>
<header>
  <h1><svg style="vertical-align:-3px;margin-right:6px;flex:none" width="18" height="18" viewBox="0 0 32 32"><rect width="32" height="32" rx="7" fill="#1e293b"/><circle cx="16" cy="16" r="11" fill="#0f172a" stroke="#4ade80" stroke-width="1.8"/><circle cx="16" cy="16" r="6" fill="none" stroke="#22c55e" stroke-width="1" stroke-opacity="0.5"/><line x1="16" y1="5" x2="16" y2="27" stroke="#22c55e" stroke-width="1" stroke-opacity="0.5"/><line x1="5" y1="16" x2="27" y2="16" stroke="#22c55e" stroke-width="1" stroke-opacity="0.5"/><line x1="16" y1="16" x2="24" y2="8" stroke="#4ade80" stroke-width="1.8" stroke-linecap="round"/><circle cx="21" cy="11" r="1.5" fill="#4ade80"/><circle cx="11" cy="20" r="1.2" fill="#38bdf8"/></svg>Test Results</h1>
  <span class="host" id="host"></span>
  <a href="LOG_URL">Call Log &rarr;</a>
</header>
<div class="wrap">
  <aside>
    <div class="aside-hd">
      <h2>Test Suites</h2>
      <button class="batch-run-btn" id="btn-batch-run" type="button" onclick="startBatchRun()">▶ Run Selected</button>
    </div>
    <div class="aside-subbar">
      <label class="aside-sel-all-label">
        <input type="checkbox" id="chk-suite-all" checked onchange="toggleAllSuites(this.checked)">
        <span>Select All</span>
      </label>
      <span class="aside-queue-indicator" id="aside-queue-indicator"></span>
    </div>
    <div id="tree"></div>
  </aside>
  <main>
    <div class="pinned-header">
      <div class="top-header-bar">
        <div class="mode-switch">
          <button class="mode-btn" id="btn-mode-business" type="button" onclick="setMode('business')">📋 Business View</button>
          <button class="mode-btn" id="btn-mode-tech" type="button" onclick="setMode('tech')">🛠️ Technical View</button>
        </div>
        <div class="global-actions">
          <button class="btn" type="button" onclick="copyMarkdownReport()">📄 Copy Report</button>
          <button class="btn" id="btn-expand-all" type="button" onclick="toggleAllSpecs()">📖 Expand All Specs</button>
        </div>
      </div>

      <div id="runbox"></div>
      <div id="exec-summary"></div>

      <div class="bar">
        <input type="search" id="q" placeholder="Filter by scenario name, ID, criteria, note…">
        <select id="only">
          <option value="">All verdicts</option>
          <option value="fail">Failures only</option>
          <option value="pass">Passes only</option>
          <option value="pending">Pending only</option>
          <option value="blocked">Blocked only</option>
          <option value="skip">Skipped only</option>
        </select>
      </div>
    </div>

    <div class="scroll-area" id="scroll-area">
      <div id="table"></div>
      <div class="files" id="files"></div>
    </div>
  </main>
</div>
<script>
var current=null, result=null, open={}, suites=[], run={}, wasRunning=false, expanded={}, suiteInfoOpen={}, suiteCasePickOpen={}, suiteOpen={}, termOpen=false;
var knownSuiteCases={}, caseSelection={};
var suiteSelection={};
var batchQueue=[], isBatchRunning=false, batchTotal=0, batchCurrentIndex=0;
var viewMode = localStorage.getItem('test_view_mode') || 'business';
var SHOWN=10;

function syncModeButtons(){
  var bBtn = document.getElementById('btn-mode-business');
  var tBtn = document.getElementById('btn-mode-tech');
  if(bBtn) bBtn.className = 'mode-btn' + (viewMode==='business' ? ' active' : '');
  if(tBtn) tBtn.className = 'mode-btn' + (viewMode==='tech' ? ' active' : '');
}
syncModeButtons();

function esc(s){return String(s==null?'':s).replace(/[&<>]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;'}[c];});}
var VERDICTS=['pass','fail','blocked','skip','running','sent','pending'];
function vclass(v){v=(v||'').toLowerCase();return VERDICTS.indexOf(v)>-1?v:'skip';}
function allRuns(){return suites.reduce(function(a,s){return a.concat(s.runs||[]);},[]);}

function setMode(mode){
  viewMode = mode;
  localStorage.setItem('test_view_mode', mode);
  syncModeButtons();
  draw();
}

function formatStamp(stamp, iso){
  if(iso){
    try {
      var d = new Date(iso);
      var now = new Date();
      var isToday = d.toDateString() === now.toDateString();
      var yesterday = new Date(now); yesterday.setDate(now.getDate() - 1);
      var isYesterday = d.toDateString() === yesterday.toDateString();
      var timeStr = d.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
      if(isToday) return 'Today at ' + timeStr;
      if(isYesterday) return 'Yesterday at ' + timeStr;
      return d.toLocaleDateString([], {month:'short', day:'numeric'}) + ' at ' + timeStr;
    } catch(e){}
  }
  if(stamp && stamp.indexOf('run-') === 0){
    var raw = stamp.replace('run-','');
    if(raw.length >= 15){
      var y = raw.substring(0,4), m = raw.substring(4,6), day = raw.substring(6,8);
      var h = raw.substring(9,11), min = raw.substring(11,13);
      return m + '/' + day + ' ' + h + ':' + min;
    }
  }
  return stamp || 'Run';
}

function runRow(r){
  var t=r.tally||{}, bits=[];
  ['pass','fail','blocked','skip'].forEach(function(k){if(t[k])bits.push(t[k]+' '+k);});
  var isBad = (t['fail']||0) > 0;
  var isBlocked = (t['blocked']||0) > 0;
  var dotClass = isBad ? 'fail' : (isBlocked ? 'blocked' : 'pass');
  return '<div class="run'+(r.id===current?' on':'')+'" data-run-id="'+esc(r.id)+'">'+
    '<button class="run-main" type="button" data-run-id="'+esc(r.id)+'">'+
      '<span class="run-dot '+dotClass+'"></span>'+
      '<div class="run-body">'+
        '<span class="run-time-text">'+esc(formatStamp(r.stamp||r.id, r.at))+'</span>'+
        '<span class="run-tally">'+(bits.join(' · ')||(r.total||0)+' case(s)')+'</span>'+
      '</div>'+
    '</button>'+
    '<button class="run-del-btn" type="button" data-del-run="'+esc(r.id)+'" title="Remove this run history">✕</button>'+
  '</div>';
}

function deleteRun(runId, ev){
  if(ev){ ev.stopPropagation(); ev.preventDefault(); }
  if(!runId) return;
  if(!confirm('Remove this test run from history?')) return;
  fetch('DATA_URL?run=' + encodeURIComponent(runId), { method: 'DELETE' })
    .then(function(r){ return r.json(); })
    .then(function(d){
      if(d && d.ok){
        if(current === runId) current = null;
        load();
      } else {
        alert('Could not remove run: ' + ((d && d.error) || 'Unknown error'));
      }
    })
    .catch(function(err){
      alert('Could not remove run: ' + err);
    });
}

function checkList(list, full){
  var head = full
    ? '<thead><tr><th>Checked</th><th>Measured</th><th>Expected</th><th>Actual</th><th>Status</th><th></th></tr></thead>'
    : '';
  return '<table class="ck">'+head+'<tbody>'+list.map(function(k){
    return '<tr class="'+(k.ok?'ok':'no')+'">'+
      '<td class="cl"'+(!full&&k.what?' title="'+esc(k.what)+'"':'')+'>'+esc(k.label)+'</td>'+
      (full?'<td class="cw">'+esc(k.what||'')+'</td>':'')+
      '<td class="ce">'+esc(k.expected)+'</td>'+
      '<td class="ca">'+esc(k.actual)+'</td>'+
      '<td class="st">'+(k.ok?'OK':'FAILED')+'</td><td class="gap"></td></tr>';
  }).join('')+'</tbody></table>';
}

function resultCell(c, isOpen){
  var list=c.checks||[];
  if(!list.length){
    return '<div class="sum">'+esc(c.expected||'')+'</div><div class="mono">'+esc(c.actual||'')+'</div>';
  }
  if(isOpen) return checkList(list, true);
  var bad=list.filter(function(k){return !k.ok;});
  if(!bad.length){
    return '<span class="sum">'+esc(c.summary||c.actual||'').replace(/ · /g,'<span class="sep">·</span>')+'</span>';
  }
  var rest=list.length-bad.length;
  return checkList(bad, false)+
    (rest?'<div class="rest">'+rest+' other check'+(rest===1?'':'s')+' passed · click for all</div>':'');
}

function checkCount(c){
  var list=c.checks||[];
  if(!list.length) return '';
  return '<span class="cnt">'+list.filter(function(k){return k.ok;}).length+'/'+list.length+'</span>';
}

function drawExecSummary(){
  var box = document.getElementById('exec-summary');
  if(!result){ box.innerHTML=''; return; }
  var cases = result.cases || [];
  var total = cases.length;
  var counts = { pass: 0, fail: 0, blocked: 0, skip: 0, pending: 0, running: 0 };
  cases.forEach(function(c){
    var v = vclass(c.verdict);
    counts[v] = (counts[v] || 0) + 1;
  });

  var pendingCases = cases.filter(function(c){
    var v = vclass(c.verdict);
    return v === 'pending' || v === 'running';
  });
  var pendingCount = pendingCases.length;

  var passPct = total ? Math.round((counts.pass / total) * 1000) / 10 : 0;
  var failPct = total ? Math.round((counts.fail / total) * 1000) / 10 : 0;
  var blockedPct = total ? Math.round((counts.blocked / total) * 1000) / 10 : 0;

  var currentFilter = document.getElementById('only').value;
  var filterQ = document.getElementById('q').value;

  var pendingAlertHtml = '';
  if(pendingCount > 0 && (!run || !run.running)){
    pendingAlertHtml = '<div class="pending-alert">'+
      '<span>⏸ <b>'+pendingCount+' Pending scenario'+(pendingCount>1?'s':'')+'</b> remaining (run paused or partial).</span>'+
      '<button class="resume-btn" type="button" data-resume-suite="'+esc(result.suite)+'">▶ Resume Pending ('+pendingCount+')</button>'+
    '</div>';
  }

  var failedCases = cases.filter(function(c){ return vclass(c.verdict) === 'fail'; });
  var failAlertHtml = '';
  if(failedCases.length > 0){
    failAlertHtml = '<div class="fail-alert">'+
      '<div class="fail-alert-hd">⚠️ '+failedCases.length+' Failing Scenario'+(failedCases.length>1?'s':'')+' Detected</div>'+
      failedCases.map(function(f){
        return '<div class="fail-item">'+
          '<b>'+esc(f.id)+'</b>: '+esc(f.name||'')+
          '<button class="jump-btn" type="button" data-jump="'+esc(f.id)+'">View Case &darr;</button>'+
        '</div>';
      }).join('')+
    '</div>';
  }

  box.innerHTML = '<div class="exec-card">'+
    '<div class="exec-hd">'+
      '<div class="exec-title">'+
        '<h2>'+esc(result.name || result.suite || 'Test Suite')+'</h2>'+
        '<div class="sub">Integration Verification & Living Specification</div>'+
      '</div>'+
      '<div style="display:flex;align-items:center;gap:8px;margin-left:auto">'+
        (pendingCount > 0 && (!run || !run.running) ? '<button class="resume-btn" type="button" data-resume-suite="'+esc(result.suite)+'">▶ Resume Pending ('+pendingCount+')</button>' : '')+
        '<div class="run-time-badge">🕒 '+esc(formatStamp(result.run, result.at))+'</div>'+
      '</div>'+
    '</div>'+
    '<div class="health-container">'+
      '<div class="health-label">'+
        '<span>Health: '+passPct+'% Passing ('+counts.pass+' of '+total+' Scenarios)</span>'+
        '<span>'+(counts.fail > 0 ? counts.fail+' Failures' : 'All Checks Green')+'</span>'+
      '</div>'+
      '<div class="health-bar-bg">'+
        '<div class="health-bar-fill health-bar-pass" style="width:'+passPct+'%"></div>'+
        '<div class="health-bar-fill health-bar-fail" style="width:'+failPct+'%"></div>'+
        '<div class="health-bar-fill health-bar-blocked" style="width:'+blockedPct+'%"></div>'+
      '</div>'+
    '</div>'+
    '<div class="chips">'+
      '<button class="chip total'+(currentFilter===''&&!filterQ?' is-active':'')+'" type="button" data-filter="">All: '+total+' Cases</button>'+
      (counts.pass ? '<button class="chip pass'+(currentFilter==='pass'?' is-active':'')+'" type="button" data-filter="pass">✅ '+counts.pass+' Passed</button>' : '')+
      (counts.fail ? '<button class="chip fail'+(currentFilter==='fail'?' is-active':'')+'" type="button" data-filter="fail">❌ '+counts.fail+' Failed</button>' : '')+
      (counts.blocked ? '<button class="chip blocked'+(currentFilter==='blocked'?' is-active':'')+'" type="button" data-filter="blocked">⚠️ '+counts.blocked+' Blocked</button>' : '')+
      (pendingCount ? '<button class="chip pending'+(currentFilter==='pending'?' is-active':'')+'" type="button" data-filter="pending">⏳ '+pendingCount+' Pending</button>' : '')+
    '</div>'+
    pendingAlertHtml+
    failAlertHtml+
  '</div>';
}

function filterByVerdict(v){
  document.getElementById('only').value = v;
  draw();
}

function jumpToCase(id){
  open[id] = true;
  document.getElementById('only').value = '';
  document.getElementById('q').value = '';
  draw();
  setTimeout(function(){
    var el = document.querySelector('tr.case[data-id="'+id+'"]');
    if(el) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }, 50);
}

function copyMarkdownReport(){
  if(!result) return;
  var cases = result.cases || [];
  var total = cases.length;
  var counts = { pass: 0, fail: 0, blocked: 0, skip: 0 };
  cases.forEach(function(c){ counts[vclass(c.verdict)] = (counts[vclass(c.verdict)] || 0) + 1; });
  var passPct = total ? Math.round((counts.pass / total) * 1000) / 10 : 0;
  var failed = cases.filter(function(c){ return vclass(c.verdict) === 'fail'; });

  var lines = [];
  lines.push('### Test Report: ' + (result.name || result.suite || 'Test Suite'));
  lines.push('- **Status**: ' + (counts.fail === 0 ? '✅ PASSED' : '❌ ' + counts.fail + ' FAILED') + ' (' + passPct + '% Health - ' + counts.pass + '/' + total + ' Passed)');
  lines.push('- **Executed At**: ' + formatStamp(result.run, result.at));
  lines.push('- **Results**: ' + counts.pass + ' passed, ' + counts.fail + ' failed, ' + (counts.blocked || 0) + ' blocked' + String.fromCharCode(10));
  if(failed.length > 0){
    lines.push('#### Failing Scenarios:');
    failed.forEach(function(f){
      lines.push('- **[' + f.id + '] ' + (f.name || '') + '**');
      if(f.note) lines.push('  - *Why*: ' + f.note);
      (f.checks || []).filter(function(k){ return !k.ok; }).forEach(function(k){
        lines.push('  - ❌ Check `' + k.label + '`: Expected `' + k.expected + '`, Actual `' + k.actual + '`');
      });
    });
  }
  var md = lines.join(String.fromCharCode(10));
  navigator.clipboard.writeText(md);
  alert('Report copied to clipboard! Ready to paste into Jira or Slack.');
}

function toggleAllSpecs(){
  if(!result) return;
  var cases = result.cases || [];
  var anyClosed = cases.some(function(c){ return !open[c.id]; });
  cases.forEach(function(c){ open[c.id] = anyClosed; });
  document.getElementById('btn-expand-all').textContent = anyClosed ? '📕 Collapse All Specs' : '📖 Expand All Specs';
  draw();
}

function runSingleCase(suiteId, caseId){
  if(!suiteId || !caseId) return;
  fetch('RUN_URL', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ suite: suiteId, flags: [], cases: [caseId] })
  }).then(function(r){ return r.json(); }).then(function(){ tick(); });
}

function drawTree(){
  var busy = !!run.running;
  document.getElementById('tree').innerHTML = suites.map(function(s){
    var list = s.runs||[], shown = expanded[s.id] ? list : list.slice(0, SHOWN);
    var desc = s.description || '';
    var isSuiteOpen = suiteOpen[s.id];
    if(isSuiteOpen === undefined){
      isSuiteOpen = (result && result.suite === s.id) || suites.length === 1;
    }
    var isOpen = !!suiteInfoOpen[s.id];
    var isCasePickOpen = !!suiteCasePickOpen[s.id];
    var briefText = s.summary || desc || s.name || s.id;
    if(s.cases && s.cases.length > 0){
      knownSuiteCases[s.id] = s.cases;
    }
    var suiteCases = (s.cases && s.cases.length > 0 ? s.cases : knownSuiteCases[s.id]) || [];

    var infoHtml = '';
    if(desc || s.estimate){
      infoHtml = '<details class="s-info" data-sinfo="'+esc(s.id)+'"'+(isOpen?' open':'')+'>'+
        '<summary class="s-sum">'+
          '<span class="s-arrow">&#9656;</span>'+
          '<span class="s-brief" title="'+esc(desc)+'">'+esc(briefText)+'</span>'+
          (s.estimate?'<span class="s-est">'+esc(s.estimate)+'</span>':'')+
        '</summary>'+
        '<div class="s-detail">'+
          (desc?'<div class="s-desc">'+esc(desc)+'</div>':'')+
          '<div class="s-meta">'+
            '<span class="s-tag">ID: <code>'+esc(s.id)+'</code></span>'+
            (s.estimate?'<span class="s-tag">Est: <b>'+esc(s.estimate)+'</b></span>':'')+
          '</div>'+
        '</div></details>';
    }

    var casePickerHtml = '';
    if(!s.orphan && suiteCases && suiteCases.length > 0){
      casePickerHtml = '<details class="case-picker" data-scases="'+esc(s.id)+'"'+(isCasePickOpen?' open':'')+'>'+
        '<summary class="case-picker-hd">'+
          '<span>Select Cases to Run ('+suiteCases.length+')</span>'+
          '<div class="case-picker-btns">'+
            '<button class="tiny-btn" type="button" data-sel-all="'+esc(s.id)+'" data-val="true">All</button>'+
            '<button class="tiny-btn" type="button" data-sel-all="'+esc(s.id)+'" data-val="false">None</button>'+
            '<button class="tiny-btn" type="button" data-sel-fail="'+esc(s.id)+'">Failures</button>'+
            '<button class="tiny-btn" type="button" data-sel-pending="'+esc(s.id)+'">Pending</button>'+
          '</div>'+
        '</summary>'+
        '<div class="case-list">'+
          suiteCases.map(function(c){
            var isChecked = caseSelection[s.id] ? (caseSelection[s.id][c.id] !== false) : true;
            return '<label class="case-opt">'+
              '<input type="checkbox" data-suite="'+esc(s.id)+'" data-case="'+esc(c.id)+'"'+(isChecked?' checked':'')+'>'+
              '<b>'+esc(c.id)+':</b>'+
              '<span>'+esc(c.name||'')+'</span>'+
            '</label>';
          }).join('')+
        '</div></details>';
    }

    var isRunningThis = !!run.running && run.suite === s.id;
    var isQueued = isBatchRunning && batchQueue.some(function(item){ return item.suiteId === s.id; });
    var queuePosition = -1;
    if(isQueued){
      queuePosition = batchQueue.findIndex(function(item){ return item.suiteId === s.id; }) + 1;
    }

    var btnText = 'Run All';
    if(isRunningThis){
      btnText = 'Running…';
    } else if(isQueued){
      btnText = 'Queued #' + queuePosition;
    } else {
      var allCount = suiteCases.length;
      if(caseSelection[s.id]){
        var checkedCount = suiteCases.filter(function(c){ return caseSelection[s.id][c.id] !== false; }).length;
        if(allCount > 0 && checkedCount < allCount){
          btnText = 'Run (' + checkedCount + ')';
        }
      }
    }

    var isSuiteChecked = suiteSelection[s.id] !== false;

    return '<details class="grp" data-suite-grp="'+esc(s.id)+'"'+(isSuiteOpen?' open':'')+'>'+
      '<summary class="ghd">'+
        (s.orphan?'':'<label class="suite-chk-label" onclick="event.stopPropagation();" title="Include in batch run"><input type="checkbox" data-suite-chk="'+esc(s.id)+'"'+(isSuiteChecked?' checked':'')+((busy||isBatchRunning)?' disabled':'')+'>'+'</label>')+
        '<span class="s-arrow">&#9656;</span>'+
        '<span class="nm" title="'+esc(s.name||s.id)+'">'+esc(s.name||s.id)+'</span>'+
        (s.orphan?'':'<button class="go" type="button" data-run-suite="'+esc(s.id)+'" id="run-btn-'+esc(s.id)+'"'+((busy||isBatchRunning)?' disabled'+(isRunningThis?'':' title="A test suite is currently running"'):'')+'>'+
          esc(btnText)+'</button>')+
      '</summary>'+
      '<div class="grp-body">'+
        infoHtml+
        (s.orphan?'':(s.options||[]).map(function(o,i){
          return '<label class="flag-opt"><input type="checkbox" data-suite="'+esc(s.id)+'" data-flag="'+esc(o.flag)+'" value="'+esc(o.flag)+
            '"> '+esc(o.label||o.flag)+'</label>';}).join(''))+
        casePickerHtml+
        '<div class="runs">'+
          (list.map(runRow).join('') || '<div class="none">No runs yet.</div>')+
        '</div>'+
      '</div>'+
    '</details>';
  }).join('') || '<div class="ds" style="padding:0 16px">No suites declared in the config.</div>';

  [].forEach.call(document.querySelectorAll('details[data-suite-grp]'),function(d){
    d.ontoggle=function(){suiteOpen[d.dataset.suiteGrp]=d.open;};});
  [].forEach.call(document.querySelectorAll('details[data-sinfo]'),function(d){
    d.ontoggle=function(){suiteInfoOpen[d.dataset.sinfo]=d.open;};});
  [].forEach.call(document.querySelectorAll('details[data-scases]'),function(d){
    d.ontoggle=function(){suiteCasePickOpen[d.dataset.scases]=d.open;};});
  updateBatchRunButton();
}

function syncSelectAllSuiteCheckbox(){
  var allChks = document.querySelectorAll('input[data-suite-chk]');
  var checkedChks = document.querySelectorAll('input[data-suite-chk]:checked');
  var masterChk = document.getElementById('chk-suite-all');
  if(masterChk && allChks.length > 0){
    masterChk.checked = (checkedChks.length === allChks.length);
    masterChk.indeterminate = (checkedChks.length > 0 && checkedChks.length < allChks.length);
  }
}

function updateBatchRunButton(){
  var btn = document.getElementById('btn-batch-run');
  var indicator = document.getElementById('aside-queue-indicator');
  if(!btn) return;

  var activeSuites = suites.filter(function(s){ return !s.orphan; });
  var selectedSuites = activeSuites.filter(function(s){ return suiteSelection[s.id] !== false; });
  var count = selectedSuites.length;

  if(isBatchRunning){
    btn.className = 'batch-run-btn running';
    btn.textContent = 'Queue ' + batchCurrentIndex + '/' + batchTotal + '…';
    btn.disabled = true;
    if(indicator) indicator.textContent = 'Running ' + batchCurrentIndex + '/' + batchTotal;
  } else {
    btn.className = 'batch-run-btn';
    btn.textContent = '▶ Run Selected (' + count + ')';
    btn.disabled = (count === 0 || !!run.running);
    if(indicator) indicator.textContent = '';
  }
  syncSelectAllSuiteCheckbox();
}

function toggleAllSuites(checked){
  suites.forEach(function(s){
    if(!s.orphan) suiteSelection[s.id] = checked;
  });
  [].forEach.call(document.querySelectorAll('input[data-suite-chk]'), function(i){
    i.checked = checked;
  });
  updateBatchRunButton();
}

function startBatchRun(){
  if(run.running || isBatchRunning) return;
  var chosenSuites = suites.filter(function(s){
    return !s.orphan && (suiteSelection[s.id] !== false);
  });
  if(!chosenSuites.length) return;

  batchQueue = chosenSuites.map(function(s){
    var flags = [].filter.call(document.querySelectorAll('input[data-suite="'+s.id+'"][data-flag]:checked'), function(){return true;}).map(function(i){return i.value;});
    var allCaseChks = document.querySelectorAll('input[data-suite="'+s.id+'"][data-case]');
    var checkedCases = [].filter.call(allCaseChks, function(i){ return i.checked; }).map(function(i){ return i.dataset.case; });
    var chosenCases = (allCaseChks.length > 0 && checkedCases.length < allCaseChks.length) ? checkedCases : [];
    return { suiteId: s.id, flags: flags, cases: chosenCases, name: s.name || s.id };
  });

  isBatchRunning = true;
  batchTotal = batchQueue.length;
  batchCurrentIndex = 0;
  runNextInBatch();
}

function runNextInBatch(){
  if(!isBatchRunning) return;
  if(batchQueue.length === 0){
    isBatchRunning = false;
    batchTotal = 0;
    batchCurrentIndex = 0;
    drawTree();
    updateBatchRunButton();
    return;
  }

  var item = batchQueue.shift();
  batchCurrentIndex++;
  updateBatchRunButton();
  drawTree();

  fetch('RUN_URL', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ suite: item.suiteId, flags: item.flags, cases: item.cases })
  }).then(function(r){ return r.json(); })
    .then(function(d){
      if(!d || !d.ok){
        console.error('Failed to start suite in batch:', d ? d.error : 'Unknown error');
        setTimeout(runNextInBatch, 1000);
      } else {
        tick();
      }
    })
    .catch(function(err){
      console.error('Batch run error on ' + item.suiteId, err);
      setTimeout(runNextInBatch, 1000);
    });
}

function stopBatch(){
  isBatchRunning = false;
  batchQueue = [];
  batchTotal = 0;
  batchCurrentIndex = 0;
  fetch('STOP_URL', { method: 'POST' }).then(tick);
}

function selectAllCases(suiteId, checked){
  if(!caseSelection[suiteId]) caseSelection[suiteId] = {};
  [].forEach.call(document.querySelectorAll('input[data-suite="'+suiteId+'"][data-case]'), function(i){
    i.checked = checked;
    caseSelection[suiteId][i.dataset.case] = checked;
  });
  updateRunBtnText(suiteId);
}

function selectFailuresOnly(suiteId){
  var failedIds = (result && result.cases ? result.cases.filter(function(c){ return vclass(c.verdict)==='fail'; }).map(function(c){ return c.id; }) : []);
  if(!caseSelection[suiteId]) caseSelection[suiteId] = {};
  [].forEach.call(document.querySelectorAll('input[data-suite="'+suiteId+'"][data-case]'), function(i){
    var chk = failedIds.indexOf(i.dataset.case) > -1;
    i.checked = chk;
    caseSelection[suiteId][i.dataset.case] = chk;
  });
  updateRunBtnText(suiteId);
}

function selectPendingOnly(suiteId){
  var pendingIds = (result && result.cases ? result.cases.filter(function(c){
    var v = vclass(c.verdict);
    return v === 'pending' || v === 'running';
  }).map(function(c){ return c.id; }) : []);
  if(!caseSelection[suiteId]) caseSelection[suiteId] = {};
  [].forEach.call(document.querySelectorAll('input[data-suite="'+suiteId+'"][data-case]'), function(i){
    var chk = pendingIds.indexOf(i.dataset.case) > -1;
    i.checked = chk;
    caseSelection[suiteId][i.dataset.case] = chk;
  });
  updateRunBtnText(suiteId);
}

function resumePending(suiteId){
  if(!result || !result.cases) return;
  var pendingIds = result.cases.filter(function(c){
    var v = vclass(c.verdict);
    return v === 'pending' || v === 'running';
  }).map(function(c){ return c.id; });
  if(!pendingIds.length) return;
  var flags=[].filter.call(document.querySelectorAll('input[data-suite="'+suiteId+'"][data-flag]:checked'), function(){return true;}).map(function(i){return i.value;});
  fetch('RUN_URL', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ suite: suiteId, flags: flags, cases: pendingIds })
  }).then(function(r){ return r.json(); }).then(function(){ tick(); });
}

function updateRunBtnText(suiteId){
  var btn = document.getElementById('run-btn-' + suiteId);
  if(!btn || (run.running && run.suite === suiteId)) return;
  var all = document.querySelectorAll('input[data-suite="'+suiteId+'"][data-case]');
  var checked = document.querySelectorAll('input[data-suite="'+suiteId+'"][data-case]:checked');
  if(all.length > 0 && checked.length < all.length){
    btn.textContent = 'Run (' + checked.length + ')';
  } else {
    btn.textContent = 'Run All';
  }
}

function drawRun(){
  var box=document.getElementById('runbox');
  if(!run.started){ box.innerHTML=''; return; }
  var done = !run.running;
  var statusText, statusClass;
  if(!done){
    statusClass = 'running';
    statusText = '<span class="spin"></span> Running…';
  } else if(run.exit_code === 0){
    statusClass = 'pass';
    statusText = 'Completed (Exit 0)';
  } else if(run.exit_code === -15 || run.exit_code === 130 || run.exit_code === -9){
    statusClass = 'blocked';
    statusText = 'Stopped (' + run.exit_code + ')';
  } else {
    statusClass = 'fail';
    statusText = 'Failed (Exit ' + run.exit_code + ')';
  }

  var summaryBar = '<details class="term-drawer" id="term-drawer"'+(termOpen?' open':'')+'>'+
    '<summary class="term-summary">'+
      '<span class="s-arrow">&#9656;</span>'+
      '<span class="chip '+statusClass+'" style="display:inline-flex;align-items:center;gap:6px">'+statusText+'</span>'+
      '<b>Terminal Output: ' + esc(run.name||run.suite||'run') + '</b>'+
      (run.cases&&run.cases.length?'<span class="mono" style="font-size:11px">['+esc(run.cases.join(', '))+']</span>':'')+
      (run.flags&&run.flags.length?'<span class="mono" style="font-size:11px">'+esc(run.flags.join(' '))+'</span>':'')+
      '<span class="el" style="margin-left:auto;font-size:11px;color:var(--muted)">'+(run.elapsed||0)+'s</span>'+
      (done?'':'<button class="go stop" type="button" id="stopbtn" style="margin-left:8px">Stop</button>')+
    '</summary>'+
    '<pre id="outp">'+esc((run.output||[]).join(String.fromCharCode(10)))+'</pre></details>';

  box.innerHTML = summaryBar;
  var drawer = document.getElementById('term-drawer');
  if(drawer){
    drawer.ontoggle = function(){ termOpen = drawer.open; };
  }
  var pre=document.getElementById('outp'); if(pre && !done && termOpen) pre.scrollTop=pre.scrollHeight;
  var sb=document.getElementById('stopbtn');
  if(sb) sb.onclick=function(ev){ ev.stopPropagation(); sb.disabled=true; stopBatch(); };
}

function tick(){
  fetch('STATUS_URL').then(function(r){return r.json();}).then(function(s){
    run=s; drawRun(); drawTree(); updateBatchRunButton();
    if(s.running){
      current=null; load();
      setTimeout(tick, 1500);
    } else if(wasRunning){
      wasRunning=false; current=null; load();
      if(isBatchRunning){
        if(batchQueue.length > 0){
          setTimeout(runNextInBatch, 600);
        } else {
          isBatchRunning = false;
          batchTotal = 0;
          batchCurrentIndex = 0;
          updateBatchRunButton();
          drawTree();
        }
      }
    }
    wasRunning = wasRunning || !!s.running;
  }).catch(function(){});
}

function draw(){
  drawExecSummary();
  var tbl=document.getElementById('table');
  if(!result){tbl.innerHTML='<div class="empty">Select a run from the sidebar to inspect results.</div>';return;}
  var cases=result.cases||[];
  var q=document.getElementById('q').value.toLowerCase();
  var only=document.getElementById('only').value;

  var rows=cases.filter(function(c){
    if(only&&vclass(c.verdict)!==only)return false;
    if(!q)return true;
    return JSON.stringify(c).toLowerCase().indexOf(q)>-1;
  });
  if(!rows.length){tbl.innerHTML='<div class="empty">No test cases match your search filter.</div>';return;}

  var groups=[], seen={};
  rows.forEach(function(c){
    var k=c.shape||'';
    if(!seen[k]){seen[k]={key:k,rows:[]};groups.push(seen[k]);}
    seen[k].rows.push(c);
  });

  var HEAD = viewMode === 'business'
    ? '<thead><tr><th class="c-id">ID</th><th class="c-case">Scenario / Business Story</th><th>Status Summary</th><th class="c-v">Verdict</th></tr></thead>'
    : '<thead><tr><th class="c-id">ID</th><th class="c-case">Case</th><th>Technical Assertions</th><th class="c-v">Verdict</th></tr></thead>';

  var suiteId = result.suite || '';

  tbl.innerHTML=groups.map(function(g){
    var bad=g.rows.filter(function(c){return vclass(c.verdict)==='fail';}).length;
    var groupTitle = g.key ? g.key.charAt(0).toUpperCase()+g.key.slice(1) + ' Cases' : 'Test Scenarios';

    return '<section class="card">'+
      '<div class="cardhd"><b>'+esc(groupTitle)+'</b>'+
        '<span>'+g.rows.length+' case'+(g.rows.length===1?'':'s')+
        (bad?' · <b style="color:var(--fail-fg)">'+bad+' failing</b>':' · all passing')+
        '</span></div>'+
      '<table class="t">'+HEAD+'<tbody>'+
      g.rows.map(function(c){
        var v=vclass(c.verdict), o=open[c.id];
        var d='';
        if(o){
          if(viewMode === 'business'){
            var acHtml = '';
            if(c.then && c.then.length){
              acHtml = '<div class="spec-box">'+
                '<div class="spec-sec-title">📋 Acceptance Criteria</div>'+
                '<ul class="spec-ac-list">'+
                  c.then.map(function(t, idx){
                    var isOk = (v === 'pass');
                    return '<li class="spec-ac-item">'+
                      '<span class="spec-ac-icon '+(isOk?'ok':'fail')+'">'+(isOk?'✅':'❌')+'</span>'+
                      '<span>'+esc(t)+'</span>'+
                    '</li>';
                  }).join('')+
                '</ul></div>';
            }
            var givenHtml = c.given ? '<div class="spec-box"><div class="spec-sec-title">📌 Given Scenario</div><p class="spec-given">'+esc(c.given)+'</p></div>' : '';
            var whyHtml = c.note ? '<div class="spec-box"><div class="spec-sec-title">💡 Why This Case Exists</div><p class="spec-why">'+esc(c.note)+'</p></div>' : '';
            var kvHtml = '<table class="kv">'+Object.keys(c.detail||{}).map(function(k){
              return '<tr><td>'+esc(k)+'</td><td class="mono">'+esc(c.detail[k])+'</td></tr>';
            }).join('')+'</table>';
            d='<tr class="detail"><td colspan="4"><div class="dwrap">'+
              givenHtml+acHtml+whyHtml+kvHtml+
              '</div></td></tr>';
          } else {
            var suiteCli = (suites.filter(function(s){return s.id===suiteId;})[0]||{}).cli;
            var cliCmd = (suiteCli || 'python3 <suite file>') + ' ' + c.id;
            d='<tr class="detail"><td colspan="4"><div class="dwrap">'+
              '<button class="copy-cli-btn" type="button" data-cli="'+esc(cliCmd)+'">📋 Copy CLI: <code>'+esc(cliCmd)+'</code></button>'+
              (c.given?'<h4>Given</h4><p class="note">'+esc(c.given)+'</p>':'')+
              (c.then&&c.then.length?'<h4>Acceptance criteria</h4><ul class="ac">'+
                 c.then.map(function(t){return '<li>'+esc(t)+'</li>';}).join('')+'</ul>':'')+
              (c.note?'<h4>Why this case exists</h4><p class="note">'+esc(c.note)+'</p>':'')+
              '<table class="kv">'+Object.keys(c.detail||{}).map(function(k){
                 return '<tr><td>'+esc(k)+'</td><td class="mono">'+esc(c.detail[k])+'</td></tr>';
               }).join('')+'</table>'+
              (c.calls&&c.calls.length?'<h4>Partner Mock Calls</h4><pre>'+
                 esc(c.calls.map(function(x){return x;}).join(String.fromCharCode(10)))+'</pre>':'')+
              '</div></td></tr>';
          }
        }

        var runBtn = '<button class="run-single-btn" type="button" data-run-suite="'+esc(suiteId)+'" data-run-case="'+esc(c.id)+'" title="Re-run only this scenario">▶ Run</button>';
        var summaryCol = viewMode === 'business' ? (c.summary || c.actual || '') : resultCell(c, o);

        return '<tr class="case'+(v==='fail'?' bad':'')+(o?' open':'')+'" data-id="'+esc(c.id)+'">'+
          '<td class="id">'+esc(c.id)+'</td>'+
          '<td><b>'+esc(c.name||'')+'</b></td>'+
          '<td>'+summaryCol+'</td>'+
          '<td class="v" style="white-space:nowrap">'+
            '<span class="'+v+'">'+esc((c.verdict||'?').toUpperCase())+'</span>'+
            checkCount(c)+runBtn+
          '</td>'+
        '</tr>'+d;
      }).join('')+'</tbody></table></section>';
  }).join('');

  [].forEach.call(tbl.querySelectorAll('tr.case'),function(tr){
    tr.onclick=function(){open[tr.dataset.id]=!open[tr.dataset.id];draw();};
  });

  var r=allRuns().filter(function(x){return x.id===current;})[0];
  document.getElementById('files').textContent =
    r&&r.files&&r.files.length ? 'Evidence files in run: '+r.files.join(', ') : '';
}

function copyText(txt){
  navigator.clipboard.writeText(txt);
  alert('Copied to clipboard: ' + txt);
}

document.addEventListener('click', function(ev){
  var jump = ev.target.closest('[data-jump]');
  if(jump){ jumpToCase(jump.dataset.jump); return; }
  var filterBtn = ev.target.closest('[data-filter]');
  if(filterBtn){ filterByVerdict(filterBtn.dataset.filter); return; }
  var runSingle = ev.target.closest('[data-run-case]');
  if(runSingle){
    ev.stopPropagation();
    runSingleCase(runSingle.dataset.runSuite, runSingle.dataset.runCase);
    return;
  }
  var copyBtn = ev.target.closest('[data-cli]');
  if(copyBtn){
    ev.stopPropagation();
    copyText(copyBtn.dataset.cli);
    return;
  }
  var selAll = ev.target.closest('[data-sel-all]');
  if(selAll){
    ev.stopPropagation();
    selectAllCases(selAll.dataset.selAll, selAll.dataset.val === 'true');
    return;
  }
  var resumeBtn = ev.target.closest('[data-resume-suite]');
  if(resumeBtn){
    ev.stopPropagation();
    resumePending(resumeBtn.dataset.resumeSuite);
    return;
  }
  var selPending = ev.target.closest('[data-sel-pending]');
  if(selPending){
    ev.stopPropagation();
    selectPendingOnly(selPending.dataset.selPending);
    return;
  }
  var selFail = ev.target.closest('[data-sel-fail]');
  if(selFail){
    ev.stopPropagation();
    selectFailuresOnly(selFail.dataset.selFail);
    return;
  }
  var delRun = ev.target.closest('[data-del-run]');
  if(delRun){
    ev.stopPropagation();
    ev.preventDefault();
    deleteRun(delRun.dataset.delRun, ev);
    return;
  }
  var runId = ev.target.closest('[data-run-id]');
  if(runId){ current=runId.dataset.runId; open={}; load(); return; }
  var more = ev.target.closest('[data-more]');
  if(more){ expanded[more.dataset.more]=!expanded[more.dataset.more]; drawTree(); return; }
  var runSuite = ev.target.closest('[data-run-suite]');
  if(runSuite && !runSuite.dataset.runCase){
      ev.preventDefault();
      ev.stopPropagation();
      isBatchRunning = false;
      batchQueue = [];
      batchTotal = 0;
      batchCurrentIndex = 0;
      var suiteId = runSuite.dataset.runSuite;
      var flags=[].filter.call(document.querySelectorAll('input[data-suite="'+suiteId+'"][data-flag]:checked'), function(){return true;}).map(function(i){return i.value;});
      var allCaseChks = document.querySelectorAll('input[data-suite="'+suiteId+'"][data-case]');
      var checkedCases = [].filter.call(allCaseChks, function(i){ return i.checked; }).map(function(i){ return i.dataset.case; });
      var chosenCases = (allCaseChks.length > 0 && checkedCases.length < allCaseChks.length) ? checkedCases : [];
      runSuite.disabled=true; runSuite.textContent='Starting…';
      updateBatchRunButton();
      fetch('RUN_URL', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({suite:suiteId, flags:flags, cases:chosenCases})
      }).then(function(r){return r.json();})
        .then(function(){ tick(); }).catch(function(){ runSuite.disabled=false; runSuite.textContent='Run'; });
      return;
  }
});

document.addEventListener('change', function(ev){
  var suiteChk = ev.target.closest('input[data-suite-chk]');
  if(suiteChk){
    var sid = suiteChk.dataset.suiteChk;
    suiteSelection[sid] = suiteChk.checked;
    updateBatchRunButton();
    return;
  }
  var caseChk = ev.target.closest('input[data-case]');
  if(caseChk){
    var sid = caseChk.dataset.suite;
    var cid = caseChk.dataset.case;
    if(!caseSelection[sid]) caseSelection[sid] = {};
    caseSelection[sid][cid] = caseChk.checked;
    updateRunBtnText(sid);
  }
});

function load(){
  fetch('DATA_URL'+(current?'?run='+encodeURIComponent(current):''))
    .then(function(r){return r.json();})
    .then(function(d){
      current=d.current; result=d.result; suites=d.suites||[];
      document.getElementById('host').textContent=d.name+' — '+d.host;
      syncModeButtons();
      drawTree(); draw();
    }).catch(function(err){ console.error('Failed to load test results:', err); });
}

document.getElementById('q').oninput=draw;
document.getElementById('only').onchange=draw;
load();
tick();
</script></body></html>
""".replace("/*BASE_CSS*/", BASE_CSS)


# ------------------------------------------------------------------------------------------ routes

class Route:
    def __init__(self, method, path, rules, before, source):
        self.method = method.upper()
        self.path = path
        self.segments = [s for s in path.strip("/").split("/") if s != ""]
        self.rules = rules
        self.before = before
        self.source = source

    def match(self, segments):
        """Returns the path params, plus how many segments matched literally so the most specific
        route wins -- /saleorders/status must beat /saleorders/{code}."""
        if len(segments) != len(self.segments):
            return None, -1
        params, literals = {}, 0
        for mine, theirs in zip(self.segments, segments):
            if mine.startswith("{") and mine.endswith("}"):
                params[mine[1:-1]] = unquote(theirs)
            elif mine == theirs:
                literals += 1
            else:
                return None, -1
        return params, literals


def build_routes(config, config_dir):
    """Every operation in the spec becomes a route answering the document's own example. Routes in
    the config are layered on top and replace the spec-derived one for the same method and path."""
    routes, spec = [], None

    spec_path = config.get("spec")
    if spec_path:
        spec_path = os.path.join(config_dir, spec_path)
        with open(spec_path, "r") as handle:
            spec = json.load(handle)
        base = (config.get("spec_base_path") or spec.get("basePath") or "").rstrip("/")
        for path, operations in (spec.get("paths") or {}).items():
            for method, operation in operations.items():
                if method.lower() not in METHODS:
                    continue
                default = spec_response(operation, spec)
                routes.append(Route(method, base + path,
                                    [{"respond": default}], [], "spec"))

    for entry in config.get("routes") or []:
        rules = list(entry.get("rules") or [])
        if "respond" in entry:
            # The route-level respond is the always-match rule at the end, and carries its own
            # `then` -- actions on the fallback path are as ordinary as actions on any other.
            rules.append({"name": entry.get("name", "default"),
                          "respond": entry["respond"],
                          "then": entry.get("then")})
        for method in ([entry["method"]] if "method" in entry else entry.get("methods", [])):
            route = Route(method, entry["path"], rules, entry.get("before"), "config")
            routes = [r for r in routes
                      if not (r.source == "spec" and r.method == route.method
                              and r.path == route.path)]
            routes.append(route)

    return routes, spec


# ----------------------------------------------------------------------------------------- serving

def make_handler(config, routes, state, api_log=None, results_dir=None,
                 suites=None, runner=None, suite_cwd=None, style=""):
    unmatched_status = int(config.get("unmatched_status", 404))
    verbose = config.get("verbose", True)
    ui_path = config.get("log_ui_path", "/log")
    data_path = ui_path.rstrip("/") + "/data"
    test_path = config.get("test_ui_path", "/")
    test_data_path = "/test/data"
    run_path = "/test/run"
    stop_path = "/test/stop"
    status_path = "/test/status"
    suites = suites or []

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def _send_raw(self, status, payload, content_type):
            """Answers without touching the call log -- viewing the log must not appear in it,
            least of all while the page is auto-refreshing."""
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def _serve_log_ui(self, parsed):
            if parsed.path.rstrip("/") == ui_path.rstrip("/"):
                page = (LOG_UI_HTML.replace("/*THEME*/", style)
                                   .replace("DATA_URL", data_path)
                                   .replace("TEST_URL", "/"))
                self._send_raw(200, page.encode("utf-8"), "text/html; charset=utf-8")
                return True
            if parsed.path.rstrip("/") != data_path:
                return False

            if self.command == "DELETE":
                if api_log and os.path.exists(api_log.path):
                    with _FILE_LOCK:
                        os.remove(api_log.path)
                self._send_raw(200, b'{"ok":true}', "application/json")
                return True

            payload = {
                "name": config.get("name", "Mock"),
                "host": "http://%s" % self.headers.get("Host", ""),
                "entries": read_log(api_log.path, api_log.format) if api_log else [],
            }
            self._send_raw(200, json.dumps(payload).encode("utf-8"), "application/json")
            return True

        def _serve_test_ui(self, parsed):
            here = parsed.path.rstrip("/")

            if here in ("", "/", "/test", "/index.html"):
                page = (TEST_UI_HTML.replace("/*THEME*/", style)
                                    .replace("DATA_URL", test_data_path)
                                    .replace("RUN_URL", run_path)
                                    .replace("STOP_URL", stop_path)
                                    .replace("STATUS_URL", status_path)
                                    .replace("LOG_URL", ui_path))
                self._send_raw(200, page.encode("utf-8"), "text/html; charset=utf-8")
                return True

            if here == status_path:
                self._send_raw(200, json.dumps(runner.status()).encode("utf-8"),
                               "application/json")
                return True

            if here == stop_path:
                self._send_raw(200, json.dumps({"stopped": runner.stop()}).encode("utf-8"),
                               "application/json")
                return True

            if here == run_path:
                length = int(self.headers.get("Content-Length", 0) or 0)
                try:
                    asked = json.loads(self.rfile.read(length).decode()) if length else {}
                except Exception:
                    asked = {}
                suite = next((s for s in suites if s["id"] == asked.get("suite")), None)
                if suite is None:
                    self._send_raw(404, b'{"ok":false,"error":"unknown suite"}',
                                   "application/json")
                    return True
                ok, error = runner.start(suite, asked.get("flags") or [], asked.get("cases") or [], suite_cwd)
                self._send_raw(200 if ok else 409,
                               json.dumps({"ok": ok, "error": error}).encode("utf-8"),
                               "application/json")
                return True

            if here != test_data_path:
                return False

            if self.command == "DELETE":
                asked_run = (parse_qs(parsed.query).get("run") or [None])[0]
                if not asked_run or ".." in asked_run or asked_run.startswith("/"):
                    self._send_raw(400, b'{"ok":false,"error":"invalid run id"}', "application/json")
                    return True
                if not results_dir or not os.path.isdir(results_dir):
                    self._send_raw(404, b'{"ok":false,"error":"results directory not found"}', "application/json")
                    return True
                target_dir = os.path.abspath(os.path.join(results_dir, asked_run))
                real_results = os.path.abspath(results_dir)
                if not target_dir.startswith(real_results) or not os.path.isdir(target_dir):
                    self._send_raw(404, b'{"ok":false,"error":"run folder not found"}', "application/json")
                    return True
                try:
                    shutil.rmtree(target_dir)
                    self._send_raw(200, b'{"ok":true}', "application/json")
                except Exception as error:
                    self._send_raw(500, json.dumps({"ok": False, "error": str(error)}).encode("utf-8"), "application/json")
                return True

            groups = group_test_runs(results_dir, suites)
            runs = all_runs(groups)
            wanted = (parse_qs(parsed.query).get("run") or [None])[0]
            chosen = next((r for r in runs if r["id"] == wanted), runs[0] if runs else None)

            def suite_cases(g):
                all_known = collections.OrderedDict()
                orig = next((s for s in suites if s.get("id") == g.get("id")), {})
                cmd = orig.get("command") or g.get("command") or []
                for part in cmd:
                    if isinstance(part, str) and part.endswith(".py") and "mock.py" not in part:
                        target = part if os.path.isabs(part) else os.path.normpath(os.path.join(suite_cwd or ".", part))
                        if os.path.isfile(target):
                            try:
                                with open(target, "r", encoding="utf-8") as f:
                                    text = f.read()
                                matches = re.findall(r'case\s*\(\s*["\']([A-Za-z0-9_.-]+)["\']\s*,\s*["\']([^"\']+)["\']', text)
                                for cid, name in matches:
                                    if cid not in all_known:
                                        shape = "error" if cid.startswith("E") else ("gap" if cid.startswith("G") else "normal")
                                        all_known[cid] = {"id": cid, "name": name, "shape": shape}
                            except Exception:
                                pass
                if not all_known:
                    sorted_runs = sorted(g.get("runs", []), key=lambda r: len((r.get("_result") or {}).get("cases") or []), reverse=True)
                    for r in sorted_runs:
                        res = r.get("_result")
                        if res and res.get("cases"):
                            for c in res.get("cases"):
                                cid = c.get("id")
                                if cid and cid not in all_known:
                                    all_known[cid] = {"id": cid, "name": c.get("name"), "shape": c.get("shape", "normal")}
                return list(all_known.values())

            def public(run):
                return {k: v for k, v in dict(run, files=run.get("_files", [])).items()
                        if not k.startswith("_")}

            payload = {
                "name": config.get("name", "Mock"),
                "host": "http://%s" % self.headers.get("Host", ""),
                "current": chosen["id"] if chosen else None,
                "result": chosen.get("_result") if chosen else None,
                "suites": [dict(g, cases=suite_cases(g), runs=[public(r) for r in g["runs"]]) for g in groups],
            }
            self._send_raw(200, json.dumps(payload).encode("utf-8"), "application/json")
            return True

        def _dispatch(self):
            started = time.time()
            parsed = urlparse(self.path)
            segments = [s for s in parsed.path.strip("/").split("/") if s != ""]

            if parsed.path == "/favicon.ico":
                referer = self.headers.get("Referer", "")
                svg = LOG_FAVICON_SVG if "/log" in referer else TEST_FAVICON_SVG
                self._send_raw(200, svg.encode("utf-8"), "image/svg+xml")
                return

            if self._serve_test_ui(parsed) or self._serve_log_ui(parsed):
                return

            length = int(self.headers.get("Content-Length", 0) or 0)
            raw_body = self.rfile.read(length).decode("utf-8", "replace") if length else ""
            try:
                body = json.loads(raw_body) if raw_body.strip() else None
            except Exception:
                body = None

            self._call = {
                "started_at": started,
                "started": datetime.datetime.now(datetime.timezone.utc)
                                   .isoformat(timespec="milliseconds").replace("+00:00", "Z"),
                "method": self.command,
                "path": parsed.path,
                # Rebuilt as an absolute URL so the logged curl runs as-is.
                "url": "http://%s%s" % (self.headers.get("Host", "127.0.0.1"), self.path),
                "query": parse_qs(parsed.query),
                "request_headers": dict(self.headers.items()),
                "request_body_text": raw_body,
                "request_body_json": body,
            }

            best, best_score = None, -1
            for route in routes:
                if route.method != self.command:
                    continue
                params, score = route.match(segments)
                if params is not None and score > best_score:
                    best, best_score = (route, params), score

            if best is None and segments and segments[0] == "api":
                sub_segments = segments[1:]
                for route in routes:
                    if route.method != self.command:
                        continue
                    params, score = route.match(sub_segments)
                    if params is not None and score > best_score:
                        best, best_score = (route, params), score

            if best is None:
                self._reply(unmatched_status, {
                    "HasError": True,
                    "ErrorMessages": ["mock_server: no route for %s %s" % (self.command, parsed.path)]
                }, None)
                return

            route, path_params = best
            ctx = {
                "method": self.command,
                "path": parsed.path,
                "path_params": path_params,
                "query": parse_qs(parsed.query),
                "headers": {k.lower(): v for k, v in self.headers.items()},
                "body": body,
                "raw_body": raw_body,
            }

            run_actions(route.before, ctx, state)

            for rule in route.rules:
                if rule.get("enabled") is False:
                    continue
                if not evaluate(rule.get("when"), ctx, state):
                    continue
                if "validate" in rule:
                    # A validation rule answers only when the request actually breaks something;
                    # a clean request falls through to whatever rule handles the happy path.
                    errors = validate(rule["validate"], ctx, state)
                    if not errors:
                        continue
                    ctx["validation"] = {"errors": errors, "count": len(errors),
                                         "summary": "; ".join(errors)}
                run_actions(rule.get("then"), ctx, state)
                respond = rule.get("respond") or {}
                delay = respond.get("delay_ms")
                if delay:
                    time.sleep(float(delay) / 1000.0)
                self._reply(int(respond.get("status", 200)),
                            render(respond.get("body"), ctx),
                            rule.get("name"),
                            respond.get("headers"))
                return

            self._reply(unmatched_status, {
                "HasError": True,
                "ErrorMessages": ["mock_server: no rule matched for %s %s" % (self.command, parsed.path)]
            }, None)

        def _reply(self, status, body, rule_name, headers=None):
            if body is None:
                payload = b""
            elif isinstance(body, (str, bytes)):
                payload = body.encode("utf-8") if isinstance(body, str) else body
            else:
                payload = json.dumps(body).encode("utf-8")

            response_headers = dict(headers or {"Content-Type": "application/json"})

            # Recorded before the response goes out. A test script that kills the server the moment
            # its last call returns would otherwise race the write and lose that call from the log.
            if api_log is not None:
                call = dict(self._call)
                call.update({
                    "duration_ms": round((time.time() - call.pop("started_at")) * 1000, 3),
                    "rule": rule_name,
                    "status": status,
                    "status_text": HTTPStatus(status).phrase if status in
                                   {s.value for s in HTTPStatus} else "",
                    "response_headers": response_headers,
                    "response_body_text": payload.decode("utf-8", "replace"),
                    "response_body_json": body if not isinstance(body, (str, bytes)) else None,
                })
                api_log.record(call)

            self.send_response(status)
            for key, value in response_headers.items():
                self.send_header(key, value)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            if payload:
                self.wfile.write(payload)

            if verbose:
                # Flushed because the server is normally launched as a background task with its
                # stdout redirected to a file, where a buffered log is a log you cannot follow.
                print("  %s %s -> %s%s" % (self.command, self.path, status,
                                           " [%s]" % rule_name if rule_name else ""), flush=True)

        def log_message(self, fmt, *args):
            pass

    for method in METHODS:
        setattr(Handler, "do_" + method.upper(), Handler._dispatch)
    return Handler


def check(config, routes, spec):
    print("%s -- %d route(s)" % (config.get("name", "mock server"), len(routes)))
    declared = set()
    if spec:
        base = (config.get("spec_base_path") or spec.get("basePath") or "").rstrip("/")
        for path, operations in (spec.get("paths") or {}).items():
            for method in operations:
                if method.lower() in METHODS:
                    declared.add((method.upper(), base + path))

    problems = 0
    for route in sorted(routes, key=lambda r: (r.path, r.method)):
        if route.source != "config":
            continue
        known = (route.method, route.path) in declared
        if not known and spec:
            problems += 1
        print("  %-6s %-52s %d rule(s) %s"
              % (route.method, route.path, len(route.rules),
                 "" if known or not spec else "<- not in spec"))

    covered = sum(1 for r in routes if r.source == "config")
    print("  %d configured, %d answered from the spec's own examples"
          % (covered, len(routes) - covered))
    if problems:
        print("  %d configured route(s) are not declared in the spec -- typo, or intentional "
              "(e.g. an auth host endpoint)" % problems)
    return 0


HERE = os.path.dirname(os.path.abspath(__file__))


def integrations():
    """Folders next to this script holding exactly the one thing that makes them an integration."""
    found = {}
    for name in sorted(os.listdir(HERE)):
        folder = os.path.join(HERE, name)
        if not os.path.isdir(folder) or name.startswith((".", "_")):
            continue
        configs = sorted(f for f in os.listdir(folder) if f.endswith(".mock.json"))
        if configs:
            found[name] = [os.path.join(folder, c) for c in configs]
    return found


def resolve_config(argument):
    """Accepts an integration name ("eton"), a folder, or a path to a config file.

    A bare name is looked up next to this script (local-test-servers root).
    """
    if argument and os.path.isfile(argument):
        return argument

    for folder in ([argument] if argument and os.path.isdir(argument) else []) + \
                  ([os.path.join(HERE, argument)] if argument else []):
        if os.path.isdir(folder):
            configs = sorted(f for f in os.listdir(folder) if f.endswith(".mock.json"))
            if len(configs) == 1:
                return os.path.join(folder, configs[0])
            if len(configs) > 1:
                raise SystemExit("%s holds %d configs -- name one:\n  %s"
                                 % (folder, len(configs),
                                    "\n  ".join(os.path.join(folder, c) for c in configs)))
            raise SystemExit("no *.mock.json in %s" % folder)

    available = integrations()
    listing = "\n".join("  %-12s %s" % (name, os.path.basename(paths[0]))
                        for name, paths in available.items()) or "  (none yet)"
    listing += "\n  %-12s %s" % ("portal", "Central portal dashboard (port 23000)")
    if argument:
        raise SystemExit("unknown integration %r. Available:\n%s" % (argument, listing))
    raise SystemExit("usage: python3 %s <integration|portal>\n\nAvailable:\n%s"
                     % (os.path.basename(__file__), listing))


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("config", nargs="?",
                        help="integration name (e.g. eton), or a path to a mock config JSON")
    parser.add_argument("--port", type=int, help="override the port in the config")
    parser.add_argument("--host", help="override the host in the config")
    parser.add_argument("--check", action="store_true",
                        help="print the route table, validate it against the spec, and exit")
    parser.add_argument("--log", help="append every call to this file (overrides the config)")
    parser.add_argument("--log-format", choices=("har", "simple"),
                        help="har (default, importable by DevTools/Postman/Insomnia) or simple")
    parser.add_argument("--no-log", action="store_true", help="disable the call log")
    parser.add_argument("--portal", action="store_true", help="run the central portal dashboard")
    parser.add_argument("--reset", action="store_true",
                        help="empty the stores, call log, and test results before starting")
    args = parser.parse_args()

    if args.config == "portal" or args.portal:
        portal_script = os.path.join(HERE, "portal.py")
        if os.path.isfile(portal_script):
            import portal
            sys.exit(portal.main())

    config_path = resolve_config(args.config)
    config_dir = os.path.dirname(os.path.abspath(config_path))
    with open(config_path, "r") as handle:
        config = json.load(handle)

    routes, spec = build_routes(config, config_dir)
    if args.check:
        return check(config, routes, spec)

    # `state_dir` is what the mock writes -- its stores and its call log. A folder named in the
    # config but not yet on disk is created, so a new mock needs no mkdir before its first call.
    state_dir = os.path.join(config_dir, config.get("state_dir", "."))
    if not os.path.isdir(state_dir):
        os.makedirs(state_dir, exist_ok=True)
    state = State(config.get("stores"), state_dir)
    host = args.host or config.get("host", "127.0.0.1")
    port = args.port or int(config.get("port", 8080))

    api_log = None
    log_file = args.log or (None if args.no_log else config.get("log_file"))
    if log_file:
        api_log = ApiLog(
            os.path.normpath(log_file if os.path.isabs(log_file)
                             else os.path.join(state_dir, log_file)),
            args.log_format or config.get("log_format", "har"),
            config.get("log_redact_headers"),
            config.get("name", "mock_server"),
        )

    # Results are evidence of a run, not state the mock writes, so they are addressed from the
    # config's own folder and stay put when `state_dir` moves.
    results_dir = os.path.normpath(os.path.join(config_dir,
                                                config.get("test_results_dir", "test-results")))

    if args.reset:
        for name in (config.get("stores") or {}):
            state.reset(name)
        if api_log and os.path.exists(api_log.path):
            os.remove(api_log.path)
        if results_dir and os.path.exists(results_dir):
            shutil.rmtree(results_dir, ignore_errors=True)
        print("reset stores, call log and test results", flush=True)

    suites = resolve_suites(config, config_dir, HERE)
    theme = load_theme(config, config_dir)
    server = _Server((host, port),
                     make_handler(config, routes, state, api_log, results_dir,
                                  suites, SuiteRunner(), HERE, theme_css(theme)))
    print("%s mock running on http://%s:%d (%d routes, %d configured)"
          % (config.get("name", "Mock"), host, port, len(routes),
             sum(1 for r in routes if r.source == "config")), flush=True)
    if api_log:
        print("logging calls to %s (%s)" % (api_log.path, api_log.format), flush=True)
        print("log viewer   http://%s:%d%s"
              % (host, port, config.get("log_ui_path", "/log")), flush=True)
    print("test results http://%s:%d%s   (%d run(s), %d suite(s) runnable from the page)"
          % (host, port, config.get("test_ui_path", "/test"),
             len(all_runs(group_test_runs(results_dir, suites))), len(suites)), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
