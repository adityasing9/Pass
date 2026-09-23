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

    def resolve_smart_path(self, raw_path: str) -> Path:
        raw = raw_path.strip().strip("\"'")
        lower = raw.lower()

        cam_dirs = [
            Path.home() / "storage" / "dcim" / "Camera",
            Path.home() / "storage" / "shared" / "DCIM" / "Camera",
        ]
        cam_dir = next((d for d in cam_dirs if d.exists()), cam_dirs[0])
        dl_dir = Path.home() / "storage" / "downloads"
        doc_dir = Path.home() / "storage" / "shared" / "Documents"

        # Check 'latest' / 'latest:photo' / 'cam:latest'
        if lower in ("latest", "latest:photo", "cam:latest", "camera:latest"):
            if cam_dir.exists():
                files = [f for f in cam_dir.iterdir() if f.is_file()]
                if files:
                    files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
                    return files[0]

        if lower in ("dl:latest", "downloads:latest"):
            if dl_dir.exists():
                files = [f for f in dl_dir.iterdir() if f.is_file()]
                if files:
                    files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
                    return files[0]

        # Prefixes: cam:, camera:, dl:, downloads:, doc:, docs:
        prefix_map = {
            "cam:": cam_dir,
            "camera:": cam_dir,
            "dl:": dl_dir,
            "downloads:": dl_dir,
            "doc:": doc_dir,
            "docs:": doc_dir,
        }
        for prefix, target_dir in prefix_map.items():
            if lower.startswith(prefix):
                rel = raw[len(prefix):].lstrip("/\\")
                return target_dir / rel

        # If a plain filename was passed, search common Android folders automatically
        direct_path = Path(os.path.expanduser(raw))
        if not direct_path.exists() and "/" not in raw and "\\" not in raw:
            for candidate_dir in (cam_dir, dl_dir, doc_dir):
                candidate = candidate_dir / raw
                if candidate.exists():
                    return candidate

        return direct_path
