"""High-level discovery engine coordinator"""
import logging
import time
from typing import Callable, List, Optional
from passx.core.config import ConfigManager
from passx.core.identity import DeviceIdentity
from .announcer import Announcer
from .beacon import PeerInfo
from .listener import Listener

logger = logging.getLogger(__name__)


class DiscoveryEngine:
    """Manages discovery announcer and listener lifecycles"""

    def __init__(
        self,
        config: ConfigManager,
        identity: DeviceIdentity,
        on_peer_discovered: Optional[Callable[[PeerInfo], None]] = None,
    ):
        self.config = config
        self.identity = identity
        self.on_peer_discovered = on_peer_discovered

        self.announcer = Announcer(
            identity=self.identity,
            discovery_port=self.config.discovery_port,
            transfer_port=self.config.transfer_port,
            multicast_group=self.config.multicast_group,
        )

        self.listener = Listener(
            identity=self.identity,
            discovery_port=self.config.discovery_port,
            multicast_group=self.config.multicast_group,
            on_probe_callback=self._handle_probe,
            on_peer_updated_callback=self.on_peer_discovered,
        )

        self.running = False

    def _handle_probe(self, sender_ip: str, sender_port: int) -> None:
        """Respond immediately to an incoming active probe"""
        self.announcer.send_unicast_beacon(sender_ip, self.config.discovery_port)

    def start(self) -> None:
        """Start discovery services"""
        if self.running:
            return
        self.listener.start()
        self.announcer.start()
        self.running = True

    def stop(self) -> None:
        """Stop discovery services"""
        if not self.running:
            return
        self.announcer.stop()
        self.listener.stop()
        self.running = False

    def get_peers(self) -> List[PeerInfo]:
        """Return all active nearby peers with nicknames attached"""
        peers = self.listener.get_peers()
        try:
            from passx.core.aliases import AliasManager
            alias_mgr = AliasManager(self.config)
            for p in peers:
                p.nickname = alias_mgr.get_alias(p.device_id) or alias_mgr.get_alias(p.device_name) or alias_mgr.get_alias(p.ip)
        except Exception as e:
            logger.debug(f"Error attaching aliases to peers: {e}")
        return peers

    def find_peer(self, identifier: str) -> Optional[PeerInfo]:
        """Find peer by device ID, friendly name, IP, or nickname"""
        peers = self.get_peers()
        ident_lower = identifier.lower().strip()
        for peer in peers:
            if peer.device_id.lower() == ident_lower or peer.device_id.lower().startswith(ident_lower):
                return peer
            if peer.device_name.lower() == ident_lower:
                return peer
            if peer.nickname and peer.nickname.lower() == ident_lower:
                return peer
            if peer.ip == ident_lower:
                return peer
        return None

    def scan(self, timeout: float = 2.0) -> List[PeerInfo]:
        """Send an active probe and wait for nearby peers to respond"""
        was_running = self.running
        if not was_running:
            self.start()

        self.announcer.send_probe()
        time.sleep(timeout)
        peers = self.get_peers()

        if not was_running:
            self.stop()
        return peers

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
