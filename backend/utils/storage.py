"""
utils/storage.py
Validates uploaded files and stores them in Cloudinary.

The DATABASE never stores the file itself, only the https URL and metadata
returned here (see the media table).

Flow for one wish:
    1. validate_files()  check count, type and size before uploading anything
    2. upload_all()      send each file to Cloudinary, collect metadata
    3. call the database procedure with that metadata
    4. if step 3 fails -> delete_uploaded() removes the files from Cloudinary,
       so failed wishes do not leave orphan files behind.
"""

import logging
import math
from urllib.parse import urlparse

from flask import current_app

from backend.utils.errors import ApiError

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------
def _file_size(f):
    f.stream.seek(0, 2)          # jump to end
    size = f.stream.tell()
    f.stream.seek(0)             # back to start for the upload
    return size


def _media_type_for(mime):
    for media_type, allowed in current_app.config["ALLOWED_MIME_TYPES"].items():
        if mime in allowed:
            return media_type
    return None


def validate_files(files):
    """Returns a list of (file, media_type, mime, size). Raises ApiError on any problem."""
    files = [f for f in files if f and f.filename]
    limit = current_app.config["MAX_FILES_PER_WISH"]
    if len(files) > limit:
        raise ApiError(f"You can attach at most {limit} files.")

    checked = []
    for f in files:
        mime = (f.mimetype or "").lower()
        media_type = _media_type_for(mime)
        if media_type is None:
            raise ApiError(f"'{f.filename}' is not a supported image, audio or video file.")
        size = _file_size(f)
        max_bytes = current_app.config["MAX_FILE_BYTES"][media_type]
        if size == 0:
            raise ApiError(f"'{f.filename}' is empty.")
        if size > max_bytes:
            raise ApiError(f"'{f.filename}' is too large. Max for {media_type} is "
                           f"{max_bytes // (1024 * 1024)} MB.")
        checked.append((f, media_type, mime, size))
    return checked


# ---------------------------------------------------------------------
# Storage backends
# ---------------------------------------------------------------------
class CloudinaryStorage:
    def __init__(self, url):
        import cloudinary
        import cloudinary.uploader

        parts = urlparse(url)   # cloudinary://API_KEY:API_SECRET@CLOUD_NAME
        cloudinary.config(cloud_name=parts.hostname, api_key=parts.username,
                          api_secret=parts.password, secure=True)
        self._uploader = cloudinary.uploader

    def upload(self, f, media_type, folder):
        # Cloudinary treats audio as a "video" resource with no picture
        resource_type = "image" if media_type == "image" else "video"
        result = self._uploader.upload(f.stream, resource_type=resource_type, folder=folder)
        return {
            "url": result["secure_url"],
            "public_id": result["public_id"],
            "resource_type": resource_type,
            "duration": result.get("duration"),
        }

    def delete(self, public_id, resource_type):
        self._uploader.destroy(public_id, resource_type=resource_type)


_storage = None


def init_storage(app):
    global _storage
    url = app.config.get("CLOUDINARY_URL")
    if url and _storage is None:
        _storage = CloudinaryStorage(url)


def set_storage(storage):
    """Lets tests swap in a fake storage backend."""
    global _storage
    _storage = storage


def upload_all(checked_files, wall_id):
    """Uploads validated files. Returns (media_json_for_db, uploaded_refs)."""
    if not checked_files:
        return [], []
    if _storage is None:
        raise ApiError("File uploads are not configured on this server.",
                       status=503, code="uploads_disabled")

    media, uploaded = [], []
    try:
        for f, media_type, mime, size in checked_files:
            info = _storage.upload(f, media_type, folder=f"birthday-wall/{wall_id}")
            uploaded.append(info)
            item = {"type": media_type, "url": info["url"], "mime": mime, "size": size}
            if media_type != "image" and info.get("duration"):
                item["duration"] = max(1, math.ceil(info["duration"]))
            media.append(item)
    except ApiError:
        raise
    except Exception:
        log.exception("Upload to storage failed")
        delete_uploaded(uploaded)
        raise ApiError("Could not upload your files. Please try again.",
                       status=502, code="upload_failed")
    return media, uploaded


def delete_uploaded(uploaded):
    if _storage is None:
        return
    for info in uploaded:
        try:
            _storage.delete(info["public_id"], info["resource_type"])
        except Exception:
            log.warning("Could not delete orphan file %s", info.get("public_id"), exc_info=True)
