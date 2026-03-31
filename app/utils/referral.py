import random
import string
from app.db import get_db_connection


def generate_referral_code(length=7):
    """
    Generate random referral code
    Example: 7F3A92K
    """

    characters = string.ascii_uppercase + string.digits
    return ''.join(random.choice(characters) for _ in range(length))


def generate_unique_referral_code():
    """
    Generate referral code that does not exist in database
    """

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        while True:

            code = generate_referral_code()

            cur.execute(
                "SELECT id FROM users WHERE referral_code=%s",
                (code,)
            )

            exists = cur.fetchone()

            if not exists:
                return code

    finally:
        cur.close()
        conn.close()
