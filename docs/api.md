# API reference

All responses are JSON. Errors always look like:

```json
{ "error": "Human readable message", "code": "machine_code" }
```

| Status | Meaning |
|--------|---------|
| 400 | Bad input, or the database rejected it (constraint / trigger) |
| 401 | Not logged in, or wrong password |
| 403 | Reveal link opened before the birthday (`code: not_yet_revealed`) |
| 404 | Unknown token, or a wall that is not yours |
| 409 | Duplicate (email already registered) |
| 410 | Wall is closed to new wishes |
| 503 | MongoDB or Cloudinary not configured |

Three kinds of user, three kinds of permission:

| Who | How they are authorised |
|-----|-------------------------|
| Organizer | Logs in; session cookie |
| Friends and family | `contribute_token` in their link |
| Birthday person | `reveal_token` in their link |

---

## Organizer accounts

### `POST /api/auth/register`
```json
{ "full_name": "Ananya Iyer", "email": "ananya@example.com", "password": "at-least-8" }
```
201 → `{ "user_id": 4, "full_name": "...", "email": "..." }` and logs in.

### `POST /api/auth/login`
```json
{ "email": "ananya@example.com", "password": "password123" }
```

### `POST /api/auth/logout` · `GET /api/auth/me`

Seed accounts (all password `password123`): `ananya@example.com`,
`karthik@example.com`, `divya@example.com`.

---

## Walls (organizer, login required)

### `POST /api/walls`
```json
{
  "birthday_person_name": "Kavya",
  "birthday_date": "2026-11-20",
  "timezone": "Asia/Kolkata",
  "theme": "confetti"
}
```
`timezone` and `theme` are optional. The wall opens at midnight of
`birthday_date` in that timezone.

201 →
```json
{
  "wall_id": 5,
  "birthday_person_name": "Kavya",
  "birthday_date": "2026-11-20",
  "reveal_at": "2026-11-19T18:30:00+00:00",
  "contribute_token": "9f2c...",
  "reveal_token": "a71b...",
  "contribute_url": "https://your-site/wall/9f2c...",
  "reveal_url": "https://your-site/reveal/a71b..."
}
```

### `GET /api/walls`
Dashboard list from `v_wall_summary`: status (`collecting` / `revealed` /
`locked`), counts of wishes, photos, voice notes, videos, storage used.

### `GET /api/walls/<wall_id>`
Summary + links + `stats` from `fn_wall_stats`.

### `GET /api/walls/<wall_id>/wishes`
Every wish including hidden ones, with media, for moderation.

### `PATCH /api/walls/<wall_id>`
```json
{ "is_locked": true }
```

### `PATCH /api/walls/<wall_id>/wishes/<wish_id>`
```json
{ "is_hidden": true }
```

### `DELETE /api/walls/<wall_id>`
Deletes the wall in PostgreSQL (cascades to wishes and media) and its documents in MongoDB.

### `GET /api/walls/<wall_id>/settings` · `PUT /api/walls/<wall_id>/settings`
Stored in MongoDB. Send only the fields you want to change:
```json
{
  "theme": "night",
  "layout": "grid",
  "font": "Poppins",
  "colors": { "background": "#1E272E", "accent": "#FFC048", "text": "#F5F6FA" },
  "background_music": { "url": "https://...", "autoplay": false },
  "stickers": ["cake", "balloon"],
  "show_sender_relation": true
}
```
Themes: confetti, minimal, pastel, night, retro. Layouts: masonry, grid, timeline.
Send `"background_music": null` to remove it.

---

## Contributing (friends and family, no login)

### `GET /api/contribute/<contribute_token>`
```json
{
  "birthday_person_name": "Arjun Nair",
  "birthday_date": "2026-10-19",
  "reveal_at": "2026-10-18T18:30:00+00:00",
  "is_open": true,
  "wish_count": 4
}
```
The reveal token is never included.

### `POST /api/contribute/<contribute_token>/wishes`

Text only, as JSON:
```json
{ "sender_name": "Deepa", "sender_relation": "classmate", "message_text": "Happy birthday!" }
```

With files, as `multipart/form-data`: fields `sender_name`, `sender_relation`,
`message_text`, and `files` repeated up to 5 times.

```js
const form = new FormData();
form.append("sender_name", "Deepa");
form.append("message_text", "Happy birthday!");
for (const f of fileInput.files) form.append("files", f);
await fetch(`/api/contribute/${token}/wishes`, { method: "POST", body: form });
```

Rules: a message, at least one file, or both. Images ≤ 10 MB, audio ≤ 20 MB,
video ≤ 50 MB, audio/video ≤ 3 minutes. `sender_relation` is one of friend,
family, colleague, classmate, other (default friend).

201 → `{ "message": "...", "wish_id": 17, "files_attached": 2 }`

---

## Reveal (birthday person, no login)

### `GET /api/reveal/<reveal_token>`

Before the birthday → 403:
```json
{
  "error": "Not yet! This wall opens on 19 October 2026.",
  "code": "not_yet_revealed",
  "reveal_at": "2026-10-18T18:30:00+00:00",
  "birthday_person_name": "Arjun Nair"
}
```

After → 200:
```json
{
  "birthday_person_name": "Priya Sharma",
  "birthday_date": "2026-10-11",
  "settings": { "theme": "confetti", "layout": "masonry", "...": "..." },
  "stats": { "total_wishes": 8, "photos": 5, "voice_notes": 2, "videos": 1, "...": "..." },
  "wishes": [
    {
      "wish_id": 1,
      "sender_name": "Rohan",
      "sender_relation": "friend",
      "message_text": "Happy birthday Priya!...",
      "created_at": "2026-09-22T03:56:51+00:00",
      "media": [ { "media_id": 1, "type": "image", "url": "https://...", "mime_type": "image/jpeg", "duration_seconds": null } ],
      "reactions": ["❤️"]
    }
  ]
}
```

### `POST /api/reveal/<reveal_token>/wishes/<wish_id>/reactions`
### `DELETE /api/reveal/<reveal_token>/wishes/<wish_id>/reactions`
```json
{ "emoji": "❤️" }
```
Allowed: ❤️ 😂 🥹 🎉 😍 🙏 🔥 👏. Returns the wish's current reactions.

---

## Other

`GET /api/health` → `{ "postgres": "ok", "mongo": "ok" }`

HTML pages served by Flask: `/` (organizer), `/wall/<contribute_token>` (contribute),
`/reveal/<reveal_token>` (countdown before the birthday, the wall after). Unknown
tokens return a 404 page.
