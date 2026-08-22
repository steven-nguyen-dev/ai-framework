#!/usr/bin/env python3
"""The assertions a suite is written from, one class per kind of evidence.

Each check reads the evidence one case produced and returns `expected`, `actual` and a verdict, in
the shape `results.json` renders. A check states its expectation by naming a key in the case's
`expect` block, so seventeen cases share one checklist and differ only in numbers.

Returning None from `evaluate` drops the check for that case: an assertion about a call that was
never made says nothing, and a green row for it would be a lie.
"""


class Check(object):
    """Base class: a label, the thing being measured, and whether the result is judged.

    `label` names the assertion in words and `what` names what is counted, in full -- it is what
    the results page shows on hover, and where partner vocabulary gets spelled out. A check with
    `judged` false is reported in the case's detail block instead of counting towards the verdict.
    """

    judged = True

    def __init__(self, label, what, expect=None, value=None):
        self.label = label
        self.what = what
        # Name of the key this check reads from a case's `expect` block.
        self.expect = expect
        # Fixed expectation, for a check every case is held to identically.
        self.value = value

    def expected_for(self, case):
        if self.expect is not None:
            return case.expect.get(self.expect)
        return self.value

    def evaluate(self, case, evidence):
        raise NotImplementedError

    def result(self, expected, actual, ok):
        return {"label": self.label, "what": self.what, "expected": str(expected),
                "actual": str(actual), "ok": bool(ok)}


class ControllerStatus(Check):
    """The status the app's own endpoint returned when the case was fired.

    On an asynchronous transport this proves publication and nothing else -- what the integration
    then did is what every other check is for.
    """

    def evaluate(self, case, evidence):
        expected = self.expected_for(case)
        if expected is None or evidence.controller is None:
            return None
        actual = evidence.controller.get("controller_status")
        return self.result(expected, actual, str(actual) == str(expected))


class Calls(Check):
    """How many calls of one group this case produced."""

    def __init__(self, group, label, what, expect=None, value=None):
        Check.__init__(self, label, what, expect, value)
        self.group = group

    def evaluate(self, case, evidence):
        expected = self.expected_for(case)
        if expected is None:
            return None
        actual = len(evidence.calls.get(self.group, []))
        return self.result(expected, actual, actual == expected)


class Status(Check):
    """The HTTP status the mock answered a group of calls with.

    `which` is `first` when only the first answer carries meaning, and `all` when every answer has
    to match -- a retry that recovers on the third attempt is a different claim from one that fails
    the same way three times.
    """

    def __init__(self, group, label, what, expect=None, value=None, which="first"):
        Check.__init__(self, label, what, expect, value)
        self.group = group
        self.which = which

    def evaluate(self, case, evidence):
        expected = self.expected_for(case)
        calls = evidence.calls.get(self.group, [])
        if expected is None or not calls:
            return None
        if self.which == "all":
            got = [call.status for call in calls]
            return self.result(expected, " ".join(str(s) for s in got),
                               all(s == expected for s in got))
        return self.result(expected, calls[0].status, calls[0].status == expected)


class Marker(Check):
    """The business marker inside a response body, rather than its HTTP status.

    A partner that answers 400 for "already exists" and 400 for "your payload is wrong" is telling
    two different things with one status, and only the marker separates them. Matched case-
    insensitively as a substring, because the marker is carried inside a longer sentence.
    """

    def __init__(self, group, label, what, expect=None, value=None, fields=None):
        Check.__init__(self, label, what, expect, value)
        self.group = group
        self.fields = fields

    def evaluate(self, case, evidence):
        expected = self.expected_for(case)
        calls = evidence.calls.get(self.group, [])
        if expected is None or not calls:
            return None
        fields = self.fields or evidence.marker_fields
        seen = " ".join(marker_of(call.body, fields) for call in calls).strip()
        return self.result(expected, seen or "nothing", str(expected).lower() in seen.lower())


class Rows(Check):
    """How many database rows the case left behind.

    Dropped when the runner could not reach the database, and the case's detail block says so -- a
    missing client must never read as a pass.
    """

    def evaluate(self, case, evidence):
        expected = self.expected_for(case)
        if expected is None or evidence.rows is None:
            return None
        return self.result(expected, evidence.rows, evidence.rows == expected)


class QueueDelta(Check):
    """How far a queue grew across the whole run.

    Reported, never judged: a queue depth is a run total and cannot be attributed to one case, so
    it belongs beside the case as context rather than in its verdict.
    """

    judged = False

    def __init__(self, queue, label, what, expect=None, value=None):
        Check.__init__(self, label, what, expect, value)
        self.queue = queue

    def evaluate(self, case, evidence):
        # `expect` here says whether this case is one that should produce a message at all; the
        # number itself is the run's, so a case that expects none is not given the line.
        wanted = self.expected_for(case)
        if not wanted:
            return None
        delta = evidence.queue_delta.get(self.queue)
        if delta is None:
            return self.result("captured", "not captured (no queue connection)", False)
        return self.result(wanted, "%d message(s) across the run" % delta, True)


class Custom(Check):
    """An assertion the vocabulary above cannot state, written as a function.

    The function is handed the case and its evidence and returns `(expected, actual, ok)`, or None
    to drop the check. Reach for it when a case needs something no other case needs; a shape that
    turns up twice belongs in a class here instead.
    """

    def __init__(self, label, what, fn, expect=None, value=None):
        Check.__init__(self, label, what, expect, value)
        self.fn = fn

    def evaluate(self, case, evidence):
        outcome = self.fn(case, evidence)
        if outcome is None:
            return None
        expected, actual, ok = outcome
        return self.result(expected, actual, ok)


def marker_of(body, fields):
    """First marker present in a response body, read in the order the fields are given.

    A field name ending in `[0]` reads the first element of a list, which is where a partner that
    answers with a list of messages puts the one that matters.
    """
    if not isinstance(body, dict):
        return ""
    for field in fields:
        if field.endswith("[0]"):
            values = body.get(field[:-3]) or []
            if isinstance(values, list) and values:
                return str(values[0])
            continue
        if body.get(field):
            return str(body[field])
    return ""
