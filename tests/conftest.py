"""Pytest configuration and fixtures."""

import pytest
import tempfile
import shutil
from pathlib import Path


@pytest.fixture
def test_resources_dir():
    """Get path to test resources directory."""
    return Path(__file__).parent / 'resources'


@pytest.fixture
def cr3_test_file(test_resources_dir):
    """Get path to CR3 test file."""
    return test_resources_dir / 'raw_image.cr3'


@pytest.fixture
def jpg_test_file(test_resources_dir):
    """Get path to JPG test file."""
    return test_resources_dir / 'jpeg_image.jpg'


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def temp_source_dir(temp_dir):
    """Create a temporary source directory."""
    source = temp_dir / 'source'
    source.mkdir()
    return source


@pytest.fixture
def temp_dest_dir(temp_dir):
    """Create a temporary destination directory."""
    dest = temp_dir / 'dest'
    dest.mkdir()
    return dest


@pytest.fixture
def copy_test_files(cr3_test_file, jpg_test_file):
    """
    Factory fixture to copy test files to a directory.
    
    Returns a function that copies files and returns their paths.
    """
    def _copy(target_dir: Path, cr3_name: str = None, jpg_name: str = None):
        target_dir.mkdir(parents=True, exist_ok=True)
        
        result = {}
        
        if cr3_name:
            cr3_target = target_dir / cr3_name
            shutil.copy2(cr3_test_file, cr3_target)
            result['cr3'] = cr3_target
        
        if jpg_name:
            jpg_target = target_dir / jpg_name
            shutil.copy2(jpg_test_file, jpg_target)
            result['jpg'] = jpg_target
        
        return result
    
    return _copy

