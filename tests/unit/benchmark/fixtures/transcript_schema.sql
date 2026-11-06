CREATE TABLE session (id TEXT PRIMARY KEY, title TEXT, directory TEXT);
CREATE TABLE message (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    time_created INTEGER NOT NULL,
    data TEXT NOT NULL
);
CREATE TABLE part (
    message_id TEXT NOT NULL,
    time_created INTEGER NOT NULL,
    data TEXT NOT NULL
);
