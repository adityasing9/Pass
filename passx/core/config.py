"""Configuration manager for PASS"""
import json
import os
from pathlib import Path
from typing import Optional, Dict, Any
from passx.platform import current_platform


DEFAULT_DISCOVERY_PORT = 42424
DEFAULT_TRANSFER_PORT = 42425
DEFAULT_MULTICAST_GROUP = "239.255.77.88"


class ConfigManager:
    """Manages PASS persistent configuration"""

    def __init__(self, config_dir: Optional[Path] = None):
        self.config_dir = Path(config_dir) if config_dir else current_platform.get_default_config_dir()
        self.config_file = self.config_dir / "config.json"
        self._ensure_dir()
        self.data: Dict[str, Any] = self._load()

    def _ensure_dir(self) -> None:
        self.config_dir.mkdir(parents=True, exist_ok=True)

    def _get_defaults(self) -> Dict[str, Any]:
        return {
            "device_name": current_platform.get_device_name(),
            "download_dir": str(current_platform.get_default_download_dir()),
            "discovery_port": DEFAULT_DISCOVERY_PORT,
            "transfer_port": DEFAULT_TRANSFER_PORT,
            "multicast_group": DEFAULT_MULTICAST_GROUP,
            "auto_accept_trusted": True,
            "chunk_size": 1024 * 1024,  # 1 MB high-throughput streaming chunks
        }

    def _load(self) -> Dict[str, Any]:
        defaults = self._get_defaults()
        if not self.config_file.exists():
            self._save(defaults)
            return defaults
        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                defaults.update(loaded)
                return defaults
        except Exception:
            return defaults

    def _save(self, data: Dict[str, Any]) -> None:
        self._ensure_dir()
        temp_file = self.config_file.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        temp_file.replace(self.config_file)

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.data[key] = value
        self._save(self.data)

    @property
    def device_name(self) -> str:
        return self.data.get("device_name", current_platform.get_device_name())

    @device_name.setter
    def device_name(self, value: str) -> None:
        self.set("device_name", value.strip())

    @property
    def download_dir(self) -> Path:
        raw = self.data.get("download_dir", str(current_platform.get_default_download_dir()))
        path = Path(os.path.expanduser(raw))
        path.mkdir(parents=True, exist_ok=True)
        return path

    @download_dir.setter
    def download_dir(self, value: Path) -> None:
        self.set("download_dir", str(value))

    @property
    def discovery_port(self) -> int:
        return int(self.data.get("discovery_port", DEFAULT_DISCOVERY_PORT))

    @property
    def transfer_port(self) -> int:
        return int(self.data.get("transfer_port", DEFAULT_TRANSFER_PORT))

    @property
    def multicast_group(self) -> str:
        return str(self.data.get("multicast_group", DEFAULT_MULTICAST_GROUP))

    @property
    def chunk_size(self) -> int:
        return int(self.data.get("chunk_size", 256 * 1024))
