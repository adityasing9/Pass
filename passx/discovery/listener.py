"""UDP discovery listener and peer registry manager"""
import logging
import socket
import threading
import time
from typing import Callable, Dict, List, Optional
from passx.core.identity import DeviceIdentity
from passx.network.socket_utils import create_udp_listener_socket
from .beacon import PeerInfo, decode_discovery_message

logger = logging.getLogger(__name__)


class Listener:
    """Listens for discovery broadcasts and maintains nearby peer cache"""

    def __init__(
        self,
        identity: DeviceIdentity,
        discovery_port: int,
        multicast_group: Optional[str] = None,
        on_probe_callback: Optional[Callable[[str, int], None]] = None,
        on_peer_updated_callback: Optional[Callable[[PeerInfo], None]] = None,
    ):
        self.identity = identity
        self.discovery_port = discovery_port
        self.multicast_group = multicast_group
        self.on_probe_callback = on_probe_callback
        self.on_peer_updated_callback = on_peer_updated_callback

        self.running = False
        self._thread: Optional[threading.Thread] = None
        self._sock: Optional[socket.socket] = None
        self._peers: Dict[str, PeerInfo] = {}
        self._lock = threading.Lock()

    def start(self) -> None:
        """Start listening for discovery broadcasts"""
        if self.running:
            return
        self.running = True
        self._sock = create_udp_listener_socket(self.discovery_port, self.multicast_group)
        self._sock.settimeout(1.0)
        self._thread = threading.Thread(target=self._run_loop, name="passx-listener", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop listening"""
        if not self.running:
            return
        self.running = False
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None

    def _run_loop(self) -> None:
        while self.running:
            try:
                data, addr = self._sock.recvfrom(4096)
                self._handle_packet(data, addr)
            except socket.timeout:
                pass
            except Exception as e:
                if self.running:
                    logger.debug(f"Error reading discovery socket: {e}")
            self.prune_expired()

    def _handle_packet(self, data: bytes, addr: tuple) -> None:
        msg = decode_discovery_message(data)
        if not msg:
            return

        msg_type = msg.get("msg_type")
        sender_ip = addr[0]

        if msg_type == "BEACON":
            dev_id = msg.get("device_id")
            # Ignore self
            if not dev_id or dev_id == self.identity.device_id:
                return

            peer = PeerInfo(
                device_id=dev_id,
                device_name=msg.get("device_name", "Unknown"),
                platform=msg.get("platform", "unknown"),
                ip=sender_ip,
                port=int(msg.get("port", 42425)),
                fingerprint=msg.get("fingerprint", ""),
                capabilities=msg.get("capabilities", []),
                last_seen=time.time(),
            )

            with self._lock:
                self._peers[dev_id] = peer

            if self.on_peer_updated_callback:
                try:
                    self.on_peer_updated_callback(peer)
                except Exception:
                    pass

        elif msg_type == "PROBE":
            sender_id = msg.get("sender_id")
            if sender_id and sender_id != self.identity.device_id:
                if self.on_probe_callback:
                    try:
                        self.on_probe_callback(sender_ip, addr[1])
                    except Exception:
                        pass

        elif msg_type == "GOODBYE":
            dev_id = msg.get("device_id")
            if dev_id and dev_id != self.identity.device_id:
                with self._lock:
                    self._peers.pop(dev_id, None)

    def prune_expired(self, ttl_seconds: float = 8.0) -> None:
        """Remove peers that have not sent a heartbeat within TTL"""
        with self._lock:
            expired = [dev_id for dev_id, p in self._peers.items() if p.is_expired(ttl_seconds)]
            for dev_id in expired:
                del self._peers[dev_id]

    def get_peers(self) -> List[PeerInfo]:
        """Return list of active, unexpired peers"""
        self.prune_expired()
        with self._lock:
            return list(self._peers.values())

    def find_peer(self, identifier: str) -> Optional[PeerInfo]:
        """Find peer by full or partial UUID or friendly device name or IP (case-insensitive)"""
        self.prune_expired()
        ident_lower = identifier.lower().strip()
        with self._lock:
            for peer in self._peers.values():
                if peer.device_id.lower() == ident_lower or peer.device_id.lower().startswith(ident_lower):
                    return peer
                if peer.device_name.lower() == ident_lower:
                    return peer
                if peer.ip == ident_lower:
                    return peer
        return None
