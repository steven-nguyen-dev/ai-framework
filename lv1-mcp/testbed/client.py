"""HTTP client for lv1-servers/contracts/testbed-api.yaml: lease, servers, content, mock uploads, mock admin.

Stdlib only. Sends the token only as ``X-Auth-Token`` and only to the configured host.
"""

from __future__ import annotations

import base64
import hashlib
import json
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

CHUNK_BYTES = 50 * 1024 * 1024  # contract: larger bodies go in Content-Range chunks of at most this
BATCH_FILE_BYTES = 8 * 1024 * 1024  # contract: per-file cap inside a batch
RESUME_ATTEMPTS = 3
MAX_RETRY_WAIT_S = 60
# Cloudflare in front of the portal answers 403 "error code: 1010" to Python's default
# `Python-urllib/x.y` User-Agent.
USER_AGENT = "testbed-mcp/1.0"
LOOPBACK_HOSTS = ("127.0.0.1", "::1", "localhost")


class TestbedError(Exception):
    """A non-2xx answer, or no answer (status 0)."""

    __test__ = False

    def __init__(self, status: int, code: str, message: str, details: dict | None = None) -> None:
        super().__init__("%s %s: %s" % (status, code, message))
        self.status = status
        self.code = code
        self.message = message
        self.details = details or {}


class AuthError(TestbedError):
    pass


class LeaseHeld(TestbedError):
    pass


class StaleBase(TestbedError):
    pass


class CheckFailed(TestbedError):
    pass


class RateLimited(TestbedError):
    def __init__(self, status, code, message, details=None, retry_after=None):
        super().__init__(status, code, message, details)
        self.retry_after = retry_after


class RolledBack(TestbedError):
    pass


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    # urllib would replay X-Auth-Token to the redirect target.
    def redirect_request(self, *args, **kwargs):
        return None


def check_url(url: str) -> str:
    """Returns ``url``; raises ValueError unless it is https, or http to a loopback host."""
    parts = urllib.parse.urlsplit(url)
    if parts.scheme == "https" or (parts.scheme == "http" and parts.hostname in LOOPBACK_HOSTS):
        return url
    raise ValueError("TESTBED_HOST must be https (http only for 127.0.0.1, ::1, localhost)")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _quote(path: str) -> str:
    return urllib.parse.quote(path.lstrip("/"), safe="/")


def _tls_context() -> ssl.SSLContext:
    try:
        import certifi  # shipped with the mcp dependency tree; python.org builds lack system roots

        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def _batch_body(files: dict, delete: list | None) -> dict:
    """files: {path: bytes}; delete: [path]."""
    entries = []
    for path, data in sorted((files or {}).items()):
        if len(data) > BATCH_FILE_BYTES:
            raise ValueError("%s is over the %d byte batch limit" % (path, BATCH_FILE_BYTES))
        entries.append({"path": path, "content_b64": base64.b64encode(data).decode("ascii"),
                        "sha256": sha256_hex(data)})
    body: dict[str, Any] = {}
    if entries:
        body["files"] = entries
    if delete:
        body["delete"] = list(delete)
    return body


class TestbedClient:
    """Methods return parsed JSON (None for an empty body) and raise TestbedError subclasses."""

    __test__ = False

    def __init__(self, url: str, token: str, timeout: float = 120, sleep=time.sleep) -> None:
        self.url = check_url(url.rstrip("/"))
        self._token = token
        self.timeout = timeout
        self._sleep = sleep
        self.lease_id: str | None = None
        handlers: list = [_NoRedirect()]
        if self.url.startswith("https"):
            handlers.append(urllib.request.HTTPSHandler(context=_tls_context()))
        self._opener = urllib.request.build_opener(*handlers)

    def __repr__(self) -> str:
        return "TestbedClient(%r)" % self.url

    # ---- transport ----

    def _send(self, method, path, query=None, body=None, headers=None, json_body=None):
        try:
            return self._send_once(method, path, query, body, headers, json_body)
        except RateLimited as limited:
            if limited.retry_after is None or limited.retry_after > MAX_RETRY_WAIT_S:
                raise
            self._sleep(limited.retry_after)
            return self._send_once(method, path, query, body, headers, json_body)

    def _send_once(self, method, path, query, body, headers, json_body):
        if not self._token:
            raise AuthError(401, "unauthorized", "TESTBED_API_TOKEN is not set (~/.mcp/.testbed.env)")
        url = self.url + path
        if query:
            url += "?" + urllib.parse.urlencode(query)
        merged = {"X-Auth-Token": self._token, "User-Agent": USER_AGENT}
        if self.lease_id:
            merged["X-Testbed-Lease"] = self.lease_id
        if json_body is not None:
            body = json.dumps(json_body).encode("utf-8")
            merged["Content-Type"] = "application/json"
        elif body is not None:
            merged["Content-Type"] = "application/octet-stream"
        merged.update(headers or {})
        request = urllib.request.Request(url, data=body, method=method, headers=merged)
        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                return response.status, response.headers, response.read()
        except urllib.error.HTTPError as error:
            try:
                raise self._error(error.code, error.read(), error.headers.get("Retry-After")) from None
            finally:
                error.close()
        except (urllib.error.URLError, OSError) as error:
            raise TestbedError(0, "unreachable", "%s: %s" % (type(error).__name__, error)) from None

    @staticmethod
    def _error(status, raw, retry_after=None):
        code, message, details = "http_%d" % status, raw[:300].decode("utf-8", "replace"), {}
        try:
            err = json.loads(raw.decode("utf-8")).get("error") or {}
            code, message, details = err.get("code", code), err.get("message", message), err.get("details") or {}
        except (ValueError, AttributeError):
            pass
        if status == 429:
            try:
                seconds = int(retry_after)
            except (TypeError, ValueError):
                seconds = None
            return RateLimited(status, code, message, details, seconds)
        cls = {
            (401, None): AuthError,
            (409, "lease_held"): LeaseHeld,
            (409, "stale_base"): StaleBase,
            (422, "check_failed"): CheckFailed,
        }.get((status, None if status == 401 else code), TestbedError)
        return cls(status, code, message, details)

    def _json(self, *args, **kwargs):
        _, _, raw = self._send(*args, **kwargs)
        return json.loads(raw.decode("utf-8")) if raw else None

    # ---- portal: lease and servers ----

    def servers(self):
        return self._json("GET", "/api/servers")

    def lease_state(self):
        return self._json("GET", "/api/lease")

    def acquire_lease(self, owner, purpose=None, ttl_s=None):
        """Takes the lease, or renews it when this client already holds one."""
        body: dict[str, Any] = {"owner": owner}
        if self.lease_id:
            body["lease_id"] = self.lease_id
        if purpose:
            body["purpose"] = purpose
        if ttl_s:
            body["ttl_s"] = ttl_s
        lease = self._json("POST", "/api/lease", json_body=body)
        self.lease_id = lease["lease_id"]
        return lease

    def release_lease(self):
        try:
            self._send("DELETE", "/api/lease")
        finally:
            self.lease_id = None

    def hold_lease(self, owner, purpose=None, ttl_s=1800):
        return LeaseHold(self, owner, purpose, ttl_s)

    # ---- C1: per-mock admin ----

    def health(self, mock):
        return self._json("GET", "/%s/__testbed/health" % mock)

    def list_stores(self, mock):
        return self._json("GET", "/%s/__testbed/stores" % mock)

    def get_store(self, mock, name):
        return self._json("GET", "/%s/__testbed/stores/%s" % (mock, _quote(name)))

    def put_store(self, mock, name, value, mode="replace"):
        self._send("PUT", "/%s/__testbed/stores/%s" % (mock, _quote(name)), query={"mode": mode}, json_body=value)

    def reset(self, mock, stores=None, log=False, files=False):
        body: dict[str, Any] = {"log": bool(log), "files": bool(files)}
        if stores is not None:
            body["stores"] = list(stores)
        return self._json("POST", "/%s/__testbed/reset" % mock, json_body=body)

    def log_data(self, mock, after_seq=None, since=None):
        query: dict[str, Any] = {}
        if after_seq is not None:
            query["after_seq"] = int(after_seq)
        if since:
            query["since"] = since
        return self._json("GET", "/%s/log/data" % mock, query=query or None)

    # ---- C4: content and mock uploads ----

    def list_content(self, area, prefix=""):
        query = {"recursive": "true"}
        if prefix:
            query["prefix"] = prefix
        return self._json("GET", "/api/content/%s/files" % area, query=query)

    def start_mock_upload(self, mock, by, commit, dirty=False, content_path=None):
        body: dict[str, Any] = {"by": by, "commit": commit, "dirty": bool(dirty)}
        if content_path:
            body["content_path"] = content_path
        return self._json("POST", "/api/mocks/%s/uploads" % mock, json_body=body)

    def put_upload_file(self, mock, upload_id, path, data):
        return self._put_bytes("/api/mocks/%s/uploads/%s/files/%s" % (mock, upload_id, _quote(path)), data)

    def batch_upload(self, mock, upload_id, files, delete=None):
        return self._json("POST", "/api/mocks/%s/uploads/%s/batch" % (mock, upload_id),
                          json_body=_batch_body(files, delete))

    def apply_upload(self, mock, upload_id):
        result = self._json("POST", "/api/mocks/%s/uploads/%s/apply" % (mock, upload_id))
        if result.get("rolled_back"):
            raise RolledBack(200, "rolled_back", "mock %s did not start; previous content restored" % mock, result)
        return result

    def rollback(self, mock):
        return self._json("POST", "/api/mocks/%s/rollback" % mock)

    def _put_bytes(self, path, data):
        """Over CHUNK_BYTES, sends Content-Range chunks and resumes from `received` on 416."""
        headers = {"X-Content-Sha256": sha256_hex(data)}
        if len(data) <= CHUNK_BYTES:
            _, _, raw = self._send("PUT", path, body=data, headers=headers)
            return json.loads(raw.decode("utf-8")) if raw else None
        total, start, resumes = len(data), 0, 0
        while True:
            end = min(start + CHUNK_BYTES, total) - 1
            chunk = dict(headers, **{"Content-Range": "bytes %d-%d/%d" % (start, end, total)})
            try:
                _, _, raw = self._send("PUT", path, body=data[start:end + 1], headers=chunk)
            except TestbedError as error:
                received = error.details.get("received")
                if error.status != 416 or not isinstance(received, int) or resumes >= RESUME_ATTEMPTS:
                    raise
                resumes += 1
                start = received if 0 <= received < total else 0
                continue
            if end + 1 >= total:
                return json.loads(raw.decode("utf-8")) if raw else None
            start = end + 1


class LeaseHold:
    """Holds the lease for a ``with`` block, renewing it every ttl/3 s; releases on exit."""

    def __init__(self, client, owner, purpose=None, ttl_s=1800):
        self.client, self.owner, self.purpose, self.ttl_s = client, owner, purpose, ttl_s
        self.error: TestbedError | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def __enter__(self):
        lease = self.client.acquire_lease(self.owner, self.purpose, self.ttl_s)
        interval = max(1.0, (lease.get("ttl_s") or self.ttl_s or 1800) / 3.0)
        self._thread = threading.Thread(target=self._renew, args=(interval,), daemon=True)
        self._thread.start()
        return self

    def _renew(self, interval):
        while not self._stop.wait(interval):
            try:
                self.client.acquire_lease(self.owner, self.purpose, self.ttl_s)
            except TestbedError as error:
                self.error = error

    def __exit__(self, *exc):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)
        try:
            self.client.release_lease()
        except TestbedError:
            pass  # lapsed or force-released: nothing left to give back
        return False
