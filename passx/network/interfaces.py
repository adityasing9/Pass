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

    # Fallback 1: Linux / Android 'ip -4 -o addr show'
    try:
        import subprocess
        import shutil
        ip_bin = shutil.which("ip") or "/system/bin/ip"
        res = subprocess.run([ip_bin, "-4", "-o", "addr", "show"], capture_output=True, text=True, timeout=1.5)
        if res.returncode == 0:
            for line in res.stdout.splitlines():
                parts = line.split()
                if len(parts) >= 4 and parts[2] == "inet":
                    iface = parts[1]
                    ip_cidr = parts[3]
                    ip = ip_cidr.split("/")[0]
                    if ip.startswith("127.") or ip == "0.0.0.0":
                        continue
                    bcast = None
                    if "brd" in parts:
                        bcast_idx = parts.index("brd") + 1
                        if bcast_idx < len(parts):
                            bcast = parts[bcast_idx]
                    if not bcast:
                        try:
                            net = ipaddress.IPv4Network(ip_cidr, strict=False)
                            bcast = str(net.broadcast_address)
                        except Exception:
                            p = ip.split(".")
                            bcast = f"{p[0]}.{p[1]}.{p[2]}.255"
                    interfaces.append((iface, ip, bcast))
            if interfaces:
                return interfaces
    except Exception:
        pass

    # Fallback 2: Standard library socket gethostbyname_ex
    try:
        hostname = socket.gethostname()
        for ip in socket.gethostbyname_ex(hostname)[2]:
            if not ip.startswith("127.") and not ip.startswith("169.254."):
                parts = ip.split(".")
                broadcast = f"{parts[0]}.{parts[1]}.{parts[2]}.255"
                interfaces.append(("default", ip, broadcast))
        if interfaces:
            return interfaces
    except Exception:
        pass

    # Fallback 3: Routing table query via UDP probe (offline-friendly)
    try:
        targets = [("8.8.8.8", 80), ("192.168.1.1", 80), ("172.16.0.1", 80), ("10.0.0.1", 80)]
        seen_ips = set()
        for target in targets:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                s.connect(target)
                ip = s.getsockname()[0]
                if ip and not ip.startswith("127.") and not ip.startswith("169.254.") and ip not in seen_ips:
                    seen_ips.add(ip)
                    parts = ip.split(".")
                    broadcast = f"{parts[0]}.{parts[1]}.{parts[2]}.255"
                    interfaces.append(("default", ip, broadcast))
            except Exception:
                pass
            finally:
                s.close()
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
