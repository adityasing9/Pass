"""Direct P2P TLS transfer receiver server"""
import hashlib
import logging
import socket
import threading
import time
from pathlib import Path
from typing import Callable, Dict, Optional, Any

from passx.core.config import ConfigManager
from passx.core.identity import DeviceIdentity
from passx.core.trust import TrustManager
from passx.network.tls_context import create_server_ssl_context, verify_peer_fingerprint
from passx.protocol.frames import (
    FRAME_TYPE_DATA,
    FRAME_TYPE_CONTROL,
    recv_frame,
    recv_control_msg,
    send_control_msg,
    send_frame,
    ProtocolError,
)
from passx.protocol.messages import (
    MSG_HANDSHAKE_INIT,
    MSG_TRANSFER_MANIFEST,
    MSG_FILE_START,
    MSG_FILE_END,
    MSG_TRANSFER_COMPLETE,
    make_handshake_resp,
    make_transfer_decision,
    make_file_verified,
    make_error,
)
from .manifest import TransferManifest
from .resume import ResumeManager
from .sanitizer import get_safe_destination_path, resolve_collision_path, SecurityError

logger = logging.getLogger(__name__)


class TransferRejected(Exception):
    pass


class IntegrityError(Exception):
    pass


class ReceiverServer:
    """TLS server listening for inbound PASS file transfers"""

    def __init__(
        self,
        config: ConfigManager,
        identity: DeviceIdentity,
        trust_manager: TrustManager,
        on_request_callback: Optional[Callable[[Dict[str, Any], TransferManifest], bool]] = None,
        progress_callback: Optional[Callable[[str, int, int, float, float], None]] = None,
        bind_host: str = "0.0.0.0",
        port: Optional[int] = None,
    ):
        self.config = config
        self.identity = identity
        self.trust_manager = trust_manager
        self.on_request_callback = on_request_callback
        self.progress_callback = progress_callback
        self.bind_host = bind_host
        self.port = port or config.transfer_port

        self.running = False
        self._server_sock: Optional[socket.socket] = None
        self._thread: Optional[threading.Thread] = None
        self.actual_port: int = self.port

    def start(self) -> None:
        """Start listening for incoming transfers"""
        if self.running:
            return

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # Try designated port, or if port is 0 / in use, find next available port
        try:
            sock.bind((self.bind_host, self.port))
        except OSError:
            sock.bind((self.bind_host, 0))

        self.actual_port = sock.getsockname()[1]
        sock.listen(5)
        self._server_sock = sock
        self.running = True

        self._thread = threading.Thread(target=self._accept_loop, name="passx-receiver", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop receiver server"""
        if not self.running:
            return
        self.running = False
        if self._server_sock:
            try:
                self._server_sock.close()
            except Exception:
                pass
            self._server_sock = None

    def _accept_loop(self) -> None:
        cert_file, key_file = self.identity.get_tls_paths()
        ssl_ctx = create_server_ssl_context(cert_file, key_file)

        while self.running:
            try:
                raw_sock, addr = self._server_sock.accept()
            except OSError:
                break

            client_thread = threading.Thread(
                target=self._handle_client,
                args=(raw_sock, addr, ssl_ctx),
                daemon=True,
            )
            client_thread.start()

    def _handle_client(self, raw_sock: socket.socket, addr: tuple, ssl_ctx) -> None:
        ssl_sock = None
        try:
            ssl_sock = ssl_ctx.wrap_socket(raw_sock, server_side=True)
            self._process_session(ssl_sock, addr)
        except Exception as e:
            logger.debug(f"Transfer session with {addr} ended: {e}")
        finally:
            if ssl_sock:
                try:
                    ssl_sock.close()
                except Exception:
                    pass

    def _process_session(self, sock: socket.socket, addr: tuple) -> None:
        # 1. Handshake Init
        init_msg = recv_control_msg(sock)
        if init_msg.get("action") != MSG_HANDSHAKE_INIT:
            send_control_msg(sock, make_error("INVALID_HANDSHAKE", "Expected HANDSHAKE_INIT"))
            return

        sender_id = init_msg.get("sender_id", "")
        sender_name = init_msg.get("sender_name", "Unknown")
        sender_fp = init_msg.get("fingerprint", "")

        # 2. Handshake Resp
        resp_msg = make_handshake_resp("OK", self.identity.device_id, self.identity.device_name)
        send_control_msg(sock, resp_msg)

        # 3. Transfer Manifest
        manifest_msg = recv_control_msg(sock)
        if manifest_msg.get("action") != MSG_TRANSFER_MANIFEST:
            send_control_msg(sock, make_error("INVALID_MANIFEST", "Expected TRANSFER_MANIFEST"))
            return

        manifest = TransferManifest.from_wire_dict(manifest_msg)

        # 4. Acceptance Check
        is_trusted = self.trust_manager.is_trusted(sender_id, sender_fp)
        accepted = False

        if is_trusted and self.config.get("auto_accept_trusted", True):
            accepted = True
        elif self.on_request_callback:
            sender_info = {
                "sender_id": sender_id,
                "sender_name": sender_name,
                "fingerprint": sender_fp,
                "ip": addr[0],
            }
            accepted = self.on_request_callback(sender_info, manifest)
        else:
            # Default auto-accept in headless/unattended mode
            accepted = True

        if not accepted:
            send_control_msg(sock, make_transfer_decision("REJECT", "Transfer declined by receiver"))
            return

        # 5. Check resume offsets
        download_base = self.config.download_dir
        resume_offsets: Dict[str, int] = {}
        for item in manifest.items:
            dest = get_safe_destination_path(download_base, item.relative_path)
            offset = ResumeManager.get_resume_offset(dest, item.size)
            if offset > 0:
                resume_offsets[item.relative_path] = offset

        send_control_msg(sock, make_transfer_decision("ACCEPT", resume_offsets=resume_offsets))

        # 6. Stream files
        total_transfer_bytes = manifest.total_bytes
        total_received_bytes = sum(resume_offsets.values())
        session_start_time = time.time()

        for item in manifest.items:
            # Receive FILE_START
            start_msg = recv_control_msg(sock)
            if start_msg.get("action") != MSG_FILE_START:
                send_control_msg(sock, make_error("PROTOCOL_ERROR", "Expected FILE_START"))
                return

            rel_path = start_msg.get("relative_path")
            file_size = int(start_msg.get("size", 0))
            resume_offset = int(start_msg.get("resume_offset", 0))

            target_dest = get_safe_destination_path(download_base, rel_path)
            partial_path, _ = ResumeManager.get_partial_paths(target_dest)
            partial_path.parent.mkdir(parents=True, exist_ok=True)

            hasher = hashlib.sha256()

            # If resuming, hash existing partial bytes
            if resume_offset > 0 and partial_path.exists():
                with open(partial_path, "rb") as pf:
                    while True:
                        block = pf.read(256 * 1024)
                        if not block:
                            break
                        hasher.update(block)
                file_mode = "ab"
            else:
                resume_offset = 0
                file_mode = "wb"

            file_received = resume_offset

            with open(partial_path, file_mode) as out_f:
                while file_received < file_size:
                    frame_type, chunk = recv_frame(sock)
                    if frame_type != FRAME_TYPE_DATA:
                        raise ProtocolError(f"Expected data frame during file stream, got {frame_type}")

                    out_f.write(chunk)
                    hasher.update(chunk)
                    chunk_len = len(chunk)
                    file_received += chunk_len
                    total_received_bytes += chunk_len

                    # Checkpoint resume metadata periodically
                    ResumeManager.save_checkpoint(
                        target_dest,
                        manifest.transfer_id,
                        rel_path,
                        file_size,
                        file_received,
                    )

                    # Update progress
                    if self.progress_callback:
                        elapsed = time.time() - session_start_time
                        speed = total_received_bytes / elapsed if elapsed > 0 else 0
                        remaining_bytes = max(0, total_transfer_bytes - total_received_bytes)
                        eta = remaining_bytes / speed if speed > 0 else 0
                        self.progress_callback(rel_path, total_received_bytes, total_transfer_bytes, speed, eta)

            # Receive FILE_END
            end_msg = recv_control_msg(sock)
            if end_msg.get("action") != MSG_FILE_END:
                send_control_msg(sock, make_error("PROTOCOL_ERROR", "Expected FILE_END"))
                return

            expected_sha256 = end_msg.get("sha256_hash", "")
            computed_sha256 = hasher.hexdigest()

            if expected_sha256 and computed_sha256.lower() != expected_sha256.lower():
                send_control_msg(sock, make_file_verified(item.index, "HASH_MISMATCH", "SHA-256 verification failed"))
                ResumeManager.cleanup_partial(target_dest)
                raise IntegrityError(f"SHA-256 mismatch for {rel_path}: expected {expected_sha256}, got {computed_sha256}")

            # Verification success
            final_path = resolve_collision_path(target_dest)
            ResumeManager.finalize_transfer(final_path)
            send_control_msg(sock, make_file_verified(item.index, "OK"))

        # 7. TRANSFER_COMPLETE
        complete_msg = recv_control_msg(sock)
        logger.debug(f"Transfer {manifest.transfer_id} successfully completed from {sender_name}")
