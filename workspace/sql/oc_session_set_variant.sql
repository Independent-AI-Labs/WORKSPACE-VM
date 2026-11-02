-- Store a session's thinking-effort variant; used by the wrapper on resume.
UPDATE session SET model = json_set(model, '$.variant', :variant) WHERE id = :sid;
