-- The newest top-level session id; used by the wrapper to resolve -c/--continue.
SELECT id FROM session WHERE parent_id IS NULL ORDER BY time_updated DESC LIMIT 1;
