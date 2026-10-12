# Birthday Wall

Create a link for someone's birthday, share it with friends and family, and let
them leave messages, photos, voice notes and videos. On the birthday, the
birthday person opens their own secret link and sees everything on one wall.

DBMS course project: PostgreSQL for relational data, MongoDB for flexible data.

## Stack

| Layer | Tool |
|-------|------|
| Frontend | HTML, CSS, JavaScript (in `frontend/`, served by Flask) |
| Backend | Python, Flask |
| Relational DB | PostgreSQL |
| NoSQL DB | MongoDB |
| File storage | Cloudinary |

## Project layout

```
backend/
  app.py              Flask app factory, health check, page routes
  config.py           settings from .env
  db/postgres.py      connection pool, one transaction per `with get_cursor()`
  db/mongo.py         Mongo client, cross-database cleanup
  routes/auth.py      organizer register / login / logout
  routes/walls.py     organizer: create, list, moderate, lock, delete, settings
  routes/wishes.py    friends: view wall info, submit wish with files
  routes/reveal.py    birthday person: countdown or the full wall
  routes/reactions.py birthday person: emoji reactions (Mongo)
  utils/errors.py     turns database errors into friendly JSON messages
  utils/storage.py    file validation, Cloudinary upload, orphan cleanup
  utils/validators.py input checks, timezone-correct reveal time
  utils/auth.py       login_required, wall ownership check
  utils/logger.py     activity logs to Mongo (never breaks a request)
frontend/
  templates/          index (organizer), contribute, countdown, wall, message
  static/css/style.css  all styles, including the five wall themes
  static/js/          common, create (organizer), contribute, countdown, wall
database/             SQL files, Mongo design and seed (see database/README.md)
docs/
  api.md              every endpoint with example requests and responses
  report.md           project report draft (fill in team details)
  er_diagram.png      ER diagram (source: er_diagram.dot)
  screenshots/        every page, desktop and mobile
tests/                34 API tests against a real PostgreSQL database
```

## Run it locally

```bash
python -m venv venv
source venv/bin/activate            # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env                # then fill in the values

# Build the database (see database/README.md for Windows / Supabase)
createdb birthday_wall
cd database/postgres
for f in 01 02 03 04 05 06 07; do psql -d birthday_wall -v ON_ERROR_STOP=1 -f ${f}_*.sql; done
cd ../..
python database/mongo/seed_mongo.py   # optional, needs MONGO_URI

flask --app backend.app run --debug
```

Open http://127.0.0.1:5000/api/health. You should see `"postgres": "ok"`.
Then open http://127.0.0.1:5000 and log in as `ananya@example.com` / `password123`.

Demo links from the seed data:

| Page | URL |
|------|-----|
| Leave a wish on Arjun's wall | http://127.0.0.1:5000/wall/arjun-contribute-2026 |
| Arjun's countdown (birthday not yet) | http://127.0.0.1:5000/reveal/arjun-reveal-secret-2026 |
| Priya's finished wall | http://127.0.0.1:5000/reveal/priya-reveal-secret-2026 |

Priya's photos will show as broken images because the seed URLs point to example
Cloudinary paths. Real uploads display normally.

Or test the API directly:

```bash
curl http://127.0.0.1:5000/api/contribute/arjun-contribute-2026
curl http://127.0.0.1:5000/api/reveal/arjun-reveal-secret-2026     # 403, too early
curl http://127.0.0.1:5000/api/reveal/priya-reveal-secret-2026     # the full wall
```

MongoDB and Cloudinary are optional while developing. Without MongoDB, logs are
skipped and reactions/settings return 503. Without Cloudinary, text wishes work
but file uploads return 503.

## Run the tests

```bash
pip install -r requirements-dev.txt
createdb birthday_wall_test
# set TEST_DATABASE_URL in .env (a SEPARATE database: tests wipe it)
pytest -v
```

## Deploy (Render + Supabase/Neon + MongoDB Atlas + Cloudinary)

1. Create the PostgreSQL database on Supabase or Neon and run files 01 to 07 in its SQL editor.
2. Create a free MongoDB Atlas cluster, allow access from anywhere (0.0.0.0/0), run `seed_mongo.py`.
3. Create a Cloudinary account and copy its API environment variable.
4. On Render: New Web Service from your GitHub repo.
   * Build command: `pip install -r requirements.txt`
   * Start command: `gunicorn "backend.app:create_app()"`
   * Environment: everything from `.env.example`, with `FLASK_ENV=production`.

## Known limitations

* **No rate limiting.** Anyone with a contribute link can post repeatedly. The
  organizer can hide spam. Flask-Limiter would be the fix.
* **Deleting a wall does not delete its files from Cloudinary**, only the database
  rows. The media table stores URLs, not Cloudinary IDs.
* **File type is taken from the browser's declared MIME type.** Cloudinary rejects
  files that are not real images/video, but a stricter check would inspect the bytes.
* **No email verification or password reset** for organizers.
* **Voice recording needs HTTPS** (or localhost). Browsers block the microphone on
  plain-HTTP sites; Render serves HTTPS automatically.
