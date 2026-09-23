"""Device trust store management"""
import datetime
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from passx.core.config import ConfigManager


class TrustManager:
    """Manages locally trusted PASS devices"""

    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self.trust_file = config_manager.config_dir / "trusted_devices.json"
        self._ensure_file()

    def _ensure_file(self) -> None:
        if not self.trust_file.exists():
            with open(self.trust_file, "w", encoding="utf-8") as f:
                json.dump({}, f, indent=2)

    def _load(self) -> Dict[str, Dict[str, Any]]:
        try:
            with open(self.trust_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save(self, data: Dict[str, Dict[str, Any]]) -> None:
        temp_file = self.trust_file.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        temp_file.replace(self.trust_file)

    def is_trusted(self, device_id: str, fingerprint: str) -> bool:
        """Returns True only if device_id is in trust store AND fingerprint matches"""
        devices = self._load()
        if device_id in devices:
            entry = devices[device_id]
            expected = entry.get("fingerprint", "").lower().strip()
            actual = fingerprint.lower().strip()
            return expected == actual
        return False

    def trust_device(self, device_id: str, device_name: str, fingerprint: str) -> None:
        """Add or update trusted device"""
        devices = self._load()
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        devices[device_id] = {
            "device_id": device_id,
            "device_name": device_name,
            "fingerprint": fingerprint.lower().strip(),
            "trusted_at": now,
            "last_seen": now,
        }
        self._save(devices)

    def untrust_device(self, device_id_or_name: str) -> bool:
        """Remove a device from trusted list by ID or friendly name. Returns True if removed."""
        devices = self._load()
        target_id = None
        for dev_id, info in devices.items():
            if dev_id == device_id_or_name or info.get("device_name", "").lower() == device_id_or_name.lower():
                target_id = dev_id
                break

        if target_id and target_id in devices:
            del devices[target_id]
            self._save(devices)
            return True
        return False

    def list_trusted(self) -> List[Dict[str, Any]]:
        """Return list of all trusted devices"""
        devices = self._load()
        return list(devices.values())
