-- Whether the opencode shard carries a project table (0 or 1).
-- Read by workspace/scripts/opencode-wrapper.sh before reconciliation.
SELECT count(*) FROM sqlite_master WHERE type='table' AND name='project';