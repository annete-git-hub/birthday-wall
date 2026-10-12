-- =====================================================================
-- 06_functions.sql
-- Stored functions and procedures. The backend calls these instead of
-- writing multi-step SQL itself, so the logic lives in one place.
--
--   sp_submit_wish(...)              PROCEDURE: insert a wish + its files
--                                    as ONE transaction (all or nothing)
--   fn_get_reveal_wall(token)        returns the wall, or errors if too early
--   fn_wall_stats(wall_id)           statistics for one wall
--   fn_lock_expired_walls()          locks every wall whose reveal time passed
-- =====================================================================

-- ---------------------------------------------------------------------
-- sp_submit_wish
-- Called by the API when a friend presses "Send".
--
-- p_media is a JSON array, e.g.
--   '[{"type":"image","url":"https://...","mime":"image/jpeg","size":204800},
--     {"type":"audio","url":"https://...","mime":"audio/webm","size":51200,"duration":12}]'
--
-- Transaction behaviour: if ANY insert fails (bad file type, file too
-- big, wall closed, more than 5 files) the procedure raises an error and
-- PostgreSQL rolls back EVERYTHING done in this call, including the wish
-- row. There is never a half-saved wish with missing files.
-- ---------------------------------------------------------------------
CREATE OR REPLACE PROCEDURE sp_submit_wish(
    IN    p_contribute_token VARCHAR,
    IN    p_sender_name      VARCHAR,
    IN    p_sender_relation  VARCHAR,
    IN    p_message_text     TEXT,
    IN    p_media            JSONB,
    INOUT p_wish_id          INTEGER DEFAULT NULL
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_wall_id INTEGER;
    v_item    JSONB;
BEGIN
    -- 1. Resolve the link token to a wall
    SELECT wall_id INTO v_wall_id
      FROM walls
     WHERE contribute_token = p_contribute_token;

    IF v_wall_id IS NULL THEN
        RAISE EXCEPTION 'Invalid contribute link'
            USING ERRCODE = 'no_data_found';
    END IF;

    -- 2. Insert the wish (trigger T1 checks the wall is open)
    INSERT INTO wishes (wall_id, sender_name, sender_relation, message_text)
    VALUES (v_wall_id,
            trim(p_sender_name),
            COALESCE(p_sender_relation, 'friend'),
            NULLIF(trim(p_message_text), ''))
    RETURNING wish_id INTO p_wish_id;

    -- 3. Insert each file (triggers T2 and T3 plus CHECK constraints apply)
    IF p_media IS NOT NULL THEN
        FOR v_item IN SELECT * FROM jsonb_array_elements(p_media)
        LOOP
            INSERT INTO media (wish_id, media_type, file_url, mime_type,
                               file_size_bytes, duration_seconds)
            VALUES (p_wish_id,
                    v_item ->> 'type',
                    v_item ->> 'url',
                    v_item ->> 'mime',
                    (v_item ->> 'size')::BIGINT,
                    (v_item ->> 'duration')::INTEGER);
        END LOOP;
    END IF;

    -- 4. Trigger T4 (deferred) checks at COMMIT that the wish has content.
END;
$$;


-- ---------------------------------------------------------------------
-- fn_get_reveal_wall
-- Called when the birthday person opens their link.
-- * Wrong token        -> error 'Invalid reveal link'
-- * Too early          -> error containing the reveal time, so the app
--                         can catch it and show a countdown
-- * Otherwise          -> every visible wish with its media as JSON
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_get_reveal_wall(p_reveal_token VARCHAR)
RETURNS TABLE (
    wish_id          INTEGER,
    sender_name      VARCHAR,
    sender_relation  VARCHAR,
    message_text     TEXT,
    created_at       TIMESTAMPTZ,
    media            JSON
)
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
    v_reveal_at TIMESTAMPTZ;
BEGIN
    SELECT w.reveal_at INTO v_reveal_at
      FROM walls w
     WHERE w.reveal_token = p_reveal_token;

    IF v_reveal_at IS NULL THEN
        RAISE EXCEPTION 'Invalid reveal link'
            USING ERRCODE = 'no_data_found';
    END IF;

    IF now() < v_reveal_at THEN
        RAISE EXCEPTION 'NOT_YET_REVEALED:%', to_char(v_reveal_at AT TIME ZONE 'UTC',
                                                      'YYYY-MM-DD"T"HH24:MI:SS"Z"')
            USING ERRCODE = 'insufficient_privilege';
    END IF;

    RETURN QUERY
    SELECT v.wish_id, v.sender_name, v.sender_relation,
           v.message_text, v.created_at, v.media
      FROM v_wish_media v
     WHERE v.reveal_token = p_reveal_token
     ORDER BY v.created_at;
END;
$$;


-- ---------------------------------------------------------------------
-- fn_wall_stats
-- Statistics for the wall header ("23 wishes from 19 people, 4 voice
-- notes...") and for the report.
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_wall_stats(p_wall_id INTEGER)
RETURNS TABLE (
    total_wishes        BIGINT,
    unique_senders      BIGINT,
    photos              BIGINT,
    voice_notes         BIGINT,
    videos              BIGINT,
    total_storage_mb    NUMERIC,
    first_wish_at       TIMESTAMPTZ,
    last_wish_at        TIMESTAMPTZ,
    most_common_relation VARCHAR
)
LANGUAGE sql
STABLE
AS $$
    SELECT
        COUNT(DISTINCT ws.wish_id),
        COUNT(DISTINCT lower(ws.sender_name)),
        COUNT(m.media_id) FILTER (WHERE m.media_type = 'image'),
        COUNT(m.media_id) FILTER (WHERE m.media_type = 'audio'),
        COUNT(m.media_id) FILTER (WHERE m.media_type = 'video'),
        ROUND(COALESCE(SUM(m.file_size_bytes), 0) / (1024.0 * 1024.0), 2),
        MIN(ws.created_at),
        MAX(ws.created_at),
        (SELECT sender_relation
           FROM wishes
          WHERE wall_id = p_wall_id AND is_hidden = FALSE
          GROUP BY sender_relation
          ORDER BY COUNT(*) DESC, sender_relation
          LIMIT 1)
    FROM wishes ws
    LEFT JOIN media m ON m.wish_id = ws.wish_id
    WHERE ws.wall_id = p_wall_id
      AND ws.is_hidden = FALSE;
$$;


-- ---------------------------------------------------------------------
-- fn_lock_expired_walls
-- Marks every wall past its reveal time as locked. Run it on a schedule
-- (or call it when the backend starts). Returns how many walls changed.
-- Uses the partial index idx_walls_open_reveal_at.
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_lock_expired_walls()
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_count INTEGER;
BEGIN
    UPDATE walls
       SET is_locked = TRUE
     WHERE is_locked = FALSE
       AND reveal_at <= now();

    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN v_count;
END;
$$;
