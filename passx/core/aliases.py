"""Device nickname and alias management for PASS"""
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any

from passx.core.config import ConfigManager

logger = logging.getLogger(__name__)


class AliasManager:
    """Manages friendly nicknames for local and remote PASS devices"""

    def __init__(self, config: ConfigManager):
        self.config = config
        self.alias_file = self.config.config_dir / "aliases.json"
        self._ensure_file()

    def _ensure_file(self) -> None:
        if not self.alias_file.exists():
            with open(self.alias_file, "w", encoding="utf-8") as f:
                json.dump({}, f, indent=2)

    def _load(self) -> Dict[str, Dict[str, Any]]:
        try:
            with open(self.alias_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save(self, data: Dict[str, Dict[str, Any]]) -> None:
        temp_file = self.alias_file.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        temp_file.replace(self.alias_file)

    def set_alias(
        self,
        target: str,
        nickname: str,
        device_id: Optional[str] = None,
        fingerprint: Optional[str] = None,
        ip: Optional[str] = None,
    ) -> None:
        """
        Assign a nickname to a remote device.
        target can be a device_id, device_name, or IP.
        """
        aliases = self._load()
        key = (device_id or target).strip()
        resolved_ip = (ip or "").strip()
        if not resolved_ip and target.count(".") == 3:
            resolved_ip = target.strip()

        aliases[key] = {
            "key": key,
            "nickname": nickname.strip(),
            "target": target.strip(),
            "ip": resolved_ip,
            "device_id": (device_id or "").strip(),
            "fingerprint": (fingerprint or "").strip(),
        }
        self._save(aliases)

        # Update ChatStore peer_name if a conversation exists for this device
        try:
            from passx.core.chat_store import ChatStore
            chat_store = ChatStore(self.config)
            chat_file = chat_store._get_chat_file(device_id or target)
            if chat_file.exists():
                data = chat_store._load_raw(chat_file, device_id or target)
                data["peer_name"] = nickname.strip()
                chat_store._save_raw(chat_file, data)
        except Exception as e:
            logger.debug(f"Failed to update chat store alias: {e}")

    def get_alias(self, target: str) -> Optional[str]:
        """Get the nickname for a target by device_id, name, or IP"""
        if not target:
            return None
        target_lower = target.lower().strip()
        aliases = self._load()

        if target in aliases:
            return aliases[target].get("nickname")

        for entry in aliases.values():
            if entry.get("device_id", "").lower() == target_lower:
                return entry.get("nickname")
            if entry.get("target", "").lower() == target_lower:
                return entry.get("nickname")
            if entry.get("key", "").lower() == target_lower:
                return entry.get("nickname")

        return None

    def get_display_name(self, device_id: str, original_name: str) -> str:
        """Returns 'Nickname (Original)' or 'Nickname' if set, otherwise original_name"""
        alias = self.get_alias(device_id) or self.get_alias(original_name)
        if alias:
            if alias.lower() != original_name.lower():
                return f"{alias} ({original_name})"
            return alias
        return original_name

    def resolve_target(self, name_or_alias: str) -> Optional[Dict[str, Any]]:
        """
        Given a nickname or name, finds the underlying device details.
        Returns dict with device_id, target, nickname or None.
        """
        if not name_or_alias:
            return None
        query_lower = name_or_alias.lower().strip()
        aliases = self._load()

        for entry in aliases.values():
            if entry.get("nickname", "").lower() == query_lower:
                return entry
            if entry.get("target", "").lower() == query_lower:
                return entry
            if entry.get("device_id", "").lower() == query_lower:
                return entry

        return None

    def remove_alias(self, target_or_nickname: str) -> bool:
        """Remove a nickname. Returns True if removed."""
        aliases = self._load()
        to_del = None
        q_lower = target_or_nickname.lower().strip()

        for key, entry in aliases.items():
            if (
                key.lower() == q_lower
                or entry.get("nickname", "").lower() == q_lower
                or entry.get("target", "").lower() == q_lower
                or entry.get("device_id", "").lower() == q_lower
            ):
                to_del = key
                break

        if to_del and to_del in aliases:
            del aliases[to_del]
            self._save(aliases)
            return True
        return False

    def list_aliases(self) -> List[Dict[str, Any]]:
        """List all nicknames"""
        return list(self._load().values())
