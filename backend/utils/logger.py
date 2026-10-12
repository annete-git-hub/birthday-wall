"""
utils/logger.py
Writes activity events to MongoDB's activity_logs collection.

Logging must NEVER break the main request: if MongoDB is down or not
configured, the wish is still saved and we just lose one log entry.
"""

import hashlib
import logging
from datetime import datetime, timezone

from flask import request

from backend.db.mongo import get_mongo

log = logging.getLogger(__name__)


def _device():
    ua = (request.user_agent.string or "").lower()
    if "ipad" in ua or "tablet" in ua:
        return "tablet"
    if "mobi" in ua or "android" in ua or "iphone" in ua:
        return "mobile"
    return "desktop"


def _ip_hash():
    # Behind a proxy (Render), the real client IP is the first entry in
    # X-Forwarded-For. We only ever store a hash of it, never the raw IP.
    ip = (request.headers.get("X-Forwarded-For", request.remote_addr or "")
          .split(",")[0].strip())
    return hashlib.sha256(ip.encode()).hexdigest()[:16]


def log_event(event, wall_id, wish_id=None):
    db = get_mongo()
    if db is None:
        return
    doc = {
        "wall_id": int(wall_id),
        "event": event,
        "device": _device(),
        "ip_hash": _ip_hash(),
        "timestamp": datetime.now(timezone.utc),
    }
    if wish_id is not None:
        doc["wish_id"] = int(wish_id)
    try:
        db.activity_logs.insert_one(doc)
    except Exception:
        log.warning("Could not write activity log", exc_info=True)
