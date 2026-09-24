"""Discovery packet models, serialization, and peer representation"""
import json
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

DISCOVERY_MAGIC = b"PASS"
PROTOCOL_VERSION = 1


@dataclass
class PeerInfo:
    """Represents a discovered PASS peer on the network"""
    device_id: str
    device_name: str
    platform: str
    ip: str
    port: int
    fingerprint: str
    capabilities: List[str] = field(default_factory=list)
    last_seen: float = field(default_factory=time.time)
    nickname: Optional[str] = None

    @property
    def display_name(self) -> str:
        if self.nickname and self.nickname.lower() != self.device_name.lower():
            return f"{self.nickname} ({self.device_name})"
        return self.nickname or self.device_name

    def is_expired(self, ttl_seconds: float = 8.0) -> bool:
        return (time.time() - self.last_seen) > ttl_seconds

    def to_dict(self) -> Dict[str, Any]:
        return {
            "device_id": self.device_id,
            "device_name": self.device_name,
            "nickname": self.nickname,
            "display_name": self.display_name,
            "platform": self.platform,
            "ip": self.ip,
            "port": self.port,
            "fingerprint": self.fingerprint,
            "capabilities": self.capabilities,
            "last_seen": self.last_seen,
        }


def encode_discovery_message(msg_type: str, payload: Dict[str, Any]) -> bytes:
    """Encode discovery message with PASS magic header and JSON payload"""
    data = {
        "magic": "PASS",
        "version": PROTOCOL_VERSION,
        "msg_type": msg_type,
        "timestamp": int(time.time()),
        **payload,
    }
    return DISCOVERY_MAGIC + json.dumps(data).encode("utf-8")


def decode_discovery_message(raw_bytes: bytes) -> Optional[Dict[str, Any]]:
    """Decode and validate discovery message from network bytes"""
    if len(raw_bytes) < len(DISCOVERY_MAGIC):
        return None
    if not raw_bytes.startswith(DISCOVERY_MAGIC):
        return None

    try:
        json_str = raw_bytes[len(DISCOVERY_MAGIC):].decode("utf-8")
        data = json.loads(json_str)
        if data.get("magic") != "PASS" or data.get("version") != PROTOCOL_VERSION:
            return None
        return data
    except Exception:
        return None
