"""Resumable transfer manager handling partial files and offset negotiation"""
import json
import os
import time
from pathlib import Path
from typing import Dict, Optional, Tuple


class ResumeManager:
    """Manages .pass-partial files and offset negotiation for interrupted transfers"""

    PARTIAL_EXT = ".pass-partial"
    META_EXT = ".pass-meta"

    @classmethod
    def get_partial_paths(cls, target_file: Path) -> Tuple[Path, Path]:
        """Return (partial_file_path, meta_file_path)"""
        partial_path = target_file.with_name(target_file.name + cls.PARTIAL_EXT)
        meta_path = target_file.with_name(target_file.name + cls.META_EXT)
        return partial_path, meta_path

    @classmethod
    def get_resume_offset(cls, target_file: Path, expected_total_size: int) -> int:
        """
        Check if a valid partial transfer exists for target_file.
        Returns the byte offset to resume from (0 if cannot resume).
        """
        partial_path, meta_path = cls.get_partial_paths(target_file)
        if not partial_path.exists() or not meta_path.exists():
            return 0

        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)

            if meta.get("total_size") != expected_total_size:
                # Size changed or different file, cannot resume
                return 0

            actual_partial_size = partial_path.stat().st_size
            if actual_partial_size >= expected_total_size:
                # File is already complete or oversized
                return 0

            return actual_partial_size
        except Exception:
            return 0

    @classmethod
    def save_checkpoint(cls, target_file: Path, transfer_id: str, relative_path: str, total_size: int, received_bytes: int) -> None:
        """Update sidecar metadata checkpoint"""
        _, meta_path = cls.get_partial_paths(target_file)
        data = {
            "transfer_id": transfer_id,
            "relative_path": relative_path,
            "total_size": total_size,
            "received_bytes": received_bytes,
            "last_updated": time.time(),
        }
        temp_meta = meta_path.with_suffix(".tmp")
        try:
            with open(temp_meta, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            temp_meta.replace(meta_path)
        except Exception:
            pass

    @classmethod
    def finalize_transfer(cls, target_file: Path) -> Path:
        """Atomically rename .pass-partial to final target and remove meta"""
        partial_path, meta_path = cls.get_partial_paths(target_file)
        if not partial_path.exists():
            raise FileNotFoundError(f"Partial file does not exist: {partial_path}")

        # Ensure parent exists
        target_file.parent.mkdir(parents=True, exist_ok=True)
        if target_file.exists():
            target_file.unlink()

        partial_path.replace(target_file)
        if meta_path.exists():
            try:
                meta_path.unlink()
            except Exception:
                pass
        return target_file

    @classmethod
    def cleanup_partial(cls, target_file: Path) -> None:
        """Remove partial and meta files upon failure or cancellation"""
        partial_path, meta_path = cls.get_partial_paths(target_file)
        for p in (partial_path, meta_path):
            if p.exists():
                try:
                    p.unlink()
                except Exception:
                    pass
