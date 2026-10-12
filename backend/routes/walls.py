"""
routes/walls.py
Everything the ORGANIZER does. All routes require login, and every wall
lookup checks creator_id so one organizer can never touch another's wall.

POST   /api/walls                                  create a wall
GET    /api/walls                                  my walls (dashboard)
GET    /api/walls/<id>                             one wall + links + stats
GET    /api/walls/<id>/wishes                      all wishes incl. hidden (moderation)
PATCH  /api/walls/<id>                             lock / unlock
PATCH  /api/walls/<id>/wishes/<wish_id>            hide / unhide a wish
DELETE /api/walls/<id>                             delete wall (Postgres + Mongo)
GET    /api/walls/<id>/settings                    theme (MongoDB)
PUT    /api/walls/<id>/settings                    update theme (MongoDB)
"""

import re
from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify, request

from backend.db.mongo import delete_wall_documents, get_mongo
from backend.db.postgres import get_cursor
from backend.utils.auth import current_user_id, get_owned_wall, login_required
from backend.utils.errors import ApiError
from backend.utils.logger import log_event
from backend.utils.validators import (json_body, midnight_in, parse_date,
                                      parse_timezone, required_str)

bp = Blueprint("walls", __name__, url_prefix="/api/walls")

THEMES = {"confetti", "minimal", "pastel", "night", "retro"}
LAYOUTS = {"masonry", "grid", "timeline"}
HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _links(wall):
    base = request.host_url.rstrip("/")
    return {
        "contribute_url": f"{base}/wall/{wall['contribute_token']}",
        "reveal_url": f"{base}/reveal/{wall['reveal_token']}",
    }


def _require_mongo():
    db = get_mongo()
    if db is None:
        raise ApiError("Wall settings are unavailable (MongoDB not configured).",
                       status=503, code="mongo_unavailable")
    return db


# ---------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------
@bp.post("")
@login_required
def create_wall():
    data = json_body()
    name = required_str(data, "birthday_person_name", 100, "Birthday person's name")
    birthday = parse_date(data.get("birthday_date"))
    tz = parse_timezone(data.get("timezone"), current_app.config["DEFAULT_TIMEZONE"])
    theme = data.get("theme", "confetti")
    if theme not in THEMES:
        raise ApiError("Theme must be one of: " + ", ".join(sorted(THEMES)) + ".")

    reveal_at = midnight_in(birthday, tz)
    if reveal_at <= datetime.now(timezone.utc):
        raise ApiError("The birthday must be in the future so friends have time to post.")

    # Tokens come from the column DEFAULTs in 01_schema.sql (random, 32 chars)
    with get_cursor() as cur:
        cur.execute(
            """INSERT INTO walls (creator_id, birthday_person_name, birthday_date, reveal_at)
               VALUES (%s, %s, %s, %s)
               RETURNING wall_id, birthday_person_name, birthday_date, reveal_at,
                         contribute_token, reveal_token""",
            (current_user_id(), name, birthday, reveal_at),
        )
        wall = cur.fetchone()

    db = get_mongo()
    if db is not None:
        try:
            db.wall_settings.insert_one({
                "wall_id": wall["wall_id"], "theme": theme, "layout": "masonry",
                "updated_at": datetime.now(timezone.utc),
            })
        except Exception:
            current_app.logger.warning("Could not create wall settings", exc_info=True)
    log_event("wall_created", wall["wall_id"])

    return jsonify({**wall, **_links(wall)}), 201


# ---------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------
@bp.get("")
@login_required
def my_walls():
    with get_cursor() as cur:
        cur.execute(
            "SELECT * FROM v_wall_summary WHERE creator_id = %s ORDER BY birthday_date",
            (current_user_id(),),
        )
        walls = cur.fetchall()
    return jsonify(walls)


@bp.get("/<int:wall_id>")
@login_required
def wall_detail(wall_id):
    with get_cursor() as cur:
        wall = get_owned_wall(cur, wall_id)
        cur.execute("SELECT * FROM v_wall_summary WHERE wall_id = %s", (wall_id,))
        summary = cur.fetchone()
        cur.execute("SELECT * FROM fn_wall_stats(%s)", (wall_id,))
        stats = cur.fetchone()
    return jsonify({**summary, **_links(wall), "stats": stats})


@bp.get("/<int:wall_id>/wishes")
@login_required
def wall_wishes(wall_id):
    """Organizer view for moderation: includes hidden wishes, ignores reveal time."""
    with get_cursor() as cur:
        get_owned_wall(cur, wall_id)
        cur.execute(
            """SELECT ws.wish_id, ws.sender_name, ws.sender_relation, ws.message_text,
                      ws.is_hidden, ws.created_at,
                      COALESCE(json_agg(json_build_object(
                          'media_id', m.media_id, 'type', m.media_type,
                          'url', m.file_url, 'duration_seconds', m.duration_seconds)
                          ORDER BY m.media_id) FILTER (WHERE m.media_id IS NOT NULL),
                        '[]') AS media
                 FROM wishes ws
                 LEFT JOIN media m ON m.wish_id = ws.wish_id
                WHERE ws.wall_id = %s
                GROUP BY ws.wish_id
                ORDER BY ws.created_at""",
            (wall_id,),
        )
        wishes = cur.fetchall()
    return jsonify(wishes)


# ---------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------
@bp.patch("/<int:wall_id>")
@login_required
def update_wall(wall_id):
    data = json_body()
    if not isinstance(data.get("is_locked"), bool):
        raise ApiError("Send {\"is_locked\": true} or {\"is_locked\": false}.")
    with get_cursor() as cur:
        get_owned_wall(cur, wall_id)
        cur.execute(
            "UPDATE walls SET is_locked = %s WHERE wall_id = %s RETURNING wall_id, is_locked",
            (data["is_locked"], wall_id),
        )
        row = cur.fetchone()
    return jsonify(row)


@bp.patch("/<int:wall_id>/wishes/<int:wish_id>")
@login_required
def moderate_wish(wall_id, wish_id):
    data = json_body()
    if not isinstance(data.get("is_hidden"), bool):
        raise ApiError("Send {\"is_hidden\": true} or {\"is_hidden\": false}.")
    with get_cursor() as cur:
        get_owned_wall(cur, wall_id)
        cur.execute(
            """UPDATE wishes SET is_hidden = %s
                WHERE wish_id = %s AND wall_id = %s
            RETURNING wish_id, is_hidden""",
            (data["is_hidden"], wish_id, wall_id),
        )
        row = cur.fetchone()
    if row is None:
        raise ApiError("Wish not found on this wall.", status=404, code="not_found")
    return jsonify(row)


# ---------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------
@bp.delete("/<int:wall_id>")
@login_required
def delete_wall(wall_id):
    with get_cursor() as cur:
        get_owned_wall(cur, wall_id)
        # ON DELETE CASCADE removes the wall's wishes and media rows too
        cur.execute("DELETE FROM walls WHERE wall_id = %s", (wall_id,))
    # No foreign keys across databases: clean MongoDB by hand, AFTER the
    # Postgres delete committed (if Postgres failed we never get here).
    delete_wall_documents(wall_id)
    return jsonify({"message": "Wall deleted.", "wall_id": wall_id})


# ---------------------------------------------------------------------
# Settings (MongoDB)
# ---------------------------------------------------------------------
@bp.get("/<int:wall_id>/settings")
@login_required
def get_settings(wall_id):
    with get_cursor() as cur:
        get_owned_wall(cur, wall_id)
    doc = _require_mongo().wall_settings.find_one({"wall_id": wall_id}, {"_id": 0})
    return jsonify(doc or {"wall_id": wall_id, "theme": "confetti", "layout": "masonry"})


@bp.put("/<int:wall_id>/settings")
@login_required
def put_settings(wall_id):
    with get_cursor() as cur:
        get_owned_wall(cur, wall_id)
    data = json_body()

    update = {}
    if "theme" in data:
        if data["theme"] not in THEMES:
            raise ApiError("Theme must be one of: " + ", ".join(sorted(THEMES)) + ".")
        update["theme"] = data["theme"]
    if "layout" in data:
        if data["layout"] not in LAYOUTS:
            raise ApiError("Layout must be one of: " + ", ".join(sorted(LAYOUTS)) + ".")
        update["layout"] = data["layout"]
    if "font" in data:
        update["font"] = required_str(data, "font", 50, "Font")
    if "colors" in data:
        colors = data["colors"]
        if not isinstance(colors, dict) or not all(
                k in {"background", "accent", "text"} and isinstance(v, str) and HEX.match(v)
                for k, v in colors.items()):
            raise ApiError("colors must be like {\"background\": \"#FFF4E6\", \"accent\": ..., \"text\": ...}.")
        update["colors"] = colors
    if "background_music" in data:
        music = data["background_music"]
        if music is not None and not (isinstance(music, dict)
                                      and str(music.get("url", "")).startswith("https://")):
            raise ApiError("background_music must be null or {\"url\": \"https://...\", \"autoplay\": false}.")
        update["background_music"] = music and {"url": music["url"],
                                                "autoplay": bool(music.get("autoplay", False))}
    if "stickers" in data:
        stickers = data["stickers"]
        if not (isinstance(stickers, list) and len(stickers) <= 20
                and all(isinstance(s, str) and len(s) <= 30 for s in stickers)):
            raise ApiError("stickers must be a list of up to 20 short names.")
        update["stickers"] = stickers
    if "show_sender_relation" in data:
        update["show_sender_relation"] = bool(data["show_sender_relation"])

    if not update:
        raise ApiError("Nothing to update.")

    db = _require_mongo()
    # Optional fields set to null are removed from the document entirely
    unset = {k: "" for k, v in update.items() if v is None}
    set_ = {k: v for k, v in update.items() if v is not None}
    set_["updated_at"] = datetime.now(timezone.utc)
    ops = {"$set": set_, "$setOnInsert": {"wall_id": wall_id}}
    if unset:
        ops["$unset"] = unset
    ops["$setOnInsert"].update({k: v for k, v in
                                {"theme": "confetti", "layout": "masonry"}.items()
                                if k not in set_})
    db.wall_settings.update_one({"wall_id": wall_id}, ops, upsert=True)
    return jsonify(db.wall_settings.find_one({"wall_id": wall_id}, {"_id": 0}))
