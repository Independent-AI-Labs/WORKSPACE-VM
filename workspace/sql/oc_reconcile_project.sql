-- Fold every project row sharing a worktree into the canonical id opencode
-- resolves today, so sessions created before an origin remote was added stay
-- visible. :root and :canon are bound by workspace/scripts/opencode-wrapper.sh.
BEGIN IMMEDIATE;
INSERT OR IGNORE INTO project (id, worktree, vcs, name, icon_url, icon_url_override, icon_color, time_created, time_updated, time_initialized, sandboxes, commands)
    SELECT :canon, worktree, vcs, name, icon_url, icon_url_override, icon_color, time_created, time_updated, time_initialized, sandboxes, commands
    FROM project WHERE worktree = :root AND id <> :canon LIMIT 1;
UPDATE OR IGNORE session SET project_id = :canon WHERE project_id IN (SELECT id FROM project WHERE worktree = :root AND id <> :canon);
UPDATE OR IGNORE permission SET project_id = :canon WHERE project_id IN (SELECT id FROM project WHERE worktree = :root AND id <> :canon);
UPDATE OR IGNORE project_directory SET project_id = :canon WHERE project_id IN (SELECT id FROM project WHERE worktree = :root AND id <> :canon);
UPDATE OR IGNORE workspace SET project_id = :canon WHERE project_id IN (SELECT id FROM project WHERE worktree = :root AND id <> :canon);
DELETE FROM session WHERE project_id IN (SELECT id FROM project WHERE worktree = :root AND id <> :canon);
DELETE FROM permission WHERE project_id IN (SELECT id FROM project WHERE worktree = :root AND id <> :canon);
DELETE FROM project_directory WHERE project_id IN (SELECT id FROM project WHERE worktree = :root AND id <> :canon);
DELETE FROM workspace WHERE project_id IN (SELECT id FROM project WHERE worktree = :root AND id <> :canon);
DELETE FROM project WHERE worktree = :root AND id <> :canon;
COMMIT;