-- =====================================================================
-- 05_views.sql
-- Views are saved queries. The backend reads from them instead of
-- repeating the same JOINs everywhere, and they hide columns the
-- frontend should never see (tokens, password hashes).
--
--   v_wall_summary      one row per wall with counts (organizer dashboard)
--   v_revealed_wishes   visible wishes of walls that have opened (reveal page)
--   v_wish_media        each wish with its files as a JSON array
--   v_open_walls        walls still accepting wishes
-- =====================================================================

DROP VIEW IF EXISTS v_wish_media      CASCADE;
DROP VIEW IF EXISTS v_revealed_wishes CASCADE;
DROP VIEW IF EXISTS v_wall_summary    CASCADE;
DROP VIEW IF EXISTS v_open_walls      CASCADE;

-- ---------------------------------------------------------------------
-- Organizer dashboard: how many wishes and files each wall has.
-- LEFT JOINs so that walls with zero wishes still appear (count = 0).
-- COUNT(DISTINCT ...) because joining wishes AND media multiplies rows.
-- FILTER (WHERE ...) counts only matching rows (PostgreSQL extension).
-- ---------------------------------------------------------------------
CREATE VIEW v_wall_summary AS
SELECT
    w.wall_id,
    w.birthday_person_name,
    w.birthday_date,
    w.reveal_at,
    w.creator_id,
    u.full_name                                              AS organizer,
    CASE
        WHEN w.is_locked           THEN 'locked'
        WHEN now() >= w.reveal_at  THEN 'revealed'
        ELSE 'collecting'
    END                                                      AS status,
    COUNT(DISTINCT ws.wish_id)                               AS total_wishes,
    COUNT(m.media_id) FILTER (WHERE m.media_type = 'image')  AS photos,
    COUNT(m.media_id) FILTER (WHERE m.media_type = 'audio')  AS voice_notes,
    COUNT(m.media_id) FILTER (WHERE m.media_type = 'video')  AS videos,
    COALESCE(SUM(m.file_size_bytes), 0)                      AS storage_bytes
FROM walls w
JOIN users       u  ON u.user_id  = w.creator_id
LEFT JOIN wishes ws ON ws.wall_id = w.wall_id AND ws.is_hidden = FALSE
LEFT JOIN media  m  ON m.wish_id  = ws.wish_id
GROUP BY w.wall_id, u.full_name;


-- ---------------------------------------------------------------------
-- Reveal page: only wishes that are visible AND whose wall has opened.
-- Even if the backend has a bug and forgets to check the date, this
-- view will never return wishes early. Security enforced in the DB.
-- ---------------------------------------------------------------------
CREATE VIEW v_revealed_wishes AS
SELECT
    w.wall_id,
    w.reveal_token,
    w.birthday_person_name,
    ws.wish_id,
    ws.sender_name,
    ws.sender_relation,
    ws.message_text,
    ws.created_at
FROM walls w
JOIN wishes ws ON ws.wall_id = w.wall_id
WHERE ws.is_hidden = FALSE
  AND now() >= w.reveal_at;


-- ---------------------------------------------------------------------
-- Each wish with all of its files bundled into one JSON array, so the
-- API can return a wish and its media in a single row.
-- ---------------------------------------------------------------------
CREATE VIEW v_wish_media AS
SELECT
    rw.wall_id,
    rw.reveal_token,
    rw.wish_id,
    rw.sender_name,
    rw.sender_relation,
    rw.message_text,
    rw.created_at,
    COALESCE(
        json_agg(
            json_build_object(
                'media_id',         m.media_id,
                'type',             m.media_type,
                'url',              m.file_url,
                'mime_type',        m.mime_type,
                'duration_seconds', m.duration_seconds
            ) ORDER BY m.media_id
        ) FILTER (WHERE m.media_id IS NOT NULL),
        '[]'::json
    ) AS media
FROM v_revealed_wishes rw
LEFT JOIN media m ON m.wish_id = rw.wish_id
GROUP BY rw.wall_id, rw.reveal_token, rw.wish_id, rw.sender_name,
         rw.sender_relation, rw.message_text, rw.created_at;


-- ---------------------------------------------------------------------
-- Walls still accepting wishes. Notice: no reveal_token column, so the
-- contribute page can never accidentally leak the reveal link.
-- ---------------------------------------------------------------------
CREATE VIEW v_open_walls AS
SELECT
    wall_id,
    contribute_token,
    birthday_person_name,
    birthday_date,
    reveal_at,
    reveal_at - now() AS time_remaining
FROM walls
WHERE is_locked = FALSE
  AND now() < reveal_at;
