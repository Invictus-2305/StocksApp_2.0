"""
Centralized Logging Configuration for the Trading Platform.

Sets up a rotating file handler and console handler with a consistent format.
All modules should use: logger = logging.getLogger(__name__)
"""

import logging
import os
from logging.handlers import RotatingFileHandler
from datetime import datetime

LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
LOG_FILE = os.path.join(LOG_DIR, "trading_app.log")

# Max 10 MB per file, keep 5 backup files
MAX_BYTES = 10 * 1024 * 1024
BACKUP_COUNT = 5

LOG_FORMAT = "[%(asctime)s] [%(levelname)-8s] [%(name)s]: %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_initialized = False

def setup_logging(level=logging.INFO):
    """
    Call once at app startup (in main.py lifespan) to configure 
    the root logger with rotating file + console output.
    """
    global _initialized
    if _initialized:
        return
    _initialized = True

    os.makedirs(LOG_DIR, exist_ok=True)

    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    # Rotating file handler
    file_handler = RotatingFileHandler(
        LOG_FILE, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT, encoding="utf-8"
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)

    # Configure root logger
    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(file_handler)
    root.addHandler(console_handler)

    # Quieten noisy third-party loggers
    logging.getLogger("telethon").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    logging.getLogger(__name__).info(
        f"Logging initialized — file: {LOG_FILE}, level: {logging.getLevelName(level)}"
    )
