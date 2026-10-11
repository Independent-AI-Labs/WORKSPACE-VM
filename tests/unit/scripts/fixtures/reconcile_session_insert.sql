-- Seed one session row (bound as :sid, :pid, :directory).
INSERT INTO session (id, project_id, directory, time_updated)
VALUES (:sid, :pid, :directory, 1);