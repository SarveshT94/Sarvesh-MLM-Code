import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
from app.config import Config

# Enterprise Connection Pool (Global Singleton)
_connection_pool = None

def init_db_pool():
    """
    Creates a pool of permanent, reusable database connections.
    Prevents server crashing under heavy user traffic.
    """
    global _connection_pool
    if _connection_pool is None:
        try:
            _connection_pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=1,
                maxconn=20,  # Allows thousands of users to comfortably share 20 active connections
                dbname=Config.DB_NAME,
                user=Config.DB_USER,
                password=Config.DB_PASSWORD,
                host=Config.DB_HOST,
                port=Config.DB_PORT,
                connect_timeout=5
            )
            print("✅ Enterprise Database Pool Initialized.")
        except Exception as e:
            print("❌ Database Pool Initialization Error:", str(e))
            raise

@contextmanager
def get_cursor():
    """
    Production-safe cursor manager using Connection Pooling.
    - Borrows a connection from the pool.
    - Uses RealDictCursor (returns dict instead of tuple).
    - Auto-commits on success, Auto-rollbacks on error.
    - Safely returns the connection to the pool.
    """
    global _connection_pool
    
    # Ensure the pool is running
    if _connection_pool is None:
        init_db_pool()

    # Borrow a connection from the pool
    conn = _connection_pool.getconn()
    
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        yield cursor
        
        # Commit only after successful execution
        conn.commit()

    except Exception as e:
        # If anything fails, rollback to protect data integrity
        conn.rollback()
        print("❌ Database Transaction Error:", str(e))
        raise

    finally:
        # Always clean up and return the connection to the pool for the next user
        cursor.close()
        _connection_pool.putconn(conn)
