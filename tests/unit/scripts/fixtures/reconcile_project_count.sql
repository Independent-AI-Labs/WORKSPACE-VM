-- Count project rows for one worktree (bound as :worktree).
SELECT count(*) FROM project WHERE worktree = :worktree;