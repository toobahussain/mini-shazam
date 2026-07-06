-- Run this once against your Postgres database:
--   psql -U postgres -d shazam -f schema.sql

CREATE TABLE IF NOT EXISTS songs (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    artist TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS fingerprints (
    hash BIGINT NOT NULL,
    song_id INTEGER NOT NULL REFERENCES songs(id) ON DELETE CASCADE,
    offset_time REAL NOT NULL
);

-- This index is the whole reason lookups are fast even with millions of rows
CREATE INDEX IF NOT EXISTS idx_fingerprints_hash ON fingerprints (hash);
