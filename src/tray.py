"""System tray integration using pystray."""

import logging
from pathlib import Path
from typing import Optional, Callable
import pystray
from PIL import Image, ImageDraw
import threading


logger = logging.getLogger('DirSync-Windows')


def create_icon_image(color: tuple[int, int, int, int] = (0, 120, 215, 255)) -> Image.Image:
    """
    Create a simple colored icon image.
    
    Args:
        color: RGBA color tuple (default: Windows blue)
        
    Returns:
        PIL Image for the tray icon
    """
    # Create 64x64 icon
    width = 64
    height = 64
    image = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    
    # Draw a circle with the specified color
    margin = 4
    draw.ellipse(
        [margin, margin, width - margin, height - margin],
        fill=color,
        outline=(255, 255, 255, 255),
        width=2
    )
    
    # Draw an "S" for Sync in the middle
    font_size = width // 2
    text = "S"
    # Simple centered text (rough positioning)
    text_bbox = draw.textbbox((0, 0), text)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    text_x = (width - text_width) // 2
    text_y = (height - text_height) // 2 - 5
    
    draw.text((text_x, text_y), text, fill=(255, 255, 255, 255))
    
    return image


def load_icon() -> Image.Image:
    """
    Load icon from assets directory or create default.
    
    Returns:
        PIL Image for the tray icon
    """
    # Try to load custom PNG icon first
    icon_paths = [
        Path('assets/SnP-ImagerSyncIcon.png'),
        Path('assets/icon.ico'),
        Path('assets/icon.png')
    ]
    
    for icon_path in icon_paths:
        if icon_path.exists():
            try:
                img = Image.open(icon_path)
                # Convert to RGBA if needed
                if img.mode != 'RGBA':
                    img = img.convert('RGBA')
                logger.info(f'Loaded custom icon from {icon_path}')
                return img
            except Exception as e:
                logger.warning(f'Failed to load icon from {icon_path}: {e}')
    
    # Fall back to generated icon
    logger.info('Using generated default icon')
    return create_icon_image()


class TrayIcon:
    """System tray icon with menu."""
    
    def __init__(
        self,
        on_show_gui: Optional[Callable[[], None]] = None,
        on_start_sync: Optional[Callable[[], None]] = None,
        on_stop_sync: Optional[Callable[[], None]] = None,
        on_exit: Optional[Callable[[], None]] = None
    ):
        """
        Initialize tray icon.
        
        Args:
            on_show_gui: Callback to show GUI
            on_start_sync: Callback to start sync
            on_stop_sync: Callback to stop sync
            on_exit: Callback to exit application
        """
        self.on_show_gui = on_show_gui
        self.on_start_sync = on_start_sync
        self.on_stop_sync = on_stop_sync
        self.on_exit = on_exit
        
        self.icon: Optional[pystray.Icon] = None
        self.thread: Optional[threading.Thread] = None
        self.running = False
    
    def _create_menu(self) -> pystray.Menu:
        """Create the tray menu."""
        return pystray.Menu(
            pystray.MenuItem(
                'Open GUI',
                self._handle_show_gui,
                default=True
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                'Start Sync',
                self._handle_start_sync
            ),
            pystray.MenuItem(
                'Stop Sync',
                self._handle_stop_sync
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                'Exit',
                self._handle_exit
            )
        )
    
    def _handle_show_gui(self, icon, item):
        """Handle show GUI menu item."""
        if self.on_show_gui:
            self.on_show_gui()
    
    def _handle_start_sync(self, icon, item):
        """Handle start sync menu item."""
        if self.on_start_sync:
            self.on_start_sync()
    
    def _handle_stop_sync(self, icon, item):
        """Handle stop sync menu item."""
        if self.on_stop_sync:
            self.on_stop_sync()
    
    def _handle_exit(self, icon, item):
        """Handle exit menu item."""
        if self.on_exit:
            self.on_exit()
    
    def start(self):
        """Start the tray icon in a separate thread."""
        if self.running:
            logger.warning('Tray icon already running')
            return
        
        self.running = True
        
        # Create icon
        image = load_icon()
        menu = self._create_menu()
        
        self.icon = pystray.Icon(
            'DirSync-Windows',
            image,
            'DirSync-Windows',
            menu
        )
        
        # Run in separate thread
        self.thread = threading.Thread(
            target=self._run,
            name='TrayIcon',
            daemon=True
        )
        self.thread.start()
        
        logger.info('Tray icon started')
    
    def _run(self):
        """Run the tray icon (blocking)."""
        try:
            self.icon.run()
        except Exception as e:
            logger.error(f'Tray icon error: {e}')
    
    def stop(self):
        """Stop the tray icon."""
        if not self.running:
            return
        
        logger.info('Stopping tray icon...')
        self.running = False
        
        if self.icon:
            try:
                self.icon.stop()
            except Exception as e:
                logger.warning(f'Error stopping tray icon: {e}')
        
        logger.info('Tray icon stopped')
    
    def update_tooltip(self, text: str):
        """
        Update the tray icon tooltip.
        
        Args:
            text: New tooltip text
        """
        if self.icon:
            self.icon.title = text
    
    def show_notification(self, title: str, message: str):
        """
        Show a notification (if supported).
        
        Args:
            title: Notification title
            message: Notification message
        """
        if self.icon and hasattr(self.icon, 'notify'):
            try:
                self.icon.notify(message, title)
            except Exception as e:
                logger.warning(f'Failed to show notification: {e}')

