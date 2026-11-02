SELECT id FROM session WHERE parent_id IS NULL ORDER BY time_updated DESC LIMIT 1;
