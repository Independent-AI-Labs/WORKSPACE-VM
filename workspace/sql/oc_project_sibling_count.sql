-- Count project rows sharing this worktree under a superseded id.
-- :root and :canon are bound by workspace/scripts/opencode-wrapper.sh.
SELECT count(*) FROM project WHERE worktree = :root AND id <> :canon;