"""Terminal formatters, banners, and table rendering"""
from typing import List, Dict, Any, Optional
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from passx import __version__
from passx.discovery.beacon import PeerInfo

console = Console()


def format_bytes(size_bytes: int) -> str:
    """Format bytes to human-readable string (e.g. 1.25 GB)"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    for unit in ["KB", "MB", "GB", "TB"]:
        size_bytes /= 1024.0
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
    return f"{size_bytes:.2f} PB"


def format_speed(bps: float) -> str:
    """Format bytes per second into speed string (e.g. 85.4 MB/s)"""
    return f"{format_bytes(int(bps))}/s"


def format_eta(seconds: float) -> str:
    """Format seconds into ETA string (e.g. 4s, 1m 20s)"""
    if seconds <= 0:
        return "0s"
    if seconds < 60:
        return f"{int(seconds)}s"
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes}m {secs}s"


def print_banner(device_name: str, platform_name: str, local_ip: Optional[str] = None) -> None:
    """Print standard PASS CLI header"""
    if not local_ip:
        try:
            from passx.network.interfaces import get_primary_ip
            local_ip = get_primary_ip()
        except Exception:
            local_ip = None

    ip_display = f" | IP: [bold green]{local_ip}[/bold green]" if local_ip else ""
    text = (
        f"[bold cyan]PASS[/bold cyan] — [italic]Peer-to-peer Automated Secure Sharing[/italic]\n"
        f"Version: [green]{__version__}[/green] | Device: [bold yellow]{device_name}[/bold yellow]{ip_display} | Platform: [blue]{platform_name}[/blue]"
    )
    console.print(Panel(text, border_style="cyan"))


def print_devices_table(peers: List[PeerInfo]) -> None:
    """Render discovered peers in a clean Rich table"""
    if not peers:
        console.print("[yellow]No PASS devices found on the local network.[/yellow]")
        console.print("[dim]Ensure other devices are running 'passx' or 'passx receive' on the same LAN/Wi-Fi.[/dim]")
        return

    table = Table(title=f"Discovered PASS Devices ({len(peers)})", border_style="cyan")
    table.add_column("#", style="dim", width=4)
    table.add_column("Device Name", style="bold green")
    table.add_column("IP Address", style="cyan")
    table.add_column("Port", style="magenta")
    table.add_column("Platform", style="blue")
    table.add_column("Fingerprint", style="dim")

    for i, peer in enumerate(peers, 1):
        fp_short = peer.fingerprint[:16] + "..." if len(peer.fingerprint) > 16 else peer.fingerprint
        table.add_row(
            str(i),
            peer.display_name,
            peer.ip,
            str(peer.port),
            peer.platform,
            fp_short,
        )

    console.print(table)


def print_trusted_table(trusted_devices: List[Dict[str, Any]]) -> None:
    """Render trusted devices list"""
    if not trusted_devices:
        console.print("[dim]No trusted devices configured yet.[/dim]")
        return

    table = Table(title=f"Trusted Devices ({len(trusted_devices)})", border_style="green")
    table.add_column("Device Name", style="bold green")
    table.add_column("IP Address", style="cyan")
    table.add_column("Device ID", style="dim")
    table.add_column("Fingerprint", style="dim")
    table.add_column("Trusted At", style="dim")

    for d in trusted_devices:
        fp_short = d.get("fingerprint", "")[:16] + "..."
        dev_name = d.get("device_name", "Unknown")
        dev_id = d.get("device_id", "")
        ip_addr = d.get("ip") or "LAN/DHCP"
        try:
            from passx.core.aliases import AliasManager
            from passx.core.config import ConfigManager
            alias_mgr = AliasManager(ConfigManager())
            alias = alias_mgr.get_alias(dev_id) or alias_mgr.get_alias(dev_name)
            if alias and alias.lower() != dev_name.lower():
                dev_name = f"{alias} ({dev_name})"
            alias_entry = alias_mgr.resolve_target(alias or dev_name)
            if alias_entry and alias_entry.get("ip"):
                ip_addr = alias_entry.get("ip")
        except Exception:
            pass
        table.add_row(
            dev_name,
            ip_addr,
            dev_id[:8] + "...",
            fp_short,
            d.get("trusted_at", "")[:19],
        )

    console.print(table)
