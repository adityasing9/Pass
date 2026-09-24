"""Mutual pairing client for PASS devices"""
import logging
import socket
from typing import Tuple

from passx.core.config import ConfigManager
from passx.core.identity import DeviceIdentity
from passx.core.trust import TrustManager
from passx.network.socket_utils import optimize_tcp_socket
from passx.network.tls_context import create_client_ssl_context
from passx.protocol.frames import send_control_msg, recv_control_msg
from passx.protocol.messages import make_pair_request, MSG_PAIR_RESP

logger = logging.getLogger(__name__)


def pair_with_peer(
    peer_ip: str,
    peer_port: int,
    config: ConfigManager,
    identity: DeviceIdentity,
    trust_manager: TrustManager,
    timeout: float = 8.0,
) -> Tuple[bool, str]:
    """
    Initiate mutual TLS pairing handshake with a remote PASS device.
    Exchanges cryptographic certificates and fingerprints so future transfers auto-accept.
    """
    raw_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    optimize_tcp_socket(raw_sock)
    raw_sock.settimeout(timeout)

    try:
        raw_sock.connect((peer_ip, peer_port))
        ssl_ctx = create_client_ssl_context()
        ssl_sock = ssl_ctx.wrap_socket(raw_sock, server_hostname=None)
    except Exception as e:
        raw_sock.close()
        return False, f"Failed to connect to {peer_ip}:{peer_port}: {e}"

    try:
        # Send PAIR_REQUEST
        pair_req = make_pair_request(
            device_id=identity.device_id,
            device_name=identity.device_name,
            fingerprint=identity.fingerprint,
        )
        send_control_msg(ssl_sock, pair_req)

        # Receive PAIR_RESP
        resp = recv_control_msg(ssl_sock)
        if resp.get("action") != MSG_PAIR_RESP:
            return False, f"Unexpected response from peer: {resp.get('action')}"

        if resp.get("status") != "OK":
            return False, resp.get("message", "Pairing was declined by the remote device")

        peer_id = resp.get("device_id")
        peer_name = resp.get("device_name", "Remote Device")
        peer_fp = resp.get("fingerprint")

        if not peer_id or not peer_fp:
            return False, "Invalid pairing credentials received from remote device"

        # Save to trust store
        trust_manager.trust_device(peer_id, peer_name, peer_fp)
        return True, f"Successfully paired with '{peer_name}' ({peer_fp[:16]}...)"

    except Exception as e:
        return False, f"Pairing handshake failed: {e}"
    finally:
        try:
            ssl_sock.close()
        except Exception:
            pass
