"""Tests for protocol frames, serialization, and message formatting"""
import io
import socket
import pytest
from passx.protocol.frames import (
    FRAME_TYPE_CONTROL,
    FRAME_TYPE_DATA,
    send_frame,
    recv_frame,
    send_control_msg,
    recv_control_msg,
    ProtocolError,
)
from passx.protocol.messages import (
    make_handshake_init,
    make_handshake_resp,
    make_transfer_manifest,
    make_transfer_decision,
)


class MockSocket:
    """In-memory mock socket simulating sendall and recv"""
    def __init__(self):
        self.buffer = bytearray()

    def sendall(self, data: bytes):
        self.buffer.extend(data)

    def recv(self, n: int) -> bytes:
        if not self.buffer:
            return b""
        chunk = self.buffer[:n]
        del self.buffer[:n]
        return bytes(chunk)


def test_frame_send_recv():
    sock = MockSocket()
    send_frame(sock, FRAME_TYPE_DATA, b"test-payload-123")

    frame_type, payload = recv_frame(sock)
    assert frame_type == FRAME_TYPE_DATA
    assert payload == b"test-payload-123"


def test_control_msg_send_recv():
    sock = MockSocket()
    orig_msg = make_handshake_init("sender-id", "SENDER-PC", "fp123")
    send_control_msg(sock, orig_msg)

    received_msg = recv_control_msg(sock)
    assert received_msg["action"] == "HANDSHAKE_INIT"
    assert received_msg["sender_id"] == "sender-id"
    assert received_msg["sender_name"] == "SENDER-PC"
    assert received_msg["fingerprint"] == "fp123"


def test_protocol_error_on_invalid_frame():
    sock = MockSocket()
    # Write invalid data
    sock.sendall(b"\x01\x00\x00\x00\x04test")
    # Trying to receive control msg when it is a data frame should raise ProtocolError
    with pytest.raises(ProtocolError):
        recv_control_msg(sock)
