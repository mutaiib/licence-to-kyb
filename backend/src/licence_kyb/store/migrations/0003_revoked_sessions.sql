-- Sign-out ends a session on the server (traceability review, round 3; FR-022). A session's
-- ID is stored here until the session would have expired anyway.
CREATE TABLE revoked_sessions (
    session_id TEXT PRIMARY KEY,
    expires_at INTEGER NOT NULL
);

-- Never written: review decisions are recorded as audit events. It also held a plain-text
-- reason column.
DROP TABLE IF EXISTS review_decisions;
