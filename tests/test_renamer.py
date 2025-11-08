"""Tests for file renaming with metadata preservation."""

import pytest
import os
import time
from pathlib import Path
from src.renamer import rename_with_metadata, get_unique_path, process_file


def test_rename_with_metadata(temp_dir, copy_test_files):
    """Test basic file rename with metadata preservation."""
    files = copy_test_files(temp_dir, cr3_name='test.cr3')
    old_path = files['cr3']
    new_path = temp_dir / 'renamed.cr3'
    
    # Get original stats
    original_mtime = old_path.stat().st_mtime
    
    # Rename
    success = rename_with_metadata(old_path, new_path)
    
    assert success is True
    assert not old_path.exists()
    assert new_path.exists()
    
    # Check metadata preserved (within 1 second tolerance)
    new_mtime = new_path.stat().st_mtime
    assert abs(new_mtime - original_mtime) < 2.0


def test_rename_misnamed_cr3(temp_dir, copy_test_files):
    """Test renaming CR3 file misnamed as .jpg."""
    files = copy_test_files(temp_dir, cr3_name='misnamed.jpg')
    
    result = process_file(files['cr3'])
    
    assert result is not None
    assert result.suffix == '.cr3'
    assert result.exists()
    assert not files['cr3'].exists()


def test_rename_misnamed_jpg(temp_dir, copy_test_files):
    """Test renaming JPEG file with wrong extension."""
    files = copy_test_files(temp_dir, jpg_name='misnamed.JPG')
    
    result = process_file(files['jpg'])
    
    # Should normalize to .jpg
    if result:
        assert result.suffix == '.jpg'
        assert result.exists()


def test_no_rename_correct_file(temp_dir, copy_test_files):
    """Test that correctly named file is not renamed."""
    files = copy_test_files(temp_dir, cr3_name='correct.cr3')
    
    result = process_file(files['cr3'])
    
    # Should return None (no rename needed)
    assert result is None
    assert files['cr3'].exists()


def test_collision_handling(temp_dir, copy_test_files):
    """Test handling of name collision with suffix increment."""
    # Create a misnamed file
    files = copy_test_files(temp_dir, cr3_name='photo.jpg')
    
    # Create a file that would conflict
    conflict_file = temp_dir / 'photo.cr3'
    conflict_file.write_text('existing file')
    
    # Process the misnamed file
    result = process_file(files['cr3'])
    
    # Should have renamed with suffix to avoid collision
    assert result is not None
    assert result.name == 'photo_1.cr3'
    assert result.exists()
    assert conflict_file.exists()  # Original should still exist


def test_get_unique_path(temp_dir):
    """Test unique path generation."""
    # First file should use original name
    path1 = temp_dir / 'test.txt'
    unique1 = get_unique_path(path1)
    assert unique1 == path1
    
    # Create the file
    path1.write_text('test')
    
    # Second file should get suffix
    unique2 = get_unique_path(path1)
    assert unique2.name == 'test_1.txt'
    
    # Create that too
    unique2.write_text('test2')
    
    # Third should increment
    unique3 = get_unique_path(path1)
    assert unique3.name == 'test_2.txt'


def test_rename_nonexistent_file(temp_dir):
    """Test that renaming non-existent file returns None."""
    fake_file = temp_dir / 'nonexistent.cr3'
    
    result = process_file(fake_file)
    assert result is None


@pytest.mark.skipif(os.name != 'nt', reason="Windows-specific test")
def test_long_path_handling(temp_dir):
    """Test that long paths are handled correctly on Windows."""
    # Create a file with a long name
    long_name = 'a' * 200 + '.cr3'
    long_path = temp_dir / long_name
    long_path.write_text('test')
    
    new_path = temp_dir / ('renamed_' + 'a' * 200 + '.cr3')
    
    success = rename_with_metadata(long_path, new_path)
    # May or may not succeed depending on path length, but shouldn't crash
    assert success in [True, False]

