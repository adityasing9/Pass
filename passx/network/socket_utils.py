"""Socket configuration and helper functions"""
import socket
import struct
from typing import Tuple


def create_broadcast_socket() -> socket.socket:
    """Create a UDP socket configured for broadcasting"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    return sock


def create_udp_listener_socket(port: int, multicast_group: str = None) -> socket.socket:
    """
    Create a UDP listener socket bound to INADDR_ANY and port.
    Optionally joins a multicast group.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    # SO_REUSEPORT if platform supports it (Linux, macOS, Android)
    if hasattr(socket, "SO_REUSEPORT"):
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except Exception:
            pass

    # Windows requires binding to 0.0.0.0
    sock.bind(("", port))

    if multicast_group:
        try:
            mreq = struct.pack("4sl", socket.inet_aton(multicast_group), socket.INADDR_ANY)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        except Exception:
            # Multicast might not be supported on all virtual adapters; broadcast remains active
            pass

    return sock
