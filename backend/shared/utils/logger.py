"""Multi-stream structured logging system for Sea Sentinel."""
import os
import sys
import logging
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
LOGS_DIR = PROJECT_ROOT / "logs"

def get_logger(module_name: str, log_category: str = "backend") -> logging.Logger:
    """Returns a configured logger that writes to logs/<log_category>/<name>.log and stdout."""
    target_dir = LOGS_DIR / log_category
    target_dir.mkdir(parents=True, exist_ok=True)
    
    logger = logging.getLogger(f"SeaSentinel.{log_category}.{module_name}")
    if logger.hasHandlers():
        return logger
        
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s:%(lineno)d] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # File handler
    log_file = target_dir / f"{log_category}.log"
    fh = logging.FileHandler(str(log_file), mode='a', encoding='utf-8')
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    
    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    
    return logger
