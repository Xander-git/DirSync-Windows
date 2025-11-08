# Assets Directory

This directory contains application assets such as icons.

## Current Icon

The application uses `SnP-ImagerSyncIcon.png` as the default icon, featuring:
- Cloud sync visualization
- Server/database representation
- Circular arrows indicating synchronization
- Blue color scheme

## Custom Icon

To use a different custom icon for the system tray and taskbar:

1. Create or obtain an icon file
   - Recommended sizes: 32x32, 64x64, or multi-resolution
   - Formats: `.ico` (Windows Icon) or `.png` (PNG image)
   - Transparent background recommended

2. Place your icon file in this directory as one of:
   - `SnP-ImagerSyncIcon.png` (highest priority)
   - `icon.ico` (Windows ICO format)
   - `icon.png` (PNG fallback)

3. Rebuild the application:
   ```bash
   build_windows.bat
   ```

The application will check for icons in this order:
1. `SnP-ImagerSyncIcon.png`
2. `icon.ico`
3. `icon.png`
4. Generated default icon (if none found)

## Supported Formats

- `.png` (PNG image) - Recommended for transparency
- `.ico` (Windows Icon) - Native Windows format

## Icon Guidelines

- Keep the design simple and recognizable at small sizes
- Use clear contrast between foreground and background
- Test at multiple sizes (16x16, 32x32, 48x48)
- Consider both light and dark taskbar themes
- Transparent background works best for system tray

