"""HTTP client for Ollama's embedding endpoint - the wiki's one text-to-vector call.

CONTRACT.md SS5a. Uses `urllib.request` from the standard library rather than a real
HTTP client: every dependency here is loaded five times over, once per pane's MCP
subprocess, and this module's only remote call is one `POST` with a JSON body. No
caller of `Embedder` ever sees an exception from it - a dead container, a timeout, a
malformed response and a wrong-width vector all collapse to `None`, so an unreachable
embedder degrades search and write quality without ever raising into a worker's turn.
"""

from __future__ import annotations

import json
import math
import threading
import urllib.request
from collections import OrderedDict
from typing import Any

_DOCUMENT_PREFIX = "title: {title} | text: {summary}\n{body}"
"""CONTRACT.md SS5a: the stored-text prefix, asymmetric from the query prefix by design -
EmbeddingGemma is trained on distinct document/query prefixes, and using one for both
(or neither) measurably loses recall. `title` is the source's real title, not the model
card's literal `none`, since the title is already known at write time."""

_QUERY_PREFIX = "task: search result | query: {query}"
"""CONTRACT.md SS5a: the search-time prefix. A change to either this or `_DOCUMENT_PREFIX`
invalidates every vector already stored - both are mandatory, in code, not by convention."""


class Embedder:
    """Wraps `POST {url}/api/embed`; every method returns `None` on failure, never raises.

    Holds no connection between calls - each `embed_documents`/`embed_query` call opens
    its own request per batch. `enabled=False` is the config-level kill switch: every
    method then returns `None` immediately, touching the network not at all, so a
    deployment without Ollama installed pays no latency and takes no dependency risk for
    disabling it.
    """

    def __init__(
        self,
        url: str,
        model: str,
        dimensions: int,
        timeout_s: float,
        batch_size: int,
        enabled: bool = True,
    ) -> None:
        """Binds the Ollama endpoint and the vector width every response is checked against.

        @param dimensions exact length every returned vector must have; a mismatch (a model
            swap, a truncated response) is treated as a failure, not a value to store - a
            wrong-width vector would otherwise poison the column silently
        @param enabled `False` short-circuits every call to `None` before any network I/O
        """
        self._url = url.rstrip("/")
        self._model = model
        self._dimensions = dimensions
        self._timeout_s = timeout_s
        self._batch_size = max(1, batch_size)
        self._enabled = enabled
        self._cache: OrderedDict[str, list[float]] = OrderedDict()
        self._cache_lock = threading.Lock()
        self._cache_max = 512

    @property
    def enabled(self) -> bool:
        """Whether any call may reach the network; `False` is the config kill switch.

        Read by `WikiStore.upsert_section`, which must decide whether to spend an extra
        unlocked `SELECT` gathering the document prefix's title *before* it opens its
        transaction. With embedding switched off there is nothing to prefix, so that read
        is skipped and the write path stays exactly the SQL the lexical-only build issued.
        """
        return self._enabled

    def embed_documents(self, pairs: list[tuple[str, str, str]]) -> list[list[float] | None]:
        """Embeds `(title, summary, body)` triples with the document prefix, batched.

        Returns one entry per input, in order - `None` for any triple whose batch failed
        or whose returned vector was the wrong width. A batch failure never drops entries;
        it fills that whole batch's slots with `None` so the caller's zip against its own
        rows never misaligns.

        @param pairs `(title, summary, body)` triples; named for the return type's shape
            (`list[... | None]`), not for the input's own arity - see the embedder's own
            module docstring for why a 3-tuple is required here
        """
        if not self._enabled or not pairs:
            return [None] * len(pairs)
        texts = [
            _DOCUMENT_PREFIX.format(title=title, summary=summary, body=body)
            for title, summary, body in pairs
        ]
        return self._embed_in_batches(texts)

    def embed_query(self, text: str) -> list[float] | None:
        """Embeds one query string with the query prefix, cached in-memory."""
        if not self._enabled:
            return None
        normalized = text.strip()
        with self._cache_lock:
            if normalized in self._cache:
                self._cache.move_to_end(normalized)
                return self._cache[normalized]

        results = self._embed_in_batches([_QUERY_PREFIX.format(query=normalized)])
        vec = results[0] if results else None
        if vec is not None:
            with self._cache_lock:
                self._cache[normalized] = vec
                if len(self._cache) > self._cache_max:
                    self._cache.popitem(last=False)
        return vec

    def _embed_in_batches(self, texts: list[str]) -> list[list[float] | None]:
        results: list[list[float] | None] = []
        for start in range(0, len(texts), self._batch_size):
            results.extend(self._embed_one_batch(texts[start : start + self._batch_size]))
        return results

    def _embed_one_batch(self, batch: list[str]) -> list[list[float] | None]:
        response = self._post(batch)
        if response is None:
            return [None] * len(batch)
        return [self._validated(vector) for vector in response]

    def _post(self, batch: list[str]) -> list[Any] | None:
        """Sends one `/api/embed` call; `None` on any transport, timeout or shape failure."""
        payload = {
            "model": self._model,
            "input": batch,
            "keep_alive": -1,  # Keep model resident in GPU VRAM to eliminate cold start
        }
        request = urllib.request.Request(
            f"{self._url}/api/embed",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout_s) as response:
                decoded = json.loads(response.read().decode("utf-8"))
        except Exception:
            return None

        embeddings = decoded.get("embeddings") if isinstance(decoded, dict) else None
        if not isinstance(embeddings, list) or len(embeddings) != len(batch):
            return None
        return embeddings

    def _validated(self, vector: Any) -> list[float] | None:
        """Accepts a vector only at the exact configured width, all values finite; else `None`.

        The rejected alternative is truncating or padding a wrong-width response to fit -
        that would store a vector `<=>` never meant to compare against, silently, with no
        error to say so.

        `NaN` and `±Inf` are rejected for a harder reason than tidiness: pgvector's input
        parser refuses them outright, so a single non-finite value would surface as a raw
        `psycopg.Error` from inside `upsert`'s transaction and roll the whole write back -
        turning a model's bad answer into exactly the lost worker learning CONTRACT.md
        SS5a's degradation rule forbids. Degrading to `None` here writes the chunk with a
        NULL embedding instead, like any other embedder failure.
        """
        if not isinstance(vector, list) or len(vector) != self._dimensions:
            return None
        try:
            values = [float(value) for value in vector]
        except (TypeError, ValueError):
            return None
        if not all(math.isfinite(value) for value in values):
            return None
        return values
