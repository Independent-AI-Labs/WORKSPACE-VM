-- Whether the opencode shard carries a session table (0 or 1).
-- Read by workspace/scripts/opencode-wrapper.sh before cross-db resume.
SELECT count(*) FROM sqlite_master WHERE type='table' AND name='session';
