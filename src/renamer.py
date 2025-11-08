"""File renaming with metadata preservation and retry logic."""

import os
import shutil
import time
import logging
from pathlib import Path
from typing import Optional

from .utils import to_long_path
from .file_detector import should_rename


logger = logging.getLogger('DirSync-Windows')


def rename_with_metadata(
    old_path: str | Path,
    new_path: str | Path,
    max_retries: int = 3,
    retry_delay: float = 0.5
) -> bool:
    """
    Atomically rename a file while preserving all metadata.
    
    Uses os.replace() for atomic rename and shutil.copystat() to preserve:
    - Timestamps (creation, modification, access)
    - File attributes
    
    Args:
        old_path: Current file path
        new_path: New file path
        max_retries: Number of retry attempts if file is locked
        retry_delay: Delay between retries in seconds
        
    Returns:
        True if rename successful, False otherwise
    """
    old_path = Path(old_path)
    new_path = Path(new_path)
    
    # Apply long-path prefix for Windows
    old_long = to_long_path(str(old_path.absolute()))
    new_long = to_long_path(str(new_path.absolute()))
    
    for attempt in range(max_retries):
        try:
            # Save metadata before rename
            stat_info = os.stat(old_long)
            
            # Atomic rename
            os.replace(old_long, new_long)
            
            # Restore metadata
            try:
                shutil.copystat(old_long if os.path.exists(old_long) else str(old_path), 
                               new_long, 
                               follow_symlinks=False)
            except FileNotFoundError:
                # Original file was renamed, use new path
                # Set times manually using saved stat
                os.utime(new_long, (stat_info.st_atime, stat_info.st_mtime))
            
            logger.info(f'Renamed: {old_path.name} -> {new_path.name}')
            return True
            
        except PermissionError as e:
            if attempt < max_retries - 1:
                logger.warning(
                    f'File locked, retry {attempt + 1}/{max_retries}: {old_path.name}'
                )
                time.sleep(retry_delay * (2 ** attempt))  # Exponential backoff
            else:
                logger.error(f'Failed to rename {old_path.name} after {max_retries} attempts: {e}')
                return False
                
        except Exception as e:
            logger.error(f'Error renaming {old_path.name}: {e}')
            return False
    
    return False


def get_unique_path(target_path: str | Path) -> Path:
    """
    Generate a unique file path by appending a numeric suffix if needed.
    
    Args:
        target_path: Desired file path
        
    Returns:
        Unique path (original or with suffix like _1, _2, etc.)
    """
    path = Path(target_path)
    
    if not path.exists():
        return path
    
    # File exists, need to find unique name
    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    
    counter = 1
    while True:
        new_path = parent / f'{stem}_{counter}{suffix}'
        if not new_path.exists():
            return new_path
        counter += 1


def process_file(file_path: str | Path) -> Optional[Path]:
    """
    Process a file: detect type and rename if needed.
    
    Args:
        file_path: Path to the file to process
        
    Returns:
        New path if renamed, None if no rename needed or failed
    """
    path = Path(file_path)
    
    if not path.exists():
        logger.warning(f'File not found: {path}')
        return None
    
    # Check if file should be renamed
    needs_rename, new_ext = should_rename(path)
    
    if not needs_rename:
        return None
    
    # Construct new path
    new_path = path.with_suffix(new_ext)
    
    # Handle collision
    if new_path.exists() and new_path != path:
        logger.warning(f'Target exists, finding unique name: {new_path.name}')
        new_path = get_unique_path(new_path)
    
    # Perform rename
    if rename_with_metadata(path, new_path):
        return new_path
    
    return None


def batch_process_directory(
    directory: str | Path,
    recursive: bool = True
) -> dict[str, int]:
    """
    Process all files in a directory, renaming as needed.
    
    Args:
        directory: Directory to process
        recursive: Whether to process subdirectories
        
    Returns:
        Statistics dict with 'processed', 'renamed', 'failed' counts
    """
    directory = Path(directory)
    stats = {'processed': 0, 'renamed': 0, 'failed': 0}
    
    if not directory.exists():
        logger.error(f'Directory not found: {directory}')
        return stats
    
    # Get file pattern
    pattern = '**/*' if recursive else '*'
    
    for file_path in directory.glob(pattern):
        if not file_path.is_file():
            continue
        
        # Only process CR3 and image files
        if file_path.suffix.lower() not in ['.cr3', '.jpg', '.jpeg']:
            continue
        
        stats['processed'] += 1
        
        result = process_file(file_path)
        if result:
            stats['renamed'] += 1
        elif result is None and should_rename(file_path)[0]:
            stats['failed'] += 1
    
    logger.info(
        f'Batch complete: {stats["processed"]} processed, '
        f'{stats["renamed"]} renamed, {stats["failed"]} failed'
    )
    
    return stats

