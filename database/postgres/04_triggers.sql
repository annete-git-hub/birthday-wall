-- =====================================================================
-- 04_triggers.sql
-- Business rules that a CHECK constraint cannot express, because they
-- depend on OTHER rows or OTHER tables, or on the current time.
--
--   T1 trg_wishes_wall_open       block wishes on a locked / revealed wall
--   T2 trg_media_wall_open        block uploads on a locked / revealed wall
--   T3 trg_media_limit            max 5 files per wish
--   T4 trg_wishes_require_content wish must have text OR at least one file
--                                 (DEFERRED: checked at COMMIT)
--   T5 trg_walls_protect_tokens   tokens and creator cannot be changed
-- =====================================================================

-- ---------------------------------------------------------------------
-- T1: A wall accepts wishes only while it is unlocked AND before reveal.
-- Why a trigger and not a CHECK? A CHECK can only see the row being
-- inserted (the wish). This rule needs data from the walls table.
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_check_wall_open()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_locked    BOOLEAN;
    v_reveal_at TIMESTAMPTZ;
BEGIN
    SELECT is_locked, reveal_at
      INTO v_locked, v_reveal_at
      FROM walls
     WHERE wall_id = NEW.wall_id;

    IF v_locked THEN
        RAISE EXCEPTION 'Wall % is locked and no longer accepts wishes', NEW.wall_id
            USING ERRCODE = 'check_violation';
    END IF;

    IF now() >= v_reveal_at THEN
        RAISE EXCEPTION 'Wall % has already been revealed (reveal_at = %)',
                        NEW.wall_id, v_reveal_at
            USING ERRCODE = 'check_violation';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_wishes_wall_open ON wishes;
CREATE TRIGGER trg_wishes_wall_open
    BEFORE INSERT ON wishes
    FOR EACH ROW
    EXECUTE FUNCTION fn_check_wall_open();


-- ---------------------------------------------------------------------
-- T2: Same rule for media. Otherwise someone could keep adding files to
-- an old wish after the birthday person has already opened the wall.
-- media has no wall_id, so we JOIN through wishes.
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_check_media_wall_open()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_wall_id   INTEGER;
    v_locked    BOOLEAN;
    v_reveal_at TIMESTAMPTZ;
BEGIN
    SELECT w.wall_id, w.is_locked, w.reveal_at
      INTO v_wall_id, v_locked, v_reveal_at
      FROM wishes ws
      JOIN walls  w ON w.wall_id = ws.wall_id
     WHERE ws.wish_id = NEW.wish_id;

    IF v_locked OR now() >= v_reveal_at THEN
        RAISE EXCEPTION 'Cannot attach media: wall % is closed', v_wall_id
            USING ERRCODE = 'check_violation';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_media_wall_open ON media;
CREATE TRIGGER trg_media_wall_open
    BEFORE INSERT ON media
    FOR EACH ROW
    EXECUTE FUNCTION fn_check_media_wall_open();


-- ---------------------------------------------------------------------
-- T3: At most 5 files per wish.
-- Concurrency note: two uploads arriving at the same time could both
-- count 4 and both succeed, giving 6. SELECT ... FOR UPDATE on the
-- parent wish row makes the second transaction wait until the first
-- commits, so the count is always accurate.
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_check_media_limit()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_count INTEGER;
BEGIN
    PERFORM 1 FROM wishes WHERE wish_id = NEW.wish_id FOR UPDATE;

    SELECT count(*) INTO v_count
      FROM media
     WHERE wish_id = NEW.wish_id;

    IF v_count >= 5 THEN
        RAISE EXCEPTION 'Wish % already has 5 files (maximum)', NEW.wish_id
            USING ERRCODE = 'check_violation';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_media_limit ON media;
CREATE TRIGGER trg_media_limit
    BEFORE INSERT ON media
    FOR EACH ROW
    EXECUTE FUNCTION fn_check_media_limit();


-- ---------------------------------------------------------------------
-- T4: Every wish needs content: message_text OR at least one media row.
--
-- Problem: the app inserts the wish FIRST (to get its wish_id) and the
-- media rows AFTER. A normal trigger would reject a media-only wish at
-- the moment it is inserted, before its files exist.
--
-- Solution: a CONSTRAINT TRIGGER that is DEFERRABLE INITIALLY DEFERRED.
-- It runs at COMMIT time, when the whole transaction (wish + files) is
-- done. If the wish is still empty, the entire transaction rolls back.
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_check_wish_has_content()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    -- Row may have been deleted later in the same transaction.
    IF NOT EXISTS (SELECT 1 FROM wishes WHERE wish_id = NEW.wish_id) THEN
        RETURN NULL;
    END IF;

    IF NEW.message_text IS NULL
       AND NOT EXISTS (SELECT 1 FROM media WHERE wish_id = NEW.wish_id) THEN
        RAISE EXCEPTION 'Wish % has no message and no media', NEW.wish_id
            USING ERRCODE = 'check_violation';
    END IF;

    RETURN NULL;   -- return value is ignored for AFTER triggers
END;
$$;

DROP TRIGGER IF EXISTS trg_wishes_require_content ON wishes;
CREATE CONSTRAINT TRIGGER trg_wishes_require_content
    AFTER INSERT ON wishes
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW
    EXECUTE FUNCTION fn_check_wish_has_content();


-- ---------------------------------------------------------------------
-- T5: Tokens and creator are permanent once a wall is created.
-- If a token changed, every link already sent to friends would break.
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_protect_wall_identity()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.contribute_token IS DISTINCT FROM OLD.contribute_token
       OR NEW.reveal_token  IS DISTINCT FROM OLD.reveal_token THEN
        RAISE EXCEPTION 'Wall tokens cannot be changed after creation';
    END IF;

    IF NEW.creator_id IS DISTINCT FROM OLD.creator_id THEN
        RAISE EXCEPTION 'Wall creator cannot be changed';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_walls_protect_tokens ON walls;
CREATE TRIGGER trg_walls_protect_tokens
    BEFORE UPDATE ON walls
    FOR EACH ROW
    EXECUTE FUNCTION fn_protect_wall_identity();
