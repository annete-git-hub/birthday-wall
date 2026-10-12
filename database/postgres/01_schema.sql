-- =====================================================================
-- 01_schema.sql
-- Birthday Wall: core relational schema (PostgreSQL 13+)
--
-- Tables (in dependency order):
--   users   -> people who create walls (organizers)
--   walls   -> one birthday wall per birthday person
--   wishes  -> one row per message sent by a friend/family member
--   media   -> files (image/audio/video) attached to a wish
--
-- Design notes:
--   * Files are NOT stored in the database. Only their URL and metadata.
--     Storing BLOBs would bloat the DB and slow every query on media.
--   * media is a separate table from wishes because one wish can carry
--     many files (1:N). Putting image_url, audio_url, video_url columns on
--     wishes would cause NULL-heavy rows and break 1NF if a wish had two
--     photos.
--   * Primary keys use GENERATED ALWAYS AS IDENTITY (SQL standard,
--     replaces the older SERIAL type).
--   * Named constraints (FKs, CHECKs, UNIQUEs) are added in
--     02_constraints.sql so each rule can be explained on its own.
-- =====================================================================

DROP TABLE IF EXISTS media  CASCADE;
DROP TABLE IF EXISTS wishes CASCADE;
DROP TABLE IF EXISTS walls  CASCADE;
DROP TABLE IF EXISTS users  CASCADE;

-- ---------------------------------------------------------------------
-- USERS: the organizer who creates a wall
-- ---------------------------------------------------------------------
CREATE TABLE users (
    user_id        INTEGER      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    full_name      VARCHAR(100) NOT NULL,
    email          VARCHAR(255) NOT NULL,
    password_hash  VARCHAR(255) NOT NULL,   -- bcrypt hash, never plain text
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------
-- WALLS: one birthday wall
--   contribute_token -> secret part of the link sent to friends/family
--   reveal_token     -> secret part of the link sent to the birthday person
--   Both default to 32 random hex characters so links cannot be guessed.
-- ---------------------------------------------------------------------
CREATE TABLE walls (
    wall_id               INTEGER      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    creator_id            INTEGER      NOT NULL,
    birthday_person_name  VARCHAR(100) NOT NULL,
    birthday_date         DATE         NOT NULL,
    reveal_at             TIMESTAMPTZ  NOT NULL,   -- moment the wall opens
    contribute_token      VARCHAR(32)  NOT NULL
                          DEFAULT replace(gen_random_uuid()::text, '-', ''),
    reveal_token          VARCHAR(32)  NOT NULL
                          DEFAULT replace(gen_random_uuid()::text, '-', ''),
    is_locked             BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at            TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------
-- WISHES: one message from one person
--   sender_name is free text because contributors do not need accounts.
-- ---------------------------------------------------------------------
CREATE TABLE wishes (
    wish_id          INTEGER      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    wall_id          INTEGER      NOT NULL,
    sender_name      VARCHAR(100) NOT NULL,
    sender_relation  VARCHAR(20)  NOT NULL DEFAULT 'friend',
    message_text     TEXT,                       -- NULL allowed if wish is media-only
    is_hidden        BOOLEAN      NOT NULL DEFAULT FALSE,  -- organizer can hide spam
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------
-- MEDIA: metadata for an uploaded file (the file lives in Cloudinary /
-- Supabase Storage; we keep only the URL)
-- ---------------------------------------------------------------------
CREATE TABLE media (
    media_id          INTEGER      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    wish_id           INTEGER      NOT NULL,
    media_type        VARCHAR(10)  NOT NULL,     -- image | audio | video
    file_url          TEXT         NOT NULL,
    mime_type         VARCHAR(100) NOT NULL,     -- e.g. image/jpeg
    file_size_bytes   BIGINT       NOT NULL,
    duration_seconds  INTEGER,                   -- only for audio/video
    uploaded_at       TIMESTAMPTZ  NOT NULL DEFAULT now()
);
