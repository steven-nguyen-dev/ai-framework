#!/usr/bin/env python3
"""
Tests for server.py's bsearch polling loop.

The bug these guard against: Kibana's first /internal/bsearch response for a
wide time range often carries no rawResponse at all. Returning it as-is reads
as "zero hits" -- a silent wrong answer, which is worse than an error. The
loop must keep polling until Kibana both stops reporting isRunning and has
attached a rawResponse, and must raise if that never happens.

No network: the HTTP layer is stubbed. Run with:
    python3 test_server.py
"""

import sys
import types
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# Stub the MCP SDK so the module imports without dependencies installed.
if "mcp" not in sys.modules:
    _m = types.ModuleType("mcp")
    _s = types.ModuleType("mcp.server")
    _f = types.ModuleType("mcp.server.fastmcp")

    class _FastMCP:
        def __init__(self, *a, **k):
            pass

        def tool(self, *a, **k):
            return lambda fn: fn

        def run(self, **k):
            pass

    _f.FastMCP = _FastMCP
    _s.fastmcp = _f
    _m.server = _s
    sys.modules["mcp"], sys.modules["mcp.server"], sys.modules["mcp.server.fastmcp"] = _m, _s, _f

import server  # noqa: E402


def _hits(n):
    return {"hits": {"total": {"value": n}, "hits": [{"fields": {"message": [f"log {i}"]}} for i in range(n)]}}


class _Fake:
    """Replays a scripted list of bsearch `result` payloads."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = 0

    def __call__(self, payload, cookie):
        self.calls += 1
        return {"result": self.script[min(self.calls - 1, len(self.script) - 1)]}


class PollingTests(unittest.TestCase):
    def setUp(self):
        self._cfg = server._config
        self._auth = server._authenticate
        self._ver = server._kbn_version
        self._sleep = server.time.sleep
        server._config = lambda: {
            "url": "https://kibana.test:5601", "username": "u", "password": "p",
            "static_cookie": "", "version": "8.19.18",
            "index_pattern": "logs-*", "verify_ssl": True,
        }
        server._authenticate = lambda force=False: "sid=test"
        server._kbn_version = lambda cfg: "8.19.18"
        server.time.sleep = lambda s: None

    def tearDown(self):
        server._config = self._cfg
        server._authenticate = self._auth
        server._kbn_version = self._ver
        server.time.sleep = self._sleep

    def _run(self, script, **kw):
        fake = _Fake(script)
        original = server.urllib.request.Request
        server.urllib.request.Request = lambda *a, **k: None
        try:
            import contextlib

            @contextlib.contextmanager
            def _noop(*a, **k):
                yield None

            # Patch the inner post() by swapping _open + json round trip:
            # simplest is to patch _bsearch's transport via monkeypatched urlopen.
            payloads = []

            class _Resp:
                def __init__(self, data):
                    self._data = data

                def read(self):
                    import json
                    return json.dumps(self._data).encode()

                def __enter__(self):
                    return self

                def __exit__(self, *a):
                    return False

            def _open(req, cfg, timeout=30):
                payloads.append(req)
                return _Resp(fake(None, None))

            server._open = _open
            return server._bsearch({"size": 10}, "logs-*", **kw)
        finally:
            server.urllib.request.Request = original

    def test_immediate_complete(self):
        raw = self._run([{"id": "a", "isRunning": False, "rawResponse": _hits(3)}])
        self.assertEqual(raw["hits"]["total"]["value"], 3)

    def test_empty_first_response_is_not_zero_hits(self):
        # The regression: first response has no rawResponse at all.
        raw = self._run([
            {"id": "a", "isRunning": True},
            {"id": "a", "isRunning": True},
            {"id": "a", "isRunning": False, "rawResponse": _hits(82)},
        ])
        self.assertEqual(raw["hits"]["total"]["value"], 82)

    def test_not_running_but_no_raw_still_polls(self):
        # isRunning absent AND no rawResponse must not be read as completion.
        raw = self._run([
            {"id": "a"},
            {"id": "a", "isRunning": False, "rawResponse": _hits(7)},
        ])
        self.assertEqual(raw["hits"]["total"]["value"], 7)

    def test_genuine_zero_hits_is_returned(self):
        raw = self._run([{"id": "a", "isRunning": False, "rawResponse": _hits(0)}])
        self.assertEqual(raw["hits"]["total"]["value"], 0)

    def test_never_completes_raises(self):
        with self.assertRaises(RuntimeError) as ctx:
            self._run([{"id": "a", "isRunning": True}], max_polls=3)
        self.assertIn("did not finish", str(ctx.exception))

    def test_no_async_id_and_no_raw_raises(self):
        with self.assertRaises(RuntimeError):
            self._run([{"isRunning": False}])


if __name__ == "__main__":
    unittest.main(verbosity=2)
