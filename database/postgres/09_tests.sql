-- =====================================================================
-- 09_tests.sql
-- Proves every constraint and trigger actually works. Each test tries
-- to insert BAD data and expects the database to reject it.
-- Output is a list of PASS / FAIL lines. Run after 07_seed_data.sql.
--
-- Good for the viva: run this live and show that the database itself
-- refuses invalid data, without relying on the backend.
-- =====================================================================

-- Helper: run a statement, PASS if it raises an error, FAIL if it succeeds.
-- Each statement runs inside its own subtransaction (the BEGIN/EXCEPTION
-- block), so a failed test does not affect the others.
CREATE OR REPLACE FUNCTION pg_temp.expect_error(p_label TEXT, p_sql TEXT)
RETURNS TEXT
LANGUAGE plpgsql
AS $$
BEGIN
    BEGIN
        EXECUTE p_sql;
        -- force deferred constraint triggers (T4) to fire now
        SET CONSTRAINTS ALL IMMEDIATE;
        RAISE EXCEPTION 'no_error_raised';
    EXCEPTION
        WHEN raise_exception THEN
            IF SQLERRM = 'no_error_raised' THEN
                RETURN 'FAIL  ' || p_label || '  (bad data was accepted)';
            END IF;
            RETURN 'PASS  ' || p_label || '  -> ' || SQLERRM;
        WHEN OTHERS THEN
            RETURN 'PASS  ' || p_label || '  -> ' || SQLERRM;
    END;
END;
$$;

BEGIN;

SELECT result FROM (VALUES
-- ---------- users ----------
(pg_temp.expect_error('duplicate email',
  $q$INSERT INTO users (full_name, email, password_hash) VALUES ('X', 'ananya@example.com', 'h')$q$)),
(pg_temp.expect_error('invalid email format',
  $q$INSERT INTO users (full_name, email, password_hash) VALUES ('X', 'not-an-email', 'h')$q$)),
(pg_temp.expect_error('blank name',
  $q$INSERT INTO users (full_name, email, password_hash) VALUES ('   ', 'x@y.com', 'h')$q$)),

-- ---------- walls ----------
(pg_temp.expect_error('wall for non-existent user (FK)',
  $q$INSERT INTO walls (creator_id, birthday_person_name, birthday_date, reveal_at)
     VALUES (999, 'Ghost', current_date + 5, now() + interval '5 days')$q$)),
(pg_temp.expect_error('reveal time in the past',
  $q$INSERT INTO walls (creator_id, birthday_person_name, birthday_date, reveal_at)
     VALUES (1, 'Late', current_date, now() - interval '1 day')$q$)),
(pg_temp.expect_error('short guessable token',
  $q$INSERT INTO walls (creator_id, birthday_person_name, birthday_date, reveal_at, contribute_token)
     VALUES (1, 'Short', current_date + 5, now() + interval '5 days', 'abc')$q$)),
(pg_temp.expect_error('same token for both links',
  $q$INSERT INTO walls (creator_id, birthday_person_name, birthday_date, reveal_at, contribute_token, reveal_token)
     VALUES (1, 'Same', current_date + 5, now() + interval '5 days', 'sametoken1234567890', 'sametoken1234567890')$q$)),
(pg_temp.expect_error('duplicate contribute token',
  $q$INSERT INTO walls (creator_id, birthday_person_name, birthday_date, reveal_at, contribute_token)
     VALUES (1, 'Dup', current_date + 5, now() + interval '5 days', 'priya-contribute-2026')$q$)),
(pg_temp.expect_error('T5: changing a token',
  $q$UPDATE walls SET contribute_token = 'brand-new-token-123456' WHERE wall_id = 2$q$)),
(pg_temp.expect_error('T5: changing creator',
  $q$UPDATE walls SET creator_id = 2 WHERE wall_id = 1$q$)),

-- ---------- wishes ----------
(pg_temp.expect_error('T1: wish on revealed wall (Priya)',
  $q$INSERT INTO wishes (wall_id, sender_name, message_text) VALUES (1, 'Late Guy', 'Sorry I am late')$q$)),
(pg_temp.expect_error('T1: wish on locked wall (Rahul)',
  $q$INSERT INTO wishes (wall_id, sender_name, message_text) VALUES (4, 'Late Guy', 'Sorry')$q$)),
(pg_temp.expect_error('invalid relation',
  $q$INSERT INTO wishes (wall_id, sender_name, sender_relation, message_text) VALUES (2, 'A', 'enemy', 'hi')$q$)),
(pg_temp.expect_error('blank message text',
  $q$INSERT INTO wishes (wall_id, sender_name, message_text) VALUES (2, 'A', '    ')$q$)),
(pg_temp.expect_error('message over 2000 chars',
  $q$INSERT INTO wishes (wall_id, sender_name, message_text) VALUES (2, 'A', repeat('x', 2001))$q$)),
(pg_temp.expect_error('T4: empty wish (no text, no media)',
  $q$INSERT INTO wishes (wall_id, sender_name, message_text) VALUES (2, 'Empty', NULL)$q$)),

-- ---------- media ----------
(pg_temp.expect_error('invalid media type',
  $q$INSERT INTO media (wish_id, media_type, file_url, mime_type, file_size_bytes)
     VALUES (9, 'pdf', 'https://x.com/a.pdf', 'pdf/x', 1000)$q$)),
(pg_temp.expect_error('mime does not match type',
  $q$INSERT INTO media (wish_id, media_type, file_url, mime_type, file_size_bytes)
     VALUES (9, 'image', 'https://x.com/a.mp4', 'video/mp4', 1000)$q$)),
(pg_temp.expect_error('image over 10 MB',
  $q$INSERT INTO media (wish_id, media_type, file_url, mime_type, file_size_bytes)
     VALUES (9, 'image', 'https://x.com/a.jpg', 'image/jpeg', 11 * 1024 * 1024)$q$)),
(pg_temp.expect_error('duration on an image',
  $q$INSERT INTO media (wish_id, media_type, file_url, mime_type, file_size_bytes, duration_seconds)
     VALUES (9, 'image', 'https://x.com/a.jpg', 'image/jpeg', 1000, 30)$q$)),
(pg_temp.expect_error('voice note over 3 minutes',
  $q$INSERT INTO media (wish_id, media_type, file_url, mime_type, file_size_bytes, duration_seconds)
     VALUES (9, 'audio', 'https://x.com/a.webm', 'audio/webm', 1000, 500)$q$)),
(pg_temp.expect_error('non-https URL',
  $q$INSERT INTO media (wish_id, media_type, file_url, mime_type, file_size_bytes)
     VALUES (9, 'image', 'http://x.com/a.jpg', 'image/jpeg', 1000)$q$)),
(pg_temp.expect_error('T2: media on revealed wall',
  $q$INSERT INTO media (wish_id, media_type, file_url, mime_type, file_size_bytes)
     VALUES (1, 'image', 'https://x.com/a.jpg', 'image/jpeg', 1000)$q$)),
(pg_temp.expect_error('T3: sixth file on one wish',
  $q$INSERT INTO media (wish_id, media_type, file_url, mime_type, file_size_bytes)
     SELECT 12, 'image', 'https://x.com/' || g || '.jpg', 'image/jpeg', 1000
     FROM generate_series(1, 6) g$q$)),

-- ---------- functions ----------
(pg_temp.expect_error('reveal link opened too early',
  $q$SELECT * FROM fn_get_reveal_wall('arjun-reveal-secret-2026')$q$)),
(pg_temp.expect_error('reveal link with wrong token',
  $q$SELECT * FROM fn_get_reveal_wall('totally-wrong-token-xyz')$q$)),
(pg_temp.expect_error('procedure rolls back wish if a file is invalid',
  $q$CALL sp_submit_wish('arjun-contribute-2026', 'Rollback Test', 'friend', 'hi',
       '[{"type":"image","url":"https://x.com/ok.jpg","mime":"image/jpeg","size":1000},
         {"type":"image","url":"https://x.com/huge.jpg","mime":"image/jpeg","size":99999999}]'::jsonb)$q$))
) AS t(result);

-- Prove the rollback test above left nothing behind
SELECT CASE WHEN COUNT(*) = 0
            THEN 'PASS  rollback left no orphan wish'
            ELSE 'FAIL  rollback left an orphan wish' END AS result
FROM wishes WHERE sender_name = 'Rollback Test';

-- Prove ON DELETE CASCADE: deleting a user removes their walls, wishes, media
SAVEPOINT before_cascade;
DELETE FROM users WHERE user_id = 3;   -- Divya owns wall 4 (Rahul)
SELECT CASE WHEN NOT EXISTS (SELECT 1 FROM walls  WHERE wall_id = 4)
             AND NOT EXISTS (SELECT 1 FROM wishes WHERE wall_id = 4)
             AND NOT EXISTS (SELECT 1 FROM media  WHERE wish_id IN (14, 15, 16))
            THEN 'PASS  cascade delete removed wall, wishes and media'
            ELSE 'FAIL  cascade delete left rows behind' END AS result;
ROLLBACK TO SAVEPOINT before_cascade;

ROLLBACK;  -- tests never change the demo data
