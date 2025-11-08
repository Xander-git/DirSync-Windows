"""Integration tests for end-to-end workflows."""

import pytest
import time
from pathlib import Path
from unittest.mock import Mock
from src.watcher import DebouncedWatcher
from src.file_detector import detect_file_type


@pytest.mark.timeout(15)
def test_watch_and_rename_cr3(temp_source_dir, copy_test_files):
    """Test full workflow: watch directory, detect misnamed CR3, rename."""
    sync_callback = Mock()
    
    # Start watcher with auto-rename enabled
    watcher = DebouncedWatcher(
        source_directory=str(temp_source_dir),
        sync_callback=sync_callback,
        debounce_seconds=1.0,
        max_latency_seconds=5.0,
        sync_rate_seconds=0.0,
        process_renames=True  # Enable auto-rename
    )
    
    watcher.start()
    
    # Copy a misnamed CR3 file (named as .jpg)
    files = copy_test_files(temp_source_dir, cr3_name='misnamed.jpg')
    
    # Wait for watcher to process and rename
    time.sleep(2.0)
    
    # File should have been renamed to .cr3
    renamed_file = temp_source_dir / 'misnamed.cr3'
    assert renamed_file.exists(), "File should be renamed to .cr3"
    assert not files['cr3'].exists(), "Original misnamed file should not exist"
    
    # Verify it's actually a CR3
    assert detect_file_type(renamed_file) == 'cr3'
    
    # Sync should have been triggered
    time.sleep(1.5)  # Wait for debounce
    assert sync_callback.called
    
    watcher.stop()


@pytest.mark.timeout(15)
def test_watch_and_rename_jpg(temp_source_dir, copy_test_files):
    """Test full workflow: watch directory, detect misnamed JPEG, rename."""
    sync_callback = Mock()
    
    watcher = DebouncedWatcher(
        source_directory=str(temp_source_dir),
        sync_callback=sync_callback,
        debounce_seconds=1.0,
        process_renames=True
    )
    
    watcher.start()
    
    # Copy a misnamed JPEG file (named as .cr3)
    files = copy_test_files(temp_source_dir, jpg_name='misnamed.cr3')
    
    # Wait for watcher to process and rename
    time.sleep(2.0)
    
    # File should have been renamed to .jpg
    renamed_file = temp_source_dir / 'misnamed.jpg'
    assert renamed_file.exists(), "File should be renamed to .jpg"
    
    # Verify it's actually a JPEG
    assert detect_file_type(renamed_file) == 'jpg'
    
    watcher.stop()


def test_metadata_preservation_in_workflow(temp_source_dir, copy_test_files):
    """Test that metadata is preserved throughout the workflow."""
    # Copy a misnamed file
    files = copy_test_files(temp_source_dir, cr3_name='photo.jpg')
    original_path = files['cr3']
    
    # Get original timestamps
    original_stat = original_path.stat()
    original_mtime = original_stat.st_mtime
    
    # Process with rename (without watcher to avoid timing issues)
    from src.renamer import process_file
    new_path = process_file(original_path)
    
    assert new_path is not None
    assert new_path.exists()
    
    # Check metadata preserved (within reasonable tolerance)
    new_stat = new_path.stat()
    assert abs(new_stat.st_mtime - original_mtime) < 2.0


@pytest.mark.timeout(15)
def test_multiple_files_batch_processing(temp_source_dir, copy_test_files):
    """Test processing multiple misnamed files."""
    # Copy multiple misnamed files
    copy_test_files(temp_source_dir, cr3_name='photo1.jpg')
    copy_test_files(temp_source_dir, cr3_name='photo2.JPG')
    copy_test_files(temp_source_dir, jpg_name='image1.cr3')
    
    # Process directory
    from src.renamer import batch_process_directory
    stats = batch_process_directory(temp_source_dir, recursive=False)
    
    # Should have processed and renamed files
    assert stats['processed'] >= 3
    assert stats['renamed'] >= 3
    
    # Check renamed files exist
    assert (temp_source_dir / 'photo1.cr3').exists()
    assert (temp_source_dir / 'photo2.cr3').exists()
    assert (temp_source_dir / 'image1.jpg').exists()


def test_recursive_directory_processing(temp_source_dir, copy_test_files):
    """Test recursive processing of subdirectories."""
    # Create subdirectories with misnamed files
    subdir1 = temp_source_dir / 'subdir1'
    subdir2 = temp_source_dir / 'subdir2'
    
    copy_test_files(subdir1, cr3_name='photo.jpg')
    copy_test_files(subdir2, jpg_name='image.cr3')
    
    # Process recursively
    from src.renamer import batch_process_directory
    stats = batch_process_directory(temp_source_dir, recursive=True)
    
    # Should have found and processed files in subdirectories
    assert stats['processed'] >= 2
    assert stats['renamed'] >= 2
    
    # Check renamed files
    assert (subdir1 / 'photo.cr3').exists()
    assert (subdir2 / 'image.jpg').exists()


@pytest.mark.timeout(10)
def test_no_rename_when_disabled(temp_source_dir, copy_test_files):
    """Test that auto-rename can be disabled."""
    sync_callback = Mock()
    
    # Watcher with rename disabled
    watcher = DebouncedWatcher(
        source_directory=str(temp_source_dir),
        sync_callback=sync_callback,
        debounce_seconds=1.0,
        process_renames=False  # Disable auto-rename
    )
    
    watcher.start()
    
    # Copy a misnamed file
    files = copy_test_files(temp_source_dir, cr3_name='misnamed.jpg')
    
    # Wait for processing
    time.sleep(2.0)
    
    # File should NOT have been renamed
    assert files['cr3'].exists(), "Original file should still exist"
    assert not (temp_source_dir / 'misnamed.cr3').exists(), "Should not be renamed"
    
    watcher.stop()

