-- Seed one project row (bound as :pid and :worktree).
INSERT INTO project (id, worktree, vcs, time_created, time_updated, sandboxes)
VALUES (:pid, :worktree, 'git', 1, 1, '[]');