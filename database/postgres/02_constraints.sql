-- =====================================================================
-- 02_constraints.sql
-- Integrity rules, each named so error messages are readable and each
-- rule can be dropped or explained individually.
--
-- Naming convention:
--   fk_<table>_<column>   foreign key
--   uq_<table>_<column>   unique
--   ck_<table>_<rule>     check
-- =====================================================================

-- ---------------------------------------------------------------------
-- USERS
-- ---------------------------------------------------------------------
ALTER TABLE users
    ADD CONSTRAINT uq_users_email UNIQUE (email),
    ADD CONSTRAINT ck_users_email_format
        CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'),
    ADD CONSTRAINT ck_users_name_not_blank
        CHECK (length(trim(full_name)) > 0);

-- ---------------------------------------------------------------------
-- WALLS
-- ---------------------------------------------------------------------
ALTER TABLE walls
    -- Deleting a user deletes their walls (and through cascades, all wishes
    -- and media rows). The organizer owns the wall.
    ADD CONSTRAINT fk_walls_creator
        FOREIGN KEY (creator_id) REFERENCES users (user_id) ON DELETE CASCADE,

    -- Tokens are the only thing protecting a wall, so they must be unique.
    -- UNIQUE also creates an index, which makes token lookups fast.
    ADD CONSTRAINT uq_walls_contribute_token UNIQUE (contribute_token),
    ADD CONSTRAINT uq_walls_reveal_token     UNIQUE (reveal_token),

    -- Short tokens are guessable. 16+ characters is the minimum we accept.
    ADD CONSTRAINT ck_walls_token_length
        CHECK (length(contribute_token) >= 16 AND length(reveal_token) >= 16),

    -- The two links must never be the same, or friends could see the wall.
    ADD CONSTRAINT ck_walls_tokens_differ
        CHECK (contribute_token <> reveal_token),

    -- A wall cannot open before it was created.
    ADD CONSTRAINT ck_walls_reveal_after_creation
        CHECK (reveal_at > created_at),

    ADD CONSTRAINT ck_walls_name_not_blank
        CHECK (length(trim(birthday_person_name)) > 0);

-- ---------------------------------------------------------------------
-- WISHES
-- ---------------------------------------------------------------------
ALTER TABLE wishes
    ADD CONSTRAINT fk_wishes_wall
        FOREIGN KEY (wall_id) REFERENCES walls (wall_id) ON DELETE CASCADE,

    ADD CONSTRAINT ck_wishes_sender_not_blank
        CHECK (length(trim(sender_name)) > 0),

    ADD CONSTRAINT ck_wishes_relation
        CHECK (sender_relation IN ('friend', 'family', 'colleague', 'classmate', 'other')),

    -- If text is given it must not be empty spaces, and must be a sane length.
    ADD CONSTRAINT ck_wishes_message_length
        CHECK (message_text IS NULL
               OR length(trim(message_text)) BETWEEN 1 AND 2000);

-- ---------------------------------------------------------------------
-- MEDIA
-- ---------------------------------------------------------------------
ALTER TABLE media
    ADD CONSTRAINT fk_media_wish
        FOREIGN KEY (wish_id) REFERENCES wishes (wish_id) ON DELETE CASCADE,

    ADD CONSTRAINT ck_media_type
        CHECK (media_type IN ('image', 'audio', 'video')),

    -- MIME type must match the declared type: an "image" must be image/*.
    ADD CONSTRAINT ck_media_mime_matches_type
        CHECK (mime_type LIKE media_type || '/%'),

    -- Size limits per type (bytes): image 10 MB, audio 20 MB, video 50 MB.
    ADD CONSTRAINT ck_media_file_size
        CHECK (
            file_size_bytes > 0 AND (
                (media_type = 'image' AND file_size_bytes <= 10 * 1024 * 1024) OR
                (media_type = 'audio' AND file_size_bytes <= 20 * 1024 * 1024) OR
                (media_type = 'video' AND file_size_bytes <= 50 * 1024 * 1024)
            )
        ),

    -- Duration only makes sense for audio/video, and is capped at 3 minutes.
    ADD CONSTRAINT ck_media_duration
        CHECK (
            (media_type = 'image' AND duration_seconds IS NULL) OR
            (media_type IN ('audio', 'video')
             AND (duration_seconds IS NULL OR duration_seconds BETWEEN 1 AND 180))
        ),

    ADD CONSTRAINT ck_media_url_https
        CHECK (file_url LIKE 'https://%');
