-- Project-id reconciliation tables (columns touched by the wrapper).
CREATE TABLE project (
    id TEXT PRIMARY KEY,
    worktree TEXT NOT NULL,
    vcs TEXT,
    name TEXT,
    icon_url TEXT,
    icon_url_override TEXT,
    icon_color TEXT,
    time_created INTEGER NOT NULL,
    time_updated INTEGER NOT NULL,
    time_initialized INTEGER,
    sandboxes TEXT NOT NULL,
    commands TEXT
);
CREATE TABLE session (
    id TEXT PRIMARY KEY,
    project_id TEXT,
    path TEXT,
    directory TEXT,
    time_updated INTEGER
);
CREATE TABLE permission (
    id TEXT PRIMARY KEY,
    project_id TEXT,
    action TEXT,
    resource TEXT,
    time_created INTEGER,
    time_updated INTEGER
);
CREATE TABLE project_directory (
    project_id TEXT NOT NULL,
    directory TEXT NOT NULL,
    type TEXT,
    strategy TEXT,
    time_created INTEGER,
    PRIMARY KEY (project_id, directory)
);
CREATE TABLE workspace (
    id TEXT PRIMARY KEY,
    type TEXT,
    name TEXT,
    branch TEXT,
    directory TEXT,
    extra TEXT,
    project_id TEXT NOT NULL,
    time_used INTEGER
);