"""
utils/auth.py
Organizer authentication using Flask's signed session cookie.

* Organizers (people who create walls) log in.
* Contributors and the birthday person do NOT log in. They are
  authorised by the secret token in their link instead.
"""

from functools import wraps

from flask import session

from backend.db.postgres import get_cursor
from backend.utils.errors import ApiError


def current_user_id():
    return session.get("user_id")


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if current_user_id() is None:
            raise ApiError("Please log in first.", status=401, code="unauthorized")
        return view(*args, **kwargs)
    return wrapper


def get_owned_wall(cur, wall_id):
    """
    Return the wall row if it exists AND belongs to the logged-in user.
    A wall owned by someone else returns 404 (not 403) so that users cannot
    discover which wall IDs exist.
    """
    cur.execute(
        "SELECT * FROM walls WHERE wall_id = %s AND creator_id = %s",
        (wall_id, current_user_id()),
    )
    wall = cur.fetchone()
    if wall is None:
        raise ApiError("Wall not found.", status=404, code="not_found")
    return wall


def require_wall_owner(wall_id):
    with get_cursor() as cur:
        return get_owned_wall(cur, wall_id)
