#!/usr/bin/env python3
"""What a suite file declares: the suite, its cases, and the call groups they are judged against.

Data only. Nothing here reaches the network, the database or the disk -- the engine does that, and
keeps a suite file readable as a statement of what the flow is supposed to do.
"""

import copy
import fnmatch
import re
try:
    from urllib.parse import urlsplit
except ImportError:                                              # pragma: no cover - python 2
    from urlparse import urlsplit


class _Delete(object):
    """Marker a payload override uses to drop a key the base payload carries."""

    def __repr__(self):
        return "DELETE"


DELETE = _Delete()


def merge(base, override):
    """Deep copy of `base` with `override` applied: dictionaries merge, everything else replaces.

    A list replaces rather than extends, because a case that states `order_items` means those items
    and not those items appended to the base's. `DELETE` as a value removes the key entirely, which
    is how a case says "this order carries no pricing block".
    """
    if isinstance(base, dict) and isinstance(override, dict):
        merged = copy.deepcopy(base)
        for key, value in override.items():
            if value is DELETE:
                merged.pop(key, None)
            elif key in merged:
                merged[key] = merge(merged[key], value)
            else:
                merged[key] = copy.deepcopy(value)
        return merged
    return copy.deepcopy(override)


class Group(object):
    """One kind of call the suite counts, named so a case can state how many it expects.

    `path` is matched with `fnmatch` against the URL path alone, so `/api/v0.2/saleorders/*/
    priceDetail` covers every sale order code without a regex in the suite file.
    """

    def __init__(self, name, method, path, label=None, plural=None):
        self.name = name
        self.method = method.upper()
        self.path = path
        # The word the one-line summary uses. Eton's pricing calls read better as "push" than as
        # "pricing", and only the summary cares.
        self.label = label or name
        self.plural = plural or (self.label + "es" if self.label.endswith(("s", "sh", "ch", "x"))
                                 else self.label + "s")

    def matches(self, call):
        if call.method != self.method:
            return False
        return fnmatch.fnmatchcase(call.path, self.path)


class Call(object):
    """One logged call to the mock, in the shape the checks read."""

    def __init__(self, entry):
        request = entry.get("request") or {}
        response = entry.get("response") or {}
        self.method = (request.get("method") or "").upper()
        self.url = request.get("url") or ""
        self.path = urlsplit(self.url).path
        self.request_body = request.get("body")
        self.status = response.get("status")
        self.body = response.get("body")
        self.rule = entry.get("rule")
        self.at = entry.get("at") or entry.get("startedDateTime") or ""


def key_from(url=None, skip=(), body=()):
    """Builds the function that says which case a logged call belongs to.

    A case is identified by a value the client already sends, so no correlation header has to be
    invented and a replay 30 seconds later still lands on the right case. Reads the first capturing
    group of `url` when it matches and is not in `skip`, otherwise the first present field of
    `body`.
    """
    pattern = re.compile(url) if url else None

    def resolve(call):
        if pattern:
            found = pattern.search(call.url)
            if found and found.group(1) not in skip:
                return str(found.group(1))
        payload = call.request_body if isinstance(call.request_body, dict) else {}
        for field in body:
            if payload.get(field) not in (None, ""):
                return str(payload[field])
        return ""

    return resolve


class Blocked(object):
    """Why a case cannot prove its last assertion under the conditions this run was given.

    A verdict of `blocked` is not `fail`: `TESTING.md` keeps them apart so a documented gap is never
    read as a regression. Applied only to a case that would otherwise pass.
    """

    def __init__(self, when, reason):
        self.when = when
        self.reason = reason


class Case(object):
    """One case: what is sent, how long the flow needs, and what has to be true afterwards.

    `key` ties the mock's calls to this case and `row_key` its database rows; both default to the
    identifier the payload carries. `expect` holds the numbers the suite's checks read by name, so
    a requirement change is an edit to this block and nothing else.
    """

    def __init__(self, id, name, payload=None, key=None, row_key=None, expect=None, shape="",
                 wait=0, checks=(), given="", then=(), note="", detail=None, blocked_when=None):
        self.id = id
        self.name = name
        self.payload = payload or {}
        self.key = str(key) if key is not None else ""
        self.row_key = str(row_key) if row_key is not None else self.key
        self.expect = expect or {}
        self.shape = shape
        self.wait = wait
        # Appended after the suite's own checklist, for an assertion only this case makes.
        self.checks = list(checks)
        self.given = given
        self.then = list(then)
        self.note = note
        self.detail = dict(detail or {})
        self.blocked_when = blocked_when

    def short_name(self):
        """Drops the `N1. ` a case name carries -- the results table already has an ID column."""
        prefix = self.id + ". "
        return self.name[len(prefix):] if self.name.startswith(prefix) else self.name


class Suite(object):
    """A whole suite: how a case is fired, what evidence is captured, and how a case is judged.

    One instance per suite file, named `SUITE`. `id` is also the folder its runs are grouped under
    on the mock's `/test` page, so it has to match a `test_suites[].id` in the mock config.
    """

    def __init__(self, id, name, mock, cases, fire, groups=(), call_key=None, checks=(),
                 description="", env=None, preflight=(), reset=(), stores=(), database=None,
                 queues=None, prepare=None, marker_fields=("Status", "ErrorCode",
                                                           "ErrorMessages[0]")):
        self.id = id
        self.name = name
        self.mock = mock
        self.cases = list(cases)
        self.fire = fire
        self.groups = list(groups)
        self.call_key = call_key or key_from()
        # The checklist every case is judged by, in the order the flow happens. A check whose
        # expectation is absent from a case is dropped for that case rather than failed.
        self.checks = list(checks)
        self.description = description
        # Defaults for the settings a run can override from the environment.
        self.env = dict(env or {})
        self.preflight = list(preflight)
        self.reset = list(reset)
        # Mock store files emptied before a run and captured into the run folder afterwards.
        self.stores = list(stores)
        self.database = database
        self.queues = queues
        # Last chance to rewrite a payload before it is sent, given the resolved settings.
        self.prepare = prepare
        self.marker_fields = tuple(marker_fields)

    def group(self, name):
        for group in self.groups:
            if group.name == name:
                return group
        raise KeyError("no call group named %r in suite %s" % (name, self.id))

    def case(self, case_id):
        for case in self.cases:
            if case.id == case_id:
                return case
        raise KeyError("no case %r in suite %s" % (case_id, self.id))
