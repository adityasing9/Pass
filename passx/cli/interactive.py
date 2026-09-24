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
        console.print("[bold cyan]4.[/bold cyan] Pair & manage trusted devices")
        console.print("[bold cyan]5.[/bold cyan] 💬 Terminal Chat (WhatsApp Mode)")
        console.print("[bold cyan]6.[/bold cyan] Background service & settings")
        console.print("[bold cyan]7.[/bold cyan] Exit")
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
        elif cmd in ("4", "pair", "trust"):
            _handle_pair_interactive(config, identity, trust_manager)
        elif cmd in ("5", "c", "chat", "msg", "whatsapp"):
            _handle_chat_interactive(config, identity, trust_manager)
        elif cmd in ("6", "settings", "status", "daemon", "config"):
            _handle_settings_interactive(config, identity, trust_manager)
        elif cmd in ("update", "upgrade"):
            from .main import cmd_update
            cmd_update()
        elif cmd in ("7", "exit", "quit", "q"):
            console.print("[green]Goodbye![/green]")
            break
        else:
            console.print(f"[yellow]Unknown option '{raw_choice}'. Please enter 1-7 or 'chat', 'send', 'exit'.[/yellow]")

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
        console.print("[yellow]No PASS devices found automatically on your local network.[/yellow]")
        console.print("[dim]Tip: Ensure the receiving device is on the same Wi-Fi/Hotspot and running 'passx receive' (Option 2).[/dim]")
        manual_ip = Prompt.ask("\nEnter receiver IP address manually (or press Enter to cancel)", default="").strip()
        if not manual_ip:
            return
        from passx.discovery.beacon import PeerInfo
        selected_peer = PeerInfo(
            device_id="direct-ip",
            device_name=manual_ip,
            platform="unknown",
            ip=manual_ip,
            port=config.transfer_port,
            fingerprint="",
            capabilities=[],
        )
    else:
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
    from passx.network.interfaces import get_active_ipv4_interfaces
    ifaces = get_active_ipv4_interfaces()
    ip_str = ", ".join(ip for _, ip, _ in ifaces if not ip.startswith("127."))
    if not ip_str:
        ip_str = "0.0.0.0"

    console.print("\n[bold green]Starting PASS Receiver...[/bold green]")
    console.print(f"Device Name: [green]{identity.device_name}[/green]")
    console.print(f"Local IP(s):  [bold green]{ip_str}[/bold green]")
    console.print(f"Download directory: [cyan]{config.download_dir}[/cyan]")
    console.print(f"Transfer Port: [yellow]{config.transfer_port}[/yellow]")
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


def _handle_pair_interactive(config: ConfigManager, identity: DeviceIdentity, trust_manager: TrustManager):
    console.print("\n[bold cyan]Pair & Manage Trusted Devices[/bold cyan]")
    console.print("[dim]Paired devices transfer files automatically without confirmation prompts.[/dim]\n")
    console.print("1. 🔍 Scan & pair with nearby device (1-click)")
    console.print("2. 🌐 Pair by IP address")
    console.print("3. 📋 View paired devices")
    console.print("4. ❌ Remove a paired device")
    console.print("5. 🏷️ Set or manage device nicknames")

    choice = Prompt.ask("\nSelect action", choices=["1", "2", "3", "4", "5"], default="1")

    if choice == "1":
        from .main import cmd_pair
        class DummyArgs:
            target = None
        cmd_pair(DummyArgs(), config, identity, trust_manager)

    elif choice == "2":
        ip = Prompt.ask("Enter device IP address to pair with").strip()
        if ip:
            from .main import cmd_pair
            class DummyArgs:
                target = ip
            cmd_pair(DummyArgs(), config, identity, trust_manager)

    elif choice == "3":
        trusted = trust_manager.list_trusted()
        print_trusted_table(trusted)

    elif choice == "4":
        trusted = trust_manager.list_trusted()
        print_trusted_table(trusted)
        if trusted:
            name_or_id = Prompt.ask("\nEnter device name or ID to untrust")
            if trust_manager.untrust_device(name_or_id):
                console.print(f"[green]✓ Removed '{name_or_id}' from trusted devices.[/green]")
            else:
                console.print(f"[yellow]No matching trusted device found for '{name_or_id}'.[/yellow]")

    elif choice == "5":
        from .main import cmd_rename
        class DummyRenameArgs:
            target = None
            nickname = None
            list = False
            remove = False
        setattr(DummyRenameArgs, "self", False)
        cmd_rename(DummyRenameArgs(), config, identity, trust_manager)


def _handle_settings_interactive(config: ConfigManager, identity: DeviceIdentity, trust_manager: TrustManager):
    from passx.core.daemon import get_daemon_status, start_daemon, stop_daemon

    is_running, pid, log_path = get_daemon_status(config.config_dir)
    daemon_status = f"[bold green]ACTIVE (PID {pid})[/bold green]" if is_running else "[yellow]OFF[/yellow]"
    auto_acc = config.get("auto_accept_all", False)
    auto_status = "[bold green]ON[/bold green]" if auto_acc else "[yellow]OFF[/yellow]"

    console.print("\n[bold cyan]Background Service & Settings[/bold cyan]")
    console.print(f"Background Receiver: {daemon_status}")
    console.print(f"Auto-Accept Mode:    {auto_status}")
    console.print(f"Device Name:         [cyan]{identity.device_name}[/cyan]")
    console.print(f"Downloads Folder:    [cyan]{config.download_dir}[/cyan]")
    console.print(f"Transfer Port:       [yellow]{config.transfer_port}[/yellow]")
    console.print()

    console.print("1. Toggle Background Receiver (Daemon)")
    console.print("2. Toggle Auto-Accept Mode (Accept all incoming transfers automatically)")
    console.print("3. Edit Device Name or Download Folder")
    console.print("4. Return to main menu")

    opt = Prompt.ask("\nSelect option", choices=["1", "2", "3", "4"], default="1")

    if opt == "1":
        if is_running:
            stop_daemon(config.config_dir)
            console.print("[green]✓ Background receiver stopped.[/green]")
        else:
            ok, msg, new_pid = start_daemon(config.config_dir)
            if ok:
                console.print(f"[bold green]✓ Background receiver started! (PID {new_pid})[/bold green]")
                console.print("[dim]PASS is now running 24/7 in background. You do not need to open PASS to receive files![/dim]")
            else:
                console.print(f"[yellow]{msg}[/yellow]")

    elif opt == "2":
        new_val = not auto_acc
        config.set("auto_accept_all", new_val)
        status_txt = "ENABLED (All incoming transfers will be auto-accepted with zero confirmation prompts!)" if new_val else "DISABLED"
        console.print(f"[bold green]Auto-accept is now {status_txt}[/bold green]")

    elif opt == "3":
        new_name = Prompt.ask("New device name (leave blank to keep)", default="")
        if new_name.strip():
            config.device_name = new_name.strip()
            console.print("[green]Device name updated![/green]")

        new_dl = Prompt.ask("New download directory (leave blank to keep)", default="")
        if new_dl.strip():
            p = Path(os.path.expanduser(new_dl.strip()))
            config.download_dir = p
            console.print("[green]Download directory updated![/green]")


def _handle_chat_interactive(
    config: ConfigManager,
    identity: DeviceIdentity,
    trust_manager: TrustManager,
) -> None:
    from passx.cli.chat_ui import pick_contact_interactively, run_chat_session
    peer = pick_contact_interactively(config, identity, trust_manager)
    if peer:
        run_chat_session(peer, config, identity, trust_manager)
