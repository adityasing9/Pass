"""Platform adapter factory and auto-detection"""
import os
import sys
from .base import BasePlatform
from .windows import WindowsPlatform
from .linux import LinuxPlatform
from .termux import TermuxPlatform


def is_termux() -> bool:
    """Detect if running inside Android Termux"""
    prefix = os.environ.get("PREFIX", "")
    return "com.termux" in prefix or "TERMUX_VERSION" in os.environ


def get_platform_adapter() -> BasePlatform:
    """Detect host OS and return appropriate PlatformAdapter instance"""
    if is_termux():
        return TermuxPlatform()
    if sys.platform.startswith("win"):
        return WindowsPlatform()
    if sys.platform.startswith("linux"):
        return LinuxPlatform()
    # Default fallback to LinuxPlatform for generic Unix/POSIX/macOS
    return LinuxPlatform()


# Global singleton instance
current_platform: BasePlatform = get_platform_adapter()
