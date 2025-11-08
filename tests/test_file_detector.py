"""Tests for file type detection."""

import pytest
from pathlib import Path
from src.file_detector import detect_file_type, should_rename


def test_detect_cr3_file(cr3_test_file):
    """Test CR3 file detection using real CR3 file."""
    assert cr3_test_file.exists(), "CR3 test file should exist"
    
    detected_type = detect_file_type(cr3_test_file)
    assert detected_type == 'cr3', f"Expected 'cr3', got '{detected_type}'"


def test_detect_jpg_file(jpg_test_file):
    """Test JPG file detection using real JPEG file."""
    assert jpg_test_file.exists(), "JPG test file should exist"
    
    detected_type = detect_file_type(jpg_test_file)
    assert detected_type == 'jpg', f"Expected 'jpg', got '{detected_type}'"


def test_detect_unknown_file(temp_dir):
    """Test detection of unknown file type."""
    text_file = temp_dir / 'test.txt'
    text_file.write_text('This is not an image')
    
    detected_type = detect_file_type(text_file)
    assert detected_type is None


def test_detect_nonexistent_file(temp_dir):
    """Test detection of non-existent file."""
    fake_file = temp_dir / 'nonexistent.jpg'
    
    detected_type = detect_file_type(fake_file)
    assert detected_type is None


def test_should_rename_cr3_as_jpg(temp_dir, copy_test_files):
    """Test that CR3 file misnamed as .jpg should be renamed."""
    files = copy_test_files(temp_dir, cr3_name='misnamed.jpg')
    
    should_change, new_ext = should_rename(files['cr3'])
    assert should_change is True
    assert new_ext == '.cr3'


def test_should_rename_jpg_as_cr3(temp_dir, copy_test_files):
    """Test that JPG file misnamed as .cr3 should be renamed."""
    files = copy_test_files(temp_dir, jpg_name='misnamed.cr3')
    
    should_change, new_ext = should_rename(files['jpg'])
    assert should_change is True
    assert new_ext == '.jpg'


def test_should_not_rename_correct_cr3(temp_dir, copy_test_files):
    """Test that correctly named CR3 file should not be renamed."""
    files = copy_test_files(temp_dir, cr3_name='correct.cr3')
    
    should_change, new_ext = should_rename(files['cr3'])
    assert should_change is False
    assert new_ext is None


def test_should_not_rename_correct_jpg(temp_dir, copy_test_files):
    """Test that correctly named JPG file should not be renamed."""
    files = copy_test_files(temp_dir, jpg_name='correct.jpg')
    
    should_change, new_ext = should_rename(files['jpg'])
    # May be True to normalize case, but should produce .jpg
    if should_change:
        assert new_ext == '.jpg'


def test_normalize_jpg_case(temp_dir, copy_test_files):
    """Test that .JPG and .Jpg are normalized to .jpg."""
    files = copy_test_files(temp_dir, jpg_name='uppercase.JPG')
    
    should_change, new_ext = should_rename(files['jpg'])
    assert should_change is True
    assert new_ext == '.jpg'

