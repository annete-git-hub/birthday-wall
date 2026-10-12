"""
routes/auth.py
Organizer accounts.

POST /api/auth/register   {full_name, email, password}
POST /api/auth/login      {email, password}
POST /api/auth/logout
GET  /api/auth/me
"""

from flask import Blueprint, jsonify, session
from werkzeug.security import check_password_hash, generate_password_hash

from backend.db.postgres import get_cursor
from backend.utils.auth import current_user_id, login_required
from backend.utils.errors import ApiError
from backend.utils.validators import json_body, required_str

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


def _public_user(row):
    return {"user_id": row["user_id"], "full_name": row["full_name"], "email": row["email"]}


@bp.post("/register")
def register():
    data = json_body()
    full_name = required_str(data, "full_name", 100, "Name")
    email = required_str(data, "email", 255, "Email").lower()
    password = required_str(data, "password", 128, "Password")
    if len(password) < 8:
        raise ApiError("Password must be at least 8 characters.")

    # Duplicate email and bad format are rejected by uq_users_email and
    # ck_users_email_format in the database; errors.py turns them into
    # friendly messages.
    with get_cursor() as cur:
        cur.execute(
            """INSERT INTO users (full_name, email, password_hash)
               VALUES (%s, %s, %s)
               RETURNING user_id, full_name, email""",
            (full_name, email, generate_password_hash(password)),
        )
        user = cur.fetchone()

    session.clear()
    session["user_id"] = user["user_id"]
    return jsonify(_public_user(user)), 201


@bp.post("/login")
def login():
    data = json_body()
    email = required_str(data, "email", 255, "Email").lower()
    password = required_str(data, "password", 128, "Password")

    with get_cursor() as cur:
        cur.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cur.fetchone()

    # Same message whether the email or the password is wrong, so attackers
    # cannot find out which emails are registered.
    if user is None or not check_password_hash(user["password_hash"], password):
        raise ApiError("Incorrect email or password.", status=401, code="unauthorized")

    session.clear()
    session["user_id"] = user["user_id"]
    return jsonify(_public_user(user))


@bp.post("/logout")
def logout():
    session.clear()
    return jsonify({"message": "Logged out."})


@bp.get("/me")
@login_required
def me():
    with get_cursor() as cur:
        cur.execute("SELECT user_id, full_name, email FROM users WHERE user_id = %s",
                    (current_user_id(),))
        user = cur.fetchone()
    if user is None:          # account deleted while logged in
        session.clear()
        raise ApiError("Please log in first.", status=401, code="unauthorized")
    return jsonify(_public_user(user))
