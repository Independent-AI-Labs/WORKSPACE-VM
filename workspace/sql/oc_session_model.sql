-- The stored model JSON of one session; used by the wrapper to rewrite the
-- session's thinking-effort variant on resume.
SELECT model FROM session WHERE id = :sid;
