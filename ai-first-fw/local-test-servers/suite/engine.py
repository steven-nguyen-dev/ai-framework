#!/usr/bin/env python3
"""Runs a suite file: preflight, reset, fire, capture, judge, publish.

The engine owns everything that is the same for every suite and every mock, so a suite file states
only what its flow is and what has to be true afterwards. It follows the runner contract in
`TESTING.md`: results are published before the first case, each case is judged as
soon as it settles, and evidence accumulates into the run folder rather than overwriting it.
"""

import collections
import datetime
import json
import os
import re
import sys
import time

from . import evidence as evidence_module
from . import probes as probes_module
from .checks import marker_of
from .resources import Mock

# The folder a mock writes its stores and its call log into, inside the mock's own folder. It is
# the `state_dir` every config in this package declares; a mock that moves it has to say so here.
MOCK_DATA = "mock-data"


def say(message):
    """Prints a progress line, flushed.

    The /test page streams the runner's output while it goes, and Python buffers a pipe by block
    rather than by line -- unflushed, the page shows nothing at all until the run has finished.
    """
    print(message, flush=True)


class Run(object):
    """One execution of one suite: its resolved settings and the systems it reached.

    A system that could not be reached is set to None here rather than raising, and every
    assertion that needed it is dropped with `not captured` against it.
    """

    def __init__(self, suite, package, env):
        self.suite = suite
        self.package = package
        self.env = env
        self.mock = Mock(env["MOCK"], os.path.join(package, suite.mock, MOCK_DATA))
        self.mysql = None
        self.queues = None
        self.run_dir = None
        if suite.database and suite.database.client:
            self.mysql = suite.database.client(env)
        if suite.queues:
            self.queues = suite.queues
            self.queues.url = self.resolve(suite.queues.url).rstrip("/")
            self.queues.auth = self.resolve(suite.queues.auth)

    def resolve(self, template):
        """Substitutes `${NAME}` from the run's settings, leaving anything unknown as it stands."""
        def replace(match):
            return str(self.env.get(match.group(1), match.group(0)))
        return re.sub(r"\$\{([A-Z_][A-Z0-9_]*)\}", replace, str(template))


# --------------------------------------------------------------------------------- selection

def select(suite, ids=(), fast=False):
    """The cases this run fires, in declaration order.

    `--fast` drops the cases that only sit through a retry backoff, chosen by their own wait rather
    than by name -- a case that stops replaying stops being slow, and nothing has to be renamed.
    """
    chosen = []
    for case in suite.cases:
        if ids and case.id not in ids:
            continue
        if fast and case.wait > 20:
            continue
        chosen.append(case)
    return chosen


# --------------------------------------------------------------------------------- preflight

def preflight(run, say=say):
    say("== preflight")
    failed = False
    for probe in run.suite.preflight:
        status, message, extra = probe.check(run)
        say("  %-4s %s" % (status, message))
        for line in extra:
            say("       " + line)
        if status == probes_module.FAIL and getattr(probe, "required", True):
            failed = True
    return not failed


# ------------------------------------------------------------------------------------- reset

def reset(run, say=say):
    """Clears everything this run owns, so a run never inherits state from the last one."""
    say("== reset")
    if run.mock.clear_log():
        say("  mock call log cleared")
    for store in run.suite.stores:
        run.mock.empty_store(store)
    if run.suite.stores:
        say("  stores emptied: " + ", ".join(run.suite.stores))
    if run.mysql and run.suite.database and run.suite.database.reset:
        if run.mysql.run(run.suite.database.reset) is not None:
            say("  database rows cleared")
    if run.queues:
        snapshot = run.queues.snapshot()
        if snapshot is not None:
            evidence_module.write_json(os.path.join(run.run_dir, "queues-before.json"), snapshot)
            say("  queue depths captured (before)")


# -------------------------------------------------------------------------------- publishing

def publish_pending(run, cases):
    """Publishes every case `pending` before the first is fired.

    The results page follows the newest run while a suite is going, so this is what makes it track
    the live run instead of showing the last finished one.
    """
    document = {
        "name": run.suite.name,
        "at": evidence_module.now(),
        "run": os.path.basename(run.run_dir),
        "suite": run.suite.id,
        "summary": {"pending": len(cases)},
        "evidence": {"status": "run in progress"},
        "cases": [{"id": case.id, "name": case.short_name(), "shape": case.shape,
                   "expected": describe(run.suite, case), "actual": "queued", "checks": [],
                   "verdict": "pending", "note": case.note, "given": case.given,
                   "then": case.then, "detail": dict(case.detail), "calls": []}
                  for case in cases],
    }
    evidence_module.write_json(os.path.join(run.run_dir, "results.json"), document)


def mark(run, case_id, verdict, actual):
    """Moves one case to a new verdict in place, leaving the rest of the file alone."""
    path = os.path.join(run.run_dir, "results.json")
    document = evidence_module.load(path, None)
    if not document:
        return
    for case in document["cases"]:
        if case["id"] == case_id:
            case["verdict"], case["actual"] = verdict, actual
    document["summary"] = dict(collections.Counter(c["verdict"] for c in document["cases"]))
    evidence_module.write_json(path, document)


# ----------------------------------------------------------------------------------- judging

def judge(suite, run_dir, cases=None, partial=False):
    """Scores a run folder against the suite and returns the `results.json` document.

    Reads only what the folder holds, so a run can be re-judged after its expectations change --
    which is how a requirement change is checked against runs already on disk instead of re-fired.
    """
    cases = list(cases if cases is not None else suite.cases)
    run_evidence = evidence_module.RunEvidence(run_dir, suite)
    results = []

    for case in cases:
        case_evidence = run_evidence.for_case(case)
        detail = collections.OrderedDict(case.detail)

        if case_evidence.controller is None:
            # Mid-run this means "not reached yet", not "skipped" -- the difference is what makes
            # the page readable while the suite is still going.
            results.append({
                "id": case.id, "name": case.short_name(), "shape": case.shape,
                "expected": describe(suite, case),
                "actual": "queued" if partial else "not run",
                "checks": [], "verdict": "pending" if partial else "skip",
                "note": case.note, "given": case.given, "then": case.then,
                "detail": detail, "calls": [],
            })
            continue

        checks, unjudged, failures = [], [], []
        for check in list(suite.checks) + list(case.checks):
            outcome = check.evaluate(case, case_evidence)
            if outcome is None:
                continue
            if check.judged:
                checks.append(outcome)
                if not outcome["ok"]:
                    failures.append("%s: expected %s, got %s"
                                    % (outcome["label"], outcome["expected"], outcome["actual"]))
            else:
                unjudged.append((check.label, outcome["actual"]))

        if suite.database and run_evidence.rows is None:
            detail["database rows"] = "not captured (no database connection)"
        for label, value in unjudged:
            detail[label] = value

        verdict = "pass" if not failures else "fail"
        if verdict == "pass" and case.blocked_when and case.blocked_when.when(run_evidence):
            verdict = "blocked"
            reason = case.blocked_when.reason
            detail["known gap"] = reason(run_evidence) if callable(reason) else reason

        results.append({
            "id": case.id, "name": case.short_name(), "shape": case.shape,
            "expected": describe(suite, case),
            "actual": ", ".join(failures) if failures else summarise(suite, case_evidence),
            "summary": summarise(suite, case_evidence),
            "checks": checks,
            "verdict": verdict,
            # Why the case exists, what it is handed, and what it has to prove. A reader arriving at
            # a red row needs the input and the criteria, not only the numbers that missed.
            "note": case.note, "given": case.given, "then": case.then,
            "detail": detail,
            # The checks are the call sequence, so a second list of the same calls says nothing new.
            # The rule each call matched stays in the folder's mock-log.json and on /log.
            "calls": [],
        })

    fired = run_evidence.fired
    document = {
        "name": suite.name,
        "at": (fired[0]["fired_at"] if fired else None),
        "run": os.path.basename(run_dir.rstrip("/")),
        # The folder this run sits in is what groups it on the page; recording the id as well means
        # a folder that gets moved can still say which suite produced it.
        "suite": run_evidence.meta.get("suite") or suite.id,
        "summary": dict(collections.Counter(r["verdict"] for r in results)),
        "evidence": run_evidence_lines(suite, run_evidence, partial),
        "cases": results,
    }
    return document


def run_evidence_lines(suite, run_evidence, partial):
    lines = collections.OrderedDict()
    lines["status"] = "run in progress" if partial else "complete"
    lines["mock log"] = run_evidence.describe_log()
    if suite.database:
        lines["database"] = "captured" if run_evidence.rows is not None else "not captured"
    if suite.queues:
        for name in suite.queues.watch:
            delta = run_evidence.queue_delta.get(name)
            lines["%s delta" % name] = "not captured" if delta is None else delta
    for key, value in (run_evidence.meta.get("settings") or {}).items():
        lines[key] = value
    return lines


def describe(suite, case):
    """The case's expectations on one line, in the words its own checks use.

    Only the expectations the case states itself. A check every case is held to identically says
    nothing about this one, and the breakdown in `checks` carries it anyway.
    """
    bits = []
    for check in list(suite.checks) + list(case.checks):
        expected = check.expected_for(case)
        if expected is None or not check.judged or check.expect is None:
            continue
        bits.append("%s: %s" % (check.label, expected))
    return " · ".join(bits)


def summarise(suite, case_evidence):
    """What the case actually did, in words, for the one line a passing case is worth.

    Every check still ships in `checks`; this is the collapsed form. A marker is folded in only
    when it is a short code like `New` or `BESO05` -- a 500's error sentence belongs in the
    breakdown, not in a summary line seventeen of which have to be scannable side by side.
    """
    bits = []
    for group in suite.groups:
        calls = case_evidence.calls.get(group.name, [])
        if not calls:
            bits.append("no %s call" % group.label)
            continue
        statuses = sorted({str(call.status) for call in calls})
        marker = marker_of(calls[0].body, case_evidence.marker_fields)
        bits.append("%d %s → %s%s"
                    % (len(calls), group.plural if len(calls) > 1 else group.label,
                       "/".join(statuses), " " + marker if marker and len(marker) <= 12 else ""))
    if suite.database:
        bits.append("database not captured" if case_evidence.rows is None
                    else "%d row%s" % (case_evidence.rows,
                                       "" if case_evidence.rows == 1 else "s"))
    return " · ".join(bits)


# ------------------------------------------------------------------------------------ firing

def fire(run, cases, say=say):
    say("== firing %d case(s)" % len(cases))
    for case in cases:
        mark(run, case.id, "running", "firing…")
        payload = case.payload
        if run.suite.prepare:
            payload = run.suite.prepare(payload, run.env)
        # The payload is kept as sent, not as it sits in the suite file, so the folder holds what
        # this run actually posted after every setting was applied.
        evidence_module.write_json(os.path.join(run.run_dir, "sent-%s.json" % case.id), payload)

        fired_at = evidence_module.now()
        status, body = run.suite.fire.send(run.resolve(run.suite.fire.url), payload)
        returned_at = evidence_module.now()
        say("  %-4s %-6s http %-4s %s" % (case.id, case.shape, status, case.name))

        path = os.path.join(run.run_dir, "controller-responses.json")
        responses = evidence_module.load(path, []) or []
        responses.append({"id": case.id, "name": case.name, "controller_status": status,
                          "controller_body": body, "fired_at": fired_at,
                          "returned_at": returned_at})
        evidence_module.write_json(path, responses)

        if case.wait > 20:
            mark(run, case.id, "running",
                 "controller %s — waiting %ds for the retry backoff" % (status, case.wait))
            say("       waiting %ds for the retry backoff to finish..." % case.wait)
        time.sleep(case.wait)

        # Judged now rather than at the end, so the page shows a real pass or fail as it goes.
        # Re-judging every fired case each time is idempotent and costs nothing at this scale.
        snapshot(run)
        document = judge(run.suite, run.run_dir, cases, partial=True)
        evidence_module.write_json(os.path.join(run.run_dir, "results.json"), document)
        verdict = next((c["verdict"] for c in document["cases"] if c["id"] == case.id), "?")
        say("       -> %s" % verdict)


def snapshot(run):
    """Unions the mock's evidence into the run folder and re-dumps the database."""
    evidence_module.capture(run.run_dir, run.mock, run.suite.stores)
    if run.mysql and run.suite.database:
        dump = run.mysql.run(run.suite.database.dump, headers=True)
        if dump is not None:
            with open(os.path.join(run.run_dir, run.suite.database.file), "w") as handle:
                handle.write(dump)


# -------------------------------------------------------------------------------------- main

def execute(suite, package, env, ids=(), fast=False, say=say):
    """Fires a suite end to end and returns its exit status."""
    cases = select(suite, ids, fast)
    if not cases:
        say("NOTHING TO FIRE -- every case was filtered out.")
        say("  valid ids: " + " ".join(case.id for case in suite.cases))
        return 1

    run = Run(suite, package, env)
    if not preflight(run, say):
        say("preflight failed, nothing run")
        return 1

    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    run.run_dir = os.path.join(package, suite.mock, "test-results", suite.id,
                               "run-" + stamp)
    os.makedirs(run.run_dir)
    evidence_module.write_json(os.path.join(run.run_dir, "meta.json"),
                               {"suite": suite.id, "mock": suite.mock,
                                "settings": {key: env[key] for key in sorted(env)
                                             if key not in ("CORE_JSON",)}})
    reset(run, say)
    publish_pending(run, cases)
    fire(run, cases, say)

    say("== snapshot")
    time.sleep(3)
    snapshot(run)
    if run.queues:
        after = run.queues.snapshot()
        if after is not None:
            evidence_module.write_json(os.path.join(run.run_dir, "queues-after.json"), after)

    say("== judge")
    document = judge(suite, run.run_dir, cases)
    evidence_module.write_json(os.path.join(run.run_dir, "results.json"), document)
    report(document, say)
    say("")
    say("results:  %s/test" % run.mock.url)
    say("folder:   %s" % os.path.relpath(run.run_dir, package))
    return 0 if not document["summary"].get("fail") else 2


def rejudge(suite, run_dir, say=say):
    """Re-scores a folder already on disk, without firing anything."""
    document = judge(suite, run_dir)
    evidence_module.write_json(os.path.join(run_dir, "results.json"), document)
    report(document, say)
    return 0 if not document["summary"].get("fail") else 2


def report(document, say=say):
    say("  " + "  ".join("%s=%d" % pair for pair in sorted(document["summary"].items())))
    for case in document["cases"]:
        if case["verdict"] != "pass":
            say("  %-4s %-8s %s" % (case["id"], case["verdict"], case["actual"]))


def settings(suite):
    """The suite's declared defaults, with the environment winning."""
    resolved = dict(suite.env)
    for key in list(resolved):
        if os.environ.get(key):
            resolved[key] = os.environ[key]
    return resolved
