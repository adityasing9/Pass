"""Terminal interactive menu loop for bare 'passx' invocation"""
import os
import sys
from pathlib import Path
from typing import List
from rich.console import Console
from rich.prompt import Prompt, Confirm

from passx.core.config import ConfigManager
from passx.core.identity import DeviceIdentity
from passx.core.trust import TrustManager
from passx.discovery.engine import DiscoveryEngine
from passx.platform import current_platform
from passx.transfer.manifest import build_manifest_from_paths
from passx.transfer.receiver import ReceiverServer
from passx.transfer.sender import TransferSender, TransferRejected, PeerVerificationError
from .formatters import print_banner, print_devices_table, print_trusted_table, format_bytes
from .progress import TransferProgressTracker

console = Console()


def interactive_menu(
    config: ConfigManager,
    identity: DeviceIdentity,
    trust_manager: TrustManager,
) -> None:
    """Main interactive terminal loop"""
    while True:
        console.clear()
        print_banner(identity.device_name, current_platform.get_platform_name())

        console.print("[bold cyan]1.[/bold cyan] Send file(s) or folder")
        console.print("[bold cyan]2.[/bold cyan] Receive mode (Wait for transfers)")
        console.print("[bold cyan]3.[/bold cyan] Discover nearby PASS devices")
        console.print("[bold cyan]4.[/bold cyan] Manage trusted devices")
        console.print("[bold cyan]5.[/bold cyan] Device settings & status")
        console.print("[bold cyan]6.[/bold cyan] Exit")
        console.print()

        raw_choice = Prompt.ask("Select an option", default="1").strip()
        cleaned = raw_choice
        if cleaned.lower().startswith("passx "):
            cleaned = cleaned[6:].strip()

        # Parse command or menu number
        parts = cleaned.split(maxsplit=1)
        cmd = parts[0].lower() if parts else "1"
        arg = parts[1] if len(parts) > 1 else None

        if cmd in ("1", "send"):
            _handle_send_interactive(config, identity, trust_manager, initial_path=arg)
        elif cmd in ("2", "receive", "recv"):
            _handle_receive_interactive(config, identity, trust_manager)
        elif cmd in ("3", "devices", "scan", "list"):
            _handle_devices_interactive(config, identity)
        elif cmd in ("4", "trust"):
            _handle_trust_interactive(trust_manager)
        elif cmd in ("5", "settings", "status", "config"):
            _handle_settings_interactive(config, identity)
        elif cmd in ("6", "exit", "quit", "q"):
            console.print("[green]Goodbye![/green]")
            break
        else:
            console.print(f"[yellow]Unknown option '{raw_choice}'. Please enter 1-6 or a command like 'send', 'receive', 'devices', 'exit'.[/yellow]")

        Prompt.ask("\n[dim]Press Enter to return to menu...[/dim]", default="")


def _handle_send_interactive(
    config: ConfigManager,
    identity: DeviceIdentity,
    trust_manager: TrustManager,
    initial_path: str = None,
):
    if initial_path:
        raw_path = initial_path.strip().strip("\"'")
        target_path = current_platform.resolve_smart_path(raw_path)
        if not target_path.exists():
            console.print(f"[red]Error: Path '{target_path}' does not exist.[/red]")
            return
        target_paths = [target_path]
    else:
        from .picker import select_files_interactively
        target_paths = select_files_interactively()
        if not target_paths:
            return

    try:
        manifest = build_manifest_from_paths(target_paths)
    except Exception as e:
        console.print(f"[red]Failed to build transfer manifest: {e}[/red]")
        return

    console.print(f"[green]Ready to send:[/green] {manifest.file_count} file(s), total {format_bytes(manifest.total_bytes)}")
    console.print("[cyan]Searching for nearby PASS devices...[/cyan]")

    with DiscoveryEngine(config, identity) as discovery:
        peers = discovery.scan(timeout=2.0)

    if not peers:
        console.print("[yellow]No PASS devices found on your local network.[/yellow]")
        console.print("[dim]Ensure the receiving device has PASS open or is running 'passx receive'.[/dim]")
        return

    print_devices_table(peers)
    peer_choices = [str(i) for i in range(1, len(peers) + 1)]
    peer_idx = Prompt.ask("Select device number", choices=peer_choices, default="1")
    selected_peer = peers[int(peer_idx) - 1]

    console.print(f"\n[cyan]Connecting to [bold]{selected_peer.device_name}[/bold] ({selected_peer.ip}:{selected_peer.port})...[/cyan]")

    sender = TransferSender(config, identity, trust_manager)
    try:
        with TransferProgressTracker("Sending") as tracker:
            sender.send(
                peer_ip=selected_peer.ip,
                peer_port=selected_peer.port,
                peer_fingerprint=selected_peer.fingerprint,
                manifest=manifest,
                progress_callback=tracker.update,
            )
        console.print("\n[bold green]✓ Transfer completed successfully and verified with SHA-256![/bold green]")
    except TransferRejected as e:
        console.print(f"\n[yellow]Transfer was rejected: {e}[/yellow]")
    except PeerVerificationError as e:
        console.print(f"\n[red]Security error: {e}[/red]")
    except Exception as e:
        console.print(f"\n[red]Transfer failed: {e}[/red]")


def _handle_receive_interactive(config: ConfigManager, identity: DeviceIdentity, trust_manager: TrustManager):
    console.print("\n[bold green]Starting PASS Receiver...[/bold green]")
    console.print(f"Download directory: [cyan]{config.download_dir}[/cyan]")
    console.print("[dim]Listening for incoming connections and advertising presence... (Press Ctrl+C to stop)[/dim]\n")

    def on_request(sender_info: dict, manifest) -> bool:
        console.print("\n[bold yellow]Incoming transfer request![/bold yellow]")
        console.print(f"From: [bold cyan]{sender_info.get('sender_name')}[/bold cyan] ({sender_info.get('ip')})")
        console.print(f"Files: {manifest.file_count} file(s), Total size: {format_bytes(manifest.total_bytes)}")

        accepted = Confirm.ask("Accept incoming transfer?", default=True)
        if accepted:
            sender_id = sender_info.get("sender_id")
            sender_fp = sender_info.get("fingerprint")
            sender_name = sender_info.get("sender_name")
            if not trust_manager.is_trusted(sender_id, sender_fp):
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
                import time
                time.sleep(0.5)
    except KeyboardInterrupt:
        console.print("\n[yellow]Stopping receiver...[/yellow]")
    finally:
        discovery.stop()
        receiver.stop()


def _handle_devices_interactive(config: ConfigManager, identity: DeviceIdentity):
    console.print("\n[cyan]Scanning local network for PASS devices (2 seconds)...[/cyan]")
    with DiscoveryEngine(config, identity) as discovery:
        peers = discovery.scan(timeout=2.0)
    print_devices_table(peers)


def _handle_trust_interactive(trust_manager: TrustManager):
    trusted = trust_manager.list_trusted()
    print_trusted_table(trusted)
    if trusted:
        if Confirm.ask("\nWould you like to remove a trusted device?", default=False):
            name_or_id = Prompt.ask("Enter device name or ID to untrust")
            if trust_manager.untrust_device(name_or_id):
                console.print(f"[green]Removed '{name_or_id}' from trusted devices.[/green]")
            else:
                console.print(f"[yellow]No matching trusted device found for '{name_or_id}'.[/yellow]")


def _handle_settings_interactive(config: ConfigManager, identity: DeviceIdentity):
    console.print("\n[bold]Current Settings & Device Identity:[/bold]")
    console.print(f"Device Name: [cyan]{identity.device_name}[/cyan]")
    console.print(f"Device ID: [dim]{identity.device_id}[/dim]")
    console.print(f"Download Folder: [cyan]{config.download_dir}[/cyan]")
    console.print(f"Discovery Port: [cyan]{config.discovery_port}[/cyan] (UDP)")
    console.print(f"Transfer Port: [cyan]{config.transfer_port}[/cyan] (TCP)")
    console.print(f"TLS Fingerprint: [dim]{identity.fingerprint}[/dim]")

    if Confirm.ask("\nEdit settings?", default=False):
        new_name = Prompt.ask("New device name (leave blank to keep)", default="")
        if new_name.strip():
            config.device_name = new_name.strip()
            console.print("[green]Device name updated![/green]")

        new_dl = Prompt.ask("New download directory (leave blank to keep)", default="")
        if new_dl.strip():
            p = Path(os.path.expanduser(new_dl.strip()))
            config.download_dir = p
            console.print("[green]Download directory updated![/green]")
