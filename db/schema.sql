-- One row per agent run. Kept deliberately minimal.
CREATE TABLE IF NOT EXISTS runs (
    id               BIGSERIAL PRIMARY KEY,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    repo_id          TEXT NOT NULL,
    bug_description  TEXT NOT NULL,
    mode             TEXT NOT NULL DEFAULT 'multi_agent',  -- e.g. multi_agent, baseline
    status           TEXT NOT NULL,                        -- resolved | failed | error
    attempts         INTEGER NOT NULL DEFAULT 0,
    tests_passed     INTEGER,
    tests_failed     INTEGER,
    test_results     JSONB,                                -- parsed pytest result
    execution_time_s DOUBLE PRECISION,
    relevant_files   JSONB,
    patch_diff       TEXT,
    agent_log        JSONB,                                -- step-by-step agent status
    options          JSONB                                 -- ablation settings used
);

CREATE INDEX IF NOT EXISTS runs_repo_id_idx ON runs (repo_id);

-- Token usage per run (for cost reporting). ALTER keeps older databases working.
ALTER TABLE runs ADD COLUMN IF NOT EXISTS llm_usage JSONB;
