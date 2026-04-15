import random
import string
from app.db import get_cursor


def generate_referral_code(length=7):
    """
    Generate random referral code
    Example: 7F3A92K
    """
    characters = string.ascii_uppercase + string.digits
    return ''.join(random.choice(characters) for _ in range(length))


def generate_unique_referral_code(cur=None):
    """
    Generate referral code that does not exist in database.
    Supports:
    - standalone usage
    - transactional usage (with cur)
    """

    def _generate(cur):
        while True:
            code = generate_referral_code()

            cur.execute(
                "SELECT id FROM users WHERE referral_code = %s",
                (code,)
            )

            exists = cur.fetchone()

            if not exists:
                return code

    # ✅ If cursor provided → use same transaction
    if cur:
        return _generate(cur)

    # ✅ Else → create new cursor
    with get_cursor() as new_cur:
        return _generate(new_cur)
