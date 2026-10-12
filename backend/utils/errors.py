"""
utils/errors.py
Turns every error into a consistent JSON response:
    {"error": "human readable message", "code": "machine_code"}

Database errors are translated here. The database already rejects bad
data (constraints and triggers), so the backend does not repeat every rule;
it just converts PostgreSQL's error into a friendly message.
"""

import logging

import psycopg2
from flask import jsonify
from werkzeug.exceptions import HTTPException

log = logging.getLogger(__name__)


class ApiError(Exception):
    """Raise this from any route to return a clean JSON error."""

    def __init__(self, message, status=400, code="bad_request", extra=None):
        super().__init__(message)
        self.message = message
        self.status = status
        self.code = code
        self.extra = extra or {}


# Friendly messages for named constraints in 02_constraints.sql
CONSTRAINT_MESSAGES = {
    "uq_users_email": "An account with this email already exists.",
    "ck_users_email_format": "Please enter a valid email address.",
    "ck_users_name_not_blank": "Name cannot be empty.",
    "fk_walls_creator": "Organizer account not found.",
    "ck_walls_reveal_after_creation": "The birthday must be in the future.",
    "ck_walls_name_not_blank": "Birthday person's name cannot be empty.",
    "ck_wishes_sender_not_blank": "Please enter your name.",
    "ck_wishes_relation": "Relation must be friend, family, colleague, classmate or other.",
    "ck_wishes_message_length": "Message must be between 1 and 2000 characters.",
    "ck_media_type": "Only images, audio and video can be uploaded.",
    "ck_media_mime_matches_type": "File type does not match its content.",
    "ck_media_file_size": "File is too large (images 10 MB, audio 20 MB, video 50 MB).",
    "ck_media_duration": "Audio and video can be at most 3 minutes long.",
    "ck_media_url_https": "File URL must use https.",
}

# PostgreSQL error codes -> (HTTP status, our code)
PG_STATUS = {
    "23505": (409, "duplicate"),          # unique_violation
    "23514": (400, "rule_violation"),     # check_violation (also raised by our triggers)
    "23503": (400, "invalid_reference"),  # foreign_key_violation
    "23502": (400, "missing_field"),      # not_null_violation
    "P0002": (404, "not_found"),          # no_data_found (invalid token in functions)
    "42501": (403, "forbidden"),          # insufficient_privilege (reveal too early)
    "P0001": (400, "rule_violation"),     # plain RAISE EXCEPTION (e.g. trigger T5)
    "22P02": (400, "invalid_value"),      # invalid_text_representation
}


def _pg_message(err):
    diag = err.diag
    if diag.constraint_name and diag.constraint_name in CONSTRAINT_MESSAGES:
        return CONSTRAINT_MESSAGES[diag.constraint_name]
    # Trigger messages (RAISE EXCEPTION '...') are already human readable
    return diag.message_primary or "Database error."


def register_error_handlers(app):

    @app.errorhandler(ApiError)
    def handle_api_error(err):
        body = {"error": err.message, "code": err.code, **err.extra}
        return jsonify(body), err.status

    @app.errorhandler(psycopg2.Error)
    def handle_db_error(err):
        status, code = PG_STATUS.get(err.pgcode, (500, "database_error"))
        if status == 500:
            log.exception("Unexpected database error")
            return jsonify({"error": "Database error.", "code": code}), 500
        return jsonify({"error": _pg_message(err), "code": code}), status

    @app.errorhandler(HTTPException)
    def handle_http_error(err):
        return jsonify({"error": err.description, "code": err.name.lower().replace(" ", "_")}), err.code

    @app.errorhandler(Exception)
    def handle_unexpected(err):
        log.exception("Unhandled error")
        return jsonify({"error": "Something went wrong.", "code": "server_error"}), 500
