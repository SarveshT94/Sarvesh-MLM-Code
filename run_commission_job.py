import logging
from app import create_app
from app.jobs.commission_processor import process_daily_commissions

logging.basicConfig(
    filename="commission_job.log",
    level=logging.INFO
)

app = create_app()

with app.app_context():

    total = process_daily_commissions()

    logging.info(f"Commission job completed. Users processed: {total}")

    print("Commission job completed")
