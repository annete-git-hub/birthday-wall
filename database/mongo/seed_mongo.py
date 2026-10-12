"""
seed_mongo.py
Creates the three MongoDB collections with validators and indexes, then
inserts demo documents that match the PostgreSQL seed data
(wall_id 1 = Priya, 2 = Arjun, 3 = Meera, 4 = Rahul).

Usage:
    pip install pymongo python-dotenv
    # put MONGO_URI in your .env, e.g. a MongoDB Atlas connection string
    python database/mongo/seed_mongo.py

WARNING: drops and recreates the collections every time it runs.
"""

import hashlib
import os
from datetime import datetime, timedelta, timezone

from pymongo import ASCENDING, MongoClient

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv is optional; plain environment variables also work

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("MONGO_DB", "birthday_wall")

NOW = datetime.now(timezone.utc)

EVENTS = [
    "wall_created", "contribute_page_viewed", "wish_submitted",
    "media_uploaded", "reveal_page_viewed", "reveal_too_early",
]

# ---------------------------------------------------------------------
# $jsonSchema validators: MongoDB's version of NOT NULL / CHECK
# ---------------------------------------------------------------------
VALIDATORS = {
    "wall_settings": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["wall_id", "theme", "layout", "updated_at"],
            "properties": {
                "wall_id": {"bsonType": "int", "minimum": 1},
                "theme": {"enum": ["confetti", "minimal", "pastel", "night", "retro"]},
                "layout": {"enum": ["masonry", "grid", "timeline"]},
                "font": {"bsonType": "string"},
                "colors": {
                    "bsonType": "object",
                    "properties": {
                        "background": {"bsonType": "string", "pattern": "^#[0-9A-Fa-f]{6}$"},
                        "accent": {"bsonType": "string", "pattern": "^#[0-9A-Fa-f]{6}$"},
                        "text": {"bsonType": "string", "pattern": "^#[0-9A-Fa-f]{6}$"},
                    },
                },
                "background_music": {
                    "bsonType": "object",
                    "required": ["url"],
                    "properties": {
                        "url": {"bsonType": "string", "pattern": "^https://"},
                        "autoplay": {"bsonType": "bool"},
                    },
                },
                "stickers": {"bsonType": "array", "items": {"bsonType": "string"}, "maxItems": 20},
                "updated_at": {"bsonType": "date"},
            },
        }
    },
    "reactions": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["wall_id", "wish_id", "emoji", "created_at"],
            "properties": {
                "wall_id": {"bsonType": "int", "minimum": 1},
                "wish_id": {"bsonType": "int", "minimum": 1},
                "emoji": {"bsonType": "string", "maxLength": 16},
                "created_at": {"bsonType": "date"},
            },
        }
    },
    "activity_logs": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["wall_id", "event", "timestamp"],
            "properties": {
                "wall_id": {"bsonType": "int", "minimum": 1},
                "event": {"enum": EVENTS},
                "wish_id": {"bsonType": "int"},
                "device": {"enum": ["mobile", "desktop", "tablet"]},
                "ip_hash": {"bsonType": "string"},
                "timestamp": {"bsonType": "date"},
            },
        }
    },
}


def ip_hash(ip: str) -> str:
    """Store a short hash of the IP, never the raw address."""
    return hashlib.sha256(ip.encode()).hexdigest()[:16]


def days_ago(n: float) -> datetime:
    return NOW - timedelta(days=n)


def create_collections(db):
    for name, validator in VALIDATORS.items():
        db.drop_collection(name)
        db.create_collection(name, validator=validator, validationLevel="strict")

    db.wall_settings.create_index([("wall_id", ASCENDING)], unique=True, name="uq_wall_id")

    db.reactions.create_index(
        [("wish_id", ASCENDING), ("emoji", ASCENDING)], unique=True, name="uq_wish_emoji"
    )
    db.reactions.create_index([("wall_id", ASCENDING)], name="idx_wall_id")

    db.activity_logs.create_index(
        [("wall_id", ASCENDING), ("timestamp", ASCENDING)], name="idx_wall_time"
    )
    # TTL index: MongoDB deletes each log 90 days after its timestamp
    db.activity_logs.create_index(
        [("timestamp", ASCENDING)], expireAfterSeconds=90 * 24 * 3600, name="ttl_90_days"
    )


def seed(db):
    db.wall_settings.insert_many([
        {
            "wall_id": 1, "theme": "confetti", "layout": "masonry",
            "background_music": {
                "url": "https://res.cloudinary.com/demo/video/upload/bw/happy_bday.mp3",
                "autoplay": False,
            },
            "stickers": ["balloon", "cake", "star"],
            "show_sender_relation": True,
            "updated_at": days_ago(29),
        },
        {
            # no music, no stickers: fields are simply absent
            "wall_id": 2, "theme": "minimal", "layout": "grid", "font": "Inter",
            "colors": {"background": "#FFFFFF", "accent": "#0984E3", "text": "#2D3436"},
            "updated_at": days_ago(10),
        },
        {
            "wall_id": 3, "theme": "pastel", "layout": "timeline",
            "updated_at": days_ago(2),
        },
        {
            "wall_id": 4, "theme": "night", "layout": "masonry", "font": "Lora",
            "colors": {"background": "#1E272E", "accent": "#FFC048", "text": "#F5F6FA"},
            "background_image": "https://res.cloudinary.com/demo/image/upload/bw/stars.jpg",
            "updated_at": days_ago(50),
        },
    ])

    # Priya (wall 1) and Rahul (wall 4) have opened their walls and reacted
    db.reactions.insert_many([
        {"wall_id": 1, "wish_id": 1, "emoji": "😂", "created_at": days_ago(0.9)},
        {"wall_id": 1, "wish_id": 2, "emoji": "❤️", "created_at": days_ago(0.9)},
        {"wall_id": 1, "wish_id": 2, "emoji": "🥹", "created_at": days_ago(0.9)},
        {"wall_id": 1, "wish_id": 3, "emoji": "😂", "created_at": days_ago(0.8)},
        {"wall_id": 1, "wish_id": 4, "emoji": "❤️", "created_at": days_ago(0.8)},
        {"wall_id": 1, "wish_id": 7, "emoji": "🎉", "created_at": days_ago(0.7)},
        {"wall_id": 1, "wish_id": 8, "emoji": "❤️", "created_at": days_ago(0.7)},
        {"wall_id": 1, "wish_id": 8, "emoji": "🥹", "created_at": days_ago(0.7)},
        {"wall_id": 4, "wish_id": 15, "emoji": "❤️", "created_at": days_ago(28)},
    ])

    logs = [{"wall_id": w, "event": "wall_created", "device": "desktop",
             "ip_hash": ip_hash(f"10.0.0.{w}"), "timestamp": days_ago(d)}
            for w, d in [(1, 30), (2, 10), (3, 2)]]
    # wall 4 was created 50 days ago, so its logs already expired under the TTL rule

    # (wall_id, wish_id, days_ago, device) for each seeded wish
    wishes = [
        (1, 1, 20, "mobile"), (1, 2, 18, "mobile"), (1, 3, 15, "desktop"),
        (1, 4, 12, "mobile"), (1, 5, 9, "mobile"), (1, 6, 6, "desktop"),
        (1, 7, 5, "mobile"), (1, 8, 2, "tablet"),
        (2, 9, 8, "mobile"), (2, 10, 6, "mobile"), (2, 11, 4, "desktop"),
        (2, 12, 3, "mobile"),
    ]
    for wall_id, wish_id, d, device in wishes:
        ip = ip_hash(f"192.168.{wall_id}.{wish_id}")
        logs.append({"wall_id": wall_id, "event": "contribute_page_viewed",
                     "device": device, "ip_hash": ip, "timestamp": days_ago(d + 0.01)})
        logs.append({"wall_id": wall_id, "event": "wish_submitted", "wish_id": wish_id,
                     "device": device, "ip_hash": ip, "timestamp": days_ago(d)})

    for wish_id in (1, 3, 4, 6, 7, 8, 10, 11):
        wall_id = 1 if wish_id <= 8 else 2
        logs.append({"wall_id": wall_id, "event": "media_uploaded", "wish_id": wish_id,
                     "timestamp": days_ago(5)})

    # Priya tried to peek early, then opened it on her birthday
    logs.append({"wall_id": 1, "event": "reveal_too_early", "device": "mobile",
                 "ip_hash": ip_hash("49.36.1.1"), "timestamp": days_ago(3)})
    logs.append({"wall_id": 1, "event": "reveal_page_viewed", "device": "mobile",
                 "ip_hash": ip_hash("49.36.1.1"), "timestamp": days_ago(0.95)})

    db.activity_logs.insert_many(logs)


def summary(db):
    print("\nDocuments per collection:")
    for name in VALIDATORS:
        print(f"  {name:15} {db[name].count_documents({})}")

    print("\nReactions on Priya's wall (wall 1):")
    for row in db.reactions.aggregate([
        {"$match": {"wall_id": 1}},
        {"$group": {"_id": "$emoji", "count": {"$sum": 1}}},
        {"$sort": {"count": -1, "_id": 1}},
    ]):
        print(f"  {row['_id']}  {row['count']}")

    print("\nEvents on wall 1:")
    for row in db.activity_logs.aggregate([
        {"$match": {"wall_id": 1}},
        {"$group": {"_id": "$event", "count": {"$sum": 1}}},
        {"$sort": {"_id": 1}},
    ]):
        print(f"  {row['_id']:24} {row['count']}")


def main():
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    client.admin.command("ping")  # fail fast with a clear error if Mongo is unreachable
    db = client[DB_NAME]

    create_collections(db)
    seed(db)
    summary(db)
    print(f"\nSeeded database '{DB_NAME}'.")


if __name__ == "__main__":
    main()
