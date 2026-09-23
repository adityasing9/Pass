"""Base platform adapter definition"""
from abc import ABC, abstractmethod
from pathlib import Path


class BasePlatform(ABC):
    """Abstract interface for platform-specific capabilities"""

    @abstractmethod
    def get_platform_name(self) -> str:
        """Return canonical platform name: 'windows', 'linux', 'android', 'darwin'"""
        pass

    @abstractmethod
    def get_default_config_dir(self) -> Path:
        """Return path to store PASS configuration and identity keys"""
        pass

    @abstractmethod
    def get_default_download_dir(self) -> Path:
        """Return default directory to save incoming transferred files"""
        pass

    @abstractmethod
    def get_device_name(self) -> str:
        """Return human-readable device hostname"""
        pass

    @abstractmethod
    def check_environment(self) -> dict:
        """Return dictionary of platform health/environment checks (e.g. storage permissions)"""
        pass

    def resolve_smart_path(self, raw_path: str) -> Path:
        """Resolve friendly shortcuts (e.g. cam:, dl:, dt:, latest) into valid Path"""
        import os
        return Path(os.path.expanduser(raw_path.strip().strip("\"'")))
