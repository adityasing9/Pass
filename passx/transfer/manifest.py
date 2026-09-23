"""Manifest generation for files and directories"""
import hashlib
import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Any, Union
from .sanitizer import sanitize_relative_path


def compute_file_sha256(file_path: Path, chunk_size: int = 256 * 1024) -> str:
    """Stream file and compute SHA-256 hex digest without loading whole file into memory"""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


@dataclass
class ManifestItem:
    """Represents a single file within a transfer manifest"""
    index: int
    source_path: Path
    relative_path: str
    size: int
    sha256: str = ""

    def to_wire_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "relative_path": self.relative_path,
            "size": self.size,
            "sha256": self.sha256,
        }


class TransferManifest:
    """Collection of files scheduled for transfer"""

    def __init__(self, transfer_id: str, items: List[ManifestItem]):
        self.transfer_id = transfer_id
        self.items = items
        self.total_bytes = sum(item.size for item in items)
        self.file_count = len(items)

    def to_wire_dict(self) -> Dict[str, Any]:
        return {
            "action": "TRANSFER_MANIFEST",
            "transfer_id": self.transfer_id,
            "file_count": self.file_count,
            "total_bytes": self.total_bytes,
            "files": [item.to_wire_dict() for item in self.items],
        }

    @classmethod
    def from_wire_dict(cls, data: Dict[str, Any]) -> "TransferManifest":
        transfer_id = data.get("transfer_id", str(uuid.uuid4()))
        raw_files = data.get("files", [])
        items = []
        for f in raw_files:
            items.append(
                ManifestItem(
                    index=int(f["index"]),
                    source_path=Path(""),
                    relative_path=sanitize_relative_path(f["relative_path"]),
                    size=int(f["size"]),
                    sha256=f.get("sha256", ""),
                )
            )
        return cls(transfer_id=transfer_id, items=items)


def build_manifest_from_paths(paths: List[Union[str, Path]], precompute_hash: bool = False) -> TransferManifest:
    """
    Build a TransferManifest from a list of file or directory paths.
    Recursively scans directories and preserves relative hierarchy.
    """
    items: List[ManifestItem] = []
    file_index = 0

    for raw_p in paths:
        p = Path(raw_p).resolve()
        if not p.exists():
            raise FileNotFoundError(f"Source path does not exist: {p}")

        if p.is_file():
            rel_name = sanitize_relative_path(p.name)
            size = p.stat().st_size
            sha256_val = compute_file_sha256(p) if precompute_hash else ""
            items.append(
                ManifestItem(
                    index=file_index,
                    source_path=p,
                    relative_path=rel_name,
                    size=size,
                    sha256=sha256_val,
                )
            )
            file_index += 1

        elif p.is_dir():
            dir_name = p.name
            for root, _, files in os.walk(p):
                for f in sorted(files):
                    full_file = Path(root) / f
                    rel_to_dir = full_file.relative_to(p)
                    # Include top-level directory name so target receives "dir_name/sub/file"
                    combined_rel = f"{dir_name}/{rel_to_dir.as_posix()}"
                    safe_rel = sanitize_relative_path(combined_rel)
                    size = full_file.stat().st_size
                    sha256_val = compute_file_sha256(full_file) if precompute_hash else ""
                    items.append(
                        ManifestItem(
                            index=file_index,
                            source_path=full_file,
                            relative_path=safe_rel,
                            size=size,
                            sha256=sha256_val,
                        )
                    )
                    file_index += 1

    return TransferManifest(transfer_id=str(uuid.uuid4()), items=items)
