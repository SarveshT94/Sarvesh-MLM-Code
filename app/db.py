import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
from app.config.config import get_config
import logging
import time

config = get_config()
logger = logging.getLogger(__name__)

_connection_pool = None


def init_db_pool():
    global _connection_pool

    if _connection_pool is None:
        try:
            _connection_pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=2,
                maxconn=20,
                dbname=config.DB_NAME,
                user=config.DB_USER,
                password=config.DB_PASSWORD,
                host=config.DB_HOST,
                port=config.DB_PORT,
                connect_timeout=5
            )
            logger.info("✅ Database connection pool initialized")

        except Exception as e:
            logger.critical(f"❌ DB pool init failed: {str(e)}")
            raise


def close_db_pool():
    global _connection_pool

    if _connection_pool:
        _connection_pool.closeall()
        logger.info("✅ Database connection pool closed")


@contextmanager
def get_cursor():
    global _connection_pool

    if _connection_pool is None:
        init_db_pool()

    conn = None
    cursor = None
    start_time = time.time()

    try:
        conn = _connection_pool.getconn()

        # Health check (important)
        if conn.closed:
            logger.warning("⚠️ Reconnecting closed DB connection")
            conn = _connection_pool.getconn()

        cursor = conn.cursor(cursor_factory=RealDictCursor)

        yield cursor

        conn.commit()

    except Exception as e:
        if conn:
            conn.rollback()

        logger.error(f"❌ DB transaction failed: {str(e)}")
        raise

    finally:
        duration = round((time.time() - start_time) * 1000, 2)

        if duration > 500:
            logger.warning(f"⚠️ Slow query detected: {duration} ms")

        if cursor:
            cursor.close()

        if conn:
            _connection_pool.putconn(conn)
