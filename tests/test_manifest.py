"""Tests for transfer manifest generation"""
import tempfile
from pathlib import Path
from passx.transfer.manifest import build_manifest_from_paths, compute_file_sha256, TransferManifest


def test_single_file_manifest():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        test_file = tmp_path / "hello.txt"
        test_file.write_text("Hello PASS!")

        manifest = build_manifest_from_paths([test_file], precompute_hash=True)
        assert manifest.file_count == 1
        assert manifest.total_bytes == len("Hello PASS!")
        assert manifest.items[0].relative_path == "hello.txt"
        assert len(manifest.items[0].sha256) == 64


def test_directory_manifest():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        project_dir = tmp_path / "my_project"
        project_dir.mkdir()
        (project_dir / "root_file.txt").write_text("root")
        sub_dir = project_dir / "subdir"
        sub_dir.mkdir()
        (sub_dir / "child.txt").write_text("child")

        manifest = build_manifest_from_paths([project_dir])
        assert manifest.file_count == 2
        rel_paths = {item.relative_path for item in manifest.items}
        assert "my_project/root_file.txt" in rel_paths
        assert "my_project/subdir/child.txt" in rel_paths


def test_wire_serialization():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        f1 = tmp_path / "f1.bin"
        f1.write_bytes(b"\x00\x01\x02")

        manifest = build_manifest_from_paths([f1])
        wire = manifest.to_wire_dict()

        rebuilt = TransferManifest.from_wire_dict(wire)
        assert rebuilt.file_count == 1
        assert rebuilt.total_bytes == 3
        assert rebuilt.items[0].relative_path == "f1.bin"
