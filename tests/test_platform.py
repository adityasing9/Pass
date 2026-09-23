"""Tests for platform adapters and smart path shortcuts"""
import tempfile
from pathlib import Path
from passx.platform.termux import TermuxPlatform
from passx.platform.windows import WindowsPlatform


def test_windows_smart_path():
    win = WindowsPlatform()
    # Test dt: prefix
    dt_path = win.resolve_smart_path("dt:my_file.txt")
    assert str(win.get_default_download_dir()) in str(dt_path)

    # Test dl: prefix
    dl_path = win.resolve_smart_path("dl:report.pdf")
    assert "Downloads" in str(dl_path)


def test_termux_smart_path():
    termux = TermuxPlatform()
    # Test cam: prefix
    cam_path = termux.resolve_smart_path("cam:photo.jpg")
    assert "Camera" in str(cam_path)

    # Test dl: prefix
    dl_path = termux.resolve_smart_path("dl:archive.zip")
    assert "downloads" in str(dl_path)
