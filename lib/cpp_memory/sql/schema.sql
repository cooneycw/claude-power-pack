-- CPP common-memory: shared friction-knowledge ledger (bucket-2-plus).
-- Scope: portable CPP knowledge / infra traps + a dedup/rejection ledger.
-- NOT a config-distribution channel and NOT an auto-apply path for permissions.
-- Idempotent: safe to re-run.

CREATE TABLE IF NOT EXISTS learnings (
    id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    fingerprint    TEXT NOT NULL UNIQUE,                 -- deterministic cross-VM dedup key
    friction_class TEXT NOT NULL CHECK (friction_class IN
                     ('permission','gate_failure','red_output',
                      'manual_intervention','infra_trap','knowledge')),
    fix_scope      TEXT NOT NULL CHECK (fix_scope IN ('repo_file','permission','knowledge')),
    title          TEXT NOT NULL,
    body           TEXT NOT NULL,                        -- the portable knowledge / trap description
    proposed_fix   TEXT,                                 -- optional remediation text (never auto-applied)
    status         TEXT NOT NULL DEFAULT 'proposed'
                     CHECK (status IN ('proposed','applied','rejected','superseded')),
    confidence     REAL NOT NULL DEFAULT 0.5,
    evidence       JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS learnings_class_idx  ON learnings (friction_class);
CREATE INDEX IF NOT EXISTS learnings_status_idx ON learnings (status);

-- Every time a VM/repo re-encounters the same learning, record a sighting.
-- Cross-VM occurrence count is the "N machines hit this" signal.
CREATE TABLE IF NOT EXISTS sightings (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    learning_id  BIGINT NOT NULL REFERENCES learnings (id) ON DELETE CASCADE,
    source_vm    TEXT NOT NULL,
    source_repo  TEXT,
    seen_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS sightings_learning_idx ON sightings (learning_id);

-- Per-VM apply/reject audit. This IS the "do not re-propose rejected fixes"
-- ledger: a human confirms application on that machine, never a cross-VM push.
CREATE TABLE IF NOT EXISTS applications (
    id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    learning_id  BIGINT NOT NULL REFERENCES learnings (id) ON DELETE CASCADE,
    source_vm    TEXT NOT NULL,
    action       TEXT NOT NULL CHECK (action IN ('applied','rejected')),
    actor        TEXT,                                   -- human who confirmed
    note         TEXT,
    decided_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (learning_id, source_vm)
);
CREATE INDEX IF NOT EXISTS applications_learning_idx ON applications (learning_id);
