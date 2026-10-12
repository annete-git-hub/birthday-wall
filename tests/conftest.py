"""
Test setup.

* PostgreSQL: a REAL database given by TEST_DATABASE_URL. Before every test
  all tables are dropped and rebuilt from database/postgres/01..07, so each
  test starts from the same seed data. Never point this at your real DB.
* MongoDB: mongomock (in-memory), so no Mongo server is needed.
* Cloudinary: a fake storage object that records uploads and deletes.

Run:  pytest -v
"""

import os
from pathlib import Path

import mongomock
import psycopg2
import pytest
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
SQL_FILES = sorted((ROOT / "database" / "postgres").glob("0[1-7]_*.sql"))
TEST_DB = os.getenv("TEST_DATABASE_URL")

if not TEST_DB:
    pytest.skip("Set TEST_DATABASE_URL to run the API tests.", allow_module_level=True)


class FakeStorage:
    def __init__(self):
        self.uploaded, self.deleted = [], []
        self.url_prefix = "https://res.cloudinary.com/test/"

    def upload(self, f, media_type, folder):
        n = len(self.uploaded) + 1
        info = {
            "url": f"{self.url_prefix}{folder}/file{n}",
            "public_id": f"{folder}/file{n}",
            "resource_type": "image" if media_type == "image" else "video",
            "duration": None if media_type == "image" else 12.4,
        }
        self.uploaded.append(info)
        return info

    def delete(self, public_id, resource_type):
        self.deleted.append(public_id)


def reset_postgres():
    conn = psycopg2.connect(TEST_DB)
    conn.autocommit = True
    with conn.cursor() as cur:
        for path in SQL_FILES:
            cur.execute(path.read_text())
    conn.close()


def make_mongo():
    db = mongomock.MongoClient()["birthday_wall_test"]
    db.wall_settings.create_index("wall_id", unique=True)
    db.reactions.create_index([("wish_id", 1), ("emoji", 1)], unique=True)
    return db


@pytest.fixture(scope="session")
def app():
    from backend.app import create_app
    return create_app({"TESTING": True, "DATABASE_URL": TEST_DB,
                       "MONGO_URI": "", "CLOUDINARY_URL": "", "SECRET_KEY": "test"})


@pytest.fixture(autouse=True)
def fresh_state(app):
    from backend.db.mongo import set_mongo
    from backend.utils.storage import set_storage

    reset_postgres()
    mongo = make_mongo()
    storage = FakeStorage()
    set_mongo(mongo)
    set_storage(storage)
    yield {"mongo": mongo, "storage": storage}


@pytest.fixture
def mongo(fresh_state):
    return fresh_state["mongo"]


@pytest.fixture
def storage(fresh_state):
    return fresh_state["storage"]


@pytest.fixture
def client(app):
    return app.test_client()


def login(client, email="ananya@example.com", password="password123"):
    res = client.post("/api/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.get_json()
    return res.get_json()


@pytest.fixture
def ananya(client):
    """Logged in as Ananya, who owns wall 1 (Priya) and wall 3 (Meera)."""
    login(client)
    return client
