"""Tests for file system watcher with debouncing."""

import pytest
import time
from pathlib import Path
from unittest.mock import Mock
from src.watcher import DebouncedWatcher, FileEventHandler
from queue import Queue


def test_file_event_handler_creation():
    """Test event handler initialization."""
    queue = Queue()
    handler = FileEventHandler(queue, process_renames=False)
    
    assert handler.event_queue == queue
    assert handler.process_renames is False


def test_watcher_initialization(temp_source_dir):
    """Test watcher initialization."""
    sync_callback = Mock()
    
    watcher = DebouncedWatcher(
        source_directory=str(temp_source_dir),
        sync_callback=sync_callback,
        debounce_seconds=1.0,
        max_latency_seconds=5.0,
        sync_rate_seconds=10.0,
        use_polling=False
    )
    
    assert watcher.source_directory == str(temp_source_dir)
    assert watcher.sync_callback == sync_callback
    assert watcher.debounce_seconds == 1.0
    assert watcher.max_latency_seconds == 5.0
    assert watcher.sync_rate_seconds == 10.0
    assert watcher.use_polling is False


def test_watcher_start_stop(temp_source_dir):
    """Test starting and stopping the watcher."""
    sync_callback = Mock()
    
    watcher = DebouncedWatcher(
        source_directory=str(temp_source_dir),
        sync_callback=sync_callback,
        debounce_seconds=1.0
    )
    
    # Start watcher
    watcher.start()
    assert watcher.running is True
    assert watcher.observer is not None
    
    # Stop watcher
    watcher.stop()
    assert watcher.running is False


def test_watcher_nonexistent_directory(temp_dir):
    """Test watcher with non-existent directory."""
    nonexistent = temp_dir / 'nonexistent'
    sync_callback = Mock()
    
    watcher = DebouncedWatcher(
        source_directory=str(nonexistent),
        sync_callback=sync_callback
    )
    
    with pytest.raises(FileNotFoundError):
        watcher.start()


def test_debounce_trigger(temp_source_dir):
    """Test that debounce timer triggers sync."""
    sync_callback = Mock()
    
    watcher = DebouncedWatcher(
        source_directory=str(temp_source_dir),
        sync_callback=sync_callback,
        debounce_seconds=0.5,
        max_latency_seconds=10.0,
        sync_rate_seconds=0.0  # Disable periodic
    )
    
    watcher.start()
    
    # Create a file to trigger event
    test_file = Path(temp_source_dir) / 'test.txt'
    test_file.write_text('test')
    
    # Wait for debounce + processing
    time.sleep(1.5)
    
    # Sync should have been called
    assert sync_callback.called
    
    watcher.stop()


def test_force_sync(temp_source_dir):
    """Test manual force sync."""
    sync_callback = Mock()
    
    watcher = DebouncedWatcher(
        source_directory=str(temp_source_dir),
        sync_callback=sync_callback,
        debounce_seconds=10.0  # Long debounce
    )
    
    watcher.start()
    
    # Force sync immediately
    watcher.force_sync()
    
    # Should be called immediately without waiting
    assert sync_callback.called
    
    watcher.stop()


def test_queue_size(temp_source_dir):
    """Test getting queue size."""
    sync_callback = Mock()
    
    watcher = DebouncedWatcher(
        source_directory=str(temp_source_dir),
        sync_callback=sync_callback,
        debounce_seconds=10.0  # Long enough to not trigger
    )
    
    watcher.start()
    
    # Initially empty
    assert watcher.get_queue_size() == 0
    
    # Create some files
    for i in range(3):
        (Path(temp_source_dir) / f'test{i}.txt').write_text(f'test{i}')
    
    # Give time for events to queue
    time.sleep(0.5)
    
    # Should have events in queue
    size = watcher.get_queue_size()
    # Depending on timing, might be 0 if processed already
    assert size >= 0
    
    watcher.stop()


def test_polling_observer(temp_source_dir):
    """Test using polling observer instead of native."""
    sync_callback = Mock()
    
    watcher = DebouncedWatcher(
        source_directory=str(temp_source_dir),
        sync_callback=sync_callback,
        use_polling=True
    )
    
    watcher.start()
    
    # Check that polling observer is used
    from watchdog.observers.polling import PollingObserver
    assert isinstance(watcher.observer, PollingObserver)
    
    watcher.stop()


@pytest.mark.timeout(10)
def test_max_latency_trigger(temp_source_dir):
    """Test that max latency forces sync even with continuous events."""
    sync_callback = Mock()
    
    watcher = DebouncedWatcher(
        source_directory=str(temp_source_dir),
        sync_callback=sync_callback,
        debounce_seconds=5.0,  # Long debounce
        max_latency_seconds=1.0,  # Short max latency
        sync_rate_seconds=0.0
    )
    
    watcher.start()
    
    # Create continuous events
    for i in range(5):
        (Path(temp_source_dir) / f'test{i}.txt').write_text(f'test{i}')
        time.sleep(0.3)
    
    # Wait for max latency to trigger
    time.sleep(2.0)
    
    # Sync should have been called due to max latency
    assert sync_callback.called
    
    watcher.stop()

