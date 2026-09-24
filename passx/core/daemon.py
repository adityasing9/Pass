"""Persistent background daemon service manager for PASS"""
import os
import shutil
import signal
import subprocess
import sys
from pathlib import Path
from typing import Optional, Tuple


def get_daemon_paths(config_dir: Path) -> Tuple[Path, Path]:
    """Return (pid_file_path, log_file_path)"""
    pid_file = config_dir / "daemon.pid"
    log_file = config_dir / "daemon.log"
    return pid_file, log_file


def is_pid_alive(pid: int) -> bool:
    """Check if a process with given PID is currently active"""
    if pid <= 0:
        return False

    if sys.platform == "win32":
        try:
            import ctypes
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            STILL_ACTIVE = 259
            h = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, 0, pid)
            if not h:
                return False
            exit_code = ctypes.c_ulong()
            ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(exit_code))
            ctypes.windll.kernel32.CloseHandle(h)
            return exit_code.value == STILL_ACTIVE
        except Exception:
            # Fallback to tasklist
            try:
                out = subprocess.check_output(
                    ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                    text=True,
                    creationflags=0x08000000,
                )
                return str(pid) in out
            except Exception:
                return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


def start_daemon(config_dir: Path) -> Tuple[bool, str, Optional[int]]:
    """
    Launch PASS in background receive mode (detached from terminal).
    All incoming transfers from trusted/paired devices are accepted automatically.
    """
    pid_file, log_file = get_daemon_paths(config_dir)

    # Check if already running
    if pid_file.exists():
        try:
            pid = int(pid_file.read_text().strip())
            if is_pid_alive(pid):
                return False, f"PASS daemon is already running in background (PID: {pid})", pid
        except Exception:
            pass

    # Android Termux wake lock to prevent sleep
    if shutil.which("termux-wake-lock"):
        try:
            subprocess.run(["termux-wake-lock"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

    # Determine executable
    py_exec = sys.executable
    if sys.platform == "win32":
        pyw = Path(py_exec).with_name("pythonw.exe")
        if pyw.exists():
            py_exec = str(pyw)

    cmd = [py_exec, "-m", "passx", "receive", "--yes"]

    # Open log file
    log_fd = open(log_file, "a", encoding="utf-8")

    try:
        if sys.platform == "win32":
            # CREATE_NO_WINDOW (0x08000000) | DETACHED_PROCESS (0x00000008)
            flags = 0x08000000 | 0x00000008
            proc = subprocess.Popen(
                cmd,
                stdout=log_fd,
                stderr=log_fd,
                stdin=subprocess.DEVNULL,
                creationflags=flags,
                close_fds=True,
            )
        else:
            proc = subprocess.Popen(
                cmd,
                stdout=log_fd,
                stderr=log_fd,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
                close_fds=True,
            )

        # Save PID
        pid_file.write_text(str(proc.pid), encoding="utf-8")
        return True, "PASS background receiver started successfully", proc.pid
    except Exception as e:
        return False, f"Failed to start background daemon: {e}", None


def stop_daemon(config_dir: Path) -> Tuple[bool, str]:
    """Stop the running background PASS daemon"""
    pid_file, _ = get_daemon_paths(config_dir)

    if not pid_file.exists():
        return False, "PASS daemon is not running (no PID file found)"

    try:
        pid = int(pid_file.read_text().strip())
    except Exception:
        pid_file.unlink(missing_ok=True)
        return False, "Invalid PID file; removed"

    if not is_pid_alive(pid):
        pid_file.unlink(missing_ok=True)
        return False, f"PASS daemon (PID {pid}) was not running; cleaned up PID file"

    try:
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/F", "/PID", str(pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=0x08000000,
            )
        else:
            os.kill(pid, signal.SIGTERM)
    except Exception as e:
        return False, f"Error terminating daemon process {pid}: {e}"

    pid_file.unlink(missing_ok=True)

    # Release wake lock on Android
    if shutil.which("termux-wake-unlock"):
        try:
            subprocess.run(["termux-wake-unlock"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

    return True, f"PASS background receiver (PID {pid}) stopped"


def get_daemon_status(config_dir: Path) -> Tuple[bool, Optional[int], Path]:
    """Return (is_running, pid, log_file_path)"""
    pid_file, log_file = get_daemon_paths(config_dir)

    if not pid_file.exists():
        return False, None, log_file

    try:
        pid = int(pid_file.read_text().strip())
        if is_pid_alive(pid):
            return True, pid, log_file
        else:
            pid_file.unlink(missing_ok=True)
            return False, None, log_file
    except Exception:
        pid_file.unlink(missing_ok=True)
        return False, None, log_file
