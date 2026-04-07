import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
from app.config import Config
import logging

logger = logging.getLogger(__name__)

# Enterprise Connection Pool (Global Singleton)
_connection_pool = None


def init_db_pool():
    """
    Initializes a reusable connection pool.
    """
    global _connection_pool

    if _connection_pool is None:
        try:
            _connection_pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=1,
                maxconn=20,
                dbname=Config.DB_NAME,
                user=Config.DB_USER,
                password=Config.DB_PASSWORD,
                host=Config.DB_HOST,
                port=Config.DB_PORT,
                connect_timeout=5
            )
            logger.info("Database connection pool initialized.")

        except Exception as e:
            logger.error(f"Database pool initialization error: {str(e)}")
            raise


def close_db_pool():
    """
    Gracefully closes all connections (use during app shutdown).
    """
    global _connection_pool

    if _connection_pool:
        _connection_pool.closeall()
        logger.info("Database connection pool closed.")


@contextmanager
def get_cursor():
    """
    Enterprise-safe DB cursor manager:
    - Uses connection pooling
    - Returns dict rows
    - Auto commit / rollback
    """
    global _connection_pool

    if _connection_pool is None:
        init_db_pool()

    conn = None
    cursor = None

    try:
        # Borrow connection
        conn = _connection_pool.getconn()

        # Create cursor
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        yield cursor

        # Commit after success
        conn.commit()

    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Database transaction error: {str(e)}")
        raise

    finally:
        # Cleanup safely
        if cursor:
            cursor.close()
        if conn:
            _connection_pool.putconn(conn)
