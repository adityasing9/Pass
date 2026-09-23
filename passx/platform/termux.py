"""Android (Termux) platform adapter"""
import os
import socket
from pathlib import Path
from .base import BasePlatform


class TermuxPlatform(BasePlatform):
    """Android Termux platform adapter"""

    def get_platform_name(self) -> str:
        return "android"

    def get_default_config_dir(self) -> Path:
        # On Termux, standard home is /data/data/com.termux/files/home
        return Path.home() / ".config" / "pass"

    def get_default_download_dir(self) -> Path:
        # Check if Android shared storage is mounted via termux-setup-storage
        shared_downloads = Path.home() / "storage" / "downloads" / "PASS"
        if (Path.home() / "storage").exists():
            return shared_downloads
        # Fallback to local home downloads
        return Path.home() / "downloads" / "PASS"

    def get_device_name(self) -> str:
        # On Android, getprop net.hostname or socket.gethostname()
        try:
            name = socket.gethostname().split(".")[0].strip()
            if name and name != "localhost":
                return name
        except Exception:
            pass
        return "TERMUX-DEVICE"

    def check_environment(self) -> dict:
        storage_mounted = (Path.home() / "storage").exists()
        advice = ""
        if not storage_mounted:
            advice = "Run 'termux-setup-storage' to allow PASS to save files directly to your Android Downloads folder."
        return {
            "platform": "android",
            "storage_ok": storage_mounted,
            "firewall_advice": advice,
        }
