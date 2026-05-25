import time
import logging

logger = logging.getLogger(__name__)

def send_welcome_email_task(user_email, full_name):
    """
    Simulates sending an email or SMS in the background.
    Because this is in a task queue, the user doesn't have to wait for this to finish!
    """
    logger.info(f"[BACKGROUND TASK] Preparing to send email to {user_email}...")
    
    # Simulate the 3-second delay of talking to an SMTP server
    time.sleep(3) 
    
    # In the future, your actual email-sending code goes here
    logger.info(f"[BACKGROUND TASK] ✅ Welcome email successfully sent to {full_name}!")

def process_large_payout_report(admin_id):
    """
    Example of a heavy admin task that would normally crash the browser.
    """
    logger.info(f"[BACKGROUND TASK] Admin {admin_id} requested a massive PDF report.")
    time.sleep(5)
    logger.info(f"[BACKGROUND TASK] ✅ Report generated and saved to server!")
