"""
utils/validators.py
Small input checks that run BEFORE touching the database. They exist to
give fast, specific error messages. The database constraints remain the
real guarantee, so even if a check here is missed, bad data still cannot
be stored.
"""

from datetime import date, datetime, time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import request

from backend.utils.errors import ApiError

RELATIONS = {"friend", "family", "colleague", "classmate", "other"}


def json_body():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ApiError("Request body must be a JSON object.")
    return data


def required_str(data, field, max_len, label=None):
    value = data.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ApiError(f"{label or field} is required.", code="missing_field")
    value = value.strip()
    if len(value) > max_len:
        raise ApiError(f"{label or field} must be at most {max_len} characters.")
    return value


def optional_str(data, field, max_len, label=None):
    value = data.get(field)
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if not isinstance(value, str):
        raise ApiError(f"{label or field} must be text.")
    value = value.strip()
    if len(value) > max_len:
        raise ApiError(f"{label or field} must be at most {max_len} characters.")
    return value


def relation(value):
    value = (value or "friend").strip().lower()
    if value not in RELATIONS:
        raise ApiError("Relation must be one of: " + ", ".join(sorted(RELATIONS)) + ".")
    return value


def parse_date(value, field="birthday_date"):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ApiError(f"{field} must be a date in YYYY-MM-DD format.")


def parse_timezone(value, default):
    name = value or default
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        raise ApiError(f"Unknown timezone '{name}'. Use a name like 'Asia/Kolkata'.")


def midnight_in(day: date, tz: ZoneInfo) -> datetime:
    """
    Midnight at the START of `day` in the birthday person's timezone, as an
    aware datetime. Midnight 19 Oct in India is 18:30 UTC on 18 Oct; if we
    used UTC the wall would open 5.5 hours late.
    """
    return datetime.combine(day, time(0, 0), tzinfo=tz)
