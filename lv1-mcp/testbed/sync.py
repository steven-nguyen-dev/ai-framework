"""Mock content diff and push: the git checkout of cloud-servers/mock-api/mocks/<content_path>/ against the cloud.

Ported from lv1-servers testbed-dev/suite/commands/sync.py (commit 21d77d0), which this server replaces.
`content_path` comes from testbed-dev/suites/<group>/<v>/integration.json.

Never uploaded: `.pushed.json` (server-owned), gitignored files (except the generated fixtures in
GENERATED), anything under a `secrets` folder, key and certificate files, `.env`, `testbed.env`.
"""

from __future__ import annotations

import getpass
import hashlib
import json
import os
import socket
import subprocess
from pathlib import Path
from typing import Any, Callable

from .client import BATCH_FILE_BYTES, RolledBack, StaleBase, TestbedClient, TestbedError
from .common import NotFoundError, ToolError

# Decoded bytes per batch; base64 inflates by 4/3 and the contract caps a body at 50 MiB.
BATCH_BUDGET = 30 * 1024 * 1024
NEVER_FILES = {".pushed.json", ".DS_Store", "testbed.env", ".env"}
NEVER_SUFFIXES = (".p12", ".pfx", ".pem", ".key")
SKIP_DIRS = {"__pycache__", ".git", ".venv", "node_modules", "test-results"}

# Gitignored generated fixtures a mock needs (too big for GitHub): content_path/relative path -> the
# command that makes it. Missing locally, the diff would otherwise read as "delete it from the cloud".
GENERATED = {
    "external/amazon/IA-5105-US1/mock-data/browse-tree-de-300mb.xml":
        "python3 cloud-servers/mock-api/tools/gen_ia5105_browse_tree.py",
}


class PushFailed(ToolError):
    code = "push_failed"


# ---- local files ----

def forbidden(rel: str) -> bool:
    parts = rel.replace("\\", "/").split("/")
    name = parts[-1]
    return "secrets" in parts[:-1] or name in NEVER_FILES or name.endswith(NEVER_SUFFIXES)


def _git(folder: Path, *args: str) -> bytes | None:
    try:
        done = subprocess.run(["git", "-C", str(folder), *args], capture_output=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout if done.returncode == 0 else None


def local_files(folder: Path) -> tuple[dict[str, Path], list[str]]:
    """Returns ({relative path: absolute path} a push may send, [skipped forbidden paths]).

    Uses ``git ls-files -co --exclude-standard`` so gitignored files never go; outside a git work
    tree it walks the folder and skips caches.
    """
    out = _git(folder, "ls-files", "-co", "--exclude-standard", "-z", ".")
    if out is not None:
        names = [n for n in out.decode("utf-8").split("\0") if n]
    else:
        names = []
        for base, dirs, files in os.walk(folder):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            names += [os.path.relpath(os.path.join(base, f), folder).replace(os.sep, "/") for f in files]
    found: dict[str, Path] = {}
    skipped: list[str] = []
    for name in sorted(set(names)):
        path = folder / name
        if not path.is_file() or path.is_symlink():
            continue
        if forbidden(name):
            if os.path.basename(name) != ".pushed.json":
                skipped.append(name)
            continue
        found[name] = path
    return found, skipped


def file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_identity(folder: Path) -> tuple[str, str, bool]:
    """(by, commit, dirty): git user.email local part, HEAD, uncommitted changes under folder."""
    email = (_git(folder, "config", "user.email") or b"").decode().strip()
    by = email.split("@")[0] or os.environ.get("USER", "unknown")
    commit = (_git(folder, "rev-parse", "HEAD") or b"").decode().strip() or "unknown"
    status = _git(folder, "status", "--porcelain", "--", ".")
    return by, commit, bool(status and status.strip())


def lease_owner() -> str:
    """The lease owner string, formatted as suite/cli.py formats it (user@host)."""
    return "%s@%s" % (getpass.getuser(), socket.gethostname().split(".")[0])


# ---- lookups ----

def content_path_of(suites_root: Path, mock: str) -> str:
    """Returns `content_path` of `mock` from suites/<group>/<v>/integration.json."""
    for base, dirs, files in os.walk(suites_root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        if "integration.json" not in files:
            continue
        try:
            with open(os.path.join(base, "integration.json"), encoding="utf-8") as f:
                doc = json.load(f)
        except (OSError, ValueError):
            continue
        if doc.get("mock") == mock and doc.get("content_path"):
            return doc["content_path"].strip("/")
        dirs[:] = []
    raise NotFoundError("no suites/<group>/<v>/integration.json names mock %r with a content_path" % mock,
                        mock=mock)


def _strip(entries: list[dict], prefix: str) -> dict[str, str]:
    cut = len(prefix) + 1 if prefix else 0
    return {e["path"][cut:]: e["sha256"] for e in entries}


def diff(local: dict[str, str], remote: dict[str, str]) -> tuple[list[str], list[str], list[str]]:
    """(added, changed, deleted) path lists from {path: sha} maps."""
    added = sorted(p for p in local if p not in remote)
    changed = sorted(p for p in local if p in remote and local[p] != remote[p])
    deleted = sorted(p for p in remote if p not in local)
    return added, changed, deleted


def known_mock(client: TestbedClient, mock: str) -> dict | None:
    for server in client.servers() or []:
        if mock in (server.get("key"), server.get("name"), *(server.get("aliases") or [])):
            return server
    return None


# ---- uploading ----

def send(files: dict[str, bytes], deletes: list[str], put: Callable, batch: Callable) -> None:
    """Writes files over the batch cap one by one, the rest in batches under BATCH_BUDGET; deletes ride the first batch."""
    big = sorted(p for p, data in files.items() if len(data) > BATCH_FILE_BYTES)
    for path in big:
        put(path, files[path])
    groups: list[dict[str, bytes]] = []
    current: dict[str, bytes] = {}
    size = 0
    for path in sorted(p for p in files if p not in big):
        n = len(files[path])
        if current and size + n > BATCH_BUDGET:
            groups.append(current)
            current, size = {}, 0
        current[path] = files[path]
        size += n
    if current:
        groups.append(current)
    if not groups and deletes:
        groups = [{}]
    for i, group in enumerate(groups):
        batch(group, list(deletes) if i == 0 else [])


# ---- plan ----

class MockPlan:
    """The local side of one mock: its content path, folder and hashed files."""

    def __init__(self, mocks_root: Path, suites_root: Path, mock: str) -> None:
        self.mock = mock
        self.content_path = content_path_of(suites_root, mock)
        self.folder = mocks_root.joinpath(*self.content_path.split("/"))
        if not self.folder.is_dir():
            raise NotFoundError("mock content folder not found: %s" % self.folder, mock=mock)

    def scan(self, client: TestbedClient) -> dict[str, Any]:
        """Hashes the local files and lists the live ones; returns the pieces diff and push need."""
        cp = self.content_path
        paths, skipped = local_files(self.folder)
        for full in GENERATED:
            if full.startswith(cp + "/"):
                path = self.folder.joinpath(*full[len(cp) + 1:].split("/"))
                if path.is_file() and not path.is_symlink():
                    paths[full[len(cp) + 1:]] = path
        local = {rel: file_sha(path) for rel, path in paths.items()}
        server = known_mock(client, self.mock)
        remote = _strip(client.list_content("mocks", prefix=cp), cp) if server else {}
        remote.pop(".pushed.json", None)
        kept = self._generated_missing(local, remote, bool(server))
        for rel in kept:
            remote.pop(rel, None)
        return {"paths": paths, "local": local, "remote": remote, "server": server,
                "kept": sorted(kept), "skipped": skipped}

    def _generated_missing(self, local: dict, remote: dict, known: bool) -> set[str]:
        """Generated fixtures absent locally but live on the cloud (left untouched)."""
        cp, kept = self.content_path, set()
        for full, command in GENERATED.items():
            if not full.startswith(cp + "/"):
                continue
            rel = full[len(cp) + 1:]
            if rel in local:
                continue
            if not known or rel not in remote:
                raise PushFailed("%s is missing and the cloud has no copy. Generate it first: %s"
                                 % (full, command))
            kept.add(rel)
        return kept


def _summary(added, changed, deleted, local) -> dict[str, Any]:
    return {"added": added, "changed": changed, "deleted": deleted,
            "counts": {"added": len(added), "changed": len(changed), "deleted": len(deleted),
                       "unchanged": len(local) - len(added) - len(changed)}}


def mocks_diff(client: TestbedClient, plan: MockPlan) -> dict[str, Any]:
    scan = plan.scan(client)
    added, changed, deleted = diff(scan["local"], scan["remote"])
    result = {"mock": plan.mock, "content_path": plan.content_path, "on_cloud": bool(scan["server"]),
              "kept_generated": scan["kept"], "skipped": scan["skipped"]}
    result.update(_summary(added, changed, deleted, scan["local"]))
    return result


def mocks_push(client: TestbedClient, plan: MockPlan, dry_run: bool = False) -> dict[str, Any]:
    """Uploads changed and deleted files under the lease, then applies; retries once on stale_base."""
    for attempt in (1, 2):
        scan = plan.scan(client)
        added, changed, deleted = diff(scan["local"], scan["remote"])
        base = {"mock": plan.mock, "content_path": plan.content_path, "dry_run": dry_run,
                "kept_generated": scan["kept"], "skipped": scan["skipped"]}
        if dry_run or not (added or changed or deleted):
            base.update(_summary(added, changed, deleted, scan["local"]))
            base["status"] = "dry_run" if dry_run else "up_to_date"
            return base
        by, commit, dirty = git_identity(plan.folder)
        try:
            with client.hold_lease(lease_owner(), "mcp mocks push %s" % plan.mock):
                upload = client.start_mock_upload(plan.mock, by, commit, dirty=dirty,
                                                  content_path=plan.content_path)
                # The staging copy, not the earlier listing, is what the changes apply to.
                live = _strip(upload["base"], "")
                live.pop(".pushed.json", None)
                for rel in scan["kept"]:
                    live.pop(rel, None)
                added, changed, deleted = diff(scan["local"], live)
                files = {rel: scan["paths"][rel].read_bytes() for rel in added + changed}
                uid = upload["upload_id"]
                send(files, deleted,
                     put=lambda p, data: client.put_upload_file(plan.mock, uid, p, data),
                     batch=lambda f, d: client.batch_upload(plan.mock, uid, f, d))
                applied = client.apply_upload(plan.mock, uid)
        except RolledBack:
            raise PushFailed("%s did not start with the new content; the previous content is live again"
                             % plan.mock, mock=plan.mock) from None
        except StaleBase:
            if attempt == 1:
                continue
            raise PushFailed("live content changed during the upload twice; try again", mock=plan.mock) from None
        except TestbedError as error:
            extra: dict[str, Any] = {"status": error.status, "api_code": error.code}
            if error.code == "check_failed":
                extra["check_output"] = error.details.get("output", "")
            raise PushFailed("push of %s failed: %s" % (plan.mock, error.message), **extra) from None
        base.update(_summary(added, changed, deleted, scan["local"]))
        base.update({"status": applied.get("status"), "pushed": applied.get("pushed"),
                     "changed_on_cloud": applied.get("changed") or [],
                     "commit": commit, "dirty": dirty, "by": by})
        return base
    raise PushFailed("push of %s did not complete" % plan.mock)  # pragma: no cover - loop always returns or raises
