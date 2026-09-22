"""Transactional access to the wiki tables: version checks, changelog, search ranking.

`WikiStore` is the wiki's only writer. `wiki.upsert` and the `wiki-ingest` loader
both build one over the same class, so a chunk is never written, versioned or
changelogged two different ways.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime
from typing import Any

from .common import (
    BackendError,
    NotFoundError,
    ValidationError,
    VersionConflict,
    count_words,
    slugify,
)
from .config import Limits

from . import queries
from .embed import Embedder

ConnectionFactory = Callable[[], Any]
"""Zero-argument callable returning a fresh, unopened-transaction psycopg connection.

Kept as `Callable[[], Any]` rather than `Callable[[], psycopg.Connection]` so this
module - and everything that imports it - stays importable with psycopg absent.
Only calling a `WikiStore` method, which calls this factory, needs the driver.
"""

_TRGM_FALLBACK_OVERFETCH = 20
"""Extra trgm rows fetched beyond the shortfall, so de-duplication against full-text
hits rarely leaves the fallback short of a full page."""

_MAX_SEARCH_K = 100
"""Ceiling for `search`'s `k`. Unvalidated, `k` is a raw SQL `LIMIT`: `0` silently
returns nothing, a negative value raises a raw Postgres error, and an
unbounded value could pull the whole live table over stdio in one response.
100 is ten times the tool's stated default (5) and comfortably above any
plausible single-turn read for an agent, while `session_log`'s own ceiling
(500) is a session-log-sized number, not a search-result-sized one - the two
tools clamp independently."""

_LIKE_ESCAPE = "\\"
"""Escape character bound to Postgres' `LIKE ... ESCAPE '\\'` in queries.py."""

_RRF_K = 60
"""Reciprocal Rank Fusion's constant, CONTRACT.md SS5a: `score = sum(1 / (60 + rank))`
over every candidate list a chunk appears in. The standard value, not tuned here."""


def _escape_like(value: str) -> str:
    """Escapes `%`, `_` and the escape character itself for a `LIKE` pattern.

    Applied to `source_prefix` before it is bound as a query parameter, so a
    literal prefix like `plan_` or `a%` matches only that literal text rather
    than acting as a wildcard. The escaping happens here, in Python, on the
    value alone - it is still passed to psycopg as a named parameter, never
    interpolated into SQL text.
    """
    escaped = value.replace(_LIKE_ESCAPE, _LIKE_ESCAPE * 2)
    escaped = escaped.replace("%", _LIKE_ESCAPE + "%")
    escaped = escaped.replace("_", _LIKE_ESCAPE + "_")
    return escaped


def _parse_since(since: str) -> str:
    """Validates `since` as an ISO-8601 timestamp or a bare date before it reaches SQL.

    `changelog_since` casts `since` to `timestamptz` in SQL; an unparseable value
    such as `"last week"` would otherwise surface as a raw
    `psycopg.errors.InvalidDatetimeFormat` from inside the transaction. Rejecting
    it here, in Python, keeps that a `validation` envelope instead - and the
    original string is what SQL casts, so a form Postgres accepts but
    `datetime.fromisoformat` would render differently is never silently rewritten.

    @raises ValidationError if `since` is not a bare date or an ISO-8601 timestamp
    """
    candidate = since.strip()
    text = candidate[:-1] + "+00:00" if candidate.endswith("Z") else candidate
    try:
        datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValidationError(
            "since must be an ISO-8601 timestamp or a bare date (YYYY-MM-DD)",
            field="since",
            limit="ISO-8601 or YYYY-MM-DD",
            actual=since,
        ) from exc
    return since


@contextmanager
def _cursor(connect: Any) -> Iterator[Any]:
    """Opens or borrows one connection, yields a dict-row cursor, commits or rolls back.

    Supports both `psycopg_pool.ConnectionPool` (warm in-memory connections with
    concurrent checkout) and zero-argument callable `ConnectionFactory` (fresh connection).
    """
    import psycopg
    from psycopg.rows import dict_row

    if hasattr(connect, "connection"):
        try:
            with connect.connection() as conn:
                try:
                    with conn.cursor(row_factory=dict_row) as cur:
                        yield cur
                    conn.commit()
                except psycopg.Error as exc:
                    conn.rollback()
                    raise BackendError(str(exc), backend="postgres") from exc
                except Exception:
                    conn.rollback()
                    raise
        except psycopg.Error as exc:
            raise BackendError(str(exc), backend="postgres") from exc
    else:
        try:
            conn = connect()
        except psycopg.Error as exc:
            raise BackendError(str(exc), backend="postgres") from exc

        try:
            with conn.cursor(row_factory=dict_row) as cur:
                yield cur
            conn.commit()
        except psycopg.Error as exc:
            conn.rollback()
            raise BackendError(str(exc), backend="postgres") from exc
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def _iso(value: Any) -> str | None:
    """Formats a psycopg-returned timestamp for JSON transport; passes `None` through."""
    return value.isoformat() if value is not None else None


class WikiStore:
    """Wiki reads and writes against PostgreSQL, one connection per call, one transaction per write.

    Holds no connection between calls and no cache - every method opens a fresh
    connection from `connect`, does its work, and closes it. That keeps a stale
    connection from outliving a long-idle pane and keeps concurrent callers from
    sharing a transaction by accident.
    """

    def __init__(
        self,
        connect: ConnectionFactory,
        limits: Limits,
        embedder: Embedder | None = None,
        inbox_prefix: str = "inbox/",
    ) -> None:
        """Binds a connection factory, the word/size limits and the embedder; opens nothing yet.

        @param connect zero-argument factory for a fresh, unopened-transaction connection;
            called anew by every method, never held across calls
        @param embedder `None` is equivalent to a disabled embedder - `search` skips the
            vector pass and `upsert_section`/`backfill` write `NULL` embeddings, with no
            network call attempted. A real server always passes a constructed `Embedder`,
            even when `config.toml`'s own `[embedder].enabled` is `false`, since `Embedder`
            itself already honours that flag; the `None` default here exists for tests and
            any caller that never wires embedding in at all.
        @param inbox_prefix the namespace `search` excludes by default and `tools.note`
            writes into (CONTRACT.md SS5b); a real server passes `config.wiki.inbox_prefix`
            here so the two can never drift apart. Empty string means no namespace is
            reserved as "the inbox" at all - `search` then excludes nothing, and `note`
            writes bare `<pane>/<slug>`.
        """
        self._connect = connect
        self._limits = limits
        self._embedder = embedder
        self._inbox_prefix = inbox_prefix

    @property
    def inbox_prefix(self) -> str:
        """The configured inbox namespace - see `__init__`'s `inbox_prefix` parameter.

        `swarm.wiki.tools.note` reads this to build `<inbox_prefix><pane>/<slug>`, so the
        identity a note lands under can never drift from the namespace `search` excludes.
        """
        return self._inbox_prefix

    def search(
        self,
        query: str,
        k: int = 5,
        source_prefix: str | None = None,
        include_inbox: bool = False,
    ) -> tuple[list[dict[str, Any]], bool]:
        """Ranks live chunks by full-text, trigram and vector similarity, fused by RRF.

        `ts_rank_cd` over the generated `fts` column runs first, always. `to_tsvector`
        does not segment Korean or Japanese into tokens, so a CJK query starves that pass
        entirely; the `pg_trgm` `similarity(body, query)` pass that follows on a shortfall
        (unchanged from the lexical-only build) is what makes those queries reachable at
        all. A third pass ranks by `embedding <=> query_vector` whenever the embedder is
        configured and answers for this call - CONTRACT.md SS5a: "runs its lexical passes
        regardless, and adds the vector pass only when the embedder answers."

        The three candidate lists are fused by Reciprocal Rank Fusion rather than merged
        by priority: `score = sum(1 / (60 + rank))` over every list a chunk appears in,
        `rank` starting at 1 within that list alone. Candidates are scored in first-seen
        order (full-text, then trigram, then vector) and the final sort is stable, so two
        equal-score chunks keep that list-priority order.

        Fusion is not priority, and that changes one lexical outcome even with the
        embedder off: when full-text falls short of `k` and the trigram fallback runs, the
        fallback's rank-1 hit scores `1/61` and so now sorts *above* full-text's rank-2 hit
        at `1/62`, where the pre-fusion build placed every full-text hit ahead of every
        trigram one. That is what CONTRACT.md SS5a asks for - `ts_rank_cd` and `similarity`
        are not comparable scales, and rank is the only thing they share - and the two
        lists still interleave by rank rather than one displacing the other. Nothing else
        about the lexical path moved: the same two statements run, under the same
        shortfall condition, with the same page sizes and the same de-duplication.

        CONTRACT.md SS5b: an unpromoted `inbox/` write must never influence a result an
        agent did not ask for by name. All three passes exclude `source_id LIKE 'inbox/%'`
        (the configured `inbox_prefix`) inside their own `WHERE`, ahead of `ORDER BY`/
        `LIMIT` - so an inbox row can never occupy a candidate slot it would then be
        filtered out of after ranking already spent it. `include_inbox=True` and a
        `source_prefix` that itself starts with `inbox_prefix` are the two, and only two,
        ways past that default; asking for the inbox by name is asking for the inbox.

        @param k maximum hits to return; also every pass's own page size. Clamped to
            `1..._MAX_SEARCH_K` - unvalidated, it is a raw SQL `LIMIT`.
        @param source_prefix restricts to `source_id LIKE prefix || '%'` when given; matched
            literally, `%` and `_` in `prefix` included, never as wildcards
        @param include_inbox `True` reaches `inbox/`-namespaced chunks too; default `False`
            keeps an unreviewed agent write out of every ranked result
        @return `(hits, vector_available)` - `hits` carry `matched_by` as a list (`'fts'`,
            `'trgm'`, `'vector'`) and `score`, the RRF score; `vector_available` is `False`
            whenever the vector pass did not run, embedder absent, disabled or unreachable
            alike
        """
        k = max(1, min(k, _MAX_SEARCH_K))
        escaped_prefix = _escape_like(source_prefix) if source_prefix is not None else None
        exclude_prefix = self._exclude_prefix_for(source_prefix, include_inbox)

        candidates: dict[tuple[str, str], dict[str, Any]] = {}
        order: list[tuple[str, str]] = []

        def _merge(rows: list[dict[str, Any]], pass_name: str) -> None:
            for list_rank, row in enumerate(rows, start=1):
                ident = (row["source_id"], row["section"])
                entry = candidates.get(ident)
                if entry is None:
                    entry = {
                        "source_id": row["source_id"],
                        "section": row["section"],
                        "version": row["version"],
                        "summary": row["summary"],
                        "body": row["body"],
                        "score": 0.0,
                        "matched_by": [],
                    }
                    candidates[ident] = entry
                    order.append(ident)
                entry["score"] += 1.0 / (_RRF_K + list_rank)
                entry["matched_by"].append(pass_name)

        # Embedded before the connection is opened, for the same reason `upsert_section`
        # embeds before its transaction (CONTRACT.md SS5a): psycopg opens a transaction on
        # the first `execute`, so calling the embedder from inside the `with` below would
        # leave a session idle-in-transaction for up to `timeout_s` on every search.
        query_vector = self._embedder.embed_query(query) if self._embedder is not None else None
        vector_available = query_vector is not None

        with _cursor(self._connect) as cur:
            cur.execute(
                queries.SEARCH_FTS,
                {
                    "query": query,
                    "source_prefix": escaped_prefix,
                    "exclude_prefix": exclude_prefix,
                    "k": k,
                },
            )
            fts_rows = cur.fetchall()
            _merge(fts_rows, "fts")

            remaining = k - len(fts_rows)
            if remaining > 0:
                cur.execute(
                    queries.SEARCH_TRGM_FALLBACK,
                    {
                        "query": query,
                        "source_prefix": escaped_prefix,
                        "exclude_prefix": exclude_prefix,
                        "limit": remaining + len(fts_rows) + _TRGM_FALLBACK_OVERFETCH,
                    },
                )
                _merge(cur.fetchall(), "trgm")

            if query_vector is not None:
                cur.execute(
                    queries.SEARCH_VECTOR,
                    {
                        "query_vec": queries.to_pgvector(query_vector),
                        "source_prefix": escaped_prefix,
                        "exclude_prefix": exclude_prefix,
                        "k": k,
                    },
                )
                _merge(cur.fetchall(), "vector")

        ranked = sorted(order, key=lambda ident: -candidates[ident]["score"])
        hits = [candidates[ident] for ident in ranked[:k]]
        return hits, vector_available

    def _exclude_prefix_for(self, source_prefix: str | None, include_inbox: bool) -> str | None:
        """Returns the escaped inbox prefix to exclude in this call's SQL, or `None` for none.

        `None` binds to `%(exclude_prefix)s::text IS NULL`, which short-circuits the
        exclusion clause in every SEARCH_* statement - the same "no filter" idiom already
        used for `source_prefix` itself. Three cases return `None`: no `inbox_prefix` is
        configured (an empty string means no namespace is reserved as "the inbox" at all),
        the caller opted in with `include_inbox=True`, or
        `source_prefix` itself already names the inbox - CONTRACT.md SS5b's "asking for
        the inbox by name is asking for the inbox".
        """
        if not self._inbox_prefix or include_inbox:
            return None
        if source_prefix is not None and source_prefix.startswith(self._inbox_prefix):
            return None
        return _escape_like(self._inbox_prefix)

    def fetch(
        self, source_id: str, section: str | None = None, include_retired: bool = False
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """Returns one source row and its chunks by exact identity.

        A retired chunk surfaces only when `include_retired` is true; `search`
        never reaches one regardless of this flag.

        @raises NotFoundError if `source_id` is unknown, or `section` names no matching row
        """
        with _cursor(self._connect) as cur:
            cur.execute(queries.SELECT_SOURCE, {"source_id": source_id})
            source_row = cur.fetchone()
            if source_row is None:
                raise NotFoundError("no such source", what="source")

            cur.execute(
                queries.SELECT_CHUNKS,
                {"source_id": source_id, "section": section, "include_retired": include_retired},
            )
            chunk_rows = cur.fetchall()

        if section is not None and not chunk_rows:
            raise NotFoundError("no such section", what="section")

        source = dict(source_row)
        source["updated_at"] = _iso(source["updated_at"])
        chunks = [
            {
                "section": row["section"],
                "summary": row["summary"],
                "body": row["body"],
                "version": row["version"],
                "deleted_at": _iso(row["deleted_at"]),
            }
            for row in chunk_rows
        ]
        return source, chunks

    def upsert_section(
        self,
        source_id: str,
        section: str,
        body: str,
        summary: str,
        expected_version: int,
        title: str | None = None,
        actor: str = "user",
    ) -> tuple[int, bool]:
        """Writes one section's body and summary, versioned, changelogged, in one transaction.

        Word limits, the version check, the sources-row bump, the `deleted_at`
        clear and the changelog append all happen inside one commit - a caller
        never observes a chunk written without its changelog row, or a version
        bumped without the body that earned it. This is the sole write path;
        `wiki-ingest` calls it through `swarm.wiki.tools.upsert`, never the SQL
        directly, so the loader's writes obey the exact same rules.

        The embedder runs **before** the transaction opens (CONTRACT.md SS5a), and its
        vector is then written by the very statement that writes the chunk, so the two
        still cannot drift: both describe the exact `summary` and `body` this call was
        given. Holding `SELECT ... FOR UPDATE` on `sources` and `chunks` across the
        embedder's HTTP call instead - bounded only by `timeout_s`, and longer still on a
        cold model load - would serialise every other writer behind one slow network round
        trip, which is why the lock is taken only after the vector is already in hand.

        The one unlocked read that costs (`SELECT_UPSERT_PRECHECK`) buys the source title
        the document prefix needs, and skips the embedder entirely when the section's
        version already disagrees with `expected_version` - that write is going to raise
        `VersionConflict` below, and a 30-second call spent on it is pure waste.

        An unreachable or disabled embedder never fails the write - the chunk commits with
        `embedding` left `NULL`, and the returned flag says so, rather than a caller's
        proven work being lost to a container that is merely down.

        @param expected_version the section's version to write against; `0` for a section
            that does not yet exist
        @param title used only when `source_id` has no row yet; ignored otherwise
        @raises ValidationError if `source_id` or `section` is empty or whitespace, if
            `section` is not already in `slugify` form, or if `body` exceeds its word
            limit, or `summary` is empty or exceeds its word limit
        @raises VersionConflict if `expected_version` does not match the section's stored
            version, carrying `current_version`, `current_body` and `current_summary` to
            merge against
        @return `(version, embedded)` - `embedded` is `False` whenever the embedder was
            absent, disabled, or failed for this call; the write itself never fails for it

        `section` must already be a slug rather than being slugified here: the
        `wiki-ingest` loader (CONTRACT.md SS4 rule 4, "the writer chunks") and any
        other caller compute their own `section` identity - for deduplication,
        for `-2`/`-3` suffixing, for cross-references - before this call. Silently
        reshaping it a second time here could make a value the caller already
        keyed elsewhere collide with a different section, with no error to say
        so. Rejecting a non-slug is louder and cheaper: the caller runs
        `swarm.common.slugify` itself, once, and the value this method stores is
        always exactly the value the caller passed.
        """
        if not source_id.strip():
            raise ValidationError("source_id must not be empty", field="source_id")
        if not section.strip():
            raise ValidationError("section must not be empty", field="section")
        if section != slugify(section):
            raise ValidationError(
                "section must already be a slug; call swarm.common.slugify before upsert",
                field="section",
                actual=section,
            )

        limits = self._limits
        body_words = count_words(body)
        if body_words > limits.body_max_words:
            raise ValidationError(
                "body exceeds the word limit",
                field="body",
                limit=limits.body_max_words,
                actual=body_words,
            )
        if not summary.strip():
            raise ValidationError(
                "summary must not be empty",
                field="summary",
                limit=limits.summary_max_words,
                actual=0,
            )
        summary_words = count_words(summary)
        if summary_words > limits.summary_max_words:
            raise ValidationError(
                "summary exceeds the word limit",
                field="summary",
                limit=limits.summary_max_words,
                actual=summary_words,
            )

        embedding = self._embed_before_transaction(
            source_id, section, body, summary, expected_version, title
        )

        with _cursor(self._connect) as cur:
            cur.execute(queries.SELECT_SOURCE_FOR_UPDATE, {"source_id": source_id})
            existing_source = cur.fetchone()
            if existing_source is None:
                cur.execute(
                    queries.INSERT_SOURCE_IF_ABSENT,
                    {"source_id": source_id, "title": title or source_id, "actor": actor},
                )

            cur.execute(
                queries.SELECT_CHUNK_FOR_UPDATE, {"source_id": source_id, "section": section}
            )
            chunk_row = cur.fetchone()
            current_version = chunk_row["version"] if chunk_row else 0
            if current_version != expected_version:
                raise VersionConflict(
                    "expected_version does not match the section's current version",
                    current_version=current_version,
                    current_body=chunk_row["body"] if chunk_row else "",
                    current_summary=chunk_row["summary"] if chunk_row else "",
                )

            if chunk_row is None:
                cur.execute(
                    queries.INSERT_CHUNK,
                    {
                        "source_id": source_id,
                        "section": section,
                        "summary": summary,
                        "body": body,
                        "embedding": embedding,
                    },
                )
                inserted = cur.fetchone()
                if inserted is None:
                    # Absent-row race: `SELECT_CHUNK_FOR_UPDATE` above locked nothing
                    # because no row existed to lock, so a concurrent first-writer for
                    # the same (source_id, section) could have committed between that
                    # SELECT and this INSERT. `ON CONFLICT ... DO NOTHING` turned our
                    # loss into a no-op instead of a raw UniqueViolation; re-read the
                    # row the winner created, in this same transaction, and report it
                    # as the version conflict it actually is.
                    cur.execute(
                        queries.SELECT_CHUNK_FOR_UPDATE,
                        {"source_id": source_id, "section": section},
                    )
                    winner = cur.fetchone()
                    raise VersionConflict(
                        "expected_version does not match the section's current version",
                        current_version=winner["version"],
                        current_body=winner["body"],
                        current_summary=winner["summary"],
                    )
                new_version = inserted["version"]
            else:
                cur.execute(
                    queries.UPDATE_CHUNK,
                    {
                        "chunk_id": chunk_row["chunk_id"],
                        "body": body,
                        "summary": summary,
                        "embedding": embedding,
                    },
                )
                new_version = cur.fetchone()["version"]

            cur.execute(queries.BUMP_SOURCE_VERSION, {"source_id": source_id, "actor": actor})
            cur.execute(
                queries.INSERT_CHANGELOG,
                {
                    "source_id": source_id,
                    "section": section,
                    "version": new_version,
                    "action": "upsert",
                    "actor": actor,
                    "note": None,
                },
            )

        return new_version, embedding is not None

    def _embed_before_transaction(
        self,
        source_id: str,
        section: str,
        body: str,
        summary: str,
        expected_version: int,
        title: str | None,
    ) -> str | None:
        """Returns this write's vector as a pgvector literal, or `None`; opens no transaction.

        Called only after the word limits have already rejected an oversized body, so a
        30-second embedder call is never spent on text that is about to fail validation.

        Skips the embedder when the section's currently stored version already disagrees
        with `expected_version`, since `upsert_section`'s locked check will raise
        `VersionConflict` moments later. That pre-read is unlocked and therefore advisory:
        in the rare case where it was stale and the locked check then succeeds, the chunk
        commits with `embedding` NULL and `embedded: False` - visible to the caller, and
        exactly the state `backfill` exists to repair. The reverse mistake (embedding on a
        stale "match" that then conflicts) costs only a discarded vector.

        @param title used for the document prefix only when `source_id` has no row yet;
            an existing source's own `sources.title` always wins, matching what the
            locked branch of the transaction resolves
        @return the `'[...]'` literal `INSERT_CHUNK`/`UPDATE_CHUNK` bind, or `None` when
            the embedder is absent, disabled, failing, or deliberately skipped
        """
        embedder = self._embedder
        if embedder is None or not embedder.enabled:
            return None

        with _cursor(self._connect) as cur:
            cur.execute(
                queries.SELECT_UPSERT_PRECHECK, {"source_id": source_id, "section": section}
            )
            precheck = cur.fetchone()

        current_version = (precheck["chunk_version"] if precheck else None) or 0
        if current_version != expected_version:
            return None

        source_title = (precheck["source_title"] if precheck else None) or title or source_id
        vector = embedder.embed_documents([(source_title, summary, body)])[0]
        return queries.to_pgvector(vector) if vector is not None else None

    def retire_sections(
        self, source_id: str, section: str | None = None, note: str = "", actor: str = "user"
    ) -> list[str]:
        """Marks one section, or every live section of a source, retired.

        Retirement only sets `deleted_at`; it bumps neither the section's version
        nor `sources.version` - only `upsert` moves those, so a retired section's
        version still reads as it did at the moment it was hidden. One changelog
        row is appended per section retired, carrying that section's unchanged
        version and the caller's `note`.

        @raises ValidationError if `note` is empty
        @raises NotFoundError if `source_id` is unknown, or `section` names no live row
        """
        if not note.strip():
            raise ValidationError("retire requires a non-empty note", field="note")

        with _cursor(self._connect) as cur:
            cur.execute(queries.SELECT_SOURCE, {"source_id": source_id})
            if cur.fetchone() is None:
                raise NotFoundError("no such source", what="source")

            cur.execute(
                queries.SELECT_LIVE_CHUNKS_FOR_RETIRE, {"source_id": source_id, "section": section}
            )
            rows = cur.fetchall()
            if not rows:
                what = "section" if section is not None else "source"
                raise NotFoundError(f"no live {what} to retire", what=what)

            retired: list[str] = []
            for row in rows:
                cur.execute(queries.RETIRE_CHUNK, {"chunk_id": row["chunk_id"]})
                cur.execute(
                    queries.INSERT_CHANGELOG,
                    {
                        "source_id": source_id,
                        "section": row["section"],
                        "version": row["version"],
                        "action": "retire",
                        "actor": actor,
                        "note": note,
                    },
                )
                retired.append(row["section"])

        return retired

    def render_source(self, source_id: str) -> str:
        """Renders every live chunk of one source as markdown, cited by the source's version.

        Output shape, exactly: `# <title>`, then `## <section>` and its body per
        live chunk in `chunk_id` order, then a trailing `wiki:<source_id> v<n>`
        line - `n` is `sources.version`, the counter bumped on every upsert to
        any section, so it reflects the freshness of the document as a whole.

        @raises NotFoundError if `source_id` is unknown
        """
        with _cursor(self._connect) as cur:
            cur.execute(queries.SELECT_SOURCE, {"source_id": source_id})
            source_row = cur.fetchone()
            if source_row is None:
                raise NotFoundError("no such source", what="source")

            cur.execute(
                queries.SELECT_CHUNKS,
                {"source_id": source_id, "section": None, "include_retired": False},
            )
            chunk_rows = cur.fetchall()

        lines = [f"# {source_row['title']}", ""]
        for row in chunk_rows:
            lines.append(f"## {row['section']}")
            lines.append(row["body"])
            lines.append("")
        lines.append(f"wiki:{source_id} v{source_row['version']}")
        return "\n".join(lines)

    def changelog_since(self, since: str, limit: int = 200) -> list[dict[str, Any]]:
        """Returns changelog rows at or after `since`, oldest first.

        @param since ISO-8601 timestamp or bare date, validated in Python (see
            `_parse_since`) before it reaches the `::timestamptz` cast in SQL
        @raises ValidationError if `since` is not a bare date or an ISO-8601 timestamp
        """
        since = _parse_since(since)
        with _cursor(self._connect) as cur:
            cur.execute(queries.SELECT_CHANGELOG_SINCE, {"since": since, "limit": limit})
            rows = cur.fetchall()
        for row in rows:
            row["at"] = _iso(row["at"])
        return rows

    def backfill(self) -> dict[str, int]:
        """Embeds every live chunk whose `embedding` is still `NULL`; safe to re-run.

        Not on the MCP surface (CONTRACT.md SS5's tool list names five tools, not six) -
        a maintenance operation run by hand or by a small script, over the same store a
        server or `wiki-ingest` already constructs. Reads the candidate rows in one
        transaction, then writes each embedded row's vector in its own - a crash mid-run
        loses at most the batch in flight, not progress already committed, and the next
        call only ever sees rows still `NULL` (CONTRACT.md SS5a: "re-running it is safe
        and cheap").

        @return `{"total": <candidate rows>, "embedded": <rows successfully embedded>}` -
            the difference is chunks an absent, disabled or failing embedder left `NULL`
        """
        with _cursor(self._connect) as cur:
            cur.execute(queries.SELECT_CHUNKS_NEEDING_EMBEDDING)
            rows = cur.fetchall()

        if not rows or self._embedder is None:
            return {"total": len(rows), "embedded": 0}

        vectors = self._embedder.embed_documents(
            [(row["title"], row["summary"], row["body"]) for row in rows]
        )
        embedded = 0
        for row, vector in zip(rows, vectors, strict=True):
            if vector is None:
                continue
            with _cursor(self._connect) as cur:
                cur.execute(
                    queries.UPDATE_CHUNK_EMBEDDING,
                    {"chunk_id": row["chunk_id"], "embedding": queries.to_pgvector(vector)},
                )
            embedded += 1
        return {"total": len(rows), "embedded": embedded}
