"""
routes/reveal.py
What the BIRTHDAY PERSON sees. No login: the reveal token is the permission.

GET /api/reveal/<token>
  * before reveal_at -> 403 {"code": "not_yet_revealed", "reveal_at": ...}
                        so the frontend can show a countdown
  * after            -> wall info, theme (MongoDB), stats, every visible
                        wish with its media and reactions
"""

import psycopg2
from flask import Blueprint, jsonify

from backend.db.mongo import get_mongo
from backend.db.postgres import get_cursor
from backend.utils.errors import ApiError
from backend.utils.logger import log_event

bp = Blueprint("reveal", __name__, url_prefix="/api/reveal")

DEFAULT_SETTINGS = {"theme": "confetti", "layout": "masonry"}


@bp.get("/<token>")
def reveal(token):
    with get_cursor() as cur:
        cur.execute(
            """SELECT wall_id, birthday_person_name, birthday_date, reveal_at
                 FROM walls WHERE reveal_token = %s""",
            (token,),
        )
        wall = cur.fetchone()
    if wall is None:
        raise ApiError("This link is not valid.", status=404, code="not_found")

    # fn_get_reveal_wall enforces the reveal time INSIDE the database, so
    # even a bug in this file cannot show wishes early.
    try:
        with get_cursor() as cur:
            cur.execute("SELECT * FROM fn_get_reveal_wall(%s)", (token,))
            wishes = cur.fetchall()
            cur.execute("SELECT * FROM fn_wall_stats(%s)", (wall["wall_id"],))
            stats = cur.fetchone()
    except psycopg2.Error as err:
        if err.pgcode == "42501":       # raised as NOT_YET_REVEALED:<time>
            log_event("reveal_too_early", wall["wall_id"])
            raise ApiError(
                f"Not yet! This wall opens on {wall['birthday_date']:%d %B %Y}.",
                status=403, code="not_yet_revealed",
                extra={"reveal_at": wall["reveal_at"].isoformat(),
                       "birthday_person_name": wall["birthday_person_name"]},
            )
        raise

    settings, reactions = dict(DEFAULT_SETTINGS), {}
    db = get_mongo()
    if db is not None:
        try:
            doc = db.wall_settings.find_one({"wall_id": wall["wall_id"]},
                                            {"_id": 0, "wall_id": 0, "updated_at": 0})
            if doc:
                settings.update(doc)
            for r in db.reactions.find({"wall_id": wall["wall_id"]}, {"_id": 0}):
                reactions.setdefault(r["wish_id"], []).append(r["emoji"])
        except Exception:
            pass   # Mongo is a nice-to-have here; the wishes still load

    for w in wishes:
        w["reactions"] = reactions.get(w["wish_id"], [])

    log_event("reveal_page_viewed", wall["wall_id"])

    return jsonify({
        "birthday_person_name": wall["birthday_person_name"],
        "birthday_date": wall["birthday_date"],
        "settings": settings,
        "stats": stats,
        "wishes": wishes,
    })
