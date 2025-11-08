"""Content-based file type detection for CR3 and JPG files."""

import logging
from pathlib import Path


logger = logging.getLogger('DirSync-Windows')


def detect_file_type(file_path: str | Path) -> str | None:
    """
    Detect file type based on content (magic bytes) rather than extension.
    
    Reads the first 32 bytes to identify:
    - CR3 (Canon RAW 3): Contains JPEG header + specific Canon markers
    - JPG/JPEG: Standard JPEG file format
    
    Args:
        file_path: Path to the file to detect
        
    Returns:
        'cr3' for Canon RAW files
        'jpg' for JPEG files
        None for unknown or unreadable files
    """
    try:
        with open(file_path, 'rb') as f:
            header = f.read(32)
        
        if len(header) < 4:
            return None
        
        # JPEG files start with FF D8 FF
        # CR3 files are JPEG-based containers, so they also start with FF D8 FF
        if header[0:3] == b'\xff\xd8\xff':
            # Check if it's a CR3 file by looking for specific markers
            # CR3 files contain "ftypcrx" or similar Canon markers
            # Let's read more to be sure
            with open(file_path, 'rb') as f:
                # Read first 64 bytes to check for CR3 signature
                full_header = f.read(64)
                
                # CR3 files have "ftyp" at offset 4 and "crx" nearby
                if b'ftypcrx' in full_header or b'crx ' in full_header:
                    return 'cr3'
                
                # Also check for Canon-specific markers in EXIF data
                if b'Canon' in full_header or b'CR3' in full_header:
                    return 'cr3'
            
            # If it starts with JPEG signature but no CR3 markers, it's a JPEG
            return 'jpg'
        
        # Check for JFIF header (another JPEG variant)
        if b'JFIF' in header or b'EXIF' in header:
            return 'jpg'
        
        return None
        
    except (IOError, OSError) as e:
        logger.warning(f'Failed to read file {file_path}: {e}')
        return None


def should_rename(file_path: str | Path) -> tuple[bool, str | None]:
    """
    Determine if a file should be renamed based on its content vs extension.
    
    Args:
        file_path: Path to the file to check
        
    Returns:
        Tuple of (should_rename, new_extension)
        - should_rename: True if file needs renaming
        - new_extension: The correct extension (with dot), or None if no rename needed
    """
    path = Path(file_path)
    current_ext = path.suffix.lower()
    
    detected_type = detect_file_type(file_path)
    
    if detected_type is None:
        return False, None
    
    # Check if CR3 file has wrong extension
    if detected_type == 'cr3':
        if current_ext in ['.jpg', '.jpeg']:
            return True, '.cr3'
    
    # Check if JPEG file has wrong extension
    elif detected_type == 'jpg':
        if current_ext in ['.cr3']:
            return True, '.jpg'
        # Normalize .JPG and .Jpg to .jpg
        elif current_ext in ['.jpg', '.jpeg']:
            # Already correct extension (case-insensitive)
            # But we might want to normalize to lowercase .jpg
            if path.suffix != '.jpg':
                return True, '.jpg'
    
    return False, None

