#!/usr/bin/env python3
"""Preflight: everything checked before the first case is fired.

A missing seed row or a mock that is not running produces an identical failure in every case and
tells you nothing about the integration. A probe that names it takes a second, so preflight is
loud, runs first, and a failed requirement stops the run before a results folder exists.
"""

import os

from . import resources


OK, WARN, FAIL = "ok", "WARN", "FAIL"


class Probe(object):
    """One preflight condition. `required` decides whether failing it stops the run."""

    required = True

    def check(self, run):
        raise NotImplementedError


class AppResponds(Probe):
    """The app under test answers at all.

    Any status counts, including a rejection: the probe asks whether something is listening, and a
    400 to an empty body proves that better than a 200 would.
    """

    def __init__(self, path, method="POST", body=None, required=True):
        self.path = path
        self.method = method
        self.body = {} if body is None else body
        self.required = required

    def check(self, run):
        url = run.resolve(self.path)
        status = resources.probe_url(url, self.method, self.body, verify_tls=False)
        if status == 0:
            return FAIL, "app not reachable at %s" % url, []
        return OK, "app responds at %s (probe returned %s)" % (url, status), []


class MockResponds(Probe):
    """The mock is up and serving its call log, which every assertion is read from."""

    def check(self, run):
        if run.mock.log() is None:
            return (FAIL, "mock not reachable at %s -- start it: python3 mock.py %s"
                    % (run.mock.url, run.suite.mock), [])
        return OK, "mock log endpoint at %s" % run.mock.url, []


class DatabaseResponds(Probe):
    """The database the app writes to is reachable. Not required: its assertions drop instead."""

    required = False

    def check(self, run):
        if run.mysql is None or not run.mysql.available():
            run.mysql = None
            return WARN, "mysql not reachable -- database checks will read 'not captured'", []
        return OK, "mysql reachable (%s)" % run.mysql.database, []


class SeedRows(Probe):
    """A fixture the app reads before it can call the partner at all.

    When it is missing, the same query is run against every other database on the server and the
    ones holding it are named -- the usual cause is an app pointed at a different schema than the
    suite, and the fix is a setting, not a seed load.
    """

    def __init__(self, label, query, at_least=1, hint="", diagnose=True):
        self.label = label
        self.query = query
        self.at_least = at_least
        self.hint = hint
        self.diagnose = diagnose

    def check(self, run):
        if run.mysql is None:
            return WARN, "%s not checked -- no mysql" % self.label, []
        found = run.mysql.count(self.query)
        if found is not None and found >= self.at_least:
            return OK, "%s present in %s (%d)" % (self.label, run.mysql.database, found), []
        lines = []
        if self.diagnose:
            for database in run.mysql.databases():
                if database == run.mysql.database:
                    continue
                elsewhere = run.mysql.count(self.query, database)
                if elsewhere and elsewhere >= self.at_least:
                    lines.append("the fixture IS in '%s' -- rerun with:  DB_NAME=%s"
                                 % (database, database))
        if self.hint:
            lines.append(run.resolve(self.hint))
        return FAIL, "%s missing from '%s' (found %s)" % (self.label, run.mysql.database,
                                                          "0" if found is None else found), lines


class QueuesRespond(Probe):
    """The queue broker's management API. Not required: queue lines read `not captured` instead."""

    required = False

    def check(self, run):
        if run.queues is None or run.queues.snapshot() is None:
            run.queues = None
            return WARN, "queue management API unreachable -- queue lines will read 'not captured'", []
        return OK, "queue management API at %s" % run.queues.url, []


class FileExists(Probe):
    """A file the run cannot proceed without, named so its absence is not a stack trace."""

    def __init__(self, path, why="", required=True):
        self.path = path
        self.why = why
        self.required = required

    def check(self, run):
        path = run.resolve(self.path)
        if os.path.exists(path):
            return OK, "found %s" % path, []
        return FAIL, "missing %s%s" % (path, " -- " + self.why if self.why else ""), []
