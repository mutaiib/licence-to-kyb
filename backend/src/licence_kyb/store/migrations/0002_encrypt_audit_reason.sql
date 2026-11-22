-- Reviewers' free-text reasons can name people, so they are encrypted like old and new
-- values (security review, round 2). Reasons written before this migration are dropped:
-- they were plain text, and this project keeps no plain-text personal data at rest.
ALTER TABLE audit_events RENAME COLUMN reason TO reason_enc;
UPDATE audit_events SET reason_enc = NULL;
