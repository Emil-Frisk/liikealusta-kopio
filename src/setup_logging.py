import logging
import os
from logging.handlers import RotatingFileHandler

def setup_logging(name, filename):
    log_dir = "logs"
    parent_log_dir = os.path.join(os.path.dirname(__file__), '..', 'logs')
    if not os.path.exists(parent_log_dir):
        os.makedirs(parent_log_dir)
    
    log_format = format='%(asctime)s - %(levelname)s - %(message)s'
    formatter = logging.Formatter(log_format)

    # Set up file handler
    log_file = os.path.join(parent_log_dir, filename)

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=1024*1024,
        backupCount=1,
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)

    #setup console
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    # config root logger
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger 