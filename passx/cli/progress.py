"""Terminal progress display with live transfer speed and ETA"""
from typing import Optional
from rich.progress import (
    Progress,
    BarColumn,
    TextColumn,
    TimeRemainingColumn,
    DownloadColumn,
    TransferSpeedColumn,
    SpinnerColumn,
)


class TransferProgressTracker:
    """Manages Rich-based terminal progress display for file transfers"""

    def __init__(self, description: str = "Transferring"):
        self.description = description
        self.progress: Optional[Progress] = None
        self.task_id = None
        self._current_filename = ""

    def __enter__(self):
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.fields[filename]}"),
            BarColumn(bar_width=40),
            "[progress.percentage]{task.percentage:>3.0f}%",
            "•",
            DownloadColumn(),
            "•",
            TransferSpeedColumn(),
            "•",
            TimeRemainingColumn(),
        )
        self.progress.start()
        self.task_id = self.progress.add_task(
            self.description,
            total=0,
            filename="",
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.progress:
            self.progress.stop()

    def update(self, filename: str, transferred: int, total: int, speed: float, eta: float) -> None:
        """Update live progress bar"""
        if not self.progress or self.task_id is None:
            return

        display_name = filename if len(filename) <= 30 else "..." + filename[-27:]
        self.progress.update(
            self.task_id,
            total=total,
            completed=transferred,
            filename=display_name,
        )
