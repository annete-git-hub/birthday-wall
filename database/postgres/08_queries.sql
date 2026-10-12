-- =====================================================================
-- 08_queries.sql
-- Queries for the report and the viva. Each one shows a different SQL
-- concept. Run them one at a time in psql or pgAdmin after seeding.
-- Note: the last section (CALL sp_submit_wish, fn_lock_expired_walls)
-- CHANGES data. Re-run 01 to 07 to get a clean demo database again.
-- =====================================================================


-- Q1. INNER JOIN: every wish with the name of the wall it belongs to
SELECT w.birthday_person_name, ws.sender_name, ws.sender_relation, ws.message_text
FROM wishes ws
JOIN walls  w ON w.wall_id = ws.wall_id
ORDER BY w.wall_id, ws.created_at;


-- Q2. LEFT JOIN + IS NULL: walls that have received no wishes yet
--     (organizer might want to remind people to contribute)
SELECT w.wall_id, w.birthday_person_name, w.birthday_date
FROM walls w
LEFT JOIN wishes ws ON ws.wall_id = w.wall_id
WHERE ws.wish_id IS NULL;


-- Q3. GROUP BY + HAVING: walls with more than 3 visible wishes
SELECT w.birthday_person_name, COUNT(*) AS wish_count
FROM walls w
JOIN wishes ws ON ws.wall_id = w.wall_id
WHERE ws.is_hidden = FALSE
GROUP BY w.wall_id, w.birthday_person_name
HAVING COUNT(*) > 3
ORDER BY wish_count DESC;


-- Q4. Aggregation over a 3-table JOIN: storage used per wall, in MB
SELECT w.birthday_person_name,
       COUNT(m.media_id)                                        AS files,
       ROUND(COALESCE(SUM(m.file_size_bytes), 0) / 1048576.0, 2) AS storage_mb
FROM walls w
LEFT JOIN wishes ws ON ws.wall_id = w.wall_id
LEFT JOIN media  m  ON m.wish_id  = ws.wish_id
GROUP BY w.wall_id, w.birthday_person_name
ORDER BY storage_mb DESC;


-- Q5. Media breakdown by type across the whole system
SELECT media_type,
       COUNT(*)                                   AS total_files,
       ROUND(AVG(file_size_bytes) / 1024.0, 1)    AS avg_size_kb,
       ROUND(AVG(duration_seconds), 1)            AS avg_duration_sec
FROM media
GROUP BY media_type
ORDER BY total_files DESC;


-- Q6. Correlated subquery: wishes whose message is longer than the
--     average message length ON THE SAME WALL
SELECT ws.wall_id, ws.sender_name, length(ws.message_text) AS msg_length
FROM wishes ws
WHERE ws.message_text IS NOT NULL
  AND length(ws.message_text) > (
        SELECT AVG(length(x.message_text))
        FROM wishes x
        WHERE x.wall_id = ws.wall_id
          AND x.message_text IS NOT NULL
  )
ORDER BY ws.wall_id;


-- Q7. Window function: rank contributors on each wall by how much they
--     sent (wishes + files). RANK() restarts for every wall (PARTITION BY).
SELECT wall_id, sender_name, wishes_sent, files_sent,
       RANK() OVER (PARTITION BY wall_id
                    ORDER BY wishes_sent + files_sent DESC) AS contributor_rank
FROM (
    SELECT ws.wall_id,
           ws.sender_name,
           COUNT(DISTINCT ws.wish_id) AS wishes_sent,
           COUNT(m.media_id)          AS files_sent
    FROM wishes ws
    LEFT JOIN media m ON m.wish_id = ws.wish_id
    GROUP BY ws.wall_id, ws.sender_name
) t
ORDER BY wall_id, contributor_rank;


-- Q8. CTE (WITH clause): which relation type sends the most media?
WITH wish_files AS (
    SELECT ws.sender_relation, COUNT(m.media_id) AS file_count
    FROM wishes ws
    LEFT JOIN media m ON m.wish_id = ws.wish_id
    GROUP BY ws.wish_id, ws.sender_relation
)
SELECT sender_relation,
       COUNT(*)                     AS wishes,
       SUM(file_count)              AS files,
       ROUND(AVG(file_count), 2)    AS avg_files_per_wish
FROM wish_files
GROUP BY sender_relation
ORDER BY files DESC;


-- Q9. Date functions: wishes received per day for one wall
--     (could power a small "activity" chart for the organizer)
SELECT date_trunc('day', created_at)::date AS day, COUNT(*) AS wishes
FROM wishes
WHERE wall_id = 1
GROUP BY day
ORDER BY day;


-- Q10. CASE expression: classify each wish by what it contains
SELECT ws.wish_id, ws.sender_name,
       CASE
           WHEN ws.message_text IS NOT NULL AND COUNT(m.media_id) > 0 THEN 'text + media'
           WHEN ws.message_text IS NOT NULL                          THEN 'text only'
           ELSE 'media only'
       END AS wish_kind
FROM wishes ws
LEFT JOIN media m ON m.wish_id = ws.wish_id
GROUP BY ws.wish_id, ws.sender_name, ws.message_text
ORDER BY ws.wish_id;


-- Q11. EXISTS: organizers who have at least one wall with a video
SELECT u.full_name, u.email
FROM users u
WHERE EXISTS (
    SELECT 1
    FROM walls  w
    JOIN wishes ws ON ws.wall_id = w.wall_id
    JOIN media  m  ON m.wish_id  = ws.wish_id
    WHERE w.creator_id = u.user_id
      AND m.media_type = 'video'
);


-- Q12. Upcoming birthdays in the next 30 days that still accept wishes
SELECT birthday_person_name, birthday_date,
       birthday_date - current_date AS days_left
FROM walls
WHERE is_locked = FALSE
  AND birthday_date BETWEEN current_date AND current_date + 30
ORDER BY birthday_date;


-- ---------------------------------------------------------------------
-- Using the views and functions (what the backend will actually call)
-- ---------------------------------------------------------------------

-- Organizer dashboard
SELECT * FROM v_wall_summary ORDER BY wall_id;

-- Walls still collecting
SELECT * FROM v_open_walls;

-- Birthday person opens their link (works: Priya's birthday has passed)
SELECT * FROM fn_get_reveal_wall('priya-reveal-secret-2026');

-- Too early (raises NOT_YET_REVEALED with the reveal time)
-- SELECT * FROM fn_get_reveal_wall('arjun-reveal-secret-2026');

-- Stats for Priya's wall
SELECT * FROM fn_wall_stats(1);

-- A friend submits a wish with a photo and a voice note (one transaction)
CALL sp_submit_wish(
    'arjun-contribute-2026',
    'Deepa',
    'classmate',
    'Happy birthday Arjun! Here is our trip photo and a song.',
    '[{"type":"image","url":"https://res.cloudinary.com/demo/image/upload/bw/trip.jpg","mime":"image/jpeg","size":1500000},
      {"type":"audio","url":"https://res.cloudinary.com/demo/video/upload/bw/song.webm","mime":"audio/webm","size":300000,"duration":20}]'::jsonb
);

-- Lock every wall whose reveal time has passed
SELECT fn_lock_expired_walls();

-- Index demonstration
-- SET enable_seqscan = off;
-- EXPLAIN ANALYZE SELECT * FROM wishes WHERE wall_id = 1 ORDER BY created_at;
-- SET enable_seqscan = on;
