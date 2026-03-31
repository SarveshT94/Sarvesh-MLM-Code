import random
import string
from app.db import get_cursor


def generate_referral_code(length=8):
    """
    Generate unique referral code
    """

    while True:

        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

        with get_cursor() as cur:

            cur.execute(
                "SELECT id FROM users WHERE referral_code = %s",
                (code,)
            )

            exists = cur.fetchone()

        if not exists:
            return code


def validate_referral_code(referral_code):
    """
    Validate referral code and return sponsor
    """

    with get_cursor() as cur:

        cur.execute(
            "SELECT id FROM users WHERE referral_code = %s",
            (referral_code,)
        )

        sponsor = cur.fetchone()

    return sponsor


def get_sponsor_id(referral_code):
    """
    Get sponsor user ID
    """

    sponsor = validate_referral_code(referral_code)

    if sponsor:
        return sponsor["id"]

    return None
