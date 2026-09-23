"""Interactive terminal file and folder picker"""
import datetime
import os
import sys
from pathlib import Path
from typing import List, Optional
from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.table import Table

from passx.cli.formatters import format_bytes
from passx.platform import current_platform

console = Console()


def _format_time_ago(timestamp: float) -> str:
    diff = datetime.datetime.now() - datetime.datetime.fromtimestamp(timestamp)
    seconds = int(diff.total_seconds())
    if seconds < 60:
        return f"{seconds}s ago"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h ago"
    days = hours // 24
    if days < 7:
        return f"{days}d ago"
    return datetime.datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d")


def pick_from_file_list(title: str, directory: Path, limit: int = 15) -> List[Path]:
    """Displays a numbered list of files in a directory sorted by newest first"""
    if not directory.exists():
        console.print(f"[yellow]Directory not found: {directory}[/yellow]")
        return []

    try:
        entries = [f for f in directory.iterdir() if f.is_file()]
    except Exception as e:
        console.print(f"[red]Error reading directory: {e}[/red]")
        return []

    if not entries:
        console.print(f"[yellow]No files found in {directory}[/yellow]")
        return []

    # Sort newest first
    entries.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    displayed = entries[:limit]

    table = Table(title=f"{title} (Showing latest {len(displayed)})", border_style="cyan")
    table.add_column("#", style="bold green", width=4)
    table.add_column("File Name", style="bold")
    table.add_column("Size", style="cyan")
    table.add_column("Modified", style="dim")

    for idx, f in enumerate(displayed, 1):
        stat = f.stat()
        table.add_row(
            str(idx),
            f.name,
            format_bytes(stat.st_size),
            _format_time_ago(stat.st_mtime),
        )

    console.print(table)
    console.print("[dim]You can select multiple numbers separated by commas (e.g. 1, 2, 4) or 'all'[/dim]")

    choice = Prompt.ask("Select file number(s) to send (or 'b' to go back)", default="1").strip()
    if choice.lower() in ("b", "back", "cancel", "q"):
        return []

    if choice.lower() == "all":
        return displayed

    selected = []
    for part in choice.replace(" ", ",").split(","):
        part = part.strip()
        if part.isdigit():
            idx = int(part)
            if 1 <= idx <= len(displayed):
                selected.append(displayed[idx - 1])

    return selected


def browse_directory_interactive(start_dir: Optional[Path] = None) -> List[Path]:
    """Interactive directory navigator to browse and select files/folders"""
    curr = (start_dir or Path.cwd()).resolve()

    while True:
        console.clear()
        console.print(f"[bold cyan]Browsing:[/bold cyan] {curr}\n")

        try:
            items = list(curr.iterdir())
        except Exception as e:
            console.print(f"[red]Permission error reading directory: {e}[/red]")
            return []

        dirs = sorted([d for d in items if d.is_dir()], key=lambda x: x.name.lower())
        files = sorted([f for f in items if f.is_file()], key=lambda x: x.name.lower())
        all_items = dirs + files

        table = Table(border_style="cyan")
        table.add_column("#", style="bold green", width=4)
        table.add_column("Type", width=6)
        table.add_column("Name", style="bold")
        table.add_column("Size", style="dim")

        # Parent directory option
        table.add_row("..", "📁 DIR", "[Parent Directory]", "")

        for idx, item in enumerate(all_items, 1):
            if item.is_dir():
                table.add_row(str(idx), "📁 DIR", item.name, "<FOLDER>")
            else:
                table.add_row(str(idx), "📄 FILE", item.name, format_bytes(item.stat().st_size))

        console.print(table)
        console.print("[dim]Commands: <#> to open folder/select, 's <#>' to send, 's .' to send this folder, 'b' to back[/dim]")

        action = Prompt.ask("Action", default="..").strip()

        if action in ("b", "back", "q", "cancel"):
            return []

        if action == "..":
            if curr.parent != curr:
                curr = curr.parent
            continue

        if action == "s .":
            return [curr]

        # Send command: s <#>
        if action.lower().startswith("s ") or action.lower().startswith("send "):
            parts = action.split()
            if len(parts) > 1 and parts[1].isdigit():
                idx = int(parts[1])
                if 1 <= idx <= len(all_items):
                    return [all_items[idx - 1]]

        # Direct number selection
        if action.isdigit():
            idx = int(action)
            if 1 <= idx <= len(all_items):
                target = all_items[idx - 1]
                if target.is_dir():
                    curr = target
                else:
                    if Confirm.ask(f"Send '{target.name}'?", default=True):
                        return [target]


def open_native_gui_picker() -> List[Path]:
    """Attempts to open native OS file dialog (Windows / macOS / Linux GUI)"""
    try:
        import tkinter
        import tkinter.filedialog
        root = tkinter.Tk()
        root.withdraw()
        root.attributes("-topmost", True)

        file_paths = tkinter.filedialog.askopenfilenames(title="PASS - Select File(s) to Send")
        root.destroy()
        if file_paths:
            return [Path(p) for p in file_paths]
    except Exception:
        pass
    return []


def select_files_interactively() -> List[Path]:
    """Main entry point to select files/folders without typing paths"""
    is_termux = current_platform.get_platform_name() == "android"

    while True:
        console.print("\n[bold cyan]Select where to pick files from:[/bold cyan]")
        options = []

        if is_termux:
            options.append(("1", "📸 Camera Photos (DCIM)", "camera"))
            options.append(("2", "📥 Downloads Folder", "downloads"))
            options.append(("3", "📁 Shared Documents", "documents"))
            options.append(("4", "📂 Browse Termux / Storage", "browse"))
            options.append(("5", "✍️ Enter path manually", "manual"))
        else:
            options.append(("1", "🖥️ Desktop Folder", "desktop"))
            options.append(("2", "📥 Downloads Folder", "downloads"))
            options.append(("3", "📂 Browse Current Directory", "browse_cwd"))
            options.append(("4", "🗂️ Browse Any Directory", "browse"))
            options.append(("5", "🖱️ Open Windows File Explorer Picker", "gui"))
            options.append(("6", "✍️ Enter path manually", "manual"))

        for key, label, _ in options:
            console.print(f"[bold green]{key}.[/bold green] {label}")

        choice = Prompt.ask("\nChoose an option", default="1").strip()

        # Find matching tag
        tag = None
        for key, _, t in options:
            if choice == key:
                tag = t
                break

        if not tag:
            console.print("[yellow]Invalid option, please choose from the list.[/yellow]")
            continue

        if tag == "camera":
            cam_dirs = [
                Path.home() / "storage" / "dcim" / "Camera",
                Path.home() / "storage" / "shared" / "DCIM" / "Camera",
            ]
            cam_dir = next((d for d in cam_dirs if d.exists()), cam_dirs[0])
            files = pick_from_file_list("Camera Photos", cam_dir)
            if files:
                return files

        elif tag == "downloads":
            if is_termux:
                dl_dir = Path.home() / "storage" / "downloads"
            else:
                dl_dir = Path.home() / "Downloads"
            files = pick_from_file_list("Downloads Folder", dl_dir)
            if files:
                return files

        elif tag == "desktop":
            dt_dir = current_platform.get_default_download_dir()
            files = pick_from_file_list("Desktop Folder", dt_dir)
            if files:
                return files

        elif tag == "documents":
            doc_dir = Path.home() / "storage" / "shared" / "Documents"
            files = pick_from_file_list("Documents Folder", doc_dir)
            if files:
                return files

        elif tag == "browse_cwd":
            files = browse_directory_interactive(Path.cwd())
            if files:
                return files

        elif tag == "browse":
            if is_termux:
                start = Path.home() / "storage" if (Path.home() / "storage").exists() else Path.home()
            else:
                start = Path.home()
            files = browse_directory_interactive(start)
            if files:
                return files

        elif tag == "gui":
            files = open_native_gui_picker()
            if files:
                return files
            console.print("[dim]No files selected in dialog.[/dim]")

        elif tag == "manual":
            raw_path = Prompt.ask("\nEnter file or directory path").strip()
            if raw_path:
                resolved = current_platform.resolve_smart_path(raw_path)
                if resolved.exists():
                    return [resolved]
                console.print(f"[red]Path does not exist: {resolved}[/red]")
