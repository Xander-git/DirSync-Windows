"""File system watcher with debouncing and sync triggering."""

import time
import logging
import threading
from pathlib import Path
from queue import Queue
from typing import Optional, Callable
from watchdog.observers import Observer
from watchdog.observers.polling import PollingObserver
from watchdog.events import FileSystemEventHandler, FileSystemEvent

from .renamer import process_file


logger = logging.getLogger('DirSync-Windows')


class FileEventHandler(FileSystemEventHandler):
    """Handler for file system events with intelligent filtering."""
    
    def __init__(self, event_queue: Queue, process_renames: bool = True):
        """
        Initialize event handler.
        
        Args:
            event_queue: Queue to put events into
            process_renames: Whether to auto-rename files
        """
        super().__init__()
        self.event_queue = event_queue
        self.process_renames = process_renames
    
    def on_created(self, event: FileSystemEvent):
        """Handle file creation."""
        if event.is_directory:
            return
        
        logger.debug(f'File created: {event.src_path}')
        
        # Auto-rename if needed
        if self.process_renames:
            self._try_rename(event.src_path)
        
        self.event_queue.put(('created', event.src_path))
    
    def on_modified(self, event: FileSystemEvent):
        """Handle file modification."""
        if event.is_directory:
            return
        
        logger.debug(f'File modified: {event.src_path}')
        
        # Auto-rename if needed
        if self.process_renames:
            self._try_rename(event.src_path)
        
        self.event_queue.put(('modified', event.src_path))
    
    def on_moved(self, event: FileSystemEvent):
        """Handle file move/rename."""
        if event.is_directory:
            return
        
        logger.debug(f'File moved: {event.src_path} -> {event.dest_path}')
        self.event_queue.put(('moved', event.dest_path))
    
    def _try_rename(self, file_path: str):
        """Try to rename a file if needed."""
        try:
            # Check if file is a CR3 or image file
            path = Path(file_path)
            if path.suffix.lower() in ['.cr3', '.jpg', '.jpeg']:
                # Small delay to ensure file is fully written
                time.sleep(0.1)
                new_path = process_file(file_path)
                if new_path:
                    logger.info(f'Auto-renamed: {path.name} -> {new_path.name}')
        except Exception as e:
            logger.warning(f'Failed to auto-rename {file_path}: {e}')


class DebouncedWatcher:
    """
    File system watcher with debouncing and sync triggering.
    
    Implements three sync triggering modes:
    1. Debounce: Sync after N seconds of no new events
    2. Max latency: Force sync after X seconds even if events keep coming
    3. Periodic: Sync every Y seconds regardless of events
    """
    
    def __init__(
        self,
        source_directory: str,
        sync_callback: Callable[[], None],
        debounce_seconds: float = 3.0,
        max_latency_seconds: float = 20.0,
        sync_rate_seconds: float = 0.0,
        use_polling: bool = False,
        process_renames: bool = True
    ):
        """
        Initialize debounced watcher.
        
        Args:
            source_directory: Directory to watch
            sync_callback: Function to call when sync is triggered
            debounce_seconds: Seconds of quiet before triggering sync
            max_latency_seconds: Maximum seconds to wait before forcing sync
            sync_rate_seconds: Periodic sync interval (0 = disabled)
            use_polling: Use polling observer instead of native
            process_renames: Auto-rename misnamed files
        """
        self.source_directory = source_directory
        self.sync_callback = sync_callback
        self.debounce_seconds = debounce_seconds
        self.max_latency_seconds = max_latency_seconds
        self.sync_rate_seconds = sync_rate_seconds
        self.use_polling = use_polling
        self.process_renames = process_renames
        
        # State
        self.event_queue: Queue = Queue()
        self.observer: Optional[Observer | PollingObserver] = None
        self.debounce_timer: Optional[threading.Timer] = None
        self.max_latency_timer: Optional[threading.Timer] = None
        self.periodic_timer: Optional[threading.Timer] = None
        self.running = False
        self.lock = threading.Lock()
        
        # Tracking
        self.last_event_time: Optional[float] = None
        self.first_event_time: Optional[float] = None
        self.event_count = 0
    
    def start(self):
        """Start watching the directory."""
        if self.running:
            logger.warning('Watcher already running')
            return
        
        source_path = Path(self.source_directory)
        if not source_path.exists():
            raise FileNotFoundError(f'Source directory not found: {self.source_directory}')
        
        if not source_path.is_dir():
            raise NotADirectoryError(f'Source is not a directory: {self.source_directory}')
        
        # Create observer
        if self.use_polling:
            self.observer = PollingObserver()
            logger.info('Using polling observer')
        else:
            self.observer = Observer()
            logger.info('Using native observer')
        
        # Create and register event handler
        event_handler = FileEventHandler(self.event_queue, self.process_renames)
        self.observer.schedule(event_handler, self.source_directory, recursive=True)
        
        # Start observer
        self.observer.start()
        self.running = True
        
        # Start event processor thread
        self.processor_thread = threading.Thread(
            target=self._process_events,
            name='EventProcessor',
            daemon=True
        )
        self.processor_thread.start()
        
        # Start periodic sync if enabled
        if self.sync_rate_seconds > 0:
            self._schedule_periodic_sync()
        
        logger.info(f'Watching directory: {self.source_directory}')
        logger.info(
            f'Debounce: {self.debounce_seconds}s, '
            f'Max latency: {self.max_latency_seconds}s, '
            f'Periodic: {self.sync_rate_seconds}s'
        )
    
    def stop(self):
        """Stop watching the directory."""
        if not self.running:
            return
        
        logger.info('Stopping watcher...')
        self.running = False
        
        # Cancel timers
        with self.lock:
            if self.debounce_timer:
                self.debounce_timer.cancel()
            if self.max_latency_timer:
                self.max_latency_timer.cancel()
            if self.periodic_timer:
                self.periodic_timer.cancel()
        
        # Stop observer
        if self.observer:
            self.observer.stop()
            self.observer.join(timeout=5)
        
        logger.info('Watcher stopped')
    
    def _process_events(self):
        """Process events from the queue."""
        while self.running:
            try:
                # Get event from queue (with timeout to allow checking running flag)
                if not self.event_queue.empty():
                    event_type, file_path = self.event_queue.get(timeout=0.5)
                    self._handle_event(event_type, file_path)
                else:
                    time.sleep(0.1)
            except Exception as e:
                if self.running:  # Only log if not shutting down
                    logger.error(f'Error processing event: {e}')
    
    def _handle_event(self, event_type: str, file_path: str):
        """Handle a file system event and update timers."""
        current_time = time.time()
        
        with self.lock:
            self.event_count += 1
            self.last_event_time = current_time
            
            if self.first_event_time is None:
                self.first_event_time = current_time
                # Start max latency timer
                if self.max_latency_seconds > 0:
                    self._schedule_max_latency_sync()
            
            # Reset debounce timer
            if self.debounce_timer:
                self.debounce_timer.cancel()
            
            self.debounce_timer = threading.Timer(
                self.debounce_seconds,
                self._trigger_debounce_sync
            )
            self.debounce_timer.daemon = True
            self.debounce_timer.start()
    
    def _trigger_debounce_sync(self):
        """Trigger sync after debounce period."""
        logger.info(f'Debounce sync triggered ({self.event_count} events)')
        self._reset_state()
        self._do_sync('debounce')
    
    def _schedule_max_latency_sync(self):
        """Schedule a forced sync after max latency."""
        if self.max_latency_timer:
            self.max_latency_timer.cancel()
        
        self.max_latency_timer = threading.Timer(
            self.max_latency_seconds,
            self._trigger_max_latency_sync
        )
        self.max_latency_timer.daemon = True
        self.max_latency_timer.start()
    
    def _trigger_max_latency_sync(self):
        """Trigger sync after max latency exceeded."""
        logger.info(f'Max latency sync triggered ({self.event_count} events)')
        self._reset_state()
        self._do_sync('max_latency')
    
    def _schedule_periodic_sync(self):
        """Schedule periodic sync."""
        if not self.running or self.sync_rate_seconds <= 0:
            return
        
        self.periodic_timer = threading.Timer(
            self.sync_rate_seconds,
            self._trigger_periodic_sync
        )
        self.periodic_timer.daemon = True
        self.periodic_timer.start()
    
    def _trigger_periodic_sync(self):
        """Trigger periodic sync."""
        logger.info('Periodic sync triggered')
        self._do_sync('periodic')
        # Reschedule next periodic sync
        if self.running:
            self._schedule_periodic_sync()
    
    def _reset_state(self):
        """Reset event tracking state."""
        with self.lock:
            self.event_count = 0
            self.first_event_time = None
            self.last_event_time = None
            if self.debounce_timer:
                self.debounce_timer.cancel()
                self.debounce_timer = None
            if self.max_latency_timer:
                self.max_latency_timer.cancel()
                self.max_latency_timer = None
    
    def _do_sync(self, trigger_type: str):
        """Execute the sync callback."""
        try:
            logger.info(f'Executing sync (trigger: {trigger_type})')
            self.sync_callback()
        except Exception as e:
            logger.error(f'Sync callback failed: {e}')
    
    def get_queue_size(self) -> int:
        """Get current event queue size."""
        return self.event_queue.qsize()
    
    def force_sync(self):
        """Manually trigger a sync."""
        logger.info('Manual sync triggered')
        self._reset_state()
        self._do_sync('manual')

