"""Security tests for path traversal, absolute path injection, and reserved names"""
import os
import tempfile
from pathlib import Path
import pytest
from passx.transfer.sanitizer import (
    sanitize_relative_path,
    get_safe_destination_path,
    resolve_collision_path,
    SecurityError,
)


def test_sanitize_valid_paths():
    assert sanitize_relative_path("file.txt") == "file.txt"
    assert sanitize_relative_path("sub/folder/file.pdf") == "sub/folder/file.pdf"
    assert sanitize_relative_path("sub\\folder\\file.pdf") == "sub/folder/file.pdf"
    assert sanitize_relative_path("/leading/slash.txt") == "leading/slash.txt"
    assert sanitize_relative_path("C:/windows/path.txt") == "windows/path.txt"


def test_sanitize_traversal_attacks():
    malicious = [
        "../secret.txt",
        "../../etc/passwd",
        "folder/../../outside.txt",
        "..\\..\\windows\\system32\\cmd.exe",
        "/../root.txt",
        "foo/bar/../../../evil",
    ]
    for path in malicious:
        with pytest.raises(SecurityError):
            sanitize_relative_path(path)


def test_sanitize_null_byte_attacks():
    with pytest.raises(SecurityError):
        sanitize_relative_path("file.txt\0.exe")


def test_sanitize_reserved_windows_names():
    reserved = ["CON", "prn", "aux.txt", "nul.dat", "COM1", "com3.log", "LPT2"]
    for name in reserved:
        with pytest.raises(SecurityError):
            sanitize_relative_path(name)


def test_safe_destination_containment():
    with tempfile.TemporaryDirectory() as tmp_dir:
        base = Path(tmp_dir)
        safe = get_safe_destination_path(base, "docs/manual.pdf")
        assert str(safe.resolve()).startswith(str(base.resolve()))


def test_collision_path_resolution():
    with tempfile.TemporaryDirectory() as tmp_dir:
        base = Path(tmp_dir)
        original = base / "test.txt"
        original.write_text("hello")

        resolved = resolve_collision_path(original)
        assert resolved.name == "test (1).txt"

        resolved.write_text("hello 2")
        resolved2 = resolve_collision_path(original)
        assert resolved2.name == "test (2).txt"
