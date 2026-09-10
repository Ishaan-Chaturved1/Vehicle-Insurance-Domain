import logging
import os
from logging.handlers import RotatingFileHandler
from datetime import datetime
from pathlib import Path

# Constants for log configuration
LOG_DIR = 'logs'
LOG_FILE = f"{datetime.now().strftime('%m_%d_%Y_%H_%M_%S')}.log"
MAX_LOG_SIZE = 5 * 1024 * 1024  # 5 MB
BACKUP_COUNT = 3  # Number of backup log files to keep

# Construct log file path
log_dir_path = str(Path(__file__).resolve().parents[2] / LOG_DIR)
os.makedirs(log_dir_path, exist_ok=True)
log_file_path = os.path.join(log_dir_path, LOG_FILE)

def configure_logger():
    """
    Configures logging with a rotating file handler and a console handler.
    """
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    # Imports happen in worker processes and test runners as well; do not add
    # duplicate handlers every time this module is imported.
    if logger.handlers:
        return
    
    # Define formatter
    formatter = logging.Formatter("[ %(asctime)s ] %(name)s - %(levelname)s - %(message)s")

    # File handler with rotation
    file_handler = RotatingFileHandler(log_file_path, maxBytes=MAX_LOG_SIZE, backupCount=BACKUP_COUNT)
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)
    
    # Add handlers to the logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

# Configure the logger
configure_logger()
