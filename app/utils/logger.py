import logging
import sys
from logging.handlers import RotatingFileHandler
import os


def setup_logging():
    """
    Centralized logging setup:
    - Console logs
    - File logs (with rotation)
    """

    log_level = logging.INFO
    log_format = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"

    # Create logger
    logger = logging.getLogger()
    logger.setLevel(log_level)

    # جلوگیری duplicate handlers
    if logger.handlers:
        return

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter(log_format))
    logger.addHandler(console_handler)

    # File handler (important for production)
    os.makedirs("logs", exist_ok=True)

    file_handler = RotatingFileHandler(
        "logs/app.log",
        maxBytes=5 * 1024 * 1024,  # 5MB
        backupCount=3
    )
    file_handler.setFormatter(logging.Formatter(log_format))
    logger.addHandler(file_handler)
