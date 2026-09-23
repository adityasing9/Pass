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

    console.print(f"[bold green]Transfer Manifest:[/bold green] {manifest.file_count} file(s), {format_bytes(manifest.total_bytes)}")

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
    print_banner(identity.device_name, current_platform.get_platform_name())

    console.print("[bold]Device Information:[/bold]")
    console.print(f"  Device Name:      [cyan]{identity.device_name}[/cyan]")
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
            return 1
    except Exception as e:
        console.print(f"[red]Error during update: {e}[/red]")
        return 1


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
    else:
        parser.print_help()
        return 1
