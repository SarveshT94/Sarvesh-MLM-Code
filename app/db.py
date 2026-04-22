import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
from app.config.config import get_config
import logging

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
    """
    Enterprise context manager for DB connections.
    Automatically handles COMMIT on success and ROLLBACK on error.
    """
    global _connection_pool

    if _connection_pool is None:
        init_db_pool()

    conn = _connection_pool.getconn()
    cursor = None
    
    try:
        # RealDictCursor returns rows as dictionaries (e.g., row['email'])
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        yield cursor
        
        # 🔥 THE MISSING PIECE: Force PostgreSQL to save the data permanently
        conn.commit()
        
    except Exception as e:
        # If ANY error happens, cancel the transaction to prevent database corruption
        conn.rollback()
        logger.error(f"Database transaction rolled back: {str(e)}")
        raise
        
    finally:
        if cursor:
            cursor.close()
        _connection_pool.putconn(conn)
