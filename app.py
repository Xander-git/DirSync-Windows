"""
DirSync-Windows - Main Application Entry Point

Windows-only directory synchronization with content-based file renaming.
Watches a source directory for changes, renames misnamed CR3/JPG files,
and performs one-way sync to a NAS destination using robocopy.
"""

import sys
import logging
from datetime import datetime
from typing import Optional

from src.utils import setup_logging
from src.config import ConfigManager, AppConfig
from src.sync_engine import SyncEngine
from src.watcher import DebouncedWatcher
from src.gui import DirSyncGUI
from src.tray import TrayIcon


logger: Optional[logging.Logger] = None


class DirSyncApp:
    """Main application coordinator."""
    
    def __init__(self):
        """Initialize the application."""
        # Set up logging first
        global logger
        logger = setup_logging(logging.INFO)
        logger.info('=' * 60)
        logger.info('DirSync-Windows starting...')
        logger.info('=' * 60)
        
        # Initialize components
        self.config_manager = ConfigManager()
        self.config_manager.load()
        
        self.sync_engine: Optional[SyncEngine] = None
        self.watcher: Optional[DebouncedWatcher] = None
        self.tray: Optional[TrayIcon] = None
        self.gui: Optional[DirSyncGUI] = None
    
    def run(self):
        """Run the application."""
        try:
            # Create GUI
            self.gui = DirSyncGUI(
                config_manager=self.config_manager,
                on_start=self._handle_start,
                on_stop=self._handle_stop,
                on_test_sync=self._handle_test_sync,
                on_close=self._handle_exit
            )
            
            # Create tray icon
            self.tray = TrayIcon(
                on_show_gui=self._handle_show_gui,
                on_start_sync=self._handle_tray_start,
                on_stop_sync=self._handle_stop,
                on_exit=self._handle_exit
            )
            self.tray.start()
            
            # Start GUI main loop
            logger.info('GUI initialized, entering main loop')
            self.gui.run()
            
        except KeyboardInterrupt:
            logger.info('Keyboard interrupt received')
            self._cleanup()
        except Exception as e:
            logger.exception(f'Fatal error: {e}')
            self._cleanup()
            sys.exit(1)
    
    def _handle_start(self, config: AppConfig):
        """
        Handle start sync from GUI.
        
        Args:
            config: Application configuration
        """
        try:
            logger.info('Starting sync operation...')
            
            # Save config
            self.config_manager.save(config)
            
            # Create sync engine
            self.sync_engine = SyncEngine(
                source=config.source_directory,
                destination=config.destination_directory,
                threads=config.threads,
                mirror=config.mirror_deletions,
                use_fft=True,
                exclude_files=config.get_exclude_files_list(),
                exclude_dirs=config.get_exclude_dirs_list()
            )
            
            # Test connection
            success, message = self.sync_engine.test_connection()
            if not success:
                logger.error(f'Connection test failed: {message}')
                if self.gui:
                    self.gui.update_sync_status('Failed', -1, 0, 'error')
                return
            
            logger.info(f'Connection test: {message}')
            
            # Create watcher
            self.watcher = DebouncedWatcher(
                source_directory=config.source_directory,
                sync_callback=self._perform_sync,
                debounce_seconds=config.debounce_seconds,
                max_latency_seconds=config.max_latency_seconds,
                sync_rate_seconds=config.sync_rate_seconds,
                use_polling=config.use_polling,
                process_renames=True
            )
            
            # Start watcher
            self.watcher.start()
            
            logger.info('Sync operation started successfully')
            
            # Update GUI
            if self.gui:
                self.gui.update_sync_status(
                    'Started',
                    0,
                    0,
                    'running'
                )
            
            # Update tray
            if self.tray:
                self.tray.update_tooltip('DirSync-Windows - Running')
            
        except Exception as e:
            logger.exception(f'Failed to start sync: {e}')
            if self.gui:
                self.gui.update_sync_status(f'Error: {e}', -1, 0, 'error')
    
    def _handle_stop(self):
        """Handle stop sync."""
        try:
            logger.info('Stopping sync operation...')
            
            # Stop watcher
            if self.watcher:
                self.watcher.stop()
                self.watcher = None
            
            logger.info('Sync operation stopped')
            
            # Update GUI
            if self.gui:
                self.gui.update_sync_status(
                    'Stopped',
                    0,
                    0,
                    'stopped'
                )
            
            # Update tray
            if self.tray:
                self.tray.update_tooltip('DirSync-Windows - Stopped')
                
        except Exception as e:
            logger.exception(f'Error stopping sync: {e}')
    
    def _handle_test_sync(self):
        """Handle test sync (dry run)."""
        try:
            config = self.gui._get_config_from_ui() if self.gui else self.config_manager.get_config()
            
            logger.info('Starting test sync (dry run)...')
            
            # Create temporary sync engine
            test_engine = SyncEngine(
                source=config.source_directory,
                destination=config.destination_directory,
                threads=config.threads,
                mirror=config.mirror_deletions,
                use_fft=True,
                exclude_files=config.get_exclude_files_list(),
                exclude_dirs=config.get_exclude_dirs_list()
            )
            
            # Test connection
            success, message = test_engine.test_connection()
            if not success:
                logger.error(f'Test sync failed: {message}')
                return
            
            # Perform dry run
            result = test_engine.sync(dry_run=True)
            
            logger.info(
                f'Test sync complete: {result.files_copied} would be copied, '
                f'exit code {result.exit_code}'
            )
            
            # Show result in GUI
            if self.gui:
                from tkinter import messagebox
                messagebox.showinfo(
                    'Test Sync Complete',
                    f'Dry run completed:\n'
                    f'Files to copy: {result.files_copied}\n'
                    f'Exit code: {result.exit_code}\n'
                    f'Duration: {result.duration_seconds:.1f}s\n\n'
                    f'Check logs for details.'
                )
            
        except Exception as e:
            logger.exception(f'Test sync error: {e}')
    
    def _handle_show_gui(self):
        """Handle show GUI from tray."""
        if self.gui:
            self.gui.show()
    
    def _handle_tray_start(self):
        """Handle start from tray menu."""
        if self.gui:
            config = self.gui._get_config_from_ui()
            self._handle_start(config)
    
    def _handle_exit(self):
        """Handle application exit."""
        logger.info('Shutting down...')
        self._cleanup()
        
        if self.gui:
            self.gui.quit()
    
    def _perform_sync(self):
        """Perform actual sync operation."""
        if not self.sync_engine:
            logger.warning('Sync triggered but engine not initialized')
            return
        
        try:
            # Perform sync
            result = self.sync_engine.sync(dry_run=False)
            
            # Log result
            if result.is_success:
                logger.info(
                    f'Sync successful: {result.files_copied} files copied, '
                    f'exit code {result.exit_code}, '
                    f'{result.duration_seconds:.1f}s'
                )
            else:
                logger.error(
                    f'Sync failed: exit code {result.exit_code}, '
                    f'{result.files_copied} files copied'
                )
            
            # Update GUI
            if self.gui:
                queue_size = self.watcher.get_queue_size() if self.watcher else 0
                self.gui.update_sync_status(
                    datetime.now().strftime('%H:%M:%S'),
                    result.exit_code,
                    queue_size,
                    'running' if result.is_success else 'error'
                )
            
        except Exception as e:
            logger.exception(f'Sync error: {e}')
    
    def _cleanup(self):
        """Clean up resources."""
        try:
            # Stop watcher
            if self.watcher:
                self.watcher.stop()
            
            # Stop tray
            if self.tray:
                self.tray.stop()
            
            logger.info('Cleanup complete')
            
        except Exception as e:
            logger.error(f'Cleanup error: {e}')


def main():
    """Main entry point."""
    # Check if running on Windows
    if sys.platform != 'win32':
        print('WARNING: This application is designed for Windows only.')
        print('Some features (robocopy, long paths) may not work correctly.')
    
    # Create and run application
    app = DirSyncApp()
    app.run()


if __name__ == '__main__':
    main()
