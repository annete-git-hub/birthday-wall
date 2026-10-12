"""
routes/reactions.py
The birthday person reacts to wishes with emojis. Stored in MongoDB.

POST   /api/reveal/<token>/wishes/<wish_id>/reactions   {"emoji": "❤️"}
DELETE /api/reveal/<token>/wishes/<wish_id>/reactions   {"emoji": "❤️"}

Cross-database check: MongoDB cannot verify that wish_id exists (no
foreign keys across databases), so we ask PostgreSQL first, using the
v_revealed_wishes view. That also guarantees the wall has been revealed
and the wish is not hidden.
"""

from datetime import datetime, timezone

from flask import Blueprint, jsonify
from pymongo.errors import DuplicateKeyError

from backend.db.mongo import get_mongo
from backend.db.postgres import get_cursor
from backend.utils.errors import ApiError
from backend.utils.validators import json_body

bp = Blueprint("reactions", __name__, url_prefix="/api/reveal")

ALLOWED_EMOJIS = {"❤️", "😂", "🥹", "🎉", "😍", "🙏", "🔥", "👏"}


def _check(token, wish_id):
    db = get_mongo()
    if db is None:
        raise ApiError("Reactions are unavailable (MongoDB not configured).",
                       status=503, code="mongo_unavailable")

    emoji = json_body().get("emoji")
    if emoji not in ALLOWED_EMOJIS:
        raise ApiError("Emoji must be one of: " + " ".join(sorted(ALLOWED_EMOJIS)))

    with get_cursor() as cur:
        cur.execute(
            "SELECT wall_id FROM v_revealed_wishes WHERE reveal_token = %s AND wish_id = %s",
            (token, wish_id),
        )
        row = cur.fetchone()
    if row is None:
        raise ApiError("Wish not found.", status=404, code="not_found")
    return db, row["wall_id"], emoji


def _emojis(db, wish_id):
    return [r["emoji"] for r in db.reactions.find({"wish_id": wish_id}, {"emoji": 1})]


@bp.post("/<token>/wishes/<int:wish_id>/reactions")
def add_reaction(token, wish_id):
    db, wall_id, emoji = _check(token, wish_id)
    try:
        db.reactions.insert_one({
            "wall_id": wall_id, "wish_id": wish_id, "emoji": emoji,
            "created_at": datetime.now(timezone.utc),
        })
    except DuplicateKeyError:
        pass   # unique index (wish_id, emoji): reacting twice is a no-op
    return jsonify({"wish_id": wish_id, "reactions": _emojis(db, wish_id)}), 201


@bp.delete("/<token>/wishes/<int:wish_id>/reactions")
def remove_reaction(token, wish_id):
    db, _, emoji = _check(token, wish_id)
    db.reactions.delete_one({"wish_id": wish_id, "emoji": emoji})
    return jsonify({"wish_id": wish_id, "reactions": _emojis(db, wish_id)})
