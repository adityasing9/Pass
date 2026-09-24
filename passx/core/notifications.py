"""Cross-platform notification dispatcher for PASS"""
import logging
import os
import shutil
import subprocess
import sys

logger = logging.getLogger(__name__)


def notify_user(title: str, message: str) -> None:
    """Send system notification on Windows, Linux, and Android Termux"""
    # 1. Android Termux
    if shutil.which("termux-notification"):
        try:
            subprocess.run(
                ["termux-notification", "--title", title, "--content", message, "--priority", "high"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=3,
            )
            return
        except Exception:
            pass

    # 2. Linux notify-send
    if shutil.which("notify-send"):
        try:
            subprocess.run(
                ["notify-send", title, message],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=3,
            )
            return
        except Exception:
            pass

    # 3. Windows audio bell + PowerShell toast
    if sys.platform == "win32":
        try:
            import winsound
            winsound.MessageBeep(winsound.MB_ICONASTERISK)
        except Exception:
            pass

        # Try PowerShell BurntToast or balloon if available
        try:
            ps_script = (
                f"[reflection.assembly]::loadwithpartialname('System.Windows.Forms') | Out-Null; "
                f"$notify = New-Object System.Windows.Forms.NotifyIcon; "
                f"$notify.Icon = [System.Drawing.SystemIcons]::Information; "
                f"$notify.Visible = $True; "
                f"$notify.ShowBalloonTip(4000, '{title}', '{message}', 'Info')"
            )
            subprocess.Popen(
                ["powershell", "-NoProfile", "-Command", ps_script],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            pass
