"""Every SQL statement the wiki issues, as named, parameterised constants.

One file holds every statement so a reviewer checks all of the wiki's SQL in one
pass (CONTRACT.md SS5). Every value crosses the wire as a psycopg named parameter
(``%(name)s``); none is ever interpolated into the query text with an f-string or
a Python ``%``-format applied by this module. A literal ``%`` needed in the SQL
itself (the ``LIKE`` patterns below) is written ``%%``, doubled so psycopg's own
``%``-style substitution leaves one ``%`` behind for Postgres to see.

``embedding`` appears only in the constants named for it below (``SEARCH_VECTOR``,
``UPDATE_CHUNK_EMBEDDING``, ``SELECT_CHUNKS_NEEDING_EMBEDDING``, ``CREATE_INDEX_CHUNKS_HNSW``)
- CONTRACT.md SS5a spends the doc's earlier deferral of vector search; every other
statement still never names the column.
"""

from __future__ import annotations

SELECT_SOURCE = """
SELECT source_id, title, version, updated_at, updated_by
FROM sources
WHERE source_id = %(source_id)s
"""
"""Fetches one source row by identity, for `get` and `render` and existence checks."""

SELECT_SOURCE_FOR_UPDATE = """
SELECT source_id, title, version
FROM sources
WHERE source_id = %(source_id)s
FOR UPDATE
"""
"""Locks the source row inside an `upsert` transaction, ahead of the conflict check."""

INSERT_SOURCE_IF_ABSENT = """
INSERT INTO sources (source_id, title, version, updated_by)
VALUES (%(source_id)s, %(title)s, 0, %(actor)s)
ON CONFLICT (source_id) DO NOTHING
"""
"""Creates the source row on a section's first write, at version 0, not the schema's `DEFAULT 1`.

BUMP_SOURCE_VERSION always runs in the same upsert transaction right after this,
including on a brand-new source. Starting at 0 means that first bump lands the
source on v1, matching the v1 chunk it was created to hold; starting at the
schema default of 1 would leave a one-section source citing `v2` over a `v1`
chunk (CONTRACT.md SS5 rule 8)."""

BUMP_SOURCE_VERSION = """
UPDATE sources
SET version = version + 1, updated_at = now(), updated_by = %(actor)s
WHERE source_id = %(source_id)s
"""
"""Advances the source-level version and freshness stamp on every successful upsert."""

SELECT_UPSERT_PRECHECK = """
SELECT
  (SELECT title FROM sources WHERE source_id = %(source_id)s) AS source_title,
  (SELECT version FROM chunks WHERE source_id = %(source_id)s AND section = %(section)s)
    AS chunk_version
"""
"""Reads a source's title and a section's version **without locking**, before the transaction.

CONTRACT.md SS5a: `upsert` "embeds before it opens the transaction", so the document
prefix's `{title}` has to be known before `SELECT_SOURCE_FOR_UPDATE` ever runs. Nothing
in the wiki ever updates `sources.title` after `INSERT_SOURCE_IF_ABSENT` writes it, so
reading it unlocked cannot go stale for a source that already exists.

`chunk_version` is read in the same round trip purely to skip a doomed embed: when it
already disagrees with the caller's `expected_version`, the transaction below is going to
raise `VersionConflict`, and a 30-second network call spent on a write that will not
happen is pure waste. It is advisory only - the authoritative check still happens under
`SELECT_CHUNK_FOR_UPDATE` inside the transaction, never here.

Deliberately two scalar sub-selects rather than a join: `chunks` may hold no row for this
section (a first write) and `sources` may hold no row for this source, and a scalar
sub-select answers `NULL` for either case without an outer join over a synthetic row."""

SELECT_CHUNK_FOR_UPDATE = """
SELECT chunk_id, version, body, summary
FROM chunks
WHERE source_id = %(source_id)s AND section = %(section)s
FOR UPDATE
"""
"""Locks one section's row - live or retired - so its version check races nothing."""

INSERT_CHUNK = """
INSERT INTO chunks (source_id, section, summary, body, version, embedding)
VALUES (%(source_id)s, %(section)s, %(summary)s, %(body)s, 1, %(embedding)s::vector)
ON CONFLICT (source_id, section) DO NOTHING
RETURNING version
"""
"""Creates a brand-new section at version 1; only attempted when `expected_version` is 0.

`SELECT_CHUNK_FOR_UPDATE` locks nothing when the row is absent, so two concurrent
first-writers can both pass the `expected_version == 0` check and both reach this
INSERT. `ON CONFLICT (source_id, section) DO NOTHING` makes the loser's insert a
no-op instead of a raw `UniqueViolation`: it returns no row, and the caller
(`WikiStore.upsert_section`) re-reads the section that won and raises
`VersionConflict` against it, inside the same transaction. This is structural
rather than a catch on the exception type, because it was never confirmed
against a live Postgres whether the loser actually raises `UniqueViolation`
rather than a serialization failure under `SELECT ... FOR UPDATE`.

`embedding` is written by this same INSERT rather than by a follow-up UPDATE
(CONTRACT.md SS5a): the vector was computed before the transaction opened, from
this exact `summary` and `body`, so row and vector land in one statement and can
never drift apart. It binds `NULL` when the embedder failed or was absent."""

UPDATE_CHUNK = """
UPDATE chunks
SET body = %(body)s, summary = %(summary)s, version = version + 1, deleted_at = NULL,
    embedding = %(embedding)s::vector
WHERE chunk_id = %(chunk_id)s
RETURNING version
"""
"""Rewrites an existing section and clears `deleted_at` - an upsert reverses a retirement.

`embedding` is overwritten in the same statement as the body it describes (CONTRACT.md
SS5a), including with `NULL` when the embedder failed: the previous vector was computed
from the previous body, so keeping it here would leave a chunk indexed under text it no
longer holds. A `NULL` left by a failed embed is what `backfill` exists to fill."""

INSERT_CHANGELOG = """
INSERT INTO changelog (source_id, section, version, action, actor, note)
VALUES (%(source_id)s, %(section)s, %(version)s, %(action)s, %(actor)s, %(note)s)
"""
"""Appends one changelog row; `action` is `'upsert'` or `'retire'`, `note` may be NULL."""

SELECT_CHUNKS = """
SELECT chunk_id, section, summary, body, version, deleted_at
FROM chunks
WHERE source_id = %(source_id)s
  AND (%(section)s::text IS NULL OR section = %(section)s)
  AND (%(include_retired)s OR deleted_at IS NULL)
ORDER BY chunk_id
"""
"""Backs both `get` (any section filter, retired opt-in) and `render` (all, live only)."""

SELECT_LIVE_CHUNKS_FOR_RETIRE = """
SELECT chunk_id, section, version
FROM chunks
WHERE source_id = %(source_id)s
  AND deleted_at IS NULL
  AND (%(section)s::text IS NULL OR section = %(section)s)
ORDER BY chunk_id
FOR UPDATE
"""
"""Locks every live section matching the retire request - one row, or the whole source."""

RETIRE_CHUNK = """
UPDATE chunks
SET deleted_at = now()
WHERE chunk_id = %(chunk_id)s
"""
"""Hides one chunk from both search indexes; the row and its history stay in place."""

SEARCH_FTS = """
SELECT source_id, section, version, summary, body,
       ts_rank_cd(fts, plainto_tsquery('english', %(query)s)) AS rank
FROM chunks
WHERE deleted_at IS NULL
  AND fts @@ plainto_tsquery('english', %(query)s)
  AND (%(source_prefix)s::text IS NULL OR source_id LIKE %(source_prefix)s || '%%' ESCAPE '\\')
  AND (%(exclude_prefix)s::text IS NULL
       OR source_id NOT LIKE %(exclude_prefix)s || '%%' ESCAPE '\\')
ORDER BY rank DESC
LIMIT %(k)s
"""
"""Ranks live chunks whose `fts` matches the plain-text query - the primary search pass.

`to_tsvector('english', ...)` (the schema's generated `fts` column) does not
segment Korean or Japanese into tokens, so a CJK query matches nothing here -
see SEARCH_TRGM_FALLBACK, the pass that reaches those chunks instead.

`source_prefix` arrives pre-escaped by `WikiStore._escape_like` - `%`, `_` and
the escape character itself are backslash-escaped there, in Python, before the
value is bound as a parameter. `ESCAPE '\\'` names that same character to
Postgres so `plan_` matches only a literal `plan_`, never `planX`. The
trailing `'%%'` stays doubled: it is unescaped literal wildcard text, not part
of the caller's value, and psycopg3 only reduces `%%` to `%` when parameters
are passed, which both statements here always do.

`exclude_prefix` is CONTRACT.md SS5b's inbox exclusion: `NULL` (unrestricted) when the
caller asked for the inbox by name or opted in, else the escaped `inbox_prefix` from
config. It excludes *before* `LIMIT` takes effect, in the same WHERE as every other
filter - an inbox row must never consume a candidate slot it would then be dropped from
after ranking.
"""

SEARCH_TRGM_FALLBACK = """
SELECT source_id, section, version, summary, body,
       similarity(body, %(query)s) AS rank
FROM chunks
WHERE deleted_at IS NULL
  AND similarity(body, %(query)s) > 0
  AND (%(source_prefix)s::text IS NULL OR source_id LIKE %(source_prefix)s || '%%' ESCAPE '\\')
  AND (%(exclude_prefix)s::text IS NULL
       OR source_id NOT LIKE %(exclude_prefix)s || '%%' ESCAPE '\\')
ORDER BY rank DESC
LIMIT %(limit)s
"""
"""Fills a full-text shortfall with `pg_trgm` similarity - CJK's only path into search.

Filters on the bare `similarity() > 0` rather than the `%` operator, so a short
CJK query is never dropped by `pg_trgm.similarity_threshold` (default 0.3)
before ranking runs. That trades an unindexed sequential scan for recall, an
acceptable trade at the "hundreds of chunks" scale this wiki is sized for
(see `knowledges/herdr-leader-swarm.md` §5, Data Plane).

`exclude_prefix` mirrors SEARCH_FTS exactly - the same inbox boundary applied in the same
WHERE clause, ahead of `LIMIT`, so the fallback cannot backfill with the rows the primary
pass just excluded.
"""

SELECT_CHANGELOG_SINCE = """
SELECT source_id, section, version, action, actor, at, note
FROM changelog
WHERE at >= %(since)s::timestamptz
ORDER BY at ASC
LIMIT %(limit)s
"""
"""Lists changelog rows oldest-first; the `::timestamptz` cast accepts a bare date too."""

SEARCH_VECTOR = """
SELECT source_id, section, version, summary, body,
       embedding <=> %(query_vec)s::vector AS rank
FROM chunks
WHERE deleted_at IS NULL
  AND embedding IS NOT NULL
  AND (%(source_prefix)s::text IS NULL OR source_id LIKE %(source_prefix)s || '%%' ESCAPE '\\')
  AND (%(exclude_prefix)s::text IS NULL
       OR source_id NOT LIKE %(exclude_prefix)s || '%%' ESCAPE '\\')
ORDER BY rank ASC
LIMIT %(k)s
"""
"""Ranks live, embedded chunks by cosine distance - CONTRACT.md SS5a's third search pass.

`<=>` is pgvector's cosine-distance operator, matching `chunks_hnsw`'s `vector_cosine_ops`
(`CREATE_INDEX_CHUNKS_HNSW` below); smaller is closer, so this orders `ASC` where the two
lexical passes order `DESC` on their own rank. `embedding IS NOT NULL` excludes a chunk an
embedder failure (or a not-yet-backfilled row) left without a vector - `WikiStore.search`
never runs this statement at all when the embedder itself is disabled or unreachable for
the query, so `vector_available` reports that before this statement would ever execute.
`query_vec` arrives as the `'[0.1,0.2,...]'` text `to_pgvector` produces below, cast with
`::vector` - psycopg has no adapter of its own for the `vector` type. `source_prefix`
escaping matches `SEARCH_FTS`/`SEARCH_TRGM_FALLBACK` exactly (CONTRACT.md SS5 rule 9).
`exclude_prefix` is the same inbox boundary as the two lexical passes (CONTRACT.md SS5b) -
every ranked pass excludes it identically, so fusion never has to reconcile passes that
disagree about what "the inbox" means."""

UPDATE_CHUNK_EMBEDDING = """
UPDATE chunks
SET embedding = %(embedding)s::vector
WHERE chunk_id = %(chunk_id)s
  AND embedding IS NULL
"""
"""Fills one still-empty chunk vector, for `WikiStore.backfill` alone.

`upsert` does not use this: it writes the vector in the same statement as the chunk
(`INSERT_CHUNK` / `UPDATE_CHUNK`), so nothing there needs a second UPDATE.

`AND embedding IS NULL` is what makes backfill safe to run beside live writers. Backfill
reads its candidates in one transaction and writes each vector in another, so an `upsert`
can rewrite a chunk's body in between; without this guard, backfill would then overwrite
that fresh vector with the one it computed from the body it read minutes earlier - the
exact chunk/embedding drift CONTRACT.md SS5a forbids. Re-reading `NULL` is also why
re-running backfill stays cheap: a row another run already filled is skipped by the
`WHERE`, not just by the candidate query."""

SELECT_CHUNKS_NEEDING_EMBEDDING = """
SELECT c.chunk_id, c.source_id, c.section, c.summary, c.body, s.title
FROM chunks c
JOIN sources s ON s.source_id = c.source_id
WHERE c.deleted_at IS NULL
  AND c.embedding IS NULL
ORDER BY c.chunk_id
"""
"""Lists every live chunk still missing a vector, for `WikiStore.backfill`.

Joins `sources` for `title`: the document prefix (CONTRACT.md SS5a) needs the source's
real title, which `chunks` itself does not carry. Unbounded by a `LIMIT` - a re-run after
a partial failure asks this same question again and only ever sees what is still `NULL`,
so backfill is safe and cheap to repeat rather than needing its own cursor or offset."""

CREATE_INDEX_CHUNKS_HNSW = """
CREATE INDEX chunks_hnsw ON chunks USING hnsw (embedding vector_cosine_ops)
  WHERE deleted_at IS NULL
"""
"""The vector index, for `schema.sql` (fresh installs) and `MIGRATION-vector.md` (existing
databases - owned by a separate migration, never re-run from `schema.sql` itself).

`vector_cosine_ops` matches the `<=>` operator `SEARCH_VECTOR` uses; partial on
`deleted_at IS NULL` like `chunks_fts` and `chunks_trgm`, so a retired chunk leaves every
index together (CONTRACT.md SS5a)."""


def to_pgvector(values: list[float]) -> str:
    """Formats floats as the `'[v1,v2,...]'` text pgvector's input parser accepts.

    The one place this conversion happens: psycopg does not adapt a Python `list` to the
    `vector` type on its own, so every caller that binds `embedding` or `query_vec` -
    `WikiStore.upsert_section`, `WikiStore.backfill`, `WikiStore.search` - passes a plain
    string through this function rather than reimplementing the format, and the SQL casts
    it explicitly with `::vector`.
    """
    return "[" + ",".join(str(float(value)) for value in values) + "]"
