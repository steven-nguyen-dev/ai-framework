#!/usr/bin/env python3
"""
Tests for the testbed tools against a fake portal (contracts/testbed-api.yaml subset) on 127.0.0.1.

No cloud and no MCP runtime: `tools.py` imports neither. The engine is a fake `.venv/bin/python`
shell script. Run with:
    python3 -m unittest testbed/test_server.py      (from lv1-mcp/)
"""

import hashlib
import json
import os
import stat
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from testbed import tools  # noqa: E402
from testbed.config import Config  # noqa: E402

TOKEN = "s3cret-admin-token"
PATH_KEY = "pk-0123456789"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class FakePortal:
    """In-memory portal: live mock content, lease, stores, call log; records every request."""

    def __init__(self):
        self.live = {}  # "external/fake/<rel>" -> bytes
        self.lease = None  # {"lease_id", "owner", "purpose"}
        self.requests = []
        self.uploads = {}
        self.stores = {"orders": []}
        self.log = []
        portal = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _reply(self, status, body=None):
                raw = b"" if body is None else json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def _handle(self):
                length = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(length) if length else b""
                portal.requests.append((self.command, self.path, dict(self.headers)))
                if self.headers.get("X-Auth-Token") != TOKEN:
                    return self._reply(401, {"error": {"code": "unauthorized", "message": "no"}})
                status, payload = portal.route(self.command, self.path, body, self.headers)
                self._reply(status, payload)

            do_GET = do_POST = do_PUT = do_DELETE = _handle

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = "http://127.0.0.1:%d" % self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()

    def _guarded(self, headers):
        if self.lease and headers.get("X-Testbed-Lease") != self.lease["lease_id"]:
            return 409, {"error": {"code": "lease_held", "message": "held",
                                   "details": {"owner": self.lease["owner"]}}}
        return None

    def route(self, method, path, body, headers):
        route, _, query = path.partition("?")
        cp = "external/fake"
        if route == "/api/servers":
            return 200, [{"key": "fake", "name": "Fake", "prefix": "/fake", "content_path": cp,
                          "status": "running", "pushed": {"by": "dev", "commit": "abc"}}]
        if route == "/api/lease":
            if method == "GET":
                if not self.lease:
                    return 200, {"held": False}
                return 200, {"held": True, "lease": {k: v for k, v in self.lease.items() if k != "lease_id"}}
            if method == "POST":
                req = json.loads(body)
                if self.lease and req.get("lease_id") != self.lease["lease_id"]:
                    return 409, {"error": {"code": "lease_held", "message": "held"}}
                self.lease = {"lease_id": "L1", "owner": req["owner"], "purpose": req.get("purpose"),
                              "expires_at": "2099-01-01T00:00:00Z"}
                return 200, dict(self.lease, ttl_s=1800)
            self.lease = None
            return 204, None
        if route == "/api/content/mocks/files":
            return 200, [{"path": p, "sha256": sha(d), "size": len(d), "mtime": "x"} for p, d in self.live.items()]
        if route == "/api/mocks/fake/uploads" and method == "POST":
            self.uploads["U1"] = {p[len(cp) + 1:]: d for p, d in self.live.items()}
            return 200, {"upload_id": "U1", "mock": "fake",
                         "base": [{"path": p, "sha256": sha(d), "size": 1, "mtime": "x"}
                                  for p, d in self.uploads["U1"].items()]}
        if route == "/api/mocks/fake/uploads/U1/batch":
            req = json.loads(body)
            import base64
            for path in req.get("delete", []):
                self.uploads["U1"].pop(path, None)
            for entry in req.get("files", []):
                self.uploads["U1"][entry["path"]] = base64.b64decode(entry["content_b64"])
            return 200, {"written": [], "deleted": req.get("delete", [])}
        if route == "/api/mocks/fake/uploads/U1/apply":
            denied = self._guarded(headers)
            if denied:
                return denied
            self.live = {"%s/%s" % (cp, p): d for p, d in self.uploads["U1"].items()}
            return 200, {"mock": "fake", "status": "running", "changed": sorted(self.uploads["U1"])}
        if route == "/fake/__testbed/stores":
            return 200, sorted(self.stores)
        if route == "/fake/__testbed/stores/orders":
            if method == "PUT":
                self.stores["orders"] = json.loads(body)
                return 204, None
            return 200, self.stores["orders"]
        if route == "/fake/__testbed/health":
            return 200, {"mock": "fake", "ok": True}
        if route == "/fake/log/data":
            return 200, {"name": "fake", "server_time": "t", "last_seq": len(self.log), "entries": self.log}
        return 404, {"error": {"code": "not_found", "message": route}}


ENGINE = r"""#!/bin/sh
# Fake engine: proves which secrets arrive, prints the run folder line, writes results.json.
echo "admin=${ADMIN_PASSWORD:-unset} key=${PATH_KEY:-unset} token=${TESTBED_API_TOKEN:-unset}"
case "$*" in
  *--validate*) echo "valid"; exit 0 ;;
esac
RUN="$FAKE_RESULTS/run-1"
mkdir -p "$RUN"
echo "  results: $RUN"
echo '{"name":"S","summary":{"pass":1},"cases":[{"id":"C1","verdict":"pass","name":"one"}]}' > "$RUN/results.json"
echo '{"exit":0,"finished":"now"}' > "$RUN/run.json"
sleep "${FAKE_SLEEP:-0}"
exit 0
"""


class Base(unittest.TestCase):
    def setUp(self):
        self.portal = FakePortal()
        self.addCleanup(self.portal.close)
        self.tmp = Path(tempfile.mkdtemp())
        root = self.tmp / "lv1-servers"
        suite = root / "testbed-dev" / "suites" / "external" / "fake" / "v1"
        suite.mkdir(parents=True)
        (suite / "integration.json").write_text(json.dumps({"mock": "fake", "content_path": "external/fake"}))
        (suite / "a.case.yaml").write_text("x: 1\n")
        self.content = root / "cloud-servers" / "mock-api" / "mocks" / "external" / "fake"
        (self.content / "secrets").mkdir(parents=True)
        (self.content / "same.json").write_text("same")
        (self.content / "changed.json").write_text("new")
        (self.content / "added.yaml").write_text("added")
        (self.content / "secrets" / "x.json").write_text("no")
        (self.content / "cert.p12").write_text("no")
        self.portal.live = {"external/fake/same.json": b"same", "external/fake/changed.json": b"old",
                            "external/fake/gone.json": b"gone"}
        venv = root / "testbed-dev" / ".venv" / "bin"
        venv.mkdir(parents=True)
        (venv / "python").write_text(ENGINE)
        (venv / "python").chmod(0o755)
        (root / "testbed-dev" / "suite").mkdir()
        (root / "testbed-dev" / "suite" / "cli.py").write_text("")
        os.environ["FAKE_RESULTS"] = str(self.tmp / "results")
        self.config = Config(host=self.portal.url, token=TOKEN, path_key=PATH_KEY, servers_root=root,
                             jpluger_root=self.tmp / "jp", data_dir=self.tmp / "data")

    def assertNoSecret(self, result):
        text = json.dumps(result)
        self.assertNotIn(TOKEN, text)
        self.assertNotIn(PATH_KEY, text)


class MocksTest(Base):
    def test_diff_reports_added_changed_deleted_and_skips_forbidden(self):
        r = tools.mocks_diff(self.config, "fake")
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["added"], ["added.yaml"])
        self.assertEqual(r["changed"], ["changed.json"])
        self.assertEqual(r["deleted"], ["gone.json"])
        self.assertEqual(r["counts"]["unchanged"], 1)
        self.assertIn("cert.p12", r["skipped"])
        self.assertIn("secrets/x.json", r["skipped"])

    def test_push_uploads_applies_and_releases_lease(self):
        r = tools.mocks_push(self.config, "fake")
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["status"], "running")
        self.assertEqual(sorted(self.portal.live),
                         ["external/fake/added.yaml", "external/fake/changed.json", "external/fake/same.json"])
        self.assertIsNone(self.portal.lease)
        self.assertNoSecret(r)
        again = tools.mocks_diff(self.config, "fake")
        self.assertEqual(again["counts"]["changed"] + again["counts"]["added"] + again["counts"]["deleted"], 0)

    def test_push_up_to_date_takes_no_lease(self):
        tools.mocks_push(self.config, "fake")
        self.portal.requests.clear()
        r = tools.mocks_push(self.config, "fake")
        self.assertEqual(r["status"], "up_to_date")
        self.assertFalse([p for m, p, _ in self.portal.requests if m == "POST" and p.startswith("/api/lease")])

    def test_push_refused_while_lease_held_names_holder(self):
        self.portal.lease = {"lease_id": "X", "owner": "someone@box", "purpose": "suite fake/a"}
        r = tools.mocks_push(self.config, "fake")
        self.assertFalse(r["ok"])
        self.assertEqual(r["error"]["code"], "busy")
        self.assertIn("someone@box", r["error"]["message"])
        self.assertIn("external/fake/gone.json", self.portal.live)

    def test_unknown_mock_has_no_content_path(self):
        r = tools.mocks_diff(self.config, "nope")
        self.assertEqual(r["error"]["code"], "not_found")

    def test_status_and_stores(self):
        r = tools.mocks_status(self.config, "fake")
        self.assertTrue(r["ok"] and r["health"]["ok"], r)
        self.assertTrue(tools.stores_put(self.config, "fake", "orders", [1, 2])["ok"])
        self.assertEqual(tools.stores_get(self.config, "fake", "orders")["value"], [1, 2])
        self.assertEqual(tools.stores_put(self.config, "fake", "orders", [], "bogus")["error"]["code"], "validation")

    def test_call_log_masks_secrets(self):
        self.portal.log = [{"_seq": 1, "request": {"url": "https://h/k/%s/fake/x" % PATH_KEY,
                                                   "headers": [{"name": "x-auth-token", "value": TOKEN}]},
                            "response": {"content": {"text": "echo " + TOKEN}}}]
        r = tools.call_log(self.config, "fake")
        self.assertTrue(r["ok"], r)
        self.assertNoSecret(r)
        self.assertIn("/k/<redacted>/", json.dumps(r))

    def test_wrong_token_is_an_error_envelope(self):
        config = Config(**{**self.config.__dict__, "token": "wrong"})
        r = tools.mocks_status(config)
        self.assertEqual(r["error"]["status"], 401)


class EngineTest(Base):
    def _wait(self, run_id):
        for _ in range(100):
            r = tools.run_status(self.config, run_id)
            if r["state"] != "running":
                return r
            time.sleep(0.05)
        self.fail("run did not finish")

    def test_offline_validate_gets_no_secrets(self):
        r = tools.suite_validate(self.config, ["suites/external/fake/v1/a.case.yaml"])
        self.assertTrue(r["ok"] and r["passed"], r)
        self.assertIn("admin=unset key=unset token=unset", r["output"])

    def test_run_start_injects_secrets_masks_output_and_reports_result(self):
        r = tools.run_start(self.config, "suites/external/fake/v1/a.case.yaml")
        self.assertTrue(r["ok"], r)
        status = self._wait(r["run_id"])
        self.assertEqual((status["state"], status["exit_code"]), ("finished", 0), status)
        # Secrets arrived (masked in output) under the engine's names, not the MCP's.
        self.assertIn("admin=<redacted> key=<redacted> token=unset", status["output_tail"])
        self.assertNoSecret(status)
        result = tools.run_result(self.config, r["run_id"])
        self.assertEqual(result["cases"], [{"id": "C1", "verdict": "pass", "name": "one", "detail": None}])
        self.assertEqual([x["run_id"] for x in tools.run_list(self.config)["runs"]], [r["run_id"]])

    def test_run_start_refused_while_lease_held(self):
        self.portal.lease = {"lease_id": "X", "owner": "other@box", "purpose": "suite"}
        r = tools.run_start(self.config, "suites/external/fake/v1/a.case.yaml")
        self.assertEqual(r["error"]["code"], "busy")
        self.assertIn("other@box", r["error"]["message"])
        self.assertEqual(tools.run_list(self.config)["runs"], [])

    def test_run_start_refused_while_a_run_is_active(self):
        os.environ["FAKE_SLEEP"] = "3"
        self.addCleanup(os.environ.pop, "FAKE_SLEEP", None)
        first = tools.run_start(self.config, "suites/external/fake/v1/a.case.yaml")
        self.addCleanup(lambda: tools.run_stop(self.config, first["run_id"]))
        second = tools.run_start(self.config, "suites/external/fake/v1/a.case.yaml")
        self.assertEqual(second["error"]["code"], "busy")
        self.assertIn(first["run_id"], second["error"]["message"])
        push = tools.mocks_push(self.config, "fake")
        self.assertEqual(push["error"]["code"], "busy")

    def test_unknown_run_id(self):
        self.assertEqual(tools.run_status(self.config, "nope")["error"]["code"], "not_found")
        self.assertEqual(tools.run_status(self.config, "../x")["error"]["code"], "validation")


if __name__ == "__main__":
    unittest.main()
