"""Tests for sync engine (robocopy wrapper)."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
from src.sync_engine import SyncEngine, SyncResult


def test_sync_engine_init(temp_source_dir, temp_dest_dir):
    """Test sync engine initialization."""
    engine = SyncEngine(
        source=str(temp_source_dir),
        destination=str(temp_dest_dir),
        threads=8,
        mirror=True,
        use_fft=False
    )
    
    assert engine.source == str(temp_source_dir)
    assert engine.destination == str(temp_dest_dir)
    assert engine.threads == 8
    assert engine.mirror is True
    assert engine.use_fft is False


def test_build_command_basic(temp_source_dir, temp_dest_dir):
    """Test basic robocopy command construction."""
    engine = SyncEngine(
        source=str(temp_source_dir),
        destination=str(temp_dest_dir),
        threads=16
    )
    
    cmd = engine.build_command()
    
    assert 'robocopy' in cmd[0]
    assert '/E' in cmd
    assert '/DCOPY:T' in cmd
    assert '/COPYALL' in cmd
    assert '/R:2' in cmd
    assert '/W:5' in cmd
    assert '/MT:16' in cmd
    assert '/NFL' in cmd
    assert '/NDL' in cmd
    assert '/NP' in cmd
    assert '/TEE' in cmd


def test_build_command_with_mirror(temp_source_dir, temp_dest_dir):
    """Test command with mirror flag."""
    engine = SyncEngine(
        source=str(temp_source_dir),
        destination=str(temp_dest_dir),
        mirror=True
    )
    
    cmd = engine.build_command()
    assert '/MIR' in cmd


def test_build_command_with_fft(temp_source_dir, temp_dest_dir):
    """Test command with FFT flag."""
    engine = SyncEngine(
        source=str(temp_source_dir),
        destination=str(temp_dest_dir),
        use_fft=True
    )
    
    cmd = engine.build_command()
    assert '/FFT' in cmd


def test_build_command_dry_run(temp_source_dir, temp_dest_dir):
    """Test command with dry run flag."""
    engine = SyncEngine(
        source=str(temp_source_dir),
        destination=str(temp_dest_dir)
    )
    
    cmd = engine.build_command(dry_run=True)
    assert '/L' in cmd


def test_build_command_with_exclusions(temp_source_dir, temp_dest_dir):
    """Test command with file and directory exclusions."""
    engine = SyncEngine(
        source=str(temp_source_dir),
        destination=str(temp_dest_dir),
        exclude_files=['*.tmp', '*.bak'],
        exclude_dirs=['__pycache__', 'cache']
    )
    
    cmd = engine.build_command()
    
    # Check file exclusions
    assert '/XF' in cmd
    assert '*.tmp' in cmd
    assert '*.bak' in cmd
    
    # Check directory exclusions
    assert '/XD' in cmd
    assert '__pycache__' in cmd
    assert 'cache' in cmd


def test_thread_clamping(temp_source_dir, temp_dest_dir):
    """Test that thread count is clamped to valid range."""
    # Too low
    engine1 = SyncEngine(
        source=str(temp_source_dir),
        destination=str(temp_dest_dir),
        threads=0
    )
    assert engine1.threads == 1
    
    # Too high
    engine2 = SyncEngine(
        source=str(temp_source_dir),
        destination=str(temp_dest_dir),
        threads=200
    )
    assert engine2.threads == 128


@patch('src.sync_engine.subprocess.run')
def test_sync_success(mock_run, temp_source_dir, temp_dest_dir):
    """Test successful sync operation."""
    # Mock robocopy output
    mock_run.return_value = Mock(
        returncode=1,  # 1 = files copied successfully
        stdout='Files : 10 5 3\n',
        stderr=''
    )
    
    engine = SyncEngine(
        source=str(temp_source_dir),
        destination=str(temp_dest_dir)
    )
    
    result = engine.sync()
    
    assert result.success is True
    assert result.is_success is True
    assert result.exit_code == 1
    assert mock_run.called


@patch('src.sync_engine.subprocess.run')
def test_sync_failure(mock_run, temp_source_dir, temp_dest_dir):
    """Test failed sync operation."""
    # Mock robocopy error
    mock_run.return_value = Mock(
        returncode=8,  # 8+ = error
        stdout='',
        stderr='Error occurred'
    )
    
    engine = SyncEngine(
        source=str(temp_source_dir),
        destination=str(temp_dest_dir)
    )
    
    result = engine.sync()
    
    assert result.success is False
    assert result.is_success is False
    assert result.exit_code == 8


@patch('src.sync_engine.subprocess.run')
def test_sync_exit_codes(mock_run, temp_source_dir, temp_dest_dir):
    """Test exit code interpretation."""
    engine = SyncEngine(
        source=str(temp_source_dir),
        destination=str(temp_dest_dir)
    )
    
    # Test success codes (0-7)
    for code in range(8):
        mock_run.return_value = Mock(returncode=code, stdout='', stderr='')
        result = engine.sync()
        assert result.is_success is True, f"Exit code {code} should be success"
    
    # Test error codes (8+)
    for code in [8, 16]:
        mock_run.return_value = Mock(returncode=code, stdout='', stderr='')
        result = engine.sync()
        assert result.is_success is False, f"Exit code {code} should be failure"


def test_test_connection_success(temp_source_dir, temp_dest_dir):
    """Test connection test with valid directories."""
    engine = SyncEngine(
        source=str(temp_source_dir),
        destination=str(temp_dest_dir)
    )
    
    success, message = engine.test_connection()
    assert success is True
    assert 'accessible' in message.lower()


def test_test_connection_bad_source(temp_dir, temp_dest_dir):
    """Test connection test with non-existent source."""
    bad_source = temp_dir / 'nonexistent'
    
    engine = SyncEngine(
        source=str(bad_source),
        destination=str(temp_dest_dir)
    )
    
    success, message = engine.test_connection()
    assert success is False
    assert 'not found' in message.lower()


def test_test_connection_creates_dest(temp_source_dir, temp_dir):
    """Test that connection test creates destination if missing."""
    new_dest = temp_dir / 'new_dest'
    
    engine = SyncEngine(
        source=str(temp_source_dir),
        destination=str(new_dest)
    )
    
    success, message = engine.test_connection()
    assert success is True
    assert new_dest.exists()

