import argparse
import os
import secrets
import sys
from pathlib import Path

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))
ADMIN_EMAIL = "admin@local.test"
MEMBER_EMAIL = "member@local.test"


def create_user(cur, *, role_id, full_name, email, phone, referral_code, sponsor_id, password):
    cur.execute(
        """
        INSERT INTO users (role_id, full_name, email, phone, password_hash, referral_code, sponsor_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (email) DO NOTHING
        RETURNING id
        """,
        (role_id, full_name, email, phone, password, referral_code, sponsor_id),
    )
    user = cur.fetchone()
    if user:
        return user["id"], True

    cur.execute("SELECT id FROM users WHERE email = %s", (email,))
    return cur.fetchone()["id"], False


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed local-only MVP users and a catalogue fixture.")
    parser.add_argument("--admin-password", help="Password for admin@local.test; generated when omitted.")
    parser.add_argument("--member-password", help="Password for member@local.test; generated when omitted.")
    args = parser.parse_args()

    load_dotenv(ROOT_DIR / ".env")
    if os.getenv("ENV", "development") != "development":
        raise ValueError("The MVP seed script only runs when ENV=development.")

    from app.db import get_cursor
    from app.utils.security import hash_password

    admin_password = args.admin_password or secrets.token_urlsafe(18)
    member_password = args.member_password or secrets.token_urlsafe(18)

    with get_cursor() as cur:
        admin_id, admin_created = create_user(
            cur,
            role_id=1,
            full_name="Local Administrator",
            email=ADMIN_EMAIL,
            phone="9000000001",
            referral_code="ADMIN001",
            sponsor_id=None,
            password=hash_password(admin_password),
        )
        member_id, member_created = create_user(
            cur,
            role_id=2,
            full_name="Local Member",
            email=MEMBER_EMAIL,
            phone="9000000002",
            referral_code="MEMBER01",
            sponsor_id=admin_id,
            password=hash_password(member_password),
        )
        cur.execute(
            """
            INSERT INTO kyc_details (user_id, status)
            VALUES (%s, 'approved'), (%s, 'pending')
            ON CONFLICT (user_id) DO NOTHING
            """,
            (admin_id, member_id),
        )
        cur.execute(
            """
            INSERT INTO subscription_plans (name, description, price)
            VALUES ('Local Demo Package', 'Development-only catalogue fixture.', 1.00)
            ON CONFLICT (name) DO NOTHING
            """
        )

    if admin_created:
        print(f"Admin login: {ADMIN_EMAIL} / {admin_password}")
    else:
        print(f"Admin already exists: {ADMIN_EMAIL}")
    if member_created:
        print(f"Member login: {MEMBER_EMAIL} / {member_password}")
    else:
        print(f"Member already exists: {MEMBER_EMAIL}")


if __name__ == "__main__":
    main()
