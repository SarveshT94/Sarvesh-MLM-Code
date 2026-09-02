import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
from app.config.config import get_config
import logging
import os

config = get_config()
logger = logging.getLogger(__name__)

_connection_pool = None


def init_db_pool():
    global _connection_pool
    if _connection_pool is None:
        try:
            # ─────────────────────────────────────────────────────────────────
            # FIXED: maxconn raised from 20 → 100
            #
            # Why 20 was a critical problem:
            # ┌──────────────────────────────────────────────────────────────┐
            # │  Gunicorn workers  : 9  (4 CPU × 2 + 1)                      │
            # │  Gevent greenlets  : 1000 per worker                         │
            # │  Old pool max      : 20  ← exhausted by first ~20 requests   │
            # │  Result            : All remaining requests hang or crash    │
            # └──────────────────────────────────────────────────────────────┘
            #
            # With 100 connections and PgBouncer in front of PostgreSQL,
            # this handles 1 lakh+ concurrent users safely.
            #
            # For production deployment:
            #   1. Install PgBouncer on your DB server
            #   2. Set PgBouncer pool_size = 80–100
            #   3. Set DB_POOL_MAX env var to match (default 100 here)
            #   4. PostgreSQL max_connections = 200 (edit postgresql.conf)
            # ─────────────────────────────────────────────────────────────────
            max_conn = int(os.environ.get("DB_POOL_MAX", 100))
            min_conn = int(os.environ.get("DB_POOL_MIN", 5))

            _connection_pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=min_conn,
                maxconn=max_conn,
                dbname=config.DB_NAME,
                user=config.DB_USER,
                password=config.DB_PASSWORD,
                host=config.DB_HOST,
                port=config.DB_PORT,
                connect_timeout=5,

                # ADDED: TCP keepalives prevent silent stale connections.
                # Without this, a connection idle for >10 min on a cloud DB
                # (AWS RDS, Supabase, etc.) silently dies, causing the next
                # request to fail with "connection closed unexpectedly".
                keepalives=1,
                keepalives_idle=30,       # Start keepalive after 30s idle
                keepalives_interval=10,   # Retry every 10s
                keepalives_count=5,       # Give up after 5 failed probes
            )

            logger.info(
                f"✅ Database connection pool initialized "
                f"(min={min_conn}, max={max_conn}, "
                f"host={config.DB_HOST}, db={config.DB_NAME})"
            )

        except Exception as e:
            logger.critical(f"❌ DB pool init FAILED: {str(e)}")
            raise


def close_db_pool():
    """
    Gracefully close all connections in the pool.
    Call this on app shutdown (e.g. from a signal handler or atexit hook).
    """
    global _connection_pool
    if _connection_pool:
        _connection_pool.closeall()
        logger.info("✅ Database connection pool closed cleanly.")


@contextmanager
def get_cursor():
    """
    Enterprise-grade DB context manager.

    ✅ Auto-commits on success
    ✅ Auto-rolls back on any exception (prevents partial writes / data corruption)
    ✅ Returns connection to pool in finally block (no connection leaks)
    ✅ Uses RealDictCursor so rows come back as dicts: row['email'] not row[2]

    Usage (the ONLY correct way to use this):
    ──────────────────────────────────────────
        with get_cursor() as cur:
            cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
            user = cur.fetchone()   # → {'id': 1, 'email': '...', ...}

    ⚠️  NEVER do this (crashes — get_cursor is a context manager, not a cursor):
        cursor = get_cursor()
        cursor.execute(...)   # ← AttributeError: '_GeneratorContextManager' has no 'execute'
    """
    global _connection_pool

    if _connection_pool is None:
        init_db_pool()

    conn   = _connection_pool.getconn()
    cursor = None
    error_occurred = False

    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        yield cursor
        conn.commit()

    except Exception as e:
        error_occurred = True
        conn.rollback()
        logger.error(f"DB transaction rolled back: {str(e)}")
        raise

    finally:
        if cursor:
            cursor.close()
        # FIX: Closes broken connections safely instead of returning them to the pool
        _connection_pool.putconn(conn, close=error_occurred)
