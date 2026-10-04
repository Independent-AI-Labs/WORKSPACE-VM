-- Does the opencode shard contain this session id?
-- Bound by workspace/scripts/opencode-wrapper.sh via sqlite3 .parameter.
SELECT count(*) FROM session WHERE id = :sid;
