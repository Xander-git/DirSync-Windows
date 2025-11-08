"""Tkinter GUI for DirSync-Windows."""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import logging
from pathlib import Path
from typing import Optional, Callable

from .config import AppConfig, ConfigManager
from .utils import get_log_tail


logger = logging.getLogger('DirSync-Windows')


class DirSyncGUI:
    """Main GUI window for DirSync-Windows."""
    
    def __init__(
        self,
        config_manager: ConfigManager,
        on_start: Optional[Callable[[AppConfig], None]] = None,
        on_stop: Optional[Callable[[], None]] = None,
        on_test_sync: Optional[Callable[[], None]] = None,
        on_close: Optional[Callable[[], None]] = None
    ):
        """
        Initialize GUI.
        
        Args:
            config_manager: Configuration manager instance
            on_start: Callback when Start button clicked
            on_stop: Callback when Stop button clicked
            on_test_sync: Callback when Test Sync button clicked
            on_close: Callback when window closed
        """
        self.config_manager = config_manager
        self.on_start = on_start
        self.on_stop = on_stop
        self.on_test_sync = on_test_sync
        self.on_close = on_close
        
        self.root = tk.Tk()
        self.root.title('DirSync-Windows')
        self.root.geometry('800x700')
        
        # Status tracking
        self.is_running = False
        self.last_sync_time = ''
        self.last_exit_code = 0
        self.queue_size = 0
        self.sync_mode = 'stopped'
        
        # Set up close protocol
        self.root.protocol('WM_DELETE_WINDOW', self._on_window_close)
        
        # Build UI
        self._build_ui()
        
        # Load configuration into UI
        self._load_config_to_ui()
        
        # Start log update timer
        self._schedule_log_update()
    
    def _build_ui(self):
        """Build the user interface."""
        # Main container with padding
        main_frame = ttk.Frame(self.root, padding='10')
        main_frame.grid(row=0, column=0, sticky='nsew')
        
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        
        row = 0
        
        # === Paths Section ===
        paths_frame = ttk.LabelFrame(main_frame, text='Paths', padding='10')
        paths_frame.grid(row=row, column=0, sticky='ew', pady=(0, 10))
        paths_frame.columnconfigure(1, weight=1)
        row += 1
        
        # Source directory
        ttk.Label(paths_frame, text='Source:').grid(row=0, column=0, sticky='w', padx=(0, 5))
        self.source_var = tk.StringVar()
        ttk.Entry(paths_frame, textvariable=self.source_var).grid(
            row=0, column=1, sticky='ew', padx=5
        )
        ttk.Button(paths_frame, text='Browse...', command=self._browse_source).grid(
            row=0, column=2
        )
        
        # Destination directory
        ttk.Label(paths_frame, text='Destination:').grid(row=1, column=0, sticky='w', padx=(0, 5), pady=(5, 0))
        self.dest_var = tk.StringVar()
        ttk.Entry(paths_frame, textvariable=self.dest_var).grid(
            row=1, column=1, sticky='ew', padx=5, pady=(5, 0)
        )
        ttk.Button(paths_frame, text='Browse...', command=self._browse_dest).grid(
            row=1, column=2, pady=(5, 0)
        )
        
        # === Options Section ===
        options_frame = ttk.LabelFrame(main_frame, text='Options', padding='10')
        options_frame.grid(row=row, column=0, sticky='ew', pady=(0, 10))
        row += 1
        
        self.mirror_var = tk.BooleanVar()
        ttk.Checkbutton(options_frame, text='Mirror deletions (/MIR)', 
                       variable=self.mirror_var).grid(row=0, column=0, sticky='w')
        
        self.polling_var = tk.BooleanVar()
        ttk.Checkbutton(options_frame, text='Use polling watcher',
                       variable=self.polling_var).grid(row=1, column=0, sticky='w')
        
        self.minimized_var = tk.BooleanVar()
        ttk.Checkbutton(options_frame, text='Start minimized to tray',
                       variable=self.minimized_var).grid(row=2, column=0, sticky='w')
        
        # === Performance Section ===
        perf_frame = ttk.LabelFrame(main_frame, text='Performance', padding='10')
        perf_frame.grid(row=row, column=0, sticky='ew', pady=(0, 10))
        perf_frame.columnconfigure(1, weight=1)
        row += 1
        
        # Threads
        ttk.Label(perf_frame, text='Threads (1-128):').grid(row=0, column=0, sticky='w', padx=(0, 5))
        self.threads_var = tk.IntVar(value=16)
        ttk.Spinbox(perf_frame, from_=1, to=128, textvariable=self.threads_var,
                   width=10).grid(row=0, column=1, sticky='w')
        
        # Debounce
        ttk.Label(perf_frame, text='Debounce (seconds):').grid(row=1, column=0, sticky='w', padx=(0, 5))
        self.debounce_var = tk.DoubleVar(value=3.0)
        ttk.Entry(perf_frame, textvariable=self.debounce_var, width=10).grid(
            row=1, column=1, sticky='w'
        )
        
        # Max latency
        ttk.Label(perf_frame, text='Max latency (seconds):').grid(row=2, column=0, sticky='w', padx=(0, 5))
        self.max_latency_var = tk.DoubleVar(value=20.0)
        ttk.Entry(perf_frame, textvariable=self.max_latency_var, width=10).grid(
            row=2, column=1, sticky='w'
        )
        
        # Sync rate
        ttk.Label(perf_frame, text='Sync rate (0=disabled):').grid(row=3, column=0, sticky='w', padx=(0, 5))
        self.sync_rate_var = tk.DoubleVar(value=0.0)
        ttk.Entry(perf_frame, textvariable=self.sync_rate_var, width=10).grid(
            row=3, column=1, sticky='w'
        )
        
        # === Exclusions Section ===
        excl_frame = ttk.LabelFrame(main_frame, text='Exclusions', padding='10')
        excl_frame.grid(row=row, column=0, sticky='ew', pady=(0, 10))
        excl_frame.columnconfigure(1, weight=1)
        row += 1
        
        # Exclude files
        ttk.Label(excl_frame, text='Files (;-separated):').grid(row=0, column=0, sticky='w', padx=(0, 5))
        self.exclude_files_var = tk.StringVar(value='*.tmp;*.bak;~*')
        ttk.Entry(excl_frame, textvariable=self.exclude_files_var).grid(
            row=0, column=1, sticky='ew', padx=5
        )
        
        # Exclude directories
        ttk.Label(excl_frame, text='Directories (;-separated):').grid(row=1, column=0, sticky='w', padx=(0, 5))
        self.exclude_dirs_var = tk.StringVar(value='__pycache__;cache')
        ttk.Entry(excl_frame, textvariable=self.exclude_dirs_var).grid(
            row=1, column=1, sticky='ew', padx=5
        )
        
        # === Control Buttons ===
        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=row, column=0, sticky='ew', pady=(0, 10))
        row += 1
        
        self.start_btn = ttk.Button(btn_frame, text='Start', command=self._on_start)
        self.start_btn.pack(side='left', padx=5)
        
        self.stop_btn = ttk.Button(btn_frame, text='Stop', command=self._on_stop, state='disabled')
        self.stop_btn.pack(side='left', padx=5)
        
        ttk.Button(btn_frame, text='Test Sync (Dry Run)', command=self._on_test_sync).pack(
            side='left', padx=5
        )
        
        ttk.Separator(btn_frame, orient='vertical').pack(side='left', fill='y', padx=10)
        
        ttk.Button(btn_frame, text='Save Config', command=self._save_config).pack(
            side='left', padx=5
        )
        ttk.Button(btn_frame, text='Load Config', command=self._load_config).pack(
            side='left', padx=5
        )
        
        ttk.Separator(btn_frame, orient='vertical').pack(side='left', fill='y', padx=10)
        
        ttk.Button(btn_frame, text='Close Program', command=self._close_program).pack(
            side='left', padx=5
        )
        
        # === Status Bar ===
        status_frame = ttk.LabelFrame(main_frame, text='Status', padding='10')
        status_frame.grid(row=row, column=0, sticky='ew', pady=(0, 10))
        status_frame.columnconfigure(0, weight=1)
        row += 1
        
        self.status_text = tk.StringVar(value='Ready')
        ttk.Label(status_frame, textvariable=self.status_text, foreground='blue').grid(
            row=0, column=0, sticky='w'
        )
        
        # === Log Viewer ===
        log_frame = ttk.LabelFrame(main_frame, text='Log (last 10 lines)', padding='10')
        log_frame.grid(row=row, column=0, sticky='nsew', pady=(0, 0))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        main_frame.rowconfigure(row, weight=1)
        
        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            height=10,
            wrap=tk.WORD,
            state='disabled',
            font=('Consolas', 9)
        )
        self.log_text.grid(row=0, column=0, sticky='nsew')
    
    def _browse_source(self):
        """Browse for source directory."""
        directory = filedialog.askdirectory(title='Select Source Directory')
        if directory:
            self.source_var.set(directory)
    
    def _browse_dest(self):
        """Browse for destination directory."""
        directory = filedialog.askdirectory(title='Select Destination Directory')
        if directory:
            self.dest_var.set(directory)
    
    def _on_start(self):
        """Handle Start button click."""
        # Validate inputs
        if not self.source_var.get():
            messagebox.showerror('Error', 'Please select a source directory')
            return
        
        if not self.dest_var.get():
            messagebox.showerror('Error', 'Please select a destination directory')
            return
        
        if not Path(self.source_var.get()).exists():
            messagebox.showerror('Error', 'Source directory does not exist')
            return
        
        # Get config from UI
        config = self._get_config_from_ui()
        
        # Validate config
        is_valid, error = config.validate()
        if not is_valid:
            messagebox.showerror('Configuration Error', error)
            return
        
        # Update UI state
        self.is_running = True
        self.start_btn.config(state='disabled')
        self.stop_btn.config(state='normal')
        self.sync_mode = 'running'
        self._update_status()
        
        # Call callback
        if self.on_start:
            self.on_start(config)
    
    def _on_stop(self):
        """Handle Stop button click."""
        self.is_running = False
        self.start_btn.config(state='normal')
        self.stop_btn.config(state='disabled')
        self.sync_mode = 'stopped'
        self._update_status()
        
        if self.on_stop:
            self.on_stop()
    
    def _on_test_sync(self):
        """Handle Test Sync button click."""
        if not self.source_var.get() or not self.dest_var.get():
            messagebox.showwarning('Warning', 'Please set source and destination directories')
            return
        
        if self.on_test_sync:
            self.on_test_sync()
    
    def _save_config(self):
        """Save configuration to file."""
        config = self._get_config_from_ui()
        if self.config_manager.save(config):
            messagebox.showinfo('Success', 'Configuration saved')
        else:
            messagebox.showerror('Error', 'Failed to save configuration')
    
    def _load_config(self):
        """Load configuration from file."""
        config = self.config_manager.load()
        self._load_config_to_ui()
        messagebox.showinfo('Success', 'Configuration loaded')
    
    def _close_program(self):
        """Close the program completely."""
        if self.is_running:
            result = messagebox.askyesno(
                'Confirm Exit',
                'Sync is currently running. Stop and exit?'
            )
            if not result:
                return
            self._on_stop()
        
        if self.on_close:
            self.on_close()
        
        self.root.quit()
    
    def _on_window_close(self):
        """Handle window close button (minimize to tray instead)."""
        self.hide()
    
    def _get_config_from_ui(self) -> AppConfig:
        """Get configuration from UI fields."""
        return AppConfig(
            source_directory=self.source_var.get(),
            destination_directory=self.dest_var.get(),
            mirror_deletions=self.mirror_var.get(),
            use_polling=self.polling_var.get(),
            start_minimized=self.minimized_var.get(),
            threads=self.threads_var.get(),
            debounce_seconds=self.debounce_var.get(),
            max_latency_seconds=self.max_latency_var.get(),
            sync_rate_seconds=self.sync_rate_var.get(),
            exclude_files=self.exclude_files_var.get(),
            exclude_dirs=self.exclude_dirs_var.get()
        )
    
    def _load_config_to_ui(self):
        """Load configuration into UI fields."""
        config = self.config_manager.get_config()
        
        self.source_var.set(config.source_directory)
        self.dest_var.set(config.destination_directory)
        self.mirror_var.set(config.mirror_deletions)
        self.polling_var.set(config.use_polling)
        self.minimized_var.set(config.start_minimized)
        self.threads_var.set(config.threads)
        self.debounce_var.set(config.debounce_seconds)
        self.max_latency_var.set(config.max_latency_seconds)
        self.sync_rate_var.set(config.sync_rate_seconds)
        self.exclude_files_var.set(config.exclude_files)
        self.exclude_dirs_var.set(config.exclude_dirs)
    
    def _update_status(self):
        """Update status bar text."""
        status_parts = [
            f'Mode: {self.sync_mode}',
        ]
        
        if self.last_sync_time:
            status_parts.append(f'Last sync: {self.last_sync_time}')
        
        if self.is_running:
            status_parts.append(f'Exit code: {self.last_exit_code}')
            status_parts.append(f'Queue: {self.queue_size}')
        
        self.status_text.set(' | '.join(status_parts))
    
    def _schedule_log_update(self):
        """Schedule periodic log update."""
        self._update_log()
        self.root.after(500, self._schedule_log_update)  # Update every 500ms
    
    def _update_log(self):
        """Update log text widget with latest log lines."""
        try:
            log_lines = get_log_tail(10)
            
            self.log_text.config(state='normal')
            self.log_text.delete('1.0', tk.END)
            
            for line in log_lines:
                self.log_text.insert(tk.END, line + '\n')
            
            self.log_text.config(state='disabled')
            self.log_text.see(tk.END)
        except Exception as e:
            # Don't let log update errors crash the GUI
            pass
    
    def update_sync_status(self, last_sync: str, exit_code: int, queue_size: int, mode: str = 'running'):
        """
        Update sync status display.
        
        Args:
            last_sync: Last sync time string
            exit_code: Last robocopy exit code
            queue_size: Current event queue size
            mode: Sync mode ('running', 'stopped', etc.)
        """
        self.last_sync_time = last_sync
        self.last_exit_code = exit_code
        self.queue_size = queue_size
        self.sync_mode = mode
        self._update_status()
    
    def show(self):
        """Show the GUI window."""
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
    
    def hide(self):
        """Hide the GUI window."""
        self.root.withdraw()
    
    def run(self):
        """Start the Tkinter main loop."""
        # Check if should start minimized
        if self.config_manager.get_config().start_minimized:
            self.hide()
        
        self.root.mainloop()
    
    def quit(self):
        """Quit the application."""
        self.root.quit()

