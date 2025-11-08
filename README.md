# DirSync-Windows

[![Build Windows Executable](https://github.com/username/SnP-ImagerSync/actions/workflows/windows-build.yml/badge.svg)](https://github.com/username/SnP-ImagerSync/actions/workflows/windows-build.yml)
[![Windows Automated Tests](https://github.com/username/SnP-ImagerSync/actions/workflows/windows-tests.yml/badge.svg)](https://github.com/username/SnP-ImagerSync/actions/workflows/windows-tests.yml)

A Windows-only Python application that watches a directory for file changes, intelligently renames misnamed CR3/JPG files based on content detection, and performs one-way synchronization to a NAS destination using robocopy with full metadata preservation.

## Features

- **Real-time Directory Watching**: Monitors source directory recursively for file changes
- **Content-Based File Detection**: Identifies CR3 and JPEG files by reading file headers, not just extensions
- **Intelligent Renaming**: Automatically renames misnamed files:
  - CR3 files with `.jpg`/`.JPG` extension → `.cr3`
  - JPEG files with wrong extensions → `.jpg`
- **Complete Metadata Preservation**: Preserves all file metadata including:
  - Timestamps (creation, modification, access)
  - File attributes
  - NTFS ACLs, Owner, and Audit information
- **Robust Sync Engine**: Uses robocopy with optimal flags for NAS compatibility
- **Smart Sync Triggering**: Three sync modes:
  - **Debounce**: Sync after N seconds of no new events
  - **Max Latency**: Force sync after X seconds even with continuous changes
  - **Periodic**: Sync every Y seconds regardless of events
- **User-Friendly GUI**: Complete Tkinter interface with all controls
- **System Tray Integration**: Runs in background, accessible from system tray
- **Comprehensive Logging**: Rotating logs with GUI tail viewer
- **Configuration Persistence**: Save/load settings to JSON
- **Offline Operation**: Runs completely offline once built

## System Requirements

- **Operating System**: Windows 10 or later
- **Python**: 3.11+ (for development only, not needed for .exe)
- **Disk Space**: ~50MB for application + logs

## Installation

### Option 1: Download Pre-built Executable (Recommended)

1. Go to [GitHub Releases](https://github.com/username/SnP-ImagerSync/releases)
2. Download `DirSync-Windows.exe` from the latest release
3. Run the executable (no Python installation needed)

### Option 2: Build from Source

1. Clone the repository:
```bash
git clone https://github.com/username/SnP-ImagerSync.git
cd SnP-ImagerSync
```

2. Install dependencies using uv (development):
```bash
uv sync
```

Or using pip:
```bash
pip install -r requirements.txt
```

3. Run the application:
```bash
python app.py
```

4. Build executable (Windows only):
```bash
build_windows.bat
```

The executable will be created in `dist/DirSync-Windows.exe`.

## Usage

### First-Time Setup

1. Launch `DirSync-Windows.exe` or run `python app.py`
2. Configure paths:
   - **Source**: Directory to watch (e.g., camera SD card mount point)
   - **Destination**: NAS or backup location
3. Adjust settings as needed (see Configuration below)
4. Click **Save Config** to persist settings
5. Click **Start** to begin watching and syncing

### GUI Controls

#### Paths
- **Source**: Directory to watch for changes
- **Destination**: Target directory for synchronization

#### Options
- **Mirror deletions**: Enable `/MIR` flag (deletes files in destination not in source)
- **Use polling watcher**: Use polling instead of native file system events (for network drives)
- **Start minimized to tray**: Application starts hidden in system tray

#### Performance
- **Threads (1-128)**: Number of robocopy threads (default: 16)
- **Debounce (seconds)**: Wait time after last event before syncing (default: 3)
- **Max latency (seconds)**: Force sync after this duration even if events continue (default: 20)
- **Sync rate (seconds)**: Periodic sync interval, 0 to disable (default: 0)

#### Exclusions
- **Files**: Semicolon-separated patterns (e.g., `*.tmp;*.bak;~*`)
- **Directories**: Semicolon-separated names (e.g., `__pycache__;cache`)

#### Actions
- **Start**: Begin watching and syncing
- **Stop**: Stop all operations
- **Test Sync (Dry Run)**: Preview what would be copied without actually copying
- **Save Config**: Save current settings to file
- **Load Config**: Load previously saved settings
- **Close Program**: Exit application completely

### System Tray

Right-click the tray icon for quick access:
- **Open GUI**: Show the main window
- **Start Sync**: Begin operations (uses saved config)
- **Stop Sync**: Stop operations
- **Exit**: Close application

### Window Behavior

- Clicking the X button **hides** the window to tray (doesn't exit)
- Use **Close Program** button or tray menu **Exit** to actually quit

## Configuration

Settings are stored in:
```
%APPDATA%\DirSync\config.json
```

Logs are stored in:
```
%LOCALAPPDATA%\DirSync\logs\app.log
```

## How It Works

### File Watching & Renaming

1. Watchdog observer monitors source directory recursively
2. When a file is created/modified:
   - Read first 64 bytes to detect file type
   - If CR3 file has `.jpg` extension → rename to `.cr3`
   - If JPEG file has wrong extension → rename to `.jpg`
   - Use `os.replace()` for atomic rename
   - Apply `shutil.copystat()` to preserve metadata
3. Event is queued for sync

### Sync Triggering

Three independent triggers:

1. **Debounce Timer**: Resets on every event, triggers after N seconds of quiet
2. **Max Latency Timer**: Starts on first event, forces sync after X seconds
3. **Periodic Timer**: Triggers every Y seconds (optional)

### Synchronization

Uses robocopy with optimized flags:
```
robocopy "\\?\SOURCE" "\\?\DEST" /E /DCOPY:T /COPYALL /R:2 /W:5 /MT:{threads} /NFL /NDL /NP /TEE [/MIR] [/FFT]
```

**Flags explained:**
- `/E`: Copy subdirectories including empty ones
- `/DCOPY:T`: Copy directory timestamps
- `/COPYALL`: Copy all file info (data, attributes, timestamps, NTFS ACLs, owner, audit)
- `/R:2 /W:5`: 2 retries with 5 second wait
- `/MT:{n}`: Multi-threaded copy (default 16 threads)
- `/NFL /NDL /NP`: Minimal console output
- `/TEE`: Output to console and log
- `/MIR`: Mirror mode (optional) - deletes files in dest not in source
- `/FFT`: FAT file timing for NAS compatibility

**Exit codes:**
- 0-7: Success (0=no change, 1=files copied, 2=extra files, 4=mismatches)
- 8+: Errors occurred

### Long Path Support

All file operations use the `\\?\` prefix to support Windows long paths (>260 characters).

## Development

### Project Structure

```
SnP-ImagerSync/
├── app.py                      # Main application entry point
├── src/
│   ├── file_detector.py        # Content-based CR3/JPG detection
│   ├── renamer.py              # File renaming with metadata preservation
│   ├── sync_engine.py          # Robocopy wrapper
│   ├── watcher.py              # Watchdog integration with debouncing
│   ├── gui.py                  # Tkinter GUI
│   ├── tray.py                 # System tray integration
│   ├── config.py               # JSON configuration management
│   └── utils.py                # Long-path helpers, logging
├── tests/
│   ├── resources/              # Real CR3/JPG test files
│   ├── test_file_detector.py  # File detection tests
│   ├── test_renamer.py         # Renaming tests
│   ├── test_sync_engine.py    # Sync engine tests (mocked)
│   ├── test_watcher.py         # Watcher tests
│   └── test_integration.py    # End-to-end tests
├── .github/workflows/
│   ├── windows-build.yml       # CI: Build executable
│   └── windows-tests.yml       # CI: Run tests
├── requirements.txt            # Dependencies
├── build_windows.bat           # Build script
└── pyproject.toml              # Project metadata (uv)
```

### Running Tests

```bash
# Install dev dependencies
pip install -r requirements.txt pytest pytest-timeout

# Run all tests
pytest -v

# Run specific test file
pytest tests/test_file_detector.py -v

# Run with coverage
pytest --cov=src tests/
```

Tests use real CR3 and JPEG files from `tests/resources/` for accurate validation.

### Building

```bash
# Windows build
build_windows.bat

# Or manually
pyinstaller app.py --onefile --noconsole --name DirSync-Windows --uac-admin --clean
```

### Code Style

- Python 3.11+ with type hints
- Black code formatting
- PEP 8 compliance
- Comprehensive docstrings

## CI/CD

### GitHub Actions Workflows

**windows-build.yml**: Builds executable on every push to main
- Sets up Python 3.11
- Installs dependencies
- Builds with PyInstaller
- Uploads artifact
- Creates release on tags

**windows-tests.yml**: Runs tests on push and PR
- Sets up Python 3.11
- Installs dependencies + pytest
- Runs full test suite
- Uploads test results

### Releases

To create a release:
1. Tag a commit: `git tag v1.0.0`
2. Push tag: `git push origin v1.0.0`
3. GitHub Actions automatically builds and attaches executable to release

## Troubleshooting

### Sync Not Triggering
- Check source directory is valid and accessible
- Verify file system events are being generated
- Try enabling "Use polling watcher" for network drives
- Check logs in `%LOCALAPPDATA%\DirSync\logs\app.log`

### Files Not Renaming
- Ensure files are CR3 or JPEG (detected by content, not extension)
- Check file is not locked by another process
- Verify you have write permissions in source directory

### Robocopy Errors
- Exit code 8+ indicates errors (see logs)
- Verify destination is accessible
- Check network connectivity for NAS
- Enable FFT for FAT32 compatibility

### Long Path Issues
- Application uses `\\?\` prefix for long path support
- Ensure Windows long path support is enabled (Windows 10 1607+)
- Keep paths under 32,767 characters

### Application Won't Start
- Check Python 3.11+ is installed (if running from source)
- Verify all dependencies are installed: `pip install -r requirements.txt`
- Run with admin privileges if needed
- Check for conflicts on port/resources

## Limitations

- **Windows Only**: Designed specifically for Windows, uses robocopy
- **CR3/JPEG Only**: Only renames CR3 and JPEG files, other file types are synced as-is
- **One-Way Sync**: Only syncs source → destination, not bidirectional
- **No Conflict Resolution**: Last write wins, no merge logic

## License

[Specify your license here]

## Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## Credits

Built with:
- [watchdog](https://github.com/gorakhargosh/watchdog) - File system monitoring
- [pystray](https://github.com/moses-palmer/pystray) - System tray integration
- [Pillow](https://python-pillow.org/) - Image processing
- [tkinter](https://docs.python.org/3/library/tkinter.html) - GUI framework

## Icon

The application uses the custom `SnP-ImagerSyncIcon.png` icon featuring:
- Cloud sync visualization with servers
- Circular arrows indicating synchronization
- Professional blue color scheme

### Icon Customization

To use a different icon:
1. Create or obtain an icon file (`.png` or `.ico`, 32x32 or 64x64 recommended)
2. Place it in `assets/` as `SnP-ImagerSyncIcon.png`, `icon.ico`, or `icon.png`
3. Rebuild the application

The app checks icons in priority order and falls back to a generated icon if none are found.

## Support

For issues, questions, or feature requests:
- Open an issue on [GitHub Issues](https://github.com/username/SnP-ImagerSync/issues)
- Check the logs at `%LOCALAPPDATA%\DirSync\logs\app.log`
- Review test suite for usage examples

