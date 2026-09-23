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

    def resolve_smart_path(self, raw_path: str) -> Path:
        raw = raw_path.strip().strip("\"'")
        lower = raw.lower()

        desktop_dir = self.get_default_download_dir()
        downloads_dir = Path.home() / "Downloads"
        docs_dir = Path.home() / "Documents"

        prefix_map = {
            "dt:": desktop_dir,
            "desktop:": desktop_dir,
            "dl:": downloads_dir,
            "downloads:": downloads_dir,
            "doc:": docs_dir,
            "docs:": docs_dir,
        }
        for prefix, target_dir in prefix_map.items():
            if lower.startswith(prefix):
                rel = raw[len(prefix):].lstrip("/\\")
                return target_dir / rel

        # If bare filename, check Desktop or Downloads if not in cwd
        direct_path = Path(os.path.expanduser(raw))
        if not direct_path.exists() and "/" not in raw and "\\" not in raw:
            for candidate_dir in (desktop_dir, downloads_dir):
                candidate = candidate_dir / raw
                if candidate.exists():
                    return candidate

        return direct_path
