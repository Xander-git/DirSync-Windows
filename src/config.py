"""Configuration management with JSON persistence."""

import json
import os
import logging
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional


logger = logging.getLogger('DirSync-Windows')


@dataclass
class AppConfig:
    """Application configuration settings."""
    # Paths
    source_directory: str = ''
    destination_directory: str = ''
    
    # Options
    mirror_deletions: bool = False
    use_polling: bool = False
    start_minimized: bool = False
    
    # Performance
    threads: int = 16
    debounce_seconds: float = 3.0
    max_latency_seconds: float = 20.0
    sync_rate_seconds: float = 0.0  # 0 = disabled
    
    # Exclusions
    exclude_files: str = '*.tmp;*.bak;~*'
    exclude_dirs: str = '__pycache__;cache'
    
    def to_dict(self) -> dict:
        """Convert config to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'AppConfig':
        """Create config from dictionary."""
        # Filter to only valid fields
        valid_fields = {k: v for k, v in data.items() if hasattr(cls, k)}
        return cls(**valid_fields)
    
    def validate(self) -> tuple[bool, Optional[str]]:
        """
        Validate configuration.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        if self.source_directory and not Path(self.source_directory).exists():
            return False, f'Source directory not found: {self.source_directory}'
        
        if self.threads < 1 or self.threads > 128:
            return False, 'Threads must be between 1 and 128'
        
        if self.debounce_seconds < 0:
            return False, 'Debounce seconds must be non-negative'
        
        if self.max_latency_seconds < 0:
            return False, 'Max latency seconds must be non-negative'
        
        if self.sync_rate_seconds < 0:
            return False, 'Sync rate seconds must be non-negative'
        
        return True, None
    
    def get_exclude_files_list(self) -> list[str]:
        """Parse exclude files string into list."""
        if not self.exclude_files:
            return []
        return [f.strip() for f in self.exclude_files.split(';') if f.strip()]
    
    def get_exclude_dirs_list(self) -> list[str]:
        """Parse exclude directories string into list."""
        if not self.exclude_dirs:
            return []
        return [d.strip() for d in self.exclude_dirs.split(';') if d.strip()]


class ConfigManager:
    """Manages application configuration persistence."""
    
    def __init__(self):
        """Initialize config manager."""
        self.config_dir = self._get_config_dir()
        self.config_file = self.config_dir / 'config.json'
        self.config = AppConfig()
    
    def _get_config_dir(self) -> Path:
        """Get the configuration directory path."""
        if os.name == 'nt':
            # Windows: Use APPDATA
            appdata = os.environ.get('APPDATA', os.path.expanduser('~'))
            config_dir = Path(appdata) / 'DirSync'
        else:
            # Non-Windows fallback for development
            config_dir = Path.home() / '.dirsync'
        
        # Create directory if it doesn't exist
        config_dir.mkdir(parents=True, exist_ok=True)
        
        return config_dir
    
    def load(self) -> AppConfig:
        """
        Load configuration from file.
        
        Returns:
            Loaded configuration, or default if file doesn't exist
        """
        if not self.config_file.exists():
            logger.info('Config file not found, using defaults')
            self.config = AppConfig()
            return self.config
        
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.config = AppConfig.from_dict(data)
            logger.info(f'Configuration loaded from {self.config_file}')
            
            # Validate after loading
            is_valid, error = self.config.validate()
            if not is_valid:
                logger.warning(f'Config validation failed: {error}')
            
            return self.config
            
        except json.JSONDecodeError as e:
            logger.error(f'Failed to parse config file: {e}')
            self.config = AppConfig()
            return self.config
        except Exception as e:
            logger.error(f'Failed to load config: {e}')
            self.config = AppConfig()
            return self.config
    
    def save(self, config: Optional[AppConfig] = None) -> bool:
        """
        Save configuration to file.
        
        Args:
            config: Configuration to save (uses current if None)
            
        Returns:
            True if save successful, False otherwise
        """
        if config is not None:
            self.config = config
        
        # Validate before saving
        is_valid, error = self.config.validate()
        if not is_valid:
            logger.error(f'Cannot save invalid config: {error}')
            return False
        
        try:
            # Ensure directory exists
            self.config_dir.mkdir(parents=True, exist_ok=True)
            
            # Write config
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config.to_dict(), f, indent=2)
            
            logger.info(f'Configuration saved to {self.config_file}')
            return True
            
        except Exception as e:
            logger.error(f'Failed to save config: {e}')
            return False
    
    def reset(self) -> AppConfig:
        """
        Reset configuration to defaults.
        
        Returns:
            Default configuration
        """
        self.config = AppConfig()
        logger.info('Configuration reset to defaults')
        return self.config
    
    def get_config(self) -> AppConfig:
        """Get current configuration."""
        return self.config

