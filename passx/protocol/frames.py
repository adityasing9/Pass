"""Framing layer for PASS TCP socket communication"""
import json
import struct
from typing import Dict, Tuple, Any, Optional

FRAME_TYPE_CONTROL = 0x00
FRAME_TYPE_DATA = 0x01

# Frame Header format: 1 byte type, 4 bytes uint32 length (big-endian)
HEADER_FORMAT = "!BI"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
MAX_FRAME_SIZE = 16 * 1024 * 1024  # 16 MB max frame size safety limit


class ProtocolError(Exception):
    """Raised when framing or wire protocol rules are violated"""
    pass


def read_exact(sock, n: int) -> bytes:
    """Read exactly n bytes from socket with zero-copy preallocated buffer"""
    if n == 0:
        return b""

    if hasattr(sock, "recv_into"):
        buf = bytearray(n)
        view = memoryview(buf)
        received = 0
        while received < n:
            read_bytes = sock.recv_into(view[received:], n - received)
            if not read_bytes:
                if received == 0:
                    raise EOFError("Connection closed by peer")
                raise ConnectionError(f"Connection closed prematurely, expected {n} bytes but got {received}")
            received += read_bytes
        return bytes(buf)

    # Fallback for mock sockets without recv_into
    chunks = []
    received = 0
    while received < n:
        chunk = sock.recv(n - received)
        if not chunk:
            if received == 0:
                raise EOFError("Connection closed by peer")
            raise ConnectionError(f"Connection closed prematurely, expected {n} bytes but got {received}")
        chunks.append(chunk)
        received += len(chunk)
    return b"".join(chunks)


def send_frame(sock, frame_type: int, payload: bytes) -> None:
    """Send length-prefixed frame over socket"""
    length = len(payload)
    if length > MAX_FRAME_SIZE:
        raise ProtocolError(f"Frame payload ({length} bytes) exceeds maximum limit ({MAX_FRAME_SIZE} bytes)")
    header = struct.pack(HEADER_FORMAT, frame_type, length)
    if length < 65536:
        sock.sendall(header + payload)
    else:
        # Avoid creating a huge concatenated copy in RAM
        sock.sendall(header)
        sock.sendall(payload)


def recv_frame(sock) -> Tuple[int, bytes]:
    """Receive next frame (frame_type, payload_bytes) from socket"""
    header_bytes = read_exact(sock, HEADER_SIZE)
    frame_type, length = struct.unpack(HEADER_FORMAT, header_bytes)
    if length > MAX_FRAME_SIZE:
        raise ProtocolError(f"Incoming frame length ({length} bytes) exceeds maximum ({MAX_FRAME_SIZE} bytes)")
    payload = read_exact(sock, length) if length > 0 else b""
    return frame_type, payload


def send_control_msg(sock, msg: Dict[str, Any]) -> None:
    """Serialize dict to JSON and send as control frame"""
    payload = json.dumps(msg).encode("utf-8")
    send_frame(sock, FRAME_TYPE_CONTROL, payload)


def recv_control_msg(sock) -> Dict[str, Any]:
    """Receive next frame, ensuring it is a control frame, and decode JSON"""
    frame_type, payload = recv_frame(sock)
    if frame_type != FRAME_TYPE_CONTROL:
        raise ProtocolError(f"Expected control frame (0x00), got {hex(frame_type)}")
    try:
        return json.loads(payload.decode("utf-8"))
    except Exception as e:
        raise ProtocolError(f"Failed to parse JSON control frame: {e}")
