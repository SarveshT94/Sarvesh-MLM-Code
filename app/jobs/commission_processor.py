from app.db import get_cursor
import logging

logger = logging.getLogger(__name__)


def process_daily_commissions():
    """
    DAILY COMMISSION JOB

    TEMPORARILY DISABLED.

    Reason:
    Old implementation was using:

        distribute_commission(user_id, 100)

    which hardcoded package_id=100 for every active user.

    This could generate:
    - duplicate commissions
    - fake payouts
    - wallet inflation
    - financial inconsistencies

    The job will remain disabled until:
    - cron logic is audited
    - recurring income rules are confirmed
    - package mapping is validated
    """

    logger.warning(
        "process_daily_commissions() is temporarily disabled for safety."
    )

    return {
        "status": "disabled",
        "processed": 0
    }
