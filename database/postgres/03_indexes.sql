-- =====================================================================
-- 03_indexes.sql
-- PostgreSQL automatically indexes PRIMARY KEY and UNIQUE columns
-- (so user_id, email, wall_id, both tokens, wish_id, media_id are
-- already covered). It does NOT index foreign keys automatically, so we
-- add those here based on how the app actually queries the data.
-- =====================================================================

-- "Show all walls I created" (organizer dashboard)
CREATE INDEX idx_walls_creator_id
    ON walls (creator_id);

-- "Load all wishes on this wall, oldest first" (the reveal page).
-- Composite index: filters by wall_id and returns rows already sorted.
CREATE INDEX idx_wishes_wall_created
    ON wishes (wall_id, created_at);

-- "Load all files attached to these wishes"
CREATE INDEX idx_media_wish_id
    ON media (wish_id);

-- Partial index: only walls still accepting wishes. Smaller than a full
-- index and used by the "lock expired walls" job, which only cares
-- about unlocked walls.
CREATE INDEX idx_walls_open_reveal_at
    ON walls (reveal_at)
    WHERE is_locked = FALSE;

-- Partial index: visible wishes only. The reveal page never shows hidden
-- ones, so there is no point indexing them.
CREATE INDEX idx_wishes_visible
    ON wishes (wall_id)
    WHERE is_hidden = FALSE;

-- To show the index is used, run in psql:
--   EXPLAIN ANALYZE SELECT * FROM wishes WHERE wall_id = 1 ORDER BY created_at;
-- (On tiny seed data Postgres may still choose a sequential scan because
--  it is cheaper. Use SET enable_seqscan = off; to demonstrate.)
