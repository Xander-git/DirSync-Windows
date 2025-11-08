"""Utility functions for long-path handling and logging setup."""

import os
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def to_long_path(path: str) -> str:
    """
    Convert a Windows path to long-path format with \\?\ prefix.
    
    Args:
        path: The path to convert
        
    Returns:
        Path with \\?\ prefix if it's an absolute Windows path, otherwise unchanged
    """
    if not path:
        return path
    
    # Check if we're on Windows and path is absolute
    if os.name == 'nt' and os.path.isabs(path):
        # Avoid double-prefixing
        if not path.startswith('\\\\?\\'):
            # Convert forward slashes to backslashes
            path = path.replace('/', '\\')
            # Add long-path prefix
            return f'\\\\?\\{path}'
    
    return path


def setup_logging(log_level: int = logging.INFO) -> logging.Logger:
    """
    Set up rotating file logger at %LOCALAPPDATA%\\DirSync\\logs\\app.log.
    
    Args:
        log_level: Logging level (default: INFO)
        
    Returns:
        Configured logger instance
    """
    # Determine log directory
    if os.name == 'nt':
        # Windows: Use LOCALAPPDATA
        local_appdata = os.environ.get('LOCALAPPDATA', os.path.expanduser('~'))
        log_dir = Path(local_appdata) / 'DirSync' / 'logs'
    else:
        # Non-Windows fallback for development
        log_dir = Path.home() / '.dirsync' / 'logs'
    
    # Create log directory if it doesn't exist
    log_dir.mkdir(parents=True, exist_ok=True)
    
    log_file = log_dir / 'app.log'
    
    # Create logger
    logger = logging.getLogger('DirSync-Windows')
    logger.setLevel(log_level)
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # Create rotating file handler (10 MB max, 5 backups)
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(log_level)
    
    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] [%(threadName)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # Add handlers to logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    logger.info(f'Logging initialized. Log file: {log_file}')
    
    return logger


def get_log_tail(num_lines: int = 10) -> list[str]:
    """
    Get the last N lines from the log file.
    
    Args:
        num_lines: Number of lines to retrieve from the end
        
    Returns:
        List of last N log lines
    """
    if os.name == 'nt':
        local_appdata = os.environ.get('LOCALAPPDATA', os.path.expanduser('~'))
        log_file = Path(local_appdata) / 'DirSync' / 'logs' / 'app.log'
    else:
        log_file = Path.home() / '.dirsync' / 'logs' / 'app.log'
    
    if not log_file.exists():
        return []
    
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            return [line.rstrip() for line in lines[-num_lines:]]
    except Exception:
        return []

