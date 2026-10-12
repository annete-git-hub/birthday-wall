# MongoDB collections

PostgreSQL holds everything that has relationships and must obey strict rules
(users, walls, wishes, media). MongoDB holds three kinds of data that are
flexible in shape or very high in volume:

| Collection       | Why MongoDB and not PostgreSQL |
|------------------|--------------------------------|
| `wall_settings`  | Every wall's look is different. Some have music, some have a custom background image, some add stickers. A fixed SQL table would need many NULL columns or constant ALTER TABLEs. |
| `reactions`      | Small, write-heavy, no integrity rules beyond "one emoji per wish". Keeps a fast-changing workload off the relational DB. |
| `activity_logs`  | Append-only event stream (page views, uploads). Grows fastest of all, never updated, and old entries can expire automatically with a TTL index. |

**Fair counter-argument your professor may raise:** PostgreSQL's JSONB could
store all of this too. The answer is about separating workloads: the relational
database stays small and focused on transactional data with integrity rules,
while logs and UI preferences (which can tolerate looser guarantees) live in a
store built for flexible documents and high write volume.

## Linking the two databases

MongoDB documents store `wall_id` and `wish_id` from PostgreSQL. There are **no
foreign keys across databases**, so:

* Before writing to Mongo, the backend first checks the ID exists in PostgreSQL.
* When a wall is deleted in PostgreSQL, the backend must also run
  `delete_many({"wall_id": id})` on all three collections.
* There is no shared transaction. If the Mongo write fails after the Postgres
  write succeeds, the wish is still saved; only the log/reaction is lost. This is
  acceptable because nothing in Mongo is critical data.

## 1. `wall_settings` (one document per wall)

```json
{
  "wall_id": 1,
  "theme": "confetti",
  "colors": { "background": "#FFF4E6", "accent": "#FF6B6B", "text": "#2D3436" },
  "font": "Poppins",
  "layout": "masonry",
  "background_music": {
    "url": "https://res.cloudinary.com/demo/video/upload/bw/song.mp3",
    "autoplay": false
  },
  "stickers": ["balloon", "cake", "star"],
  "show_sender_relation": true,
  "updated_at": "2026-10-01T10:00:00Z"
}
```

Optional fields (`background_music`, `stickers`, `background_image`) simply do
not exist on walls that do not use them. That is the flexibility argument.

Indexes: unique on `wall_id`.

## 2. `reactions` (birthday person reacting to a wish)

```json
{
  "wall_id": 1,
  "wish_id": 3,
  "emoji": "❤️",
  "created_at": "2026-10-11T00:05:12Z"
}
```

Indexes: unique compound `(wish_id, emoji)` so the same emoji cannot be added to
the same wish twice; `wall_id` for loading all reactions on a wall.

## 3. `activity_logs` (append-only event stream)

```json
{
  "wall_id": 1,
  "event": "wish_submitted",
  "wish_id": 7,
  "device": "mobile",
  "ip_hash": "9f86d081884c7d65",
  "timestamp": "2026-10-05T14:22:10Z"
}
```

`event` is one of: `wall_created`, `contribute_page_viewed`, `wish_submitted`,
`media_uploaded`, `reveal_page_viewed`, `reveal_too_early`.

Store a **hash** of the IP, never the raw IP (privacy).

Indexes: compound `(wall_id, timestamp)`; TTL index on `timestamp` that deletes
logs automatically after 90 days.

## Validation

Mongo is schema-less by default, but `seed_mongo.py` attaches a `$jsonSchema`
validator to each collection so required fields and allowed values are still
enforced. That is MongoDB's equivalent of CHECK constraints.

## Useful queries (mongosh)

```js
// Settings for a wall
db.wall_settings.findOne({ wall_id: 1 })

// Reaction counts per emoji on a wall
db.reactions.aggregate([
  { $match: { wall_id: 1 } },
  { $group: { _id: "$emoji", count: { $sum: 1 } } },
  { $sort: { count: -1 } }
])

// How many times each event happened on a wall
db.activity_logs.aggregate([
  { $match: { wall_id: 1 } },
  { $group: { _id: "$event", count: { $sum: 1 } } }
])

// Mobile vs desktop visitors
db.activity_logs.aggregate([
  { $match: { event: "contribute_page_viewed" } },
  { $group: { _id: "$device", visits: { $sum: 1 } } }
])
```
