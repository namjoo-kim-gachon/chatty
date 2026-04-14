CREATE TABLE IF NOT EXISTS users (
    id             TEXT PRIMARY KEY,
    email          TEXT UNIQUE NOT NULL,
    nickname       TEXT UNIQUE NOT NULL,
    google_id      TEXT,
    is_admin       BOOLEAN NOT NULL DEFAULT FALSE,
    is_active      BOOLEAN NOT NULL DEFAULT FALSE,
    token_version  INTEGER NOT NULL DEFAULT 0,
    created_at     DOUBLE PRECISION NOT NULL
);

CREATE TABLE IF NOT EXISTS rooms (
    id              TEXT PRIMARY KEY,
    room_number     INTEGER NOT NULL,
    name            TEXT NOT NULL,
    type            TEXT NOT NULL DEFAULT 'chat',
    is_private      BOOLEAN NOT NULL DEFAULT FALSE,
    is_dm           BOOLEAN NOT NULL DEFAULT FALSE,
    password_hash   TEXT,
    owner_id        TEXT NOT NULL,
    description     TEXT NOT NULL DEFAULT '',
    llm_context     TEXT NOT NULL DEFAULT '',
    announcement    TEXT NOT NULL DEFAULT '',
    max_members     INTEGER NOT NULL DEFAULT 500,
    slow_mode_sec   INTEGER NOT NULL DEFAULT 1,
    game_server_url TEXT,
    created_by      TEXT NOT NULL,
    created_at      DOUBLE PRECISION NOT NULL,
    updated_at      DOUBLE PRECISION NOT NULL,
    deleted_at      DOUBLE PRECISION,
    FOREIGN KEY (owner_id)   REFERENCES users(id),
    FOREIGN KEY (created_by) REFERENCES users(id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_rooms_number_active
    ON rooms(room_number) WHERE deleted_at IS NULL;

CREATE TABLE IF NOT EXISTS room_tags (
    room_id    TEXT NOT NULL,
    tag        TEXT NOT NULL,
    PRIMARY KEY (room_id, tag),
    FOREIGN KEY (room_id) REFERENCES rooms(id)
);

CREATE TABLE IF NOT EXISTS room_attrs (
    room_id    TEXT NOT NULL,
    key        TEXT NOT NULL,
    value      TEXT NOT NULL,
    PRIMARY KEY (room_id, key),
    FOREIGN KEY (room_id) REFERENCES rooms(id)
);

CREATE TABLE IF NOT EXISTS room_members (
    room_id    TEXT NOT NULL,
    user_id    TEXT NOT NULL,
    joined_at  DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (room_id, user_id),
    FOREIGN KEY (room_id) REFERENCES rooms(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS global_bans (
    id          TEXT PRIMARY KEY,
    user_id     TEXT UNIQUE NOT NULL,
    reason      TEXT NOT NULL DEFAULT '',
    banned_by   TEXT NOT NULL,
    created_at  DOUBLE PRECISION NOT NULL,
    expires_at  DOUBLE PRECISION,
    FOREIGN KEY (user_id)   REFERENCES users(id),
    FOREIGN KEY (banned_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS room_bans (
    id          TEXT PRIMARY KEY,
    room_id     TEXT NOT NULL,
    user_id     TEXT NOT NULL,
    reason      TEXT NOT NULL DEFAULT '',
    banned_by   TEXT NOT NULL,
    created_at  DOUBLE PRECISION NOT NULL,
    expires_at  DOUBLE PRECISION,
    UNIQUE (room_id, user_id),
    FOREIGN KEY (room_id)   REFERENCES rooms(id),
    FOREIGN KEY (user_id)   REFERENCES users(id),
    FOREIGN KEY (banned_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS room_mutes (
    id          TEXT PRIMARY KEY,
    room_id     TEXT NOT NULL,
    user_id     TEXT NOT NULL,
    reason      TEXT NOT NULL DEFAULT '',
    muted_by    TEXT NOT NULL,
    created_at  DOUBLE PRECISION NOT NULL,
    expires_at  DOUBLE PRECISION,
    UNIQUE (room_id, user_id),
    FOREIGN KEY (room_id)  REFERENCES rooms(id),
    FOREIGN KEY (user_id)  REFERENCES users(id),
    FOREIGN KEY (muted_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS reports (
    id             TEXT PRIMARY KEY,
    reporter_id    TEXT NOT NULL,
    target_type    TEXT NOT NULL,
    target_id      TEXT NOT NULL,
    room_id        TEXT,
    reason         TEXT NOT NULL,
    detail         TEXT NOT NULL DEFAULT '',
    status         TEXT NOT NULL DEFAULT 'pending',
    resolved_by    TEXT,
    created_at     DOUBLE PRECISION NOT NULL,
    resolved_at    DOUBLE PRECISION,
    FOREIGN KEY (reporter_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS room_filters (
    id           TEXT PRIMARY KEY,
    room_id      TEXT NOT NULL,
    pattern      TEXT NOT NULL,
    pattern_type TEXT NOT NULL DEFAULT 'keyword',
    action       TEXT NOT NULL DEFAULT 'block',
    created_by   TEXT NOT NULL,
    created_at   DOUBLE PRECISION NOT NULL,
    FOREIGN KEY (room_id)    REFERENCES rooms(id),
    FOREIGN KEY (created_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS global_filters (
    id           TEXT PRIMARY KEY,
    pattern      TEXT NOT NULL,
    pattern_type TEXT NOT NULL DEFAULT 'keyword',
    action       TEXT NOT NULL DEFAULT 'block',
    created_by   TEXT NOT NULL,
    created_at   DOUBLE PRECISION NOT NULL,
    FOREIGN KEY (created_by) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_global_bans_user    ON global_bans(user_id);
CREATE INDEX IF NOT EXISTS idx_room_bans_room_user  ON room_bans(room_id, user_id);
CREATE INDEX IF NOT EXISTS idx_room_mutes_room_user ON room_mutes(room_id, user_id);
CREATE INDEX IF NOT EXISTS idx_reports_status       ON reports(status);

CREATE TABLE IF NOT EXISTS room_seq (
    room_id  TEXT PRIMARY KEY,
    seq      INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (room_id) REFERENCES rooms(id)
);


CREATE TABLE IF NOT EXISTS messages (
    id          TEXT PRIMARY KEY,
    room_id     TEXT NOT NULL,
    user_id     TEXT NOT NULL,
    nickname    TEXT NOT NULL,
    text        TEXT NOT NULL,
    msg_type    TEXT NOT NULL DEFAULT 'chat',
    seq         INTEGER NOT NULL,
    created_at  DOUBLE PRECISION NOT NULL,
    FOREIGN KEY (room_id) REFERENCES rooms(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_messages_room_seq ON messages(room_id, seq);
CREATE INDEX IF NOT EXISTS idx_messages_room_ts  ON messages(room_id, created_at);
CREATE INDEX IF NOT EXISTS idx_room_tags_tag     ON room_tags(tag);

-- Schema migrations (idempotent, handles existing databases)
ALTER TABLE users DROP COLUMN IF EXISTS password_hash;
ALTER TABLE users ADD COLUMN IF NOT EXISTS google_id TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_google_id
    ON users(google_id) WHERE google_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS refresh_tokens (
    id         TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL,
    expires_at DOUBLE PRECISION NOT NULL,
    created_at DOUBLE PRECISION NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user ON refresh_tokens(user_id);
