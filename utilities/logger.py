import os
import logging
from logging.handlers import RotatingFileHandler

def setup_logger(name: str, log_file: str, level: int = logging.INFO) -> logging.Logger:
    """
    Create and return a logger that writes to `log_file`.
    - Ensures the directory exists.
    - Uses a rotating handler to avoid giant files.
    """
    # 1) Make sure the directory for the log file exists
    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    # 2) Get (or create) the logger by name
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Avoid adding multiple handlers if setup_logger is called twice
    if not logger.handlers:
        # 3) Create a rotating file handler (1 MB per file, keep 3 backups)
        handler = RotatingFileHandler(log_file, maxBytes=1_000_000, backupCount=3, encoding="utf-8")

        # 4) Format: timestamp level loggername message
        formatter = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
        handler.setFormatter(formatter)

        logger.addHandler(handler)

    return logger
