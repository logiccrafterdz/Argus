import logging
import sys

LOG_FORMAT = '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s'
DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

_initialized = False

def setup_logger(name='argus', level=logging.INFO, log_file=None):
    global _initialized
    logger = logging.getLogger(name)
    
    if _initialized:
        return logger
    
    logger.setLevel(level)
    logger.handlers.clear()
    
    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)
    
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    logger.addHandler(console)
    
    if log_file:
        fh = logging.FileHandler(log_file)
        fh.setFormatter(formatter)
        logger.addHandler(fh)
    
    _initialized = True
    return logger

def get_logger(name='argus'):
    return logging.getLogger(name)
