-- Project ids sharing one worktree (bound as :worktree).
SELECT id FROM project WHERE worktree = :worktree;