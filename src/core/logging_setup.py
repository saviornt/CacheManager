"""Logging configuration for CacheManager."""

import os
import logging
import logging.handlers
from datetime import datetime

from ..cache_config import CacheConfig, LogLevel

class CorrelationIdFilter(logging.Filter):
    """Add correlation_id to all log records.
    
    This allows tracking operations across multiple function calls.
    """
    def filter(self, record: logging.LogRecord) -> bool:
        """Filter log records and add correlation_id if not present.
        
        Args:
            record: The log record to filter
            
        Returns:
            bool: Always True to allow the record to be emitted
        """
        if not hasattr(record, 'correlation_id'):
            record.correlation_id = 'N/A'
        return True

def setup_logging(config: CacheConfig) -> logging.Logger:
    """Set up logging configuration based on CacheConfig.
    
    Args:
        config: The cache configuration containing logging settings
        
    Returns:
        logging.Logger: Configured logger instance
    """
    # Map LogLevel enum to logging module levels
    log_level_map = {
        LogLevel.DEBUG: logging.DEBUG,
        LogLevel.INFO: logging.INFO,
        LogLevel.WARNING: logging.WARNING,
        LogLevel.ERROR: logging.ERROR,
        LogLevel.CRITICAL: logging.CRITICAL
    }
    
    log_level = log_level_map.get(config.log_level, logging.INFO)
    logger = logging.getLogger(__name__.split('.')[0])  # Get the top-level package name
    
    # Remove any existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    logger.setLevel(log_level)
    
    # Create formatter with correlation ID
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(name)s - [%(correlation_id)s] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Add correlation ID filter
    logger.addFilter(CorrelationIdFilter())
    
    # Add console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(log_level)
    logger.addHandler(console_handler)
    
    # Add file handler if log_to_file is enabled
    if config.log_to_file:
        # Create logs directory if it doesn't exist
        os.makedirs(config.log_dir, exist_ok=True)
        
        # Create log filename with current datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filename = f"{logger.name}_{timestamp}.log"
        log_path = os.path.join(config.log_dir, log_filename)
        
        # Set up rotating file handler with size limits
        file_handler = logging.handlers.RotatingFileHandler(
            log_path,
            maxBytes=config.log_max_size,
            backupCount=config.log_backup_count
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(log_level)
        logger.addHandler(file_handler)
    
    return logger 