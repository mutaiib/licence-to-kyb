-- Forward-only. Every write entity has a unique key (data-model.md, "Writes and resumption").
CREATE TABLE runs (
  run_id          TEXT PRIMARY KEY,
  file_sha256     TEXT NOT NULL UNIQUE,
  applicant_name  TEXT NOT NULL,              -- encrypted when a cipher is configured
  status          TEXT NOT NULL DEFAULT 'received',
  route           TEXT,
  reasons_json    TEXT NOT NULL DEFAULT '[]',
  form_version    INTEGER NOT NULL DEFAULT 0,
  deadline_at     TEXT,
  cost_usd        REAL NOT NULL DEFAULT 0,
  duration_ms     INTEGER NOT NULL DEFAULT 0,
  created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE files (
  run_id          TEXT PRIMARY KEY REFERENCES runs(run_id) ON DELETE CASCADE,
  mime            TEXT NOT NULL,
  page_count      INTEGER NOT NULL,
  megapixels      REAL NOT NULL,
  encrypted_path  TEXT NOT NULL
);

CREATE TABLE review_decisions (
  decision_id     TEXT PRIMARY KEY,
  run_id          TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
  form_version    INTEGER NOT NULL,
  target          TEXT NOT NULL,
  action          TEXT NOT NULL CHECK (action IN ('approve','correct','override')),
  value_enc       TEXT,
  reason          TEXT,
  reviewer        TEXT NOT NULL,
  ts              TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE approvals (
  action_id       TEXT PRIMARY KEY,
  run_id          TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
  form_version    INTEGER NOT NULL,
  reviewer        TEXT NOT NULL,
  ts              TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  UNIQUE (run_id, form_version)
);

CREATE TABLE submissions (
  submission_id   TEXT PRIMARY KEY,
  action_id       TEXT NOT NULL UNIQUE,
  run_id          TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
  form_version    INTEGER NOT NULL,
  form_enc        TEXT NOT NULL,
  approved_by     TEXT NOT NULL,
  verified        INTEGER,
  ts              TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  UNIQUE (run_id, form_version)
);

CREATE TABLE audit_events (
  event_key       TEXT PRIMARY KEY,
  seq             INTEGER NOT NULL,
  run_id          TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
  action          TEXT NOT NULL,
  target          TEXT,
  old_enc         TEXT,
  new_enc         TEXT,
  reason          TEXT,
  actor           TEXT NOT NULL,
  ts              TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE INDEX audit_by_run ON audit_events(run_id, seq);

CREATE TABLE captured_corrections (
  capture_key          TEXT PRIMARY KEY,
  run_id               TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
  field                TEXT NOT NULL,
  read_value_enc       TEXT NOT NULL,
  corrected_value_enc  TEXT NOT NULL,
  fault_group          TEXT NOT NULL,
  status               TEXT NOT NULL DEFAULT 'pending'
                       CHECK (status IN ('pending','approved_for_eval','discarded'))
);

CREATE TABLE spans (
  span_id            TEXT PRIMARY KEY,
  parent_id          TEXT,
  run_id             TEXT REFERENCES runs(run_id) ON DELETE CASCADE,
  kind               TEXT NOT NULL CHECK (kind IN ('step','model_call','tool_call')),
  name               TEXT NOT NULL,
  requested_model    TEXT,
  serving_model      TEXT,
  effort             TEXT,
  input_tokens       INTEGER NOT NULL DEFAULT 0,
  output_tokens      INTEGER NOT NULL DEFAULT 0,
  thinking_tokens    INTEGER NOT NULL DEFAULT 0,
  cache_read_tokens  INTEGER NOT NULL DEFAULT 0,
  latency_ms         INTEGER NOT NULL DEFAULT 0,
  cost_usd           REAL NOT NULL DEFAULT 0,
  prompt_hash        TEXT,
  error_code         TEXT,
  raw_result_enc     TEXT,
  model_view_enc     TEXT,
  started_at         TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE INDEX spans_by_run ON spans(run_id, started_at);
