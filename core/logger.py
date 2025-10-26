# core/logger.py
import logging
from pathlib import Path
from .paths import log_file_path

def setup_logger() -> logging.Logger:
    """Setup application logger with file and console handlers."""
    logger = logging.getLogger("PDFReporter")
    logger.setLevel(logging.INFO)
    
    # Avoid duplicate handlers
    if logger.handlers:
        return logger
    
    # File handler
    try:
        fh = logging.FileHandler(log_file_path(), encoding='utf-8')
        fh.setLevel(logging.INFO)
        fh.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
        logger.addHandler(fh)
    except Exception as e:
        print(f"Could not setup file logging: {e}")
    
    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.WARNING)
    ch.setFormatter(logging.Formatter('%(levelname)s - %(message)s'))
    logger.addHandler(ch)
    
    return logger

# Global logger instance
logger = setup_logger()