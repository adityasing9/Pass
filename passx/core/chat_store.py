"""Persistent chat history storage for PASS"""
import json
import logging
import time
import uuid
from pathlib import Path
from typing import Dict, List, Any, Optional

from passx.core.config import ConfigManager

logger = logging.getLogger(__name__)


class ChatStore:
    """Manages chat messages stored per peer in ~/.pass/chats/<peer_id>.json"""

    def __init__(self, config: ConfigManager):
        self.config = config
        self.chats_dir = self.config.config_dir / "chats"
        self._ensure_dir()

    def _ensure_dir(self) -> None:
        self.chats_dir.mkdir(parents=True, exist_ok=True)

    def _get_chat_file(self, peer_id: str) -> Path:
        safe_id = "".join(c for c in peer_id if c.isalnum() or c in ("-", "_", "."))
        if not safe_id:
            safe_id = "unknown"
        return self.chats_dir / f"{safe_id}.json"

    def save_message(
        self,
        peer_id: str,
        peer_name: str,
        sender: str,  # "me" or "peer"
        text: str,
        msg_type: str = "text",
        file_info: Optional[Dict[str, Any]] = None,
        msg_id: Optional[str] = None,
        timestamp: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Save a new message to the peer's chat file"""
        self._ensure_dir()
        chat_file = self._get_chat_file(peer_id)

        data = self._load_raw(chat_file, peer_id, peer_name)
        if peer_name:
            data["peer_name"] = peer_name

        message_entry = {
            "id": msg_id or str(uuid.uuid4()),
            "sender": sender,
            "sender_name": "You" if sender == "me" else peer_name,
            "text": text,
            "type": msg_type,
            "file_info": file_info,
            "timestamp": timestamp or time.time(),
        }

        data["messages"].append(message_entry)
        # Cap at 500 messages to prevent unbounded disk growth
        if len(data["messages"]) > 500:
            data["messages"] = data["messages"][-500:]

        self._save_raw(chat_file, data)
        return message_entry

    def get_history(self, peer_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieve recent messages for a peer"""
        chat_file = self._get_chat_file(peer_id)
        data = self._load_raw(chat_file, peer_id)
        messages = data.get("messages", [])
        return messages[-limit:]

    def get_last_message(self, peer_id: str) -> Optional[Dict[str, Any]]:
        """Get the most recent message from or to a peer"""
        history = self.get_history(peer_id, limit=1)
        return history[-1] if history else None

    def list_conversations(self) -> List[Dict[str, Any]]:
        """List all conversations sorted by latest activity"""
        self._ensure_dir()
        convs = []
        for file in self.chats_dir.glob("*.json"):
            try:
                with open(file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                msgs = data.get("messages", [])
                last_msg = msgs[-1] if msgs else None
                convs.append({
                    "peer_id": data.get("peer_id", file.stem),
                    "peer_name": data.get("peer_name", file.stem),
                    "message_count": len(msgs),
                    "last_message": last_msg.get("text", "") if last_msg else "",
                    "last_timestamp": last_msg.get("timestamp", 0) if last_msg else 0,
                    "last_sender": last_msg.get("sender", "") if last_msg else "",
                })
            except Exception as e:
                logger.debug(f"Error loading chat file {file}: {e}")
        convs.sort(key=lambda x: x["last_timestamp"], reverse=True)
        return convs

    def clear_history(self, peer_id: str) -> None:
        """Clear conversation history with a peer"""
        chat_file = self._get_chat_file(peer_id)
        if chat_file.exists():
            try:
                chat_file.unlink()
            except Exception:
                pass

    def _load_raw(self, chat_file: Path, peer_id: str, peer_name: str = "") -> Dict[str, Any]:
        if not chat_file.exists():
            return {
                "peer_id": peer_id,
                "peer_name": peer_name or peer_id,
                "created_at": time.time(),
                "messages": [],
            }
        try:
            with open(chat_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {
                "peer_id": peer_id,
                "peer_name": peer_name or peer_id,
                "created_at": time.time(),
                "messages": [],
            }

    def _save_raw(self, chat_file: Path, data: Dict[str, Any]) -> None:
        temp_file = chat_file.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        temp_file.replace(chat_file)
