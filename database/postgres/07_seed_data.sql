-- =====================================================================
-- 07_seed_data.sql
-- Demo data. Run AFTER 01 to 06 on a fresh database (01 recreates the
-- tables, so IDs always start at 1 and the wish_id numbers below match).
--
-- Four walls covering every state the app has to handle:
--   Wall 1  Priya  -> REVEALED  (birthday was yesterday, has wishes + media)
--   Wall 2  Arjun  -> COLLECTING (birthday in 7 days, has some wishes)
--   Wall 3  Meera  -> COLLECTING (birthday in 20 days, no wishes yet)
--   Wall 4  Rahul  -> LOCKED    (birthday last month)
--
-- Tokens are fixed and readable here so you can test URLs in the demo,
-- e.g. /wall/priya-contribute-2026 . Real walls get random tokens.
--
-- Why this order? Trigger T1 blocks wishes on walls that have already
-- opened. So every wall starts with reveal_at in the FUTURE, we insert
-- the wishes, and only then move walls 1 and 4 into the past.
-- =====================================================================

BEGIN;

-- ---------------- USERS (organizers) ----------------
-- password_hash values are Werkzeug (scrypt) hashes of "password123",
-- the same format the Flask backend creates, so you can log in as any of them.
INSERT INTO users (full_name, email, password_hash, created_at) VALUES
('Ananya Iyer',   'ananya@example.com', 'scrypt:32768:8:1$zp8915OaCB2DsvOs$70bba02d4efd41c102e3b6a7ababab90563b205060fe87eafff14bdb8048975d0f5ff4f35fbd696ef500f1d6d0f5724014cf007fb906730abf4171618ff39ade', now() - interval '60 days'),
('Karthik Raman', 'karthik@example.com','scrypt:32768:8:1$zp8915OaCB2DsvOs$70bba02d4efd41c102e3b6a7ababab90563b205060fe87eafff14bdb8048975d0f5ff4f35fbd696ef500f1d6d0f5724014cf007fb906730abf4171618ff39ade', now() - interval '45 days'),
('Divya Menon',   'divya@example.com',  'scrypt:32768:8:1$zp8915OaCB2DsvOs$70bba02d4efd41c102e3b6a7ababab90563b205060fe87eafff14bdb8048975d0f5ff4f35fbd696ef500f1d6d0f5724014cf007fb906730abf4171618ff39ade', now() - interval '40 days');

-- ---------------- WALLS ----------------
INSERT INTO walls (creator_id, birthday_person_name, birthday_date, reveal_at,
                   contribute_token, reveal_token, created_at) VALUES
(1, 'Priya Sharma', current_date - 1,  now() + interval '1 day',
    'priya-contribute-2026', 'priya-reveal-secret-2026', now() - interval '30 days'),
(2, 'Arjun Nair',   current_date + 7,  (current_date + 7)::timestamp AT TIME ZONE 'Asia/Kolkata',
    'arjun-contribute-2026', 'arjun-reveal-secret-2026', now() - interval '10 days'),
(1, 'Meera Krishnan', current_date + 20, (current_date + 20)::timestamp AT TIME ZONE 'Asia/Kolkata',
    'meera-contribute-2026', 'meera-reveal-secret-2026', now() - interval '2 days'),
(3, 'Rahul Verma',  current_date - 30, now() + interval '1 day',
    'rahul-contribute-2026', 'rahul-reveal-secret-2026', now() - interval '50 days');

-- ---------------- WISHES ----------------
-- wish_id 1..8 -> Priya (wall 1)
INSERT INTO wishes (wall_id, sender_name, sender_relation, message_text, created_at) VALUES
(1, 'Rohan',        'friend',    'Happy birthday Priya! Thanks for always dragging me to the 8am lab. Have the best year!', now() - interval '20 days'),
(1, 'Amma',         'family',    'Happy birthday kanna. So proud of you. Come home soon, I will make payasam.',            now() - interval '18 days'),
(1, 'Sneha',        'classmate', 'Happy birthday to my DBMS project partner. May your queries always return rows.',        now() - interval '15 days'),
(1, 'Vikram',       'friend',    NULL,                                                                                    now() - interval '12 days'),  -- voice note only
(1, 'Lakshmi Aunty','family',    'Many happy returns of the day! God bless.',                                             now() - interval '9 days'),
(1, 'Farhan',       'colleague', 'Happy birthday! The internship team misses you.',                                       now() - interval '6 days'),
(1, 'Sneha',        'classmate', 'Also here is the photo from the fest!',                                                 now() - interval '5 days'),
(1, 'Appa',         'family',    NULL,                                                                                    now() - interval '2 days');   -- video only

-- wish_id 9..13 -> Arjun (wall 2)
INSERT INTO wishes (wall_id, sender_name, sender_relation, message_text, created_at) VALUES
(2, 'Karthik',  'friend',    'Advance happy birthday da! Treat is pending.',              now() - interval '8 days'),
(2, 'Nisha',    'classmate', 'Happy birthday Arjun! Good luck with placements.',          now() - interval '6 days'),
(2, 'Akka',     'family',    NULL,                                                         now() - interval '4 days'),  -- photo only
(2, 'Harish',   'friend',    'Happy birthday! Cricket on Sunday to celebrate.',            now() - interval '3 days'),
(2, 'Spam Bot', 'other',     'Click here for free crypto!!!',                              now() - interval '1 day');

-- wish_id 14..16 -> Rahul (wall 4)
INSERT INTO wishes (wall_id, sender_name, sender_relation, message_text, created_at) VALUES
(4, 'Divya',  'friend', 'Happy birthday Rahul! Hope this year is amazing.', now() - interval '40 days'),
(4, 'Mom',    'family', 'Happy birthday beta!',                            now() - interval '35 days'),
(4, 'Sameer', 'friend', NULL,                                              now() - interval '33 days');  -- photo only

-- ---------------- MEDIA ----------------
INSERT INTO media (wish_id, media_type, file_url, mime_type, file_size_bytes, duration_seconds, uploaded_at) VALUES
(1,  'image', 'https://res.cloudinary.com/demo/image/upload/bw/priya_rohan_trip.jpg',  'image/jpeg', 1843200, NULL, now() - interval '20 days'),
(3,  'image', 'https://res.cloudinary.com/demo/image/upload/bw/priya_lab.png',         'image/png',  2457600, NULL, now() - interval '15 days'),
(4,  'audio', 'https://res.cloudinary.com/demo/video/upload/bw/vikram_voice.webm',     'audio/webm',  512000,   24, now() - interval '12 days'),
(6,  'image', 'https://res.cloudinary.com/demo/image/upload/bw/team_photo.jpg',        'image/jpeg', 3145728, NULL, now() - interval '6 days'),
(7,  'image', 'https://res.cloudinary.com/demo/image/upload/bw/fest_1.jpg',            'image/jpeg', 2097152, NULL, now() - interval '5 days'),
(7,  'image', 'https://res.cloudinary.com/demo/image/upload/bw/fest_2.jpg',            'image/jpeg', 1966080, NULL, now() - interval '5 days'),
(8,  'video', 'https://res.cloudinary.com/demo/video/upload/bw/appa_wish.mp4',         'video/mp4', 18874368,   45, now() - interval '2 days'),
(8,  'audio', 'https://res.cloudinary.com/demo/video/upload/bw/appa_song.mp3',         'audio/mpeg', 1048576,   60, now() - interval '2 days'),
(10, 'audio', 'https://res.cloudinary.com/demo/video/upload/bw/nisha_voice.webm',      'audio/webm',  409600,   18, now() - interval '6 days'),
(11, 'image', 'https://res.cloudinary.com/demo/image/upload/bw/arjun_childhood.jpg',   'image/jpeg', 2621440, NULL, now() - interval '4 days'),
(16, 'image', 'https://res.cloudinary.com/demo/image/upload/bw/rahul_goa.jpg',         'image/jpeg', 2228224, NULL, now() - interval '33 days');

-- Organizer hides the spam wish on Arjun's wall
UPDATE wishes SET is_hidden = TRUE WHERE wish_id = 13;

-- Move walls 1 and 4 into the past now that their wishes exist
UPDATE walls SET reveal_at = now() - interval '1 day'  WHERE wall_id = 1;
UPDATE walls SET reveal_at = now() - interval '29 days' WHERE wall_id = 4;

-- Organizer manually locked Rahul's wall after the birthday.
-- Wall 1 stays unlocked but is still closed to new wishes, because
-- trigger T1 also checks reveal_at. (fn_lock_expired_walls() would lock
-- it too; see 08_queries.sql.)
UPDATE walls SET is_locked = TRUE WHERE wall_id = 4;

COMMIT;  -- deferred trigger T4 checks every wish has content here
