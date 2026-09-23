"""Direct P2P TLS transfer sender client"""
import hashlib
import logging
import socket
import time
from pathlib import Path
from typing import Callable, Dict, Optional, Any

from passx.core.config import ConfigManager
from passx.core.identity import DeviceIdentity
from passx.core.trust import TrustManager
from passx.network.socket_utils import optimize_tcp_socket
from passx.network.tls_context import create_client_ssl_context, verify_peer_fingerprint
from passx.protocol.frames import (
    FRAME_TYPE_DATA,
    FRAME_TYPE_CONTROL,
    recv_control_msg,
    send_control_msg,
    send_frame,
    ProtocolError,
)
from passx.protocol.messages import (
    MSG_HANDSHAKE_RESP,
    MSG_TRANSFER_DECISION,
    MSG_FILE_VERIFIED,
    make_handshake_init,
    make_file_start,
    make_file_end,
    make_transfer_complete,
)
from .manifest import TransferManifest
from .sanitizer import SecurityError

logger = logging.getLogger(__name__)


class TransferRejected(Exception):
    pass


class IntegrityError(Exception):
    pass


class PeerVerificationError(Exception):
    pass


class TransferSender:
    """Connects to a remote PASS receiver and streams files over TLS"""

    def __init__(self, config: ConfigManager, identity: DeviceIdentity, trust_manager: TrustManager):
        self.config = config
        self.identity = identity
        self.trust_manager = trust_manager

    def send(
        self,
        peer_ip: str,
        peer_port: int,
        peer_fingerprint: str,
        manifest: TransferManifest,
        progress_callback: Optional[Callable[[str, int, int, float, float], None]] = None,
        timeout: float = 15.0,
    ) -> bool:
        """
        Execute direct P2P TLS file transfer to remote peer.
        progress_callback signature: (current_file_path, transferred_bytes, total_bytes, speed_bps, eta_seconds)
        """
        raw_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        optimize_tcp_socket(raw_sock)
        raw_sock.settimeout(timeout)
        raw_sock.connect((peer_ip, peer_port))

        ssl_ctx = create_client_ssl_context()
        ssl_sock = ssl_ctx.wrap_socket(raw_sock, server_hostname=None)

        # Cryptographic peer verification (TOFU / Pinning)
        if peer_fingerprint:
            if not verify_peer_fingerprint(ssl_sock, peer_fingerprint):
                ssl_sock.close()
                raise PeerVerificationError(
                    f"Security alert: Remote TLS certificate fingerprint does not match advertised beacon!"
                )

        try:
            # 1. Handshake Init
            send_control_msg(
                ssl_sock,
                make_handshake_init(
                    self.identity.device_id,
                    self.identity.device_name,
                    self.identity.fingerprint,
                ),
            )

            # 2. Handshake Resp
            resp = recv_control_msg(ssl_sock)
            if resp.get("action") != MSG_HANDSHAKE_RESP or resp.get("status") != "OK":
                raise ProtocolError(f"Handshake rejected by remote peer: {resp.get('message')}")

            receiver_id = resp.get("receiver_id")
            receiver_name = resp.get("receiver_name")

            # 3. Transfer Manifest
            send_control_msg(ssl_sock, manifest.to_wire_dict())

            # 4. Transfer Decision
            decision = recv_control_msg(ssl_sock)
            if decision.get("action") == "ERROR":
                raise ProtocolError(f"Remote error: {decision.get('message', decision.get('code'))}")
            if decision.get("action") != MSG_TRANSFER_DECISION:
                raise ProtocolError(f"Expected TRANSFER_DECISION, got {decision.get('action')}")

            if decision.get("status") != "ACCEPT":
                reason = decision.get("reason", "Declined by remote device")
                raise TransferRejected(f"Transfer was declined: {reason}")

            resume_offsets: Dict[str, int] = decision.get("resume_offsets", {})

            # 5. Stream files
            total_transfer_bytes = manifest.total_bytes
            transferred_bytes = sum(resume_offsets.values())
            chunk_size = self.config.chunk_size
            start_time = time.time()
            last_progress_time = 0.0

            for item in manifest.items:
                resume_offset = resume_offsets.get(item.relative_path, 0)
                send_control_msg(
                    ssl_sock,
                    make_file_start(item.index, item.relative_path, item.size, resume_offset),
                )

                hasher = hashlib.sha256()

                with open(item.source_path, "rb", buffering=1024 * 1024) as f:
                    # If resuming, hash already-transferred prefix
                    if resume_offset > 0:
                        hashed_so_far = 0
                        while hashed_so_far < resume_offset:
                            to_read = min(chunk_size, resume_offset - hashed_so_far)
                            buf = f.read(to_read)
                            if not buf:
                                break
                            hasher.update(buf)
                            hashed_so_far += len(buf)
                        f.seek(resume_offset)

                    # Stream remaining bytes
                    while True:
                        chunk = f.read(chunk_size)
                        if not chunk:
                            break
                        hasher.update(chunk)
                        send_frame(ssl_sock, FRAME_TYPE_DATA, chunk)
                        chunk_len = len(chunk)
                        transferred_bytes += chunk_len

                        now = time.time()
                        if progress_callback and (now - last_progress_time >= 0.08 or transferred_bytes == total_transfer_bytes):
                            last_progress_time = now
                            elapsed = now - start_time
                            speed = transferred_bytes / elapsed if elapsed > 0 else 0
                            remaining = max(0, total_transfer_bytes - transferred_bytes)
                            eta = remaining / speed if speed > 0 else 0
                            progress_callback(item.relative_path, transferred_bytes, total_transfer_bytes, speed, eta)

                # Send FILE_END with computed SHA-256
                send_control_msg(ssl_sock, make_file_end(item.index, hasher.hexdigest()))

                # Wait for FILE_VERIFIED
                verified = recv_control_msg(ssl_sock)
                if verified.get("action") != MSG_FILE_VERIFIED or verified.get("status") != "OK":
                    err = verified.get("error", "Integrity check failed")
                    raise IntegrityError(f"Integrity check failed for {item.relative_path}: {err}")

            # 6. Complete transfer
            send_control_msg(ssl_sock, make_transfer_complete(manifest.transfer_id))
            return True

        finally:
            try:
                ssl_sock.close()
            except Exception:
                pass
