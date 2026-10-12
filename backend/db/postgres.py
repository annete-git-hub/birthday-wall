"""
db/postgres.py
PostgreSQL connection pool and a helper for running queries safely.

Why a pool? Opening a new database connection takes tens of milliseconds.
A pool opens a few connections once and lends them out per request.

Usage in a route:
    with get_cursor() as cur:
        cur.execute("SELECT * FROM walls WHERE wall_id = %s", (wall_id,))
        row = cur.fetchone()          # a dict, e.g. row["birthday_person_name"]

Every `with get_cursor()` block is ONE transaction:
  * block finishes normally -> COMMIT
  * any exception           -> ROLLBACK, then the exception is re-raised
"""

from contextlib import contextmanager

from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool

_pool = None


def init_pool(app):
    global _pool
    if _pool is None:
        _pool = ThreadedConnectionPool(
            app.config["DB_POOL_MIN"],
            app.config["DB_POOL_MAX"],
            dsn=app.config["DATABASE_URL"],
        )


def close_pool():
    global _pool
    if _pool is not None:
        _pool.closeall()
        _pool = None


@contextmanager
def get_cursor():
    if _pool is None:
        raise RuntimeError("Database pool not initialised. Call init_pool(app) first.")

    conn = _pool.getconn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            yield cur
        conn.commit()          # deferred trigger T4 runs here
    except Exception:
        conn.rollback()
        raise
    finally:
        _pool.putconn(conn)
