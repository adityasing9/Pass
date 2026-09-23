"""Tests for resumable file transfer management"""
import tempfile
from pathlib import Path
from passx.transfer.resume import ResumeManager


def test_resume_offset_and_finalization():
    with tempfile.TemporaryDirectory() as tmp_dir:
        base = Path(tmp_dir)
        target = base / "large_file.bin"
        partial, meta = ResumeManager.get_partial_paths(target)

        # No partial initially
        assert ResumeManager.get_resume_offset(target, expected_total_size=1000) == 0

        # Create simulated interrupted partial file (400 bytes written out of 1000)
        partial.write_bytes(b"A" * 400)
        ResumeManager.save_checkpoint(target, "tx-1", "large_file.bin", total_size=1000, received_bytes=400)

        # Offset should be 400
        offset = ResumeManager.get_resume_offset(target, expected_total_size=1000)
        assert offset == 400

        # If expected size does not match, offset must be 0 (cannot resume different file)
        assert ResumeManager.get_resume_offset(target, expected_total_size=2000) == 0

        # Simulate completion
        with open(partial, "ab") as f:
            f.write(b"B" * 600)

        assert partial.stat().st_size == 1000
        final_file = ResumeManager.finalize_transfer(target)
        assert final_file.exists()
        assert not partial.exists()
        assert not meta.exists()
        assert final_file.stat().st_size == 1000
