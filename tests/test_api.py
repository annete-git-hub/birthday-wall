"""
End-to-end API tests against a real PostgreSQL database.
Seed data (07_seed_data.sql):
  wall 1 Priya  revealed   owner Ananya   wishes 1-8
  wall 2 Arjun  collecting owner Karthik  wishes 9-13 (13 hidden spam)
  wall 3 Meera  collecting owner Ananya   no wishes
  wall 4 Rahul  locked     owner Divya    wishes 14-16
"""

import io
from datetime import date, datetime, timedelta, timezone

from tests.conftest import login

PRIYA_REVEAL = "priya-reveal-secret-2026"
ARJUN_CONTRIBUTE = "arjun-contribute-2026"
ARJUN_REVEAL = "arjun-reveal-secret-2026"
RAHUL_CONTRIBUTE = "rahul-contribute-2026"


def fake_file(name, mime, size=1000):
    return (io.BytesIO(b"x" * size), name, mime)


# ---------------------------------------------------------------- health
def test_health(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.get_json()["postgres"] == "ok"


# ---------------------------------------------------------------- auth
def test_register_login_me_logout(client):
    res = client.post("/api/auth/register", json={
        "full_name": "Test User", "email": "Test@Example.com", "password": "secret123"})
    assert res.status_code == 201
    assert res.get_json()["email"] == "test@example.com"       # lower-cased

    assert client.get("/api/auth/me").status_code == 200
    client.post("/api/auth/logout")
    assert client.get("/api/auth/me").status_code == 401

    login(client, "test@example.com", "secret123")
    assert client.get("/api/auth/me").get_json()["full_name"] == "Test User"


def test_register_duplicate_email_gives_friendly_message(client):
    res = client.post("/api/auth/register", json={
        "full_name": "X", "email": "ananya@example.com", "password": "secret123"})
    assert res.status_code == 409
    assert res.get_json()["error"] == "An account with this email already exists."


def test_register_bad_email_rejected_by_database(client):
    res = client.post("/api/auth/register", json={
        "full_name": "X", "email": "not-an-email", "password": "secret123"})
    assert res.status_code == 400
    assert "valid email" in res.get_json()["error"]


def test_login_wrong_password(client):
    res = client.post("/api/auth/login", json={"email": "ananya@example.com", "password": "nope"})
    assert res.status_code == 401


def test_organizer_routes_need_login(client):
    assert client.get("/api/walls").status_code == 401
    assert client.post("/api/walls", json={}).status_code == 401


# ---------------------------------------------------------------- walls
def test_create_wall(ananya, mongo):
    bday = date.today() + timedelta(days=10)
    res = ananya.post("/api/walls", json={
        "birthday_person_name": "Kavya", "birthday_date": bday.isoformat(), "theme": "pastel"})
    assert res.status_code == 201
    wall = res.get_json()
    assert len(wall["contribute_token"]) == 32
    assert wall["contribute_token"] != wall["reveal_token"]
    assert wall["contribute_url"].endswith("/wall/" + wall["contribute_token"])

    # Midnight IST = 18:30 UTC the previous day
    reveal = datetime.fromisoformat(wall["reveal_at"]).astimezone(timezone.utc)
    assert (reveal.hour, reveal.minute) == (18, 30)
    assert reveal.date() == bday - timedelta(days=1)

    assert mongo.wall_settings.find_one({"wall_id": wall["wall_id"]})["theme"] == "pastel"
    assert mongo.activity_logs.count_documents({"event": "wall_created"}) == 1


def test_create_wall_in_past_rejected(ananya):
    res = ananya.post("/api/walls", json={
        "birthday_person_name": "Old", "birthday_date": date.today().isoformat()})
    assert res.status_code == 400


def test_create_wall_bad_input(ananya):
    assert ananya.post("/api/walls", json={"birthday_date": "2030-01-01"}).status_code == 400
    assert ananya.post("/api/walls", json={
        "birthday_person_name": "A", "birthday_date": "tomorrow"}).status_code == 400
    assert ananya.post("/api/walls", json={
        "birthday_person_name": "A", "birthday_date": "2030-01-01",
        "timezone": "Mars/Base"}).status_code == 400


def test_my_walls_only_shows_own(client):
    login(client, "karthik@example.com")
    walls = client.get("/api/walls").get_json()
    assert [w["birthday_person_name"] for w in walls] == ["Arjun Nair"]
    assert walls[0]["total_wishes"] == 4          # spam wish is hidden


def test_cannot_access_someone_elses_wall(ananya):
    assert ananya.get("/api/walls/2").status_code == 404
    assert ananya.delete("/api/walls/2").status_code == 404


def test_wall_detail_has_stats(ananya):
    data = ananya.get("/api/walls/1").get_json()
    assert data["status"] == "revealed"
    assert data["stats"]["total_wishes"] == 8
    assert data["stats"]["videos"] == 1


# ---------------------------------------------------------------- contribute
def test_contribute_info_never_leaks_reveal_token(client):
    res = client.get(f"/api/contribute/{ARJUN_CONTRIBUTE}")
    data = res.get_json()
    assert res.status_code == 200
    assert data["is_open"] is True
    assert data["wish_count"] == 4
    assert ARJUN_REVEAL not in res.get_data(as_text=True)


def test_contribute_invalid_token(client):
    assert client.get("/api/contribute/does-not-exist").status_code == 404


def test_submit_text_wish(client, ananya):
    res = client.post(f"/api/contribute/{ARJUN_CONTRIBUTE}/wishes", json={
        "sender_name": "Deepa", "sender_relation": "classmate", "message_text": "Happy bday!"})
    assert res.status_code == 201
    assert client.get(f"/api/contribute/{ARJUN_CONTRIBUTE}").get_json()["wish_count"] == 5


def test_submit_wish_with_files(client, storage, mongo):
    res = client.post(
        f"/api/contribute/{ARJUN_CONTRIBUTE}/wishes",
        data={"sender_name": "Ravi", "message_text": "Photo and voice note!",
              "files": [fake_file("a.jpg", "image/jpeg"), fake_file("v.webm", "audio/webm")]},
        content_type="multipart/form-data",
    )
    assert res.status_code == 201, res.get_json()
    assert res.get_json()["files_attached"] == 2
    assert len(storage.uploaded) == 2
    assert mongo.activity_logs.count_documents({"event": "media_uploaded"}) == 2

    login(client, "karthik@example.com")
    wishes = client.get("/api/walls/2/wishes").get_json()
    ravi = next(w for w in wishes if w["sender_name"] == "Ravi")
    assert sorted(m["type"] for m in ravi["media"]) == ["audio", "image"]
    audio = next(m for m in ravi["media"] if m["type"] == "audio")
    assert audio["duration_seconds"] == 13          # 12.4 s rounded up


def test_media_only_wish_allowed(client):
    res = client.post(f"/api/contribute/{ARJUN_CONTRIBUTE}/wishes",
                      data={"sender_name": "Silent", "files": [fake_file("p.png", "image/png")]},
                      content_type="multipart/form-data")
    assert res.status_code == 201


def test_empty_wish_rejected(client):
    res = client.post(f"/api/contribute/{ARJUN_CONTRIBUTE}/wishes", json={"sender_name": "A"})
    assert res.status_code == 400


def test_closed_wall_rejects_before_uploading(client, storage):
    for token in (RAHUL_CONTRIBUTE, "priya-contribute-2026"):
        res = client.post(f"/api/contribute/{token}/wishes",
                          data={"sender_name": "Late", "files": [fake_file("a.jpg", "image/jpeg")]},
                          content_type="multipart/form-data")
        assert res.status_code == 410
    assert storage.uploaded == []


def test_too_many_files(client):
    files = [fake_file(f"{i}.jpg", "image/jpeg") for i in range(6)]
    res = client.post(f"/api/contribute/{ARJUN_CONTRIBUTE}/wishes",
                      data={"sender_name": "A", "files": files}, content_type="multipart/form-data")
    assert res.status_code == 400


def test_file_too_big(client):
    big = fake_file("big.jpg", "image/jpeg", size=10 * 1024 * 1024 + 1)
    res = client.post(f"/api/contribute/{ARJUN_CONTRIBUTE}/wishes",
                      data={"sender_name": "A", "files": [big]}, content_type="multipart/form-data")
    assert res.status_code == 400
    assert "too large" in res.get_json()["error"]


def test_unsupported_file_type(client):
    res = client.post(f"/api/contribute/{ARJUN_CONTRIBUTE}/wishes",
                      data={"sender_name": "A", "files": [fake_file("x.pdf", "application/pdf")]},
                      content_type="multipart/form-data")
    assert res.status_code == 400


def test_database_rejection_deletes_uploaded_files(client, storage):
    # Make storage return a non-https URL: ck_media_url_https rejects it in
    # the database AFTER the upload, so the backend must clean up.
    storage.url_prefix = "http://insecure.example/"
    res = client.post(f"/api/contribute/{ARJUN_CONTRIBUTE}/wishes",
                      data={"sender_name": "A", "message_text": "hi",
                            "files": [fake_file("a.jpg", "image/jpeg")]},
                      content_type="multipart/form-data")
    assert res.status_code == 400
    assert res.get_json()["error"] == "File URL must use https."
    assert storage.deleted == [storage.uploaded[0]["public_id"]]
    # and the wish itself was rolled back
    assert client.get(f"/api/contribute/{ARJUN_CONTRIBUTE}").get_json()["wish_count"] == 4


# ---------------------------------------------------------------- reveal
def test_reveal_too_early(client, mongo):
    res = client.get(f"/api/reveal/{ARJUN_REVEAL}")
    assert res.status_code == 403
    data = res.get_json()
    assert data["code"] == "not_yet_revealed"
    assert "reveal_at" in data
    assert "wishes" not in data
    assert mongo.activity_logs.count_documents({"event": "reveal_too_early"}) == 1


def test_reveal_after_birthday(client):
    res = client.get(f"/api/reveal/{PRIYA_REVEAL}")
    assert res.status_code == 200
    data = res.get_json()
    assert data["birthday_person_name"] == "Priya Sharma"
    assert len(data["wishes"]) == 8
    appa = next(w for w in data["wishes"] if w["sender_name"] == "Appa")
    assert {m["type"] for m in appa["media"]} == {"video", "audio"}
    assert data["settings"]["theme"] == "confetti"
    assert data["stats"]["photos"] == 5


def test_reveal_invalid_token(client):
    assert client.get("/api/reveal/nope").status_code == 404


def test_hidden_wish_not_revealed(ananya, client):
    assert ananya.patch("/api/walls/1/wishes/1", json={"is_hidden": True}).status_code == 200
    data = client.get(f"/api/reveal/{PRIYA_REVEAL}").get_json()
    assert len(data["wishes"]) == 7
    assert all(w["wish_id"] != 1 for w in data["wishes"])


# ---------------------------------------------------------------- reactions
def test_reactions(client, mongo):
    url = f"/api/reveal/{PRIYA_REVEAL}/wishes/2/reactions"
    assert client.post(url, json={"emoji": "❤️"}).status_code == 201
    assert client.post(url, json={"emoji": "❤️"}).status_code == 201     # duplicate is a no-op
    assert client.post(url, json={"emoji": "😂"}).get_json()["reactions"] == ["❤️", "😂"]

    data = client.get(f"/api/reveal/{PRIYA_REVEAL}").get_json()
    assert next(w for w in data["wishes"] if w["wish_id"] == 2)["reactions"] == ["❤️", "😂"]

    assert client.delete(url, json={"emoji": "😂"}).get_json()["reactions"] == ["❤️"]


def test_reaction_rules(client):
    url = f"/api/reveal/{PRIYA_REVEAL}/wishes/2/reactions"
    assert client.post(url, json={"emoji": "💩"}).status_code == 400
    # wish 9 is on Arjun's wall: wrong token for it
    assert client.post(f"/api/reveal/{PRIYA_REVEAL}/wishes/9/reactions",
                       json={"emoji": "❤️"}).status_code == 404
    # Arjun's wall has not been revealed yet
    assert client.post(f"/api/reveal/{ARJUN_REVEAL}/wishes/9/reactions",
                       json={"emoji": "❤️"}).status_code == 404


# ---------------------------------------------------------------- organizer actions
def test_lock_wall(client):
    login(client, "karthik@example.com")
    assert client.patch("/api/walls/2", json={"is_locked": True}).status_code == 200
    assert client.get(f"/api/contribute/{ARJUN_CONTRIBUTE}").get_json()["is_open"] is False
    res = client.post(f"/api/contribute/{ARJUN_CONTRIBUTE}/wishes",
                      json={"sender_name": "A", "message_text": "hi"})
    assert res.status_code == 410


def test_delete_wall_cleans_both_databases(ananya, mongo):
    mongo.wall_settings.insert_one({"wall_id": 1, "theme": "confetti"})
    mongo.reactions.insert_one({"wall_id": 1, "wish_id": 2, "emoji": "❤️"})
    assert ananya.delete("/api/walls/1").status_code == 200
    assert ananya.get("/api/walls/1").status_code == 404
    assert mongo.wall_settings.count_documents({"wall_id": 1}) == 0
    assert mongo.reactions.count_documents({"wall_id": 1}) == 0


def test_settings(ananya):
    res = ananya.put("/api/walls/3/settings", json={
        "theme": "night", "colors": {"background": "#000000"}, "stickers": ["cake"],
        "background_music": {"url": "https://example.com/song.mp3"}})
    assert res.status_code == 200, res.get_json()
    data = ananya.get("/api/walls/3/settings").get_json()
    assert data["theme"] == "night" and data["layout"] == "masonry"
    assert data["background_music"] == {"url": "https://example.com/song.mp3", "autoplay": False}

    ananya.put("/api/walls/3/settings", json={"background_music": None})
    assert "background_music" not in ananya.get("/api/walls/3/settings").get_json()

    assert ananya.put("/api/walls/3/settings", json={"theme": "neon"}).status_code == 400
    assert ananya.put("/api/walls/3/settings", json={"colors": {"background": "red"}}).status_code == 400


# ---------------------------------------------------------------- HTML pages
def test_pages(client):
    assert client.get("/").status_code == 200
    assert client.get(f"/wall/{ARJUN_CONTRIBUTE}").status_code == 200
    assert client.get("/wall/not-a-real-token").status_code == 404


def test_reveal_page_shows_countdown_before_birthday(client):
    early = client.get(f"/reveal/{ARJUN_REVEAL}").get_data(as_text=True)
    assert 'class="clock"' in early
    assert "wall.js" not in early            # wishes page is never sent early
    opened = client.get(f"/reveal/{PRIYA_REVEAL}").get_data(as_text=True)
    assert "wall.js" in opened
    assert client.get("/reveal/not-a-real-token").status_code == 404
