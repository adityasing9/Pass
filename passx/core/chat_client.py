"""Chat client to send instant messages over TLS to PASS peers"""
import logging
import socket
import time
import uuid
from typing import Tuple, Optional, Dict, Any

from passx.core.config import ConfigManager
from passx.core.identity import DeviceIdentity
from passx.core.trust import TrustManager
from passx.core.chat_store import ChatStore
from passx.network.socket_utils import optimize_tcp_socket
from passx.network.tls_context import create_client_ssl_context
from passx.protocol.frames import send_control_msg, recv_control_msg
from passx.protocol.messages import make_chat_msg, MSG_CHAT_ACK

logger = logging.getLogger(__name__)


def send_chat(
    peer_ip: str,
    peer_port: int,
    text: str,
    config: ConfigManager,
    identity: DeviceIdentity,
    trust_manager: TrustManager,
    peer_id: Optional[str] = None,
    peer_name: Optional[str] = None,
    msg_type: str = "text",
    file_info: Optional[Dict[str, Any]] = None,
    timeout: float = 6.0,
) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Send an encrypted chat message to a PASS peer over TLS.
    Saves the outgoing message to the local ChatStore upon successful delivery.
    Returns (success, status_or_error_msg, saved_message_dict).
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
        return False, f"Could not connect to {peer_ip}:{peer_port}: {e}", None

    try:
        msg_id = str(uuid.uuid4())
        msg = make_chat_msg(
            sender_id=identity.device_id,
            sender_name=identity.device_name,
            fingerprint=identity.fingerprint,
            text=text,
            msg_id=msg_id,
            msg_type=msg_type,
            file_info=file_info,
        )
        send_control_msg(ssl_sock, msg)

        resp = recv_control_msg(ssl_sock)
        if resp.get("action") != MSG_CHAT_ACK:
            return False, f"Unexpected response from peer: {resp.get('action')}", None

        resp_peer_id = resp.get("device_id") or peer_id or peer_ip
        resp_peer_name = resp.get("device_name") or peer_name or peer_ip

        # Save to local ChatStore
        chat_store = ChatStore(config)
        saved = chat_store.save_message(
            peer_id=resp_peer_id,
            peer_name=resp_peer_name,
            sender="me",
            text=text,
            msg_type=msg_type,
            file_info=file_info,
            msg_id=msg_id,
        )

        return True, "Delivered", saved

    except Exception as e:
        return False, f"Delivery failed: {e}", None
    finally:
        try:
            ssl_sock.close()
        except Exception:
            pass
