"""UDP beacon announcer and probe dispatcher"""
import logging
import socket
import threading
import time
from typing import Optional, Set
from passx.core.identity import DeviceIdentity
from passx.network.interfaces import get_all_broadcast_addresses
from passx.network.socket_utils import create_broadcast_socket
from passx.platform import current_platform
from .beacon import encode_discovery_message

logger = logging.getLogger(__name__)


class Announcer:
    """Sends periodic discovery beacons and responds to probes"""

    def __init__(self, identity: DeviceIdentity, discovery_port: int, transfer_port: int, multicast_group: Optional[str] = None):
        self.identity = identity
        self.discovery_port = discovery_port
        self.transfer_port = transfer_port
        self.multicast_group = multicast_group
        
        self.running = False
        self._thread: Optional[threading.Thread] = None
        self._sock: Optional[socket.socket] = None

    def _get_beacon_payload(self) -> dict:
        return {
            "device_id": self.identity.device_id,
            "device_name": self.identity.device_name,
            "platform": current_platform.get_platform_name(),
            "port": self.transfer_port,
            "fingerprint": self.identity.fingerprint,
            "capabilities": ["tls1.3", "resume", "dir_transfer"],
        }

    def start(self) -> None:
        """Start the background announcer thread"""
        if self.running:
            return
        self.running = True
        self._sock = create_broadcast_socket()
        self._thread = threading.Thread(target=self._run_loop, name="passx-announcer", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop announcer and send goodbye message"""
        if not self.running:
            return
        self.running = False
        self.send_goodbye()
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None

    def _run_loop(self) -> None:
        # Send initial beacon immediately
        self.broadcast_beacon()
        while self.running:
            time.sleep(2.5)
            if not self.running:
                break
            self.broadcast_beacon()

    def broadcast_beacon(self) -> None:
        """Broadcast beacon to all local subnet broadcast addresses and multicast group"""
        if not self._sock:
            return
        msg = encode_discovery_message("BEACON", self._get_beacon_payload())
        targets: Set[str] = get_all_broadcast_addresses()
        if self.multicast_group:
            targets.add(self.multicast_group)

        for target_ip in targets:
            try:
                self._sock.sendto(msg, (target_ip, self.discovery_port))
            except Exception as e:
                logger.debug(f"Failed to send beacon to {target_ip}:{self.discovery_port}: {e}")

    def send_unicast_beacon(self, target_ip: str, target_port: int) -> None:
        """Send a single beacon directly to a peer IP (e.g. in reply to a PROBE)"""
        if not self._sock:
            return
        msg = encode_discovery_message("BEACON", self._get_beacon_payload())
        try:
            self._sock.sendto(msg, (target_ip, target_port))
        except Exception as e:
            logger.debug(f"Failed to send unicast beacon to {target_ip}:{target_port}: {e}")

    def send_probe(self) -> None:
        """Send active PROBE broadcast to query all active PASS devices immediately"""
        if not self._sock:
            return
        payload = {"sender_id": self.identity.device_id}
        msg = encode_discovery_message("PROBE", payload)
        targets: Set[str] = get_all_broadcast_addresses()
        if self.multicast_group:
            targets.add(self.multicast_group)

        for target_ip in targets:
            try:
                self._sock.sendto(msg, (target_ip, self.discovery_port))
            except Exception as e:
                logger.debug(f"Failed to send probe to {target_ip}: {e}")

    def send_goodbye(self) -> None:
        """Send GOODBYE packet to announce node departure"""
        if not self._sock:
            return
        payload = {"device_id": self.identity.device_id}
        msg = encode_discovery_message("GOODBYE", payload)
        targets: Set[str] = get_all_broadcast_addresses()
        for target_ip in targets:
            try:
                self._sock.sendto(msg, (target_ip, self.discovery_port))
            except Exception:
                pass
