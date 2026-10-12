# Database layer

PostgreSQL (13 or newer) for structured data, MongoDB for flexible and
high-volume data. See `mongo/collections.md` for why each piece lives where it does.

## ER summary (PostgreSQL)

```
users 1 ──< walls 1 ──< wishes 1 ──< media
```

| Table   | Key columns | Relationship |
|---------|-------------|--------------|
| users   | user_id (PK), email (UNIQUE) | one user creates many walls |
| walls   | wall_id (PK), creator_id (FK), contribute_token (UNIQUE), reveal_token (UNIQUE) | one wall has many wishes |
| wishes  | wish_id (PK), wall_id (FK) | one wish has 0 to 5 files |
| media   | media_id (PK), wish_id (FK) | each file belongs to one wish |

All foreign keys are `ON DELETE CASCADE`. Every table is in 3NF: no repeating
groups (files are rows in `media`, not columns on `wishes`), and every non-key
column depends only on its own table's primary key.

## Files and run order

| File | What it contains |
|------|------------------|
| `postgres/01_schema.sql` | 4 tables (drops and recreates them) |
| `postgres/02_constraints.sql` | 20 named FK / UNIQUE / CHECK constraints |
| `postgres/03_indexes.sql` | FK indexes, a composite index, 2 partial indexes |
| `postgres/04_triggers.sql` | 5 triggers incl. a deferred constraint trigger |
| `postgres/05_views.sql` | 4 views (dashboard, reveal page, JSON media, open walls) |
| `postgres/06_functions.sql` | transactional procedure + 3 functions |
| `postgres/07_seed_data.sql` | 3 users, 4 walls in different states, 16 wishes, 11 files |
| `postgres/08_queries.sql` | 12 report queries + how the backend calls everything |
| `postgres/09_tests.sql` | 29 tests proving every rule rejects bad data |
| `mongo/collections.md` | MongoDB design and sample queries |
| `mongo/seed_mongo.py` | creates collections with validators, indexes, demo data |

### PostgreSQL (local)

```bash
createdb birthday_wall
cd database/postgres
for f in 01 02 03 04 05 06 07; do psql -d birthday_wall -v ON_ERROR_STOP=1 -f ${f}_*.sql; done
psql -d birthday_wall -f 09_tests.sql      # every line should say PASS
```

On Windows without bash, run each file in order in pgAdmin's Query Tool or with
`psql -d birthday_wall -f 01_schema.sql` and so on.

### PostgreSQL (Supabase / Neon)

Paste each file, in order, into the SQL editor and run it. Then copy the
connection string into your `.env` as `DATABASE_URL`.

### MongoDB

```bash
pip install pymongo python-dotenv
# .env: MONGO_URI=mongodb+srv://...   (from MongoDB Atlas, or mongodb://localhost:27017)
python database/mongo/seed_mongo.py
```

## How the backend uses this

| API endpoint | Database call |
|--------------|---------------|
| `POST /api/walls` | `INSERT INTO walls (...) RETURNING ...` + `wall_settings` document in Mongo |
| `GET /api/walls` | `SELECT * FROM v_wall_summary WHERE creator_id = %s` |
| `GET /api/contribute/<token>` | `SELECT ... FROM walls WHERE contribute_token = %s` |
| `POST /api/contribute/<token>/wishes` | `CALL sp_submit_wish(...)` + `activity_logs` in Mongo |
| `GET /api/reveal/<token>` | `fn_get_reveal_wall(%s)` + `fn_wall_stats(%s)`; error 42501 means "too early" |
| `POST /api/reveal/<token>/wishes/<id>/reactions` | check `v_revealed_wishes`, then Mongo `reactions` |
| `DELETE /api/walls/<id>` | `DELETE FROM walls` (cascades) + Mongo cleanup |

Full details in `docs/api.md`. Every query passes values as parameters
(`%s`), never by building SQL strings, which is what prevents SQL injection.

## Things to know

* **Time zones.** `reveal_at` is `TIMESTAMPTZ`. If the birthday person is in India,
  midnight is `'2026-10-19 00:00'::timestamp AT TIME ZONE 'Asia/Kolkata'`, which is
  18:30 UTC the day before. Get this wrong and the wall opens 5.5 hours late.
* **The seed file must run on a fresh schema.** It refers to wish IDs 1 to 16, so run
  `01_schema.sql` first to reset the identity counters.
* **`08_queries.sql` changes data** in its last section. Re-run 01 to 07 to reset.
* **Mongo validators were not tested against a live MongoDB server** while writing
  this, only the data and indexes were. Run `seed_mongo.py` once against your real
  database to confirm.
