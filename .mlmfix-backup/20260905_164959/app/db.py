"""
app/db.py  —  REWRITE (drop-in replacement)

Connection-pool + transaction management.

Scale notes for 100,000 concurrent users
----------------------------------------
* Use a SMALL per-process pool (DB_POOL_MIN/MAX) and put **PgBouncer** in
  TRANSACTION pooling mode in front of PostgreSQL. 10 gunicorn workers x
  gevent x a 10-20 pool is plenty; PgBouncer multiplexes them onto a few
  dozen real Postgres connections. A per-process pool of 100 against a
  single Postgres = up to 1,000 server connections = guaranteed meltdown.
* Every transaction gets a `statement_timeout` so one runaway recursive
  query can never pin a DB connection for minutes.
* get_cursor() commits on success, rolls back on error, and never leaks a
  connection back into the pool dirty.
"""
import os
import logging
import contextlib

import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor

from app.config.config import get_config

config = get_config()
logger = logging.getLogger(__name__)

_connection_pool = None


def init_db_pool():
    global _connection_pool
    if _connection_pool is not None:
        return

    max_conn = int(os.environ.get("DB_POOL_MAX", config.DB_POOL_MAX))
    min_conn = int(os.environ.get("DB_POOL_MIN", config.DB_POOL_MIN))
    timeout_ms = int(os.environ.get("DB_STATEMENT_TIMEOUT_MS",
                                    config.DB_STATEMENT_TIMEOUT_MS))

    _connection_pool = psycopg2.pool.ThreadedConnectionPool(
        minconn=min_conn,
        maxconn=max_conn,
        dbname=config.DB_NAME,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        host=config.DB_HOST,
        port=config.DB_PORT,
        connect_timeout=5,
        options=f"-c statement_timeout={timeout_ms}",
        keepalives=1,
        keepalives_idle=30,
        keepalives_interval=10,
        keepalives_count=5,
    )
    logger.info(
        "DB pool ready (min=%s max=%s host=%s db=%s)",
        min_conn, max_conn, config.DB_HOST, config.DB_NAME,
    )


def close_db_pool():
    global _connection_pool
    if _connection_pool:
        _connection_pool.closeall()
        _connection_pool = None
        logger.info("DB pool closed.")


@contextlib.contextmanager
def get_cursor():
    """
    Yield a RealDictCursor inside a transaction.

        with get_cursor() as cur:
            cur.execute("SELECT ...")
            row = cur.fetchone()

    Commits automatically on success, rolls back on exception, and always
    returns the connection to the pool.
    """
    global _connection_pool
    if _connection_pool is None:
        init_db_pool()

    conn = _connection_pool.getconn()
    cursor = None
    failed = False
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        yield cursor
        conn.commit()
    except Exception:
        failed = True
        conn.rollback()
        raise
    finally:
        if cursor is not None:
            cursor.close()
        # A connection that errored may be in a bad state - close it instead
        # of recycling it.
        _connection_pool.putconn(conn, close=failed)


# Backwards-compatible alias used by some modules.
transaction = get_cursor
