import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
from app.config import Config


def get_db_connection():
    """
    Create a new PostgreSQL database connection (Production Safe)
    """
    try:
        conn = psycopg2.connect(
            dbname=Config.DB_NAME,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            host=Config.DB_HOST,
            port=Config.DB_PORT,
            connect_timeout=5
        )

        return conn

    except Exception as e:
        print("❌ Database Connection Error:", str(e))
        raise


@contextmanager
def get_cursor():
    """
    Production-safe cursor manager
    - Uses RealDictCursor (returns dict instead of tuple)
    - Auto commit on success
    - Auto rollback on error
    """
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)  # ✅ FIX

    try:
        yield cursor

        conn.commit()  # ✅ commit only after success

    except Exception as e:
        conn.rollback()
        print("❌ Database Transaction Error:", str(e))
        raise

    finally:
        cursor.close()
        conn.close()
