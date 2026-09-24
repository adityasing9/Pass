"""WhatsApp-style interactive terminal chat (TUI) for PASS"""
import datetime
import os
import sys
import threading
import time
from pathlib import Path
from typing import Optional, Dict, Any, List

from rich.align import Align
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text

from passx.core.config import ConfigManager
from passx.core.identity import DeviceIdentity
from passx.core.trust import TrustManager
from passx.core.chat_store import ChatStore
from passx.core.chat_client import send_chat
from passx.discovery.engine import DiscoveryEngine
from passx.discovery.beacon import PeerInfo
from passx.platform import current_platform
from passx.transfer.manifest import build_manifest_from_paths
from passx.transfer.receiver import ReceiverServer
from passx.transfer.sender import TransferSender
from .formatters import format_bytes
from .progress import TransferProgressTracker

console = Console()


def format_timestamp(ts: float) -> str:
    """Format Unix timestamp into human-readable HH:MM:SS"""
    dt = datetime.datetime.fromtimestamp(ts)
    return dt.strftime("%H:%M:%S")


def render_message_bubble(msg: Dict[str, Any], peer_name: str) -> None:
    """Render a single message as a chat bubble"""
    sender = msg.get("sender", "peer")
    text = msg.get("text", "")
    ts_str = format_timestamp(msg.get("timestamp", time.time()))
    msg_type = msg.get("type", "text")

    if sender == "me":
        # Outgoing message (Right-aligned, green)
        title = f"[bold green]You[/bold green] [dim]{ts_str}[/dim] [green]✓✓[/green]"
        border_style = "green"
        if msg_type == "file":
            content = f"[bold yellow]{text}[/bold yellow]"
            border_style = "yellow"
        else:
            content = text
        panel = Panel(content, title=title, border_style=border_style, expand=False)
        console.print(Align.right(panel))
    else:
        # Incoming message (Left-aligned, cyan)
        name = msg.get("sender_name") or peer_name
        title = f"[bold cyan]📱 {name}[/bold cyan] [dim]{ts_str}[/dim]"
        border_style = "cyan"
        if msg_type == "file":
            content = f"[bold yellow]{text}[/bold yellow]"
            border_style = "yellow"
        else:
            content = text
        panel = Panel(content, title=title, border_style=border_style, expand=False)
        console.print(Align.left(panel))


def clear_screen() -> None:
    """Clear terminal screen"""
    os.system("cls" if os.name == "nt" else "clear")


def print_chat_header(peer_name: str, peer_ip: str, peer_port: int, is_online: bool = True) -> None:
    """Print the chat conversation header banner"""
    status_icon = "🟢 ONLINE" if is_online else "⚪ OFFLINE"
    title_text = f"💬 PASS Chat — {peer_name} ({peer_ip}:{peer_port})  {status_icon}"
    sub_text = "End-to-End TLS Encrypted • Direct P2P • No Cloud Servers • 100% Private"
    
    panel = Panel(
        f"[bold white]{title_text}[/bold white]\n[dim]{sub_text}[/dim]",
        border_style="bright_blue",
        padding=(0, 2),
    )
    console.print(panel)
    console.print("[dim]Commands: [bold]/send <path>[/bold] (attach file/folder) | [bold]/clip[/bold] (send clipboard) | [bold]/clear[/bold] | [bold]/history[/bold] | [bold]/exit[/bold][/dim]")
    console.print("─" * min(console.width, 80))


def pick_contact_interactively(
    config: ConfigManager,
    identity: DeviceIdentity,
    trust_manager: TrustManager,
) -> Optional[PeerInfo]:
    """Show WhatsApp-style contact list combining discovered and past chats"""
    console.print("[cyan]Scanning for nearby PASS devices...[/cyan]")
    discovered_peers: List[PeerInfo] = []
    with DiscoveryEngine(config, identity) as discovery:
        discovered_peers = discovery.scan(timeout=1.5)

    chat_store = ChatStore(config)
    conversations = chat_store.list_conversations()

    # Build contact list
    contacts = []
    seen_ids = set()

    # 1. Add discovered online peers
    for p in discovered_peers:
        seen_ids.add(p.device_id)
        contacts.append({
            "name": p.device_name,
            "id": p.device_id,
            "ip": p.ip,
            "port": p.port,
            "online": True,
            "peer_info": p,
        })

    # 2. Add past conversations if not already discovered
    for c in conversations:
        pid = c["peer_id"]
        if pid not in seen_ids and pid != "unknown":
            contacts.append({
                "name": c["peer_name"],
                "id": pid,
                "ip": "",
                "port": config.transfer_port,
                "online": False,
                "peer_info": None,
                "last_msg": c.get("last_message", ""),
            })

    table = Table(title="💬 PASS Contacts (WhatsApp Mode)", border_style="cyan")
    table.add_column("#", style="bold yellow", width=4)
    table.add_column("Status", width=10)
    table.add_column("Device / Contact", style="bold white")
    table.add_column("Address / Last Message", style="dim")

    if not contacts:
        console.print("[yellow]No PASS devices found online, and no past chats recorded.[/yellow]")
        console.print("[dim]You can connect directly by IP address.[/dim]\n")
        direct_ip = Prompt.ask("Enter receiver IP address directly (or press Enter to cancel)", default="").strip()
        if direct_ip:
            return PeerInfo(
                device_id="direct-ip",
                device_name=direct_ip,
                platform="unknown",
                ip=direct_ip,
                port=config.transfer_port,
                fingerprint="",
                capabilities=[],
            )
        return None

    for idx, c in enumerate(contacts, 1):
        status_badge = "[green]🟢 Online[/green]" if c["online"] else "[dim]⚪ Offline[/dim]"
        addr_or_msg = f"{c['ip']}:{c['port']}" if c["online"] else f"Last: {c.get('last_msg', '')[:30]}"
        table.add_row(str(idx), status_badge, c["name"], addr_or_msg)

    console.print(table)
    console.print("[dim]Tip: Enter [bold]D[/bold] for direct IP, or [bold]0[/bold] to cancel.[/dim]")

    choice = Prompt.ask("\nSelect contact", default="1").strip()
    if choice in ("0", "cancel", "q", "exit"):
        return None
    if choice.upper() == "D":
        direct_ip = Prompt.ask("Enter receiver IP address", default="").strip()
        if direct_ip:
            return PeerInfo(
                device_id="direct-ip",
                device_name=direct_ip,
                platform="unknown",
                ip=direct_ip,
                port=config.transfer_port,
                fingerprint="",
                capabilities=[],
            )
        return None

    try:
        idx = int(choice) - 1
        if 0 <= idx < len(contacts):
            selected = contacts[idx]
            if selected["peer_info"]:
                return selected["peer_info"]
            else:
                # Was offline from history, ask for IP or probe
                ip = Prompt.ask(f"Enter IP address for '{selected['name']}'", default="").strip()
                if ip:
                    return PeerInfo(
                        device_id=selected["id"],
                        device_name=selected["name"],
                        platform="unknown",
                        ip=ip,
                        port=selected["port"],
                        fingerprint="",
                        capabilities=[],
                    )
    except ValueError:
        pass

    return None


def run_chat_session(
    target_peer: PeerInfo,
    config: ConfigManager,
    identity: DeviceIdentity,
    trust_manager: TrustManager,
) -> None:
    """Run an interactive real-time chat session with a peer"""
    peer_id = target_peer.device_id
    peer_name = target_peer.device_name
    peer_ip = target_peer.ip
    peer_port = target_peer.port

    chat_store = ChatStore(config)

    # Ensure a local receiver is running so replies can be received
    local_receiver: Optional[ReceiverServer] = None
    try:
        # Test if receiver port is already listening (e.g. background daemon)
        import socket
        test_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        test_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            test_sock.bind(("0.0.0.0", config.transfer_port))
            # If bind succeeded, daemon is not running, so start an in-process receiver!
            test_sock.close()
            local_receiver = ReceiverServer(config, identity, trust_manager)
            local_receiver.start()
        except OSError:
            # Port already in use by background daemon — perfect!
            try:
                test_sock.close()
            except Exception:
                pass
    except Exception:
        pass

    clear_screen()
    print_chat_header(peer_name, peer_ip, peer_port, is_online=True)

    # Load recent history
    history = chat_store.get_history(peer_id, limit=20)
    seen_ids = set()
    for m in history:
        seen_ids.add(m.get("id"))
        render_message_bubble(m, peer_name)

    running = True

    # Background polling thread for live incoming messages
    def poll_incoming():
        while running:
            time.sleep(0.4)
            try:
                latest = chat_store.get_history(peer_id, limit=30)
                for m in latest:
                    mid = m.get("id")
                    if mid and mid not in seen_ids:
                        seen_ids.add(mid)
                        render_message_bubble(m, peer_name)
            except Exception:
                pass

    poller_thread = threading.Thread(target=poll_incoming, name="chat-poller", daemon=True)
    poller_thread.start()

    try:
        while running:
            try:
                user_input = Prompt.ask(f"[bold green]You[/bold green]").strip()
            except (KeyboardInterrupt, EOFError):
                break

            if not user_input:
                continue

            # Command: /exit or /quit
            if user_input in ("/exit", "/quit", "/q"):
                break

            # Command: /clear
            if user_input == "/clear":
                clear_screen()
                print_chat_header(peer_name, peer_ip, peer_port, is_online=True)
                history = chat_store.get_history(peer_id, limit=10)
                for m in history:
                    render_message_bubble(m, peer_name)
                continue

            # Command: /history
            if user_input == "/history":
                console.print("\n[bold dim]─── Older Conversation History ───[/bold dim]")
                older = chat_store.get_history(peer_id, limit=50)
                for m in older:
                    render_message_bubble(m, peer_name)
                console.print("[bold dim]──────────────────────────────────[/bold dim]\n")
                continue

            # Command: /clip (send clipboard contents)
            if user_input == "/clip":
                clip_text = current_platform.get_clipboard_text()
                if not clip_text:
                    console.print("[yellow]Clipboard is empty or could not be accessed.[/yellow]")
                    continue
                console.print(f"[cyan]Sending clipboard ({len(clip_text)} chars)...[/cyan]")
                user_input = f"📋 [Clipboard]: {clip_text}"

            # Command: /send <path>
            if user_input.startswith("/send "):
                raw_path = user_input[6:].strip()
                resolved = current_platform.resolve_smart_path(raw_path)
                if not resolved.exists():
                    console.print(f"[red]Error: Path '{resolved}' does not exist.[/red]")
                    continue

                console.print(f"[cyan]Preparing '{resolved.name}' to send...[/cyan]")
                try:
                    manifest = build_manifest_from_paths([resolved])
                    tracker = TransferProgressTracker()
                    sender = TransferSender(config, identity, trust_manager)

                    with tracker.progress:
                        sender.send_transfer(
                            peer_host=peer_ip,
                            peer_port=peer_port,
                            manifest=manifest,
                            peer_fingerprint=target_peer.fingerprint,
                            progress_callback=tracker.update_progress,
                        )

                    console.print(f"[bold green]✓ Sent successfully:[/bold green] {resolved.name} ({format_bytes(manifest.total_bytes)})")
                except Exception as e:
                    console.print(f"[bold red]File transfer failed:[/bold red] {e}")
                continue

            # Regular text message
            success, status_msg, saved_dict = send_chat(
                peer_ip=peer_ip,
                peer_port=peer_port,
                text=user_input,
                config=config,
                identity=identity,
                trust_manager=trust_manager,
                peer_id=peer_id,
                peer_name=peer_name,
            )

            if success and saved_dict:
                seen_ids.add(saved_dict.get("id"))
                render_message_bubble(saved_dict, peer_name)
            else:
                console.print(f"[bold red]✗ Delivery failed:[/bold red] {status_msg}")

    finally:
        running = False
        if local_receiver:
            local_receiver.stop()
        console.print("[yellow]Exited chat.[/yellow]")
