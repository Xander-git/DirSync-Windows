"""Robocopy-based synchronization engine for Windows."""

import subprocess
import logging
from pathlib import Path
from typing import Optional
from dataclasses import dataclass
from datetime import datetime

from .utils import to_long_path


logger = logging.getLogger('DirSync-Windows')


@dataclass
class SyncResult:
    """Result of a sync operation."""
    exit_code: int
    success: bool
    files_copied: int
    files_failed: int
    duration_seconds: float
    output: str
    
    @property
    def is_success(self) -> bool:
        """Exit codes 0-7 are considered success in robocopy."""
        return 0 <= self.exit_code < 8


class SyncEngine:
    """Robocopy-based sync engine with proper metadata preservation."""
    
    def __init__(
        self,
        source: str,
        destination: str,
        threads: int = 16,
        mirror: bool = False,
        use_fft: bool = True,
        exclude_files: Optional[list[str]] = None,
        exclude_dirs: Optional[list[str]] = None
    ):
        """
        Initialize sync engine.
        
        Args:
            source: Source directory path
            destination: Destination directory path
            threads: Number of threads for multi-threaded copy
            mirror: Enable mirror mode (delete files in dest not in source)
            use_fft: Use FAT file timing (for NAS compatibility)
            exclude_files: List of file patterns to exclude (e.g., ['*.tmp', '*.bak'])
            exclude_dirs: List of directory names to exclude (e.g., ['__pycache__'])
        """
        self.source = source
        self.destination = destination
        self.threads = max(1, min(threads, 128))  # Clamp to 1-128
        self.mirror = mirror
        self.use_fft = use_fft
        self.exclude_files = exclude_files or []
        self.exclude_dirs = exclude_dirs or []
    
    def build_command(self, dry_run: bool = False) -> list[str]:
        """
        Build robocopy command with all necessary flags.
        
        Args:
            dry_run: If True, adds /L flag for testing without copying
            
        Returns:
            List of command arguments
        """
        # Convert paths to long-path format
        source_long = to_long_path(str(Path(self.source).absolute()))
        dest_long = to_long_path(str(Path(self.destination).absolute()))
        
        cmd = [
            'robocopy',
            source_long,
            dest_long,
            '/E',           # Copy subdirectories including empty ones
            '/DCOPY:T',     # Copy directory timestamps
            '/COPYALL',     # Copy all file info (data, attributes, timestamps, NTFS ACLs, owner, audit)
            '/R:2',         # Retry 2 times on failed copies
            '/W:5',         # Wait 5 seconds between retries
            f'/MT:{self.threads}',  # Multi-threaded copy
            '/NFL',         # No file list in output
            '/NDL',         # No directory list in output
            '/NP',          # No progress percentage in output
            '/TEE',         # Output to console and log
        ]
        
        # Mirror mode (deletes files in dest not in source)
        if self.mirror:
            cmd.append('/MIR')
        
        # FAT file timing (for NAS compatibility)
        if self.use_fft:
            cmd.append('/FFT')
        
        # Dry run mode
        if dry_run:
            cmd.append('/L')
        
        # Exclude files
        for pattern in self.exclude_files:
            cmd.extend(['/XF', pattern])
        
        # Exclude directories
        for dirname in self.exclude_dirs:
            cmd.extend(['/XD', dirname])
        
        return cmd
    
    def sync(self, dry_run: bool = False) -> SyncResult:
        """
        Execute synchronization.
        
        Args:
            dry_run: If True, performs a test run without actually copying
            
        Returns:
            SyncResult with operation details
        """
        cmd = self.build_command(dry_run)
        
        logger.info(f'Starting sync: {self.source} -> {self.destination}')
        if dry_run:
            logger.info('DRY RUN mode - no files will be copied')
        
        start_time = datetime.now()
        
        try:
            # Run robocopy
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace'
            )
            
            duration = (datetime.now() - start_time).total_seconds()
            
            # Parse output for statistics
            files_copied = self._parse_files_copied(result.stdout)
            files_failed = self._parse_files_failed(result.stdout)
            
            # Robocopy exit codes:
            # 0 = No files copied (no change)
            # 1 = Files copied successfully
            # 2 = Extra files or directories detected
            # 4 = Mismatched files or directories
            # 8+ = Errors occurred
            exit_code = result.returncode
            success = 0 <= exit_code < 8
            
            sync_result = SyncResult(
                exit_code=exit_code,
                success=success,
                files_copied=files_copied,
                files_failed=files_failed,
                duration_seconds=duration,
                output=result.stdout + result.stderr
            )
            
            if success:
                logger.info(
                    f'Sync completed: {files_copied} files copied, '
                    f'{files_failed} failed, {duration:.1f}s, exit code {exit_code}'
                )
            else:
                logger.error(
                    f'Sync failed: exit code {exit_code}, '
                    f'{files_copied} copied, {files_failed} failed'
                )
            
            return sync_result
            
        except FileNotFoundError:
            logger.error('Robocopy not found - is this running on Windows?')
            return SyncResult(
                exit_code=-1,
                success=False,
                files_copied=0,
                files_failed=0,
                duration_seconds=0,
                output='Robocopy command not found'
            )
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error(f'Sync error: {e}')
            return SyncResult(
                exit_code=-1,
                success=False,
                files_copied=0,
                files_failed=0,
                duration_seconds=duration,
                output=str(e)
            )
    
    def _parse_files_copied(self, output: str) -> int:
        """Parse robocopy output for number of files copied."""
        try:
            for line in output.splitlines():
                if 'Files :' in line:
                    # Line format: "    Files :       123      456      789"
                    # Third column is files copied
                    parts = line.split()
                    if len(parts) >= 4:
                        return int(parts[3])
        except (ValueError, IndexError):
            pass
        return 0
    
    def _parse_files_failed(self, output: str) -> int:
        """Parse robocopy output for number of failed files."""
        try:
            for line in output.splitlines():
                if 'Failed :' in line or 'FAILED :' in line:
                    parts = line.split()
                    if len(parts) >= 3:
                        return int(parts[2])
        except (ValueError, IndexError):
            pass
        return 0
    
    def test_connection(self) -> tuple[bool, str]:
        """
        Test if source and destination are accessible.
        
        Returns:
            Tuple of (success, message)
        """
        source_path = Path(self.source)
        dest_path = Path(self.destination)
        
        if not source_path.exists():
            return False, f'Source directory not found: {self.source}'
        
        if not source_path.is_dir():
            return False, f'Source is not a directory: {self.source}'
        
        # Try to create destination if it doesn't exist
        try:
            dest_path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            return False, f'Cannot create destination directory: {e}'
        
        if not dest_path.is_dir():
            return False, f'Destination is not a directory: {self.destination}'
        
        return True, 'Source and destination are accessible'

