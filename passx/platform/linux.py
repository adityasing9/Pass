"""Linux (Ubuntu/Debian) platform adapter"""
import os
import socket
from pathlib import Path
from .base import BasePlatform


class LinuxPlatform(BasePlatform):
    """Linux platform adapter"""

    def get_platform_name(self) -> str:
        return "linux"

    def get_default_config_dir(self) -> Path:
        xdg_config = os.environ.get("XDG_CONFIG_HOME")
        if xdg_config:
            base = Path(xdg_config)
        else:
            base = Path.home() / ".config"
        return base / "pass"

    def get_default_download_dir(self) -> Path:
        xdg_download = os.environ.get("XDG_DOWNLOAD_DIR")
        if xdg_download:
            downloads = Path(xdg_download)
        else:
            downloads = Path.home() / "Downloads"
        return downloads / "PASS"

    def get_device_name(self) -> str:
        name = socket.gethostname().split(".")[0].strip()
        return name if name else "LINUX-DEVICE"

    def check_environment(self) -> dict:
        return {
            "platform": "linux",
            "storage_ok": True,
            "firewall_advice": "Check ufw or iptables if discovery or transfers are blocked on ports 42424/42425.",
        }
