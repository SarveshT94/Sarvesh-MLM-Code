def distribute_commission(cur, from_user_id, purchase_amount):
    """
    Distribute unilevel commission based on commission plan.
    """

    try:

        # ---------------------------
        # Fetch Commission Plan
        # ---------------------------
        cur.execute("""
            SELECT level, percentage
            FROM commission_plan
            ORDER BY level ASC
        """)

        plan = cur.fetchall()

        current_user = from_user_id

        for row in plan:

            level = row["level"]
            percentage = row["percentage"]

            # ---------------------------
            # Find Sponsor
            # ---------------------------
            cur.execute("""
                SELECT sponsor_id
                FROM users
                WHERE id = %s
            """, (current_user,))

            sponsor = cur.fetchone()

            if not sponsor or sponsor["sponsor_id"] is None:
                break

            sponsor_id = sponsor["sponsor_id"]

            # ---------------------------
            # Calculate Commission
            # ---------------------------
            commission_amount = (purchase_amount * percentage) / 100

            if commission_amount <= 0:
                current_user = sponsor_id
                continue

            # ---------------------------
            # Duplicate Commission Check
            # ---------------------------
            cur.execute("""
                SELECT id
                FROM commissions
                WHERE earner_id = %s
                AND from_user_id = %s
                AND level = %s
                AND commission_type = %s
                LIMIT 1
            """, (
                sponsor_id,
                from_user_id,
                level,
                "unilevel"
            ))

            exists = cur.fetchone()

            if exists:
                current_user = sponsor_id
                continue

            # ---------------------------
            # Insert Commission Record
            # ---------------------------
            cur.execute("""
                INSERT INTO commissions
                (earner_id, from_user_id, level, amount, commission_type, created_at)
                VALUES (%s,%s,%s,%s,%s,NOW())
            """, (
                sponsor_id,
                from_user_id,
                level,
                commission_amount,
                "unilevel"
            ))

            # ---------------------------
            # Wallet Credit
            # ---------------------------
            reference_id = f"lvl_{level}_from_{from_user_id}"

            cur.execute("""
                INSERT INTO wallet_ledger
                (user_id, transaction_type, amount, reference_id, description, created_at)
                VALUES (%s,%s,%s,%s,%s,NOW())
            """, (
                sponsor_id,
                "commission_credit",
                commission_amount,
                reference_id,
                f"Level {level} commission from user {from_user_id}"
            ))

            # ---------------------------
            # Move to next level
            # ---------------------------
            current_user = sponsor_id

    except Exception as e:
        raise e


# ✅ Wrapper function (UPDATED)
def process_commission(cur, from_user_id, purchase_amount):
    """
    Wrapper to maintain compatibility with old imports
    """
    return distribute_commission(cur, from_user_id, purchase_amount)
