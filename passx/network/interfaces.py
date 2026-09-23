"""Cross-platform network interface scanning and broadcast calculation"""
import ipaddress
import socket
from typing import List, Set, Tuple, Optional


def get_local_ip_for_peer(peer_ip: str) -> str:
    """Determine which local IP address is routed toward a specific peer IP"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Does not send actual traffic, just queries OS routing table
        s.connect((peer_ip, 1))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


def get_active_ipv4_interfaces() -> List[Tuple[str, str, str]]:
    """
    Returns list of (interface_name, ip_address, broadcast_address).
    Uses psutil if available, with robust socket-based fallback for minimal environments (Termux).
    """
    interfaces = []
    
    # Try psutil first if installed
    try:
        import psutil
        stats = psutil.net_if_stats()
        addrs = psutil.net_if_addrs()

        for iface_name, iface_addrs in addrs.items():
            # Check if interface is up (if stats available)
            if iface_name in stats and not stats[iface_name].isup:
                continue

            for addr in iface_addrs:
                if addr.family == socket.AF_INET:
                    ip = addr.address
                    if ip.startswith("127.") or ip == "0.0.0.0":
                        continue

                    broadcast = addr.broadcast
                    if not broadcast and addr.netmask:
                        try:
                            net = ipaddress.IPv4Network(f"{ip}/{addr.netmask}", strict=False)
                            broadcast = str(net.broadcast_address)
                        except Exception:
                            broadcast = None

                    if not broadcast:
                        # Fallback to class C style broadcast
                        parts = ip.split(".")
                        broadcast = f"{parts[0]}.{parts[1]}.{parts[2]}.255"

                    interfaces.append((iface_name, ip, broadcast))
        if interfaces:
            return interfaces
    except ImportError:
        pass
    except Exception:
        pass

    # Fallback using standard library socket
    try:
        hostname = socket.gethostname()
        for ip in socket.gethostbyname_ex(hostname)[2]:
            if not ip.startswith("127.") and not ip.startswith("169.254."):
                parts = ip.split(".")
                broadcast = f"{parts[0]}.{parts[1]}.{parts[2]}.255"
                interfaces.append(("default", ip, broadcast))
    except Exception:
        pass

    return interfaces


def get_all_broadcast_addresses() -> Set[str]:
    """
    Returns unique set of broadcast addresses to target for discovery.
    Always includes 255.255.255.255 and all active subnet broadcast addresses.
    """
    broadcasts = {"255.255.255.255"}
    for _, _, bcast in get_active_ipv4_interfaces():
        if bcast:
            broadcasts.add(bcast)
    return broadcasts
