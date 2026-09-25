"""Main CLI entry point for passx"""
import argparse
import logging
import os
import sys
import time
from pathlib import Path
from rich.console import Console
from rich.prompt import Prompt, Confirm

from passx import __version__, __cli_name__
from passx.core.config import ConfigManager
from passx.core.identity import DeviceIdentity
from passx.core.trust import TrustManager
from passx.discovery.engine import DiscoveryEngine
from passx.network.interfaces import get_active_ipv4_interfaces
from passx.platform import current_platform
from passx.protocol.messages import PROTOCOL_VERSION
from passx.transfer.manifest import build_manifest_from_paths
from passx.transfer.receiver import ReceiverServer
from passx.transfer.sender import TransferSender, TransferRejected, PeerVerificationError
from .formatters import print_banner, print_devices_table, print_trusted_table, format_bytes
from .interactive import interactive_menu
from .progress import TransferProgressTracker

console = Console()


def setup_logging(debug: bool = False) -> None:
    level = logging.DEBUG if debug else logging.WARNING
    logging.basicConfig(
        level=level,
        format="[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
        datefmt="%H:%M:%S",
    )


def cmd_send(args, config: ConfigManager, identity: DeviceIdentity, trust_manager: TrustManager) -> int:
    """Handle 'passx send [path...]'"""
    if args.paths:
        paths = [current_platform.resolve_smart_path(p) for p in args.paths]
        for p in paths:
            if not p.exists():
                console.print(f"[red]Error: Source path '{p}' does not exist.[/red]")
                return 1
    else:
        from .picker import select_files_interactively
        paths = select_files_interactively()
        if not paths:
            return 0

    try:
        manifest = build_manifest_from_paths(paths)
    except Exception as e:
        console.print(f"[red]Error preparing files for transfer: {e}[/red]")
        return 1

    if getattr(args, "turbo", False):
        config.data["chunk_size"] = 2 * 1024 * 1024
        console.print("[bold yellow]⚡ Turbo mode active (2 MB chunk pipeline)[/bold yellow]")

    target_peer = None
    with DiscoveryEngine(config, identity) as discovery:
        if args.to:
            console.print(f"[cyan]Searching for device '{args.to}'...[/cyan]")
            peers = discovery.scan(timeout=1.5)
            target_peer = discovery.find_peer(args.to)
            if not target_peer:
                # Check if args.to is an IP address
                is_ip = False
                try:
                    import ipaddress
                    ipaddress.ip_address(args.to)
                    is_ip = True
                except ValueError:
                    pass

                if is_ip:
                    from passx.discovery.beacon import PeerInfo
                    console.print(f"[yellow]'{args.to}' not discovered via broadcast. Connecting directly via TCP...[/yellow]")
                    target_peer = PeerInfo(
                        device_id="direct-ip",
                        device_name=args.to,
                        platform="unknown",
                        ip=args.to,
                        port=config.transfer_port,
                        fingerprint="",
                        capabilities=[],
                    )
                else:
                    console.print(f"[red]Device '{args.to}' not found on the local network.[/red]")
                    console.print("[dim]Tip: Check if the receiving device is running 'passx receive' or specify its IP address (e.g. --to 192.168.1.105).[/dim]")
                    return 1
        else:
            console.print("[cyan]Discovering nearby PASS devices on local network...[/cyan]")
            peers = discovery.scan(timeout=2.0)
            if not peers:
                console.print("[yellow]No PASS devices found automatically on the local network.[/yellow]")
                console.print("[dim]Tip: Ensure the destination device is running 'passx receive' on the same Wi-Fi or Hotspot.[/dim]")
                direct_ip = Prompt.ask("\nEnter receiver IP address directly (or press Enter to cancel)", default="").strip()
                if not direct_ip:
                    return 1
                from passx.discovery.beacon import PeerInfo
                target_peer = PeerInfo(
                    device_id="direct-ip",
                    device_name=direct_ip,
                    platform="unknown",
                    ip=direct_ip,
                    port=config.transfer_port,
                    fingerprint="",
                    capabilities=[],
                )
            else:
                print_devices_table(peers)
                choices = [str(i) for i in range(1, len(peers) + 1)]
                selected_idx = Prompt.ask("Select device number to send to", choices=choices, default="1")
                target_peer = peers[int(selected_idx) - 1]

    console.print(f"[cyan]Connecting directly to [bold]{target_peer.device_name}[/bold] ({target_peer.ip}:{target_peer.port})...[/cyan]")

    sender = TransferSender(config, identity, trust_manager)
    try:
        with TransferProgressTracker("Sending") as tracker:
            sender.send(
                peer_ip=target_peer.ip,
                peer_port=target_peer.port,
                peer_fingerprint=target_peer.fingerprint,
                manifest=manifest,
                progress_callback=tracker.update,
            )
        console.print("\n[bold green]✓ File transfer completed successfully and verified with SHA-256![/bold green]")
        return 0
    except TransferRejected as e:
        console.print(f"\n[yellow]Transfer was declined by receiver: {e}[/yellow]")
        return 2
    except PeerVerificationError as e:
        console.print(f"\n[bold red]Security Error: {e}[/bold red]")
        return 3
    except Exception as e:
        console.print(f"\n[red]Transfer failed: {e}[/red]")
        return 1


def cmd_receive(args, config: ConfigManager, identity: DeviceIdentity, trust_manager: TrustManager) -> int:
    """Handle 'passx receive'"""
    if args.dir:
        config.download_dir = Path(os.path.expanduser(args.dir))

    from passx.network.interfaces import get_active_ipv4_interfaces
    ifaces = get_active_ipv4_interfaces()
    ip_list = ", ".join(ip for _, ip, _ in ifaces if not ip.startswith("127."))
    if not ip_list:
        ip_list = "0.0.0.0"

    console.print(f"[bold cyan]PASS Receiver Ready[/bold cyan]")
    console.print(f"Device Name: [green]{identity.device_name}[/green]")
    console.print(f"Local IP(s):  [bold green]{ip_list}[/bold green]")
    console.print(f"Download Directory: [cyan]{config.download_dir}[/cyan]")
    console.print(f"Transfer Port: [yellow]{config.transfer_port}[/yellow]")
    console.print("[dim]Listening for incoming file transfers... (Press Ctrl+C to exit)[/dim]\n")

    def on_request(sender_info: dict, manifest) -> bool:
        sender_id = sender_info.get("sender_id", "")
        sender_fp = sender_info.get("fingerprint", "")
        sender_name = sender_info.get("sender_name", "Unknown")

        if args.yes:
            console.print(f"[dim]Auto-accepting transfer of {manifest.file_count} files from {sender_name}[/dim]")
            return True

        console.print("\n[bold yellow]Incoming transfer request![/bold yellow]")
        console.print(f"From: [bold cyan]{sender_name}[/bold cyan] ({sender_info.get('ip')})")
        console.print(f"Files: {manifest.file_count} file(s) ({format_bytes(manifest.total_bytes)})")

        accepted = Confirm.ask("Accept transfer?", default=True)
        if accepted and not trust_manager.is_trusted(sender_id, sender_fp):
            if Confirm.ask(f"Trust '{sender_name}' for future transfers?", default=False):
                trust_manager.trust_device(sender_id, sender_name, sender_fp)
                console.print(f"[green]Added '{sender_name}' to trusted devices.[/green]")
        return accepted

    tracker = TransferProgressTracker("Receiving")
    receiver = ReceiverServer(
        config=config,
        identity=identity,
        trust_manager=trust_manager,
        on_request_callback=on_request,
        progress_callback=lambda f, trans, total, spd, eta: tracker.update(f, trans, total, spd, eta),
    )

    discovery = DiscoveryEngine(config, identity)
    try:
        receiver.start()
        discovery.start()
        with tracker:
            while True:
                time.sleep(0.5)
    except KeyboardInterrupt:
        console.print("\n[yellow]Stopping receiver...[/yellow]")
        return 0
    finally:
        discovery.stop()
        receiver.stop()


def cmd_devices(args, config: ConfigManager, identity: DeviceIdentity) -> int:
    """Handle 'passx devices'"""
    console.print("[cyan]Searching for nearby PASS devices on the local network...[/cyan]")
    with DiscoveryEngine(config, identity) as discovery:
        peers = discovery.scan(timeout=2.0)
    print_devices_table(peers)
    return 0


def cmd_trust(args, config: ConfigManager, identity: DeviceIdentity, trust_manager: TrustManager) -> int:
    """Handle 'passx trust <device>' or listing trusted devices"""
    if not args.target:
        trusted = trust_manager.list_trusted()
        print_trusted_table(trusted)
        return 0

    target = args.target.strip()
    with DiscoveryEngine(config, identity) as discovery:
        peers = discovery.scan(timeout=1.5)
        peer = discovery.find_peer(target)

    if peer:
        trust_manager.trust_device(peer.device_id, peer.device_name, peer.fingerprint)
        console.print(f"[green]Successfully trusted '{peer.device_name}' ({peer.device_id[:8]}...)[/green]")
        return 0
    else:
        console.print(f"[yellow]Device '{target}' not found on the local network to trust.[/yellow]")
        return 1


def cmd_untrust(args, trust_manager: TrustManager) -> int:
    """Handle 'passx untrust <device>'"""
    if trust_manager.untrust_device(args.target):
        console.print(f"[green]Successfully removed '{args.target}' from trusted devices.[/green]")
        return 0
    else:
        console.print(f"[yellow]No trusted device matching '{args.target}' found.[/yellow]")
        return 1


def cmd_status(args, config: ConfigManager, identity: DeviceIdentity, trust_manager: TrustManager) -> int:
    """Handle 'passx status'"""
    from passx.network.interfaces import get_primary_ip
    primary_ip = get_primary_ip()

    print_banner(identity.device_name, current_platform.get_platform_name(), local_ip=primary_ip)

    console.print("[bold]Device Information:[/bold]")
    console.print(f"  Device Name:      [cyan]{identity.device_name}[/cyan]")
    console.print(f"  Local IP Address: [bold green]{primary_ip}[/bold green]")
    console.print(f"  Device ID:        [dim]{identity.device_id}[/dim]")
    console.print(f"  Platform:         [blue]{current_platform.get_platform_name()}[/blue]")
    console.print(f"  TLS Fingerprint:  [dim]{identity.fingerprint}[/dim]")
    console.print(f"  Config Directory: [cyan]{config.config_dir}[/cyan]")
    console.print(f"  Downloads Folder: [cyan]{config.download_dir}[/cyan]")
    console.print(f"  Discovery Port:   [yellow]{config.discovery_port}[/yellow] (UDP)")
    console.print(f"  Transfer Port:    [yellow]{config.transfer_port}[/yellow] (TCP)")
    console.print(f"  Trusted Devices:  [green]{len(trust_manager.list_trusted())}[/green]")

    env_status = current_platform.check_environment()
    if env_status.get("firewall_advice"):
        console.print(f"\n[bold yellow]Platform Notice:[/bold yellow] {env_status.get('firewall_advice')}")

    interfaces = get_active_ipv4_interfaces()
    if interfaces:
        console.print(f"\n[bold]Active Network Interfaces ({len(interfaces)}):[/bold]")
        for iface_name, ip, bcast in interfaces:
            console.print(f"  • {iface_name}: IP [cyan]{ip}[/cyan] (Broadcast: [dim]{bcast}[/dim])")
    else:
        console.print("\n[yellow]Warning: No active non-loopback IPv4 interfaces detected.[/yellow]")

    return 0


def cmd_version() -> int:
    """Handle 'passx version'"""
    console.print(f"PASS ({__cli_name__}) version [bold green]{__version__}[/bold green] (Protocol v{PROTOCOL_VERSION})")
    return 0


def cmd_update() -> int:
    """Upgrade PASS to the latest version directly from GitHub"""
    import os
    import shutil
    import subprocess
    import tempfile

    console.print("[cyan]Updating PASS to the latest version from GitHub...[/cyan]")
    url = "https://github.com/adityasing9/Pass/archive/refs/heads/main.zip"
    
    tmp_path = None
    install_src = url
    try:
        if shutil.which("curl"):
            tmp_fd, tmp_path = tempfile.mkstemp(suffix=".zip")
            os.close(tmp_fd)
            ret = subprocess.run(["curl", "-sSL", "-L", url, "-o", tmp_path])
            if ret.returncode == 0 and os.path.getsize(tmp_path) > 0:
                install_src = tmp_path
    except Exception:
        install_src = url

    base_cmd = [
        sys.executable, "-m", "pip", "install",
        "--upgrade", "--no-deps", "--force-reinstall", "--no-cache-dir", install_src
    ]
    try:
        res = subprocess.run(base_cmd)
        if res.returncode != 0:
            res = subprocess.run(base_cmd + ["--break-system-packages"])
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        if res.returncode == 0:
            console.print("[bold green]✓ PASS successfully updated to the latest version![/bold green]")
            return 0
        else:
            console.print("[red]Update failed. You can run manually:[/red]")
            console.print("curl -sSL tinyurl.com/passx-linux | bash")
    except Exception as e:
        console.print(f"[red]Error during update: {e}[/red]")
        return 1


def cmd_pair(args, config: ConfigManager, identity: DeviceIdentity, trust_manager: TrustManager) -> int:
    """Handle 'passx pair [target]'"""
    import ipaddress
    from passx.core.pairing import pair_with_peer
    from passx.discovery.beacon import PeerInfo

    target_peer = None

    if getattr(args, "target", None):
        target = args.target.strip()
        is_ip = False
        try:
            ipaddress.ip_address(target)
            is_ip = True
        except ValueError:
            pass

        if is_ip:
            target_peer = PeerInfo("direct", target, "unknown", target, config.transfer_port, "", [])
        else:
            with DiscoveryEngine(config, identity) as discovery:
                discovery.scan(timeout=1.5)
                target_peer = discovery.find_peer(target)
    else:
        console.print("[cyan]Scanning for nearby PASS devices to pair with...[/cyan]")
        with DiscoveryEngine(config, identity) as discovery:
            peers = discovery.scan(timeout=2.0)

        if not peers:
            console.print("[yellow]No PASS devices found automatically on the local network.[/yellow]")
            console.print("[dim]Tip: Ensure the other device is on the same Wi-Fi/Hotspot and running 'passx', 'passx receive', or 'passx daemon'.[/dim]")
            direct_ip = Prompt.ask("\nEnter device IP address manually to pair (or press Enter to cancel)", default="").strip()
            if not direct_ip:
                return 1
            target_peer = PeerInfo("direct", direct_ip, "unknown", direct_ip, config.transfer_port, "", [])
        else:
            print_devices_table(peers)
            choices = [str(i) for i in range(1, len(peers) + 1)]
            selected_idx = Prompt.ask("Select device number to pair with", choices=choices, default="1")
            target_peer = peers[int(selected_idx) - 1]

    if not target_peer:
        console.print(f"[red]Device '{args.target}' could not be located on the local network.[/red]")
        return 1

    console.print(f"[cyan]Establishing mutual pairing with [bold]{target_peer.device_name}[/bold] ({target_peer.ip}:{target_peer.port})...[/cyan]")
    ok, msg = pair_with_peer(target_peer.ip, target_peer.port, config, identity, trust_manager)
    if ok:
        console.print(f"[bold green]✓ {msg}[/bold green]")
        console.print("[dim]Devices are now paired! All future transfers will be accepted automatically without confirmation prompts.[/dim]")
        return 0
    else:
        # Fallback to local trust if discovery beacon has fingerprint
        if target_peer.fingerprint:
            trust_manager.trust_device(target_peer.device_id, target_peer.device_name, target_peer.fingerprint)
            console.print(f"[green]✓ Paired locally using verified beacon fingerprint for '{target_peer.device_name}'![/green]")
            console.print("[dim]Transfers from this device will now be accepted automatically.[/dim]")
            return 0
        console.print(f"[red]Pairing failed: {msg}[/red]")
        return 1


def cmd_daemon(args, config: ConfigManager) -> int:
    """Handle 'passx daemon [start|stop|status]'"""
    from passx.core.daemon import start_daemon, stop_daemon, get_daemon_status

    action = getattr(args, "action", "status") or "status"

    if action == "start":
        ok, msg, pid = start_daemon(config.config_dir)
        if ok:
            console.print(f"[bold green]✓ {msg}! (PID: {pid})[/bold green]")
            console.print(f"Downloads Folder: [cyan]{config.download_dir}[/cyan]")
            console.print("[dim]PASS is now running in the background 24/7. Transferred files will arrive automatically without opening PASS![/dim]")
            return 0
        else:
            console.print(f"[yellow]{msg}[/yellow]")
            return 0

    elif action == "stop":
        ok, msg = stop_daemon(config.config_dir)
        if ok:
            console.print(f"[green]✓ {msg}[/green]")
            return 0
        else:
            console.print(f"[yellow]{msg}[/yellow]")
            return 1

    else:  # status
        is_running, pid, log_path = get_daemon_status(config.config_dir)
        if is_running:
            console.print(f"[bold green]● PASS Background Receiver is ACTIVE[/bold green] (PID: [cyan]{pid}[/cyan])")
            console.print(f"Log file: [dim]{log_path}[/dim]")
            console.print(f"Downloads Folder: [cyan]{config.download_dir}[/cyan]")
            console.print("[dim]Use 'passx daemon stop' to terminate the background receiver.[/dim]")
        else:
            console.print("[yellow]○ PASS Background Receiver is NOT running.[/yellow]")
            console.print("[dim]Use 'passx daemon start' to keep PASS running in the background for automatic receiving.[/dim]")
        return 0


def cmd_auto_accept(args, config: ConfigManager) -> int:
    """Handle 'passx auto-accept [on|off|status]'"""
    state = getattr(args, "state", "status") or "status"
    if state in ("on", "enable", "true", "1"):
        config.set("auto_accept_all", True)
        console.print("[bold green]✓ Auto-accept enabled![/bold green] All incoming transfers will be received automatically with zero confirmation prompts.")
        return 0
    elif state in ("off", "disable", "false", "0"):
        config.set("auto_accept_all", False)
        console.print("[yellow]Auto-accept disabled.[/yellow] Inbound transfers from non-paired devices will require confirmation.")
        return 0
    else:
        current = config.get("auto_accept_all", False)
        status_str = "[bold green]ON (All transfers auto-accepted)[/bold green]" if current else "[yellow]OFF (Pairing required for auto-accept)[/yellow]"
        console.print(f"Auto-accept is currently: {status_str}")
        console.print("[dim]Run 'passx auto-accept on' to accept transfers automatically without prompting.[/dim]")
        return 0


def cmd_chat(args, config: ConfigManager, identity: DeviceIdentity, trust_manager: TrustManager) -> int:
    """Handle 'passx chat [target]'"""
    from passx.cli.chat_ui import run_chat_session, pick_contact_interactively
    from passx.discovery.beacon import PeerInfo

    target_peer = None
    if getattr(args, "target", None):
        target_str = args.target.strip()
        is_ip = False
        try:
            import ipaddress
            ipaddress.ip_address(target_str)
            is_ip = True
        except ValueError:
            pass

        if is_ip:
            target_peer = PeerInfo(
                device_id="direct-ip",
                device_name=target_str,
                platform="unknown",
                ip=target_str,
                port=config.transfer_port,
                fingerprint="",
                capabilities=[],
            )
        else:
            with DiscoveryEngine(config, identity) as discovery:
                discovery.scan(timeout=1.5)
                target_peer = discovery.find_peer(target_str)

            if not target_peer:
                for dev in trust_manager.list_trusted():
                    if target_str.lower() in dev.get("name", "").lower() or target_str == dev.get("device_id"):
                        ip = Prompt.ask(f"Enter IP address for '{dev['name']}'", default="").strip()
                        if ip:
                            target_peer = PeerInfo(
                                device_id=dev["device_id"],
                                device_name=dev["name"],
                                platform="unknown",
                                ip=ip,
                                port=config.transfer_port,
                                fingerprint=dev.get("fingerprint", ""),
                                capabilities=[],
                            )
                        break

        if not target_peer:
            console.print(f"[red]Device '{target_str}' not found on the local network.[/red]")
            return 1
    else:
        target_peer = pick_contact_interactively(config, identity, trust_manager)
        if not target_peer:
            return 0

    run_chat_session(target_peer, config, identity, trust_manager)
    return 0


def cmd_msg(args, config: ConfigManager, identity: DeviceIdentity, trust_manager: TrustManager) -> int:
    """Handle 'passx msg <target> <message...>'"""
    from passx.core.chat_client import send_chat
    from passx.discovery.beacon import PeerInfo

    target_str = args.target.strip()
    text = " ".join(args.message).strip()
    if not text:
        console.print("[red]Error: Message cannot be empty.[/red]")
        return 1

    target_peer = None
    is_ip = False
    try:
        import ipaddress
        ipaddress.ip_address(target_str)
        is_ip = True
    except ValueError:
        pass

    if is_ip:
        target_peer = PeerInfo(
            device_id="direct-ip",
            device_name=target_str,
            platform="unknown",
            ip=target_str,
            port=config.transfer_port,
            fingerprint="",
            capabilities=[],
        )
    else:
        with DiscoveryEngine(config, identity) as discovery:
            discovery.scan(timeout=1.5)
            target_peer = discovery.find_peer(target_str)

    if not target_peer:
        console.print(f"[red]Device '{target_str}' not found on the local network.[/red]")
        console.print("[dim]Tip: Check if the receiving device is online or specify its IP address directly.[/dim]")
        return 1

    console.print(f"[cyan]Sending message to {target_peer.device_name}...[/cyan]")
    ok, status_msg, saved = send_chat(
        peer_ip=target_peer.ip,
        peer_port=target_peer.port,
        text=text,
        config=config,
        identity=identity,
        trust_manager=trust_manager,
        peer_id=target_peer.device_id,
        peer_name=target_peer.device_name,
    )

    if ok:
        console.print(f"[bold green]✓✓ Delivered to {target_peer.device_name}:[/bold green] [white]\"{text}\"[/white]")
        return 0
    else:
        console.print(f"[bold red]✗ Delivery failed:[/bold red] {status_msg}")
        return 1


def cmd_clip(args, config: ConfigManager, identity: DeviceIdentity, trust_manager: TrustManager) -> int:
    """Handle 'passx clip <target>'"""
    from passx.core.chat_client import send_chat
    from passx.discovery.beacon import PeerInfo

    target_str = args.target.strip()
    clip_text = current_platform.get_clipboard_text()
    if not clip_text:
        console.print("[yellow]Clipboard is empty or could not be read.[/yellow]")
        return 1

    target_peer = None
    is_ip = False
    try:
        import ipaddress
        ipaddress.ip_address(target_str)
        is_ip = True
    except ValueError:
        pass

    if is_ip:
        target_peer = PeerInfo(
            device_id="direct-ip",
            device_name=target_str,
            platform="unknown",
            ip=target_str,
            port=config.transfer_port,
            fingerprint="",
            capabilities=[],
        )
    else:
        with DiscoveryEngine(config, identity) as discovery:
            discovery.scan(timeout=1.5)
            target_peer = discovery.find_peer(target_str)

    if not target_peer:
        console.print(f"[red]Device '{target_str}' not found on the local network.[/red]")
        return 1

    preview = clip_text[:60] + "..." if len(clip_text) > 60 else clip_text
    console.print(f"[cyan]Sending clipboard to {target_peer.device_name} ({len(clip_text)} chars): '{preview}'...[/cyan]")
    ok, status_msg, saved = send_chat(
        peer_ip=target_peer.ip,
        peer_port=target_peer.port,
        text=f"📋 [Clipboard]: {clip_text}",
        config=config,
        identity=identity,
        trust_manager=trust_manager,
        peer_id=target_peer.device_id,
        peer_name=target_peer.device_name,
    )

    if ok:
        console.print(f"[bold green]✓✓ Clipboard sent to {target_peer.device_name}![/bold green]")
        return 0
    else:
        console.print(f"[bold red]✗ Delivery failed:[/bold red] {status_msg}")
        return 1


def cmd_rename(args, config: ConfigManager, identity: DeviceIdentity, trust_manager: TrustManager) -> int:
    """Handle 'passx rename [target] [nickname]' or 'passx alias'"""
    from passx.core.aliases import AliasManager
    alias_mgr = AliasManager(config)

    # Flag: --list
    if getattr(args, "list", False) or getattr(args, "target", "") in ("--list", "-l", "list"):
        aliases = alias_mgr.list_aliases()
        if not aliases:
            console.print("[yellow]No device nicknames configured yet.[/yellow]")
            console.print("[dim]Use 'passx rename <device> <nickname>' to nickname a device.[/dim]")
            return 0
        from rich.table import Table
        table = Table(title=f"Device Nicknames ({len(aliases)})", border_style="cyan")
        table.add_column("Nickname", style="bold green")
        table.add_column("Original Target", style="cyan")
        table.add_column("IP Address", style="magenta")
        table.add_column("Device ID / Key", style="dim")
        for a in aliases:
            ip_val = a.get("ip") or (a.get("target") if a.get("target", "").count(".") == 3 else "Auto/LAN")
            table.add_row(a.get("nickname", ""), a.get("target", ""), ip_val, a.get("key", "")[:16] + "...")
        console.print(table)
        return 0

    # Flag: --remove
    if getattr(args, "remove", False) or getattr(args, "target", "") in ("--remove", "-r", "remove"):
        target_to_remove = getattr(args, "nickname", None) or (args.target if args.target not in ("--remove", "-r", "remove") else None)
        if not target_to_remove:
            target_to_remove = Prompt.ask("Enter nickname or device to remove", default="").strip()
        if not target_to_remove:
            return 1
        if alias_mgr.remove_alias(target_to_remove):
            console.print(f"[green]✓ Nickname for '{target_to_remove}' removed.[/green]")
            return 0
        else:
            console.print(f"[yellow]No nickname found for '{target_to_remove}'.[/yellow]")
            return 1

    # Flag: --self or single argument intended for this device
    is_self = getattr(args, "self", False) or getattr(args, "target", "") in ("--self", "-s", "--me", "me", "self")
    if is_self:
        new_name = getattr(args, "nickname", None) or (args.target if args.target not in ("--self", "-s", "--me", "me", "self") else None)
        if not new_name:
            new_name = Prompt.ask(f"Enter new name for this device (Current: '{identity.device_name}')", default="").strip()
        if not new_name:
            return 0
        config.device_name = new_name
        console.print(f"[bold green]✓ This device has been renamed to: '{new_name}'![/bold green]")
        return 0

    target = getattr(args, "target", None)
    nickname = getattr(args, "nickname", None)

    # Two arguments: passx rename <target> <nickname>
    if target and nickname:
        dev_id = ""
        dev_fp = ""
        dev_ip = ""
        with DiscoveryEngine(config, identity) as discovery:
            peer = discovery.find_peer(target)
            if peer:
                dev_id = peer.device_id
                dev_fp = peer.fingerprint
                dev_ip = peer.ip
        if not dev_id:
            for t in trust_manager.list_trusted():
                if target.lower() in t.get("device_name", "").lower() or target == t.get("device_id"):
                    dev_id = t.get("device_id")
                    dev_fp = t.get("fingerprint")
                    dev_ip = t.get("ip", "")
                    break

        alias_mgr.set_alias(target, nickname, device_id=dev_id, fingerprint=dev_fp, ip=dev_ip)
        ip_info = f" ({dev_ip})" if dev_ip else ""
        console.print(f"[bold green]✓ Nickname set:[/bold green] '{target}'{ip_info} will now appear as '[bold cyan]{nickname}[/bold cyan]' everywhere in PASS!")
        return 0

    # One argument: passx rename "NewName"
    if target and not nickname:
        console.print(f"\nTarget name: [bold cyan]{target}[/bold cyan]")
        console.print("1. Rename THIS device to this name")
        console.print("2. Set this as a nickname for a nearby/paired device")
        console.print("0. Cancel")
        c = Prompt.ask("Choose option", choices=["1", "2", "0"], default="1")
        if c == "1":
            config.device_name = target
            console.print(f"[bold green]✓ This device has been renamed to: '{target}'![/bold green]")
            return 0
        elif c == "2":
            nick = target
            with DiscoveryEngine(config, identity) as discovery:
                peers = discovery.scan(timeout=1.5)
            if peers:
                print_devices_table(peers)
                p_idx = Prompt.ask("Select device number", choices=[str(i) for i in range(1, len(peers)+1)], default="1")
                picked = peers[int(p_idx)-1]
                alias_mgr.set_alias(picked.device_name, nick, device_id=picked.device_id, fingerprint=picked.fingerprint, ip=picked.ip)
                console.print(f"[bold green]✓ Nickname set:[/bold green] '{picked.device_name}' ({picked.ip}) is now nicknamed '[bold cyan]{nick}[/bold cyan]'!")
                return 0
            else:
                remote = Prompt.ask("Enter device name or IP to assign nickname to").strip()
                if remote:
                    alias_mgr.set_alias(remote, nick)
                    console.print(f"[bold green]✓ Nickname set:[/bold green] '{remote}' is now nicknamed '[bold cyan]{nick}[/bold cyan]'!")
                    return 0
        return 0

    # Interactive wizard (passx rename with no args)
    console.print("\n[bold cyan]=== Device Nickname & Rename Manager ===[/bold cyan]")
    console.print(f"1. 📱 Rename THIS device (Current: [bold yellow]{identity.device_name}[/bold yellow])")
    console.print("2. 🏷️ Nickname a remote device / peer (e.g. 'IQOO-NEO-10' -> 'My Phone')")
    console.print("3. 📋 View all configured nicknames")
    console.print("4. ❌ Remove a nickname")
    console.print("0. Cancel\n")

    choice = Prompt.ask("Select an option", choices=["1", "2", "3", "4", "0"], default="1")
    if choice == "1":
        new_name = Prompt.ask(f"Enter new name for this device (Current: '{identity.device_name}')", default="").strip()
        if new_name:
            config.device_name = new_name
            console.print(f"[bold green]✓ This device has been renamed to: '{new_name}'![/bold green]")
    elif choice == "2":
        console.print("[cyan]Scanning for nearby devices...[/cyan]")
        with DiscoveryEngine(config, identity) as discovery:
            peers = discovery.scan(timeout=1.5)
        if peers:
            print_devices_table(peers)
            p_idx = Prompt.ask("Select device number (or enter device name/IP directly)", default="1").strip()
            if p_idx.isdigit() and 1 <= int(p_idx) <= len(peers):
                picked = peers[int(p_idx)-1]
                nick = Prompt.ask(f"Enter nickname for '{picked.device_name}'").strip()
                if nick:
                    alias_mgr.set_alias(picked.device_name, nick, device_id=picked.device_id, fingerprint=picked.fingerprint, ip=picked.ip)
                    console.print(f"[bold green]✓ Nickname set:[/bold green] '{picked.device_name}' ({picked.ip}) is now nicknamed '[bold cyan]{nick}[/bold cyan]'!")
            elif p_idx:
                nick = Prompt.ask(f"Enter nickname for '{p_idx}'").strip()
                if nick:
                    alias_mgr.set_alias(p_idx, nick)
                    console.print(f"[bold green]✓ Nickname set:[/bold green] '{p_idx}' is now nicknamed '[bold cyan]{nick}[/bold cyan]'!")
        else:
            target_in = Prompt.ask("Enter device name, IP, or ID to nickname").strip()
            if target_in:
                nick = Prompt.ask(f"Enter nickname for '{target_in}'").strip()
                if nick:
                    alias_mgr.set_alias(target_in, nick)
                    console.print(f"[bold green]✓ Nickname set:[/bold green] '{target_in}' is now nicknamed '[bold cyan]{nick}[/bold cyan]'!")
    elif choice == "3":
        aliases = alias_mgr.list_aliases()
        if not aliases:
            console.print("[yellow]No nicknames configured yet.[/yellow]")
        else:
            from rich.table import Table
            table = Table(title=f"Device Nicknames ({len(aliases)})", border_style="cyan")
            table.add_column("Nickname", style="bold green")
            table.add_column("Original Target", style="cyan")
            table.add_column("IP Address", style="magenta")
            table.add_column("Device ID / Key", style="dim")
            for a in aliases:
                ip_val = a.get("ip") or (a.get("target") if a.get("target", "").count(".") == 3 else "Auto/LAN")
                table.add_row(a.get("nickname", ""), a.get("target", ""), ip_val, a.get("key", "")[:16] + "...")
            console.print(table)
    elif choice == "4":
        aliases = alias_mgr.list_aliases()
        if not aliases:
            console.print("[yellow]No nicknames configured to remove.[/yellow]")
        else:
            for idx, a in enumerate(aliases, 1):
                console.print(f"[{idx}] {a.get('nickname')} -> {a.get('target')}")
            del_c = Prompt.ask("Select nickname number to remove (or 0 to cancel)", default="0").strip()
            if del_c.isdigit() and 1 <= int(del_c) <= len(aliases):
                target_del = aliases[int(del_c)-1].get("key")
                alias_mgr.remove_alias(target_del)
                console.print("[green]✓ Nickname removed.[/green]")

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=__cli_name__,
        description="PASS — Peer-to-peer Automated Secure Sharing CLI",
    )
    parser.add_argument("--debug", action="store_true", help="Enable verbose debug logging")
    parser.add_argument("-v", "--version", action="store_true", help="Show PASS version")

    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # send
    send_p = subparsers.add_parser("send", help="Send file(s) or directory to a nearby PASS device")
    send_p.add_argument("paths", nargs="*", help="File or folder path(s) to transfer (omit to browse/select interactively)")
    send_p.add_argument("--to", help="Destination device name or ID (skips selection prompt)")
    send_p.add_argument("--turbo", action="store_true", help="Enable high-speed turbo streaming (2 MB chunks)")

    # receive
    recv_p = subparsers.add_parser("receive", help="Start PASS in receive mode to accept incoming transfers")
    recv_p.add_argument("--dir", help="Custom directory to save received files")
    recv_p.add_argument("-y", "--yes", action="store_true", help="Automatically accept all incoming transfers")

    # devices
    subparsers.add_parser("devices", help="Scan and list nearby PASS devices on the local network")

    # trust
    trust_p = subparsers.add_parser("trust", help="Trust a discovered device for automated transfers")
    trust_p.add_argument("target", nargs="?", help="Device name or ID to trust (or omit to list trusted)")

    # untrust
    untrust_p = subparsers.add_parser("untrust", help="Remove a device from trusted devices")
    untrust_p.add_argument("target", help="Device name or ID to untrust")

    # status
    subparsers.add_parser("status", help="Show local device identity, network status, and configuration")

    # version
    subparsers.add_parser("version", help="Show PASS version and protocol information")

    # pair
    pair_p = subparsers.add_parser("pair", help="Pair with a nearby device for instant automatic transfers")
    pair_p.add_argument("target", nargs="?", help="Device name or IP address to pair with (or omit to scan)")

    # daemon
    daemon_p = subparsers.add_parser("daemon", help="Manage 24/7 background receiver service")
    daemon_p.add_argument("action", nargs="?", choices=["start", "stop", "status"], default="status", help="Action: start, stop, status (default: status)")

    # auto-accept
    auto_p = subparsers.add_parser("auto-accept", help="Toggle automatic acceptance of incoming transfers")
    auto_p.add_argument("state", nargs="?", choices=["on", "off", "status"], default="status", help="State: on, off, status")

    # chat
    chat_p = subparsers.add_parser("chat", help="Start real-time terminal chat (WhatsApp mode)")
    chat_p.add_argument("target", nargs="?", help="Device name, ID, or IP to chat with (or omit to pick contact)")

    # msg
    msg_p = subparsers.add_parser("msg", help="Send a quick instant message to a device")
    msg_p.add_argument("target", help="Device name, ID, or IP to send to")
    msg_p.add_argument("message", nargs="+", help="Message text to send")

    # clip
    clip_p = subparsers.add_parser("clip", help="Send current clipboard contents directly to a device")
    clip_p.add_argument("target", help="Device name, ID, or IP to send clipboard to")

    # rename / alias / nickname
    rename_p = subparsers.add_parser("rename", help="Rename this device or assign a friendly nickname to another device")
    rename_p.add_argument("target", nargs="?", help="Target device name/IP to nickname, or new name for this device")
    rename_p.add_argument("nickname", nargs="?", help="Nickname to assign to target device")
    rename_p.add_argument("--self", "--me", action="store_true", help="Rename this local device")
    rename_p.add_argument("--list", "-l", action="store_true", help="List all configured device nicknames")
    rename_p.add_argument("--remove", "-r", action="store_true", help="Remove a device nickname")

    alias_p = subparsers.add_parser("alias", help="Assign or manage device nicknames")
    alias_p.add_argument("target", nargs="?", help="Target device name/IP to nickname, or new name for this device")
    alias_p.add_argument("nickname", nargs="?", help="Nickname to assign to target device")
    alias_p.add_argument("--self", "--me", action="store_true", help="Rename this local device")
    alias_p.add_argument("--list", "-l", action="store_true", help="List all configured device nicknames")
    alias_p.add_argument("--remove", "-r", action="store_true", help="Remove a device nickname")

    nick_p = subparsers.add_parser("nickname", help="Assign or manage device nicknames")
    nick_p.add_argument("target", nargs="?", help="Target device name/IP to nickname, or new name for this device")
    nick_p.add_argument("nickname", nargs="?", help="Nickname to assign to target device")
    nick_p.add_argument("--self", "--me", action="store_true", help="Rename this local device")
    nick_p.add_argument("--list", "-l", action="store_true", help="List all configured device nicknames")
    nick_p.add_argument("--remove", "-r", action="store_true", help="Remove a device nickname")

    # update
    subparsers.add_parser("update", help="Update PASS to the latest version directly from GitHub")

    return parser


def main(argv=None) -> int:
    if sys.platform.startswith("win"):
        import os
        os.system("")
        if hasattr(sys.stdout, "reconfigure"):
            try:
                sys.stdout.reconfigure(encoding="utf-8")
                sys.stderr.reconfigure(encoding="utf-8")
            except Exception:
                pass

    if argv is None:
        argv = sys.argv[1:]

    parser = build_parser()
    args = parser.parse_args(argv)

    setup_logging(args.debug)

    if args.version:
        return cmd_version()

    config = ConfigManager()
    identity = DeviceIdentity(config)
    trust_manager = TrustManager(config)

    if not args.command:
        # Launch interactive menu when run with no arguments
        try:
            interactive_menu(config, identity, trust_manager)
            return 0
        except KeyboardInterrupt:
            console.print("\n[yellow]Exiting PASS.[/yellow]")
            return 0

    if args.command == "send":
        return cmd_send(args, config, identity, trust_manager)
    elif args.command == "receive":
        return cmd_receive(args, config, identity, trust_manager)
    elif args.command == "devices":
        return cmd_devices(args, config, identity)
    elif args.command == "trust":
        return cmd_trust(args, config, identity, trust_manager)
    elif args.command == "untrust":
        return cmd_untrust(args, trust_manager)
    elif args.command == "status":
        return cmd_status(args, config, identity, trust_manager)
    elif args.command == "version":
        return cmd_version()
    elif args.command == "update":
        return cmd_update()
    elif args.command == "pair":
        return cmd_pair(args, config, identity, trust_manager)
    elif args.command == "daemon":
        return cmd_daemon(args, config)
    elif args.command in ("auto-accept", "autoaccept"):
        return cmd_auto_accept(args, config)
    elif args.command == "chat":
        return cmd_chat(args, config, identity, trust_manager)
    elif args.command == "msg":
        return cmd_msg(args, config, identity, trust_manager)
    elif args.command == "clip":
        return cmd_clip(args, config, identity, trust_manager)
    elif args.command in ("rename", "alias", "nickname"):
        return cmd_rename(args, config, identity, trust_manager)
    else:
        parser.print_help()
        return 1
