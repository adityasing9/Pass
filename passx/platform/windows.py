"""Windows platform adapter"""
import os
import socket
from pathlib import Path
from .base import BasePlatform


class WindowsPlatform(BasePlatform):
    """Windows 10/11 platform adapter"""

    def get_platform_name(self) -> str:
        return "windows"

    def get_default_config_dir(self) -> Path:
        appdata = os.environ.get("APPDATA")
        if appdata:
            base = Path(appdata)
        else:
            base = Path.home() / "AppData" / "Roaming"
        return base / "pass"

    def get_default_download_dir(self) -> Path:
        user_profile = os.environ.get("USERPROFILE")
        if user_profile:
            desktop = Path(user_profile) / "Desktop"
        else:
            desktop = Path.home() / "Desktop"
        return desktop

    def get_device_name(self) -> str:
        name = socket.gethostname().split(".")[0].strip()
        return name if name else "WINDOWS-PC"

    def check_environment(self) -> dict:
        return {
            "platform": "windows",
            "storage_ok": True,
            "firewall_advice": "Ensure UDP port 42424 and TCP port 42425 are permitted in Windows Defender Firewall.",
        }
