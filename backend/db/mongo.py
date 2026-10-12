"""
db/mongo.py
MongoDB connection. MongoClient manages its own connection pool and is
thread-safe, so one client is created and reused for the whole app.

MongoDB is optional at runtime: if MONGO_URI is not set, get_mongo()
returns None and callers decide what to do (logging silently skips,
reactions/settings endpoints return 503).
"""

from pymongo import MongoClient

_client = None
_db = None


def init_mongo(app):
    global _client, _db
    uri = app.config.get("MONGO_URI")
    if uri and _db is None:
        _client = MongoClient(uri, serverSelectionTimeoutMS=3000)
        _db = _client[app.config["MONGO_DB"]]


def set_mongo(db):
    """Lets tests swap in an in-memory database (mongomock)."""
    global _db
    _db = db


def get_mongo():
    return _db


def delete_wall_documents(wall_id: int) -> None:
    """
    There are no foreign keys across PostgreSQL and MongoDB, so when a wall
    is deleted in PostgreSQL the backend must clean up MongoDB itself.
    """
    db = get_mongo()
    if db is None:
        return
    for name in ("wall_settings", "reactions", "activity_logs"):
        db[name].delete_many({"wall_id": wall_id})
