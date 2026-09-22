-- Wiki schema. Runs once, on first container start, against an empty volume.
-- A later change needs a migration, not a re-run.

CREATE EXTENSION IF NOT EXISTS vector;    -- column type below; pgvector image ships it disabled
CREATE EXTENSION IF NOT EXISTS pg_trgm;   -- substring fallback, and what makes CJK searchable

CREATE TABLE sources (
  source_id   text PRIMARY KEY,          -- 'lotteon/order-status-mapping'
  title       text NOT NULL,
  version     int  NOT NULL DEFAULT 1,   -- bumped on any section change; changelog cursor
  updated_at  timestamptz NOT NULL DEFAULT now(),
  updated_by  text NOT NULL              -- pane name or 'user'
);

CREATE TABLE chunks (
  chunk_id    bigserial PRIMARY KEY,
  source_id   text NOT NULL REFERENCES sources ON DELETE CASCADE,
  section     text NOT NULL,             -- heading slug, e.g. 'step-3'
  summary     text NOT NULL,             -- 50-100 tokens, whole-source context
  body        text NOT NULL,             -- <= 200 words, enforced by upsert
  version     int  NOT NULL DEFAULT 1,   -- per-section; what expected_version checks
  deleted_at  timestamptz,               -- non-NULL = retired; row kept, hidden from search
  fts         tsvector GENERATED ALWAYS AS (to_tsvector('english', summary || ' ' || body)) STORED,
  embedding   vector(768),               -- filled by upsert/backfill; NULL if the embedder failed
  UNIQUE (source_id, section)
);
CREATE INDEX chunks_fts  ON chunks USING gin (fts)               WHERE deleted_at IS NULL;
CREATE INDEX chunks_trgm ON chunks USING gin (body gin_trgm_ops) WHERE deleted_at IS NULL;
CREATE INDEX chunks_src  ON chunks (source_id, section);
-- Fresh installs only (CONTRACT.md SS5a). An already-initialised database does NOT get
-- this by re-running schema.sql - see MIGRATION-vector.md for the existing-database path.
CREATE INDEX chunks_hnsw ON chunks USING hnsw (embedding vector_cosine_ops)
  WHERE deleted_at IS NULL;

CREATE TABLE changelog (
  id          bigserial PRIMARY KEY,
  source_id   text NOT NULL,
  section     text NOT NULL,
  version     int  NOT NULL,
  action      text NOT NULL,             -- 'upsert' | 'retire'
  actor       text NOT NULL,
  at          timestamptz NOT NULL DEFAULT now(),
  note        text
);
CREATE INDEX changelog_at ON changelog (at DESC);
