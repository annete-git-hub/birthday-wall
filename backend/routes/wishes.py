"""
routes/wishes.py
What FRIENDS AND FAMILY do. No login: the contribute token in the link is
the permission.

GET  /api/contribute/<token>           wall info for the contribute page
POST /api/contribute/<token>/wishes    send a wish (text and/or files)

The POST accepts either:
  * multipart/form-data  fields: sender_name, sender_relation, message_text
                         files:  files (repeat up to 5 times)
  * application/json     {sender_name, sender_relation, message_text}  (text only)
"""

import json

from flask import Blueprint, jsonify, request

from backend.db.postgres import get_cursor
from backend.utils.errors import ApiError
from backend.utils.logger import log_event
from backend.utils.storage import delete_uploaded, upload_all, validate_files
from backend.utils.validators import optional_str, relation, required_str

bp = Blueprint("wishes", __name__, url_prefix="/api/contribute")


def _find_wall(cur, token):
    cur.execute(
        """SELECT wall_id, birthday_person_name, birthday_date, reveal_at, is_locked,
                  (NOT is_locked AND now() < reveal_at) AS is_open
             FROM walls WHERE contribute_token = %s""",
        (token,),
    )
    wall = cur.fetchone()
    if wall is None:
        raise ApiError("This link is not valid.", status=404, code="not_found")
    return wall


@bp.get("/<token>")
def wall_info(token):
    with get_cursor() as cur:
        wall = _find_wall(cur, token)
        cur.execute(
            "SELECT COUNT(*) AS n FROM wishes WHERE wall_id = %s AND is_hidden = FALSE",
            (wall["wall_id"],),
        )
        count = cur.fetchone()["n"]
    log_event("contribute_page_viewed", wall["wall_id"])

    # Never return reveal_token here. Note the SELECT above does not even fetch it.
    return jsonify({
        "birthday_person_name": wall["birthday_person_name"],
        "birthday_date": wall["birthday_date"],
        "reveal_at": wall["reveal_at"],
        "is_open": wall["is_open"],
        "wish_count": count,
    })


@bp.post("/<token>/wishes")
def submit_wish(token):
    if request.is_json:
        data = request.get_json(silent=True) or {}
        files = []
    else:
        data = request.form
        files = request.files.getlist("files")

    sender_name = required_str(data, "sender_name", 100, "Your name")
    sender_relation = relation(data.get("sender_relation"))
    message_text = optional_str(data, "message_text", 2000, "Message")

    checked = validate_files(files)
    if message_text is None and not checked:
        raise ApiError("Write a message or attach at least one file.")

    # Fail fast BEFORE uploading files to a wall that is already closed.
    # (Trigger T1 would reject it anyway, but the files would already be
    #  uploaded by then.)
    with get_cursor() as cur:
        wall = _find_wall(cur, token)
    if not wall["is_open"]:
        raise ApiError("This wall is closed and no longer accepts wishes.",
                       status=410, code="wall_closed")

    media, uploaded = upload_all(checked, wall["wall_id"])

    # One procedure call = one transaction: wish + all media, or nothing.
    try:
        with get_cursor() as cur:
            cur.execute(
                "CALL sp_submit_wish(%s, %s, %s, %s, %s::jsonb, NULL)",
                (token, sender_name, sender_relation, message_text,
                 json.dumps(media) if media else None),
            )
            wish_id = cur.fetchone()["p_wish_id"]
    except Exception:
        # Database rejected it: remove the files we just uploaded
        delete_uploaded(uploaded)
        raise

    log_event("wish_submitted", wall["wall_id"], wish_id)
    for _ in media:
        log_event("media_uploaded", wall["wall_id"], wish_id)

    return jsonify({
        "message": f"Your wish for {wall['birthday_person_name']} has been saved!",
        "wish_id": wish_id,
        "files_attached": len(media),
    }), 201
