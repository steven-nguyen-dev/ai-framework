#!/usr/bin/env python3
"""The systems a suite touches: the app under test, the mock, its database and its queues.

Everything here is optional. A suite that drives a mock alone declares no database and no queues,
and the engine records what it could not reach as `not captured` rather than letting a missing
client read as a pass.
"""

import base64
import json
import os
import subprocess
import urllib.request

try:
    from urllib.error import HTTPError, URLError
except ImportError:                                              # pragma: no cover - python 2
    from urllib2 import HTTPError, URLError


# --------------------------------------------------------------------------------- the app

class PostJson(object):
    """Fires one case as a JSON POST to the app, and records what came back.

    On an asynchronous transport the status this returns means published, never succeeded, which is
    why a case also carries a wait and every other assertion is made against the mock.
    """

    def __init__(self, url, timeout=30, headers=None, verify_tls=False):
        self.url = url
        self.timeout = timeout
        self.headers = dict(headers or {"Content-Type": "application/json"})
        # A local app serves HTTPS with a self-signed certificate, so verification is off by
        # default; a suite pointed at anything shared should turn it back on.
        self.verify_tls = verify_tls

    def send(self, url, payload):
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(url, data=body, method="POST")
        for name, value in self.headers.items():
            request.add_header(name, value)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout,
                                        context=_tls_context(self.verify_tls)) as response:
                return response.status, response.read().decode("utf-8", "replace")
        except HTTPError as error:
            return error.code, error.read().decode("utf-8", "replace")
        except Exception as error:
            return 0, str(error)


def _tls_context(verify):
    import ssl
    if verify:
        return ssl.create_default_context()
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context


def probe_url(url, method="GET", body=None, timeout=5, verify_tls=False):
    """The status a URL answers with, or 0 when nothing answered at all."""
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=timeout,
                                    context=_tls_context(verify_tls)) as response:
            return response.status
    except HTTPError as error:
        return error.code
    except Exception:
        return 0


# ---------------------------------------------------------------------------- the database

class Sql(object):
    """What the suite reads out of the database, and what it clears before a run.

    `dump` is run after every case and written to `file`; `key_column` says which column names the
    case a row belongs to, so rows can be counted per case without a query per case.
    """

    def __init__(self, dump, client=None, file="rows.tsv", key_column=0, reset=None):
        self.dump = dump
        # Builds the client from the run's settings, so the suite reads the same connection the
        # app does instead of carrying its own copy of the credentials.
        self.client = client
        self.file = file
        self.key_column = key_column
        self.reset = reset


class MySql(object):
    """A MySQL client, reached locally or through a container, or absent.

    Absent is a first-class state: the engine keeps running and every database assertion is dropped
    with `not captured` against it, because a suite that silently skipped them would report green.
    """

    def __init__(self, host, port, user, password, database, container=None):
        self.host = host
        self.port = str(port)
        self.user = user
        self.password = password
        self.database = database
        self.container = container

    @classmethod
    def from_json(cls, path, database, url_key="integration.db.url",
                  user_key="integration.db.username", password_key="integration.db.password",
                  container="mysql"):
        """Reads host, port and credentials out of the app's own connection settings file.

        The suite must read the same settings the app does; a suite carrying its own copy drifts
        and then reports rows missing from a database nothing ever wrote to.
        """
        try:
            with open(path) as handle:
                document = json.load(handle)
        except Exception:
            return None
        url = str(document.get(url_key) or "")
        if not url:
            return None
        host, _, port = url.partition(":")
        return cls(host, port or "3306", document.get(user_key), document.get(password_key),
                   database, container)

    def command(self, database=None):
        if self.container is not None and not _has_local_mysql():
            return ["docker", "exec", "-i", self.container, "mysql",
                    "-u", self.user, "-p" + self.password] + ([database] if database else [])
        return (["mysql", "-h", self.host, "-P", self.port, "-u", self.user,
                 "-p" + self.password] + ([database] if database else []))

    def run(self, sql, database=None, headers=False):
        """Runs one statement and returns its output, or None when the client is unreachable.

        stdin is closed for the child on purpose. `docker exec -i` attaches stdin and swallows
        whatever is left of it, which is how a runner looping over a plan file used to stop after
        its first case with every other one reported not run.
        """
        flags = ["-B"] if headers else ["-N", "-B"]
        argv = self.command(database or self.database) + flags + ["-e", sql]
        try:
            done = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  stdin=subprocess.DEVNULL, timeout=30)
        except Exception:
            return None
        if done.returncode != 0:
            return None
        return done.stdout.decode("utf-8", "replace")

    def available(self):
        return self.run("SELECT 1") is not None

    def count(self, sql, database=None):
        output = self.run(sql, database)
        if output is None:
            return None
        first = output.strip().split("\n")[0] if output.strip() else "0"
        try:
            return int(first.split("\t")[0])
        except ValueError:
            return None

    def databases(self):
        output = self.run("SHOW DATABASES", database="")
        if output is None:
            return []
        skip = ("information_schema", "mysql", "performance_schema", "sys")
        return [line.strip() for line in output.split("\n")
                if line.strip() and line.strip() not in skip]


_LOCAL_MYSQL = None


def _has_local_mysql():
    global _LOCAL_MYSQL
    if _LOCAL_MYSQL is None:
        try:
            _LOCAL_MYSQL = subprocess.run(["which", "mysql"], stdout=subprocess.DEVNULL,
                                          stderr=subprocess.DEVNULL,
                                          stdin=subprocess.DEVNULL).returncode == 0
        except Exception:
            _LOCAL_MYSQL = False
    return _LOCAL_MYSQL


# ------------------------------------------------------------------------------- the queues

class Queues(object):
    """The RabbitMQ management API, and the queues whose depth a run compares before and after."""

    def __init__(self, url, auth="guest:guest", watch=()):
        self.url = url.rstrip("/")
        self.auth = auth
        self.watch = list(watch)

    def snapshot(self):
        """Every queue and its depth, or None when the management API cannot be reached."""
        request = urllib.request.Request(self.url + "/api/queues")
        token = base64.b64encode(self.auth.encode("utf-8")).decode("ascii")
        request.add_header("Authorization", "Basic " + token)
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception:
            return None

    @staticmethod
    def depth(snapshot, name):
        if not isinstance(snapshot, list):
            return None
        for queue in snapshot:
            if queue.get("name") == name:
                return queue.get("messages", 0) or 0
        return 0


# -------------------------------------------------------------------------------- the mock

class Mock(object):
    """The mock server: its call log, its HAR archive and its state stores.

    The log and the stores are global and stay mutable while the mock is up, so the engine unions
    them into the run folder rather than copying over it. See `evidence.py`.
    """

    def __init__(self, url, directory, log_file="api-calls.har.json"):
        # `directory` is the mock's data folder -- the `state_dir` its config declares, holding the
        # stores and the HAR archive. Run folders live beside it, not in it.
        self.url = url.rstrip("/")
        self.directory = directory
        self.log_file = log_file

    def log(self):
        try:
            with urllib.request.urlopen(self.url + "/log/data", timeout=15) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception:
            return None

    def clear_log(self):
        request = urllib.request.Request(self.url + "/log/data", method="DELETE")
        try:
            urllib.request.urlopen(request, timeout=10).read()
            return True
        except Exception:
            return False

    def empty_store(self, name):
        path = os.path.join(self.directory, name + ".json")
        try:
            with open(path, "w") as handle:
                handle.write("[]\n")
            return True
        except Exception:
            return False
