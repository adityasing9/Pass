"""Security-critical path sanitizer to prevent path traversal and arbitrary file write"""
import os
import re
from pathlib import Path
from typing import Tuple

WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
}


class SecurityError(Exception):
    """Raised when an unsafe or malicious path is detected"""
    pass


def sanitize_relative_path(raw_path: str) -> str:
    """
    Sanitize incoming relative path from peer.
    Ensures no directory traversal, no null bytes, no drive letters, and no reserved names.
    Returns normalized forward-slash relative path.
    """
    if not raw_path or not raw_path.strip():
        raise SecurityError("File path cannot be empty")

    # Reject null bytes
    if "\0" in raw_path:
        raise SecurityError("Path contains null byte")

    # Normalize slashes
    normalized = raw_path.replace("\\", "/").strip()

    # Strip leading drive letters (e.g. C:, D:)
    if len(normalized) >= 2 and normalized[1] == ":" and normalized[0].isalpha():
        normalized = normalized[2:]

    # Strip leading slashes
    normalized = normalized.lstrip("/")

    # Split into components
    parts = normalized.split("/")
    safe_parts = []

    for part in parts:
        part = part.strip()
        if not part or part == ".":
            continue
        if part == "..":
            raise SecurityError(f"Directory traversal detected in path: '{raw_path}'")

        # Check Windows reserved names (e.g., 'CON', 'NUL.txt', 'aux.dat')
        base_name = part.split(".")[0].upper()
        if base_name in WINDOWS_RESERVED_NAMES:
            raise SecurityError(f"Prohibited reserved filename detected: '{part}'")

        # Sanitize prohibited characters on Windows (< > : " | ? *)
        if any(c in part for c in '<>:"|?*'):
            raise SecurityError(f"Prohibited characters detected in path component: '{part}'")

        safe_parts.append(part)

    if not safe_parts:
        raise SecurityError(f"Sanitization resulted in an empty path for: '{raw_path}'")

    return "/".join(safe_parts)


def get_safe_destination_path(base_download_dir: Path, raw_relative_path: str) -> Path:
    """
    Combines base_download_dir with sanitized relative path.
    Cryptographically verifies that the resolved path stays strictly inside base_download_dir.
    """
    safe_rel = sanitize_relative_path(raw_relative_path)
    base_resolved = Path(os.path.realpath(str(base_download_dir)))
    target_candidate = base_resolved / Path(safe_rel)
    target_resolved = Path(os.path.realpath(str(target_candidate)))

    # Ensure target_resolved starts with base_resolved
    try:
        target_resolved.relative_to(base_resolved)
    except ValueError:
        raise SecurityError(f"Path escape detected! Candidate '{target_resolved}' is outside '{base_resolved}'")

    return target_candidate


def resolve_collision_path(target_path: Path) -> Path:
    """If target_path already exists, append ' (1)', ' (2)', etc. to prevent overwriting"""
    if not target_path.exists():
        return target_path

    parent = target_path.parent
    stem = target_path.stem
    suffix = target_path.suffix

    counter = 1
    while True:
        candidate = parent / f"{stem} ({counter}){suffix}"
        if not candidate.exists():
            return candidate
        counter += 1
